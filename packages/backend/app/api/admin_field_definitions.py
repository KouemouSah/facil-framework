"""Admin field-definitions API — CRUD, caps, guards, archive/purge (`fields.manage`).

This is the ONLY place a `FieldDefinition` is ever written — so it is the
place three of the four guards built earlier (`assert_key_allowed`,
`assert_not_secretish`, `assert_relation_resource_allowed`) get wired in, via
`_guard_key_and_relation` below. The fourth, `clean_richtext`, applies to
*entity* custom-field VALUES, not to a definition's own fields — it is wired
inline in the organization/location/party API modules' create/update
handlers, right after `validate_blob`/`merge_blob` produces the clean dict
(via `app.core.schema.sanitize.clean_richtext_fields`).

Style follows `admin_providers.py`: `enforce_if_match` + `row_etag` for
optimistic concurrency, `audit.record` + `session.commit()` on every mutation.

Scope model — every route enforces on the scope of the TARGET, never the caller
(repo rule: "écriture `enforce` sur le scope de la cible"), and NO route uses a
router-level `require_permission` dependency:

* `GET /` and `POST /` name their org via `?organization_id=` and authorize
  IN-HANDLER through `_authorize_org`, bound to the very same variable the
  handler reads/persists. A router-level dependency would be a confused deputy
  here — see `_authorize_org`'s docstring for the `org_id`-alias attack it
  closes.
* `GET/PUT/{id}` + `archive`/`unarchive`/`purge` address a definition by `{id}`
  alone, so the only organisation that may authorize the action is the ROW'S OWN
  `organization_id`, loaded from the DB (`_authorize_target`). A caller who
  cannot see that organisation gets **404, not 403** — a 403 would confirm the
  id exists and belongs to a real tenant (mirrors `GET /api/v1/schema`, Task 12).

Known residual (accepted, documented): the 404-vs-403 path does strictly less DB
work when the row does not exist than when it exists-but-is-invisible, so a
determined attacker with timing measurements could in principle distinguish the
two. Closing it would mean doing the full RBAC walk for ids that don't exist.
Judged not worth it: it discloses only the existence of an id they already had
to guess, never its contents.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.concurrency import enforce_if_match, row_etag
from app.api.deps import get_session
from app.auth import audit
from app.core.cache import Cache
from app.core.schema import cache as schema_cache
from app.core.schema import indexing
from app.core.schema import repository as schema_repo
from app.core.schema.registry import EXTENSIBLE_TARGETS
from app.core.schema.reserved import assert_key_allowed, assert_relation_resource_allowed
from app.core.schema.sanitize import assert_not_secretish
from app.core.schema.spec import FieldSpec
from app.core.schema.types import DEFAULT_WIDGET
from app.db.engine import Database
from app.models.field_definition import FieldDefinition
from app.modules.organization.models import Organization
from app.rbac.scope import Scope
from app.security.auth_dep import require_auth
from app.security.permission_dep import enforce, visible_orgs

logger = logging.getLogger(__name__)

# Per (organization_id, target) — an org cannot saturate the database for every
# other tenant, and an unbounded set of `indexed` fields cannot force unbounded
# concurrent index builds. Counted OWN definitions only (`repository.count_for`):
# a child org is never penalised for what its parent already defined.
#
# The two caps count DIFFERENTLY on purpose (Fix wave 1 review finding):
#   - MAX_FIELDS_PER_TARGET counts archived rows too (`include_archived=True`
#     in `_check_field_cap`) — it bounds STORAGE and the `(org, target, key)`
#     unique-constraint footprint, which an archived row still consumes
#     (archive never destroys anything, spec §3 principle 7). Otherwise an
#     org could create 50, archive all 50, create 50 more, forever. PURGE is
#     the deliberate, explicit, audited escape valve — not archive.
#   - MAX_INDEXED_PER_TARGET excludes archived rows — it bounds LIVE database
#     indexes, and an archived field is not sortable, so it should not hold
#     one. (Whether archiving actually DROPS the index is Task 14 work — see
#     that task's notes; today `indexed`/`index_state` are metadata only,
#     no DDL exists yet.)
# `_set_archived` re-checks both on UNARCHIVE (not just on create/update) —
# unarchiving pushes a row back into the counted-as-active set for whichever
# cap excludes archived rows.
MAX_FIELDS_PER_TARGET = 50
MAX_INDEXED_PER_TARGET = 10

router = APIRouter(prefix="/api/v1/admin/field-definitions",
                   tags=["admin-field-definitions"],
                   dependencies=[Depends(require_auth)])


async def _authorize_org(session: AsyncSession, principal: dict,
                         organization_id: str) -> None:
    """`fields.manage` on `organization_id` — enforced IN-HANDLER, bound to the
    exact value the handler goes on to use.

    This is deliberately NOT a router-level `Depends(require_permission(...))`.
    That dependency resolves its scope through `rbac.scope.raw_scope_ids`, whose
    `_pick(request, "org_id", "organization_id")` prefers the `org_id` ALIAS over
    the canonical name — in the query string as well as the path. A route that
    both (a) leans on the router-level dependency and (b) binds its own
    `organization_id` query parameter is therefore a confused deputy: a caller
    can send `?organization_id=<victim>&org_id=<their own org>`, RBAC authorises
    against `org_id` (theirs), and the handler writes the row against
    `organization_id` (the victim's). FastAPI ignores the undeclared extra param
    silently, so nothing catches it.

    Binding the check to the same variable the handler persists closes that gap
    by construction — the same reason `location/api.create_site` enforces
    in-handler against the org it takes from the body. Do not "simplify" this
    back into a router-level dependency.
    """
    await enforce(session, principal, "fields.manage",
                  Scope(organization_id=organization_id))


class FieldDefinitionIn(FieldSpec):
    """The request body IS a `FieldSpec` (+ the two columns that are not part
    of the wire descriptor: `target` and `inherit_to_suborgs`) — subclassing
    reuses `FieldSpec`'s own `_coherent`/`_key_shape`/`_label_localised`
    validators verbatim (pydantic v2 runs a subclass's inherited validators),
    so FastAPI's normal body-parsing already rejects a type/widget/indexed
    mismatch, a `select` without `options`, a `relation` without
    `relation_resource`, etc. — before this module's handler ever runs. No
    duplicated field list to drift out of sync with `FieldSpec`.

    `index_state` is inherited too, but is DELIBERATELY NEVER READ from this
    model anywhere below: it is runtime state owned by the (future) indexing
    job, not a client-declarable attribute — reading it here would let a
    caller forge `"ready"` and have `sortable_keys()` (a later task) treat an
    unindexed column as safely sortable.
    """

    target: str
    inherit_to_suborgs: bool = False

    @field_validator("target")
    @classmethod
    def _extensible(cls, v: str) -> str:
        """`target` must be on the opt-in `EXTENSIBLE_TARGETS` allowlist. A tenant
        must never be able to bolt custom fields onto a security table (RBAC,
        settings, accounts, audit). `assert_key_allowed` would reject an unknown
        target anyway (its `_model_for` raises), but only as a side effect — this
        states the rule directly, and yields a 422 naming the legal targets."""
        if v not in EXTENSIBLE_TARGETS:
            raise ValueError(
                f"target {v!r} is not extensible; one of {sorted(EXTENSIBLE_TARGETS)}")
        return v

    @model_validator(mode="before")
    @classmethod
    def _default_widget(cls, data: object) -> object:
        """`FieldSpec.widget` defaults to `""` because the `field()` factory
        (used by code-declared product schemas) always resolves it before
        construction. A raw client JSON body has no such factory in front of
        it, so an omitted/blank `widget` must resolve to the type's canonical
        widget HERE — the same rule `field()` applies — or `_coherent`
        (inherited from `FieldSpec`) would reject every request that
        (reasonably) omits `widget` entirely."""
        if isinstance(data, dict) and not data.get("widget"):
            data = {**data, "widget": DEFAULT_WIDGET.get(data.get("type", "string"), "plain")}
        return data


def _public(row: FieldDefinition) -> dict:
    return {**row.as_dict(), "etag": row_etag(row)}


async def _get_or_404(session: AsyncSession, definition_id: str) -> FieldDefinition:
    row = await session.get(FieldDefinition, definition_id)
    if row is None:
        raise HTTPException(404, f"field definition '{definition_id}' not found")
    return row


async def _authorize_target(session: AsyncSession, principal: dict,
                            organization_id: str) -> None:
    """`fields.manage`, enforced at the TARGET row's own organisation — never
    the caller's claimed scope.

    TWO checks, and both are needed — they answer different questions:

    1. `visible_orgs` (org-granular) → can the caller see this organisation AT
       ALL? If not: **404, not 403** — a 403 would confirm that this definition
       id exists and belongs to a real organisation, leaking another tenant's
       existence (mirrors `GET /api/v1/schema`'s pattern, Task 12).
    2. `enforce` at the row's org SCOPE → is the caller actually authorized to
       WRITE there? `visible_orgs` alone is NOT sufficient authorization: its
       own docstring (`rbac/service.visible_org_ids`) states it is deliberately
       coarse — "a unit/site-scoped grant makes its parent organization
       visible (org-level granularity)". It is a *listing* filter, and every
       other caller in the repo uses it only for `*.read`. Using it as the
       write decision would let a `fields.manage` grant scoped to ONE SITE
       inside org A rewrite and purge org A's org-wide definitions. `enforce`
       runs the real `covers()` predicate (org → unit subtree → site), which
       is exactly what the POST path already gets from `require_permission`.
       This keeps PUT/archive/purge exactly as strong as POST, per the repo
       rule: "écriture `enforce` sur le scope de la cible".
    """
    allowed = await visible_orgs(session, principal, "fields.manage")
    if allowed is not None and organization_id not in allowed:
        raise HTTPException(404, "field definition not found")
    await _authorize_org(session, principal, organization_id)


def _guard_key_and_relation(body: FieldDefinitionIn) -> None:
    """The three definition-shape guards (Task 8-era code, zero callers until
    now): a custom key must never shadow a real column, must never look like a
    plaintext credential, and a `relation` field's resource must be on the
    fixed allowlist (a free-form resource string would be interpolated into a
    client request path by the picker). Raises 422 on any violation."""
    try:
        assert_key_allowed(body.target, body.key)
        assert_not_secretish(body.key)
        if body.type == "relation":
            assert_relation_resource_allowed(body.relation_resource)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


async def _check_field_cap(session: AsyncSession, target: str,
                           organization_id: str) -> None:
    """The 50-field cap. Checked on CREATE ONLY — an operation that adds no new
    field (e.g. flipping an existing one to `indexed`) must not be refused just
    because the org is legitimately AT its limit.

    Counts ARCHIVED rows too (`include_archived=True`) — an archived row still
    occupies storage and still holds the `(organization_id, target, key)`
    unique constraint, so it must count against the cap that bounds total row
    footprint. Without this, archive would be a free, repeatable way to reset
    the cap: create 50, archive all 50, create 50 more, forever. PURGE is the
    intended, explicit, audited way to actually free capacity.
    """
    total = await schema_repo.count_for(session, target, organization_id,
                                        include_archived=True)
    if total >= MAX_FIELDS_PER_TARGET:
        raise HTTPException(
            422, f"organization already has {total} field(s) (including archived) "
                 f"on {target!r} (max {MAX_FIELDS_PER_TARGET}); purge archived "
                 "definitions to free capacity")


async def _check_indexed_cap(session: AsyncSession, target: str,
                             organization_id: str) -> None:
    """The 10-indexed cap. Checked on create-with-`indexed` AND on a
    False->True flip in update (the row being flipped is not yet counted, so
    `>=` is right in both cases)."""
    indexed_total = await schema_repo.count_for(
        session, target, organization_id, indexed_only=True)
    if indexed_total >= MAX_INDEXED_PER_TARGET:
        raise HTTPException(
            422, f"organization already has {indexed_total} indexed field(s) on "
                 f"{target!r} (max {MAX_INDEXED_PER_TARGET})")


async def _commit(session: AsyncSession, *, key: str, target: str,
                  organization_id: str, cache: Cache | None) -> None:
    """Commit, mapping the `uq_field_definition_org_target_key` violation to a
    409 instead of a bare 500. Redefining a key that already exists is the most
    likely admin mistake there is; it must not surface as a server error. Same
    convention as `organization/api._commit` and `party/api._save_new`.

    NOTE (TOCTOU, accepted and explicit): the caps above are a `SELECT count(*)`
    followed by an INSERT with no serialization, so two concurrent creates at
    49/9 could both pass and land 51/11. The window is a few milliseconds on an
    endpoint only an org admin can call; the cost of closing it (a row lock on
    the owning organization for every definition write) is not worth it at this
    scale. Documented rather than silently ignored; revisit if the indexed cap
    ever gates real concurrent index builds (Task 14).

    D2: on a SUCCESSFUL commit only (a rolled-back 409 persisted nothing, so
    there is nothing stale to evict), invalidate the resolved-schema cache
    entry for this exact `(organization_id, target)` — every write path in
    this module funnels through here for exactly this reason: miss one and
    an admin defines/archives/purges a field and does not see the change,
    the worst kind of "it works on my machine" (see `core.schema.cache`).
    """
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            409, f"a field definition for key {key!r} on {target!r} already "
                 f"exists in this organization") from e
    await schema_cache.invalidate(cache, organization_id, target)


async def _assert_org_exists(session: AsyncSession, organization_id: str) -> None:
    """A definition's `organization_id` is a NOT NULL FK — the formal statement
    of tenant isolation. Creating one against an organisation that does not
    exist would either orphan the row (SQLite, no FK pragma) or blow up as an
    unhandled IntegrityError -> 500 (Postgres). Check explicitly, 404."""
    exists = (await session.execute(
        select(Organization.id).where(Organization.id == organization_id)
    )).scalar_one_or_none()
    if exists is None:
        raise HTTPException(404, f"organization '{organization_id}' not found")


def _apply_spec(row: FieldDefinition, body: FieldDefinitionIn) -> None:
    label, hint = body.label, body.hint or {}
    row.type = body.type
    row.widget = body.widget
    row.label_en, row.label_fr, row.label_es = label["en"], label["fr"], label["es"]
    row.hint_en = hint.get("en")
    row.hint_fr = hint.get("fr")
    row.hint_es = hint.get("es")
    row.required = body.required
    row.default = body.default
    row.rules = body.rules
    row.options = body.options
    row.relation_resource = body.relation_resource
    row.relation_filter = body.relation_filter
    row.group = body.group
    row.order = body.order
    row.col_span = body.col_span
    row.inherit_to_suborgs = body.inherit_to_suborgs


async def _run_index_build(db: Database, definition_id: str, target: str,
                          spec: dict, organization_id: str,
                          actor: str | None, cache: Cache | None = None) -> None:
    """The background job Task 14 promised: `CREATE INDEX CONCURRENTLY` cannot
    run inside the request's transaction, so this runs AFTER the response
    (via `BackgroundTasks`), on the app's own engine, in its own AUTOCOMMIT
    connection (`indexing.create_index`). It then opens a FRESH session (the
    request's session is long gone) to record the outcome.

    D2: the TERMINAL `index_state` (`ready`/`failed`, or SQLite's `none`) is
    part of the resolved schema payload (`FieldDefinition.as_spec()` carries
    `index_state`), so this transition must invalidate the resolved-schema
    cache exactly like every other write path in this module — otherwise a
    build that just went `pending` -> `ready` would keep reporting `pending`
    to every form that reads the cached entry until the TTL expires.

    Never swallows a failure: on ANY exception the reason is logged
    (`logger.exception`, full traceback) and `index_state` is set to
    `"failed"` — an operator can see it, never a silently stuck "pending".
    `indexing.create_index` now VERIFIES the built index is actually valid
    (`pg_index.indisvalid`) before returning normally, so `"failed"` also
    catches the case where `CREATE INDEX CONCURRENTLY` raised nothing but
    left an unusable index behind (`indexing.IndexBuildFailed`) — a retry
    that used to be reported `ready` on a genuinely broken index.

    Postgres-only by construction (`indexing.create_index` no-ops under any
    other dialect) — under SQLite (the test suite) this leaves `index_state`
    at `"none"`, NOT `"ready"`: a no-op must never be reported as success, or
    `sortable_keys()` would treat an unindexed column as safely sortable.

    Audits the TERMINAL outcome (`ready`/`failed`) — never `"none"`, which is
    the SQLite dialect no-op, not a real production state transition. A
    field silently losing (or gaining) sortability is exactly the kind of
    state change the repo rule "every sensitive mutation -> audit.record"
    is for.
    """
    terminal = "none" if db.engine.dialect.name != "postgresql" else "failed"
    try:
        await indexing.create_index(db.engine, target, spec, organization_id)
        terminal = "none" if db.engine.dialect.name != "postgresql" else "ready"
    except Exception:
        logger.exception(
            "index build failed for field definition %s (%s.%s, org %s)",
            definition_id, target, spec.get("key"), organization_id)
    async with db.session_factory() as session:
        row = await session.get(FieldDefinition, definition_id)
        if row is not None and row.index_state == "pending":
            row.index_state = terminal
            if terminal in ("ready", "failed"):
                action = (audit.FIELD_DEFINITION_INDEXED if terminal == "ready"
                         else audit.FIELD_DEFINITION_CHANGED)
                await audit.record(session, action, account_id=actor,
                                   detail={"id": definition_id, "target": target,
                                           "key": spec.get("key"),
                                           "organization_id": organization_id,
                                           "action": f"index_build_{terminal}"})
            await session.commit()
            await schema_cache.invalidate(cache, organization_id, target)


@router.post("/{definition_id}/index")
async def build_index(definition_id: str, background_tasks: BackgroundTasks,
                      request: Request,
                      principal: dict = Depends(require_auth),
                      session: AsyncSession = Depends(get_session)) -> dict:
    """Kick off a CONCURRENT partial expression index build for this
    definition. `indexed` must already be `True` (flip it via PUT first — the
    10-indexed cap check lives there, not here). Sets `index_state =
    "pending"` and commits BEFORE launching the build — the build itself runs
    in a background job on its own AUTOCOMMIT connection (see
    `_run_index_build`), never inside this request's transaction."""
    row = await _get_or_404(session, definition_id)
    await _authorize_target(session, principal, row.organization_id)
    enforce_if_match(request, row_etag(row))
    if not row.indexed:
        raise HTTPException(
            422, "field is not marked `indexed`; PUT `indexed: true` first "
                 "(the 10-indexed-per-target cap is enforced there)")
    if row.archived:
        raise HTTPException(422, "cannot build an index for an archived definition")
    if row.index_state == "pending":
        raise HTTPException(409, "an index build is already pending for this field")
    row.index_state = "pending"
    row.updated_by = principal.get("sub")
    await audit.record(session, audit.FIELD_DEFINITION_CHANGED,
                       account_id=principal.get("sub"),
                       detail={"id": definition_id, "target": row.target,
                               "key": row.key, "action": "index_build_requested"})
    cache = getattr(request.app.state, "cache", None)
    await _commit(session, key=row.key, target=row.target,
                 organization_id=row.organization_id, cache=cache)
    background_tasks.add_task(_run_index_build, request.app.state.db, definition_id,
                              row.target, row.as_spec(), row.organization_id,
                              principal.get("sub"), cache)
    return _public(row)


@router.get("/")
async def list_definitions(organization_id: str, target: str | None = None,
                           include_archived: bool = False,
                           principal: dict = Depends(require_auth),
                           session: AsyncSession = Depends(get_session)) -> dict:
    """The org's OWN definitions (ids included — `GET /api/v1/schema/{target}`
    returns `as_spec()`, which deliberately carries no `id`, so without this
    route the PUT/archive/purge endpoints below would be unaddressable and an
    ARCHIVED definition would be permanently unreachable, contradicting
    "archive is reversible"). Scope comes from `?organization_id=`, enforced
    IN-HANDLER by `_authorize_org` below, bound to that same query parameter
    — same confused-deputy reasoning as `_authorize_org`'s own docstring
    (MINORS fix, final fix wave: this used to claim a router-level
    `fields.manage` dependency reading `raw_scope_ids`, which does not exist
    on this router — see the module docstring above. A stale claim like that
    would talk a future reader back into the exact confused-deputy hole
    `_authorize_org` closes).

    Inherited (ancestor `inherit_to_suborgs`) definitions are NOT listed: this
    is the MANAGEMENT surface — you may only manage what you own. Use
    `GET /api/v1/schema/{target}` to see the resolved, inherited set.
    """
    await _authorize_org(session, principal, organization_id)
    stmt = select(FieldDefinition).where(
        FieldDefinition.organization_id == organization_id)
    if target is not None:
        stmt = stmt.where(FieldDefinition.target == target)
    if not include_archived:
        stmt = stmt.where(FieldDefinition.archived.is_(False))
    rows = (await session.execute(
        stmt.order_by(FieldDefinition.target, FieldDefinition.group,
                      FieldDefinition.order, FieldDefinition.key)
    )).scalars().all()
    return {"items": [_public(r) for r in rows], "count": len(rows)}


@router.get("/{definition_id}")
async def get_definition(definition_id: str,
                         principal: dict = Depends(require_auth),
                         session: AsyncSession = Depends(get_session)) -> dict:
    row = await _get_or_404(session, definition_id)
    await _authorize_target(session, principal, row.organization_id)
    return _public(row)


@router.post("/", status_code=201)
async def create_definition(organization_id: str, body: FieldDefinitionIn,
                            request: Request,
                            principal: dict = Depends(require_auth),
                            session: AsyncSession = Depends(get_session)) -> dict:
    await _authorize_org(session, principal, organization_id)
    await _assert_org_exists(session, organization_id)
    _guard_key_and_relation(body)
    await _check_field_cap(session, body.target, organization_id)
    if body.indexed:
        await _check_indexed_cap(session, body.target, organization_id)

    row = FieldDefinition(organization_id=organization_id, target=body.target,
                          key=body.key, indexed=body.indexed,
                          index_state="none")  # never client-controlled
    _apply_spec(row, body)
    actor = principal.get("sub")
    row.created_by = row.updated_by = actor
    session.add(row)
    # FLUSH BEFORE THE AUDIT — deliberately, and this order matters. `audit.record`
    # itself flushes, and it swallows every exception by design ("audit must never
    # break the auth flow"). If the new row's first flush happened INSIDE
    # `audit.record`, a `uq_field_definition_org_target_key` violation (a plain
    # duplicate key — the single most likely admin mistake) would be caught and
    # discarded there as a mere warning, leaving the transaction poisoned, and the
    # `commit()` below would then raise PendingRollbackError as an unhandled 500.
    # Flushing here means the IntegrityError surfaces to OUR handler, as a 409.
    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            409, f"a field definition for key {body.key!r} on {body.target!r} "
                 f"already exists in this organization") from e
    await audit.record(session, audit.FIELD_DEFINITION_CREATED, account_id=actor,
                       detail={"target": body.target, "key": body.key,
                               "organization_id": organization_id})
    await _commit(session, key=body.key, target=body.target,
                 organization_id=organization_id,
                 cache=getattr(request.app.state, "cache", None))
    return _public(row)


@router.put("/{definition_id}")
async def update_definition(definition_id: str, body: FieldDefinitionIn,
                            request: Request, background_tasks: BackgroundTasks,
                            principal: dict = Depends(require_auth),
                            session: AsyncSession = Depends(get_session)) -> dict:
    row = await _get_or_404(session, definition_id)
    await _authorize_target(session, principal, row.organization_id)
    enforce_if_match(request, row_etag(row))

    # `target`/`key` are immutable after creation: renaming either would
    # silently orphan every value already stored under the old key (the
    # frontend Studio — Task 15 — marks `key` non-editable client-side for the
    # same reason; the backend must not rely on that alone, per "backend
    # decides, frontend reflects"). Archive and create a new definition instead.
    if body.target != row.target or body.key != row.key:
        raise HTTPException(
            422, "target and key are immutable after creation; "
                 "archive this definition and create a new one instead")
    _guard_key_and_relation(body)

    # The 10-indexed cap only needs re-checking on a False -> True flip (target
    # is now immutable, so a move-to-a-different-target cap dodge is not
    # possible). `index_state` resets to "none" on either transition — the
    # actual index is (re)built by a later, explicit `/index` request.
    if body.indexed and not row.indexed:
        # ONLY the indexed cap — NOT the 50-field cap. Flipping an existing
        # field to `indexed` adds no field, so an org legitimately sitting AT
        # 50 must not be refused (and told "you already have 50 fields", which
        # would be an actively misleading error for an index request).
        await _check_indexed_cap(session, row.target, row.organization_id)

    # CRITICAL (Fix wave 1): `type` changing while `indexed` stays `True` is
    # JUST AS DANGEROUS as the `indexed` flip above, and `FieldSpec._coherent`
    # does NOT catch it — it only forbids `indexed=True` on a non-indexable
    # type, never a type DRIFT on an already-indexed field. A live Postgres
    # index carries `INDEX_CAST[row.type]` (the OLD type); `custom_sort_column`
    # would immediately start emitting `INDEX_CAST[body.type]` (the NEW type)
    # for this same key. Byte-for-byte mismatch -> Postgres silently stops
    # using the index for ORDER BY, while `sortable_keys()` still reports
    # `ready` -> a seq scan on millions of rows, reported as healthy. Treat it
    # exactly like the `indexed` flip: reset `index_state` to "none" (not
    # sortable again until an explicit re-`/index`) and drop any live index
    # object under the (immutable) key/target — `drop_index` is `IF EXISTS`,
    # a harmless no-op if nothing was ever actually built.
    #
    # `widget` changing does NOT trigger any of this: `widget` has no entry
    # in `INDEX_CAST` (it is presentation-only, per `types.py`'s "does it
    # change storage, comparison or indexing?" admission test) and cannot
    # desync the index expression from the ORDER BY expression.
    type_changed = body.type != row.type
    was_indexed = row.indexed
    if body.indexed != row.indexed or (row.indexed and type_changed):
        row.index_state = "none"
    row.indexed = body.indexed
    if type_changed and was_indexed:
        background_tasks.add_task(indexing.drop_index, request.app.state.db.engine,
                                  row.target, row.key, row.organization_id)

    _apply_spec(row, body)
    row.updated_by = principal.get("sub")
    await audit.record(session, audit.FIELD_DEFINITION_CHANGED,
                       account_id=principal.get("sub"),
                       detail={"id": definition_id, "target": row.target, "key": row.key})
    await _commit(session, key=row.key, target=row.target,
                 organization_id=row.organization_id,
                 cache=getattr(request.app.state, "cache", None))
    return _public(row)


async def _check_unarchive_caps(session: AsyncSession, row: FieldDefinition) -> None:
    """Un-archiving pushes `row` back into the counted-as-active set. Both
    caps are re-checked with ACTIVE-only counts (`count_for`'s default,
    archived excluded) — "does putting this row back on the form exceed the
    cap", independent of how the row came to be archived.

    TOTAL cap: in steady state this is structurally hard to hit — since
    `_check_field_cap` now counts archived rows too, an org's total row count
    can never exceed `MAX_FIELDS_PER_TARGET`, and active rows are a subset of
    total rows. It is kept anyway as defence-in-depth for any org whose total
    already exceeded the cap from BEFORE this fix shipped — which is exactly
    the state the pre-fix exploit (archive-then-create in a loop) could have
    left behind.

    INDEXED cap: this is the one an org can concretely still hit post-fix,
    precisely BECAUSE the indexed cap deliberately excludes archived rows
    (see the constants' docstring above): fill the 10-indexed cap, archive
    one indexed field (frees a slot for `count_for(indexed_only=True)`),
    create a replacement indexed field to refill to 10, then un-archive the
    first one — active-indexed count would go to 11 without this check.
    """
    active_total = await schema_repo.count_for(session, row.target, row.organization_id)
    if active_total >= MAX_FIELDS_PER_TARGET:
        raise HTTPException(
            422, f"organization already has {active_total} active field(s) on "
                 f"{row.target!r} (max {MAX_FIELDS_PER_TARGET}); purge archived "
                 "definitions to free capacity")
    if row.indexed:
        active_indexed = await schema_repo.count_for(
            session, row.target, row.organization_id, indexed_only=True)
        if active_indexed >= MAX_INDEXED_PER_TARGET:
            raise HTTPException(
                422, f"organization already has {active_indexed} indexed field(s) "
                     f"on {row.target!r} (max {MAX_INDEXED_PER_TARGET}); purge "
                     "archived indexed definitions or un-index another field "
                     "before restoring this one")


async def _set_archived(definition_id: str, request: Request, background_tasks: BackgroundTasks,
                        principal: dict, session: AsyncSession, *,
                        archived: bool, action: str) -> dict:
    row = await _get_or_404(session, definition_id)
    await _authorize_target(session, principal, row.organization_id)
    enforce_if_match(request, row_etag(row))
    if not archived and row.archived:
        await _check_unarchive_caps(session, row)
    row.archived = archived
    row.updated_by = principal.get("sub")
    # ARCHIVE DROPS THE INDEX (Task 14 lifecycle). The 10-indexed cap
    # (`MAX_INDEXED_PER_TARGET` above) deliberately EXCLUDES archived rows —
    # an archived field is not sortable, so it must not keep occupying a live
    # database index; otherwise an org could archive-and-recreate to
    # accumulate unbounded live Postgres indexes, the exact hole the cap
    # exists to close. `row.indexed` (not `index_state`) gates the drop: a
    # `pending`/`failed` build can leave a half-built/INVALID index object
    # under the same name, which `DROP INDEX CONCURRENTLY IF EXISTS` cleans
    # up too. `index_state` resets to "none" so the whitelist (`indexing.
    # sortable_keys`) immediately stops offering the field for sorting.
    #
    # UNARCHIVE deliberately does NOT auto-rebuild: the field comes back with
    # `index_state == "none"` (not sortable — the whitelist already enforces
    # that) until the admin explicitly re-requests `/index`. Simpler and more
    # honest than a silent background rebuild the admin never asked for;
    # `_check_unarchive_caps` above already re-validates the INDEXED cap
    # before allowing the field back onto the active form.
    if archived and row.indexed:
        row.index_state = "none"
        background_tasks.add_task(indexing.drop_index, request.app.state.db.engine,
                                  row.target, row.key, row.organization_id)
    await audit.record(session, action, account_id=principal.get("sub"),
                       detail={"id": definition_id, "target": row.target,
                               "key": row.key})
    await _commit(session, key=row.key, target=row.target,
                 organization_id=row.organization_id,
                 cache=getattr(request.app.state, "cache", None))
    return _public(row)


@router.post("/{definition_id}/archive")
async def archive_definition(definition_id: str, request: Request,
                             background_tasks: BackgroundTasks,
                             principal: dict = Depends(require_auth),
                             session: AsyncSession = Depends(get_session)) -> dict:
    """`archived = True` only. NEVER touches the entity rows' `custom_fields`
    JSONB — the field leaves the form, the VALUES STAY PUT (spec §3 principle
    7: "rien n'est détruit"). Reversible via `/unarchive` below. Also drops
    the field's live index, if any — see `_set_archived`'s comment."""
    return await _set_archived(definition_id, request, background_tasks, principal,
                               session, archived=True, action=audit.FIELD_DEFINITION_ARCHIVED)


@router.post("/{definition_id}/unarchive")
async def unarchive_definition(definition_id: str, request: Request,
                               background_tasks: BackgroundTasks,
                               principal: dict = Depends(require_auth),
                               session: AsyncSession = Depends(get_session)) -> dict:
    """Puts an archived field back on the form. This is what makes archive
    genuinely REVERSIBLE (the spec's word) rather than a one-way door: the
    values never left the JSONB, so restoring the definition restores the
    field intact. Without this route, `archived` would be a trapdoor — and
    since `GET /schema` filters archived rows out, the field would be
    unreachable forever. Does NOT rebuild the index — see `_set_archived`'s
    comment; the field is `indexed` again but not yet sortable until an
    explicit `POST /{id}/index`."""
    return await _set_archived(definition_id, request, background_tasks, principal,
                               session, archived=False, action=audit.FIELD_DEFINITION_CHANGED)


@router.post("/{definition_id}/purge")
async def purge_definition(definition_id: str, request: Request,
                           background_tasks: BackgroundTasks,
                           principal: dict = Depends(require_auth),
                           session: AsyncSession = Depends(get_session)) -> dict:
    """Definitive deletion of the DEFINITION row — explicit, audited, `If-Match`
    guarded, and a SEPARATE action from archive (one click on "archive" must
    never destroy anything). Still does not touch any entity's stored
    `custom_fields` VALUES; a purge only stops the key from being offered and
    validated going forward — it does not scrub historic data (consistent with
    `merge_blob` preserving undeclared keys forever). Also drops the field's
    live index, if any — a purged definition cannot be un-purged, so a
    leftover index would be a permanent, unrecoverable leak (see `_set_archived`)."""
    row = await _get_or_404(session, definition_id)
    await _authorize_target(session, principal, row.organization_id)
    enforce_if_match(request, row_etag(row))
    detail = {"id": definition_id, "target": row.target, "key": row.key,
              "organization_id": row.organization_id}
    had_index = row.indexed
    target, key, organization_id = row.target, row.key, row.organization_id
    await session.delete(row)
    await audit.record(session, audit.FIELD_DEFINITION_PURGED,
                       account_id=principal.get("sub"), detail=detail)
    await _commit(session, key=key, target=target, organization_id=organization_id,
                 cache=getattr(request.app.state, "cache", None))
    if had_index:
        background_tasks.add_task(indexing.drop_index, request.app.state.db.engine,
                                  target, key, organization_id)
    return {"deleted": definition_id}
