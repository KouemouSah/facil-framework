"""Unit tests for the list-query helpers (Lot 1 / L1.0).

Self-contained: a tiny throwaway model + in-memory SQLite, so the contract
(clamp / whitelist-sort / total + pagination) is tested in isolation.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.api.list_query import MAX_LIMIT, apply_sort, clamp_page, paginated


class _Base(DeclarativeBase):
    pass


class Widget(_Base):
    __tablename__ = "widget"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


_ALLOWED = {"id": Widget.id, "name": Widget.name}


@pytest_asyncio.fixture
async def sess():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        for i, n in enumerate(["c", "a", "b", "a"]):
            s.add(Widget(id=i + 1, name=n))
        await s.commit()
        yield s
    await engine.dispose()


def test_clamp_page():
    assert clamp_page(50, 0) == (50, 0)
    assert clamp_page(9999, -5) == (MAX_LIMIT, 0)  # over-cap + negative offset
    assert clamp_page(0, 10) == (1, 10)             # under-floor limit


def test_apply_sort_unknown_field_422():
    with pytest.raises(HTTPException) as e:
        apply_sort(select(Widget), "bogus", allowed=_ALLOWED, default="id")
    assert e.value.status_code == 422


@pytest.mark.asyncio
async def test_paginated_total_and_order(sess):
    # names = [c, a, b, a]; asc -> [a, a, b, c]
    stmt = apply_sort(select(Widget), "name", allowed=_ALLOWED, default="id")
    items, total = await paginated(sess, stmt, limit=2, offset=0)
    assert total == 4                       # total ignores limit/offset
    assert [w.name for w in items] == ["a", "a"]


@pytest.mark.asyncio
async def test_paginated_desc_with_offset(sess):
    # desc -> [c, b, a, a]; offset 1 limit 2 -> [b, a]
    stmt = apply_sort(select(Widget), "-name", allowed=_ALLOWED, default="id")
    items, total = await paginated(sess, stmt, limit=2, offset=1)
    assert total == 4
    assert [w.name for w in items] == ["b", "a"]


@pytest.mark.asyncio
async def test_default_sort_used_when_empty(sess):
    stmt = apply_sort(select(Widget), None, allowed=_ALLOWED, default="-id")
    items, _ = await paginated(sess, stmt, limit=10, offset=0)
    assert [w.id for w in items] == [4, 3, 2, 1]
