# Enterprise Audit — Field Genius Engine
**Date:** 2026-04-05
**Target:** 1,000 users (Telecable, telecom, Central America)

## Scores (Pre-Remediation)

| Agent | Score | Verdict |
|-------|-------|---------|
| Security Engineer | 4/10 | NOT enterprise ready |
| Backend Architect | 4.5/10 | Solid MVP, fundamental scale gaps |
| API Product Architect | 4.5/10 | Functional prototype, not enterprise |
| Performance Benchmarker | 3/10 | Will fail at ~50-100 users |
| **Average** | **4/10** | **2-3 weeks to enterprise** |

## Post-Remediation Status: ~7.5/10
All 10 sprints (E-1 to E-6 + O-1 to O-4) completed same day.
Estimated capacity: 500-700 users. For 1,000: separate worker process on Railway.

## CRITICAL Issues (P0 — showstoppers)

### SEC-C1. Live secrets in .env file
- `.env` has production Twilio, Supabase, Anthropic, OpenAI, Google keys
- Must rotate ALL keys immediately
- Add pre-commit hook (gitleaks/truffleHog)

### SEC-C2 / ARCH-H4. Auth bypass in transition mode
- `ENVIRONMENT=transition` grants superadmin to anonymous users
- Currently SET in Railway production
- Remove transition mode entirely

### SEC-C3. OpenAPI docs exposed in production
- `/docs` and `/redoc` accessible without auth
- Exposes full attack surface map
- Disable in production

### PERF-C1 / ARCH-C1. Event loop starvation (sync clients)
- `content_safety.py`: sync `Anthropic()` blocks 1-3s per image
- `transcriber.py`: sync `OpenAI()` blocks 3-5s per audio
- `media_downloader.py`: sync Supabase upload
- At 5,000 photos/day, server stops responding
- **Fix:** Replace with AsyncAnthropic/AsyncOpenAI

### ARCH-C2 / API-C5. Pipeline blocks webhook response
- `webhook.py:195` runs full AI pipeline inline (30-120s)
- Twilio timeout = 15s → retry → duplicate processing
- **Fix:** Enqueue to Redis/arq, return 200 immediately

### API-C4 / ARCH-C5. No webhook idempotency
- No MessageSid dedup
- Twilio retry = double AI costs
- **Fix:** Redis set with MessageSid + 5min TTL

### API-C6 / ARCH-H6. Rate limiter is broken
- `admin.py` creates orphaned Limiter (never connected to app)
- Only per-IP (useless behind load balancer)
- **Fix:** Single shared Limiter, per-user keying

## HIGH Issues (P1)

### PERF-H1. Base64 memory explosion
- 40 concurrent images × 6.7MB base64 = 268MB
- Railway 512MB-1GB → OOM kills
- **Fix:** Resize to 1024px before base64, stream-process

### ARCH-H5. JSONB raw_files doesn't scale
- O(n²) read-modify-write per session
- **Fix:** Normalize to `session_files` table

### SEC-H2. Phone numbers logged in plaintext (20+ sites)
- PII compliance violation (GDPR, Ley 1581)
- **Fix:** `mask_phone()` utility + structlog processor

### SEC-H5. Redis URL password logged at startup
- `main.py:128` logs first 30 chars including password
- **Fix:** Parse URL, log only host:port

### SEC-H6. Supabase client falls back to anon key silently
- If service role key is empty → anon key used → RLS blocks backend
- **Fix:** Fail fast on missing service role key

### API-H2. No pagination on most list endpoints
- Only sessions has pagination; 7 other lists return all rows
- 1,000 users → unbounded responses

### ARCH-H1. No backpressure on AI calls during segmentation
- Worker semaphore (40) only applies to preprocessing
- 100 simultaneous reports → 100 unthrottled Sonnet calls

### ARCH-H3. Config cache never invalidates
- In-memory dict, no TTL
- Admin updates stale until redeploy

### ARCH-H7. 5 separate Anthropic client singletons
- vision.py, analyzer.py, extractor.py, segmenter.py, content_safety.py
- Segmenter creates NEW client on every call
- **Fix:** Single shared factory

### API-H1. Two competing error response formats
- Endpoints: `{success, data, error}`
- Error handler: `{error: {code, message, request_id}}`

### SEC-H3. SSRF protection incomplete
- No DNS rebinding protection
- No redirect blocking
- Missing IPv6 loopback

### SEC-H1. No file type validation / malware scanning
- `store_bytes` accepts anything, no size limit
- No ClamAV or equivalent

## MEDIUM Issues (P2) — 25+ items across all audits

Key items:
- No OpenAPI response schemas (all endpoints → dict)
- No date parameter validation
- Raw dict body on user updates
- Content safety fails open on error
- PII regex incomplete (no names, addresses)
- No request body size limits
- UUID path params not validated
- In-memory menu state (lost on restart)
- No dead letter queue / retry visibility
- Video temp files without size limits
- No database migrations framework
- Deprecated FastAPI lifecycle events
- Bulk import N+1 queries (sequential)

## Cost Projection at 1,000 Users

| Category | Monthly |
|----------|---------|
| Claude Sonnet (vision) | $2,250 |
| Claude Sonnet (segmentation + extraction + analysis) | $2,850 |
| Claude Haiku (classification + facts) | $240 |
| OpenAI Whisper | $360 |
| **Total AI** | **$5,700** |
| Railway + Redis | $50 |
| Supabase Pro | $25 |
| Storage bandwidth | $150 |
| **Total Infra** | **$225** |
| **TOTAL** | **$5,925/mo** |
| Per user | $5.93/user |
| At $6K/mo pricing | **$75/mo margin (1.3%)** |

**Note:** Margin is nearly zero with Sonnet Vision. Tiered approach (Haiku first → Sonnet escalation) would cut to ~$3,700/mo = $2,300 margin (38%).

## Scalability Verdict

| Users | Status | Requirements |
|-------|--------|-------------|
| 1-50 | Works today | Current architecture |
| 50-100 | Will degrade | Fix sync clients (PERF-C1) |
| 100-300 | Requires fixes | + async pipeline + idempotency |
| 300-700 | Requires arch changes | + separate worker process + image resize |
| 700-1000 | Requires full hardening | + normalized DB + distributed semaphore + multi-container |

## Recommended Sprint Priority

### Sprint E-1: Async Everything (2 days)
- Replace sync Anthropic → AsyncAnthropic in content_safety.py
- Replace sync OpenAI → AsyncOpenAI in transcriber.py
- Wrap sync Supabase calls in media_downloader.py, pipeline.py, retention.py
- Single shared AsyncAnthropic factory
- Increase thread pool to 100

### Sprint E-2: Webhook Hardening (1 day)
- Enqueue pipeline to arq (not inline)
- MessageSid dedup in Redis (5min TTL)
- Return 200 immediately from webhook
- Move menu state to Redis

### Sprint E-3: Security Hardening (1 day)
- Remove auth bypass / transition mode
- Rotate all secrets
- Disable /docs in production
- Fix Redis URL logging
- Fail fast on missing service role key
- Phone number masking in logs

### Sprint E-4: Rate Limiting + Validation (1 day)
- Single shared Limiter connected to app
- Per-user rate limiting (not IP-only)
- Webhook rate limiting per phone
- Date parameter validation
- Phone number E.164 validation
- Request body size limits
- Pydantic response models

### Sprint E-5: Database + Performance (2 days)
- Normalize raw_files → session_files table
- Pagination on all list endpoints
- Image resize before base64 (1024px max)
- Config cache with 5min TTL
- Shared AI semaphore across all call sites
- SQL COUNT aggregation for stats

### Sprint E-6: Infrastructure (1 day)
- Separate arq worker process on Railway
- Circuit breakers with tenacity + jitter
- Health check caching (5min for Anthropic)
- Full UUID request IDs
- Request/response logging middleware
- Startup validation for required env vars

**Total estimated: 8 days focused work**
