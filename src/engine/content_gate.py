"""Content gate — policy layer between raw session files and demo analysis.

Responsibilities:
  1. Read preprocessor classification (content_category, blocked, flagged)
     from session_files when available.
  2. For files without a classification (preprocessor hasn't finished or
     failed), run inline classify_image() in parallel.
  3. Apply demo-mode policy: only BUSINESS content is analyzed. Everything
     else is excluded with a specific reason.
  4. Return a structured result that tells the caller what to do:
       - proceed (all good)
       - partial (some files excluded, but enough remain — mention in report)
       - refuse (nothing usable — send a friendly "please send retail content")

The gate is the single source of truth for "is this file good to analyze?".
Both demo_analyzer and _run_demo_batch_safe call it before synthesis; no
other code inspects content_category / blocked / flagged directly.

Videos bypass the image gate for now (preprocessor does not set
content_category on videos, and running ffmpeg + classify inline would
dominate demo latency). Videos always proceed — a separate sprint can
add video frame classification if abuse happens.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import structlog

from src.engine.content_safety import classify_image
from src.engine.supabase_client import _run, get_client

logger = structlog.get_logger(__name__)

# Categories produced by content_safety.classify_image
BUSINESS = "BUSINESS"
PERSONAL = "PERSONAL"
NSFW = "NSFW"
CONFIDENTIAL = "CONFIDENTIAL"
UNCLEAR = "UNCLEAR"

# Policy: which categories survive for demo analysis.
# UNCLEAR is allowed because the classifier is conservative — a blurry
# but real storefront photo often classifies as UNCLEAR, and we'd rather
# include it than lose it.
ALLOWED_FOR_DEMO = {BUSINESS, UNCLEAR}


@dataclass
class FileVerdict:
    """One file's classification + decision."""
    file: dict[str, Any]
    category: str
    source: str  # "preprocessor_cache" | "inline_haiku" | "blocked_flag"
    included: bool
    exclusion_reason: str | None = None  # human-readable, Spanish


@dataclass
class ContentGateResult:
    """Output of classify_session_images."""
    verdicts: list[FileVerdict] = field(default_factory=list)

    @property
    def allowed_files(self) -> list[dict[str, Any]]:
        return [v.file for v in self.verdicts if v.included]

    @property
    def excluded_verdicts(self) -> list[FileVerdict]:
        return [v for v in self.verdicts if not v.included]

    @property
    def any_allowed(self) -> bool:
        return any(v.included for v in self.verdicts)

    @property
    def all_excluded(self) -> bool:
        return bool(self.verdicts) and not self.any_allowed

    @property
    def decision(self) -> str:
        """'proceed' | 'partial' | 'refuse'."""
        if not self.verdicts:
            return "proceed"  # No images to gate (videos only or empty)
        if self.all_excluded:
            return "refuse"
        if self.excluded_verdicts:
            return "partial"
        return "proceed"

    def exclusion_note_for_prompt(self) -> str | None:
        """Text to append to the synthesis prompt when some files were excluded.

        The LLM should mention this to the user in the final report so it's
        transparent why the analysis focuses on fewer photos than sent.
        """
        if not self.excluded_verdicts:
            return None
        n_excluded = len(self.excluded_verdicts)
        n_total = len(self.verdicts)
        n_allowed = n_total - n_excluded
        reasons = {v.exclusion_reason for v in self.excluded_verdicts if v.exclusion_reason}
        reason_str = ", ".join(sorted(reasons)) if reasons else "contenido no relevante"
        return (
            f"Nota para el usuario: solo se analizaron {n_allowed} de {n_total} imágenes enviadas. "
            f"Las otras {n_excluded} fueron excluidas ({reason_str}). "
            f"En el reporte, mencioná brevemente este dato al final, antes de los bullets de cierre, "
            f"con una línea tipo: _Analicé {n_allowed} de {n_total} fotos. Las demás no parecían ser de un punto de venta._"
        )

    def refusal_message(self) -> str:
        """Friendly message to send to the user when the gate refuses everything.

        Includes a hint about what kind of content IS valid, so they can retry.
        """
        # If everything was blocked as NSFW, say something different
        only_nsfw = all(v.category == NSFW for v in self.excluded_verdicts)
        if only_nsfw:
            return (
                "Las imágenes que enviaste no pueden procesarse por políticas de contenido 🚫\n\n"
                "Este demo analiza fotos de campo comercial: puntos de venta, anaqueles, "
                "publicidad, fachadas, obras, materiales de construcción.\n\n"
                "Envía fotos de un lugar de trabajo y escribe *generar* cuando estés listo."
            )
        return (
            "No reconocí contenido de punto de venta en tus imágenes 🤔\n\n"
            "Este demo analiza fotos de:\n"
            "📦 Góndolas, anaqueles o exhibiciones\n"
            "🏬 Fachadas y puntos de venta\n"
            "📣 Publicidad y material POP\n"
            "🏗️ Obras o materiales de construcción\n\n"
            "Envía una foto de alguna de estas categorías y escribe *generar* cuando estés listo. "
            "Si quieres empezar con el otro demo, escribe *otro*."
        )


# ── Exclusion reasons (short human strings for UI) ──────────────
_REASON_BY_CATEGORY = {
    NSFW: "contenido no permitido",
    PERSONAL: "parece una foto personal",
    CONFIDENTIAL: "contenido confidencial",
    UNCLEAR: "no era reconocible",  # only used when we explicitly reject unclear
}


async def classify_session_images(files: list[dict[str, Any]]) -> ContentGateResult:
    """Classify all image files in a session and return a ContentGateResult.

    Reads content_category + blocked + flagged from session_files rows when
    populated by the preprocessor. For rows without a classification, runs
    classify_image() inline in parallel (fast — ~1-2s per image via Haiku).

    Videos, audios, locations, and text rows are not gated here. Only images.
    """
    result = ContentGateResult()
    image_files = [f for f in files if f.get("type") == "image" and f.get("storage_path")]
    if not image_files:
        return result

    # Partition: files with cached classification vs files needing inline
    cached: list[tuple[dict, str, bool, bool]] = []  # (file, category, blocked, flagged)
    needs_inline: list[dict] = []
    for f in image_files:
        cat = f.get("content_category")
        blocked = bool(f.get("blocked"))
        flagged = bool(f.get("flagged"))
        if cat or blocked:
            cached.append((f, cat or NSFW if blocked else UNCLEAR, blocked, flagged))
        else:
            needs_inline.append(f)

    # Classify missing files in parallel
    inline_results: list[tuple[dict, str]] = []
    if needs_inline:
        inline_results = await asyncio.gather(
            *[_classify_inline(f) for f in needs_inline],
            return_exceptions=False,  # _classify_inline never raises
        )

    # Build verdicts from cached results
    for f, category, blocked, flagged in cached:
        cat_norm = (category or UNCLEAR).upper()
        if blocked:
            result.verdicts.append(FileVerdict(
                file=f, category=NSFW, source="blocked_flag",
                included=False, exclusion_reason=_REASON_BY_CATEGORY[NSFW],
            ))
            continue
        included = cat_norm in ALLOWED_FOR_DEMO and not flagged
        reason = None if included else _REASON_BY_CATEGORY.get(cat_norm, "no reconocible")
        result.verdicts.append(FileVerdict(
            file=f, category=cat_norm, source="preprocessor_cache",
            included=included, exclusion_reason=reason,
        ))

    # Build verdicts from inline classifications
    for f, cat_norm in inline_results:
        included = cat_norm in ALLOWED_FOR_DEMO
        reason = None if included else _REASON_BY_CATEGORY.get(cat_norm, "no reconocible")
        result.verdicts.append(FileVerdict(
            file=f, category=cat_norm, source="inline_haiku",
            included=included, exclusion_reason=reason,
        ))

    logger.info(
        "content_gate_classified",
        total=len(result.verdicts),
        allowed=len(result.allowed_files),
        excluded=len(result.excluded_verdicts),
        decision=result.decision,
        cached=len(cached),
        inline=len(inline_results),
    )
    return result


async def _classify_inline(file: dict[str, Any]) -> tuple[dict, str]:
    """Download + classify a single image inline. Never raises."""
    storage_path = file.get("storage_path")
    if not storage_path:
        return file, UNCLEAR
    try:
        sb = get_client()
        image_bytes = await _run(lambda: sb.storage.from_("media").download(storage_path))
        if not image_bytes:
            return file, UNCLEAR
        result = await classify_image(image_bytes)
        return file, (result.get("category") or UNCLEAR).upper()
    except Exception as e:
        logger.warning("content_gate_inline_failed", path=storage_path, error=str(e)[:120])
        return file, UNCLEAR
