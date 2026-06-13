"""location — physical sites / branches / offices (Phase A.5).

Generalises the legacy `entity_locations` + `cities` (de-hardcoded of the gov
regions/cities). A Site belongs to an Organization and optionally an OrgUnit, and
can nest under a parent Site (branch hierarchy). Supports site-scoping (the row
carries organization_id/org_unit_id; enforcement wires at D4).
See docs/architecture/MODULES_ORG_LOCATION.md.
"""
