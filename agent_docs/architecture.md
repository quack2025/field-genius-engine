# Architecture Overview

## System Components

```
                    [WhatsApp]
                        |
                    [Twilio]
                        |
        [FastAPI Engine] ← Railway (zealous-endurance-production-f9b2.up.railway.app)
           /    |     \
    [Supabase] [Claude] [Whisper]
     DB+Storage  Vision   Transcription
          |
    [Backoffice] ← Vercel (field-genius-backoffice.vercel.app)
     React SPA
```

## Repos

| Repo | Path | Stack | Deploy |
|------|------|-------|--------|
| `quack2025/field-genius-engine` | `C:\Users\jorge\field-genius-engine` | Python 3.12, FastAPI | Railway (auto-deploy on push to main) |
| `quack2025/field-genius-backoffice` | `C:\Users\jorge\field-genius-backoffice` | React 18, Vite, Tailwind 3 | Vercel (`vercel --prod`) |

## Supabase

- Project: `sglvhzmwfzetyrhwouiw`
- Storage bucket: `media` (private — use signed URLs)
- Auth: Used by backoffice (email/password login)

## Engine Structure

```
src/
├── main.py                        # FastAPI app, CORS, router mounting
├── config/settings.py             # Pydantic Settings (all env vars)
├── engine/                        # CORE — never imports from implementations/
│   ├── config_loader.py           # DB-first, file-fallback config
│   ├── media_downloader.py        # Twilio → Supabase Storage
│   ├── pipeline.py                # 7-step orchestrator
│   ├── segmenter.py               # Phase 1: identify visits in batch
│   ├── extractor.py               # Phase 2: structured extraction per visit
│   ├── vision.py                  # Claude Sonnet image analysis
│   ├── transcriber.py             # Whisper audio → text
│   ├── video.py                   # ffmpeg frame sampling
│   ├── consolidator.py            # Merge transcriptions + vision + text
│   ├── schema_builder.py          # JSON schema → system prompt
│   └── supabase_client.py         # All DB queries (singleton client)
├── implementations/argos/         # File-based schemas (legacy, DB preferred)
├── channels/whatsapp/
│   ├── webhook.py                 # POST /webhook/whatsapp
│   ├── sender.py                  # Send messages/media via Twilio
│   └── session_manager.py         # Daily batch accumulation + trigger detection
├── outputs/
│   ├── sheets.py                  # Google Sheets writer
│   └── gamma.py                   # Gamma API presentations
├── routes/
│   ├── admin.py                   # Backoffice CRUD API (16 endpoints)
│   └── simulate.py                # Test endpoint (no Twilio needed)
└── utils/
    ├── logger.py                  # Structured JSON logging
    └── pdf.py                     # WeasyPrint PDF generation
```

## Backoffice Structure

```
src/
├── App.tsx                        # BrowserRouter, auth guard, routes
├── lib/
│   ├── api.ts                     # Typed API client (all admin endpoints)
│   └── supabase.ts                # Supabase client (auth only)
├── hooks/useAuth.ts               # Supabase session management
├── components/
│   ├── Layout.tsx                 # Sidebar + Outlet
│   └── Sidebar.tsx                # Navigation + reload + signout
└── pages/
    ├── Login.tsx                   # Email/password form
    ├── Dashboard.tsx               # Stats cards + breakdowns
    ├── Implementations.tsx         # List + inline create
    ├── ImplementationDetail.tsx    # 4-tab detail (config, visit-types, prompts, users)
    ├── Sessions.tsx                # Filterable session list
    ├── SessionDetail.tsx           # Media timeline + visit reports
    └── tabs/
        ├── VisitTypesTab.tsx
        ├── PromptsTab.tsx
        └── UsersTab.tsx
```

## Key Design Principles

1. **Engine is implementation-agnostic** — `src/engine/` never imports from `src/implementations/`
2. **DB-first, file-fallback** — ConfigLoader tries Supabase first, falls back to JSON files
3. **Daily batch model** — User sends media all day, triggers processing with "reporte"
4. **Fire-and-forget outputs** — Sheets/Gamma failures don't block the pipeline
5. **Signed URLs for media** — Storage bucket is private, backend generates 1-hour signed URLs
