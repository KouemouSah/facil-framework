"""
Company Classification Routes — Draft workflow + classification + import.

Endpoints:
  POST /classification/classify          — Classify single company data
  POST /classification/classify-batch    — Classify batch (JSON array)
  POST /classification/import-csv        — Upload CSV → classify → drafts
  POST /classification/reclassify/{id}   — Reclassify existing company

  GET  /classification/drafts            — List drafts (paginated)
  GET  /classification/drafts/{id}       — Get draft detail
  POST /classification/drafts/{id}/approve    — Approve → create company
  POST /classification/drafts/{id}/reject     — Reject
  POST /classification/drafts/{id}/request-info — Request more info
  POST /classification/drafts/{id}/reclassify   — Re-run classification

  GET  /classification/history/{id}      — Classification history for company
  GET  /classification/stats             — Dashboard stats
"""

from typing import Any, Dict, Optional

import asyncpg
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from loguru import logger

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.companies.models.classification import (
    BatchClassificationResult,
    ClassificationHistoryEntry,
    ClassificationResult,
    ClassificationStatsResponse,
    ClassifySingleRequest,
    ClassifyBatchRequest,
    DraftActionRequest,
    DraftListResponse,
    DraftResponse,
    ReclassifyRequest,
)
from app.modules.permissions.middleware.permission_middleware import permission_required

router = APIRouter(prefix="/classification", tags=["Company Classification"])


# ── Classification ───────────────────────────────────────────────────────────

@router.post(
    "/classify",
    response_model=ClassificationResult,
    summary="Classify single company data",
)
async def classify_single(
    request: ClassifySingleRequest,
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.classify")),
):
    """Classify a company's fiscal regime from provided data."""
    from app.modules.companies.services.classification_agent import classification_agent

    data = request.model_dump(exclude_none=True)
    result = await classification_agent.classify_company(
        db, data, zone_id=data.pop("zone_id", None)
    )
    return result


@router.post(
    "/classify-batch",
    response_model=BatchClassificationResult,
    summary="Classify batch of companies",
)
async def classify_batch(
    request: ClassifyBatchRequest,
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.classify")),
):
    """Classify a batch of companies (max 1000)."""
    from app.modules.companies.services.classification_agent import classification_agent

    items = [item.model_dump(exclude_none=True) for item in request.items]
    result = await classification_agent.classify_batch(db, items, request.zone_id)
    return result


@router.post(
    "/import-csv",
    summary="Import companies from CSV",
)
async def import_csv(
    file: UploadFile = File(...),
    zone_id: Optional[str] = Query(None, description="Default zone for all companies"),
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.import_csv")),
):
    """Upload CSV → parse → validate → classify → create drafts."""
    from app.modules.companies.services.csv_import_service import csv_import_service

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    user_id = str(current_user.get("sub", ""))
    result = await csv_import_service.import_csv(db, content, user_id, zone_id)
    return result


@router.post(
    "/reclassify/{company_id}",
    response_model=ClassificationResult,
    summary="Reclassify existing company",
)
async def reclassify_company(
    company_id: str,
    request: ReclassifyRequest,
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.classify")),
):
    """Re-run classification on an existing company and update DB."""
    from app.modules.companies.services.classification_agent import classification_agent

    user_id = str(current_user.get("sub", ""))
    result = await classification_agent.classify_and_update(
        db, company_id, triggered_by=request.reason, user_id=user_id
    )

    if result is None:
        raise HTTPException(status_code=404, detail="Company not found")

    return result


# ── Drafts ───────────────────────────────────────────────────────────────────

@router.get(
    "/drafts",
    response_model=DraftListResponse,
    summary="List company creation drafts",
)
async def list_drafts(
    status: Optional[str] = Query(None, description="Filter by draft status"),
    batch_id: Optional[str] = Query(None, description="Filter by batch ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.validate_draft")),
):
    """List drafts for admin review (ordered by confidence ASC)."""
    from app.modules.companies.services.company_onboarding_service import (
        company_onboarding_service,
    )

    result = await company_onboarding_service.get_drafts(
        db, status=status, page=page, page_size=page_size, batch_id=batch_id
    )
    return result


@router.get(
    "/drafts/{draft_id}",
    response_model=DraftResponse,
    summary="Get draft detail",
)
async def get_draft(
    draft_id: str,
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.validate_draft")),
):
    """Get a single draft by ID."""
    from app.modules.companies.services.company_onboarding_service import (
        company_onboarding_service,
    )

    draft = await company_onboarding_service.get_draft(db, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.post(
    "/drafts/{draft_id}/approve",
    summary="Approve draft → create company",
)
async def approve_draft(
    draft_id: str,
    request: DraftActionRequest,
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.validate_draft")),
):
    """Admin approves draft → creates company + commercial license."""
    from app.modules.companies.services.company_onboarding_service import (
        company_onboarding_service,
    )

    reviewer_id = str(current_user.get("sub", ""))
    result = await company_onboarding_service.approve_draft(
        db, draft_id, reviewer_id, notes=request.notes or ""
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post(
    "/drafts/{draft_id}/reject",
    summary="Reject draft",
)
async def reject_draft(
    draft_id: str,
    request: DraftActionRequest,
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.validate_draft")),
):
    """Admin rejects a draft."""
    from app.modules.companies.services.company_onboarding_service import (
        company_onboarding_service,
    )

    reviewer_id = str(current_user.get("sub", ""))
    result = await company_onboarding_service.reject_draft(
        db, draft_id, reviewer_id, notes=request.notes or ""
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post(
    "/drafts/{draft_id}/request-info",
    summary="Request more info on draft",
)
async def request_draft_info(
    draft_id: str,
    request: DraftActionRequest,
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.validate_draft")),
):
    """Admin requests more information on a draft."""
    from app.modules.companies.services.company_onboarding_service import (
        company_onboarding_service,
    )

    reviewer_id = str(current_user.get("sub", ""))
    result = await company_onboarding_service.request_info(
        db, draft_id, reviewer_id, notes=request.notes or ""
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post(
    "/drafts/{draft_id}/reclassify",
    summary="Re-run classification on a draft",
)
async def reclassify_draft(
    draft_id: str,
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.classify")),
):
    """Re-run classification on a draft's company_data."""
    from app.modules.companies.services.classification_agent import classification_agent
    from app.modules.companies.services.company_onboarding_service import (
        company_onboarding_service,
    )
    import json

    draft = await company_onboarding_service.get_draft(db, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    if draft["status"] not in ("pending_review", "needs_info", "auto_approved"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reclassify draft with status '{draft['status']}'"
        )

    company_data = draft.get("company_data", {})
    result = await classification_agent.classify_company(db, company_data)

    # Determine new status
    new_status = "pending_review"
    if result.confidence >= 0.90 and not result.flags:
        new_status = "auto_approved"

    # Update draft
    from uuid import UUID as _UUID
    await db.execute(
        """UPDATE company_creation_drafts
           SET regimen_fiscal = $2, classification_confidence = $3,
               classification_reason = $4, classification_details = $5,
               status = $6
           WHERE id = $1""",
        _UUID(draft_id),
        result.regimen_fiscal,
        result.confidence,
        result.reason,
        json.dumps({
            "rules_applied": result.rules_applied,
            "flags": result.flags,
            "commerce_type": result.commerce_type,
            "llm_validated": result.llm_validated,
            "llm_issues": result.llm_issues,
            "suggested_actions": result.suggested_actions,
        }),
        new_status,
    )

    return {
        "classification": result.model_dump(),
        "new_status": new_status,
    }


# ── History ──────────────────────────────────────────────────────────────────

@router.get(
    "/history/{company_id}",
    summary="Get classification history for a company",
)
async def get_classification_history(
    company_id: str,
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.view_classification")),
):
    """Get classification history for a company (audit trail)."""
    from uuid import UUID as _UUID
    try:
        company_uuid = _UUID(company_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid company_id format")

    rows = await db.fetch(
        """SELECT id, company_id, old_regimen, new_regimen,
                  old_commerce_type, new_commerce_type,
                  reason, confidence, triggered_by, created_at
           FROM company_classification_history
           WHERE company_id = $1
           ORDER BY created_at DESC
           LIMIT 50""",
        company_uuid,
    )

    return {
        "company_id": company_id,
        "entries": [
            {
                "id": str(r["id"]),
                "company_id": str(r["company_id"]),
                "old_regimen": r["old_regimen"],
                "new_regimen": r["new_regimen"],
                "old_commerce_type": r["old_commerce_type"],
                "new_commerce_type": r["new_commerce_type"],
                "reason": r["reason"],
                "confidence": r["confidence"] or 0.0,
                "triggered_by": r["triggered_by"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
    }


# ── Stats ────────────────────────────────────────────────────────────────────

@router.get(
    "/stats",
    response_model=ClassificationStatsResponse,
    summary="Classification dashboard stats",
)
async def get_classification_stats(
    db: asyncpg.Connection = Depends(get_database),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _=Depends(permission_required("company.view_classification")),
):
    """Get classification statistics for the admin dashboard."""
    from app.modules.companies.services.company_onboarding_service import (
        company_onboarding_service,
    )

    return await company_onboarding_service.get_stats(db)
