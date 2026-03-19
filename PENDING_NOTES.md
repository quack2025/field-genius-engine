# Field Genius Engine — Notas Pendientes

Documento vivo. Se actualiza al final de cada sprint.

---

## Seguridad

- [x] **Secrets fail-fast** — `main.py` valida ANTHROPIC_API_KEY, OPENAI_API_KEY, SUPABASE_SERVICE_ROLE_KEY al arrancar.
- [ ] **Admin API sin autenticacion** — Todos los endpoints `/api/admin/*` estan abiertos. Agregar JWT auth antes de multi-cliente.
- [ ] **`/api/simulate` y `/api/test-db` sin auth** — Proteger o deshabilitar en produccion.
- [ ] **HTML injection en PDF** — `pdf.py` inserta datos sin escapar. Bajo riesgo pero deberia sanitizarse.
- [ ] **Rate limiting** — No hay rate limiting en ningun endpoint.
- [x] **Rotar Supabase service_role key** — Secreto removido de scripts.

## Pipeline

- [x] **Phase 1 (Segmentacion)** — Multi-visita con clarificacion.
- [x] **Phase 2 (Extraccion)** — Haiku con schema dinamico, retry de JSON.
- [x] **Phase 3 (Analisis Estrategico)** — Pentagono de Babson via Sonnet. 5 dimensiones + Gold Insight + oportunidades.
- [x] **Pre-procesamiento al recibir** — Whisper y Vision corren como background tasks al recibir media. Segmenter usa cache si existe.
- [x] **Auto-split WhatsApp** — Mensajes largos se dividen en chunks de 1500 chars.
- [x] **Sheets retry** — Exponential backoff (3 intentos) para errores 503.
- [ ] **PDF y Gamma deshabilitados** — En `pipeline.py`, PDF y Gamma estan comentados. Rehabilitar cuando WeasyPrint este en Docker.
- [ ] **Session post-completion** — Archivos enviados despues de "completed" se acumulan pero no se procesan.
- [x] **Frame extraction 5s** — Video frames cada 5 segundos.

## UX (Quick Wins implementados)

- [x] **QW1** — Notificar falla del pipeline al usuario (send_message en except).
- [x] **QW2** — Hint de trigger word para palabras similares ("informe" → "escribe: reporte").
- [x] **QW3** — Notificar error de descarga de media.
- [x] **QW4** — Conteo de archivos en acknowledgment ("Recibido (7 archivo(s) hoy)").
- [x] **QW5** — Mensaje de progreso despues de segmentacion.
- [ ] **Onboarding message** — Al registrar usuario, enviar instrucciones por WhatsApp.
- [ ] **Auto-prompt 5pm** — Recordar al usuario que escriba "reporte" si tiene archivos acumulados.
- [ ] **Daily reminder** — Notificar usuarios inactivos.

## Multi-tenant

- [x] **Trigger words desde DB** — Per-implementation via config_loader.
- [x] **Eficacia como default** — `settings.py` + DB.
- [x] **Google Spreadsheet Eficacia** — ID configurado en DB.
- [x] **Babson framework Eficacia** — `analysis_framework` en `implementations` table.
- [ ] **Group publishing** — Publicar resumen en grupo de WhatsApp del equipo.

## Backoffice

- [x] **SessionDetail mejorado** — Transcripciones, descripciones de imagen, analisis Babson, segmentacion, GPS links, badges Sheets/Gamma.
- [x] **Deploy en Vercel** — `field-genius-backoffice.vercel.app`.
- [ ] **Consolidacion UI** — Boton para generar reporte consolidado multi-visita desde backoffice.
- [ ] **Dashboard de metricas** — Tabs: Pipeline Health, Data Quality, Executive Activity.
- [ ] **Alertas UI** — Tabla `alerts` creada (migration 003), falta frontend.

## DB Migrations pendientes de correr

- [x] `005_strategic_analysis.sql` — analysis_framework, strategic_analysis column, consolidated_reports table.
- [ ] `003_alerts.sql` — Tabla de alertas automaticas.
- [ ] `004_hitl_states.sql` — Estados awaiting_confirmation para Human-in-the-Loop.

## Deploy / Infra

- [x] **Railway activo** — `zealous-endurance-production-f9b2.up.railway.app`.
- [x] **Twilio webhook** — Verificado, recibe mensajes.
- [ ] **Tests automatizados** — Archivos de test existen pero no estan validados en CI.
- [ ] **WeasyPrint en Docker** — Requiere pango/cairo para rehabilitar PDF.

## Documentacion

- [x] `agent_docs/strategic_scenarios.md` — Escenarios tacticos vs estrategicos, paquetes, pricing, competencia.
- [x] `agent_docs/experience_quality_assessment.md` — Phase 1 UX assessment (5 criterios, 10 findings).
- [x] `agent_docs/usability_test_protocol.md` — 8 test tasks para validacion con usuarios.
- [x] `agent_docs/metrics_framework.md` — 4 niveles de metricas con SQL queries.
- [x] `agent_docs/monitoring_dashboard_spec.md` — 3 tabs + 6 alertas.
- [x] `agent_docs/hitl_workflow_spec.md` — 5 intervenciones HITL.
- [x] `agent_docs/executive_adoption_funnel.md` — Funnel + cohort analysis.

---

*Ultima actualizacion: 2026-03-19 — Phase 3 Babson en produccion, pre-procesamiento al recibir, backoffice mejorado, strategic_scenarios.md creado*
