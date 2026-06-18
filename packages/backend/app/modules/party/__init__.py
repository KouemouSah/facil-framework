"""party module — the universal directory (res.partner / SAP Business Partner).

The second canonical pillar next to `organization` (= the Company / res.company):
a Party is any person OR organization you deal with (customer, vendor, contact,
employee) AND the legal identity of each of your own companies. Business natures
are roles (`party_role`), not separate tables. Reusable `address` rows (referencing
the reference-module country/region) are shared by parties, companies and sites.
See `.claude/plans/ERP_GRADE_FOUNDATION_PLAN.md` (Phase F.3).
"""
