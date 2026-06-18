"""S2 — hydrate the backend's infra creds from OpenBao before settings/DB."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import secrets_bootstrap as sb  # noqa: E402


class FakeProvider:
    """Stand-in for OpenBaoSecretsProvider with deterministic load_all()."""

    def __init__(self, config=None, *, secrets=None, error=None, fail_times=None):
        self._secrets = secrets or {}
        self._error = error
        # None => always raise (when error set); int => raise N times then succeed.
        self._fail_times = fail_times
        self.calls = 0

    async def load_all(self):
        self.calls += 1
        if self._error is not None and (
                self._fail_times is None or self.calls <= self._fail_times):
            raise self._error
        return dict(self._secrets)


def _factory(fp):
    return lambda config: fp


async def _noop_sleep(_):  # never actually delays the tests
    return None


def _http_status_error(code=403):
    req = httpx.Request("GET", "http://openbao:8200/v1/auth/approle/login")
    resp = httpx.Response(code, request=req)
    return httpx.HTTPStatusError("forbidden", request=req, response=resp)


@pytest.mark.asyncio
async def test_vault_overrides_stale_env():
    env = {"OPENBAO_ROLE_ID": "r", "DATABASE_URL": "stale", "MINIO_ACCESS_KEY": "old"}
    fp = FakeProvider(secrets={"DATABASE_URL": "fresh", "MINIO_ACCESS_KEY": "new",
                               "MINIO_SECRET_KEY": "sk"})
    rep = await sb.hydrate_secrets_from_vault(
        env=env, provider_factory=_factory(fp), sleep=_noop_sleep)
    assert rep["source"] == "vault"
    assert env["DATABASE_URL"] == "fresh"          # vault wins over stale env
    assert env["MINIO_ACCESS_KEY"] == "new"
    assert env["MINIO_SECRET_KEY"] == "sk"          # newly added
    assert set(rep["keys"]) >= {"DATABASE_URL", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY"}


@pytest.mark.asyncio
async def test_unchanged_keys_not_reported():
    env = {"OPENBAO_ROLE_ID": "r", "DATABASE_URL": "same"}
    fp = FakeProvider(secrets={"DATABASE_URL": "same"})
    rep = await sb.hydrate_secrets_from_vault(env=env, provider_factory=_factory(fp))
    assert rep["source"] == "vault" and rep["keys"] == []  # nothing changed


@pytest.mark.asyncio
async def test_skips_without_role_id():
    env = {"DATABASE_URL": "x"}

    def _boom(config):  # must never be built in env_file mode
        raise AssertionError("provider must not be built without OPENBAO_ROLE_ID")

    rep = await sb.hydrate_secrets_from_vault(env=env, provider_factory=_boom)
    assert rep["source"] == "env-only" and env["DATABASE_URL"] == "x"


@pytest.mark.asyncio
async def test_disabled_by_knob():
    env = {"OPENBAO_ROLE_ID": "r", "SECRETS_VAULT_HYDRATE": "0"}
    rep = await sb.hydrate_secrets_from_vault(
        env=env, provider_factory=_factory(FakeProvider(secrets={"DATABASE_URL": "v"})))
    assert rep["source"] == "disabled" and "DATABASE_URL" not in env


@pytest.mark.asyncio
async def test_connection_error_falls_back_and_retries():
    env = {"OPENBAO_ROLE_ID": "r", "DATABASE_URL": "stale"}
    fp = FakeProvider(error=httpx.ConnectError("down"))   # always fails
    rep = await sb.hydrate_secrets_from_vault(
        env=env, provider_factory=_factory(fp), sleep=_noop_sleep, attempts=3)
    assert rep["source"] == "env-fallback"
    assert env["DATABASE_URL"] == "stale"     # untouched fallback
    assert fp.calls == 3                       # retried up to attempts


@pytest.mark.asyncio
async def test_required_hard_fails_when_vault_down():
    env = {"OPENBAO_ROLE_ID": "r", "SECRETS_VAULT_REQUIRED": "1"}
    fp = FakeProvider(error=httpx.ConnectError("down"))
    with pytest.raises(RuntimeError, match="SECRETS_VAULT_REQUIRED"):
        await sb.hydrate_secrets_from_vault(
            env=env, provider_factory=_factory(fp), sleep=_noop_sleep, attempts=2)


@pytest.mark.asyncio
async def test_retries_then_succeeds():
    env = {"OPENBAO_ROLE_ID": "r"}
    fp = FakeProvider(secrets={"DATABASE_URL": "fresh"},
                      error=httpx.ConnectError("x"), fail_times=2)
    rep = await sb.hydrate_secrets_from_vault(
        env=env, provider_factory=_factory(fp), sleep=_noop_sleep, attempts=5)
    assert rep["source"] == "vault" and env["DATABASE_URL"] == "fresh"
    assert fp.calls == 3                       # 2 failures + 1 success


@pytest.mark.asyncio
async def test_auth_error_is_not_retried():
    env = {"OPENBAO_ROLE_ID": "r", "DATABASE_URL": "stale"}
    fp = FakeProvider(error=_http_status_error(403))
    rep = await sb.hydrate_secrets_from_vault(
        env=env, provider_factory=_factory(fp), sleep=_noop_sleep, attempts=5)
    assert rep["source"] == "env-fallback"
    assert fp.calls == 1                       # 403 not retried (won't self-heal)


# --- fail-secure default posture (derived from ENVIRONMENT when knob unset) ---

@pytest.mark.asyncio
async def test_fail_secure_default_in_prod_when_vault_down():
    # No SECRETS_VAULT_REQUIRED knob + non-dev env => required is implied.
    env = {"OPENBAO_ROLE_ID": "r", "ENVIRONMENT": "production"}
    fp = FakeProvider(error=httpx.ConnectError("down"))
    with pytest.raises(RuntimeError, match="SECRETS_VAULT_REQUIRED"):
        await sb.hydrate_secrets_from_vault(
            env=env, provider_factory=_factory(fp), sleep=_noop_sleep, attempts=2)


@pytest.mark.asyncio
async def test_dev_default_falls_back_when_vault_down():
    env = {"OPENBAO_ROLE_ID": "r", "ENVIRONMENT": "development", "DATABASE_URL": "x"}
    fp = FakeProvider(error=httpx.ConnectError("down"))
    rep = await sb.hydrate_secrets_from_vault(
        env=env, provider_factory=_factory(fp), sleep=_noop_sleep, attempts=2)
    assert rep["source"] == "env-fallback" and env["DATABASE_URL"] == "x"


@pytest.mark.asyncio
async def test_explicit_relax_overrides_prod():
    # Operator opt-out wins even in prod.
    env = {"OPENBAO_ROLE_ID": "r", "ENVIRONMENT": "production",
           "SECRETS_VAULT_REQUIRED": "0"}
    fp = FakeProvider(error=httpx.ConnectError("down"))
    rep = await sb.hydrate_secrets_from_vault(
        env=env, provider_factory=_factory(fp), sleep=_noop_sleep, attempts=2)
    assert rep["source"] == "env-fallback"


@pytest.mark.asyncio
async def test_programming_bug_propagates_not_swallowed():
    # A non-httpx error (e.g. malformed vault response) must NOT be masked as
    # "vault down" — it propagates so the bug crashes the boot loudly.
    env = {"OPENBAO_ROLE_ID": "r", "SECRETS_VAULT_REQUIRED": "0"}
    fp = FakeProvider(error=KeyError("auth"))
    with pytest.raises(KeyError):
        await sb.hydrate_secrets_from_vault(
            env=env, provider_factory=_factory(fp), sleep=_noop_sleep, attempts=3)
    assert fp.calls == 1                       # not retried (not an httpx transient)


@pytest.mark.asyncio
async def test_warns_when_vault_up_but_infra_missing(caplog):
    import logging
    env = {"OPENBAO_ROLE_ID": "r", "DATABASE_URL": "fromenv"}
    fp = FakeProvider(secrets={"JWT_SECRET_KEY": "j"})   # no DATABASE_URL in vault
    with caplog.at_level(logging.WARNING):
        rep = await sb.hydrate_secrets_from_vault(env=env, provider_factory=_factory(fp))
    assert rep["source"] == "vault" and env["DATABASE_URL"] == "fromenv"
    assert any("no DATABASE_URL" in r.message for r in caplog.records)
