# Field Genius Engine — HITL Workflow Spec

**Fase 6 del UX/AI Quality Plan**
**Creado:** 2026-03-15
**Objetivo:** Agregar checkpoints humanos sin romper el flujo WhatsApp-only

---

## El reto fundamental

El ejecutivo de campo interactúa SOLO por WhatsApp. Cualquier checkpoint humano debe funcionar como un intercambio de mensajes de texto. No hay botones, no hay formularios, no hay pantalla web.

**Restricciones:**
- Mensajes de WhatsApp: max ~4096 chars (pero óptimo <500 para legibilidad)
- No hay botones interactivos (WhatsApp Business API los tiene, pero requieren templates aprobados por Meta)
- Respuesta del usuario: texto libre (no se puede forzar "SI/NO")
- Timeout: el usuario puede no responder por horas
- Idioma: español informal colombiano

---

## Estado actual del state machine

```
accumulating ──[trigger word]──> segmenting
      │                              │
      │                    ┌─────────┴──────────┐
      │                    │                    │
      │              needs_clarification    processing
      │                    │                    │
      │              [user responds]            │
      │                    │                    │
      │                    └──> processing ─────┤
      │                                         │
      │                                    completed
      │                                         │
      └──[more files after completed]──> accumulating (IGNORED today)

      Any state ──[error]──> failed ──[retry trigger]──> segmenting
```

**Estado propuesto con HITL:**

```
accumulating ──[trigger]──> segmenting
                                │
                     ┌──────────┴───────────┐
                     │                      │
              needs_clarification    awaiting_confirmation  ← NEW
                     │                      │
              [user responds]        [user confirms/corrects]
                     │                      │
                     └──> processing ────────┤
                              │              │
                              │         [timeout 30min]
                              │              │
                              │         processing (auto-proceed with flag)
                              │
                         completed
                              │
                     ┌────────┴────────┐
                     │                 │
              [summary sent]    [low confidence]
                     │                 │
                     │           needs_review (in visit_reports)
                     │                 │
                     │           [admin reviews in backoffice]
                     │
              [session done]
```

---

## Intervención 1: Segmentation Confirmation (ALTA prioridad, MEDIO esfuerzo)

### Por qué

La segmentación incorrecta cascadea a todo lo demás. Si el sistema piensa que 2 ferreterías son 1 sola, la extracción mezcla datos de ambas. Esto es invisible para el ejecutivo en el resumen final.

Confirmación después de Phase 1 permite al ejecutivo corregir ANTES de la extracción.

### Flujo WhatsApp

```
Engine → Ejecutivo:
────────────────────
Identifiqué 3 visitas en tu reporte de hoy:

1. *Ferreteria El Constructor* (ferretería)
   📁 5 archivos | 10:15 - 10:52

2. *Obra Centro Comercial Santafé* (obra civil)
   📁 3 archivos + 1 video | 14:30 - 15:20

3. *Ferreteria La Esquina* (ferretería)
   📁 2 archivos | 16:00 - 16:15

¿Es correcto? Responde *SI* para continuar o escribe tu corrección.
────────────────────

Ejecutivo → Engine (caso OK):
"si"
→ Procede a Phase 2

Ejecutivo → Engine (caso corrección):
"la 3 no es ferreteria, es una obra pequeña"
→ Corrige visit_type de visita 3 y procede

Ejecutivo → Engine (caso merge):
"la 1 y la 3 son la misma ferreteria"
→ Merge visitas 1+3, re-segmenta con hint

Ejecutivo → Engine (timeout 30 min):
(no responde)
→ Auto-proceed con flag confirmation_status='auto'
```

### Nuevo estado: `awaiting_confirmation`

```python
# session_manager.py — nuevo handler
async def handle_confirmation_response(phone: str, body: str) -> dict:
    """Handle user response to segmentation confirmation."""
    session = await get_or_create_session(phone, datetime.date.today())

    normalized = body.strip().lower()

    if normalized in ("si", "sí", "yes", "ok", "correcto", "dale"):
        # User confirms — proceed to extraction
        return {
            "action": "confirmation_accepted",
            "session": session,
            "message": "Perfecto, extrayendo datos de tus visitas...",
        }
    else:
        # User sent a correction — save and re-segment with hint
        correction_meta = {
            "filename": None,
            "storage_path": None,
            "type": "confirmation_correction",
            "content_type": "text/plain",
            "body": body,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        }
        await add_file_to_session(session["id"], correction_meta)
        return {
            "action": "confirmation_correction",
            "session": session,
            "message": "Entendido, ajustando tu reporte...",
            "correction_text": body,
        }
```

### Cambios en pipeline.py

```python
# Después de Phase 1 segmentation (línea ~168):

# Si no needs_clarification Y tiene >1 visita → pedir confirmación
if not segmentation.needs_clarification and len(segmentation.visits) > 1:
    await update_session_status(session_id, "awaiting_confirmation")
    result.status = "awaiting_confirmation"

    # Build confirmation message
    confirmation_msg = _build_confirmation_message(segmentation.visits)
    await send_message(phone, confirmation_msg)

    # Start timeout timer (30 min)
    # Implementar como cron job o asyncio.sleep con check
    asyncio.create_task(_confirmation_timeout(session_id, delay_seconds=1800))

    return result

# Si solo 1 visita → proceder directo (no necesita confirmación)
```

### Builder del mensaje de confirmación

```python
def _build_confirmation_message(visits: list[VisitSegment]) -> str:
    """Build WhatsApp confirmation message for segmentation result."""
    lines = [f"Identifiqué {len(visits)} visita(s) en tu reporte de hoy:\n"]

    for i, v in enumerate(visits, 1):
        visit_label = {
            "ferreteria": "ferretería",
            "obra_civil": "obra civil",
            "obra_pequeña": "obra pequeña",
        }.get(v.visit_type, v.visit_type)

        lines.append(f"{i}. *{v.inferred_location}* ({visit_label})")
        lines.append(f"   📁 {len(v.files)} archivo(s) | {v.time_range}")
        lines.append("")

    lines.append("¿Es correcto? Responde *SI* para continuar o escribe tu corrección.")
    return "\n".join(lines)
```

### Timeout handler

```python
async def _confirmation_timeout(session_id: str, delay_seconds: int = 1800):
    """Auto-proceed after timeout if user didn't confirm."""
    await asyncio.sleep(delay_seconds)

    session = await get_session(session_id)
    if session and session.get("status") == "awaiting_confirmation":
        logger.warning("confirmation_timeout", session_id=session_id)

        # Save auto-proceed flag
        client = get_client()
        client.table("sessions").update({
            "confirmation_status": "auto",
            "updated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        }).eq("id", session_id).execute()

        # Proceed to extraction
        result = await _run_extraction_phase(session)

        # Notify user
        phone = session.get("user_phone", "")
        if phone:
            await send_message(
                phone,
                "Tu reporte se procesó automáticamente porque no confirmaste. "
                "Si hay errores, contacta a tu supervisor.",
            )
```

### DB changes

```sql
-- Agregar 'awaiting_confirmation' al CHECK constraint
ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_status_check;
ALTER TABLE sessions ADD CONSTRAINT sessions_status_check CHECK (
    status IN ('accumulating', 'segmenting', 'awaiting_confirmation', 'processing',
               'generating_outputs', 'completed', 'needs_clarification', 'failed')
);

-- Campo para tracking de confirmación
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS confirmation_status text
    DEFAULT NULL
    CHECK (confirmation_status IN ('confirmed', 'corrected', 'auto'));
```

### Cuándo NO pedir confirmación

- **1 sola visita:** No preguntar. Proceder directo.
- **Confidence >0.95 en todas las visitas:** No preguntar. La segmentación es casi segura.
- **Configuración de implementación:** `impl.require_confirmation = false` para desactivar.

---

## Intervención 2: Low-Confidence Review Flag (ALTA prioridad, BAJO esfuerzo)

### Por qué

Cuando el confidence_score es bajo, la extracción probablemente tiene errores. El manager no puede revisar TODOS los reportes, pero sí puede spot-check los de baja confianza.

### Implementación

Ya parcialmente construida: `visit_reports.status` soporta `needs_review`. Solo falta:

1. **Threshold desde DB** (no hardcoded):

```python
# extractor.py — después de extraction (línea ~124):
# Cargar threshold del visit_type config
from src.engine.config_loader import get_visit_type_schema
schema = await get_visit_type_schema(implementation, visit.visit_type)
threshold = schema.get("confidence_threshold", 0.7)

needs_review = confidence < threshold  # en vez de confidence < 0.5
```

2. **Google Sheets highlighting:**

```python
# sheets.py — después de escribir fila:
if report_data.get("status") == "needs_review":
    # Pintar fila de amarillo
    worksheet.format(f"A{row_num}:{last_col}{row_num}", {
        "backgroundColor": {"red": 1, "green": 0.95, "blue": 0.6}
    })
```

3. **Alert creation** (ya spec'd en Phase 5):

```python
# pipeline.py — después de save_visit_report:
if extraction.confidence_score < threshold:
    await _create_alert(
        impl=implementation,
        alert_type="low_confidence",
        severity="warning",
        title=f"Baja confianza: {extraction.inferred_location} ({extraction.confidence_score:.0%})",
        detail=f"Tipo: {extraction.visit_type}, archivos: {len(visit.files)}",
        context={"report_id": report_id, "session_id": session_id},
    )
```

---

## Intervención 3: Post-Extraction Summary Enrichment (MEDIA prioridad, BAJO esfuerzo)

### Por qué

El ejecutivo recibe un resumen genérico. Si pudiera ver un resumen más rico, detectaría errores temprano.

### Estado actual del summary (`build_whatsapp_summary`):

```
*Reporte de campo* - Carlos Lopez
Fecha: 2026-03-14 | 3 visita(s) | 8 archivo(s)

==============================
*1. Ferreteria El Constructor* (ferreteria)
Confianza: 92%

Precios Capturados: 3 registro(s)
  1. Cemento Gris 50kg - Argos: $32,000
  2. Cemento Gris 50kg - Holcim: $30,000
  ...
==============================
```

### Summary enriquecido propuesto:

```
*Reporte de campo* - Carlos Lopez
Fecha: 2026-03-14 | 3 visita(s) | 8 archivo(s)

==============================
*1. Ferreteria El Constructor* (ferreteria)
✅ Confianza: 92%

💰 3 precios capturados
   Argos: $32,000 | Holcim: $30,000 | Mortero: $18,000
📊 Share Argos: medio (Holcim domina)
⚠️ 1 alerta: Holcim mejor margen al ferretero
👤 Contacto: Pedro (positivo)

==============================
*2. Obra Centro Comercial Santafé* (obra civil)
✅ Confianza: 78%

🏗️ Etapa: estructura | 200 bultos/semana
📦 Proveedor: Holcim tipo 3
🎯 Oportunidad: Ofrecer Argos tipo 3

==============================
⚠️ La visita 2 tiene confianza baja (78%). Revisa los datos en el Sheet.

Detalle completo en Google Sheets.
```

### Implementación

```python
# pdf.py — nueva función o enrich de build_whatsapp_summary

def _build_enriched_visit_summary(report: dict, i: int) -> str:
    """Build enriched per-visit summary line."""
    data = report.get("extracted_data", {})
    lines = []

    location = report.get("inferred_location", "Sin ubicación")
    vtype = report.get("visit_type", "")
    conf = report.get("confidence_score", 0)
    conf_icon = "✅" if conf >= 0.7 else "⚠️"

    lines.append(f"*{i}. {location}* ({vtype})")
    lines.append(f"{conf_icon} Confianza: {conf:.0%}")
    lines.append("")

    # Precios (ferreteria)
    precios = data.get("precios", [])
    if precios:
        price_summary = " | ".join(
            f"{p.get('marca', '?')}: ${p.get('precio', '?'):,}"
            for p in precios[:3]
            if p.get("precio")
        )
        lines.append(f"💰 {len(precios)} precio(s): {price_summary}")

    # Share of shelf
    share = data.get("share_of_shelf", {})
    if share.get("argos_facing"):
        comp = share.get("competencia_dominante", "")
        lines.append(f"📊 Share Argos: {share['argos_facing']}" +
                     (f" ({comp} domina)" if comp else ""))

    # Alertas
    alertas = [a for a in data.get("actividad_competencia", [])
               if a.get("alerta")]
    if alertas:
        lines.append(f"⚠️ {len(alertas)} alerta(s): {alertas[0].get('actividad', '')}")

    # Obra data
    proyecto = data.get("datos_proyecto", {})
    if proyecto.get("etapa"):
        prov = data.get("proveedor_actual", [])
        prov_str = ", ".join(p.get("marca", "?") for p in prov[:2]) if prov else "?"
        lines.append(f"🏗️ Etapa: {proyecto['etapa']}")
        lines.append(f"📦 Proveedor: {prov_str}")

    # Oportunidades
    oportunidades = data.get("oportunidad", [])
    if oportunidades:
        lines.append(f"🎯 {oportunidades[0].get('descripcion', '')}")

    # Contacto
    contacto = data.get("relacion_comercial", {}) or data.get("contacto_clave", {})
    if contacto.get("nombre"):
        sat = contacto.get("satisfaccion", "")
        lines.append(f"👤 Contacto: {contacto['nombre']}" +
                     (f" ({sat})" if sat else ""))

    return "\n".join(lines)
```

---

## Intervención 4: Manager Approval Gate for Alerts (BAJA prioridad, MEDIO esfuerzo)

### Por qué

Cuando el sistema detecta una alerta competitiva (e.g., "Cemex tiene promo 2x1"), puede ser falso positivo. Antes de que llegue al Sheet del cliente, el manager puede confirmar/rechazar.

### Flujo

```
Pipeline detecta alerta competitiva con alerta=true
        │
        ▼
Engine → Manager (WhatsApp):
────────────────────
⚠️ Alerta competitiva detectada:

Ejecutivo: Carlos Lopez
Punto: Ferreteria La Esquina (Envigado)
Competencia: Cemex
Actividad: Promoción 2x1 en mortero de pega

¿Confirmar? Responde *SI* o *FALSO*
────────────────────

Manager responde "si" → fila se agrega al Sheet con flag verified=true
Manager responde "falso" → fila se marca en Sheet con flag verified=false, row gris
Manager no responde (1h) → fila se agrega con flag verified='pending'
```

### Prerequisitos

- Manager debe tener `role='manager'` en tabla `users`
- Manager debe tener `phone` registrado
- Requiere nuevo módulo: `src/channels/whatsapp/manager_flow.py`

### No implementar aún

Esta intervención agrega complejidad significativa (nuevo actor en el flujo WhatsApp, nuevo estado para alertas). Implementar solo cuando:
1. Hay un cliente real con manager activo
2. La tasa de falsos positivos en alertas competitivas es >30%
3. El manager ya está usando el Sheet activamente

---

## Intervención 5: Schema Test-Before-Deploy (MEDIA prioridad, BAJO esfuerzo)

### Por qué

Cuando un admin crea o modifica un visit_type schema, un error en el JSON puede resultar en extracciones vacías para todos los ejecutivos de esa implementación. Validar automáticamente antes de activar.

### Flujo

```
Admin crea/modifica visit_type via backoffice
        │
        ▼
Backend valida JSON schema structure
        │
        ├─ Invalid → retorna error con detalle
        │
        ▼
Backend corre test-extraction con sample input
        │
        ▼
Backoffice muestra preview:
────────────────────
Preview de extracción para "pharmacy_visit":

Input: "Farmacia en el centro, tienen Advil a 15 mil..."

Resultado:
{
  "productos_exhibicion": [
    {"nombre": "Advil", "precio": 15000, ...}
  ],
  "confidence_score": 0.78
}

✅ 3/4 categorías pobladas
⚠️ Categoría "material_pop" vacía

[Activar] [Editar schema] [Cancelar]
────────────────────
```

### Implementación

```python
# admin.py — modificar POST/PUT visit_type

@router.post("/api/admin/implementations/{impl_id}/visit-types")
async def create_visit_type(impl_id: str, body: VisitTypeCreate):
    # 1. Validate schema structure
    errors = _validate_schema_structure(body.schema_json)
    if errors:
        return {"success": False, "error": f"Schema inválido: {'; '.join(errors)}"}

    # 2. Run test extraction with sample input
    sample_input = _generate_sample_input(body.schema_json)
    test_result = await _run_test_extraction(body.schema_json, sample_input)

    # 3. Save as inactive (is_active=false) until admin confirms
    visit_type_id = await _save_visit_type(impl_id, body, is_active=False)

    return {
        "success": True,
        "data": {
            "id": visit_type_id,
            "test_result": test_result,
            "is_active": False,
            "message": "Schema guardado como borrador. Revisa el preview y activa cuando esté listo.",
        }
    }


def _validate_schema_structure(schema: dict) -> list[str]:
    """Validate that a visit_type schema has the required structure."""
    errors = []

    if "categories" not in schema:
        errors.append("Falta 'categories'")
        return errors

    for i, cat in enumerate(schema.get("categories", [])):
        if "id" not in cat:
            errors.append(f"Categoría {i}: falta 'id'")
        if "fields" not in cat:
            errors.append(f"Categoría {i}: falta 'fields'")
        for j, field in enumerate(cat.get("fields", [])):
            if "id" not in field:
                errors.append(f"Categoría {i}, campo {j}: falta 'id'")
            if "type" not in field:
                errors.append(f"Categoría {i}, campo {j}: falta 'type'")
            if field.get("type") not in ("string", "number", "boolean"):
                errors.append(f"Categoría {i}, campo {j}: type '{field.get('type')}' no soportado")

    return errors


def _generate_sample_input(schema: dict) -> str:
    """Generate a realistic sample input text for test extraction."""
    categories = schema.get("categories", [])
    parts = ["## Transcripciones de audio"]
    parts.append("**audio_test.ogg:** Estoy en un punto de venta. ")

    for cat in categories:
        label = cat.get("label", cat.get("id", ""))
        fields = cat.get("fields", [])
        field_names = [f.get("label", f.get("id", "")) for f in fields[:3]]
        parts.append(f"Sobre {label}: vi {', '.join(field_names)}. ")

    parts.append("\n## Observaciones de fotos")
    parts.append("**img_test.jpg:** Interior de punto de venta con productos visibles.")

    return "\n".join(parts)
```

---

## Prioridad de implementación

| # | Intervención | Esfuerzo | Impacto | Sprint |
|---|-------------|----------|---------|--------|
| 2 | Low-confidence review flag | 2h | Alto — catches bad extractions automatically | Inmediato |
| 3 | Summary enrichment | 3h | Medio — ejecutivo detecta errores | Inmediato |
| 5 | Schema test-before-deploy | 2h | Medio — prevents broken schemas | Siguiente |
| 1 | Segmentation confirmation | 6h | Alto — prevents cascade errors | Siguiente |
| 4 | Manager approval gate | 8h | Bajo — solo útil con manager activo | Futuro |

### Sprint recomendado

**Sprint HITL-1 (inmediato, 5h):**
- Item 2: Low-confidence flag (threshold de DB + Sheets highlight + alert)
- Item 3: Summary enrichment (nuevo `_build_enriched_visit_summary`)

**Sprint HITL-2 (siguiente, 8h):**
- Item 5: Schema validation + test preview
- Item 1: Segmentation confirmation (nuevo estado + handler + timeout)
- DB migration: `awaiting_confirmation` status + `confirmation_status` column

**Sprint HITL-3 (futuro, 8h):**
- Item 4: Manager approval gate (nuevo módulo `manager_flow.py`)
- WhatsApp templates para confirmación de alertas

---

## Templates WhatsApp completos

### Template: Segmentation Confirmation

```
Identifiqué {visit_count} visita(s) en tu reporte de hoy:

{for each visit:}
{i}. *{location}* ({visit_type_label})
   📁 {file_count} archivo(s) | {time_range}

{end for}
¿Es correcto? Responde *SI* para continuar o escribe tu corrección.
```

**Max length estimate:** 3 visits × ~80 chars + header/footer = ~400 chars (OK)

### Template: Enriched Summary

```
*Reporte de campo* - {user_name}
Fecha: {date} | {visit_count} visita(s) | {file_count} archivo(s)

{for each visit:}
==============================
{enriched_visit_summary}

{end for}
{if any visit has low confidence:}
⚠️ {count} visita(s) con confianza baja. Revisa en Google Sheets.

{end if}
Detalle completo en Google Sheets.
```

**Max length estimate:** 3 visits × ~200 chars + header/footer = ~800 chars (OK, WhatsApp limit is 4096)

### Template: Confirmation Timeout

```
Tu reporte se procesó automáticamente porque no confirmaste en 30 minutos.

{visit_count} visita(s) procesada(s). Si hay errores, contacta a tu supervisor.

Detalle en Google Sheets.
```

### Template: Manager Alert (futuro)

```
⚠️ Alerta competitiva detectada:

Ejecutivo: {exec_name}
Punto: {location} ({visit_type})
Competencia: {brand}
Actividad: {activity}

¿Confirmar? Responde *SI* o *FALSO*
```

---

## DB Migration resumen

```sql
-- Archivo: sql/004_hitl_states.sql

-- 1. Agregar awaiting_confirmation al CHECK constraint de sessions
ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_status_check;
ALTER TABLE sessions ADD CONSTRAINT sessions_status_check CHECK (
    status IN ('accumulating', 'segmenting', 'awaiting_confirmation', 'processing',
               'generating_outputs', 'completed', 'needs_clarification', 'failed')
);

-- 2. Tracking de confirmación
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS confirmation_status text
    CHECK (confirmation_status IN ('confirmed', 'corrected', 'auto', NULL));

-- 3. Timestamp de cuando se pidió confirmación
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS confirmation_requested_at timestamptz;
```

---

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Mitigación |
|--------|-------------|------------|
| Ejecutivo nunca confirma (100% auto-proceed) | Alta | Timeout de 30 min es suficiente. Monitorear tasa de auto-proceed. Si >80%, desactivar confirmación. |
| Corrección del ejecutivo es ambigua | Media | Usar Claude para interpretar la corrección (NLP sobre texto libre) |
| Summary enriquecido es muy largo | Baja | Limitar a primeros 3 items por categoría. Truncar a 1000 chars. |
| Confirmation agrega latencia | Media | Solo preguntar si >1 visita. Single visit = directo. |
| Schema validation bloquea deploys válidos | Baja | Validación es advisory (preview), no bloqueante. Admin siempre puede forzar activación. |
| Manager no usa WhatsApp para aprobar alertas | Alta | Por eso es baja prioridad. Backoffice es canal primario para managers. |
