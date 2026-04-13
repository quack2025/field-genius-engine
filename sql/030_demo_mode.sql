-- 030: Demo instant mode flag
-- Enables single-photo → single-report flow (no "reporte" trigger word).
-- Used by laundry_care and demo_telecom for commercial demos.

BEGIN;

UPDATE implementations
SET onboarding_config = onboarding_config || jsonb_build_object('demo_mode', true)
WHERE id IN ('laundry_care', 'demo_telecom');

-- Verify
SELECT id,
       onboarding_config->>'demo_mode' AS demo_mode,
       onboarding_config->>'post_switch_message' IS NOT NULL AS has_post_switch,
       onboarding_config->>'sample_report' IS NOT NULL AS has_sample
FROM implementations
WHERE id IN ('laundry_care', 'demo_telecom', 'telecable')
ORDER BY id;

COMMIT;
