-- Migration 131: entity_code direct routing + priority_weight on workflows
--
-- Fixes 3 bugs in agent_queue_service.py:
-- Bug 1: ENTITY_TO_MINISTRY dict had fake IDs (1-5 vs real 85-102)
-- Bug 2: CATEGORY_PRIORITIES dict had mismatched names (conducir vs CONDUCCION)
-- Bug 3: priority_weight column didn't exist → SELECT always returned NULL
--
-- Changes:
-- 1. Add entity_code column to agent_work_queue (replace ministry_id indirection)
-- 2. Add priority_weight column to workflows (replace broken CATEGORY_PRIORITIES dict)

-- 1. Add entity_code to agent_work_queue (direct routing)
ALTER TABLE agent_work_queue ADD COLUMN IF NOT EXISTS entity_code TEXT;

CREATE INDEX IF NOT EXISTS idx_agent_work_queue_entity_pending
    ON agent_work_queue (entity_code)
    WHERE status = 'pending';

COMMENT ON COLUMN agent_work_queue.entity_code IS
    'Entity code for direct queue routing. Replaces ministry_id indirection via ENTITY_TO_MINISTRY dict.';

-- 2. Add priority_weight to workflows
ALTER TABLE workflows ADD COLUMN IF NOT EXISTS priority_weight INTEGER NOT NULL DEFAULT 50;

COMMENT ON COLUMN workflows.priority_weight IS
    'Base priority score (1-100) for agent queue ordering. Higher = processed first.';

-- Set values per category (preserves original CATEGORY_PRIORITIES intent)
UPDATE workflows SET priority_weight = 60 WHERE category = 'EXTRANJERIA';
UPDATE workflows SET priority_weight = 55 WHERE category = 'FUNCION_PUBLICA';
UPDATE workflows SET priority_weight = 50 WHERE category = 'IDENTIDAD';
UPDATE workflows SET priority_weight = 45 WHERE category = 'CONTRATOS';
UPDATE workflows SET priority_weight = 40 WHERE category = 'VEHICULOS';
UPDATE workflows SET priority_weight = 35 WHERE category = 'CONDUCCION';
