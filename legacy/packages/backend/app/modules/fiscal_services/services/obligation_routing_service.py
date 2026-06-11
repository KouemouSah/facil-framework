"""Obligation Routing Service — Post-payment routing for license obligations.

Determines where an obligation goes after payment validation:
- TESORO (Mode A per_line): paid → processing (routed to specific ministry agent)
- TESORO (Mode B consolidated): paid → processing (routed to polyvalent agent)
- MUNICIPAL: paid → processing (routed to AYUNTAMIENTO agent) — ALWAYS independent
- CHAMBER: paid → processing (routed to CAMARA_COMERCIO agent) — ALWAYS independent

Addendum 2+3 (2026-03-20): ALL fee_types go through agent processing.
Ayuntamiento and Cámara are ALWAYS independent regardless of Mode A/B.
Mode A/B only affects TESORO routing (per-ministry vs polyvalent).
"""

import logging
from typing import Dict, List, Optional
from uuid import UUID

from app.modules.fiscal_services.repositories.license_repository import (
    LicenseRepository,
)

logger = logging.getLogger(__name__)


class ObligationRoutingService:
    """Determines where an obligation goes after payment validation."""

    @staticmethod
    def resolve_target_status(fee_type: str) -> str:
        """Return the target status after payment validation.

        Args:
            fee_type: 'tesoro', 'municipal', or 'chamber'

        Returns:
            'processing' — ALL fee_types routed to their respective entity agent.
            Addendum 3: Ayuntamiento/Cámara ALWAYS have their own agent workflow,
            never auto-completed.
        """
        # All obligations go through agent processing (Addendum 2+3, 2026-03-20)
        return "processing"

    @staticmethod
    async def resolve_target_entity(
        conn, obligation: Dict, license_row: Dict
    ) -> Optional[Dict]:
        """Resolve which entity processes this obligation post-payment.

        Addendum 3 (2026-03-20): Mode A/B only affects TESORO routing.
        Ayuntamiento and Cámara are ALWAYS independent.

        Routing rules:
          municipal → AYUNTAMIENTO (always, regardless of mode)
          chamber   → CAMARA_COMERCIO (always, regardless of mode)
          tesoro + Mode A (per_line)     → MIN_HACIENDA / MIN_COMERCIO / etc. (by ministry_id)
          tesoro + Mode B (consolidated) → TESORO polyvalent (single agent handles all)

        Returns:
            {entity_code, ministry_id, routing_mode} — always non-None
        """
        fee_type = obligation["fee_type"]

        # --- Municipal: ALWAYS routed to AYUNTAMIENTO (Addendum 3) ---
        if fee_type == "municipal":
            return {
                "entity_code": "AYUNTAMIENTO",
                "ministry_id": None,
                "routing_mode": "independent",
            }

        # --- Chamber: ALWAYS routed to CAMARA_COMERCIO (Addendum 3) ---
        if fee_type == "chamber":
            return {
                "entity_code": "CAMARA_COMERCIO",
                "ministry_id": None,
                "routing_mode": "independent",
            }

        # --- Tesoro (or unknown fee_type — treated as tesoro): ---
        if fee_type != "tesoro":
            logger.warning(
                "Unknown fee_type '%s' on obligation %s — treating as tesoro",
                fee_type,
                obligation.get("id"),
            )
        processing_mode = license_row.get("processing_mode", "per_line")

        if processing_mode == "consolidated":
            # Mode B: polyvalent agent at TESORO handles all tesoro obligations
            return {
                "entity_code": "TESORO",
                "ministry_id": None,
                "routing_mode": "consolidated",
            }

        # Mode A (per_line): route by ministry_id to specific ministry entity
        ministry_id = obligation.get("ministry_id")
        if not ministry_id:
            logger.warning(
                "Obligation %s has fee_type=tesoro but no ministry_id "
                "— falling back to TESORO entity",
                obligation["id"],
            )
            return {
                "entity_code": "TESORO",
                "ministry_id": None,
                "routing_mode": "per_line_fallback",
            }

        # Resolve entity_code from ministry_id.
        # Exclude TESORO (polyvalent, Mode B only) — prefer MIN_* entity for per_line.
        # Example: ministry_id=91 has both TESORO and MIN_HACIENDA → prefer MIN_HACIENDA.
        entity_row = await conn.fetchrow(
            """SELECT code FROM entities
               WHERE ministry_id = $1 AND code != 'TESORO'
               LIMIT 1""",
            ministry_id,
        )
        if not entity_row:
            # Fallback: try without TESORO exclusion (edge case)
            entity_row = await conn.fetchrow(
                "SELECT code FROM entities WHERE ministry_id = $1 LIMIT 1",
                ministry_id,
            )
        entity_code = entity_row["code"] if entity_row else "TESORO"
        if not entity_row:
            logger.warning(
                "No entity found for ministry_id=%s on obligation %s "
                "— falling back to TESORO",
                ministry_id,
                obligation["id"],
            )

        return {
            "entity_code": entity_code,
            "ministry_id": ministry_id,
            "routing_mode": "per_line",
        }

    @staticmethod
    async def route_paid_obligations(
        conn,
        obligations: List[Dict],
        license_row: Dict,
        user_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """Route a batch of paid obligations to their target entities + create assignments.

        For each obligation:
        1. Determine target status ('processing') and target entity
        2. Update obligation status
        3. Log routing event
        4. Create assignment for the target entity's agent (per-obligation)

        After all obligations:
        5. Refresh license counters (once per affected license)

        Assignment architecture:
          - item_id = obligation.id, item_type = 'obligation_processing'
          - Direct call to AutoAssignmentService (not outbox, because outbox
            has UNIQUE constraint per service_request and OMS needs N assignments
            for N entities on 1 service_request)
          - Each entity's agent gets assigned their obligation(s) independently
          - Agents process; supervisors coordinate and can process too

        Returns list of updated obligation dicts.
        """
        from app.modules.fiscal_services.services.license_service import LicenseService

        updated = []
        license_ids = set()

        # Pre-cache entity_locations to avoid N+1 queries in assignment loop.
        location_cache = await ObligationRoutingService._preload_entity_locations(
            conn, license_row.get("city_id")
        )

        # Pre-instantiate AutoAssignmentService once (avoids N re-instantiations)
        try:
            from app.modules.assignment.services.auto_assignment_service import (
                AutoAssignmentService,
            )
            auto_assignment_svc = AutoAssignmentService()
        except Exception:
            auto_assignment_svc = None
            logger.warning("AutoAssignmentService unavailable — assignments will be skipped")

        for obl in obligations:
            target_status = ObligationRoutingService.resolve_target_status(
                obl["fee_type"]
            )
            target_entity = await ObligationRoutingService.resolve_target_entity(
                conn, obl, license_row
            )

            # 1. Update obligation status: paid → processing
            update_data = {"status": target_status}
            result = await LicenseService.update_obligation_status(
                conn,
                obl["id"],
                update_data,
                user_id=user_id,
                expected_license_id=obl["license_id"],
                _skip_counter_refresh=True,
            )

            if result:
                updated.append(result)
                license_ids.add(obl["license_id"])

            # 2. Log payment_validated event
            await LicenseRepository.log_event(
                conn,
                obl["license_id"],
                "payment_validated",
                event_data={
                    "fee_type": obl["fee_type"],
                    "amount": str(obl["amount"]),
                    "payment_id": str(obl.get("payment_id")),
                },
                obligation_id=obl["id"],
                triggered_by=user_id,
            )

            # 3. Log routing event
            if target_entity:
                await LicenseRepository.log_event(
                    conn,
                    obl["license_id"],
                    "obligation_routed",
                    event_data={
                        "target_entity": target_entity["entity_code"],
                        "routing_mode": target_entity["routing_mode"],
                        "ministry_id": target_entity.get("ministry_id"),
                        "fee_type": obl["fee_type"],
                    },
                    obligation_id=obl["id"],
                    triggered_by=user_id,
                )

            # 4. Create assignment for target entity agent
            if target_entity and result and auto_assignment_svc:
                await ObligationRoutingService._create_obligation_assignment(
                    conn,
                    obligation=obl,
                    license_row=license_row,
                    target_entity=target_entity,
                    user_id=user_id,
                    location_cache=location_cache,
                    auto_assignment_svc=auto_assignment_svc,
                )

            logger.info(
                "OMS routing: obligation %s → %s → entity %s "
                "(fee_type=%s, mode=%s)",
                obl["id"],
                target_status,
                target_entity["entity_code"] if target_entity else "NONE",
                obl["fee_type"],
                license_row.get("processing_mode", "unknown"),
            )

        # 5. Single counter refresh per affected license
        for lic_id in license_ids:
            await LicenseService.update_license_counters(conn, lic_id, user_id)

        return updated

    @staticmethod
    async def _preload_entity_locations(
        conn, company_city_id: Optional[UUID] = None
    ) -> Dict[str, Optional[UUID]]:
        """Pre-load entity_locations for all OMS entities in 1 query.

        Returns dict: entity_code → best entity_location_id.
        Prefers location matching company's city; falls back to main office.
        """
        rows = await conn.fetch(
            """SELECT entity_code, id, city_id, is_main_office
               FROM entity_locations
               WHERE is_active = true
                 AND entity_code IN (
                     SELECT code FROM entities
                     WHERE workflow_codes @> '"BUNDLE_PAYMENT"'::jsonb
                 )
               ORDER BY is_main_office DESC NULLS LAST"""
        )

        # Build: entity_code → {city_match: id, main_office: id}
        by_entity: Dict[str, Dict[str, UUID]] = {}
        for r in rows:
            ec = r["entity_code"]
            if ec not in by_entity:
                by_entity[ec] = {}
            if company_city_id and r["city_id"] == company_city_id:
                by_entity[ec]["city_match"] = r["id"]
            if r["is_main_office"] and "main_office" not in by_entity[ec]:
                by_entity[ec]["main_office"] = r["id"]
            if "fallback" not in by_entity[ec]:
                by_entity[ec]["fallback"] = r["id"]

        # Resolve: prefer city_match > main_office > fallback
        cache: Dict[str, Optional[UUID]] = {}
        for ec, locs in by_entity.items():
            cache[ec] = (
                locs.get("city_match")
                or locs.get("main_office")
                or locs.get("fallback")
            )

        return cache

    @staticmethod
    async def _create_obligation_assignment(
        conn,
        obligation: Dict,
        license_row: Dict,
        target_entity: Dict,
        user_id: Optional[UUID] = None,
        location_cache: Optional[Dict[str, Optional[UUID]]] = None,
        auto_assignment_svc=None,
    ) -> None:
        """Create an assignment for a routed obligation.

        Uses AutoAssignmentService directly (same pattern as assignment_outbox_service.py
        line 324). Cannot use the outbox because its UNIQUE constraint on service_request_id
        prevents multiple entries for different entities on the same request.

        Args:
            conn: Database connection (within existing transaction)
            obligation: Obligation dict (id, fee_type, amount, license_id, etc.)
            license_row: License dict (service_request_id, processing_mode, city_id, etc.)
            target_entity: Routing result (entity_code, ministry_id, routing_mode)
            user_id: User who triggered the payment
            location_cache: Pre-loaded entity_code → entity_location_id mapping
            auto_assignment_svc: Pre-instantiated AutoAssignmentService (avoids N re-instantiations)
        """
        try:
            if not auto_assignment_svc:
                from app.modules.assignment.services.auto_assignment_service import (
                    AutoAssignmentService,
                )
                auto_assignment_svc = AutoAssignmentService()

            obligation_id = obligation["id"]
            if isinstance(obligation_id, str):
                obligation_id = UUID(obligation_id)

            entity_code = target_entity["entity_code"]

            # Use pre-cached location (0 queries) instead of per-obligation lookup
            entity_location_id = (
                location_cache.get(entity_code) if location_cache else None
            )

            assignment = await auto_assignment_svc.auto_assign_item(
                db=conn,
                item_id=obligation_id,
                item_type="obligation_processing",
                item_data={
                    "workflow_code": "BUNDLE_PAYMENT",
                    "entity_code": entity_code,
                    "fee_type": obligation["fee_type"],
                    "amount": str(obligation.get("amount", 0)),
                    "license_id": str(obligation.get("license_id", "")),
                    "service_request_id": str(
                        license_row.get("service_request_id", "")
                    ),
                    "routing_mode": target_entity.get("routing_mode", ""),
                    "ministry_id": str(target_entity.get("ministry_id") or ""),
                },
                entity_type="entity",
                priority_level=5,
                entity_code=entity_code,
                entity_location_id=entity_location_id,
            )

            if assignment:
                agent_profile_id = getattr(assignment, "agent_profile_id", None)
                logger.info(
                    "OMS assignment created: obligation %s → agent %s (entity %s)",
                    obligation["id"],
                    agent_profile_id or "unknown",
                    entity_code,
                )

                # Notify the assigned agent (email) about the new obligation
                if agent_profile_id:
                    await ObligationRoutingService._notify_agent_new_obligation(
                        conn,
                        agent_profile_id=agent_profile_id,
                        obligation=obligation,
                        license_row=license_row,
                        entity_code=entity_code,
                    )
            else:
                logger.warning(
                    "OMS assignment: no available agent for obligation %s "
                    "at entity %s — obligation stays in 'processing' until "
                    "manual assignment or next auto-assign cycle",
                    obligation["id"],
                    entity_code,
                )

        except Exception as e:
            # Assignment failure must NOT block the routing transaction.
            # The obligation is already in 'processing' status — a supervisor
            # or cron job can pick it up later.
            logger.error(
                "OMS assignment failed for obligation %s → entity %s: %s",
                obligation.get("id"),
                target_entity.get("entity_code"),
                str(e),
                exc_info=True,
            )

    @staticmethod
    async def _notify_agent_new_obligation(
        conn,
        agent_profile_id,
        obligation: Dict,
        license_row: Dict,
        entity_code: str,
    ) -> None:
        """Send email notification to assigned agent about new obligation.

        Non-blocking: failures are logged but do not affect the transaction.
        """
        import asyncio

        try:
            # Get agent email
            row = await conn.fetchrow("""
                SELECT u.email, u.first_name
                FROM agent_profiles ap
                JOIN users u ON u.id = ap.user_id
                WHERE ap.id = $1 AND u.status = 'active'
            """, agent_profile_id)

            if not row or not row["email"]:
                return

            agent_name = row["first_name"] or "Agent"
            company_name = license_row.get("company_name") or "—"
            fee_type = obligation.get("fee_type", "—")
            amount = obligation.get("amount", 0)

            subject = f"OMS: Nueva obligación asignada — {company_name}"
            html = f"""
            <div style="font-family:Arial,sans-serif;max-width:500px">
                <h3 style="color:#1d4ed8">Nueva obligación en tu cola</h3>
                <p>Hola {agent_name},</p>
                <p>Se te ha asignado una nueva obligación:</p>
                <table style="border-collapse:collapse;width:100%" cellpadding="8">
                    <tr style="background:#f3f4f6">
                        <td><strong>Empresa</strong></td><td>{company_name}</td>
                    </tr>
                    <tr>
                        <td><strong>Tipo</strong></td><td>{fee_type}</td>
                    </tr>
                    <tr style="background:#f3f4f6">
                        <td><strong>Monto</strong></td><td>{amount:,.0f} XAF</td>
                    </tr>
                    <tr>
                        <td><strong>Entidad</strong></td><td>{entity_code}</td>
                    </tr>
                </table>
                <p style="margin-top:16px">
                    <a href="#" style="background:#1d4ed8;color:white;padding:8px 16px;
                    border-radius:4px;text-decoration:none">Ver en mi cola OMS</a>
                </p>
            </div>"""

            try:
                from app.modules.communications.services.communication_service import (
                    CommunicationService,
                )
                from app.modules.communications.models.communication import (
                    CommunicationType,
                )

                comm = CommunicationService()
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None,
                    lambda: comm.send_communication(
                        channel=CommunicationType.EMAIL,
                        recipient=row["email"],
                        subject=subject,
                        content=html,
                    ),
                )
                logger.info(
                    "OMS agent notification sent: %s → %s",
                    obligation["id"], row["email"],
                )
            except Exception as email_err:
                logger.warning(
                    "OMS agent notification email failed: %s", email_err
                )

        except Exception as e:
            # Notification failure must NEVER block assignment
            logger.warning(
                "OMS agent notification lookup failed for profile %s: %s",
                agent_profile_id, e,
            )
