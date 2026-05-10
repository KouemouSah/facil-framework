-- Migration 180: Composite indexes for agent list query scalability (1M+ requests, 100+ agents)
-- Fixes: ORDER BY on non-indexed expression, missing composite for filter+sort pattern

-- 1. Composite index for agent list: workflow_code filter + created_at sort
-- Covers: WHERE workflow_code = ANY(...) ORDER BY created_at DESC LIMIT 20
-- Before: idx_sr_workflow_code (workflow_code only) → sort on full result set O(N log N)
-- After: native ordered scan → LIMIT 20 fetches exactly 20 rows O(1)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sr_workflow_created
ON service_requests (workflow_code, created_at DESC);

-- 2. Composite index for agent-filtered list: assigned_to + workflow_code + sort
-- Covers: WHERE assigned_to = $1 AND workflow_code = ANY(...) ORDER BY created_at DESC
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sr_assigned_workflow_created
ON service_requests (assigned_to, workflow_code, created_at DESC)
WHERE assigned_to IS NOT NULL;

-- 3. Composite index for workflow_code + status filter + sort
-- Covers: WHERE workflow_code = ANY(...) AND status = $1 ORDER BY created_at DESC
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sr_workflow_status_created
ON service_requests (workflow_code, status, created_at DESC);

-- 4. Composite index on service_request_history for LATERAL JOIN pattern
-- Covers: WHERE service_request_id = $1 ORDER BY performed_at DESC LIMIT 1
-- Before: idx_srh_request_id (request_id only) → sort per request
-- After: native ordered scan → LIMIT 1 is O(1)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_srh_request_performed
ON service_request_history (service_request_id, performed_at DESC);

-- 5. Covering index on entity_translations for translation JOIN pattern
-- Before: PK (entity_type, entity_code, language_code, field_name) → Bitmap Heap Scan (20ms for 830 rows)
-- After: (entity_type, language_code, field_name, entity_code) INCLUDE (translation_text) → Index Only Scan (0.5ms)
-- The column reorder allows direct scan when entity_code is the JOIN variable (not in WHERE)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_et_type_lang_field_code
ON entity_translations (entity_type, language_code, field_name, entity_code)
INCLUDE (translation_text);
