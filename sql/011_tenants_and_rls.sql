-- 011: Multi-tenant permissions + RLS
-- Run in Supabase SQL Editor

-- ═══════════════════════════════════════════════════════════════
-- 1. Create backoffice_users table (if not exists)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS backoffice_users (
    id uuid PRIMARY KEY REFERENCES auth.users(id),
    email text NOT NULL DEFAULT '',
    name text NOT NULL DEFAULT '',
    role text NOT NULL DEFAULT 'viewer',
    allowed_implementations text[] DEFAULT '{}',
    permissions jsonb DEFAULT '{}'::jsonb,
    last_login timestamptz,
    is_active boolean DEFAULT true,
    created_at timestamptz DEFAULT now()
);

-- Add constraint (drop first to be safe)
ALTER TABLE backoffice_users DROP CONSTRAINT IF EXISTS backoffice_users_role_check;
ALTER TABLE backoffice_users ADD CONSTRAINT backoffice_users_role_check
  CHECK (role IN ('superadmin', 'admin', 'analyst', 'viewer'));

-- Add columns that might be missing if table already existed
ALTER TABLE backoffice_users ADD COLUMN IF NOT EXISTS permissions jsonb DEFAULT '{}'::jsonb;
ALTER TABLE backoffice_users ADD COLUMN IF NOT EXISTS last_login timestamptz;
ALTER TABLE backoffice_users ADD COLUMN IF NOT EXISTS is_active boolean DEFAULT true;

-- ═══════════════════════════════════════════════════════════════
-- 2. Seed superadmin (Jorge)
-- ═══════════════════════════════════════════════════════════════

INSERT INTO backoffice_users (id, email, name, role, allowed_implementations, is_active)
SELECT
  id,
  email,
  'Jorge Rosales',
  'superadmin',
  '{}',
  true
FROM auth.users
WHERE email = 'jorgealejandro.rosales@gmail.com'
ON CONFLICT (id) DO UPDATE SET
  role = 'superadmin',
  name = 'Jorge Rosales',
  allowed_implementations = '{}',
  is_active = true;

-- ═══════════════════════════════════════════════════════════════
-- 3. Helper functions
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
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION get_backoffice_role(user_id uuid)
RETURNS text AS $$
DECLARE
  r text;
BEGIN
  SELECT role INTO r FROM backoffice_users WHERE id = user_id AND is_active = true;
  RETURN COALESCE(r, 'none');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ═══════════════════════════════════════════════════════════════
-- 4. Enable RLS + create policies
-- ═══════════════════════════════════════════════════════════════

ALTER TABLE implementations ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE visit_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE consolidated_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE visit_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE backoffice_users ENABLE ROW LEVEL SECURITY;

-- Drop existing policies
DO $$
DECLARE
  tbl text;
  pol record;
BEGIN
  FOR tbl IN SELECT unnest(ARRAY[
    'implementations', 'sessions', 'visit_reports', 'users',
    'user_groups', 'session_facts', 'consolidated_reports', 'visit_types',
    'backoffice_users'
  ]) LOOP
    FOR pol IN SELECT policyname FROM pg_policies WHERE tablename = tbl LOOP
      EXECUTE format('DROP POLICY IF EXISTS %I ON %I', pol.policyname, tbl);
    END LOOP;
  END LOOP;
END $$;

-- Policies
CREATE POLICY impl_select ON implementations FOR SELECT USING (user_has_impl_access(auth.uid(), id));
CREATE POLICY impl_modify ON implementations FOR ALL USING (get_backoffice_role(auth.uid()) IN ('superadmin', 'admin') AND user_has_impl_access(auth.uid(), id));

CREATE POLICY sessions_select ON sessions FOR SELECT USING (user_has_impl_access(auth.uid(), implementation));

CREATE POLICY users_select ON users FOR SELECT USING (user_has_impl_access(auth.uid(), implementation));
CREATE POLICY users_modify ON users FOR ALL USING (get_backoffice_role(auth.uid()) IN ('superadmin', 'admin') AND user_has_impl_access(auth.uid(), implementation));

CREATE POLICY vr_select ON visit_reports FOR SELECT USING (user_has_impl_access(auth.uid(), implementation));

CREATE POLICY vt_select ON visit_types FOR SELECT USING (user_has_impl_access(auth.uid(), implementation_id));
CREATE POLICY vt_modify ON visit_types FOR ALL USING (get_backoffice_role(auth.uid()) IN ('superadmin', 'admin') AND user_has_impl_access(auth.uid(), implementation_id));

CREATE POLICY ug_select ON user_groups FOR SELECT USING (user_has_impl_access(auth.uid(), implementation_id));
CREATE POLICY ug_modify ON user_groups FOR ALL USING (get_backoffice_role(auth.uid()) IN ('superadmin', 'admin') AND user_has_impl_access(auth.uid(), implementation_id));

CREATE POLICY sf_select ON session_facts FOR SELECT USING (user_has_impl_access(auth.uid(), implementation_id));

CREATE POLICY cr_select ON consolidated_reports FOR SELECT USING (user_has_impl_access(auth.uid(), implementation_id));

CREATE POLICY bu_self ON backoffice_users FOR SELECT USING (id = auth.uid() OR get_backoffice_role(auth.uid()) = 'superadmin');
CREATE POLICY bu_manage ON backoffice_users FOR ALL USING (get_backoffice_role(auth.uid()) = 'superadmin');
