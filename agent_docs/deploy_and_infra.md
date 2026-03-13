# Deploy & Infrastructure

## Railway (Engine Backend)

- **Service:** Field Genius Engine
- **Domain:** `zealous-endurance-production-f9b2.up.railway.app`
  - NOTE: Old domain `field-genius-engine.up.railway.app` is STALE (service was renamed)
- **Auto-deploy:** On push to `main` branch
- **Health check:** `GET /health`
- **Runtime:** Python 3.12

### Environment Variables (Railway)

```
SUPABASE_URL=https://sglvhzmwfzetyrhwouiw.supabase.co
SUPABASE_ANON_KEY=<anon key>
SUPABASE_SERVICE_ROLE_KEY=<service role key — MUST BE ROTATED after GitGuardian leak>
OPENAI_API_KEY=<whisper>
ANTHROPIC_API_KEY=<claude>
TWILIO_ACCOUNT_SID=<sid>
TWILIO_AUTH_TOKEN=<token>
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
DEFAULT_IMPLEMENTATION=argos
```

## Vercel (Backoffice Frontend)

- **URL:** `https://field-genius-backoffice.vercel.app`
- **Deploy:** `cd field-genius-backoffice && vercel --prod --yes`
- **Framework:** Vite (auto-detected)
- **SPA routing:** `vercel.json` with rewrite `/(.*) → /`
- **Branch:** `master`

### Environment Variables (Vercel)

```
VITE_SUPABASE_URL=https://sglvhzmwfzetyrhwouiw.supabase.co
VITE_SUPABASE_ANON_KEY=<anon key>
VITE_API_URL=https://zealous-endurance-production-f9b2.up.railway.app
```

## Supabase

- **Project ID:** `sglvhzmwfzetyrhwouiw`
- **Migrations:** NOT auto-deployed — run manually in SQL Editor
- **Storage bucket:** `media` (private)
- **Auth:** Email/password for backoffice admins

## Twilio / WhatsApp

- **Webhook URL:** Must point to `https://zealous-endurance-production-f9b2.up.railway.app/webhook/whatsapp`
- **NOTE:** If Twilio was configured with old domain, it needs updating

## Security Notes

- **CRITICAL:** Supabase service_role key was leaked via GitGuardian (Mar 13, 2026). The key in `scripts/seed_eficacia.py` was removed (commit `73c0d53`), but the key MUST be rotated in Supabase Dashboard → Settings → API → Rotate.
- Admin API (`/api/admin/*`) is currently unauthenticated
- `/api/simulate` and `/api/test-db` are unauthenticated
- No rate limiting on any endpoint
