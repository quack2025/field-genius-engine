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
from src.engine.vision import analyze_from_storage
from src.engine.transcriber import transcribe

logger = structlog.get_logger(__name__)

HAIKU = "claude-haiku-4-5-20251001"

# Hard caps to keep latency + cost reasonable in demo mode
MAX_IMAGES_PER_BATCH = 8
MAX_AUDIOS_PER_BATCH = 4

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
- Si las fotos NO son relevantes al caso (selfies, paisajes), entrega un reporte corto explicando qué sí se ve e invita a enviar fotos del punto de venta."""


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

    # Split files by type and apply caps
    images = [f for f in files if f.get("type") == "image" and f.get("storage_path")]
    audios = [f for f in files if f.get("type") == "audio" and f.get("storage_path")]

    if len(images) > MAX_IMAGES_PER_BATCH:
        logger.info("demo_batch_images_capped", total=len(images), kept=MAX_IMAGES_PER_BATCH)
        images = images[-MAX_IMAGES_PER_BATCH:]  # Keep most recent
    if len(audios) > MAX_AUDIOS_PER_BATCH:
        audios = audios[-MAX_AUDIOS_PER_BATCH:]

    if not images:
        raise RuntimeError("no_images_in_batch")

    # Build vision context (common to all image analyses)
    context_parts: list[str] = []
    if country_name:
        context_parts.append(f"País: {country_name}")
    if location_hint:
        context_parts.append(f"Ubicación: {location_hint}")
    if text_context:
        context_parts.append(f"El usuario escribió: \"{text_context}\"")
    vision_context = " | ".join(context_parts)

    # Step 1: Parallel vision analysis on all images
    image_tasks = [
        analyze_from_storage(
            storage_path=img["storage_path"],
            context=vision_context,
            implementation=impl_config.id,
        )
        for img in images
    ]
    # Step 2: Parallel audio transcription
    audio_tasks = [transcribe(a["storage_path"]) for a in audios]

    all_results = await asyncio.gather(
        *image_tasks, *audio_tasks, return_exceptions=True
    )
    image_results = all_results[: len(images)]
    audio_results = all_results[len(images) :]

    # Collect successful descriptions
    descriptions: list[str] = []
    for i, result in enumerate(image_results):
        if isinstance(result, Exception) or (isinstance(result, str) and result.startswith("[Error")):
            logger.warning("demo_image_analysis_failed", idx=i, error=str(result)[:100])
            continue
        descriptions.append(f"**Foto {i + 1}** ({images[i].get('filename', 'unknown')}):\n{result}")

    if not descriptions:
        raise RuntimeError("all_images_failed_analysis")

    transcripts: list[str] = []
    for i, result in enumerate(audio_results):
        if isinstance(result, Exception):
            logger.warning("demo_audio_transcribe_failed", idx=i, error=str(result)[:100])
            continue
        if isinstance(result, str) and result.strip():
            transcripts.append(f"**Audio {i + 1}**: {result.strip()}")

    # Step 3: Synthesize consolidated report
    asset_pieces = [f"{len(descriptions)} foto{'s' if len(descriptions) != 1 else ''}"]
    if transcripts:
        asset_pieces.append(f"{len(transcripts)} audio{'s' if len(transcripts) != 1 else ''}")
    asset_summary = " y ".join(asset_pieces)

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
        images_analyzed=len(descriptions),
        images_failed=len(images) - len(descriptions),
        audios_transcribed=len(transcripts),
        chars=len(report),
        elapsed_ms=elapsed_ms,
        country=country_name,
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
