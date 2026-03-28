# Implementations (Clients)

## Current Implementations

### Laundry Care — Cuidado de la Ropa (CPG demo)
- **ID:** `laundry_care`
- **Industry:** CPG (detergents, softeners, stain removers)
- **Status:** active (default)
- **Visit types:** supermarket_visit, drugstore_visit, tienda_barrio, hard_discount
- **Analysis frameworks (3):**
  - `tactical` — Execution audit: availability, pricing, promotions, shelf share, execution score
  - `strategic` — Babson Pentagon: shopper, value proposition, revenue model, delivery, ecosystem
  - `innovation` — Gaps, trends, packaging/comms, shopper friction, innovation roadmap
- **Vision prompt:** 9-dimension retail analysis (productos, share of shelf, posicion, promos, estado anaquel, innovacion, exhibiciones, competencia, comunicacion)
- **Seeded via:** `sql/006_laundry_care.sql`

### Telecable (Telecom)
- **ID:** `telecable`
- **Industry:** Telecom (cable/internet provider, Costa Rica)
- **Status:** active
- **Visit types:** visita_campo, atencion_cliente, instalacion
- **Analysis frameworks (3):**
  - `competidor` (C1) — Competitive intelligence: competitor presence, promotions, pricing, threats
  - `cliente` (C2) — Customer experience: satisfaction, pain points, churn risk, NPS signals
  - `comunicacion` (C3) — Brand communication: visibility, messaging, POP effectiveness
- **Seeded via:** `sql/007_telecable.sql`

### Argos (Construction) — INACTIVE
- **ID:** `argos`
- **Industry:** construction (cement company)
- **Status:** inactive (legacy, first implementation)
- **Visit types:** ferreteria, obra_civil, obra_pequena
- **Schema files (legacy):** `src/implementations/argos/schemas/*.json`

## Analysis Framework Structure

Each implementation stores its frameworks in the `analysis_framework` JSONB column:

```json
{
  "frameworks": {
    "tactical": {
      "id": "tactical",
      "name": "Reporte Tactico de Ejecucion",
      "model": "claude-sonnet-4-20250514",
      "system_prompt": "Eres un auditor senior...",
      "sections": [
        {"id": "availability", "label": "Disponibilidad y Agotados", "prompt": "Analiza..."},
        {"id": "pricing", "label": "Precios y Competitividad", "prompt": "..."}
      ]
    },
    "strategic": { ... },
    "innovation": { ... }
  }
}
```

The `sections` array drives report generation — each section becomes a `## heading` in the markdown output.

## WhatsApp Menu — Implementation Switching

Users can switch between implementations by sending "menu" (or "proyecto", "cambiar") via WhatsApp:

```
User: menu
Bot: *Selecciona un proyecto:*
     1. Cuidado de la Ropa (actual)
     2. Telecable
     Responde con el numero (1-2)
User: 2
Bot: Proyecto cambiado a *Telecable*.
     Todo lo que envies ahora se asocia a este proyecto.
```

State is persisted in the `users` table (`implementation` + `implementation_id` columns).

## Adding a New Implementation

1. Create SQL migration with INSERT into `implementations` (include `analysis_framework` JSONB)
2. Define visit types in same migration
3. Write `vision_system_prompt` (what to look for in photos)
4. Define framework sections with prompts
5. Run migration in Supabase SQL Editor
6. `POST /api/admin/reload-config` to refresh cache
7. Assign user phones via backoffice or API
8. Test: send photos via WhatsApp → generate report from backoffice
