-- 016: Per-client WhatsApp number — each implementation gets its own Twilio number
-- Run in Supabase SQL Editor

-- 1. Add whatsapp_number column to implementations
ALTER TABLE implementations
  ADD COLUMN IF NOT EXISTS whatsapp_number text;

-- 2. Set Telecable's number
UPDATE implementations
  SET whatsapp_number = 'whatsapp:+17792284312'
  WHERE id = 'telecable';

-- 3. Set laundry_care to the same number for now (default/demo)
UPDATE implementations
  SET whatsapp_number = 'whatsapp:+17792284312'
  WHERE id = 'laundry_care';

-- 4. Verify
SELECT id, name, whatsapp_number, status FROM implementations ORDER BY id;
