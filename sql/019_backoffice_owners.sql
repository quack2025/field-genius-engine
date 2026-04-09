-- 019: Add owner-level backoffice users
-- Run AFTER users have signed in via Google SSO at least once
-- (auth.users records must exist first)
--
-- Step 1: Get their auth.users IDs
-- SELECT id, email FROM auth.users WHERE email IN ('jorge.rosales@xponencial.net', 'jorge.quintero@xponencial.net');
--
-- Step 2: Insert into backoffice_users (replace UUIDs from Step 1)

-- Jorge Rosales
INSERT INTO backoffice_users (id, email, name, role, allowed_implementations, is_active)
SELECT id, email, 'Jorge Rosales', 'superadmin', '{}', true
FROM auth.users WHERE email = 'jorge.rosales@xponencial.net'
ON CONFLICT (id) DO UPDATE SET
  role = 'superadmin',
  name = 'Jorge Rosales',
  is_active = true;

-- Jorge Quintero
INSERT INTO backoffice_users (id, email, name, role, allowed_implementations, is_active)
SELECT id, email, 'Jorge Quintero', 'superadmin', '{}', true
FROM auth.users WHERE email = 'jorge.quintero@xponencial.net'
ON CONFLICT (id) DO UPDATE SET
  role = 'superadmin',
  name = 'Jorge Quintero',
  is_active = true;

-- Verify
SELECT id, email, name, role, is_active FROM backoffice_users ORDER BY email;
