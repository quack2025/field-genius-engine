"""Segmenter — Phase 1: identify distinct visits in a day's capture batch."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import structlog
from anthropic import AsyncAnthropic

from src.config.settings import settings
from src.engine.transcriber import transcribe
from src.engine.vision import analyze_from_storage

# Singleton async client for segmentation
_seg_client: AsyncAnthropic | None = None


def _get_seg_client() -> AsyncAnthropic:
    global _seg_client
    if _seg_client is None:
        _seg_client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=180.0)
    return _seg_client
from src.engine.video import process_video
from src.engine.transcriber import transcribe_bytes

logger = structlog.get_logger(__name__)


@dataclass
class VisitSegment:
    """A single identified visit within a session."""
    segment_id: str
    inferred_location: str
    visit_type: str  # ferreteria / obra_civil / obra_pequeña
    confidence: float
    files: list[str]
    time_range: str
    transcriptions: dict[str, str] = field(default_factory=dict)
    image_descriptions: dict[str, str] = field(default_factory=dict)
    text_notes: list[str] = field(default_factory=list)


@dataclass
class SegmentationResult:
    """Result of Phase 1 segmentation."""
    visits: list[VisitSegment] = field(default_factory=list)
    unassigned_files: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_message: str = ""
    raw_json: dict[str, Any] = field(default_factory=dict)
    elapsed_ms: int = 0


def _build_segmentation_schema(visit_type_options: str) -> str:
    """Build the segmentation JSON schema with dynamic visit types."""
    return f"""{{"sessions": [{{"id": "session-1", "inferred_location": "Nombre/ubicación del punto visitado", "visit_type": "{visit_type_options}", "confidence": 0.92, "files": ["archivo1.jpg", "audio1.ogg"], "time_range": "10:15 - 10:52"}}], "unassigned_files": [], "needs_clarification": false, "clarification_message": ""}}"""


async def segment_session(
    session: dict[str, Any],
    implementation: str = "",
) -> SegmentationResult:
    """Analyze all files in a session and identify distinct visits.

    Steps:
    1. Transcribe all audio files
    2. Analyze all images with vision
    3. Process any videos (extract frames + audio)
    4. Build consolidated context
    5. Call Claude Sonnet to segment into visits
    """
    start = time.time()
    session_id = session["id"]
    raw_files: list[dict[str, Any]] = session.get("raw_files", [])
    logger.info("segmenter_start", session_id=session_id, file_count=len(raw_files))

    # Collect transcriptions and image descriptions
    transcriptions: dict[str, str] = {}
    image_descriptions: dict[str, str] = {}
    text_notes: list[dict[str, str]] = []

    for file_entry in raw_files:
        filename = file_entry.get("filename", "unknown")
        file_type = file_entry.get("type", "unknown")
        storage_path = file_entry.get("storage_path")
        timestamp = file_entry.get("timestamp", "")

        if file_type == "audio" and storage_path:
            # Use pre-processed transcription if available
            pre_text = file_entry.get("transcription")
            if pre_text:
                logger.info("segmenter_using_cached_transcription", filename=filename)
                transcriptions[filename] = pre_text
            else:
                logger.info("segmenter_transcribing", filename=filename)
                text = await transcribe(storage_path)
                if text:
                    transcriptions[filename] = text

        elif file_type == "image" and storage_path:
            # Use pre-processed image description if available
            pre_desc = file_entry.get("image_description")
            if pre_desc:
                logger.info("segmenter_using_cached_description", filename=filename)
                image_descriptions[filename] = pre_desc
            else:
                logger.info("segmenter_analyzing_image", filename=filename)
                desc = await analyze_from_storage(storage_path, implementation=implementation)
                if desc:
                    image_descriptions[filename] = desc

        elif file_type == "video" and storage_path:
            # Use pre-processed video data if available
            pre_text = file_entry.get("transcription")
            pre_desc = file_entry.get("image_description")
            if pre_text or pre_desc:
                logger.info("segmenter_using_cached_video", filename=filename)
                if pre_text:
                    transcriptions[f"{filename}_audio"] = pre_text
                if pre_desc:
                    image_descriptions[f"{filename}_frame1"] = pre_desc
            else:
                logger.info("segmenter_processing_video", filename=filename)
                video_result = await process_video(storage_path)
                # Transcribe extracted audio
                if video_result.audio_bytes:
                    text = await transcribe_bytes(video_result.audio_bytes)
                    if text:
                        transcriptions[f"{filename}_audio"] = text
                # Analyze frames
                for idx, frame in enumerate(video_result.frames):
                    from src.engine.vision import analyze_image
                    frame_desc = await analyze_image(frame, context="frame de video de visita de campo", implementation=implementation)
                    image_descriptions[f"{filename}_frame{idx+1}"] = frame_desc

        elif file_type == "location":
            lat = file_entry.get("latitude", "")
            lng = file_entry.get("longitude", "")
            addr = file_entry.get("address", "")
            label = file_entry.get("label", "")
            loc_text = f"Lat: {lat}, Lng: {lng}"
            if addr:
                loc_text += f", Direccion: {addr}"
            if label:
                loc_text += f", Nombre: {label}"
            text_notes.append({"timestamp": timestamp, "text": f"[UBICACION GPS COMPARTIDA] {loc_text}"})
            logger.info("segmenter_location_found", lat=lat, lng=lng, address=addr)

        elif file_type == "text":
            body = file_entry.get("body", "")
            if body:
                text_notes.append({"timestamp": timestamp, "text": body})

    # Build consolidated context for Claude
    context_parts: list[str] = []

    for filename, text in transcriptions.items():
        ts = _find_timestamp(raw_files, filename)
        context_parts.append(f"[Audio: {filename} | {ts}]\n{text}\n")

    for filename, desc in image_descriptions.items():
        ts = _find_timestamp(raw_files, filename)
        context_parts.append(f"[Imagen: {filename} | {ts}]\n{desc}\n")

    for note in text_notes:
        context_parts.append(f"[Texto: {note['timestamp']}]\n{note['text']}\n")

    consolidated_context = "\n".join(context_parts)

    if not consolidated_context.strip():
        logger.warning("segmenter_empty_context", session_id=session_id)
        return SegmentationResult(
            needs_clarification=True,
            clarification_message="No pude procesar ningún archivo de la sesión. Intenta enviar los archivos de nuevo.",
            elapsed_ms=int((time.time() - start) * 1000),
        )

    # Call Claude Sonnet to segment
    logger.info("segmenter_calling_claude", context_chars=len(consolidated_context))

    all_filenames = [f.get("filename", "unknown") for f in raw_files]

    # Load implementation config for dynamic visit types and prompt
    from src.engine.config_loader import get_implementation, get_visit_types
    impl_config = await get_implementation(implementation)
    visit_type_configs = await get_visit_types(implementation)
    visit_type_slugs = [vt.slug for vt in visit_type_configs]
    visit_type_options = " | ".join(visit_type_slugs)

    segmentation_schema = _build_segmentation_schema(visit_type_options)

    # Use custom template if available, otherwise build default prompt
    # NOTE: Use .replace() instead of .format() because templates contain literal
    # JSON braces {} that would cause KeyError with str.format()
    if impl_config.segmentation_prompt_template:
        prompt = impl_config.segmentation_prompt_template
        prompt = prompt.replace("{implementation_name}", impl_config.name)
        prompt = prompt.replace("{visit_type_options}", visit_type_options)
        prompt = prompt.replace("{filenames}", json.dumps(all_filenames, ensure_ascii=False))
        prompt = prompt.replace("{consolidated_context}", consolidated_context)
        prompt = prompt.replace("{segmentation_schema}", segmentation_schema)
    else:
        prompt = f"""Eres un analista que debe identificar cuántas visitas de campo distintas
hay en este conjunto de capturas enviadas por un representante de {impl_config.name}.

Una visita = un punto físico visitado.
Tipos de visita posibles: {visit_type_options}

Archivos disponibles: {json.dumps(all_filenames, ensure_ascii=False)}

Contexto capturado durante el día:
{consolidated_context}

Identifica:
1. Cuántas visitas distintas hay
2. Qué archivos pertenecen a cada visita
3. El tipo de cada visita ({visit_type_options})
4. El nombre/ubicación inferida de cada punto
5. Tu nivel de confianza (0-1) para cada agrupación
6. Si hay archivos que no puedes asignar con confianza

Responde SOLO en JSON siguiendo este schema exacto:
{segmentation_schema}

Si alguna visita tiene confidence < 0.75 o hay archivos sin asignar, pon needs_clarification: true
y en clarification_message explica qué necesitas saber."""

    response_text = ""
    try:
        message = await _get_seg_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text.strip()
        logger.info(
            "segmenter_response_received",
            chars=len(response_text),
            stop_reason=message.stop_reason,
            preview=response_text[:100],
        )

        # Parse JSON — handle markdown wrapping and partial responses
        json_text = response_text
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()

        # Fallback: find the first { and last } if json.loads fails on raw text
        try:
            segmentation_data = json.loads(json_text)
        except json.JSONDecodeError:
            brace_start = json_text.find("{")
            brace_end = json_text.rfind("}")
            if brace_start != -1 and brace_end != -1:
                json_text = json_text[brace_start:brace_end + 1]
                segmentation_data = json.loads(json_text)
            else:
                raise

    except json.JSONDecodeError as e:
        logger.error("segmenter_json_parse_failed", error=str(e), response=response_text[:500])
        return SegmentationResult(
            needs_clarification=True,
            clarification_message="Error interno procesando la segmentación. Intenta de nuevo.",
            elapsed_ms=int((time.time() - start) * 1000),
        )
    except Exception as e:
        logger.error(
            "segmenter_claude_failed",
            error=str(e),
            error_type=type(e).__name__,
            response_preview=response_text[:200] if response_text else "no_response",
        )
        return SegmentationResult(
            needs_clarification=True,
            clarification_message=f"Error procesando: {e}",
            elapsed_ms=int((time.time() - start) * 1000),
        )

    # Build VisitSegment objects
    visits: list[VisitSegment] = []
    for seg in segmentation_data.get("sessions", []):
        visit = VisitSegment(
            segment_id=seg.get("id", ""),
            inferred_location=seg.get("inferred_location", "Desconocido"),
            visit_type=seg.get("visit_type", "ferreteria"),
            confidence=seg.get("confidence", 0.0),
            files=seg.get("files", []),
            time_range=seg.get("time_range", ""),
        )

        # Attach transcriptions and descriptions for this visit's files
        for fname in visit.files:
            if fname in transcriptions:
                visit.transcriptions[fname] = transcriptions[fname]
            if fname in image_descriptions:
                visit.image_descriptions[fname] = image_descriptions[fname]

        # Also attach text notes (they apply to all visits for now)
        visit.text_notes = [n["text"] for n in text_notes]

        visits.append(visit)

    elapsed_ms = int((time.time() - start) * 1000)

    result = SegmentationResult(
        visits=visits,
        unassigned_files=segmentation_data.get("unassigned_files", []),
        needs_clarification=segmentation_data.get("needs_clarification", False),
        clarification_message=segmentation_data.get("clarification_message", ""),
        raw_json=segmentation_data,
        elapsed_ms=elapsed_ms,
    )

    logger.info(
        "segmenter_complete",
        visits=len(visits),
        unassigned=len(result.unassigned_files),
        needs_clarification=result.needs_clarification,
        elapsed_ms=elapsed_ms,
    )

    return result


def _find_timestamp(raw_files: list[dict[str, Any]], filename: str) -> str:
    """Find the timestamp for a file in raw_files list."""
    for f in raw_files:
        if f.get("filename") == filename:
            return f.get("timestamp", "")
    return ""
