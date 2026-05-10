-- ============================================================================
-- MIGRATION 066: Synchronisation des permissions Backend vers Database
-- Date: 2026-01-24
-- Description: Ajoute les 239 permissions définies dans le backend mais
--              absentes de la base de données
-- ============================================================================

-- Transaction pour assurer l'atomicité
BEGIN;

-- ============================================================================
-- INSERTION DES PERMISSIONS MANQUANTES
-- Utilise ON CONFLICT pour ignorer les doublons si déjà insérées
-- ============================================================================

INSERT INTO permissions (name, description, module, created_at)
VALUES
    -- ========================================================================
    -- TREASURY (18 permissions)
    -- ========================================================================
    ('treasury.validate_payment', 'Validate treasury payments', 'treasury', NOW()),
    ('treasury.reject_payment', 'Reject treasury payments', 'treasury', NOW()),
    ('treasury.view_payment', 'View treasury payments', 'treasury', NOW()),
    ('treasury.process_payment', 'Process treasury payments', 'treasury', NOW()),
    ('treasury_audit.view', 'View treasury audit logs', 'treasury', NOW()),
    ('treasury_audit.export', 'Export treasury audit logs', 'treasury', NOW()),
    ('treasury_stat.view', 'View treasury statistics', 'treasury', NOW()),
    ('treasury_stat.export', 'Export treasury statistics', 'treasury', NOW()),
    ('treasury_anomaly.view', 'View treasury anomalies', 'treasury', NOW()),
    ('treasury_anomaly.create', 'Create treasury anomalies', 'treasury', NOW()),
    ('treasury_anomaly.update', 'Update treasury anomalies', 'treasury', NOW()),
    ('treasury_anomaly.resolve', 'Resolve treasury anomalies', 'treasury', NOW()),
    ('treasury_export.view', 'View treasury exports', 'treasury', NOW()),
    ('treasury_export.create', 'Create treasury exports', 'treasury', NOW()),
    ('treasury_export.download', 'Download treasury exports', 'treasury', NOW()),
    ('treasury.reconcile', 'Reconcile treasury payments', 'treasury', NOW()),
    ('treasury.view_reconciliation', 'View treasury reconciliation', 'treasury', NOW()),
    ('treasury.manage_settings', 'Manage treasury settings', 'treasury', NOW()),

    -- ========================================================================
    -- PAYMENTS (14 permissions)
    -- ========================================================================
    ('payment.view', 'View payments', 'payments', NOW()),
    ('payment.view_all', 'View all payments', 'payments', NOW()),
    ('payment.update', 'Update payments', 'payments', NOW()),
    ('payment.create', 'Create payments', 'payments', NOW()),
    ('payment.cancel', 'Cancel payments', 'payments', NOW()),
    ('payment.refund', 'Refund payments', 'payments', NOW()),
    ('payment_plan.view', 'View payment plans', 'payments', NOW()),
    ('payment_plan.create', 'Create payment plans', 'payments', NOW()),
    ('payment_plan.update', 'Update payment plans', 'payments', NOW()),
    ('receipt.view', 'View receipts', 'payments', NOW()),
    ('receipt.regenerate', 'Regenerate receipts', 'payments', NOW()),
    ('receipt.void', 'Void receipts', 'payments', NOW()),
    ('payment.reconcile', 'Reconcile payments', 'payments', NOW()),
    ('payment.view_reconciliation', 'View payment reconciliation', 'payments', NOW()),

    -- ========================================================================
    -- SERVICE REQUEST (23 permissions)
    -- ========================================================================
    ('service_request.view_queue', 'View service request queue', 'service_requests', NOW()),
    ('service_request.view_queue_stats', 'View queue statistics', 'service_requests', NOW()),
    ('service_request.view_my_queue', 'View own queue', 'service_requests', NOW()),
    ('service_request.assign_to_self', 'Assign requests to self', 'service_requests', NOW()),
    ('service_request.release', 'Release service requests', 'service_requests', NOW()),
    ('service_request.view', 'View service requests', 'service_requests', NOW()),
    ('service_request.view_documents', 'View request documents', 'service_requests', NOW()),
    ('service_request.view_extraction', 'View OCR extraction results', 'service_requests', NOW()),
    ('service_request.process', 'Process service requests', 'service_requests', NOW()),
    ('service_request.approve', 'Approve service requests', 'service_requests', NOW()),
    ('service_request.reject', 'Reject service requests', 'service_requests', NOW()),
    ('service_request.request_documents', 'Request additional documents', 'service_requests', NOW()),
    ('service_request.escalate', 'Escalate service requests', 'service_requests', NOW()),
    ('service_request.view_appointments', 'View appointments', 'service_requests', NOW()),
    ('service_request.schedule_appointment', 'Schedule appointments', 'service_requests', NOW()),
    ('service_request.reschedule_appointment', 'Reschedule appointments', 'service_requests', NOW()),
    ('service_request.cancel_appointment', 'Cancel appointments', 'service_requests', NOW()),
    ('service_request.view_available_slots', 'View available appointment slots', 'service_requests', NOW()),
    ('service_request.verify_manually', 'Manually verify requests', 'service_requests', NOW()),
    ('service_request.view_all', 'View all service requests', 'service_requests', NOW()),
    ('service_request.reassign', 'Reassign service requests', 'service_requests', NOW()),
    ('service_request.export', 'Export service requests', 'service_requests', NOW()),
    ('service_request.view_audit_log', 'View request audit log', 'service_requests', NOW()),

    -- ========================================================================
    -- AGENT (14 permissions)
    -- ========================================================================
    ('agent.create', 'Create agents', 'agents', NOW()),
    ('agent.view', 'View agents', 'agents', NOW()),
    ('agent.list', 'List agents', 'agents', NOW()),
    ('agent.update', 'Update agents', 'agents', NOW()),
    ('agent.deactivate', 'Deactivate agents', 'agents', NOW()),
    ('agent.reactivate', 'Reactivate agents', 'agents', NOW()),
    ('agent.view_workload', 'View agent workload', 'agents', NOW()),
    ('agent.manage_workload', 'Manage agent workload', 'agents', NOW()),
    ('agent.set_availability', 'Set agent availability', 'agents', NOW()),
    ('agent.view_available', 'View available agents', 'agents', NOW()),
    ('agent.rebalance_workload', 'Rebalance agent workload', 'agents', NOW()),
    ('agent.view_performance', 'View agent performance', 'agents', NOW()),
    ('agent.view_capacity_prediction', 'View capacity prediction', 'agents', NOW()),
    ('agent.export_stats', 'Export agent statistics', 'agents', NOW()),

    -- ========================================================================
    -- ASSIGNMENT (18 permissions)
    -- ========================================================================
    ('assignment.create', 'Create assignments', 'agents', NOW()),
    ('assignment.view', 'View assignments', 'agents', NOW()),
    ('assignment.list', 'List assignments', 'agents', NOW()),
    ('assignment.update', 'Update assignments', 'agents', NOW()),
    ('assignment.auto_assign', 'Auto-assign tasks', 'agents', NOW()),
    ('assignment.start', 'Start assignments', 'agents', NOW()),
    ('assignment.complete', 'Complete assignments', 'agents', NOW()),
    ('assignment.reassign', 'Reassign tasks', 'agents', NOW()),
    ('assignment.reassign_in_progress', 'Reassign in-progress tasks', 'agents', NOW()),
    ('assignment.cancel', 'Cancel assignments', 'agents', NOW()),
    ('assignment.update_priority', 'Update assignment priority', 'agents', NOW()),
    ('assignment.extend_deadline', 'Extend assignment deadline', 'agents', NOW()),

    -- ========================================================================
    -- QUEUE (6 permissions)
    -- ========================================================================
    ('queue.view', 'View queue', 'agents', NOW()),
    ('queue.add', 'Add to queue', 'agents', NOW()),
    ('queue.assign', 'Assign from queue', 'agents', NOW()),
    ('queue.complete', 'Complete queue items', 'agents', NOW()),
    ('queue.escalate', 'Escalate queue items', 'agents', NOW()),
    ('queue.release', 'Release queue items', 'agents', NOW()),

    -- ========================================================================
    -- ADMIN (15 permissions)
    -- ========================================================================
    ('admin.manage_workflow', 'Manage workflows', 'admin', NOW()),
    ('admin.view_workflow', 'View workflows', 'admin', NOW()),
    ('admin.manage_tariff', 'Manage tariffs', 'admin', NOW()),
    ('admin.view_tariff', 'View tariffs', 'admin', NOW()),
    ('admin.manage_appointment', 'Manage appointments', 'admin', NOW()),
    ('admin.view_appointment', 'View appointments', 'admin', NOW()),
    ('admin.manage_system', 'Manage system settings', 'admin', NOW()),
    ('admin.view_system', 'View system settings', 'admin', NOW()),
    ('admin.run_migrations', 'Run database migrations', 'admin', NOW()),
    ('admin.view_diagnostics', 'View system diagnostics', 'admin', NOW()),
    ('admin.manage_entity', 'Manage entities', 'admin', NOW()),
    ('admin.view_entity', 'View entities', 'admin', NOW()),
    ('admin.manage_user', 'Manage users', 'admin', NOW()),
    ('admin.view_user', 'View users', 'admin', NOW()),
    ('admin.impersonate_user', 'Impersonate users', 'admin', NOW()),

    -- ========================================================================
    -- USER (13 permissions)
    -- ========================================================================
    ('user.view', 'View user profile', 'users', NOW()),
    ('user.view_all', 'View all users', 'users', NOW()),
    ('user.create', 'Create users', 'users', NOW()),
    ('user.update', 'Update own profile', 'users', NOW()),
    ('user.update_any', 'Update any user', 'users', NOW()),
    ('user.delete', 'Delete users', 'users', NOW()),
    ('user.search', 'Search users', 'users', NOW()),
    ('user.view_stats', 'View user statistics', 'users', NOW()),
    ('user.view_any_activities', 'View any user activities', 'users', NOW()),
    ('user.change_role', 'Change user roles', 'users', NOW()),
    ('user.suspend', 'Suspend users', 'users', NOW()),
    ('user.reactivate', 'Reactivate users', 'users', NOW()),
    ('user.impersonate', 'Impersonate users', 'users', NOW()),

    -- ========================================================================
    -- DECLARATION (30 permissions)
    -- ========================================================================
    ('declaration.view', 'View declarations', 'declarations', NOW()),
    ('declaration.list', 'List declarations', 'declarations', NOW()),
    ('declaration.search', 'Search declarations', 'declarations', NOW()),
    ('declaration.create', 'Create declarations', 'declarations', NOW()),
    ('declaration.update', 'Update declarations', 'declarations', NOW()),
    ('declaration.submit', 'Submit declarations', 'declarations', NOW()),
    ('declaration.withdraw', 'Withdraw declarations', 'declarations', NOW()),
    ('declaration.delete', 'Delete declarations', 'declarations', NOW()),
    ('declaration.upload_documents', 'Upload declaration documents', 'declarations', NOW()),
    ('declaration.view_documents', 'View declaration documents', 'declarations', NOW()),
    ('declaration.delete_documents', 'Delete declaration documents', 'declarations', NOW()),
    ('declaration.view_all', 'View all declarations', 'declarations', NOW()),
    ('declaration.assign', 'Assign declarations', 'declarations', NOW()),
    ('declaration.review', 'Review declarations', 'declarations', NOW()),
    ('declaration.process', 'Process declarations', 'declarations', NOW()),
    ('declaration.approve', 'Approve declarations', 'declarations', NOW()),
    ('declaration.reject', 'Reject declarations', 'declarations', NOW()),
    ('declaration.request_correction', 'Request declaration corrections', 'declarations', NOW()),
    ('declaration.bulk_operations', 'Bulk declaration operations', 'declarations', NOW()),
    ('declaration.amend', 'Amend declarations', 'declarations', NOW()),
    ('declaration.adjust_amount', 'Adjust declaration amounts', 'declarations', NOW()),
    ('declaration.batch_create', 'Batch create declarations', 'declarations', NOW()),
    ('declaration.batch_submit', 'Batch submit declarations', 'declarations', NOW()),
    ('declaration.import_excel', 'Import declarations from Excel', 'declarations', NOW()),
    ('declaration.mark_paid', 'Mark declarations as paid', 'declarations', NOW()),
    ('declaration.update_payment_info', 'Update payment information', 'declarations', NOW()),
    ('declaration.view_workflow', 'View declaration workflow', 'declarations', NOW()),
    ('declaration.view_activity_log', 'View declaration activity log', 'declarations', NOW()),
    ('declaration.view_stats', 'View declaration statistics', 'declarations', NOW()),
    ('declaration.export', 'Export declarations', 'declarations', NOW()),

    -- ========================================================================
    -- DOCUMENT (11 permissions)
    -- ========================================================================
    ('document.view', 'View documents', 'documents', NOW()),
    ('document.view_stats', 'View document statistics', 'documents', NOW()),
    ('document.download', 'Download documents', 'documents', NOW()),
    ('document.delete', 'Delete documents', 'documents', NOW()),
    ('template.view', 'View templates', 'documents', NOW()),
    ('template.create', 'Create templates', 'documents', NOW()),
    ('template.update', 'Update templates', 'documents', NOW()),
    ('template.delete', 'Delete templates', 'documents', NOW()),
    ('ocr.view_queue', 'View OCR queue', 'documents', NOW()),
    ('ocr.reprocess', 'Reprocess OCR', 'documents', NOW()),
    ('ocr.view_stats', 'View OCR statistics', 'documents', NOW()),

    -- ========================================================================
    -- AUDIT (4 permissions)
    -- ========================================================================
    ('audit.view', 'View audit logs', 'audit', NOW()),
    ('audit.view_stats', 'View audit statistics', 'audit', NOW()),
    ('audit.export', 'Export audit logs', 'audit', NOW()),
    ('audit.search', 'Search audit logs', 'audit', NOW()),

    -- ========================================================================
    -- SUPPORT (15 permissions)
    -- ========================================================================
    ('support.view', 'View support tickets', 'support', NOW()),
    ('support.view_all', 'View all support tickets', 'support', NOW()),
    ('support.manage', 'Manage support tickets', 'support', NOW()),
    ('support.assign', 'Assign support tickets', 'support', NOW()),
    ('support.escalate', 'Escalate support tickets', 'support', NOW()),
    ('support.close', 'Close support tickets', 'support', NOW()),
    ('support.reopen', 'Reopen support tickets', 'support', NOW()),
    ('support_message.reply', 'Reply to support messages', 'support', NOW()),
    ('support_message.delete', 'Delete support messages', 'support', NOW()),
    ('support_category.view', 'View support categories', 'support', NOW()),
    ('support_category.create', 'Create support categories', 'support', NOW()),
    ('support_category.update', 'Update support categories', 'support', NOW()),
    ('support_category.delete', 'Delete support categories', 'support', NOW()),
    ('support_stat.view', 'View support statistics', 'support', NOW()),
    ('support_stat.export', 'Export support statistics', 'support', NOW()),

    -- ========================================================================
    -- COMMUNICATION (23 permissions)
    -- ========================================================================
    ('communication.view', 'View communications', 'communications', NOW()),
    ('communication.manage', 'Manage communications', 'communications', NOW()),
    ('email_template.view', 'View email templates', 'communications', NOW()),
    ('email_template.create', 'Create email templates', 'communications', NOW()),
    ('email_template.update', 'Update email templates', 'communications', NOW()),
    ('email_template.delete', 'Delete email templates', 'communications', NOW()),
    ('sms_template.view', 'View SMS templates', 'communications', NOW()),
    ('sms_template.create', 'Create SMS templates', 'communications', NOW()),
    ('sms_template.update', 'Update SMS templates', 'communications', NOW()),
    ('sms_template.delete', 'Delete SMS templates', 'communications', NOW()),
    ('notification_template.view', 'View notification templates', 'communications', NOW()),
    ('notification_template.create', 'Create notification templates', 'communications', NOW()),
    ('notification_template.update', 'Update notification templates', 'communications', NOW()),
    ('notification_template.delete', 'Delete notification templates', 'communications', NOW()),
    ('push_template.view', 'View push templates', 'communications', NOW()),
    ('push_template.create', 'Create push templates', 'communications', NOW()),
    ('push_template.update', 'Update push templates', 'communications', NOW()),
    ('push_template.delete', 'Delete push templates', 'communications', NOW()),
    ('provider_setting.view', 'View provider settings', 'communications', NOW()),
    ('provider_setting.manage', 'Manage provider settings', 'communications', NOW()),
    ('communication.send_email', 'Send emails', 'communications', NOW()),
    ('communication.send_sms', 'Send SMS', 'communications', NOW()),
    ('communication.send_notification', 'Send notifications', 'communications', NOW()),

    -- ========================================================================
    -- WEBHOOK (7 permissions)
    -- ========================================================================
    ('webhook.view', 'View webhooks', 'webhooks', NOW()),
    ('webhook.create', 'Create webhooks', 'webhooks', NOW()),
    ('webhook.update', 'Update webhooks', 'webhooks', NOW()),
    ('webhook.delete', 'Delete webhooks', 'webhooks', NOW()),
    ('webhook.test', 'Test webhooks', 'webhooks', NOW()),
    ('webhook_log.view', 'View webhook logs', 'webhooks', NOW()),
    ('webhook_log.export', 'Export webhook logs', 'webhooks', NOW()),

    -- ========================================================================
    -- FISCAL SERVICE (12 permissions)
    -- ========================================================================
    ('fiscal_service.view', 'View fiscal services', 'fiscal_services', NOW()),
    ('fiscal_service.create', 'Create fiscal services', 'fiscal_services', NOW()),
    ('fiscal_service.update', 'Update fiscal services', 'fiscal_services', NOW()),
    ('fiscal_service.delete', 'Delete fiscal services', 'fiscal_services', NOW()),
    ('fiscal_service.view_stats', 'View fiscal service statistics', 'fiscal_services', NOW()),
    ('fiscal_service.manage_hierarchy', 'Manage service hierarchy', 'fiscal_services', NOW()),
    ('fiscal_service.manage_ministry', 'Manage ministries', 'fiscal_services', NOW()),
    ('fiscal_service.manage_sector', 'Manage sectors', 'fiscal_services', NOW()),
    ('fiscal_service.manage_category', 'Manage categories', 'fiscal_services', NOW()),
    ('fiscal_service.bulk_import', 'Bulk import services', 'fiscal_services', NOW()),
    ('fiscal_service.bulk_update', 'Bulk update services', 'fiscal_services', NOW()),
    ('fiscal_service.bulk_export', 'Bulk export services', 'fiscal_services', NOW()),

    -- ========================================================================
    -- TRANSLATION (13 permissions)
    -- ========================================================================
    ('translation.view', 'View translations', 'translations', NOW()),
    ('translation.create', 'Create translations', 'translations', NOW()),
    ('translation.update', 'Update translations', 'translations', NOW()),
    ('translation.delete', 'Delete translations', 'translations', NOW()),
    ('translation.batch_create', 'Batch create translations', 'translations', NOW()),
    ('entity_translation.view', 'View entity translations', 'translations', NOW()),
    ('entity_translation.create', 'Create entity translations', 'translations', NOW()),
    ('entity_translation.update', 'Update entity translations', 'translations', NOW()),
    ('entity_translation.delete', 'Delete entity translations', 'translations', NOW()),
    ('enum_translation.view', 'View enum translations', 'translations', NOW()),
    ('enum_translation.manage', 'Manage enum translations', 'translations', NOW()),
    ('frontend_translation.export', 'Export frontend translations', 'translations', NOW()),
    ('frontend_translation.sync', 'Sync frontend translations', 'translations', NOW()),

    -- ========================================================================
    -- DASHBOARD (7 permissions)
    -- ========================================================================
    ('dashboard.view', 'View dashboard', 'dashboard', NOW()),
    ('dashboard.view_realtime', 'View realtime dashboard', 'dashboard', NOW()),
    ('dashboard.team_stats', 'View team statistics', 'dashboard', NOW()),
    ('dashboard.team_performance', 'View team performance', 'dashboard', NOW()),
    ('dashboard.team_workload', 'View team workload', 'dashboard', NOW()),
    ('dashboard.view_own', 'View own dashboard', 'dashboard', NOW()),
    ('dashboard.view_own_stats', 'View own statistics', 'dashboard', NOW()),

    -- ========================================================================
    -- REPORTS (10 permissions)
    -- ========================================================================
    ('reports.view', 'View reports', 'reports', NOW()),
    ('reports.view_comparison', 'View comparison reports', 'reports', NOW()),
    ('reports.view_trends', 'View trend reports', 'reports', NOW()),
    ('reports.generate', 'Generate reports', 'reports', NOW()),
    ('reports.schedule', 'Schedule reports', 'reports', NOW()),
    ('reports.export_pdf', 'Export reports as PDF', 'reports', NOW()),
    ('reports.export_excel', 'Export reports as Excel', 'reports', NOW()),
    ('reports.export_json', 'Export reports as JSON', 'reports', NOW()),
    ('reports.view_financial', 'View financial reports', 'reports', NOW()),
    ('reports.view_performance', 'View performance reports', 'reports', NOW()),

    -- ========================================================================
    -- RULES (7 permissions)
    -- ========================================================================
    ('rules.view', 'View rules', 'rules', NOW()),
    ('rules.create', 'Create rules', 'rules', NOW()),
    ('rules.edit', 'Edit rules', 'rules', NOW()),
    ('rules.delete', 'Delete rules', 'rules', NOW()),
    ('rules.activate', 'Activate rules', 'rules', NOW()),
    ('rules.view_effectiveness', 'View rule effectiveness', 'rules', NOW()),
    ('rules.view_history', 'View rule history', 'rules', NOW()),

    -- ========================================================================
    -- CITY/ENTITY (8 permissions)
    -- ========================================================================
    ('city.view', 'View cities', 'locations', NOW()),
    ('city.create', 'Create cities', 'locations', NOW()),
    ('city.update', 'Update cities', 'locations', NOW()),
    ('city.delete', 'Delete cities', 'locations', NOW()),
    ('entity.view', 'View entities', 'locations', NOW()),
    ('entity.create', 'Create entities', 'locations', NOW()),
    ('entity.update', 'Update entities', 'locations', NOW()),
    ('entity.delete', 'Delete entities', 'locations', NOW()),

    -- ========================================================================
    -- SYSTEM/PERMISSIONS (16 permissions)
    -- ========================================================================
    ('permissions.view', 'View permissions', 'system', NOW()),
    ('permissions.create', 'Create permissions', 'system', NOW()),
    ('permissions.update', 'Update permissions', 'system', NOW()),
    ('permissions.delete', 'Delete permissions', 'system', NOW()),
    ('roles.view', 'View roles', 'system', NOW()),
    ('roles.create', 'Create roles', 'system', NOW()),
    ('roles.update', 'Update roles', 'system', NOW()),
    ('roles.delete', 'Delete roles', 'system', NOW()),
    ('roles.assign_permissions', 'Assign role permissions', 'system', NOW()),
    ('user_permissions.view', 'View user permissions', 'system', NOW()),
    ('user_permissions.grant', 'Grant user permissions', 'system', NOW()),
    ('user_permissions.revoke', 'Revoke user permissions', 'system', NOW()),
    ('user_permissions.update', 'Update user permissions', 'system', NOW()),
    ('user_permissions.cleanup', 'Cleanup user permissions', 'system', NOW()),
    ('permissions.audit', 'Audit permissions', 'system', NOW()),
    ('permissions.analytics', 'View permission analytics', 'system', NOW()),

    -- ========================================================================
    -- FUNCIONARIO (4 permissions)
    -- ========================================================================
    ('funcionario_verificacion.read_all', 'Read all funcionario verifications', 'funcionario', NOW()),
    ('funcionario_verificacion.process', 'Process funcionario verifications', 'funcionario', NOW()),
    ('funcionario_verificacion.view_stats', 'View funcionario statistics', 'funcionario', NOW()),
    ('funcionario_verificacion.export', 'Export funcionario data', 'funcionario', NOW()),

    -- ========================================================================
    -- MENU (13 permissions)
    -- ========================================================================
    ('menu.view_templates', 'View menu templates', 'menu', NOW()),
    ('menu.create_template', 'Create menu templates', 'menu', NOW()),
    ('menu.update_template', 'Update menu templates', 'menu', NOW()),
    ('menu.delete_template', 'Delete menu templates', 'menu', NOW()),
    ('menu.view_mappings', 'View menu mappings', 'menu', NOW()),
    ('menu.create_mapping', 'Create menu mappings', 'menu', NOW()),
    ('menu.update_mapping', 'Update menu mappings', 'menu', NOW()),
    ('menu.delete_mapping', 'Delete menu mappings', 'menu', NOW()),
    ('menu.view_role_config', 'View role menu config', 'menu', NOW()),
    ('menu.update_role_config', 'Update role menu config', 'menu', NOW()),
    ('menu.view_dashboard_config', 'View dashboard config', 'menu', NOW()),
    ('menu.update_dashboard_config', 'Update dashboard config', 'menu', NOW()),
    ('menu.manage', 'Manage menus', 'menu', NOW())

ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- VERIFICATION: Compte des permissions après insertion
-- ============================================================================
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM permissions;
    RAISE NOTICE 'Total permissions after sync: %', v_count;
END $$;

COMMIT;

-- ============================================================================
-- VERIFICATION QUERY (à exécuter séparément pour vérifier)
-- ============================================================================
-- SELECT
--     'Backend permissions synced' AS status,
--     COUNT(*) AS total_permissions
-- FROM permissions
-- WHERE name IN (
--     'treasury.validate_payment',
--     'service_request.view_queue',
--     'declaration.view',
--     'agent.view'
-- );
