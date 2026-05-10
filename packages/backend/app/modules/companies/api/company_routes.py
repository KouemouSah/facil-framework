"""Company Routes - Business Company Management API

Includes:
- User-scoped CRUD (membership-based access)
- Admin endpoints (permission-based access)
"""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.security import HTTPBearer
from typing import Dict, Any, List, Optional
from loguru import logger

from app.modules.companies.models import (
    CompanyCreate, CompanyUpdate, CompanyResponse,
    CompanyListResponse, CompanyMember, CompanyMemberRole,
    AddMemberRequest, UpdateMemberRoleRequest,
    CompanyAdminResponse, CompanyAdminListResponse,
    CompanyStatsResponse, CompanySearchResult, CompanyVerifyRequest,
    CompanyClassifyResponse,
    AdminCompanyCreateRequest, AdminCompanyCreateResponse,
)
from app.modules.companies.repositories import CompanyRepository
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.modules.permissions.services.permission_service import create_permission_service
from app.database.connection import get_database

router = APIRouter(tags=["Companies"])
security = HTTPBearer()
company_repository = CompanyRepository()


# =============================================================================
# IMPORTANT: Static/admin paths MUST be declared BEFORE /{company_id}
# to avoid FastAPI matching "admin" as a UUID → 422 error.
# =============================================================================


# =============================================================================
# ADMIN ENDPOINTS (permission-based)
# =============================================================================

@router.get("/admin/all", response_model=CompanyAdminListResponse)
async def admin_list_all_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=100),
    is_active: Optional[bool] = Query(None),
    is_verified: Optional[bool] = Query(None),
    regimen_fiscal: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    city_id: Optional[str] = Query(None),
    archived: str = Query(
        "active",
        regex="^(active|archived|all)$",
        description="Archive scope. 'active' (default) excludes soft-deleted; "
                    "'archived' returns only soft-deleted; 'all' returns both.",
    ),
    sort_by: str = Query("created_at", regex="^(created_at|legal_name|is_active|is_verified|member_count|license_count)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("company.view_all")),
):
    """List all companies with filters — admin view.

    Includes the archive scope toggle (Phase 4 of SOFT_DELETE_COMPANIES_PLAN).
    Default 'active' preserves the legacy list behaviour; the archived view
    on /admin/companies/archived passes archived='archived'.
    """
    offset = (page - 1) * page_size

    items = await company_repository.list_all(
        db, limit=page_size, offset=offset,
        search=search, is_active=is_active, is_verified=is_verified,
        regimen_fiscal=regimen_fiscal, zone_id=zone_id, city_id=city_id,
        sort_by=sort_by, sort_order=sort_order,
        archived=archived,
    )
    total = await company_repository.count_all(
        db, search=search, is_active=is_active, is_verified=is_verified,
        regimen_fiscal=regimen_fiscal, zone_id=zone_id, city_id=city_id,
        archived=archived,
    )

    return CompanyAdminListResponse(
        items=[CompanyAdminResponse(**c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/admin/stats", response_model=CompanyStatsResponse)
async def admin_company_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("company.view_stats")),
):
    """Aggregated company statistics for admin dashboard."""
    stats = await company_repository.get_stats(db)
    return CompanyStatsResponse(**stats)


@router.get("/admin/search", response_model=List[CompanySearchResult])
async def admin_search_companies(
    q: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(10, ge=1, le=50),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("company.view")),
):
    """Lightweight company search for autocomplete (admin/agent)."""
    results = await company_repository.search(db, q, limit)
    return [CompanySearchResult(**r) for r in results]


@router.put("/admin/{company_id}/verify", response_model=CompanyResponse)
async def admin_verify_company(
    company_id: str,
    body: CompanyVerifyRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("company.verify")),
):
    """Toggle company verification status (admin only)."""
    result = await company_repository.verify(db, company_id, body.is_verified)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")
    action = "verified" if body.is_verified else "unverified"
    logger.info(f"Admin {user_id} {action} company {company_id}")
    return CompanyResponse(**result)


@router.post("/admin/{company_id}/classify", response_model=CompanyClassifyResponse)
async def admin_classify_company(
    company_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("company.update")),
):
    """Classify company's fiscal regime using the 3-layer classification agent.

    Uses the same engine as auto-classification (rules + LLM + validation).
    Updates regimen_fiscal + commerce_type. Creates audit trail in
    company_classification_history.
    """
    from app.modules.companies.services.classification_agent import classification_agent

    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")
    result = await classification_agent.classify_and_update(
        db, company_id, triggered_by="manual",
        user_id=user_id,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    logger.info(
        f"Admin {user_id} classified company {company_id}: "
        f"{result.regimen_fiscal} (confidence={result.confidence:.0%})"
    )
    return CompanyClassifyResponse(
        regimen_fiscal=result.regimen_fiscal,
        confidence=result.confidence,
        reason=result.reason,
    )


@router.post("/admin/create-with-license", response_model=AdminCompanyCreateResponse,
              status_code=status.HTTP_201_CREATED)
async def admin_create_company_with_license(
    data: AdminCompanyCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("company.manage")),
):
    """Create company manually + auto-generate licence and obligations.

    Flow (single transaction):
    1. Validate zone_code → zone_id
    2. Validate commerce_type → bundle exists
    3. Check NIF/registration_number uniqueness
    4. Create company (regimen_fiscal = 'bundle')
    5. Open licence for current fiscal year
    6. Auto-generate obligations from bundle items × zone

    Source tagged as 'admin_manual' for audit trail.
    """
    from datetime import date as _date
    from app.modules.fiscal_services.services.license_service import LicenseService

    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")
    fiscal_year = _date.today().year

    async with db.transaction():
        # 1. Resolve zone_code → zone_id
        zone_row = await db.fetchrow(
            "SELECT id, zone_code, zone_tier FROM commerce_zones WHERE zone_code = $1",
            data.zone_code.upper(),
        )
        if not zone_row:
            raise HTTPException(
                status_code=422,
                detail=f"Zone '{data.zone_code}' not found. Valid: A1-A3, B1-B3, C1-C3, D1-D3",
            )
        zone_id = zone_row["id"]

        # 2. Resolve commerce_type → bundle
        bundle_row = await db.fetchrow(
            "SELECT id, commerce_type, name_es, processing_mode "
            "FROM service_bundles WHERE commerce_type = $1 AND is_active = true",
            data.commerce_type.lower(),
        )
        if not bundle_row:
            valid_types = await db.fetch(
                "SELECT commerce_type FROM service_bundles WHERE is_active = true ORDER BY commerce_type"
            )
            valid_list = ", ".join(r["commerce_type"] for r in valid_types)
            raise HTTPException(
                status_code=422,
                detail=f"Commerce type '{data.commerce_type}' not found. Valid: {valid_list}",
            )
        bundle_id = bundle_row["id"]

        # 3. Check uniqueness (NIF or registration_number)
        if data.nif:
            dup = await db.fetchval(
                "SELECT id FROM companies WHERE nif = $1", data.nif,
            )
            if dup:
                raise HTTPException(status_code=409, detail=f"NIF '{data.nif}' already exists")
        if data.registration_number:
            dup = await db.fetchval(
                "SELECT id FROM companies WHERE registration_number = $1",
                data.registration_number,
            )
            if dup:
                raise HTTPException(
                    status_code=409,
                    detail=f"Registration number '{data.registration_number}' already exists",
                )

        # 4. Resolve city (optional)
        city_id = None
        if data.city_name:
            city_row = await db.fetchrow(
                "SELECT id FROM cities WHERE name ILIKE $1 LIMIT 1",
                data.city_name.strip(),
            )
            if city_row:
                city_id = city_row["id"]

        # 5. Create company
        tax_id = data.nif or data.registration_number or f"ADMIN-{_date.today().isoformat()}"
        company_data = CompanyCreate(
            legal_name=data.legal_name,
            tax_id=tax_id,
            nif=data.nif,
            registration_number=data.registration_number,
            forma_juridica=data.forma_juridica,
            sector_actividad=data.sector_actividad,
            subsector_actividad=data.subsector_actividad,
            objeto_social=data.objeto_social,
            commerce_type=data.commerce_type.lower(),
            regimen_fiscal="bundle",
            representante_legal=data.representante_legal,
            address=data.address,
            phone=data.phone,
            email=data.email,
            employee_count=data.employee_count,
            zone_id=zone_id,
            city_id=city_id,
            is_active=True,
            is_verified=False,
        )

        company_result = await company_repository.create(db, company_data, user_id)
        company_id = company_result["id"]

        logger.info(
            f"Admin {user_id} created company {company_id} "
            f"({data.legal_name}, {data.commerce_type}, zone={data.zone_code})"
        )

        # 6. Open licence → auto-generates obligations
        license_data = {
            "company_id": company_id,
            "bundle_id": bundle_id,
            "zone_id": zone_id,
            "city_id": city_id,
            "fiscal_year": fiscal_year,
            "source": "admin_manual",
        }
        license_result = await LicenseService.open_license(
            conn=db,
            data=license_data,
            user_id=user_id,
        )

        license_id = str(license_result["license"]["id"])
        obligations_count = license_result["license"].get("obligations_total", 0)
        total_amount = float(license_result["license"].get("total_amount", 0))

        logger.info(
            f"Admin created licence {license_id} for company {company_id}: "
            f"{obligations_count} obligations, {total_amount} XAF"
        )

    return AdminCompanyCreateResponse(
        company_id=str(company_id),
        company_name=data.legal_name,
        license_id=license_id,
        license_status="open",
        obligations_count=obligations_count,
        total_amount=total_amount,
        zone_code=data.zone_code.upper(),
        fiscal_year=fiscal_year,
        source="admin_manual",
    )


# =============================================================================
# SUPERVISOR ENDPOINTS (entity-scoped)
# =============================================================================

async def _get_supervisor_entity_id(user_id: str, db) -> Optional[str]:
    """Get entity_id from agent_profiles for the current user."""
    from uuid import UUID as _UUID
    uid = _UUID(user_id) if isinstance(user_id, str) else user_id
    row = await db.fetchrow(
        "SELECT entity_id, is_supervisor FROM agent_profiles WHERE user_id = $1 AND is_active = true",
        uid,
    )
    if not row:
        return None
    return str(row["entity_id"]) if row["entity_id"] else None


@router.get("/supervisor/my-companies", response_model=CompanyAdminListResponse)
async def supervisor_list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=100),
    is_active: Optional[bool] = Query(None),
    is_verified: Optional[bool] = Query(None),
    regimen_fiscal: Optional[str] = Query(None),
    sort_by: str = Query("created_at", regex="^(created_at|legal_name|is_active|is_verified|member_count|license_count)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("company.view_entity_scoped")),
):
    """List companies scoped to supervisor's entity cities.

    Scoping: entity → entity_locations → city_ids →
    companies (city_id match OR commercial_licenses.city_id match).
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    entity_id = await _get_supervisor_entity_id(user_id, db)
    if not entity_id:
        # No entity = no scope = empty result
        return CompanyAdminListResponse(items=[], total=0, page=page, page_size=page_size)

    city_ids = await company_repository.get_entity_city_ids(db, entity_id)
    if not city_ids:
        return CompanyAdminListResponse(items=[], total=0, page=page, page_size=page_size)

    offset = (page - 1) * page_size
    items = await company_repository.list_all(
        db, limit=page_size, offset=offset,
        search=search, is_active=is_active, is_verified=is_verified,
        regimen_fiscal=regimen_fiscal, city_ids=city_ids,
        sort_by=sort_by, sort_order=sort_order,
    )
    total = await company_repository.count_all(
        db, search=search, is_active=is_active, is_verified=is_verified,
        regimen_fiscal=regimen_fiscal, city_ids=city_ids,
    )

    return CompanyAdminListResponse(
        items=[CompanyAdminResponse(**c) for c in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/supervisor/stats", response_model=CompanyStatsResponse)
async def supervisor_company_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _=Depends(permission_required("company.view_entity_scoped")),
):
    """Entity-scoped company statistics for supervisor dashboard."""
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    entity_id = await _get_supervisor_entity_id(user_id, db)
    if not entity_id:
        return CompanyStatsResponse()

    city_ids = await company_repository.get_entity_city_ids(db, entity_id)
    if not city_ids:
        return CompanyStatsResponse()

    stats = await company_repository.get_stats_by_cities(db, city_ids)
    return CompanyStatsResponse(**stats)


# =============================================================================
# USER-SCOPED ENDPOINTS (membership-based)
# =============================================================================

@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    company: CompanyCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Create new company with auto-classification.

    After INSERT, automatically classifies the company's fiscal regime
    using the 3-layer classification agent (rules + LLM + validation).
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")
    result = await company_repository.create(db, company, user_id)
    company_id = result["id"]
    logger.info(f"User {user_id} created company {company_id}")

    # Auto-classify fiscal regime (non-blocking — failure doesn't break create)
    try:
        from app.modules.companies.services.classification_agent import classification_agent
        classification = await classification_agent.classify_company(
            db, result, result.get("zone_id")
        )
        if classification.regimen_fiscal != (result.get("regimen_fiscal") or "pendiente"):
            await db.execute(
                "UPDATE companies SET regimen_fiscal = $2, commerce_type = $3, updated_at = NOW() "
                "WHERE id = $1",
                company_id, classification.regimen_fiscal,
                classification.commerce_type,
            )
            result["regimen_fiscal"] = classification.regimen_fiscal
            result["commerce_type"] = classification.commerce_type
            logger.info(
                f"Auto-classified company {company_id}: {classification.regimen_fiscal} "
                f"(confidence={classification.confidence:.0%})"
            )
    except Exception as e:
        logger.warning(f"Auto-classification failed for company {company_id}: {e}")

    # Auto-create license for bundle companies with zone (non-blocking)
    if result.get("regimen_fiscal") == "bundle" and result.get("zone_id"):
        try:
            from datetime import datetime, timezone
            from app.modules.fiscal_services.services.license_service import LicenseService
            from app.modules.fiscal_services.repositories.bundle_repository import BundleRepository

            fiscal_year = datetime.now(timezone.utc).year
            # Find the bundle matching this commerce_type
            commerce_type = result.get("commerce_type")
            if commerce_type:
                bundle = await db.fetchrow(
                    "SELECT id FROM service_bundles WHERE commerce_type = $1 AND is_active = true LIMIT 1",
                    commerce_type,
                )
                if bundle:
                    # Check no license exists yet for this year
                    existing = await db.fetchval(
                        "SELECT id FROM commercial_licenses WHERE company_id = $1 AND fiscal_year = $2",
                        company_id, fiscal_year,
                    )
                    if not existing:
                        await LicenseService.open_license(db, {
                            "company_id": company_id,
                            "bundle_id": bundle["id"],
                            "zone_id": result["zone_id"],
                            "city_id": result.get("city_id"),
                            "fiscal_year": fiscal_year,
                        }, user_id)
                        logger.info(
                            f"Auto-created license for company {company_id} "
                            f"(bundle={commerce_type}, FY={fiscal_year})"
                        )
        except Exception as e:
            logger.warning(f"Auto-license creation failed for {company_id}: {e}")

    return CompanyResponse(**result)


@router.get("", response_model=CompanyListResponse)
async def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_archived: bool = Query(
        False,
        description="Include archived (soft-deleted) companies. Reserved for "
                    "admin/audit views — citizen UI defaults to false.",
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """List user's companies (citizen surface — archived hidden by default)."""
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")
    offset = (page - 1) * page_size

    # Only admins are allowed to opt into archived rows. Strip the flag
    # silently for everyone else (no 403 — keeps the route forgiving).
    effective_include_archived = include_archived
    if include_archived:
        perm_service = create_permission_service(db)
        if not await perm_service.has_permission(user_id, "company.view_all"):
            effective_include_archived = False

    companies, total = await company_repository.list_by_user(
        db, user_id, page_size, offset,
        include_archived=effective_include_archived,
    )
    return CompanyListResponse(
        companies=[CompanyResponse(**c) for c in companies],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: UUID,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Get company by ID.

    Citizens can read their own companies as long as ``archived_at IS NULL``.
    Admins with ``company.view_all`` see archived rows too.
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    # Admin with company.view_all can access any company (incl. archived)
    perm_service = create_permission_service(db)
    has_view_all = await perm_service.has_permission(user_id, "company.view_all")

    if not has_view_all:
        # Non-admins must be members
        role = await company_repository.check_membership(db, company_id, user_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")

    company = await company_repository.get_by_id(db, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    # Hide archived rows from citizens — same UX as the listing endpoint.
    if not has_view_all and company.get("archived_at") is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    return CompanyResponse(**company)


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: str,
    update_data: CompanyUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Update company (owner/admin only)"""
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    # Admin with company.update can update any company
    perm_service = create_permission_service(db)
    has_admin_perm = await perm_service.has_permission(user_id, "company.update")

    if not has_admin_perm:
        role = await company_repository.check_membership(db, company_id, user_id)
        if role not in ["company_owner", "company_admin"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires company_owner or company_admin role")

    updated = await company_repository.update(db, company_id, update_data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    logger.info(f"User {user_id} updated company {company_id}")

    # Auto-reclassify if classification-relevant fields changed
    CLASSIFICATION_FIELDS = {
        "forma_juridica", "sector_actividad", "subsector_actividad",
        "capital_social", "employee_count", "commerce_type", "zone_id",
    }
    changed_fields = set(update_data.model_dump(exclude_unset=True).keys())
    if changed_fields & CLASSIFICATION_FIELDS:
        try:
            from app.modules.companies.services.classification_agent import classification_agent
            classification = await classification_agent.classify_company(
                db, updated, updated.get("zone_id")
            )
            old_regimen = updated.get("regimen_fiscal", "pendiente")
            if classification.regimen_fiscal != old_regimen:
                from uuid import UUID as _UUID
                await db.execute(
                    "UPDATE companies SET regimen_fiscal = $2, commerce_type = $3, updated_at = NOW() "
                    "WHERE id = $1",
                    _UUID(company_id), classification.regimen_fiscal,
                    classification.commerce_type,
                )
                updated["regimen_fiscal"] = classification.regimen_fiscal
                updated["commerce_type"] = classification.commerce_type
                logger.info(
                    f"Auto-reclassified company {company_id}: {old_regimen} → "
                    f"{classification.regimen_fiscal} (confidence={classification.confidence:.0%})"
                )
        except Exception as e:
            logger.warning(f"Auto-reclassification failed for company {company_id}: {e}")

    return CompanyResponse(**updated)


@router.post("/{company_id}/archive", status_code=status.HTTP_200_OK)
async def archive_company(
    company_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Soft-delete (archive) a company — citizen-initiated.

    Reserved to ``company_owner`` (the role check is done here, NOT via the
    permission system, because every owner must be able to archive their own
    company without being granted a global permission).

    Returns:
      - 200  ``{"message": "...", "archived_at": "..."}``
      - 403  caller is not the company_owner
      - 404  company not found
      - 409  active dependencies prevent the archive — payload includes a
             ``blockers`` dict with non-zero counts (active_licenses,
             pending_payments, open_requests, active_inspections)

    Idempotent: re-archiving an already-archived company refreshes the
    timestamp without error.

    See migration ``314_companies_soft_delete_archive.sql`` and
    ``.claude/plans/SOFT_DELETE_COMPANIES_PLAN.md``.
    """
    import json

    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    # Existence check (also confirms the UUID is well-formed)
    company = await company_repository.get_by_id(db, company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    # Owner-only — admins use the unarchive/hard-delete admin endpoints
    role = await company_repository.check_membership(db, company_id, user_id)
    if role != "company_owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the company owner can archive this company",
        )

    # 409 guard — refuse archive while business records are alive
    blockers = await company_repository.check_archive_blockers(db, company_id)
    if sum(blockers.values()) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Cannot archive: company has active dependencies",
                "blockers": blockers,
            },
        )

    async with db.transaction():
        ok = await company_repository.archive(
            db, company_id, archived_by_user_id=user_id, reason="archived_by_owner",
        )
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )
        await db.execute(
            """
            INSERT INTO audit_logs (
                user_id, entity_type, entity_id, action, new_values
            ) VALUES ($1, 'company', $2, 'archive', $3::jsonb)
            """,
            UUID(str(user_id)),
            company_id,
            json.dumps({
                "reason": "archived_by_owner",
                "blockers_at_check": blockers,
            }),
        )

    logger.info(f"User {user_id} archived company {company_id}")

    refreshed = await company_repository.get_by_id(db, company_id)
    archived_at = refreshed.get("archived_at") if refreshed else None
    return {
        "message": "Company archived",
        "archived_at": archived_at.isoformat() if archived_at else None,
    }


@router.post("/{company_id}/unarchive", status_code=status.HTTP_200_OK)
async def unarchive_company(
    company_id: str,
    current_user: Dict[str, Any] = Depends(permission_required("company.unarchive")),
    db=Depends(get_database),
):
    """Restore an archived company — admin only.

    Requires the ``company.unarchive`` permission (granted to admins +
    supervisor_onrc per migration 314). Companies that are already active are
    a 400 — no silent no-op.
    """
    import json

    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    company = await company_repository.get_by_id(db, company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
    if company.get("archived_at") is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company is not archived",
        )

    async with db.transaction():
        ok = await company_repository.unarchive(db, company_id)
        if not ok:
            # Race: another admin unarchived between our SELECT and UPDATE.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Company state changed during unarchive — retry",
            )
        await db.execute(
            """
            INSERT INTO audit_logs (
                user_id, entity_type, entity_id, action, new_values
            ) VALUES ($1, 'company', $2, 'unarchive', $3::jsonb)
            """,
            UUID(str(user_id)),
            company_id,
            json.dumps({"restored_by_admin": True}),
        )

    logger.info(f"Admin {user_id} unarchived company {company_id}")
    return {"message": "Company restored"}


@router.delete("/{company_id}", status_code=status.HTTP_200_OK)
async def delete_company(
    company_id: str,
    current_user: Dict[str, Any] = Depends(permission_required("company.hard_delete")),
    db=Depends(get_database),
):
    """Hard-delete a company — admin only, post-archive only.

    Replaces the previous citizen-facing flow. The endpoint now requires:
      1. The ``company.hard_delete`` permission (admin/super_admin per
         migration 314 — citizens never receive it).
      2. The company to have been archived first
         (``archived_at IS NOT NULL``). This protects against accidental
         hard-deletes and ensures every removal goes through the soft-delete
         grace period.
      3. Zero active dependencies — same blocker check as
         ``POST /{id}/archive``. An archived company can grow new
         dependencies (e.g. retroactive license adjustments) and we do not
         want to lose them.
    """
    import json

    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    company = await company_repository.get_by_id(db, company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    if company.get("archived_at") is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company must be archived before hard-delete",
        )

    blockers = await company_repository.check_archive_blockers(db, company_id)
    if sum(blockers.values()) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Cannot hard-delete: company has active dependencies",
                "blockers": blockers,
            },
        )

    async with db.transaction():
        deleted = await company_repository.delete(db, company_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )
        await db.execute(
            """
            INSERT INTO audit_logs (
                user_id, entity_type, entity_id, action, new_values
            ) VALUES ($1, 'company', $2, 'hard_delete', $3::jsonb)
            """,
            UUID(str(user_id)),
            company_id,
            json.dumps({
                "previous_archived_at": company.get("archived_at").isoformat()
                    if company.get("archived_at") else None,
                "blockers_at_check": blockers,
            }),
        )

    logger.info(f"Admin {user_id} hard-deleted company {company_id}")
    return {"message": "Company deleted"}


# =============================================================================
# MEMBER ENDPOINTS
# =============================================================================

@router.get("/{company_id}/members", response_model=List[CompanyMember])
async def get_company_members(
    company_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Get company members"""
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    # Admin with company.manage_members can view any company's members
    perm_service = create_permission_service(db)
    has_admin_perm = await perm_service.has_permission(user_id, "company.manage_members")

    if not has_admin_perm:
        role = await company_repository.check_membership(db, company_id, user_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")

    members = await company_repository.get_members(db, company_id)
    return [CompanyMember(**m) for m in members]


@router.post("/{company_id}/members", response_model=CompanyMember)
async def add_company_member(
    company_id: str,
    body: AddMemberRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """
    Add member to company

    Requires either:
    - company_owner or company_admin role in the company, OR
    - company.manage_members permission (admin override)
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    perm_service = create_permission_service(db)
    has_admin_perm = await perm_service.has_permission(user_id, "company.manage_members")

    if not has_admin_perm:
        user_role = await company_repository.check_membership(db, company_id, user_id)
        if user_role not in ["company_owner", "company_admin"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires company_owner/company_admin role or company.manage_members permission")

    result = await company_repository.add_member(db, company_id, body.member_user_id, body.role)
    logger.info(f"User {user_id} added member {body.member_user_id} to company {company_id}")
    return CompanyMember(**result)


@router.put("/{company_id}/members/{member_user_id}/role", response_model=CompanyMember)
async def update_member_role(
    company_id: str,
    member_user_id: str,
    body: UpdateMemberRoleRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Update member role within a company."""
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    perm_service = create_permission_service(db)
    has_admin_perm = await perm_service.has_permission(user_id, "company.manage_members")

    if not has_admin_perm:
        user_role = await company_repository.check_membership(db, company_id, user_id)
        if user_role not in ["company_owner", "company_admin"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires company_owner/company_admin role or company.manage_members permission")

    result = await company_repository.update_member_role(db, company_id, member_user_id, body.role.value)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    logger.info(f"User {user_id} updated role of {member_user_id} in company {company_id} to {body.role.value}")
    return CompanyMember(**result)


@router.delete("/{company_id}/members/{member_user_id}", status_code=status.HTTP_200_OK)
async def remove_company_member(
    company_id: str,
    member_user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Remove member from company (owner/admin only)"""
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    perm_service = create_permission_service(db)
    has_admin_perm = await perm_service.has_permission(user_id, "company.manage_members")

    if not has_admin_perm:
        user_role = await company_repository.check_membership(db, company_id, user_id)
        if user_role not in ["company_owner", "company_admin"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires company_owner or company_admin role")

    if member_user_id == user_id:
        user_role = await company_repository.check_membership(db, company_id, user_id)
        if user_role == "company_owner":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owner cannot remove self")

    removed = await company_repository.remove_member(db, company_id, member_user_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    logger.info(f"User {user_id} removed member {member_user_id} from company {company_id}")
    return {"message": "Member removed successfully"}
