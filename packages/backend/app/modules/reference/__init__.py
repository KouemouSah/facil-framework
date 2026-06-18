"""reference module — master data (country / region / currency) for the ERP core.

Replaces the free-text country/region/currency previously stored on organization
and site with managed reference tables (ISO 3166-1 / 3166-2 / 4217), so geography
and money carry referential integrity and i18n labels. See
`.claude/plans/ERP_GRADE_FOUNDATION_PLAN.md` (Phase F.2).
"""
