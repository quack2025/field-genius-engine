-- 033: Prevent duplicate sessions per (user_phone, date) + force PostgREST schema reload
--
-- Two fixes for the Sprint Demo-POC test loop:
--
-- 1. Under burst media loads (8 photos forwarded at once = 8 concurrent webhooks),
--    each webhook's get_or_create_session was creating its own session row because
--    there is no unique constraint. This caused files to be split across multiple
--    session rows and made the "generar" report see only a subset. Add a unique
--    constraint so INSERTs fail fast and the caller can retry with a SELECT.
--
-- 2. The users.pending_contact_request_at + pending_poc_selection_at +
--    pending_location_request_at columns were added in recent migrations (031/032),
--    but the PostgREST schema cache was not picking them up, causing updates to
--    throw "Could not find the column in the schema cache". Force a reload.

BEGIN;

-- ═══════════════════════════════════════════════════════════════
-- 1. Ensure no duplicates currently exist before adding constraint
-- ═══════════════════════════════════════════════════════════════
-- Keep the oldest session per (user_phone, date), delete duplicates.
-- Orphaned session_files are cascade-deleted via the FK.
WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY user_phone, date
               ORDER BY created_at ASC
           ) AS rn
    FROM sessions
)
DELETE FROM sessions
WHERE id IN (SELECT id FROM ranked WHERE rn > 1);

-- ═══════════════════════════════════════════════════════════════
-- 2. Add unique constraint on (user_phone, date)
-- ═══════════════════════════════════════════════════════════════
-- IF NOT EXISTS guard for idempotent reruns
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'sessions_user_phone_date_uniq'
    ) THEN
        ALTER TABLE sessions
          ADD CONSTRAINT sessions_user_phone_date_uniq UNIQUE (user_phone, date);
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════
-- 3. Force PostgREST to reload its schema cache
-- ═══════════════════════════════════════════════════════════════
-- Supabase's PostgREST instance caches the schema for performance. Newly added
-- columns sometimes aren't picked up until a reload signal is sent. This is
-- idempotent and safe to run repeatedly.
NOTIFY pgrst, 'reload schema';

-- ═══════════════════════════════════════════════════════════════
-- 4. Verification
-- ═══════════════════════════════════════════════════════════════
SELECT conname, contype
FROM pg_constraint
WHERE conrelid = 'sessions'::regclass
  AND conname = 'sessions_user_phone_date_uniq';

SELECT column_name
FROM information_schema.columns
WHERE table_name = 'users'
  AND column_name IN ('pending_poc_selection_at', 'pending_location_request_at', 'pending_contact_request_at')
ORDER BY column_name;

COMMIT;
