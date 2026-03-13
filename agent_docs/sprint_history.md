# Sprint History

## Completed Sprints

### Sprint 1-4: Engine Foundation (Pre-backoffice)
- FastAPI setup, Pydantic Settings, Supabase schema + seed
- WhatsApp webhook (Twilio), media download to Supabase Storage
- Session manager (daily batch accumulation, trigger detection)
- Full pipeline: segmentation (Phase 1) → extraction (Phase 2)
- Outputs: Google Sheets (working), PDF/Gamma (temporarily disabled)
- First implementation: Argos (3 visit types)

### Sprint A: Multi-Tenant Decoupling
- `implementations` table + `visit_types` table in DB
- `config_loader.py` — DB-first, file-fallback config
- Removed 5 Argos hardcodes from vision.py, segmenter.py, extractor.py, sheets.py
- Session-Implementation wiring (user.implementation_id → session)
- `backoffice_users` table for admin access

### Sprint B: Admin API
- 16 endpoints in `src/routes/admin.py`
- CRUD: implementations, visit types, users
- Stats, config reload, prompt testing (vision + extraction)
- Pydantic models for request validation
- Soft deletes (status→inactive, is_active→false)

### Sprint C: Backoffice Scaffold
- New repo: `quack2025/field-genius-backoffice`
- React 18 + Vite + Tailwind 3 + Supabase Auth
- Pages: Login, Dashboard, Implementations, ImplementationDetail (4 tabs)
- Deployed to Vercel

### Sprint D: Second Client (Eficacia)
- Created `eficacia` implementation (FMCG industry)
- 2 visit types: supermarket_visit (5 categories), wholesale_visit (4 categories)
- FMCG-specific vision and segmentation prompts
- Seeded via `scripts/seed_eficacia.py`

### Post-Sprint Fixes
- CORS middleware added to engine (backoffice + xponencial.net)
- Railway domain updated (service rename)
- Supabase service_role key leak fixed (GitGuardian alert)
- Sessions page + SessionDetail with media timeline viewer
- Signed URLs for private storage bucket

## Pending Items

See `PENDING_NOTES.md` for the full living checklist. Key items:

### Security
- Admin API authentication (JWT + backoffice_users)
- Rate limiting
- Auth on /api/simulate and /api/test-db

### Pipeline
- PDF and Gamma outputs (disabled — need cairo/pango on Railway)
- Trigger words per implementation (currently hardcoded)

### Eficacia Onboarding
- Google Spreadsheet creation
- Assign real user phones
- End-to-end WhatsApp test

### Infrastructure
- Twilio webhook URL update to new Railway domain
- Automated tests
- WeasyPrint dependencies on Railway
