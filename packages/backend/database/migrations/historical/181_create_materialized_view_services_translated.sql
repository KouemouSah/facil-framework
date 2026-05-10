-- Migration 181: Materialized view for translated service catalog
-- Eliminates 5 entity_translations JOINs from every search/list query
-- Refresh via CRON (hourly) or on service/translation changes

-- Drop if exists (idempotent)
DROP MATERIALIZED VIEW IF EXISTS mv_services_translated;

CREATE MATERIALIZED VIEW mv_services_translated AS
SELECT
    fs.id,
    fs.service_code,
    fs.name_es,
    fs.description_es,
    fs.service_type,
    fs.status,
    fs.category_id,
    fs.tasa_expedicion,
    fs.tasa_renovacion,
    fs.processing_time_days,
    fs.calculation_method,
    fs.view_count,
    fs.calculation_count,
    c.category_code,
    c.name_es AS category_name_es,
    s.sector_code,
    s.name_es AS sector_name_es,
    m.id AS ministry_id,
    m.ministry_code,
    m.name_es AS ministry_name_es,
    -- French translations
    et_name_fr.translation_text AS name_fr,
    et_desc_fr.translation_text AS description_fr,
    et_cat_fr.translation_text AS category_name_fr,
    et_sec_fr.translation_text AS sector_name_fr,
    et_min_fr.translation_text AS ministry_name_fr,
    -- English translations
    et_name_en.translation_text AS name_en,
    et_desc_en.translation_text AS description_en,
    et_cat_en.translation_text AS category_name_en,
    et_sec_en.translation_text AS sector_name_en,
    et_min_en.translation_text AS ministry_name_en
FROM fiscal_services fs
LEFT JOIN categories c ON fs.category_id = c.id
LEFT JOIN sectors s ON c.sector_id = s.id
LEFT JOIN ministries m ON s.ministry_id = m.id
-- French service translations
LEFT JOIN entity_translations et_name_fr ON et_name_fr.entity_type = 'service' AND et_name_fr.entity_code = fs.service_code AND et_name_fr.field_name = 'name' AND et_name_fr.language_code = 'fr'
LEFT JOIN entity_translations et_desc_fr ON et_desc_fr.entity_type = 'service' AND et_desc_fr.entity_code = fs.service_code AND et_desc_fr.field_name = 'description' AND et_desc_fr.language_code = 'fr'
LEFT JOIN entity_translations et_cat_fr ON et_cat_fr.entity_type = 'category' AND et_cat_fr.entity_code = c.category_code AND et_cat_fr.field_name = 'name' AND et_cat_fr.language_code = 'fr'
LEFT JOIN entity_translations et_sec_fr ON et_sec_fr.entity_type = 'sector' AND et_sec_fr.entity_code = s.sector_code AND et_sec_fr.field_name = 'name' AND et_sec_fr.language_code = 'fr'
LEFT JOIN entity_translations et_min_fr ON et_min_fr.entity_type = 'ministry' AND et_min_fr.entity_code = m.ministry_code AND et_min_fr.field_name = 'name' AND et_min_fr.language_code = 'fr'
-- English service translations
LEFT JOIN entity_translations et_name_en ON et_name_en.entity_type = 'service' AND et_name_en.entity_code = fs.service_code AND et_name_en.field_name = 'name' AND et_name_en.language_code = 'en'
LEFT JOIN entity_translations et_desc_en ON et_desc_en.entity_type = 'service' AND et_desc_en.entity_code = fs.service_code AND et_desc_en.field_name = 'description' AND et_desc_en.language_code = 'en'
LEFT JOIN entity_translations et_cat_en ON et_cat_en.entity_type = 'category' AND et_cat_en.entity_code = c.category_code AND et_cat_en.field_name = 'name' AND et_cat_en.language_code = 'en'
LEFT JOIN entity_translations et_sec_en ON et_sec_en.entity_type = 'sector' AND et_sec_en.entity_code = s.sector_code AND et_sec_en.field_name = 'name' AND et_sec_en.language_code = 'en'
LEFT JOIN entity_translations et_min_en ON et_min_en.entity_type = 'ministry' AND et_min_en.entity_code = m.ministry_code AND et_min_en.field_name = 'name' AND et_min_en.language_code = 'en'
WHERE fs.status = 'active';

-- Indexes on materialized view for fast queries
CREATE UNIQUE INDEX idx_mv_services_id ON mv_services_translated (id);
CREATE INDEX idx_mv_services_category ON mv_services_translated (category_id);
CREATE INDEX idx_mv_services_ministry ON mv_services_translated (ministry_id);
CREATE INDEX idx_mv_services_type ON mv_services_translated (service_type);
CREATE INDEX idx_mv_services_name_es ON mv_services_translated (name_es);

-- Grant read access
GRANT SELECT ON mv_services_translated TO postgres;
