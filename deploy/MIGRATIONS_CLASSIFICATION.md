# Migrations classification — Phase C

Source: `packages/backend/database/migrations/` (319 files)

## Summary

| Category | Count | Share |
|---|---|---|
| DDL | 73 | 22.9% |
| DML | 77 | 24.1% |
| MIXED | 165 | 51.7% |
| EMPTY | 4 | 1.3% |

## Tables receiving INSERT/UPDATE statements (seed extraction candidates)

Sorted by number of migrations that touch each table.

| Table | # migrations | Action |
|---|---|---|
| `role_permissions` | 59 | **SEED candidate** |
| `permissions` | 42 | **SEED candidate** |
| `email_templates` | 11 | **SEED candidate** |
| `sms_templates` | 10 | **SEED candidate** |
| `roles` | 9 | **SEED candidate** |
| `entities` | 5 | **SEED candidate** |
| `push_templates` | 5 | **SEED candidate** |
| `dashboard_registrations` | 5 | **SEED candidate** |
| `appointment_holds` | 4 | **SEED candidate** |
| `notification_templates` | 4 | **SEED candidate** |
| `workflow_menu_mapping` | 4 | **SEED candidate** |
| `audit_logs` | 4 | **SEED candidate** |
| `workflows` | 3 | **SEED candidate** |
| `appointment_delay_rules` | 3 | **SEED candidate** |
| `appointment_slot_configs` | 3 | **SEED candidate** |
| `entity_locations` | 3 | **SEED candidate** |
| `translations` | 3 | **SEED candidate** |
| `valid_workflow_codes` | 3 | **SEED candidate** |
| `system_rules` | 3 | **SEED candidate** |
| `appointment_reservations` | 2 | **SEED candidate** |
| `cities` | 2 | **SEED candidate** |
| `export_templates` | 2 | **SEED candidate** |
| `agent_profiles` | 2 | **SEED candidate** |
| `workflow_display_config` | 2 | **SEED candidate** |
| `service_request_history` | 2 | **SEED candidate** |
| `service_bundles` | 2 | **SEED candidate** |
| `service_bundle_items` | 2 | **SEED candidate** |
| `ussd_configurations` | 1 | **SEED candidate** |
| `communication_provider_settings` | 1 | **SEED candidate** |
| `workflow_document_requirements` | 1 | **SEED candidate** |
| `workflow_tariffs` | 1 | **SEED candidate** |
| `workflow_supplement_config` | 1 | **SEED candidate** |
| `tariff_supplements` | 1 | **SEED candidate** |
| `gemini_processing_logs` | 1 | **SEED candidate** |
| `notification_log` | 1 | **SEED candidate** |
| `appointment_blocked_dates` | 1 | **SEED candidate** |
| `queue` | 1 | **SEED candidate** |
| `document_verification_config` | 1 | **SEED candidate** |
| `verification_queue` | 1 | **SEED candidate** |
| `workflow_code_mapping` | 1 | **SEED candidate** |
| ... (18 more) | | |

## Recommended seed extraction shortlist

Tables that are reference/configuration data (not user-generated). Extract these into `database/seeds/` so a fresh DB is operational without replaying 319 migrations.

| Priority | Table | Touched by N migrations |
|---|---|---|
| HIGH | `permissions` | 42  |
| HIGH | `roles` | 9  |
| HIGH | `role_permissions` | 59  |
| HIGH | `categories` | 0 (no INSERT found) |
| HIGH | `ministries` | 1  |
| HIGH | `sectors` | 0 (no INSERT found) |
| HIGH | `fiscal_services` | 1  |
| HIGH | `service_keywords` | 0 (no INSERT found) |
| HIGH | `service_document_assignments` | 0 (no INSERT found) |
| HIGH | `service_procedure_assignments` | 0 (no INSERT found) |
| HIGH | `procedure_templates` | 0 (no INSERT found) |
| HIGH | `procedure_template_steps` | 0 (no INSERT found) |
| HIGH | `document_templates` | 0 (no INSERT found) |
| HIGH | `translations` | 3  |
| HIGH | `entity_translations` | 0 (no INSERT found) |
| HIGH | `workflow_menu_mapping` | 4  |

## Per-file detail

| Filename | Category | DDL | DML | DO | Notes |
|---|---|---|---|---|---|
| `010_communications_module.sql` | DDL | 44 | 0 | 0 |  |
| `012_seed_sms_templates.sql` | MIXED | 2 | 5 | 0 | INSERTs on: sms_templates |
| `013_seed_ussd_configs.sql` | MIXED | 0 | 2 | 1 | INSERTs on: ussd_configurations |
| `014_create_communication_provider_settings.sql` | MIXED | 8 | 4 | 1 | INSERTs on: communication_provider_settings |
| `015_add_password_changed_sms_template.sql` | DML | 0 | 2 | 0 | INSERTs on: email_templates, sms_templates |
| `016_email_templates_add_html_content.sql` | DDL | 4 | 0 | 0 |  |
| `017_update_password_changed_sms_add_user_name.sql` | DML | 0 | 1 | 0 |  |
| `018_add_sms_notifications_column.sql` | MIXED | 2 | 1 | 0 |  |
| `020_service_requests_base.sql` | MIXED | 33 | 1 | 2 | INSERTs on: permissions |
| `021_workflow_document_requirements.sql` | MIXED | 23 | 1 | 1 | INSERTs on: permissions |
| `022_workflow_tariffs.sql` | MIXED | 32 | 1 | 0 | INSERTs on: permissions |
| `023_seed_workflow_documents.sql` | DML | 0 | 14 | 0 | INSERTs on: workflow_document_requirements |
| `024_seed_workflow_tariffs.sql` | DML | 0 | 13 | 0 | INSERTs on: tariff_supplements, workflow_supplement_config, workflow_tariffs |
| `025_add_tariff_type_column.sql` | MIXED | 13 | 2 | 0 |  |
| `026_gemini_processing_audit.sql` | DDL | 31 | 0 | 0 | INSERTs on: gemini_processing_logs |
| `027_notification_log.sql` | MIXED | 25 | 1 | 0 | INSERTs on: notification_log, permissions |
| `028_workflows_and_appointments.sql` | MIXED | 47 | 4 | 0 | INSERTs on: appointment_blocked_dates, appointment_delay_rules, appointment_slot_configs... |
| `029_appointment_holds_and_bata_locations.sql` | MIXED | 24 | 15 | 0 | INSERTs on: appointment_delay_rules, appointment_holds, appointment_reservations... |
| `030_entity_locations.sql` | MIXED | 71 | 15 | 1 | INSERTs on: appointment_holds, entity_locations |
| `031_cities_table.sql` | MIXED | 13 | 4 | 2 | INSERTs on: cities, entities |
| `033_payment_method_drop_translations.sql` | DDL | 2 | 0 | 0 |  |
| `034_payment_anomalies.sql` | MIXED | 25 | 1 | 0 | INSERTs on: permissions |
| `034b_alter_payment_anomalies.sql` | MIXED | 2 | 1 | 1 |  |
| `035_treasury_exports.sql` | MIXED | 20 | 2 | 0 | INSERTs on: export_templates, permissions |
| `036_treasury_kpis_view.sql` | MIXED | 24 | 1 | 0 | INSERTs on: permissions |
| `036b_replace_kpis_view.sql` | DDL | 11 | 0 | 0 |  |
| `037_treasury_permissions.sql` | DML | 0 | 5 | 0 | INSERTs on: permissions, role_permissions, roles |
| `038_anomaly_types_extension.sql` | MIXED | 13 | 0 | 3 |  |
| `039_event_notification_templates.sql` | DML | 0 | 28 | 0 | INSERTs on: email_templates, notification_templates, push_templates... |
| `040_verification_status.sql` | MIXED | 36 | 6 | 2 | INSERTs on: document_verification_config, permissions, queue... |
| `041_drop_fiscal_service_code_from_payments.sql` | MIXED | 23 | 0 | 1 |  |
| `042_fix_calculate_payment_ministry_trigger.sql` | MIXED | 3 | 0 | 1 |  |
| `043_fix_payment_type_constraint.sql` | MIXED | 2 | 0 | 1 |  |
| `044_add_check_to_payment_method_enum.sql` | MIXED | 0 | 0 | 2 |  |
| `045_fix_trigger_respect_processor_values.sql` | MIXED | 1 | 0 | 1 |  |
| `046a_verificacion_funcionario_add_column.sql` | MIXED | 13 | 0 | 1 |  |
| `046b_verificacion_funcionario_views.sql` | MIXED | 6 | 3 | 0 |  |
| `046c_views_and_functions.sql` | MIXED | 6 | 3 | 0 |  |
| `047_rbac_phase1_entities_agents.sql` | MIXED | 30 | 0 | 1 |  |
| `048_complete_agent_architecture_migration.sql` | MIXED | 62 | 12 | 0 | INSERTs on: agent_profiles |
| `049_cleanup_deprecated_agent_columns.sql` | MIXED | 55 | 0 | 2 |  |
| `050_recreate_agent_views.sql` | DDL | 22 | 0 | 0 |  |
| `051_drop_deprecated_tables.sql` | MIXED | 52 | 0 | 3 |  |
| `052_assignments_agent_profile_migration.sql` | MIXED | 17 | 3 | 1 |  |
| `053_assignments_unification.sql` | MIXED | 40 | 0 | 1 |  |
| `054_workloads_agent_profile_consolidation.sql` | MIXED | 13 | 4 | 4 |  |
| `055_agent_rbac_roles.sql` | MIXED | 2 | 13 | 0 | INSERTs on: permissions, role_permissions, roles |
| `056_entities_workflow_codes.sql` | MIXED | 14 | 10 | 0 | INSERTs on: entities |
| `057_normalize_workflow_codes.sql` | MIXED | 4 | 4 | 4 | INSERTs on: workflow_code_mapping |
| `058_entities_rbac_restructure.sql` | MIXED | 3 | 28 | 1 | INSERTs on: entities, permissions, role_permissions... |
| `060_fix_entity_agent_ministry_constraint.sql` | MIXED | 3 | 0 | 1 |  |
| `062_treasury_roles_unified.sql` | MIXED | 1 | 4 | 0 | INSERTs on: permissions, role_permissions, roles |
| `063_role_menu_dashboard_config.sql` | MIXED | 33 | 2 | 0 | INSERTs on: workflow_menu_mapping |
| `064_seed_workflow_based_menu_configs.sql` | DML | 0 | 6 | 0 | INSERTs on: menu_templates |
| `065_supervisor_escalation_menus.sql` | MIXED | 2 | 4 | 0 | INSERTs on: permissions, role_permissions |
| `066_remove_queue_lock_columns.sql` | MIXED | 7 | 0 | 1 |  |
| `067_remove_locked_by_agent_workflow.sql` | MIXED | 3 | 1 | 2 |  |
| `068_drop_lock_columns.sql` | MIXED | 9 | 0 | 2 |  |
| `069_complete_notification_templates.sql` | DML | 0 | 24 | 0 | INSERTs on: email_templates, notification_templates, push_templates... |
| `070_email_templates_html_content.sql` | DML | 0 | 18 | 0 |  |
| `075_add_verified_identifiers_permissions.sql` | MIXED | 0 | 4 | 1 | INSERTs on: permissions, role_permissions |
| `076_assign_view_performance_to_agents.sql` | MIXED | 0 | 3 | 2 | INSERTs on: permissions, role_permissions |
| `077_populate_workflow_config_pasaporte.sql` | DML | 0 | 5 | 0 |  |
| `078_add_appointments_menu_to_agents.sql` | DML | 0 | 15 | 0 | INSERTs on: role_permissions, roles |
| `079_add_appointment_status_columns.sql` | DDL | 7 | 0 | 0 |  |
| `080_seed_identifier_type_translations.sql` | MIXED | 0 | 3 | 1 | INSERTs on: translations |
| `081_add_numero_seguridad_social_identifier.sql` | MIXED | 2 | 2 | 1 | INSERTs on: translations |
| `082_add_verification_permissions_to_agents.sql` | DML | 0 | 6 | 0 | INSERTs on: role_permissions |
| `083_create_identifiers_permissions.sql` | DML | 0 | 5 | 0 | INSERTs on: permissions, role_permissions |
| `085_enable_auto_menu_generation_phase1.sql` | MIXED | 1 | 2 | 1 | INSERTs on: _backup_role_menu_config_phase1 |
| `086_drop_menu_templates_table.sql` | MIXED | 3 | 0 | 1 |  |
| `087_create_workflow_display_config.sql` | MIXED | 9 | 1 | 0 | INSERTs on: workflow_display_config |
| `088_workflow_display_config_exact_code.sql` | MIXED | 7 | 1 | 2 |  |
| `089_add_file_hash_to_srd.sql` | DDL | 3 | 0 | 0 |  |
| `090_add_missing_assignment_permissions.sql` | DML | 0 | 3 | 0 | INSERTs on: permissions, role_permissions |
| `091_add_entity_code_to_delay_rules.sql` | MIXED | 5 | 4 | 0 | INSERTs on: appointment_delay_rules |
| `092_fix_get_available_slots_v2.sql` | DDL | 2 | 0 | 0 |  |
| `093_optimize_available_slots_v3.sql` | DDL | 2 | 0 | 0 |  |
| `094_fix_hold_appointment_expires_at_ambiguity.sql` | MIXED | 1 | 3 | 0 | INSERTs on: appointment_holds |
| `095_fix_service_payments_agent_columns.sql` | DDL | 9 | 0 | 0 |  |
| `096_fix_confirm_hold_missing_reservation.sql` | MIXED | 4 | 4 | 0 | INSERTs on: appointment_reservations |
| `097_payment_sla_partial_index.sql` | MIXED | 1 | 1 | 0 |  |
| `098_citizen_last_viewed_at.sql` | DDL | 2 | 0 | 0 |  |
| `099_residencia_phase2_cnedoge.sql` | DML | 0 | 2 | 0 |  |
| `100_batch_service_requests.sql` | MIXED | 20 | 1 | 0 | INSERTs on: permissions |
| `101_assign_batch_requests_permissions.sql` | DML | 0 | 4 | 0 | INSERTs on: role_permissions |
| `102_fix_batch_reference_race_condition.sql` | DDL | 4 | 0 | 0 |  |
| `103_complete_workflow_menu_display_config.sql` | DML | 0 | 2 | 0 | INSERTs on: workflow_menu_mapping |
| `104_site_based_routing.sql` | MIXED | 5 | 2 | 1 |  |
| `106_fix_available_slots_time_generation.sql` | DDL | 2 | 0 | 0 |  |
| `107_add_gin_index_workflow_codes.sql` | MIXED | 1 | 0 | 1 |  |
| `108_cleanup_orphaned_menu_permissions.sql` | DML | 0 | 2 | 0 |  |
| `109_seed_visado_individual_mappings.sql` | DML | 0 | 1 | 0 | INSERTs on: workflow_menu_mapping |
| `110_add_include_batch_column.sql` | MIXED | 1 | 3 | 0 |  |
| `111_cleanup_placeholder_display_configs.sql` | MIXED | 0 | 1 | 1 |  |
| `112_seed_curated_display_configs.sql` | MIXED | 0 | 1 | 1 | INSERTs on: workflow_display_config |
| `113_add_escalation_to_service_requests.sql` | DDL | 6 | 0 | 0 |  |
| `114_escalation_hardening.sql` | MIXED | 5 | 1 | 0 |  |
| `115_custom_sub_items.sql` | MIXED | 1 | 1 | 0 |  |
| `116_fix_supervisor_permissions_and_menu.sql` | DML | 0 | 4 | 0 | INSERTs on: permissions, role_permissions |
| `117_create_escalation_permissions.sql` | DML | 0 | 1 | 0 | INSERTs on: permissions |
| `118_backfill_entity_locations_entity_id.sql` | MIXED | 0 | 1 | 1 |  |
| `119_assign_orphan_treasury_payments.sql` | MIXED | 0 | 1 | 1 |  |
| `120_restructure_tesoro_permissions_and_menus.sql` | MIXED | 0 | 6 | 1 | INSERTs on: role_permissions |
| `121_backfill_tesoro_locations_entity_id.sql` | MIXED | 0 | 1 | 1 |  |
| `122_fix_tesoro_agent_permissions.sql` | MIXED | 0 | 2 | 1 | INSERTs on: role_permissions |
| `123_fix_tesoro_menu_and_permissions.sql` | MIXED | 0 | 3 | 1 |  |
| `124_batch_grouping_and_escalation.sql` | MIXED | 2 | 1 | 1 |  |
| `125_update_tesoro_dashboard_config.sql` | DML | 0 | 1 | 0 |  |
| `126_backfill_treasury_assignments_audit.sql` | DML | 0 | 5 | 0 | INSERTs on: payment_validation_audit |
| `127_complete_notification_templates.sql` | DML | 0 | 19 | 0 | INSERTs on: email_templates, sms_templates |
| `128_add_logo_to_email_templates.sql` | EMPTY | 0 | 0 | 0 |  |
| `129_add_references_to_payment_email_templates.sql` | EMPTY | 0 | 0 | 0 |  |
| `130_assignment_outbox.sql` | DDL | 5 | 0 | 0 |  |
| `131_entity_code_queue_and_priority_weight.sql` | MIXED | 5 | 6 | 0 |  |
| `132_fix_queue_constraints.sql` | MIXED | 3 | 0 | 1 |  |
| `133_recreate_queue_view_entity_code.sql` | DDL | 3 | 0 | 0 |  |
| `134_backfill_entity_code_and_enqueue.sql` | DML | 0 | 3 | 0 | INSERTs on: assignment_outbox |
| `135_agent_workflow_proficiency.sql` | DDL | 4 | 0 | 0 |  |
| `136_fix_priority_trigger_add_complexity.sql` | MIXED | 4 | 2 | 0 |  |
| `137_drop_agent_role_column.sql` | MIXED | 15 | 0 | 1 |  |
| `138_add_default_agent_config_to_roles.sql` | MIXED | 2 | 2 | 0 |  |
| `139_assign_admin_dashboard_permissions.sql` | MIXED | 0 | 0 | 1 | INSERTs on: role_permissions |
| `140_create_supervisor_roles_per_entity.sql` | MIXED | 0 | 2 | 1 | INSERTs on: role_permissions, roles |
| `141_drop_dead_lock_functions.sql` | DDL | 5 | 0 | 0 |  |
| `142_add_missing_supervisor_permissions.sql` | DML | 0 | 1 | 0 | INSERTs on: role_permissions |
| `143_fix_treasury_legacy_views_and_export.sql` | MIXED | 4 | 1 | 0 |  |
| `144_add_treasury_analyst_menu.sql` | DML | 0 | 2 | 0 |  |
| `145_remove_locked_by_agent_from_enum.sql` | MIXED | 41 | 6 | 2 |  |
| `146_add_entity_code_to_service_payments.sql` | MIXED | 6 | 3 | 2 |  |
| `147_refactor_treasury_views_entity_code.sql` | MIXED | 15 | 0 | 1 |  |
| `148_treasury_performance_indexes.sql` | MIXED | 3 | 0 | 1 |  |
| `149_add_monitoring_permission.sql` | MIXED | 0 | 2 | 1 | INSERTs on: permissions, role_permissions |
| `150_cleanup_agent_workloads_legacy.sql` | MIXED | 1 | 0 | 1 |  |
| `151_ops_center_performance_indexes.sql` | DDL | 2 | 0 | 0 |  |
| `152_treasury_completed_index.sql` | DDL | 1 | 0 | 0 |  |
| `153_agent_tesoro_dashboard_redirect.sql` | DML | 0 | 1 | 0 |  |
| `154_supervisor_tesoro_dashboard_treasury.sql` | DML | 0 | 2 | 0 |  |
| `155_revert_supervisor_dashboard_to_supervisor.sql` | DML | 0 | 1 | 0 |  |
| `156_backfill_action_duration_seconds.sql` | DML | 0 | 1 | 0 |  |
| `157_fix_agent_performance_stats_pk.sql` | MIXED | 5 | 2 | 0 | INSERTs on: agent_performance_stats |
| `158_workload_performance_indexes_mv.sql` | DDL | 9 | 0 | 0 |  |
| `159_remove_performance_menu_item.sql` | DML | 0 | 1 | 0 |  |
| `160_add_webhook_view_to_supervisor_tesoro.sql` | DML | 0 | 1 | 0 | INSERTs on: role_permissions |
| `161_add_webhook_update_to_supervisor_tesoro.sql` | DML | 0 | 1 | 0 | INSERTs on: role_permissions |
| `162_migrate_payment_fks_to_service_payments.sql` | DDL | 14 | 0 | 0 |  |
| `163_cleanup_legacy_payment_index.sql` | DDL | 1 | 0 | 0 |  |
| `164_add_bank_transaction_id_to_service_payments.sql` | MIXED | 2 | 1 | 0 |  |
| `165_fix_legacy_reconciliation_views.sql` | DDL | 7 | 0 | 0 |  |
| `167_payment_architecture_coherence.sql` | MIXED | 13 | 7 | 0 |  |
| `168_remove_performance_from_tesoro_menu.sql` | DML | 0 | 1 | 0 |  |
| `169_mpgs_gateway_config.sql` | DDL | 2 | 0 | 0 |  |
| `170_export_templates_multilingual.sql` | MIXED | 1 | 4 | 0 | INSERTs on: export_templates |
| `171_analyst_performance_indexes.sql` | DDL | 2 | 0 | 0 |  |
| `172_fix_validated_by_agent_id.sql` | MIXED | 1 | 3 | 0 |  |
| `173_agent_query_logs.sql` | DDL | 8 | 0 | 0 |  |
| `174_agent_query_logs_embedding.sql` | DDL | 3 | 0 | 0 |  |
| `175_analyst_ask_permission.sql` | MIXED | 0 | 1 | 1 | INSERTs on: permissions, role_permissions |
| `176_fix_analyst_ask_missing_roles.sql` | MIXED | 0 | 1 | 1 | INSERTs on: role_permissions |
| `177_add_treasury_entity_type.sql` | MIXED | 0 | 1 | 1 |  |
| `178_fix_orphan_appointments_expired_requests.sql` | DML | 0 | 3 | 0 | INSERTs on: service_request_history |
| `179_fix_supervisor_tesoro_menu_urls.sql` | DML | 0 | 1 | 0 |  |
| `180_add_composite_indexes_scalability.sql` | DDL | 5 | 0 | 0 |  |
| `181_create_materialized_view_services_translated.sql` | DDL | 8 | 0 | 0 |  |
| `182_cleanup_pasaporte_nuevo_display_config.sql` | DML | 0 | 1 | 0 |  |
| `183_workflow_code_production_hardening.sql` | MIXED | 6 | 2 | 2 | INSERTs on: app_migrations, valid_workflow_codes |
| `184_fix_workflow_menu_mapping_title_keys.sql` | DML | 0 | 5 | 0 |  |
| `185_backfill_submitted_at.sql` | DML | 0 | 1 | 0 |  |
| `186_sla_submitted_at_trigger.sql` | MIXED | 3 | 1 | 0 |  |
| `187_auth_security_hardening.sql` | MIXED | 5 | 3 | 0 |  |
| `188_fix_last_failed_ip_to_inet.sql` | DDL | 2 | 0 | 0 |  |
| `189_auth_cleanup_expired_tokens.sql` | MIXED | 1 | 1 | 0 |  |
| `190_add_last_attempt_at_pending_registrations.sql` | DDL | 2 | 0 | 0 |  |
| `191_auth_hotpath_indexes.sql` | DDL | 5 | 0 | 0 |  |
| `192_create_permissions_views.sql` | MIXED | 4 | 2 | 0 | INSERTs on: role_permissions |
| `193_cleanup_duplicate_roles.sql` | MIXED | 0 | 6 | 1 | INSERTs on: role_permissions |
| `194_scoped_admin_roles.sql` | DML | 0 | 9 | 0 | INSERTs on: permissions, role_permissions, roles |
| `195_agent_trade_presets.sql` | DML | 0 | 9 | 0 | INSERTs on: role_permissions, roles |
| `196_fix_admin_privilege_inversion.sql` | DML | 0 | 8 | 0 | INSERTs on: permissions, role_permissions |
| `197_fix_business_role_permissions.sql` | DML | 0 | 1 | 0 | INSERTs on: role_permissions |
| `198_role_hierarchy_and_audit_triggers.sql` | MIXED | 11 | 1 | 1 | INSERTs on: audit_logs |
| `199_permission_scoping_and_cache_events.sql` | DDL | 13 | 0 | 0 |  |
| `200_effective_permissions_materialized_view.sql` | DDL | 5 | 0 | 0 |  |
| `201_fix_supervisor_permissions_and_config.sql` | MIXED | 0 | 4 | 1 | INSERTs on: role_permissions |
| `202_fiscal_services_schema_optimization.sql` | MIXED | 15 | 1 | 0 | INSERTs on: fiscal_service_pricing |
| `203_service_bundles_and_zones.sql` | MIXED | 25 | 0 | 1 |  |
| `204_seed_commerce_zones_and_bundles.sql` | MIXED | 0 | 23 | 3 | INSERTs on: commerce_zones, service_bundle_items, service_bundles |
| `205_service_bundle_permissions.sql` | DML | 0 | 3 | 0 | INSERTs on: permissions, role_permissions |
| `206_correct_bundle_seed_data.sql` | DML | 0 | 62 | 0 | INSERTs on: fiscal_services, ministries, service_bundle_items... |
| `214_workflow_translations.sql` | DML | 0 | 9 | 0 | INSERTs on: translations |
| `215_enrichment_queue.sql` | MIXED | 8 | 1 | 0 |  |
| `216_enrichment_critical_fixes.sql` | MIXED | 3 | 1 | 0 |  |
| `217_description_visible_ministry_source.sql` | MIXED | 6 | 1 | 0 |  |
| `218_bundle_workflow_foundations.sql` | MIXED | 95 | 29 | 2 | INSERTs on: cities, entities, entity_locations... |
| `219_add_bundle_license_permissions.sql` | DML | 0 | 2 | 0 | INSERTs on: permissions, role_permissions |
| `220_license_notification_templates.sql` | DML | 0 | 2 | 0 | INSERTs on: email_templates, sms_templates |
| `221_fix_sl_sa_regimen_fiscal.sql` | MIXED | 0 | 4 | 2 |  |
| `222_fix_routing_view_and_config_trigger.sql` | MIXED | 3 | 0 | 1 |  |
| `223_critical_missing_indexes.sql` | DDL | 7 | 0 | 0 |  |
| `224_oms_performance_indexes.sql` | DDL | 7 | 0 | 0 |  |
| `225_company_permissions_and_indexes.sql` | MIXED | 4 | 9 | 0 | INSERTs on: permissions, role_permissions |
| `226_company_entity_scoped_permission.sql` | DML | 0 | 5 | 0 | INSERTs on: permissions, role_permissions |
| `227_fix_oms_permissions_assignment.sql` | DML | 0 | 3 | 0 | INSERTs on: permissions, role_permissions |
| `228_fix_vector_indexes_and_rag.sql` | DDL | 3 | 0 | 0 |  |
| `229_chatbot_conversations.sql` | DDL | 3 | 0 | 0 |  |
| `230_company_classification_agent.sql` | MIXED | 12 | 1 | 1 | INSERTs on: permissions, role_permissions |
| `231_add_draft_license_fk.sql` | MIXED | 0 | 0 | 1 |  |
| `232_fix_classification_permissions_metadata.sql` | DML | 0 | 2 | 0 |  |
| `233_nif_normalization.sql` | MIXED | 6 | 4 | 0 |  |
| `234_company_fulltext_search.sql` | DDL | 10 | 0 | 0 |  |
| `235_company_dashboard_views.sql` | DDL | 10 | 0 | 0 |  |
| `236_fix_company_role_check_constraint.sql` | DDL | 1 | 0 | 0 |  |
| `237_company_menu_config.sql` | DML | 0 | 3 | 0 | INSERTs on: workflow_menu_mapping |
| `238_fix_bundle_permissions_assignment.sql` | MIXED | 0 | 4 | 1 | INSERTs on: role_permissions |
| `239_assign_company_permissions.sql` | MIXED | 0 | 0 | 1 | INSERTs on: role_permissions |
| `240_company_analytics_mv.sql` | DDL | 3 | 0 | 0 |  |
| `241_fix_global_stats_mv.sql` | DDL | 3 | 0 | 0 |  |
| `242_fix_zone_stats_mv.sql` | DDL | 3 | 0 | 0 |  |
| `243_fix_supervisor_menus_permissions.sql` | MIXED | 0 | 2 | 2 | INSERTs on: role_permissions |
| `244_cleanup_dead_oms_menus.sql` | EMPTY | 0 | 0 | 0 |  |
| `245_oms_permissions_and_menus.sql` | EMPTY | 0 | 0 | 0 |  |
| `246_oms_reminders_and_assignment_index.sql` | MIXED | 8 | 1 | 1 | INSERTs on: email_templates |
| `247_fix_oms_menu_configs.sql` | MIXED | 0 | 4 | 1 |  |
| `248_fix_oms_polyvalent_permissions.sql` | MIXED | 0 | 1 | 1 | INSERTs on: role_permissions |
| `249_field_inspections.sql` | MIXED | 9 | 8 | 0 | INSERTs on: email_templates, notification_templates, permissions... |
| `250_field_collection_columns.sql` | DDL | 6 | 0 | 0 |  |
| `251_field_collection_reconciliation.sql` | MIXED | 1 | 2 | 0 | INSERTs on: permissions, role_permissions |
| `252_fix_cascade_delete_security.sql` | DDL | 6 | 0 | 0 |  |
| `253_rbc_calculation_history.sql` | MIXED | 6 | 1 | 0 | INSERTs on: extraction_schemas |
| `254_city_and_appointment_holds.sql` | MIXED | 23 | 8 | 1 | INSERTs on: appointment_holds, appointment_slot_configs |
| `255_cleanup_generic_workflows_and_sync_tariffs.sql` | DDL | 12 | 0 | 0 |  |
| `256_pending_registrations_metadata.sql` | MIXED | 3 | 0 | 1 |  |
| `257_sync_backend_permissions.sql` | MIXED | 0 | 1 | 1 | INSERTs on: permissions |
| `258_assign_treasury_role_permissions.sql` | MIXED | 0 | 0 | 4 | INSERTs on: role_permissions |
| `259_assign_agent_stats_permission.sql` | DML | 0 | 2 | 0 | INSERTs on: role_permissions |
| `260_fix_document_verification_config.sql` | MIXED | 6 | 14 | 0 |  |
| `261_appointment_rescheduled_templates.sql` | DML | 0 | 4 | 0 | INSERTs on: email_templates, notification_templates, push_templates... |
| `262_sync_agent_permissions_and_menus.sql` | MIXED | 0 | 6 | 2 | INSERTs on: permissions, role_permissions |
| `263_update_valid_city_constraint.sql` | DDL | 2 | 0 | 0 |  |
| `264_fix_supervisor_tesoro_menu.sql` | DML | 0 | 1 | 0 |  |
| `265_reduce_display_config_splitview.sql` | DML | 0 | 24 | 0 |  |
| `266_resolve_workflow_codes_existing.sql` | DML | 0 | 11 | 0 |  |
| `267_fix_classification_permission_names.sql` | DML | 0 | 4 | 0 |  |
| `268_public_installment_visible.sql` | DDL | 2 | 0 | 0 |  |
| `269_split_process_obligations_permission.sql` | DML | 0 | 3 | 0 | INSERTs on: permissions, role_permissions |
| `270_oms_entities_and_locations.sql` | MIXED | 2 | 4 | 1 | INSERTs on: entities, entity_locations |
| `271_remove_mixto_from_schema.sql` | MIXED | 7 | 0 | 1 |  |
| `272_oms_agent_roles_and_profiles.sql` | MIXED | 0 | 11 | 1 | INSERTs on: agent_profiles, permissions, role_permissions... |
| `273_register_bundle_payment_workflow.sql` | DML | 0 | 5 | 0 | INSERTs on: workflows |
| `274_add_missing_indexes_audit.sql` | DDL | 10 | 0 | 0 |  |
| `275_performance_critical_indexes.sql` | DDL | 6 | 0 | 0 |  |
| `276_permission_audit_cleanup_and_index.sql` | MIXED | 4 | 2 | 0 | INSERTs on: permission_audit_log_archive |
| `277_supervisor_field_operations.sql` | MIXED | 34 | 6 | 0 | INSERTs on: permissions, role_permissions, system_rules |
| `278_field_operations_automations.sql` | MIXED | 5 | 5 | 0 | INSERTs on: email_templates, system_rules |
| `279_fix_inspection_permission_assignments.sql` | MIXED | 2 | 3 | 0 | INSERTs on: role_permissions |
| `280_agent_live_status_tracking.sql` | MIXED | 11 | 2 | 0 | INSERTs on: system_rules |
| `281_chatbot_feedback.sql` | DDL | 6 | 0 | 0 |  |
| `282_chatbot_user_preferences.sql` | DDL | 2 | 0 | 0 |  |
| `283_cleanup_test_agents.sql` | DML | 0 | 1 | 0 | INSERTs on: audit_logs |
| `284_fix_verification_code_column_size.sql` | DDL | 1 | 0 | 0 |  |
| `285_fix_audit_trigger_fk_and_branding.sql` | DDL | 1 | 0 | 0 | INSERTs on: audit_logs |
| `286_add_device_push_token.sql` | DDL | 9 | 0 | 0 |  |
| `287_allow_field_payments_without_service_request.sql` | MIXED | 5 | 2 | 1 | INSERTs on: valid_workflow_codes, workflows |
| `287_user_documents_vault.sql` | MIXED | 28 | 0 | 1 |  |
| `288_migrate_existing_docs_to_vault.sql` | MIXED | 0 | 1 | 1 | INSERTs on: user_documents |
| `289_grant_service_request_view_to_oms_agents.sql` | MIXED | 0 | 3 | 1 | INSERTs on: role_permissions |
| `290_fix_batch_requests_permissions.sql` | DML | 0 | 4 | 0 | INSERTs on: permissions, role_permissions |
| `291_fix_bundle_dossier_linking.sql` | MIXED | 17 | 1 | 3 |  |
| `292_agent_executive_audit_log.sql` | DDL | 9 | 0 | 0 |  |
| `293_register_bundle_payment_in_valid_workflow_codes.sql` | MIXED | 0 | 1 | 1 | INSERTs on: valid_workflow_codes |
| `294_ayunt_camara_treasury_validation_menu.sql` | DML | 0 | 7 | 0 |  |
| `295_grant_queue_stats_to_bundle_agents.sql` | MIXED | 0 | 1 | 1 | INSERTs on: role_permissions |
| `296_fix_receipt_cosmetics.sql` | DML | 0 | 5 | 0 |  |
| `297_relax_bundle_sr_unique_index.sql` | DDL | 2 | 0 | 0 |  |
| `298_grant_treasury_view_to_ayunt_camara.sql` | MIXED | 0 | 0 | 1 | INSERTs on: role_permissions |
| `299_fix_min_dashboard_default_route.sql` | MIXED | 0 | 1 | 1 |  |
| `300_min_dashboard_entity_route.sql` | MIXED | 0 | 1 | 1 |  |
| `301_enrich_bundle_email_template.sql` | DML | 0 | 1 | 0 |  |
| `302_fix_oms_menu_config_and_dashboard.sql` | DML | 0 | 5 | 0 |  |
| `303_fix_oms_menu_config_v2.sql` | DML | 0 | 7 | 0 | INSERTs on: role_permissions |
| `304_oms_performance_indexes_and_timeout.sql` | DDL | 2 | 0 | 0 |  |
| `305_agent_work_queue_waiting_documents.sql` | MIXED | 1 | 0 | 1 |  |
| `306_restore_inspection_payment_menus.sql` | DML | 0 | 16 | 0 |  |
| `307_citizen_companies_indexes.sql` | DDL | 2 | 0 | 0 |  |
| `308_add_representante_legal_to_companies.sql` | MIXED | 3 | 1 | 0 |  |
| `309_citizen_alert_templates.sql` | DML | 0 | 3 | 0 | INSERTs on: email_templates, push_templates, sms_templates |
| `310_mission_notification_templates.sql` | DML | 0 | 3 | 0 | INSERTs on: email_templates, push_templates, sms_templates |
| `310_oms_agent_escalation_permissions.sql` | DML | 0 | 2 | 0 | INSERTs on: role_permissions |
| `311_add_certificate_url_to_licenses.sql` | DDL | 4 | 0 | 0 |  |
| `311_add_missions_menu_item.sql` | DML | 0 | 1 | 0 |  |
| `312_add_reminder_columns_to_obligations.sql` | DDL | 1 | 0 | 0 |  |
| `312_mission_templates.sql` | DDL | 6 | 0 | 0 |  |
| `313_users_soft_delete.sql` | DDL | 3 | 0 | 0 | INSERTs on: audit_logs |
| `314_companies_soft_delete_archive.sql` | MIXED | 5 | 3 | 1 | INSERTs on: permissions, role_permissions |
| `315_looker_readonly_role.sql` | MIXED | 37 | 0 | 1 |  |
| `316_dashboards_view_permission.sql` | DML | 0 | 2 | 0 | INSERTs on: permissions, role_permissions |
| `317_dashboard_registrations.sql` | MIXED | 7 | 2 | 0 | INSERTs on: dashboard_registrations, permissions, role_permissions |
| `319_dashboard_provider_dual.sql` | MIXED | 10 | 0 | 1 | INSERTs on: dashboard_registrations |
| `320_looker_enriched_views.sql` | DDL | 12 | 0 | 0 |  |
| `321_audit_inspections_channel_views.sql` | DDL | 12 | 0 | 0 |  |
| `322_treasury_by_site_view.sql` | DDL | 3 | 0 | 0 |  |
| `323_dashboards_metadata_dynamic.sql` | MIXED | 28 | 1 | 0 | INSERTs on: dashboard_registrations |
| `324_flip_legacy_dashboards_to_grafana.sql` | DML | 0 | 2 | 0 |  |
| `325_ai_call_metrics.sql` | DDL | 19 | 0 | 0 | INSERTs on: ai_call_metrics |
| `326_register_ai_observability_dashboard.sql` | DML | 0 | 1 | 0 | INSERTs on: dashboard_registrations |
| `327_ai_pricing_config.sql` | MIXED | 5 | 1 | 0 | INSERTs on: ai_pricing_config |
| `328_ai_call_metrics_injection.sql` | DDL | 9 | 0 | 0 |  |
| `329_request_telemetry.sql` | DDL | 14 | 0 | 0 |  |
| `330_register_security_dashboard.sql` | DML | 0 | 1 | 0 | INSERTs on: dashboard_registrations |
| `331_add_legal_acceptance_columns.sql` | MIXED | 5 | 1 | 0 |  |
| `332_fix_min_supervisor_dashboard_hrefs.sql` | MIXED | 0 | 1 | 1 |  |
| `333_treasury_exports_entity_denormalize.sql` | MIXED | 3 | 1 | 1 |  |
| `334_fix_agent_min_dashboard_hrefs.sql` | MIXED | 0 | 1 | 1 |  |
| `335_revert_334_agent_min_hrefs.sql` | MIXED | 0 | 1 | 1 |  |
| `336_create_schema_migrations.sql` | DDL | 4 | 0 | 0 |  |
| `add_funcionario_verification.sql` | MIXED | 30 | 4 | 1 | INSERTs on: permissions |
| `add_tsvector_to_fiscal_services.sql` | MIXED | 6 | 1 | 1 |  |
| `fix_submitted_status.sql` | MIXED | 0 | 2 | 2 | INSERTs on: service_request_history |
| `support_module.sql` | MIXED | 26 | 1 | 0 | INSERTs on: support_categories |

## Methodology

Each migration is parsed by stripping `--` and `/* */` comments, then split on `;`. The first keyword of each statement is matched against:

- **DDL**: CREATE, ALTER, DROP, TRUNCATE TABLE, GRANT, REVOKE, COMMENT, RENAME, REINDEX, CLUSTER
- **DML**: INSERT, UPDATE, DELETE, MERGE, COPY
- **DO blocks** (`DO $$ ... $$`) are counted separately. When present, the file is conservatively marked MIXED — the parser cannot inspect the body without a full SQL grammar.

Classification is heuristic, not strict — false positives (MIXED) on simple files with a DO block are acceptable. False negatives (DML missed in a DO block) are caught at Phase D when the baseline is generated and at Phase G during validation.