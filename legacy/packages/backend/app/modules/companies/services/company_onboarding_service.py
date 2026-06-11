"""
CompanyOnboardingService — Draft → Company lifecycle management.

Admin validates drafts → creates real company + commercial_license + obligations.
Supports: approve, reject, request-info, get-drafts, stats.
"""

import json
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import asyncpg
from loguru import logger

from app.modules.fiscal_services.services.license_service import LicenseService


class CompanyOnboardingService:
    """Manages company creation draft approval workflow."""

    async def get_drafts(
        self,
        conn: asyncpg.Connection,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List drafts for admin review, ordered by confidence ASC (lowest first).

        Returns paginated response with items, total, page, page_size.
        """
        conditions = []
        params: list = []
        idx = 1

        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        if batch_id:
            conditions.append(f"batch_id = ${idx}")
            params.append(UUID(batch_id))
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Count total
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM company_creation_drafts {where}",
            *params,
        )

        # Fetch page (lowest confidence first for review prioritization)
        offset = (page - 1) * page_size
        limit_idx = idx
        offset_idx = idx + 1
        rows = await conn.fetch(
            f"""SELECT id, source_type, source_file_id, batch_id,
                       company_data, regimen_fiscal,
                       classification_confidence, classification_reason,
                       classification_details, extraction_confidence,
                       extraction_details,
                       status, reviewer_notes, reviewed_at,
                       created_company_id, created_license_id,
                       created_by, created_at, updated_at
                FROM company_creation_drafts {where}
                ORDER BY
                    CASE WHEN status = 'pending_review' THEN 0
                         WHEN status = 'needs_info' THEN 1
                         WHEN status = 'auto_approved' THEN 2
                         WHEN status = 'error' THEN 3
                         ELSE 4 END,
                    COALESCE(classification_confidence, 0) ASC,
                    created_at DESC
                LIMIT ${limit_idx} OFFSET ${offset_idx}""",
            *params, page_size, offset,
        )

        items = []
        for r in rows:
            item = dict(r)
            # Parse JSONB fields (asyncpg auto-parses JSONB, but guard against str)
            for jsonb_field in ("company_data", "classification_details", "extraction_details"):
                if isinstance(item.get(jsonb_field), str):
                    item[jsonb_field] = json.loads(item[jsonb_field])
            # Ensure UUID serializable
            for uid_field in ("id", "source_file_id", "batch_id",
                              "created_company_id", "created_license_id", "created_by"):
                if item.get(uid_field):
                    item[uid_field] = str(item[uid_field])
            # Ensure nullable floats default to 0.0 for Pydantic
            if item.get("classification_confidence") is None:
                item["classification_confidence"] = 0.0
            if item.get("extraction_confidence") is None:
                item["extraction_confidence"] = 0.0
            items.append(item)

        return {
            "items": items,
            "total": total or 0,
            "page": page,
            "page_size": page_size,
        }

    async def get_draft(
        self,
        conn: asyncpg.Connection,
        draft_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a single draft by ID."""
        row = await conn.fetchrow(
            """SELECT * FROM company_creation_drafts WHERE id = $1""",
            UUID(draft_id),
        )
        if not row:
            return None

        item = dict(row)
        if isinstance(item.get("company_data"), str):
            item["company_data"] = json.loads(item["company_data"])
        if isinstance(item.get("classification_details"), str):
            item["classification_details"] = json.loads(item["classification_details"])
        if isinstance(item.get("extraction_details"), str):
            item["extraction_details"] = json.loads(item["extraction_details"])
        for uid_field in ("id", "created_company_id", "created_by", "reviewer_id",
                          "source_file_id"):
            if item.get(uid_field):
                item[uid_field] = str(item[uid_field])
        return item

    async def _resolve_location(
        self,
        conn: asyncpg.Connection,
        company_data: Dict[str, Any],
    ) -> Tuple[Optional[str], Optional[str]]:
        """Resolve zone_id and city_id from company data.

        Priority chain:
          1. Explicit zone_id → use as-is
          2. city_id → lookup cities.zone_id
          3. localidad string (OCR) → match cities.name → city_id + zone_id

        Returns:
            (zone_id, city_id) — either may be None.
        """
        zone_id = company_data.get("zone_id")
        city_id = company_data.get("city_id")

        if zone_id and city_id:
            return str(zone_id), str(city_id)

        # Step 1: If no city_id, try localidad string match
        if not city_id and company_data.get("localidad"):
            localidad = str(company_data["localidad"]).strip()
            provincia = company_data.get("provincia")
            if provincia:
                row = await conn.fetchrow(
                    """SELECT c.id AS city_id, c.zone_id
                       FROM cities c
                       WHERE LOWER(c.name) = LOWER($1)
                         AND LOWER(c.provincia) = LOWER($2)""",
                    localidad, str(provincia).strip(),
                )
            else:
                row = await conn.fetchrow(
                    """SELECT c.id AS city_id, c.zone_id
                       FROM cities c WHERE LOWER(c.name) = LOWER($1)""",
                    localidad,
                )
            if row:
                city_id = str(row["city_id"])
                zone_id = str(row["zone_id"])
                logger.info(f"Location resolved from localidad='{localidad}': city={city_id}, zone={zone_id}")
                return zone_id, city_id

        # Step 2: If city_id but no zone_id, resolve FK
        if city_id and not zone_id:
            city_id_param = UUID(city_id) if isinstance(city_id, str) else city_id
            resolved = await conn.fetchval(
                "SELECT zone_id FROM cities WHERE id = $1", city_id_param
            )
            if resolved:
                return str(resolved), str(city_id)
            logger.warning(f"City {city_id} has no zone_id assigned")

        return (str(zone_id) if zone_id else None, str(city_id) if city_id else None)

    async def approve_draft(
        self,
        conn: asyncpg.Connection,
        draft_id: str,
        reviewer_id: str,
        notes: str = "",
    ) -> Dict[str, Any]:
        """Admin approves draft → create company + license + obligations.

        Full pipeline for bundle regimes:
          1. Create company (with zone_id + city_id)
          2. Find active bundle for commerce_type
          3. Call LicenseService.open_license() — creates license + obligations + events
          4. Update draft with created_company_id + created_license_id
          5. Record classification history

        Uses LicenseService.open_license() which handles:
          - Zone-specific pricing (service_bundle_items filtered by zone_id)
          - Total amount computation from zone items
          - Obligation generation (1 per bundle_item) with penalty/deadline configs
          - Compliance event logging
          - Previous year compliance check
        """
        draft = await self.get_draft(conn, draft_id)
        if not draft:
            return {"error": "Draft not found"}

        if draft["status"] not in ("pending_review", "auto_approved", "needs_info"):
            return {"error": f"Cannot approve draft with status '{draft['status']}'"}

        company_data = draft.get("company_data") or {}
        regimen = draft.get("regimen_fiscal") or "pendiente"

        # Safe type coercion for DB columns
        capital_raw = company_data.get("capital_social")
        capital_val = float(capital_raw) if capital_raw is not None else None

        employee_raw = company_data.get("employee_count")
        employee_val = int(employee_raw) if employee_raw is not None else None

        reg_date_raw = company_data.get("registration_date")
        reg_date_val = None
        if reg_date_raw:
            try:
                reg_date_val = date.fromisoformat(str(reg_date_raw)[:10])
            except (ValueError, TypeError):
                reg_date_val = None

        # Resolve location: localidad (OCR string) → city_id → zone_id
        zone_id, city_id = await self._resolve_location(conn, company_data)

        # Pre-INSERT validation: check NIF / registration_number uniqueness
        nif = company_data.get("nif")
        reg_num = company_data.get("registration_number")

        if nif:
            existing = await conn.fetchrow(
                "SELECT id, legal_name FROM companies WHERE nif = $1", nif
            )
            if existing:
                return {
                    "error": (
                        f"Una empresa con NIF '{nif}' ya existe: "
                        f"{existing['legal_name']} (id={existing['id']})"
                    )
                }

        if reg_num:
            existing = await conn.fetchrow(
                "SELECT id, legal_name FROM companies WHERE registration_number = $1",
                reg_num,
            )
            if existing:
                return {
                    "error": (
                        f"Una empresa con N° Registro '{reg_num}' ya existe: "
                        f"{existing['legal_name']} (id={existing['id']})"
                    )
                }

        # Cross-check: AUTONOMO must have registration_number (PE-XXXX), others must have NIF
        forma = (company_data.get("forma_juridica") or "").lower()
        if forma == "autonomo" and not reg_num:
            logger.warning(
                f"Draft {draft_id}: AUTONOMO without registration_number (PE-XXXX)"
            )
        elif forma not in ("autonomo", "") and not nif:
            logger.warning(
                f"Draft {draft_id}: {forma} without NIF"
            )

        async with conn.transaction():
            # 1. Create company (includes zone_id and city_id)
            company_id = await conn.fetchval(
                """INSERT INTO companies
                   (legal_name, tax_id, nif, trade_name, forma_juridica, nacionalidad,
                    capital_social, registration_number, registration_date,
                    sector_actividad, subsector_actividad, objeto_social,
                    commerce_type, regimen_fiscal, employee_count,
                    address, phone, email, zone_id, city_id,
                    is_active, is_verified)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                           $13, $14, $15, $16, $17, $18, $19, $20, true, true)
                   RETURNING id""",
                company_data.get("legal_name", "Unknown"),
                company_data.get("nif") or company_data.get("tax_id") or company_data.get("registration_number") or f"PENDING-{uuid4()}",
                company_data.get("nif"),
                company_data.get("trade_name"),
                company_data.get("forma_juridica"),
                company_data.get("nacionalidad"),
                capital_val,
                company_data.get("registration_number"),
                reg_date_val,
                company_data.get("sector_actividad"),
                company_data.get("subsector_actividad"),
                company_data.get("objeto_social"),
                company_data.get("commerce_type"),
                regimen,
                employee_val,
                company_data.get("domicilio_fiscal") or company_data.get("address"),
                company_data.get("phone"),
                company_data.get("email"),
                UUID(zone_id) if zone_id else None,
                UUID(city_id) if city_id else None,
            )

            # 2. If autonomo/bundle regime with commerce_type → full license pipeline
            # Only persona física (autonomo, empresa_individual) can have bundle licenses.
            # SL/SA are always declarativo — no zone-based bundle pricing.
            created_license_id = None
            license_error = None
            commerce_type = company_data.get("commerce_type")
            forma = company_data.get("forma_juridica", "")
            is_persona_fisica = forma in ("autonomo", "empresa_individual")

            if is_persona_fisica and regimen == "bundle" and commerce_type:
                # Find matching active bundle
                bundle = await conn.fetchrow(
                    """SELECT id FROM service_bundles
                       WHERE commerce_type = $1 AND is_active = true
                       LIMIT 1""",
                    commerce_type,
                )

                if bundle and zone_id:
                    # Use LicenseService.open_license() for the FULL pipeline:
                    # license + zone-specific obligations + events + compliance check
                    fiscal_year = datetime.now(timezone.utc).year
                    try:
                        license_row = await LicenseService.open_license(
                            conn,
                            {
                                "company_id": company_id,
                                "bundle_id": bundle["id"],
                                "zone_id": UUID(zone_id),
                                "city_id": UUID(city_id) if city_id else None,
                                "fiscal_year": fiscal_year,
                            },
                            user_id=UUID(reviewer_id),
                        )
                        created_license_id = license_row["id"]
                        logger.info(
                            f"License auto-created via open_license: {created_license_id} "
                            f"(zone={zone_id}, bundle={bundle['id']}, year={fiscal_year})"
                        )
                    except ValueError as e:
                        # open_license raises ValueError for missing items, inactive, duplicates
                        license_error = str(e)
                        logger.warning(
                            f"License creation failed for draft {draft_id}: {e}"
                        )
                elif bundle and not zone_id:
                    license_error = (
                        "Cannot create license: company has no zone_id. "
                        "Assign zone in company settings to generate license."
                    )
                    logger.warning(
                        f"Draft {draft_id}: bundle found but no zone_id — "
                        f"license creation skipped"
                    )
                elif not bundle:
                    license_error = (
                        f"No active bundle found for commerce_type='{commerce_type}'"
                    )

            # 3. Update draft
            await conn.execute(
                """UPDATE company_creation_drafts
                   SET status = 'approved', reviewer_id = $2,
                       reviewer_notes = $3, reviewed_at = NOW(),
                       created_company_id = $4, created_license_id = $5
                   WHERE id = $1""",
                UUID(draft_id), UUID(reviewer_id), notes,
                company_id,  # already UUID from fetchval RETURNING
                created_license_id,  # already UUID or None
            )

            # 4. Classification history (full audit trail)
            await conn.execute(
                """INSERT INTO company_classification_history
                   (company_id, old_regimen, new_regimen,
                    old_commerce_type, new_commerce_type,
                    reason, confidence, details, triggered_by, created_by)
                   VALUES ($1, NULL, $2, NULL, $3, $4, $5, $6, 'initial', $7)""",
                company_id,  # already UUID from fetchval RETURNING
                regimen,
                commerce_type,
                f"Draft approved: {draft.get('classification_reason', 'N/A')}",
                draft.get("classification_confidence", 0),
                json.dumps(draft.get("classification_details", {})),
                UUID(reviewer_id),
            )

        logger.info(
            f"Draft {draft_id} approved → company {company_id} "
            f"(regime={regimen}, license={created_license_id})"
        )

        result = {
            "status": "approved",
            "company_id": str(company_id),
            "license_id": str(created_license_id) if created_license_id else None,
        }
        if license_error:
            result["license_warning"] = license_error
        return result

    async def reject_draft(
        self,
        conn: asyncpg.Connection,
        draft_id: str,
        reviewer_id: str,
        notes: str = "",
    ) -> Dict[str, Any]:
        """Admin rejects draft."""
        row = await conn.fetchrow(
            """UPDATE company_creation_drafts
               SET status = 'rejected', reviewer_id = $2,
                   reviewer_notes = $3, reviewed_at = NOW()
               WHERE id = $1 AND status IN ('pending_review', 'auto_approved', 'needs_info')
               RETURNING id""",
            UUID(draft_id), UUID(reviewer_id), notes,
        )

        if not row:
            return {"error": "Draft not found or cannot be rejected"}

        logger.info(f"Draft {draft_id} rejected by {reviewer_id}")
        return {"status": "rejected"}

    async def request_info(
        self,
        conn: asyncpg.Connection,
        draft_id: str,
        reviewer_id: str,
        notes: str = "",
    ) -> Dict[str, Any]:
        """Admin requests more info on a draft."""
        row = await conn.fetchrow(
            """UPDATE company_creation_drafts
               SET status = 'needs_info', reviewer_id = $2,
                   reviewer_notes = $3, reviewed_at = NOW()
               WHERE id = $1 AND status IN ('pending_review', 'auto_approved', 'needs_info')
               RETURNING id""",
            UUID(draft_id), UUID(reviewer_id), notes,
        )

        if not row:
            return {"error": "Draft not found or cannot request info"}

        logger.info(f"Draft {draft_id} needs_info by {reviewer_id}")
        return {"status": "needs_info"}

    async def get_stats(
        self,
        conn: asyncpg.Connection,
    ) -> Dict[str, Any]:
        """Classification statistics for admin dashboard."""
        # Company stats by regime
        regimen_stats = await conn.fetch(
            """SELECT COALESCE(regimen_fiscal, 'pendiente') AS regimen, COUNT(*) AS cnt
               FROM companies GROUP BY regimen_fiscal"""
        )
        by_regimen = {r["regimen"]: r["cnt"] for r in regimen_stats}

        # Draft stats
        draft_stats = await conn.fetch(
            """SELECT status, COUNT(*) AS cnt
               FROM company_creation_drafts GROUP BY status"""
        )
        drafts_by_status = {r["status"]: r["cnt"] for r in draft_stats}

        total_drafts = sum(drafts_by_status.values())
        approved = drafts_by_status.get("approved", 0) + drafts_by_status.get("auto_approved", 0)

        # Average confidence
        avg_conf = await conn.fetchval(
            "SELECT AVG(classification_confidence) FROM company_creation_drafts"
        )

        return {
            "total_companies": sum(by_regimen.values()),
            "by_regimen": by_regimen,
            "total_drafts": total_drafts,
            "drafts_pending": drafts_by_status.get("pending_review", 0),
            "drafts_approved": drafts_by_status.get("approved", 0),
            "drafts_auto_approved": drafts_by_status.get("auto_approved", 0),
            "drafts_rejected": drafts_by_status.get("rejected", 0),
            "drafts_needs_info": drafts_by_status.get("needs_info", 0),
            "auto_approval_rate": (
                round(drafts_by_status.get("auto_approved", 0) / total_drafts, 4)
                if total_drafts > 0 else 0.0
            ),
            "avg_confidence": round(float(avg_conf or 0), 4),
        }


# ── Module-level singleton ────────────────────────────────────────────────────

company_onboarding_service = CompanyOnboardingService()
