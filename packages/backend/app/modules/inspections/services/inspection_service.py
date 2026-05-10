"""Inspection Service — Business logic for field inspections.

Fixes: D1 (dynamic roles from BD), H6/H7 (configurable deadlines),
       OWASP A08 (signature integrity hash), A09 (audit trail)
"""

import asyncio
import hashlib
import json
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from app.modules.inspections.repositories.inspection_repository import (
    InspectionRepository,
)

logger = logging.getLogger(__name__)

MAX_SEAL_NOTES_LENGTH = 2000


async def _log_audit(conn, user_id: UUID, action: str, entity_type: str,
                     entity_id: str, details: Optional[Dict] = None):
    """OWASP A09: Persistent audit trail for critical inspection actions."""
    try:
        await conn.execute("""
            INSERT INTO audit_logs (user_id, action, entity_type, entity_id,
                                    new_values, ip_address, created_at)
            VALUES ($1, $2, $3, $4, $5, '0.0.0.0'::inet, NOW())
        """, user_id, action, entity_type, entity_id,
            __import__("json").dumps(details or {}))
    except Exception as e:
        logger.warning(f"Audit log failed for {action}/{entity_id}: {e}")


class InspectionService:
    """Business logic for field inspections."""

    @staticmethod
    async def resolve_inspector_context(conn, user_id: UUID) -> Dict:
        """Resolve agent's context for inspections.

        Fix D1: Roles are checked dynamically via permission 'inspection.create'
        in the BD instead of a hardcoded set. Any role with this permission
        can perform inspections without code changes.
        """
        row = await conn.fetchrow("""
            SELECT
                ap.id AS agent_profile_id,
                ap.entity_id, ap.entity_location_id,
                ap.is_supervisor,
                e.code AS entity_code,
                el.region, el.city_id,
                COALESCE(el.is_main_office, false) AS is_main_office,
                r.code AS role_code,
                EXISTS(
                    SELECT 1 FROM role_permissions rp2
                    JOIN permissions p2 ON p2.id = rp2.permission_id
                    WHERE rp2.role_id = r.id AND p2.name = 'inspection.create'
                ) AS has_inspection_permission,
                EXISTS(
                    SELECT 1 FROM role_permissions rp3
                    JOIN permissions p3 ON p3.id = rp3.permission_id
                    WHERE rp3.role_id = r.id AND p3.name = 'inspection.seal_approve'
                ) AS has_seal_approve
            FROM agent_profiles ap
            JOIN entities e ON e.id = ap.entity_id
            JOIN entity_locations el ON el.id = ap.entity_location_id
            JOIN users u ON u.id = ap.user_id
            JOIN roles r ON r.id = u.role_id
            WHERE ap.user_id = $1
              AND ap.is_active = true
        """, user_id)

        if not row:
            raise ValueError("No active agent profile found")

        role_code = row["role_code"]
        has_permission = row["has_inspection_permission"]
        is_supervisor = row["is_supervisor"] or row["has_seal_approve"]

        if not has_permission and not is_supervisor:
            raise ValueError(
                f"Role '{role_code}' does not have inspection permissions"
            )

        # City scope: only supervisors at main office get global visibility
        is_main_office = row["is_main_office"]
        has_global_scope = is_supervisor and is_main_office
        queue_city_id = None if has_global_scope else row["city_id"]

        return {
            "agent_profile_id": row["agent_profile_id"],
            "entity_id": row["entity_id"],
            "entity_location_id": row["entity_location_id"],
            "entity_code": row["entity_code"],
            "region": row["region"],
            "city_id": row["city_id"],
            "queue_city_id": queue_city_id,
            "is_main_office": is_main_office,
            "role_code": role_code,
            "is_supervisor": is_supervisor,
            "has_global_scope": has_global_scope,
        }

    # ============================================================
    # CREATE
    # ============================================================

    @staticmethod
    async def create_inspection(
        conn, user_id: UUID,
        license_id: UUID, company_id: UUID,
        notes: Optional[str] = None,
        mission_id: Optional[UUID] = None,
        zone_id: Optional[UUID] = None,
    ) -> Dict:
        """Create a new field inspection."""
        ctx = await InspectionService.resolve_inspector_context(conn, user_id)

        # Verify license exists and belongs to the company
        license_row = await conn.fetchrow("""
            SELECT id, company_id, status, fiscal_year
            FROM commercial_licenses
            WHERE id = $1
        """, license_id)

        if not license_row:
            raise ValueError(f"License {license_id} not found")

        if license_row["company_id"] != company_id:
            raise ValueError("License does not belong to this company")

        # Resolve zone_id from company if not provided
        if not zone_id:
            zone_id = await conn.fetchval(
                "SELECT zone_id FROM companies WHERE id = $1", company_id,
            )

        # Snapshot obligations at inspection time
        obl_stats = await conn.fetchrow("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status IN ('pending', 'overdue')) AS unpaid,
                COALESCE(SUM(amount + penalty_amount) FILTER (
                    WHERE status IN ('pending', 'overdue')
                ), 0) AS unpaid_amount
            FROM license_obligations
            WHERE license_id = $1
        """, license_id)

        inspection_data = {
            "agent_id": user_id,
            "agent_profile_id": ctx["agent_profile_id"],
            "entity_id": ctx["entity_id"],
            "entity_location_id": ctx["entity_location_id"],
            "license_id": license_id,
            "company_id": company_id,
            "notes": notes,
            "unpaid_obligations_count": obl_stats["unpaid"],
            "unpaid_obligations_amount": obl_stats["unpaid_amount"],
            "total_obligations_count": obl_stats["total"],
        }
        if mission_id:
            inspection_data["mission_id"] = mission_id
        if zone_id:
            inspection_data["zone_id"] = zone_id

        inspection = await InspectionRepository.create(conn, inspection_data)

        # Auto-transition: agent assigned→active + mission planned→in_progress
        if mission_id:
            await conn.execute("""
                UPDATE field_mission_agents
                SET status = 'active', started_at = COALESCE(started_at, NOW())
                WHERE mission_id = $1 AND agent_id = $2 AND status = 'assigned'
            """, mission_id, user_id)

            await conn.execute("""
                UPDATE field_missions
                SET status = 'in_progress', started_at = COALESCE(started_at, NOW())
                WHERE id = $1 AND status = 'planned'
            """, mission_id)

        return await InspectionRepository.get_by_id(conn, inspection["id"])

    # ============================================================
    # UPDATE
    # ============================================================

    @staticmethod
    async def update_inspection(
        conn, inspection_id: UUID, user_id: UUID, data: Dict,
    ) -> Dict:
        """Update inspection (photos, GPS, notes, activity check)."""
        inspection = await InspectionRepository.get_by_id(conn, inspection_id)
        if not inspection:
            raise ValueError(f"Inspection {inspection_id} not found")

        if inspection["agent_id"] != user_id:
            raise ValueError("Cannot update another agent's inspection")

        if inspection["status"] != "in_progress":
            raise ValueError(
                f"Cannot update inspection in status '{inspection['status']}'"
            )

        # OWASP A08: If signature is being set, hash it for tamper detection
        if "agent_signature" in data and data["agent_signature"]:
            sig_data = data["agent_signature"]
            ts = datetime.now(timezone.utc).isoformat()
            sig_hash = hashlib.sha256(
                f"{sig_data}|{user_id}|{ts}".encode()
            ).hexdigest()[:32]
            # Store hash alongside signature for later verification
            data["notes"] = (
                (data.get("notes") or inspection.get("notes") or "")
                + f"\n[SIG_HASH:{sig_hash}:{ts}]"
            ).strip()

        return await InspectionRepository.update(conn, inspection_id, data)

    # ============================================================
    # COMPLETE (conforme)
    # ============================================================

    @staticmethod
    async def complete_inspection(
        conn, inspection_id: UUID, user_id: UUID,
        notes: Optional[str] = None,
    ) -> Dict:
        """Complete an inspection as conforme."""
        inspection = await InspectionRepository.get_by_id(conn, inspection_id)
        if not inspection:
            raise ValueError(f"Inspection {inspection_id} not found")

        if inspection["agent_id"] != user_id:
            raise ValueError("Cannot complete another agent's inspection")

        if inspection["status"] != "in_progress":
            raise ValueError(
                f"Cannot complete inspection in status '{inspection['status']}'"
            )

        # Fix M2: Require activity_conforme to be set before completing
        if inspection.get("activity_conforme") is None:
            raise ValueError(
                "Cannot complete inspection: activity conformity check "
                "has not been performed. Set activity_conforme first."
            )

        # Determine result based on activity + payment
        result = "conforme"
        if inspection["activity_conforme"] is False:
            result = "non_conforme"
        elif inspection["unpaid_obligations_count"] > 0:
            result = "non_conforme"

        update_data = {
            "status": "completed",
            "result": result,
        }
        if notes:
            update_data["notes"] = notes

        updated = await InspectionRepository.update(
            conn, inspection_id, update_data
        )

        # Generate PDF + emit event with attachment
        try:
            from app.core.events import EventBus, EventType
            from app.modules.inspections.services.inspection_pdf_service import (
                inspection_pdf_service,
            )

            # Get company owner for notification
            owner = await conn.fetchrow("""
                SELECT u.email, u.full_name, u.phone_number, u.preferred_language
                FROM user_company_roles ucr
                JOIN users u ON u.id = ucr.user_id
                WHERE ucr.company_id = $1
                  AND ucr.role = 'company_owner' AND ucr.is_active = true
                LIMIT 1
            """, inspection["company_id"])

            # Generate PDF report as attachment
            attachments = []
            try:
                lang = owner["preferred_language"] if owner else "es"
                pdf_bytes = await inspection_pdf_service.generate_inspection_report(
                    conn, str(inspection_id), lang,
                )
                attachments.append((
                    f"inspection-{str(inspection_id)[:8]}.pdf",
                    pdf_bytes,
                    "application/pdf",
                ))
            except Exception as pdf_err:
                logger.warning(f"Inspection PDF generation failed: {pdf_err}")

            EventBus.publish_nowait(EventType.INSPECTION_COMPLETED, {
                "inspection_id": str(inspection_id),
                "company_name": inspection.get("company_name"),
                "company_nif": inspection.get("company_nif"),
                "result": result,
                "inspection_date": str(inspection["inspection_date"]),
                "agent_name": inspection.get("agent_name"),
                "user_id": str(user_id),
                "user_email": owner["email"] if owner else None,
                "user_phone": owner["phone_number"] if owner else None,
                "user_name": owner["full_name"] if owner else None,
                "preferred_language": owner["preferred_language"] if owner else "es",
                "attachments": attachments if attachments else None,
            })
        except Exception as e:
            logger.warning(f"INSPECTION_COMPLETED event emission failed: {e}")

        # OWASP A09: Audit trail
        await _log_audit(conn, user_id, "INSPECTION_COMPLETED", "field_inspection",
                         str(inspection_id), {"result": result,
                         "company": inspection.get("company_name")})

        logger.info(
            f"Inspection {inspection_id} completed: {result} "
            f"by agent {user_id}"
        )
        return updated

    # ============================================================
    # MISE EN DEMEURE
    # ============================================================

    @staticmethod
    async def issue_mise_en_demeure(
        conn, inspection_id: UUID, user_id: UUID,
        obligation_ids: List[UUID],
        deadline_hours: int = 72,
        notes: Optional[str] = None,
    ) -> Dict:
        """Issue a mise en demeure (formal notice)."""
        inspection = await InspectionRepository.get_by_id(conn, inspection_id)
        if not inspection:
            raise ValueError(f"Inspection {inspection_id} not found")

        if inspection["agent_id"] != user_id:
            raise ValueError("Cannot issue MED on another agent's inspection")

        if inspection["status"] != "in_progress":
            raise ValueError(
                f"Cannot issue MED on inspection in status '{inspection['status']}'"
            )

        # Verify obligations exist and are unpaid
        obls = await conn.fetch("""
            SELECT id, status, amount, penalty_amount
            FROM license_obligations
            WHERE id = ANY($1::uuid[])
              AND license_id = $2
        """, obligation_ids, inspection["license_id"])

        if len(obls) != len(obligation_ids):
            raise ValueError("Some obligation IDs are invalid")

        unpayable = [
            o for o in obls
            if o["status"] not in ("pending", "overdue")
        ]
        if unpayable:
            raise ValueError(
                f"Obligations must be pending/overdue, found: "
                f"{[str(o['id']) for o in unpayable]}"
            )

        deadline = datetime.now(timezone.utc) + timedelta(hours=deadline_hours)

        update_data = {
            "status": "mise_en_demeure",
            "result": "non_conforme",
            "mise_en_demeure_issued": True,
            "mise_en_demeure_deadline": deadline,
            "mise_en_demeure_obligations": json.dumps([str(oid) for oid in obligation_ids]),
        }
        if notes:
            update_data["notes"] = notes

        updated = await InspectionRepository.update(
            conn, inspection_id, update_data
        )

        # Fix M6: Get company owner via user_company_roles (no owner_id column)
        owner = await conn.fetchrow("""
            SELECT u.email, u.full_name, u.phone_number, u.preferred_language
            FROM user_company_roles ucr
            JOIN users u ON u.id = ucr.user_id
            WHERE ucr.company_id = $1
              AND ucr.role = 'company_owner'
              AND ucr.is_active = true
            LIMIT 1
        """, inspection["company_id"])

        total_unpaid = sum(
            (o["amount"] or 0) + (o["penalty_amount"] or 0) for o in obls
        )

        # Generate MED PDF + emit event with attachment
        try:
            from app.core.events import EventBus, EventType
            from app.modules.inspections.services.inspection_pdf_service import (
                inspection_pdf_service,
            )

            attachments = []
            try:
                lang = owner["preferred_language"] if owner else "es"
                pdf_bytes = await inspection_pdf_service.generate_med_pdf(
                    conn, str(inspection_id), lang,
                )
                attachments.append((
                    f"mise-en-demeure-{str(inspection_id)[:8]}.pdf",
                    pdf_bytes,
                    "application/pdf",
                ))
                # Store in Firebase + vault
                try:
                    from app.modules.documents.services.storage_service import storage_service
                    from app.modules.user_documents.services.vault_registry import register_document_in_vault
                    med_filename = f"mise-en-demeure-{str(inspection_id)[:8]}.pdf"
                    med_url = await storage_service.upload_bytes(
                        pdf_bytes, f"inspections/{inspection_id}/{med_filename}",
                        content_type="application/pdf",
                    )
                    if med_url and owner:
                        company_id = inspection.get("company_id")
                        owner_id = await conn.fetchval(
                            "SELECT user_id FROM user_company_roles WHERE company_id = $1 AND role = 'company_owner' LIMIT 1",
                            company_id,
                        ) if company_id else None
                        if owner_id:
                            await register_document_in_vault(
                                conn, user_id=owner_id,
                                file_path=med_url, file_name=med_filename,
                                document_type="MISE_EN_DEMEURE", document_category="inspections",
                                holder_name=inspection.get("company_name"),
                            )
                except Exception as vault_err:
                    logger.warning(f"MED vault storage failed: {vault_err}")
            except Exception as pdf_err:
                logger.warning(f"MED PDF generation failed: {pdf_err}")

            EventBus.publish_nowait(EventType.MISE_EN_DEMEURE_ISSUED, {
                "inspection_id": str(inspection_id),
                "company_name": inspection.get("company_name"),
                "company_nif": inspection.get("company_nif"),
                "unpaid_amount": float(total_unpaid),
                "deadline": deadline.isoformat(),
                "obligations_list": ", ".join(
                    f"{o['amount']} XAF" for o in obls
                ),
                "user_email": owner["email"] if owner else None,
                "user_phone": owner["phone_number"] if owner else None,
                "user_name": owner["full_name"] if owner else None,
                "preferred_language": (
                    owner["preferred_language"] if owner else "es"
                ),
                "attachments": attachments if attachments else None,
            })
        except Exception as e:
            logger.warning(f"MISE_EN_DEMEURE event emission failed: {e}")

        await _log_audit(conn, user_id, "MISE_EN_DEMEURE_ISSUED", "field_inspection",
                         str(inspection_id), {"deadline": deadline.isoformat(),
                         "amount": float(total_unpaid),
                         "company": inspection.get("company_name")})

        logger.info(
            f"MED issued on inspection {inspection_id}, deadline: {deadline}"
        )
        return updated

    # ============================================================
    # SEAL
    # ============================================================

    @staticmethod
    async def propose_seal(
        conn, inspection_id: UUID, user_id: UUID,
        reason: str,
        notes: Optional[str] = None,
        photo: Optional[str] = None,
    ) -> Dict:
        """Propose sealing a business (requires supervisor approval)."""
        inspection = await InspectionRepository.get_by_id(conn, inspection_id)
        if not inspection:
            raise ValueError(f"Inspection {inspection_id} not found")

        if inspection["agent_id"] != user_id:
            raise ValueError("Cannot propose seal on another agent's inspection")

        if inspection["status"] not in ("in_progress", "mise_en_demeure"):
            raise ValueError(
                f"Cannot propose seal on inspection in status "
                f"'{inspection['status']}'"
            )

        # For non_paiement_apres_med, check MED is expired
        if reason == "non_paiement_apres_med":
            # Check if there's an expired MED for this company
            expired_med = await conn.fetchrow("""
                SELECT id FROM field_inspections
                WHERE company_id = $1
                  AND mise_en_demeure_issued = true
                  AND mise_en_demeure_deadline < NOW()
                  AND status = 'mise_en_demeure'
                LIMIT 1
            """, inspection["company_id"])

            if not expired_med:
                raise ValueError(
                    "Cannot seal for non-payment: no expired mise en demeure "
                    "found. Issue a MED first and wait for the deadline."
                )

        update_data = {
            "status": "seal_proposed",
            "result": "non_conforme",
            "seal_applied": True,
            "seal_reason": reason,
            "seal_proposed_at": datetime.now(timezone.utc),
        }
        if notes:
            update_data["seal_notes"] = notes
        if photo:
            update_data["seal_photo"] = photo

        updated = await InspectionRepository.update(
            conn, inspection_id, update_data
        )

        # Fix F1: Notify ALL supervisors of the entity (not single user)
        try:
            from app.core.events import EventBus, EventType

            # Fetch all supervisor emails for this entity
            supervisors = await conn.fetch("""
                SELECT u.id, u.email, u.full_name, u.phone_number, u.preferred_language
                FROM agent_profiles ap
                JOIN users u ON u.id = ap.user_id
                WHERE ap.entity_id = $1
                  AND ap.is_supervisor = true
                  AND ap.is_active = true
                  AND u.email IS NOT NULL
            """, inspection["entity_id"])

            if not supervisors:
                logger.warning(
                    f"SEAL_PROPOSED: No supervisors found for entity "
                    f"{inspection['entity_id']}"
                )

            # Emit one event per supervisor so each gets an email
            for sup in supervisors:
                EventBus.publish_nowait(EventType.SEAL_PROPOSED, {
                    "inspection_id": str(inspection_id),
                    "company_name": inspection.get("company_name"),
                    "company_nif": inspection.get("company_nif"),
                    "seal_reason": reason,
                    "agent_name": inspection.get("agent_name"),
                    "entity_id": str(inspection["entity_id"]),
                    "user_id": str(sup["id"]),
                    "user_email": sup["email"],
                    "user_phone": sup["phone_number"],
                    "user_name": sup["full_name"],
                    "preferred_language": sup["preferred_language"] or "es",
                })

            logger.info(
                f"SEAL_PROPOSED: Notified {len(supervisors)} supervisor(s) "
                f"for entity {inspection['entity_id']}"
            )
        except Exception as e:
            logger.warning(f"SEAL_PROPOSED event emission failed: {e}")

        await _log_audit(conn, user_id, "SEAL_PROPOSED", "field_inspection",
                         str(inspection_id), {"reason": reason,
                         "company": inspection.get("company_name")})

        logger.info(
            f"Seal proposed on inspection {inspection_id}: {reason}"
        )
        return updated

    @staticmethod
    async def approve_seal(
        conn, inspection_id: UUID, supervisor_id: UUID,
        approved: bool,
        notes: Optional[str] = None,
    ) -> Dict:
        """Supervisor approves or rejects a seal proposal."""
        ctx = await InspectionService.resolve_inspector_context(
            conn, supervisor_id
        )

        if not ctx["is_supervisor"]:
            raise ValueError("Only supervisors can approve/reject seals")

        inspection = await InspectionRepository.get_by_id(conn, inspection_id)
        if not inspection:
            raise ValueError(f"Inspection {inspection_id} not found")

        if inspection["status"] != "seal_proposed":
            raise ValueError(
                f"Inspection is not in 'seal_proposed' status "
                f"(current: {inspection['status']})"
            )

        # IDOR: supervisor must be from same entity
        if inspection["entity_id"] != ctx["entity_id"]:
            raise ValueError("Cannot approve seal for another entity")

        if approved:
            update_data = {
                "status": "seal_approved",
                "seal_approved_by": supervisor_id,
                "seal_approved_at": datetime.now(timezone.utc),
            }

            # Deactivate company + suspend license
            await conn.execute("""
                UPDATE companies SET is_active = false, updated_at = NOW()
                WHERE id = $1
            """, inspection["company_id"])

            await conn.execute("""
                UPDATE commercial_licenses
                SET status = 'suspended', updated_at = NOW()
                WHERE id = $1 AND status != 'closed'
            """, inspection["license_id"])

            # Generate seal PV PDF + emit event with attachment + notify owner
            try:
                from app.core.events import EventBus, EventType
                from app.modules.inspections.services.inspection_pdf_service import (
                    inspection_pdf_service,
                )

                # Get company owner for notification
                owner = await conn.fetchrow("""
                    SELECT u.email, u.full_name, u.phone_number, u.preferred_language
                    FROM user_company_roles ucr
                    JOIN users u ON u.id = ucr.user_id
                    WHERE ucr.company_id = $1
                      AND ucr.role = 'company_owner' AND ucr.is_active = true
                    LIMIT 1
                """, inspection["company_id"])

                attachments = []
                try:
                    lang = owner["preferred_language"] if owner else "es"
                    pdf_bytes = await inspection_pdf_service.generate_seal_pdf(
                        conn, str(inspection_id), lang,
                    )
                    attachments.append((
                        f"pv-scelle-{str(inspection_id)[:8]}.pdf",
                        pdf_bytes,
                        "application/pdf",
                    ))
                    # Store in Firebase + vault
                    try:
                        from app.modules.documents.services.storage_service import storage_service
                        from app.modules.user_documents.services.vault_registry import register_document_in_vault
                        seal_filename = f"pv-scelle-{str(inspection_id)[:8]}.pdf"
                        seal_url = await storage_service.upload_bytes(
                            pdf_bytes, f"inspections/{inspection_id}/{seal_filename}",
                            content_type="application/pdf",
                        )
                        if seal_url:
                            owner_id = await conn.fetchval(
                                "SELECT user_id FROM user_company_roles WHERE company_id = $1 AND role = 'company_owner' LIMIT 1",
                                inspection["company_id"],
                            ) if inspection.get("company_id") else None
                            if owner_id:
                                await register_document_in_vault(
                                    conn, user_id=owner_id,
                                    file_path=seal_url, file_name=seal_filename,
                                    document_type="SEAL_ORDER", document_category="inspections",
                                    holder_name=inspection.get("company_name"),
                                )
                    except Exception as vault_err:
                        logger.warning(f"Seal vault storage failed: {vault_err}")
                except Exception as pdf_err:
                    logger.warning(f"Seal PDF generation failed: {pdf_err}")

                EventBus.publish_nowait(EventType.SEAL_APPROVED, {
                    "inspection_id": str(inspection_id),
                    "company_name": inspection.get("company_name"),
                    "company_nif": inspection.get("company_nif"),
                    "seal_reason": inspection.get("seal_reason"),
                    "unpaid_amount": float(inspection.get("unpaid_obligations_amount", 0)),
                    "user_id": str(supervisor_id),
                    "user_email": owner["email"] if owner else None,
                    "user_phone": owner["phone_number"] if owner else None,
                    "user_name": owner["full_name"] if owner else None,
                    "preferred_language": owner["preferred_language"] if owner else "es",
                    "attachments": attachments if attachments else None,
                })
            except Exception as e:
                logger.warning(f"SEAL_APPROVED event emission failed: {e}")

            await _log_audit(conn, supervisor_id, "SEAL_APPROVED", "field_inspection",
                             str(inspection_id), {"company": inspection.get("company_name"),
                             "reason": inspection.get("seal_reason")})

            logger.info(
                f"Seal APPROVED on inspection {inspection_id} "
                f"by supervisor {supervisor_id}"
            )
        else:
            update_data = {
                "status": "seal_rejected",
                "seal_rejection_reason": notes,
                "seal_approved_by": supervisor_id,
                "seal_approved_at": datetime.now(timezone.utc),
            }

            await _log_audit(conn, supervisor_id, "SEAL_REJECTED", "field_inspection",
                             str(inspection_id), {"reason": notes,
                             "company": inspection.get("company_name")})

            logger.info(
                f"Seal REJECTED on inspection {inspection_id} "
                f"by supervisor {supervisor_id}: {notes}"
            )

        if notes:
            # Fix m6: Truncate seal_notes to prevent unbounded growth
            existing = (inspection.get("seal_notes") or "").strip()
            new_note = f"\n[Supervisor] {notes}"
            combined = (existing + new_note).strip()
            update_data["seal_notes"] = combined[:MAX_SEAL_NOTES_LENGTH]

        return await InspectionRepository.update(
            conn, inspection_id, update_data
        )

    # ============================================================
    # SUPERVISOR DASHBOARD
    # ============================================================

    @staticmethod
    async def get_supervisor_dashboard(
        conn, user_id: UUID,
        entity_location_id: Optional[UUID] = None,
    ) -> Dict:
        """Get supervisor inspection dashboard data.

        If entity_location_id is provided, scopes stats to that site.
        Non-main-office supervisors are auto-scoped to their own location.
        """
        ctx = await InspectionService.resolve_inspector_context(conn, user_id)

        if not ctx["is_supervisor"]:
            raise ValueError("Dashboard is supervisor-only")

        entity_id = ctx["entity_id"]

        # City-scoped entities (AYUNTAMIENTO, CAMARA_COMERCIO): always forced
        # to own location. National entities: only non-main-office forced.
        CITY_SCOPED = {"AYUNTAMIENTO", "CAMARA_COMERCIO"}
        is_city_scoped = ctx.get("entity_code", "") in CITY_SCOPED
        location_filter = entity_location_id
        if not location_filter and (is_city_scoped or not ctx.get("is_main_office", False)):
            location_filter = ctx.get("entity_location_id")

        # CTE-based dashboard: 1 query for all stats
        cte_data = await InspectionRepository.get_supervisor_dashboard_cte(
            conn, entity_id, entity_location_id=location_filter,
        )

        # Sequential — asyncpg does NOT support concurrent queries on single connection
        pending_seals = await InspectionRepository.get_pending_seals(conn, entity_id)
        recent = await InspectionRepository.list_by_entity(
            conn, entity_id, page=1, page_size=10,
        )
        recent_items = recent[0] if isinstance(recent, tuple) else recent

        return {
            "today": cte_data.get("today", {}),
            "week": cte_data.get("week", {}),
            "pending_seals": pending_seals,
            "overdue_med": cte_data.get("overdue_med", 0),
            "unreconciled_cash_amount": cte_data.get("cash_amount", Decimal("0")),
            "unreconciled_cash_count": cte_data.get("cash_count", 0),
            "recent_inspections": recent_items,
        }

    # ============================================================
    # CRON: Auto-approve seals after 24h
    # ============================================================

    @staticmethod
    async def auto_approve_expired_seals(conn) -> int:
        """Fix m8: Batch auto-approve seals in O(1) queries instead of O(N)."""
        count = await InspectionRepository.batch_auto_approve_seals(
            conn, hours=24
        )
        if count > 0:
            logger.info(f"Auto-approved {count} expired seals (batch)")
        return count

    # ============================================================
    # VERIFY LICENSE (Agent Mode)
    # ============================================================

    @staticmethod
    async def verify_license_for_agent(
        conn, user_id: UUID,
        license_id: Optional[UUID] = None,
        nif: Optional[str] = None,
    ) -> Dict:
        """Get enriched license data for agent field verification.

        Plan P3 — INSPECTION_BUNDLE_P3_DETAIL.md §3 P3.E:
          Returns all obligations of the licence (unfiltered) plus computed
          fields that let the mobile UI show which ones the agent may collect:

            - existing_dossier: {service_request_id, reference, source, status,
                                 created_at} | None (if SR already linked)
            - has_pending_citizen_payment: bool
            - pending_payment_info: {payment_reference, ...} | None
            - obligations[*].agent_restricted: bool per obligation
            - restricted_obligations: [UUID] list of blocked ones
            - agent_can_collect_all: bool
            - agent_scope: {allowed_fee_types, required_ministry_id,
                            is_polyvalent, is_independent, role_code}
        """
        ctx = await InspectionService.resolve_inspector_context(conn, user_id)

        if not license_id and nif:
            # Search by NIF (GE-format) or registration_number (PE-format)
            found = await InspectionRepository.find_license_by_identifier(
                conn, nif
            )
            if not found:
                raise ValueError(
                    f"No current license found for identifier: {nif}. "
                    f"Search covers both NIF (GExxxxx) and N° Registro (PE-xxxxxx)."
                )
            license_id = found["license_id"]

        if not license_id:
            raise ValueError("Either license_id or nif/registration_number is required")

        # Fetch unfiltered licence + obligations. Agent scope filtering is
        # done post-query so we can return restricted_obligations metadata.
        result = await InspectionRepository.get_license_for_verification(
            conn, license_id, ctx["entity_id"],
            fee_type=None,  # No filter — caller computes restricted_obligations
        )

        if not result:
            raise ValueError(f"License {license_id} not found")

        # Resolve OMS agent scope (Plan P3 — D2/D3)
        # Wrap in try/except so non-OMS users (ex: legacy staff) still get
        # license data for read-only consultation (no collection rights).
        from app.modules.fiscal_services.services.oms_agent_service import (
            OmsAgentService,
        )
        try:
            oms_ctx = await OmsAgentService.resolve_agent_context(conn, user_id)
            allowed_fee_types, required_ministry_id = (
                OmsAgentService.compute_collection_scope(oms_ctx)
            )
            agent_scope = {
                "role_code": oms_ctx.get("role_code"),
                "allowed_fee_types": (
                    sorted(allowed_fee_types) if allowed_fee_types else None
                ),
                "required_ministry_id": required_ministry_id,
                "is_polyvalent": bool(oms_ctx.get("is_polyvalent")),
                "is_independent": bool(oms_ctx.get("is_independent")),
                "is_supervisor": bool(oms_ctx.get("is_supervisor")),
            }
        except ValueError:
            oms_ctx = None
            allowed_fee_types = set()
            required_ministry_id = None
            agent_scope = {
                "role_code": None,
                "allowed_fee_types": [],
                "required_ministry_id": None,
                "is_polyvalent": False,
                "is_independent": False,
                "is_supervisor": False,
            }

        # Mark each obligation with agent_restricted flag
        obligations = result.get("obligations", [])
        restricted_ids: List[str] = []
        for o in obligations:
            obl_fee_type = o.get("fee_type")
            obl_ministry_id = o.get("ministry_id")
            is_restricted = False
            reason = None

            if oms_ctx is None:
                is_restricted = True
                reason = "non_oms_user"
            elif allowed_fee_types is not None and obl_fee_type not in allowed_fee_types:
                is_restricted = True
                reason = f"fee_type_{obl_fee_type}_not_in_scope"
            elif required_ministry_id is not None and obl_ministry_id != required_ministry_id:
                is_restricted = True
                reason = f"ministry_{obl_ministry_id}_not_agent_ministry"

            o["agent_restricted"] = is_restricted
            o["agent_restricted_reason"] = reason
            if is_restricted:
                restricted_ids.append(str(o["id"]))

        result["restricted_obligations"] = restricted_ids
        result["agent_can_collect_all"] = len(restricted_ids) == 0
        result["agent_scope"] = agent_scope

        # Existing dossier (lazy-created SR linked to the licence) — Plan P3 D4
        dossier_row = await conn.fetchrow(
            """
            SELECT sr.id, sr.reference, sr.source, sr.status::text AS status,
                   sr.created_at
            FROM commercial_licenses cl
            JOIN service_requests sr ON sr.id = cl.service_request_id
            WHERE cl.id = $1
              AND cl.service_request_id IS NOT NULL
            """,
            license_id,
        )
        if dossier_row:
            result["existing_dossier"] = {
                "service_request_id": str(dossier_row["id"]),
                "reference": dossier_row["reference"],
                "source": dossier_row["source"],
                "status": dossier_row["status"],
                "created_at": dossier_row["created_at"].isoformat()
                              if dossier_row["created_at"] else None,
            }
        else:
            result["existing_dossier"] = None

        # Pending citizen payment (Plan P3 D5) — signals active online payment
        pending_row = await conn.fetchrow(
            """
            SELECT sp.payment_reference, sp.payment_method,
                   sp.total_amount, sp.workflow_status::text AS workflow_status,
                   sp.created_at
            FROM commercial_licenses cl
            JOIN service_requests sr ON sr.id = cl.service_request_id
            JOIN service_payments sp ON sp.service_request_id = sr.id
            WHERE cl.id = $1
              AND sp.workflow_status NOT IN (
                  'completed', 'rejected_by_agent', 'expired',
                  'cancelled_by_user', 'cancelled_by_agent'
              )
            ORDER BY sp.created_at DESC
            LIMIT 1
            """,
            license_id,
        )
        if pending_row:
            result["has_pending_citizen_payment"] = True
            result["pending_payment_info"] = {
                "payment_reference": pending_row["payment_reference"],
                "payment_method": pending_row["payment_method"],
                "total_amount": float(pending_row["total_amount"])
                                if pending_row["total_amount"] is not None else None,
                "workflow_status": pending_row["workflow_status"],
                "created_at": pending_row["created_at"].isoformat()
                              if pending_row["created_at"] else None,
            }
        else:
            result["has_pending_citizen_payment"] = False
            result["pending_payment_info"] = None

        return result

    # ============================================================
    # LIVE STATUS (Phase 8 — Real-Time View)
    # ============================================================

    @staticmethod
    async def get_live_agent_status(conn, entity_id: UUID, entity_location_id: UUID = None) -> dict:
        """Get real-time agent status for a supervisor's entity.

        Single CTE query fetching:
        - Agent profiles with last_activity_at
        - Today's inspection stats per agent
        - Current in-progress inspections
        - Cash collection totals
        - Entity-wide counters

        Cached in Redis for 30s to prevent DB hammering from polling.
        """
        from app.core.cache import get_cache

        cache = get_cache()
        loc_suffix = f":loc:{entity_location_id}" if entity_location_id else ""
        cache_key = f"live_status:entity:{entity_id}{loc_suffix}"

        cached = await cache.get(cache_key)
        if cached:
            return cached

        # Fetch configurable thresholds from system_rules
        thresholds = await conn.fetch("""
            SELECT rule_code, rule_value
            FROM system_rules
            WHERE rule_code IN ('AGENT_STATUS_IDLE_MINUTES', 'AGENT_STATUS_OFFLINE_MINUTES')
              AND is_active = true
        """)
        idle_minutes = 120
        offline_minutes = 240
        for t in thresholds:
            val = t["rule_value"]
            # rule_value is JSONB — safely parse as int
            try:
                minutes = int(val) if isinstance(val, (int, float)) else int(str(val).strip('"'))
            except (ValueError, TypeError):
                continue  # Skip invalid values, keep defaults
            if t["rule_code"] == "AGENT_STATUS_IDLE_MINUTES":
                idle_minutes = minutes
            elif t["rule_code"] == "AGENT_STATUS_OFFLINE_MINUTES":
                offline_minutes = minutes

        # Build location filter for secondary-site supervisors
        location_filter = ""
        query_params = [entity_id]
        if entity_location_id:
            location_filter = "AND ap.entity_location_id = $2"
            query_params.append(entity_location_id)

        # Single CTE query — O(agents) not O(inspections)
        rows = await conn.fetch(f"""
            WITH agent_base AS (
                SELECT
                    ap.id AS agent_profile_id,
                    ap.user_id AS agent_id,
                    u.full_name AS agent_name,
                    ap.last_activity_at,
                    EXTRACT(EPOCH FROM (NOW() - ap.last_activity_at)) / 60.0
                        AS minutes_since_activity
                FROM agent_profiles ap
                JOIN users u ON u.id = ap.user_id
                WHERE ap.entity_id = $1
                  AND ap.is_active = true
                  {location_filter}
            ),
            today_stats AS (
                SELECT
                    fi.agent_id,
                    COUNT(*) AS inspections_today,
                    COALESCE(SUM(fi.payment_amount) FILTER (WHERE fi.payment_collected), 0)
                        AS cash_collected_today
                FROM field_inspections fi
                WHERE fi.entity_id = $1
                  AND fi.inspection_date = CURRENT_DATE
                GROUP BY fi.agent_id
            ),
            in_progress AS (
                SELECT
                    fi.agent_id,
                    fi.id AS inspection_id,
                    fi.gps_latitude,
                    fi.gps_longitude,
                    ROW_NUMBER() OVER (PARTITION BY fi.agent_id ORDER BY fi.updated_at DESC)
                        AS rn
                FROM field_inspections fi
                WHERE fi.entity_id = $1
                  AND fi.status = 'in_progress'
            )
            SELECT
                ab.agent_profile_id,
                ab.agent_id,
                ab.agent_name,
                ab.last_activity_at,
                ab.minutes_since_activity,
                COALESCE(ts.inspections_today, 0) AS inspections_today,
                COALESCE(ts.cash_collected_today, 0) AS cash_collected_today,
                ip.inspection_id AS current_inspection_id,
                ip.gps_latitude AS last_gps_latitude,
                ip.gps_longitude AS last_gps_longitude
            FROM agent_base ab
            LEFT JOIN today_stats ts ON ts.agent_id = ab.agent_id
            LEFT JOIN in_progress ip ON ip.agent_id = ab.agent_id AND ip.rn = 1
            ORDER BY ab.minutes_since_activity ASC NULLS LAST
        """, *query_params)

        # Build agent statuses
        agents = []
        counters = {
            "active_agents": 0,
            "idle_agents": 0,
            "offline_agents": 0,
            "total_agents": 0,
            "inspections_today": 0,
            "inspections_in_progress": 0,
            "cash_collected_today": 0,
            "cash_pending_reconciliation": 0,
        }

        for r in rows:
            mins = r["minutes_since_activity"]
            if mins is not None and mins < idle_minutes:
                status = "active"
            elif mins is not None and mins < offline_minutes:
                status = "idle"
            else:
                status = "offline"

            agent = {
                "agent_id": str(r["agent_id"]),
                "agent_profile_id": str(r["agent_profile_id"]),
                "agent_name": r["agent_name"],
                "status": status,
                "last_activity_at": r["last_activity_at"].isoformat() if r["last_activity_at"] else None,
                "minutes_since_activity": int(mins) if mins is not None else None,
                "inspections_today": r["inspections_today"],
                "cash_collected_today": float(r["cash_collected_today"]),
                "current_inspection_id": str(r["current_inspection_id"]) if r["current_inspection_id"] else None,
                "last_gps_latitude": float(r["last_gps_latitude"]) if r["last_gps_latitude"] is not None else None,
                "last_gps_longitude": float(r["last_gps_longitude"]) if r["last_gps_longitude"] is not None else None,
            }
            agents.append(agent)

            counters["total_agents"] += 1
            if status == "active":
                counters["active_agents"] += 1
            elif status == "idle":
                counters["idle_agents"] += 1
            else:
                counters["offline_agents"] += 1
            counters["inspections_today"] += r["inspections_today"]
            counters["cash_collected_today"] += float(r["cash_collected_today"])
            if r["current_inspection_id"]:
                counters["inspections_in_progress"] += 1

        # Get pending reconciliation amount
        pending = await conn.fetchrow("""
            SELECT COALESCE(SUM(total_amount), 0) AS pending
            FROM service_payments
            WHERE collection_type = 'field'
              AND workflow_status = 'field_collected'
              AND entity_code = (SELECT code FROM entities WHERE id = $1)
        """, entity_id)
        counters["cash_pending_reconciliation"] = float(pending["pending"]) if pending else 0

        from datetime import datetime, timezone
        result = {
            "agents": agents,
            "counters": counters,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }

        # Cache for 30s
        await cache.set(cache_key, result, ttl=30)

        return result
