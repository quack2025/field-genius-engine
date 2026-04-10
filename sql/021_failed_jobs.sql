-- 021: Failed jobs table — dead letter queue with retry support
-- Run in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS failed_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id text NOT NULL,
    queue_name text DEFAULT 'preprocess',
    function_name text,
    args_json jsonb,
    error text,
    error_type text,
    retries integer DEFAULT 0,
    status text NOT NULL DEFAULT 'failed',  -- failed, retried, resolved
    created_at timestamptz DEFAULT now(),
    resolved_at timestamptz
);

ALTER TABLE failed_jobs DROP CONSTRAINT IF EXISTS failed_jobs_status_check;
ALTER TABLE failed_jobs ADD CONSTRAINT failed_jobs_status_check
  CHECK (status IN ('failed', 'retried', 'resolved'));

CREATE INDEX IF NOT EXISTS idx_failed_jobs_status ON failed_jobs(status);
CREATE INDEX IF NOT EXISTS idx_failed_jobs_created ON failed_jobs(created_at DESC);

-- RLS
ALTER TABLE failed_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY failed_jobs_select ON failed_jobs FOR SELECT USING (true);
CREATE POLICY failed_jobs_insert ON failed_jobs FOR INSERT WITH CHECK (true);
CREATE POLICY failed_jobs_update ON failed_jobs FOR UPDATE USING (true);

-- Verify
SELECT count(*) as existing_failed_jobs FROM failed_jobs;
