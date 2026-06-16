"""OIDC identity federation — link/provision + scope mapping (D4.7).

Keycloak (federating LDAP/AD, brokering SAML) authenticates the agent and hands
us an OIDC token. This module resolves that external identity to a LOCAL account
so our RBAC scope (account_role) applies unchanged:

- resolve_principal(): OIDC `sub` -> local account.id (the heart). Tries the
  immutable (provider, subject) link; falls back to a VERIFIED-email match onto a
  pre-provisioned account; else JIT-creates an agent account. Then re-syncs the
  IdP-mapped roles. Returns claims with `sub` rewritten to the local account id.
- Authorization stays 100% local: module permissions are NEVER mapped from the
  IdP — once linked, the same RBAC (roles + scope) covers natives and agents.

Security: link key is (provider, subject), never email; email merge only when the
token asserts email_verified; suspended/inactive accounts are denied (offboarding).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import FederatedIdentity
from app.identity import repository as identity_repo
from app.identity.models import Account
from app.modules.organization import repository as org_repo
from app.rbac import repository as rbac_repo
from app.rbac.models import AccountRole


def _usable(account: Account | None) -> bool:
    return bool(account and account.is_active
                and account.status not in ("suspended", "deactivated"))


async def _link(session: AsyncSession, provider: str, subject: str) -> FederatedIdentity | None:
    return await session.scalar(select(FederatedIdentity).where(
        FederatedIdentity.provider == provider, FederatedIdentity.subject == subject))


async def link_or_provision(session: AsyncSession, provider: str, subject: str,
                            claims: dict) -> str | None:
    """Resolve the external identity to a local account id (or None if the
    account is disabled). Creates the link / account on first sight."""
    existing = await _link(session, provider, subject)
    if existing is not None:
        account = await identity_repo.get_account(session, existing.account_id)
        return account.id if _usable(account) else None

    email = (claims.get("email") or "").strip().lower()
    verified = claims.get("email_verified") is True
    # Merge onto a pre-provisioned account ONLY by a verified email (anti-takeover).
    if email and verified:
        account = await identity_repo.get_by_email(session, email)
        if account is not None:
            if not _usable(account):
                return None
            session.add(FederatedIdentity(account_id=account.id, provider=provider,
                                          subject=subject))
            await session.flush()
            return account.id

    # JIT-provision a new agent account. Only claim the email if it is verified
    # (else leave NULL to avoid collisions / takeover).
    account = Account(
        email=email if (email and verified) else None,
        display_name=claims.get("name") or claims.get("preferred_username"),
        subject_type="agent", status="active", email_verified=verified)
    session.add(account)
    await session.flush()
    try:
        async with session.begin_nested():  # race-safe link creation
            session.add(FederatedIdentity(account_id=account.id, provider=provider,
                                          subject=subject))
            await session.flush()
    except IntegrityError:
        link = await _link(session, provider, subject)  # concurrent first login
        return link.account_id if link else None
    return account.id


async def sync_mapped_roles(session: AsyncSession, account_id: str, claims: dict, *,
                            role_map: dict, group_claim: str = "groups",
                            org_claim: str = "org", unit_claim: str = "unit") -> None:
    """Re-derive the IdP-mapped (source='idp') roles from the token's groups +
    org/unit claims. Admin-assigned (source='local') roles are left untouched.
    Unknown role codes or org/unit codes are skipped (no silent auto-create)."""
    groups = claims.get(group_claim) or []
    if isinstance(groups, str):
        groups = [groups]

    org_id = unit_id = None
    org_code = claims.get(org_claim)
    if org_code:
        org = await org_repo.get_organization_by_code(session, org_code)
        org_id = org.id if org else None
        unit_code = claims.get(unit_claim)
        if org_id and unit_code:
            unit = await org_repo.get_unit_by_code(session, org_id, unit_code)
            unit_id = unit.id if unit else None

    desired: set[tuple[str, str | None, str | None]] = set()
    for group in groups:
        role_code = (role_map or {}).get(group)
        if not role_code:
            continue
        role = await rbac_repo.get_role_by_code(session, role_code, None)
        if role is not None:
            desired.add((role.id, org_id, unit_id))

    current = list(await session.scalars(select(AccountRole).where(
        AccountRole.account_id == account_id, AccountRole.source == "idp")))
    current_keys = {(ar.role_id, ar.organization_id, ar.org_unit_id) for ar in current}
    for ar in current:  # drop stale IdP grants (e.g. removed from an AD group)
        if (ar.role_id, ar.organization_id, ar.org_unit_id) not in desired:
            await session.delete(ar)
    for role_id, oid, uid in desired - current_keys:
        session.add(AccountRole(account_id=account_id, role_id=role_id,
                                organization_id=oid, org_unit_id=uid, source="idp"))
    await session.flush()


async def resolve_principal(session: AsyncSession, provider: str, claims: dict, *,
                            role_map: dict | None = None, claim_groups: str = "groups",
                            claim_org: str = "org",
                            claim_unit: str = "unit") -> dict | None:
    """OIDC claims -> local principal (sub = local account id), syncing mapped
    roles. None if the subject is missing or the account is disabled."""
    subject = claims.get("sub")
    if not subject:
        return None
    account_id = await link_or_provision(session, provider, subject, claims)
    if account_id is None:
        return None
    await sync_mapped_roles(session, account_id, claims, role_map=role_map or {},
                            group_claim=claim_groups, org_claim=claim_org,
                            unit_claim=claim_unit)
    return {**claims, "sub": account_id, "idp": provider, "idp_subject": subject}
