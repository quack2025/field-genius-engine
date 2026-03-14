# Field Genius Engine — Notas Pendientes

Documento vivo. Se actualiza al final de cada sprint con items que no bloquean el avance actual pero deben resolverse antes de produccion multi-cliente.

---

## Seguridad

- [x] **Secrets fail-fast** — `main.py` valida ANTHROPIC_API_KEY, OPENAI_API_KEY, SUPABASE_SERVICE_ROLE_KEY al arrancar. Si faltan, exit(1).
- [ ] **Admin API sin autenticacion** — Todos los endpoints `/api/admin/*` estan abiertos. Agregar JWT auth via tabla `backoffice_users` antes de exponer a clientes externos. (Sprint B)
- [ ] **`/api/simulate` sin auth** — Cualquiera puede simular mensajes. Proteger o deshabilitar en produccion. (Sprint 5)
- [ ] **`/api/test-db` sin auth** — Expone datos de usuarios. Proteger o eliminar. (Sprint 5)
- [ ] **HTML injection en PDF** — `_build_html()` en `pdf.py` inserta datos de usuario sin escapar. Riesgo bajo (datos vienen de AI, no de input directo) pero deberia sanitizarse. (Sprint 5)
- [ ] **Rate limiting** — No hay rate limiting en ningun endpoint. Agregar antes de multi-cliente. (Sprint 5)
- [x] **Rotar Supabase service_role key** — Secreto removido de `scripts/seed_eficacia.py`. Key debe rotarse en Supabase Dashboard. (Sprint D - accion del usuario)

## Pipeline

- [ ] **PDF y Gamma deshabilitados** — En `pipeline.py` lineas 253-255, PDF y Gamma estan comentados. Rehabilitar cuando esten listos. (Sprint 4)
- [ ] **Session post-completion** — Si un usuario envia mas archivos despues de "completed", se acumulan pero no se procesan. Definir UX: crear nueva session? Reabrir? (Sprint A)
- [x] **Frame extraction 5s** — Cambiado de 10s a 5s en `video.py`. Mejor detalle para gondolas de supermercado.

## Multi-tenant

- [x] **Trigger words desde DB** — `session_manager.py` ahora lee `trigger_words` de la implementacion via `config_loader.get_implementation()`. Fallback a defaults.
- [x] **Eficacia como default** — `settings.py` tiene `default_implementation = "eficacia"`.
- [x] **Google Spreadsheet Eficacia** — ID `1yhLUTWp1e2cP2svJEvZcJgyUMcIO0v5tNvrGaQ1h0CQ` configurado en DB.
- [ ] **Group publishing** — Publicar resumen en grupo de WhatsApp del equipo. No implementado aun. (Sprint 5)

## Backoffice

- [x] **Sprint C completado** — Repo `quack2025/field-genius-backoffice` creado. React 18 + Vite + Tailwind + Supabase Auth.
- [x] **Deploy a Vercel** — Produccion en `https://field-genius-backoffice.vercel.app`. Auto-deploy via `vercel --prod`.
- [x] **CORS en engine** — CORSMiddleware configurado en `main.py` (localhost, Vercel, xponencial.net).
- [x] **.env anon key** — Verificado: `sglvhzmwfzetyrhwouiw.supabase.co` con anon key correcta.
- [x] **Sessions viewer** — Lista filtrable + detalle con media timeline (imagenes, audio, video, texto) + signed URLs.

## Sprint D — Segundo cliente (Eficacia)

- [x] **Implementation creada** — `eficacia` con industria FMCG, prompts de vision y segmentacion especificos para retail/supermercados.
- [x] **Visit types creados** — `supermarket_visit`, `tienda_barrio` (TAT), `wholesale_visit` en tabla `visit_types`.
- [x] **Google Spreadsheet** — Sheet de Eficacia compartido con service account. ID configurado en DB.
- [ ] **Usuarios Eficacia** — Asignar telefonos de impulsadoras reales.
- [ ] **Test end-to-end** — Enviar fotos como usuario Eficacia por WhatsApp y verificar pipeline completo.

## Deploy / Infra

- [x] **Railway activo** — Dominio: `https://zealous-endurance-production-f9b2.up.railway.app`.
- [ ] **Twilio webhook URL** — Verificar que Twilio/WhatsApp apunta al dominio correcto de Railway.
- [ ] **Tests** — No hay tests automatizados corriendo en CI. Los archivos de test existen pero no estan validados. (Sprint 5)
- [ ] **WeasyPrint en Railway** — Requiere dependencias de sistema (pango, cairo). Verificar que el Dockerfile las incluya antes de rehabilitar PDF. (Sprint 4)

---

*Ultima actualizacion: 2026-03-14 — Trigger words desde DB, secrets fail-fast, frame 5s, Spreadsheet ID Eficacia*
