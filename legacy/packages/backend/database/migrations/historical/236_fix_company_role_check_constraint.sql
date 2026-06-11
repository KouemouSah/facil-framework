-- Migration 236: Fix user_company_roles CHECK constraint mismatch
--
-- BUG: The CHECK constraint user_company_roles_role_check accepts
--   ('owner', 'admin', 'accountant', 'employee', 'viewer')
-- But the column type company_role_enum has values:
--   ('company_owner', 'company_admin', 'company_accountant', 'company_member')
--
-- The CHECK casts role::text and compares against the old short names,
-- which NEVER match the enum values. Any INSERT with a valid enum value
-- is REJECTED by the CHECK.
--
-- Fix: DROP the redundant CHECK constraint. The enum type already
-- enforces valid values — a CHECK on top of an enum is unnecessary
-- and in this case actively harmful.
--
-- VERIFIED: user_company_roles.role is type company_role_enum (USER-DEFINED)
-- VERIFIED: 0 rows in user_company_roles (no data to migrate)

BEGIN;

-- Drop the broken CHECK constraint
ALTER TABLE user_company_roles
    DROP CONSTRAINT IF EXISTS user_company_roles_role_check;

COMMIT;
