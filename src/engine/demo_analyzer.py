"""Demo instant mode — multi-media batch → WhatsApp-ready report.

Used by implementations flagged with `onboarding_config.demo_mode=true`.

Modes (via onboarding_config.demo_batch_mode):
  - "instant"   → single photo processed immediately (legacy)
  - "explicit"  → user sends N files, types trigger word → one consolidated report
  - "debounce"  → auto-process after a timer expires (not implemented yet)

Does NOT write to visit_reports — demo output is ephemeral.
Content safety still runs in parallel via the preprocessor worker.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog
from anthropic import AsyncAnthropic

from src.config.settings import settings
from src.engine.ai_semaphore import get_ai_semaphore
from src.engine.config_loader import ImplementationConfig
from src.engine.content_gate import (
    ContentGateResult,
    classify_session_images,
)
from src.engine.vision import analyze_from_storage, analyze_image
from src.engine.transcriber import transcribe, transcribe_bytes
from src.engine.video import process_video

logger = structlog.get_logger(__name__)

HAIKU = "claude-haiku-4-5-20251001"

# Default soft caps for analysis (most recent are kept). These are now the
# fallback when an implementation doesn't override them via onboarding_config:
#   demo_max_images_per_batch
#   demo_max_audios_per_batch
#   demo_max_videos_per_batch
# Each project can tune its own limits from the backoffice.
DEFAULT_MAX_IMAGES_PER_BATCH = 8
DEFAULT_MAX_AUDIOS_PER_BATCH = 4
DEFAULT_MAX_VIDEOS_PER_BATCH = 2  # videos are expensive (ffmpeg + vision + whisper)
# Backwards-compat aliases — DO NOT use in new code, kept only so any external
# importer (tests, old branches) doesn't break. Will be removed in a later sprint.
MAX_IMAGES_PER_BATCH = DEFAULT_MAX_IMAGES_PER_BATCH
MAX_AUDIOS_PER_BATCH = DEFAULT_MAX_AUDIOS_PER_BATCH
MAX_VIDEOS_PER_BATCH = DEFAULT_MAX_VIDEOS_PER_BATCH


def get_demo_caps(impl_config: "ImplementationConfig") -> tuple[int, int, int]:
    """Resolve the per-project demo batch caps from onboarding_config.

    Returns (max_images, max_audios, max_videos). Falls back to DEFAULT_*
    when a key is missing or invalid. Always returns at least 1 image,
    0 audios, 0 videos. No upper hard cap — the analyzer trusts the
    configured values; abuse protection lives at a higher layer in the
    webhook (ABUSE_CAP_*).
    """
    ob = impl_config.onboarding_config or {}

    def _read(key: str, default: int, minimum: int = 0) -> int:
        raw = ob.get(key)
        if raw is None or raw == "":
            return default
        try:
            n = int(raw)
        except (TypeError, ValueError):
            return default
        return max(n, minimum)

    return (
        _read("demo_max_images_per_batch", DEFAULT_MAX_IMAGES_PER_BATCH, minimum=1),
        _read("demo_max_audios_per_batch", DEFAULT_MAX_AUDIOS_PER_BATCH, minimum=0),
        _read("demo_max_videos_per_batch", DEFAULT_MAX_VIDEOS_PER_BATCH, minimum=0),
    )

# Source types that Vision returns on the first line of each demo description.
# Any unknown value defaults to INCIERTO.
VALID_SOURCE_TYPES = {"CAMPO", "CAPTURA_DIGITAL", "MIXTO", "INCIERTO"}


def _parse_source_tag(description: str) -> tuple[str, str]:
    """Extract a 'FUENTE=...' marker from the first line of a Vision
    description and return (source_type, cleaned_description).

    If the marker is missing or unrecognized, returns ('INCIERTO', original).
    Robust to the LLM occasionally ignoring the instruction or adding
    trailing whitespace / punctuation.
    """
    if not description:
        return "INCIERTO", description
    lines = description.splitlines()
    if not lines:
        return "INCIERTO", description
    first = lines[0].strip()
    # Accept variants: "FUENTE=CAMPO", "FUENTE= CAMPO", "FUENTE: CAMPO"
    if first.upper().startswith("FUENTE"):
        after_eq = first.split("=", 1)[-1] if "=" in first else first.split(":", 1)[-1] if ":" in first else ""
        token = after_eq.strip().split()[0].strip(".,;:").upper() if after_eq.strip() else ""
        if token in VALID_SOURCE_TYPES:
            rest = "\n".join(lines[1:]).lstrip()
            return token, rest
    return "INCIERTO", description

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=60.0)
    return _client


SYNTHESIS_SYSTEM = """Eres un analista senior de {industry} que entrega insights accionables vía WhatsApp.

Recibes el análisis de UNA O VARIAS fotos de campo (del mismo punto o de puntos relacionados), junto con transcripciones de audios y notas del usuario si las hay. Tu trabajo es producir UN SOLO mini-reporte de WhatsApp de 400-650 palabras, en español neutro, con este formato EXACTO:

*📊 Análisis — {impl_name}*
_{location_line}_
━━━━━━━━━━━━━━━━━━━━

*Resumen ejecutivo*
[2-3 líneas integrando lo que muestran TODAS las fotos y lo que dijo el usuario. Principal hallazgo accionable.]

*🏷️ Hallazgos clave*
• [hallazgo específico con datos — cita la foto si aplica ("foto 2: ...")]
• [hallazgo específico con datos]
• [hallazgo específico con datos]
• [4to opcional si las fotos muestran cosas distintas]

*⚠️ Alertas*
[Solo si hay algo crítico. 🔴 crítico, 🟡 atención. OMITE la sección entera si no hay nada destacable.]

*💡 Oportunidades*
1. [acción concreta ejecutable hoy]
2. [acción concreta ejecutable hoy]
3. [acción concreta ejecutable hoy]

━━━━━━━━━━━━━━━━━━━━
_Reporte generado automáticamente desde {asset_summary}._

Reglas estrictas:
- Formato WhatsApp: *bold*, _italic_, • bullets, 1. listas numeradas. NADA de markdown tipo **bold** ni [link](url).
- Mercado: {country_name}. Usa marcas, moneda local y cadenas retail de ese país cuando sea relevante.
- Si no hay precios visibles, NO los inventes. Prefiere "precios no visibles" a fabricar cifras.
- Sé específico: "Rexona 38% share" > "marca líder". "Nivel ojos vacío" > "exhibición mejorable".
- Si hay múltiples fotos del mismo punto, consolida (no repitas hallazgos). Si muestran puntos distintos, agrupa.
- Si el usuario dio contexto por audio/texto, intégralo naturalmente — no lo repitas literal.
- Cero disclaimers, cero hedging, ve directo al insight.
- Si las fotos NO son relevantes al caso (selfies, paisajes), entrega un reporte corto explicando qué sí se ve e invita a enviar fotos del punto de venta.

Tipo de fuente de cada foto (CRÍTICO):
- Cada foto/video trae entre corchetes el tipo de fuente: [fuente: CAMPO], [fuente: CAPTURA_DIGITAL], [fuente: MIXTO] o [fuente: INCIERTO].
- *CAMPO* = foto tomada en el mundo real (valla física, tienda, fachada, obra, producto en anaquel, folleto impreso). Representa *presencia física* en el mercado.
- *CAPTURA_DIGITAL* = screenshot de red social, web, app, anuncio online, publicación de Instagram/Facebook/TikTok/LinkedIn, captura de pantalla. Representa *canal digital* de la marca.
- *MIXTO* = foto de una pantalla mostrando contenido digital, o contenido ambiguo. Tratar como CAPTURA_DIGITAL si el contenido es claramente publicitario.
- *INCIERTO* = no se pudo determinar; trata la foto de forma general.

REGLA NO NEGOCIABLE: *NO mezcles* hallazgos de CAMPO con CAPTURA_DIGITAL como si fueran del mismo plano. Son canales diferentes con implicancias estratégicas diferentes:
- Los hallazgos de CAMPO responden a "¿quién está físicamente presente en el territorio?" (presencia en puntos de venta, share of shelf físico, vallas publicitarias, material POP).
- Los hallazgos de CAPTURA_DIGITAL responden a "¿qué narrativa está empujando la marca en canales digitales?" (posicionamiento, alianzas anunciadas, tono, engagement visible).

Cuando haya AMBOS tipos en el batch, estructura los hallazgos con etiquetas explícitas. Ejemplo:
- _*Presencia física (CAMPO):* Liberty domina Parque La Sabana con 3 vallas de fibra simétrica…_
- _*Canal digital (CAPTURA_DIGITAL):* Liberty y Kólbi anuncian alianzas Starlink en Instagram, apuntando a mercados rurales…_

Cuando haya SOLO un tipo (ej: todos CAMPO o todos CAPTURA_DIGITAL), no fuerces la división — hazlo natural como siempre."""


async def generate_demo_report(
    files: list[dict[str, Any]],
    impl_config: ImplementationConfig,
    country_name: str | None,
    location_hint: str | None = None,
    text_context: str | None = None,
) -> str:
    """Generate a WhatsApp-ready demo report from a batch of session files.

    Args:
        files: List of session_file dicts (filename, storage_path, type, ...).
        impl_config: Implementation config (used for name, industry, vision prompt).
        country_name: Human-readable country from phone prefix, e.g. "Colombia".
        location_hint: Optional location label (address/coords) if shared.
        text_context: Optional user-typed context to include.

    Returns:
        Markdown string ready to send via WhatsApp.

    Raises:
        RuntimeError on hard failure — caller must catch.
    """
    start = time.time()

    # Per-project caps from onboarding_config (fallback to DEFAULT_*)
    max_images, max_audios, max_videos = get_demo_caps(impl_config)

    # Split files by type and apply soft caps (keep most recent)
    images = [f for f in files if f.get("type") == "image" and f.get("storage_path")]
    videos = [f for f in files if f.get("type") == "video" and f.get("storage_path")]
    audios = [f for f in files if f.get("type") == "audio" and f.get("storage_path")]

    if len(images) > max_images:
        logger.info("demo_batch_images_capped", total=len(images), kept=max_images, impl=impl_config.id)
        images = images[-max_images:]
    if len(videos) > max_videos:
        logger.info("demo_batch_videos_capped", total=len(videos), kept=max_videos, impl=impl_config.id)
        videos = videos[-max_videos:]
    if len(audios) > max_audios:
        audios = audios[-max_audios:]

    if not images and not videos:
        raise RuntimeError("no_visual_content")

    # ── Content gate: filter out non-retail images before vision ──
    # Reads preprocessor classification (content_category/blocked/flagged)
    # from session_files, runs inline Haiku classification for any file
    # missing a cached verdict. Videos bypass the gate (see content_gate.py).
    gate_result: ContentGateResult = await classify_session_images(images)
    if gate_result.decision == "refuse" and not videos:
        # All images rejected and no videos to fall back on — raise a
        # specific error so the caller can send the gate's refusal message.
        logger.info("demo_content_gate_refused", impl=impl_config.id,
                    excluded=len(gate_result.excluded_verdicts))
        err = RuntimeError("content_gate_refused")
        err.user_message = gate_result.refusal_message()  # attach for caller
        raise err
    # Replace the images list with the allowed subset. `gate_result` keeps
    # track of the excluded files so we can mention them in the final report.
    if gate_result.verdicts:
        images = gate_result.allowed_files

    # Build vision context (common to all image analyses)
    context_parts: list[str] = []
    if country_name:
        context_parts.append(f"País: {country_name}")
    if location_hint:
        context_parts.append(f"Ubicación: {location_hint}")
    if text_context:
        context_parts.append(f"El usuario escribió: \"{text_context}\"")
    vision_context = " | ".join(context_parts)

    # Step 1a: Process videos inline — extract first frame + transcribe audio track.
    # Each video contributes one "image" to the vision pool and one transcript.
    video_frame_bytes: list[tuple[bytes, str]] = []  # (frame_bytes, label)
    video_transcripts: list[str] = []
    for i, vid in enumerate(videos):
        try:
            vr = await process_video(vid["storage_path"])
            if vr.frames:
                # Use the first frame as the representative image
                video_frame_bytes.append((vr.frames[0], f"Video {i + 1}"))
            if vr.audio_bytes:
                try:
                    t = await transcribe_bytes(vr.audio_bytes, f"video_{i + 1}.ogg")
                    if t and t.strip():
                        video_transcripts.append(f"**Video {i + 1} (audio)**: {t.strip()}")
                except Exception as e:
                    logger.warning("demo_video_audio_failed", idx=i, error=str(e)[:100])
        except Exception as e:
            logger.warning("demo_video_process_failed", idx=i, error=str(e)[:100])

    # Step 1b: Parallel vision analysis — stored images + in-memory video frames.
    # Demo mode: ask Vision to prefix each response with a FUENTE=... marker
    # so we can distinguish in-site photos from screenshots of social/web
    # content and tag them structurally for the synthesis prompt.
    total_visual = len(images) + len(video_frame_bytes)
    storage_image_tasks = [
        analyze_from_storage(
            storage_path=img["storage_path"],
            context=vision_context,
            implementation=impl_config.id,
            demo_mode=True,
            image_index=i,
            image_total=total_visual,
        )
        for i, img in enumerate(images)
    ]
    frame_tasks = [
        analyze_image(
            image_bytes=frame_bytes,
            context=vision_context,
            implementation=impl_config.id,
            demo_mode=True,
            image_index=len(images) + i,
            image_total=total_visual,
        )
        for i, (frame_bytes, _label) in enumerate(video_frame_bytes)
    ]
    # Step 1c: Parallel audio transcription for standalone audio files
    audio_tasks = [transcribe(a["storage_path"]) for a in audios]

    all_results = await asyncio.gather(
        *storage_image_tasks, *frame_tasks, *audio_tasks, return_exceptions=True
    )
    n_stored = len(storage_image_tasks)
    n_frames = len(frame_tasks)
    stored_results = all_results[:n_stored]
    frame_results = all_results[n_stored : n_stored + n_frames]
    audio_results = all_results[n_stored + n_frames :]

    # Collect successful descriptions. Each entry carries:
    #   media_kind: "photo" | "video" (for asset_summary counting)
    #   source_type: CAMPO | CAPTURA_DIGITAL | MIXTO | INCIERTO (from Vision)
    #   text: formatted description prefixed with label + [fuente: X]
    tagged_descriptions: list[tuple[str, str, str]] = []
    for i, result in enumerate(stored_results):
        if isinstance(result, Exception) or (isinstance(result, str) and result.startswith("[Error")):
            logger.warning("demo_image_analysis_failed", idx=i, error=str(result)[:100])
            continue
        source_type, cleaned = _parse_source_tag(result)
        logger.info("vision_source_tag_parsed", idx=i, source_type=source_type, kind="photo")
        label = f"**Foto {i + 1}** ({images[i].get('filename', 'unknown')}) [fuente: {source_type}]:\n{cleaned}"
        tagged_descriptions.append(("photo", source_type, label))

    for i, result in enumerate(frame_results):
        video_label = video_frame_bytes[i][1]
        if isinstance(result, Exception) or (isinstance(result, str) and result.startswith("[Error")):
            logger.warning("demo_video_frame_analysis_failed", idx=i, error=str(result)[:100])
            continue
        source_type, cleaned = _parse_source_tag(result)
        logger.info("vision_source_tag_parsed", idx=i, source_type=source_type, kind="video")
        label = f"**{video_label}** (primer frame) [fuente: {source_type}]:\n{cleaned}"
        tagged_descriptions.append(("video", source_type, label))

    if not tagged_descriptions:
        raise RuntimeError("all_visual_content_failed")

    descriptions = [text for _, _, text in tagged_descriptions]
    n_photos = sum(1 for kind, _, _ in tagged_descriptions if kind == "photo")
    n_video_frames = sum(1 for kind, _, _ in tagged_descriptions if kind == "video")
    # Source-type counts across photos+videos (for asset_summary + synthesis hint)
    source_counts: dict[str, int] = {}
    for _kind, source_type, _ in tagged_descriptions:
        source_counts[source_type] = source_counts.get(source_type, 0) + 1

    transcripts: list[str] = list(video_transcripts)
    for i, result in enumerate(audio_results):
        if isinstance(result, Exception):
            logger.warning("demo_audio_transcribe_failed", idx=i, error=str(result)[:100])
            continue
        if isinstance(result, str) and result.strip():
            transcripts.append(f"**Audio {i + 1}**: {result.strip()}")

    # Step 3: Synthesize consolidated report
    # Prefer the richer per-source breakdown when the batch mixes CAMPO and
    # CAPTURA_DIGITAL — otherwise fall back to the plain "N fotos" summary.
    n_campo = source_counts.get("CAMPO", 0)
    n_digital = source_counts.get("CAPTURA_DIGITAL", 0) + source_counts.get("MIXTO", 0)
    n_incierto = source_counts.get("INCIERTO", 0)
    has_meaningful_mix = n_campo > 0 and n_digital > 0

    asset_pieces: list[str] = []
    if has_meaningful_mix:
        if n_campo:
            asset_pieces.append(f"{n_campo} foto{'s' if n_campo != 1 else ''} de campo")
        if n_digital:
            asset_pieces.append(f"{n_digital} captura{'s' if n_digital != 1 else ''} de redes sociales")
        if n_incierto:
            asset_pieces.append(f"{n_incierto} foto{'s' if n_incierto != 1 else ''}")
    else:
        if n_photos:
            asset_pieces.append(f"{n_photos} foto{'s' if n_photos != 1 else ''}")
        if n_video_frames:
            asset_pieces.append(f"{n_video_frames} video{'s' if n_video_frames != 1 else ''}")
    if transcripts:
        asset_pieces.append(f"{len(transcripts)} audio{'s' if len(transcripts) != 1 else ''}")
    asset_summary = " y ".join(asset_pieces) or "tu material"

    location_line = location_hint or (f"Mercado: {country_name}" if country_name else "Análisis de campo")

    system = SYNTHESIS_SYSTEM.format(
        industry=impl_config.industry or "retail y campo",
        impl_name=impl_config.name,
        location_line=location_line,
        country_name=country_name or "Latinoamérica",
        asset_summary=asset_summary,
    )

    user_msg_parts = ["Material recibido para analizar:\n"]
    user_msg_parts.append("\n\n".join(descriptions))
    if transcripts:
        user_msg_parts.append("\n\nAudios del usuario:\n" + "\n".join(transcripts))
    if text_context:
        user_msg_parts.append(f"\n\nTexto adicional del usuario: \"{text_context}\"")
    exclusion_note = gate_result.exclusion_note_for_prompt()
    if exclusion_note:
        user_msg_parts.append(f"\n\n{exclusion_note}")
    user_msg_parts.append(
        "\n\nGenera el mini-reporte WhatsApp siguiendo EXACTAMENTE el formato del system prompt. "
        "Integra los hallazgos de TODAS las fotos en un solo análisis consolidado."
    )
    user_msg = "".join(user_msg_parts)

    try:
        async with get_ai_semaphore():
            client = _get_client()
            message = await client.messages.create(
                model=HAIKU,
                max_tokens=1800,
                system=system,
                messages=[{"role": "user", "content": user_msg}],
            )
    except Exception as e:
        raise RuntimeError(f"synthesis_failed: {e}") from e

    report = message.content[0].text.strip()

    elapsed_ms = int((time.time() - start) * 1000)
    logger.info(
        "demo_batch_report_generated",
        impl=impl_config.id,
        photos=n_photos,
        video_frames=n_video_frames,
        audios=len(transcripts),
        images_failed=len(images) - n_photos,
        chars=len(report),
        elapsed_ms=elapsed_ms,
        country=country_name,
        has_location=bool(location_hint),
        source_campo=source_counts.get("CAMPO", 0),
        source_digital=source_counts.get("CAPTURA_DIGITAL", 0),
        source_mixto=source_counts.get("MIXTO", 0),
        source_incierto=source_counts.get("INCIERTO", 0),
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens,
    )
    return report


async def generate_single_photo_demo_report(
    storage_path: str,
    impl_config: ImplementationConfig,
    country_name: str | None,
    audio_context: str | None = None,
    location_hint: str | None = None,
) -> str:
    """Legacy wrapper for instant mode — one photo → one report.

    Kept for backward compat and for `demo_batch_mode="instant"`.
    Internally delegates to generate_demo_report with a single-image batch.
    """
    fake_file = {
        "filename": storage_path.rsplit("/", 1)[-1],
        "storage_path": storage_path,
        "type": "image",
    }
    return await generate_demo_report(
        files=[fake_file],
        impl_config=impl_config,
        country_name=country_name,
        location_hint=location_hint,
        text_context=audio_context,  # audio_context treated as text hint in legacy path
    )
