# Backoffice Frontend — Radar Xponencial

**Repo:** `quack2025/field-genius-backoffice` (historic name)
**Path:** `C:\Users\jorge\field-genius-backoffice`
**URL:** `https://app.xponencial.net` (primary) / `https://field-genius-backoffice.vercel.app` (fallback)
**Branch:** `master` (not main)
**Deploy:** Vercel auto-deploy on push to `master`

## Stack

- React 19 + TypeScript 5.9
- Vite 8 (build tool)
- Tailwind CSS 3.4
- Supabase Auth (Google SSO + email/password fallback)
- No component library (raw HTML + Tailwind)
- Icons: lucide-react

## Pages

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | Dashboard | Stats cards, time filter, breakdowns por proyecto |
| `/implementations` | Implementations | Proyectos with folder organization + create form |
| `/implementations/:id` | ImplementationDetail | 4 tabs: Config (5 sections), Visit Types, Prompts, Users |
| `/sessions` | Sessions | Filterable table + pagination (25/page) + search + skeleton loading |
| `/sessions/:id` | SessionDetail | Timeline + persistent reports + Gamma/Sheets export |
| `/reports` | Reports | Multi-level: Individual / Grupo / Proyecto tabs |
| `/user-groups` | UserGroups | CRUD for groups + member management |
| `/compliance` | Compliance | User activity tracking + Sheets export |

UI labels use "Proyectos" (not "Implementaciones") but routes stay as `/implementations` for API backward compatibility.

## ImplementationDetail — Config tab sections

Five editable sections on each project:

1. **General** — name, industry, country, language, color, Google Spreadsheet ID, trigger words
2. **WhatsApp y Control de Acceso** — `whatsapp_number`, `access_mode` (open | whitelist)
3. **Configuración AI** — `vision_strategy` (tiered | sonnet_only) with cost hints
4. **Mensajes de Onboarding** — welcome message, terms accepted, rejection, first photo hint, require_terms toggle
5. **Resumen por Email (Digest)** — enabled toggle, emails, frequency (daily/weekly)

## Projects page — Folders

- "Nueva carpeta" button creates folder (stored in state + persisted when a project is moved in)
- "Nuevo proyecto" button creates new implementation
- Each project card has folder icon → dropdown with all folders + inline "new folder" input + "remove from folder" option
- Empty folders shown with "Carpeta vacia" message
- Collapsible folder groups with project count

## API Client (`src/lib/api.ts`)

All calls go to `VITE_API_URL` (Railway backend). Auth headers from Supabase session.

```typescript
interface ApiResponse<T> {
  success: boolean;
  data: T;
  error: string | null;
  pagination?: { total, limit, offset, has_more };
}
```

### Key interfaces
- `Implementation` — includes `whatsapp_number`, `access_mode`, `vision_strategy`, `onboarding_config`, `folder`
- `VisitType`, `User`, `Session`, `RawFile`, `VisitReport`, `UserGroup`
- `SavedReport` — from `consolidated_reports` table
- `GammaExportResponse`, `SheetsExportResponse`
- `ComplianceUser`, `ComplianceResponse`
- `MultiLevelReportResponse` — group/project reports

### Key export functions
- `listReports({session_id})` — loads saved reports on SessionDetail mount
- `exportGamma({markdown, title})` — Gamma presentation export
- `exportSheets({implementation_id})` — structured facts + compliance to Sheets
- `getCompliance(implId, dateFrom, dateTo)` — compliance dashboard data

## Auth (Google SSO)

- Provider: Supabase Auth with Google OAuth
- Site URL: `https://app.xponencial.net`
- Google Cloud Console redirect URI: `https://sglvhzmwfzetyrhwouiw.supabase.co/auth/v1/callback`
- Owner accounts: `jorge.rosales@xponencial.net`, `jorge.quintero@xponencial.net` (superadmin)
- Permission model: `superadmin` | `admin` | `analyst` | `viewer`

## Env Variables

```
VITE_SUPABASE_URL=https://sglvhzmwfzetyrhwouiw.supabase.co
VITE_SUPABASE_ANON_KEY=<anon key>
VITE_API_URL=https://zealous-endurance-production-f9b2.up.railway.app
```

## Branding

- **Product name:** Radar Xponencial (NOT "Field Genius")
- **Section label:** "Panel de control"
- **Navigation:** "Proyectos" (NOT "Implementaciones")
- **Brand color:** `#003366` (brand-500)
