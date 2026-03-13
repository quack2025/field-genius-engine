# Field Genius Engine — Notas Pendientes

Documento vivo. Se actualiza al final de cada sprint con items que no bloquean el avance actual pero deben resolverse antes de produccion multi-cliente.

---

## Seguridad

- [ ] **Admin API sin autenticacion** — Todos los endpoints `/api/admin/*` estan abiertos. Agregar JWT auth via tabla `backoffice_users` antes de exponer a clientes externos. (Sprint B)
- [ ] **`/api/simulate` sin auth** — Cualquiera puede simular mensajes. Proteger o deshabilitar en produccion. (Sprint 5)
- [ ] **`/api/test-db` sin auth** — Expone datos de usuarios. Proteger o eliminar. (Sprint 5)
- [ ] **Secrets con default vacio** — `twilio_auth_token`, `openai_api_key`, `anthropic_api_key` tienen default `""`. Si no estan configurados, el sistema falla silenciosamente en lugar de al inicio. (Sprint 5)
- [ ] **HTML injection en PDF** — `_build_html()` en `pdf.py` inserta datos de usuario sin escapar. Riesgo bajo (datos vienen de AI, no de input directo) pero deberia sanitizarse. (Sprint 5)
- [ ] **Rate limiting** — No hay rate limiting en ningun endpoint. Agregar antes de multi-cliente. (Sprint 5)

## Pipeline

- [ ] **PDF y Gamma deshabilitados** — En `pipeline.py` lineas 253-255, PDF y Gamma estan comentados. Rehabilitar cuando esten listos. (Sprint 4)
- [ ] **Session post-completion** — Si un usuario envia mas archivos despues de "completed", se acumulan pero no se procesan. Definir UX: crear nueva session? Reabrir? (Sprint A)

## Multi-tenant

- [ ] **Trigger words por implementacion** — `session_manager.py` usa `TRIGGER_WORDS` hardcodeado. Deberia leer de `implementations.trigger_words` en DB. (Sprint A)
- [ ] **Group publishing** — Publicar resumen en grupo de WhatsApp del equipo. No implementado aun. (Sprint 5)

## Backoffice

- [x] **Sprint C completado** — Repo `quack2025/field-genius-backoffice` creado. React 18 + Vite + Tailwind + Supabase Auth.
- [x] **Deploy a Vercel** — Produccion en `https://field-genius-backoffice.vercel.app`. Auto-deploy via `vercel --prod`.
- [x] **CORS en engine** — CORSMiddleware configurado en `main.py` (localhost:5173, localhost:3000, field-genius-backoffice.vercel.app).
- [x] **.env anon key** — Verificado: `sglvhzmwfzetyrhwouiw.supabase.co` con anon key correcta.

## Sprint D — Segundo cliente (Eficacia)

- [x] **Implementation creada** — `eficacia` con industria FMCG, prompts de vision y segmentacion especificos para retail/supermercados.
- [x] **Visit types creados** — `supermarket_visit` (5 categorias) y `wholesale_visit` (4 categorias) en tabla `visit_types`.
- [ ] **Google Spreadsheet** — Crear Sheet de Eficacia y compartir con service account. Actualizar `google_spreadsheet_id`.
- [ ] **Usuarios Eficacia** — Asignar telefonos de impulsadoras reales.
- [ ] **Test end-to-end** — Enviar fotos como usuario Eficacia por WhatsApp y verificar pipeline completo.

## Deploy / Infra

- [x] **Railway activo** — Dominio: `https://zealous-endurance-production-f9b2.up.railway.app` (dominio cambio al renombrar servicio).
- [ ] **Twilio webhook URL** — Verificar que Twilio/WhatsApp apunta al dominio correcto de Railway.
- [ ] **Tests** — No hay tests automatizados corriendo en CI. Los archivos de test existen pero no estan validados. (Sprint 5)
- [ ] **WeasyPrint en Railway** — Requiere dependencias de sistema (pango, cairo). Verificar que el Dockerfile las incluya antes de rehabilitar PDF. (Sprint 4)

---

*Ultima actualizacion: 2026-03-13 — Sprints C+D completados, backoffice deployed, CORS activo*
