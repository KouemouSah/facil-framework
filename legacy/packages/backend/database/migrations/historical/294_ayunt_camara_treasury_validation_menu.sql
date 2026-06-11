-- 294_ayunt_camara_treasury_validation_menu.sql
--
-- P8.2 X2 fix: route AYUNT/CAMARA validation menu (agents + supervisors) to
-- the existing payment-level treasury validation page.
--
-- Root cause:
--   Commit 3fdce698 (2026-03-01) introduced /dashboard/agent/treasury/validation
--   as the canonical treasury-style validation flow but forgot to migrate
--   AYUNT/CAMARA roles. Their menu_config still pointed at the OMS PendingPage
--   route which calls a SR-level decision endpoint that 403s for bundle splits
--   (agent_work_queue has no row for non-primary-entity agents on bundle SRs).
--
-- Why safe to migrate (verified 2026-04-15):
--   - Permission treasury.validate_payment is already granted to
--     agent_ayuntamiento, agent_camara, supervisor_ayuntamiento, supervisor_camara
--   - Backend _get_treasury_context() is entity-agnostic (returns profile of
--     any active agent, not TESORO-only)
--   - GET /treasury/payments/pending filters by assigned_agent_id only
--     (no entity filter) -> each agent sees their own assigned splits
--   - POST /treasury/payments/{id}/validate delegates to validate_manual_payment
--     without entity check
--   - i18n keys treasury.validation.title are neutral across es/fr/en
--     ("Validación de Pagos" / "Validation des Paiements" / "Payment Validation")
--   - Supervisor features on the treasury page (assign/escalate via
--     PaymentValidationDialog + treasuryAgents filter) activate automatically
--     when context.isSupervisor=true -> supervisors get full toolset
--
-- Idempotency:
--   run_migrations.py re-runs every .sql file on each deploy with no tracking.
--   WHERE clauses check id='pending' AND old href value, so re-runs become no-ops
--   after the first successful application.
--
-- JSONB path indexes differ between agents and supervisors because supervisors
-- have an extra 'team' menu inserted before 'validation':
--   agent_ayuntamiento / agent_camara       -> menus[1] = validation
--   supervisor_ayuntamiento / supervisor_camara -> menus[2] = validation
--
-- Scope:
--   agents: items[0] (pending) + items[1] (history)
--   supervisors: items[0] (pending) only -- items[1] is 'escalations' and
--     points at /dashboard/supervisor/oms/escalations, a separate OMS-scoped
--     escalations flow that remains intact.

BEGIN;

-- ---------------------------------------------------------------------------
-- Agents: agent_ayuntamiento, agent_camara
--   path: menus[1].items[0] = pending   -> treasury/validation
--         menus[1].items[1] = history   -> treasury/validation?status=processed
-- ---------------------------------------------------------------------------

UPDATE roles
SET menu_config = jsonb_set(
    menu_config,
    '{menus,1,items,0,href}',
    '"/dashboard/agent/treasury/validation"'::jsonb
)
WHERE code IN ('agent_ayuntamiento', 'agent_camara')
  AND menu_config->'menus'->1->>'id' = 'validation'
  AND menu_config->'menus'->1->'items'->0->>'id' = 'pending'
  AND menu_config->'menus'->1->'items'->0->>'href' = '/dashboard/agent/oms/validation';

UPDATE roles
SET menu_config = jsonb_set(
    menu_config,
    '{menus,1,items,1,href}',
    '"/dashboard/agent/treasury/validation?status=processed"'::jsonb
)
WHERE code IN ('agent_ayuntamiento', 'agent_camara')
  AND menu_config->'menus'->1->>'id' = 'validation'
  AND menu_config->'menus'->1->'items'->1->>'id' = 'history'
  AND menu_config->'menus'->1->'items'->1->>'href' = '/dashboard/agent/oms/validation/history';

-- ---------------------------------------------------------------------------
-- Supervisors: supervisor_ayuntamiento, supervisor_camara
--   path: menus[2].items[0] = pending -> treasury/validation
--   (items[1] = 'escalations' left untouched, lives on supervisor/oms/escalations)
-- ---------------------------------------------------------------------------

UPDATE roles
SET menu_config = jsonb_set(
    menu_config,
    '{menus,2,items,0,href}',
    '"/dashboard/agent/treasury/validation"'::jsonb
)
WHERE code IN ('supervisor_ayuntamiento', 'supervisor_camara')
  AND menu_config->'menus'->2->>'id' = 'validation'
  AND menu_config->'menus'->2->'items'->0->>'id' = 'pending'
  AND menu_config->'menus'->2->'items'->0->>'href' = '/dashboard/agent/oms/validation';

-- ---------------------------------------------------------------------------
-- AYUNT/CAMARA agents: fix dashboard href (menus[0]) — was pointing at the
-- broken OMS /dashboard/agent/oms/validator page (PendingPage with bundle-
-- unaware decision endpoint 403-ing). Align with Tesoro pattern: generic
-- entity dashboard via catch-all [entityCode] route.
-- Supervisors keep their existing /dashboard/supervisor/oms landing.
-- ---------------------------------------------------------------------------

UPDATE roles
SET menu_config = jsonb_set(
    menu_config,
    '{menus,0,href}',
    '"/dashboard/agent/ayuntamiento"'::jsonb
)
WHERE code = 'agent_ayuntamiento'
  AND menu_config->'menus'->0->>'id' = 'dashboard'
  AND menu_config->'menus'->0->>'href' = '/dashboard/agent/oms/validator';

UPDATE roles
SET menu_config = jsonb_set(
    menu_config,
    '{menus,0,href}',
    '"/dashboard/agent/camara-comercio"'::jsonb
)
WHERE code = 'agent_camara'
  AND menu_config->'menus'->0->>'id' = 'dashboard'
  AND menu_config->'menus'->0->>'href' = '/dashboard/agent/oms/validator';

-- ---------------------------------------------------------------------------
-- Data fix: ayumalabo1 was flagged agent_profiles.is_supervisor=true despite
-- holding the agent_ayuntamiento role (not supervisor_*). Combined with the
-- pre-P8.2 `has_global_scope = (supervisor AND main_office)` property, this
-- gave the account a cross-entity global scope in the treasury endpoints
-- (they could see Tesoro/Camara payments). Resetting the flag closes the
-- leak for this specific account; the backend refactor in admin_routes.py
-- (TreasuryAgentContext) closes it architecturally.
-- Idempotent: only updates rows still incorrectly flagged.
-- ---------------------------------------------------------------------------

UPDATE agent_profiles
SET is_supervisor = false, updated_at = NOW()
WHERE is_supervisor = true
  AND user_id IN (
      SELECT u.id
      FROM users u
      JOIN roles r ON r.id = u.role_id
      WHERE u.email = 'ayumalabo1@gmail.com'
        AND r.code = 'agent_ayuntamiento'
  );

-- ---------------------------------------------------------------------------
-- Version bump (trace migration origin; idempotent via version match)
-- ---------------------------------------------------------------------------

UPDATE roles
SET menu_config = jsonb_set(menu_config, '{version}', '"1.1"'::jsonb)
WHERE code IN (
    'agent_ayuntamiento',
    'agent_camara',
    'supervisor_ayuntamiento',
    'supervisor_camara'
)
  AND menu_config->>'version' = '1.0';

COMMIT;

-- ============================================================================
-- ROLLBACK (manual, uncomment + execute if this migration needs to be reverted)
-- ============================================================================
--
-- BEGIN;
--
-- -- Agents: revert validation.pending + validation.history
-- UPDATE roles
-- SET menu_config = jsonb_set(menu_config, '{menus,1,items,0,href}',
--     '"/dashboard/agent/oms/validation"'::jsonb)
-- WHERE code IN ('agent_ayuntamiento', 'agent_camara')
--   AND menu_config->'menus'->1->'items'->0->>'id' = 'pending';
-- UPDATE roles
-- SET menu_config = jsonb_set(menu_config, '{menus,1,items,1,href}',
--     '"/dashboard/agent/oms/validation/history"'::jsonb)
-- WHERE code IN ('agent_ayuntamiento', 'agent_camara')
--   AND menu_config->'menus'->1->'items'->1->>'id' = 'history';
--
-- -- Agents: revert dashboard href
-- UPDATE roles
-- SET menu_config = jsonb_set(menu_config, '{menus,0,href}',
--     '"/dashboard/agent/oms/validator"'::jsonb)
-- WHERE code IN ('agent_ayuntamiento', 'agent_camara')
--   AND menu_config->'menus'->0->>'id' = 'dashboard';
--
-- -- Supervisors: revert pending
-- UPDATE roles
-- SET menu_config = jsonb_set(menu_config, '{menus,2,items,0,href}',
--     '"/dashboard/agent/oms/validation"'::jsonb)
-- WHERE code IN ('supervisor_ayuntamiento', 'supervisor_camara')
--   AND menu_config->'menus'->2->'items'->0->>'id' = 'pending';
--
-- -- Revert version
-- UPDATE roles
-- SET menu_config = jsonb_set(menu_config, '{version}', '"1.0"'::jsonb)
-- WHERE code IN (
--     'agent_ayuntamiento', 'agent_camara',
--     'supervisor_ayuntamiento', 'supervisor_camara'
-- ) AND menu_config->>'version' = '1.1';
--
-- -- NOTE: rollback of `ayumalabo1.is_supervisor = false` is intentional:
-- -- leaving this unchanged even on rollback. Flipping back to true would
-- -- re-introduce the cross-entity leak. If the user was actually meant to be
-- -- a supervisor, change their role from agent_ayuntamiento to
-- -- supervisor_ayuntamiento instead.
--
-- COMMIT;
