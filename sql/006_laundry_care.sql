-- 006: Laundry Care demo implementation with 3 analysis frameworks
-- Run in Supabase SQL Editor

-- 1. Create implementation
INSERT INTO implementations (id, name, industry, country, language, primary_color, status, vision_system_prompt, segmentation_prompt_template, trigger_words, analysis_framework)
VALUES (
  'laundry_care',
  'Cuidado de la Ropa',
  'CPG',
  'CO',
  'es',
  '#1E3A5F',
  'active',
  'Eres un experto en trade marketing y retail de productos de cuidado de la ropa (detergentes, suavizantes, quitamanchas, blanqueadores, etc).

Al analizar cada imagen de punto de venta, identifica y describe con precision:

1. PRODUCTOS VISIBLES: Marca, submarca, formato (polvo, liquido, pods, barra), tamano/presentacion, precio visible
2. SHARE OF SHELF: Estimacion del espacio que ocupa cada marca en la gondola (% aproximado)
3. POSICION EN GONDOLA: Nivel (ojos, manos, piso), ubicacion (punta, centro), facing
4. PROMOCIONES: Descuentos, ofertas, packs especiales, material POP, comunicacion en gondola
5. ESTADO DEL ANAQUEL: Agotados visibles (huecos), productos mal ubicados, desorden, suciedad
6. INNOVACION: Productos nuevos, formatos diferentes, tendencias (eco, concentrado, premium, refill)
7. EXHIBICIONES ESPECIALES: Cabeceras, islas, cross-merchandising (ej: detergente + suavizante juntos)
8. COMPETENCIA: Todas las marcas visibles y su posicionamiento relativo
9. COMUNICACION: Mensajes en packaging, claims (biodegradable, hipoalergenico, rinde mas), idioma

Se muy especifico con marcas y precios. Si un precio no es legible, indicalo. Si una marca no es reconocible, describela.',
  NULL,
  '["reporte","generar","listo","fin","report","done"]'::jsonb,
  '{
    "frameworks": {
      "tactical": {
        "id": "tactical",
        "name": "Reporte Tactico de Ejecucion",
        "description": "Revision de ejecucion en punto de venta: agotados, precios, promociones, share of shelf, cumplimiento",
        "model": "claude-sonnet-4-20250514",
        "system_prompt": "Eres un auditor senior de ejecucion en punto de venta para la categoria de cuidado de la ropa. Tu trabajo es evaluar la ejecucion comercial a partir de fotos, audios y notas de campo capturadas por impulsadoras.",
        "sections": [
          {
            "id": "availability",
            "label": "Disponibilidad y Agotados",
            "prompt": "Analiza la disponibilidad de productos en la gondola. Identifica:\n- Huecos visibles (agotados) y estima que marca/producto falta basandote en el espacio\n- Productos con stock bajo (1-2 unidades visibles)\n- Categorias completas que estan ausentes\n- Ratio estimado de disponibilidad (productos presentes / espacios totales)\nSe especifico: nombra marcas y formatos."
          },
          {
            "id": "pricing",
            "label": "Precios y Competitividad",
            "prompt": "Analiza los precios visibles en la gondola:\n- Lista todos los precios que puedas leer (marca, formato, precio)\n- Compara precio por ml/gr entre marcas cuando sea posible\n- Identifica el producto mas barato y mas caro por subcategoria (detergente liquido, polvo, suavizante)\n- Detecta precios promocionales vs regulares\n- Senala si hay inconsistencias (precio diferente en etiqueta vs anaquel)"
          },
          {
            "id": "promotions",
            "label": "Promociones y Material POP",
            "prompt": "Evalua la actividad promocional visible:\n- Promociones activas (descuento %, 2x1, pack, gratis X)\n- Material POP presente (habladores, cenefas, stoppers, banderines)\n- Exhibiciones especiales (cabeceras, islas, floor displays)\n- Cross-merchandising (detergente + suavizante, combos)\n- Calidad de la comunicacion promocional (es clara? es atractiva?)\n- Que marcas tienen mas actividad promocional vs cuales no tienen nada"
          },
          {
            "id": "shelf_share",
            "label": "Share of Shelf y Planograma",
            "prompt": "Evalua la distribucion del espacio en gondola:\n- Estimacion de share of shelf por marca (% del espacio total)\n- Posicion en gondola por marca (nivel de ojos/manos/piso)\n- Numero de facings por marca principal\n- Cumplimiento aparente de planograma (hay logica en la organizacion?)\n- Marcas con sobre-espacio vs sub-espacio relativo a su importancia\n- Bloqueo de marca (productos de la misma marca juntos) vs mezclado"
          },
          {
            "id": "execution_score",
            "label": "Score de Ejecucion y Acciones Inmediatas",
            "prompt": "Genera un score de ejecucion del 1 al 10 para este punto de venta en la categoria de cuidado de ropa, evaluando:\n- Disponibilidad (peso 30%)\n- Precio correcto y visible (peso 20%)\n- Promociones activas (peso 20%)\n- Orden y limpieza del anaquel (peso 15%)\n- Material POP (peso 15%)\n\nLuego lista las TOP 5 acciones inmediatas que deberia tomar el equipo de campo manana mismo, ordenadas por impacto."
          }
        ]
      },
      "strategic": {
        "id": "strategic",
        "name": "Analisis Estrategico (Pentagono de Babson)",
        "description": "Vision estrategica del canal usando el Pentagono de Babson College: Customer, Value Proposition, Revenue, Delivery, Ecosystem",
        "model": "claude-sonnet-4-20250514",
        "system_prompt": "Eres un consultor senior de estrategia de retail y shopper marketing especializado en la categoria de cuidado de la ropa. Aplicas el marco del Pentagono de Babson College para analizar puntos de venta.",
        "sections": [
          {
            "id": "customer",
            "label": "Shopper (Customer)",
            "prompt": "Identifica los segmentos de shopper que este punto de venta esta disenado para atender en la categoria de cuidado de ropa. Para cada segmento describe:\n- Perfil y mision de compra (reposicion, oferta, premium, conveniencia)\n- Evidencia visible en las fotos (que productos/precios/formatos lo sugieren)\n- Tamano de la canasta probable\n- Sensibilidad al precio vs calidad\nBusca al menos 3 segmentos diferenciados."
          },
          {
            "id": "value_proposition",
            "label": "Propuesta de Valor del Canal",
            "prompt": "Sintetiza la propuesta de valor que este punto de venta ofrece para la categoria de cuidado de ropa:\n- A nivel funcional: amplitud de surtido, rango de precios, formatos disponibles\n- A nivel emocional: experiencia de compra, confianza, descubrimiento\n- A nivel aspiracional: marcas premium presentes, innovacion visible\nEvalua si la propuesta esta claramente articulada o es implicita. Compara con lo que un shopper podria encontrar en otros canales (tienda de barrio, hard discount, e-commerce)."
          },
          {
            "id": "revenue_model",
            "label": "Modelo de Captura de Valor",
            "prompt": "Analiza como el retailer captura valor en esta categoria:\n- Motor de trafico: productos gancho con precio agresivo\n- Motor de margen: productos premium o nichos con mayor rentabilidad\n- Promociones estructuradas: hay logica en las ofertas o son aleatorias?\n- Cross-selling: se fomenta la compra de detergente + suavizante + quitamanchas?\n- Private label: hay marca propia del retailer? que espacio tiene?\nIdentifica la ecuacion economica implicita de la categoria para el retailer."
          },
          {
            "id": "delivery",
            "label": "Arquitectura Comercial",
            "prompt": "Evalua la arquitectura comercial de la categoria en este punto de venta:\n- Layout: como esta organizada la gondola (por marca, por formato, por precio, por subcategoria)\n- Navegacion: es facil encontrar lo que buscas? hay senalizacion?\n- Merchandising: productos bien facing, limpieza, iluminacion\n- Flujo del shopper: donde empieza y termina el recorrido de la categoria\n- Puntos calientes vs frios: que zona tiene mas visibilidad\nIdentifica fortalezas y debilidades operativas."
          },
          {
            "id": "ecosystem",
            "label": "Ecosistema de Marcas",
            "prompt": "Mapea el ecosistema completo de marcas presentes en la categoria:\n- Lideres: marcas con mayor espacio y presencia (Ariel, Fab, etc)\n- Retadores: marcas con menor espacio pero posicionamiento agresivo\n- Nicho: marcas especializadas (eco, hipoalergenico, premium)\n- Private label: marca del retailer\n- Nuevos entrantes: productos que parecen ser nuevos o recientes\nPara cada grupo, evalua que aporta al ecosistema (trafico, margen, innovacion, credibilidad). Identifica dependencias criticas y oportunidades de disrupcion."
          },
          {
            "id": "gold_insight",
            "label": "Gold Insight Estrategico",
            "prompt": "Genera un Gold Insight estrategico:\n- Cual es el modelo competitivo real de la categoria de cuidado de ropa en este canal?\n- Con quien compite realmente este canal por el shopper de detergentes? (tiendas de barrio? hard discount? e-commerce?)\n- Que transicion estrategica esta ocurriendo en la categoria? (commoditizacion? premiumizacion? fragmentacion?)\n- Formula una hipotesis estrategica en el estilo de Babson\n- Lista las 3 oportunidades estrategicas mas importantes con acciones concretas"
          }
        ]
      },
      "innovation": {
        "id": "innovation",
        "name": "Reporte de Oportunidades de Innovacion",
        "description": "Identificacion de gaps de portafolio, tendencias emergentes, oportunidades de formato, packaging y comunicacion",
        "model": "claude-sonnet-4-20250514",
        "system_prompt": "Eres un director de innovacion de una empresa de CPG especializada en cuidado de la ropa. Tu trabajo es identificar oportunidades de innovacion a partir de la observacion directa del punto de venta. Piensas en terminos de jobs-to-be-done, tendencias de consumo y whitespace de mercado.",
        "sections": [
          {
            "id": "portfolio_gaps",
            "label": "Gaps de Portafolio",
            "prompt": "Analiza la gondola e identifica gaps de portafolio — productos o formatos que NO estan presentes pero que el shopper podria necesitar:\n- Formatos faltantes (pods/capsulas si solo hay liquido y polvo, refill si solo hay envase completo, monodosis para viajeros)\n- Tamanos faltantes (entre el mas pequeno y el mas grande, hay saltos?)\n- Subcategorias ausentes (detergente para ropa oscura, para deportiva, para bebe, para alergicos)\n- Fragancias o variantes que se ven en otras categorias pero no aqui\n- Combos o kits que no existen pero tendrian sentido\nPara cada gap, estima el tamano de la oportunidad (nicho vs masivo)."
          },
          {
            "id": "trends",
            "label": "Tendencias Visibles e Invisibles",
            "prompt": "Identifica tendencias de consumo visibles en la gondola y tendencias AUSENTES que deberian estar:\n\nVISIBLES (ya hay productos que las atienden):\n- Eco/sustentable (biodegradable, envase reciclado, refill)\n- Concentrado (rinde mas, menos plastico)\n- Premium (fragancias sofisticadas, formulas especiales)\n- Conveniencia (pods, sheets, monodosis)\n\nINVISIBLES (tendencia global que NO se refleja aun):\n- Zero waste / solid detergent bars\n- Personalizacion (detergente por tipo de tela)\n- Subscription/refill model\n- Clean label (sin fosfatos, sin colorantes)\n- Tech-enabled (QR con instrucciones, app companion)\n\nPara cada tendencia, evalua: madurez en este mercado, barreras de adopcion, tamaño de oportunidad."
          },
          {
            "id": "packaging_comms",
            "label": "Oportunidades de Packaging y Comunicacion",
            "prompt": "Evalua el packaging y la comunicacion en gondola:\n- Claims dominantes: que dicen los productos? (rinde mas, quita manchas, protege colores)\n- Claims ausentes: que NO dice nadie que podria ser diferenciador?\n- Packaging funcional: hay innovacion en como se abre, se dosifica, se almacena?\n- Legibilidad: se puede leer la informacion a distancia de gondola?\n- Diferenciacion visual: que marca se distingue mas rapido? cual se pierde?\n- Storytelling: alguna marca cuenta una historia o todas son genericas?\nIdentifica 3 oportunidades concretas de innovacion en packaging o comunicacion."
          },
          {
            "id": "shopper_friction",
            "label": "Fricciones del Shopper",
            "prompt": "Ponte en los zapatos del shopper frente a esta gondola. Identifica fricciones:\n- Decision overload: hay demasiadas opciones que confunden?\n- Comparabilidad: es facil comparar precio/rendimiento entre marcas?\n- Informacion faltante: que necesita saber el shopper que no esta visible?\n- Accesibilidad: hay productos dificiles de alcanzar o ver?\n- Momento de verdad: que ve el shopper en los primeros 3 segundos?\nPara cada friccion, propone una innovacion que la resuelva (puede ser producto, packaging, exhibicion o digital)."
          },
          {
            "id": "innovation_roadmap",
            "label": "Roadmap de Innovacion",
            "prompt": "Basandote en todo el analisis anterior, genera un Innovation Roadmap priorizado:\n\nQUICK WINS (0-3 meses, bajo costo):\n- Cambios de packaging, comunicacion, exhibicion que no requieren producto nuevo\n\nSHORT TERM (3-6 meses, inversion moderada):\n- Extensiones de linea, nuevos formatos, variantes que usan tecnologia existente\n\nMEDIUM TERM (6-12 meses, inversion significativa):\n- Productos nuevos, formulas nuevas, modelos de negocio nuevos\n\nBIG BETS (12+ meses, transformacional):\n- Innovaciones disruptivas que cambiarian la categoria\n\nPara cada item incluye: descripcion, insight que lo soporta, riesgo, impacto estimado."
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

-- 2. Create visit types for laundry care
INSERT INTO visit_types (implementation_id, slug, display_name, description, schema_json, sheets_tab, sort_order)
VALUES
  ('laundry_care', 'supermarket_visit', 'Supermercado / Gran Superficie', 'Exito, Jumbo, Carulla, Olímpica, D1, Ara', '{}'::jsonb, 'Supermercados', 1),
  ('laundry_care', 'drugstore_visit', 'Droguería / Farmacia', 'Farmacias con sección de aseo del hogar', '{}'::jsonb, 'Droguerías', 2),
  ('laundry_care', 'tienda_barrio', 'Tienda de Barrio / TAT', 'Canal tradicional, tiendas pequeñas', '{}'::jsonb, 'TAT', 3),
  ('laundry_care', 'hard_discount', 'Hard Discount', 'D1, Ara, Ísimo, Justo & Bueno', '{}'::jsonb, 'Hard Discount', 4)
ON CONFLICT (implementation_id, slug) DO UPDATE SET
  display_name = EXCLUDED.display_name,
  description = EXCLUDED.description;

-- 3. Set laundry_care as default
UPDATE implementations SET status = 'inactive' WHERE id != 'laundry_care';

-- 4. Update all existing users to laundry_care
UPDATE users SET implementation = 'laundry_care', implementation_id = 'laundry_care';

-- 5. Update existing sessions to laundry_care
UPDATE sessions SET implementation = 'laundry_care';

COMMENT ON TABLE implementations IS 'Default implementation is now laundry_care for demo purposes';
