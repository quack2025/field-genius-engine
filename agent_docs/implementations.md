# Implementations (Clients)

## Current Implementations

### Argos (construction)
- **ID:** `argos`
- **Industry:** construction (cement company)
- **Visit types:** ferreteria (3 cats), obra_civil, obra_pequena
- **Vision prompt:** 6-dimension analysis (tipo de toma, presencia institucional, presencia producto, precios, competencia, perfil del punto)
- **Schema files (legacy):** `src/implementations/argos/schemas/*.json`
- **DB seeded:** Yes (implementations + visit_types tables)

### Eficacia (FMCG/retail promoters)
- **ID:** `eficacia`
- **Industry:** fmcg (supermarket promoters/merchandisers)
- **Visit types:**
  - `supermarket_visit` — 5 categories: share_of_shelf, precios, exhibiciones_especiales, actividad_competencia, perfil_punto
  - `wholesale_visit` — 4 categories: inventario_visible, precios_mayorista, actividad_competencia, relacion_comercial
- **Vision prompt:** Retail-specific (gondola, share of shelf, facings, POP material)
- **Seeded via:** `scripts/seed_eficacia.py` (requires SUPABASE_SERVICE_ROLE_KEY env var)

## Schema Structure

Each visit type has a JSON schema that drives AI extraction:

```json
{
  "implementation": "argos",
  "visit_type": "ferreteria",
  "display_name": "Visita a Ferreteria",
  "description": "...",
  "primary_media": ["image", "voice"],
  "categories": [
    {
      "id": "precios",
      "label": "Precios capturados",
      "description": "...",
      "fields": [
        {"id": "producto", "type": "string", "label": "Producto"},
        {"id": "precio", "type": "number", "label": "Precio COP"}
      ],
      "is_array": true,        // can have multiple entries
      "applies_to": ["image", "voice"]  // which media types extract this
    }
  ],
  "confidence_threshold": 0.7,
  "sheets_tab": "Ferreterias"
}
```

`schema_builder.py` converts this JSON into a Claude system prompt dynamically.

## Adding a New Implementation

1. Create in backoffice (or `POST /api/admin/implementations`)
2. Define visit types with schemas
3. Write vision_system_prompt (what to look for in photos)
4. Write segmentation_prompt_template (how to group visits)
5. Assign user phones
6. Create Google Spreadsheet + share with service account
7. Test end-to-end via WhatsApp or `/api/simulate`
