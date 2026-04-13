-- 028: Fix telecable welcome for POC phase + provide reset tools
-- Run in Supabase SQL Editor

BEGIN;

-- 1. Replace telecable welcome_message so it NO LONGER asks for "acepto"
--    (during POC, require_terms is false anyway — this just makes the text match)
UPDATE implementations
SET onboarding_config = onboarding_config || jsonb_build_object(
    'welcome_message',
    E'Hola! Soy *Radar* de Xponencial 🎯\n\n' ||
    E'Convertimos fotos de campo en reportes estratégicos con inteligencia artificial — en segundos, sin formularios.\n\n' ||
    E'Si estás viendo una demo:\n' ||
    E'- Envía *retail* para ver el demo de Trade Marketing / CPG\n' ||
    E'- Envía *telecom* para ver el demo de Inteligencia Competitiva\n\n' ||
    E'Si eres parte del equipo de Telecable, envía una foto directamente para comenzar tu análisis de campo.\n\n' ||
    E'Más info: https://xponencial.net',
    'require_terms', false,
    'terms_accepted_message', 'Perfecto. Ya puedes empezar a enviar fotos.',
    'terms_declined_message', 'Entendido. Si cambias de opinión, escríbenos de nuevo.'
)
WHERE id = 'telecable';

COMMIT;

-- ───────────────────────────────────────────────────────────────
-- RESET TOOLS — run manually if you get stuck in demo testing
-- ───────────────────────────────────────────────────────────────

-- Check your current user state (replace phone):
-- SELECT phone, name, implementation, accepted_terms FROM users WHERE phone LIKE '%6671%';

-- Delete your user row to force brand-new-visitor flow:
-- DELETE FROM users WHERE phone LIKE '%6671%';

-- Verify telecable's current config:
SELECT id, name, access_mode,
       onboarding_config->>'require_terms' as require_terms,
       onboarding_config->>'welcome_message' as welcome,
       fallback_implementation
FROM implementations
WHERE id = 'telecable';
