"""Cache of the RESOLVED schema (spec §7) — the debt this module closes.

Reuses the repo's ONE shared cache abstraction (`app.core.cache.Cache` —
`MemoryCache`/`RedisCache`, wired at `app.state.cache`, `CACHE_REQUIRED`
fail-closed, Redis shared across replicas). This module introduces NO second
caching mechanism: it is a thin (get/set/invalidate) wrapper around that
cache, keyed and serialized for one purpose only — the list of resolved
`FieldSpec` dicts (`FieldDefinition.as_spec()`) for one `(organization_id,
target)` pair.

GUARD THAT MATTERS (SP1 spent a whole branch closing a cross-tenant leak —
see `test_schema_isolation.py`; a careless cache key would reopen it in the
one place nobody thinks to look): `_key()` is a pure function of
`(organization_id, target)` and NOTHING else. It must NEVER fold in anything
derived from the calling principal (account id, scope, break-glass flag) —
the resolved schema for a given org+target is identical no matter who asks
(authorization already gates the call BEFORE this module is ever touched,
see `app.api.schema.get_schema`), so there is nothing to gain from a
principal-keyed cache and everything to lose: dropping `organization_id`
from the key (or computing it from anything other than the exact org being
resolved) is the change that would let org A's cached entry answer for org
B. `test_schema_cache.py::test_cache_never_serves_org_As_definitions_to_org_B`
pins this — it fails immediately if the key stops depending on
`organization_id`.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.cache import Cache

# Bump if the cached SHAPE (`FieldDefinition.as_spec()`) ever changes — a
# stale deploy's leftover entries must never be misread across a shape
# upgrade; changing the version namespaces them apart instead of requiring a
# manual flush.
_VERSION = "v1"

# Bounds staleness for the one case this module does NOT invalidate precisely
# (documented in `invalidate()`'s docstring): a write on an ancestor org with
# `inherit_to_suborgs=True` can change a DESCENDANT org's resolved schema
# without this module walking the (potentially large, unbounded) descendant
# subtree to evict every affected entry. A short TTL bounds that window to a
# constant, instead of adding an unbounded fan-out write path.
DEFAULT_TTL_SECONDS = 60


def _key(organization_id: str, target: str) -> str:
    """The ENTIRE cache key — see the module docstring's GUARD note. Every
    character here comes from `organization_id`/`target`; nothing else may
    ever be folded in."""
    return f"schema:resolved:{_VERSION}:{organization_id}:{target}"


async def get(cache: Cache | None, organization_id: str, target: str
              ) -> list[dict[str, Any]] | None:
    """The cached resolved `db_specs` for `(organization_id, target)`, or
    `None` on a miss (including "no cache configured" — the caller falls back
    to resolving from the database, exactly like `security/rate_limit.py`'s
    "no cache -> no-op" convention)."""
    if cache is None:
        return None
    raw = await cache.get(_key(organization_id, target))
    if raw is None:
        return None
    return json.loads(raw)


async def set(cache: Cache | None, organization_id: str, target: str,
              specs: list[dict[str, Any]], *, ttl: int = DEFAULT_TTL_SECONDS
              ) -> None:
    """Populate the cache after a real database resolution. A no-op when no
    cache is configured."""
    if cache is None:
        return
    await cache.set(_key(organization_id, target), json.dumps(specs), ttl)


async def invalidate(cache: Cache | None, organization_id: str, target: str
                     ) -> None:
    """Evict the entry for the ROW'S OWN `(organization_id, target)`. Called
    from EVERY definition write path — create, update, archive, unarchive,
    purge, and both index-state transitions (the `/index` request setting
    `pending`, and the background job's terminal `ready`/`failed`) — see
    `app.api.admin_field_definitions`. Miss one and an admin defines a field
    and does not see it: the worst kind of "it works on my machine".

    KNOWN, DOCUMENTED LIMITATION: this evicts only the WRITING org's own
    entry. A definition with `inherit_to_suborgs=True` also affects every
    DESCENDANT org's resolved schema, and this function does not walk that
    (potentially large, unbounded) subtree to evict their entries too —
    `DEFAULT_TTL_SECONDS` bounds that staleness instead. Precise invalidation
    would need an org -> descendants query this module does not have (only
    the ANCESTOR direction is walked, by `repository._ancestor_org_ids`);
    `inherit_to_suborgs` is edited far less often than schemas are read, so a
    bounded TTL was judged the right trade-off over an unbounded fan-out
    write path. Revisit if this ever proves too stale in practice.
    """
    if cache is None:
        return
    await cache.delete(_key(organization_id, target))
