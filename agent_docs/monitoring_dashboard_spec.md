# Field Genius Engine — Monitoring & Alerting Spec

**Fase 5 del UX/AI Quality Plan**
**Creado:** 2026-03-15
**Objetivo:** Dashboard de monitoreo en backoffice + sistema de alertas automáticas

---

## Estado actual del backoffice

- **Stack:** React 19 + Tailwind 3.4 + Supabase Auth + lucide-react
- **Sin librería de charts** — todo es texto/badges plano
- **Stats endpoint** (`GET /api/admin/stats`) retorna solo agregados (no series de tiempo)
- **4 páginas:** Dashboard, Implementations, Sessions, SessionDetail
- **Deploy:** Vercel (auto-deploy on push)
- **Repo:** `C:\Users\jorge\field-genius-backoffice`

---

## Part A: Backend — Nuevos endpoints y migración

### A.1 Tabla `alerts` (nueva)

```sql
-- Archivo: sql/003_alerts.sql
CREATE TABLE IF NOT EXISTS alerts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    implementation text NOT NULL,
    alert_type text NOT NULL,
    severity text NOT NULL DEFAULT 'warning',
    title text NOT NULL,
    detail text,
    context jsonb DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'open',
    resolved_at timestamptz,
    resolved_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT alerts_type_check CHECK (
        alert_type IN (
            'pipeline_failure',
            'executive_inactive',
            'low_confidence',
            'schema_mismatch',
            'price_anomaly',
            'high_unassigned'
        )
    ),
    CONSTRAINT alerts_severity_check CHECK (severity IN ('info', 'warning', 'critical')),
    CONSTRAINT alerts_status_check CHECK (status IN ('open', 'acknowledged', 'resolved'))
);

CREATE INDEX IF NOT EXISTS idx_alerts_impl_status ON alerts(implementation, status);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC);
```

### A.2 Endpoint: `GET /api/admin/stats/timeseries`

Nuevo endpoint que retorna datos por día para charts.

**Request:**
```
GET /api/admin/stats/timeseries?implementation=argos&days=14
```

**Response:**
```json
{
  "success": true,
  "data": {
    "daily": [
      {
        "date": "2026-03-14",
        "sessions_completed": 5,
        "sessions_failed": 0,
        "sessions_total": 6,
        "visits_total": 12,
        "avg_confidence": 0.84,
        "avg_processing_ms": 45000,
        "files_total": 38,
        "clarification_count": 1,
        "needs_review_count": 0
      }
    ],
    "executive_activity": [
      {
        "phone": "+573001234567",
        "name": "Carlos Lopez",
        "dates": {
          "2026-03-14": { "sessions": 1, "visits": 3, "files": 8 },
          "2026-03-13": { "sessions": 1, "visits": 2, "files": 5 }
        },
        "last_session": "2026-03-14",
        "days_inactive": 0
      }
    ],
    "confidence_histogram": [
      { "bucket": "0.0-0.1", "count": 0 },
      { "bucket": "0.1-0.2", "count": 0 },
      { "bucket": "0.2-0.3", "count": 1 },
      { "bucket": "0.3-0.4", "count": 0 },
      { "bucket": "0.4-0.5", "count": 2 },
      { "bucket": "0.5-0.6", "count": 1 },
      { "bucket": "0.6-0.7", "count": 3 },
      { "bucket": "0.7-0.8", "count": 8 },
      { "bucket": "0.8-0.9", "count": 12 },
      { "bucket": "0.9-1.0", "count": 5 }
    ],
    "category_fill_rates": [
      {
        "visit_type": "ferreteria",
        "category": "precios",
        "fill_rate_pct": 92.0
      },
      {
        "visit_type": "ferreteria",
        "category": "relacion_comercial",
        "fill_rate_pct": 45.0
      }
    ]
  }
}
```

**SQL backend (en `routes/admin.py`):**

```python
@router.get("/api/admin/stats/timeseries")
async def get_timeseries_stats(
    implementation: str | None = None,
    days: int = 14,
):
    # daily: aggregate sessions + visits per day
    # executive_activity: pivot users x dates
    # confidence_histogram: WIDTH_BUCKET on visit_reports
    # category_fill_rates: jsonb_each on extracted_data
    ...
```

### A.3 Endpoint: `GET /api/admin/alerts`

```
GET /api/admin/alerts?implementation=argos&status=open&limit=50
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "implementation": "argos",
      "alert_type": "pipeline_failure",
      "severity": "critical",
      "title": "Pipeline falló para +573001234567",
      "detail": "Error en Phase 2 extraction: timeout after 90s",
      "context": { "session_id": "uuid", "user_phone": "+573001234567" },
      "status": "open",
      "created_at": "2026-03-14T16:30:00Z"
    }
  ]
}
```

### A.4 Endpoint: `PATCH /api/admin/alerts/{alert_id}`

Permite acknowledged/resolve alertas desde el dashboard.

```json
{ "status": "resolved", "resolved_by": "admin@geniuslabs.ai" }
```

### A.5 Alert generation (en pipeline.py y cron)

Alertas se generan en dos puntos:

**Inline (durante pipeline):**

```python
# pipeline.py — en el except block (ya notifica al usuario con QW1)
# Ahora también crea alerta en DB:
async def _create_alert(impl: str, alert_type: str, severity: str, title: str, detail: str, context: dict):
    from src.engine.supabase_client import supabase
    supabase.table("alerts").insert({
        "implementation": impl,
        "alert_type": alert_type,
        "severity": severity,
        "title": title,
        "detail": detail,
        "context": context,
    }).execute()
```

Puntos de inserción:
- `pipeline.py` except block → `pipeline_failure` (critical)
- `extractor.py` confidence < threshold → `low_confidence` (warning)
- `segmenter.py` unassigned_files > 3 → `high_unassigned` (warning)

**Batch (cron job diario o endpoint manual):**

```python
# routes/admin.py — POST /api/admin/alerts/check
# Ejecuta las verificaciones batch:

async def check_alerts(implementation: str | None = None):
    """Run batch alert checks."""
    alerts = []

    # 1. Executive inactive >2 days
    inactive = await _query_inactive_executives(implementation, days=2)
    for exec in inactive:
        alerts.append({
            "alert_type": "executive_inactive",
            "severity": "warning",
            "title": f"{exec['name']} sin sesión hace {exec['days']} días",
            "context": {"phone": exec["phone"], "days_inactive": exec["days"]},
        })

    # 2. Schema mismatch — category fill_rate <10%
    mismatches = await _query_schema_mismatches(implementation, threshold=10)
    for m in mismatches:
        alerts.append({
            "alert_type": "schema_mismatch",
            "severity": "warning",
            "title": f"Categoría '{m['category']}' vacía en {m['visit_type']}",
            "context": {"visit_type": m["visit_type"], "fill_rate": m["fill_rate"]},
        })

    # 3. Price anomaly — CV >25%
    anomalies = await _query_price_anomalies(implementation, cv_threshold=25)
    for a in anomalies:
        alerts.append({
            "alert_type": "price_anomaly",
            "severity": "info",
            "title": f"Precio inconsistente: {a['marca']} {a['producto']} (CV={a['cv']}%)",
            "context": a,
        })

    # Deduplicate — don't create if same type+context exists open in last 24h
    ...
    return alerts
```

---

## Part B: Frontend — Dashboard Monitoring Tabs

### B.1 Dependencias a agregar

```bash
npm install recharts
```

Recharts es lightweight (~45KB gzipped), compatible con Tailwind, y soporta AreaChart, BarChart, PieChart, Tooltip, ResponsiveContainer.

### B.2 Navegación

Agregar tabs al Dashboard existente:

```
[Overview] [Pipeline Health] [Data Quality] [Executives] [Alerts]
```

El tab "Overview" es el dashboard actual (3 stat cards + breakdowns).

### B.3 Tab: Pipeline Health

**Layout:**

```
┌─────────────────────────────────────────────────────┐
│ [Gauge] Success Rate: 94%    [Gauge] Avg Time: 42s  │
│ [Gauge] Sessions Today: 5/8  [Gauge] Clar Rate: 12% │
├─────────────────────────────────────────────────────┤
│ [AreaChart — 14 días]                               │
│  - Línea verde: completed                           │
│  - Línea roja: failed                               │
│  - Área gris: total                                 │
│  - Tooltip: fecha, completed, failed, total         │
├─────────────────────────────────────────────────────┤
│ [BarChart — Processing Time por visit_type]         │
│  - Barra: avg_ms                                    │
│  - Línea: p95_ms                                    │
│  - Color: verde <60s, amarillo 60-90s, rojo >90s    │
├─────────────────────────────────────────────────────┤
│ [Table — Failed Sessions (last 7 days)]             │
│  Fecha | Ejecutivo | Archivos | Error | [Ver]       │
└─────────────────────────────────────────────────────┘
```

**Fuente de datos:** `GET /api/admin/stats/timeseries?days=14`

**Componentes React:**

```
PipelineHealthTab.tsx
├── GaugeCard.tsx (reutilizable — valor, target, label, color by threshold)
├── SessionsTrendChart.tsx (Recharts AreaChart)
├── ProcessingTimeChart.tsx (Recharts BarChart)
└── FailedSessionsTable.tsx (tabla plain con link a /sessions/:id)
```

### B.4 Tab: Data Quality

**Layout:**

```
┌─────────────────────────────────────────────────────┐
│ [Heatmap — visit_type x category → fill_rate]       │
│                                                     │
│              precios  share  compet  relacion        │
│  ferreteria    92%     78%    65%      45%           │
│  obra_civil    88%     --     --       70%           │
│  obra_peq      75%     --     --       60%           │
│                                                     │
│  Color: verde >70%, amarillo 30-70%, rojo <30%      │
├─────────────────────────────────────────────────────┤
│ [Histogram — Confidence Score Distribution]         │
│  [Recharts BarChart con 10 buckets 0.0-1.0]         │
│  Color: rojo <0.5, amarillo 0.5-0.7, verde >0.7    │
├─────────────────────────────────────────────────────┤
│ [Table — Visits needs_review]                       │
│  Fecha | Ejecutivo | Tipo | Ubicación | Conf | [Ver]│
└─────────────────────────────────────────────────────┘
```

**Fuente de datos:** `GET /api/admin/stats/timeseries` (category_fill_rates, confidence_histogram)

**Componentes React:**

```
DataQualityTab.tsx
├── FillRateHeatmap.tsx (grid con celdas coloreadas por threshold)
├── ConfidenceHistogram.tsx (Recharts BarChart vertical)
└── NeedsReviewTable.tsx (filtro: status=needs_review)
```

### B.5 Tab: Executives

**Layout:**

```
┌─────────────────────────────────────────────────────┐
│ [Heatmap — ejecutivo x día → visits count]          │
│                                                     │
│                  Lun  Mar  Mie  Jue  Vie  Sab       │
│  Carlos Lopez     3    2    4    3    2    -         │
│  Maria Garcia     2    -    3    2    1    -         │
│  Pedro Ruiz       -    -    1    -    -    -  ⚠️     │
│                                                     │
│  Color: blanco=0, azul claro=1-2, azul=3+, rojo=⚠️  │
├─────────────────────────────────────────────────────┤
│ [BarChart — Archivos por ejecutivo]                  │
│  - Stacked: image, audio, video, location           │
│  - Sorted by total DESC                             │
├─────────────────────────────────────────────────────┤
│ [Alert banner — Ejecutivos inactivos]               │
│  ⚠️ Pedro Ruiz sin sesión hace 3 días               │
│  ⚠️ Ana Perez sin sesión hace 5 días                │
├─────────────────────────────────────────────────────┤
│ [Scatter — Gaming detection]                        │
│  X: hora primer archivo, Y: hora último archivo     │
│  Ejecutivos en esquina (17,17) = posible gaming     │
└─────────────────────────────────────────────────────┘
```

**Fuente de datos:** `GET /api/admin/stats/timeseries` (executive_activity)

**Componentes React:**

```
ExecutivesTab.tsx
├── ActivityHeatmap.tsx (grid coloreado ejecutivo x día)
├── FileVolumeChart.tsx (Recharts StackedBarChart)
├── InactiveAlert.tsx (banner amarillo con lista)
└── GamingScatter.tsx (Recharts ScatterChart, opcional Phase 7)
```

### B.6 Tab: Alerts

**Layout:**

```
┌─────────────────────────────────────────────────────┐
│ [Filter bar]                                        │
│  Status: [Open ▼]  Severity: [All ▼]  Type: [All ▼]│
├─────────────────────────────────────────────────────┤
│ [Alert cards — stack vertical]                      │
│                                                     │
│  🔴 CRITICAL — Pipeline falló para +573001234567    │
│  Hace 2 horas | pipeline_failure                    │
│  Error en Phase 2: timeout after 90s                │
│  [Acknowledge] [Ver sesión]                         │
│                                                     │
│  🟡 WARNING — Pedro Ruiz sin sesión hace 3 días    │
│  Hace 1 día | executive_inactive                    │
│  [Acknowledge] [Resolve]                            │
│                                                     │
│  🟡 WARNING — Categoría 'relacion' vacía en ferret │
│  Hace 3 días | schema_mismatch                      │
│  fill_rate: 8%                                      │
│  [Acknowledge] [Resolve]                            │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Fuente de datos:** `GET /api/admin/alerts?status=open`

**Componentes React:**

```
AlertsTab.tsx
├── AlertFilters.tsx (dropdowns: status, severity, type)
├── AlertCard.tsx (card con ícono severity, título, detail, acciones)
└── (PATCH /api/admin/alerts/:id on action click)
```

---

## Part C: Alert System — Reglas y canales

### C.1 Reglas de alerta

| # | Tipo | Trigger | Severity | Canal | Deduplication |
|---|------|---------|----------|-------|---------------|
| A1 | `pipeline_failure` | Session status → failed | critical | Backoffice + WhatsApp admin | 1 por sesión |
| A2 | `executive_inactive` | No session >2 days | warning | Backoffice | 1 por ejecutivo por día |
| A3 | `low_confidence` | confidence_score < threshold | warning | Backoffice | 1 por visit_report |
| A4 | `schema_mismatch` | Category fill_rate <10% | warning | Backoffice | 1 por (visit_type, category) por semana |
| A5 | `price_anomaly` | Price CV >25% | info | Backoffice | 1 por (producto, marca) por semana |
| A6 | `high_unassigned` | >3 unassigned files | warning | Backoffice | 1 por sesión |

### C.2 Canal WhatsApp (solo critical)

Solo `pipeline_failure` notifica por WhatsApp al admin. Usa el mismo `sender.py`:

```python
async def notify_admin_alert(alert: dict):
    """Send critical alert to admin via WhatsApp."""
    if alert["severity"] != "critical":
        return
    admin_phone = settings.admin_phone  # nuevo setting
    if not admin_phone:
        return
    msg = f"⚠️ ALERTA: {alert['title']}\n{alert.get('detail', '')}"
    await send_message(admin_phone, msg)
```

### C.3 Deduplicación

Antes de insertar alerta, verificar si ya existe una abierta del mismo tipo+contexto:

```sql
SELECT id FROM alerts
WHERE alert_type = $1
  AND implementation = $2
  AND context @> $3::jsonb
  AND status = 'open'
  AND created_at > NOW() - INTERVAL '24 hours'
LIMIT 1;
```

Si existe, no crear otra. Esto evita spam cuando el mismo error se repite.

### C.4 Auto-resolve

Algunas alertas se resuelven automáticamente:

| Tipo | Auto-resolve cuando |
|------|---------------------|
| `executive_inactive` | Ejecutivo crea nueva sesión |
| `low_confidence` | Visit report se marca como `completed` (verificado manualmente) |

```python
# En session_manager.py, al crear sesión:
async def _auto_resolve_inactive_alerts(phone: str, implementation: str):
    supabase.table("alerts").update({
        "status": "resolved",
        "resolved_at": datetime.now(UTC).isoformat(),
        "resolved_by": "auto",
    }).eq("alert_type", "executive_inactive").eq("status", "open").eq(
        "context->>phone", phone
    ).execute()
```

---

## Part D: Signal Detection — Distinguir cambio real de ruido

### D.1 Confidence scores cayendo

```
¿Confidence promedio bajó >10% vs semana anterior?
├── SÍ → ¿Cambió el modelo de Anthropic?
│   ├── SÍ → Benchmark con golden set, ajustar prompts si necesario
│   └── NO → ¿Cambió el schema recientemente?
│       ├── SÍ → Nuevo schema puede ser más difícil de extraer
│       └── NO → Calidad real de input empeoró (menos fotos, audio malo)
│           → Verificar file_count y types por ejecutivo
└── NO → Normal, no action needed
```

**Query para detectar:**
```sql
WITH weekly AS (
    SELECT
        DATE_TRUNC('week', created_at) AS week,
        AVG(confidence_score) AS avg_conf
    FROM visit_reports
    WHERE confidence_score IS NOT NULL
    GROUP BY week
    ORDER BY week DESC
    LIMIT 4
)
SELECT
    w1.week AS this_week,
    w1.avg_conf AS current,
    w2.avg_conf AS previous,
    ROUND((w1.avg_conf - w2.avg_conf) / NULLIF(w2.avg_conf, 0) * 100, 1) AS change_pct
FROM weekly w1
JOIN weekly w2 ON w2.week = w1.week - INTERVAL '1 week';
```

### D.2 Menos visitas por sesión

```
¿Promedio de visitas/sesión bajó >20%?
├── SÍ → ¿Promedio de archivos/sesión también bajó?
│   ├── SÍ → Ejecutivos capturan menos (problema de adopción)
│   └── NO → Segmentación más agresiva (splitting)
│       → Correr golden test set y comparar con baseline
└── NO → Normal
```

### D.3 Más requests de clarificación

```
¿Tasa de clarificación subió >10pp?
├── SÍ → ¿Es un ejecutivo nuevo?
│   ├── SÍ → Normal para onboarding, monitorear 2 semanas
│   └── NO → ¿Cambió el segmentation prompt?
│       ├── SÍ → Prompt más cauteloso, considerar relajar threshold
│       └── NO → Input ambiguo (menos fotos de fachada, mismos ángulos)
│           → Agregar guidance al ejecutivo
└── NO → Normal
```

### D.4 Categoría vacía en todos los reportes

```
¿Categoría X tiene fill_rate <10% por >7 días?
├── SÍ → ¿Es categoría nueva (agregada recientemente)?
│   ├── SÍ → Schema no está alineado con realidad de campo
│   │   → Entrevistar ejecutivo: ¿esta info existe en campo?
│   └── NO → ¿Antes tenía fill_rate >30%?
│       ├── SÍ → Algo cambió (modelo, prompt, tipo de punto)
│       └── NO → Siempre ha estado vacía → eliminar del schema
└── NO → Normal
```

---

## Part E: Prioridad de implementación

| # | Item | Esfuerzo | Impacto | Dependencias |
|---|------|----------|---------|-------------|
| 1 | Migración SQL `alerts` table | 5 min | Prerequisito | Ninguna |
| 2 | Alert creation inline (pipeline.py) | 30 min | Captura fallas en tiempo real | #1 |
| 3 | `GET /api/admin/alerts` + `PATCH` | 1h | Backoffice puede ver/resolver alertas | #1 |
| 4 | `GET /api/admin/stats/timeseries` | 2h | Base de datos para todos los charts | Ninguna |
| 5 | `npm install recharts` + PipelineHealthTab | 3h | Visualización principal | #4 |
| 6 | DataQualityTab (heatmap + histogram) | 2h | Detectar schema issues | #4 |
| 7 | ExecutivesTab (activity heatmap) | 2h | Adopción tracking | #4 |
| 8 | AlertsTab (card list + actions) | 2h | Manage alertas | #3 |
| 9 | Batch alert checks (inactive, mismatch) | 1h | Alertas proactivas | #1 |
| 10 | WhatsApp admin notification (critical only) | 30 min | Critical alerts a tiempo | #2 |

**Total estimado:** ~14h de desarrollo (backend 5h, frontend 9h)

**Sprint recomendado:**
- Sprint P-1 (backend): items 1-4 (4h)
- Sprint P-2 (frontend): items 5-8 (9h)
- Sprint P-3 (batch): items 9-10 (1.5h)

---

## Wireframe reference (ASCII)

### Dashboard con tabs

```
┌──────────────────────────────────────────────────┐
│  Field Genius Backoffice          [Implementation ▼] │
├──────────────────────────────────────────────────┤
│  [Overview] [Health] [Quality] [Executives] [Alerts(3)]│
├──────────────────────────────────────────────────┤
│                                                  │
│  (contenido del tab seleccionado)                │
│                                                  │
└──────────────────────────────────────────────────┘
```

El badge `(3)` en Alerts muestra el count de alertas open. Se obtiene con:
```
GET /api/admin/alerts?status=open&limit=0
→ response header X-Total-Count o campo count en response
```
