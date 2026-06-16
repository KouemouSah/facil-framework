"""OIDC identity federation (D4.7) — link/provision + role mapping + E2E scope.

External (Keycloak/LDAP/SAML-via-Keycloak) identities resolve to a LOCAL account
so our RBAC scope applies unchanged. Tested with mocked OIDC claims (no realm).
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.auth import federation
from app.auth.models import FederatedIdentity
from app.identity import repository as identity_repo
from app.identity.models import Account
from app.modules.organization.models import Organization
from app.rbac import repository as rbac_repo
from app.rbac import seed
from app.rbac.models import AccountRole


async def _org(s, code):
    o = Organization(code=code, legal_name=code)
    s.add(o)
    await s.flush()
    return o


@pytest.mark.asyncio
async def test_jit_provision_and_stable_link(client):
    _, db = client
    async with db.session_factory() as s:
        claims = {"sub": "kc-1", "email": "a@x.io", "email_verified": True, "name": "Ana"}
        aid = await federation.link_or_provision(s, "keycloak", "kc-1", claims)
        acc = await identity_repo.get_account(s, aid)
        assert acc.subject_type == "agent" and acc.email == "a@x.io"
        # same subject resolves to the SAME account (immutable link), even w/o email
        again = await federation.link_or_provision(s, "keycloak", "kc-1", {"sub": "kc-1"})
        assert again == aid
        await s.commit()


@pytest.mark.asyncio
async def test_verified_email_merges_preprovisioned_account(client):
    _, db = client
    async with db.session_factory() as s:
        pre = Account(email="b@x.io", status="active", subject_type="agent")
        s.add(pre)
        await s.flush()
        aid = await federation.link_or_provision(
            s, "keycloak", "kc-2", {"email": "b@x.io", "email_verified": True})
        assert aid == pre.id            # merged onto the pre-provisioned account
        await s.commit()


@pytest.mark.asyncio
async def test_unverified_email_does_not_merge_or_claim(client):
    _, db = client
    async with db.session_factory() as s:
        pre = Account(email="c@x.io", status="active")
        s.add(pre)
        await s.flush()
        aid = await federation.link_or_provision(
            s, "keycloak", "kc-3", {"email": "c@x.io", "email_verified": False})
        assert aid != pre.id            # NOT merged (anti-takeover)
        new = await identity_repo.get_account(s, aid)
        assert new.email is None        # unverified email not claimed
        await s.commit()


@pytest.mark.asyncio
async def test_disabled_account_is_denied(client):
    _, db = client
    async with db.session_factory() as s:
        acc = Account(email="d@x.io", status="suspended")
        s.add(acc)
        await s.flush()
        s.add(FederatedIdentity(account_id=acc.id, provider="keycloak", subject="kc-4"))
        await s.flush()
        assert await federation.link_or_provision(s, "keycloak", "kc-4", {}) is None
        await s.commit()


@pytest.mark.asyncio
async def test_group_role_mapping_sync_and_offboarding(client):
    _, db = client
    async with db.session_factory() as s:
        await seed.seed_roles(s, "empty")          # 'member' global role exists
        org = await _org(s, "orga")
        member = await rbac_repo.get_role_by_code(s, "member", None)
        acc = Account(status="active", subject_type="agent")
        s.add(acc)
        await s.flush()
        rmap = {"agents": "member"}

        # in group 'agents' + org claim -> member scoped to org A (source=idp)
        await federation.sync_mapped_roles(
            s, acc.id, {"groups": ["agents"], "org": "orga"}, role_map=rmap)
        rows = list(await s.scalars(
            select(AccountRole).where(AccountRole.account_id == acc.id)))
        assert len(rows) == 1
        assert rows[0].role_id == member.id and rows[0].organization_id == org.id
        assert rows[0].source == "idp"

        # add a LOCAL role -> must be preserved across re-sync
        s.add(AccountRole(account_id=acc.id, role_id=member.id, source="local"))
        await s.flush()

        # offboarding: removed from the group -> idp role dropped, local kept
        await federation.sync_mapped_roles(
            s, acc.id, {"groups": [], "org": "orga"}, role_map=rmap)
        rows = list(await s.scalars(
            select(AccountRole).where(AccountRole.account_id == acc.id)))
        assert len(rows) == 1 and rows[0].source == "local"
        await s.commit()


# --- E2E: a Keycloak-authenticated agent gets local scope ----------------

class _FakeOIDC:
    code = "keycloak_oidc"

    def __init__(self, by_token):
        self._by_token = by_token

    async def verify(self, token):
        return self._by_token.get(token)


@pytest_asyncio.fixture
async def fed_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-0123456789abcdef0123456789")
    import app.config as cfg
    cfg._settings = None

    from app.api import auth as auth_api
    from app.api import rbac as rbac_api
    from app.config_store.resolver import ConfigResolver
    from app.core.module_registry import import_module_models, load_modules
    from app.core.providers.registry import default_registry
    from app.db.base import Base
    from app.db.engine import Database
    from app.identity import models as _a  # noqa: F401
    from app.auth import models as _c  # noqa: F401
    from app.rbac import models as _r  # noqa: F401

    import_module_models()
    db = Database(f"sqlite+aiosqlite:///{tmp_path/'fed.db'}")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    application = FastAPI()
    application.state.db = db
    application.state.resolver = ConfigResolver(defaults={
        "branding.app_name": "Facil", "profile": "empty",
        "auth.oidc.role_map": {"agents": "member"},
        "auth.oidc.claim_groups": "groups", "auth.oidc.claim_org": "org",
        "auth.oidc.claim_unit": "unit"}, env={})
    application.state.registry = default_registry()
    application.state.auth = application.state.registry.build("auth", "native",
                                                              {"issuer": "facil"})
    # token "agent-tok" is an org-A agent in group 'agents'
    fake = _FakeOIDC({"agent-tok": {"sub": "kc-agent-1", "email": "agent@x.io",
                                    "email_verified": True, "groups": ["agents"],
                                    "org": "orga"}})
    application.state.auth_verifiers = [application.state.auth, fake]
    application.include_router(auth_api.router)
    application.include_router(rbac_api.router)
    load_modules(application, enabled=["organization", "location"])

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, db
    await db.dispose()
    cfg._settings = None


@pytest.mark.asyncio
async def test_keycloak_agent_is_scoped_via_local_rbac(fed_app):
    ac, _ = fed_app
    admin = {"X-Admin-Token": "test-token"}
    ORG = "/api/v1/modules/organization"
    await ac.post("/api/v1/rbac/admin/reseed?profile=empty", headers=admin)
    org_a = (await ac.post(f"{ORG}/", headers=admin,
                           json={"code": "orga", "legal_name": "A"})).json()["id"]
    org_b = (await ac.post(f"{ORG}/", headers=admin,
                           json={"code": "orgb", "legal_name": "B"})).json()["id"]

    # the agent presents its Keycloak token; federation links + maps member@orgA
    hdr = {"Authorization": "Bearer agent-tok"}
    assert (await ac.get(f"{ORG}/{org_a}", headers=hdr)).status_code == 200
    assert (await ac.get(f"{ORG}/{org_b}", headers=hdr)).status_code == 403
