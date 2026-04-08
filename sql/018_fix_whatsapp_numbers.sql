-- 018: Fix WhatsApp number assignments
-- Sandbox number for demos, paid number for Telecable only

UPDATE implementations
  SET whatsapp_number = 'whatsapp:+14155238886'
  WHERE id = 'laundry_care';

UPDATE implementations
  SET whatsapp_number = 'whatsapp:+17792284312'
  WHERE id = 'telecable';

-- Verify
SELECT id, name, whatsapp_number, access_mode, status FROM implementations ORDER BY id;
