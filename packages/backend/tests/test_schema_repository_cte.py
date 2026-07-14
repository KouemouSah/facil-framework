"""D2 — kill the ancestor-walk N+1.

`_ancestor_org_ids` used to do up to `MAX_ORG_DEPTH` (20) SEQUENTIAL round
trips walking `Organization.parent_id` upward — a textbook N+1 that fires on
every schema-form open. This pins THREE things:

  1. Under SQLite (the default suite dialect) the ORIGINAL loop is still
     there as the fallback, and really is an N+1 (baseline, "before").
  2. Under real Postgres, `_ancestor_org_ids` now does the SAME walk in ONE
     round trip via a bounded `WITH RECURSIVE` CTE — measured with a
     SQLAlchemy event listener, not asserted from code reading.
  3. The CTE returns EXACTLY the same (nearest-first, depth-bounded) result
     as the loop it replaces — an equivalence test, not a rewrite-and-hope.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

import pytest
import pytest_asyncio
from sqlalchemy import event

from app.core.schema.repository import (
    MAX_ORG_DEPTH,
    _ancestor_org_ids,
    _ancestor_org_ids_cte,
    _ancestor_org_ids_loop,
)


def _count_round_trips(engine):
    """Counts real DBAPI cursor executions ("round trips") on `engine` between
    `start()`/`stop()`. Hooking `before_cursor_execute` on the underlying SYNC
    engine (an `AsyncEngine` always wraps one) is the one place that fires
    exactly once per statement actually sent to the database — unlike
    counting `session.execute()` calls in Python, this cannot be fooled by
    driver-level batching/pipelining."""
    counter = {"n": 0}
    sync_engine = engine.sync_engine if hasattr(engine, "sync_engine") else engine

    def _tick(*_args, **_kwargs):
        counter["n"] += 1

    event.listen(sync_engine, "before_cursor_execute", _tick)

    def _stop():
        event.remove(sync_engine, "before_cursor_execute", _tick)

    return counter, _stop


# --- SQLite fallback (default suite dialect): baseline / "before" -----------

@pytest.mark.asyncio
async def test_loop_fallback_is_one_round_trip_per_ancestor_hop(
        session, org_a, org_child_of_a):
    """The BEFORE number: under SQLite, resolving one hop of ancestry still
    costs one round trip PER HOP (plus the final "no parent" probe) — this is
    exactly the N+1 the CTE below eliminates on Postgres."""
    counter, stop = _count_round_trips(session.bind)
    try:
        result = await _ancestor_org_ids_loop(session, org_child_of_a.id)
    finally:
        stop()
    assert result == [org_a.id]
    # hop 1: child -> org_a (found) ; hop 2: org_a -> None (stops the loop).
    assert counter["n"] == 2


@pytest.mark.asyncio
async def test_dispatcher_falls_back_to_the_loop_under_sqlite(
        session, org_a, org_child_of_a):
    """`_ancestor_org_ids` (the public dispatcher every caller uses) must
    still work correctly under a non-Postgres dialect — degrades cleanly to
    the loop, per the repo rule that Postgres-only SQL is dialect-guarded."""
    assert await _ancestor_org_ids(session, org_child_of_a.id) == [org_a.id]


@pytest.mark.asyncio
async def test_loop_respects_the_depth_bound(session):
    """A chain longer than MAX_ORG_DEPTH must still terminate, capped."""
    from app.modules.organization.models import Organization
    parent_id = None
    chain: list[str] = []
    for i in range(MAX_ORG_DEPTH + 5):
        org = Organization(code=f"deep-{i}", legal_name=f"Deep {i}", parent_id=parent_id)
        session.add(org)
        await session.flush()
        chain.append(org.id)
        parent_id = org.id
    deepest = chain[-1]
    result = await _ancestor_org_ids_loop(session, deepest)
    assert len(result) == MAX_ORG_DEPTH
    # nearest-first: the deepest org's immediate parent must be first.
    assert result[0] == chain[-2]


# --- Postgres: the fix, measured -----------------------------------------

def _pg_test_url() -> str | None:
    base = os.environ.get("PG_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not base:
        return None
    if base.startswith("postgres://"):
        base = base.replace("postgres://", "postgresql+asyncpg://", 1)
    elif base.startswith("postgresql://") and "+asyncpg" not in base:
        base = base.replace("postgresql://", "postgresql+asyncpg://", 1)
    parts = urlsplit(base)
    return urlunsplit((parts.scheme, parts.netloc, "/facil_test", "", ""))


@pytest_asyncio.fixture
async def pg_session():
    """A real Postgres `AsyncSession` against a throwaway `facil_test`
    database, schema created fresh. Skips (never fails) when no real
    Postgres is reachable — same convention as `test_schema_indexing.py`."""
    admin_url = os.environ.get("PG_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    test_url = _pg_test_url()
    if not admin_url or not test_url:
        pytest.skip("no DATABASE_URL/PG_TEST_DATABASE_URL — no real Postgres to test against")
    if admin_url.startswith("postgres://"):
        admin_url = admin_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif admin_url.startswith("postgresql://") and "+asyncpg" not in admin_url:
        admin_url = admin_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    try:
        admin_engine = create_async_engine(admin_url, pool_pre_ping=True)
        autocommit = admin_engine.execution_options(isolation_level="AUTOCOMMIT")
        async with autocommit.connect() as conn:
            await conn.exec_driver_sql("DROP DATABASE IF EXISTS facil_test WITH (FORCE)")
            await conn.exec_driver_sql("CREATE DATABASE facil_test")
        await admin_engine.dispose()
    except Exception as exc:  # noqa: BLE001 — any connectivity failure => skip, don't fail
        pytest.skip(f"real Postgres not reachable at {admin_url!r}: {exc!r}")

    from app.core.module_registry import import_module_models
    from app.db.base import Base
    from app.identity import models as _a  # noqa: F401
    from app.auth import models as _c  # noqa: F401
    from app.rbac import models as _r  # noqa: F401
    import_module_models()

    engine = create_async_engine(test_url, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine) as s:
        yield s

    await engine.dispose()
    cleanup_engine = create_async_engine(admin_url, pool_pre_ping=True)
    autocommit = cleanup_engine.execution_options(isolation_level="AUTOCOMMIT")
    async with autocommit.connect() as conn:
        await conn.exec_driver_sql("DROP DATABASE IF EXISTS facil_test WITH (FORCE)")
    await cleanup_engine.dispose()


async def _chain(session, n: int) -> list[str]:
    """n orgs, each the parent of the next: chain[0] is the ROOT (no parent),
    chain[-1] is the deepest descendant."""
    from app.modules.organization.models import Organization
    parent_id = None
    ids: list[str] = []
    for i in range(n):
        org = Organization(code=f"pg-chain-{i}", legal_name=f"PG Chain {i}",
                           parent_id=parent_id)
        session.add(org)
        await session.flush()
        ids.append(org.id)
        parent_id = org.id
    await session.commit()
    return ids


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_dispatcher_picks_the_cte_under_postgres(pg_session):
    assert pg_session.bind.dialect.name == "postgresql"
    chain = await _chain(pg_session, 3)
    # chain = [root, mid, leaf] ; ancestors of leaf, nearest first = [mid, root]
    result = await _ancestor_org_ids(pg_session, chain[-1])
    assert result == [chain[1], chain[0]]


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_cte_matches_the_loop_result_over_a_deep_chain(pg_session):
    """Equivalence: the CTE must return EXACTLY what the loop returns —
    same members, same nearest-first order — over a chain deep enough to
    exercise several recursive steps but short of the depth bound."""
    chain = await _chain(pg_session, 8)
    deepest = chain[-1]
    via_loop = await _ancestor_org_ids_loop(pg_session, deepest)
    via_cte = await _ancestor_org_ids_cte(pg_session, deepest)
    assert via_cte == via_loop
    assert via_cte == list(reversed(chain[:-1]))


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_cte_respects_the_depth_bound(pg_session):
    """A chain longer than MAX_ORG_DEPTH must still be capped at
    MAX_ORG_DEPTH ancestors — the SQL's own `depth < :max_depth` guard, not
    just the (Python-side) loop's `range(MAX_ORG_DEPTH)`."""
    chain = await _chain(pg_session, MAX_ORG_DEPTH + 5)
    deepest = chain[-1]
    result = await _ancestor_org_ids_cte(pg_session, deepest)
    assert len(result) == MAX_ORG_DEPTH
    # nearest-first: the deepest org's immediate parent must be first.
    assert result[0] == chain[-2]
    # and it must match the (also-bounded) loop over the same chain.
    assert result == await _ancestor_org_ids_loop(pg_session, deepest)


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_cte_resolves_ancestors_in_exactly_one_round_trip(pg_session):
    """THE measured proof: whatever the chain's depth, the CTE costs ONE
    round trip — not one-per-hop. Built on the SAME connection the loop test
    below uses, so the comparison is apples-to-apples."""
    chain = await _chain(pg_session, 10)
    deepest = chain[-1]

    counter, stop = _count_round_trips(pg_session.bind)
    try:
        result = await _ancestor_org_ids_cte(pg_session, deepest)
    finally:
        stop()

    assert result == list(reversed(chain[:-1]))
    assert counter["n"] == 1, f"expected exactly 1 round trip, measured {counter['n']}"


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_loop_over_the_same_chain_costs_one_round_trip_per_hop_on_postgres(
        pg_session):
    """The BEFORE number, reproduced on real Postgres (not just SQLite) so the
    before/after comparison in the report is apples-to-apples on one engine:
    a 10-deep chain costs 10 round trips via the loop, versus 1 via the CTE
    (previous test) — the N+1 this task exists to kill."""
    chain = await _chain(pg_session, 10)
    deepest = chain[-1]

    counter, stop = _count_round_trips(pg_session.bind)
    try:
        result = await _ancestor_org_ids_loop(pg_session, deepest)
    finally:
        stop()

    assert result == list(reversed(chain[:-1]))
    assert counter["n"] == 10, f"expected 10 round trips (one per hop), measured {counter['n']}"
