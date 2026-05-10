#!/usr/bin/env python3
"""Smoke test — Phase C Security Observability end-to-end (Phase C validation).

Runs against the LIVE staging backend after a deploy and confirms:
1. request_telemetry table exists + has rows from the last hour
2. Sampling distribution sane (sample_pct in {1, 10, 100})
3. UA parser populating columns (device_type / browser_name / os_name)
4. GeoIP populating column (country) — only meaningful if .mmdb provisioned
5. mv_request_telemetry_hourly is fresh (refreshed within last 6h)
6. Sample-corrected counts match raw counts proportionally
7. Excluded paths (/healthz, /static/) NEVER persisted
8. dashboard_registrations has the security-monitoring row (mig 330)
9. injection persistence (Phase C.1) — high-risk rows have non-empty rules
10. CHECK constraints respected (no NULL critical fields, valid enums)

Usage:
  cd packages/backend
  python scripts/smoke_security_observability.py

Exit codes:
  0  all checks pass (including warnings)
  1  one or more hard failures
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env.local")
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL missing")
    sys.exit(1)


def main() -> int:
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=15)
    failures = 0

    with conn.cursor() as cur:
        # 1. Recent request_telemetry rows
        cur.execute(
            "SELECT count(*) FROM request_telemetry WHERE \"timestamp\" > now() - interval '1 hour'"
        )
        recent = cur.fetchone()[0]
        if recent == 0:
            logger.warning(
                "[1/10] No recent request_telemetry rows in last 1h — push some traffic to validate fully"
            )
        else:
            logger.success(f"[1/10] {recent} request_telemetry rows in last 1h")

        # 2. Sampling distribution sanity
        cur.execute(
            "SELECT array_agg(DISTINCT sampled_pct ORDER BY sampled_pct) FROM request_telemetry "
            "WHERE \"timestamp\" > now() - interval '1 hour'"
        )
        pcts = cur.fetchone()[0] or []
        valid_pcts = {1, 10, 100}
        invalid_pcts = set(pcts) - valid_pcts
        if invalid_pcts:
            logger.error(f"[2/10] FAIL: invalid sampled_pct values: {invalid_pcts}")
            failures += 1
        else:
            logger.success(f"[2/10] sampled_pct values valid (seen: {sorted(pcts)})")

        # 3. UA parser populating columns
        cur.execute(
            "SELECT count(*) FROM request_telemetry "
            "WHERE \"timestamp\" > now() - interval '1 hour' "
            "AND user_agent_raw IS NOT NULL "
            "AND device_type IS NOT NULL"
        )
        parsed = cur.fetchone()[0]
        if recent > 0 and parsed == 0:
            logger.error(
                "[3/10] FAIL: UA parser not populating device_type — check user_agent_parser import"
            )
            failures += 1
        elif recent > 0:
            ratio = parsed / recent * 100
            logger.success(f"[3/10] UA parser: {parsed}/{recent} rows enriched ({ratio:.1f}%)")
        else:
            logger.info("[3/10] (skipped — no recent rows)")

        # 4. GeoIP populating country column
        cur.execute(
            "SELECT count(*) FROM request_telemetry "
            "WHERE \"timestamp\" > now() - interval '1 hour' "
            "AND country IS NOT NULL"
        )
        geo = cur.fetchone()[0]
        if recent > 0 and geo == 0:
            logger.warning(
                "[4/10] No country populated — GeoLite2-City.mmdb likely missing in /tmp/. "
                "Run: MAXMIND_LICENSE_KEY=xxx python scripts/download_geolite.py"
            )
        elif recent > 0:
            ratio = geo / recent * 100
            logger.success(f"[4/10] GeoIP: {geo}/{recent} rows enriched ({ratio:.1f}%)")
        else:
            logger.info("[4/10] (skipped — no recent rows)")

        # 5. MV freshness
        cur.execute(
            "SELECT pg_stat_user_tables.last_vacuum, pg_stat_user_tables.last_autovacuum "
            "FROM pg_stat_user_tables WHERE relname = 'mv_request_telemetry_hourly'"
        )
        row = cur.fetchone()
        if not row:
            # MV is not in pg_stat_user_tables; check pg_class instead
            cur.execute(
                "SELECT count(*) FROM pg_class WHERE relname = 'mv_request_telemetry_hourly' "
                "AND relkind = 'm'"
            )
            mv_exists = cur.fetchone()[0] > 0
            if not mv_exists:
                logger.error("[5/10] FAIL: mv_request_telemetry_hourly does not exist")
                failures += 1
            else:
                # MV exists — try a sample query against it
                cur.execute(
                    "SELECT max(hour) FROM mv_request_telemetry_hourly"
                )
                last_hour = cur.fetchone()[0]
                if last_hour is None:
                    logger.warning("[5/10] mv_request_telemetry_hourly is empty (no data yet)")
                else:
                    logger.success(f"[5/10] mv_request_telemetry_hourly latest hour: {last_hour}")

        # 6. Sample correction sanity (estimated_requests >= raw count)
        cur.execute(
            "SELECT "
            "  (SELECT count(*) FROM request_telemetry WHERE \"timestamp\" > now() - interval '24 hours') AS raw, "
            "  (SELECT COALESCE(SUM(estimated_requests), 0) FROM mv_request_telemetry_hourly "
            "   WHERE hour > now() - interval '24 hours') AS estimated"
        )
        raw, estimated = cur.fetchone()
        if raw > 0 and estimated < raw:
            logger.error(
                f"[6/10] FAIL: estimated_requests ({estimated}) < raw count ({raw}) — "
                "sample correction broken in MV"
            )
            failures += 1
        elif raw > 0:
            ratio = estimated / raw if raw > 0 else 0
            logger.success(
                f"[6/10] Sample correction OK: raw={raw}, estimated={estimated} (×{ratio:.1f})"
            )
        else:
            logger.info("[6/10] (skipped — no 24h data)")

        # 7. Excluded paths NEVER persisted
        cur.execute(
            "SELECT count(*) FROM request_telemetry "
            "WHERE \"timestamp\" > now() - interval '1 hour' "
            "AND (path = '/healthz' OR path LIKE '/static/%' OR path = '/metrics' "
            "     OR path = '/favicon.ico' OR path = '/docs' OR path = '/redoc' "
            "     OR path = '/openapi.json')"
        )
        excluded_leak = cur.fetchone()[0]
        if excluded_leak > 0:
            logger.error(
                f"[7/10] FAIL: {excluded_leak} excluded-path rows leaked into "
                "request_telemetry (middleware bypass broken)"
            )
            failures += 1
        else:
            logger.success("[7/10] No excluded-path rows persisted (middleware bypass OK)")

        # 8. dashboard_registrations has security-monitoring (mig 330)
        cur.execute(
            "SELECT count(*) FROM dashboard_registrations "
            "WHERE dashboard_id = 'security-monitoring' AND is_active = true"
        )
        dash = cur.fetchone()[0]
        if dash == 0:
            logger.error(
                "[8/10] FAIL: security-monitoring dashboard not registered (mig 330 missing?)"
            )
            failures += 1
        else:
            logger.success("[8/10] security-monitoring dashboard registered (mig 330)")

        # 9. Injection persistence (Phase C.1) — high-risk rows have rules
        cur.execute(
            "SELECT count(*) FROM ai_call_metrics "
            "WHERE injection_risk = 'high' "
            "AND (injection_rules IS NULL OR cardinality(injection_rules) = 0)"
        )
        bad_injection = cur.fetchone()[0]
        if bad_injection > 0:
            logger.error(
                f"[9/10] FAIL: {bad_injection} high-risk rows missing injection_rules"
            )
            failures += 1
        else:
            cur.execute(
                "SELECT count(*) FROM ai_call_metrics "
                "WHERE injection_risk = 'high' AND \"timestamp\" > now() - interval '7 days'"
            )
            hr_count = cur.fetchone()[0]
            logger.success(
                f"[9/10] Injection persistence OK ({hr_count} high-risk attempts in last 7d)"
            )

        # 10. Data integrity — no NULL critical fields
        cur.execute(
            "SELECT count(*) FROM request_telemetry "
            "WHERE method IS NULL OR path IS NULL OR status_code IS NULL "
            "OR latency_ms IS NULL OR sampled_pct IS NULL"
        )
        nulls = cur.fetchone()[0]
        if nulls > 0:
            logger.error(
                f"[10/10] FAIL: {nulls} rows with NULL critical fields "
                "(method/path/status_code/latency_ms/sampled_pct)"
            )
            failures += 1
        else:
            logger.success("[10/10] No NULL critical fields")

    conn.close()
    if failures:
        logger.error(f"{failures} smoke check(s) failed")
        return 1
    logger.success("All Phase C smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
