-- Migration: Add Funcionario Role and Verification System
-- Date: 2025-12-26
-- Description: Creates the funcionario role and verification workflow tables
-- Author: TaxasGE Development Team

-- ============================================================================
-- 1. ADD 'funcionario' TO USER ROLE ENUM
-- ============================================================================

-- Check if 'funcionario' already exists before adding
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum
        WHERE enumlabel = 'funcionario'
        AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'user_role_enum')
    ) THEN
        ALTER TYPE user_role_enum ADD VALUE 'funcionario';
    END IF;
END
$$;

-- ============================================================================
-- 2. ADD FUNCIONARIO COLUMNS TO USERS TABLE
-- ============================================================================

-- Matricula funcionario (unique identifier from Ministry)
ALTER TABLE users
ADD COLUMN IF NOT EXISTS matricula_funcionario VARCHAR(50) UNIQUE;

-- Verification timestamp
ALTER TABLE users
ADD COLUMN IF NOT EXISTS funcionario_verified_at TIMESTAMPTZ;

-- Agent who verified
ALTER TABLE users
ADD COLUMN IF NOT EXISTS funcionario_verified_by UUID REFERENCES users(id);

-- Add comment for documentation
COMMENT ON COLUMN users.matricula_funcionario IS 'Matricula del funcionario verificada por el Ministerio de la Funcion Publica';
COMMENT ON COLUMN users.funcionario_verified_at IS 'Fecha y hora de verificacion del funcionario';
COMMENT ON COLUMN users.funcionario_verified_by IS 'ID del agente que verifico al funcionario';

-- ============================================================================
-- 3. CREATE VERIFICACION_FUNCIONARIO TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS verificacion_funcionario (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Demandeur
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    matricula VARCHAR(50) NOT NULL,

    -- Document d'identite pour verification (reference uploaded_files)
    documento_id UUID REFERENCES uploaded_files(id),
    datos_extraidos_dip JSONB,

    -- Statut de la demande
    status VARCHAR(20) NOT NULL DEFAULT 'pendiente'
        CHECK (status IN ('pendiente', 'aprobado', 'rechazado')),

    -- Traitement par agent
    processed_by UUID REFERENCES users(id),
    processed_at TIMESTAMPTZ,

    -- Checklist de verification (obligatoire pour approuver)
    verificacion_matricula_existe BOOLEAN DEFAULT FALSE,
    verificacion_nombre_coincide BOOLEAN DEFAULT FALSE,
    verificacion_dip_coincide BOOLEAN DEFAULT FALSE,

    -- En cas de rejet
    rejection_reason TEXT,

    -- Notes de l'agent
    notes TEXT,

    -- Audit et securite
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Contrainte: approbation requiert verification
    CONSTRAINT chk_approval_requires_verification CHECK (
        status != 'aprobado' OR (
            verificacion_matricula_existe = TRUE AND
            verificacion_nombre_coincide = TRUE
        )
    ),

    -- Contrainte: rejet requiert motif
    CONSTRAINT chk_rejection_requires_reason CHECK (
        status != 'rechazado' OR rejection_reason IS NOT NULL
    )
);

-- Index pour recherches frequentes
CREATE INDEX IF NOT EXISTS idx_verificacion_func_status
    ON verificacion_funcionario(status);

CREATE INDEX IF NOT EXISTS idx_verificacion_func_user
    ON verificacion_funcionario(user_id);

CREATE INDEX IF NOT EXISTS idx_verificacion_func_matricula
    ON verificacion_funcionario(matricula);

CREATE INDEX IF NOT EXISTS idx_verificacion_func_created
    ON verificacion_funcionario(created_at DESC);

-- Index partiel pour demandes pendantes (optimisation)
CREATE INDEX IF NOT EXISTS idx_verificacion_func_pending
    ON verificacion_funcionario(user_id)
    WHERE status = 'pendiente';

-- Comments
COMMENT ON TABLE verificacion_funcionario IS 'Demandes de verification du statut funcionario';
COMMENT ON COLUMN verificacion_funcionario.datos_extraidos_dip IS 'Donnees extraites du DIP par Gemini (nom, numero, etc.)';
COMMENT ON COLUMN verificacion_funcionario.verificacion_matricula_existe IS 'Agent a verifie que la matricula existe dans SIGEF';
COMMENT ON COLUMN verificacion_funcionario.verificacion_nombre_coincide IS 'Agent a verifie que le nom correspond';

-- ============================================================================
-- 4. CREATE FRAUD LOG TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS verificacion_fraud_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    matricula VARCHAR(50),
    reason VARCHAR(100) NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index pour analyse fraude
CREATE INDEX IF NOT EXISTS idx_fraud_log_user
    ON verificacion_fraud_log(user_id);

CREATE INDEX IF NOT EXISTS idx_fraud_log_created
    ON verificacion_fraud_log(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_fraud_log_reason
    ON verificacion_fraud_log(reason);

-- Comment
COMMENT ON TABLE verificacion_fraud_log IS 'Log des tentatives suspectes de verification funcionario';

-- ============================================================================
-- 5. CREATE TRIGGER FOR updated_at
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_verificacion_funcionario_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger
DROP TRIGGER IF EXISTS trg_verificacion_funcionario_updated_at ON verificacion_funcionario;

CREATE TRIGGER trg_verificacion_funcionario_updated_at
    BEFORE UPDATE ON verificacion_funcionario
    FOR EACH ROW
    EXECUTE FUNCTION update_verificacion_funcionario_updated_at();

-- ============================================================================
-- 6. CREATE FUNCTION TO PROCESS VERIFICATION
-- ============================================================================

CREATE OR REPLACE FUNCTION process_verificacion_funcionario(
    p_verificacion_id UUID,
    p_agent_id UUID,
    p_action VARCHAR(20),
    p_matricula_existe BOOLEAN DEFAULT FALSE,
    p_nombre_coincide BOOLEAN DEFAULT FALSE,
    p_dip_coincide BOOLEAN DEFAULT FALSE,
    p_rejection_reason TEXT DEFAULT NULL,
    p_notes TEXT DEFAULT NULL
)
RETURNS JSONB AS $$
DECLARE
    v_verificacion RECORD;
    v_user_id UUID;
    v_matricula VARCHAR(50);
BEGIN
    -- Get verification record
    SELECT * INTO v_verificacion
    FROM verificacion_funcionario
    WHERE id = p_verificacion_id;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'error', 'Verificacion no encontrada');
    END IF;

    IF v_verificacion.status != 'pendiente' THEN
        RETURN jsonb_build_object('success', false, 'error', 'Verificacion ya procesada');
    END IF;

    v_user_id := v_verificacion.user_id;
    v_matricula := v_verificacion.matricula;

    IF p_action = 'aprobar' THEN
        -- Validate checklist
        IF NOT p_matricula_existe OR NOT p_nombre_coincide THEN
            RETURN jsonb_build_object(
                'success', false,
                'error', 'Debe verificar matricula y nombre para aprobar'
            );
        END IF;

        -- Update verification record
        UPDATE verificacion_funcionario
        SET status = 'aprobado',
            processed_by = p_agent_id,
            processed_at = NOW(),
            verificacion_matricula_existe = p_matricula_existe,
            verificacion_nombre_coincide = p_nombre_coincide,
            verificacion_dip_coincide = p_dip_coincide,
            notes = p_notes
        WHERE id = p_verificacion_id;

        -- Update user role
        UPDATE users
        SET role = 'funcionario',
            matricula_funcionario = v_matricula,
            funcionario_verified_at = NOW(),
            funcionario_verified_by = p_agent_id
        WHERE id = v_user_id;

        RETURN jsonb_build_object(
            'success', true,
            'status', 'aprobado',
            'user_id', v_user_id,
            'matricula', v_matricula
        );

    ELSIF p_action = 'rechazar' THEN
        -- Validate rejection reason
        IF p_rejection_reason IS NULL OR p_rejection_reason = '' THEN
            RETURN jsonb_build_object(
                'success', false,
                'error', 'Debe proporcionar motivo de rechazo'
            );
        END IF;

        -- Update verification record
        UPDATE verificacion_funcionario
        SET status = 'rechazado',
            processed_by = p_agent_id,
            processed_at = NOW(),
            verificacion_matricula_existe = p_matricula_existe,
            verificacion_nombre_coincide = p_nombre_coincide,
            verificacion_dip_coincide = p_dip_coincide,
            rejection_reason = p_rejection_reason,
            notes = p_notes
        WHERE id = p_verificacion_id;

        RETURN jsonb_build_object(
            'success', true,
            'status', 'rechazado',
            'user_id', v_user_id,
            'reason', p_rejection_reason
        );

    ELSE
        RETURN jsonb_build_object('success', false, 'error', 'Accion invalida');
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Comment
COMMENT ON FUNCTION process_verificacion_funcionario IS 'Traite une demande de verification funcionario (approuver ou rejeter)';

-- ============================================================================
-- 7. ADD PERMISSIONS FOR FUNCIONARIO VERIFICATION
-- ============================================================================

-- Insert permissions if they don't exist
INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES
    ('funcionario.verificacion.create', 'funcionario_verificacion', 'create', 'Soumettre une demande de verification funcionario', FALSE, 'funcionario'),
    ('funcionario.verificacion.read_own', 'funcionario_verificacion', 'read_own', 'Voir le statut de sa propre verification', FALSE, 'funcionario'),
    ('funcionario.verificacion.read_all', 'funcionario_verificacion', 'read_all', 'Voir toutes les demandes de verification', FALSE, 'funcionario'),
    ('funcionario.verificacion.process', 'funcionario_verificacion', 'process', 'Approuver ou rejeter les verifications', TRUE, 'funcionario'),
    ('funcionario.carnet.create', 'funcionario_carnet', 'create', 'Demander un carnet de funcionario', FALSE, 'funcionario'),
    ('funcionario.promocion.create', 'funcionario_promocion', 'create', 'Demander une promotion administrative', FALSE, 'funcionario'),
    ('funcionario.permiso.create', 'funcionario_permiso', 'create', 'Demander un permiso extraordinario', FALSE, 'funcionario'),
    ('funcionario.certificado.create', 'funcionario_certificado', 'create', 'Demander un certificado administrativo', FALSE, 'funcionario')
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- 8. CREATE VIEW FOR PENDING VERIFICATIONS (Agent Dashboard)
-- ============================================================================

CREATE OR REPLACE VIEW v_verificaciones_pendientes AS
SELECT
    vf.id,
    vf.matricula,
    vf.created_at,
    vf.datos_extraidos_dip->>'nombre' AS nombre_dip,
    vf.datos_extraidos_dip->>'numero_dip' AS numero_dip,
    u.id AS user_id,
    u.email AS user_email,
    u.full_name AS user_full_name,
    u.phone_number AS user_phone
FROM verificacion_funcionario vf
JOIN users u ON vf.user_id = u.id
WHERE vf.status = 'pendiente'
ORDER BY vf.created_at ASC;

-- Comment
COMMENT ON VIEW v_verificaciones_pendientes IS 'Vue des verifications funcionario en attente pour le dashboard agent';

-- ============================================================================
-- 9. CREATE STATISTICS VIEW
-- ============================================================================

CREATE OR REPLACE VIEW v_verificacion_stats AS
SELECT
    COUNT(*) FILTER (WHERE status = 'pendiente') AS pendientes,
    COUNT(*) FILTER (WHERE status = 'aprobado') AS aprobadas,
    COUNT(*) FILTER (WHERE status = 'rechazado') AS rechazadas,
    COUNT(*) AS total,
    AVG(EXTRACT(EPOCH FROM (processed_at - created_at))/3600)
        FILTER (WHERE processed_at IS NOT NULL) AS avg_processing_hours
FROM verificacion_funcionario;

-- Comment
COMMENT ON VIEW v_verificacion_stats IS 'Statistiques des verifications funcionario';

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
