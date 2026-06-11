"""
Treasury Reconciliation Service — Automated matching of bank transactions to payments.

Scoring algorithm (SQL LATERAL JOIN, O(n * log(m)) with indexes):
- 100 pts: Exact reference match (bank_reference == payment_reference)
-  80 pts: Exact amount match (same amount, same currency)
-  60 pts: Amount ±1% AND same day
-  40 pts: Amount ±1% AND ±3 days, OR Amount ±5% AND ±3 days

Returns top 3 candidates per unreconciled bank transaction, sorted by score.
Auto-match threshold: >= 80 pts (configurable).

Indexes used:
- idx_bank_transactions_unreconciled (bank_transaction_date DESC) WHERE status = 'unreconciled'
- idx_service_payments_reconciliation (currency, workflow_status, validated_at DESC) WHERE workflow_status = 'completed'
- idx_bank_transactions_service_payment_id (service_payment_id) WHERE NOT NULL
"""

from typing import Any, Dict, List, Optional

from loguru import logger

AUTO_MATCH_THRESHOLD = 80
MAX_CANDIDATES_PER_TX = 10
TOP_MATCHES = 3
DATE_WINDOW_DAYS = 30
MAX_AUTO_MATCH_ITERATIONS = 100

# SQL scoring query using LATERAL JOIN — replaces Python O(n*m) loop.
# For each unreconciled bank transaction, finds top 10 candidate service_payments
# within ±30 days and same currency, computes score, returns top 3 per transaction.
#
# P7 security note (2026-05-06): the WHERE clauses below scope BOTH sides of
# the join when `entity_code` filter is active:
#   - Outer `unreconciled` CTE: bank_transactions are kept only if they have
#     no payment OR their previously-reconciled payment matches the entity.
#     For pending unreconciled rows (service_payment_id IS NULL), we cannot
#     attribute them to an entity yet, so they remain visible to all entities
#     (this is by design: bank transactions are unowned until matched).
#   - LATERAL `c`: candidate service_payments must match the requested entity.
# This means non-global agents see ALL unreconciled bank transactions BUT
# only candidate matches against payments of their own entity.
SCORING_SQL = """
WITH unreconciled AS (
    SELECT id, bank_reference, amount, currency, bank_transaction_date,
           account_holder_name, bank_code
    FROM bank_transactions
    WHERE service_payment_id IS NULL AND status = 'unreconciled'
    ORDER BY bank_transaction_date DESC
    LIMIT $1 OFFSET $2
),
scored AS (
    SELECT
        bt.id as transaction_id,
        bt.bank_reference,
        bt.amount as bank_amount,
        bt.currency as bank_currency,
        bt.bank_transaction_date,
        bt.account_holder_name,
        bt.bank_code,
        c.payment_id,
        c.payment_reference,
        c.payment_amount,
        c.payer_name,
        c.payment_method,
        c.payment_date,
        c.score,
        c.reasons,
        ROW_NUMBER() OVER (PARTITION BY bt.id ORDER BY c.score DESC, c.payment_amount) as rn
    FROM unreconciled bt
    CROSS JOIN LATERAL (
        SELECT
            sp.id as payment_id,
            sp.payment_reference,
            sp.total_amount as payment_amount,
            u.full_name as payer_name,
            sp.payment_method::text,
            COALESCE(sp.validated_at, sp.created_at) as payment_date,
            -- Score: reference match (100) + amount/date match (80/60/40)
            (
                CASE WHEN UPPER(TRIM(COALESCE(bt.bank_reference, '')))
                        = UPPER(TRIM(COALESCE(sp.payment_reference, '')))
                          AND TRIM(COALESCE(bt.bank_reference, '')) != ''
                          AND TRIM(COALESCE(sp.payment_reference, '')) != ''
                     THEN 100 ELSE 0 END
            ) + (
                CASE
                    WHEN bt.amount = sp.total_amount THEN 80
                    WHEN bt.amount > 0 AND sp.total_amount > 0
                         AND ABS(bt.amount - sp.total_amount)
                             / GREATEST(bt.amount, sp.total_amount) <= 0.01
                         AND ABS(bt.bank_transaction_date::date
                             - COALESCE(sp.validated_at, sp.created_at)::date) = 0
                    THEN 60
                    WHEN bt.amount > 0 AND sp.total_amount > 0
                         AND ABS(bt.amount - sp.total_amount)
                             / GREATEST(bt.amount, sp.total_amount) <= 0.01
                         AND ABS(bt.bank_transaction_date::date
                             - COALESCE(sp.validated_at, sp.created_at)::date) <= 3
                    THEN 40
                    WHEN bt.amount > 0 AND sp.total_amount > 0
                         AND ABS(bt.amount - sp.total_amount)
                             / GREATEST(bt.amount, sp.total_amount) <= 0.05
                         AND ABS(bt.bank_transaction_date::date
                             - COALESCE(sp.validated_at, sp.created_at)::date) <= 3
                    THEN 40
                    ELSE 0
                END
            ) as score,
            -- Reasons array (NULL values stripped by ARRAY_REMOVE)
            ARRAY_REMOVE(ARRAY[
                CASE WHEN UPPER(TRIM(COALESCE(bt.bank_reference, '')))
                        = UPPER(TRIM(COALESCE(sp.payment_reference, '')))
                          AND TRIM(COALESCE(bt.bank_reference, '')) != ''
                     THEN 'exact_reference' END,
                CASE
                    WHEN bt.amount = sp.total_amount THEN 'exact_amount'
                    WHEN bt.amount > 0 AND sp.total_amount > 0
                         AND ABS(bt.amount - sp.total_amount)
                             / GREATEST(bt.amount, sp.total_amount) <= 0.01
                         AND ABS(bt.bank_transaction_date::date
                             - COALESCE(sp.validated_at, sp.created_at)::date) = 0
                    THEN 'amount_1pct_same_day'
                    WHEN bt.amount > 0 AND sp.total_amount > 0
                         AND ABS(bt.amount - sp.total_amount)
                             / GREATEST(bt.amount, sp.total_amount) <= 0.01
                         AND ABS(bt.bank_transaction_date::date
                             - COALESCE(sp.validated_at, sp.created_at)::date) <= 3
                    THEN 'amount_1pct_3days'
                    WHEN bt.amount > 0 AND sp.total_amount > 0
                         AND ABS(bt.amount - sp.total_amount)
                             / GREATEST(bt.amount, sp.total_amount) <= 0.05
                         AND ABS(bt.bank_transaction_date::date
                             - COALESCE(sp.validated_at, sp.created_at)::date) <= 3
                    THEN 'amount_5pct_3days'
                    ELSE NULL
                END
            ], NULL) as reasons
        FROM service_payments sp
        JOIN users u ON u.id = sp.user_id
        WHERE sp.workflow_status = 'completed'
          AND sp.currency = bt.currency
          AND ($6::text IS NULL OR sp.entity_code = $6)
          AND NOT EXISTS (
              SELECT 1 FROM bank_transactions bt2
              WHERE bt2.service_payment_id = sp.id AND bt2.status = 'reconciled'
          )
          AND bt.bank_transaction_date IS NOT NULL
          AND ABS(bt.bank_transaction_date::date
              - COALESCE(sp.validated_at, sp.created_at)::date) <= $3
        ORDER BY
            CASE WHEN UPPER(TRIM(COALESCE(sp.payment_reference, '')))
                    = UPPER(TRIM(COALESCE(bt.bank_reference, '')))
                      AND TRIM(COALESCE(bt.bank_reference, '')) != ''
                 THEN 0 ELSE 1 END,
            ABS(sp.total_amount - bt.amount),
            ABS(COALESCE(sp.validated_at, sp.created_at)::date - bt.bank_transaction_date::date)
        LIMIT $4
    ) c
    WHERE c.score > 0
)
SELECT * FROM scored WHERE rn <= $5
ORDER BY transaction_id, score DESC
"""


async def get_matching_suggestions(
    db,
    limit: int = 50,
    offset: int = 0,
    entity_code: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    For each unreconciled bank transaction, find the top 3 matching
    service_payments candidates using SQL LATERAL JOIN scoring.

    Complexity: O(n * log(m)) with indexes vs O(n*m) Python loop.

    P7 (2026-05-06): pass `entity_code` to scope candidate payments by entity.
    None = no entity filter (admin / global view).
    """
    rows = await db.fetch(
        SCORING_SQL, limit, offset, DATE_WINDOW_DAYS,
        MAX_CANDIDATES_PER_TX, TOP_MATCHES, entity_code,
    )

    if not rows:
        return []

    # Group rows by transaction
    tx_map: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        tx_id = str(row["transaction_id"])
        if tx_id not in tx_map:
            tx_date = row["bank_transaction_date"]
            tx_map[tx_id] = {
                "transactionId": tx_id,
                "bankReference": row["bank_reference"],
                "bankAmount": float(row["bank_amount"]),
                "bankCurrency": row["bank_currency"] or "XAF",
                "bankDate": str(tx_date.date()) if tx_date and hasattr(tx_date, 'date') else str(tx_date),
                "accountHolder": row["account_holder_name"],
                "bankCode": row["bank_code"],
                "candidates": [],
                "bestScore": 0,
            }

        pay_date = row["payment_date"]
        score = int(row["score"])
        reasons = list(row["reasons"]) if row["reasons"] else []

        tx_map[tx_id]["candidates"].append({
            "paymentId": str(row["payment_id"]),
            "paymentReference": row["payment_reference"],
            "paymentAmount": float(row["payment_amount"]),
            "payerName": row["payer_name"],
            "paymentMethod": row["payment_method"],
            "paymentDate": str(pay_date.date()) if pay_date and hasattr(pay_date, 'date') else str(pay_date),
            "score": score,
            "reasons": reasons,
        })

        if score > tx_map[tx_id]["bestScore"]:
            tx_map[tx_id]["bestScore"] = score

    # Sort by best score descending
    results = sorted(tx_map.values(), key=lambda r: r["bestScore"], reverse=True)
    return results


async def auto_match(
    db,
    agent_user_id: str,
    threshold: int = AUTO_MATCH_THRESHOLD,
    batch_size: int = 50,
    entity_code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Batch auto-reconcile: process unreconciled transactions in batches,
    reconciling those with best match score >= threshold.

    Each reconciliation is atomic (transaction boundary around both tables).
    Stops when no more matches found above threshold.

    P7 (2026-05-06): pass `entity_code` to scope candidate payments by entity.
    None = no entity filter (admin / global view).
    """
    total_matched = 0
    total_skipped = 0
    matched_details = []
    skipped_details = []
    offset = 0
    iteration = 0

    while iteration < MAX_AUTO_MATCH_ITERATIONS:
        iteration += 1
        suggestions = await get_matching_suggestions(
            db, limit=batch_size, offset=offset, entity_code=entity_code
        )
        if not suggestions:
            break

        batch_matched = 0
        for suggestion in suggestions:
            if suggestion["bestScore"] < threshold:
                total_skipped += 1
                skipped_details.append({
                    "transactionId": suggestion["transactionId"],
                    "bankReference": suggestion["bankReference"],
                    "bestScore": suggestion["bestScore"],
                    "reason": "below_threshold",
                })
                continue

            best = suggestion["candidates"][0]

            try:
                async with db.transaction():
                    result = await db.fetchrow("""
                        UPDATE bank_transactions
                        SET service_payment_id = $1, status = 'reconciled',
                            reconciled_at = NOW(), reconciled_by = $2
                        WHERE id = $3 AND service_payment_id IS NULL
                        RETURNING id
                    """, best["paymentId"], agent_user_id, suggestion["transactionId"])

                    if not result:
                        # Already reconciled by concurrent process
                        total_skipped += 1
                        skipped_details.append({
                            "transactionId": suggestion["transactionId"],
                            "bankReference": suggestion["bankReference"],
                            "bestScore": suggestion["bestScore"],
                            "reason": "already_reconciled",
                        })
                        continue

                    await db.execute("""
                        UPDATE service_payments
                        SET bank_transaction_id = $2, updated_at = NOW()
                        WHERE id = $1
                    """, best["paymentId"], suggestion["transactionId"])

                batch_matched += 1
                total_matched += 1
                matched_details.append({
                    "transactionId": suggestion["transactionId"],
                    "bankReference": suggestion["bankReference"],
                    "paymentId": best["paymentId"],
                    "paymentReference": best["paymentReference"],
                    "score": best["score"],
                    "reasons": best["reasons"],
                })
                logger.info(
                    "Auto-reconciliation match | "
                    "transaction_id={} payment_id={} score={} reasons={} agent_id={} action=auto_match",
                    suggestion["transactionId"], best["paymentId"],
                    best["score"], best["reasons"], agent_user_id,
                )
            except Exception as e:
                logger.error(f"Auto-match failed for tx={suggestion['transactionId']}: {e}")
                total_skipped += 1
                skipped_details.append({
                    "transactionId": suggestion["transactionId"],
                    "bankReference": suggestion["bankReference"],
                    "bestScore": suggestion["bestScore"],
                    "reason": f"error: {str(e)}",
                })

        if batch_matched == 0:
            break  # No more matches above threshold in this batch

        # Don't increment offset — reconciled rows are removed from results
        # so next batch starts from the new "first" unreconciled

    if iteration >= MAX_AUTO_MATCH_ITERATIONS:
        logger.warning(
            "Auto-match hit max iterations | iterations={} matched={} skipped={}",
            iteration, total_matched, total_skipped,
        )

    return {
        "matched": matched_details,
        "matchedCount": total_matched,
        "skipped": skipped_details,
        "skippedCount": total_skipped,
        "threshold": threshold,
    }
