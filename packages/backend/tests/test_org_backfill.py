"""Unit test for the F.3 org -> party/address backfill (self-contained SQLite)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.modules.organization.backfill import backfill_org_party
from app.modules.organization.models import Organization
from app.modules.party.models import Address, Party
from app.modules.reference.models import Country, CountryRegion, Currency


@pytest_asyncio.fixture
async def sess():
    engine = create_async_engine("sqlite+aiosqlite://")
    tables = [m.__table__ for m in
              (Country, Currency, CountryRegion, Party, Address, Organization)]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_backfill_links_org_to_party_address(sess):
    gq = Country(code="GQ", name="Equatorial Guinea")
    xaf = Currency(code="XAF", name="CFA Franc")
    sess.add_all([gq, xaf])
    await sess.flush()
    sess.add_all([
        Organization(code="acme", legal_name="Acme SA", tax_id="T-1",
                     country_code="GQ", currency="XAF", city="Malabo"),
        Organization(code="zz", legal_name="Z", country_code="ZZ", currency="ZZZ"),
    ])
    await sess.commit()

    r = await backfill_org_party(sess)
    assert r["backfilled"] == 2
    # Unmapped codes are reported, never silently dropped.
    assert r["unmapped_country"] == ["ZZ"] and r["unmapped_currency"] == ["ZZZ"]

    org = (await sess.scalars(
        select(Organization).where(Organization.code == "acme"))).one()
    assert org.party_id and org.hq_address_id and org.currency_id == xaf.id
    party = await sess.get(Party, org.party_id)
    assert party.name == "Acme SA" and party.tax_id == "T-1"
    assert party.party_type == "organization"
    addr = await sess.get(Address, org.hq_address_id)
    assert addr.country_id == gq.id and addr.city == "Malabo"

    # Idempotent: a second run links nothing new.
    assert (await backfill_org_party(sess))["backfilled"] == 0
