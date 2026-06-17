"""Unit tests for the list-query helpers (Lot 1 / L1.0 + scale keyset).

Self-contained: a tiny throwaway model + in-memory SQLite, so the contract
(clamp / whitelist-sort / total + offset pagination, and keyset cursor +
capped count) is tested in isolation.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import DateTime, String, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.api.list_query import (MAX_LIMIT, apply_sort, clamp_page,
                                decode_cursor, encode_cursor, keyset_page,
                                paginated, resolve_sort)


class _Base(DeclarativeBase):
    pass


class Widget(_Base):
    __tablename__ = "widget"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=True)


_ALLOWED = {"id": Widget.id, "name": Widget.name, "ts": Widget.ts}
_T0 = datetime(2026, 1, 1, 12, 0, 0)


@pytest_asyncio.fixture
async def sess():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        # names [c, a, b, a] -> asc(name, id) order is ids [2, 4, 3, 1]
        for i, n in enumerate(["c", "a", "b", "a"]):
            s.add(Widget(id=i + 1, name=n, ts=_T0 + timedelta(minutes=i)))
        await s.commit()
        yield s
    await engine.dispose()


# --- existing offset helpers ---------------------------------------------

def test_clamp_page():
    assert clamp_page(50, 0) == (50, 0)
    assert clamp_page(9999, -5) == (MAX_LIMIT, 0)
    assert clamp_page(0, 10) == (1, 10)


def test_resolve_sort_parses_direction_and_422():
    assert resolve_sort("name", allowed=_ALLOWED, default="id") == (Widget.name, False)
    assert resolve_sort("-name", allowed=_ALLOWED, default="id") == (Widget.name, True)
    assert resolve_sort("", allowed=_ALLOWED, default="-id") == (Widget.id, True)
    with pytest.raises(HTTPException) as e:
        resolve_sort("bogus", allowed=_ALLOWED, default="id")
    assert e.value.status_code == 422


@pytest.mark.asyncio
async def test_paginated_total_and_order(sess):
    stmt = apply_sort(select(Widget), "name", allowed=_ALLOWED, default="id")
    items, total = await paginated(sess, stmt, limit=2, offset=0)
    assert total == 4
    assert [w.name for w in items] == ["a", "a"]


@pytest.mark.asyncio
async def test_paginated_desc_with_offset(sess):
    stmt = apply_sort(select(Widget), "-name", allowed=_ALLOWED, default="id")
    items, total = await paginated(sess, stmt, limit=2, offset=1)
    assert total == 4
    assert [w.name for w in items] == ["b", "a"]


# --- keyset cursor + capped count ----------------------------------------

def test_cursor_roundtrip_and_bad_token():
    assert decode_cursor(encode_cursor("a", "id-2")) == ("a", "id-2")
    with pytest.raises(HTTPException) as e:
        decode_cursor("!!!not-base64!!!")
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_keyset_pages_through_with_tiebreaker(sess):
    # Page by 1 over asc(name, id); duplicate "a" must not skip/duplicate.
    seen, cursor, guard = [], None, 0
    while guard < 10:
        guard += 1
        items, cursor, count, capped = await keyset_page(
            sess, select(Widget), sort_col=Widget.name, sort_desc=False,
            cursor=cursor, limit=1)
        assert count == 4 and capped is False  # capped count, full set
        seen.extend(w.id for w in items)
        if cursor is None:
            break
    assert seen == [2, 4, 3, 1]  # stable order, no dup/skip across the two "a"s


@pytest.mark.asyncio
async def test_keyset_last_page_has_no_cursor(sess):
    items, cursor, _, _ = await keyset_page(
        sess, select(Widget), sort_col=Widget.name, sort_desc=False,
        cursor=None, limit=10)
    assert [w.id for w in items] == [2, 4, 3, 1]
    assert cursor is None  # everything fit -> no next page


@pytest.mark.asyncio
async def test_keyset_capped_count(sess):
    _, _, count, capped = await keyset_page(
        sess, select(Widget), sort_col=Widget.name, sort_desc=False,
        cursor=None, limit=2, count_cap=2)
    assert count == 2 and capped is True   # 4 rows > cap 2 -> "2+"


@pytest.mark.asyncio
async def test_keyset_datetime_cursor_coercion(sess):
    # Sort by ts desc; the cursor round-trips a datetime (ISO <-> DateTime col)
    # without mis-comparing on SQLite. ts asc = ids [1,2,3,4] -> desc [4,3,2,1].
    p1, cursor, _, _ = await keyset_page(
        sess, select(Widget), sort_col=Widget.ts, sort_desc=True,
        cursor=None, limit=2)
    assert [w.id for w in p1] == [4, 3]
    assert cursor is not None
    p2, cursor2, _, _ = await keyset_page(
        sess, select(Widget), sort_col=Widget.ts, sort_desc=True,
        cursor=cursor, limit=2)
    assert [w.id for w in p2] == [2, 1]
    assert cursor2 is None
