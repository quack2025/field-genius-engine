-- 008: User Groups + Session Facts for multi-level report aggregation
-- Run in Supabase SQL Editor

-- 1. User groups table (zone + tags)
CREATE TABLE IF NOT EXISTS user_groups (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    implementation_id text NOT NULL REFERENCES implementations(id),
    name text NOT NULL,
    slug text NOT NULL,
    zone text,
    tags text[] DEFAULT '{}',
    created_at timestamptz DEFAULT now(),
    UNIQUE(implementation_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_user_groups_impl ON user_groups(implementation_id);

-- 2. Add group_id and tags to users
ALTER TABLE users ADD COLUMN IF NOT EXISTS group_id uuid REFERENCES user_groups(id);
ALTER TABLE users ADD COLUMN IF NOT EXISTS tags text[] DEFAULT '{}';

-- 3. Session facts table — structured extraction per session per framework
CREATE TABLE IF NOT EXISTS session_facts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    implementation_id text NOT NULL,
    framework text NOT NULL,
    facts jsonb NOT NULL DEFAULT '{}',
    key_quotes text[] DEFAULT '{}',
    fact_count integer DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    UNIQUE(session_id, framework)
);

CREATE INDEX IF NOT EXISTS idx_session_facts_impl_framework
ON session_facts(implementation_id, framework, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_session_facts_session
ON session_facts(session_id);

-- 4. Add group_id to sessions for fast group-level queries
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS group_id uuid REFERENCES user_groups(id);

COMMENT ON TABLE user_groups IS 'Groups of field users by zone/team for aggregated reporting';
COMMENT ON TABLE session_facts IS 'Structured facts extracted from individual reports, used for SQL aggregation in group/project reports';
COMMENT ON COLUMN session_facts.facts IS 'JSON with structured data: competitors, prices, alerts, sentiment, zones — schema varies by framework';
COMMENT ON COLUMN session_facts.key_quotes IS 'Top 3-5 representative quotes from the session for use in aggregated reports';
