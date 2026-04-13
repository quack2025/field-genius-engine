-- 023: Add demo_keywords + fallback_implementation to implementations
-- Enables keyword-based demo switching and whitelist fallback routing.
-- Run in Supabase SQL Editor.

BEGIN;

ALTER TABLE implementations
  ADD COLUMN IF NOT EXISTS demo_keywords text[] NOT NULL DEFAULT '{}'::text[];

ALTER TABLE implementations
  ADD COLUMN IF NOT EXISTS fallback_implementation text REFERENCES implementations(id);

-- GIN index for keyword lookup (not used directly yet, but cheap and ready)
CREATE INDEX IF NOT EXISTS idx_impl_demo_keywords
  ON implementations USING GIN (demo_keywords);

COMMIT;

-- Verify
SELECT id, name, demo_keywords, fallback_implementation, access_mode, status
FROM implementations
ORDER BY id;
