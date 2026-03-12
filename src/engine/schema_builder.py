"""Schema builder — converts JSON implementation schemas into dynamic system prompts for Claude."""

from __future__ import annotations

from typing import Any

MEDIA_LABELS: dict[str, str] = {
    "image": "fotos",
    "voice": "audio",
    "video": "video",
    "text": "texto",
}


def build_system_prompt(schema: dict[str, Any]) -> str:
    """Take an implementation JSON schema and generate the system prompt for Claude extraction.

    The generated prompt:
    1. Describes the context and analyst role
    2. Lists each category with its fields and applicable media types
    3. Specifies the exact JSON response schema
    4. Includes anti-hallucination instructions
    """
    impl = schema.get("implementation", "unknown")
    visit_type = schema.get("display_name", schema.get("visit_type", "unknown"))
    description = schema.get("description", "")
    categories: list[dict[str, Any]] = schema.get("categories", [])

    # Build category sections
    category_sections: list[str] = []
    for cat in categories:
        media_list = ", ".join(MEDIA_LABELS.get(m, m) for m in cat.get("applies_to", []))
        is_array = cat.get("is_array", False)

        fields_desc = "\n".join(
            f"    - {f['label']} ({f['id']}, tipo: {f['type']})"
            for f in cat.get("fields", [])
        )

        multiplicity = "Puede haber múltiples registros." if is_array else "Un solo registro."

        section = (
            f"### {cat['label'].upper()} (aplica a: {media_list})\n"
            f"{cat.get('description', '')}\n"
            f"Campos a extraer:\n"
            f"{fields_desc}\n"
            f"{multiplicity}"
        )
        category_sections.append(section)

    categories_block = "\n\n".join(category_sections)

    # Build the expected JSON structure description
    json_structure = build_extraction_schema(schema)

    prompt = f"""Eres un analista de campo especializado en "{visit_type}" para {impl.capitalize()}.
{description}

Analiza todo el contenido capturado (transcripciones de audio, observaciones de fotos, texto directo) y extrae información estructurada en las siguientes categorías:

{categories_block}

## Instrucciones de extracción

1. Analiza TODA la información disponible: transcripciones, descripciones de fotos y texto directo.
2. Cruza información entre fuentes — un precio mencionado en audio puede complementar una foto de góndola.
3. Si un campo aplica a un tipo de medio que no está presente, intenta inferirlo de otros medios disponibles.
4. Para campos de tipo array, incluye TODOS los registros que encuentres, no solo el primero.

## Reglas anti-alucinación

- Si no tienes información suficiente para un campo, usa null. NUNCA inventes datos.
- El confidence_score debe reflejar honestamente cuánta información real tenías disponible.
- Si la información es ambigua, indica needs_clarification: true y formula preguntas específicas.
- Prefiere dejar un campo vacío a inventar un valor plausible pero no confirmado.

## Formato de respuesta

Responde ÚNICAMENTE con JSON válido siguiendo este schema exacto:

```json
{json_structure}
```

No incluyas texto antes ni después del JSON. No uses markdown. Solo el JSON puro."""

    return prompt


def build_extraction_schema(schema: dict[str, Any]) -> str:
    """Generate the expected JSON response structure from an implementation schema."""
    categories: list[dict[str, Any]] = schema.get("categories", [])

    lines: list[str] = ["{"]
    for i, cat in enumerate(categories):
        is_array = cat.get("is_array", False)
        cat_id = cat["id"]

        # Build field object
        field_pairs: list[str] = []
        for f in cat.get("fields", []):
            type_example = _type_example(f["type"])
            field_pairs.append(f'      "{f["id"]}": {type_example}')

        field_obj = "{\n" + ",\n".join(field_pairs) + "\n    }"

        if is_array:
            lines.append(f'  "{cat_id}": [\n    {field_obj}\n  ],')
        else:
            lines.append(f'  "{cat_id}": {field_obj},')

    # Add meta fields
    lines.append('  "confidence_score": 0.85,')
    lines.append('  "needs_clarification": false,')
    lines.append('  "clarification_questions": []')
    lines.append("}")

    return "\n".join(lines)


def _type_example(field_type: str) -> str:
    """Return a JSON example value for a given field type."""
    match field_type:
        case "string":
            return '"string o null"'
        case "number":
            return "0"
        case "boolean":
            return "false"
        case _:
            return "null"
