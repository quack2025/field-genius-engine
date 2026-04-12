# Field Genius Engine — Product-Market Fit Evaluation Plan

**Created:** 2026-03-14
**Updated:** 2026-03-14 — Corrección crítica de target user
**Scope:** Validate that the product solves a real problem before investing in quality/scale
**Source frameworks:** `product-plugins` (product-strategy, product-discovery, ai-product skills)
**Prerequisite for:** `ux_ai_quality_data_plan.md` — no tiene sentido pulir UX si el producto no resuelve un problema real

---

## Corrección crítica: ¿Quién es el usuario?

La asunción inicial era que el usuario es un "ejecutivo de ventas" haciendo rutas diarias de auditoría
(5-8 visitas/día, compliance, formularios obligatorios). **Esto es INCORRECTO.**

El usuario real tiene DOS perfiles:

### Perfil 1: Directivo que sale al mercado (el diferenciador)

| Aspecto | Descripción |
|---|---|
| **Quién** | Director comercial, gerente de marketing, VP de ventas — cargos directivos |
| **Qué hace** | Sale al mercado a conocer, observar, interactuar con consumidores/clientes |
| **Frecuencia** | 2-4 veces al mes (NO diario) |
| **Motivación** | Entender el mercado de primera mano, no auditar ejecución |
| **Qué captura hoy** | Fotos en su celular que quedan en el rollo, notas mentales que olvida, audios que manda a su equipo sin contexto |
| **Qué pasa con eso** | NADA. Se pierde. No se estructura. No se compara entre salidas. |
| **Dolor real** | "Salí al mercado, vi cosas interesantes, pero 3 días después ya no recuerdo los detalles ni puedo compartirlos con mi equipo de forma útil." |

### Perfil 2: Equipos de campo (mercado ya cubierto por competencia)

| Aspecto | Descripción |
|---|---|
| **Quién** | Promotoras, impulsadoras, vendedores de ruta |
| **Frecuencia** | Diario (5-8 visitas) |
| **Competencia directa** | Repsly, GoSpotCheck, VisitBasis — requieren annual commitment ($300+/user/mo, 12-month contract, pago anual upfront) |
| **Por qué compiten mal aquí** | El mercado de field execution ya está servido por plataformas maduras y caras |

### La oportunidad real: el directivo desatendido

Los Repsly / GoSpotCheck del mundo están diseñados para:
- Equipos de 50-200 promotoras con rutas fijas
- Auditoría diaria obligatoria
- Compliance y GPS tracking
- 12-month annual commitment, pago upfront
- Onboarding complejo, app nativa

**Un director que sale 3 veces al mes al mercado NUNCA va a:**
- Contratar Repsly por $300/user/mes para 3 salidas
- Firmar un contrato anual
- Instalar una app de auditoría en su celular personal
- Llenar un formulario mientras habla con un tendero

**Pero SÍ va a mandar fotos y audios por WhatsApp**, porque ya lo hace.

---

## La pregunta central (reformulada)

> "¿Los directivos de empresas de consumo/construcción en LatAm pierden insights valiosos
> de sus salidas al mercado porque no tienen una forma natural de estructurarlos?
> ¿Y estarían dispuestos a pagar por una solución que lo haga automáticamente desde WhatsApp?"

Field Genius tiene 4 sprints de features, 0 usuarios reales, y 0 datos de adopción.
No sabemos si alguien realmente quiere esto.

---

## Step 1: Identify Problem & Opportunity

**Skill:** `identify-problem-opportunity`
**Goal:** Separar síntomas de causas raíz — ¿cuál es el problema REAL?

### La señal que originó el producto

**Señal original (incorrecta):** "Los ejecutivos de campo no llenan los formularios de visita."
**Señal corregida:** "Los directivos salen al mercado regularmente, capturan fotos y observaciones, pero esos insights se pierden porque no hay un sistema que funcione con su flujo natural (WhatsApp) ni con su frecuencia esporádica."

**¿Es esto un síntoma o la causa?** Hay que descomponer:

| Síntoma | Posibles causas raíz | Cómo validar |
|---|---|---|
| Directivos toman fotos que quedan en el rollo | No hay sistema que las procese sin esfuerzo adicional | "¿Qué haces con las fotos que tomas en tus salidas al mercado?" |
| Insights de campo no llegan al equipo | Compartir requiere esfuerzo de estructuración que el directivo no tiene tiempo de hacer | "¿Alguna vez tu equipo te ha pedido un resumen de tu visita?" |
| Decisiones comerciales se toman con datos viejos | Los datos frescos de campo no se sistematizan | "¿Con qué información decides cambios de pricing/distribución?" |
| Las plataformas de field execution no aplican | Están diseñadas para auditoría diaria masiva, no para salidas esporádicas de directivos | "¿Han evaluado Repsly/GoSpotCheck? ¿Por qué no lo adoptaron?" |
| El directivo no usa formularios | No es que no quiera reportar — es que el formato no encaja con su rol | "¿Cómo te imaginas compartiendo lo que ves en campo?" |

### Preguntas que necesitan respuesta ANTES de seguir construyendo

1. **¿Los directivos ya capturan fotos/audios cuando salen al mercado?** Si sí, solo falta la estructuración automática. Si no, hay que crear el hábito de captura (mucho más difícil).
2. **¿Qué pasa con esas capturas hoy?** ¿Las mandan a un grupo de WhatsApp? ¿Las muestran en una reunión? ¿Se quedan en el celular?
3. **¿Qué decisiones tomarían SI tuvieran datos estructurados de sus salidas?** Pricing, distribución, respuesta competitiva, trade marketing?
4. **¿Con qué frecuencia salen?** Si es 1 vez al mes, ¿vale la pena un sistema? Si es 2-3 veces por semana, el valor es claro.
5. **¿Quién más en la organización se beneficiaría de estos datos?** Si solo el directivo los ve, es una nota personal. Si el equipo comercial los usa, es inteligencia de mercado.
6. **¿Cuánto pagan hoy por inteligencia de mercado?** (Nielsen, Kantar, GfK) — Field Genius no reemplaza datos de panel, pero complementa con observación directa.

### Problem Statement (hipótesis a validar)

> "Los directivos comerciales de empresas de consumo y construcción en LatAm salen al mercado
> 2-4 veces al mes y capturan información valiosa (precios, competencia, exhibición, relación
> con el canal), pero esos insights se pierden porque:
> (a) no tienen un sistema que funcione desde WhatsApp,
> (b) las plataformas de field execution son diseñadas para auditoría diaria masiva con annual commitments, y
> (c) no van a instalar una app ni llenar un formulario para 3 salidas al mes.
>
> Esto causa que las decisiones de pricing, distribución y respuesta competitiva se tomen
> con datos de panel (viejos, agregados) en vez de observación directa (fresca, granular)."

**Evidencia actual:** Anecdótica (conversaciones con Argos). No validada con datos.
**Confidence:** Provisional.

**Deliverable:** Problem statement validado o reformulado después de entrevistas.

---

## Step 2: Apply JTBD Framework

**Skill:** `apply-jtbd-framework`
**Goal:** Entender las motivaciones reales de cada actor

### Job 1: Directivo que sale al mercado (USUARIO PRINCIPAL)

```
CUANDO salgo al mercado a visitar puntos de venta y veo precios,
exhibición, actividad de la competencia, y hablo con tenderos,

QUIERO que mis fotos y notas de voz se conviertan automáticamente
en un reporte estructurado sin que yo tenga que hacer nada más
allá de lo que ya hago (mandar por WhatsApp),

PARA QUE esos insights no se pierdan y mi equipo comercial
pueda actuar sobre ellos con datos frescos de primera mano.
```

**Dimensiones:**

| Dimensión | Lo que busca | Lo que evita |
|---|---|---|
| **Funcional** | Convertir observaciones en datos accionables sin esfuerzo extra | Llenar formularios, abrir apps, escribir reportes después |
| **Emocional** | Sentir que su tiempo en campo fue productivo, no solo anecdótico | Sentir que instalar una app lo convierte en un "promotor" — es director |
| **Social** | Que su equipo vea que está conectado con el mercado, que lidera con ejemplo | Parecer desorganizado cuando muestra fotos sueltas en una reunión |

**Struggling moment:** "Salí al mercado el martes, vi que Holcim tiene una promoción agresiva en ferreterías del sur. Tomé fotos. Mandé un audio al grupo. Pero el viernes en la reunión comercial ya no tengo los datos organizados y termino diciendo 'vi que la competencia está fuerte' sin datos concretos."

**Alternativas que evalúa:**

| Alternativa | Por qué la usa | Por qué falla |
|---|---|---|
| Fotos que quedan en el rollo del celular | 0 esfuerzo | Se pierden entre 500 fotos personales. Nunca se estructuran. |
| Audio de WhatsApp al equipo | Rápido, natural | Nadie escucha un audio de 3 min. No es buscable ni comparable. |
| Fotos al grupo de WhatsApp con comentario | Ya lo hacen | 50 fotos sin contexto. El equipo no sabe qué hacer con ellas. |
| Pedir a un asistente que organice | Se delega | Asistente no estuvo en campo, interpreta mal. Tarda 1-2 días. |
| Repsly / GoSpotCheck | — | **NUNCA lo consideran.** Annual commitment de $300+/user/mo, diseñado para 50 promotoras, no para 1 director que sale 3 veces al mes. Es como contratar SAP para una tienda de barrio. |
| Google Forms / Excel después | "Debería..." | Nunca lo hace. La reunión ya pasó. Los datos se quedaron en su cabeza. |
| No hacer nada | — | Es lo que pasa hoy. Los insights mueren en el celular del directivo. |

**Insight clave:** El directivo YA captura (fotos, audios). El problema no es captura — es **estructuración sin esfuerzo**. Field Genius no cambia el comportamiento, solo agrega inteligencia a lo que ya hacen.

### Job 2: Equipo de campo / promotoras (USUARIO SECUNDARIO)

```
CUANDO visito 5-8 puntos de venta por día y necesito reportar
precios, exhibición y competencia,

QUIERO enviar mis fotos y audios por WhatsApp en vez de llenar
un formulario en una app que se traba,

PARA QUE pueda enfocarme en vender y no en reportar.
```

**Nota:** Este job SÍ tiene competencia directa (Repsly, GoSpotCheck). La ventaja de Field Genius es:
- Sin app (WhatsApp ya está instalado)
- Sin annual commitment (pay-per-use posible)
- Sin onboarding complejo
- La desventaja: no tiene GPS tracking ni compliance features

### Job 3: Equipo comercial / analistas (CONSUMIDOR DE DATOS)

```
CUANDO necesito preparar la reunión comercial del lunes con datos
frescos de campo,

QUIERO datos estructurados y comparables de las salidas
del director y del equipo,

PARA QUE pueda construir una vista competitiva actualizada
sin llamar a cada persona a preguntar "¿qué viste?".
```

**Struggling moment:** "El director salió al mercado la semana pasada. Me mandó 20 fotos al WhatsApp sin contexto. Necesito armar una presentación para el comité y tengo que adivinar qué es cada foto."

**Insight:** El equipo comercial es quien MÁS sufre la falta de estructura. Ellos son los que convierten insights en acciones. Hoy, reciben ruido (fotos sueltas, audios largos) y deben crear la estructura manualmente.

**Deliverable:** 3 JTBD statements validados + mapa de alternativas.

---

## Step 3: Frame AI Product Value

**Skill:** `frame-ai-product-value`
**Goal:** ¿El AI realmente agrega valor, o es tecnología buscando problema?

### El test ácido: ¿Qué pasa sin AI?

**Para un directivo que sale 3 veces al mes:**

| Con Field Genius (AI) | Sin Field Genius (lo que hace hoy) | Delta real |
|---|---|---|
| Manda fotos por WhatsApp → recibe reporte estructurado | Manda fotos al grupo → nadie las organiza → se pierden | Insights capturados vs perdidos |
| Audio transcrito y clasificado por visita | Audio queda en el chat → nadie lo escucha dos veces | Datos recuperables vs efímeros |
| Datos comparables entre salidas | Cada salida es anecdótica, no comparable | Tendencias vs anécdotas |
| Reporte listo en 10 min post-trigger | Nunca hay reporte (o asistente tarda 2 días) | Inmediato vs nunca |
| Costo: ~$2-5 por sesión (AI + Whisper) | Costo: $0 (pero valor perdido es enorme) | Bajo costo vs alto costo de oportunidad |

**Para equipos de campo (20+ promotoras):**

| Con Field Genius | Sin Field Genius (Repsly/GoSpotCheck) | Delta real |
|---|---|---|
| WhatsApp (ya instalado) | App nativa que deben instalar y aprender | Adoption rate: ~90% vs ~40-60% |
| Pay-per-session (sin compromiso anual) | $300+/user/mo con 12-month annual commitment upfront | $60/user/mo vs $3,600/user/año |
| Setup en 1 día (JSON schema) | Setup en 2-4 semanas (configuración enterprise) | Time to value |
| Sin GPS tracking | Con GPS tracking + compliance | Trade-off: simplicidad vs control |

**Veredicto:** Para directivos, el valor no es escala — es **capturar algo que hoy se pierde completamente**. El competidor no es Repsly, es "no hacer nada". Para equipos de campo, el valor es **accesibilidad y costo** vs plataformas enterprise.

### Build / Don't Build Assessment

| Factor | Assessment |
|---|---|
| ¿Resuelve un problema real? | Probable para directivos (insights que se pierden). Validar con entrevistas. |
| ¿Los usuarios adoptarían? | MUY Alto para directivos — 0 cambio de comportamiento (ya mandan fotos por WhatsApp). |
| ¿El AI agrega valor vs alternativas? | Para directivos: SÍ incluso para 1 usuario (no hay alternativa razonable). Para equipos: SÍ por costo. |
| ¿Es viable técnicamente? | Sí — pipeline funciona end-to-end. |
| ¿El modelo de negocio funciona? | Desconocido — pero el pricing puede ser por sesión (no annual commitment), lo cual ES el diferenciador. |
| ¿Hay competencia directa para directivos? | NO. Repsly/GoSpotCheck no compiten aquí. El competidor es "no hacer nada". |
| ¿Hay competencia para equipos de campo? | Sí, pero Field Genius compite en accesibilidad y costo, no en features. |

**Recommendation:** Continue building. El segmento de directivos es un **blue ocean** — nadie lo atiende.
Validar con entrevistas ANTES del Sprint 5.

**Deliverable:** Value frame document con build/don't build assessment.

---

## Step 4: Discovery Research — Entrevistas de validación

**Skills:** `scope-discovery-research` + `run-user-interviews`
**Goal:** Hablar con 5-8 personas reales antes de seguir construyendo

### Entrevistas necesarias

| # | Perfil | Empresa | Qué validar | Preguntas clave |
|---|---|---|---|---|
| 1-2 | **Director comercial / VP ventas** | Argos o similar (construcción) | ¿Sale al mercado? ¿Con qué frecuencia? ¿Qué hace con lo que observa? | "Contame de la última vez que saliste al mercado" |
| 3 | **Gerente de marketing / trade** | Consumo masivo | ¿Sale a ver exhibición? ¿Cómo comparte lo que ve? | "¿Cómo compartes con tu equipo lo que ves en punto de venta?" |
| 4 | **Analista / equipo comercial** | Argos o similar | ¿Recibe fotos/audios del director? ¿Qué hace con ellos? | "¿Tu jefe te manda fotos de sus salidas? ¿Las usas para algo?" |
| 5-6 | **Gerente de canal / KAM** | FMCG | ¿Visita clientes? ¿Documenta? | "Cuando visitas un cliente grande, ¿cómo documentas la visita?" |
| 7 | **Jefe de impulsadoras** | Eficacia | ¿Cómo reportan hoy? ¿Qué herramientas evaluaron? | "¿Evaluaron Repsly o GoSpotCheck? ¿Por qué sí/no?" |
| 8 | **Director de otra industria** | Farmacéutica, automotriz, agroindustria | ¿El problema es universal o solo en consumo/construcción? | "¿Tiene equipos que visitan el mercado? ¿Cómo capturan información?" |

### Guía de entrevista para DIRECTIVOS (30 min)

**Bloque 1: Salidas al mercado (10 min)**
- "¿Cada cuánto sales a visitar puntos de venta / clientes / el mercado?"
- "Contame de la última vez que saliste. ¿A dónde fuiste? ¿Qué buscabas?"
- "Cuando estás en el punto, ¿qué haces? ¿Tomas fotos? ¿Hablas con alguien? ¿Grabas algo?"
- "¿Con quién vas? ¿Solo o con equipo?"

**Bloque 2: ¿Qué pasa después de la salida? (10 min)**
- "Después de visitar el mercado, ¿qué haces con las fotos/audios que tomaste?"
- "¿Las compartes con alguien? ¿Cómo?" (WhatsApp, email, reunión)
- "¿Alguna vez quisiste buscar una foto de una visita anterior y no la encontraste?"
- "¿Has sentido que lo que viste en campo no se tradujo en una acción concreta?"
- "¿Tu equipo comercial usa lo que observas en campo para tomar decisiones?"
- "¿Han evaluado alguna herramienta de field execution? ¿Qué les pareció?" (Si mencionan Repsly/GoSpotCheck: "¿Por qué no la adoptaron?")

**Bloque 3: Reacción al concepto (10 min)**
- "Imaginá que todo lo que mandás por WhatsApp durante tu salida (fotos, audios, videos) se convierte automáticamente en un reporte estructurado con precios, competencia, observaciones. ¿Lo usarías?"
- "¿Qué te preocuparía?" (que el AI interprete mal, privacidad, que sea un gasto innecesario)
- "¿Qué información de campo sería la más valiosa de tener estructurada?"
- "Si esto costara [X] por salida, ¿tu empresa pagaría?" (probar: $5, $20, $50 por sesión)
- "¿Lo usarías solo tú, o también tu equipo comercial?"

### Guía de entrevista para EQUIPOS DE CAMPO (30 min)

**Bloque 1: Situación actual (10 min)**
- "Contame cómo es un día típico de trabajo en campo."
- "¿Cuántos puntos visitás por día?"
- "¿Qué información capturás durante una visita?" (no sugerir — dejar que digan)
- "¿Cómo registrás esa información?" (papel, app, fotos, nada)
- "¿Cuánto tiempo te toma reportar al final del día?"

**Bloque 2: Dolor (10 min)**
- "¿Qué pasa cuando no reportás?" (consecuencias reales)
- "¿Alguna vez perdiste información importante por no registrarla a tiempo?"
- "¿Tu jefe te pide reportes? ¿Cada cuánto? ¿Qué hace con ellos?"
- "¿Han intentado usar alguna app para esto? ¿Qué pasó?"

**Bloque 3: Reacción al concepto (10 min)**
- "¿Si pudieras mandar fotos y audios por WhatsApp y que un sistema los convirtiera automáticamente en un reporte, lo usarías?"
- "¿Qué te preocuparía?"
- "¿Preferirías esto o una app dedicada? ¿Por qué?"
- "¿Cuánto crees que tu empresa pagaría por esto?" (por persona/mes)

### Señales de PMF a buscar en las entrevistas

| Señal | PMF fuerte | PMF débil |
|---|---|---|
| Reacción al concepto | "¿Dónde firmo?" / "¿Cuándo puedo probarlo?" | "Interesante..." / "Tendría que pensarlo" |
| Dolor actual | "Pierdo 1 hora diaria en reportes" / "Mi jefe me regaña cada semana" | "No es un gran problema" / "Ya tenemos algo que funciona" |
| Alternativas | "Intentamos 3 apps y ninguna pegó" | "No hemos buscado soluciones" |
| Willingness to pay | Monto concreto sin pensarlo mucho | "Depende..." / "Tendría que consultarlo" |
| Frequency | Todos los días capturan información | Capturan esporádicamente |
| Pull | "¿Pueden agregarle X?" (piden features) | No hacen preguntas |

**Deliverable:** 5-8 entrevistas transcritas + síntesis de findings.

---

## Step 5: Assess Product-Market Fit

**Skill:** `assess-product-market-fit`
**Goal:** Con los datos de las entrevistas, clasificar el nivel de PMF

### PMF Assessment Framework

| Indicador | Cómo medirlo | Fuente |
|---|---|---|
| **Retención** | ¿Los ejecutivos del piloto reportan todos los días después de semana 2? | Supabase sessions |
| **NPS / Sean Ellis** | "¿Qué tan decepcionado estarías si ya no pudieras usar esto?" (Muy/Algo/No mucho) | Encuesta post-piloto |
| **Engagement orgánico** | ¿Mandan más fotos con el tiempo? ¿O menos? | raw_files count trend |
| **Pull signals** | ¿Piden features? ¿Preguntan cuándo estará listo X? | Notas de entrevistas |
| **Word of mouth** | ¿Un ejecutivo le cuenta a otro? ¿Otros equipos preguntan? | Observación |
| **Willingness to pay** | ¿El director pone presupuesto sin negociar? | Conversación comercial |
| **Alternative abandonment** | ¿Dejan de usar formularios/apps cuando tienen Field Genius? | Observación |

### Clasificación de PMF

| Nivel | Señales | Qué hacer |
|---|---|---|
| **Pre-fit** | Entrevistados dicen "interesante" pero no muestran urgencia. No piden probarlo. Alternativas actuales "funcionan más o menos". | Pivot o reformular el problema. No invertir más en features. |
| **Early signals** | 2-3 entrevistados muestran dolor real. Quieren probarlo. Pero no claro si pagarían. | Piloto de 4 semanas con 3-5 ejecutivos. Medir retención diaria. |
| **Strong signals** | Ejecutivos del piloto reportan diariamente. Gerente toma decisiones con los datos. Piden features. Director pregunta precio. | Invertir en calidad (ejecutar `ux_ai_quality_data_plan.md`). Definir pricing. |
| **Confirmed fit** | Retención >80% en semana 4+. Segundo cliente pide acceso. Willing to pay sin negociar. | Escalar. Multi-tenant. Equipo de ventas. |

**Deliverable:** PMF assessment document con nivel + evidencia + next steps.

---

## Step 6: Strategic Positioning (si PMF = Early signals o mejor)

**Skill:** `define-strategic-positioning`
**Goal:** Definir para quién es y para quién NO es

### Posicionamiento hipótesis — DOS segmentos

**Segmento A: Directivos (blue ocean — sin competencia directa)**

```
Para [directivos comerciales de empresas de consumo y construcción en LatAm]
que [salen al mercado regularmente pero pierden los insights porque no van a
instalar una app de auditoría ni llenar formularios para 3 salidas al mes],

Field Genius es [un asistente de inteligencia de campo vía WhatsApp]
que [convierte fotos, audios y videos en reportes estructurados
automáticamente, sin cambiar nada en cómo trabajan],

a diferencia de [no hacer nada (lo que hacen hoy)]
donde [las observaciones de campo mueren en el rollo de fotos
y se convierten en anécdotas en vez de datos].
```

**Segmento B: Equipos de campo (red ocean — compite con Repsly/GoSpotCheck)**

```
Para [equipos de promotoras y vendedores de ruta en LatAm]
que [necesitan reportar desde campo pero las plataformas enterprise
exigen annual commitment de $3,600+/user y apps que no adoptan],

Field Genius es [un sistema de captura vía WhatsApp sin app ni contratos anuales]
que [estructura reportes automáticamente desde el canal que ya usan],

a diferencia de [Repsly, GoSpotCheck, VisitBasis]
que [cuestan $300+/user/mes con 12-month minimum, requieren app nativa,
y tienen adoption rates de 40-60% porque los equipos no las usan].
```

### Para quién NO es (trade-offs explícitos)

| Segmento excluido | Por qué no |
|---|---|
| Empresas que necesitan GPS tracking + compliance estricto | Field Genius es captura e inteligencia, no vigilancia |
| Empresas que ya adoptaron Repsly/GoSpotCheck exitosamente | Si les funciona, no hay dolor que resolver |
| Directivos que NO salen al mercado (solo oficina) | Sin captura no hay qué estructurar |
| Mercados donde WhatsApp no es dominante (USA, Japón, China) | El canal no aplica — el producto es WhatsApp-first |
| Empresas que solo necesitan datos de panel (Nielsen/Kantar) | Field Genius es observación directa, no datos estadísticos de mercado |
| Directivos que ya tienen un asistente personal que organiza todo | El asistente humano ya resuelve el problema (pero no escala) |

### Competencia por segmento

**Para Directivos: NO HAY competencia directa**

| "Competidor" | Por qué no compite realmente |
|---|---|
| Repsly / GoSpotCheck | Diseñados para 50+ promotoras. Annual commitment. Un director nunca los evaluaría para sí mismo. |
| Asistente personal | Funciona para 1 director. Pero no escala, tarda 1-2 días, y el asistente no estuvo en campo. |
| Notas en el celular | No se comparten, no se estructuran, no son buscables. |
| Fotos al grupo de WhatsApp | Se comparten pero sin contexto. El equipo no puede hacer nada útil con 20 fotos sueltas. |
| **No hacer nada** | **ESTE es el competidor real.** Y es muy fuerte — porque "no hacer nada" cuesta $0 y la gente ya está acostumbrada. |

**Para Equipos de campo: competencia directa pero con modelo diferente**

| Competidor | Modelo | Debilidad que Field Genius explota |
|---|---|---|
| Repsly | App nativa + annual commitment | $3,600+/user/año. Adoption rate ~50%. Overkill para equipos <20. |
| GoSpotCheck (Wiser) | App + image recognition | Mismo modelo enterprise. Solo imagen, no audio. |
| VisitBasis | App nativa | Misma fricción que toda app de formularios. |
| Google Forms | Formulario web | 0 inteligencia, 0 estructura automática, misma no-adopción. |

### La ventaja competitiva REAL

No es la IA. No es la tecnología. Es el **modelo de engagement**:

| Dimensión | Repsly/GoSpotCheck | Field Genius |
|---|---|---|
| Canal | App nativa (nueva instalación) | WhatsApp (ya instalado en 100% de los celulares en LatAm) |
| Commitment | 12-month annual, upfront payment | Pay-per-session o mensual sin compromiso |
| Onboarding | 2-4 semanas, training presencial | "Manda tus fotos a este número" — 5 minutos |
| Adoption rate | 40-60% (fuente: churn de field apps) | ~90% proyectado (no cambia comportamiento) |
| Target company size | Enterprise (50+ field reps) | Desde 1 directivo hasta 100 promotoras |
| Setup de nuevo cliente | Semanas de configuración | 1 JSON schema + seed en DB = 1 hora |

**Deliverable:** Positioning statement + competitive map.

---

## Execution Timeline

| Semana | Qué hacer | Output | Decisión que informa |
|---|---|---|---|
| **1** | Steps 1-3: Problem frame + JTBD + Value assessment | Hipótesis documentadas | ¿Estamos resolviendo el problema correcto? |
| **2** | Step 4: 5-8 entrevistas de validación | Transcripciones + síntesis | ¿El dolor es real? ¿Pagarían? |
| **3** | Step 5: PMF assessment con datos de entrevistas | Nivel de PMF + evidencia | ¿Seguimos, pivotamos, o paramos? |
| **3** | Step 6: Positioning (si PMF >= Early signals) | Positioning statement | ¿Para quién es y para quién no? |
| **4+** | Si PMF = Early signals → Piloto 4 semanas con Argos | Retention data + usage metrics | ¿Invertir en calidad? |

### Decision Gate (Semana 3)

```
IF PMF = Pre-fit:
  → STOP feature development
  → Reformular problema o pivotar (ej: enfocarse SOLO en gerentes, no ejecutivos)
  → No ejecutar ux_ai_quality_data_plan.md

IF PMF = Early signals:
  → Piloto 4 semanas con 3-5 ejecutivos Argos
  → Ejecutar SOLO Fases 1-3 de ux_ai_quality_data_plan.md (assessment + test sets)
  → No invertir en monitoring ni dashboards todavía

IF PMF = Strong signals:
  → Ejecutar ux_ai_quality_data_plan.md completo
  → Definir pricing
  → Preparar onboarding para segundo cliente (Eficacia)

IF PMF = Confirmed fit:
  → Escalar: multi-tenant, pricing, equipo de ventas
  → product-strategy skills: roadmap, portfolio, competitive positioning
```

---

## Cómo se conecta con el plan de UX/AI/Data

```
pmf_evaluation_plan.md (ESTE PLAN)
  ↓
  Decision Gate (Semana 3)
  ↓
  IF PMF >= Early signals
  ↓
ux_ai_quality_data_plan.md (plan existente)
  Fase 1: Assess Experience Quality
  Fase 2: Usability Test Design
  Fase 3: AI Pipeline Evaluation
  ...etc
```

El plan de UX/AI/Data asume que el producto resuelve un problema real.
Este plan valida esa asunción PRIMERO.

**Si PMF = Pre-fit, el plan de UX/AI/Data se cancela o se reformula.**

---

## Información que ya tenemos vs lo que falta

| Lo que sabemos | Fuente | Confianza |
|---|---|---|
| Ejecutivos de campo no llenan formularios bien | Conversaciones con Argos | Anecdótica |
| WhatsApp es el canal natural en LatAm | Observación general | Alta |
| El pipeline técnico funciona end-to-end | Simulaciones (Sprint 1-4) | Alta (técnica) |
| Argos tiene ejecutivos que visitan ferreterías | Conversaciones | Media |
| Eficacia tiene impulsadoras en supermercados | Conversaciones | Media |

| Lo que NO sabemos | Cómo averiguarlo | Prioridad |
|---|---|---|
| ¿Los ejecutivos realmente mandarían fotos todos los días? | Piloto real | CRITICA |
| ¿Los gerentes usarían los datos para tomar decisiones? | Entrevista + piloto | CRITICA |
| ¿El director pagaría? ¿Cuánto? | Entrevista con director | CRITICA |
| ¿La calidad de extracción es suficiente para decisiones reales? | Golden test set (Phase 3 del otro plan) | ALTA |
| ¿Funciona igual en FMCG que en construcción? | Entrevistas Eficacia | MEDIA |
| ¿El modelo WhatsApp-only escala a 100 ejecutivos? | Stress test (no urgente) | BAJA |

---

## Rules

1. **No más features hasta validar PMF** — El producto tiene suficiente funcionalidad para un piloto.
2. **Entrevistar antes de construir** — Cada entrevista vale más que 100 líneas de código ahora.
3. **Buscar desconfirmación** — No preguntar "¿te gusta?". Preguntar "¿qué no te gusta?" y "¿por qué no lo usarías?"
4. **Distinguir cortesía de demanda** — "Qué interesante" ≠ "¿Cuándo puedo probarlo?"
5. **El director paga, el ejecutivo usa** — Ambos deben estar convencidos.
6. **Pre-fit no es fracaso** — Es información. Pivotar temprano es más barato que escalar algo que nadie quiere.
7. **Un piloto real > 100 entrevistas** — Pero las entrevistas deciden SI hacemos el piloto.
