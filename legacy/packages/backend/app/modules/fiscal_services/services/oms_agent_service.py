"""OMS Agent Service — Post-payment processing for commercial license obligations.

Handles Mode A (per-line ministry routing) and Mode B (consolidated polyvalent).
Payment validation is handled by the existing treasury pipeline — NOT by this service.
"""

import logging
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from app.modules.fiscal_services.repositories.license_repository import (
    LicenseRepository,
)
from app.modules.fiscal_services.services.license_service import LicenseService

logger = logging.getLogger(__name__)

# Roles that can access OMS processing queue
OMS_PROCESSOR_ROLES = {
    # Treasury / Tesoro agents (existing, pre-OMS)
    "agent_tesoro",
    # Municipal agents (independent, Addendum 3)
    "agent_ayuntamiento",
    # Chamber agents (independent, Addendum 3)
    "agent_camara",
    # Ministry agents (Mode A per-line)
    "agent_min_comercio", "agent_min_hacienda", "agent_min_informacion",
    "agent_min_turismo", "agent_min_agricultura", "agent_min_electricidad",
    # Municipal & Chamber supervisors
    "supervisor_ayuntamiento", "supervisor_camara",
    # Ministry supervisors (Mode A per-line)
    "supervisor_min_comercio", "supervisor_min_hacienda", "supervisor_min_informacion",
    "supervisor_min_turismo", "supervisor_min_agricultura", "supervisor_min_electricidad",
    # Polyvalent (Mode B consolidated)
    "agent_oms_polyvalent",
    # TESORO supervisor (supervises polyvalent + tesoro agents)
    "supervisor_tesoro",
}

POLYVALENT_ROLES = {"agent_oms_polyvalent", "supervisor_tesoro"}

# Roles that see ALL obligations in their scope (no assignment filter)
SUPERVISOR_ROLES = {
    "supervisor_tesoro", "supervisor_ayuntamiento", "supervisor_camara",
    "supervisor_min_comercio", "supervisor_min_hacienda", "supervisor_min_informacion",
    "supervisor_min_turismo", "supervisor_min_agricultura", "supervisor_min_electricidad",
}

# Roles that process obligations independent of Mode A/B (Addendum 3).
# Municipal and chamber obligations exist on BOTH per_line and consolidated
# licenses. These agents must NOT filter by processing_mode — only by fee_type.
INDEPENDENT_FEE_ROLES = {
    "agent_ayuntamiento": "municipal",
    "supervisor_ayuntamiento": "municipal",
    "agent_camara": "chamber",
    "supervisor_camara": "chamber",
}


class OmsAgentService:
    """Service for OMS post-payment agent operations."""

    @staticmethod
    async def resolve_agent_context(conn, user_id: UUID) -> Dict:
        """Resolve agent's entity, role, and queue scope.

        Returns:
            {
                agent_profile_id, entity_id, entity_code, entity_location_id,
                region, role_code, ministry_id, is_supervisor,
                is_polyvalent: bool,
                queue_processing_mode: 'per_line' | 'consolidated',
                queue_ministry_id: int | None,
            }

        Raises ValueError if user is not an OMS processor agent.
        """
        row = await conn.fetchrow("""
            SELECT
                ap.id AS agent_profile_id,
                ap.entity_id, ap.ministry_id, ap.entity_location_id,
                ap.is_supervisor,
                e.code AS entity_code,
                el.region,
                el.city_id,
                COALESCE(el.is_main_office, false) AS is_main_office,
                r.code AS role_code
            FROM agent_profiles ap
            JOIN entities e ON e.id = ap.entity_id
            JOIN entity_locations el ON el.id = ap.entity_location_id
            JOIN users u ON u.id = ap.user_id
            JOIN roles r ON r.id = u.role_id
            WHERE ap.user_id = $1
              AND ap.is_active = true
        """, user_id)

        if not row:
            raise ValueError("No active OMS agent profile found")

        role_code = row["role_code"]
        if role_code not in OMS_PROCESSOR_ROLES:
            raise ValueError(
                f"Role '{role_code}' cannot access OMS processing queue"
            )

        is_polyvalent = role_code in POLYVALENT_ROLES
        is_supervisor = role_code in SUPERVISOR_ROLES or row["is_supervisor"]
        is_independent = role_code in INDEPENDENT_FEE_ROLES

        # Determine queue scope:
        # - Polyvalent: processing_mode='consolidated', no ministry filter
        # - Independent (ayuntamiento/camara): NO processing_mode filter, fee_type filter
        # - Ministry (Mode A): processing_mode='per_line', ministry filter
        if is_polyvalent:
            queue_mode = "consolidated"
            queue_ministry = None
            queue_fee_type = None
        elif is_independent:
            queue_mode = None  # No processing_mode filter (Addendum 3)
            queue_ministry = None  # No ministry filter (independent entity)
            queue_fee_type = INDEPENDENT_FEE_ROLES[role_code]
        else:
            queue_mode = "per_line"
            queue_ministry = row["ministry_id"]
            queue_fee_type = None

        # City scope — agents ALWAYS see only their city.
        # Only SUPERVISORS at main office get global visibility.
        # Regular agents at main office are still restricted to their city.
        is_main_office = row["is_main_office"]
        has_global_scope = is_supervisor and is_main_office
        queue_city_id = None if has_global_scope else row["city_id"]

        return {
            "agent_profile_id": row["agent_profile_id"],
            "entity_id": row["entity_id"],
            "entity_code": row["entity_code"],
            "entity_location_id": row["entity_location_id"],
            "region": row["region"],
            "city_id": row["city_id"],
            "role_code": role_code,
            "ministry_id": row["ministry_id"],
            "is_supervisor": is_supervisor,
            "is_polyvalent": is_polyvalent,
            "is_independent": is_independent,
            "is_main_office": is_main_office,
            "queue_processing_mode": queue_mode,
            "queue_ministry_id": queue_ministry,
            "queue_fee_type": queue_fee_type,
            "queue_city_id": queue_city_id,
        }

    # ==================================================================
    # Field Collection Scope (Plan P3 — INSPECTION_BUNDLE_P3_DETAIL.md)
    # ==================================================================

    @staticmethod
    def compute_collection_scope(
        oms_ctx: Dict,
    ) -> Tuple[Optional[Set[str]], Optional[int]]:
        """
        Compute the field collection scope for an OMS agent.

        Returns (allowed_fee_types, required_ministry_id):
          - allowed_fee_types: Set of fee_types the agent may collect.
                               None = no restriction (supervisor_tesoro only
                               in very specific cases, currently unused).
          - required_ministry_id: int if the agent must collect only obligations
                                  matching a specific ministry_id (ministry agents).
                                  None if no ministry filter (polyvalent,
                                  independent, or ministry_id undefined).

        Rules (Addendum 3 applied):
          - is_polyvalent (agent_oms_polyvalent, supervisor_tesoro):
              → ({'tesoro'}, None)
              Polyvalent collects tesoro across all ministries. Municipal and
              chamber obligations are ALWAYS independent (ayuntamiento/camara
              only), never collectible by polyvalent.
          - is_independent (agent_ayuntamiento → 'municipal',
                            agent_camara → 'chamber', + supervisors):
              → ({queue_fee_type}, None)
              Strict single fee_type, no ministry filter.
          - Ministry agent (agent_min_*, supervisor_min_*):
              → ({'tesoro'}, ministry_id)
              Can collect tesoro obligations of their own ministry only.
        """
        if oms_ctx.get("is_polyvalent"):
            # Addendum 3: polyvalent tesoro only (municipal/chamber always independent)
            return ({"tesoro"}, None)
        if oms_ctx.get("is_independent"):
            fee_type = oms_ctx.get("queue_fee_type")
            if not fee_type:
                # Defensive: independent role without fee_type mapping is a bug
                return (set(), None)
            return ({fee_type}, None)
        # Ministry agent (or supervisor ministry) — tesoro scoped to own ministry
        ministry_id = oms_ctx.get("ministry_id")
        return ({"tesoro"}, ministry_id)

    @staticmethod
    def check_obligations_in_scope(
        obligations: List[Dict],
        allowed_fee_types: Optional[Set[str]],
        required_ministry_id: Optional[int],
    ) -> List[Dict]:
        """
        Return the list of obligations that are OUT of the agent's scope.

        Each item has keys: {id, reason, fee_type, ministry_id}.

        Args:
            obligations: List of obligation rows (dict-like) with at least
                         'id', 'fee_type', 'ministry_id' keys.
            allowed_fee_types: Set of allowed fee_types (None = no filter).
            required_ministry_id: Required ministry_id for tesoro agents
                                  (None = no ministry filter).

        Returns:
            List of forbidden obligations with reason metadata.
            Empty list = all obligations are collectible.
        """
        forbidden: List[Dict] = []
        for o in obligations:
            obl_fee_type = o.get("fee_type")
            obl_ministry_id = o.get("ministry_id")

            # fee_type check
            if allowed_fee_types is not None and obl_fee_type not in allowed_fee_types:
                forbidden.append({
                    "id": str(o["id"]),
                    "fee_type": obl_fee_type,
                    "ministry_id": obl_ministry_id,
                    "reason": (
                        f"fee_type '{obl_fee_type}' not in agent scope "
                        f"(allowed: {sorted(allowed_fee_types) if allowed_fee_types else 'none'})"
                    ),
                })
                continue

            # ministry check (only meaningful for ministry agents with required_ministry_id)
            if required_ministry_id is not None and obl_ministry_id != required_ministry_id:
                forbidden.append({
                    "id": str(o["id"]),
                    "fee_type": obl_fee_type,
                    "ministry_id": obl_ministry_id,
                    "reason": (
                        f"ministry_id {obl_ministry_id} != agent scope "
                        f"ministry_id {required_ministry_id}"
                    ),
                })
        return forbidden

    # ==================================================================
    # Queue — Read
    # ==================================================================

    @staticmethod
    async def get_queue(
        conn, user_id: UUID,
        status: Optional[str] = None,
        fee_type: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1, page_size: int = 50,
    ) -> Tuple[List[Dict], int]:
        """Get agent's obligation queue, auto-filtered by entity scope + assignment.

        Regular agents: see only obligations assigned to them via AutoAssignmentService.
        Supervisors: see all obligations in their ministry/mode scope.
        """
        ctx = await OmsAgentService.resolve_agent_context(conn, user_id)

        # Post-payment queue: only paid (awaiting agent action) and processing
        # (routed to agent). Pre-payment statuses (pending, overdue) belong to
        # the citizen view, not the OMS agent work queue.
        status_filter = [status] if status else ["paid", "processing"]

        # Supervisors see all; independent agents (camara/ayuntamiento) see all
        # in their fee_type scope (no assignment needed). Ministry agents see
        # only their assigned obligations.
        if ctx["is_supervisor"] or ctx["is_independent"]:
            agent_profile_id = None
        else:
            agent_profile_id = ctx["agent_profile_id"]

        # Role-scoped fee_type takes priority over user-requested fee_type.
        # Independent agents (ayuntamiento=municipal, camara=chamber) are locked
        # to their fee_type — user dropdown cannot override.
        effective_fee_type = ctx["queue_fee_type"] or fee_type

        return await LicenseRepository.get_agent_queue(
            conn,
            ministry_id=ctx["queue_ministry_id"],
            processing_mode=ctx["queue_processing_mode"],
            status_filter=status_filter,
            fee_type=effective_fee_type,
            search=search,
            agent_profile_id=agent_profile_id,
            city_id=ctx["queue_city_id"],
            page=page, page_size=page_size,
        )

    @staticmethod
    async def get_queue_stats(conn, user_id: UUID) -> Dict:
        """Queue stats for agent OMS dashboard."""
        ctx = await OmsAgentService.resolve_agent_context(conn, user_id)

        agent_profile_id = None if ctx["is_supervisor"] else ctx["agent_profile_id"]

        return await LicenseRepository.get_agent_queue_stats(
            conn,
            ministry_id=ctx["queue_ministry_id"],
            processing_mode=ctx["queue_processing_mode"],
            fee_type=ctx["queue_fee_type"],
            agent_profile_id=agent_profile_id,
            city_id=ctx["queue_city_id"],
        )

    # ==================================================================
    # Supervisor — Team performance
    # ==================================================================

    @staticmethod
    async def get_team_performance(
        conn, supervisor_context: Dict,
        period_days: int = 30,
        fiscal_year: int = 2026,
    ) -> Dict:
        """Per-agent OMS performance for supervisor's team.

        Returns obligation processing metrics grouped by agent within
        the supervisor's scope (ministry/mode/fee_type).
        """
        return await LicenseRepository.get_team_performance(
            conn,
            ministry_id=supervisor_context["queue_ministry_id"],
            processing_mode=supervisor_context["queue_processing_mode"],
            fee_type=supervisor_context["queue_fee_type"],
            city_id=supervisor_context["queue_city_id"],
            period_days=period_days,
            fiscal_year=fiscal_year,
        )

    # ==================================================================
    # Queue — Processing
    # ==================================================================

    @staticmethod
    async def _validate_obligation_scope(
        conn, obligation_id: UUID, user_id: UUID,
        require_processing: bool = True,
    ) -> Tuple[Dict, Dict]:
        """Validate that an obligation is in the agent's scope (IDOR protection).

        Uses a single atomic JOIN query (obligation + license) to prevent
        TOCTOU race conditions between separate reads.

        Args:
            require_processing: If True (default), obligation must be in
                'processing' status. Set to False for read-only operations
                that need scope validation without status gating.

        Returns: (obligation, agent_context)
        Raises ValueError if obligation is not in agent's scope.
        """
        ctx = await OmsAgentService.resolve_agent_context(conn, user_id)

        # Atomic fetch with row-level lock — prevents two agents from
        # processing the same obligation concurrently (TOCTOU fix).
        # SKIP LOCKED: if another agent holds this row, return NULL
        # immediately instead of waiting (no deadlock, no contention).
        row = await conn.fetchrow("""
            SELECT lo.id, lo.license_id, lo.bundle_item_id,
                   lo.fiscal_service_id, lo.ministry_id, lo.fee_type,
                   lo.amount, lo.penalty_amount, lo.status,
                   lo.payment_id, lo.issued_document_id,
                   lo.created_at, lo.updated_at,
                   fs.name_es as service_name,
                   fs.service_code,
                   m.name_es as ministry_name,
                   cl.processing_mode as license_processing_mode
            FROM license_obligations lo
            JOIN commercial_licenses cl ON cl.id = lo.license_id
            LEFT JOIN fiscal_services fs ON lo.fiscal_service_id = fs.id
            LEFT JOIN ministries m ON lo.ministry_id = m.id
            WHERE lo.id = $1
            FOR UPDATE OF lo SKIP LOCKED
        """, obligation_id)

        if not row:
            raise ValueError(
                f"Obligation {obligation_id} not found or locked by another agent"
            )

        obligation = dict(row)
        processing_mode = obligation.pop("license_processing_mode")

        # Status check: OMS agents only process POST-PAYMENT obligations.
        # All fee_types go through paid → processing → completed (Addendum 2+3).
        # Pre-payment statuses (pending, overdue) belong to citizen flow, not agent queue.
        if require_processing:
            actionable = ("paid", "processing")
            if obligation["status"] not in actionable:
                raise ValueError(
                    f"Obligation {obligation_id} is not actionable "
                    f"(current: {obligation['status']}, expected: {actionable})"
                )

        # IDOR: verify obligation matches agent's scope
        if ctx["is_polyvalent"]:
            # Polyvalent (TESORO) processes consolidated licenses only
            if processing_mode != "consolidated":
                raise ValueError(
                    f"Obligation {obligation_id} belongs to a per_line license "
                    f"— polyvalent agents can only process consolidated obligations"
                )
        elif ctx["is_independent"]:
            # Independent agents (CAMARA/AYUNTAMIENTO) validate by fee_type
            expected_fee = ctx.get("queue_fee_type")
            if expected_fee and obligation.get("fee_type") != expected_fee:
                raise ValueError(
                    f"Obligation {obligation_id} fee_type={obligation.get('fee_type')} "
                    f"does not match agent scope fee_type={expected_fee}"
                )
        else:
            # Ministry agents (MIN_*) process per_line obligations for their ministry
            if processing_mode != "per_line":
                raise ValueError(
                    f"Obligation {obligation_id} belongs to a consolidated license "
                    f"— ministry agents can only process per_line obligations"
                )
            if obligation["ministry_id"] != ctx["queue_ministry_id"]:
                raise ValueError(
                    f"Obligation {obligation_id} belongs to ministry "
                    f"{obligation['ministry_id']}, not {ctx['queue_ministry_id']}"
                )

        return obligation, ctx

    @staticmethod
    async def process_obligation(
        conn, obligation_id: UUID, user_id: UUID,
        issued_document_id: Optional[UUID] = None,
        notes: Optional[str] = None,
    ) -> Dict:
        """Process obligation: processing -> completed.

        Validates IDOR scope, updates status, logs events, refreshes counters.
        """
        obligation, ctx = await OmsAgentService._validate_obligation_scope(
            conn, obligation_id, user_id
        )

        # Update status to completed
        update_data = {"status": "completed"}
        if issued_document_id:
            update_data["issued_document_id"] = issued_document_id

        result = await LicenseService.update_obligation_status(
            conn, obligation_id, update_data,
            user_id=user_id,
            expected_license_id=obligation["license_id"],
        )

        # Log agent_approved event
        await LicenseRepository.log_event(
            conn, obligation["license_id"], "agent_approved",
            event_data={
                "agent_role": ctx["role_code"],
                "entity_code": ctx["entity_code"],
                "notes": notes,
                "issued_document_id": (
                    str(issued_document_id) if issued_document_id else None
                ),
            },
            obligation_id=obligation_id,
            triggered_by=user_id,
        )

        if issued_document_id:
            await LicenseRepository.log_event(
                conn, obligation["license_id"], "document_issued",
                event_data={
                    "document_id": str(issued_document_id),
                    "agent_role": ctx["role_code"],
                },
                obligation_id=obligation_id,
                triggered_by=user_id,
            )

        logger.info(
            f"OMS: Obligation {obligation_id} processed by {ctx['role_code']} "
            f"({ctx['entity_code']})"
        )

        # Notify citizen of progress (async, non-blocking).
        # Individual obligation completion → push notification only
        # (email would spam for 10 obligations; full email at LICENSE_COMPLETED).
        try:
            from app.core.events import EventBus, EventType

            # Resolve company owner for push notification target
            owner_row = await conn.fetchrow("""
                SELECT u.id, u.email, u.first_name
                FROM users u
                JOIN user_company_roles ucr ON ucr.user_id = u.id
                JOIN commercial_licenses cl ON cl.company_id = ucr.company_id
                WHERE cl.id = (SELECT license_id FROM license_obligations WHERE id = $1)
                ORDER BY ucr.created_at ASC LIMIT 1
            """, obligation_id)

            if owner_row:
                EventBus.publish_nowait(EventType.OBLIGATION_PROCESSED, {
                    "obligation_id": str(obligation_id),
                    "license_id": str(obligation["license_id"]),
                    "user_id": str(owner_row["id"]),
                    "user_email": owner_row["email"],
                    "user_name": owner_row["first_name"] or "",
                    "fee_type": obligation.get("fee_type"),
                    "amount": float(obligation.get("amount", 0)),
                    "service_name": obligation.get("service_name"),
                    "agent_entity": ctx["entity_code"],
                })
        except Exception:
            pass  # Best-effort — obligation already completed

        return result

    @staticmethod
    async def reject_obligation(
        conn, obligation_id: UUID, user_id: UUID,
        reason: str,
    ) -> Dict:
        """Reject obligation: processing -> paid (re-routable).

        The obligation returns to 'paid' status and can be re-routed.
        """
        obligation, ctx = await OmsAgentService._validate_obligation_scope(
            conn, obligation_id, user_id
        )

        result = await LicenseService.update_obligation_status(
            conn, obligation_id, {"status": "paid"},
            user_id=user_id,
            expected_license_id=obligation["license_id"],
        )

        await LicenseRepository.log_event(
            conn, obligation["license_id"], "agent_rejected",
            event_data={
                "agent_role": ctx["role_code"],
                "entity_code": ctx["entity_code"],
                "reason": reason,
            },
            obligation_id=obligation_id,
            triggered_by=user_id,
        )

        logger.info(
            f"OMS: Obligation {obligation_id} rejected by {ctx['role_code']} "
            f"({ctx['entity_code']}): {reason}"
        )

        return result

    @staticmethod
    async def batch_process(
        conn, obligation_ids: List[UUID], user_id: UUID,
        issued_document_id: Optional[UUID] = None,
    ) -> Dict:
        """Batch process obligations. All must be in agent's scope.

        Optimized: 1 query for all obligations+licenses, 1 bulk UPDATE,
        batch event logging, single counter refresh per license.
        """
        if not obligation_ids:
            raise ValueError("No obligation IDs provided")
        if len(obligation_ids) > 500:
            raise ValueError("Batch size exceeds maximum of 500")

        ctx = await OmsAgentService.resolve_agent_context(conn, user_id)

        # 1. Batch-fetch all obligations with row-level lock (TOCTOU fix).
        # SKIP LOCKED: obligations being processed by another agent are
        # excluded — prevents double-processing and counter double-count.
        rows = await conn.fetch("""
            SELECT lo.id, lo.license_id, lo.ministry_id, lo.fee_type,
                   lo.amount, lo.status,
                   cl.processing_mode
            FROM license_obligations lo
            JOIN commercial_licenses cl ON cl.id = lo.license_id
            WHERE lo.id = ANY($1::uuid[])
            FOR UPDATE OF lo SKIP LOCKED
        """, obligation_ids)

        if len(rows) != len(obligation_ids):
            found = {r["id"] for r in rows}
            missing = [oid for oid in obligation_ids if oid not in found]
            raise ValueError(
                f"Obligations not found or locked by other agents: {missing}"
            )

        # 2. Validate ALL obligations before any mutation (fail-fast)
        license_ids = set()
        for row in rows:
            if row["status"] not in ("paid", "processing"):
                raise ValueError(
                    f"Obligation {row['id']} is not processable "
                    f"(current: {row['status']}, expected: paid or processing)"
                )

            if ctx["is_polyvalent"]:
                if row["processing_mode"] != "consolidated":
                    raise ValueError(
                        f"Obligation {row['id']} not in polyvalent scope"
                    )
            else:
                if row["processing_mode"] != "per_line":
                    raise ValueError(
                        f"Obligation {row['id']} not in ministry scope"
                    )
                if row["ministry_id"] != ctx["queue_ministry_id"]:
                    raise ValueError(
                        f"Obligation {row['id']} not in ministry scope"
                    )
            license_ids.add(row["license_id"])

        # 3. Bulk UPDATE (single statement, no N+1)
        update_fields = "status = 'completed', updated_at = NOW()"
        update_params = [obligation_ids]
        if issued_document_id:
            update_fields += ", issued_document_id = $2"
            update_params.append(issued_document_id)

        results = await conn.fetch(f"""
            UPDATE license_obligations
            SET {update_fields}
            WHERE id = ANY($1::uuid[])
              AND status IN ('paid', 'processing')
            RETURNING *
        """, *update_params)
        results = [dict(r) for r in results]

        # 4. Batch event logging (single INSERT)
        if results:
            event_items = [
                {
                    "obligation_id": r["id"],
                    "event_data": {
                        "agent_role": ctx["role_code"],
                        "entity_code": ctx["entity_code"],
                        "batch": True,
                        "fee_type": r["fee_type"],
                        "amount": str(r["amount"]),
                    },
                }
                for r in results
            ]
            # Group by license for batch logging
            by_license = {}
            for r in results:
                by_license.setdefault(r["license_id"], []).append({
                    "obligation_id": r["id"],
                    "event_data": {
                        "agent_role": ctx["role_code"],
                        "entity_code": ctx["entity_code"],
                        "batch": True,
                    },
                })
            for lic_id, items in by_license.items():
                await LicenseRepository.log_events_batch(
                    conn, lic_id, "agent_approved", items,
                    triggered_by=user_id,
                )

        # 5. Single counter refresh per affected license
        for lic_id in license_ids:
            await LicenseService.update_license_counters(conn, lic_id, user_id)

        logger.info(
            f"OMS: Batch processed {len(results)}/{len(obligation_ids)} "
            f"by {ctx['role_code']} ({ctx['entity_code']})"
        )

        return {"updated": len(results), "items": results}
