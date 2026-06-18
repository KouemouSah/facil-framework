"""Data access for the reference module (Currency / Country / CountryRegion).

Each `*_select` returns an already filtered, UNSORTED select — the caller applies
the whitelisted sort + keyset pagination via app.api.list_query.keyset_page.
"""

from __future__ import annotations

from sqlalchemy import Select, or_, select

from app.modules.reference.models import Country, CountryRegion, Currency


def currencies_select(*, q: str | None = None, active: bool | None = None) -> Select:
    stmt = select(Currency)
    if active is not None:
        stmt = stmt.where(Currency.is_active.is_(active))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Currency.code.ilike(like), Currency.name.ilike(like)))
    return stmt


def countries_select(*, q: str | None = None, active: bool | None = None) -> Select:
    stmt = select(Country)
    if active is not None:
        stmt = stmt.where(Country.is_active.is_(active))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Country.code.ilike(like), Country.name.ilike(like),
            Country.alpha3.ilike(like)))
    return stmt


def regions_select(*, country_id: str | None = None, q: str | None = None,
                   active: bool | None = None) -> Select:
    stmt = select(CountryRegion)
    if country_id is not None:
        stmt = stmt.where(CountryRegion.country_id == country_id)
    if active is not None:
        stmt = stmt.where(CountryRegion.is_active.is_(active))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            CountryRegion.code.ilike(like), CountryRegion.name.ilike(like)))
    return stmt
