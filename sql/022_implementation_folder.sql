-- 022: Add folder column to implementations for organizing projects
-- Run in Supabase SQL Editor

ALTER TABLE implementations
  ADD COLUMN IF NOT EXISTS folder text;

-- Index for grouping queries
CREATE INDEX IF NOT EXISTS idx_implementations_folder ON implementations(folder);

-- Verify
SELECT id, name, folder, status FROM implementations ORDER BY folder NULLS LAST, name;
