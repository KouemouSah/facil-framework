-- Migration 099: Remove hardcoded CHECK constraints on entity_locations
-- City and region validation is now done in Python code against the cities table
-- which is the single source of truth for available cities.
--
-- Before: CHECK (city IN ('Malabo', 'Bata', ...)) — breaks when adding cities
-- After: Python validates city EXISTS in cities table before INSERT/UPDATE

ALTER TABLE entity_locations DROP CONSTRAINT IF EXISTS valid_city;
ALTER TABLE entity_locations DROP CONSTRAINT IF EXISTS valid_region;
