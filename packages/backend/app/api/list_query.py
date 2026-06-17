"""Reusable server-side list contract helpers (Lot 1 — DataGrid).

See `docs/ENGINEERING_STANDARDS.md` §1. An endpoint builds a base SELECT that is
already filtered and RBAC-scoped, applies a **whitelisted** sort, then returns
`(items, total)` so the route can answer `{items, total, limit, offset}`.

Why a whitelist for sort: it is the only safe way to expose ordering — an
arbitrary client-supplied column is an injection/abuse vector, so an unknown
field is a 422, never a silent fallback.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def clamp_page(limit: int, offset: int) -> tuple[int, int]:
    """Bound a page request: limit in [1, MAX_LIMIT], offset >= 0. Idempotent."""
    return min(max(limit, 1), MAX_LIMIT), max(offset, 0)


def apply_sort(stmt: Select, sort: str | None, *,
               allowed: dict[str, Any], default: str) -> Select:
    """Apply `sort` (`field` asc / `-field` desc) to `stmt`.

    `allowed` maps a public field name -> ORM column. A field outside the
    whitelist raises 422 (no arbitrary ordering). `default` is used when `sort`
    is empty and MUST itself be a whitelisted spec.
    """
    spec = (sort or default).strip()
    descending = spec.startswith("-")
    field = spec[1:] if descending else spec
    col = allowed.get(field)
    if col is None:
        raise HTTPException(
            422, f"cannot sort by '{field}'; allowed: {sorted(allowed)}")
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
