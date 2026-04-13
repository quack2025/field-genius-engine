"""ConfigLoader — DB-first, file-fallback configuration for implementations."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class VisitTypeConfig:
    """A visit type with its extraction schema."""
    slug: str
    display_name: str
    schema_json: dict[str, Any]
    sheets_tab: str | None = None
    confidence_threshold: float = 0.7


@dataclass
class ImplementationConfig:
    """Full configuration for an implementation/client."""
    id: str
    name: str
    industry: str | None = None
    country: str = "CO"
    language: str = "es"
    primary_color: str = "#003366"
    vision_system_prompt: str = ""
    segmentation_prompt_template: str = ""
    google_spreadsheet_id: str | None = None
    trigger_words: list[str] = field(default_factory=lambda: ["reporte", "generar", "listo", "fin"])
    analysis_framework: dict[str, Any] | None = None
    country_config: dict[str, Any] = field(default_factory=dict)
    visit_types: dict[str, VisitTypeConfig] = field(default_factory=dict)
    # Vision strategy: "tiered" (default, Haiku first → Sonnet escalation), "sonnet_only"
    vision_strategy: str = "tiered"
    # Per-client WhatsApp number (Twilio format: whatsapp:+1XXXXXXXXXX)
    whatsapp_number: str = ""
    # Access control: "open" (anyone can use) or "whitelist" (registered users only)
    access_mode: str = "open"
    # Onboarding messages (configurable per implementation)
    onboarding_config: dict[str, Any] = field(default_factory=dict)
    # Demo keywords — first token of a message matching any of these switches the user to this impl
    demo_keywords: list[str] = field(default_factory=list)
    # Fallback implementation when access_mode=whitelist rejects a user (useful for demo fallback)
    fallback_implementation: str | None = None

    def get_country_context(self, country_code: str) -> dict[str, Any]:
        """Get country-specific config. Falls back to first available or empty."""
        if country_code in self.country_config:
            return self.country_config[country_code]
        if self.country_config:
            return next(iter(self.country_config.values()))
        return {}


# Module-level cache with TTL (5 minutes)
_cache: dict[str, ImplementationConfig] = {}
_cache_ts: dict[str, float] = {}
_CACHE_TTL = 300  # seconds

# Keyword → impl_id index (built lazily, invalidated with _cache_ts)
_keyword_index: dict[str, str] = {}
_keyword_index_ts: float = 0.0

# Reserved keywords that cannot be used as demo_keywords (they trigger the existing menu)
RESERVED_KEYWORDS = {"menu", "menú", "proyectos", "proyecto", "cambiar"}


async def get_implementation(impl_id: str) -> ImplementationConfig:
    """Get implementation config. Tries cache (5min TTL), then DB, then files."""
    import time
    now = time.time()
    if impl_id in _cache and (now - _cache_ts.get(impl_id, 0)) < _CACHE_TTL:
        return _cache[impl_id]

    # Try DB
    config = await _load_from_db(impl_id)
    if config:
        _cache[impl_id] = config
        _cache_ts[impl_id] = now
        return config

    # Fall back to files
    config = _load_from_files(impl_id)
    if config:
        _cache[impl_id] = config
        _cache_ts[impl_id] = now
        return config

    raise ValueError(f"Implementation '{impl_id}' not found in DB or files")


async def get_vision_prompt(impl_id: str) -> str:
    """Get the vision system prompt for an implementation."""
    config = await get_implementation(impl_id)
    return config.vision_system_prompt


async def get_vision_strategy(impl_id: str) -> str:
    """Get the vision strategy for an implementation: 'sonnet_only' or 'tiered'."""
    config = await get_implementation(impl_id)
    return config.vision_strategy


async def _build_keyword_index() -> dict[str, str]:
    """Scan all active implementations and build the keyword → impl_id lookup.

    Colisiones: log WARNING y queda el primer impl_id en orden alfabético.
    Reserved keywords se excluyen.
    """
    try:
        from src.engine.supabase_client import get_client, _run

        def _fetch():
            client = get_client()
            result = (
                client.table("implementations")
                .select("id, demo_keywords")
                .eq("status", "active")
                .order("id")
                .execute()
            )
            return result.data or []

        rows = await _run(_fetch)
    except Exception as e:
        logger.warning("keyword_index_build_failed", error=str(e))
        return {}

    index: dict[str, str] = {}
    for row in rows:
        impl_id = row["id"]
        keywords = row.get("demo_keywords") or []
        for kw in keywords:
            if not kw:
                continue
            kw_norm = kw.strip().lower()
            if not kw_norm:
                continue
            if kw_norm in RESERVED_KEYWORDS:
                logger.warning("keyword_reserved_skipped", keyword=kw_norm, impl=impl_id)
                continue
            if kw_norm in index:
                logger.warning(
                    "keyword_collision",
                    keyword=kw_norm,
                    kept=index[kw_norm],
                    skipped=impl_id,
                )
                continue
            index[kw_norm] = impl_id

    logger.info("keyword_index_built", entries=len(index))
    return index


async def get_impl_by_keyword(keyword: str) -> str | None:
    """Return the impl_id that owns a given demo keyword, or None.

    Rebuilds the index lazily if expired (aligned with _CACHE_TTL).
    """
    global _keyword_index, _keyword_index_ts
    import time
    now = time.time()
    if not _keyword_index or (now - _keyword_index_ts) > _CACHE_TTL:
        _keyword_index = await _build_keyword_index()
        _keyword_index_ts = now
    return _keyword_index.get((keyword or "").strip().lower())


async def get_visit_types(impl_id: str) -> list[VisitTypeConfig]:
    """Get all active visit types for an implementation."""
    config = await get_implementation(impl_id)
    return list(config.visit_types.values())


async def get_visit_type_schema(impl_id: str, visit_type_slug: str) -> dict[str, Any]:
    """Get the extraction schema for a specific visit type."""
    config = await get_implementation(impl_id)

    # Direct match
    if visit_type_slug in config.visit_types:
        return config.visit_types[visit_type_slug].schema_json

    # Try normalized slug (obra_pequeña -> obra_pequena)
    normalized = visit_type_slug.replace("ñ", "n")
    if normalized in config.visit_types:
        return config.visit_types[normalized].schema_json

    # Fallback to first visit type
    if config.visit_types:
        first = next(iter(config.visit_types.values()))
        logger.warning(
            "visit_type_not_found_fallback",
            requested=visit_type_slug,
            fallback=first.slug,
            implementation=impl_id,
        )
        return first.schema_json

    raise ValueError(f"No visit types found for implementation '{impl_id}'")


async def reload(impl_id: str | None = None) -> None:
    """Clear cache, forcing next access to reload from DB/files."""
    global _keyword_index, _keyword_index_ts
    if impl_id:
        _cache.pop(impl_id, None)
        _cache_ts.pop(impl_id, None)
        logger.info("config_cache_cleared", implementation=impl_id)
    else:
        _cache.clear()
        _cache_ts.clear()
        logger.info("config_cache_cleared_all")
    # Always rebuild keyword index on reload
    _keyword_index = {}
    _keyword_index_ts = 0.0


async def _load_from_db(impl_id: str) -> ImplementationConfig | None:
    """Load implementation config from Supabase."""
    try:
        from src.engine.supabase_client import get_client
        client = get_client()

        # Load implementation row
        result = (
            client.table("implementations")
            .select("*")
            .eq("id", impl_id)
            .eq("status", "active")
            .maybe_single()
            .execute()
        )
        if not result or not result.data:
            return None

        row = result.data
        trigger_words = row.get("trigger_words", ["reporte", "generar", "listo", "fin"])
        if isinstance(trigger_words, str):
            trigger_words = json.loads(trigger_words)

        config = ImplementationConfig(
            id=row["id"],
            name=row["name"],
            industry=row.get("industry"),
            country=row.get("country", "CO"),
            language=row.get("language", "es"),
            primary_color=row.get("primary_color", "#003366"),
            vision_system_prompt=row.get("vision_system_prompt", ""),
            segmentation_prompt_template=row.get("segmentation_prompt_template", ""),
            google_spreadsheet_id=row.get("google_spreadsheet_id"),
            trigger_words=trigger_words,
            analysis_framework=row.get("analysis_framework"),
            country_config=row.get("country_config") or {},
            vision_strategy=row.get("vision_strategy", "sonnet_only"),
            whatsapp_number=row.get("whatsapp_number", ""),
            access_mode=row.get("access_mode", "open"),
            onboarding_config=row.get("onboarding_config") or {},
            demo_keywords=row.get("demo_keywords") or [],
            fallback_implementation=row.get("fallback_implementation"),
        )

        # Load visit types
        vt_result = (
            client.table("visit_types")
            .select("*")
            .eq("implementation_id", impl_id)
            .eq("is_active", True)
            .order("sort_order")
            .execute()
        )
        if vt_result and vt_result.data:
            for vt in vt_result.data:
                schema = vt["schema_json"]
                if isinstance(schema, str):
                    schema = json.loads(schema)
                config.visit_types[vt["slug"]] = VisitTypeConfig(
                    slug=vt["slug"],
                    display_name=vt["display_name"],
                    schema_json=schema,
                    sheets_tab=vt.get("sheets_tab"),
                    confidence_threshold=vt.get("confidence_threshold", 0.7),
                )

        logger.info(
            "config_loaded_from_db",
            implementation=impl_id,
            visit_types=len(config.visit_types),
        )
        return config

    except Exception as e:
        logger.warning("config_db_load_failed", implementation=impl_id, error=str(e))
        return None


def _load_from_files(impl_id: str) -> ImplementationConfig | None:
    """Load implementation config from filesystem (backward compat)."""
    import os

    schemas_dir = f"src/implementations/{impl_id}/schemas"
    if not os.path.isdir(schemas_dir):
        logger.warning("config_files_not_found", implementation=impl_id, path=schemas_dir)
        return None

    # Build config from JSON files
    config = ImplementationConfig(
        id=impl_id,
        name=impl_id.title(),
    )

    # Load default vision prompt for file-based implementations
    config.vision_system_prompt = _default_vision_prompt(impl_id)

    # Load all schema JSONs
    for filename in os.listdir(schemas_dir):
        if not filename.endswith(".json") or filename.startswith("__"):
            continue

        filepath = os.path.join(schemas_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                schema = json.load(f)

            slug = schema.get("visit_type", filename.replace(".json", ""))
            config.visit_types[slug] = VisitTypeConfig(
                slug=slug,
                display_name=schema.get("display_name", slug.replace("_", " ").title()),
                schema_json=schema,
                sheets_tab=schema.get("sheets_tab"),
                confidence_threshold=schema.get("confidence_threshold", 0.7),
            )
        except Exception as e:
            logger.warning("config_file_load_failed", file=filepath, error=str(e))

    if config.visit_types:
        logger.info(
            "config_loaded_from_files",
            implementation=impl_id,
            visit_types=len(config.visit_types),
        )
        return config

    return None


def _default_vision_prompt(impl_id: str) -> str:
    """Fallback vision prompt for file-based implementations."""
    return f"""Eres un analista de campo experto.
Analiza esta imagen capturada durante una visita de campo.

Describe en detalle lo que observas, organizado en estas dimensiones:

1. TIPO DE TOMA: ¿Es exterior (fachada), interior (góndola/mostrador), o detalle (producto/precio)?

2. PRESENCIA INSTITUCIONAL:
   - ¿Hay logos, avisos o letreros de alguna marca en fachada o interior?
   - ¿Hay material POP? (banners, cenefas, exhibidores, stickers)

3. PRODUCTOS Y PRECIOS:
   - Productos visibles (marcas, referencias, presentaciones)
   - Precios visibles (etiquetas, letreros)

4. COMPETENCIA:
   - Marcas presentes y en qué categorías
   - Promociones o material POP visible

5. PERFIL DEL PUNTO:
   - Categorías que maneja
   - Nivel de surtido y organización (alto/medio/bajo)
   - Señales de actividad comercial
   - Tamaño estimado del punto (pequeño/mediano/grande)

Sé específico y objetivo. Si no puedes ver algo claramente, dilo.
Responde en español, en párrafos cortos y concretos."""
