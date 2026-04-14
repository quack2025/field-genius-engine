-- 034: Add missing pending_contact_request_at column on users
--
-- Fixes a warning seen in production logs:
--   reset_user_fields_failed: "Could not find the 'pending_contact_request_at'
--   column of 'users' in the schema cache"
--
-- The column was originally declared in sql/031_demo_leads.sql but the ALTER
-- statement didn't get applied to the live database (likely only part of the
-- migration file was executed at the time). This file re-adds it idempotently
-- and forces a PostgREST schema reload.

BEGIN;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS pending_contact_request_at timestamptz;

NOTIFY pgrst, 'reload schema';

-- Verify all three pending flags are now in place
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'users'
  AND column_name IN (
    'pending_poc_selection_at',
    'pending_location_request_at',
    'pending_contact_request_at'
  )
ORDER BY column_name;

COMMIT;
