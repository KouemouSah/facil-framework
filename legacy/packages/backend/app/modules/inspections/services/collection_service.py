"""Collection Service — Field payment with unified dossier per commercial_license.

ARCHITECTURE (migration 291 — plan INSPECTION_BUNDLE_P1_DETAIL.md):
  1 commercial_license ↔ 1 service_request (1:1 lazy-create)
  1 service_request   ↔ N service_payments (citizen + field + office)

Field collection flow:
  1. Validate inspection ownership + obligations (UPPERCASE enum)
  2. SET LOCAL lock_timeout + statement_timeout (D5)
  3. SELECT commercial_licenses FOR UPDATE (root lock, D5)
  4. Find company owner for service_request.user_id
  5. Find or lazy-create service_request via _find_or_create_bundle_dossier
  6. INSERT service_payment (chk_service_request_required satisfied)
  7. UPDATE license_obligations SET status='payment_pending' (D2 — NOT paid)
  8. UPDATE field_inspections
  9. INSERT license_compliance_events (event_type='payment_initiated')
 10. POST-TRANSACTION: EventBus + audit_logs (best-effort)
 11. Supervisor validates via POST /inspections/reconcile/supervisor/{id}/validate
    → LicenseService.on_payment_completed → payment_pending → paid → routing

OWASP compliance:
  A01: agent_id == inspection.agent_id (access control)
  A03: Decimal amount == sum(obligations) (injection prevention)
  A04: payment_collected check prevents double payment
  A04: Double validation — agent collects, supervisor approves
  A05: service_request_id always set (FK constraint satisfied via lazy-create)
  A08: SHA integrity not applicable (cash, not digital signature)
  A09: audit_logs + license_compliance_events + EventBus for full traceability

Concurrency:
  - Root lock on commercial_licenses (FOR UPDATE) — serializes all agents
  - Safety net: partial UNIQUE index idx_sr_commercial_license_unique
  - UniqueViolationError recovery is deterministic (no retry/backoff — D3)
  - Transaction-scoped timeouts: lock_timeout=3s, statement_timeout=5s
"""

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
from uuid import UUID, uuid4

import asyncpg

from app.core.events import EventBus, EventType
from app.modules.fiscal_services.services.oms_agent_service import OmsAgentService
from app.modules.inspections.repositories.inspection_repository import (
    InspectionRepository,
)

logger = logging.getLogger(__name__)


def _normalize_amount(val) -> Decimal:
    """Normalize to 2 decimal places."""
    if val is None:
        return Decimal("0.00")
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class CollectionService:
    """Field payment collection with 1:1 unified dossier per commercial_license."""

    # ═══════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    async def _resolve_agent_entity_code(
        conn: asyncpg.Connection, user_id: UUID,
    ) -> Optional[str]:
        """Fetch the entity_code of the agent's active profile."""
        row = await conn.fetchrow(
            """
            SELECT e.code
            FROM agent_profiles ap
            JOIN entities e ON e.id = ap.entity_id
            WHERE ap.user_id = $1 AND ap.is_active = true
            LIMIT 1
            """,
            user_id,
        )
        return row["code"] if row else None

    @staticmethod
    async def _find_or_create_bundle_dossier(
        conn: asyncpg.Connection,
        license_id: UUID,
        company_owner_user_id: UUID,
    ) -> UUID:
        """
        Find or lazy-create service_request for a commercial_license (1:1).

        Must be called inside an active transaction where commercial_licenses
        has already been locked via SELECT FOR UPDATE by the caller (D5).

        The UNIQUE partial index `idx_sr_commercial_license_unique` (migration 291)
        is a safety net against race conditions. Recovery on UniqueViolationError
        is deterministic — no retry/backoff (D3).

        Args:
            conn: active asyncpg connection (must be inside transaction
                  with commercial_licenses row already locked)
            license_id: commercial_licenses.id
            company_owner_user_id: user_id of company_owner (NOT the agent)

        Returns:
            service_request UUID (existing or newly created)

        Raises:
            ValueError: if license not found
        """
        # The license row MUST already be locked by the caller via FOR UPDATE
        # (see collect_field_payment step 3). We re-read it here to access
        # bundle_id / fiscal_year / service_request_id without re-locking.
        row = await conn.fetchrow(
            """
            SELECT id, company_id, bundle_id, fiscal_year, service_request_id
            FROM commercial_licenses
            WHERE id = $1
            """,
            license_id,
        )
        if not row:
            raise ValueError(f"License {license_id} not found")

        # Reuse existing dossier (1:1 lazy)
        if row["service_request_id"]:
            logger.info(
                "Reusing existing service_request %s for license %s",
                row["service_request_id"], license_id,
            )
            return row["service_request_id"]

        # Lazy create — reference auto-generated by trigger trg_sr_auto_reference
        # (patched in migration 291 → will produce 'FLD-YYYY-NNNNN')
        new_id = uuid4()
        try:
            await conn.execute(
                """
                INSERT INTO service_requests (
                    id, user_id, company_id,
                    workflow_code, status, source,
                    commercial_license_id, bundle_id, fiscal_year,
                    created_at, updated_at
                ) VALUES (
                    $1, $2, $3,
                    'FIELD_INSPECTION', 'SUBMITTED', 'field_inspection',
                    $4, $5, $6,
                    NOW(), NOW()
                )
                """,
                new_id, company_owner_user_id, row["company_id"],
                license_id, row["bundle_id"], row["fiscal_year"],
            )
        except asyncpg.UniqueViolationError:
            # Safety net per D3: UNIQUE partial index idx_sr_commercial_license_unique
            # caught a concurrent insert. Recover deterministically (no retry).
            existing = await conn.fetchval(
                """
                SELECT id FROM service_requests
                WHERE commercial_license_id = $1
                LIMIT 1
                """,
                license_id,
            )
            if existing is None:
                # Different unique violation — not our partial index
                raise
            logger.warning(
                "UniqueViolationError recovered for license %s → existing SR %s",
                license_id, existing,
            )
            return existing

        # Link back from commercial_licenses (also enforced by trigger
        # trg_sync_license_sr_id, but explicit here for defensive clarity)
        await conn.execute(
            """
            UPDATE commercial_licenses
            SET service_request_id = $1, updated_at = NOW()
            WHERE id = $2
            """,
            new_id, license_id,
        )

        logger.info(
            "Created service_request %s for license %s (company=%s, bundle=%s, year=%d)",
            new_id, license_id, row["company_id"], row["bundle_id"], row["fiscal_year"],
        )
        return new_id

    # ═══════════════════════════════════════════════════════════════
    # MAIN ENTRY POINT
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    async def collect_field_payment(
        conn: asyncpg.Connection,
        inspection_id: UUID,
        user_id: UUID,
        obligation_ids: List[UUID],
        method: str,
        amount: Decimal,
        phone_number: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """
        Collect field payment and attach to unified 1:1 dossier.

        Full flow per plan §2.2 / §2.3 (INSPECTION_BUNDLE_P1_DETAIL.md).
        Transaction-scoped timeouts prevent indefinite blocking (D5).
        """
        # ── Step 1: Validate (outside transaction, read-only) ─────────

        inspection = await InspectionRepository.get_by_id(conn, inspection_id)
        if not inspection:
            raise ValueError(f"Inspection {inspection_id} not found")

        # OWASP A01: Access control
        if inspection["agent_id"] != user_id:
            raise ValueError("Cannot collect payment on another agent's inspection")

        if not obligation_ids:
            raise ValueError("At least one obligation ID is required")

        # OWASP A04: Prevent double payment
        if inspection.get("payment_collected"):
            raise ValueError("Payment already collected for this inspection")

        if method == "mobile_money" and not phone_number:
            raise ValueError("Phone number required for mobile money")

        # ── Transactional section ─────────────────────────────────────

        payment_id = uuid4()
        payment_ref: str = ""
        service_request_id: UUID
        base_amount: Decimal
        penalties: Decimal
        received: Decimal
        company_id: UUID
        fee_type: Optional[str] = None
        ministry_id: Optional[int] = None

        async with conn.transaction():
            # D5: Transaction-scoped timeouts
            await conn.execute("SET LOCAL lock_timeout = '3s'")
            await conn.execute("SET LOCAL statement_timeout = '5s'")

            # ── Step 2: Validate obligations are payable ──────────────
            obls = await conn.fetch(
                """
                SELECT lo.id, lo.status, lo.amount, lo.penalty_amount, lo.fee_type,
                       lo.license_id, lo.ministry_id
                FROM license_obligations lo
                WHERE lo.id = ANY($1::uuid[])
                  AND lo.license_id = $2
                ORDER BY lo.fee_type
                """,
                obligation_ids, inspection["license_id"],
            )

            if len(obls) != len(obligation_ids):
                found_ids = {o["id"] for o in obls}
                missing = [str(oid) for oid in obligation_ids if oid not in found_ids]
                raise ValueError(f"Obligations not found: {missing}")

            uncollectable = [o for o in obls if o["status"] not in ("pending", "overdue")]
            if uncollectable:
                raise ValueError(
                    f"Obligations must be pending/overdue. "
                    f"Invalid: {[str(o['id']) for o in uncollectable]}"
                )

            # Plan P3 — D2: agent fee_type/ministry scope check (OWASP A04)
            # Prevents an agent from collecting obligations outside their
            # entity's responsibility (ex: MIN_AGRICULTURA cannot collect
            # municipal obligations, only AYUNTAMIENTO can).
            try:
                oms_ctx = await OmsAgentService.resolve_agent_context(conn, user_id)
            except ValueError as exc:
                raise PermissionError(
                    f"User {user_id} is not an OMS agent, cannot collect bundle payments: {exc}"
                ) from exc

            allowed_fee_types, required_ministry_id = (
                OmsAgentService.compute_collection_scope(oms_ctx)
            )
            forbidden_obligations = OmsAgentService.check_obligations_in_scope(
                obls, allowed_fee_types, required_ministry_id,
            )
            if forbidden_obligations:
                forbidden_ids = [f["id"] for f in forbidden_obligations]
                logger.warning(
                    "Field collection blocked — agent %s (role=%s) out of scope for "
                    "obligations %s",
                    user_id, oms_ctx.get("role_code"), forbidden_ids,
                )
                raise PermissionError(
                    f"Agent (role={oms_ctx.get('role_code')}) cannot collect these "
                    f"obligations out of fee_type/ministry scope: {forbidden_ids}"
                )

            # OWASP A03: Amount must exactly match obligations
            base_amount = sum(
                (_normalize_amount(o["amount"]) for o in obls),
                start=Decimal("0.00"),
            )
            penalties = sum(
                (_normalize_amount(o["penalty_amount"]) for o in obls),
                start=Decimal("0.00"),
            )
            expected = base_amount + penalties
            received = _normalize_amount(amount)

            if received != expected:
                raise ValueError(
                    f"Amount mismatch: expected {expected} XAF, received {received} XAF"
                )

            ministry_id = obls[0]["ministry_id"]
            fee_type = obls[0]["fee_type"]

            # ── Step 3: LOCK commercial_licenses (D5 root lock) ────────
            license_row = await conn.fetchrow(
                """
                SELECT id, company_id, bundle_id, fiscal_year
                FROM commercial_licenses
                WHERE id = $1
                FOR UPDATE
                """,
                inspection["license_id"],
            )
            if not license_row:
                raise ValueError("License not found")
            company_id = license_row["company_id"]

            # ── Step 4: Find company owner ────────────────────────────
            owner = await conn.fetchrow(
                """
                SELECT u.id AS user_id, u.email, u.full_name, u.phone_number
                FROM user_company_roles ucr
                JOIN users u ON u.id = ucr.user_id
                WHERE ucr.company_id = $1
                  AND ucr.role = 'company_owner'
                  AND ucr.is_active = true
                LIMIT 1
                """,
                company_id,
            )
            payment_user_id = owner["user_id"] if owner else user_id

            # ── Step 5: Lazy-create or reuse 1:1 dossier ──────────────
            service_request_id = await CollectionService._find_or_create_bundle_dossier(
                conn,
                license_id=license_row["id"],
                company_owner_user_id=payment_user_id,
            )

            # ── Step 6: INSERT service_payment ────────────────────────
            seq = await conn.fetchval("SELECT nextval('field_receipt_seq')")
            payment_ref = f"FLD-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{seq:05d}"

            entity_code = inspection.get("entity_code")
            if not entity_code:
                entity_code = await CollectionService._resolve_agent_entity_code(
                    conn, user_id,
                )

            await conn.execute(
                """
                INSERT INTO service_payments (
                    id, payment_reference, user_id, company_id,
                    service_request_id,
                    payment_type, base_amount, penalties, discounts, total_amount,
                    payment_method, currency, status, workflow_status,
                    entity_code, ministry_id, fee_type,
                    collection_type, collected_by, field_inspection_id,
                    supporting_documents,
                    created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4,
                    $5,
                    'full', $6, $7, 0, $8,
                    $9, 'XAF', 'pending', 'field_collected',
                    $10, $11, $12,
                    'field', $13, $14,
                    $15,
                    NOW(), NOW()
                )
                """,
                payment_id,           # $1
                payment_ref,          # $2
                payment_user_id,      # $3
                company_id,           # $4
                service_request_id,   # $5 ← unified 1:1 dossier
                base_amount,          # $6
                penalties,            # $7
                received,             # $8
                method,               # $9
                entity_code,          # $10
                ministry_id,          # $11
                fee_type,             # $12
                user_id,              # $13 collected_by
                inspection_id,        # $14 field_inspection_id
                json.dumps({          # $15 supporting_documents
                    "inspection_id": str(inspection_id),
                    "obligation_ids": [str(oid) for oid in obligation_ids],
                    "phone_number": phone_number,
                    "notes": notes,
                    "fee_types": list({o["fee_type"] for o in obls}),
                }),
            )

            # ── Step 7: Obligations → payment_pending (D2) ────────────
            # Agent creates in payment_pending; supervisor validates to 'paid'
            # via POST /inspections/reconcile/supervisor/{payment_id}/validate
            # which calls LicenseService.on_payment_completed() → paid → routing.
            await conn.execute(
                """
                UPDATE license_obligations
                SET status = 'payment_pending',
                    payment_id = $1,
                    updated_at = NOW()
                WHERE id = ANY($2::uuid[])
                  AND status IN ('pending', 'overdue')
                """,
                payment_id, obligation_ids,
            )

            # ── Step 8: Update inspection ─────────────────────────────
            await InspectionRepository.update(conn, inspection_id, {
                "payment_collected": True,
                "payment_amount": amount,
                "payment_id": payment_id,
                "payment_receipt_number": payment_ref,
            })

            # ── Step 9: Compliance event (audit trail bundle) ─────────
            await conn.execute(
                """
                INSERT INTO license_compliance_events (
                    license_id, event_type, event_data,
                    triggered_by, created_at
                ) VALUES (
                    $1, 'payment_initiated', $2::jsonb,
                    $3, NOW()
                )
                """,
                license_row["id"],
                json.dumps({
                    "source": "field_inspection",
                    "inspection_id": str(inspection_id),
                    "service_request_id": str(service_request_id),
                    "payment_id": str(payment_id),
                    "payment_reference": payment_ref,
                    "obligation_ids": [str(oid) for oid in obligation_ids],
                    "amount": float(received),
                    "method": method,
                    "collected_by": str(user_id),
                }),
                user_id,
            )

        # ── Post-transaction: non-atomic side effects ─────────────────

        # OWASP A09: EventBus notification (best-effort)
        try:
            EventBus.publish_nowait(EventType.PAYMENT_CASH_PENDING, {
                "payment_id": str(payment_id),
                "payment_reference": payment_ref,
                "inspection_id": str(inspection_id),
                "service_request_id": str(service_request_id),
                "company_name": inspection.get("company_name"),
                "amount": float(received),
                "method": method,
                "user_id": str(payment_user_id) if owner else None,
                "user_email": owner["email"] if owner else None,
                "user_name": owner["full_name"] if owner else None,
            })
        except Exception as e:
            logger.warning(f"Field collection event emission failed: {e}")

        # OWASP A09: Legacy audit_logs (parallel to license_compliance_events)
        # Uses new_values JSONB column (not 'details' — verified BD 2026-04-11)
        try:
            await conn.execute(
                """
                INSERT INTO audit_logs (
                    user_id, action, entity_type, entity_id, new_values, created_at
                ) VALUES (
                    $1, 'FIELD_COLLECTION', 'service_payment', $2, $3, NOW()
                )
                """,
                user_id, str(payment_id), json.dumps({
                    "inspection_id": str(inspection_id),
                    "amount": float(received),
                    "method": method,
                    "obligation_count": len(obligation_ids),
                    "service_request_id": str(service_request_id),
                    "payment_reference": payment_ref,
                }),
            )
        except Exception as e:
            logger.warning(f"Audit log failed (non-blocking): {e}")

        logger.info(
            "Field collection OK: %s — %s XAF (%s), %d obls, dossier=%s, inspection=%s",
            payment_ref, received, method, len(obligation_ids),
            service_request_id, inspection_id,
        )

        return {
            "method": method,
            "payment_id": str(payment_id),
            "payment_reference": payment_ref,
            "service_request_id": str(service_request_id),
            "amount": float(received),
            "obligation_count": len(obligation_ids),
            "status": "field_collected",
        }
