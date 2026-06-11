-- Migration 189: Auth Security Cleanup
-- Executed: 2026-03-09
-- 1. Clear expired password reset tokens (security hygiene)
-- 2. Widen two_factor_secret for Fernet encryption (VARCHAR(64) → TEXT)
-- 3. TOTP secrets encrypted via Python script 189_encrypt_totp_secrets.py

-- D2: Clear expired password reset tokens (2 cleaned)
UPDATE users
SET password_reset_token = NULL,
    password_reset_expires_at = NULL
WHERE password_reset_token IS NOT NULL
  AND password_reset_expires_at < NOW();

-- D3 pre-req: Widen column for Fernet-encrypted TOTP secrets (~120 chars)
ALTER TABLE users ALTER COLUMN two_factor_secret TYPE TEXT;
-- D3: Run 189_encrypt_totp_secrets.py to encrypt plaintext secrets
