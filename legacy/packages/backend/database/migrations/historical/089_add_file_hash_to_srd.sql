-- Migration: 089_add_file_hash_to_srd.sql
-- Date: 2026-02-06
-- Description: Add file_hash column to service_request_documents for duplicate detection
-- Author: TaxasGE Development Team

-- Add SHA-256 hash column (nullable - existing documents don't have hashes)
ALTER TABLE service_request_documents
    ADD COLUMN IF NOT EXISTS file_hash VARCHAR(64);

-- Partial index for duplicate lookups (only index non-null hashes)
CREATE INDEX IF NOT EXISTS idx_srd_file_hash
    ON service_request_documents(file_hash)
    WHERE file_hash IS NOT NULL;

COMMENT ON COLUMN service_request_documents.file_hash
    IS 'SHA-256 hash of file content for duplicate detection across requests';
