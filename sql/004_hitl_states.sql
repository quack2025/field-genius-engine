-- Field Genius Engine — HITL state extensions
-- Run this AFTER 003_alerts.sql in Supabase SQL Editor

-- 1. Add 'awaiting_confirmation' to sessions status CHECK constraint
ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_status_check;
ALTER TABLE sessions ADD CONSTRAINT sessions_status_check CHECK (
    status IN ('accumulating', 'segmenting', 'awaiting_confirmation', 'processing',
               'generating_outputs', 'completed', 'needs_clarification', 'failed')
);

-- 2. Confirmation tracking fields
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS confirmation_status text
    CHECK (confirmation_status IN ('confirmed', 'corrected', 'auto'));
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS confirmation_requested_at timestamptz;
