-- Migration 231: Add FK constraint on company_creation_drafts.created_license_id
-- References commercial_licenses(id) with ON DELETE SET NULL
-- This was intentionally omitted in migration 230 pending table verification

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_draft_created_license'
          AND table_name = 'company_creation_drafts'
    ) THEN
        ALTER TABLE company_creation_drafts
            ADD CONSTRAINT fk_draft_created_license
            FOREIGN KEY (created_license_id)
            REFERENCES commercial_licenses(id)
            ON DELETE SET NULL;
    END IF;
END $$;
