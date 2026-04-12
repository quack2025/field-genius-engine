# Proyectos (Implementations)

## Current Projects

### Laundry Care — Cuidado de la Ropa (CPG demo)
- **ID:** `laundry_care`
- **Industry:** CPG (detergents, softeners, stain removers)
- **Status:** active
- **WhatsApp:** `+14155238886` (Twilio sandbox, for demos)
- **Access mode:** `open` (anyone can use)
- **Vision strategy:** `tiered` (Haiku first, Sonnet fallback)
- **Visit types:** supermarket_visit, drugstore_visit, tienda_barrio, hard_discount
- **Analysis frameworks (3):**
  - `tactical` — Execution audit: availability, pricing, promotions, shelf share, execution score
  - `strategic` — Babson Pentagon: shopper, value proposition, revenue model, delivery, ecosystem
  - `innovation` — Gaps, trends, packaging/comms, shopper friction, innovation roadmap
- **Seeded via:** `sql/006_laundry_care.sql`

### Telecable — IA | Telecable (Telecom, Costa Rica)
- **ID:** `telecable`
- **Industry:** Telecom (cable/internet provider)
- **Status:** active (enterprise pilot)
- **WhatsApp:** `+17792284312` (paid, exclusive)
- **Access mode:** `whitelist` (only registered users can send)
- **Vision strategy:** `tiered`
- **Onboarding:** requires T&C acceptance via WhatsApp
- **Visit types:** visita_campo, atencion_cliente, instalacion
- **Analysis frameworks (3):**
  - `competidor` (C1) — Competitive intelligence
  - `cliente` (C2) — Customer experience
  - `comunicacion` (C3) — Brand communication
- **Seeded via:** `sql/007_telecable.sql`

### Argos (Construction) — INACTIVE
- **ID:** `argos` (legacy, first implementation)
- Not in use

### Eficacia — Impulsadoras — INACTIVE
- **ID:** `eficacia` (legacy)
- Not in use

## Project Configuration (All Editable from Backoffice)

Each project stores configuration in the `implementations` table, editable from ImplementationDetail config tab:

### General
- `name`, `industry`, `country`, `language`, `primary_color`
- `google_spreadsheet_id`, `trigger_words`

### WhatsApp + Access Control
- `whatsapp_number` — Twilio sender (format: `whatsapp:+1XXXXXXXXXX`)
- `access_mode` — `open` (anyone) | `whitelist` (registered users only)

### AI Configuration
- `vision_strategy` — `tiered` (Haiku→Sonnet fallback) | `sonnet_only`

### Onboarding (`onboarding_config` JSONB)
- `welcome_message` — First contact message
- `terms_accepted_message` — After user replies "acepto"
- `rejection_message` — For non-whitelisted users
- `first_photo_hint` — File receipt confirmation (supports `{count}` placeholder)
- `require_terms` — Boolean: enforce T&C acceptance

### Digest Email (`onboarding_config.digest`)
- `enabled` — Toggle
- `emails` — Array of recipient addresses
- `frequency` — `daily` | `weekly`

### Organization
- `folder` — Optional text folder name for backoffice grouping

## Analysis Framework Structure

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
    }
  }
}
```

## WhatsApp Onboarding Flow

### First contact (user registered, require_terms=true)
```
User: hola (or sends first photo)
Bot: [welcome_message with instructions + T&C]
User: acepto
Bot: [terms_accepted_message]
User: [sends photo]
Bot: [first_photo_hint with {count}]
```

### First contact (user NOT registered, whitelist mode)
```
User: hola
Bot: [rejection_message — no processing occurs]
```

### First contact (open mode, user not registered)
- User sent to default implementation
- No rejection, but no pre-configured access

## WhatsApp Menu — Project Switching (legacy)

Users can switch projects by sending "menu":
```
User: menu
Bot: *Selecciona un proyecto:*
     1. Cuidado de la Ropa (actual)
     2. Telecable
User: 2
Bot: Proyecto cambiado a *Telecable*.
```

Note: with per-client WhatsApp numbers, the menu is less critical since each project has its own dedicated number.

## Adding a New Project

1. Create SQL migration with INSERT into `implementations` (include `analysis_framework` JSONB)
2. Define visit types in same migration
3. Write `vision_system_prompt` (what to look for in photos)
4. Configure `onboarding_config` with welcome/rejection messages
5. Set `whatsapp_number` to the Twilio sender
6. Set `access_mode` (whitelist for enterprise)
7. Run migration in Supabase SQL Editor
8. Configure Twilio webhook for the new number pointing to Railway
9. Test via WhatsApp → verify onboarding flow → generate report from backoffice
