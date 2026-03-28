# Backoffice Frontend

**Repo:** `quack2025/field-genius-backoffice`
**Path:** `C:\Users\jorge\field-genius-backoffice`
**URL:** `https://field-genius-backoffice.vercel.app`
**Branch:** `master` (not main)
**Deploy:** `vercel --prod` from repo root

## Stack

- React 18 + TypeScript
- Vite (build tool)
- Tailwind CSS 3 (NOT v4 — v4 had eresolve issues)
- Supabase Auth (email/password)
- No component library (raw HTML + Tailwind)
- Icons: lucide-react

## Pages

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | Dashboard | Stats cards (sessions, reports, avg confidence), time filter, breakdowns |
| `/implementations` | Implementations | Card grid with create form |
| `/implementations/:id` | ImplementationDetail | 4 tabs: Config, Visit Types, Prompts, Users |
| `/sessions` | Sessions | Filterable table (impl, status, dates) |
| `/sessions/:id` | SessionDetail | Media timeline + report generation buttons (3 frameworks) |
| `/reports` | Reports | Multi-level report generation: Individual / Grupo / Proyecto tabs |
| `/user-groups` | UserGroups | CRUD for groups + member management |

## API Client (`src/lib/api.ts`)

All calls go to `VITE_API_URL` (Railway backend). Response wrapper:
```typescript
interface ApiResponse<T> { success: boolean; data: T; error: string | null; }
```

Key interfaces: `Implementation`, `VisitType`, `User`, `Stats`, `Session`, `RawFile`, `VisitReport`, `UserGroup`, `GenerateReportResponse`, `MultiLevelReportResponse`

## Auth

- Supabase Auth via `src/hooks/useAuth.ts`
- Login with email/password → Supabase session
- Admin user: `jorgealejandrorosales@gmail.com`
- No RLS or JWT validation on backend yet (PENDING)

## Environment Variables

```
VITE_SUPABASE_URL=https://sglvhzmwfzetyrhwouiw.supabase.co
VITE_SUPABASE_ANON_KEY=<anon key>
VITE_API_URL=https://zealous-endurance-production-f9b2.up.railway.app
```

## Styling Patterns

- Brand color: `#003366` (brand-500 in tailwind.config.js)
- Cards: `bg-white rounded-lg shadow p-4`
- Tables: `bg-white rounded-lg shadow` → `table w-full text-sm`
- Buttons: `bg-brand-500 text-white px-4 py-2 rounded text-sm hover:bg-brand-600`
- Status badges: colored bg+text (blue=accumulating, green=completed, red=failed)

## TypeScript Notes

- `verbatimModuleSyntax` enabled — must use `import type {}` for type-only imports
- No `@/` path aliases — use relative imports
