-- 025: UX improvements to demo onboarding copy
-- Based on UX research critique — clearer value prop, persona-specific instructions,
-- expectation setting, and preview of output.

BEGIN;

-- 1. Rename laundry_care for demo clarity
UPDATE implementations
SET name = 'Demo Retail CPG'
WHERE id = 'laundry_care';

-- 2. Update laundry_care (Demo Retail CPG) onboarding copy
UPDATE implementations
SET onboarding_config = jsonb_build_object(
    'welcome_message',
    E'Hola! Soy *Radar* de Xponencial 🎯\n\n' ||
    E'Convertimos fotos de campo (góndolas, exhibiciones, competencia) en reportes estratégicos con inteligencia artificial — en segundos, sin formularios.\n\n' ||
    E'Responde:\n' ||
    E'- *retail* para ver el demo de Trade Marketing / CPG\n' ||
    E'- *telecom* para ver el demo de Inteligencia Competitiva Telecom\n\n' ||
    E'Más info: https://xponencial.net',

    'post_switch_message',
    E'¡Perfecto! Empezamos con el *Demo Retail / CPG* 📸\n\n' ||
    E'Estás por ver cómo funciona Radar para equipos de *trade marketing y mercadería* que hacen visitas a puntos de venta.\n\n' ||
    E'📍 *Escenario:* Sos una persona de mercadeo o trade marketing visitando un supermercado, farmacia o punto de venta. Querés capturar rápido el estado del anaquel sin llenar formularios.\n\n' ||
    E'Tomá o enviá una foto de:\n' ||
    E'• Una góndola de supermercado o hipermercado\n' ||
    E'• Un anaquel de farmacia o droguería\n' ||
    E'• Exhibición con precios y promociones\n' ||
    E'• Punto de venta de tu categoría o la competencia\n\n' ||
    E'En ~15-20 segundos te devuelvo un análisis con:\n' ||
    E'✓ Marcas identificadas y share of shelf\n' ||
    E'✓ Precios y promociones visibles\n' ||
    E'✓ Estado del anaquel (agotados, desorden)\n' ||
    E'✓ Oportunidades de ejecución en punto\n\n' ||
    E'Cuando estés listo, enviame la foto 👇',

    'first_photo_hint',
    E'Recibí tu foto 📸\n\nAnalizando con múltiples modelos de inteligencia artificial... esto tarda ~15-20 segundos. Ya vuelvo 🔍',

    'rejection_message',
    E'No tienes acceso a este servicio. Contacta al administrador.',

    'require_terms', false,
    'welcome_content_sid', COALESCE(onboarding_config->>'welcome_content_sid', '')
)
WHERE id = 'laundry_care';

-- 3. Update demo_telecom onboarding copy
UPDATE implementations
SET onboarding_config = jsonb_build_object(
    'welcome_message',
    E'Demo Telecom de Radar Xponencial 📡\n\n' ||
    E'Inteligencia competitiva para operadoras de telecomunicaciones basada en lo que ves en la calle.',

    'post_switch_message',
    E'¡Perfecto! Empezamos con el *Demo Telecom* 📡\n\n' ||
    E'Estás por ver cómo funciona Radar para *ejecutivos de telecomunicaciones* que capturan inteligencia de calle mientras están en ruta — todo lo que ven de la competencia sin necesidad de reportes formales.\n\n' ||
    E'📍 *Escenario:* Sos un ejecutivo o analista de una operadora telecom. Mientras manejás o caminás por la ciudad, ves publicidad, promociones, POP de la competencia. Sacás una foto rápida y listo.\n\n' ||
    E'Tomá o enviá una foto de:\n' ||
    E'• Publicidad de competidores (Claro, Movistar, Liberty, Tigo, etc.)\n' ||
    E'• Promociones en calle, vallas, banners\n' ||
    E'• Material POP en fachadas\n' ||
    E'• Puntos de venta o kioscos de otras operadoras\n' ||
    E'• Ofertas publicadas en puntos físicos\n\n' ||
    E'En ~15-20 segundos te devuelvo un análisis con:\n' ||
    E'✓ Competidor identificado y su oferta\n' ||
    E'✓ Precios y condiciones promocionales detectadas\n' ||
    E'✓ Amenazas competitivas relevantes\n' ||
    E'✓ Insights de posicionamiento de marca\n\n' ||
    E'Cuando estés listo, enviame la foto 👇',

    'first_photo_hint',
    E'Recibí tu foto 📸\n\nAnalizando con múltiples modelos de inteligencia artificial... esto tarda ~15-20 segundos. Ya vuelvo 🔍',

    'rejection_message',
    E'Servicio no disponible. Contacta a hola@xponencial.net',

    'require_terms', false
)
WHERE id = 'demo_telecom';

COMMIT;

-- Verify
SELECT id, name,
       onboarding_config->>'welcome_message' as welcome,
       onboarding_config->>'post_switch_message' as post_switch
FROM implementations
WHERE id IN ('laundry_care', 'demo_telecom')
ORDER BY id;
