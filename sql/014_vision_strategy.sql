-- 014: Add vision_strategy column — tiered (Haiku→Sonnet) as default for all
-- Run in Supabase SQL Editor

-- 1. Add vision_strategy column with tiered as default
ALTER TABLE implementations
  ADD COLUMN IF NOT EXISTS vision_strategy text NOT NULL DEFAULT 'tiered';

-- 2. Add CHECK constraint
ALTER TABLE implementations
  DROP CONSTRAINT IF EXISTS implementations_vision_strategy_check;
ALTER TABLE implementations
  ADD CONSTRAINT implementations_vision_strategy_check
  CHECK (vision_strategy IN ('sonnet_only', 'tiered'));

-- 3. Set ALL existing implementations to tiered
UPDATE implementations SET vision_strategy = 'tiered';

-- 4. Verify
SELECT id, name, vision_strategy, status FROM implementations ORDER BY id;
