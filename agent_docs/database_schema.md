# Database Schema

Supabase project: `sglvhzmwfzetyrhwouiw`
SQL files: `sql/schema.sql` (base) + `sql/002_multi_tenant.sql` (multi-tenant extensions)

## Tables

### users
Field executives and managers who send media via WhatsApp.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | auto-generated |
| implementation | text | 'laundry_care', 'telecable' (used for lookup) |
| implementation_id | text FK → implementations | |
| phone | text UNIQUE | WhatsApp number (e.g. +573001234567) |
| name | text | |
| role | text | 'executive' or 'manager' |
| country | text | |
| group_id | uuid FK → user_groups | Zone/team group assignment |
| tags | text[] | DEFAULT '{}' — flexible tags |
| notification_group | text | WhatsApp group ID for shared reports |
| accepted_terms | boolean | DEFAULT false — did user accept T&C via WhatsApp |
| onboarded_at | timestamptz | When user accepted terms |
| created_at | timestamptz | |

### sessions
Daily batch per user — accumulates media throughout the day.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| implementation | text | legacy field |
| implementation_id | text FK | |
| user_phone | text | |
| user_name | text | denormalized from users |
| date | date | DEFAULT CURRENT_DATE |
| status | text | CHECK constraint (see below) |
| raw_files | jsonb | Array of file metadata objects |
| segments | jsonb | Phase 1 segmentation output |
| created_at | timestamptz | |
| updated_at | timestamptz | |

**Status values:** `accumulating` → `segmenting` → `processing` → `generating_outputs` → `completed`
Also: `needs_clarification`, `failed`

**raw_files entry structure:**
```json
{
  "filename": "8a3f5c2e.jpg",
  "storage_path": "session-uuid/8a3f5c2e.jpg",
  "type": "image|audio|video|text|clarification_response",
  "content_type": "image/jpeg",
  "size_bytes": 245680,
  "timestamp": "2026-03-12T10:15:00+00:00",
  "body": "text content here",             // only for type=text|clarification_response
  "transcription": "transcribed text...",   // pre-processed Whisper output (audio/video)
  "image_description": "Vision AI output..."  // pre-processed Claude Vision output (image)
}
```

### visit_reports
One row per identified visit within a session (a session can have multiple visits).

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| session_id | uuid FK → sessions | CASCADE delete |
| implementation | text | |
| implementation_id | text FK | |
| visit_type | text | e.g. 'ferreteria', 'supermarket_visit' |
| inferred_location | text | AI-inferred point name |
| extracted_data | jsonb | Full Claude extraction output |
| confidence_score | float | 0-1 |
| status | text | processing, completed, failed, needs_review |
| sheets_row_id | text | Google Sheets row reference |
| gamma_url | text | Gamma presentation URL |
| processing_time_ms | integer | |
| created_at | timestamptz | |

### implementations (multi-tenant / proyectos)
Client configurations — each implementation = one customer.

| Column | Type | Notes |
|--------|------|-------|
| id | text PK | e.g. 'laundry_care', 'telecable' |
| name | text | Display name |
| industry | text | 'cpg', 'telecom', 'construction' |
| country | text | DEFAULT 'CO' |
| language | text | DEFAULT 'es' |
| logo_url | text | |
| primary_color | text | DEFAULT '#003366' |
| status | text | CHECK: active, inactive, archived |
| vision_system_prompt | text | What to look for in photos |
| segmentation_prompt_template | text | How to group visits |
| google_spreadsheet_id | text | |
| trigger_words | jsonb | DEFAULT ["reporte","generar","listo","fin"] |
| analysis_framework | jsonb | Frameworks config (see implementations.md) |
| country_config | jsonb | Per-country context (competitors, currency, products) |
| whatsapp_number | text | Per-client Twilio number (e.g. 'whatsapp:+17792284312') |
| access_mode | text | CHECK: 'open' \| 'whitelist' |
| vision_strategy | text | CHECK: 'sonnet_only' \| 'tiered' (default: tiered) |
| onboarding_config | jsonb | welcome_message, terms_accepted_message, rejection_message, first_photo_hint, require_terms, digest |
| folder | text | Optional folder name for organizing in backoffice |
| created_at, updated_at | timestamptz | |

**onboarding_config structure:**
```json
{
  "welcome_message": "Bienvenido a Radar Xponencial!...",
  "terms_accepted_message": "Perfecto! Ya puedes empezar.",
  "rejection_message": "Este servicio es exclusivo para...",
  "first_photo_hint": "Recibido ({count} archivo(s) hoy)...",
  "require_terms": true,
  "digest": {
    "enabled": true,
    "emails": ["admin@xponencial.net"],
    "frequency": "daily"
  }
}
```

### visit_types
Visit type schemas per implementation — replaces JSON files.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| implementation_id | text FK → implementations | |
| slug | text | e.g. 'ferreteria', 'supermarket_visit' |
| display_name | text | |
| description | text | |
| schema_json | jsonb | Full extraction schema |
| sheets_tab | text | Google Sheets tab name |
| confidence_threshold | float | DEFAULT 0.7 |
| is_active | boolean | DEFAULT true (soft delete) |
| sort_order | int | |
| created_at, updated_at | timestamptz | |
| UNIQUE(implementation_id, slug) | | |

### backoffice_users
Admin access control for backoffice (Google SSO + role-based).

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK FK → auth.users | |
| email | text | |
| name | text | |
| role | text | CHECK: superadmin, admin, analyst, viewer |
| allowed_implementations | text[] | Empty for superadmin (has all access) |
| permissions | jsonb | Override role defaults |
| last_login | timestamptz | |
| is_active | boolean | |
| created_at | timestamptz | |

Current owners: `jorge.rosales@xponencial.net`, `jorge.quintero@xponencial.net` (both superadmin)

### session_files (normalized — replaces raw_files JSONB for O(1) ops)
New writes go here AND to raw_files for backward compat. Report generation reads from here.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| session_id | uuid FK → sessions | ON DELETE CASCADE |
| filename | text | |
| storage_path | text | Path in Supabase Storage |
| type | text | image, audio, video, text, location |
| content_type | text | MIME type |
| size_bytes | integer | |
| transcription | text | Whisper result (audio/video) |
| image_description | text | Vision AI result (images) |
| content_category | text | BUSINESS/PERSONAL/NSFW/CONFIDENTIAL/UNCLEAR |
| blocked | boolean | NSFW content blocked |
| flagged | boolean | Personal/confidential flagged |
| pii_scrubbed | integer | Number of PII instances removed |
| latitude, longitude | double precision | Location data |
| address, label | text | |
| public_url | text | |
| timestamp | timestamptz | Client-side timestamp |
| created_at, updated_at | timestamptz | |

### failed_jobs (dead letter queue)
Worker failures stored for retry/review from backoffice.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| job_id | text | arq job ID |
| queue_name | text | DEFAULT 'preprocess' |
| function_name | text | |
| args_json | jsonb | Original job arguments |
| error | text | Truncated to 500 chars |
| error_type | text | Exception class name |
| retries | integer | DEFAULT 0 |
| status | text | CHECK: failed, retried, resolved |
| created_at | timestamptz | |
| resolved_at | timestamptz | |

### user_groups
Zone/team-based grouping for multi-level report aggregation.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| implementation_id | text FK → implementations | |
| name | text | e.g. 'Zona San Jose' |
| slug | text | e.g. 'zona_san_jose' |
| zone | text | Geographic zone |
| tags | text[] | DEFAULT '{}' |
| created_at | timestamptz | |

### session_facts
Structured facts extracted from reports — enables aggregation without re-reading raw media.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| session_id | uuid FK → sessions | |
| implementation_id | text | |
| framework | text | 'tactical', 'competidor', etc. |
| facts | jsonb | Structured extraction (entities, prices, alerts, sentiment) |
| key_quotes | text[] | Top 3-5 representative quotes |
| fact_count | integer | DEFAULT 0 |
| created_at | timestamptz | |

**facts JSONB structure:**
```json
{
  "entities_mentioned": [{"name": "Claro", "type": "competitor", "count": 3, "context": "promo agresiva"}],
  "prices_detected": [{"entity": "Claro", "item": "Internet 100Mbps", "price": 15000, "currency": "CRC"}],
  "alerts": [{"type": "competitive_threat", "severity": "high", "description": "...", "zone": "Heredia"}],
  "sentiment": {"positive": 2, "negative": 5, "neutral": 1},
  "zones_covered": ["Heredia"],
  "key_themes": ["pricing", "churn"]
}
```

## Supabase Storage

- **Bucket:** `media` (private)
- **Path pattern:** `{session_id}/{filename}` for user uploads, `reports/{session_id}/reporte_{date}.pdf` for generated PDFs
- **Access:** Use signed URLs (1h expiry) via `create_signed_urls()`

## Current Data

- 2 active implementations: `laundry_care` (CPG, sandbox number), `telecable` (Telecom CR, paid number, whitelist)
- `argos` and `eficacia` are inactive (legacy)
- Superadmins: `jorge.rosales@xponencial.net`, `jorge.quintero@xponencial.net`

## Migrations (chronological)

| File | Description |
|------|-------------|
| `sql/schema.sql` | Base tables (users, sessions, visit_reports) |
| `sql/002_multi_tenant.sql` | implementations, visit_types, backoffice_users |
| `sql/005_strategic_analysis.sql` | consolidated_reports table |
| `sql/006_laundry_care.sql` | Laundry care implementation + 3 frameworks |
| `sql/007_telecable.sql` | Telecable implementation + 3 frameworks |
| `sql/008_user_groups_and_facts.sql` | user_groups, session_facts |
| `sql/009_country_config_and_roles.sql` | country_config JSONB, user roles/country |
| `sql/010_usage_tracking.sql` | usage_monthly table |
| `sql/011_tenants_and_rls.sql` | backoffice_users table, RLS policies |
| `sql/012_atomic_file_append.sql` | PostgreSQL RPCs for atomic jsonb ops |
| `sql/013_supabase_hardening.sql` | search_path, indexes, constraints |
| `sql/014_vision_strategy.sql` | vision_strategy column + tiered default |
| `sql/015_session_files_table.sql` | Normalized session_files table + backfill |
| `sql/016_per_client_whatsapp_number.sql` | whatsapp_number column |
| `sql/017_access_control.sql` | access_mode column (open/whitelist) |
| `sql/018_fix_whatsapp_numbers.sql` | Sandbox for demo, paid for telecable |
| `sql/019_backoffice_owners.sql` | Owner users (run after SSO first login) |
| `sql/020_onboarding_config.sql` | onboarding_config JSONB + accepted_terms |
| `sql/021_failed_jobs.sql` | failed_jobs table (dead letter queue) |
| `sql/022_implementation_folder.sql` | folder column on implementations |
