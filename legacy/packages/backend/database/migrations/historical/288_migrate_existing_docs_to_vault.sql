-- Migration 288: Migrate existing service_request_documents into user_documents vault
-- Idempotent: skips documents already migrated (checks source_document_id)
-- Date: 2026-04-05
-- Ref: Feature 2 — vault bootstrap from wizard history

BEGIN;

-- Migrate existing service_request_documents into user_documents vault
-- Only for documents not already migrated (idempotent)
INSERT INTO user_documents (
    user_id, source, source_request_id, source_document_id,
    document_type, document_category,
    file_path, file_name, file_size_bytes, mime_type, file_hash,
    extraction_data, extraction_confidence, extraction_status,
    classification_method, status, is_verified, verified_at
)
SELECT
    sr.user_id,
    'wizard_import',
    sr.id,
    srd.id,
    srd.document_code,
    'other',  -- Will be classified later by migrate_vault_categories.py
    srd.file_path,
    srd.file_name,
    COALESCE(srd.file_size, 0),
    COALESCE(srd.mime_type, 'application/pdf'),
    MD5(srd.file_path),  -- Use file_path hash as proxy for file content hash
    COALESCE(srd.extraction_data, '{}'::jsonb),
    srd.extraction_confidence,
    CASE
        WHEN srd.extraction_status = 'success' THEN 'completed'
        WHEN srd.extraction_status IN ('pending', 'processing', 'completed', 'failed') THEN srd.extraction_status
        ELSE 'pending'
    END,
    'gemini',
    'active',
    TRUE,
    srd.validated_at
FROM service_request_documents srd
JOIN service_requests sr ON sr.id = srd.service_request_id
WHERE NOT EXISTS (
    SELECT 1 FROM user_documents ud
    WHERE ud.source_document_id = srd.id
)
AND srd.file_path IS NOT NULL
AND srd.file_path != '';

-- Report how many were migrated
DO $$
DECLARE
    migrated_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO migrated_count
    FROM user_documents WHERE source = 'wizard_import';
    RAISE NOTICE 'Migration 288: % documents migrated to vault', migrated_count;
END $$;

COMMIT;
