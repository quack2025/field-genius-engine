-- 031: Demo leads capture + pending contact flag
-- Sprint Demo-2 — CTAs post-reporte
--
-- demo_leads: rows created when a demo visitor asks to be contacted.
-- users.pending_contact_request_at: set when user writes "contacto",
--   cleared when they reply with their contact info or after TTL.

BEGIN;

-- ═══════════════════════════════════════════════════════════════
-- 1. demo_leads table
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS demo_leads (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    phone           text NOT NULL,
    implementation  text,
    country         text,
    payload         text,
    source          text DEFAULT 'whatsapp_demo',
    status          text NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'contacted', 'resolved', 'spam')),
    notes           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    contacted_at    timestamptz
);

CREATE INDEX IF NOT EXISTS idx_demo_leads_phone ON demo_leads(phone);
CREATE INDEX IF NOT EXISTS idx_demo_leads_status_created ON demo_leads(status, created_at DESC);

-- ═══════════════════════════════════════════════════════════════
-- 2. users.pending_contact_request_at
-- ═══════════════════════════════════════════════════════════════
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS pending_contact_request_at timestamptz;

-- ═══════════════════════════════════════════════════════════════
-- 3. Verify
-- ═══════════════════════════════════════════════════════════════
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'demo_leads'
ORDER BY ordinal_position;

SELECT column_name
FROM information_schema.columns
WHERE table_name = 'users' AND column_name = 'pending_contact_request_at';

COMMIT;
