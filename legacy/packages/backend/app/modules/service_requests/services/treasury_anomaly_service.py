"""
Treasury Anomaly Detection Service - Enhanced Version

Automatic detection of payment anomalies:
- Duplicate payments (with time window analysis)
- Amount mismatches (configurable thresholds)
- Late validations (SLA monitoring)
- Orphan transactions
- Suspicious patterns (frequency, amounts)
- High amount transactions (statistical outliers)
- Missing references

Features:
- Configurable thresholds via class attributes or env
- Batch processing for performance
- Transaction isolation for data consistency
- Comprehensive logging and error handling
"""

import json
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
import asyncpg
from loguru import logger


class TreasuryAnomalyService:
    """Service for detecting and managing payment anomalies."""

    # Anomaly types with descriptions
    ANOMALY_TYPES = {
        "duplicate_payment": "Possible duplicate payment detected",
        "amount_mismatch": "Amount mismatch between payment and bank transaction",
        "reference_missing": "Payment reference missing or invalid",
        "orphan_transaction": "Bank transaction without matching payment",
        "late_validation": "Payment validation exceeded SLA threshold",
        "suspicious_pattern": "Suspicious payment pattern detected",
        "high_amount": "Unusually high amount transaction",
    }

    # =========================================================================
    # CONFIGURABLE THRESHOLDS (can be overridden via environment variables)
    # =========================================================================

    # SLA threshold in hours (payments taking longer trigger anomaly)
    SLA_THRESHOLD_HOURS = int(os.getenv("TREASURY_SLA_THRESHOLD_HOURS", "24"))

    # Amount mismatch threshold (percentage difference)
    AMOUNT_MISMATCH_THRESHOLD = float(os.getenv("TREASURY_AMOUNT_MISMATCH_PCT", "0.01"))  # 1%

    # High amount threshold (standard deviations above mean)
    HIGH_AMOUNT_STD_DEVIATIONS = float(os.getenv("TREASURY_HIGH_AMOUNT_STD", "3.0"))

    # High amount absolute minimum (XAF) - below this, no high_amount anomaly
    HIGH_AMOUNT_MINIMUM = float(os.getenv("TREASURY_HIGH_AMOUNT_MIN", "10000000"))  # 10M XAF

    # Duplicate detection time window (hours)
    DUPLICATE_TIME_WINDOW_HOURS = int(os.getenv("TREASURY_DUPLICATE_WINDOW_HOURS", "24"))

    # Suspicious pattern threshold (payments per user in 24h)
    SUSPICIOUS_PAYMENT_COUNT = int(os.getenv("TREASURY_SUSPICIOUS_COUNT", "5"))

    # Detection lookback period (days)
    DETECTION_LOOKBACK_DAYS = int(os.getenv("TREASURY_LOOKBACK_DAYS", "7"))

    # Batch size for processing
    BATCH_SIZE = int(os.getenv("TREASURY_BATCH_SIZE", "100"))

    def __init__(self):
        """Initialize service with configuration logging."""
        logger.info(
            f"TreasuryAnomalyService initialized - "
            f"SLA: {self.SLA_THRESHOLD_HOURS}h, "
            f"Mismatch: {self.AMOUNT_MISMATCH_THRESHOLD*100}%, "
            f"High Amount: >{self.HIGH_AMOUNT_MINIMUM:,.0f} XAF or {self.HIGH_AMOUNT_STD_DEVIATIONS} std devs"
        )

    async def run_detection(
        self,
        db: asyncpg.Connection,
        detection_types: Optional[List[str]] = None,
        entity_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run anomaly detection across all types with transaction isolation.

        Args:
            db: Database connection
            detection_types: Optional list of specific types to detect
            entity_code: Optional entity scope. None = global (all entities).
                Propagated to every _detect_* method (P8 2026-05-06,
                resolves TODO P7.D.2). When set, the detection SQL filters
                on sp.entity_code so only payments belonging to that entity
                produce anomalies.

        Returns:
            Dict with detection results by type
        """
        if entity_code:
            logger.info(f"run_detection scoped to entity_code={entity_code}")
        results = {
            "detected_at": datetime.now().isoformat(),
            "anomalies_found": 0,
            "by_type": {},
            "errors": [],
            "config": {
                "sla_threshold_hours": self.SLA_THRESHOLD_HOURS,
                "amount_mismatch_pct": self.AMOUNT_MISMATCH_THRESHOLD,
                "high_amount_min": self.HIGH_AMOUNT_MINIMUM,
                "lookback_days": self.DETECTION_LOOKBACK_DAYS,
            }
        }

        types_to_check = detection_types or list(self.ANOMALY_TYPES.keys())

        # Map detection type to method
        detection_methods = {
            "duplicate_payment": self._detect_duplicates,
            "amount_mismatch": self._detect_amount_mismatches,
            "orphan_transaction": self._detect_orphan_transactions,
            "late_validation": self._detect_late_validations,
            "suspicious_pattern": self._detect_suspicious_patterns,
            "high_amount": self._detect_high_amounts,
            "reference_missing": self._detect_missing_references,
        }

        for anomaly_type in types_to_check:
            if anomaly_type not in detection_methods:
                logger.warning(f"Unknown anomaly type: {anomaly_type}")
                continue

            try:
                logger.info(f"Running detection: {anomaly_type}")
                method = detection_methods[anomaly_type]

                # Run detection within a savepoint for isolation
                async with db.transaction():
                    found = await method(db, entity_code=entity_code)

                results["by_type"][anomaly_type] = {
                    "found": found,
                    "status": "success"
                }
                results["anomalies_found"] += found
                logger.info(f"Detection {anomaly_type} completed: {found} anomalies")

            except Exception as e:
                error_msg = f"Error detecting {anomaly_type}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                results["by_type"][anomaly_type] = {
                    "found": 0,
                    "status": "error",
                    "error": str(e)
                }
                results["errors"].append(error_msg)

        logger.info(
            f"Anomaly detection completed: {results['anomalies_found']} found, "
            f"{len(results['errors'])} errors"
        )
        return results

    async def _detect_duplicates(
        self, db: asyncpg.Connection, entity_code: Optional[str] = None
    ) -> int:
        """
        Detect potential duplicate payments with enhanced criteria.

        Criteria:
        - Same user, same amount, same service within configurable time window
        - Excludes cancelled payments
        - Groups duplicates to avoid multiple alerts for same set

        Args:
            db: Database connection
            entity_code: Optional entity scope. None = global. When set,
                filters on sp1.entity_code via parameterized query.
        """
        # Build optional entity scope clause (parameterized $1)
        entity_clause = ""
        extra_params: List[Any] = []
        if entity_code:
            entity_clause = "AND sp1.entity_code = $1"
            extra_params.append(entity_code)

        query = f"""
            WITH potential_duplicates AS (
                SELECT
                    sp1.id as payment_id,
                    sp1.payment_reference,
                    sp1.total_amount,
                    sp1.created_at,
                    sp1.payment_method,
                    sr1.user_id,
                    sr1.workflow_code,
                    sr1.id as service_request_id,
                    sr1.reference as service_request_reference,
                    -- Count duplicates within time window
                    COUNT(*) OVER (
                        PARTITION BY sr1.user_id, sp1.total_amount, sr1.workflow_code
                    ) as duplicate_count,
                    -- Get time span of potential duplicates
                    MAX(sp1.created_at) OVER (
                        PARTITION BY sr1.user_id, sp1.total_amount, sr1.workflow_code
                    ) - MIN(sp1.created_at) OVER (
                        PARTITION BY sr1.user_id, sp1.total_amount, sr1.workflow_code
                    ) as time_span,
                    -- Row number to identify first in group
                    ROW_NUMBER() OVER (
                        PARTITION BY sr1.user_id, sp1.total_amount, sr1.workflow_code
                        ORDER BY sp1.created_at
                    ) as rn
                FROM service_payments sp1
                JOIN service_requests sr1 ON sr1.id = sp1.service_request_id
                WHERE sp1.created_at > NOW() - INTERVAL '{self.DETECTION_LOOKBACK_DAYS} days'
                  AND sp1.workflow_status NOT IN ('cancelled_by_user', 'cancelled_by_agent', 'expired')
                  {entity_clause}
            )
            SELECT *
            FROM potential_duplicates
            WHERE duplicate_count > 1
              AND rn = 1  -- Only first in each group
              AND time_span < INTERVAL '{self.DUPLICATE_TIME_WINDOW_HOURS} hours'
              AND NOT EXISTS (
                SELECT 1 FROM payment_anomalies pa
                WHERE pa.entity_id = payment_id
                  AND pa.anomaly_type = 'duplicate_payment'
                  AND pa.status NOT IN ('resolved', 'false_positive')
              )
            ORDER BY created_at DESC
            LIMIT {self.BATCH_SIZE}
        """

        rows = await db.fetch(query, *extra_params)
        anomalies_created = 0

        for row in rows:
            await self._create_anomaly(
                db=db,
                entity_type="service_payment",
                entity_id=str(row["payment_id"]),
                service_request_id=str(row["service_request_id"]),
                service_request_reference=row["service_request_reference"],
                payment_reference=row["payment_reference"],
                anomaly_type="duplicate_payment",
                severity="high" if row["duplicate_count"] > 2 else "medium",
                title=f"Posible pago duplicado: {row['payment_reference']}",
                description=(
                    f"Se detectaron {row['duplicate_count']} pagos con el mismo monto "
                    f"({float(row['total_amount']):,.0f} XAF) para el mismo usuario y servicio "
                    f"en un periodo de {self.DUPLICATE_TIME_WINDOW_HOURS} horas."
                ),
                affected_amount=float(row["total_amount"]) * (row["duplicate_count"] - 1),
                related_entities={
                    "duplicate_count": row["duplicate_count"],
                    "payment_method": row["payment_method"],
                    "workflow_code": row["workflow_code"],
                },
            )
            anomalies_created += 1

        return anomalies_created

    async def _detect_amount_mismatches(
        self, db: asyncpg.Connection, entity_code: Optional[str] = None
    ) -> int:
        """
        Detect mismatches between payment amounts and bank transactions.
        Uses configurable percentage threshold.

        Args:
            db: Database connection
            entity_code: Optional entity scope. None = global. When set,
                filters on sp.entity_code via parameterized query.
        """
        # Existing param: $1 = AMOUNT_MISMATCH_THRESHOLD
        # Optional param: $2 = entity_code
        existing_params: List[Any] = [self.AMOUNT_MISMATCH_THRESHOLD]
        entity_clause = ""
        extra_params: List[Any] = []
        if entity_code:
            entity_clause = f"AND sp.entity_code = ${len(existing_params) + 1}"
            extra_params.append(entity_code)

        query = f"""
            SELECT
                sp.id as payment_id,
                sp.payment_reference,
                sp.total_amount as expected_amount,
                bt.amount as bank_amount,
                bt.id as transaction_id,
                bt.bank_reference,
                bt.bank_code,
                sr.id as service_request_id,
                sr.reference as service_request_reference,
                ABS(sp.total_amount - bt.amount) as difference,
                CASE
                    WHEN sp.total_amount > 0
                    THEN ABS(sp.total_amount - bt.amount) / sp.total_amount * 100
                    ELSE 0
                END as diff_percentage
            FROM service_payments sp
            JOIN service_requests sr ON sr.id = sp.service_request_id
            JOIN bank_transactions bt ON bt.service_payment_id = sp.id
            WHERE bt.status = 'reconciled'
              AND bt.reconciled_at > NOW() - INTERVAL '{self.DETECTION_LOOKBACK_DAYS} days'
              AND sp.total_amount > 0
              AND ABS(sp.total_amount - bt.amount) > 0
              AND ABS(sp.total_amount - bt.amount) / sp.total_amount > $1
              {entity_clause}
              AND NOT EXISTS (
                SELECT 1 FROM payment_anomalies pa
                WHERE pa.entity_id = sp.id
                  AND pa.anomaly_type = 'amount_mismatch'
                  AND pa.status NOT IN ('resolved', 'false_positive')
              )
            ORDER BY difference DESC
            LIMIT {self.BATCH_SIZE}
        """

        rows = await db.fetch(query, *existing_params, *extra_params)
        anomalies_created = 0

        for row in rows:
            diff_pct = float(row["diff_percentage"])
            severity = "low" if diff_pct < 2 else ("medium" if diff_pct < 5 else "high")

            await self._create_anomaly(
                db=db,
                entity_type="service_payment",
                entity_id=str(row["payment_id"]),
                service_request_id=str(row["service_request_id"]),
                service_request_reference=row["service_request_reference"],
                payment_reference=row["payment_reference"],
                anomaly_type="amount_mismatch",
                severity=severity,
                title=f"Diferencia de monto: {row['payment_reference']}",
                description=(
                    f"Monto esperado: {float(row['expected_amount']):,.0f} XAF, "
                    f"Monto banco: {float(row['bank_amount']):,.0f} XAF. "
                    f"Diferencia: {float(row['difference']):,.0f} XAF ({diff_pct:.2f}%)"
                ),
                affected_amount=float(row["difference"]),
                related_entities={
                    "expected_amount": float(row["expected_amount"]),
                    "bank_amount": float(row["bank_amount"]),
                    "bank_transaction_id": str(row["transaction_id"]),
                    "bank_reference": row["bank_reference"],
                    "bank_code": row["bank_code"],
                    "diff_percentage": diff_pct,
                },
            )
            anomalies_created += 1

        return anomalies_created

    async def _detect_orphan_transactions(
        self, db: asyncpg.Connection, entity_code: Optional[str] = None
    ) -> int:
        """
        Detect bank transactions without matching payments.
        Enhanced with age-based severity.

        Args:
            db: Database connection
            entity_code: Optional entity scope. NOTE: orphan bank transactions
                have NO linked service_payment by definition (status='unreconciled',
                service_payment_id IS NULL), so they cannot be attributed to any
                entity. When entity_code is set, this detection returns 0 with a
                warning log. Detection only runs globally (entity_code is None).
        """
        # Orphan transactions are not attributable to an entity (no sp link).
        # Skip detection cleanly when entity-scoped to avoid leaking
        # cross-entity anomalies into a single entity dashboard.
        if entity_code:
            logger.info(
                f"_detect_orphan_transactions skipped for entity_code={entity_code}: "
                f"orphan bank transactions have no linked service_payment, cannot be "
                f"attributed to any entity. Detection runs globally only."
            )
            return 0

        query = f"""
            SELECT
                bt.id as transaction_id,
                bt.bank_reference,
                bt.amount,
                bt.currency,
                bt.bank_code,
                bt.created_at,
                bt.account_holder_name,
                bt.bank_transaction_date,
                EXTRACT(EPOCH FROM (NOW() - bt.created_at)) / 3600 as hours_since_creation
            FROM bank_transactions bt
            WHERE bt.service_payment_id IS NULL
              AND bt.status = 'unreconciled'
              AND bt.created_at > NOW() - INTERVAL '{self.DETECTION_LOOKBACK_DAYS} days'
              AND NOT EXISTS (
                SELECT 1 FROM payment_anomalies pa
                WHERE pa.entity_id = bt.id
                  AND pa.anomaly_type = 'orphan_transaction'
                  AND pa.status NOT IN ('resolved', 'false_positive')
              )
            ORDER BY bt.amount DESC, bt.created_at DESC
            LIMIT {self.BATCH_SIZE}
        """

        rows = await db.fetch(query)
        anomalies_created = 0

        for row in rows:
            hours = int(row["hours_since_creation"])
            # Severity based on age and amount
            if hours > 72 or float(row["amount"]) > 1000000:
                severity = "high"
            elif hours > 24:
                severity = "medium"
            else:
                severity = "low"

            await self._create_anomaly(
                db=db,
                entity_type="bank_transaction",
                entity_id=str(row["transaction_id"]),
                anomaly_type="orphan_transaction",
                severity=severity,
                title=f"Transaccion huerfana: {row['bank_reference']}",
                description=(
                    f"Transaccion bancaria de {float(row['amount']):,.0f} {row['currency']} "
                    f"sin pago asociado desde hace {hours} horas. "
                    f"Banco: {row['bank_code']}. "
                    f"Titular: {row['account_holder_name'] or 'N/A'}"
                ),
                affected_amount=float(row["amount"]),
                related_entities={
                    "bank_code": row["bank_code"],
                    "bank_reference": row["bank_reference"],
                    "hours_unreconciled": hours,
                    "account_holder": row["account_holder_name"],
                },
            )
            anomalies_created += 1

        return anomalies_created

    async def _detect_late_validations(
        self, db: asyncpg.Connection, entity_code: Optional[str] = None
    ) -> int:
        """
        Detect payments that exceeded SLA threshold.
        Uses parameterized query for safety.

        Args:
            db: Database connection
            entity_code: Optional entity scope. None = global. When set,
                filters on sp.entity_code via parameterized query.
        """
        # Build optional entity scope clause (parameterized $1)
        entity_clause = ""
        extra_params: List[Any] = []
        if entity_code:
            entity_clause = "AND sp.entity_code = $1"
            extra_params.append(entity_code)

        query = f"""
            SELECT
                sp.id as payment_id,
                sp.payment_reference,
                sp.total_amount,
                sp.payment_method,
                sp.created_at,
                sp.workflow_status::text,
                sp.sla_target_date,
                sr.id as service_request_id,
                sr.reference as service_request_reference,
                EXTRACT(EPOCH FROM (NOW() - sp.created_at)) / 3600 as hours_elapsed,
                CASE
                    WHEN sp.sla_target_date IS NOT NULL
                    THEN sp.sla_target_date < NOW()
                    ELSE FALSE
                END as sla_breached
            FROM service_payments sp
            JOIN service_requests sr ON sr.id = sp.service_request_id
            WHERE sp.workflow_status IN ('pending_agent_review', 'agent_reviewing')
              AND sp.created_at < NOW() - INTERVAL '{self.SLA_THRESHOLD_HOURS} hours'
              {entity_clause}
              AND NOT EXISTS (
                SELECT 1 FROM payment_anomalies pa
                WHERE pa.entity_id = sp.id
                  AND pa.anomaly_type = 'late_validation'
                  AND pa.status NOT IN ('resolved', 'false_positive')
              )
            ORDER BY sp.created_at ASC
            LIMIT {self.BATCH_SIZE}
        """

        rows = await db.fetch(query, *extra_params)
        anomalies_created = 0

        for row in rows:
            hours = int(row["hours_elapsed"])
            # Dynamic severity based on time exceeded
            if hours >= 72 or row["sla_breached"]:
                severity = "high"
            elif hours >= 48:
                severity = "medium"
            else:
                severity = "low"

            sla_info = ""
            if row["sla_target_date"]:
                sla_info = f" SLA objetivo: {row['sla_target_date'].strftime('%d/%m/%Y %H:%M')}."

            await self._create_anomaly(
                db=db,
                entity_type="service_payment",
                entity_id=str(row["payment_id"]),
                service_request_id=str(row["service_request_id"]),
                service_request_reference=row["service_request_reference"],
                payment_reference=row["payment_reference"],
                anomaly_type="late_validation",
                severity=severity,
                title=f"Validacion tardia: {row['payment_reference']}",
                description=(
                    f"Pago pendiente hace {hours} horas (umbral SLA: {self.SLA_THRESHOLD_HOURS}h). "
                    f"Estado actual: {row['workflow_status']}.{sla_info}"
                ),
                affected_amount=float(row["total_amount"]),
                related_entities={
                    "hours_elapsed": hours,
                    "sla_threshold": self.SLA_THRESHOLD_HOURS,
                    "current_status": row["workflow_status"],
                    "payment_method": row["payment_method"],
                    "sla_breached": row["sla_breached"],
                },
            )
            anomalies_created += 1

        return anomalies_created

    async def _detect_suspicious_patterns(
        self, db: asyncpg.Connection, entity_code: Optional[str] = None
    ) -> int:
        """
        Detect suspicious payment patterns:
        - Multiple payments from same user in short time
        - Unusually high total amounts

        Args:
            db: Database connection
            entity_code: Optional entity scope. None = global. When set,
                filters on sp.entity_code via parameterized query.
        """
        # Build optional entity scope clause (parameterized $1)
        entity_clause = ""
        extra_params: List[Any] = []
        if entity_code:
            entity_clause = "AND sp.entity_code = $1"
            extra_params.append(entity_code)

        query = f"""
            WITH user_payment_frequency AS (
                SELECT
                    sr.user_id,
                    u.full_name,
                    u.email,
                    COUNT(*) as payment_count,
                    SUM(sp.total_amount) as total_amount,
                    AVG(sp.total_amount) as avg_amount,
                    MAX(sp.total_amount) as max_amount,
                    MAX(sp.id) as last_payment_id,
                    MAX(sp.payment_reference) as last_payment_ref,
                    MAX(sr.id) as last_request_id,
                    MAX(sr.reference) as last_request_ref,
                    array_agg(DISTINCT sp.payment_method) as payment_methods
                FROM service_payments sp
                JOIN service_requests sr ON sr.id = sp.service_request_id
                JOIN users u ON u.id = sr.user_id
                WHERE sp.created_at > NOW() - INTERVAL '24 hours'
                  AND sp.workflow_status NOT IN ('cancelled_by_user', 'cancelled_by_agent', 'expired')
                  {entity_clause}
                GROUP BY sr.user_id, u.full_name, u.email
                HAVING COUNT(*) >= {self.SUSPICIOUS_PAYMENT_COUNT}
            )
            SELECT *
            FROM user_payment_frequency
            WHERE NOT EXISTS (
                SELECT 1 FROM payment_anomalies pa
                WHERE pa.metadata->>'user_id' = user_id::text
                  AND pa.anomaly_type = 'suspicious_pattern'
                  AND pa.detected_at > NOW() - INTERVAL '24 hours'
                  AND pa.status NOT IN ('resolved', 'false_positive')
            )
            ORDER BY total_amount DESC
            LIMIT {self.BATCH_SIZE}
        """

        rows = await db.fetch(query, *extra_params)
        anomalies_created = 0

        for row in rows:
            payment_count = row["payment_count"]
            total_amount = float(row["total_amount"])

            # Higher severity for more payments or higher amounts
            if payment_count >= 10 or total_amount > 50000000:
                severity = "high"
            elif payment_count >= 7 or total_amount > 20000000:
                severity = "medium"
            else:
                severity = "low"

            await self._create_anomaly(
                db=db,
                entity_type="user",
                entity_id=str(row["user_id"]),
                service_request_id=str(row["last_request_id"]) if row["last_request_id"] else None,
                service_request_reference=row["last_request_ref"],
                payment_reference=row["last_payment_ref"],
                anomaly_type="suspicious_pattern",
                severity=severity,
                title=f"Patron sospechoso: {row['full_name']}",
                description=(
                    f"Usuario con {payment_count} pagos en las ultimas 24 horas. "
                    f"Monto total: {total_amount:,.0f} XAF, "
                    f"Promedio: {float(row['avg_amount']):,.0f} XAF, "
                    f"Max: {float(row['max_amount']):,.0f} XAF"
                ),
                affected_amount=total_amount,
                metadata={"user_id": str(row["user_id"])},
                related_entities={
                    "payment_count": payment_count,
                    "user_name": row["full_name"],
                    "user_email": row["email"],
                    "avg_amount": float(row["avg_amount"]),
                    "max_amount": float(row["max_amount"]),
                    "payment_methods": row["payment_methods"],
                },
            )
            anomalies_created += 1

        return anomalies_created

    async def _detect_high_amounts(
        self, db: asyncpg.Connection, entity_code: Optional[str] = None
    ) -> int:
        """
        Detect unusually high amount transactions.
        Uses statistical analysis (mean + N standard deviations).

        Args:
            db: Database connection
            entity_code: Optional entity scope. None = global. When set,
                BOTH the statistical baseline and the detection scan are
                filtered on entity_code (entity-scoped baseline so outliers
                are detected relative to the entity's own distribution,
                not the global one).
        """
        # First, calculate statistics for recent payments.
        # Entity-scoped baseline when entity_code is provided so outliers are
        # detected relative to the entity's own distribution.
        stats_entity_clause = ""
        stats_params: List[Any] = []
        if entity_code:
            stats_entity_clause = "AND entity_code = $1"
            stats_params.append(entity_code)

        stats_query = f"""
            SELECT
                AVG(total_amount) as avg_amount,
                STDDEV(total_amount) as std_amount,
                MAX(total_amount) as max_amount,
                COUNT(*) as total_count
            FROM service_payments
            WHERE created_at > NOW() - INTERVAL '30 days'
              AND workflow_status NOT IN ('cancelled_by_user', 'cancelled_by_agent', 'expired')
              AND total_amount > 0
              {stats_entity_clause}
        """

        stats = await db.fetchrow(stats_query, *stats_params)

        if not stats or not stats["std_amount"] or stats["total_count"] < 100:
            # Not enough data for statistical analysis
            logger.info(
                f"Not enough data for high amount detection (need 100+ payments)"
                f"{f' for entity_code={entity_code}' if entity_code else ''}"
            )
            return 0

        avg_amount = float(stats["avg_amount"])
        std_amount = float(stats["std_amount"])
        threshold = max(
            avg_amount + (self.HIGH_AMOUNT_STD_DEVIATIONS * std_amount),
            self.HIGH_AMOUNT_MINIMUM
        )

        logger.info(
            f"High amount threshold: {threshold:,.0f} XAF "
            f"(avg: {avg_amount:,.0f}, std: {std_amount:,.0f})"
        )

        # Existing params: $1 = avg_amount, $2 = std_amount, $3 = threshold
        # Optional param: $4 = entity_code
        existing_params: List[Any] = [avg_amount, std_amount, threshold]
        entity_clause = ""
        extra_params: List[Any] = []
        if entity_code:
            entity_clause = f"AND sp.entity_code = ${len(existing_params) + 1}"
            extra_params.append(entity_code)

        query = f"""
            SELECT
                sp.id as payment_id,
                sp.payment_reference,
                sp.total_amount,
                sp.payment_method,
                sp.created_at,
                sp.workflow_status::text,
                sr.id as service_request_id,
                sr.reference as service_request_reference,
                sr.workflow_code,
                fs.name_es as service_name,
                u.full_name as user_name,
                (sp.total_amount - $1) / NULLIF($2, 0) as std_deviations_above
            FROM service_payments sp
            JOIN service_requests sr ON sr.id = sp.service_request_id
            LEFT JOIN fiscal_services fs ON fs.id = sr.fiscal_service_id
            LEFT JOIN users u ON u.id = sr.user_id
            WHERE sp.created_at > NOW() - INTERVAL '{self.DETECTION_LOOKBACK_DAYS} days'
              AND sp.total_amount >= $3
              AND sp.workflow_status NOT IN ('cancelled_by_user', 'cancelled_by_agent', 'expired')
              {entity_clause}
              AND NOT EXISTS (
                SELECT 1 FROM payment_anomalies pa
                WHERE pa.entity_id = sp.id
                  AND pa.anomaly_type = 'high_amount'
                  AND pa.status NOT IN ('resolved', 'false_positive')
              )
            ORDER BY sp.total_amount DESC
            LIMIT {self.BATCH_SIZE}
        """

        rows = await db.fetch(query, *existing_params, *extra_params)
        anomalies_created = 0

        for row in rows:
            amount = float(row["total_amount"])
            std_devs = float(row["std_deviations_above"]) if row["std_deviations_above"] else 0

            # Severity based on how many standard deviations above
            if std_devs >= 5 or amount >= 100000000:  # 100M XAF
                severity = "critical"
            elif std_devs >= 4 or amount >= 50000000:
                severity = "high"
            else:
                severity = "medium"

            await self._create_anomaly(
                db=db,
                entity_type="service_payment",
                entity_id=str(row["payment_id"]),
                service_request_id=str(row["service_request_id"]),
                service_request_reference=row["service_request_reference"],
                payment_reference=row["payment_reference"],
                anomaly_type="high_amount",
                severity=severity,
                title=f"Monto elevado: {row['payment_reference']}",
                description=(
                    f"Pago de {amount:,.0f} XAF ({std_devs:.1f} desv. estandar sobre la media). "
                    f"Servicio: {row['service_name'][:50] if row['service_name'] else 'N/A'}. "
                    f"Usuario: {row['user_name'] or 'N/A'}"
                ),
                affected_amount=amount,
                related_entities={
                    "workflow_code": row["workflow_code"],
                    "service_name": row["service_name"],
                    "user_name": row["user_name"],
                    "payment_method": row["payment_method"],
                    "std_deviations_above": round(std_devs, 2),
                    "statistical_threshold": round(threshold, 2),
                    "avg_amount": round(avg_amount, 2),
                },
            )
            anomalies_created += 1

        return anomalies_created

    async def _detect_missing_references(
        self, db: asyncpg.Connection, entity_code: Optional[str] = None
    ) -> int:
        """
        Detect payments with missing or invalid references.

        Args:
            db: Database connection
            entity_code: Optional entity scope. None = global. When set,
                filters on sp.entity_code via parameterized query.
        """
        # Build optional entity scope clause (parameterized $1)
        entity_clause = ""
        extra_params: List[Any] = []
        if entity_code:
            entity_clause = "AND sp.entity_code = $1"
            extra_params.append(entity_code)

        query = f"""
            SELECT
                sp.id as payment_id,
                sp.payment_reference,
                sp.total_amount,
                sp.payment_method,
                sp.created_at,
                sp.workflow_status::text,
                sr.id as service_request_id,
                sr.reference as service_request_reference
            FROM service_payments sp
            JOIN service_requests sr ON sr.id = sp.service_request_id
            WHERE sp.created_at > NOW() - INTERVAL '{self.DETECTION_LOOKBACK_DAYS} days'
              AND sp.workflow_status NOT IN ('cancelled_by_user', 'cancelled_by_agent', 'expired')
              {entity_clause}
              AND (
                sp.payment_reference IS NULL
                OR sp.payment_reference = ''
                OR LENGTH(sp.payment_reference) < 5
                OR sp.payment_reference ~ '^[0]+$'  -- All zeros
              )
              AND NOT EXISTS (
                SELECT 1 FROM payment_anomalies pa
                WHERE pa.entity_id = sp.id
                  AND pa.anomaly_type = 'reference_missing'
                  AND pa.status NOT IN ('resolved', 'false_positive')
              )
            ORDER BY sp.created_at DESC
            LIMIT {self.BATCH_SIZE}
        """

        rows = await db.fetch(query, *extra_params)
        anomalies_created = 0

        for row in rows:
            ref = row["payment_reference"]
            issue = "faltante" if not ref else f"invalida ({ref})"

            await self._create_anomaly(
                db=db,
                entity_type="service_payment",
                entity_id=str(row["payment_id"]),
                service_request_id=str(row["service_request_id"]),
                service_request_reference=row["service_request_reference"],
                payment_reference=row["payment_reference"],
                anomaly_type="reference_missing",
                severity="medium",
                title=f"Referencia {issue}",
                description=(
                    f"Pago de {float(row['total_amount']):,.0f} XAF con referencia {issue}. "
                    f"Metodo: {row['payment_method']}. "
                    f"Esto puede dificultar la reconciliacion bancaria."
                ),
                affected_amount=float(row["total_amount"]),
                related_entities={
                    "current_reference": ref,
                    "payment_method": row["payment_method"],
                    "workflow_status": row["workflow_status"],
                },
            )
            anomalies_created += 1

        return anomalies_created

    async def _create_anomaly(
        self,
        db: asyncpg.Connection,
        entity_type: str,
        entity_id: str,
        anomaly_type: str,
        severity: str,
        title: str,
        description: str,
        affected_amount: Optional[float] = None,
        service_request_id: Optional[str] = None,
        service_request_reference: Optional[str] = None,
        payment_reference: Optional[str] = None,
        related_entities: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new anomaly record with proper error handling."""
        try:
            row = await db.fetchrow("""
                INSERT INTO payment_anomalies (
                    entity_type, entity_id, service_request_id, payment_reference,
                    anomaly_type, severity, status, title, description,
                    detected_by, affected_amount, related_entities, metadata
                )
                VALUES (
                    $1, $2::uuid, $3::uuid, $4,
                    $5::anomaly_type_enum, $6::anomaly_severity_enum, 'open'::anomaly_status_enum,
                    $7, $8, 'system', $9,
                    $10::jsonb, $11::jsonb
                )
                RETURNING id
            """,
                entity_type, entity_id,
                service_request_id,
                payment_reference,
                anomaly_type, severity, title, description,
                affected_amount,
                json.dumps(related_entities) if related_entities else None,
                json.dumps(metadata) if metadata else None,
            )

            anomaly_id = str(row["id"])
            logger.debug(f"Created anomaly {anomaly_id}: {anomaly_type} - {title}")
            return anomaly_id

        except Exception as e:
            logger.error(f"Failed to create anomaly: {str(e)}", exc_info=True)
            raise

    async def get_detection_stats(self, db: asyncpg.Connection) -> Dict[str, Any]:
        """Get statistics about current anomalies for monitoring."""
        query = """
            SELECT
                anomaly_type,
                status::text,
                severity::text,
                COUNT(*) as count,
                SUM(affected_amount) as total_affected
            FROM payment_anomalies
            WHERE detected_at > NOW() - INTERVAL '30 days'
            GROUP BY anomaly_type, status, severity
            ORDER BY anomaly_type, status
        """

        rows = await db.fetch(query)

        stats = {
            "by_type": {},
            "by_status": {},
            "by_severity": {},
            "total_affected_amount": 0,
        }

        for row in rows:
            atype = row["anomaly_type"]
            status = row["status"]
            severity = row["severity"]
            count = row["count"]
            amount = float(row["total_affected"] or 0)

            if atype not in stats["by_type"]:
                stats["by_type"][atype] = 0
            stats["by_type"][atype] += count

            if status not in stats["by_status"]:
                stats["by_status"][status] = 0
            stats["by_status"][status] += count

            if severity not in stats["by_severity"]:
                stats["by_severity"][severity] = 0
            stats["by_severity"][severity] += count

            stats["total_affected_amount"] += amount

        return stats


# Singleton instance
treasury_anomaly_service = TreasuryAnomalyService()
