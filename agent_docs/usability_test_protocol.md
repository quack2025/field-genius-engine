# Field Genius Engine — Protocolo de Usability Testing

**Fase 2 del UX/AI Quality Plan**
**Creado:** 2026-03-15
**Objetivo:** 8 tareas de test goal-based para validar las 3 journeys en condiciones reales de campo

---

## Principios de diseño del test

1. **WhatsApp-only para ejecutivos** — No hay pantalla web. El test es en el teléfono real del participante.
2. **Español siempre** — Instrucciones, tareas y métricas en español.
3. **Goal-based, no step-based** — Se le dice al participante QUÉ lograr, no CÓMO. Se mide si descubre el flujo solo.
4. **Condiciones reales** — T1 y T5 requieren fotos de un lugar real (tienda, bodega, oficina simulada). No sirven con screenshots.
5. **Simulación cuando es suficiente** — T2-T4 pueden usar `/api/simulate` para inyectar archivos sin WhatsApp real.

---

## Participantes

| Rol | Cantidad | Perfil | Reclutamiento |
|-----|----------|--------|---------------|
| Ejecutivo de campo | 3 | Vendedores o impulsadoras con smartphone Android, usan WhatsApp diariamente, NO han visto el sistema antes | Equipo de Eficacia o Argos |
| Gerente / Supervisor | 1 | Supervisor de equipo que revisará reportes en Google Sheets y backoffice | Cliente directo |
| Admin / Configurador | 1 | Persona técnica que configura implementaciones desde el backoffice | Equipo interno Genius Labs |

**Criterios de exclusión:**
- No incluir a nadie que haya participado en el desarrollo o demo del sistema
- El ejecutivo debe tener acceso a una tienda/punto real (o un espacio que simule uno)

---

## Equipamiento necesario

| Item | Para qué | Quién lo provee |
|------|----------|-----------------|
| Teléfono Android con WhatsApp | Ejecutivo envía media al sistema | Participante |
| Número WhatsApp del engine registrado en Twilio | Recibir mensajes | Genius Labs |
| Cámara de pantalla (grabación) | Capturar la pantalla del teléfono durante el test | Facilitador (AZ Screen Recorder o similar) |
| Laptop con acceso a Google Sheets | Manager revisa reportes | Participante (manager) |
| Laptop con acceso a backoffice | Admin configura implementación | Participante (admin) |
| 5 productos con precios visibles | Simular góndola de tienda | Facilitador monta escenario |
| Grabadora de audio (facilitador) | Think-aloud del participante | Facilitador |
| Checklist impreso de la tarea | Dar al participante | Facilitador |

---

## Pre-test setup

### Para el facilitador (antes de cada sesión de test):

1. **Verificar pipeline funcional:**
   ```bash
   curl https://field-genius-engine.up.railway.app/health
   # Debe retornar {"status": "ok"}
   ```

2. **Registrar el teléfono del participante:**
   ```bash
   curl -X POST https://field-genius-engine.up.railway.app/api/admin/implementations/eficacia/users \
     -H "Content-Type: application/json" \
     -d '{"phone": "+57XXXXXXXXXX", "name": "Participante Test", "role": "executive"}'
   ```

3. **Verificar que no hay sesión previa del día:**
   ```bash
   curl https://field-genius-engine.up.railway.app/api/sessions/+57XXXXXXXXXX
   ```

4. **Preparar escenario físico** (para T1 y T5):
   - Montar 3-5 productos con etiquetas de precio visibles
   - Tener al menos 2 marcas distintas
   - Si es posible, usar productos reales del cliente (cemento, alimentos, etc.)

5. **Iniciar grabación de pantalla** en el teléfono del participante.

### Briefing al participante (leer textual):

> "Vamos a probar un sistema nuevo para capturar información de visitas de campo usando WhatsApp. No estamos evaluándote a ti — estamos evaluando el sistema. Si algo no funciona o no entiendes algo, es culpa del sistema, no tuya. Piensa en voz alta: dime qué esperas que pase y qué piensas cuando ves cada respuesta."

---

## Tarea T1: Documentar un punto de venta (CAMPO)

**Rol:** Ejecutivo de campo
**Método:** Observación en campo
**Duración:** 45-60 min (incluye desplazamiento al punto)
**Requiere:** Punto de venta real o escenario montado

### Instrucción al participante:

> "Imagina que tu jefe te pide documentar este punto de venta. Necesitas registrar qué productos hay, sus precios, qué marcas de la competencia ves, y cómo está el espacio en la estantería. Tienes este número de WhatsApp [mostrar número]. Hazlo como creas conveniente."

### NO decirle:
- Qué tipo de archivos enviar (fotos, audio, video)
- Cuántos archivos enviar
- La palabra clave "reporte"
- Que debe enviar un mensaje al final

### Qué observar (facilitador):

| # | Observación | Métrica |
|---|------------|---------|
| O1 | ¿El participante sabe qué capturar sin instrucciones? | Discoverability |
| O2 | ¿Cuántas fotos toma? ¿Graba audio? ¿Video? | Eficiencia |
| O3 | ¿Lee y entiende el mensaje "Recibido (X archivos hoy)"? | Claridad |
| O4 | ¿Intenta generar el reporte? ¿Cómo? ¿Qué palabra usa? | Discoverability |
| O5 | Si escribe algo que no es trigger, ¿entiende la sugerencia? | Error Recovery |
| O6 | ¿Cuánto espera después del trigger? ¿Se pone ansioso? | Confianza |
| O7 | ¿Entiende el resumen final? ¿Identifica errores en los datos? | Claridad |
| O8 | ¿Intenta corregir algo del resumen? ¿Cómo? | Error Recovery |

### Criterios de éxito:

| Criterio | Pasa | Falla |
|----------|------|-------|
| Envía al menos 3 fotos del punto | Sí, sin ayuda | Necesitó que le dijeran |
| Descubre cómo generar el reporte | Sí, en <3 intentos | No lo descubre o necesita >3 intentos |
| Recibe resumen en <5 min | Pipeline completa | Timeout o error |
| Datos extraídos tienen ≥3 precios correctos | Precisión ≥60% | <60% |
| Participante confía en que los datos están bien | Dice "sí, está bien" | Dice "no sé si está correcto" |

### Post-tarea — preguntas al participante:

1. ¿Qué fue lo más confuso del proceso?
2. ¿Supiste en todo momento qué estaba pasando?
3. Si los datos del resumen tuvieran un error, ¿cómo lo corregirías?
4. ¿Usarías esto todos los días? ¿Por qué sí/no?
5. En una escala del 1-5, ¿qué tan fácil fue? (SUS simplificado)

---

## Tarea T2: Múltiples visitas en un día (SIMULACIÓN)

**Rol:** Ejecutivo de campo
**Método:** Moderado remoto (videollamada + WhatsApp)
**Duración:** 30 min
**Requiere:** 3 sets de fotos pre-preparados (ferretería, obra, otra ferretería)

### Setup del facilitador:

Preparar 3 carpetas con archivos:
- **Set A** (ferretería): 3 fotos de productos + 1 audio describiendo precios
- **Set B** (obra): 2 fotos de construcción + 1 audio describiendo materiales
- **Set C** (ferretería 2): 2 fotos de otra tienda + 1 audio

### Instrucción al participante:

> "Hoy visitaste 3 puntos: una ferretería por la mañana, una obra de construcción al mediodía, y otra ferretería por la tarde. Te voy a pasar los archivos de cada visita. Envíalos al sistema como si los hubieras tomado tú y genera tu reporte del día."

### Qué observar:

| # | Observación | Métrica |
|---|------------|---------|
| O1 | ¿Envía todos los archivos juntos o por visita? | Eficiencia |
| O2 | ¿Espera confirmación entre visitas o envía todo seguido? | Modelo mental |
| O3 | ¿El sistema segmenta correctamente en 3 visitas? | Segmentación (Phase 1) |
| O4 | ¿El resumen muestra 3 visitas separadas? | Claridad |
| O5 | ¿Los tipos de visita son correctos? (2 ferreterías + 1 obra) | Precisión AI |

### Criterios de éxito:

| Criterio | Pasa | Falla |
|----------|------|-------|
| Sistema identifica 3 visitas distintas | 3 visitas en segmentación | <3 o >3 visitas |
| Tipos de visita correctos | 2 ferretería + 1 obra | Tipos incorrectos |
| Archivos asignados a la visita correcta | ≥80% correctos | <80% |
| Participante entiende que son 3 reportes separados | Lo describe correctamente | Confundido |

---

## Tarea T3: Enviar archivos después del reporte (POST-COMPLETION)

**Rol:** Ejecutivo de campo
**Método:** Moderado remoto
**Duración:** 15 min
**Requiere:** T2 completada (sesión en estado `completed`)

### Instrucción al participante:

> "Acuerdas que olvidaste enviar unas fotos de la segunda ferretería. Envíalas ahora y trata de que se incluyan en tu reporte."

### Qué observar:

| # | Observación | Métrica |
|---|------------|---------|
| O1 | ¿Qué hace el participante? ¿Envía fotos y espera? ¿Vuelve a escribir "reporte"? | Modelo mental |
| O2 | ¿Qué responde el sistema? (actualmente: "Ya generaste tu reporte de hoy...") | Error Recovery |
| O3 | ¿El participante entiende que sus fotos NO se procesaron? | Claridad |
| O4 | ¿Intenta alguna alternativa? ¿Se frustra? | Satisfacción |

### Criterios de éxito:

| Criterio | Pasa | Falla |
|----------|------|-------|
| Sistema comunica claramente qué pasó con las fotos | Mensaje explicativo | Silencio o ambigüedad |
| Participante sabe cómo resolver la situación | Entiende la limitación | Queda confundido |

**Nota:** Actualmente el sistema NO soporta post-completion append. Esta tarea valida el gap conocido y mide la frustración real del usuario.

---

## Tarea T4: Responder a una pregunta de clarificación (CLARIFICATION FLOW)

**Rol:** Ejecutivo de campo
**Método:** Moderado remoto
**Duración:** 20 min
**Requiere:** Sesión con archivos ambiguos que disparen `needs_clarification`

### Setup del facilitador:

Preparar un set de archivos diseñado para generar ambigüedad:
- 4 fotos de un lugar (ferretería)
- 2 fotos de otro lugar (pero sin señalización clara — ¿es otra ferretería o una bodega?)
- 1 audio que mencione ambos lugares sin distinguirlos bien

Si el pipeline no dispara clarificación naturalmente, usar `/api/simulate` para inyectar una sesión con `needs_clarification: true`.

### Instrucción al participante:

> "Envía estos archivos al sistema y genera tu reporte. El sistema puede hacerte una pregunta — contesta como lo harías normalmente."

### Qué observar:

| # | Observación | Métrica |
|---|------------|---------|
| O1 | ¿El participante lee la pregunta de clarificación completa? | Atención |
| O2 | ¿Entiende qué le están preguntando? | Claridad del prompt |
| O3 | ¿Responde de forma natural o se confunde con el formato? | UX conversacional |
| O4 | ¿El sistema procesa la respuesta correctamente? | Robustez AI |
| O5 | ¿Cuánto tiempo pasa entre pregunta y respuesta? | Fricción |

### Criterios de éxito:

| Criterio | Pasa | Falla |
|----------|------|-------|
| Participante entiende la pregunta sin ayuda | Sí | Necesita que el facilitador explique |
| Responde en <2 min | Sí | >2 min o no responde |
| Sistema acepta la respuesta y continúa | Pipeline completa | Error o no procesa |
| Segmentación mejora con la clarificación | Visitas correctas | Misma segmentación que antes |

---

## Tarea T5: Primer uso sin instrucciones (ONBOARDING)

**Rol:** Ejecutivo de campo (nuevo, nunca ha visto el sistema)
**Método:** Observación en campo
**Duración:** 60 min
**Requiere:** Punto de venta real, participante que NUNCA ha oído del sistema

### Instrucción al participante (mínima):

> "Tu empresa contrató un servicio para que reportes tus visitas de campo por WhatsApp. Este es el número: [número]. Hoy tienes una visita en [lugar]. Haz tu reporte."

### NO decirle:
- Que debe enviar fotos/audio/video
- Qué información capturar
- La palabra "reporte" ni ningún trigger
- Que hay un resumen al final
- Nada sobre el sistema excepto el número de WhatsApp

### Qué observar:

| # | Observación | Métrica |
|---|------------|---------|
| O1 | ¿Qué hace primero? ¿Escribe "hola"? ¿Envía foto? | Modelo mental inicial |
| O2 | ¿Cuánto tiempo tarda en enviar el primer archivo? | Time-to-first-action |
| O3 | ¿Qué tipo de archivos envía? ¿Solo fotos? ¿Audio? | Discovery de capacidades |
| O4 | ¿Intenta generar un reporte? ¿Cómo? | Discoverability del trigger |
| O5 | Si escribe algo incorrecto, ¿el hint le ayuda? | Error Recovery |
| O6 | ¿Completa el flujo sin ayuda del facilitador? | Éxito autónomo |
| O7 | ¿En qué momento se rinde o pide ayuda? | Punto de quiebre |

### Criterios de éxito:

| Criterio | Pasa | Falla |
|----------|------|-------|
| Envía al menos 1 archivo sin ayuda | Sí | No, pide instrucciones |
| Descubre el trigger word en <5 intentos | Sí | No lo descubre |
| Completa el flujo completo sin intervención | Sí | Necesita ayuda |
| Tiempo total <30 min (sin contar desplazamiento) | Sí | >30 min |

**Esta es la tarea más importante.** Si un ejecutivo nuevo no puede completar el flujo sin instrucciones, necesitamos onboarding (mensaje de bienvenida, instrucciones al primer contacto).

---

## Tarea T6: Revisar reportes del equipo (MANAGER)

**Rol:** Gerente / Supervisor
**Método:** Moderado remoto (screen share)
**Duración:** 30 min
**Requiere:** Google Sheet con ≥10 filas de reportes de ≥3 ejecutivos, backoffice con sesiones visibles

### Setup del facilitador:

Asegurar que el Google Sheet tenga datos de al menos 3 ejecutivos con múltiples visitas. Si no hay datos reales, generar con `/api/simulate` usando 3 teléfonos distintos.

### Instrucción al participante:

> "Eres supervisor de un equipo de 5 ejecutivos de campo. Necesitas revisar los reportes de hoy, encontrar quién reportó actividad de competencia, y verificar si algún reporte parece incompleto. Usa el Google Sheet y el panel de administración."

### Qué observar:

| # | Observación | Métrica |
|---|------------|---------|
| O1 | ¿Entiende las columnas del Sheet? | Claridad de datos |
| O2 | ¿Puede filtrar por ejecutivo? | Eficiencia |
| O3 | ¿Encuentra alertas de competencia? ¿Cómo? | Discoverability |
| O4 | ¿Identifica reportes incompletos? ¿Por qué criterio? | Juicio de calidad |
| O5 | ¿Usa el backoffice para ver detalle de sesiones? | Adopción backoffice |
| O6 | ¿Puede ver las fotos/audios originales en el backoffice? | Trazabilidad |

### Criterios de éxito:

| Criterio | Pasa | Falla |
|----------|------|-------|
| Entiende columnas del Sheet sin explicación | Sí | Pregunta qué significan |
| Encuentra actividad de competencia en <5 min | Sí | >5 min o no la encuentra |
| Identifica al menos 1 reporte incompleto | Sí | No detecta problemas |
| Puede ver evidencia fotográfica de un reporte | Sí | No encuentra las fotos |

---

## Tarea T7: Investigar reporte incompleto (MANAGER)

**Rol:** Gerente / Supervisor
**Método:** Moderado remoto
**Duración:** 20 min
**Requiere:** T6 completada, 1 sesión con solo 2 de 5 visitas esperadas

### Setup del facilitador:

Crear una sesión con `/api/simulate` que tenga solo 2 visitas segmentadas pero el participante "debía" visitar 5 puntos (info que se le da verbalmente).

### Instrucción al participante:

> "Uno de tus ejecutivos debía visitar 5 puntos hoy pero el reporte solo muestra 2 visitas. Investiga qué pasó usando las herramientas que tienes."

### Qué observar:

| # | Observación | Métrica |
|---|------------|---------|
| O1 | ¿Dónde busca primero? ¿Sheets? ¿Backoffice? | Modelo mental |
| O2 | ¿Encuentra la sesión en el backoffice? | Eficiencia |
| O3 | ¿Revisa la timeline de media? ¿Ve archivos no asignados? | Trazabilidad |
| O4 | ¿Puede distinguir si el ejecutivo no capturó o si el AI falló? | Diagnóstico |
| O5 | ¿Qué acción toma? ¿Contacta al ejecutivo? | Workflow |

### Criterios de éxito:

| Criterio | Pasa | Falla |
|----------|------|-------|
| Encuentra la sesión del ejecutivo en backoffice | <3 min | >3 min o no la encuentra |
| Identifica cuántos archivos envió el ejecutivo | Sí | No puede determinarlo |
| Llega a una hipótesis (no capturó vs AI falló) | Sí | Queda sin conclusión |

---

## Tarea T8: Crear un nuevo tipo de visita (ADMIN)

**Rol:** Admin / Configurador
**Método:** Moderado remoto (screen share)
**Duración:** 30 min
**Requiere:** Acceso al backoffice, API admin disponible

### Instrucción al participante:

> "Eficacia necesita un nuevo tipo de visita: 'pharmacy_visit' para farmacias. Debe capturar: productos en exhibición (nombre, marca, precio, ubicación en tienda), material POP visible, y nivel de stock. Configúralo en el sistema y verifica que funciona."

### Qué observar:

| # | Observación | Métrica |
|---|------------|---------|
| O1 | ¿Sabe dónde crear el visit type? (backoffice vs API directa) | Discoverability |
| O2 | ¿Puede escribir el JSON schema sin ayuda? | Complejidad |
| O3 | ¿Usa el endpoint de test-extraction para validar? | Workflow |
| O4 | ¿El schema produce extracciones razonables? | Calidad del schema |
| O5 | ¿Comete errores en el JSON? ¿Cómo los detecta? | Error Recovery |

### Criterios de éxito:

| Criterio | Pasa | Falla |
|----------|------|-------|
| Crea el visit type con schema válido | <15 min | >15 min o JSON inválido |
| Prueba la extracción con test-extraction | Sí | No sabe que existe |
| El schema extrae datos razonables de un input de prueba | ≥3 campos correctos | <3 campos |
| Puede modificar el schema si el resultado no es bueno | Sí | Se atasca |

---

## Protocolo de ejecución

### Orden recomendado de ejecución

| Día | Tareas | Participantes | Ubicación |
|-----|--------|---------------|-----------|
| 1 (mañana) | T5 (onboarding) | Ejecutivo 1 (nuevo) | Campo — tienda real |
| 1 (tarde) | T1 (documentar punto) | Ejecutivo 2 | Campo — tienda real |
| 2 (mañana) | T2 + T3 + T4 | Ejecutivo 3 | Remoto (videollamada) |
| 2 (tarde) | T6 + T7 | Manager | Remoto (screen share) |
| 3 (mañana) | T8 | Admin | Remoto (screen share) |

**T5 va primero** porque es la prueba más reveladora y no contamina al participante con conocimiento previo.

### Durante cada sesión

1. **Briefing** (3 min) — Leer instrucción estándar
2. **Tarea** (variable) — Observar, no intervenir. Tomar notas con timestamps.
3. **Intervención solo si:** el participante se atasca >5 min sin progreso → dar hint mínimo y anotar
4. **Post-tarea** (5 min) — Preguntas de cierre
5. **SUS simplificado** — "Del 1 al 5, ¿qué tan fácil fue?" + "¿Qué cambiarías?"

### Notas del facilitador

Usar esta plantilla por tarea:

```
TAREA: T__
PARTICIPANTE: [nombre/código]
FECHA: ____-__-__
DURACIÓN: __ min

OBSERVACIONES (con timestamp):
[HH:MM] ...
[HH:MM] ...

INTERVENCIONES DEL FACILITADOR:
- [HH:MM] Hint dado: "..."

MÉTRICAS:
- Tiempo hasta primer archivo: __ min
- Intentos hasta trigger: __
- Pipeline completó: SÍ / NO
- Errores encontrados: __
- Score facilidad (1-5): __

CITAS TEXTUALES DEL PARTICIPANTE:
- "..."

BUGS DETECTADOS:
- BUG __: [descripción]
```

---

## Métricas agregadas post-test

| Métrica | Cálculo | Target |
|---------|---------|--------|
| Task completion rate | Tareas completadas sin ayuda / total | ≥75% |
| Time-to-first-action (T5) | Promedio de tiempo hasta primer archivo | <3 min |
| Trigger discovery rate | % que descubre "reporte" sin ayuda | ≥60% |
| Pipeline success rate | Pipelines completados / disparados | ≥90% |
| Segmentation accuracy (T2) | Visitas correctas / esperadas | ≥80% |
| SUS promedio | Promedio del score 1-5 | ≥3.5 |
| Bugs críticos encontrados | Bugs que bloquean el flujo | 0 |
| Intervenciones del facilitador | Total de hints dados | ≤5 total |

---

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Mitigación |
|--------|-------------|------------|
| Pipeline falla durante test | Media | Tener `/api/simulate` como backup. Pre-testear el flujo 1h antes. |
| Participante no tiene tienda accesible | Alta | Montar escenario con productos reales en oficina. |
| WhatsApp Sandbox limita mensajes | Media | Verificar cuota de Twilio antes. Tener 2 números backup. |
| Participante se frustra y abandona | Baja | Intervenir con hint mínimo. Recordar que evaluamos el sistema, no a ellos. |
| Sheets no actualiza en tiempo real | Baja | Refrescar Sheet manualmente. Verificar service account antes. |
| Audio en ambiente ruidoso | Alta (campo) | Pedir al participante que hable cerca del teléfono. Evaluar calidad de Whisper en ese contexto. |

---

## Entregables post-test

1. **Reporte de hallazgos** — Resumen de cada tarea con pass/fail, observaciones clave, citas del participante
2. **Lista de bugs** — Bugs encontrados durante testing, priorizados por severidad
3. **Recomendaciones de UX** — Cambios concretos al flujo basados en evidencia del test
4. **Video highlights** — Clips de 30s-1min de los momentos más reveladores
5. **Actualización de `PENDING_NOTES.md`** — Nuevos items descubiertos durante testing
