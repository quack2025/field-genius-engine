# Database Schema

Supabase project: `sglvhzmwfzetyrhwouiw`
SQL files: `sql/schema.sql` (base) + `sql/002_multi_tenant.sql` (multi-tenant extensions)

## Tables

### users
Field executives and managers who send media via WhatsApp.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | auto-generated |
| implementation | text | 'argos', 'eficacia' (legacy field) |
| implementation_id | text FK → implementations | Added by migration 002 |
| phone | text UNIQUE | WhatsApp number for lookup (e.g. +573001234567) |
| name | text | |
| role | text | 'executive' or 'manager' |
| notification_group | text | WhatsApp group ID for shared reports |
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
  "body": "text content here"  // only for type=text|clarification_response
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

### implementations (multi-tenant)
Client configurations — each implementation = one customer.

| Column | Type | Notes |
|--------|------|-------|
| id | text PK | e.g. 'argos', 'eficacia' |
| name | text | Display name |
| industry | text | 'construction', 'fmcg', 'telecom' |
| country | text | DEFAULT 'CO' |
| language | text | DEFAULT 'es' |
| logo_url | text | |
| primary_color | text | DEFAULT '#003366' |
| status | text | CHECK: active, paused, archived |
| vision_system_prompt | text | What to look for in photos |
| segmentation_prompt_template | text | How to group visits |
| google_spreadsheet_id | text | |
| trigger_words | jsonb | DEFAULT ["reporte","generar","listo","fin"] |
| created_at, updated_at | timestamptz | |

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
Admin access control for backoffice.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK FK → auth.users | |
| email | text | |
| name | text | |
| role | text | CHECK: superadmin, admin, viewer |
| allowed_implementations | text[] | |
| created_at | timestamptz | |

## Supabase Storage

- **Bucket:** `media` (private)
- **Path pattern:** `{session_id}/{filename}` for user uploads, `reports/{session_id}/reporte_{date}.pdf` for generated PDFs
- **Access:** Use signed URLs (1h expiry) via `create_signed_urls()`

## Current Data

- 2 implementations: `argos` (construction), `eficacia` (FMCG)
- 5 visit types: 3 argos (ferreteria, obra_civil, obra_pequena), 2 eficacia (supermarket_visit, wholesale_visit)
- Admin user: jorgealejandrorosales@gmail.com
