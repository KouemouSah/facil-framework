-- Migration: Seed USSD Configurations
-- Date: 2025-12-19
-- Description: Create default USSD configurations for GETESA and MUNI operators

-- =============================================================================
-- First, ensure unique constraint exists on operator_code for ON CONFLICT to work
-- =============================================================================

-- Create unique constraint if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ussd_configurations_operator_code_unique'
    ) THEN
        ALTER TABLE ussd_configurations
        ADD CONSTRAINT ussd_configurations_operator_code_unique UNIQUE (operator_code);
    END IF;
END $$;

-- =============================================================================
-- GETESA Configuration
-- =============================================================================

INSERT INTO ussd_configurations (
    operator_name,
    operator_code,
    short_code,
    api_endpoint,
    auth_config,
    menu_structure,
    session_timeout_seconds,
    max_input_length,
    is_active,
    created_at
) VALUES (
    'getesa',
    'GETESA_GQ',
    '*123#',
    'https://api.getesa.gq/ussd/v1',
    '{"type": "api_key", "header": "X-API-Key"}'::jsonb,
    '[
        {
            "id": "main",
            "title_es": "Bienvenido a TaxasGE",
            "title_fr": "Bienvenue sur TaxasGE",
            "title_en": "Welcome to TaxasGE",
            "is_root": true,
            "options": [
                {"key": "1", "label_es": "Consultar Saldo Fiscal", "label_fr": "Consulter Solde Fiscal", "label_en": "Check Tax Balance", "action": "balance"},
                {"key": "2", "label_es": "Estado de Declaracion", "label_fr": "Statut Declaration", "label_en": "Declaration Status", "action": "declaration_status"},
                {"key": "3", "label_es": "Pagar Impuesto", "label_fr": "Payer Impot", "label_en": "Pay Tax", "next_menu": "payment_menu"},
                {"key": "4", "label_es": "Buscar Servicio", "label_fr": "Rechercher Service", "label_en": "Search Service", "action": "service_search"},
                {"key": "5", "label_es": "Soporte", "label_fr": "Support", "label_en": "Support", "next_menu": "support_menu"}
            ]
        },
        {
            "id": "payment_menu",
            "title_es": "Seleccione tipo de pago",
            "title_fr": "Selectionnez le type de paiement",
            "title_en": "Select payment type",
            "is_root": false,
            "parent_menu": "main",
            "options": [
                {"key": "1", "label_es": "MTN Mobile Money", "label_fr": "MTN Mobile Money", "label_en": "MTN Mobile Money", "action": "payment", "action_params": {"method": "mtn_mobile_money"}},
                {"key": "2", "label_es": "BANGE", "label_fr": "BANGE", "label_en": "BANGE", "action": "payment", "action_params": {"method": "bange"}},
                {"key": "0", "label_es": "Volver", "label_fr": "Retour", "label_en": "Back", "next_menu": "main"}
            ]
        },
        {
            "id": "support_menu",
            "title_es": "Centro de Soporte",
            "title_fr": "Centre de Support",
            "title_en": "Support Center",
            "is_root": false,
            "parent_menu": "main",
            "options": [
                {"key": "1", "label_es": "Llamar al Soporte", "label_fr": "Appeler le Support", "label_en": "Call Support", "action": "support", "action_params": {"type": "call", "number": "+240222123456"}},
                {"key": "2", "label_es": "Enviar SMS", "label_fr": "Envoyer SMS", "label_en": "Send SMS", "action": "support", "action_params": {"type": "sms"}},
                {"key": "0", "label_es": "Volver", "label_fr": "Retour", "label_en": "Back", "next_menu": "main"}
            ]
        }
    ]'::jsonb,
    180,
    160,
    true,
    NOW()
) ON CONFLICT (operator_code) DO UPDATE SET
    menu_structure = EXCLUDED.menu_structure,
    updated_at = NOW();

-- =============================================================================
-- MUNI Configuration
-- =============================================================================

INSERT INTO ussd_configurations (
    operator_name,
    operator_code,
    short_code,
    api_endpoint,
    auth_config,
    menu_structure,
    session_timeout_seconds,
    max_input_length,
    is_active,
    created_at
) VALUES (
    'muni',
    'MUNI_GQ',
    '*456#',
    'https://api.muni.gq/ussd/v1',
    '{"type": "bearer", "token_endpoint": "/auth/token"}'::jsonb,
    '[
        {
            "id": "main",
            "title_es": "TaxasGE - Servicios Fiscales",
            "title_fr": "TaxasGE - Services Fiscaux",
            "title_en": "TaxasGE - Tax Services",
            "is_root": true,
            "options": [
                {"key": "1", "label_es": "Mi Saldo", "label_fr": "Mon Solde", "label_en": "My Balance", "action": "balance"},
                {"key": "2", "label_es": "Mis Declaraciones", "label_fr": "Mes Declarations", "label_en": "My Declarations", "next_menu": "declarations_menu"},
                {"key": "3", "label_es": "Realizar Pago", "label_fr": "Effectuer Paiement", "label_en": "Make Payment", "action": "payment"},
                {"key": "4", "label_es": "Servicios Disponibles", "label_fr": "Services Disponibles", "label_en": "Available Services", "action": "service_search"},
                {"key": "5", "label_es": "Ayuda", "label_fr": "Aide", "label_en": "Help", "action": "support"}
            ]
        },
        {
            "id": "declarations_menu",
            "title_es": "Mis Declaraciones",
            "title_fr": "Mes Declarations",
            "title_en": "My Declarations",
            "is_root": false,
            "parent_menu": "main",
            "options": [
                {"key": "1", "label_es": "Declaraciones Pendientes", "label_fr": "Declarations en Attente", "label_en": "Pending Declarations", "action": "declaration_status", "action_params": {"filter": "pending"}},
                {"key": "2", "label_es": "Declaraciones Aprobadas", "label_fr": "Declarations Approuvees", "label_en": "Approved Declarations", "action": "declaration_status", "action_params": {"filter": "approved"}},
                {"key": "3", "label_es": "Todas las Declaraciones", "label_fr": "Toutes les Declarations", "label_en": "All Declarations", "action": "declaration_status", "action_params": {"filter": "all"}},
                {"key": "0", "label_es": "Volver", "label_fr": "Retour", "label_en": "Back", "next_menu": "main"}
            ]
        }
    ]'::jsonb,
    180,
    160,
    true,
    NOW()
) ON CONFLICT (operator_code) DO UPDATE SET
    menu_structure = EXCLUDED.menu_structure,
    updated_at = NOW();

-- Note: Indexes already exist on ussd_configurations table:
-- - idx_ussd_configs_operator (on operator_code)
-- - idx_ussd_configs_active (on is_active)
