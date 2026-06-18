"""Seed reference master data from the COMPLETE ISO datasets (dynamic, not hardcoded).

Source = `pycountry` (maintained ISO 3166-1 / 3166-2 / 4217): ~249 countries,
~178 currencies, ~5000 subdivisions — so a fresh deployment is fully populated by
default, no curated/hardcoded list.

Strategy:
- "seed if empty" per table (bulk insert) so boot stays fast — reference data is
  stable, we don't re-upsert thousands of rows on every restart;
- `force=True` (admin reseed) re-syncs by upsert (code business key), e.g. after a
  pycountry bump.

Cities are deliberately NOT seeded: they are not ISO reference data (millions of
them); city stays validated free text (optional GeoNames import is a later, opt-in
feature), the SAP/Odoo convention.
"""

from __future__ import annotations

import pycountry
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reference.models import Country, CountryRegion, Currency


async def _count(session: AsyncSession, model) -> int:
    return await session.scalar(select(func.count()).select_from(model)) or 0


def _currency_rows() -> list[dict]:
    # ISO 4217 has no symbol/decimal-places; default 2 dp, symbol null (editable).
    return [{"code": c.alpha_3, "name": c.name[:80]} for c in pycountry.currencies]


def _country_rows() -> list[dict]:
    return [{
        "code": c.alpha_2, "alpha3": getattr(c, "alpha_3", None),
        "numeric_code": getattr(c, "numeric", None), "name": c.name[:120],
    } for c in pycountry.countries]


async def _seed_flat(session: AsyncSession, model, rows: list[dict], force: bool) -> int:
    """Bulk-insert when empty; upsert by `code` when force. Skip if populated."""
    existing = await _count(session, model)
    if existing and not force:
        return existing
    if not force:
        session.add_all(model(**r) for r in rows)
        return len(rows)
    have = {r.code: r for r in (await session.scalars(select(model))).all()}
    for data in rows:
        row = have.get(data["code"])
        if row:
            for k, v in data.items():
                setattr(row, k, v)
        else:
            session.add(model(**data))
    return len(rows)


async def _seed_regions(session: AsyncSession, code_to_id: dict[str, str], force: bool) -> int:
    existing = await _count(session, CountryRegion)
    if existing and not force:
        return existing
    rows = []
    for s in pycountry.subdivisions:
        cid = code_to_id.get(s.country_code)
        if cid is None:
            continue
        rtype = getattr(s, "type", None)
        rows.append({"country_id": cid, "code": s.code[:10], "name": s.name[:120],
                     "region_type": rtype[:40] if rtype else None})
    if not force:
        session.add_all(CountryRegion(**r) for r in rows)
        return len(rows)
    have = {(r.country_id, r.code): r
            for r in (await session.scalars(select(CountryRegion))).all()}
    for data in rows:
        row = have.get((data["country_id"], data["code"]))
        if row:
            for k, v in data.items():
                setattr(row, k, v)
        else:
            session.add(CountryRegion(**data))
    return len(rows)


async def seed_reference(session: AsyncSession, *, force: bool = False) -> dict:
    """Populate currencies/countries/regions from the full ISO datasets. Idempotent:
    seeds only-if-empty by default; `force` re-syncs. Commits once."""
    n_cur = await _seed_flat(session, Currency, _currency_rows(), force)
    n_country = await _seed_flat(session, Country, _country_rows(), force)
    await session.flush()  # country ids needed to resolve regions' country_id
    code_to_id = {c.code: c.id for c in (await session.scalars(select(Country))).all()}
    n_region = await _seed_regions(session, code_to_id, force)
    await session.commit()
    return {"currencies": n_cur, "countries": n_country, "regions": n_region}
