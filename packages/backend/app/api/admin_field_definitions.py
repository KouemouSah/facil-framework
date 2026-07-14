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

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.concurrency import enforce_if_match, row_etag
from app.api.deps import get_session
from app.auth import audit
from app.core.schema import repository as schema_repo
from app.core.schema.registry import EXTENSIBLE_TARGETS
from app.core.schema.reserved import assert_key_allowed, assert_relation_resource_allowed
from app.core.schema.sanitize import assert_not_secretish
from app.core.schema.spec import FieldSpec
from app.core.schema.types import DEFAULT_WIDGET
from app.models.field_definition import FieldDefinition
from app.modules.organization.models import Organization
from app.rbac.scope import Scope
from app.security.auth_dep import require_auth
from app.security.permission_dep import enforce, visible_orgs

# Per (organization_id, target) — an org cannot saturate the database for every
# other tenant, and an unbounded set of `indexed` fields cannot force unbounded
# concurrent index builds. Counted OWN definitions only (`repository.count_for`):
# a child org is never penalised for what its parent already defined.
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
    because the org is legitimately AT its limit."""
    total = await schema_repo.count_for(session, target, organization_id)
    if total >= MAX_FIELDS_PER_TARGET:
        raise HTTPException(
            422, f"organization already has {total} field(s) on {target!r} "
                 f"(max {MAX_FIELDS_PER_TARGET})")


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


async def _commit(session: AsyncSession, *, key: str, target: str) -> None:
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
    """
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            409, f"a field definition for key {key!r} on {target!r} already "
                 f"exists in this organization") from e


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


@router.get("/")
async def list_definitions(organization_id: str, target: str | None = None,
                           include_archived: bool = False,
                           principal: dict = Depends(require_auth),
                           session: AsyncSession = Depends(get_session)) -> dict:
    """The org's OWN definitions (ids included — `GET /api/v1/schema/{target}`
    returns `as_spec()`, which deliberately carries no `id`, so without this
    route the PUT/archive/purge endpoints below would be unaddressable and an
    ARCHIVED definition would be permanently unreachable, contradicting
    "archive is reversible"). Scope comes from `?organization_id=`, enforced by
    the router-level `fields.manage` dependency (`raw_scope_ids` reads it).

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
    await _commit(session, key=body.key, target=body.target)
    return _public(row)


@router.put("/{definition_id}")
async def update_definition(definition_id: str, body: FieldDefinitionIn,
                            request: Request,
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
    if body.indexed != row.indexed:
        row.indexed = body.indexed
        row.index_state = "none"

    _apply_spec(row, body)
    row.updated_by = principal.get("sub")
    await audit.record(session, audit.FIELD_DEFINITION_CHANGED,
                       account_id=principal.get("sub"),
                       detail={"id": definition_id, "target": row.target, "key": row.key})
    await _commit(session, key=row.key, target=row.target)
    return _public(row)


async def _set_archived(definition_id: str, request: Request, principal: dict,
                        session: AsyncSession, *, archived: bool, action: str) -> dict:
    row = await _get_or_404(session, definition_id)
    await _authorize_target(session, principal, row.organization_id)
    enforce_if_match(request, row_etag(row))
    row.archived = archived
    row.updated_by = principal.get("sub")
    await audit.record(session, action, account_id=principal.get("sub"),
                       detail={"id": definition_id, "target": row.target,
                               "key": row.key})
    await _commit(session, key=row.key, target=row.target)
    return _public(row)


@router.post("/{definition_id}/archive")
async def archive_definition(definition_id: str, request: Request,
                             principal: dict = Depends(require_auth),
                             session: AsyncSession = Depends(get_session)) -> dict:
    """`archived = True` only. NEVER touches the entity rows' `custom_fields`
    JSONB — the field leaves the form, the VALUES STAY PUT (spec §3 principle
    7: "rien n'est détruit"). Reversible via `/unarchive` below."""
    return await _set_archived(definition_id, request, principal, session,
                               archived=True, action=audit.FIELD_DEFINITION_ARCHIVED)


@router.post("/{definition_id}/unarchive")
async def unarchive_definition(definition_id: str, request: Request,
                               principal: dict = Depends(require_auth),
                               session: AsyncSession = Depends(get_session)) -> dict:
    """Puts an archived field back on the form. This is what makes archive
    genuinely REVERSIBLE (the spec's word) rather than a one-way door: the
    values never left the JSONB, so restoring the definition restores the
    field intact. Without this route, `archived` would be a trapdoor — and
    since `GET /schema` filters archived rows out, the field would be
    unreachable forever."""
    return await _set_archived(definition_id, request, principal, session,
                               archived=False, action=audit.FIELD_DEFINITION_CHANGED)


@router.post("/{definition_id}/purge")
async def purge_definition(definition_id: str, request: Request,
                           principal: dict = Depends(require_auth),
                           session: AsyncSession = Depends(get_session)) -> dict:
    """Definitive deletion of the DEFINITION row — explicit, audited, `If-Match`
    guarded, and a SEPARATE action from archive (one click on "archive" must
    never destroy anything). Still does not touch any entity's stored
    `custom_fields` VALUES; a purge only stops the key from being offered and
    validated going forward — it does not scrub historic data (consistent with
    `merge_blob` preserving undeclared keys forever)."""
    row = await _get_or_404(session, definition_id)
    await _authorize_target(session, principal, row.organization_id)
    enforce_if_match(request, row_etag(row))
    detail = {"id": definition_id, "target": row.target, "key": row.key,
              "organization_id": row.organization_id}
    await session.delete(row)
    await audit.record(session, audit.FIELD_DEFINITION_PURGED,
                       account_id=principal.get("sub"), detail=detail)
    await _commit(session, key=row.key, target=row.target)
    return {"deleted": definition_id}
