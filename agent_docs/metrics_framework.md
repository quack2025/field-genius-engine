# Field Genius Engine — Metrics Framework

**Fase 4 del UX/AI Quality Plan**
**Creado:** 2026-03-15
**Objetivo:** Definir qué medir en 4 niveles: operacional, calidad de datos, impacto de negocio, per-implementación

---

## Nivel 1: Pipeline Health (Operacional)

Métricas para detectar fallas técnicas antes de que el cliente las note.

### 1.1 Sesiones procesadas por día

```sql
SELECT
    date,
    implementation,
    COUNT(*) FILTER (WHERE status = 'completed') AS completed,
    COUNT(*) FILTER (WHERE status = 'failed') AS failed,
    COUNT(*) FILTER (WHERE status = 'accumulating') AS pending,
    COUNT(*) AS total
FROM sessions
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY date, implementation
ORDER BY date DESC, implementation;
```

**Alerta:** `completed < COUNT(DISTINCT user_phone WHERE role='executive')` — no todos los ejecutivos reportaron.

### 1.2 Tasa de éxito del pipeline

```sql
SELECT
    implementation,
    COUNT(*) FILTER (WHERE status = 'completed') AS ok,
    COUNT(*) FILTER (WHERE status = 'failed') AS failed,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'completed')::numeric /
        NULLIF(COUNT(*) FILTER (WHERE status IN ('completed', 'failed')), 0) * 100,
        1
    ) AS success_rate_pct
FROM sessions
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
  AND status IN ('completed', 'failed')
GROUP BY implementation;
```

**Target:** ≥90%. **Alerta:** <90%.

### 1.3 Tiempo promedio de procesamiento

```sql
SELECT
    vr.implementation,
    vr.visit_type,
    COUNT(*) AS visits,
    ROUND(AVG(vr.processing_time_ms)) AS avg_ms,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY vr.processing_time_ms)) AS p95_ms,
    MAX(vr.processing_time_ms) AS max_ms
FROM visit_reports vr
WHERE vr.created_at >= NOW() - INTERVAL '7 days'
  AND vr.processing_time_ms IS NOT NULL
GROUP BY vr.implementation, vr.visit_type
ORDER BY avg_ms DESC;
```

**Target:** avg <60s por visita. **Alerta:** p95 >120s.

### 1.4 Archivos acumulados por sesión

```sql
SELECT
    s.implementation,
    s.date,
    s.user_phone,
    jsonb_array_length(s.raw_files) AS file_count,
    CASE
        WHEN jsonb_array_length(s.raw_files) < 3 THEN 'low'
        WHEN jsonb_array_length(s.raw_files) BETWEEN 3 AND 10 THEN 'normal'
        ELSE 'high'
    END AS volume_tier
FROM sessions s
WHERE s.date >= CURRENT_DATE - INTERVAL '7 days'
  AND s.status = 'completed'
ORDER BY file_count ASC;
```

**Alerta:** `file_count < 3` — ejecutivo no está capturando suficiente.

### 1.5 Distribución de tipos de archivo

```sql
SELECT
    s.implementation,
    f->>'type' AS file_type,
    COUNT(*) AS count
FROM sessions s,
     jsonb_array_elements(s.raw_files) AS f
WHERE s.date >= CURRENT_DATE - INTERVAL '7 days'
  AND s.status = 'completed'
GROUP BY s.implementation, f->>'type'
ORDER BY count DESC;
```

**Uso:** Verificar que los ejecutivos usen audio además de fotos. Audio-only = baja extracción visual.

### 1.6 Sesiones con clarificación

```sql
SELECT
    implementation,
    COUNT(*) FILTER (WHERE status = 'needs_clarification') AS needs_clar,
    COUNT(*) FILTER (WHERE status = 'completed') AS completed,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'needs_clarification')::numeric /
        NULLIF(COUNT(*), 0) * 100, 1
    ) AS clar_rate_pct
FROM sessions
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY implementation;
```

**Target:** <20%. Si sube, revisar si el segmentation prompt está pidiendo clarificación excesiva.

---

## Nivel 2: Data Quality (Analítico)

Métricas para medir qué tan buenos son los datos extraídos.

### 2.1 Completitud de extracción por categoría

```sql
SELECT
    vr.visit_type,
    key AS category,
    COUNT(*) AS total_visits,
    COUNT(*) FILTER (WHERE value::text != '{}' AND value::text != '[]' AND value::text != 'null') AS populated,
    ROUND(
        COUNT(*) FILTER (WHERE value::text != '{}' AND value::text != '[]' AND value::text != 'null')::numeric /
        NULLIF(COUNT(*), 0) * 100, 1
    ) AS fill_rate_pct
FROM visit_reports vr,
     jsonb_each(vr.extracted_data) AS kv(key, value)
WHERE vr.created_at >= NOW() - INTERVAL '30 days'
  AND vr.status = 'completed'
  AND key NOT IN ('confidence_score', 'needs_clarification', 'clarification_questions')
GROUP BY vr.visit_type, key
ORDER BY fill_rate_pct ASC;
```

**Interpretación:**
- fill_rate <30% → la categoría probablemente no aplica al tipo de visita real, o el schema no es adecuado
- fill_rate 30-70% → hay oportunidad de mejorar la extracción o guiar mejor al ejecutivo
- fill_rate >70% → la categoría está funcionando bien

### 2.2 Distribución de confidence_score

```sql
SELECT
    vr.implementation,
    vr.visit_type,
    WIDTH_BUCKET(vr.confidence_score, 0, 1, 10) AS bucket,
    COUNT(*) AS count,
    ROUND(AVG(vr.confidence_score), 2) AS avg_conf
FROM visit_reports vr
WHERE vr.created_at >= NOW() - INTERVAL '30 days'
  AND vr.confidence_score IS NOT NULL
GROUP BY vr.implementation, vr.visit_type, bucket
ORDER BY vr.visit_type, bucket;
```

**Target:** Distribución concentrada en buckets 7-9 (0.7-0.9). Si hay pico en buckets 1-4, revisar calidad de input.

### 2.3 Visits marcadas como needs_review

```sql
SELECT
    vr.implementation,
    vr.visit_type,
    vr.inferred_location,
    vr.confidence_score,
    vr.created_at,
    s.user_phone,
    s.user_name
FROM visit_reports vr
JOIN sessions s ON s.id = vr.session_id
WHERE vr.status = 'needs_review'
  AND vr.created_at >= NOW() - INTERVAL '7 days'
ORDER BY vr.confidence_score ASC;
```

**Acción:** Revisar manualmente las visitas con confidence <0.5 para verificar si la extracción fue correcta.

### 2.4 Consistencia de precios (ferretería)

```sql
WITH prices AS (
    SELECT
        vr.inferred_location,
        p->>'producto' AS producto,
        p->>'marca' AS marca,
        (p->>'precio')::numeric AS precio,
        vr.created_at::date AS fecha
    FROM visit_reports vr,
         jsonb_array_elements(vr.extracted_data->'precios') AS p
    WHERE vr.visit_type = 'ferreteria'
      AND vr.status = 'completed'
      AND p->>'precio' IS NOT NULL
      AND (p->>'precio')::numeric > 0
)
SELECT
    producto,
    marca,
    COUNT(*) AS obs,
    ROUND(AVG(precio)) AS avg_precio,
    ROUND(STDDEV(precio)) AS stddev_precio,
    MIN(precio) AS min_precio,
    MAX(precio) AS max_precio,
    ROUND(STDDEV(precio) / NULLIF(AVG(precio), 0) * 100, 1) AS cv_pct
FROM prices
GROUP BY producto, marca
HAVING COUNT(*) >= 3
ORDER BY cv_pct DESC NULLS LAST;
```

**Alerta:** CV (coeficiente de variación) >15% — precios inconsistentes, posible error de transcripción/extracción.

### 2.5 Share of shelf — distribución

```sql
SELECT
    vr.implementation,
    vr.extracted_data->'share_of_shelf'->>'argos_facing' AS argos_facing,
    COUNT(*) AS count,
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 1) AS pct
FROM visit_reports vr
WHERE vr.visit_type = 'ferreteria'
  AND vr.status = 'completed'
  AND vr.extracted_data->'share_of_shelf'->>'argos_facing' IS NOT NULL
GROUP BY vr.implementation, vr.extracted_data->'share_of_shelf'->>'argos_facing'
ORDER BY count DESC;
```

**Alerta:** Si >60% reportan "medio", la extracción probablemente defaultea a "medio" cuando no puede determinar.

### 2.6 Alertas de competencia activadas

```sql
SELECT
    vr.implementation,
    vr.visit_type,
    a->>'marca' AS marca_competencia,
    a->>'actividad' AS actividad,
    COUNT(*) AS frequency
FROM visit_reports vr,
     jsonb_array_elements(vr.extracted_data->'actividad_competencia') AS a
WHERE vr.status = 'completed'
  AND (a->>'alerta')::boolean = true
  AND vr.created_at >= NOW() - INTERVAL '30 days'
GROUP BY vr.implementation, vr.visit_type, a->>'marca', a->>'actividad'
ORDER BY frequency DESC;
```

**Uso:** Intelligence competitiva — qué marcas están más activas y con qué tipo de actividad.

### 2.7 Campos vacíos por tipo de visita (detección de schema mismatch)

```sql
WITH field_checks AS (
    SELECT
        vr.visit_type,
        cat_key,
        field_key,
        CASE
            WHEN field_val::text IN ('null', '""', '[]', '{}') THEN 0
            ELSE 1
        END AS is_populated
    FROM visit_reports vr,
         jsonb_each(vr.extracted_data) AS cat(cat_key, cat_val),
         LATERAL (
             SELECT key AS field_key, value AS field_val
             FROM jsonb_each(cat_val)
             WHERE jsonb_typeof(cat_val) = 'object'
             UNION ALL
             SELECT NULL, NULL WHERE jsonb_typeof(cat_val) != 'object'
         ) AS fields
    WHERE vr.status = 'completed'
      AND cat_key NOT IN ('confidence_score', 'needs_clarification', 'clarification_questions')
      AND field_key IS NOT NULL
)
SELECT
    visit_type,
    cat_key AS category,
    field_key AS field,
    COUNT(*) AS total,
    SUM(is_populated) AS populated,
    ROUND(SUM(is_populated)::numeric / NULLIF(COUNT(*), 0) * 100, 1) AS fill_pct
FROM field_checks
GROUP BY visit_type, cat_key, field_key
HAVING ROUND(SUM(is_populated)::numeric / NULLIF(COUNT(*), 0) * 100, 1) < 30
ORDER BY fill_pct ASC;
```

**Acción:** Campos con fill_pct <30% probablemente no aplican o el ejecutivo no captura esa información. Considerar eliminar del schema o agregar guidance al ejecutivo.

---

## Nivel 3: Business Impact (Estratégico)

Métricas para medir el valor que el sistema genera para el cliente.

### 3.1 Adopción de ejecutivos

```sql
SELECT
    u.implementation,
    COUNT(DISTINCT u.phone) AS registered,
    COUNT(DISTINCT s.user_phone) FILTER (WHERE s.date >= CURRENT_DATE - INTERVAL '7 days') AS active_7d,
    COUNT(DISTINCT s.user_phone) FILTER (WHERE s.date >= CURRENT_DATE - INTERVAL '1 day') AS active_today,
    ROUND(
        COUNT(DISTINCT s.user_phone) FILTER (WHERE s.date >= CURRENT_DATE - INTERVAL '7 days')::numeric /
        NULLIF(COUNT(DISTINCT u.phone), 0) * 100, 1
    ) AS adoption_7d_pct
FROM users u
LEFT JOIN sessions s ON s.user_phone = u.phone AND s.status = 'completed'
WHERE u.role = 'executive'
GROUP BY u.implementation;
```

**Target:** ≥80% adoption_7d. **Alerta:** <50%.

### 3.2 Cobertura de visitas

```sql
SELECT
    s.implementation,
    s.user_phone,
    u.name,
    s.date,
    (SELECT COUNT(*)
     FROM visit_reports vr
     WHERE vr.session_id = s.id AND vr.status = 'completed') AS visits_reported
FROM sessions s
JOIN users u ON u.phone = s.user_phone
WHERE s.date >= CURRENT_DATE - INTERVAL '7 days'
  AND s.status = 'completed'
ORDER BY s.implementation, s.date DESC, visits_reported ASC;
```

**Uso:** Cruzar con ruta planificada (dato externo) para calcular cobertura real.

### 3.3 Yield de inteligencia competitiva

```sql
SELECT
    vr.implementation,
    COUNT(DISTINCT vr.session_id) AS total_sessions,
    COUNT(DISTINCT vr.id) AS total_visits,
    COUNT(DISTINCT vr.id) FILTER (
        WHERE EXISTS (
            SELECT 1 FROM jsonb_array_elements(vr.extracted_data->'actividad_competencia') a
            WHERE (a->>'alerta')::boolean = true
        )
    ) AS visits_with_alerts,
    ROUND(
        COUNT(DISTINCT vr.id) FILTER (
            WHERE EXISTS (
                SELECT 1 FROM jsonb_array_elements(vr.extracted_data->'actividad_competencia') a
                WHERE (a->>'alerta')::boolean = true
            )
        )::numeric / NULLIF(COUNT(DISTINCT vr.id), 0) * 100, 1
    ) AS alert_yield_pct
FROM visit_reports vr
WHERE vr.status = 'completed'
  AND vr.created_at >= NOW() - INTERVAL '30 days'
GROUP BY vr.implementation;
```

**Target:** ≥30% de visitas con al menos 1 alerta.

### 3.4 Ejecutivos inactivos

```sql
SELECT
    u.implementation,
    u.phone,
    u.name,
    MAX(s.date) AS last_session_date,
    CURRENT_DATE - MAX(s.date) AS days_inactive
FROM users u
LEFT JOIN sessions s ON s.user_phone = u.phone AND s.status = 'completed'
WHERE u.role = 'executive'
GROUP BY u.implementation, u.phone, u.name
HAVING MAX(s.date) IS NULL OR MAX(s.date) < CURRENT_DATE - INTERVAL '2 days'
ORDER BY days_inactive DESC NULLS FIRST;
```

**Alerta:** >2 días sin sesión → notificar al gerente.

### 3.5 Tiempo de onboarding por implementación

```sql
SELECT
    u.implementation,
    u.phone,
    u.name,
    u.created_at::date AS registered,
    MIN(s.date) AS first_session,
    MIN(s.date) - u.created_at::date AS days_to_first_session
FROM users u
LEFT JOIN sessions s ON s.user_phone = u.phone AND s.status = 'completed'
WHERE u.role = 'executive'
GROUP BY u.implementation, u.phone, u.name, u.created_at
ORDER BY days_to_first_session DESC NULLS FIRST;
```

**Target:** <5 días entre registro y primera sesión completada.

### 3.6 Patrones temporales (detección de gaming)

```sql
SELECT
    s.implementation,
    s.user_phone,
    u.name,
    EXTRACT(HOUR FROM MIN(
        (f->>'timestamp')::timestamptz
    )) AS first_file_hour,
    EXTRACT(HOUR FROM MAX(
        (f->>'timestamp')::timestamptz
    )) AS last_file_hour,
    COUNT(DISTINCT s.id) AS sessions_count
FROM sessions s
JOIN users u ON u.phone = s.user_phone
CROSS JOIN jsonb_array_elements(s.raw_files) AS f
WHERE s.date >= CURRENT_DATE - INTERVAL '7 days'
  AND s.status = 'completed'
  AND f->>'timestamp' IS NOT NULL
GROUP BY s.implementation, s.user_phone, u.name;
```

**Alerta:** Si first_file_hour = last_file_hour Y hour > 16 — ejecutivo probablemente envía todo al final del día en vez de capturar en campo.

---

## Nivel 4: Per-Implementation Dashboards

### 4.1 Argos — Precios por producto por región

```sql
SELECT
    vr.inferred_location,
    p->>'marca' AS marca,
    p->>'producto' AS producto,
    (p->>'precio')::numeric AS precio,
    p->>'presentacion' AS presentacion,
    vr.created_at::date AS fecha
FROM visit_reports vr,
     jsonb_array_elements(vr.extracted_data->'precios') AS p
WHERE vr.implementation = 'argos'
  AND vr.visit_type = 'ferreteria'
  AND vr.status = 'completed'
  AND p->>'precio' IS NOT NULL
ORDER BY p->>'marca', p->>'producto', vr.created_at DESC;
```

### 4.2 Argos — Share of shelf trend (semanal)

```sql
SELECT
    DATE_TRUNC('week', vr.created_at) AS week,
    vr.extracted_data->'share_of_shelf'->>'argos_facing' AS facing,
    COUNT(*) AS visits
FROM visit_reports vr
WHERE vr.implementation = 'argos'
  AND vr.visit_type = 'ferreteria'
  AND vr.status = 'completed'
  AND vr.extracted_data->'share_of_shelf'->>'argos_facing' IS NOT NULL
GROUP BY week, facing
ORDER BY week, facing;
```

### 4.3 Argos — Heatmap de actividad competitiva

```sql
SELECT
    a->>'marca' AS marca_competencia,
    vr.inferred_location,
    a->>'actividad' AS tipo_actividad,
    COUNT(*) AS ocurrencias,
    (a->>'alerta')::boolean AS es_alerta
FROM visit_reports vr,
     jsonb_array_elements(vr.extracted_data->'actividad_competencia') AS a
WHERE vr.implementation = 'argos'
  AND vr.status = 'completed'
GROUP BY a->>'marca', vr.inferred_location, a->>'actividad', (a->>'alerta')::boolean
ORDER BY ocurrencias DESC;
```

### 4.4 Argos — Frecuencia de visitas por ejecutivo

```sql
SELECT
    u.name AS ejecutivo,
    DATE_TRUNC('week', s.date) AS week,
    COUNT(DISTINCT s.id) AS sessions,
    SUM(
        (SELECT COUNT(*) FROM visit_reports vr WHERE vr.session_id = s.id AND vr.status = 'completed')
    ) AS total_visits
FROM sessions s
JOIN users u ON u.phone = s.user_phone
WHERE s.implementation = 'argos'
  AND s.status = 'completed'
GROUP BY u.name, week
ORDER BY week DESC, total_visits DESC;
```

### 4.5 Argos — Oportunidades en obra civil

```sql
SELECT
    vr.inferred_location AS proyecto,
    vr.extracted_data->'datos_proyecto'->>'etapa' AS etapa,
    vr.extracted_data->'datos_proyecto'->>'tamano_estimado' AS tamano,
    o->>'tipo' AS tipo_oportunidad,
    o->>'descripcion' AS descripcion,
    o->>'urgencia' AS urgencia,
    vr.created_at::date AS fecha
FROM visit_reports vr,
     jsonb_array_elements(vr.extracted_data->'oportunidad') AS o
WHERE vr.implementation = 'argos'
  AND vr.visit_type = 'obra_civil'
  AND vr.status = 'completed'
ORDER BY
    CASE o->>'urgencia' WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END,
    vr.created_at DESC;
```

### 4.6 Eficacia — SKU por tipo de tienda

```sql
SELECT
    vr.visit_type,
    i->>'nombre_producto' AS producto,
    i->>'marca' AS marca,
    COUNT(*) AS presencia_en_visitas
FROM visit_reports vr,
     jsonb_array_elements(vr.extracted_data->'inventario') AS i
WHERE vr.implementation = 'eficacia'
  AND vr.status = 'completed'
GROUP BY vr.visit_type, i->>'nombre_producto', i->>'marca'
ORDER BY presencia_en_visitas DESC;
```

### 4.7 Eficacia — Cumplimiento de exhibiciones

```sql
SELECT
    vr.visit_type,
    COUNT(*) AS total_visits,
    COUNT(*) FILTER (
        WHERE vr.extracted_data->'exhibiciones_especiales' IS NOT NULL
          AND vr.extracted_data->>'exhibiciones_especiales' != '[]'
          AND vr.extracted_data->>'exhibiciones_especiales' != 'null'
    ) AS con_exhibicion,
    ROUND(
        COUNT(*) FILTER (
            WHERE vr.extracted_data->'exhibiciones_especiales' IS NOT NULL
              AND vr.extracted_data->>'exhibiciones_especiales' != '[]'
        )::numeric / NULLIF(COUNT(*), 0) * 100, 1
    ) AS cumplimiento_pct
FROM visit_reports vr
WHERE vr.implementation = 'eficacia'
  AND vr.status = 'completed'
GROUP BY vr.visit_type;
```

---

## Umbrales de alerta (resumen)

| Métrica | Target | Alerta | Crítico |
|---------|--------|--------|---------|
| Pipeline success rate | ≥95% | <90% | <80% |
| Avg processing time (por visita) | <60s | >90s | >120s |
| Archivos por sesión | ≥3 | <3 | 0 (trigger sin archivos) |
| Confidence score promedio | ≥0.75 | <0.65 | <0.50 |
| Categoría fill rate | ≥50% | <30% | <10% (schema mismatch) |
| Adopción ejecutivos (7d) | ≥80% | <50% | <30% |
| Días sin sesión (ejecutivo) | 0-1 | 2-3 | >3 |
| Tasa de clarificación | <20% | >30% | >50% (prompt issue) |
| Yield alertas competencia | ≥30% | <15% | <5% |
| Coeficiente variación precios | <10% | >15% | >25% |

---

## Implementación en backoffice

### Dashboard Tab 1: Pipeline Health
- **Gauge:** Sesiones completadas hoy vs ejecutivos registrados
- **Line chart (7d):** Success rate trend (query 1.2)
- **Bar chart:** Processing time por visit_type (query 1.3)
- **Table:** Sesiones fallidas del día con error detail

### Dashboard Tab 2: Data Quality
- **Heatmap:** visit_type x category → fill_rate_pct (query 2.1)
- **Histogram:** Confidence score distribution (query 2.2)
- **Table:** needs_review visits con link a detalle (query 2.3)
- **Alert banner:** Categorías con fill_rate <30%

### Dashboard Tab 3: Executive Activity
- **Heatmap:** ejecutivo x día → visit_count (query 3.2)
- **Bar chart:** Archivos por ejecutivo (query 1.4)
- **Table:** Ejecutivos inactivos con días_inactive (query 3.4)
- **Scatter:** first_file_hour vs last_file_hour por ejecutivo (gaming detection, query 3.6)

### Dashboard Tab 4: Competitive Intelligence (Argos-specific)
- **Bar chart:** Marcas competidoras más frecuentes (query 2.6)
- **Map view:** Alertas por ubicación (query 4.3, futuro)
- **Table:** Oportunidades en obras ordenadas por urgencia (query 4.5)
- **Trend:** Share of shelf semanal (query 4.2)

---

## Queries Supabase RPC (para backoffice)

Para el backoffice, estas queries deberían exponerse como RPCs de Supabase o endpoints del engine API. Recomendación:

```sql
-- Ejemplo: RPC para pipeline health summary
CREATE OR REPLACE FUNCTION get_pipeline_health(
    p_implementation text DEFAULT NULL,
    p_days int DEFAULT 7
)
RETURNS TABLE (
    metric text,
    value numeric,
    target numeric,
    status text
) AS $$
BEGIN
    -- Success rate
    RETURN QUERY
    SELECT
        'success_rate'::text,
        ROUND(
            COUNT(*) FILTER (WHERE s.status = 'completed')::numeric /
            NULLIF(COUNT(*) FILTER (WHERE s.status IN ('completed', 'failed')), 0) * 100, 1
        ),
        90.0::numeric,
        CASE
            WHEN ROUND(COUNT(*) FILTER (WHERE s.status = 'completed')::numeric / NULLIF(COUNT(*) FILTER (WHERE s.status IN ('completed', 'failed')), 0) * 100, 1) >= 90 THEN 'ok'
            WHEN ROUND(COUNT(*) FILTER (WHERE s.status = 'completed')::numeric / NULLIF(COUNT(*) FILTER (WHERE s.status IN ('completed', 'failed')), 0) * 100, 1) >= 80 THEN 'warning'
            ELSE 'critical'
        END::text
    FROM sessions s
    WHERE s.date >= CURRENT_DATE - (p_days || ' days')::interval
      AND (p_implementation IS NULL OR s.implementation = p_implementation);

    -- Avg processing time
    RETURN QUERY
    SELECT
        'avg_processing_ms'::text,
        ROUND(AVG(vr.processing_time_ms)::numeric),
        60000.0::numeric,
        CASE
            WHEN AVG(vr.processing_time_ms) <= 60000 THEN 'ok'
            WHEN AVG(vr.processing_time_ms) <= 90000 THEN 'warning'
            ELSE 'critical'
        END::text
    FROM visit_reports vr
    WHERE vr.created_at >= NOW() - (p_days || ' days')::interval
      AND (p_implementation IS NULL OR vr.implementation = p_implementation)
      AND vr.processing_time_ms IS NOT NULL;

    -- Avg confidence
    RETURN QUERY
    SELECT
        'avg_confidence'::text,
        ROUND(AVG(vr.confidence_score)::numeric, 2),
        0.75::numeric,
        CASE
            WHEN AVG(vr.confidence_score) >= 0.75 THEN 'ok'
            WHEN AVG(vr.confidence_score) >= 0.65 THEN 'warning'
            ELSE 'critical'
        END::text
    FROM visit_reports vr
    WHERE vr.created_at >= NOW() - (p_days || ' days')::interval
      AND (p_implementation IS NULL OR vr.implementation = p_implementation)
      AND vr.confidence_score IS NOT NULL;
END;
$$ LANGUAGE plpgsql;
```

---

## Notas de implementación

1. **No bloquear el pipeline** — todas las métricas se calculan sobre datos históricos, nunca en real-time durante procesamiento.
2. **Índices ya creados** — Sprint N creó 65 índices en columnas hot-path. Las queries de este doc deberían ser eficientes.
3. **Refresh interval** — Dashboard debe refrescar cada 5 min, no en real-time. Evitar carga en Supabase.
4. **Privacy** — Los queries muestran `user_phone` y `name`. En producción multi-cliente, filtrar por `implementation` y aplicar RLS.
5. **Eficacia queries (4.6, 4.7)** — Usan keys de extracted_data que dependen del schema de Eficacia. Verificar que los keys coincidan cuando el schema esté finalizado.
