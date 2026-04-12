# API Endpoints — Radar Xponencial Engine

Base URL (production): `https://zealous-endurance-production-f9b2.up.railway.app`

All `/api/admin/*` endpoints are also available at `/v1/api/admin/*`. The unversioned routes include `Deprecation: true` + `Sunset: 2026-10-01` headers.

## Authentication

All `/api/admin/*` endpoints require JWT from Supabase Auth in `Authorization: Bearer <token>` header.

Permission model (`backoffice_users.role`):
- `superadmin` — full access, bypasses implementation checks
- `admin` — manage users, generate reports, edit implementations
- `analyst` — read-only + generate reports
- `viewer` — read-only

## Health & Debug

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Basic health check (always returns 200) |
| GET | `/health/deep` | Verifies Redis, Supabase, Anthropic key format, OpenAI key format |

## WhatsApp Webhook

| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhook/whatsapp` | Twilio webhook (form-encoded). Dedup via MessageSid (5min TTL). Pipeline runs in background. |

## Admin API (`/api/admin/*`)

### Implementations (Proyectos)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/implementations` | List (paginated: limit, offset) |
| POST | `/implementations` | Create new |
| GET | `/implementations/:id` | Get by ID |
| PUT | `/implementations/:id` | Update — supports all editable fields including `folder`, `whatsapp_number`, `access_mode`, `vision_strategy`, `onboarding_config` |
| DELETE | `/implementations/:id` | Soft delete (status→inactive) |

### Visit Types

| Method | Path | Description |
|--------|------|-------------|
| GET | `/implementations/:id/visit-types` | List for implementation |
| POST | `/implementations/:id/visit-types` | Create |
| PUT | `/visit-types/:vtId` | Update |
| DELETE | `/visit-types/:vtId` | Soft delete |

### Users (Field Agents)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/implementations/:id/users` | List (paginated) |
| POST | `/implementations/:id/users` | Upsert user |
| DELETE | `/implementations/:id/users/:phone` | Remove user |
| POST | `/implementations/:id/bulk-import-users` | CSV bulk import |

### Sessions (read-only)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/sessions` | List with filters + pagination |
| GET | `/sessions/:id` | Full detail with signed media URLs |

### Stats & Config

| Method | Path | Description |
|--------|------|-------------|
| GET | `/stats?impl=X&days=7` | Session/report counts and breakdowns |
| POST | `/reload-config?impl_id=X` | Clear config cache (auto-invalidates after 5min) |
| GET | `/usage` | Monthly usage + queue stats |

### User Groups

| Method | Path | Description |
|--------|------|-------------|
| GET | `/user-groups?impl=X` | List (paginated) |
| POST | `/implementations/:id/user-groups` | Create group |
| POST | `/user-groups/:groupId/members` | Add member |
| DELETE | `/user-groups/:groupId/members/:phone` | Remove member |

### Report Generation & Persistence

| Method | Path | Description |
|--------|------|-------------|
| POST | `/generate-report` | Generate report for session (rate limited 20/min) |
| POST | `/generate-group-report` | Group-level report |
| POST | `/generate-project-report` | Project-wide report |
| GET | `/reports` | List saved reports (paginated, filter by session_id/impl/framework) |
| GET | `/reports/:id` | Get saved report |

### Export

| Method | Path | Description |
|--------|------|-------------|
| POST | `/export-gamma` | Export report markdown to Gamma (API or clipboard content) |
| POST | `/export-sheets` | Export facts + compliance to Google Sheets tabs |

### Compliance

| Method | Path | Description |
|--------|------|-------------|
| GET | `/compliance?implementation_id=X&date_from&date_to` | User activity + summary stats |

### Digest (Cron)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/send-digest?implementation_id=X` | Send digest email (omit impl to send for all) |
| POST | `/test-digest` | Send test digest to specific email (superadmin only) |

### Backoffice Users

| Method | Path | Description |
|--------|------|-------------|
| GET | `/backoffice-users` | List (paginated, superadmin only) |
| POST | `/backoffice-users` | Create (superadmin only) |
| PUT | `/backoffice-users/:id` | Update role/permissions (typed `BackofficeUserUpdate` model) |
| GET | `/my-profile` | Current user's profile |

### Failed Jobs (Dead Letter Queue)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/failed-jobs` | List failed jobs (paginated, status filter, superadmin only) |
| POST | `/failed-jobs/:id/retry` | Re-enqueue to arq worker |
| POST | `/failed-jobs/:id/resolve` | Mark as manually resolved |

### Retention

| Method | Path | Description |
|--------|------|-------------|
| POST | `/run-retention?dry_run=true` | Delete media older than 90 days (superadmin) |

### Testing (Prompt Engineering)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/test-vision-prompt` | Test vision prompt against image URL (AsyncAnthropic + SSRF hardened) |
| POST | `/test-extraction` | Test extraction schema against text (AsyncAnthropic) |

## CORS

Allowed origins (from `CORS_ORIGINS` env var):
- `http://localhost:5173`, `http://localhost:3000`
- `https://app.xponencial.net` (primary)
- `https://field-genius-backoffice.vercel.app` (fallback)
- `https://xponencial.net`, `https://www.xponencial.net`

## Rate Limits

All admin endpoints share a single `Limiter` instance (fixed in Sprint E-4):
- Global default: 120/min per IP
- AI-invoking endpoints: 5-20/min (`@limiter.limit("X/minute")`)

## Response Format

Success:
```json
{
  "success": true,
  "data": <T>,
  "pagination": { "total": 100, "limit": 50, "offset": 0, "has_more": true },
  "error": null
}
```

Error (standardized, no `str(e)` leaks):
```json
{
  "error": {
    "code": "internal_error",
    "message": "Internal error",
    "request_id": "uuid"
  }
}
```

## Security notes

- `Deprecation: true` + `Sunset: 2026-10-01` headers on `/api/admin/*` (use `/v1/api/admin/*` going forward)
- PII auto-masking in all logs (structlog processor: `phone` → `+57***4567`)
- Magic byte validation on file uploads (rejects content/type mismatch)
- SSRF: DNS resolution check + no redirects on `test-vision-prompt`
- Webhook signature: header fallback only in development mode
- `ENVIRONMENT=production` disables OpenAPI docs + enforces auth
