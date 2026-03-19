# Field Genius Engine — Escenarios Estrategicos para Clientes

> Documento de discusion interna. Objetivo: mapear las capacidades actuales del motor a escenarios de negocio concretos que se pueden vender.

---

## Lo que el motor hace hoy (Marzo 2026)

Field Genius convierte capturas no estructuradas (fotos, audio, video, ubicacion GPS) enviadas por WhatsApp en:

1. **Datos tabulares** — filas en Google Sheets con campos estructurados
2. **Analisis estrategico narrativo** — usando frameworks academicos (Pentagono de Babson)
3. **Resumen ejecutivo** — enviado al usuario por WhatsApp en tiempo real

Todo esto sin que el usuario cambie su comportamiento. Solo usa WhatsApp como siempre.

### Capacidades tecnicas actuales

| Capacidad | Estado | Costo por visita |
|-----------|--------|-----------------|
| Recepcion de fotos, audio, video | Produccion | $0 (Twilio) |
| Transcripcion de audio (Whisper) | Produccion | ~$0.006/min |
| Analisis de imagen (Claude Vision) | Produccion | ~$0.01/imagen |
| Segmentacion multi-visita (Sonnet) | Produccion | ~$0.03/sesion |
| Extraccion estructurada (Haiku) | Produccion | ~$0.005/visita |
| Analisis estrategico Babson (Sonnet) | Produccion | ~$0.10/visita |
| Pre-procesamiento en tiempo real | Produccion | Incluido arriba |
| Google Sheets automatico | Produccion | $0 |
| Ubicacion GPS | Produccion | $0 |
| Backoffice de administracion | Produccion | $0 |
| Consolidacion multi-visita | Backoffice (API lista) | ~$0.15/reporte |
| PDF de reporte | Deshabilitado temporalmente | — |
| Presentacion Gamma | Deshabilitado temporalmente | — |

**Costo total estimado por usuario/mes** (asumiendo 20 dias, 4 visitas/dia, 5 fotos + 1 audio por visita):
- Whisper: $2.40
- Vision: $4.00
- Segmentacion: $0.60
- Extraccion: $0.40
- Analisis Babson: $8.00
- **Total: ~$15.40/usuario/mes**

---

## Dos enfoques, dos mercados

El motor soporta dos modos fundamentales de analisis que apuntan a compradores diferentes:

### Enfoque 1: Revision Tactica de Canal (Trade Marketing / Operaciones)

**Comprador:** Director de Trade Marketing, Gerente de Canal, Jefe de Operaciones de Campo

**Problema que resuelve:** "Mis promotores visitan 200 tiendas al mes pero no tengo datos confiables de lo que pasa en el punto de venta."

**Output principal:** Datos estructurados → Dashboard operativo

| Dato | Como se captura | Ejemplo |
|------|----------------|---------|
| Precios propios y competencia | Foto de gondola → Vision | "CeraVe 250ml: $45,000. Cetaphil 250ml: $42,000" |
| Share of shelf / facing | Foto de categoria → Vision | "CeraVe: 35% de facing. Competencia: Cetaphil 25%, Bioderma 20%" |
| Cumplimiento de exhibicion | Foto de PDV → Vision | "Material POP presente: SI. Ubicacion: gondola principal" |
| Disponibilidad (out of stock) | Foto + audio → Vision + Whisper | "Producto X agotado hace 3 dias segun el tendero" |
| Precios de competencia | Foto de etiqueta → Vision | "Precio promo competidor: $39,900 (vs nuestro $45,000)" |
| Estado de activos | Foto de nevera/exhibidor → Vision | "Nevera marca propia: funcionando, 80% con producto nuestro" |
| Contacto del punto | Audio de conversacion → Whisper | "Don Carlos, satisfecho, pide mas producto sabor fresa" |

**Metricas que se pueden generar:**
- Indice de cumplimiento de exhibicion por zona
- Mapa de precios vs competencia por region
- Tasa de out-of-stock por SKU
- Indice de salud de activos en campo

**Industrias target:**
- CPG / FMCG (Eficacia, P&G, Unilever, Nestle)
- Bebidas (Coca-Cola, AB InBev, Postobon)
- Cementos y materiales (Argos, Corona)
- Farma OTC (Bayer, GSK)
- Cosmeticos (L'Oreal, Belcorp)

**Pricing sugerido:** Setup $2,000-5,000 + $49/usuario/mes (margen ~70%)

---

### Enfoque 2: Entendimiento Estrategico de Oportunidades (Consultoria / Innovacion)

**Comprador:** Director de Innovacion, VP de Estrategia, Director Comercial, Consultoras

**Problema que resuelve:** "Necesito entender que esta pasando en el mercado a nivel estrategico, no solo operativo. Quiero patrones, insights, hipotesis."

**Output principal:** Analisis narrativo estrategico (tipo el que hizo GPT con las fotos de Pasteur)

| Dimension del analisis | Que evalua | Ejemplo de insight |
|----------------------|-----------|-------------------|
| Cliente (Customer) | Segmentos de comprador, misiones de compra | "El PDV captura 4 misiones: conveniencia, reposicion, wellness, dermocosmética" |
| Propuesta de Valor | Posicionamiento implicito del PDV | "No es una farmacia — es un hub de bienestar urbano" |
| Modelo de Revenue | Motores de ingreso visibles | "Trafico (bebidas) + ticket incremental (wellness) + margen premium (dermo)" |
| Arquitectura (Delivery) | Layout, merchandising, flujo | "Zonificacion por mision de compra, no por categoria de producto" |
| Ecosistema (Partners) | Marcas presentes, rol de cada una | "CeraVe aporta credibilidad cientifica, Monster aporta trafico juvenil" |
| Gold Insight | Hipotesis estrategica central | "Farmacias Pasteur compite con tiendas fitness, no solo con otras farmacias" |

**El poder de la consolidacion multi-visita:**

Una visita genera un analisis interesante. 50 visitas generan inteligencia estrategica:

| Escala | Output |
|--------|--------|
| 1 visita | Analisis individual tipo "Retail Safari" |
| 10 visitas | Patrones de categoria (ej: "el wellness crece en 7 de 10 farmacias") |
| 50 visitas | Benchmarks internos ("el PDV de Laureles tiene 2x facing que Bello") |
| 200+ visitas | Estudio de mercado cuantitativo + cualitativo ("en cadena X, la dermocosmetica crece 30% vs hace 6 meses") |

**Casos de uso concretos:**

1. **Retail Safari digital** — Estudiantes MBA, equipos de innovacion, consultoras. Enviar fotos de PDV → recibir analisis Babson inmediato.

2. **Auditoria de categoria** — Fabricante quiere entender como se ve su categoria en 100 PDV del pais. Equipo de campo captura → consolidacion automatica → dashboard por zona/cadena.

3. **Inteligencia competitiva** — "Como esta Competidor X posicionandose en tiendas de barrio?" Campo captura 50 TAT → patrones de estrategia competitiva emergen.

4. **Due diligence retail** — Fondo de inversion evaluando adquirir cadena. Equipo visita 20 tiendas → reporte estrategico de salud del negocio.

5. **Innovacion de formato** — Cadena diseñando nuevo formato de tienda. Safari de 30 PDV referentes → benchmark de mejores practicas → recomendaciones.

**Industrias target:**
- Consultoras (McKinsey, BCG, Bain, firmas locales)
- Universidades / programas MBA
- Departamentos de innovacion en retail
- Fondos de inversion / PE
- Cadenas disenando nuevos formatos

**Pricing sugerido:** Setup $5,000-15,000 + $99-199/usuario/mes (margen ~75-80%, el valor percibido es mucho mayor)

---

## Combinacion: el producto mas poderoso

Lo interesante es que ambos enfoques **corren sobre los mismos datos**. Un equipo de campo puede capturar fotos que simultaneamente alimentan:

1. El dashboard operativo (precio, facing, OOS)
2. El analisis estrategico (posicionamiento, oportunidades)

Esto es unico. Ningun competidor ofrece ambos desde la misma captura.

```
MISMO SET DE FOTOS
        |
        ├──→ Fase 2 (Extraccion) → Datos tabulares → Dashboard operativo
        |                           precio, facing, OOS, competencia
        |
        └──→ Fase 3 (Analisis)  → Narrativa estrategica → Insights
                                   cliente, valor, revenue, delivery, ecosistema
```

---

## Escenarios de empaquetamiento

### Paquete Basico — "Field Data"
- Captura via WhatsApp
- Extraccion estructurada (datos tabulares)
- Google Sheets automatico
- Backoffice con media timeline
- **$49/usuario/mes + Setup $2,000**

### Paquete Pro — "Field Intelligence"
- Todo lo de Basico +
- Analisis estrategico por visita (Babson u otro framework)
- Pre-procesamiento en tiempo real
- Transcripciones y descripciones visibles en backoffice
- **$99/usuario/mes + Setup $5,000**

### Paquete Enterprise — "Field Strategy"
- Todo lo de Pro +
- Consolidacion multi-visita (reportes semanales/mensuales)
- Frameworks personalizados (no solo Babson — PEST, Porter, Jobs to Be Done)
- Dashboard de metricas operativas
- API para integracion con BI (Power BI, Tableau)
- Onboarding + configuracion de implementation custom
- **$199/usuario/mes + Setup $10,000-15,000**

---

## Diferenciadores vs competencia

| Competidor | Que hace | Nuestra ventaja |
|-----------|---------|----------------|
| GoSpotCheck / FORM | Formularios digitales + fotos | Nosotros no usamos formularios — captura natural via WhatsApp |
| Trax / Planorama | Image recognition automatizado | Nosotros no necesitamos training de SKU — vision generativa entiende cualquier gondola |
| Repsly | CRM de campo + formularios | Nosotros sumamos analisis estrategico — ellos solo datos operativos |
| SurveyMonkey / Qualtrics | Encuestas post-visita | Nosotros capturamos durante la visita, no despues |
| ChatGPT manual | El usuario sube fotos y pide analisis | Nosotros automatizamos el pipeline end-to-end con datos persistentes y consolidacion |

**Ventaja fundamental:** WhatsApp como canal = adopcion inmediata. No hay app que instalar, no hay formulario que llenar, no hay training que dar. El ejecutivo de campo usa la herramienta que ya tiene en la mano.

---

## Roadmap de capacidades (Q2 2026)

| Capacidad | Impacto | Esfuerzo | Prioridad |
|-----------|---------|----------|-----------|
| PDF de reporte por visita | Alto — entregable tangible | 1 dia | P0 |
| Consolidacion desde backoffice (UI) | Muy alto — desbloquea Enterprise | 3 dias | P0 |
| Dashboard de metricas operativas | Alto — diferenciador vs formularios | 5 dias | P1 |
| Frameworks adicionales (Porter, PEST) | Medio — mas versatilidad | 1 dia c/u | P1 |
| Alertas automaticas por WhatsApp | Alto — valor en tiempo real | 2 dias | P1 |
| Onboarding automatico por WhatsApp | Medio — reduce friccion | 1 dia | P2 |
| API REST para integracion BI | Alto — Enterprise | 3 dias | P2 |
| Multi-idioma (PT, EN) | Medio — expansion regional | 2 dias | P2 |
| Comparacion temporal (wave analysis) | Muy alto — tracking de tendencias | 3 dias | P2 |

---

## Metricas clave para el pitch

- **Tiempo de setup:** <1 hora (crear implementation, registrar usuarios, compartir Sheets)
- **Tiempo de adopcion:** 0 minutos (el usuario ya sabe usar WhatsApp)
- **Tiempo de primer reporte:** <5 minutos despues de trigger
- **Costo por visita completa (datos + analisis):** ~$0.20
- **Precio por visita (al cliente):** ~$1.25 (a $49/mes, 20 dias, 2 visitas/dia)
- **Margen bruto:** 73-84% dependiendo del paquete

---

## Preguntas para la discusion con socio

1. **Cual enfoque atacamos primero?** Tactico (mas volumen, ticket bajo) vs Estrategico (menos volumen, ticket alto)?

2. **Verticalizamos?** Un producto para CPG, otro para consultoras? O uno generico con frameworks intercambiables?

3. **Canal de venta?** Venta directa a directores de trade marketing? Partnership con consultoras? Canal academico (MBA programs)?

4. **Primer cliente piloto?** Eficacia ya esta conectado. Quien sigue?

5. **Pricing validation?** Hacer 5 entrevistas con potenciales compradores antes de fijar precios.

6. **Consolidacion como diferenciador clave?** El "Gold Insight" de una visita es interesante. El de 50 visitas es vendible como estudio de mercado.

---

*Ultima actualizacion: 2026-03-19*
*Basado en: implementacion Eficacia (CPG/retail), prueba con fotos Farmacias Pasteur, pipeline productivo con Phase 3 Babson*
