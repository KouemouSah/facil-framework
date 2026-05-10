"""BundleWorkflowService — Business logic for the BUNDLE_PAYMENT workflow.

Handles the complete lifecycle of paying bundle obligations for autonomo companies:
  - my_companies_status(): List user's companies + obligation counts (1 SQL query)
  - search_eligible_companies(): Search companies eligible for bundle (regimen=bundle, active)
  - initiate(): Verify/create license → return obligations for review
  - initiate_from_upload(): OCR extraction → create company → classify → create license
  - validate_selection(): Validate mode + obligation selection before payment
  - initiate_payment(): Create service_request + service_payment + link obligations (atomic)

Architecture:
  - This service contains the BUSINESS LOGIC. The BundlePaymentWorkflow class
    (PredefinedWorkflow) is a lightweight registration for WorkflowEngine/menus.
  - Payment processing delegates to PaymentProcessorRegistry (BANGE/Manual).
  - Post-payment routing handled by ObligationRoutingService (Phase 1).

See: .claude/plans/design_bundle_workflow.md for complete data flow.
"""

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import asyncpg

logger = logging.getLogger(__name__)


class BundleWorkflowService:
    """Business logic for bundle payment workflow."""

    # ================================================================
    # Step 0: "Mis empresas" — user's companies with obligation counts
    # ================================================================

    @staticmethod
    async def my_companies_status(
        conn, user_id: UUID, fiscal_year: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get user's companies with pending obligation counts.

        Returns max 5 companies, sorted by urgency (pending obligations first).
        1 SQL query with LEFT JOINs — no N+1.

        Args:
            conn: Database connection
            user_id: Authenticated user
            fiscal_year: Defaults to current year
        """
        if not fiscal_year:
            fiscal_year = datetime.now(timezone.utc).year

        rows = await conn.fetch("""
            SELECT
                c.id, c.legal_name, c.tax_id, c.nif,
                c.registration_number, c.regimen_fiscal,
                c.commerce_type, c.zone_id, c.city_id,
                c.is_active, c.is_verified,
                cz.zone_code,
                ct.name as city_name,
                cl.id as license_id,
                cl.status as license_status,
                cl.fiscal_year as license_fiscal_year,
                COALESCE(
                    COUNT(lo.id) FILTER (
                        WHERE lo.status IN ('pending', 'overdue')
                    ), 0
                )::int as pending_obligations
            FROM companies c
            JOIN user_company_roles ucr
                ON ucr.company_id = c.id AND ucr.user_id = $1
            LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
            LEFT JOIN cities ct ON c.city_id = ct.id
            LEFT JOIN commercial_licenses cl
                ON cl.company_id = c.id AND cl.fiscal_year = $2
            LEFT JOIN license_obligations lo
                ON lo.license_id = cl.id
            WHERE c.is_active = true
              AND c.archived_at IS NULL
            GROUP BY c.id, cz.zone_code, ct.name,
                     cl.id, cl.status, cl.fiscal_year
            ORDER BY pending_obligations DESC NULLS LAST,
                     c.created_at DESC
            LIMIT 5
        """, user_id, fiscal_year)

        results = []
        for r in rows:
            results.append({
                "company": {
                    "id": str(r["id"]),
                    "legal_name": r["legal_name"],
                    "tax_id": r["tax_id"],
                    "nif": r["nif"],
                    "registration_number": r["registration_number"],
                    "regimen_fiscal": r["regimen_fiscal"],
                    "commerce_type": r["commerce_type"],
                    "zone_code": r["zone_code"],
                    "city_name": r["city_name"],
                    "is_verified": r["is_verified"],
                },
                "license_id": str(r["license_id"]) if r["license_id"] else None,
                "license_status": r["license_status"],
                "pending_obligations": r["pending_obligations"],
                "fiscal_year": fiscal_year,
                "is_eligible": r["regimen_fiscal"] == "bundle",
            })

        return results

    # ================================================================
    # Citizen — Company detail + payment history
    # ================================================================

    @staticmethod
    async def my_company_detail(
        conn, user_id: UUID, company_id: UUID, fiscal_year: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get detailed company info with license and obligations for citizen.

        Verifies ownership via user_company_roles.
        Returns company info + current license + all obligations with statuses.
        """
        if not fiscal_year:
            fiscal_year = datetime.now(timezone.utc).year

        # Verify ownership
        is_member = await conn.fetchval(
            "SELECT 1 FROM user_company_roles WHERE user_id = $1 AND company_id = $2",
            user_id, company_id,
        )
        if not is_member:
            raise ValueError("COMPANY_NOT_OWNED")

        # Company + license — archived companies are hidden from the citizen
        # surface (the AND archived_at IS NULL clause turns them into
        # COMPANY_NOT_FOUND, same response as a deleted row).
        row = await conn.fetchrow("""
            SELECT c.id, c.legal_name, c.nif, c.registration_number,
                   c.regimen_fiscal, c.commerce_type, c.objeto_social,
                   c.forma_juridica, c.is_active, c.is_verified,
                   c.representante_legal,
                   cz.zone_code, ct.name as city_name,
                   cl.id as license_id, cl.status as license_status,
                   cl.fiscal_year, cl.total_amount, cl.amount_paid,
                   cl.penalty_amount, cl.obligations_total, cl.obligations_paid,
                   cl.deadline, cl.completed_at, cl.created_at as license_created_at,
                   cl.certificate_number, cl.certificate_url
            FROM companies c
            LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
            LEFT JOIN cities ct ON c.city_id = ct.id
            LEFT JOIN commercial_licenses cl
                ON cl.company_id = c.id AND cl.fiscal_year = $2
            WHERE c.id = $1
              AND c.archived_at IS NULL
        """, company_id, fiscal_year)

        if not row:
            raise ValueError("COMPANY_NOT_FOUND")

        # Obligations (if license exists)
        obligations = []
        if row["license_id"]:
            obl_rows = await conn.fetch("""
                SELECT lo.id, lo.fee_type, lo.amount, lo.penalty_amount,
                       lo.status, lo.due_date, lo.paid_at,
                       fs.name_es as service_name, fs.service_code,
                       m.name_es as ministry_name
                FROM license_obligations lo
                LEFT JOIN fiscal_services fs ON lo.fiscal_service_id = fs.id
                LEFT JOIN ministries m ON lo.ministry_id = m.id
                WHERE lo.license_id = $1
                ORDER BY lo.fee_type, fs.service_code
            """, row["license_id"])
            obligations = [
                {
                    "id": str(o["id"]),
                    "fee_type": o["fee_type"],
                    "amount": float(o["amount"]),
                    "penalty_amount": float(o["penalty_amount"] or 0),
                    "status": o["status"],
                    "due_date": o["due_date"].isoformat() if o["due_date"] else None,
                    "paid_at": o["paid_at"].isoformat() if o["paid_at"] else None,
                    "service_name": o["service_name"],
                    "service_code": o["service_code"],
                    "ministry_name": o["ministry_name"],
                }
                for o in obl_rows
            ]

        # Field inspections (mise en demeure, scellés, reçus inspection)
        inspections = []
        insp_rows = await conn.fetch("""
            SELECT fi.id, fi.inspection_date, fi.status, fi.result,
                   fi.activity_conforme, fi.activity_declared, fi.activity_observed,
                   fi.mise_en_demeure_issued, fi.mise_en_demeure_deadline,
                   fi.seal_applied, fi.seal_reason, fi.seal_approved_at,
                   fi.payment_collected, fi.payment_receipt_number, fi.payment_amount,
                   fi.notes, fi.created_at
            FROM field_inspections fi
            WHERE fi.company_id = $1
            ORDER BY fi.inspection_date DESC NULLS LAST, fi.created_at DESC
            LIMIT 20
        """, company_id)
        for insp in insp_rows:
            inspections.append({
                "id": str(insp["id"]),
                "date": insp["inspection_date"].isoformat() if insp["inspection_date"] else None,
                "status": insp["status"],
                "result": insp["result"],
                "conforme": insp["activity_conforme"],
                "activity_declared": insp["activity_declared"],
                "activity_observed": insp["activity_observed"],
                "mise_en_demeure": insp["mise_en_demeure_issued"] or False,
                "mise_en_demeure_deadline": (
                    insp["mise_en_demeure_deadline"].isoformat()
                    if insp["mise_en_demeure_deadline"] else None
                ),
                "seal_applied": insp["seal_applied"] or False,
                "seal_reason": insp["seal_reason"],
                "seal_approved_at": (
                    insp["seal_approved_at"].isoformat()
                    if insp["seal_approved_at"] else None
                ),
                "payment_collected": insp["payment_collected"] or False,
                "payment_receipt": insp["payment_receipt_number"],
                "payment_amount": float(insp["payment_amount"]) if insp["payment_amount"] else None,
                "notes": insp["notes"],
                "created_at": insp["created_at"].isoformat() if insp["created_at"] else None,
            })

        total = float(row["total_amount"] or 0)
        paid = float(row["amount_paid"] or 0)

        return {
            "company": {
                "id": str(row["id"]),
                "legal_name": row["legal_name"],
                "nif": row["nif"],
                "registration_number": row["registration_number"],
                "regimen_fiscal": row["regimen_fiscal"],
                "commerce_type": row["commerce_type"],
                "objeto_social": row["objeto_social"],
                "forma_juridica": row["forma_juridica"],
                "is_active": row["is_active"],
                "is_verified": row["is_verified"],
                "representante_legal": row["representante_legal"],
                "zone_code": row["zone_code"],
                "city_name": row["city_name"],
            },
            "license": {
                "id": str(row["license_id"]),
                "status": row["license_status"],
                "fiscal_year": row["fiscal_year"],
                "total_amount": total,
                "amount_paid": paid,
                "amount_remaining": total - paid,
                "penalty_amount": float(row["penalty_amount"] or 0),
                "obligations_total": row["obligations_total"],
                "obligations_paid": row["obligations_paid"],
                "deadline": row["deadline"].isoformat() if row["deadline"] else None,
                "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
                "expiry_date": f"{row['fiscal_year']}-12-31",
                "certificate_number": row.get("certificate_number"),
                "certificate_url": row.get("certificate_url"),
            } if row["license_id"] else None,
            "obligations": obligations,
            "inspections": inspections,
            "fiscal_year": fiscal_year,
        }

    @staticmethod
    async def my_company_payments(
        conn, user_id: UUID, company_id: UUID, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """Get payment history for a citizen's company.

        Verifies ownership. Returns service_payments with receipt info.
        """
        # Verify ownership AND that the company is not archived (citizen
        # surface — archived companies appear as COMPANY_NOT_OWNED to the
        # caller, matching the listing/detail behaviour).
        is_visible = await conn.fetchval(
            """
            SELECT 1 FROM user_company_roles ucr
            JOIN companies c ON c.id = ucr.company_id
            WHERE ucr.user_id = $1
              AND ucr.company_id = $2
              AND c.archived_at IS NULL
            """,
            user_id, company_id,
        )
        if not is_visible:
            raise ValueError("COMPANY_NOT_OWNED")

        offset = (page - 1) * page_size
        rows = await conn.fetch("""
            SELECT sp.id, sp.payment_reference, sp.total_amount, sp.currency,
                   sp.payment_method, sp.workflow_status, sp.fee_type,
                   sp.entity_code, sp.receipt_number, sp.receipt_url,
                   sp.created_at, sp.validated_at,
                   sr.reference as sr_reference
            FROM service_payments sp
            JOIN service_requests sr ON sr.id = sp.service_request_id
            WHERE sp.company_id = $1
            ORDER BY sp.created_at DESC
            LIMIT $2 OFFSET $3
        """, company_id, page_size, offset)

        count = await conn.fetchval(
            "SELECT COUNT(*) FROM service_payments WHERE company_id = $1",
            company_id,
        )

        return {
            "payments": [
                {
                    "id": str(r["id"]),
                    "reference": r["payment_reference"] or str(r["id"])[:12],
                    "sr_reference": r["sr_reference"],
                    "amount": float(r["total_amount"] or 0),
                    "currency": r["currency"],
                    "method": r["payment_method"],
                    "status": r["workflow_status"],
                    "fee_type": r["fee_type"],
                    "entity_code": r["entity_code"],
                    "receipt_number": r["receipt_number"],
                    "receipt_url": r["receipt_url"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                    "validated_at": r["validated_at"].isoformat() if r["validated_at"] else None,
                }
                for r in rows
            ],
            "total": count,
            "page": page,
            "page_size": page_size,
        }

    # ================================================================
    # Step 0: Search eligible companies (bundle + active)
    # ================================================================

    @staticmethod
    async def search_eligible_companies(
        conn, query: str, user_id: UUID, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search companies eligible for bundle payment.

        Filters: regimen_fiscal='bundle', is_active=true.
        No permission required (citizen-accessible endpoint).
        Includes "registered_by_current_user" flag for tiers indicator.
        """
        if not query or len(query) < 2:
            return []

        # Use FTS (search_vector GIN index) for scalability (800K+ companies).
        # Falls back to ILIKE if search_vector is empty (pre-migration data).
        # Exact PE-XXXX/NIF match uses btree index directly (no FTS needed).
        is_exact_match = query.upper().startswith("PE-") or query.upper().startswith("NIF")
        if is_exact_match:
            rows = await conn.fetch("""
                SELECT c.id, c.legal_name, c.tax_id, c.nif,
                       c.registration_number, c.regimen_fiscal,
                       c.commerce_type, c.is_verified,
                       cz.zone_code, ct.name as city_name,
                       EXISTS(SELECT 1 FROM user_company_roles ucr
                              WHERE ucr.company_id = c.id AND ucr.user_id = $3
                       ) as registered_by_current_user
                FROM companies c
                LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
                LEFT JOIN cities ct ON c.city_id = ct.id
                WHERE c.is_active = true AND c.regimen_fiscal = 'bundle'
                  AND c.archived_at IS NULL
                  AND (c.registration_number ILIKE $1 OR c.nif ILIKE $1
                       OR c.tax_id ILIKE $1)
                ORDER BY c.legal_name LIMIT $2
            """, f"{query}%", limit, user_id)
        else:
            # FTS via search_vector (GIN index) — O(log n) at scale
            # Use websearch_to_tsquery (lenient parsing) instead of to_tsquery (strict)
            rows = await conn.fetch("""
                SELECT c.id, c.legal_name, c.tax_id, c.nif,
                       c.registration_number, c.regimen_fiscal,
                       c.commerce_type, c.is_verified,
                       cz.zone_code, ct.name as city_name,
                       EXISTS(SELECT 1 FROM user_company_roles ucr
                              WHERE ucr.company_id = c.id AND ucr.user_id = $3
                       ) as registered_by_current_user
                FROM companies c
                LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
                LEFT JOIN cities ct ON c.city_id = ct.id
                WHERE c.is_active = true AND c.regimen_fiscal = 'bundle'
                  AND c.archived_at IS NULL
                  AND (c.search_vector @@ websearch_to_tsquery('spanish', $1)
                       OR c.legal_name ILIKE $4)
                ORDER BY c.legal_name LIMIT $2
            """, query.strip(), limit, user_id, f"%{query}%")

        return [
            {
                "id": str(r["id"]),
                "legal_name": r["legal_name"],
                "tax_id": r["tax_id"],
                "nif": r["nif"],
                "registration_number": r["registration_number"],
                "commerce_type": r["commerce_type"],
                "zone_code": r["zone_code"],
                "city_name": r["city_name"],
                "is_verified": r["is_verified"],
                "registered_by_current_user": r["registered_by_current_user"],
            }
            for r in rows
        ]

    # ================================================================
    # Step 0b: Classify preview — extraction → zone + classification (no DB writes)
    # ================================================================

    @staticmethod
    async def preview_classification(
        conn, extraction: Dict[str, Any],
        override_zone_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Preview classification without creating anything.

        Args:
            extraction: OCR extraction data
            override_zone_id: User-selected zone (overrides OCR detection).
                When provided, categories are fetched for THIS zone.

        Returns:
        - extracted_data: key fields from OCR
        - zone_resolved: bool
        - zone: {id, code, name} if resolved
        - available_zones: ALWAYS returned (user can correct OCR zone)
        - classification: {regimen_fiscal, commerce_type, confidence}
        - available_categories: categories for resolved/override zone
        - available_commerce_types: ALL commerce_types for manual selection
        """
        from app.modules.companies.services.classification_agent import CompanyClassificationAgent as ClassificationAgent

        # 1. Map extraction to company data
        logger.info(
            "classify-preview: extraction top-level keys=%s, has_empresa=%s, has_ubicacion=%s",
            list(extraction.keys())[:10],
            "empresa" in extraction,
            "ubicacion" in extraction,
        )
        company_data = ClassificationAgent.map_gemini_extraction_to_company_data(extraction)
        logger.info(
            "classify-preview: mapped company_data legal_name=%s, reg=%s, localidad=%s",
            company_data.get("legal_name"),
            company_data.get("registration_number"),
            company_data.get("localidad"),
        )

        # 2. Resolve zone: user override > OCR extraction > None
        #
        # Zone resolution is TIER-based, not city-based:
        #   - A city (Malabo) maps to a tier (A = Capitales de Regiones)
        #   - Within that tier, there are 3 ranks: A1 (centro), A2 (secundario), A3 (periferia)
        #   - The user must select the specific zone (A1/A2/A3) based on their commerce location
        #   - The OCR can detect the CITY → TIER, but NOT the rank (1/2/3)
        zone_id = None
        zone_info = None
        detected_tier = None  # Tier detected from OCR localidad
        detected_city = None

        if override_zone_id:
            # User explicitly selected a zone — use it (final, no ambiguity)
            from uuid import UUID as _UUID
            try:
                zid = _UUID(override_zone_id)
                zrow = await conn.fetchrow(
                    "SELECT cz.id, cz.zone_code, cz.zone_tier, cz.name_es "
                    "FROM commerce_zones cz WHERE cz.id = $1",
                    zid
                )
                if zrow:
                    zone_id = zrow["id"]
                    zone_info = {
                        "id": str(zrow["id"]),
                        "code": zrow["zone_code"],
                        "name": zrow["name_es"],
                        "tier": zrow["zone_tier"],
                    }
            except (ValueError, Exception):
                pass

        if not zone_id:
            # Try OCR localidad extraction → resolves to TIER (not specific zone)
            localidad = company_data.get("localidad", "")
            if localidad:
                city_row = await conn.fetchrow(
                    "SELECT c.id as city_id, c.name as city_name, "
                    "cz.zone_tier, cz.zone_code, cz.name_es as zone_name "
                    "FROM cities c "
                    "LEFT JOIN commerce_zones cz ON cz.id = c.zone_id "
                    "WHERE c.name ILIKE $1",
                    localidad.strip()
                )
                if city_row and city_row["zone_tier"]:
                    detected_tier = city_row["zone_tier"]
                    detected_city = city_row["city_name"]
                    # Do NOT set zone_id — user must choose specific zone within tier

        # 3. Build available zones — filtered by detected tier if available
        # If OCR detected city → show only zones of that tier (e.g., A1/A2/A3 for Malabo)
        # If no city detected → show ALL 12 zones
        # If user already selected a zone (override) → still show tier zones for reference
        all_zones = await conn.fetch(
            "SELECT cz.id, cz.zone_code, cz.zone_tier, cz.zone_rank, cz.name_es, "
            "cz.description_es "
            "FROM commerce_zones cz "
            "ORDER BY cz.zone_code"
        )

        available_zones = []
        for r in all_zones:
            available_zones.append({
                "id": str(r["id"]),
                "code": r["zone_code"],
                "tier": r["zone_tier"],
                "rank": r["zone_rank"],
                "name": r["name_es"],
                "description": r["description_es"] or "",
            })

        # Zones matching detected tier (for smart pre-filtering in UI)
        tier_zones = [z for z in available_zones if z["tier"] == detected_tier] if detected_tier else []

        # 4. Classify (rules-based, no DB writes)
        classification_agent = ClassificationAgent()
        classification = await classification_agent.classify_company(
            conn, company_data, zone_id=zone_id
        )

        # 5. Get available categories FOR the resolved/override zone
        available_categories = []
        if zone_id:
            cat_rows = await conn.fetch(
                "SELECT DISTINCT sb.commerce_type, sb.name_es as bundle_name "
                "FROM service_bundles sb "
                "JOIN service_bundle_items sbi ON sbi.bundle_id = sb.id "
                "WHERE sbi.zone_id = $1 AND sb.is_active = true "
                "ORDER BY sb.commerce_type",
                zone_id
            )
            available_categories = [
                {"commerce_type": r["commerce_type"], "bundle_name": r["bundle_name"]}
                for r in cat_rows
            ]

        # 6. ALWAYS get all commerce_types (user can select if classification fails)
        all_types = await conn.fetch(
            "SELECT DISTINCT sb.commerce_type, sb.name_es as bundle_name "
            "FROM service_bundles sb "
            "WHERE sb.is_active = true "
            "ORDER BY sb.commerce_type"
        )
        available_commerce_types = [
            {"commerce_type": r["commerce_type"], "bundle_name": r["bundle_name"]}
            for r in all_types
        ]

        return {
            "extracted_data": {
                "legal_name": company_data.get("legal_name"),
                "registration_number": company_data.get("registration_number"),
                "nif": company_data.get("nif"),
                "forma_juridica": company_data.get("forma_juridica"),
                "localidad": company_data.get("localidad"),
                "provincia": company_data.get("provincia"),
                "sector": company_data.get("sector_actividad"),
                "objeto_social": company_data.get("objeto_social"),
            },
            "zone_resolved": zone_id is not None,
            "zone": zone_info,
            "detected_tier": detected_tier,
            "detected_city": detected_city,
            "tier_zones": tier_zones,
            "available_zones": available_zones,
            "classification": {
                "regimen_fiscal": classification.regimen_fiscal,
                "commerce_type": classification.commerce_type,
                "confidence": classification.confidence,
            },
            "available_categories": available_categories,
            "available_commerce_types": available_commerce_types,
            "needs_manual_zone": zone_id is None,
            "needs_manual_category": not classification.commerce_type,
        }

    # ================================================================
    # Step 1: Initiate from upload — extraction → company → classify → initiate
    # ================================================================

    @staticmethod
    async def initiate_from_upload(
        conn, extraction: Dict[str, Any], user_id: UUID,
        fiscal_year: Optional[int] = None,
        zone_id: Optional[UUID] = None,
        commerce_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create company from OCR extraction, classify, then initiate workflow.

        Reuses existing components:
          - map_gemini_extraction_to_company_data() (classification_agent.py)
          - CompanyRepository.create() (auto owner role)
          - ClassificationAgent.classify_company() (R2b: autonomo+PE → bundle)
          - BundleWorkflowService.initiate() (license + obligations)

        Args:
            conn: Database connection
            extraction: GeminiDocumentProcessor extraction output (nested dict)
            user_id: Authenticated user
            fiscal_year: Defaults to current year
            zone_id: Override zone (from classify-preview manual selection)
            commerce_type: Override commerce type (from classify-preview manual selection)

        Returns:
            BundleInitiateResponse (same as initiate()) + company creation info
        """
        from app.modules.companies.services.classification_agent import (
            CompanyClassificationAgent as ClassificationAgent,
            classification_agent,
        )
        from app.modules.companies.repositories.company_repository import (
            CompanyRepository,
        )

        # 1. Map extraction → flat company_data
        company_data = ClassificationAgent.map_gemini_extraction_to_company_data(
            extraction
        )
        if not company_data.get("legal_name"):
            raise ValueError("EXTRACTION_MISSING_LEGAL_NAME")

        registration_number = company_data.get("registration_number", "")

        # 2. Check duplicate by registration_number (PE-XXXX)
        if registration_number:
            existing = await conn.fetchrow(
                "SELECT id FROM companies WHERE registration_number = $1",
                registration_number,
            )
            if existing:
                # Company already exists — just initiate with it
                logger.info(
                    "Upload: company %s already exists (PE=%s) — using existing",
                    existing["id"],
                    registration_number,
                )
                result = await BundleWorkflowService.initiate(
                    conn, existing["id"], user_id, fiscal_year
                )
                result["company_created"] = False
                result["company_already_existed"] = True
                return result

        # 3. Resolve city from localidad + use zone_id override if provided
        #    Zone selection is tier-based: user picks specific zone (A1/A2/A3)
        #    City resolution is separate: localidad → cities.id (for city_id FK)
        localidad = company_data.get("localidad", "")
        city_id = None

        # Always resolve city_id from localidad (regardless of zone override)
        if localidad:
            city_row = await conn.fetchrow(
                "SELECT id, zone_id FROM cities WHERE name ILIKE $1 LIMIT 1",
                localidad.strip(),
            )
            if city_row:
                city_id = city_row["id"]
                # Only use city's zone_id as fallback if no override provided
                if not zone_id:
                    zone_id = city_row["zone_id"]

        if zone_id:
            logger.info("Upload: zone=%s, city_id=%s, localidad=%s", zone_id, city_id, localidad)

        # 4. Create company via repository (adds owner role automatically)
        from app.modules.companies.models.company import CompanyCreate

        create_data = CompanyCreate(
            legal_name=company_data["legal_name"],
            tax_id=company_data.get("nif") or registration_number or f"PE-{str(uuid4())[:6]}",
            nif=company_data.get("nif"),
            registration_number=registration_number or None,
            forma_juridica=company_data.get("forma_juridica", "autonomo"),
            sector_actividad=company_data.get("sector_actividad"),
            objeto_social=company_data.get("objeto_social"),
            representante_legal=company_data.get("representante_legal"),
            address=company_data.get("direccion"),
            phone=company_data.get("telefono"),
        )

        company_repo = CompanyRepository()
        company_row = await company_repo.create(conn, create_data, str(user_id))
        company_id = company_row["id"]

        # Set city_id + zone_id (not in CompanyCreate)
        if city_id or zone_id:
            await conn.execute(
                """UPDATE companies
                   SET city_id = COALESCE($2, city_id),
                       zone_id = COALESCE($3, zone_id)
                   WHERE id = $1""",
                company_id, city_id, zone_id,
            )

        logger.info(
            "Upload: created company %s (PE=%s, localidad=%s)",
            company_id, registration_number, localidad,
        )

        # 5. Auto-classify (non-blocking — failure doesn't break flow)
        #    Use commerce_type override if provided (from classify-preview manual selection)
        try:
            if commerce_type:
                # User overrode classification — set directly, skip LLM inference
                await conn.execute(
                    """UPDATE companies
                       SET regimen_fiscal = 'bundle', commerce_type = $2, updated_at = NOW()
                       WHERE id = $1""",
                    company_id,
                    commerce_type,
                )
                logger.info(
                    "Upload: using commerce_type override for company %s → bundle (commerce=%s)",
                    company_id,
                    commerce_type,
                )
            else:
                company_full = await conn.fetchrow(
                    "SELECT * FROM companies WHERE id = $1", company_id
                )
                classification = await classification_agent.classify_company(
                    conn, dict(company_full), zone_id=zone_id
                )
                if classification.regimen_fiscal:
                    await conn.execute(
                        """UPDATE companies
                           SET regimen_fiscal = $2, commerce_type = $3, updated_at = NOW()
                           WHERE id = $1""",
                        company_id,
                        classification.regimen_fiscal,
                        classification.commerce_type,
                    )
                    logger.info(
                        "Upload: classified company %s → %s (commerce=%s, conf=%.0f%%)",
                        company_id,
                        classification.regimen_fiscal,
                        classification.commerce_type,
                        (classification.confidence or 0) * 100,
                    )
        except Exception as e:
            logger.warning(
                "Upload: auto-classification failed for company %s: %s",
                company_id, e,
            )

        # 6. Initiate workflow with newly created company
        try:
            result = await BundleWorkflowService.initiate(
                conn, company_id, user_id, fiscal_year
            )
        except ValueError as e:
            # Company created but initiate failed (e.g., no bundle for commerce_type).
            # Return partial result so frontend doesn't lose the created company.
            logger.warning(
                "Upload: company %s created but initiate failed: %s",
                company_id, e,
            )
            raise ValueError(f"INITIATE_AFTER_UPLOAD_FAILED:{e}")

        result["company_created"] = True
        result["company_already_existed"] = False
        return result

    # ================================================================
    # Step 2: Initiate — verify/create license, return obligations
    # ================================================================

    @staticmethod
    async def initiate(
        conn, company_id: UUID, user_id: UUID,
        fiscal_year: Optional[int] = None
    ) -> Dict[str, Any]:
        """Verify company eligibility, find/create license, return obligations.

        This is the MAIN entry point after company identification (Step 0).

        Flow:
          1. Verify company exists, is_active, regimen_fiscal='bundle'
          2. Resolve bundle from company.commerce_type
          3. Find or create commercial_license for this year
          4. Return obligations for review

        Returns:
            BundleInitiateResponse with license + obligations + amounts
        """
        from app.modules.fiscal_services.services.license_service import LicenseService
        from app.modules.fiscal_services.services.bundle_service import BundleService

        if not fiscal_year:
            fiscal_year = datetime.now(timezone.utc).year

        # 1. Verify company
        company = await conn.fetchrow(
            """SELECT c.*, cz.zone_code, ct.name as city_name
               FROM companies c
               LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
               LEFT JOIN cities ct ON c.city_id = ct.id
               WHERE c.id = $1""",
            company_id,
        )
        if not company:
            raise ValueError("COMPANY_NOT_FOUND")
        if not company["is_active"]:
            raise ValueError("COMPANY_INACTIVE")
        if company["regimen_fiscal"] != "bundle":
            raise ValueError("COMPANY_NOT_AUTONOMO")
        if not company["zone_id"]:
            raise ValueError("COMPANY_NO_ZONE")

        # Audit: log if user is acting on someone else's company (tiers payment)
        is_owner = await conn.fetchval(
            "SELECT 1 FROM user_company_roles WHERE company_id = $1 AND user_id = $2",
            company_id, user_id,
        )
        if not is_owner:
            logger.info(
                "AUDIT: third-party payment initiated — user %s acting on "
                "company %s (%s) without membership",
                user_id, company_id, company["legal_name"],
            )

        # 2. Resolve bundle from commerce_type
        if not company["commerce_type"]:
            raise ValueError("COMPANY_NO_COMMERCE_TYPE")

        bundle = await conn.fetchrow(
            """SELECT id, commerce_type, name_es, processing_mode,
                      installment_eligible, max_installments
               FROM service_bundles
               WHERE commerce_type = $1 AND is_active = true
               LIMIT 1""",
            company["commerce_type"],
        )
        if not bundle:
            raise ValueError("NO_BUNDLE_FOR_COMMERCE_TYPE")

        # 3. Find or create license
        license_row = await conn.fetchrow(
            """SELECT cl.*, cz.zone_code
               FROM commercial_licenses cl
               LEFT JOIN commerce_zones cz ON cl.zone_id = cz.id
               WHERE cl.company_id = $1
                 AND cl.bundle_id = $2
                 AND cl.fiscal_year = $3""",
            company_id, bundle["id"], fiscal_year,
        )

        if license_row and license_row["status"] == "complete":
            # Already fully paid
            return {
                "license_id": str(license_row["id"]),
                "already_complete": True,
                "license_status": "complete",
                "total_amount": float(license_row["total_amount"]),
                "amount_paid": float(license_row["amount_paid"]),
                "amount_remaining": 0,
                "obligations": [],
                "company": BundleWorkflowService._format_company(company),
                "bundle": BundleWorkflowService._format_bundle(bundle),
                "fiscal_year": fiscal_year,
                "currency": "XAF",
                "processing_modes_available": [],
            }

        if not license_row:
            # Create new license + obligations via LicenseService
            license_data = await LicenseService.open_license(conn, {
                "company_id": company_id,
                "bundle_id": bundle["id"],
                "zone_id": company["zone_id"],
                "city_id": company["city_id"],
                "fiscal_year": fiscal_year,
            }, user_id=user_id)
            license_id = license_data["id"]

            # Emit license creation notification (deferred email to owner)
            notification = license_data.get("_notification")
            if notification:
                try:
                    from app.core.events import EventBus, EventType
                    EventBus.publish_nowait(EventType.LICENSE_CREATED, notification)
                except Exception as e:
                    logger.warning("Failed to publish LICENSE_CREATED event: %s", e)
        else:
            license_id = license_row["id"]

        # 4. Fetch obligations with service/ministry details
        obligations = await conn.fetch("""
            SELECT lo.*,
                   fs.name_es as fiscal_service_name,
                   m.name_es as ministry_name
            FROM license_obligations lo
            LEFT JOIN fiscal_services fs ON lo.fiscal_service_id = fs.id
            LEFT JOIN ministries m ON lo.ministry_id = m.id
            WHERE lo.license_id = $1
            ORDER BY
                CASE lo.fee_type
                    WHEN 'tesoro' THEN 1
                    WHEN 'municipal' THEN 2
                    WHEN 'chamber' THEN 3
                END,
                lo.amount DESC
        """, license_id)

        # Re-fetch license (might have been just created)
        license_row = await conn.fetchrow(
            "SELECT * FROM commercial_licenses WHERE id = $1",
            license_id,
        )

        formatted_obligations = []
        for ob in obligations:
            is_payable = ob["status"] in ("pending", "overdue")
            formatted_obligations.append({
                "id": str(ob["id"]),
                "bundle_item_id": str(ob["bundle_item_id"]),
                "fiscal_service_name": ob["fiscal_service_name"] or "Obligación fiscal",
                "fee_type": ob["fee_type"],
                "ministry_name": ob["ministry_name"] or "",
                "amount": float(ob["amount"]),
                "penalty_amount": float(ob["penalty_amount"]),
                "total": float(ob["amount"] + ob["penalty_amount"]),
                "status": ob["status"],
                "is_payable": is_payable,
                "due_date": ob["due_date"].isoformat() if ob["due_date"] else None,
                "paid_at": ob["paid_at"].isoformat() if ob["paid_at"] else None,
            })

        total = float(license_row["total_amount"])
        paid = float(license_row["amount_paid"])

        return {
            "license_id": str(license_id),
            "already_complete": False,
            "license_status": license_row["status"],
            "total_amount": total,
            "amount_paid": paid,
            "amount_remaining": total - paid,
            "obligations": formatted_obligations,
            "company": BundleWorkflowService._format_company(company),
            "bundle": BundleWorkflowService._format_bundle(bundle),
            "fiscal_year": fiscal_year,
            "currency": "XAF",
            "processing_modes_available": ["per_line", "consolidated"],
        }

    # ================================================================
    # Step 2: Validate selection before payment
    # ================================================================

    @staticmethod
    async def validate_selection(
        conn,
        license_id: UUID,
        processing_mode: str,
        selected_obligation_ids: Optional[List[UUID]] = None,
    ) -> Dict[str, Any]:
        """Validate mode + obligation selection before payment.

        Args:
            license_id: License to pay
            processing_mode: 'per_line' or 'consolidated'
            selected_obligation_ids: Required for per_line, ignored for consolidated

        Returns:
            Validated selection summary with total amount
        """
        if processing_mode not in ("per_line", "consolidated"):
            raise ValueError("INVALID_PROCESSING_MODE")

        license_row = await conn.fetchrow(
            "SELECT * FROM commercial_licenses WHERE id = $1", license_id
        )
        if not license_row:
            raise ValueError("LICENSE_NOT_FOUND")
        if license_row["status"] in ("suspended", "closed"):
            raise ValueError("LICENSE_SUSPENDED")
        if license_row["status"] == "complete":
            raise ValueError("LICENSE_ALREADY_COMPLETE")

        # Fetch payable obligations
        payable = await conn.fetch("""
            SELECT id, fee_type, amount, penalty_amount
            FROM license_obligations
            WHERE license_id = $1 AND status IN ('pending', 'overdue')
        """, license_id)

        if not payable:
            raise ValueError("NO_PAYABLE_OBLIGATIONS")

        payable_ids = {r["id"] for r in payable}
        payable_map = {r["id"]: r for r in payable}

        if processing_mode == "consolidated":
            # All payable obligations selected
            selected = payable
        else:
            # per_line: validate selection
            if not selected_obligation_ids:
                raise ValueError("NO_OBLIGATIONS_SELECTED")

            # Check all selected IDs are valid and payable
            for oid in selected_obligation_ids:
                if oid not in payable_ids:
                    raise ValueError(f"OBLIGATION_NOT_PAYABLE:{oid}")

            selected = [payable_map[oid] for oid in selected_obligation_ids]

        total_amount = sum(
            float(ob["amount"]) + float(ob["penalty_amount"])
            for ob in selected
        )

        return {
            "valid": True,
            "processing_mode": processing_mode,
            "selected_count": len(selected),
            "total_amount": total_amount,
            "selected_obligation_ids": [str(ob["id"]) for ob in selected],
            "currency": "XAF",
        }

    # ================================================================
    # Step 3: Initiate payment (atomic transaction)
    # ================================================================

    @staticmethod
    async def initiate_payment(
        conn,
        license_id: UUID,
        processing_mode: str,
        payment_method: str,
        selected_obligation_ids: List[UUID],
        user_id: UUID,
        phone_number: Optional[str] = None,
        wizard_session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create service_request + service_payment + link obligations.

        This is the ATOMIC step — all-or-nothing within a transaction.

        Flow:
          1. Validate (re-check obligations are still payable — race protection)
          2. Create service_request
          2b. Persist documents from wizard session to Firebase (if session_id provided)
          3. Update license.processing_mode + service_request_id
          4. Create service_payment
          5. Link obligations to payment (UPDATE ... WHERE status IN (...) RETURNING)
          6. Log compliance events

        Returns:
            Payment result (redirect_url for BANGE, reference for cash)
        """
        from app.modules.payments.services.processors.base import (
            PaymentContext,
        )
        from app.modules.payments.services.processors.registry import (
            PaymentProcessorRegistry,
        )
        from app.modules.service_requests.repositories.service_request_repository import (
            ServiceRequestRepository,
        )
        from app.modules.fiscal_services.repositories.license_repository import (
            LicenseRepository,
        )

        # Transaction-scoped timeouts — CLAUDE.md lock ordering requirement.
        # Prevents deadlock fan-out when many agents/users touch the same
        # commercial_license / service_requests / license_obligations chain.
        await conn.execute("SET LOCAL lock_timeout = '3s'")
        await conn.execute("SET LOCAL statement_timeout = '10s'")

        # 1. Re-validate within transaction (race protection)
        # NOWAIT: fail immediately if another transaction is locking this license
        # (prevents blocking during BANGE API call which holds the lock 2-5s)
        try:
            license_row = await conn.fetchrow(
                "SELECT * FROM commercial_licenses WHERE id = $1 FOR UPDATE NOWAIT",
                license_id,
            )
        except Exception as lock_err:
            if "could not obtain lock" in str(lock_err).lower():
                raise ValueError("PAYMENT_ALREADY_IN_PROGRESS")
            raise
        if not license_row:
            raise ValueError("LICENSE_NOT_FOUND")
        if license_row["status"] in ("suspended", "closed", "complete"):
            raise ValueError("LICENSE_NOT_PAYABLE")

        # Audit: log third-party bundle payments (user paying for a company
        # they don't own). Consistent with BundleWorkflowService.initiate:
        # GE policy allows a citizen to pay for a family/acquaintance's
        # obligations. We log for traceability, we DO NOT block.
        is_company_member = await conn.fetchval(
            "SELECT 1 FROM user_company_roles "
            "WHERE company_id = $1 AND user_id = $2 AND is_active = true",
            license_row["company_id"], user_id,
        )
        if not is_company_member:
            logger.info(
                "AUDIT: third-party bundle payment — user=%s license=%s "
                "company=%s processing_mode=%s amount_obligations=%d",
                user_id, license_id, license_row["company_id"],
                processing_mode, len(selected_obligation_ids),
            )

        # Check for in-flight payment overlap on the SELECTED obligations.
        # Scoped per-obligation (not company-wide) so a citizen who paid 8/10
        # can initiate a 2nd bundle for the remaining 2 once all splits from
        # the 1st complete. Only block if a selected obligation already has an
        # in-flight payment (status='payment_pending').
        inflight_obligation = await conn.fetchrow("""
            SELECT lo.id, sr.id AS sr_id, sr.reference AS sr_reference
            FROM license_obligations lo
            JOIN service_payments sp ON sp.id = lo.payment_id
            JOIN service_requests sr ON sr.id = sp.service_request_id
            WHERE lo.id = ANY($1::uuid[])
              AND lo.license_id = $2
              AND lo.status = 'payment_pending'
            LIMIT 1
        """, selected_obligation_ids, license_id)
        if inflight_obligation:
            raise ValueError(
                f"PAYMENT_ALREADY_IN_PROGRESS:{inflight_obligation['sr_id']}:"
                f"{inflight_obligation['sr_reference']}"
            )

        # Verify obligations are still payable. JOIN fiscal_services so the
        # calculation_details snapshot carries a human-readable name per
        # obligation — surfaced later in the receipt PDF (P8.2-X8 follow-up).
        obligations = await conn.fetch("""
            SELECT lo.id, lo.fee_type, lo.amount, lo.penalty_amount,
                   lo.license_id, lo.ministry_id, lo.fiscal_service_id,
                   fs.name_es AS fiscal_service_name,
                   fs.service_code AS fiscal_service_code
            FROM license_obligations lo
            LEFT JOIN fiscal_services fs ON fs.id = lo.fiscal_service_id
            WHERE lo.id = ANY($1::uuid[])
              AND lo.license_id = $2
              AND lo.status IN ('pending', 'overdue')
        """, selected_obligation_ids, license_id)

        if len(obligations) != len(selected_obligation_ids):
            raise ValueError("OBLIGATION_RACE_CONDITION")

        total_amount = sum(
            r["amount"] + r["penalty_amount"] for r in obligations
        )

        # 2. Group obligations by target payment entity (Mode A: per-entity validation)
        # Routing: chamber→CAMARA, municipal→AYUNTAMIENTO, tesoro→TESORO
        # Dynamic: uses v_obligation_routing config, no hardcoded entity codes
        FEE_TO_ENTITY_SQL = """
            SELECT DISTINCT validates_fee_type, entity_code
            FROM v_obligation_routing
            WHERE routing_role = 'payment_validator'
        """
        fee_entity_rows = await conn.fetch(FEE_TO_ENTITY_SQL)
        fee_to_entity = {r["validates_fee_type"]: r["entity_code"] for r in fee_entity_rows}
        # Fallback: unknown fee_types go to TESORO
        default_entity = "TESORO"

        # Determine the primary entity (entity with the most obligations = service_request owner)
        entity_groups: dict = {}  # entity_code -> list of obligations
        for ob in obligations:
            target_entity = fee_to_entity.get(ob["fee_type"], default_entity)
            entity_groups.setdefault(target_entity, []).append(ob)

        # Primary entity = largest group (or TESORO if only tesoro obligations)
        primary_entity = max(entity_groups, key=lambda e: len(entity_groups[e]))

        # 2b. Create service_request (1 per bundle, primary entity owns it).
        # Bundle workflow requires commercial_license_id + fiscal_year (migration 291,
        # trigger fn_enforce_bundle_sr_integrity). bundle_id + zone_id are inserted in
        # the same INSERT to avoid a redundant UPDATE round-trip on the critical path.
        sr_repo = ServiceRequestRepository()
        form_data = {
            "license_id": str(license_id),
            "processing_mode": processing_mode,
            "obligation_ids": [str(oid) for oid in selected_obligation_ids],
            "company_id": str(license_row["company_id"]),
            "entity_payments": {ec: len(obs) for ec, obs in entity_groups.items()},
        }

        try:
            sr = await sr_repo.create(
                db=conn,
                user_id=user_id,
                workflow_code="BUNDLE_PAYMENT",
                solicitud_type="expedicion",
                form_data=form_data,
                company_id=license_row["company_id"],
                entity_code=primary_entity,
                commercial_license_id=license_id,
                fiscal_year=license_row["fiscal_year"],
                bundle_id=license_row["bundle_id"],
                zone_id=license_row["zone_id"],
                source="citizen_wizard",
            )
        except asyncpg.UniqueViolationError:
            # Safety net: idx_sr_commercial_license_unique (migration 291,
            # relaxed in 297 to exclude terminal statuses PAID/EXPIRED).
            # Fires when a concurrent request creates an SR for the same
            # license while one is already in-flight. Deterministic: the
            # caller should resume the existing SR, not retry.
            raise ValueError("PAYMENT_ALREADY_IN_PROGRESS")
        except asyncpg.CheckViolationError as ex:
            # Defensive: fn_enforce_bundle_sr_integrity fired despite our
            # fail-fast guard in sr_repo.create(). Surface a clear metier code
            # instead of leaking a 500 to the client.
            logger.error(
                "Bundle SR integrity trigger fired unexpectedly: %s (license=%s)",
                ex, license_id,
            )
            raise ValueError("BUNDLE_INTEGRITY_ERROR")
        service_request_id = sr["id"]

        # 2b. Persist documents from wizard session cache to Firebase (if provided)
        # Same process as PredefinedWorkflow: base64 from Redis → Firebase Storage → uploaded_files
        if wizard_session_id:
            try:
                doc_count = await BundleWorkflowService._persist_session_documents(
                    conn, wizard_session_id, user_id, service_request_id,
                )
                if doc_count > 0:
                    logger.info(
                        "Persisted %d document(s) from wizard session %s to SR %s",
                        doc_count, wizard_session_id, service_request_id,
                    )
            except Exception as e:
                # Document persistence failure should NOT block payment
                logger.warning(
                    "Failed to persist documents from session %s: %s",
                    wizard_session_id, e,
                )

        # 3. Update license with processing_mode chosen by citizen.
        # service_request_id is synced automatically by trigger trg_sync_license_sr_id
        # (AFTER INSERT on service_requests, migration 291) — do NOT write it here.
        await conn.execute("""
            UPDATE commercial_licenses
            SET processing_mode = $1,
                updated_at = NOW()
            WHERE id = $2
        """, processing_mode, license_id)

        # Update service_request amounts and mark as SUBMITTED.
        # bundle_id / zone_id were already set at INSERT time above.
        await conn.execute("""
            UPDATE service_requests
            SET total_amount = $1, base_amount = $1,
                currency = 'XAF', status = 'SUBMITTED',
                submitted_at = NOW()
            WHERE id = $2
        """, total_amount, service_request_id)

        # 4. Create N service_payments — one per target entity (Mode A split)
        #    Each entity validates their portion independently.
        #    Electronic payments (BANGE): all complete simultaneously via webhook.
        #    Cash/check: each entity validates their payment in their queue.
        from app.modules.payments.models.payment import PaymentMethod
        try:
            pm_enum = PaymentMethod(payment_method)
        except ValueError:
            raise ValueError(f"INVALID_PAYMENT_METHOD:{payment_method}")

        registry = PaymentProcessorRegistry()
        all_payment_ids = []
        primary_payment_id = None

        for entity_code, entity_obligations in entity_groups.items():
            entity_amount = sum(
                ob["amount"] + ob["penalty_amount"] for ob in entity_obligations
            )
            entity_ob_ids = [ob["id"] for ob in entity_obligations]

            calculation_details = {
                "obligations": [
                    {
                        "id": str(ob["id"]),
                        "fee_type": ob["fee_type"],
                        "amount": float(ob["amount"]),
                        "penalty": float(ob["penalty_amount"]),
                        # Human-readable name for receipts / citizen summaries.
                        # Falls back to fee_type label if the fiscal_service link
                        # is missing (legacy data).
                        "name": ob.get("fiscal_service_name") or None,
                        "code": ob.get("fiscal_service_code") or None,
                    }
                    for ob in entity_obligations
                ],
                "processing_mode": processing_mode,
                "license_id": str(license_id),
                "target_entity": entity_code,
            }

            context = PaymentContext(
                service_request_id=str(service_request_id),
                user_id=str(user_id),
                amount=Decimal(str(entity_amount)),
                currency="XAF",
                payment_method=pm_enum,
                tariff_breakdown=calculation_details,
                workflow_code="BUNDLE_PAYMENT",
                service_name=f"Obligaciones Fiscales - {entity_code}",
                user_phone=phone_number,
                metadata={
                    # Tells PaymentAssignmentHandler which entity's agents
                    # should validate THIS split (TESORO / AYUNTAMIENTO /
                    # CAMARA_COMERCIO). Without this the handler falls back
                    # to TESORO and every bundle split ends up in the
                    # Treasury queue regardless of fee_type.
                    "target_entity_code": entity_code,
                },
            )

            payment_result = await registry.initiate_payment(conn, context)
            if not payment_result.success:
                raise ValueError(
                    f"PAYMENT_INITIATION_FAILED:{entity_code}:{payment_result.error}"
                )

            # Update service_payment with entity_code + fee_type + company_id.
            # fee_type MUST be one of tesoro/municipal/chamber (CHECK constraint
            # service_payments_fee_type_check). Because entity_groups are built
            # from v_obligation_routing which maps fee_type <-> entity_code 1:1,
            # every obligation in entity_obligations shares the same fee_type
            # as the entity_code — so taking the first one is safe and
            # semantically correct.
            entity_fee_type = entity_obligations[0]["fee_type"]
            await conn.execute(
                """
                UPDATE service_payments
                SET fee_type = $2,
                    entity_code = $3,
                    company_id = $4
                WHERE id = $1::uuid
                """,
                payment_result.payment_id,
                entity_fee_type,
                entity_code,
                license_row["company_id"],
            )

            # Inline auto-assignment INSIDE the transaction.
            # Rationale (P8.2-B1.2): the previous flow relied on an async event
            # handler (PaymentAssignmentHandler → PAYMENT_MANUAL_PENDING) to do
            # the assignment. That handler runs on a different connection (its
            # own pool slot) while this transaction is still open, which means
            # it cannot see the just-INSERTed service_payments row in its MVCC
            # snapshot. The handler's `UPDATE service_payments ... WHERE id=X`
            # silently returned `UPDATE 0` and the row stayed
            # assigned_agent_id=NULL. Observed on 2026-04-15 as the
            # CAMARA_COMERCIO split of LIC-2026-00001 staying unassigned while
            # AYUNT/TESORO got assigned by pure timing luck.
            # Doing the assignment inline eliminates the cross-transaction race
            # entirely: both the INSERT assignments row and the UPDATE
            # service_payments run in T1 with full row visibility.
            #
            # Location routing (P8.2-B1.3): the SR created here has no
            # entity_location_id of its own (bundle does not pick a site), so
            # we derive the target entity_location from the commercial_license
            # city. Without this, auto_assign_item has no city preference and
            # picks agents "at random" across all the entity's sites — a bundle
            # for a Malabo license was being routed to Bata agents and vice
            # versa. Fall back to no-location filter if the entity has no
            # active location in that city.
            try:
                from app.modules.assignment.services.auto_assignment_service import (
                    AutoAssignmentService,
                )

                target_location_id = None
                if license_row.get("city_id"):
                    target_location_id = await conn.fetchval("""
                        SELECT el.id
                        FROM entity_locations el
                        JOIN entities e ON e.id = el.entity_id
                        WHERE e.code = $1
                          AND el.city_id = $2
                          AND el.is_active = true
                        ORDER BY el.is_main_office DESC NULLS LAST
                        LIMIT 1
                    """, entity_code, license_row["city_id"])

                assignment_service = AutoAssignmentService()
                assignment = await assignment_service.auto_assign_item(
                    db=conn,
                    item_id=UUID(str(payment_result.payment_id)),
                    item_type="payment_validation",
                    item_data={
                        "amount": float(entity_amount),
                        "payment_method": payment_method,
                    },
                    entity_code=entity_code,
                    entity_location_id=target_location_id,
                    priority_level=5,
                )
                if assignment:
                    await conn.execute(
                        """
                        UPDATE service_payments
                        SET assigned_agent_id = $1::uuid,
                            assigned_at = NOW(),
                            updated_at = NOW()
                        WHERE id = $2::uuid
                        """,
                        str(assignment.agent_profile_id),
                        payment_result.payment_id,
                    )
                    logger.info(
                        "OMS: Payment %s inline-assigned to agent_profile %s "
                        "(entity=%s)",
                        payment_result.payment_id,
                        assignment.agent_profile_id,
                        entity_code,
                    )
                else:
                    logger.warning(
                        "OMS: No %s agent available for payment %s; remains "
                        "unassigned (PaymentAssignmentHandler fallback may "
                        "still pick it up post-commit)",
                        entity_code,
                        payment_result.payment_id,
                    )
            except Exception as assign_err:
                # Non-fatal: log and continue. PaymentAssignmentHandler will
                # receive its event and retry the assignment after commit.
                logger.error(
                    "OMS: Inline auto-assignment failed for payment %s "
                    "(%s): %s. Falling back to event-based handler.",
                    payment_result.payment_id, entity_code, assign_err,
                )

            # Link this entity's obligations to their payment
            updated_rows = await conn.fetch("""
                UPDATE license_obligations
                SET payment_id = $1::uuid,
                    status = 'payment_pending',
                    updated_at = NOW()
                WHERE id = ANY($2::uuid[])
                  AND status IN ('pending', 'overdue')
                RETURNING id
            """, payment_result.payment_id, entity_ob_ids)

            if len(updated_rows) != len(entity_ob_ids):
                logger.error(
                    "OMS: %s — Expected %d obligations linked, got %d",
                    entity_code, len(entity_ob_ids), len(updated_rows),
                )

            # Log compliance events per obligation
            for ob in entity_obligations:
                await LicenseRepository.log_event(
                    conn, license_id, "payment_initiated",
                    event_data={
                        "payment_id": payment_result.payment_id,
                        "fee_type": ob["fee_type"],
                        "amount": float(ob["amount"]),
                        "payment_method": payment_method,
                        "target_entity": entity_code,
                    },
                    obligation_id=ob["id"],
                    triggered_by=user_id,
                )

            all_payment_ids.append(payment_result.payment_id)
            if entity_code == primary_entity:
                primary_payment_id = payment_result.payment_id

            logger.info(
                "OMS: Created payment %s for %s (%d obligations, %s XAF)",
                payment_result.payment_id, entity_code,
                len(entity_obligations), entity_amount,
            )

        # 7b. Schedule async counter refresh AFTER transaction commits.
        # Obligations moved from pending/overdue → payment_pending, so overdue
        # counts must be decremented. Done async to avoid adding 250-500ms
        # to the critical transaction path (statement_timeout = 5-10s).
        # The EventBus handler runs on a separate connection post-commit.
        try:
            from app.core.events import EventBus, EventType
            EventBus.publish_nowait(EventType.LICENSE_COUNTER_REFRESH, {
                "license_id": str(license_id),
                "user_id": str(user_id),
                "trigger": "initiate_payment",
            })
        except Exception as e:
            logger.warning("Failed to schedule counter refresh: %s", e)

        # 8. Update service_request with primary payment_id
        await conn.execute("""
            UPDATE service_requests
            SET payment_id = $1::uuid,
                payment_status = 'processing',
                status = 'PAYMENT_PROCESSING'
            WHERE id = $2
        """, primary_payment_id, service_request_id)

        # 9. (removed in P8.2-B1) We no longer re-publish PAYMENT_MANUAL_PENDING
        # here. `manual_processor.initiate` (called by registry.initiate_payment
        # above) already publishes the event once per split with the correct
        # `target_entity_code` taken from PaymentContext.metadata. The previous
        # second publish used the wrong key ("entity_code" instead of
        # "target_entity_code"), which caused PaymentAssignmentHandler to fall
        # back to DEFAULT_VALIDATOR_ENTITY_CODE="TESORO" and route AYUNTAMIENTO
        # and CAMARA_COMERCIO splits to the Treasury queue — observed on
        # 2026-04-15 as the assignment inversion where tesoreria.ge was handed
        # the AYUNT/CAMARA splits while the TESORO split ended up unassigned.

        # 10. Notify company owner if payment initiated by a third party
        is_owner = await conn.fetchval(
            "SELECT 1 FROM user_company_roles WHERE company_id = $1 AND user_id = $2",
            license_row["company_id"], user_id,
        )
        if not is_owner:
            try:
                owner_row = await conn.fetchrow("""
                    SELECT u.id, u.email, u.first_name
                    FROM users u
                    JOIN user_company_roles ucr ON ucr.user_id = u.id
                    WHERE ucr.company_id = $1 AND ucr.role = 'company_owner'
                    LIMIT 1
                """, license_row["company_id"])
                if owner_row and owner_row["email"]:
                    logger.info(
                        "AUDIT: third-party payment — notifying owner %s for company %s",
                        owner_row["id"], license_row["company_id"],
                    )
                    # Email will be sent via CommunicationService in Session 7C
                    # For now, log the event for audit trail
                    await LicenseRepository.log_event(
                        conn, license_id, "payment_initiated",
                        event_data={
                            "third_party_user_id": str(user_id),
                            "owner_user_id": str(owner_row["id"]),
                            "owner_notified": True,
                        },
                        triggered_by=user_id,
                    )
            except Exception as e:
                logger.warning("Failed to notify owner for third-party payment: %s", e)

        entities_summary = ", ".join(
            f"{ec}({len(obs)})" for ec, obs in entity_groups.items()
        )
        logger.info(
            "OMS bundle payment initiated: license=%s, mode=%s, "
            "method=%s, obligations=%d, amount=%s XAF, entities=[%s], payments=%d",
            license_id, processing_mode, payment_method,
            len(obligations), total_amount, entities_summary, len(all_payment_ids),
        )

        # 11. Notify citizen: publish PAYMENT_CASH_PENDING for bundle.
        # manual_processor skips this event for bundles (P8.2-B1.2 assignment
        # race fix), but the citizen notification is still needed. Without
        # this, the citizen has ZERO confirmation after initiating a cash
        # bundle payment. The handler sends payment_cash_pending email + SMS.
        if payment_method in ("cash", "check"):
            try:
                from app.core.events import EventBus, EventType

                # Fetch citizen contact info (best-effort, outside critical path)
                citizen = await conn.fetchrow(
                    "SELECT email, phone_number, first_name, last_name "
                    "FROM users WHERE id = $1",
                    user_id,
                )
                if citizen and citizen["email"]:
                    EventBus.publish_nowait(EventType.PAYMENT_CASH_PENDING, {
                        "payment_id": primary_payment_id,
                        "payment_reference": primary_payment_id,
                        "service_request_id": str(service_request_id),
                        "amount": float(total_amount),
                        "method": payment_method,
                        "user_id": str(user_id),
                        "user_email": citizen["email"],
                        "user_phone": citizen["phone_number"],
                        "user_name": (
                            f"{citizen['first_name'] or ''} "
                            f"{citizen['last_name'] or ''}".strip()
                        ),
                        "company_name": license_row.get("company_name")
                            or (await conn.fetchval(
                                "SELECT legal_name FROM companies WHERE id = $1",
                                license_row["company_id"],
                            )),
                        "workflow_code": "BUNDLE_PAYMENT",
                        "obligations_count": len(obligations),
                        "entities": entities_summary,
                    })
                    logger.info(
                        "PAYMENT_CASH_PENDING event published for bundle "
                        "payment %s (citizen=%s)",
                        primary_payment_id, citizen["email"],
                    )
            except Exception as e:
                # Non-fatal: log and continue. The payment is already created.
                logger.warning(
                    "Failed to publish PAYMENT_CASH_PENDING for bundle: %s", e
                )

        # Build trilingual messages for the response
        if payment_method in ("cash", "check"):
            msg_es = "Su solicitud de pago ha sido registrada. Cada entidad validará su parte."
            msg_fr = "Votre demande de paiement a été enregistrée. Chaque entité validera sa part."
            msg_en = "Your payment request has been registered. Each entity will validate their portion."
        else:
            msg_es = "Pago iniciado correctamente."
            msg_fr = "Paiement initié avec succès."
            msg_en = "Payment initiated successfully."

        return {
            "success": True,
            "service_request_id": str(service_request_id),
            "payment_id": primary_payment_id,
            "payment_ids": all_payment_ids,
            "payment_reference": primary_payment_id,
            "redirect_url": None,  # Cash/check: no redirect; BANGE: handled per-payment
            "requires_action": payment_method in ("cash", "check"),
            "action_type": "agent_validation" if payment_method in ("cash", "check") else None,
            "total_amount": float(total_amount),
            "obligations_count": len(obligations),
            "processing_mode": processing_mode,
            "entity_payments": {
                ec: {"count": len(obs), "amount": float(sum(o["amount"] + o["penalty_amount"] for o in obs))}
                for ec, obs in entity_groups.items()
            },
            "message_es": msg_es,
            "message_fr": msg_fr,
            "message_en": msg_en,
        }

    # ================================================================
    # Document Persistence (Firebase)
    # ================================================================

    @staticmethod
    async def _persist_session_documents(
        conn, session_id: str, user_id: UUID, service_request_id: UUID,
    ) -> int:
        """Persist documents from wizard session cache (Redis) to Firebase Storage.

        Same process as PredefinedWorkflow's persist_to_db():
          1. Load session from Redis cache
          2. For each document: decode base64 → upload to Firebase Storage
          3. Create uploaded_files + service_request_documents records in DB

        Args:
            conn: Database connection (inside transaction)
            session_id: Wizard session ID
            user_id: User who uploaded the documents
            service_request_id: Service request to link documents to

        Returns:
            Number of documents persisted
        """
        import base64
        from app.core.cache import get_cache

        cache = get_cache()
        cache_key = f"wizard_session:{session_id}"
        session_data = await cache.get(cache_key)

        if not session_data or not isinstance(session_data, dict):
            logger.warning("Session %s not found in cache — no documents to persist", session_id)
            return 0

        documents = session_data.get("documents", {})
        if not documents:
            return 0

        from app.modules.documents.services.storage_service import firebase_storage_service
        from app.modules.documents.repositories.document_repository import (
            document_repository,
        )

        persisted = 0
        for doc_code, doc_data in documents.items():
            if not doc_data.get("content_b64"):
                continue

            try:
                file_content = base64.b64decode(doc_data["content_b64"])

                upload_result = await firebase_storage_service.upload_user_document(
                    user_id=str(user_id),
                    application_id=str(service_request_id),
                    file=file_content,
                    metadata={
                        "filename": doc_data.get("file_name", f"{doc_code}.pdf"),
                        "mime_type": doc_data.get("mime_type", "application/pdf"),
                        "document_code": doc_code,
                        "document_name": doc_data.get("document_name") or doc_code,
                    },
                )

                await document_repository.add_document(
                    db=conn,
                    service_request_id=service_request_id,
                    document_code=doc_code,
                    document_name=doc_data.get("document_name") or doc_code,
                    file_path=upload_result.file_path,
                    file_name=doc_data.get("file_name", f"{doc_code}.pdf"),
                    file_size=doc_data.get("file_size", len(file_content)),
                    mime_type=doc_data.get("mime_type", "application/pdf"),
                    uploaded_by=user_id,
                    source="bundle_workflow",
                    file_hash=doc_data.get("doc_hash"),
                )

                persisted += 1
                logger.info(
                    "Document %s persisted to Firebase for SR %s",
                    doc_code, service_request_id,
                )

            except Exception as e:
                logger.error(
                    "Failed to persist document %s for SR %s: %s",
                    doc_code, service_request_id, e,
                )

        # Clean up session from cache after documents are persisted
        try:
            await cache.delete(cache_key)
        except Exception:
            pass

        return persisted

    # ================================================================
    # Helpers
    # ================================================================

    @staticmethod
    def _format_company(row) -> Dict[str, Any]:
        return {
            "id": str(row["id"]),
            "legal_name": row["legal_name"],
            "tax_id": row["tax_id"],
            "nif": row.get("nif"),
            "registration_number": row.get("registration_number"),
            "commerce_type": row.get("commerce_type"),
            "regimen_fiscal": row.get("regimen_fiscal"),
            "zone_code": row.get("zone_code"),
            "city_name": row.get("city_name"),
            "is_verified": row.get("is_verified", False),
        }

    @staticmethod
    def _format_bundle(row) -> Dict[str, Any]:
        return {
            "id": str(row["id"]),
            "commerce_type": row["commerce_type"],
            "name_es": row["name_es"],
        }
