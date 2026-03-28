-- 010: Usage tracking for billing and monitoring
-- Run in Supabase SQL Editor

-- Monthly usage aggregation per implementation
CREATE TABLE IF NOT EXISTS usage_monthly (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    implementation_id text NOT NULL REFERENCES implementations(id),
    month text NOT NULL,                    -- '2026-03'
    active_users integer DEFAULT 0,
    total_sessions integer DEFAULT 0,
    total_files integer DEFAULT 0,
    total_images integer DEFAULT 0,
    total_audio integer DEFAULT 0,
    total_video integer DEFAULT 0,
    total_text integer DEFAULT 0,
    total_bytes bigint DEFAULT 0,
    reports_generated integer DEFAULT 0,
    ai_calls_vision integer DEFAULT 0,
    ai_calls_whisper integer DEFAULT 0,
    ai_calls_report integer DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE(implementation_id, month)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_usage_monthly_impl ON usage_monthly(implementation_id);
CREATE INDEX IF NOT EXISTS idx_usage_monthly_month ON usage_monthly(month);

-- Quick function to get current month usage
CREATE OR REPLACE FUNCTION get_usage_summary(p_impl text, p_month text DEFAULT NULL)
RETURNS json AS $$
DECLARE
    target_month text;
    result json;
BEGIN
    target_month := COALESCE(p_month, to_char(now(), 'YYYY-MM'));

    SELECT json_build_object(
        'month', target_month,
        'implementation_id', p_impl,
        'active_users', COALESCE(
            (SELECT COUNT(DISTINCT user_phone) FROM sessions
             WHERE implementation = p_impl
             AND to_char(created_at, 'YYYY-MM') = target_month), 0),
        'total_sessions', COALESCE(
            (SELECT COUNT(*) FROM sessions
             WHERE implementation = p_impl
             AND to_char(created_at, 'YYYY-MM') = target_month), 0),
        'total_files', COALESCE(
            (SELECT SUM(jsonb_array_length(COALESCE(raw_files, '[]'::jsonb))) FROM sessions
             WHERE implementation = p_impl
             AND to_char(created_at, 'YYYY-MM') = target_month), 0)
    ) INTO result;

    RETURN result;
END;
$$ LANGUAGE plpgsql;
