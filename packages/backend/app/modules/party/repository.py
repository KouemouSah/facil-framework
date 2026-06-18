"""Data access for the party module (Party / Address). Each `*_select` returns a
filtered, UNSORTED select for app.api.list_query.keyset_page."""

from __future__ import annotations

from sqlalchemy import Select, or_, select

from app.modules.party.models import Address, Party


def parties_select(*, q: str | None = None, party_type: str | None = None,
                   active: bool | None = None) -> Select:
    stmt = select(Party)
    if party_type:
        stmt = stmt.where(Party.party_type == party_type)
    if active is not None:
        stmt = stmt.where(Party.is_active.is_(active))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Party.name.ilike(like), Party.tax_id.ilike(like), Party.email.ilike(like)))
    return stmt


def addresses_select(*, q: str | None = None, country_id: str | None = None,
                     active: bool | None = None) -> Select:
    stmt = select(Address)
    if country_id:
        stmt = stmt.where(Address.country_id == country_id)
    if active is not None:
        stmt = stmt.where(Address.is_active.is_(active))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Address.label.ilike(like), Address.city.ilike(like), Address.line1.ilike(like)))
    return stmt
