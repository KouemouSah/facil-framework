-- ============================================================================
-- ACCOUNTANT DEADLINE TRACKING - DATABASE INDEXES
-- ============================================================================
-- Version: 1.0
-- Date: 2025-02-03
-- Module: Accountant Deadline Tracking API
-- Description: Critical indexes for optimal query performance
--
-- IMPORTANT: These indexes are MANDATORY for production deployment.
-- Without these indexes, queries can take 5-20 seconds instead of 50-200ms.
--
-- Performance Impact: 10-50x improvement with these indexes
-- ============================================================================

-- ============================================================================
-- INDEX 1: Company Members - Accountant Filter (CRITICAL)
-- ============================================================================
-- Purpose: Filter declarations to accountant's assigned client companies
-- Impact: 10-50x performance improvement
-- Used by: All deadline queries
-- Estimated rows per accountant: 100-1,000

CREATE INDEX IF NOT EXISTS idx_company_members_user_role
ON company_members(user_id, role)
WHERE role IN ('company_accountant', 'company_owner', 'company_admin');

COMMENT ON INDEX idx_company_members_user_role IS
'Critical index for accountant deadline tracking - filters to accountant''s client companies';

-- ============================================================================
-- INDEX 2: Declarations Status + Due Date (CRITICAL)
-- ============================================================================
-- Purpose: Filter out completed/rejected declarations and enable date filtering
-- Impact: 5-20x performance improvement
-- Used by: All deadline queries
-- Estimated rows: 10,000-100,000 active declarations

CREATE INDEX IF NOT EXISTS idx_declarations_status_due_date
ON tax_declarations(status, fiscal_period_end)
WHERE status NOT IN ('approved', 'rejected');

COMMENT ON INDEX idx_declarations_status_due_date IS
'Index for filtering active declarations by status and due date';

-- ============================================================================
-- INDEX 3: Upcoming Deadlines Composite (HIGH PRIORITY)
-- ============================================================================
-- Purpose: Optimize queries for upcoming deadlines with sorting
-- Impact: Enables index-only scans, reduces query time by 5-10x
-- Used by: GET /deadlines/upcoming endpoint
-- Estimated rows: 1,000-10,000 upcoming declarations

CREATE INDEX IF NOT EXISTS idx_declarations_upcoming
ON tax_declarations(fiscal_period_end, calculated_tax DESC)
WHERE fiscal_period_end > CURRENT_DATE
  AND status NOT IN ('approved', 'rejected');

COMMENT ON INDEX idx_declarations_upcoming IS
'Composite index for upcoming deadlines with amount sorting';

-- ============================================================================
-- INDEX 4: Overdue Deadlines Composite (HIGH PRIORITY)
-- ============================================================================
-- Purpose: Optimize queries for overdue declarations with sorting
-- Impact: Enables index-only scans, reduces query time by 5-10x
-- Used by: GET /deadlines/overdue endpoint
-- Estimated rows: 500-5,000 overdue declarations

CREATE INDEX IF NOT EXISTS idx_declarations_overdue
ON tax_declarations(fiscal_period_end DESC, calculated_tax DESC)
WHERE fiscal_period_end < CURRENT_DATE
  AND status NOT IN ('approved', 'rejected');

COMMENT ON INDEX idx_declarations_overdue IS
'Composite index for overdue deadlines with severity sorting';

-- ============================================================================
-- INDEX 5: Agent Work Queue - Declaration Items (MEDIUM PRIORITY)
-- ============================================================================
-- Purpose: Optimize LEFT JOIN for escalation information
-- Impact: 3-10x improvement for escalation queries
-- Used by: All deadline queries (optional escalation data)
-- Estimated rows: 1,000-10,000 queue items

CREATE INDEX IF NOT EXISTS idx_agent_work_queue_item
ON agent_work_queue(item_type, item_id)
WHERE item_type = 'declaration';

COMMENT ON INDEX idx_agent_work_queue_item IS
'Index for joining agent work queue with declarations for escalation data';

-- ============================================================================
-- INDEX 6: Declarations Company ID (EXISTING - VERIFY)
-- ============================================================================
-- Purpose: Optimize JOIN between declarations and companies
-- Impact: 5-20x improvement for company filtering
-- Note: This index should already exist, but verify
-- Estimated rows: 10,000-100,000 declarations

-- Check if index exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE tablename = 'tax_declarations'
        AND indexname = 'idx_declarations_company_id'
    ) THEN
        CREATE INDEX idx_declarations_company_id
        ON tax_declarations(company_id);

        RAISE NOTICE 'Created index: idx_declarations_company_id';
    ELSE
        RAISE NOTICE 'Index already exists: idx_declarations_company_id';
    END IF;
END $$;

COMMENT ON INDEX idx_declarations_company_id IS
'Foreign key index for joining declarations with companies';

-- ============================================================================
-- INDEX 7: Calendar View - Date Grouping (OPTIONAL)
-- ============================================================================
-- Purpose: Optimize calendar view queries with date grouping
-- Impact: 2-5x improvement for calendar aggregations
-- Used by: GET /calendar endpoint
-- Note: Only create if calendar queries are slow (>200ms)

-- Uncomment if needed:
-- CREATE INDEX IF NOT EXISTS idx_declarations_calendar_date
-- ON tax_declarations(date_trunc('day', fiscal_period_end), calculated_tax)
-- WHERE status NOT IN ('approved', 'rejected');

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify all indexes are created
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE indexname IN (
    'idx_company_members_user_role',
    'idx_declarations_status_due_date',
    'idx_declarations_upcoming',
    'idx_declarations_overdue',
    'idx_agent_work_queue_item',
    'idx_declarations_company_id'
)
ORDER BY tablename, indexname;

-- Check index sizes
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(schemaname||'.'||indexname)) AS index_size
FROM pg_indexes
WHERE indexname IN (
    'idx_company_members_user_role',
    'idx_declarations_status_due_date',
    'idx_declarations_upcoming',
    'idx_declarations_overdue',
    'idx_agent_work_queue_item',
    'idx_declarations_company_id'
)
ORDER BY pg_relation_size(schemaname||'.'||indexname) DESC;

-- ============================================================================
-- MAINTENANCE NOTES
-- ============================================================================

/*
1. REINDEX periodically (monthly recommended):
   REINDEX INDEX CONCURRENTLY idx_company_members_user_role;
   REINDEX INDEX CONCURRENTLY idx_declarations_status_due_date;
   REINDEX INDEX CONCURRENTLY idx_declarations_upcoming;
   REINDEX INDEX CONCURRENTLY idx_declarations_overdue;
   REINDEX INDEX CONCURRENTLY idx_agent_work_queue_item;

2. ANALYZE tables after large data changes:
   ANALYZE tax_declarations;
   ANALYZE company_members;
   ANALYZE agent_work_queue;

3. Monitor index usage:
   SELECT
       schemaname,
       tablename,
       indexname,
       idx_scan,
       idx_tup_read,
       idx_tup_fetch
   FROM pg_stat_user_indexes
   WHERE tablename IN ('tax_declarations', 'company_members', 'agent_work_queue')
   ORDER BY idx_scan DESC;

4. Monitor bloat (quarterly):
   SELECT
       schemaname,
       tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
       pg_size_pretty(pg_table_size(schemaname||'.'||tablename)) AS table_size,
       pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) AS indexes_size
   FROM pg_tables
   WHERE tablename IN ('tax_declarations', 'company_members', 'agent_work_queue')
   ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
*/

-- ============================================================================
-- ROLLBACK (if needed)
-- ============================================================================

/*
-- Drop all indexes created by this script:
DROP INDEX IF EXISTS idx_company_members_user_role;
DROP INDEX IF EXISTS idx_declarations_status_due_date;
DROP INDEX IF EXISTS idx_declarations_upcoming;
DROP INDEX IF EXISTS idx_declarations_overdue;
DROP INDEX IF EXISTS idx_agent_work_queue_item;
-- DROP INDEX IF EXISTS idx_declarations_company_id; -- Only if you created it
*/

-- ============================================================================
-- END OF SCRIPT
-- ============================================================================
