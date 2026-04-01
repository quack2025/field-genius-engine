# Enterprise Readiness Audit — 2026-03-31

## Scores

| Auditor | Score | Key Finding |
|---------|-------|-------------|
| Security Engineer | 2/10 | 30+ endpoints sin auth, SSRF, secrets en .env |
| Backend Architect | 3/10 | Sync DB client bloquea event loop, race condition en raw_files |
| API Product Architect | 2/10 | Sin versioning, sin rate limiting, sin OpenAPI spec |
| Supabase Specialist | 3/10 | RLS bypassed por service_role, sin storage policies |
| **Promedio** | **2.5/10** | |

## Top 10 Blockers (cross-auditor consensus)

1. **30+ admin endpoints sin auth** — Todos los auditors. Cualquier persona puede CRUD todo.
2. **Supabase client sincrono** — Backend Architect. Bloquea event loop, server stalls.
3. **Race condition raw_files** — Backend + Supabase. Read-modify-write sin lock.
4. **Sin rate limiting** — Todos. curl loop quema budget AI.
5. **/test-db y /simulate en prod** — Security. Data leak + impersonation.
6. **/my-profile superadmin fallback** — Security + Supabase. Auth failure = admin access.
7. **Sin API versioning** — API Architect. Breaking changes rompen integraciones.
8. **Anthropic client per-request** — Backend. Connection leak bajo carga.
9. **Sin request IDs** — Backend + API. Imposible debuggear a escala.
10. **Sin OpenAPI spec** — API Architect. Ningun equipo puede integrar.

## Hardening Sprints

### Sprint E-1: SEGURIDAD (P0) — COMPLETADO 2026-03-31
- [x] Wire `Depends(get_current_user)` en todos los 30+ admin endpoints
- [x] Tenant filtering en queries de lista (sessions, implementations, stats, groups)
- [x] Permission checks: can_edit_frameworks, can_manage_users, can_generate_reports, etc.
- [x] Remover /test-db y /simulate de produccion (gated con ENVIRONMENT env var)
- [x] Fix /my-profile: eliminado fallback a superadmin en auth failure
- [x] Add slowapi rate limiting (5-20/min AI endpoints, 120/min global)
- [x] Fix SSRF en test-vision-prompt (HTTPS only, block private IPs)
- [x] Fix require_permission factory (removed async)
- [x] Singleton AsyncAnthropic client (eliminado connection leak)
- [x] Frontend envia JWT en todas las requests (api.ts getAuthHeaders)
- [ ] Rotar secrets: .env local NO apunta a produccion
- [ ] Validate phone E.164, role enum, session_id UUID

### Sprint E-2: PERFORMANCE (P1) — COMPLETADO 2026-04-01
- [x] Supabase async wrapping (asyncio.to_thread on ALL sync DB calls)
- [x] Atomic raw_files append (PostgreSQL RPC: jsonb || operator, SQL 012)
- [x] Singleton AsyncAnthropic client (module-level in analyzer.py)
- [x] Retention pagination (batches of 200, was unbounded)
- [x] Request ID middleware (X-Request-Id header + structlog contextvars)
- [x] Graceful shutdown handler (close Redis pool on SIGTERM)
- [ ] JSON structured logging en produccion (ConsoleRenderer still used)
- [ ] Fix datetime.date.today() → timezone-aware per user

### Sprint E-3: API PRODUCT (P1) — COMPLETADO 2026-04-01
- [x] /v1/ prefix: routes at /v1/api/admin/* (backwards compat at /api/admin/*)
- [x] Standardized error responses: { error: { code, message, request_id } }
- [x] Error handlers: HTTPException, ValidationError, unhandled (500s never leak)
- [x] Pagination metadata on /sessions: { pagination: { total, limit, offset, has_more } }
- [x] OpenAPI spec enhanced: title, description, auth docs, rate limit docs, tags
- [x] Available at /docs (Swagger UI) and /redoc (ReDoc)
- [ ] Custom domain: api.fieldgenius.io
- [ ] Idempotency-Key header en POST endpoints
- [ ] Async report generation (return 202 + job_id, poll for result)

### Sprint E-4: SUPABASE HARDENING (P1, 1 dia)
- [ ] SET search_path = public en funciones SECURITY DEFINER
- [ ] RLS policies para INSERT/UPDATE/DELETE (no solo SELECT)
- [ ] Storage bucket policies para media bucket
- [ ] Index en sessions(implementation) para RLS performance
- [ ] CHECK constraint en users.role
- [ ] Migrate RLS policies to use implementation_id consistently
- [ ] NOT NULL constraint en implementation_id
- [ ] updated_at trigger automatico (moddatetime)
- [ ] CREATE TABLE IF NOT EXISTS para consolidated_reports en migracion

### Sprint E-5: OBSERVABILITY (P2, 1 dia)
- [ ] Health check con dependency status (Supabase, Anthropic, OpenAI, Twilio)
- [ ] Correlation IDs propagated through pipeline (trace_id)
- [ ] Dead letter queue + alerting on failed jobs
- [ ] Backpressure signal to WhatsApp users (estimated wait time)
- [ ] Usage metering middleware (per-tenant API call tracking)

### Sprint E-6: HARDENING (P2, 1 dia)
- [ ] Pin dependency versions (pip-compile lockfile)
- [ ] Remove weasyprint if PDF not in use
- [ ] Hardcode webhook public URL (don't trust X-Forwarded-* headers)
- [ ] Move CORS origins to env vars
- [ ] Integration tests with test Supabase project
- [ ] Webhook event system for customers (future upsell)

## Context
- Platform: Field Genius Engine (multi-tenant field intelligence SaaS)
- Target customer: Telecable (1,000+ users, multi-country)
- Stack: FastAPI + Supabase + Redis + Railway + Vercel
- Revenue target: $6-8K/month
