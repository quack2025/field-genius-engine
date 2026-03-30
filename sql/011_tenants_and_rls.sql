-- 011: Multi-tenant permissions + RLS
-- Run in Supabase SQL Editor
--
-- Roles:
--   superadmin  → ve todo, edita todo (Jorge + socio)
--   admin       → ve/edita solo sus implementations asignadas (equipo Telecable)
--   analyst     → ve reportes de sus implementations, no edita config
--   viewer      → solo lectura de reportes
--
-- RLS: el backend usa service_role_key (bypasses RLS), pero RLS protege
-- contra acceso directo a Supabase desde frontend o API keys filtradas.

-- ═══════════════════════════════════════════════════════════════
-- 1. Actualizar backoffice_users con permisos granulares
-- ═══════════════════════════════════════════════════════════════

-- Drop old constraint if exists
ALTER TABLE backoffice_users DROP CONSTRAINT IF EXISTS backoffice_users_role_check;

-- Add/update columns
ALTER TABLE backoffice_users ADD COLUMN IF NOT EXISTS role text DEFAULT 'viewer';
ALTER TABLE backoffice_users ADD COLUMN IF NOT EXISTS allowed_implementations text[] DEFAULT '{}';
ALTER TABLE backoffice_users ADD COLUMN IF NOT EXISTS name text DEFAULT '';
ALTER TABLE backoffice_users ADD COLUMN IF NOT EXISTS email text DEFAULT '';
ALTER TABLE backoffice_users ADD COLUMN IF NOT EXISTS permissions jsonb DEFAULT '{}'::jsonb;
ALTER TABLE backoffice_users ADD COLUMN IF NOT EXISTS last_login timestamptz;
ALTER TABLE backoffice_users ADD COLUMN IF NOT EXISTS is_active boolean DEFAULT true;

-- New constraint with all roles
ALTER TABLE backoffice_users ADD CONSTRAINT backoffice_users_role_check
  CHECK (role IN ('superadmin', 'admin', 'analyst', 'viewer'));

-- ═══════════════════════════════════════════════════════════════
-- 2. Seed superadmins (Jorge + socio)
-- ═══════════════════════════════════════════════════════════════

-- Jorge (already exists in auth.users from Supabase Auth)
INSERT INTO backoffice_users (id, email, name, role, allowed_implementations, is_active)
SELECT
  id,
  email,
  'Jorge Rosales',
  'superadmin',
  '{}',  -- superadmin sees all, empty = no filter
  true
FROM auth.users
WHERE email = 'jorge.rosales@xponencial.net'
ON CONFLICT (id) DO UPDATE SET
  role = 'superadmin',
  name = 'Jorge Rosales',
  allowed_implementations = '{}',
  is_active = true;

-- ═══════════════════════════════════════════════════════════════
-- 3. Helper function: check if user has access to implementation
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

  -- Superadmin has access to everything
  IF user_role = 'superadmin' THEN RETURN true; END IF;

  -- Others need explicit implementation access
  IF allowed IS NULL OR array_length(allowed, 1) IS NULL THEN RETURN false; END IF;

  RETURN impl_id = ANY(allowed);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ═══════════════════════════════════════════════════════════════
-- 4. Helper function: get user's backoffice role
-- ═══════════════════════════════════════════════════════════════

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
-- 5. RLS Policies
-- ═══════════════════════════════════════════════════════════════

-- Enable RLS on key tables
ALTER TABLE implementations ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE visit_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE consolidated_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE visit_types ENABLE ROW LEVEL SECURITY;

-- Drop existing policies to avoid conflicts
DO $$
DECLARE
  tbl text;
  pol record;
BEGIN
  FOR tbl IN SELECT unnest(ARRAY[
    'implementations', 'sessions', 'visit_reports', 'users',
    'user_groups', 'session_facts', 'consolidated_reports', 'visit_types'
  ]) LOOP
    FOR pol IN SELECT policyname FROM pg_policies WHERE tablename = tbl LOOP
      EXECUTE format('DROP POLICY IF EXISTS %I ON %I', pol.policyname, tbl);
    END LOOP;
  END LOOP;
END $$;

-- IMPLEMENTATIONS: superadmin sees all, others see allowed
CREATE POLICY impl_select ON implementations FOR SELECT USING (
  user_has_impl_access(auth.uid(), id)
);
CREATE POLICY impl_modify ON implementations FOR ALL USING (
  get_backoffice_role(auth.uid()) IN ('superadmin', 'admin')
  AND user_has_impl_access(auth.uid(), id)
);

-- SESSIONS: filtered by implementation access
CREATE POLICY sessions_select ON sessions FOR SELECT USING (
  user_has_impl_access(auth.uid(), implementation)
);

-- USERS (field users): filtered by implementation
CREATE POLICY users_select ON users FOR SELECT USING (
  user_has_impl_access(auth.uid(), implementation)
);
CREATE POLICY users_modify ON users FOR ALL USING (
  get_backoffice_role(auth.uid()) IN ('superadmin', 'admin')
  AND user_has_impl_access(auth.uid(), implementation)
);

-- VISIT_REPORTS: follow session access
CREATE POLICY vr_select ON visit_reports FOR SELECT USING (
  user_has_impl_access(auth.uid(), implementation)
);

-- VISIT_TYPES: follow implementation access
CREATE POLICY vt_select ON visit_types FOR SELECT USING (
  user_has_impl_access(auth.uid(), implementation_id)
);
CREATE POLICY vt_modify ON visit_types FOR ALL USING (
  get_backoffice_role(auth.uid()) IN ('superadmin', 'admin')
  AND user_has_impl_access(auth.uid(), implementation_id)
);

-- USER_GROUPS: follow implementation access
CREATE POLICY ug_select ON user_groups FOR SELECT USING (
  user_has_impl_access(auth.uid(), implementation_id)
);
CREATE POLICY ug_modify ON user_groups FOR ALL USING (
  get_backoffice_role(auth.uid()) IN ('superadmin', 'admin')
  AND user_has_impl_access(auth.uid(), implementation_id)
);

-- SESSION_FACTS: follow implementation access
CREATE POLICY sf_select ON session_facts FOR SELECT USING (
  user_has_impl_access(auth.uid(), implementation_id)
);

-- CONSOLIDATED_REPORTS: follow implementation access
CREATE POLICY cr_select ON consolidated_reports FOR SELECT USING (
  user_has_impl_access(auth.uid(), implementation_id)
);

-- BACKOFFICE_USERS: only superadmin can see all, others see themselves
ALTER TABLE backoffice_users ENABLE ROW LEVEL SECURITY;
CREATE POLICY bu_self ON backoffice_users FOR SELECT USING (
  id = auth.uid() OR get_backoffice_role(auth.uid()) = 'superadmin'
);
CREATE POLICY bu_manage ON backoffice_users FOR ALL USING (
  get_backoffice_role(auth.uid()) = 'superadmin'
);

-- ═══════════════════════════════════════════════════════════════
-- 6. IMPORTANT: service_role bypasses RLS
-- ═══════════════════════════════════════════════════════════════
-- The backend uses service_role_key which bypasses all RLS policies.
-- RLS only applies to:
--   - Direct Supabase client (anon key) from frontend
--   - Supabase REST API with user JWT
-- This is correct: backend is trusted, frontend is restricted.

-- ═══════════════════════════════════════════════════════════════
-- 7. Permissions JSON structure (for granular control)
-- ═══════════════════════════════════════════════════════════════
-- The permissions column allows fine-grained control per tenant admin:
-- {
--   "can_edit_prompts": true,      -- edit vision/segmentation prompts
--   "can_manage_users": true,      -- add/remove field users
--   "can_manage_groups": true,     -- create/edit user groups
--   "can_generate_reports": true,  -- generate individual/group/project reports
--   "can_view_usage": false,       -- see usage/billing stats
--   "can_bulk_import": true,       -- CSV bulk import
--   "can_edit_frameworks": false   -- modify analysis frameworks
-- }

-- Default permissions by role:
COMMENT ON COLUMN backoffice_users.permissions IS 'Granular permissions override. Empty = use role defaults.
superadmin: all permissions
admin: manage_users, manage_groups, generate_reports, edit_prompts, bulk_import
analyst: generate_reports, view_usage
viewer: read-only';
