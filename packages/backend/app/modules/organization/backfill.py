"""Backfill the legacy organization text fields into the party + address pillar (F.3).

For each Company (organization) not yet linked to a Party, create:
- a Party (its legal identity in the directory) from legal_name/tax_id/contact;
- an Address from the org's address text, resolving country/currency to the
  reference master data BY CODE (best-effort — unmapped codes are reported, never
  silently dropped, per the engineering standard);
and link org.party_id / hq_address_id / currency_id.

Idempotent: only orgs with `party_id IS NULL` are processed, so it is safe at
every boot (after the reference seed) and re-runnable. Region text is left
unresolved (free-text region had no structured value); set it via the UI later.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.organization.models import Organization
from app.modules.party.models import Address, Party
from app.modules.reference.models import Country, Currency


async def backfill_org_party(session: AsyncSession) -> dict:
    orgs = list((await session.scalars(
        select(Organization).where(Organization.party_id.is_(None)))).all())
    if not orgs:
        return {"backfilled": 0, "unmapped_country": [], "unmapped_currency": []}

    countries = {c.code: c.id for c in (await session.scalars(select(Country))).all()}
    currencies = {c.code: c.id for c in (await session.scalars(select(Currency))).all()}
    unmapped_country: set[str] = set()
    unmapped_currency: set[str] = set()
    backfilled = 0

    for org in orgs:
        party = Party(
            party_type="organization",
            name=org.legal_name or org.display_name or org.code,
            tax_id=org.tax_id, registration_number=org.registration_number,
            email=org.email, phone=org.phone, website=org.website)
        session.add(party)

        country_id = None
        if org.country_code:
            country_id = countries.get(org.country_code.upper())
            if country_id is None:
                unmapped_country.add(org.country_code)
        address = Address(
            line1=org.address_line1, line2=org.address_line2, city=org.city,
            postal_code=org.postal_code, country_id=country_id)
        session.add(address)
        await session.flush()  # need party/address ids

        org.party_id = party.id
        org.hq_address_id = address.id
        if org.currency:
            cur_id = currencies.get(org.currency.upper())
            if cur_id is not None:
                org.currency_id = cur_id
            else:
                unmapped_currency.add(org.currency)
        backfilled += 1

    await session.commit()
    return {"backfilled": backfilled,
            "unmapped_country": sorted(unmapped_country),
            "unmapped_currency": sorted(unmapped_currency)}
