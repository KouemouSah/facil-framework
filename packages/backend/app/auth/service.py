"""Auth service — register, authenticate (lockout + TOTP), login, 2FA setup.

Branches identity (Account/NIU, D4.1) and credentials (Credential). Login by
email OR NIU. Anti-enumeration: a wrong identifier or password yields the SAME
InvalidCredentials (no oracle). Lockout after repeated failures (legacy-parity).
Token issuance is delegated to the AuthProvider (auth/native by default).
"""

from __future__ import annotations

import datetime as _dt
import inspect

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import backup_codes as backup_mod
from app.auth import password as password_mod
from app.auth import repository as repo
from app.auth import sessions as sessions_mod
from app.auth import tokens as tokens_mod
from app.auth import totp as totp_mod
from app.auth.models import Credential
from app.config import get_settings
from app.security import crypto
from app.identity import repository as identity_repo
from app.identity import service as identity_service
from app.identity.number import NumberStrategy

LOCKOUT_THRESHOLD = 5
LOCKOUT_MINUTES = 15


class AuthError(Exception):
    pass


class WeakPassword(AuthError):
    pass


class InvalidCredentials(AuthError):
    pass


class AccountLocked(AuthError):
    pass


class TotpRequired(AuthError):
    pass


def _now() -> _dt.datetime:
    return _dt.datetime.now(tz=_dt.timezone.utc)


def _aware(dt: _dt.datetime | None) -> _dt.datetime | None:
    # SQLite returns naive datetimes; treat stored times as UTC for comparison.
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=_dt.timezone.utc)
    return dt


def _verify_second_factor(cred: Credential, code: str) -> bool:
    """TOTP code (decrypting the stored secret) OR a one-time backup code.
    A consumed backup code is removed from the credential in place."""
    try:
        secret = crypto.decrypt(cred.totp_secret) if cred.totp_secret else ""
    except crypto.DecryptionError:
        secret = ""
    if secret and totp_mod.verify_code(secret, code):
        return True
    ok, remaining = backup_mod.verify_and_consume(cred.totp_backup_codes or [], code)
    if ok:
        cred.totp_backup_codes = remaining
    return ok


def _register_failure(cred: Credential) -> None:
    cred.failed_attempts += 1
    if cred.failed_attempts >= LOCKOUT_THRESHOLD:
        cred.locked_until = _now() + _dt.timedelta(minutes=LOCKOUT_MINUTES)


async def register(session: AsyncSession, *, password: str, email: str | None = None,
                   organization_id: str | None = None, display_name: str | None = None,
                   policy: str = "immediate", category: str | None = None,
                   strategy: NumberStrategy | None = None):
    ok, reason = password_mod.check_strength(password)
    if not ok:
        raise WeakPassword(reason)
    account = await identity_service.register(
        session, email=email, organization_id=organization_id,
        display_name=display_name, policy=policy, category=category, strategy=strategy)
    session.add(Credential(account_id=account.id,
                           password_hash=password_mod.hash_password(password)))
    await session.flush()
    return account


async def authenticate(session: AsyncSession, identifier: str, password: str, *,
                      totp_code: str | None = None,
                      strategy: NumberStrategy | None = None):
    account = await identity_service.resolve_identifier(session, identifier, strategy)
    # Suspended/deactivated/inactive accounts must not authenticate — return a
    # uniform None (same as a bad identifier; no status oracle to an attacker).
    if not identity_service.is_usable(account):
        return None
    cred = await repo.get_credential(session, account.id)
    if cred is None:
        return None
    locked = _aware(cred.locked_until)
    if locked and locked > _now():
        raise AccountLocked("account temporarily locked")
    if not password_mod.verify_password(password, cred.password_hash):
        _register_failure(cred)
        await session.flush()
        return None
    if cred.totp_enabled:
        if not totp_code:
            raise TotpRequired("2fa code required")
        if not _verify_second_factor(cred, totp_code):
            _register_failure(cred)
            await session.flush()
            return None
    cred.failed_attempts = 0
    cred.locked_until = None
    await session.flush()
    return account


def _claims(account) -> dict:
    return {"act": account.account_number, "org": account.organization_id}


async def login(session: AsyncSession, identifier: str, password: str, *,
               auth_provider, totp_code: str | None = None,
               strategy: NumberStrategy | None = None,
               ip: str | None = None, ua: str | None = None):
    account = await authenticate(session, identifier, password,
                                 totp_code=totp_code, strategy=strategy)
    if account is None:
        raise InvalidCredentials("invalid credentials")
    settings = get_settings()
    tokens = await sessions_mod.open_session(
        session, account.id, auth_provider=auth_provider, claims=_claims(account),
        ip=ip, ua=ua,
        single_session=settings.single_session_for(account.subject_type))
    return account, tokens


async def refresh(session: AsyncSession, refresh_token: str, *, auth_provider):
    """Rotate a refresh token (revoke old, mint new). None if invalid/reused, or
    if the sliding idle timeout elapsed (agent 30 min / user 1 h). Policy is per
    account type (subject_type)."""
    settings = get_settings()
    # Peek the subject (no DB) to pick the per-type idle / single-session policy.
    peek = await auth_provider.verify(refresh_token, expect="refresh")
    idle = single = None
    if peek and peek.get("sub"):
        acc = await identity_repo.get_account(session, peek["sub"])
        st = acc.subject_type if acc else None
        idle = settings.idle_seconds_for(st) or None
        single = settings.single_session_for(st)

    async def claims_for(account_id: str) -> dict | None:
        acc = await identity_repo.get_account(session, account_id)
        return _claims(acc) if acc else None
    return await sessions_mod.rotate(session, refresh_token,
                                     auth_provider=auth_provider,
                                     claims_for=claims_for, idle_seconds=idle,
                                     single_session=bool(single))


async def logout(session: AsyncSession, refresh_token: str | None, *, auth_provider,
                 all_devices: bool = False, account_id: str | None = None) -> bool:
    if all_devices and account_id:
        await sessions_mod.revoke_all(session, account_id)
        return True
    if refresh_token:
        return await sessions_mod.revoke(session, refresh_token,
                                         auth_provider=auth_provider)
    return False


async def request_password_reset(session: AsyncSession, email: str) -> str | None:
    """Mint a reset token if the email maps to an account. Returns the RAW token
    (the API mails it). None if no such account — the API answers uniformly anyway."""
    account = await identity_repo.get_by_email(session, email.strip().lower())
    if account is None:
        return None
    return await tokens_mod.issue(session, account.id, tokens_mod.PASSWORD_RESET)


async def confirm_password_reset(session: AsyncSession, raw_token: str,
                                 new_password: str) -> bool:
    ok, reason = password_mod.check_strength(new_password)
    if not ok:
        raise WeakPassword(reason)
    account_id = await tokens_mod.consume(session, tokens_mod.PASSWORD_RESET, raw_token)
    if account_id is None:
        return False
    cred = await repo.get_credential(session, account_id)
    if cred is None:
        return False
    cred.password_hash = password_mod.hash_password(new_password)
    cred.failed_attempts = 0
    cred.locked_until = None
    await sessions_mod.revoke_all(session, account_id)  # log out everywhere on reset
    await session.flush()
    return True


async def request_email_verification(session: AsyncSession,
                                     account_id: str) -> str | None:
    account = await identity_repo.get_account(session, account_id)
    if account is None or not account.email:
        return None
    return await tokens_mod.issue(session, account_id, tokens_mod.EMAIL_VERIFICATION)


async def confirm_email_verification(session: AsyncSession, raw_token: str) -> bool:
    account_id = await tokens_mod.consume(
        session, tokens_mod.EMAIL_VERIFICATION, raw_token)
    if account_id is None:
        return False
    account = await identity_repo.get_account(session, account_id)
    if account is None:
        return False
    account.email_verified = True
    await session.flush()
    return True


async def setup_totp(session: AsyncSession, account_id: str, *, issuer: str = "Facil"):
    cred = await repo.get_credential(session, account_id)
    if cred is None:
        raise InvalidCredentials("no credential for this account")
    secret = totp_mod.generate_secret()
    cred.totp_secret = crypto.encrypt(secret)  # encrypted at rest
    cred.totp_enabled = False
    await session.flush()
    account = await identity_repo.get_account(session, account_id)
    name = (account.email or account.account_number or account_id) if account else account_id
    return secret, totp_mod.provisioning_uri(secret, name, issuer=issuer)


async def enable_totp(session: AsyncSession, account_id: str, code: str) -> list[str]:
    """Confirm the TOTP code, enable 2FA, and return one-time backup codes
    (shown ONCE — only their hashes are stored)."""
    cred = await repo.get_credential(session, account_id)
    if cred is None or not cred.totp_secret:
        raise InvalidCredentials("2fa not set up")
    try:
        secret = crypto.decrypt(cred.totp_secret)
    except crypto.DecryptionError as e:
        raise InvalidCredentials("2fa secret unreadable") from e
    if not totp_mod.verify_code(secret, code):
        raise InvalidCredentials("invalid 2fa code")
    cred.totp_enabled = True
    plaintext, hashes = backup_mod.generate()
    cred.totp_backup_codes = hashes
    await session.flush()
    return plaintext
