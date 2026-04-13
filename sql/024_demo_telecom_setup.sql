-- 024: Create demo_telecom + configure laundry_care / telecable for shared number
-- Run in Supabase SQL Editor after 023.
--
-- After this migration:
--   telecable     → +17792284312, whitelist,  fallback=laundry_care  (POC real)
--   laundry_care  → NULL,         open,       demo_keywords={retail,cpg,shopper}
--   demo_telecom  → NULL,         open,       demo_keywords={telecom,telco,demo}

BEGIN;

-- 1. Create demo_telecom by cloning telecable's framework + prompts
INSERT INTO implementations (
    id, name, industry, country, language, primary_color, status,
    vision_system_prompt, segmentation_prompt_template, trigger_words,
    analysis_framework, country_config, vision_strategy,
    access_mode, onboarding_config, demo_keywords, whatsapp_number
)
SELECT
    'demo_telecom',
    'Demo Telecom',
    'telecom',
    country,
    language,
    primary_color,
    'active',
    vision_system_prompt,
    segmentation_prompt_template,
    trigger_words,
    analysis_framework,
    country_config,
    'tiered',
    'open',
    jsonb_build_object(
        'welcome_message',
        'Bienvenido al *Demo Telecom* de Radar Xponencial.' || E'\n\n' ||
        'Envía fotos de:' || E'\n' ||
        '- Puntos de venta de competencia (Claro, Movistar, Liberty)' || E'\n' ||
        '- Instalaciones de clientes' || E'\n' ||
        '- Material POP y publicidad en calle' || E'\n\n' ||
        'Cuando termines, escribe *reporte* y te genero el análisis estratégico.' || E'\n\n' ||
        'Para volver al demo retail, envía *retail*.',
        'first_photo_hint',
        'Recibido ({count} archivo(s) hoy). Sigue enviando o escribe *reporte* cuando termines.',
        'rejection_message',
        'Servicio no disponible. Contacta a soporte@xponencial.net',
        'require_terms', false
    ),
    ARRAY['telecom','telco','demo']::text[],
    NULL
FROM implementations
WHERE id = 'telecable'
ON CONFLICT (id) DO UPDATE SET
    status = 'active',
    access_mode = 'open',
    demo_keywords = ARRAY['telecom','telco','demo']::text[],
    whatsapp_number = NULL,
    onboarding_config = EXCLUDED.onboarding_config;

-- 2. Copy visit_types from telecable → demo_telecom
INSERT INTO visit_types (
    implementation_id, slug, display_name, schema_json,
    sheets_tab, confidence_threshold, sort_order, is_active
)
SELECT
    'demo_telecom', slug, display_name, schema_json,
    sheets_tab, confidence_threshold, sort_order, is_active
FROM visit_types
WHERE implementation_id = 'telecable'
ON CONFLICT DO NOTHING;

-- 3. Configure laundry_care as demo retail primary (no number, demo keywords, updated welcome)
UPDATE implementations
SET
    whatsapp_number = NULL,
    demo_keywords = ARRAY['retail','cpg','shopper']::text[],
    onboarding_config = jsonb_set(
        jsonb_set(
            COALESCE(onboarding_config, '{}'::jsonb),
            '{welcome_message}',
            to_jsonb(
                'Bienvenido a *Radar Xponencial*.' || E'\n\n' ||
                'Este número ofrece dos demos:' || E'\n' ||
                '- Envía *retail* para la demo CPG/Retail (anaquel, precios, promociones)' || E'\n' ||
                '- Envía *telecom* para la demo Telecable (competencia, cliente, cobertura)' || E'\n\n' ||
                'O envíame una foto directamente para comenzar con la demo retail.'
            )
        ),
        '{require_terms}',
        'false'::jsonb
    )
WHERE id = 'laundry_care';

-- 4. Telecable: keep number + whitelist, add fallback to laundry_care
UPDATE implementations
SET
    fallback_implementation = 'laundry_care',
    whatsapp_number = 'whatsapp:+17792284312'
WHERE id = 'telecable';

COMMIT;

-- Verify
SELECT id, name, whatsapp_number, access_mode, demo_keywords, fallback_implementation, status
FROM implementations
WHERE id IN ('telecable','laundry_care','demo_telecom')
ORDER BY id;
