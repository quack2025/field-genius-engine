# Plan de Produccion — Field Genius x Telecable

> Fecha: 2026-03-28
> Estado: Aprobado por cliente. En fase de implementacion.
> Multi-pais (Centroamerica). Hasta 1,000 usuarios. Roles: ventas, operadores, mercadeo.

---

## 1. Pricing Aprobado

**Setup unico: $5,500 USD**
- Configuracion multi-pais
- Personalizacion de frameworks por rol
- Onboarding de usuarios (bulk import)
- 3 frameworks de analisis customizados (competidor, cliente, comunicacion)

**Mensualidad por tier:**

| Plan | Usuarios | Precio/mes | Precio/usuario |
|------|----------|-----------|----------------|
| Starter | hasta 100 | $2,500 | $25 |
| Growth | hasta 500 | $6,000 | $12 |
| Enterprise | hasta 1,000 | $8,000 | $8 |

**Extras (upsell futuro):**
- Pais adicional: +$1,000 setup + $500/mes
- Usuarios 1,001-2,000: +$3,000/mes
- Dashboard ejecutivo tiempo real: +$1,000/mes
- Alertas automaticas a gerentes: +$500/mes
- API para integracion CRM/BI: +$500/mes

---

## 2. Estructura de Costos

### Costos fijos mensuales

| Concepto | Mensual | Anual |
|----------|---------|-------|
| Supabase Pro | $25 | $300 |
| Railway Pro | $20 | $240 |
| Dominio + DNS | $15 | $180 |
| WhatsApp Cloud API (base) | $50 | $600 |
| **Total** | **$110** | **$1,320** |

### Costos variables por tier

| | 100 users | 500 users | 1,000 users |
|--|-----------|-----------|-------------|
| Archivos/mes estimados | 1,500 | 7,500 | 25,000 |
| AI pre-procesamiento | $15 | $75 | $250 |
| AI reportes | $10 | $40 | $100 |
| WhatsApp API variable | $30 | $50 | $100 |
| **Total variable** | **$55** | **$165** | **$450** |
| **Total (fijo+variable)** | **$165** | **$295** | **$600** |

### Distribucion de ingresos (sociedad 50/50 + fee de operacion para Jorge)

| | 100 users | 500 users | 1,000 users |
|--|-----------|-----------|-------------|
| Revenue mensual | $2,500 | $6,000 | $8,000 |
| Costos operativos | -$165 | -$295 | -$600 |
| Jorge operacion | -$750 | -$1,500 | -$2,000 |
| Utilidad neta | $1,585 | $4,205 | $5,400 |
| Por socio (div 2) | $792 | $2,102 | $2,700 |
| **Jorge total/mes** | **$1,542** | **$3,602** | **$4,700** |
| **Socio total/mes** | **$792** | **$2,102** | **$2,700** |

---

## 3. Los 15 Aspectos Criticos para Produccion

### P0 — Bloqueantes (resolver antes de piloto)

#### 3.1 WhatsApp a escala
- **Problema:** whatsapp-web.js NO escala (Meta banea a ~200 msgs/dia). Twilio tiene problemas de verificacion y es caro.
- **Solucion:** WhatsApp Cloud API (Meta directo). Gratis las primeras 1,000 conversaciones/mes por numero/pais.
- **Accion:** Telecable aplica a verificacion Business (ellos son la empresa). Un numero por pais.
- **Alternativa:** 360dialog ($49/mes flat, API oficial Meta) si Meta tarda en aprobar.

#### 3.2 Multi-pais (country_config)
- **Problema:** Cada pais tiene competidores diferentes, moneda, planes, jerga.
- **Solucion:** Agregar `country_config` JSONB en implementations:
```json
{
  "CR": {
    "currency": "CRC",
    "competitors": ["Claro", "Movistar", "Liberty"],
    "products": ["Internet 100Mbps", "TV Basico", "Triple Play"],
    "slang": {"mae": "persona", "tuanis": "bien"}
  },
  "GT": {
    "currency": "GTQ",
    "competitors": ["Claro", "Tigo"],
    "products": [...]
  }
}
```
- **Impacto en prompts:** El vision_system_prompt y los frameworks se parametrizan con el contexto del pais.

#### 3.3 Roles y frameworks diferenciados
- **Problema:** Ventas, operadores y mercadeo necesitan capturar cosas diferentes y generar reportes diferentes.
- **Solucion:** Agregar `role` a users. Cada rol tiene frameworks asignados:
  - Ventas: competidor, cliente (captura diaria)
  - Operadores: instalacion, calidad_servicio (por visita tecnica)
  - Mercadeo: comunicacion, brand_tracking (esporadico)
- **Implementacion:** Campo `allowed_frameworks` por rol, o filtro en el menu de WhatsApp.

#### 3.4 Numeros de WhatsApp por pais
- **Recomendacion:** Un numero por pais (requerido por Meta para WhatsApp Business).
- **Los roles se manejan por software** (menu WhatsApp), no por numero.
- **Routing:** El webhook del Cloud API envia a nuestro backend, que identifica usuario por telefono y rutea al pais/rol correcto.

#### 3.5 Pricing y limites contractuales
- **Limites en contrato:**

| Recurso | Incluido | Excedente |
|---------|----------|-----------|
| Usuarios activos | Segun plan (100/500/1000) | $5/usuario extra |
| Archivos/mes | 50,000 | $0.01/archivo |
| Reportes generados/mes | 2,000 | $0.05/reporte |
| Paises configurados | 1 (Costa Rica) | $500/mes por pais |
| Retencion de media | 90 dias | Negociable |

### P1 — Necesarios para escala (resolver en primeras 4 semanas)

#### 3.6 Cola de tareas (job queue)
- **Problema:** Hoy usamos `asyncio.create_task()` que no sobrevive a un restart. Con 1,000 usuarios enviando media a las 8am, el server se satura.
- **Solucion:** Redis + queue (Celery, arq, o bull). Pre-procesamiento va a la cola, se ejecuta con rate limiting.
- **Prioridad:** Media pre-processing (Vision + Whisper) es lo mas pesado. Reportes son bajo demanda.

#### 3.7 Almacenamiento y retencion
- **Estimacion:** 1,000 users x 5 fotos/dia x 300KB = 1.5GB/dia = 45GB/mes
- **Supabase Storage:** $25/100GB (plan Pro).
- **Politica de retencion:**
  - Media raw (fotos, audio): eliminar a los 90 dias
  - Transcripciones + image_descriptions: conservar indefinidamente (son texto, pesan poco)
  - Reportes generados: conservar indefinidamente
  - session_facts: conservar indefinidamente (son JSON estructurado)
- **Implementacion:** Cron job semanal que limpia media > 90 dias.

#### 3.8 Onboarding masivo (bulk import)
- **Problema:** Registrar 1,000 telefonos uno por uno es imposible.
- **Solucion:** Endpoint `POST /api/admin/bulk-import-users` que acepta CSV:
```csv
phone,name,role,group,country
+50688001234,Carlos Mora,ventas,zona_san_jose,CR
+50688005678,Ana Lopez,operador,zona_heredia,CR
```
- **UI en backoffice:** Drag-and-drop de CSV en pagina de Users.

#### 3.9 Seguridad y compliance
- **Datos sensibles:** Precios de competencia, fotos de instalaciones, datos de clientes de Telecable.
- **Acciones:**
  - Habilitar RLS en Supabase (cada implementation solo ve sus datos)
  - Encriptar media en reposo (Supabase lo hace por default)
  - Audit trail de accesos (backoffice_users + logs)
  - Politica de retencion documentada
  - TOS y privacy policy para los usuarios
  - Backoffice auth: verificar JWT + allowed_implementations

#### 3.10 SLA y monitoring
- **Requirimiento:** 99.5% uptime (permite ~3.6h downtime/mes).
- **Acciones:**
  - Railway Pro con health checks + auto-restart
  - Webhook retry de WhatsApp (Meta reintenta 3 veces automaticamente)
  - Alertas con UptimeRobot (gratis) o Better Uptime
  - Logging estructurado para debugging (ya implementado con structlog)
  - Metricas de uso: sesiones/dia, archivos procesados, reportes generados

#### 3.11 Concurrencia y rate limiting
- **Anthropic Tier:** Verificar tier actual. Tier 3 permite 50 concurrent, 300 req/min.
- **OpenAI Whisper:** Rate limit 50 req/min por default.
- **Solucion:** Rate limiter en la cola de pre-procesamiento. Maximo 20 archivos en paralelo.

### P2 — Valor agregado (implementar despues del piloto)

#### 3.12 Dashboard ejecutivo en tiempo real
- **Que:** Los gerentes de Telecable ven KPIs agregados sin generar reportes manualmente.
- **Contenido:** Alertas de competencia por zona, tendencias semanales, heatmap de cobertura, top amenazas.
- **Basado en:** session_facts agregados con SQL, actualizado cada hora.
- **Precio extra:** +$1,000/mes.

#### 3.13 Alertas automaticas
- **Que:** Cuando extract_facts() detecta alert severity=high, notificacion instantanea al gerente de zona.
- **Canal:** WhatsApp (mismo numero) o email.
- **Ejemplo:** "ALERTA: Claro oferta 3 meses gratis en Heredia. Detectado por Carlos Mora hoy 10:30am."
- **Precio extra:** +$500/mes.

#### 3.14 Usage tracking y billing
- **Tabla:** `usage_logs` con sesiones/mes, archivos, reportes, tokens consumidos por implementation.
- **Dashboard:** En backoffice, pestaña "Uso" con graficas de consumo vs limites del plan.
- **Necesario para:** Facturacion, deteccion de abuso, planning de capacidad.

#### 3.15 Integracion con sistemas de Telecable
- **API REST:** Para que el CRM/BI de Telecable consuma datos de session_facts.
- **Webhooks:** Notificar al sistema de Telecable cuando un reporte se genera.
- **Export:** CSV/Excel de session_facts con filtros.
- **Precio extra:** +$500/mes.

---

## 4. Roadmap de Implementacion

### Fase 1: Pre-Piloto (Semana 1-2)
- [ ] Definir pricing final con Telecable y firmar contrato
- [ ] Telecable aplica a WhatsApp Cloud API (verificacion Business)
- [ ] Implementar country_config (CR como primer pais)
- [ ] Agregar roles a users + frameworks por rol
- [ ] Endpoint de bulk import (CSV)
- [ ] Ajustar prompts con contexto real de Telecable (competidores, planes, productos)

### Fase 2: Piloto (Semana 3-4)
- [ ] Onboarding de 50 usuarios de prueba en Costa Rica
- [ ] Testing con usuarios reales: ventas (20), operadores (20), mercadeo (10)
- [ ] Validar calidad de reportes con el equipo de Telecable
- [ ] Iterar prompts basado en feedback
- [ ] Implementar cola de tareas (Redis)
- [ ] Politica de retencion de media

### Fase 3: Rollout (Semana 5-8)
- [ ] Escalar a 100 usuarios (Plan Starter)
- [ ] Habilitar RLS en Supabase
- [ ] Monitoring + alertas de uptime
- [ ] Rate limiting en pre-procesamiento
- [ ] Documentar SLA

### Fase 4: Escala (Mes 3+)
- [ ] Escalar a 500+ usuarios (Plan Growth)
- [ ] Segundo pais (Guatemala o Honduras)
- [ ] Dashboard ejecutivo (si lo contratan)
- [ ] Alertas automaticas (si lo contratan)
- [ ] Usage tracking + billing dashboard

---

## 5. Decisiones Tecnicas Pendientes

| Decision | Opciones | Recomendacion | Estado |
|----------|---------|---------------|--------|
| WhatsApp provider | Cloud API vs 360dialog vs Twilio | Cloud API (gratis, oficial) | Pendiente verificacion |
| Job queue | Celery+Redis vs arq vs asyncio | arq (async-native, simple) | Por implementar |
| Multi-pais en DB | 1 implementation per country vs 1 con country_config | country_config JSONB (menos duplicacion) | Por implementar |
| Roles | Campo en users vs tabla roles | Campo `role` en users + `allowed_frameworks` | Por implementar |
| Media retention | Cron job vs Supabase lifecycle rules | Cron job semanal (mas control) | Por implementar |
| Backup | Supabase built-in vs custom | Supabase Pro incluye backups diarios | Cubierto |

---

## 6. System Prompts por Pais

Los system prompts deben incluir contexto especifico del pais. Ejemplo para el framework `competidor` en Costa Rica:

```
Eres un analista de inteligencia competitiva para Telecable en Costa Rica.

CONTEXTO DEL MERCADO:
- Telecable: operador de cable, internet y telefonia. Cobertura urbana principalmente.
- Competidores principales: Claro (America Movil), Movistar (Telefonica), Liberty (Cable Tica adquirido), Kolbi (ICE, estatal)
- Moneda: Colones (CRC). Tipo de cambio aproximado: 1 USD = 510 CRC.
- Planes actuales de Telecable: [lista de planes y precios actuales]
- Diferenciadores: servicio al cliente, cobertura de fibra optica, paquetes triple play

Al analizar cada captura de campo, identifica...
```

Cada pais tendria su version con competidores y contexto local actualizado. Telecable debe proveer la lista de planes/precios actuales para cada pais.

---

## 7. Metricas de Exito

| Metrica | Meta Piloto (50 users) | Meta Produccion (500+ users) |
|---------|----------------------|------------------------------|
| Adopcion | 70% de usuarios envian al menos 1 archivo/semana | 80% |
| Calidad de reportes | 4/5 rating por gerentes | 4.2/5 |
| Uptime | 95% | 99.5% |
| Tiempo de pre-procesamiento | < 30s por archivo | < 15s |
| Tiempo de generacion de reporte | < 60s individual | < 60s |
| Alertas detectadas/mes | Baseline | +20% vs manual |
| Cobertura de zonas | 5 zonas piloto | Todas las zonas operativas |
