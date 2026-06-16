"""Auth API — register / login / refresh / logout / 2FA (D4.2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.auth import service
from app.identity import service as identity_service
from app.security.auth_dep import require_auth

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


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


class CodeIn(BaseModel):
    code: str


@router.post("/register", status_code=201)
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


@router.post("/login")
async def login(body: LoginIn, request: Request,
                session: AsyncSession = Depends(get_session)) -> dict:
    try:
        account, tokens = await service.login(
            session, body.identifier, body.password,
            auth_provider=request.app.state.auth, totp_code=body.totp_code)
    except service.TotpRequired:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "totp_required")
    except service.AccountLocked:
        raise HTTPException(status.HTTP_423_LOCKED, "account locked")
    except service.InvalidCredentials:
        await session.commit()  # persist the failed-attempt increment (lockout)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    await session.commit()
    return {**tokens, "account": account.as_dict()}


@router.post("/refresh")
async def refresh(body: RefreshIn, request: Request) -> dict:
    tokens = await request.app.state.auth.refresh(body.refresh_token)
    if tokens is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh token")
    return tokens


@router.post("/logout")
async def logout() -> dict:
    # Stateless JWT: the client discards its tokens. Server-side refresh
    # revocation (a session/blocklist table) lands later.
    return {"status": "ok"}


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
        await service.enable_totp(session, principal["sub"], body.code)
    except service.InvalidCredentials as e:
        raise HTTPException(400, str(e)) from e
    await session.commit()
    return {"totp_enabled": True}
