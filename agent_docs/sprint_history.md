# Sprint History — Radar Xponencial Engine

## Foundation (Sprints 1-5, Early 2026)
- FastAPI setup, Pydantic Settings, Supabase schema + seed
- WhatsApp webhook (Twilio), media download to Supabase Storage
- Session manager (daily batch accumulation, trigger detection)
- Full pipeline: segmentation (Phase 1) → extraction (Phase 2)
- Outputs: Google Sheets (working), PDF/Gamma (temporarily disabled)
- First implementation: Argos (3 visit types)

## Multi-Tenant + Admin (Sprints A-D)
- `implementations` + `visit_types` tables in DB
- `config_loader.py` — DB-first, file-fallback config
- Removed hardcodes from engine (fully agnostic)
- Admin API with CRUD endpoints
- Backoffice frontend (Vercel, React 19 + Vite)

## Pre-processing + Multi-Implementation (Sprints 6-7)
- Media preprocessed at ingestion (Vision + Whisper in background)
- `laundry_care` implementation (CPG demo with 3 frameworks)
- `telecable` implementation (Telecom CR)
- WhatsApp menu for project switching
- On-demand report generation from backoffice

## Multi-Level Reports (Sprint 8)
- User groups for zone-based aggregation
- Session facts extraction
- Group-level and project-level reports
- Reports page (Individual / Grupo / Proyecto tabs)
- UserGroups page (CRUD + member management)

## Sprint R-1: Report Persistence + Export (Apr 5 2026)
- Report persistence: saved reports load on page revisit (no re-generation)
- Gamma export endpoint + UI buttons
- Google Sheets export (facts + compliance)
- Compliance page (user activity tracking)

## Enterprise Audit (Apr 5 2026)
4 specialized agents audited: Security, Backend Architect, API Architect, Performance Benchmarker.
**Score: 4/10** (would fail at ~50 users)

Full report: `enterprise_audit_2026_04_05.md`

## Sprints E-1 to E-6: Enterprise Hardening P0 (Apr 5 2026)

| Sprint | Focus | Key changes |
|--------|-------|-------------|
| E-1 | Async Everything | content_safety, transcriber, media_downloader, preprocessor, pipeline, retention, segmenter all async. Thread pool 100. |
| E-2 | Webhook Hardening | MessageSid dedup, pipeline in background (not inline) |
| E-3 | Security | Removed transition auth bypass, disabled OpenAPI in prod, fixed Redis URL leak, fail-fast on missing service role key |
| E-4 | Rate Limiting | Shared Limiter singleton (was orphaned), date validation |
| E-5 | Performance | Config cache TTL 5min, shared AI semaphore (40 max), full UUID request IDs |
| E-6 | Infrastructure | Request/response logging middleware, health check optimization |

**Score after E-1 to E-6: 7.5/10**

## Sprints O-1 to O-4: Performance Optimization (Apr 5 2026)

| Sprint | Focus | Impact |
|--------|-------|--------|
| O-1 | Image resize (1536px max) | Memory: 268MB → 16MB at 40 concurrent |
| O-2 | Jittered retries | Prevents thundering herd on AI API recovery |
| O-3 | session_files normalized table | O(1) inserts vs O(n²) JSONB read-modify-write |
| O-4 | Separate worker process | Procfile with web + worker processes |

## Vision Strategy — Tiered (Apr 5 2026)
A/B tested Sonnet vs Haiku on real pharmacy photos (Medellin). **Haiku outperformed Sonnet:**
- 1.8x more content (5,500 vs 3,000 chars)
- 1.6x more brands identified
- 52% cheaper per image
- Tiered (Haiku first → Sonnet fallback on poor result) is now default

## Sprints E-7 to E-9: P0 Security/API (Apr 6 2026)

| Sprint | Focus |
|--------|-------|
| E-7 | Magic byte validation, PII auto-masking via structlog processor, SSRF hardening (DNS check + redirect blocking), webhook signature header fallback removed |
| E-8 | All 17 `detail=str(e)` leaks eliminated, `BackofficeUserUpdate` Pydantic model, test-extraction async |
| E-9 | Pagination on all list endpoints, deprecation headers on unversioned routes |

**Score after E-7 to E-9: 9.0/10**

## Sprints E-10 to E-12: P1 Enterprise (Apr 6 2026)

| Sprint | Focus |
|--------|-------|
| E-10 | Dead letter queue: `failed_jobs` table, worker context on failure, admin endpoints (list/retry/resolve) |
| E-11 | Session files dual-read: `get_session_files()` helper, analyzer + report generation read from normalized table |
| E-12 | FastAPI `lifespan` context manager (replaces deprecated `on_event`), migration runner script |

**Score after E-10 to E-12: ~9.6/10**

## WhatsApp UX + Enterprise Features (Apr 6-10 2026)

### Per-client WhatsApp numbers (SQL 016, 018)
- `whatsapp_number` column on implementations
- Webhook resolves implementation from incoming `To` number
- Sender uses per-implementation number
- laundry_care: `+14155238886` (sandbox, demos)
- telecable: `+17792284312` (paid, exclusive)

### Whitelist access control (SQL 017)
- `access_mode` column: `open` | `whitelist`
- Webhook rejects unknown users with configurable message
- telecable: whitelist (enforced)
- laundry_care: open (demo)

### Configurable onboarding (SQL 020)
- `onboarding_config` JSONB on implementations
- `welcome_message`, `terms_accepted_message`, `rejection_message`, `first_photo_hint`
- `require_terms` toggle — user must reply "acepto" before processing
- `accepted_terms` + `onboarded_at` columns on users

### Daily digest emails
- `digest.enabled`, `digest.emails`, `digest.frequency` in onboarding_config
- `POST /api/admin/send-digest` cron endpoint
- Email via Resend API
- HTML digest with stats, top users, inactive users, cost estimate
- Railway cron or manual trigger

### Rebrand (Apr 10 2026)
- Field Genius → Radar Xponencial (UI only)
- Implementaciones → Proyectos
- Project folders (SQL 022) for organization
- Backoffice UI: all new fields editable from ImplementationDetail config tab

---

## SQL Migrations Summary

| File | Purpose |
|------|---------|
| 001-005 | Foundation (users, sessions, visit_reports, implementations, visit_types, strategic_analysis) |
| 006 | laundry_care implementation + 3 frameworks |
| 007 | telecable implementation + 3 frameworks |
| 008 | user_groups + session_facts tables |
| 009 | country_config + user roles/country |
| 010 | usage_monthly table |
| 011 | backoffice_users + RLS policies |
| 012 | Atomic jsonb file append RPC |
| 013 | Supabase hardening (search_path, indexes, constraints) |
| 014 | vision_strategy column + tiered default |
| 015 | session_files normalized table + backfill |
| 016 | whatsapp_number column (per-client) |
| 017 | access_mode column (open/whitelist) |
| 018 | Fix WhatsApp numbers (sandbox for laundry_care, paid for telecable) |
| 019 | Backoffice owner users (run after SSO first login) |
| 020 | onboarding_config JSONB + accepted_terms/onboarded_at on users |
| 021 | failed_jobs table (dead letter queue) |
| 022 | folder column on implementations |

---

## Current State (Apr 10 2026)

- **Audit score:** ~9.6/10
- **Capacity:** 500-700 users comfortably, 1000+ with separate worker service on Railway
- **Active projects:** laundry_care (demo), telecable (enterprise pilot)
- **Pending items for full production:**
  - Twilio webhook URL configured for `+17792284312`
  - Bulk import Telecable employees via CSV
  - Railway cron for daily digest (7pm)
  - Deploy worker as separate Railway service for 1000+ scale
