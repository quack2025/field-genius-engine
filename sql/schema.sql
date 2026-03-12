-- Field Genius Engine — Supabase schema
-- Run this in the SQL Editor of your Supabase project

-- Users: ejecutivos registrados
CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    implementation text NOT NULL DEFAULT 'argos',
    phone text UNIQUE NOT NULL,
    name text NOT NULL,
    role text NOT NULL DEFAULT 'executive',
    notification_group text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);

-- Sessions: sesión diaria por usuario (acumula media)
CREATE TABLE IF NOT EXISTS sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    implementation text NOT NULL DEFAULT 'argos',
    user_phone text NOT NULL,
    user_name text NOT NULL,
    date date NOT NULL DEFAULT CURRENT_DATE,
    status text NOT NULL DEFAULT 'accumulating',
    raw_files jsonb NOT NULL DEFAULT '[]'::jsonb,
    segments jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT sessions_status_check CHECK (
        status IN ('accumulating', 'segmenting', 'processing', 'completed', 'needs_clarification')
    )
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_date ON sessions(user_phone, date);

-- Visit reports: reporte por visita identificada
CREATE TABLE IF NOT EXISTS visit_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    implementation text NOT NULL DEFAULT 'argos',
    visit_type text NOT NULL,
    inferred_location text,
    extracted_data jsonb NOT NULL DEFAULT '{}'::jsonb,
    confidence_score float,
    status text NOT NULL DEFAULT 'processing',
    sheets_row_id text,
    gamma_url text,
    processing_time_ms integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT visit_reports_status_check CHECK (
        status IN ('processing', 'completed', 'failed', 'needs_review')
    )
);

CREATE INDEX IF NOT EXISTS idx_visit_reports_session ON visit_reports(session_id);
