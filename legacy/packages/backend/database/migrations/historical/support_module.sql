-- =============================================================================
-- SUPPORT MODULE MIGRATION
-- Creates tables for the support ticketing system
-- Version: 1.0.0
-- Date: 2025-12-17
-- =============================================================================

-- =============================================================================
-- 1. SUPPORT CATEGORIES TABLE
-- Defines categories for support tickets (technical, billing, general, etc.)
-- =============================================================================
CREATE TABLE IF NOT EXISTS support_categories (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name_es VARCHAR(255) NOT NULL,
    name_fr VARCHAR(255),
    name_en VARCHAR(255),
    description_es TEXT,
    description_fr TEXT,
    description_en TEXT,
    target_role VARCHAR(50) DEFAULT 'all',  -- 'admin', 'agent', 'all'
    icon VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add comment
COMMENT ON TABLE support_categories IS 'Support ticket categories with multilingual support';
COMMENT ON COLUMN support_categories.target_role IS 'Target role for this category: admin, agent, or all';

-- =============================================================================
-- 2. SUPPORT TICKETS TABLE
-- Main table for support tickets
-- =============================================================================
CREATE TABLE IF NOT EXISTS support_tickets (
    id SERIAL PRIMARY KEY,
    ticket_number VARCHAR(20) UNIQUE NOT NULL,  -- Format: SUP-YYYYMMDD-XXXX
    category_id INTEGER REFERENCES support_categories(id),
    subject VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    priority VARCHAR(20) DEFAULT 'normal',  -- 'low', 'normal', 'high', 'urgent'
    status VARCHAR(30) DEFAULT 'open',  -- 'open', 'in_progress', 'pending_user', 'resolved', 'closed'
    created_by UUID REFERENCES users(id) NOT NULL,
    assigned_to UUID REFERENCES users(id),
    resolved_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add comments
COMMENT ON TABLE support_tickets IS 'Support tickets for user help requests and agent technical support';
COMMENT ON COLUMN support_tickets.ticket_number IS 'Human-readable ticket number: SUP-YYYYMMDD-XXXX';
COMMENT ON COLUMN support_tickets.priority IS 'Ticket priority: low, normal, high, urgent';
COMMENT ON COLUMN support_tickets.status IS 'Ticket status: open, in_progress, pending_user, resolved, closed';

-- =============================================================================
-- 3. SUPPORT MESSAGES TABLE
-- Messages within a ticket (conversation thread)
-- =============================================================================
CREATE TABLE IF NOT EXISTS support_messages (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER REFERENCES support_tickets(id) ON DELETE CASCADE,
    sender_id UUID REFERENCES users(id) NOT NULL,
    content TEXT NOT NULL,
    is_internal BOOLEAN DEFAULT false,  -- Internal notes visible only to admins
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add comments
COMMENT ON TABLE support_messages IS 'Messages within support tickets';
COMMENT ON COLUMN support_messages.is_internal IS 'If true, message is an internal note visible only to admins';

-- =============================================================================
-- 4. SUPPORT ATTACHMENTS TABLE
-- File attachments for messages (future feature)
-- =============================================================================
CREATE TABLE IF NOT EXISTS support_attachments (
    id SERIAL PRIMARY KEY,
    message_id INTEGER REFERENCES support_messages(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER,
    mime_type VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add comment
COMMENT ON TABLE support_attachments IS 'File attachments for support messages';

-- =============================================================================
-- 5. INDEXES FOR PERFORMANCE
-- =============================================================================

-- Support tickets indexes
CREATE INDEX IF NOT EXISTS idx_support_tickets_user ON support_tickets(created_by);
CREATE INDEX IF NOT EXISTS idx_support_tickets_assigned ON support_tickets(assigned_to);
CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status);
CREATE INDEX IF NOT EXISTS idx_support_tickets_priority ON support_tickets(priority);
CREATE INDEX IF NOT EXISTS idx_support_tickets_number ON support_tickets(ticket_number);
CREATE INDEX IF NOT EXISTS idx_support_tickets_category ON support_tickets(category_id);
CREATE INDEX IF NOT EXISTS idx_support_tickets_created_at ON support_tickets(created_at DESC);

-- Support messages indexes
CREATE INDEX IF NOT EXISTS idx_support_messages_ticket ON support_messages(ticket_id);
CREATE INDEX IF NOT EXISTS idx_support_messages_sender ON support_messages(sender_id);

-- Support attachments indexes
CREATE INDEX IF NOT EXISTS idx_support_attachments_message ON support_attachments(message_id);

-- =============================================================================
-- 6. DEFAULT CATEGORIES
-- Pre-populate with common support categories
-- =============================================================================
INSERT INTO support_categories (code, name_es, name_fr, name_en, description_es, target_role, icon, sort_order)
VALUES
    ('TECH_ISSUE', 'Problema Técnico', 'Problème Technique', 'Technical Issue',
     'Problemas técnicos con la plataforma (errores, fallos, acceso)', 'all', 'wrench', 1),
    ('ACCOUNT', 'Mi Cuenta', 'Mon Compte', 'My Account',
     'Problemas relacionados con la cuenta de usuario', 'all', 'user', 2),
    ('BILLING', 'Facturación y Pagos', 'Facturation et Paiements', 'Billing & Payments',
     'Consultas sobre facturación y pagos', 'all', 'credit-card', 3),
    ('DECLARATION', 'Declaraciones Fiscales', 'Déclarations Fiscales', 'Tax Declarations',
     'Ayuda con declaraciones fiscales y trámites', 'all', 'file-text', 4),
    ('GENERAL', 'Consulta General', 'Question Générale', 'General Inquiry',
     'Preguntas generales sobre los servicios', 'all', 'help-circle', 5),
    ('AGENT_TECH', 'Soporte Técnico Agente', 'Support Technique Agent', 'Agent Technical Support',
     'Problemas técnicos para agentes fiscales', 'agent', 'tool', 10),
    ('AGENT_SYSTEM', 'Problema Sistema Agente', 'Problème Système Agent', 'Agent System Issue',
     'Problemas con el sistema de asignación de agentes', 'agent', 'settings', 11),
    ('ADMIN_SYSTEM', 'Sistema Administrativo', 'Système Administratif', 'Admin System',
     'Problemas del sistema para administradores', 'admin', 'shield', 20),
    ('FEEDBACK', 'Sugerencias y Mejoras', 'Suggestions et Améliorations', 'Feedback & Suggestions',
     'Sugerencias para mejorar la plataforma', 'all', 'lightbulb', 99)
ON CONFLICT (code) DO NOTHING;

-- =============================================================================
-- 7. TRIGGER FOR UPDATED_AT
-- Automatically update updated_at on ticket modifications
-- =============================================================================
CREATE OR REPLACE FUNCTION update_support_ticket_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_support_ticket_updated_at ON support_tickets;
CREATE TRIGGER trigger_support_ticket_updated_at
    BEFORE UPDATE ON support_tickets
    FOR EACH ROW
    EXECUTE FUNCTION update_support_ticket_updated_at();

-- =============================================================================
-- MIGRATION COMPLETE
-- =============================================================================
