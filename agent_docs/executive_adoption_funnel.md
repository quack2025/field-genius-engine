# Field Genius Engine — Executive Adoption Funnel & Cohort Analysis

**Fase 7 del UX/AI Quality Plan**
**Creado:** 2026-03-15
**Objetivo:** Entender dónde los ejecutivos abandonan el flujo y diseñar intervenciones para cada punto de caída

---

## Funnel de adopción

```
[1. Registrado]              ← Admin crea usuario en tabla users
       ↓  ────────── Drop: "No sabe que existe" ──────────
[2. Primer contacto]         ← Envía cualquier mensaje al WhatsApp del engine
       ↓  ────────── Drop: "No sabe qué capturar" ────────
[3. Primer archivo]          ← Envía al menos 1 foto/audio/video
       ↓  ────────── Drop: "No sabe la palabra mágica" ───
[4. Primer trigger]          ← Escribe "reporte" o similar
       ↓  ────────── Drop: "Pipeline falló o tardó mucho" ─
[5. Primer reporte]          ← Pipeline completa exitosamente
       ↓  ────────── Drop: "Resultado no fue útil" ────────
[6. Segundo día]             ← Envía archivos al día siguiente
       ↓  ────────── Drop: "No formó hábito" ──────────────
[7. Reportero semanal]       ← Reporta ≥3 días en una semana
       ↓  ────────── Drop: "Fatiga / cambio de prioridades"
[8. Reportero habitual]      ← Reporta ≥3 días/semana por ≥3 semanas consecutivas
```

---

## SQL Queries para cada etapa

### Query F1: Funnel completo por implementación

```sql
WITH funnel AS (
    SELECT
        u.implementation,
        u.phone,
        u.name,
        u.created_at AS registered_at,

        -- Stage 2: Primer contacto (cualquier raw_file o text en sessions)
        (SELECT MIN(s.created_at)
         FROM sessions s WHERE s.user_phone = u.phone
        ) AS first_contact_at,

        -- Stage 3: Primer archivo (sesión con al menos 1 raw_file no-text)
        (SELECT MIN(s.created_at)
         FROM sessions s WHERE s.user_phone = u.phone
           AND jsonb_array_length(s.raw_files) > 0
           AND EXISTS (
               SELECT 1 FROM jsonb_array_elements(s.raw_files) f
               WHERE f->>'type' IN ('image', 'audio', 'video')
           )
        ) AS first_file_at,

        -- Stage 4: Primer trigger (sesión que salió de accumulating)
        (SELECT MIN(s.created_at)
         FROM sessions s WHERE s.user_phone = u.phone
           AND s.status IN ('segmenting', 'processing', 'completed', 'failed', 'needs_clarification', 'awaiting_confirmation')
        ) AS first_trigger_at,

        -- Stage 5: Primer reporte exitoso
        (SELECT MIN(s.date)
         FROM sessions s WHERE s.user_phone = u.phone
           AND s.status = 'completed'
        ) AS first_completed_date,

        -- Stage 6: Segundo día con reporte
        (SELECT MIN(s2.date)
         FROM sessions s2
         WHERE s2.user_phone = u.phone
           AND s2.status = 'completed'
           AND s2.date > (
               SELECT MIN(s3.date) FROM sessions s3
               WHERE s3.user_phone = u.phone AND s3.status = 'completed'
           )
        ) AS second_day_date,

        -- Stage 7: Primera semana con ≥3 días activos
        (SELECT MIN(week_start)
         FROM (
             SELECT DATE_TRUNC('week', s.date) AS week_start,
                    COUNT(DISTINCT s.date) AS active_days
             FROM sessions s
             WHERE s.user_phone = u.phone AND s.status = 'completed'
             GROUP BY DATE_TRUNC('week', s.date)
             HAVING COUNT(DISTINCT s.date) >= 3
         ) sub
        ) AS first_active_week

    FROM users u
    WHERE u.role = 'executive'
)
SELECT
    implementation,
    COUNT(*) AS registered,
    COUNT(first_contact_at) AS contacted,
    COUNT(first_file_at) AS sent_file,
    COUNT(first_trigger_at) AS triggered,
    COUNT(first_completed_date) AS completed,
    COUNT(second_day_date) AS returned,
    COUNT(first_active_week) AS weekly_active,

    -- Conversion rates
    ROUND(COUNT(first_contact_at)::numeric / NULLIF(COUNT(*), 0) * 100, 1) AS "reg→contact_%",
    ROUND(COUNT(first_file_at)::numeric / NULLIF(COUNT(first_contact_at), 0) * 100, 1) AS "contact→file_%",
    ROUND(COUNT(first_trigger_at)::numeric / NULLIF(COUNT(first_file_at), 0) * 100, 1) AS "file→trigger_%",
    ROUND(COUNT(first_completed_date)::numeric / NULLIF(COUNT(first_trigger_at), 0) * 100, 1) AS "trigger→complete_%",
    ROUND(COUNT(second_day_date)::numeric / NULLIF(COUNT(first_completed_date), 0) * 100, 1) AS "complete→return_%",
    ROUND(COUNT(first_active_week)::numeric / NULLIF(COUNT(second_day_date), 0) * 100, 1) AS "return→weekly_%"
FROM funnel
GROUP BY implementation;
```

### Query F2: Detalle por ejecutivo (diagnóstico individual)

```sql
WITH exec_funnel AS (
    SELECT
        u.implementation,
        u.phone,
        u.name,
        u.created_at::date AS registered,
        (SELECT MIN(s.date) FROM sessions s WHERE s.user_phone = u.phone AND s.status = 'completed') AS first_report,
        (SELECT MAX(s.date) FROM sessions s WHERE s.user_phone = u.phone AND s.status = 'completed') AS last_report,
        (SELECT COUNT(DISTINCT s.date) FROM sessions s WHERE s.user_phone = u.phone AND s.status = 'completed') AS total_days_active,
        (SELECT COUNT(*) FROM sessions s WHERE s.user_phone = u.phone AND s.status = 'failed') AS failed_sessions,
        (SELECT COALESCE(SUM(jsonb_array_length(s.raw_files)), 0) FROM sessions s WHERE s.user_phone = u.phone) AS total_files,
        CURRENT_DATE - (SELECT MAX(s.date) FROM sessions s WHERE s.user_phone = u.phone AND s.status = 'completed') AS days_since_last
    FROM users u
    WHERE u.role = 'executive'
)
SELECT
    implementation,
    phone,
    name,
    registered,
    first_report,
    last_report,
    total_days_active,
    failed_sessions,
    total_files,
    days_since_last,
    CASE
        WHEN first_report IS NULL AND total_files = 0 THEN 'never_contacted'
        WHEN first_report IS NULL AND total_files > 0 THEN 'stuck_before_trigger'
        WHEN first_report IS NOT NULL AND total_days_active = 1 THEN 'one_and_done'
        WHEN days_since_last > 7 THEN 'churned'
        WHEN days_since_last > 2 THEN 'at_risk'
        ELSE 'active'
    END AS lifecycle_stage
FROM exec_funnel
ORDER BY
    CASE
        WHEN first_report IS NULL THEN 1
        WHEN days_since_last > 7 THEN 2
        WHEN days_since_last > 2 THEN 3
        ELSE 4
    END,
    days_since_last DESC NULLS FIRST;
```

### Query F3: Retention cohort (semana de registro × semana de actividad)

```sql
WITH cohorts AS (
    SELECT
        u.phone,
        u.implementation,
        DATE_TRUNC('week', u.created_at) AS cohort_week,
        s.date
    FROM users u
    LEFT JOIN sessions s ON s.user_phone = u.phone AND s.status = 'completed'
    WHERE u.role = 'executive'
)
SELECT
    cohort_week,
    implementation,
    COUNT(DISTINCT phone) AS cohort_size,
    COUNT(DISTINCT phone) FILTER (
        WHERE date BETWEEN cohort_week AND cohort_week + INTERVAL '6 days'
    ) AS week_0,
    COUNT(DISTINCT phone) FILTER (
        WHERE date BETWEEN cohort_week + INTERVAL '7 days' AND cohort_week + INTERVAL '13 days'
    ) AS week_1,
    COUNT(DISTINCT phone) FILTER (
        WHERE date BETWEEN cohort_week + INTERVAL '14 days' AND cohort_week + INTERVAL '20 days'
    ) AS week_2,
    COUNT(DISTINCT phone) FILTER (
        WHERE date BETWEEN cohort_week + INTERVAL '21 days' AND cohort_week + INTERVAL '27 days'
    ) AS week_3,

    -- Retention rates
    ROUND(COUNT(DISTINCT phone) FILTER (
        WHERE date BETWEEN cohort_week AND cohort_week + INTERVAL '6 days'
    )::numeric / NULLIF(COUNT(DISTINCT phone), 0) * 100, 0) AS "W0_%",
    ROUND(COUNT(DISTINCT phone) FILTER (
        WHERE date BETWEEN cohort_week + INTERVAL '7 days' AND cohort_week + INTERVAL '13 days'
    )::numeric / NULLIF(COUNT(DISTINCT phone), 0) * 100, 0) AS "W1_%",
    ROUND(COUNT(DISTINCT phone) FILTER (
        WHERE date BETWEEN cohort_week + INTERVAL '14 days' AND cohort_week + INTERVAL '20 days'
    )::numeric / NULLIF(COUNT(DISTINCT phone), 0) * 100, 0) AS "W2_%",
    ROUND(COUNT(DISTINCT phone) FILTER (
        WHERE date BETWEEN cohort_week + INTERVAL '21 days' AND cohort_week + INTERVAL '27 days'
    )::numeric / NULLIF(COUNT(DISTINCT phone), 0) * 100, 0) AS "W3_%"

FROM cohorts
GROUP BY cohort_week, implementation
ORDER BY cohort_week DESC;
```

### Query F4: Time-to-first-report por ejecutivo

```sql
SELECT
    u.implementation,
    u.phone,
    u.name,
    u.created_at::date AS registered,
    MIN(s.date) AS first_report,
    MIN(s.date) - u.created_at::date AS days_to_first_report
FROM users u
LEFT JOIN sessions s ON s.user_phone = u.phone AND s.status = 'completed'
WHERE u.role = 'executive'
GROUP BY u.implementation, u.phone, u.name, u.created_at
ORDER BY days_to_first_report DESC NULLS FIRST;
```

### Query F5: Sesiones stuck en accumulating (nunca triggeraron)

```sql
SELECT
    s.implementation,
    s.user_phone,
    s.user_name,
    s.date,
    jsonb_array_length(s.raw_files) AS file_count,
    s.created_at,
    s.updated_at,
    AGE(NOW(), s.updated_at) AS time_since_update
FROM sessions s
WHERE s.status = 'accumulating'
  AND jsonb_array_length(s.raw_files) > 0
  AND s.updated_at < NOW() - INTERVAL '4 hours'
ORDER BY s.updated_at ASC;
```

**Uso:** Ejecutivos que mandaron archivos pero nunca escribieron "reporte". Candidatos para auto-prompt.

### Query F6: Frecuencia de uso semanal (para definir "habitual")

```sql
SELECT
    u.implementation,
    u.phone,
    u.name,
    DATE_TRUNC('week', s.date) AS week,
    COUNT(DISTINCT s.date) AS days_active,
    SUM(jsonb_array_length(s.raw_files)) AS total_files,
    COUNT(DISTINCT vr.id) AS total_visits,
    ROUND(AVG(vr.confidence_score), 2) AS avg_confidence
FROM users u
JOIN sessions s ON s.user_phone = u.phone AND s.status = 'completed'
LEFT JOIN visit_reports vr ON vr.session_id = s.id AND vr.status = 'completed'
WHERE u.role = 'executive'
GROUP BY u.implementation, u.phone, u.name, DATE_TRUNC('week', s.date)
ORDER BY week DESC, days_active DESC;
```

---

## Hipótesis de drop-off e intervenciones

### Drop 1→2: Registrado pero nunca contactó

**Hipótesis:** No sabe que el sistema existe, o no tiene el número.

**Cómo detectar:** `lifecycle_stage = 'never_contacted'` en query F2.

**Intervención: Mensaje de bienvenida automático**

Al registrar un usuario via admin API, enviar WhatsApp de onboarding:

```python
# admin.py — después de crear usuario:
async def _send_onboarding_message(phone: str, name: str, implementation: str):
    from src.channels.whatsapp.sender import send_message

    msg = (
        f"Hola {name} 👋\n\n"
        f"Soy el asistente de reportes de campo. "
        f"Para usarme, simplemente envíame fotos, audios o videos "
        f"de tus visitas durante el día.\n\n"
        f"Cuando termines, escribe *reporte* y yo proceso todo.\n\n"
        f"¡Pruébalo ahora! Envíame una foto de lo que tengas cerca."
    )
    await send_message(phone, msg)
```

**Métrica:** % de ejecutivos que envían primer archivo dentro de 48h del onboarding.
**Target:** ≥70%.

### Drop 2→3: Contactó pero no envió archivo

**Hipótesis:** Escribió "hola" o preguntó algo, pero no entendió que debe enviar media.

**Cómo detectar:** Sessions con solo text notes, sin media files.

**Intervención: Respuesta inteligente al primer texto**

```python
# webhook.py — cuando el usuario envía texto y no tiene archivos:
if session_file_count == 0 and not is_trigger:
    await send_message(phone,
        "Para generar un reporte, primero envíame fotos o audios de tu visita. "
        "Puedes enviar tantos como quieras. Cuando termines, escribe *reporte*."
    )
```

**Métrica:** % de ejecutivos que envían primer archivo después del hint.
**Target:** ≥80%.

### Drop 3→4: Envió archivos pero nunca triggeró

**Hipótesis:** No sabe la palabra clave, o asume que el sistema procesa automáticamente.

**Cómo detectar:** Query F5 (sessions stuck in accumulating con archivos).

**Intervención: Auto-prompt a las 5pm**

```python
# Cron job diario a las 17:00 local:
async def auto_prompt_pending_sessions():
    """Send reminder to executives with files but no trigger today."""
    stuck = await _get_stuck_sessions()  # Query F5

    for session in stuck:
        phone = session["user_phone"]
        file_count = session["file_count"]
        await send_message(phone,
            f"Tienes {file_count} archivo(s) de hoy sin procesar. "
            f"Escribe *reporte* para generar tu informe."
        )
        logger.info("auto_prompt_sent", phone=phone, files=file_count)
```

**Métrica:** % de sesiones auto-prompteadas que completan pipeline.
**Target:** ≥50%.

**Implementación:** Cron job via Railway cron, Celery beat, o endpoint `POST /api/admin/auto-prompt` llamado externamente.

### Drop 4→5: Triggeó pero pipeline falló

**Hipótesis:** Error técnico, timeout, o archivos corruptos.

**Cómo detectar:** `sessions.status = 'failed'` + `lifecycle_stage = 'stuck_before_trigger'`.

**Intervención:** Ya implementada:
- QW1: Notificación de error al usuario
- Phase 5: Alert `pipeline_failure` al admin
- Retry: usuario puede volver a escribir "reporte"

**Métrica adicional:** % de retries exitosos después de falla.

### Drop 5→6: Completó pero no volvió al día siguiente

**Hipótesis:** El resultado no fue útil, o el proceso fue doloroso.

**Cómo detectar:** `lifecycle_stage = 'one_and_done'` en query F2.

**Intervención: Feedback post-reporte**

24 horas después del primer reporte exitoso:

```python
async def send_feedback_request(phone: str):
    await send_message(phone,
        "¿Cómo te fue con el reporte de ayer? "
        "Responde del 1 al 5 (1=malo, 5=excelente).\n\n"
        "Tu respuesta nos ayuda a mejorar el servicio."
    )
```

Guardar respuesta como metric en tabla (o simplemente como text note en una sesión especial).

**Métrica:** NPS simplificado — % de 4-5 vs 1-3.
**Target:** ≥60% responden 4 o 5.

### Drop 6→7: Volvió pero no formó hábito

**Hipótesis:** No hay incentivo para reportar diariamente. El manager no revisa los reportes.

**Cómo detectar:** `total_days_active > 1 AND total_days_active < 10 AND days_since_last > 3`.

**Intervención: Daily reminder configurable**

```python
# Cron diario a hora configurable por implementación:
async def send_daily_reminder():
    """Remind executives who usually report but haven't today."""
    # Solo ejecutivos que han reportado ≥3 días total Y no han reportado hoy
    candidates = await _get_reminder_candidates()

    for exec in candidates:
        await send_message(exec["phone"],
            f"Buenos días {exec['name']}. ¿Tienes visitas hoy? "
            f"Recuerda enviarme fotos y audios durante tus visitas."
        )
```

**Guardrails:**
- Solo enviar si el ejecutivo ha reportado ≥3 días (no spamear a nuevos)
- No enviar en fines de semana (configurable por implementación)
- Max 1 reminder por día
- Desactivable por ejecutivo (responde "NO MAS" → flag en users)

**Métrica:** % de días con reporte entre ejecutivos que reciben reminder vs no.

### Drop 7→8: Semanal activo pero no sostiene

**Hipótesis:** Fatiga, cambio de ruta, rotación de personal.

**Cómo detectar:** Cohort analysis (query F3) — W2 y W3 retention.

**Intervención:** Más allá del scope técnico — requiere:
- Manager engagement (que revise y dé feedback a los ejecutivos)
- Gamification (ranking de ejecutivos, reconocimiento)
- Valor tangible (que el ejecutivo VEA que su reporte generó una acción)

---

## Dashboard de Funnel (para backoffice)

### Tab: Adoption Funnel

```
┌─────────────────────────────────────────────────────┐
│ [Funnel chart — horizontal bars, narrowing]         │
│                                                     │
│  Registrados      ████████████████████████  20      │
│  Contactaron      ██████████████████       16 (80%) │
│  Enviaron archivo ████████████████         14 (88%) │
│  Triggeraron      ██████████████           12 (86%) │
│  Reporte exitoso  ████████████             11 (92%) │
│  Volvieron        ████████                  8 (73%) │
│  Semanales        ██████                    5 (63%) │
│  Habituales       ████                      3 (60%) │
│                                                     │
│  Biggest drop: Reporte → Volvieron (27% drop)       │
├─────────────────────────────────────────────────────┤
│ [Table — Executives by lifecycle stage]              │
│                                                     │
│  🔴 never_contacted (2): Pedro Ruiz, Ana Perez      │
│  🟡 stuck_before_trigger (1): Luis Garcia           │
│  🟡 one_and_done (3): Maria..., Carlos..., Juan...  │
│  🟡 at_risk (2): Sandra..., Diego...                │
│  🟢 active (5): ...                                 │
└─────────────────────────────────────────────────────┘
```

**Fuente:** Query F1 (aggregate) + Query F2 (per-executive).

### Tab: Retention Cohorts

```
┌─────────────────────────────────────────────────────┐
│ [Cohort heatmap — registration week × activity week]│
│                                                     │
│  Cohort    Size  W0    W1    W2    W3                │
│  Mar 3      5   100%   80%   60%   40%              │
│  Mar 10     3   100%   67%    —     —               │
│  Mar 17     8   100%    —     —     —               │
│                                                     │
│  Color: verde >70%, amarillo 40-70%, rojo <40%      │
├─────────────────────────────────────────────────────┤
│ [Line chart — Retention curve overlay per cohort]   │
│                                                     │
│  100% ─●────●                                       │
│   80% ─     │──●                                    │
│   60% ─          ──●                                │
│   40% ─               ──●                           │
│        W0   W1   W2   W3   W4                       │
└─────────────────────────────────────────────────────┘
```

**Fuente:** Query F3.

### Tab: Time-to-Value

```
┌─────────────────────────────────────────────────────┐
│ [Histogram — Days from registration to first report]│
│                                                     │
│  Day 0: ████████  6                                 │
│  Day 1: ████      3                                 │
│  Day 2: ██        2                                 │
│  Day 3: █         1                                 │
│  Day 4:                                             │
│  Day 5+: ██       2 (still waiting)                 │
│                                                     │
│  Median: 0 days | Mean: 1.2 days | Target: <5 days  │
├─────────────────────────────────────────────────────┤
│ [Table — Stuck sessions (files but no trigger)]     │
│  Ejecutivo | Archivos | Última actividad | [Prompt] │
│  Luis G.   |    5     | Hace 6 horas     | [Enviar] │
└─────────────────────────────────────────────────────┘
```

**Fuente:** Query F4 (time-to-first) + Query F5 (stuck sessions).

---

## Endpoints nuevos para funnel

### `GET /api/admin/stats/funnel`

```json
{
  "success": true,
  "data": {
    "funnel": {
      "registered": 20,
      "contacted": 16,
      "sent_file": 14,
      "triggered": 12,
      "completed": 11,
      "returned": 8,
      "weekly_active": 5,
      "habitual": 3
    },
    "executives": [
      {
        "phone": "+573001234567",
        "name": "Carlos Lopez",
        "lifecycle_stage": "active",
        "registered": "2026-03-03",
        "first_report": "2026-03-03",
        "last_report": "2026-03-14",
        "total_days_active": 10,
        "days_since_last": 1
      }
    ],
    "stuck_sessions": [
      {
        "phone": "+573009876543",
        "name": "Luis Garcia",
        "file_count": 5,
        "hours_since_update": 6.2
      }
    ]
  }
}
```

### `GET /api/admin/stats/cohorts`

```json
{
  "success": true,
  "data": {
    "cohorts": [
      {
        "cohort_week": "2026-03-03",
        "size": 5,
        "retention": {
          "W0": 100,
          "W1": 80,
          "W2": 60,
          "W3": 40
        }
      }
    ]
  }
}
```

### `POST /api/admin/auto-prompt`

Trigger manual del auto-prompt para sesiones stuck.

```json
{
  "success": true,
  "data": {
    "prompted": 3,
    "phones": ["+573009876543", "+573007654321", "+573001112233"]
  }
}
```

---

## Automated interventions — Resumen

| Trigger | Acción | Canal | Timing |
|---------|--------|-------|--------|
| Usuario registrado | Mensaje de bienvenida | WhatsApp | Inmediato |
| Primer texto sin archivo | Hint "envía fotos primero" | WhatsApp | Inmediato |
| Archivos sin trigger >4h | Auto-prompt "escribe reporte" | WhatsApp | 17:00 local |
| Pipeline falla | Error msg + alert admin | WhatsApp + Backoffice | Inmediato |
| Primer reporte +24h | Feedback request (1-5) | WhatsApp | +24h |
| ≥3 reportes, no reportó hoy | Daily reminder | WhatsApp | 08:00 local |
| Ejecutivo inactivo >2 días | Alert a admin/manager | Backoffice | Batch diario |

### Opt-out

```python
# webhook.py — detectar opt-out
OPT_OUT_PHRASES = {"no mas", "no más", "parar", "stop", "cancelar"}

if body.strip().lower() in OPT_OUT_PHRASES:
    # Set flag en users table
    client.table("users").update({
        "reminders_enabled": False
    }).eq("phone", phone).execute()
    await send_message(phone, "Listo, no recibirás más recordatorios.")
```

```sql
-- DB change
ALTER TABLE users ADD COLUMN IF NOT EXISTS reminders_enabled boolean DEFAULT true;
```

---

## KPIs target por fase de madurez

### Fase 1: Piloto (1-2 semanas, 5-10 ejecutivos)

| KPI | Target | Mínimo viable |
|-----|--------|---------------|
| Funnel Registered → First report | ≥80% | ≥60% |
| Time to first report | <2 días | <5 días |
| Pipeline success rate | ≥90% | ≥80% |
| W1 retention | ≥60% | ≥40% |

### Fase 2: Adopción (3-6 semanas, 10-30 ejecutivos)

| KPI | Target | Mínimo viable |
|-----|--------|---------------|
| W2 retention | ≥50% | ≥30% |
| Daily active rate | ≥70% | ≥50% |
| Avg files per session | ≥5 | ≥3 |
| Avg confidence score | ≥0.75 | ≥0.65 |

### Fase 3: Escala (6+ semanas, 30+ ejecutivos)

| KPI | Target | Mínimo viable |
|-----|--------|---------------|
| W4 retention | ≥40% | ≥25% |
| Habitual rate (≥3d/wk × 3wk) | ≥30% | ≥15% |
| Auto-prompt conversion | ≥50% | ≥30% |
| NPS (feedback 4-5) | ≥60% | ≥40% |

---

## Prioridad de implementación

| # | Item | Esfuerzo | Impacto | Dependencias |
|---|------|----------|---------|-------------|
| 1 | Funnel queries (F1-F6) | 1h | Base de todo el análisis | Ninguna |
| 2 | `GET /api/admin/stats/funnel` | 2h | Dashboard data | #1 |
| 3 | Onboarding message | 30min | Mayor drop-off (reg→contact) | Ninguna |
| 4 | Auto-prompt at 5pm | 2h | Segundo mayor drop (file→trigger) | Cron setup |
| 5 | `GET /api/admin/stats/cohorts` | 1h | Retention tracking | #1 |
| 6 | Funnel dashboard tab | 3h | Visualización | #2 |
| 7 | Cohort dashboard tab | 2h | Retention charts | #5 |
| 8 | Daily reminder | 1h | Habit formation | Cron + opt-out |
| 9 | Feedback request (post-first-report) | 1h | Qualitative signal | Cron |
| 10 | `reminders_enabled` + opt-out | 30min | User control | DB migration |

**Sprint recomendado:**
- **Sprint F-1 (3.5h):** Items 1, 2, 3 — funnel queries + endpoint + onboarding
- **Sprint F-2 (5h):** Items 4, 5, 6 — auto-prompt + cohorts + dashboard
- **Sprint F-3 (4.5h):** Items 7, 8, 9, 10 — retention charts + reminders + feedback
