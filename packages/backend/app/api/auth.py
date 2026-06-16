"""Auth API — register / login / refresh / logout / 2FA (D4.2)."""

from __future__ import annotations

import contextlib

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.auth import audit
from app.auth import service
from app.identity import service as identity_service
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


@router.post("/refresh")
async def refresh(body: RefreshIn, request: Request,
                  session: AsyncSession = Depends(get_session)) -> dict:
    # Rotation with reuse detection (revokes the old session, mints a new one).
    tokens = await service.refresh(session, body.refresh_token,
                                   auth_provider=request.app.state.auth)
    if tokens is None:
        await session.commit()  # persist any reuse-triggered mass revocation
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh token")
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
