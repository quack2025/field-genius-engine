"""Demo instant mode — single photo → WhatsApp-ready report.

Used by implementations flagged with `onboarding_config.demo_mode=true`.
Flow:
  1. Run tiered vision analysis on the photo (impl's normal vision prompt).
  2. Synthesize a WhatsApp-friendly mini-report with country + optional audio context.
  3. Caller sends the resulting markdown back to the user.

Does NOT write to visit_reports — this is an ephemeral demo output, not a real report.
Content safety still runs in parallel via the normal preprocessor worker.
"""

from __future__ import annotations

import time

import structlog
from anthropic import AsyncAnthropic

from src.config.settings import settings
from src.engine.ai_semaphore import get_ai_semaphore
from src.engine.config_loader import ImplementationConfig
from src.engine.vision import analyze_from_storage

logger = structlog.get_logger(__name__)

HAIKU = "claude-haiku-4-5-20251001"

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=60.0)
    return _client


SYNTHESIS_SYSTEM = """Eres un analista senior de {industry} que entrega insights accionables vía WhatsApp.

Recibes una descripción técnica detallada de una foto de campo y debes convertirla en un mini-reporte de WhatsApp de 350-550 palabras, en español neutro, con este formato EXACTO:

*📊 Análisis — {impl_name}*
_{location_line}_
━━━━━━━━━━━━━━━━━━━━

*Resumen ejecutivo*
[2-3 líneas: qué se ve y el hallazgo principal accionable]

*🏷️ Hallazgos clave*
• [hallazgo específico con datos]
• [hallazgo específico con datos]
• [hallazgo específico con datos]

*⚠️ Alertas*
[Solo si hay algo crítico. 🔴 crítico, 🟡 atención. Si no hay nada destacable, OMITE esta sección entera.]

*💡 Oportunidades*
1. [acción concreta ejecutable hoy]
2. [acción concreta ejecutable hoy]
3. [acción concreta ejecutable hoy]

━━━━━━━━━━━━━━━━━━━━
_Reporte generado automáticamente desde tu foto._

Reglas estrictas:
- Formato WhatsApp: *bold*, _italic_, • bullets, 1. listas numeradas. NADA de markdown tipo **bold** ni [link](url).
- Mercado: {country_name}. Usa marcas, moneda local y cadenas retail de ese país cuando sea relevante.
- Si no hay precios visibles en la descripción, NO inventes precios. Prefiere "precios no visibles en la foto" a fabricar cifras.
- Sé específico: "Rexona 38% share" > "marca líder". "Nivel ojos vacío" > "exhibición mejorable".
- Cero disclaimers, cero hedging, cero frases como "según lo observado" — ve directo al insight.
- Si la foto no corresponde al caso (ej: selfie, paisaje), entrega un reporte corto explicando qué sí se ve e invita a enviar una foto del punto de venta / publicidad."""


async def generate_single_photo_demo_report(
    storage_path: str,
    impl_config: ImplementationConfig,
    country_name: str | None,
    audio_context: str | None = None,
    location_hint: str | None = None,
) -> str:
    """Generate a WhatsApp-ready demo report from a single photo.

    Args:
        storage_path: Supabase Storage path (e.g., "{session_id}/{filename}").
        impl_config: Implementation config (used for name, industry, vision prompt).
        country_name: Human-readable country from phone prefix, e.g. "Colombia".
        audio_context: Optional transcribed audio the user sent with the photo.
        location_hint: Optional location label (address/coords) if shared.

    Returns:
        Markdown string ready to send via WhatsApp.

    Raises:
        RuntimeError on vision or synthesis failure — caller must catch.
    """
    start = time.time()

    context_parts: list[str] = []
    if country_name:
        context_parts.append(f"País: {country_name}")
    if location_hint:
        context_parts.append(f"Ubicación: {location_hint}")
    if audio_context:
        context_parts.append(f"El usuario dijo en audio: \"{audio_context}\"")
    context = " | ".join(context_parts)

    # Step 1: tiered vision analysis using impl's configured prompt
    description = await analyze_from_storage(
        storage_path=storage_path,
        context=context,
        implementation=impl_config.id,
    )

    if not description or description.startswith("[Error"):
        raise RuntimeError(f"vision_failed: {description[:100]}")

    # Step 2: synthesis → WhatsApp report
    location_line = location_hint or (f"Mercado: {country_name}" if country_name else "Análisis de campo")

    system = SYNTHESIS_SYSTEM.format(
        industry=impl_config.industry or "retail y campo",
        impl_name=impl_config.name,
        location_line=location_line,
        country_name=country_name or "Latinoamérica",
    )

    user_msg = (
        "Descripción técnica de la foto (generada por análisis de visión):\n\n"
        f"{description}\n\n"
        "Genera el mini-reporte WhatsApp siguiendo EXACTAMENTE el formato indicado en el system prompt."
    )

    try:
        async with get_ai_semaphore():
            client = _get_client()
            message = await client.messages.create(
                model=HAIKU,
                max_tokens=1500,
                system=system,
                messages=[{"role": "user", "content": user_msg}],
            )
    except Exception as e:
        raise RuntimeError(f"synthesis_failed: {e}") from e

    report = message.content[0].text.strip()

    elapsed_ms = int((time.time() - start) * 1000)
    logger.info(
        "demo_report_generated",
        impl=impl_config.id,
        chars=len(report),
        description_chars=len(description),
        elapsed_ms=elapsed_ms,
        country=country_name,
        has_audio=bool(audio_context),
        has_location=bool(location_hint),
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens,
    )
    return report
