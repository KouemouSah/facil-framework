-- Migration 125: Update TESORO agent dashboard_config
-- Agent: remove in_progress_payments widget (agents see pending in split view validation page)
-- Supervisor: NO CHANGE (keep management-focused widgets: team_workload, escalations, anomaly_summary, alerts)

-- ============================================================================
-- AGENT TESORO ONLY: Remove in_progress_payments, keep pending + completed
-- ============================================================================

UPDATE roles
SET dashboard_config = '{
  "layout": "grid",
  "version": "2.2",
  "widgets": [
    {"id": "pending_payments", "size": "medium", "visible": true, "position": 1},
    {"id": "completed_payments", "size": "medium", "visible": true, "position": 2}
  ]
}'::jsonb
WHERE code = 'agent_tesoro';

-- NOTE: supervisor_tesoro is NOT modified. Its dashboard remains management-focused:
-- pending_payments, team_workload, escalations, anomaly_summary, alerts
