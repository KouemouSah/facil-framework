-- Migration: Add html_content column to email_templates
-- Date: 2025-12-20
-- Description: Store HTML content directly in DB instead of file references
--              This aligns email_templates with sms_templates architecture

-- =============================================================================
-- SCHEMA MODIFICATION
-- =============================================================================

-- 1. Add html_content column for storing HTML directly
ALTER TABLE email_templates
ADD COLUMN IF NOT EXISTS html_content TEXT;

-- 2. Make html_file_path nullable (deprecated, kept for backwards compatibility)
ALTER TABLE email_templates
ALTER COLUMN html_file_path DROP NOT NULL;

-- 3. Add comment explaining the change
COMMENT ON COLUMN email_templates.html_content IS 'HTML content stored directly (preferred). Contains multilingual sections.';
COMMENT ON COLUMN email_templates.html_file_path IS 'DEPRECATED: Path to HTML file. Use html_content instead.';

-- =============================================================================
-- NOTES
-- =============================================================================
-- Priority logic in service:
--   content = template.html_content OR read_file(template.html_file_path)
--
-- New templates should use html_content exclusively.
-- html_file_path is kept for backwards compatibility only.
