-- Field Genius Engine — Alerts table for monitoring system
-- Run this AFTER 002_multi_tenant.sql in Supabase SQL Editor

-- 1. Alerts table
CREATE TABLE IF NOT EXISTS alerts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    implementation text NOT NULL,
    alert_type text NOT NULL,
    severity text NOT NULL DEFAULT 'warning',
    title text NOT NULL,
    detail text,
    context jsonb DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'open',
    resolved_at timestamptz,
    resolved_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT alerts_type_check CHECK (
        alert_type IN (
            'pipeline_failure',
            'executive_inactive',
            'low_confidence',
            'schema_mismatch',
            'price_anomaly',
            'high_unassigned'
        )
    ),
    CONSTRAINT alerts_severity_check CHECK (severity IN ('info', 'warning', 'critical')),
    CONSTRAINT alerts_status_check CHECK (status IN ('open', 'acknowledged', 'resolved'))
);

-- 2. Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_alerts_impl_status ON alerts(implementation, status);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);

-- 3. RLS policies (read-only for authenticated, write via service_role)
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated read" ON alerts
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Allow service_role all" ON alerts
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
