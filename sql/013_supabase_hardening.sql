-- 013: Supabase hardening — security, indexes, constraints
-- Run in Supabase SQL Editor

-- ═══════════════════════════════════════════════════════════════
-- 1. Fix SECURITY DEFINER functions: add SET search_path
-- ═══════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION user_has_impl_access(user_id uuid, impl_id text)
RETURNS boolean AS $$
DECLARE
  user_role text;
  allowed text[];
BEGIN
  SELECT bu.role, bu.allowed_implementations
  INTO user_role, allowed
  FROM backoffice_users bu
  WHERE bu.id = user_id AND bu.is_active = true;

  IF NOT FOUND THEN RETURN false; END IF;
  IF user_role = 'superadmin' THEN RETURN true; END IF;
  IF allowed IS NULL OR array_length(allowed, 1) IS NULL THEN RETURN false; END IF;
  RETURN impl_id = ANY(allowed);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

CREATE OR REPLACE FUNCTION get_backoffice_role(user_id uuid)
RETURNS text AS $$
DECLARE
  r text;
BEGIN
  SELECT role INTO r FROM backoffice_users WHERE id = user_id AND is_active = true;
  RETURN COALESCE(r, 'none');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Restrict execution to authenticated users only
REVOKE EXECUTE ON FUNCTION user_has_impl_access FROM public;
GRANT EXECUTE ON FUNCTION user_has_impl_access TO authenticated;
GRANT EXECUTE ON FUNCTION user_has_impl_access TO service_role;

REVOKE EXECUTE ON FUNCTION get_backoffice_role FROM public;
GRANT EXECUTE ON FUNCTION get_backoffice_role TO authenticated;
GRANT EXECUTE ON FUNCTION get_backoffice_role TO service_role;

-- ═══════════════════════════════════════════════════════════════
-- 2. Add missing indexes for RLS performance + query speed
-- ═══════════════════════════════════════════════════════════════

-- Sessions: RLS filters by implementation (text field)
CREATE INDEX IF NOT EXISTS idx_sessions_implementation_text
ON sessions(implementation);

-- Sessions: filter by date range (common in reports)
CREATE INDEX IF NOT EXISTS idx_sessions_date_desc
ON sessions(date DESC);

-- Visit reports: filter by implementation
CREATE INDEX IF NOT EXISTS idx_visit_reports_implementation
ON visit_reports(implementation);

-- Session facts: compound index for group/project reports
CREATE INDEX IF NOT EXISTS idx_session_facts_impl_framework
ON session_facts(implementation_id, framework);

-- Users: filter by implementation + role
CREATE INDEX IF NOT EXISTS idx_users_implementation_role
ON users(implementation, role);

-- Users: filter by group_id
CREATE INDEX IF NOT EXISTS idx_users_group_id
ON users(group_id) WHERE group_id IS NOT NULL;

-- Backoffice users: covering index for RLS function
CREATE INDEX IF NOT EXISTS idx_backoffice_users_active
ON backoffice_users(id) WHERE is_active = true;

-- Consolidated reports: filter by implementation + status
CREATE INDEX IF NOT EXISTS idx_consolidated_reports_impl_status
ON consolidated_reports(implementation_id, status);

-- ═══════════════════════════════════════════════════════════════
-- 3. Add CHECK constraints
-- ═══════════════════════════════════════════════════════════════

-- Users: role validation
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check
  CHECK (role IN ('field_agent', 'sales', 'operator', 'marketing', 'supervisor', 'manager', 'executive'));

-- Session facts: framework validation
ALTER TABLE session_facts DROP CONSTRAINT IF EXISTS session_facts_framework_check;
ALTER TABLE session_facts ADD CONSTRAINT session_facts_framework_check
  CHECK (framework IN ('tactical', 'strategic', 'innovation', 'competidor', 'cliente', 'comunicacion'));

-- ═══════════════════════════════════════════════════════════════
-- 4. Add RLS policies for INSERT/UPDATE/DELETE (not just SELECT)
-- ═══════════════════════════════════════════════════════════════

-- Sessions: allow service_role to insert (webhook creates sessions)
-- Note: service_role bypasses RLS, but these are defense-in-depth

DO $$
BEGIN
  -- Sessions INSERT for service_role (webhook)
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'sessions' AND policyname = 'sessions_insert') THEN
    CREATE POLICY sessions_insert ON sessions FOR INSERT WITH CHECK (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'sessions' AND policyname = 'sessions_update') THEN
    CREATE POLICY sessions_update ON sessions FOR UPDATE USING (user_has_impl_access(auth.uid(), implementation));
  END IF;

  -- Visit reports
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'visit_reports' AND policyname = 'vr_insert') THEN
    CREATE POLICY vr_insert ON visit_reports FOR INSERT WITH CHECK (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'visit_reports' AND policyname = 'vr_update') THEN
    CREATE POLICY vr_update ON visit_reports FOR UPDATE USING (user_has_impl_access(auth.uid(), implementation));
  END IF;

  -- Session facts
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'session_facts' AND policyname = 'sf_insert') THEN
    CREATE POLICY sf_insert ON session_facts FOR INSERT WITH CHECK (true);
  END IF;

  -- Consolidated reports
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'consolidated_reports' AND policyname = 'cr_insert') THEN
    CREATE POLICY cr_insert ON consolidated_reports FOR INSERT WITH CHECK (true);
  END IF;

  -- Users INSERT (admin creates field users)
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'users' AND policyname = 'users_insert') THEN
    CREATE POLICY users_insert ON users FOR INSERT WITH CHECK (
      get_backoffice_role(auth.uid()) IN ('superadmin', 'admin')
    );
  END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════
-- 5. Enable RLS on usage_monthly (was missing)
-- ═══════════════════════════════════════════════════════════════

ALTER TABLE usage_monthly ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'usage_monthly' AND policyname = 'usage_select') THEN
    CREATE POLICY usage_select ON usage_monthly FOR SELECT USING (
      user_has_impl_access(auth.uid(), implementation_id)
    );
  END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════
-- 6. Storage bucket policies for media
-- ═══════════════════════════════════════════════════════════════

-- Ensure media bucket exists and is private
-- (This must be done via Supabase Dashboard or API, not SQL)
-- The backend uses service_role to upload/download, so no storage
-- policies are needed for the backend flow.
-- If frontend ever accesses storage directly, add policies here.

-- ═══════════════════════════════════════════════════════════════
-- 7. Add updated_at trigger (auto-update on any modification)
-- ═══════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
  tbl text;
BEGIN
  FOR tbl IN SELECT unnest(ARRAY['sessions', 'implementations', 'visit_types']) LOOP
    IF NOT EXISTS (
      SELECT 1 FROM pg_trigger WHERE tgname = tbl || '_updated_at'
    ) THEN
      EXECUTE format(
        'CREATE TRIGGER %I BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at()',
        tbl || '_updated_at', tbl
      );
    END IF;
  END LOOP;
END $$;

-- ═══════════════════════════════════════════════════════════════
-- 8. Ensure consolidated_reports exists (referenced in RLS)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS consolidated_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    implementation_id text NOT NULL,
    title text NOT NULL DEFAULT '',
    framework text NOT NULL DEFAULT '',
    visit_report_ids uuid[] DEFAULT '{}',
    filters jsonb DEFAULT '{}',
    analysis_markdown text,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    requested_by uuid,
    processing_time_ms integer,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);
