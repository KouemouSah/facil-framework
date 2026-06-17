"""Reusable server-side list contract helpers (Lot 1 — DataGrid).

See `docs/ENGINEERING_STANDARDS.md` §1. An endpoint builds a base SELECT that is
already filtered and RBAC-scoped, applies a **whitelisted** sort, then returns
`(items, total)` so the route can answer `{items, total, limit, offset}`.

Why a whitelist for sort: it is the only safe way to expose ordering — an
arbitrary client-supplied column is an injection/abuse vector, so an unknown
field is a 422, never a silent fallback.
"""

from __future__ import annotations

import base64
import json
from datetime import date, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
# Capped count: list endpoints count at most COUNT_CAP rows then report "N+"
# (see keyset_page). Bounds the per-request cost at 1M+ — no full COUNT(*) scan.
COUNT_CAP = 1000


def clamp_page(limit: int, offset: int) -> tuple[int, int]:
    """Bound a page request: limit in [1, MAX_LIMIT], offset >= 0. Idempotent."""
    return min(max(limit, 1), MAX_LIMIT), max(offset, 0)


def resolve_sort(sort: str | None, *,
                 allowed: dict[str, Any], default: str) -> tuple[Any, bool]:
    """Parse a sort spec (`field` asc / `-field` desc) into `(column, descending)`.

    `allowed` maps a public field name -> ORM column; an unknown field is a 422
    (no arbitrary ordering — injection/abuse vector). `default` is used when
    `sort` is empty and MUST itself be a whitelisted spec. Shared by `apply_sort`
    (offset lists) and `keyset_page` (cursor lists)."""
    spec = (sort or default).strip()
    descending = spec.startswith("-")
    field = spec[1:] if descending else spec
    col = allowed.get(field)
    if col is None:
        raise HTTPException(
            422, f"cannot sort by '{field}'; allowed: {sorted(allowed)}")
    return col, descending


def apply_sort(stmt: Select, sort: str | None, *,
               allowed: dict[str, Any], default: str) -> Select:
    """Apply a whitelisted `sort` to `stmt` (offset pagination path)."""
    col, descending = resolve_sort(sort, allowed=allowed, default=default)
    return stmt.order_by(col.desc() if descending else col.asc())


async def paginated(session: AsyncSession, base_stmt: Select, *,
                    limit: int, offset: int) -> tuple[list, int]:
    """Return `(items, total)` for an already filtered/scoped/sorted SELECT.

    `total` counts the same filtered/scoped set (ordering stripped, before
    limit/offset). Caller is expected to have clamped limit/offset already
    (use `clamp_page`)."""
    total = await session.scalar(
        select(func.count()).select_from(base_stmt.order_by(None).subquery())) or 0
    items = list((await session.scalars(base_stmt.limit(limit).offset(offset))).all())
    return items, total


# --- Keyset (cursor) pagination + capped count (scale 1M+) ----------------

def _encode_value(value: Any) -> Any:
    """Make a sort value JSON-safe for the cursor (datetimes -> ISO string)."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _coerce_value(sort_col: Any, raw: Any) -> Any:
    """Coerce a decoded cursor value back to the column's Python type, so the
    DB binds a typed parameter (a raw ISO string would mis-compare against a
    DateTime column on SQLite). String/int/bool pass through unchanged."""
    if raw is None:
        return None
    try:
        pytype = sort_col.type.python_type
    except (NotImplementedError, AttributeError):
        return raw
    if pytype is datetime:
        return datetime.fromisoformat(raw)
    if pytype is date:
        return date.fromisoformat(raw)
    return raw


def encode_cursor(value: Any, row_id: str) -> str:
    """Opaque forward cursor = base64url(JSON{v: <sort value>, id: <row id>})."""
    raw = json.dumps({"v": _encode_value(value), "id": row_id},
                     separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode()


def decode_cursor(token: str) -> tuple[Any, str]:
    """Inverse of `encode_cursor`. A malformed token is a 400 (client error)."""
    try:
        data = json.loads(base64.urlsafe_b64decode(token.encode()))
        return data["v"], data["id"]
    except Exception as exc:  # noqa: BLE001 — any decode failure = bad cursor
        raise HTTPException(400, "invalid cursor") from exc


async def keyset_page(session: AsyncSession, base_stmt: Select, *,
                      sort_col: Any, sort_desc: bool, cursor: str | None,
                      limit: int, count_cap: int = COUNT_CAP
                      ) -> tuple[list, str | None, int, bool]:
    """Keyset (cursor) page over an already filtered/scoped SELECT.

    Returns `(items, next_cursor, count, capped)`:
      - forward-only; `next_cursor` is None on the last page (caller's front-end
        keeps a stack of cursors for "previous").
      - stable total order via the `id` tiebreaker. NULL-safe: a nullable sort
        column orders NULLs last (ASC) / first (DESC), and the cursor predicate
        branches on whether the boundary value is NULL — so NULL rows are never
        skipped (a naive `col > v` would drop them on later pages).
      - `count` is the filtered total capped at `count_cap`; `capped` is True when
        the real total exceeds it (front-end shows e.g. "1000+"). No full COUNT.

    The total order is made explicit (`NULLS LAST`/`NULLS FIRST`) because SQLite
    (tests) and Postgres (prod) disagree on the default NULL placement — without
    it a cursor computed on one dialect would mis-page on the other.

    The cursor encodes the sort value + id of the last row; it is only valid for
    the current sort — the caller MUST reset it when sort/filters change.
    """
    limit = min(max(limit, 1), MAX_LIMIT)
    id_col = sort_col.class_.id

    stmt = base_stmt
    if cursor:
        v_raw, last_id = decode_cursor(cursor)
        v = _coerce_value(sort_col, v_raw)
        if v is None:
            # Boundary sits in the NULL block.
            if sort_desc:  # NULLS FIRST: remaining NULLs (id<cid), then all non-null
                stmt = stmt.where(or_(and_(sort_col.is_(None), id_col < last_id),
                                      sort_col.is_not(None)))
            else:          # NULLS LAST: NULLs are last -> only remaining NULLs
                stmt = stmt.where(and_(sort_col.is_(None), id_col > last_id))
        elif sort_desc:    # non-null block; NULLs were first and already passed
            stmt = stmt.where(or_(sort_col < v, and_(sort_col == v, id_col < last_id)))
        else:              # greater non-null, ties, then all NULLs (which come last)
            stmt = stmt.where(or_(sort_col > v, and_(sort_col == v, id_col > last_id),
                                  sort_col.is_(None)))

    order = ([sort_col.desc().nulls_first(), id_col.desc()] if sort_desc
             else [sort_col.asc().nulls_last(), id_col.asc()])
    stmt = stmt.order_by(None).order_by(*order).limit(limit + 1)
    rows = list((await session.scalars(stmt)).all())

    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_cursor(getattr(last, sort_col.key), last.id)

    # Capped count over the filtered set (no keyset predicate, no order).
    counted = await session.scalar(select(func.count()).select_from(
        base_stmt.order_by(None).limit(count_cap + 1).subquery())) or 0
    return items, next_cursor, min(counted, count_cap), counted > count_cap
