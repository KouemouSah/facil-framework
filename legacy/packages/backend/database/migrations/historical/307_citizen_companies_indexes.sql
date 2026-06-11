-- Migration 307: Indexes for citizen company detail + payment history
--
-- Audit BD findings:
-- 1. service_payments has NO index on company_id — sequential scan at 1M+ rows
--    for GET /my-companies/{id}/payments
-- 2. field_inspections(company_id) — verify index exists for inspection history
--
-- NOTE: CREATE INDEX CONCURRENTLY cannot run inside a transaction.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sp_company_id
    ON service_payments (company_id)
    WHERE company_id IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fi_company_id
    ON field_inspections (company_id)
    WHERE company_id IS NOT NULL;
