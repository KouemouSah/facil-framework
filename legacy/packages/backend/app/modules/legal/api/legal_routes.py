"""Legal routes — versions endpoint (public) + accept endpoint (auth, role-gated).

Created: Phase 10/B (2026-05-02)
Plan: .claude/plans/MOBILE_PHASE_10_B_LEGAL_DETAILED.md

Public endpoints
- GET /api/v1/legal/versions
    Returns current Privacy + Terms + Cookies versions and last-updated dates.
    Mobile reads this on sign-up to populate POST /auth/register.terms_version_accepted.
    Web reads it post-login to decide whether to nag for re-acceptance after a bump.

Authenticated endpoints
- POST /api/v1/legal/accept
    Records explicit acceptance of current Privacy + Terms versions for the
    authenticated user. Used by the mobile post-login modal when an existing
    user (backfilled "1.0.0-legacy" or never accepted) needs to ratify.

    Role gate : only citizen/business/accountant. admin/agent/funcionario
    return 403 — they have no in-app CGU obligation (separate contractual
    agreement). See migration 331 + plan §3.0.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.config import settings
from app.database.connection import get_db_pool
from app.modules.auth.dependencies import get_current_user

router = APIRouter(prefix="/legal", tags=["legal"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LegalVersionsResponse(BaseModel):
    """Current legal-doc versions (public). All ISO date strings (YYYY-MM-DD)."""

    privacy_version: str = Field(..., examples=["1.0.0"])
    privacy_last_updated: str = Field(..., examples=["2026-05-02"])
    terms_version: str = Field(..., examples=["1.0.0"])
    terms_last_updated: str = Field(..., examples=["2026-05-02"])
    cookies_version: str = Field(..., examples=["1.0.0"])
    cookies_last_updated: str = Field(..., examples=["2026-05-02"])


class LegalAcceptPayload(BaseModel):
    """Body for POST /legal/accept — explicit acceptance with strict version match."""

    terms_version: str = Field(..., min_length=1, max_length=16)
    privacy_version: str = Field(..., min_length=1, max_length=16)


class LegalAcceptResponse(BaseModel):
    status: str = Field(..., examples=["accepted"])
    terms_accepted_at: datetime
    privacy_accepted_at: datetime


# Roles that self-onboard via public sign-up and therefore require explicit
# in-app legal acceptance. admin/agent/funcionario are created internally
# and are exempt (separate employment/mandate contract).
_PUBLIC_ROLES = ("citizen", "business", "accountant")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/versions",
    response_model=LegalVersionsResponse,
    summary="Current legal document versions",
    description=(
        "Public endpoint (no auth). Mobile and web read this to know which "
        "versions to ask the user to accept. Bumping any version triggers "
        "a re-acceptance prompt for users whose persisted version is "
        "older."
    ),
)
async def get_legal_versions() -> LegalVersionsResponse:
    return LegalVersionsResponse(
        privacy_version=settings.LEGAL_PRIVACY_VERSION,
        privacy_last_updated=settings.LEGAL_PRIVACY_LAST_UPDATED,
        terms_version=settings.LEGAL_TERMS_VERSION,
        terms_last_updated=settings.LEGAL_TERMS_LAST_UPDATED,
        cookies_version=settings.LEGAL_COOKIES_VERSION,
        cookies_last_updated=settings.LEGAL_COOKIES_LAST_UPDATED,
    )


@router.post(
    "/accept",
    response_model=LegalAcceptResponse,
    summary="Record legal acceptance for current user",
    description=(
        "Authenticated. Persists `terms_accepted_at`, `terms_version`, "
        "`privacy_accepted_at`, `privacy_version` on `users` row for the "
        "current user. Strict version match — if the client posts a stale "
        "version, returns 400 with `expected` to force a refresh. "
        "Role-gated : only citizen/business/accountant. Other roles "
        "receive 403."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Stale version submitted (mobile must refresh)"
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Role exempt from in-app CGU (admin/agent/funcionario)"
        },
    },
)
async def accept_legal_versions(
    payload: LegalAcceptPayload,
    current_user=Depends(get_current_user),
) -> LegalAcceptResponse:
    # 1. Role gate — internal employees are exempt
    user_role = getattr(current_user, "role", None) or current_user.get("role")
    if user_role not in _PUBLIC_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "legal_acceptance_not_required_for_role",
                "role": user_role,
                "message": (
                    "Internal roles (admin/agent/funcionario) are bound by a "
                    "separate contractual agreement and do not need in-app "
                    "CGU acceptance."
                ),
            },
        )

    # 2. Strict version match — protect against stale clients
    if payload.terms_version != settings.LEGAL_TERMS_VERSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "outdated_terms_version",
                "expected": settings.LEGAL_TERMS_VERSION,
                "received": payload.terms_version,
            },
        )
    if payload.privacy_version != settings.LEGAL_PRIVACY_VERSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "outdated_privacy_version",
                "expected": settings.LEGAL_PRIVACY_VERSION,
                "received": payload.privacy_version,
            },
        )

    # 3. Persist
    now = datetime.now(timezone.utc)
    user_id = getattr(current_user, "id", None) or current_user.get("id")

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET terms_accepted_at   = $1,
                terms_version       = $2,
                privacy_accepted_at = $3,
                privacy_version     = $4,
                updated_at          = $5
            WHERE id = $6
            """,
            now,
            payload.terms_version,
            now,
            payload.privacy_version,
            now,
            user_id,
        )

    return LegalAcceptResponse(
        status="accepted",
        terms_accepted_at=now,
        privacy_accepted_at=now,
    )
