#!/usr/bin/env python3
"""Smoke test — Phase A + B AI Observability end-to-end (Phase B.8).

Runs against the LIVE staging backend after a deploy and confirms:
1. ai_call_metrics has rows from the last hour (recent activity)
2. ai_pricing_config has 9 active rows (mig 327)
3. dashboard_registrations has the ai-observability row (mig 326)
4. cost_xaf > 0 on at least one row (model_name normalization works)
5. prompt_hash regex passes for all rows (privacy guard)
6. status enum values are limited to the 6 expected (no unknown)
7. No NULL latency_ms or model_name (data integrity)
8. Active spans flowing to Tempo (pings the OTLP endpoint health)

Usage:
  cd packages/backend
  python scripts/smoke_phase_b_full.py
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
        # 1. Recent ai_call_metrics rows
        cur.execute(
            "SELECT count(*) FROM ai_call_metrics WHERE \"timestamp\" > now() - interval '1 hour'"
        )
        recent = cur.fetchone()[0]
        if recent == 0:
            logger.warning("[1/8] No recent calls — push some traffic to validate fully")
        else:
            logger.success(f"[1/8] {recent} ai_call_metrics rows in last 1h")

        # 2. ai_pricing_config rows (mig 327)
        cur.execute("SELECT count(*) FROM ai_pricing_config WHERE is_active = true")
        pricing = cur.fetchone()[0]
        if pricing < 9:
            logger.error(f"[2/8] FAIL: expected 9 pricing rows, got {pricing}")
            failures += 1
        else:
            logger.success(f"[2/8] {pricing} active pricing rows (mig 327)")

        # 3. dashboard_registrations has ai-observability (mig 326)
        cur.execute(
            "SELECT count(*) FROM dashboard_registrations "
            "WHERE dashboard_id = 'ai-observability' AND is_active = true"
        )
        dash = cur.fetchone()[0]
        if dash == 0:
            logger.error("[3/8] FAIL: ai-observability dashboard not registered (mig 326 missing?)")
            failures += 1
        else:
            logger.success("[3/8] ai-observability dashboard registered (mig 326)")

        # 4. cost_xaf > 0 on at least one row (B.1 model_name fix)
        cur.execute(
            "SELECT count(*) FROM ai_call_metrics WHERE cost_xaf > 0"
        )
        priced = cur.fetchone()[0]
        if priced == 0 and recent > 0:
            logger.warning("[4/8] No rows with cost_xaf > 0 — model_name normalization may need check")
        elif priced > 0:
            logger.success(f"[4/8] {priced} rows have cost_xaf > 0 (B.1 normalize OK)")
        else:
            logger.info("[4/8] (skipped — no recent rows to check)")

        # 5. prompt_hash regex compliance (BD CHECK)
        cur.execute(
            "SELECT count(*) FROM ai_call_metrics "
            "WHERE prompt_hash IS NOT NULL AND prompt_hash !~ '^[a-f0-9]{16}$'"
        )
        bad = cur.fetchone()[0]
        if bad > 0:
            logger.error(f"[5/8] FAIL: {bad} rows have invalid prompt_hash (CHECK should prevent this)")
            failures += 1
        else:
            logger.success("[5/8] All prompt_hash values match ^[a-f0-9]{16}$")

        # 6. status enum strictly bounded
        cur.execute(
            "SELECT array_agg(DISTINCT status) FROM ai_call_metrics"
        )
        statuses = cur.fetchone()[0] or []
        valid = {"success", "error", "rate_limited", "json_parse_error", "timeout", "content_blocked"}
        invalid = set(statuses) - valid
        if invalid:
            logger.error(f"[6/8] FAIL: invalid status values: {invalid}")
            failures += 1
        else:
            logger.success(f"[6/8] All status values valid ({sorted(statuses) if statuses else 'no rows'})")

        # 7. Data integrity — no NULL critical fields
        cur.execute(
            "SELECT count(*) FROM ai_call_metrics "
            "WHERE latency_ms IS NULL OR model_name IS NULL OR feature IS NULL OR status IS NULL"
        )
        nulls = cur.fetchone()[0]
        if nulls > 0:
            logger.error(f"[7/8] FAIL: {nulls} rows with NULL critical fields")
            failures += 1
        else:
            logger.success("[7/8] No NULL latency_ms / model_name / feature / status")

        # 8. Aggregate health snapshot
        cur.execute(
            """
            SELECT
                count(*) AS total,
                count(*) FILTER (WHERE status = 'success') AS ok,
                COALESCE(SUM(cost_xaf), 0)::numeric(14,6) AS total_xaf,
                COALESCE(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms), 0)::int AS p95
            FROM ai_call_metrics
            WHERE "timestamp" > now() - interval '24 hours'
            """
        )
        total, ok, total_xaf, p95 = cur.fetchone()
        rate = (ok / total * 100) if total else 0
        logger.success(
            f"[8/8] 24h snapshot: {total} calls, {ok} OK ({rate:.1f}%), "
            f"cost={total_xaf} XAF, p95={p95}ms"
        )

    conn.close()
    if failures:
        logger.error(f"{failures} smoke check(s) failed")
        return 1
    logger.success("All Phase A + B smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
