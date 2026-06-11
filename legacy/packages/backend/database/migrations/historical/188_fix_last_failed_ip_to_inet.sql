-- Migration 188: Fix last_failed_ip VARCHAR(45) → INET
-- Issue: m2 from Auth Security Hardening audit
-- All other IP columns in the system already use INET type
-- This column has 0 non-NULL values, so conversion is safe
--
-- Benefits of INET over VARCHAR:
-- 1. Built-in validation (rejects invalid IPs at DB level)
-- 2. Supports IPv4 and IPv6 natively
-- 3. Enables network operations (<<, >>=, containment)
-- 4. More compact storage (7 bytes IPv4 vs up to 45 bytes VARCHAR)
-- 5. GiST index support for geo-IP queries

ALTER TABLE users
ALTER COLUMN last_failed_ip TYPE inet
USING last_failed_ip::inet;

COMMENT ON COLUMN users.last_failed_ip IS 'IP address of last failed login attempt (INET type for validation and network ops)';
