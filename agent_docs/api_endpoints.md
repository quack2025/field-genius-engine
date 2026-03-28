# API Endpoints

Base URL (production): `https://zealous-endurance-production-f9b2.up.railway.app`

## Health & Debug

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/test-db` | Query first user from DB (no auth) |

## WhatsApp Webhook

| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhook/whatsapp` | Twilio webhook (form-encoded) |
| GET | `/webhook/whatsapp` | Twilio verification challenge |

## Simulate (Testing)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/simulate` | Simulate WhatsApp message (form: phone, body, file) |
| GET | `/api/sessions/{phone}` | Get today's session for phone |

## Admin API (`/api/admin/*`)

**NOTE:** Currently unauthenticated — auth via JWT + backoffice_users is pending.

### Implementations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/implementations` | List all |
| POST | `/api/admin/implementations` | Create new |
| GET | `/api/admin/implementations/:id` | Get by ID |
| PUT | `/api/admin/implementations/:id` | Update fields |
| DELETE | `/api/admin/implementations/:id` | Soft delete (status→inactive) |

### Visit Types

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/implementations/:id/visit-types` | List for implementation |
| POST | `/api/admin/implementations/:id/visit-types` | Create new |
| PUT | `/api/admin/visit-types/:vtId` | Update |
| DELETE | `/api/admin/visit-types/:vtId` | Soft delete (is_active→false) |

### Users

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/implementations/:id/users` | List users |
| POST | `/api/admin/implementations/:id/users` | Assign user (upsert) |
| DELETE | `/api/admin/implementations/:id/users/:phone` | Remove user |

### Sessions (read-only)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/sessions` | List with filters (impl, phone, status, date_from, date_to, limit, offset) |
| GET | `/api/admin/sessions/:id` | Full detail with signed media URLs + visit reports |

### Stats & Config

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/stats?impl=X&days=7` | Session/report counts and breakdowns |
| POST | `/api/admin/reload-config?impl_id=X` | Clear config cache |

### User Groups

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/user-groups?impl=X` | List groups (optional impl filter) |
| POST | `/api/admin/implementations/:id/user-groups` | Create group { name, slug, zone?, tags? } |
| POST | `/api/admin/user-groups/:groupId/members` | Add member { phone } |
| DELETE | `/api/admin/user-groups/:groupId/members/:phone` | Remove member |

### Report Generation

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/admin/generate-report` | Generate report for 1 session { session_id, report_type } |
| POST | `/api/admin/generate-group-report` | Generate group-level report { group_id, framework, date_from?, date_to? } |
| POST | `/api/admin/generate-project-report` | Generate project-wide report { implementation_id, framework, date_from?, date_to? } |
| POST | `/api/admin/trigger-pipeline/:sessionId` | Manually trigger old pipeline (legacy) |
| POST | `/api/admin/consolidate-analysis` | Consolidate per-visit analyses (legacy) |

`report_type` / `framework` values depend on the implementation's `analysis_framework` config:
- **laundry_care**: `tactical`, `strategic`, `innovation`
- **telecable**: `competidor`, `cliente`, `comunicacion`
- Use `"all"` as report_type to generate all frameworks in parallel.

### Testing (Prompt Engineering)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/admin/test-vision-prompt` | Test vision prompt against image URL (uses Sonnet) |
| POST | `/api/admin/test-extraction` | Test extraction schema against text (uses Haiku) |

## CORS

Allowed origins:
- `http://localhost:5173`
- `http://localhost:3000`
- `https://field-genius-backoffice.vercel.app`
- `https://xponencial.net`
- `https://www.xponencial.net`

## Response Format

All endpoints return:
```json
{
  "success": true,
  "data": <T>,
  "error": null
}
```
