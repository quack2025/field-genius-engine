-- 027: Disable T&C requirement on telecable during POC phase
-- While the paid number is shared between POC + demos, we don't want random
-- demo visitors to get stuck in a terms-acceptance loop if cache/fallback
-- misroutes them. When Telecable gets their own dedicated number, re-enable
-- terms by updating onboarding_config.require_terms = true from backoffice.

BEGIN;

UPDATE implementations
SET onboarding_config = onboarding_config || '{"require_terms": false}'::jsonb
WHERE id = 'telecable';

COMMIT;

-- Verify
SELECT id, onboarding_config->>'require_terms' as require_terms,
       fallback_implementation
FROM implementations
WHERE id = 'telecable';
