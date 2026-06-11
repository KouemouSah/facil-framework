# Query Optimization Notes - Accountant Deadline Tracking API

## Database Schema Requirements

### Required Tables
- `tax_declarations` - Main declarations table
- `companies` - Company information
- `company_members` - Accountant-company relationships
- `agent_work_queue` - Escalation and assignment tracking
- `users` - User authentication

### Critical Indexes

**1. Company Members Index (Most Important)**
```sql
CREATE INDEX idx_company_members_user_role
ON company_members(user_id, role)
WHERE role IN ('company_accountant', 'company_owner', 'company_admin');
```
- **Impact:** 10-50x performance improvement
- **Why:** Filters declarations to accountant's clients
- **Expected rows:** 100-1,000 per accountant

**2. Declarations Status + Due Date Index**
```sql
CREATE INDEX idx_declarations_status_due_date
ON tax_declarations(status, fiscal_period_end)
WHERE status NOT IN ('approved', 'rejected');
```
- **Impact:** 5-20x performance improvement
- **Why:** Filters out completed declarations
- **Expected rows:** 10,000-100,000 active declarations

**3. Upcoming Deadlines Composite Index**
```sql
CREATE INDEX idx_declarations_upcoming
ON tax_declarations(fiscal_period_end, calculated_tax DESC)
WHERE fiscal_period_end > CURRENT_DATE
  AND status NOT IN ('approved', 'rejected');
```
- **Impact:** Enables index-only scans
- **Why:** Supports sorting and filtering
- **Use case:** Upcoming deadlines endpoint

**4. Overdue Deadlines Composite Index**
```sql
CREATE INDEX idx_declarations_overdue
ON tax_declarations(fiscal_period_end DESC, calculated_tax DESC)
WHERE fiscal_period_end < CURRENT_DATE
  AND status NOT IN ('approved', 'rejected');
```
- **Impact:** Enables index-only scans
- **Why:** Supports overdue queries
- **Use case:** Overdue deadlines endpoint

**5. Agent Work Queue Index**
```sql
CREATE INDEX idx_agent_work_queue_item
ON agent_work_queue(item_type, item_id)
WHERE item_type = 'declaration';
```
- **Impact:** 3-10x for escalation queries
- **Why:** Left join for escalation info
- **Expected rows:** 1,000-10,000

## Query Analysis

### 1. Upcoming Deadlines Query

**Query Structure:**
```sql
WITH deadline_calc AS (
    SELECT
        d.*,
        EXTRACT(DAY FROM (d.fiscal_period_end - CURRENT_DATE))::INTEGER AS days_until_due,
        -- ... other fields
        COUNT(*) OVER() AS total_count
    FROM tax_declarations d
    INNER JOIN companies c ON d.company_id = c.id
    INNER JOIN company_members cm ON c.id = cm.company_id
    LEFT JOIN agent_work_queue awq ON awq.item_id = d.id
    WHERE cm.user_id = $1
      AND d.fiscal_period_end > CURRENT_DATE
      AND d.status NOT IN ('approved', 'rejected')
)
SELECT * FROM deadline_calc
ORDER BY fiscal_period_end ASC
LIMIT $2 OFFSET $3;
```

**Performance Analysis:**
- **Best case:** 20-50ms (with indexes, 10 companies)
- **Average case:** 50-150ms (with indexes, 100 companies)
- **Worst case:** 200-500ms (with indexes, 1,000+ companies)
- **Without indexes:** 5,000-20,000ms (5-20 seconds)

**Optimization Techniques:**
1. **CTE (Common Table Expression)**
   - Calculates `days_until_due` once
   - Avoids duplicate calculations
   - Improves readability

2. **Window Function for Total Count**
   - `COUNT(*) OVER()` eliminates separate COUNT query
   - Reduces round trips to database
   - Single query instead of 2

3. **INNER JOINs**
   - `company_members` filter happens early
   - Query planner can use small result set
   - Index on `company_members(user_id)` is critical

4. **LEFT JOIN on agent_work_queue**
   - Optional escalation data
   - Doesn't filter out rows
   - Index on `(item_type, item_id)` helps

**EXPLAIN ANALYZE Output (expected):**
```
CTE Scan on deadline_calc  (cost=1000..2000 rows=100 width=200) (actual time=5..50 rows=100 loops=1)
  ->  WindowAgg  (cost=800..1500 rows=100 width=200)
        ->  Nested Loop Left Join  (cost=50..800 rows=100 width=200)
              ->  Hash Join  (cost=20..400 rows=100 width=200)
                    Hash Cond: (c.id = d.company_id)
                    ->  Nested Loop  (cost=0..200 rows=100 width=100)
                          Index Cond: (cm.user_id = 'accountant-uuid')
                          Index Name: idx_company_members_user_role
              ->  Index Scan using idx_agent_work_queue_item
Planning Time: 2.5 ms
Execution Time: 50.2 ms
```

### 2. Overdue Deadlines Query

**Query Structure:**
```sql
WITH overdue_calc AS (
    SELECT
        d.*,
        EXTRACT(DAY FROM (CURRENT_DATE - d.fiscal_period_end))::INTEGER AS days_overdue,
        CASE
            WHEN EXTRACT(DAY FROM (CURRENT_DATE - d.fiscal_period_end)) BETWEEN 1 AND 7 THEN 'recent'
            WHEN EXTRACT(DAY FROM (CURRENT_DATE - d.fiscal_period_end)) BETWEEN 8 AND 30 THEN 'moderate'
            ELSE 'critical'
        END AS severity,
        -- ... other fields
    FROM tax_declarations d
    WHERE d.fiscal_period_end < CURRENT_DATE
)
SELECT * FROM overdue_calc
ORDER BY days_overdue DESC;
```

**Performance Analysis:**
- **Best case:** 30-80ms
- **Average case:** 80-200ms
- **Worst case:** 300-800ms

**Optimization Techniques:**
1. **CASE WHEN for Severity**
   - Calculates severity in SQL
   - Avoids application-layer processing
   - Can be indexed if needed

2. **Grouping in Application Layer**
   - More flexible than SQL GROUP BY
   - Allows complex grouping logic
   - Better for small result sets (<1,000 rows)

3. **Index on fiscal_period_end DESC**
   - Supports ORDER BY days_overdue DESC
   - Enables efficient range scan
   - Critical for overdue filtering

### 3. Calendar View Queries

**Day View:**
```sql
SELECT
    DATE(d.fiscal_period_end) AS deadline_date,
    COUNT(*) AS count,
    SUM(d.calculated_tax) AS total_amount,
    json_agg(json_build_object(...)) AS deadlines
FROM tax_declarations d
WHERE d.fiscal_period_end BETWEEN $1 AND $2
GROUP BY DATE(d.fiscal_period_end);
```

**Performance:** 50-150ms

**Week View:**
```sql
SELECT
    DATE_TRUNC('week', d.fiscal_period_end)::DATE AS week_start,
    COUNT(*) AS count,
    SUM(d.calculated_tax) AS total_amount
FROM tax_declarations d
WHERE d.fiscal_period_end BETWEEN $1 AND $2
GROUP BY DATE_TRUNC('week', d.fiscal_period_end);
```

**Performance:** 30-100ms

**Month View:**
```sql
SELECT
    TO_CHAR(d.fiscal_period_end, 'YYYY-MM') AS month,
    COUNT(*) AS count,
    SUM(d.calculated_tax) AS total_amount
FROM tax_declarations d
WHERE d.fiscal_period_end BETWEEN $1 AND $2
GROUP BY TO_CHAR(d.fiscal_period_end, 'YYYY-MM');
```

**Performance:** 20-80ms

**Optimization Techniques:**
1. **DATE_TRUNC Function**
   - Built-in PostgreSQL function
   - Efficiently groups by time period
   - Can use functional indexes if needed

2. **json_agg for Day View**
   - Builds JSON array in SQL
   - Avoids N+1 queries
   - More efficient than application-layer aggregation

3. **Date Range Limit**
   - Capped at 365 days
   - Prevents excessive data
   - Returns error if exceeded

## Performance Monitoring

### Query Performance Metrics

**Track these metrics:**
```python
import time
from loguru import logger

start = time.time()
results = await repository.get_upcoming_deadlines(...)
duration = (time.time() - start) * 1000  # milliseconds

logger.info(f"Query duration: {duration:.2f}ms, rows: {len(results)}")

# Alert if slow
if duration > 500:
    logger.warning(f"SLOW QUERY: {duration:.2f}ms")
```

**Target Metrics:**
- p50 (median): <100ms
- p95: <200ms
- p99: <500ms
- Max: <1,000ms

### Database Monitoring

**Monitor these PostgreSQL stats:**
```sql
-- Query statistics
SELECT
    query,
    calls,
    mean_exec_time,
    max_exec_time,
    stddev_exec_time
FROM pg_stat_statements
WHERE query LIKE '%tax_declarations%'
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE tablename = 'tax_declarations'
ORDER BY idx_scan DESC;

-- Table statistics
SELECT
    n_tup_ins,
    n_tup_upd,
    n_tup_del,
    n_live_tup,
    n_dead_tup
FROM pg_stat_user_tables
WHERE relname = 'tax_declarations';
```

## Scalability Considerations

### Current Design (Good for)
- Up to 10,000 active declarations
- Up to 1,000 accountants
- Up to 100 companies per accountant
- Query time: <200ms

### Scaling to 100,000+ Declarations

**Option 1: Materialized Views**
```sql
CREATE MATERIALIZED VIEW accountant_deadlines_mv AS
SELECT
    cm.user_id AS accountant_id,
    d.*,
    EXTRACT(DAY FROM (d.fiscal_period_end - CURRENT_DATE))::INTEGER AS days_until_due
FROM tax_declarations d
INNER JOIN companies c ON d.company_id = c.id
INNER JOIN company_members cm ON c.id = cm.company_id
WHERE d.fiscal_period_end > CURRENT_DATE - INTERVAL '7 days'
  AND d.status NOT IN ('approved', 'rejected');

-- Refresh every hour
REFRESH MATERIALIZED VIEW CONCURRENTLY accountant_deadlines_mv;
```

**Benefits:**
- Pre-computed results
- Query time: <10ms
- Reduces CPU load

**Tradeoffs:**
- Stale data (up to 1 hour)
- Storage overhead
- Refresh time increases

**Option 2: Partitioning**
```sql
-- Partition by fiscal_period_end (year-month)
CREATE TABLE tax_declarations (
    ...
) PARTITION BY RANGE (fiscal_period_end);

CREATE TABLE tax_declarations_2025_01 PARTITION OF tax_declarations
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

CREATE TABLE tax_declarations_2025_02 PARTITION OF tax_declarations
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
```

**Benefits:**
- Faster queries (smaller partitions)
- Easier maintenance (drop old partitions)
- Better index performance

**Tradeoffs:**
- Complex setup
- Requires partition management
- Cross-partition queries slower

**Option 3: Caching**
```python
# Redis cache for frequently accessed data
cache_key = f"accountant:{user_id}:deadlines:upcoming"
cached = await redis.get(cache_key)
if cached:
    return json.loads(cached)

# Fetch from database
results = await repository.get_upcoming_deadlines(...)

# Cache for 5 minutes
await redis.setex(cache_key, 300, json.dumps(results))
```

**Benefits:**
- Dramatically faster (1-5ms)
- Reduces database load
- Easy to implement

**Tradeoffs:**
- Stale data (5 minutes)
- Cache invalidation complexity
- Memory overhead

### Recommended Scaling Strategy

**Phase 1: Current (0-10K declarations)**
- Use current indexes
- No caching needed
- Monitor query times

**Phase 2: Growth (10K-100K declarations)**
- Add Redis caching (5-minute TTL)
- Optimize indexes based on actual queries
- Consider read replicas

**Phase 3: Scale (100K+ declarations)**
- Implement materialized views
- Add partitioning if needed
- Use connection pooling
- Consider separate analytics database

## Testing Performance

### Benchmark Script
```python
import asyncio
import time
from app.modules.accountant.repositories import AccountantDeadlineRepository

async def benchmark():
    repo = AccountantDeadlineRepository()

    # Test upcoming deadlines
    start = time.time()
    results, total = await repo.get_upcoming_deadlines(
        conn=db,
        accountant_user_id="test-user-id",
        limit=100,
        offset=0,
    )
    duration = (time.time() - start) * 1000
    print(f"Upcoming: {duration:.2f}ms, rows: {len(results)}")

    # Test overdue deadlines
    start = time.time()
    results, grouped, total = await repo.get_overdue_deadlines(
        conn=db,
        accountant_user_id="test-user-id",
        limit=100,
        offset=0,
    )
    duration = (time.time() - start) * 1000
    print(f"Overdue: {duration:.2f}ms, rows: {len(results)}")

asyncio.run(benchmark())
```

### Load Testing
```bash
# Use Apache Bench for load testing
ab -n 1000 -c 10 -H "Authorization: Bearer $TOKEN" \
  "https://api.taxasge.com/api/v1/accountant/deadlines/upcoming"

# Expected results:
# Requests per second: >100
# Mean time per request: <200ms
# 99th percentile: <500ms
```

## Summary

### Critical Success Factors
1. **Indexes are mandatory** - 10-50x performance improvement
2. **Monitor query times** - Alert on slow queries (>500ms)
3. **Use CTEs and window functions** - Reduce round trips
4. **Cache aggressively** - 5-minute Redis cache for hot paths
5. **Scale horizontally** - Add read replicas before optimizing queries

### Expected Performance (with indexes)
- **Upcoming deadlines:** 50-150ms (100 rows)
- **Overdue deadlines:** 80-200ms (50 rows)
- **Calendar view:** 30-150ms (depending on aggregation)
- **Analytics:** 200-300ms (multiple queries)

### Without Indexes
- All queries: **5,000-20,000ms** (5-20 seconds)
- **DO NOT DEPLOY WITHOUT INDEXES**
