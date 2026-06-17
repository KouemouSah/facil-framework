"""Auth API — register / login / refresh / logout / 2FA (D4.2)."""

from __future__ import annotations

import contextlib
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.auth import audit
from app.auth import service
from app.identity import repository as identity_repo
from app.identity import service as identity_service
from app.rbac import repository as rbac_repo
from app.rbac import service as rbac_service
from app.security.auth_dep import require_auth
from app.security.rate_limit import rate_limited

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Ingress limits on abuse-prone public endpoints (per client IP).
_RL_LOGIN = Depends(rate_limited("login", 30, 60))
_RL_REGISTER = Depends(rate_limited("register", 10, 60))
_RL_RESET = Depends(rate_limited("pwreset", 10, 60))


async def _send_email(request: Request, to: str, subject: str, body: str) -> None:
    """Best-effort send via the configured email provider. Never blocks the flow
    (no provider configured in dev/test -> silently skipped; token still issued)."""
    with contextlib.suppress(Exception):
        async with request.app.state.db.session_factory() as s:
            provider = await request.app.state.registry.get_default("email", s)
        await provider.send(to, subject, body)


class RegisterIn(BaseModel):
    password: str
    email: str | None = None
    display_name: str | None = None
    organization_id: str | None = None


class LoginIn(BaseModel):
    identifier: str          # email OR account_number (NIU)
    password: str
    totp_code: str | None = None


class RefreshIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    refresh_token: str | None = None
    all_devices: bool = False


class CodeIn(BaseModel):
    code: str


class EmailIn(BaseModel):
    email: str


class ResetConfirmIn(BaseModel):
    token: str
    new_password: str


class TokenIn(BaseModel):
    token: str


@router.post("/register", status_code=201, dependencies=[_RL_REGISTER])
async def register(body: RegisterIn,
                   session: AsyncSession = Depends(get_session)) -> dict:
    try:
        account = await service.register(
            session, password=body.password, email=body.email,
            display_name=body.display_name, organization_id=body.organization_id)
    except service.WeakPassword as e:
        raise HTTPException(422, str(e)) from e
    except identity_service.EmailTaken as e:
        raise HTTPException(409, str(e)) from e
    await session.commit()
    return account.as_dict()


@router.post("/login", dependencies=[_RL_LOGIN])
async def login(body: LoginIn, request: Request,
                session: AsyncSession = Depends(get_session)) -> dict:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    try:
        account, tokens = await service.login(
            session, body.identifier, body.password,
            auth_provider=request.app.state.auth, totp_code=body.totp_code,
            ip=ip, ua=ua)
    except service.TotpRequired:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "totp_required")
    except service.AccountLocked:
        await audit.record(session, audit.LOGIN_FAILED, ip=ip, ua=ua,
                           detail={"reason": "locked"})
        await session.commit()
        raise HTTPException(status.HTTP_423_LOCKED, "account locked")
    except service.InvalidCredentials:
        await audit.record(session, audit.LOGIN_FAILED, ip=ip, ua=ua,
                           detail={"reason": "invalid"})
        await session.commit()  # persist the failed-attempt increment (lockout)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    await audit.record(session, audit.LOGIN, account_id=account.id, ip=ip, ua=ua)
    await session.commit()
    return {**tokens, "account": account.as_dict()}


@router.get("/me")
async def me(principal: dict = Depends(require_auth),
             session: AsyncSession = Depends(get_session)) -> dict:
    """Whoami — the current principal + account + scoped role assignments, so the
    UI can REFLECT permissions (show/hide). The backend stays the authority."""
    if principal.get("break_glass"):
        return {"break_glass": True,
                "account": {"id": "bootstrap-admin", "display_name": "Bootstrap Admin"},
                "roles": []}
    account = await identity_repo.get_account(session, principal["sub"])
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "account not found")
    assignments = await rbac_repo.list_account_roles(session, account.id)
    return {"break_glass": False, "account": account.as_dict(),
            "idp": principal.get("idp"),
            "roles": [a.as_dict() for a in assignments]}


@router.get("/me/permissions")
async def my_permissions(principal: dict = Depends(require_auth),
                         session: AsyncSession = Depends(get_session)) -> dict:
    """Effective permission codes for the current principal — the UI uses these
    to hide nav/actions the user can't use (the backend still enforces scope).
    Break-glass holds everything (`*`)."""
    if principal.get("break_glass"):
        return {"break_glass": True, "permissions": ["*"]}
    codes = await rbac_service.effective_permissions(session, principal["sub"])
    return {"break_glass": False, "permissions": sorted(codes)}


@router.post("/refresh")
async def refresh(body: RefreshIn, request: Request,
                  session: AsyncSession = Depends(get_session)) -> dict:
    # Rotation with reuse detection + idle/single-session policy (per account type).
    tokens = await service.refresh(session, body.refresh_token,
                                   auth_provider=request.app.state.auth)
    if tokens is None:
        await session.commit()  # persist any reuse/idle-triggered revocation
        # Uniform 401 — the client (D5 frontend) redirects to the login page on
        # this; session expired (idle/absolute), revoked, reused or invalid.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "session expired or invalid — re-authenticate")
    await session.commit()
    return tokens


@router.post("/logout")
async def logout(body: LogoutIn, request: Request,
                 principal: dict = Depends(require_auth),
                 session: AsyncSession = Depends(get_session)) -> dict:
    # Revoke the presented session, or every session for the account.
    await service.logout(session, body.refresh_token,
                         auth_provider=request.app.state.auth,
                         all_devices=body.all_devices, account_id=principal.get("sub"))
    await audit.record(session, audit.LOGOUT, account_id=principal.get("sub"),
                       detail={"all_devices": body.all_devices})
    await session.commit()
    return {"status": "ok"}


@router.post("/password-reset/request", dependencies=[_RL_RESET])
async def password_reset_request(body: EmailIn, request: Request,
                                 session: AsyncSession = Depends(get_session)) -> dict:
    raw = await service.request_password_reset(session, body.email)
    await session.commit()
    if raw:
        app_name = request.app.state.resolver.resolve("branding.app_name", "Facil")
        await _send_email(request, body.email, f"{app_name} — password reset",
                          f"Use this token to reset your password: {raw}")
    # Uniform response whether or not the email exists (anti-enumeration).
    return {"status": "ok"}


@router.post("/password-reset/confirm")
async def password_reset_confirm(body: ResetConfirmIn,
                                 session: AsyncSession = Depends(get_session)) -> dict:
    try:
        done = await service.confirm_password_reset(session, body.token, body.new_password)
    except service.WeakPassword as e:
        raise HTTPException(422, str(e)) from e
    if done:
        await audit.record(session, audit.PASSWORD_RESET)
    await session.commit()
    if not done:
        raise HTTPException(400, "invalid or expired token")
    return {"status": "ok"}


@router.post("/email-verification/request")
async def email_verification_request(request: Request,
                                     principal: dict = Depends(require_auth),
                                     session: AsyncSession = Depends(get_session)) -> dict:
    raw = await service.request_email_verification(session, principal["sub"])
    await session.commit()
    if raw:
        from app.identity import repository as identity_repo
        async with request.app.state.db.session_factory() as s:
            acc = await identity_repo.get_account(s, principal["sub"])
        app_name = request.app.state.resolver.resolve("branding.app_name", "Facil")
        if acc and acc.email:
            await _send_email(request, acc.email, f"{app_name} — verify your email",
                              f"Use this token to verify your email: {raw}")
    return {"status": "ok"}


@router.post("/email-verification/confirm")
async def email_verification_confirm(body: TokenIn,
                                     session: AsyncSession = Depends(get_session)) -> dict:
    done = await service.confirm_email_verification(session, body.token)
    if done:
        await audit.record(session, audit.EMAIL_VERIFIED)
    await session.commit()
    if not done:
        raise HTTPException(400, "invalid or expired token")
    return {"email_verified": True}


@router.post("/oidc/backchannel-logout")
async def oidc_backchannel_logout(request: Request) -> dict:
    """OIDC back-channel logout (D4.9 #5): the IdP posts a signed logout_token
    (application/x-www-form-urlencoded per spec; JSON also accepted). We verify it
    and revoke the session id so matching access tokens are rejected by
    require_auth until they expire. Form parsed manually (no python-multipart dep)."""
    raw = (await request.body()).decode("utf-8", "ignore")
    logout_token = (parse_qs(raw).get("logout_token") or [None])[0]
    if not logout_token:
        with contextlib.suppress(Exception):
            import json as _json
            logout_token = _json.loads(raw).get("logout_token")
    if not logout_token:
        raise HTTPException(400, "missing logout_token")
    cache = getattr(request.app.state, "cache", None)
    if cache is None:
        raise HTTPException(503, "oidc revocation not enabled")
    for verifier in getattr(request.app.state, "auth_verifiers", []):
        if getattr(verifier, "code", "native") == "native":
            continue
        claims = await verifier.verify(logout_token)
        if claims is None:
            continue
        sid = claims.get("sid") or claims.get("jti")
        if not sid:
            continue
        ttl = int(request.app.state.resolver.resolve("auth.oidc.revocation_ttl", 3600))
        await cache.set(f"oidc_revoked:{sid}", "1", ttl)
        return {"revoked": True, "sid": sid}
    raise HTTPException(400, "invalid logout_token")


@router.post("/2fa/setup")
async def twofa_setup(request: Request, principal: dict = Depends(require_auth),
                      session: AsyncSession = Depends(get_session)) -> dict:
    issuer = request.app.state.resolver.resolve("branding.app_name", "Facil")
    try:
        secret, uri = await service.setup_totp(session, principal["sub"], issuer=issuer)
    except service.InvalidCredentials as e:
        raise HTTPException(400, str(e)) from e
    await session.commit()
    return {"secret": secret, "otpauth_uri": uri}


@router.post("/2fa/enable")
async def twofa_enable(body: CodeIn, principal: dict = Depends(require_auth),
                       session: AsyncSession = Depends(get_session)) -> dict:
    try:
        backup = await service.enable_totp(session, principal["sub"], body.code)
    except service.InvalidCredentials as e:
        raise HTTPException(400, str(e)) from e
    await audit.record(session, audit.TWO_FACTOR_ENABLED, account_id=principal["sub"])
    await session.commit()
    # Backup codes are shown ONCE here; only their hashes are stored.
    return {"totp_enabled": True, "backup_codes": backup}
