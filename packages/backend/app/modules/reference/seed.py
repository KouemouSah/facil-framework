"""Idempotent seed of reference master data (currencies / countries / regions).

Upsert by the ISO business key (`code`), so re-running is safe (boot or reseed).
This is a curated starter set (major world currencies + ~30 countries incl. the
Central-African / Equatorial-Guinea context, plus sample subdivisions); it is
extensible to the full ISO 4217 / 3166 datasets without schema change.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reference.models import Country, CountryRegion, Currency

# (code, name, symbol, decimal_places)
_CURRENCIES = [
    ("USD", "US Dollar", "$", 2), ("EUR", "Euro", "€", 2),
    ("GBP", "Pound Sterling", "£", 2), ("JPY", "Yen", "¥", 0),
    ("CNY", "Yuan Renminbi", "¥", 2), ("XAF", "CFA Franc BEAC", "FCFA", 0),
    ("XOF", "CFA Franc BCEAO", "CFA", 0), ("NGN", "Naira", "₦", 2),
    ("ZAR", "Rand", "R", 2), ("CAD", "Canadian Dollar", "$", 2),
    ("AUD", "Australian Dollar", "$", 2), ("CHF", "Swiss Franc", "Fr", 2),
    ("INR", "Indian Rupee", "₹", 2), ("BRL", "Brazilian Real", "R$", 2),
    ("MXN", "Mexican Peso", "$", 2), ("RUB", "Russian Ruble", "₽", 2),
    ("AED", "UAE Dirham", "د.إ", 2), ("SAR", "Saudi Riyal", "﷼", 2),
    ("MAD", "Moroccan Dirham", "DH", 2), ("EGP", "Egyptian Pound", "E£", 2),
    ("KES", "Kenyan Shilling", "KSh", 2), ("GHS", "Ghana Cedi", "₵", 2),
]

# (code, alpha3, numeric, name, phone_code, default_currency_code)
_COUNTRIES = [
    ("GQ", "GNQ", "226", "Equatorial Guinea", "+240", "XAF"),
    ("CM", "CMR", "120", "Cameroon", "+237", "XAF"),
    ("GA", "GAB", "266", "Gabon", "+241", "XAF"),
    ("CG", "COG", "178", "Congo", "+242", "XAF"),
    ("TD", "TCD", "148", "Chad", "+235", "XAF"),
    ("CF", "CAF", "140", "Central African Republic", "+236", "XAF"),
    ("SN", "SEN", "686", "Senegal", "+221", "XOF"),
    ("CI", "CIV", "384", "Côte d'Ivoire", "+225", "XOF"),
    ("NG", "NGA", "566", "Nigeria", "+234", "NGN"),
    ("GH", "GHA", "288", "Ghana", "+233", "GHS"),
    ("ZA", "ZAF", "710", "South Africa", "+27", "ZAR"),
    ("KE", "KEN", "404", "Kenya", "+254", "KES"),
    ("MA", "MAR", "504", "Morocco", "+212", "MAD"),
    ("EG", "EGY", "818", "Egypt", "+20", "EGP"),
    ("US", "USA", "840", "United States", "+1", "USD"),
    ("CA", "CAN", "124", "Canada", "+1", "CAD"),
    ("GB", "GBR", "826", "United Kingdom", "+44", "GBP"),
    ("FR", "FRA", "250", "France", "+33", "EUR"),
    ("ES", "ESP", "724", "Spain", "+34", "EUR"),
    ("DE", "DEU", "276", "Germany", "+49", "EUR"),
    ("IT", "ITA", "380", "Italy", "+39", "EUR"),
    ("PT", "PRT", "620", "Portugal", "+351", "EUR"),
    ("CN", "CHN", "156", "China", "+86", "CNY"),
    ("JP", "JPN", "392", "Japan", "+81", "JPY"),
    ("IN", "IND", "356", "India", "+91", "INR"),
    ("AU", "AUS", "036", "Australia", "+61", "AUD"),
    ("BR", "BRA", "076", "Brazil", "+55", "BRL"),
    ("MX", "MEX", "484", "Mexico", "+52", "MXN"),
    ("RU", "RUS", "643", "Russia", "+7", "RUB"),
    ("AE", "ARE", "784", "United Arab Emirates", "+971", "AED"),
    ("SA", "SAU", "682", "Saudi Arabia", "+966", "SAR"),
]

# country_code -> [(region_code, name, region_type)]  (sample subdivisions)
_REGIONS = {
    "GQ": [
        ("GQ-BN", "Bioko Norte", "province"), ("GQ-BS", "Bioko Sur", "province"),
        ("GQ-LI", "Litoral", "province"), ("GQ-CS", "Centro Sur", "province"),
        ("GQ-KN", "Kié-Ntem", "province"), ("GQ-WN", "Wele-Nzas", "province"),
        ("GQ-AN", "Annobón", "province"), ("GQ-DJ", "Djibloho", "province"),
    ],
    "US": [
        ("US-CA", "California", "state"), ("US-NY", "New York", "state"),
        ("US-TX", "Texas", "state"), ("US-FL", "Florida", "state"),
    ],
}


async def _upsert(session: AsyncSession, model, code_value: str,
                  fields: dict, *, extra_key: dict | None = None):
    """Upsert one row by its business key (code, optionally scoped). Returns the row."""
    stmt = select(model).where(model.code == code_value)
    for k, v in (extra_key or {}).items():
        stmt = stmt.where(getattr(model, k) == v)
    row = await session.scalar(stmt)
    if row is None:
        row = model(code=code_value, **(extra_key or {}), **fields)
        session.add(row)
    else:
        for k, v in fields.items():
            setattr(row, k, v)
    return row


async def seed_reference(session: AsyncSession) -> dict:
    """Idempotent: upsert currencies, then countries (linking default currency),
    then sample regions. Commits once. Returns counts."""
    cur_by_code: dict[str, Currency] = {}
    for code, name, symbol, dp in _CURRENCIES:
        cur = await _upsert(session, Currency, code,
                            {"name": name, "symbol": symbol, "decimal_places": dp})
        cur_by_code[code] = cur
    await session.flush()  # currencies need ids before countries reference them

    country_by_code: dict[str, Country] = {}
    for code, a3, num, name, phone, cur_code in _COUNTRIES:
        cur = cur_by_code.get(cur_code)
        country = await _upsert(session, Country, code, {
            "alpha3": a3, "numeric_code": num, "name": name, "phone_code": phone,
            "default_currency_id": cur.id if cur else None})
        country_by_code[code] = country
    await session.flush()

    region_n = 0
    for country_code, regions in _REGIONS.items():
        country = country_by_code.get(country_code)
        if country is None:
            continue
        for rcode, rname, rtype in regions:
            await _upsert(session, CountryRegion, rcode,
                          {"name": rname, "region_type": rtype},
                          extra_key={"country_id": country.id})
            region_n += 1

    await session.commit()
    return {"currencies": len(_CURRENCIES), "countries": len(_COUNTRIES),
            "regions": region_n}
