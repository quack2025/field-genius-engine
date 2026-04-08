-- 017: Access control — whitelist mode per implementation
-- Run in Supabase SQL Editor

-- 1. Add access_mode column (open = anyone, whitelist = registered users only)
ALTER TABLE implementations
  ADD COLUMN IF NOT EXISTS access_mode text NOT NULL DEFAULT 'open';

ALTER TABLE implementations
  DROP CONSTRAINT IF EXISTS implementations_access_mode_check;
ALTER TABLE implementations
  ADD CONSTRAINT implementations_access_mode_check
  CHECK (access_mode IN ('open', 'whitelist'));

-- 2. Set Telecable to whitelist (enterprise = always whitelist)
UPDATE implementations SET access_mode = 'whitelist' WHERE id = 'telecable';

-- 3. Keep laundry_care open (demo mode)
UPDATE implementations SET access_mode = 'open' WHERE id = 'laundry_care';

-- 4. Verify
SELECT id, name, access_mode, whatsapp_number, status FROM implementations ORDER BY id;
