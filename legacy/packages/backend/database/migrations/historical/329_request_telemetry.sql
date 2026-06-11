-- =============================================================================
-- Migration 329 — request_telemetry table + hourly MV (Phase C.2)
-- =============================================================================
-- Created: 2026-05-05
-- Plan reference: .claude/plans/SECURITY_OBSERVABILITY_PLAN.md §C.2
--
-- Persists every HTTP request hitting facil-backend with IP / device / geo /
-- timing data. Powers the security-monitoring dashboard (Phase C.5) +
-- 4 security alert rules (IP spike, failed-login burst, etc.).
--
-- Volume protection (decision §1.D):
--   - errors (status >= 400) sampled at 100%
--   - new IPs / new user_ids in last hour sampled at 100%
--   - successes from known IPs sampled at 10% (steady-state)
--   - bots sampled at 1% (noise reduction)
-- The app middleware decides; this schema just stores `sampled_pct` so
-- aggregations multiply for accurate metrics.
--
-- Retention:
--   - raw rows: 30 days (cleanup cron every 6h)
--   - hourly MV mv_request_telemetry_hourly: 90 days (auto-refresh)
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS request_telemetry (
    id              bigserial PRIMARY KEY,
    "timestamp"     timestamptz NOT NULL DEFAULT now(),
    trace_id        text,
    -- Identity
    user_id         uuid REFERENCES users(id) ON DELETE SET NULL,
    user_role       text,
    session_id      text,
    -- Request
    method          text NOT NULL,
    path            text NOT NULL,
    status_code     int,
    latency_ms      int,
    request_bytes   int DEFAULT 0,
    response_bytes  int DEFAULT 0,
    -- Network
    ip_address      inet,
    -- UA parsed (filled by C.3 user_agent_parser)
    device_type     text,
    browser_name    text,
    browser_version text,
    os_name         text,
    os_version      text,
    is_bot          boolean DEFAULT false,
    -- GeoIP (filled by C.4 geoip module)
    geo_country     text,
    geo_country_name text,
    geo_city        text,
    geo_lat         numeric(8,5),
    geo_lon         numeric(8,5),
    geo_subdivision text,
    -- Raw bounded
    user_agent      text,
    referer         text,
    sampled_pct     numeric(5,2) DEFAULT 100.0,
    -- Security flags
    is_suspicious   boolean DEFAULT false,
    suspicious_reasons text[],
    -- Audit
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_rt_method CHECK (method IN ('GET','POST','PUT','PATCH','DELETE','OPTIONS','HEAD')),
    CONSTRAINT chk_rt_status CHECK (status_code IS NULL OR (status_code >= 100 AND status_code < 600)),
    CONSTRAINT chk_rt_latency CHECK (latency_ms IS NULL OR latency_ms >= 0),
    CONSTRAINT chk_rt_bytes CHECK (
        (request_bytes IS NULL OR request_bytes >= 0)
        AND (response_bytes IS NULL OR response_bytes >= 0)
    ),
    CONSTRAINT chk_rt_device CHECK (device_type IS NULL OR device_type IN ('mobile','desktop','tablet','bot','unknown')),
    CONSTRAINT chk_rt_country CHECK (geo_country IS NULL OR length(geo_country) <= 5),
    CONSTRAINT chk_rt_sampled_pct CHECK (sampled_pct > 0 AND sampled_pct <= 100)
);

COMMENT ON TABLE request_telemetry IS
    'Per-request HTTP telemetry: IP, device, geo, timing. Phase C.2 (mig 329). Source for security-monitoring dashboard + DDoS/brute-force alerts. RGPD: 30-day retention raw rows; aggregations preserved via mv_request_telemetry_hourly.';

-- ---------------------------------------------------------------------------
-- Indexes designed for the dashboard panels (§C.5)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_rt_timestamp     ON request_telemetry ("timestamp" DESC);
CREATE INDEX IF NOT EXISTS idx_rt_ip_time       ON request_telemetry (ip_address, "timestamp" DESC);
CREATE INDEX IF NOT EXISTS idx_rt_user_time     ON request_telemetry (user_id, "timestamp" DESC) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_rt_status_errors ON request_telemetry (status_code, "timestamp" DESC) WHERE status_code >= 400;
CREATE INDEX IF NOT EXISTS idx_rt_device_time   ON request_telemetry (device_type, "timestamp" DESC);
CREATE INDEX IF NOT EXISTS idx_rt_geo_time      ON request_telemetry (geo_country, "timestamp" DESC) WHERE geo_country IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_rt_suspicious    ON request_telemetry ("timestamp" DESC) WHERE is_suspicious = true;
CREATE INDEX IF NOT EXISTS idx_rt_trace         ON request_telemetry (trace_id) WHERE trace_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Hourly rollup MV (refreshed by cron — see §C.2.2)
-- ---------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_request_telemetry_hourly AS
SELECT
    date_trunc('hour', "timestamp")  AS hour,
    geo_country,
    device_type,
    user_role,
    method,
    -- Aggregates (multiply by 100/sampled_pct for accurate counts)
    sum((100.0 / sampled_pct))::bigint                        AS request_count_est,
    count(*)                                                   AS request_count_raw,
    count(DISTINCT ip_address)                                 AS unique_ips,
    count(DISTINCT user_id) FILTER (WHERE user_id IS NOT NULL) AS unique_users,
    sum((status_code >= 400)::int)                             AS error_count,
    sum((status_code >= 500)::int)                             AS server_error_count,
    sum(is_bot::int)                                           AS bot_count,
    sum(is_suspicious::int)                                    AS suspicious_count,
    percentile_cont(0.50) WITHIN GROUP (ORDER BY latency_ms)   AS p50_latency_ms,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)   AS p95_latency_ms,
    percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms)   AS p99_latency_ms,
    sum(response_bytes)                                        AS total_response_bytes
FROM request_telemetry
WHERE "timestamp" > now() - interval '90 days'
GROUP BY 1,2,3,4,5;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_rth_pk
    ON mv_request_telemetry_hourly (hour, geo_country, device_type, user_role, method);

GRANT SELECT ON request_telemetry TO looker_readonly;
GRANT SELECT ON mv_request_telemetry_hourly TO looker_readonly;

COMMIT;

-- VERIFICATION:
--   \d request_telemetry
--   SELECT count(*) FROM request_telemetry;  -- 0 expected at install
--   SELECT relname, relkind FROM pg_class WHERE relname LIKE 'mv_request%';
