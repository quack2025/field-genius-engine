# Field Genius Engine — Multimodal Capture → AI → Structured Reports

> **Repo:** `quack2025/field-genius-engine`
> **Deploy:** Railway — `https://field-genius-engine.up.railway.app`
> **Estado:** En construcción. Primera implementación: Argos (visitas de campo).

---

## Qué es este proyecto

**Field Genius Engine** es un motor reutilizable que convierte capturas no estructuradas (fotos, audio, video, texto) enviadas por WhatsApp en reportes estructurados. El motor es agnóstico al caso de uso — cada implementación define su propio schema de extracción.

### El modelo mental correcto

```
[Ejecutivo en campo]
       ↓ manda fotos, audios, videos a WhatsApp
[Engine: ingestion → segmentación → análisis → consolidación]
       ↓
[Google Sheets con datos estructurados]
[Presentación Gamma auto-generada]
[PDF vía WhatsApp al ejecutivo]
```

El ejecutivo **no cambia su comportamiento**. WhatsApp ya es su herramienta natural. El engine hace el trabajo de estructuración que antes tomaba horas o simplemente no se hacía.

---

## Por qué existe

Los formularios de campo siempre fallan. La gente no los llena, o los llena mal, o los llena después y olvida detalles. El problema no es disciplina — es que el formulario interrumpe el flujo natural de la visita.

Este engine invierte el modelo: **captura en el flujo, estructura después**. El ejecutivo habla, toma fotos, manda un video. La IA organiza todo.

---

## Arquitectura del engine

### Stack técnico

| Capa | Tecnología | Rol |
|------|-----------|-----|
| Canal entrada | WhatsApp Business API (Meta Cloud) | Recibir mensajes + media |
| Backend | FastAPI + Python (Railway) | Orquestación del pipeline |
| Storage | Supabase Storage | Guardar media recibida |
| Base de datos | Supabase PostgreSQL | Sesiones, reportes, usuarios |
| Transcripción | OpenAI Whisper API | Voz → texto |
| Visión | Claude Sonnet (claude-sonnet-4-20250514) | Análisis de fotos + frames de video |
| Video | ffmpeg → frame sampling | Extraer frames + audio del video |
| Clasificación | Claude Haiku (claude-haiku-4-5-20251001) | Extracción estructurada rápida |
| Output tabular | Google Sheets API | Datos por fila para análisis |
| Output presentación | Gamma API | Auto-generar slides del reporte |
| Notificación | WhatsApp Business API | Devolver PDF + resumen al ejecutivo |

### Estructura del repositorio

```
field-genius-engine/
├── CLAUDE.md                          # Este archivo — leer siempre primero
├── PROGRESS.md                        # Estado de construcción
├── pyproject.toml                     # Dependencias Python
├── .env.example
├── sql/
│   ├── schema.sql                     # Tablas Supabase
│   └── seed.sql                       # Datos de prueba
├── src/
│   ├── main.py                        # FastAPI app entry point
│   ├── config/
│   │   └── settings.py                # Variables de entorno (Pydantic Settings)
│   ├── engine/                        # ← CORE: no depende de implementaciones
│   │   ├── __init__.py
│   │   ├── ingestion.py               # Descarga y guarda media de WhatsApp
│   │   ├── transcriber.py             # Audio → texto via Whisper
│   │   ├── vision.py                  # Imagen/frames → observaciones via Claude Vision
│   │   ├── video.py                   # Video → frames + audio via ffmpeg
│   │   ├── segmenter.py               # Batch de archivos → sesiones identificadas
│   │   ├── extractor.py               # Sesión + schema → JSON estructurado via Claude
│   │   ├── consolidator.py            # Une transcripciones + visión + texto → contexto completo
│   │   └── schema_builder.py          # JSON config → system prompt dinámico
│   ├── implementations/               # ← Configuraciones por caso de uso
│   │   └── argos/
│   │       ├── __init__.py
│   │       ├── config.py              # Metadatos de la implementación
│   │       ├── schemas/
│   │       │   ├── ferreteria.json    # Schema extracción ferreterías
│   │       │   ├── obra_civil.json    # Schema extracción obras civiles
│   │       │   └── obra_pequeña.json  # Schema extracción obras pequeñas
│   │       └── classifier.py         # Inferir tipo de visita del contenido
│   ├── channels/
│   │   └── whatsapp/
│   │       ├── webhook.py             # POST /webhook/whatsapp — recibe mensajes
│   │       ├── sender.py              # Enviar mensajes/archivos al usuario
│   │       └── session_manager.py    # Acumular media por usuario/día
│   ├── outputs/
│   │   ├── sheets.py                  # → Google Sheets
│   │   └── gamma.py                   # → Gamma API (presentación)
│   ├── routes/
│   │   ├── webhook.py                 # Rutas WhatsApp
│   │   ├── reports.py                 # GET /api/reports/*
│   │   └── health.py                  # GET /health
│   └── utils/
│       ├── logger.py                  # Logging estructurado JSON
│       └── pdf.py                     # Generar PDF del reporte
└── tests/
    ├── test_segmenter.py
    ├── test_extractor.py
    └── test_pipeline.py
```

---

## Concepto central: el Schema de Implementación

Cada implementación define sus schemas en JSON. El engine los convierte en system prompts dinámicos para Claude.

### Estructura de un schema JSON

```json
{
  "implementation": "argos",
  "visit_type": "ferreteria",
  "display_name": "Visita a Ferretería",
  "description": "Auditoría de punto de venta: precios, exhibición, competencia",
  "primary_media": ["image", "voice"],
  "categories": [
    {
      "id": "precios",
      "label": "Precios capturados",
      "description": "Precios de productos Argos y competencia visibles en fotos o mencionados en audio",
      "fields": [
        { "id": "producto", "type": "string", "label": "Producto/referencia" },
        { "id": "marca", "type": "string", "label": "Marca" },
        { "id": "precio", "type": "number", "label": "Precio COP" },
        { "id": "presentacion", "type": "string", "label": "Presentación (ej: bolsa 50kg)" }
      ],
      "is_array": true,
      "applies_to": ["image", "voice"]
    },
    {
      "id": "share_of_shelf",
      "label": "Espacio en góndola",
      "fields": [
        { "id": "argos_facing", "type": "string", "label": "Espacio Argos (alto/medio/bajo)" },
        { "id": "competencia_dominante", "type": "string", "label": "Marca con más espacio" },
        { "id": "notas", "type": "string", "label": "Observaciones" }
      ],
      "applies_to": ["image"]
    },
    {
      "id": "actividad_competencia",
      "label": "Actividad de competencia",
      "fields": [
        { "id": "marca", "type": "string", "label": "Marca competidora" },
        { "id": "actividad", "type": "string", "label": "Descripción (promo, descuento, nuevo producto)" },
        { "id": "alerta", "type": "boolean", "label": "¿Requiere atención urgente?" }
      ],
      "is_array": true,
      "applies_to": ["image", "voice", "text"]
    },
    {
      "id": "relacion_comercial",
      "label": "Relación con el punto",
      "fields": [
        { "id": "nombre_contacto", "type": "string", "label": "Nombre del ferretero/contacto" },
        { "id": "satisfaccion", "type": "string", "label": "Percepción general (positiva/neutral/negativa)" },
        { "id": "oportunidad", "type": "string", "label": "Oportunidad de negocio detectada" },
        { "id": "seguimiento", "type": "string", "label": "Acción de seguimiento recomendada" }
      ],
      "applies_to": ["voice", "text"]
    }
  ],
  "confidence_threshold": 0.7,
  "sheets_tab": "Ferreterías"
}
```

### Cómo el engine usa el schema

`schema_builder.py` toma este JSON y genera el system prompt:

```
Eres un analista de campo especializado en visitas a ferreterías para Argos.
Analiza el contenido capturado y extrae información en estas categorías:

PRECIOS CAPTURADOS (aplica a: fotos, audio)
Extrae todos los precios visibles o mencionados...
[campos: producto, marca, precio COP, presentación]
Puede haber múltiples registros.

ESPACIO EN GÓNDOLA (aplica a: fotos)
...

Responde ÚNICAMENTE con JSON válido siguiendo este schema exacto:
{
  "precios": [...],
  "share_of_shelf": {...},
  ...
  "confidence_score": 0.0-1.0,
  "needs_clarification": false,
  "clarification_questions": []
}
```

---

## Pipeline de dos fases

### Fase 1 — Segmentación inteligente

Antes de extraer datos, el engine identifica cuántas visitas hay en el batch del día.

**Input:** todos los archivos del día de un usuario (con timestamps y transcripciones de audio)

**Proceso:** Claude recibe el contexto completo y produce un mapa de sesiones:

```json
{
  "sessions": [
    {
      "id": "session-1",
      "inferred_location": "Ferretería El Constructor, Medellín",
      "visit_type": "ferreteria",
      "confidence": 0.92,
      "files": ["img_001.jpg", "img_002.jpg", "audio_01.ogg"],
      "time_range": "10:15 - 10:52"
    },
    {
      "id": "session-2", 
      "inferred_location": "Obra Centro Comercial Santafé",
      "visit_type": "obra_civil",
      "confidence": 0.78,
      "files": ["img_003.jpg", "audio_02.ogg", "video_01.mp4"],
      "time_range": "14:30 - 15:20"
    }
  ],
  "unassigned_files": ["img_004.jpg"],
  "needs_clarification": true,
  "clarification_message": "La foto img_004.jpg no la pude ubicar en ninguna visita. ¿Es de El Constructor o de la obra del Santafé?"
}
```

Si `needs_clarification: true`, el engine le pregunta al ejecutivo por WhatsApp antes de procesar.

### Fase 2 — Extracción por sesión

Cada sesión identificada se procesa independientemente:
1. Consolidar todo el contenido (transcripciones + observaciones de visión + texto)
2. Inferir tipo de visita (ferretería / obra civil / obra pequeña)
3. Cargar schema correspondiente
4. Generar system prompt dinámico
5. Llamar a Claude con el contexto consolidado
6. Parsear y validar JSON de respuesta
7. Guardar en Supabase

---

## Modelo de sesión: daily-batch

```
DURANTE EL DÍA (acumulación)
────────────────────────────
Usuario manda cualquier medio → engine responde "📸 Recibido"
No procesa nada todavía. Solo acumula en la sesión del día.

AL FINAL (trigger)
──────────────────
Usuario manda: "reporte" | "generar" | "listo" | "fin"
→ Engine cierra la sesión del día
→ Corre Fase 1 (segmentación)
→ Si hay dudas → pregunta al usuario
→ Corre Fase 2 (extracción por visita)
→ Genera outputs (Sheets + Gamma + PDF)
→ Responde con resumen + PDF adjunto

CANAL COMPARTIDO (automático)
─────────────────────────────
Engine publica resumen en grupo "Reportes Argos"
El gerente ve todos los reportes del equipo consolidados
```

---

## Modelo de datos Supabase

### sessions
| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| implementation | text | 'argos' |
| user_phone | text | Teléfono WhatsApp |
| user_name | text | Nombre del ejecutivo |
| date | date | Fecha de la sesión |
| status | text | accumulating, segmenting, processing, completed, needs_clarification |
| raw_files | jsonb | Lista de archivos recibidos con metadata |
| segments | jsonb | Output de Fase 1 (mapa de visitas) |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### visit_reports
| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| session_id | uuid FK → sessions | |
| implementation | text | 'argos' |
| visit_type | text | 'ferreteria', 'obra_civil', 'obra_pequeña' |
| inferred_location | text | Nombre del punto |
| extracted_data | jsonb | Output estructurado de Claude |
| confidence_score | float | 0-1 |
| status | text | processing, completed, failed, needs_review |
| sheets_row_id | text | ID de fila en Google Sheets |
| gamma_url | text | URL de presentación generada |
| processing_time_ms | integer | |
| created_at | timestamptz | |

### users
| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| implementation | text | 'argos' |
| phone | text UNIQUE | Para lookup por WhatsApp |
| name | text | |
| role | text | 'executive', 'manager' |
| notification_group | text | ID del grupo de WhatsApp para resultados |
| created_at | timestamptz | |

---

## Outputs

### Google Sheets
- Una pestaña por tipo de visita (Ferreterías / Obras Civiles / Obras Pequeñas)
- Una fila por hallazgo o por visita (según el schema)
- Columnas generadas automáticamente desde el JSON schema
- Fire-and-forget: si Sheets falla, el reporte ya está en Supabase

### Gamma (presentación)
Dos modos:
1. **Gamma API directa:** llamada programática → presentación lista
2. **Super prompt:** generar un prompt estructurado para pegar en Gamma manualmente (fallback)

La presentación incluye: resumen ejecutivo, hallazgos por categoría, fotos anotadas como evidencia, alertas destacadas, acciones recomendadas.

### PDF via WhatsApp
- Generado con WeasyPrint desde template HTML
- Adjunto directamente en el chat del ejecutivo
- Resumen en texto plano en el mismo mensaje

---

## Reglas de código

1. **Python tipado** — Type hints en todas las funciones. Usar `pydantic` para modelos de datos.
2. **Async por defecto** — FastAPI es async. Todas las llamadas a APIs externas deben ser `async/await`.
3. **Error handling explícito** — Cada llamada externa (WhatsApp, Whisper, Claude, Supabase, Sheets, Gamma) tiene try/except con logging claro y fallback definido.
4. **Engine agnóstico** — `src/engine/` no puede importar nada de `src/implementations/`. Las implementaciones sí pueden usar el engine.
5. **Variables de entorno** — Nunca hardcodear keys. Todo desde `config/settings.py` via `pydantic-settings`.
6. **Prompts como código** — Los prompts viven en `src/engine/prompts/` como funciones Python que reciben parámetros tipados y retornan strings.
7. **Logging estructurado** — JSON en stdout/stderr. Cada paso del pipeline loguea: qué entró, qué salió, cuánto tardó.
8. **Respuestas consistentes** — Todas las rutas retornan `{ "success": bool, "data": T | None, "error": str | None }`.
9. **Idioma del código** — Código y comentarios en inglés. Prompts de IA y mensajes al usuario en español.
10. **Fire-and-forget para outputs** — Sheets y Gamma no bloquean el pipeline. Si fallan, se loguea y el reporte sigue en Supabase.

---

## Variables de entorno requeridas

```bash
# WhatsApp Business API
WHATSAPP_TOKEN=          # Meta Cloud API token
WHATSAPP_PHONE_ID=       # Phone Number ID de Meta
WHATSAPP_VERIFY_TOKEN=   # Token de verificación del webhook
WHATSAPP_GROUP_ID=       # ID del grupo donde publicar reportes

# Supabase
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# AI
OPENAI_API_KEY=          # Whisper transcripción
ANTHROPIC_API_KEY=       # Claude visión + clasificación

# Outputs
GOOGLE_SERVICE_ACCOUNT_EMAIL=
GOOGLE_PRIVATE_KEY=
GOOGLE_SPREADSHEET_ID=   # ID del Sheet de Argos
GAMMA_API_KEY=           # Gamma para presentaciones

# Config
DEFAULT_IMPLEMENTATION=argos
DEFAULT_LANGUAGE=es
NODE_ENV=production
```

---

## Multi-Agent Setup en Claude Code

- **Orchestrator** — Planifica tareas por sprint, asigna al Builder, revisa avance
- **Builder** — Implementa código, crea archivos, sigue las reglas de código
- **Critic** — Revisa código del Builder: busca bugs, valida reglas, sugiere mejoras

El Critic es especialmente importante en:
- `engine/segmenter.py` — lógica de segmentación de visitas
- `engine/extractor.py` — parsing y validación del JSON de Claude
- `engine/schema_builder.py` — generación dinámica de prompts
- `channels/whatsapp/session_manager.py` — manejo de estado por usuario

---

## Implementaciones disponibles

| Implementación | Cliente | Tipos de visita | Estado |
|----------------|---------|-----------------|--------|
| `argos` | Argos (cementos) | ferreteria, obra_civil, obra_pequeña | 🚧 En construcción |
| `eficacia` | Eficacia (impulsadoras) | supermarket_visit | ⏳ Migrar desde field-genius repo |

---

## Documentación detallada

Para contexto completo del proyecto (arquitectura, DB schema, endpoints, pipeline, implementaciones, backoffice, deploy), consultar la carpeta `agent_docs/`. Cada archivo cubre un área específica:

- `architecture.md` — Componentes del sistema, estructura de repos, principios de diseño
- `database_schema.md` — Las 6 tablas con columnas, tipos, notas, estructura de raw_files
- `api_endpoints.md` — Los 16+ endpoints documentados con método, ruta, descripción
- `pipeline.md` — Flujo daily-batch, 7 pasos del pipeline, modelos AI, ConfigLoader
- `implementations.md` — Detalle de Argos y Eficacia, estructura de schemas
- `backoffice.md` — Stack frontend, páginas, API client, patrones de estilo
- `deploy_and_infra.md` — Railway, Vercel, Supabase, Twilio config
- `sprint_history.md` — Todos los sprints completados y items pendientes

**Siempre consultar `agent_docs/` al retomar contexto tras perder conversación.**

---

## Sprints planificados

### Sprint 1 — Fundación (~2h)
- Setup FastAPI + Pydantic Settings
- Schema Supabase + seed data Argos (3 ejecutivos de prueba)
- Servicio Supabase básico
- Health check + test-db endpoints

### Sprint 2 — WhatsApp Ingestion (~3h)
- Webhook WhatsApp (verificación + recepción de mensajes)
- Descarga de media (fotos, audio, video) a Supabase Storage
- Session manager: acumular media por usuario/día
- Respuestas básicas ("Recibido 📸")

### Sprint 3 — Pipeline de análisis (~4h)
- Transcriber (Whisper)
- Vision analyzer (Claude Sonnet + fotos)
- Video processor (ffmpeg → frames + audio)
- Segmenter (Fase 1: identificar visitas en el batch)
- Schema builder (JSON config → system prompt)
- Extractor (Fase 2: extracción estructurada por visita)

### Sprint 4 — Outputs (~3h)
- Google Sheets writer (columnas dinámicas desde schema)
- Gamma API integration (presentación auto-generada)
- PDF generator (WeasyPrint)
- Respuesta final al ejecutivo via WhatsApp

### Sprint 5 — Polish (~2h)
- Flujo de clarificación (cuando segmentación tiene dudas)
- Publicación en grupo de resultados
- Error handling robusto
- Tests del pipeline con datos reales de Argos
- Deploy a Railway
