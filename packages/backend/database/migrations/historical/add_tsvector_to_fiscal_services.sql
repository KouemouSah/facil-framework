-- ===================================================================================================
-- Migration: Add full-text search support to fiscal_services table
-- ===================================================================================================
-- Purpose: Add tsvector column with GIN index for fast full-text search
-- Performance: ~10-100x faster than ILIKE for large datasets (10K+ rows)
-- Language: Spanish (majority of content)
-- ===================================================================================================

-- Step 1: Add tsvector column
ALTER TABLE fiscal_services
ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- Step 2: Create function to update search_vector
-- Combines name_es, description_es for comprehensive search
CREATE OR REPLACE FUNCTION fiscal_services_search_vector_update()
RETURNS trigger AS $$
BEGIN
  NEW.search_vector :=
    setweight(to_tsvector('spanish', COALESCE(NEW.name_es, '')), 'A') ||
    setweight(to_tsvector('spanish', COALESCE(NEW.description_es, '')), 'B');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Step 3: Create trigger to auto-update search_vector on INSERT/UPDATE
DROP TRIGGER IF EXISTS fiscal_services_search_vector_trigger ON fiscal_services;

CREATE TRIGGER fiscal_services_search_vector_trigger
BEFORE INSERT OR UPDATE OF name_es, description_es
ON fiscal_services
FOR EACH ROW
EXECUTE FUNCTION fiscal_services_search_vector_update();

-- Step 4: Populate search_vector for existing rows
UPDATE fiscal_services
SET search_vector =
  setweight(to_tsvector('spanish', COALESCE(name_es, '')), 'A') ||
  setweight(to_tsvector('spanish', COALESCE(description_es, '')), 'B')
WHERE search_vector IS NULL OR search_vector = ''::tsvector;

-- Step 5: Create GIN index for fast full-text search
-- GIN (Generalized Inverted Index) is optimized for tsvector searches
CREATE INDEX IF NOT EXISTS idx_fiscal_services_search_vector
ON fiscal_services
USING GIN (search_vector);

-- Step 6: Add comment for documentation
COMMENT ON COLUMN fiscal_services.search_vector IS
'Full-text search vector (Spanish). Auto-updated via trigger. Weight A for name_es, B for description_es.';

-- ===================================================================================================
-- Performance Notes:
-- ===================================================================================================
-- BEFORE (ILIKE):
--   SELECT * FROM fiscal_services WHERE name_es ILIKE '%permiso%';
--   → Sequential scan, ~50-200ms for 10K rows
--
-- AFTER (ts_vector):
--   SELECT * FROM fiscal_services WHERE search_vector @@ to_tsquery('spanish', 'permiso');
--   → Index scan, ~2-10ms for 10K rows
--
-- Improvement: 10-100x faster
-- ===================================================================================================

-- ===================================================================================================
-- Usage Example:
-- ===================================================================================================
-- Search for "permiso construccion":
--   SELECT id, name_es, ts_rank(search_vector, query) AS rank
--   FROM fiscal_services, to_tsquery('spanish', 'permiso & construccion') query
--   WHERE search_vector @@ query
--   ORDER BY rank DESC;
--
-- Phrase search:
--   SELECT * FROM fiscal_services
--   WHERE search_vector @@ phraseto_tsquery('spanish', 'permiso de construccion');
-- ===================================================================================================

-- Verify migration
DO $$
BEGIN
  -- Check column exists
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'fiscal_services' AND column_name = 'search_vector'
  ) THEN
    RAISE EXCEPTION 'Migration failed: search_vector column not created';
  END IF;

  -- Check index exists
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE tablename = 'fiscal_services' AND indexname = 'idx_fiscal_services_search_vector'
  ) THEN
    RAISE EXCEPTION 'Migration failed: GIN index not created';
  END IF;

  -- Check trigger exists
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgname = 'fiscal_services_search_vector_trigger'
  ) THEN
    RAISE EXCEPTION 'Migration failed: trigger not created';
  END IF;

  RAISE NOTICE 'Migration completed successfully!';
  RAISE NOTICE 'Column: fiscal_services.search_vector ✓';
  RAISE NOTICE 'Index: idx_fiscal_services_search_vector (GIN) ✓';
  RAISE NOTICE 'Trigger: fiscal_services_search_vector_trigger ✓';
END $$;
