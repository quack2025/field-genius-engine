-- 007: Telecable Costa Rica & Panama — 3C Intelligence Platform
-- Run in Supabase SQL Editor

-- 1. Create Telecable implementation with 3C analysis frameworks
INSERT INTO implementations (id, name, industry, country, language, primary_color, status, vision_system_prompt, segmentation_prompt_template, trigger_words, analysis_framework)
VALUES (
  'telecable',
  'IA | Telecable',
  'telecom',
  'CR',
  'es',
  '#FF6600',
  'active',
  'Eres un analista experto de campo en la industria de telecomunicaciones en Costa Rica y Panama. Tu trabajo es analizar imagenes capturadas por el equipo de campo de Telecable.

Al analizar cada imagen, identifica y describe con precision:

1. MATERIAL COMPETITIVO: Publicidad, promociones, material POP de competidores (Claro, Movistar, Liberty, Tigo, Kolbi/ICE). Incluye precios, planes, ofertas visibles.
2. PUNTOS DE ATENCION: Tiendas, kioscos, stands de competidores o propios. Evalua ubicacion, visibilidad, estado, afluencia aparente.
3. INFRAESTRUCTURA: Torres, antenas, cableado, cajas de distribucion visibles. Estado de la infraestructura.
4. COMUNICACION DE MARCA: Mensajes de Telecable y competidores visibles en el entorno. Vallas, banners, senalizacion, branding en vehiculos.
5. CONTEXTO DEL CLIENTE: Si hay interaccion con clientes visible, describe el contexto: tipo de zona (residencial, comercial, rural), nivel socioeconomico aparente, densidad poblacional.
6. PROMOCIONES Y PRECIOS: Todos los precios y ofertas legibles de cualquier operador. Compara cuando sea posible.
7. ESTADO DEL SERVICIO: Cualquier evidencia visual de calidad de servicio: tecnicos trabajando, cables desordenados, equipos danados.
8. SENALES DE MERCADO: Cualquier otro elemento relevante para inteligencia competitiva o de mercado.

Se muy especifico con nombres de competidores, precios y ubicaciones. Si algo no es legible, indicalo.',
  NULL,
  '["reporte","generar","listo","fin","report","done"]'::jsonb,
  '{
    "frameworks": {
      "competidor": {
        "id": "competidor",
        "name": "C1: Inteligencia Competitiva",
        "description": "Lectura estrategica del entorno competitivo: ofertas, comunicacion, canal y percepcion de Claro, Movistar, Liberty vs Telecable",
        "model": "claude-sonnet-4-20250514",
        "system_prompt": "Eres un analista senior de inteligencia competitiva en telecomunicaciones para Costa Rica y Panama. Analizas evidencia de campo (fotos de tiendas competidoras, notas de voz de ejecutivos, observaciones escritas) capturada por el equipo de Telecable para detectar movimientos de Claro, Movistar, Liberty, Kolbi/ICE y otros competidores. Tu analisis debe ser accionable para el equipo de marketing y estrategia de Telecable.",
        "sections": [
          {
            "id": "offers_pricing",
            "label": "Ofertas y Precios Competitivos",
            "prompt": "Analiza todas las ofertas y precios de competidores mencionados o visibles:\n- Planes de internet, TV y telefonia con precios especificos\n- Promociones activas (descuentos, meses gratis, instalacion gratis, combos)\n- Comparacion directa de precio/valor con Telecable cuando sea posible\n- Diferencias por zona geografica (hay zonas mas agresivas?)\n- Agresividad relativa: quien esta siendo mas agresivo y donde\nSe especifico: nombra operador, plan, precio, zona."
          },
          {
            "id": "communication_sales",
            "label": "Comunicacion y Argumentos de Venta",
            "prompt": "Identifica como se comunican los competidores en el campo:\n- Mensajes clave visibles en material POP, vallas, puntos de atencion\n- Argumentos de venta que usan los ejecutivos competidores (reportados en audios)\n- Claims principales: velocidad, precio, cobertura, servicio, tecnologia\n- Tono y estilo: agresivo, premium, economico, tecnologico\n- Que promesas estan haciendo que Telecable no hace (o viceversa)\nEvalua la efectividad percibida de la comunicacion competitiva."
          },
          {
            "id": "channel_strategy",
            "label": "Estrategia de Canal y Distribucion",
            "prompt": "Evalua la presencia fisica y estrategia de distribucion de los competidores:\n- Puntos de atencion: cantidad, ubicacion, calidad, afluencia\n- Presencia en retail (tiendas de electronica, centros comerciales, supermercados)\n- Equipos de venta en calle: hay vendedores puerta a puerta?\n- Alianzas de canal visibles (con retailers, constructoras, desarrolladores)\n- Cobertura territorial: donde tiene mas presencia cada competidor\nCompara la presencia de canal de Telecable vs competidores."
          },
          {
            "id": "comparative_perception",
            "label": "Percepcion Comparada de Marca",
            "prompt": "Basandote en lo que reporta el equipo de campo sobre conversaciones con clientes y prospectos:\n- Como percibe el mercado a Telecable vs cada competidor\n- Fortalezas percibidas de Telecable (que valoran los clientes)\n- Debilidades percibidas (que mencionan como razon para considerar cambiar)\n- Percepcion de relacion precio-valor por operador\n- Factores de decision: que pesa mas al elegir operador en cada zona\nSi no hay suficiente evidencia, indicalo en vez de inventar."
          },
          {
            "id": "alerts_trends",
            "label": "Alertas Tempranas y Tendencias",
            "prompt": "Genera un mapa de alertas competitivas:\n- ALERTA ROJA: Movimientos que requieren respuesta inmediata (nueva promo agresiva, expansion a zona clave)\n- ALERTA AMARILLA: Tendencias que hay que monitorear (cambio de comunicacion, nuevo punto de atencion)\n- OPORTUNIDAD: Debilidades competitivas que Telecable puede explotar\n- TENDENCIA: Patrones que se repiten en multiples reportes\n\nPara cada alerta incluye: que, donde, quien, evidencia, urgencia, accion recomendada."
          }
        ]
      },
      "cliente": {
        "id": "cliente",
        "name": "C2: Ciclo de Vida del Cliente",
        "description": "Comprension profunda del journey del cliente: momentos de verdad, senales de churn, oportunidades de expansion y necesidades no satisfechas",
        "model": "claude-sonnet-4-20250514",
        "system_prompt": "Eres un consultor experto en customer experience y gestion del ciclo de vida del cliente en telecomunicaciones. Analizas senales de campo capturadas por el equipo de Telecable (notas de voz despues de visitas, fotos de instalaciones, observaciones de ejecutivos) para anticipar churn, identificar oportunidades de expansion y mejorar la experiencia del cliente en Costa Rica y Panama.",
        "sections": [
          {
            "id": "moments_of_truth",
            "label": "Momentos de Verdad",
            "prompt": "Identifica los momentos criticos en el journey del cliente reportados por el equipo:\n- Experiencias POSITIVAS: que genera satisfaccion, lealtad, recomendacion\n- Experiencias NEGATIVAS: que genera frustracion, queja, comparacion con competidores\n- Momento de instalacion: como fue la experiencia (es el momento mas critico en telecom)\n- Momento de soporte: como se resolvio el problema, tiempo de respuesta\n- Momento de facturacion: percepciones sobre precio, cobros, claridad\nPara cada momento, evalua impacto en retencion (alto/medio/bajo)."
          },
          {
            "id": "churn_signals",
            "label": "Senales de Churn",
            "prompt": "Detecta senales tempranas de abandono en lo reportado por el equipo:\n- Clientes que mencionan estar comparando con otros operadores\n- Quejas recurrentes sobre velocidad, estabilidad, precio\n- Clientes que preguntan por penalidades de cancelacion\n- Insatisfaccion con el servicio tecnico o atencion al cliente\n- Zonas donde hay mas senales de riesgo\n- Perfil del cliente en riesgo: hogar/empresa, tiempo como cliente, servicio contratado\n\nPara cada senal, sugiere una accion preventiva de retencion."
          },
          {
            "id": "upsell_crosssell",
            "label": "Oportunidades de Upsell y Cross-sell",
            "prompt": "Identifica oportunidades de expansion de valor basadas en lo observado en campo:\n- Clientes que expresan necesidad de mas velocidad, mas canales, mejor WiFi\n- Hogares con multiples dispositivos que podrian beneficiarse de un upgrade\n- Clientes de un solo servicio que podrian tomar el bundle\n- Empresas pequenas con necesidades de conectividad empresarial\n- Momentos de mayor receptividad para ofertas de upgrade\nEstima el potencial de cada oportunidad (alto/medio/bajo)."
          },
          {
            "id": "unmet_needs",
            "label": "Necesidades No Satisfechas",
            "prompt": "Detecta gaps entre lo que el cliente necesita y lo que Telecable ofrece:\n- Servicios que los clientes piden y no existen en el portafolio\n- Funcionalidades especificas mencionadas (WiFi mesh, parental control, streaming bundles)\n- Expectativas de servicio que no se cumplen (tiempo de instalacion, horario de atencion)\n- Necesidades por segmento: que pide el hogar vs la empresa vs el gamer\nPara cada necesidad, evalua: frecuencia (cuantos lo mencionan), viabilidad, impacto en retencion."
          },
          {
            "id": "segment_patterns",
            "label": "Patrones por Segmento y Zona",
            "prompt": "Identifica diferencias significativas entre segmentos y zonas:\n- Hogar vs Empresa: necesidades, satisfaccion, riesgo de churn\n- Por zona geografica: donde hay mayor satisfaccion vs mayor riesgo\n- Por antiguedad: clientes nuevos vs veteranos, que cambia\n- Por servicio: solo internet vs bundle completo\n- Patrones emergentes: hay un perfil de cliente que esta creciendo o disminuyendo?\n\nGenera un mapa de prioridades: que segmento/zona necesita atencion inmediata."
          }
        ]
      },
      "comunicacion": {
        "id": "comunicacion",
        "name": "C3: Efectividad de Comunicacion",
        "description": "Diagnostico de como percibe el mercado los mensajes de Telecable vs competencia, efectividad de campanas y oportunidades de ajuste",
        "model": "claude-sonnet-4-20250514",
        "system_prompt": "Eres un estratega senior de marca y comunicaciones especializado en telecomunicaciones. Evaluas como los mensajes de Telecable resuenan en el mercado real de Costa Rica y Panama — no en focus groups controlados, sino en el campo, en el momento de contacto real con el cliente. Tu analisis debe ser accionable para el equipo de marketing y comunicaciones.",
        "sections": [
          {
            "id": "campaign_recall",
            "label": "Recordacion y Percepcion de Campanas",
            "prompt": "Basandote en lo reportado por el equipo de campo:\n- Que campanas o mensajes de Telecable mencionan los clientes espontaneamente?\n- Hay recordacion de campanas recientes? cuales?\n- Que emociones o asociaciones generan los mensajes de Telecable?\n- Campanas de competidores que los clientes recuerdan mas que las de Telecable\n- Diferencias de recordacion por zona o segmento\nSi no hay suficiente evidencia sobre recordacion, indicalo claramente."
          },
          {
            "id": "message_effectiveness",
            "label": "Efectividad de Mensajes Clave",
            "prompt": "Evalua si los mensajes clave de Telecable estan funcionando:\n- Propuesta de valor principal: la entiende el cliente? la valora?\n- Diferenciadores comunicados: el cliente percibe que Telecable es diferente? en que?\n- Promesas vs realidad: hay gaps entre lo que Telecable comunica y lo que el cliente experimenta?\n- Mensajes que confunden o no resuenan\n- Mensajes que SI funcionan: que esta generando traccion\nPara cada mensaje evaluado, califica: claridad (1-5), relevancia (1-5), diferenciacion (1-5)."
          },
          {
            "id": "vs_competition",
            "label": "Comunicacion Telecable vs Competencia",
            "prompt": "Compara la comunicacion de Telecable con la de competidores en el campo:\n- Quien tiene mayor presencia de marca visible en el territorio?\n- Que operador tiene el mensaje mas claro? mas atractivo? mas agresivo?\n- Share of voice en campo: proporcion de material visible por operador\n- Gaps de comunicacion: que dice la competencia que Telecable no dice\n- Ventajas comunicacionales de Telecable que no esta explotando\nGenera una matriz comparativa cuando haya suficiente evidencia."
          },
          {
            "id": "zone_perception",
            "label": "Percepcion de Marca por Zona",
            "prompt": "Identifica diferencias territoriales en como se percibe Telecable:\n- Zonas donde Telecable tiene mayor equity de marca\n- Zonas donde la competencia domina la percepcion\n- Factores locales que afectan la percepcion (calidad de servicio local, presencia de competidores)\n- Oportunidades de comunicacion localizada\n- Zonas criticas que necesitan atencion comunicacional inmediata\nSi no hay suficiente cobertura geografica en los datos, indicalo."
          },
          {
            "id": "recommendations",
            "label": "Recomendaciones de Ajuste",
            "prompt": "Genera recomendaciones accionables para el equipo de marketing:\n\nQUICK WINS (esta semana):\n- Ajustes de mensaje que se pueden hacer inmediatamente\n- Material POP que necesita actualizacion\n\nSHORT TERM (proximo mes):\n- Campanas que necesitan pivotear\n- Nuevos mensajes a probar\n- Canales a reforzar o abandonar\n\nESTRATEGICO (proximo trimestre):\n- Reposicionamiento necesario\n- Nuevas narrativas de marca\n- Inversion en comunicacion por zona\n\nPara cada recomendacion: que hacer, donde, por que, impacto esperado."
          }
        ]
      }
    }
  }'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  industry = EXCLUDED.industry,
  vision_system_prompt = EXCLUDED.vision_system_prompt,
  analysis_framework = EXCLUDED.analysis_framework,
  updated_at = now();

-- 2. Create visit types for Telecable
INSERT INTO visit_types (implementation_id, slug, display_name, description, schema_json, sheets_tab, sort_order)
VALUES
  ('telecable', 'customer_visit', 'Visita a Cliente', 'Evaluacion de satisfaccion, churn risk, oportunidades de upgrade', '{}'::jsonb, 'Clientes', 1),
  ('telecable', 'competitor_store', 'Auditoria de Competidor', 'Tienda o punto de atencion de ISP rival (Claro, Movistar, Liberty)', '{}'::jsonb, 'Competencia', 2),
  ('telecable', 'installation_visit', 'Visita de Instalacion', 'Seguimiento tecnico post-instalacion, calidad del servicio', '{}'::jsonb, 'Instalaciones', 3),
  ('telecable', 'support_visit', 'Visita de Soporte', 'Resolucion de problemas en terreno, escalacion', '{}'::jsonb, 'Soporte', 4),
  ('telecable', 'field_observation', 'Observacion de Campo', 'Observacion general: promo competencia, zona, cobertura, senal', '{}'::jsonb, 'Observaciones', 5)
ON CONFLICT (implementation_id, slug) DO UPDATE SET
  display_name = EXCLUDED.display_name,
  description = EXCLUDED.description;
