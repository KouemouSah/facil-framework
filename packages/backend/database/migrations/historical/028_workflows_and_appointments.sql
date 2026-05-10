-- ============================================================================
-- Migration 028: Create workflows table and appointment scheduling tables
-- ============================================================================
-- Purpose:
--   1. Create the missing `workflows` table to define workflow configurations
--   2. Create appointment scheduling tables for automatic CITA calculation
--   3. Seed workflows from existing Python workflow classes
--
-- Tables created:
--   - workflows: Main workflow definition table
--   - appointment_slot_configs: Available time slots by entity
--   - appointment_delay_rules: Delay rules by workflow/priority
--   - appointment_blocked_dates: Holidays and blocked dates
--   - appointment_reservations: Actual booked appointments
--
-- Date: 2024-12-28
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. WORKFLOWS TABLE (MISSING!)
-- ============================================================================
-- This table was missing - workflow_document_requirements and workflow_tariffs
-- reference workflow_code without any FK constraint. This fixes that.

CREATE TABLE IF NOT EXISTS workflows (
    -- Primary identifier
    code VARCHAR(100) PRIMARY KEY,

    -- Names (multilingual via translations module for fr/en)
    name_es VARCHAR(255) NOT NULL,
    description_es TEXT,

    -- Classification
    category VARCHAR(50) NOT NULL,          -- identite, vehiculo, contrato, conducir, funcion_publica
    entity_code VARCHAR(50) NOT NULL,       -- CNEDOGE, DGT, EXTRANJERIA, ONRC, MINFP

    -- Workflow type (determines which GenericWorkflow class to use)
    workflow_type VARCHAR(30) NOT NULL DEFAULT 'standard',
    -- 'standard'       = Agent validation BEFORE payment (default)
    -- 'direct_payment' = Direct payment WITHOUT agent validation
    -- 'multi_phase'    = Complex workflows with custom Python logic (residencia, vehiculo)

    -- Behavior flags
    requires_agent_validation BOOLEAN NOT NULL DEFAULT TRUE,
    requires_appointment BOOLEAN NOT NULL DEFAULT FALSE,
    is_generic BOOLEAN NOT NULL DEFAULT FALSE,  -- TRUE = uses GenericWorkflow, FALSE = has Python class

    -- Appointment configuration (if defined here, overrides rules table)
    appointment_delay_days INTEGER,              -- NULL = use appointment_delay_rules table
    appointment_entity_code VARCHAR(50),         -- NULL = same as entity_code

    -- SLA and processing limits
    sla_hours INTEGER NOT NULL DEFAULT 48,       -- Hours to process (for agent queue)
    max_processing_days INTEGER DEFAULT 30,      -- Max days from submission to completion

    -- Display
    display_order INTEGER DEFAULT 0,
    icon VARCHAR(50),                            -- Icon name for UI
    color VARCHAR(20),                           -- Color code for UI

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- Configuration (for additional settings)
    config JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by UUID REFERENCES users(id) ON DELETE SET NULL
);

-- Indexes
CREATE INDEX idx_workflows_category ON workflows(category);
CREATE INDEX idx_workflows_entity ON workflows(entity_code);
CREATE INDEX idx_workflows_type ON workflows(workflow_type);
CREATE INDEX idx_workflows_active ON workflows(is_active) WHERE is_active = TRUE;

-- Comments
COMMENT ON TABLE workflows IS 'Workflow definitions - determines how service requests are processed';
COMMENT ON COLUMN workflows.workflow_type IS 'standard=agent validation before payment, direct_payment=no validation, multi_phase=complex Python logic';
COMMENT ON COLUMN workflows.is_generic IS 'TRUE=uses GenericWorkflow class, FALSE=has dedicated Python class';
COMMENT ON COLUMN workflows.appointment_delay_days IS 'If set, overrides appointment_delay_rules table';

-- ============================================================================
-- 2. APPOINTMENT SLOT CONFIGS
-- ============================================================================
-- Defines available time slots for appointments by entity

CREATE TABLE IF NOT EXISTS appointment_slot_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Entity (office location)
    entity_code VARCHAR(50) NOT NULL,

    -- Day and time
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),  -- 0=Monday, 6=Sunday
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,

    -- Capacity
    slot_duration_minutes INTEGER NOT NULL DEFAULT 30,
    max_appointments_per_slot INTEGER NOT NULL DEFAULT 10,

    -- Location details
    location_name VARCHAR(255),
    location_address TEXT,

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Constraints
    CONSTRAINT valid_time_range CHECK (end_time > start_time),
    CONSTRAINT unique_slot UNIQUE (entity_code, day_of_week, start_time)
);

-- Indexes
CREATE INDEX idx_asc_entity ON appointment_slot_configs(entity_code);
CREATE INDEX idx_asc_day ON appointment_slot_configs(day_of_week);
CREATE INDEX idx_asc_active ON appointment_slot_configs(entity_code, is_active) WHERE is_active = TRUE;

COMMENT ON TABLE appointment_slot_configs IS 'Available appointment time slots by entity and day of week';
COMMENT ON COLUMN appointment_slot_configs.day_of_week IS '0=Monday, 1=Tuesday, ..., 6=Sunday';

-- ============================================================================
-- 3. APPOINTMENT DELAY RULES
-- ============================================================================
-- Configurable delays between validation and appointment by workflow/priority

CREATE TABLE IF NOT EXISTS appointment_delay_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Scope (NULL workflow_code = default rule for all workflows)
    workflow_code VARCHAR(100) REFERENCES workflows(code) ON DELETE CASCADE,
    priority service_request_priority_enum NOT NULL,

    -- Delay configuration
    delay_business_days INTEGER NOT NULL DEFAULT 3,

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,

    -- One rule per workflow/priority combination
    CONSTRAINT unique_delay_rule UNIQUE (workflow_code, priority)
);

-- Indexes
CREATE INDEX idx_adr_workflow ON appointment_delay_rules(workflow_code);
CREATE INDEX idx_adr_priority ON appointment_delay_rules(priority);
CREATE INDEX idx_adr_lookup ON appointment_delay_rules(workflow_code, priority, is_active) WHERE is_active = TRUE;

COMMENT ON TABLE appointment_delay_rules IS 'Configurable delay (in business days) between validation and appointment';
COMMENT ON COLUMN appointment_delay_rules.workflow_code IS 'NULL = default rule for all workflows without specific rule';
COMMENT ON COLUMN appointment_delay_rules.delay_business_days IS 'Number of business days to wait after validation';

-- ============================================================================
-- 4. APPOINTMENT BLOCKED DATES
-- ============================================================================
-- Holidays and other blocked dates when appointments cannot be scheduled

CREATE TABLE IF NOT EXISTS appointment_blocked_dates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Scope (NULL entity_code = applies to all entities)
    entity_code VARCHAR(50),

    -- Blocked date
    blocked_date DATE NOT NULL,

    -- Reason
    reason VARCHAR(255),

    -- Recurrence (for annual holidays)
    is_recurring BOOLEAN NOT NULL DEFAULT FALSE,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Constraints
    CONSTRAINT unique_blocked_date UNIQUE (entity_code, blocked_date)
);

-- Indexes
CREATE INDEX idx_abd_entity ON appointment_blocked_dates(entity_code);
CREATE INDEX idx_abd_date ON appointment_blocked_dates(blocked_date);
CREATE INDEX idx_abd_lookup ON appointment_blocked_dates(entity_code, blocked_date);

COMMENT ON TABLE appointment_blocked_dates IS 'Holidays and blocked dates when appointments cannot be scheduled';
COMMENT ON COLUMN appointment_blocked_dates.entity_code IS 'NULL = applies to all entities';
COMMENT ON COLUMN appointment_blocked_dates.is_recurring IS 'TRUE = same date every year (annual holidays)';

-- ============================================================================
-- 5. APPOINTMENT RESERVATIONS
-- ============================================================================
-- Actual booked appointments for service requests

CREATE TABLE IF NOT EXISTS appointment_reservations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to service request
    service_request_id UUID NOT NULL REFERENCES service_requests(id) ON DELETE CASCADE,

    -- Appointment details
    entity_code VARCHAR(50) NOT NULL,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,

    -- Location (copied from slot config or workflow config)
    location_name VARCHAR(255),
    location_address TEXT,

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled',
    -- 'scheduled'  = Appointment booked
    -- 'confirmed'  = Citizen confirmed attendance
    -- 'completed'  = Appointment completed
    -- 'cancelled'  = Cancelled by citizen or system
    -- 'no_show'    = Citizen did not show up
    -- 'rescheduled' = Moved to new date

    -- Notifications
    reminder_sent_at TIMESTAMPTZ,
    confirmation_sent_at TIMESTAMPTZ,

    -- Rescheduling
    rescheduled_from UUID REFERENCES appointment_reservations(id),
    rescheduled_reason TEXT,

    -- Completion
    completed_at TIMESTAMPTZ,
    completed_by UUID REFERENCES users(id),
    completion_notes TEXT,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cancelled_at TIMESTAMPTZ,
    cancelled_by UUID REFERENCES users(id),
    cancellation_reason TEXT,

    -- Constraints
    CONSTRAINT valid_status CHECK (status IN ('scheduled', 'confirmed', 'completed', 'cancelled', 'no_show', 'rescheduled'))
);

-- Indexes
CREATE INDEX idx_ar_service_request ON appointment_reservations(service_request_id);
CREATE INDEX idx_ar_entity_date ON appointment_reservations(entity_code, appointment_date);
CREATE INDEX idx_ar_status ON appointment_reservations(status);
CREATE INDEX idx_ar_scheduled ON appointment_reservations(entity_code, appointment_date, appointment_time)
    WHERE status IN ('scheduled', 'confirmed');
CREATE INDEX idx_ar_pending_reminders ON appointment_reservations(appointment_date)
    WHERE status = 'scheduled' AND reminder_sent_at IS NULL;

COMMENT ON TABLE appointment_reservations IS 'Booked appointments for service requests';
COMMENT ON COLUMN appointment_reservations.status IS 'scheduled, confirmed, completed, cancelled, no_show, rescheduled';

-- ============================================================================
-- 6. UPDATE TRIGGER FOR workflows
-- ============================================================================

CREATE OR REPLACE FUNCTION update_workflows_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_workflows_updated_at
    BEFORE UPDATE ON workflows
    FOR EACH ROW
    EXECUTE FUNCTION update_workflows_updated_at();

-- ============================================================================
-- 7. UPDATE TRIGGER FOR appointment_reservations
-- ============================================================================

CREATE OR REPLACE FUNCTION update_appointment_reservations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_appointment_reservations_updated_at
    BEFORE UPDATE ON appointment_reservations
    FOR EACH ROW
    EXECUTE FUNCTION update_appointment_reservations_updated_at();

-- ============================================================================
-- 8. SEED WORKFLOWS FROM EXISTING PYTHON CLASSES
-- ============================================================================
-- These workflows have dedicated Python classes with custom logic

INSERT INTO workflows (code, name_es, description_es, category, entity_code, workflow_type, requires_agent_validation, requires_appointment, is_generic, sla_hours, display_order, is_active) VALUES
-- PASAPORTE (5 types)
('PASAPORTE_NUEVO', 'Pasaporte Nuevo', 'Solicitud de pasaporte por primera vez', 'identite', 'CNEDOGE', 'standard', TRUE, TRUE, FALSE, 48, 1, TRUE),
('PASAPORTE_RENOVACION', 'Renovación de Pasaporte', 'Renovación de pasaporte expirado o próximo a expirar', 'identite', 'CNEDOGE', 'standard', TRUE, TRUE, FALSE, 48, 2, TRUE),
('PASAPORTE_PERDIDA', 'Pasaporte por Pérdida', 'Solicitud de pasaporte por pérdida del anterior', 'identite', 'CNEDOGE', 'standard', TRUE, TRUE, FALSE, 48, 3, TRUE),
('PASAPORTE_ROBO', 'Pasaporte por Robo', 'Solicitud de pasaporte por robo del anterior', 'identite', 'CNEDOGE', 'standard', TRUE, TRUE, FALSE, 48, 4, TRUE),
('PASAPORTE_DETERIORO', 'Pasaporte por Deterioro', 'Solicitud de pasaporte por deterioro del anterior', 'identite', 'CNEDOGE', 'standard', TRUE, TRUE, FALSE, 48, 5, TRUE),

-- RESIDENCIA (5 types) - Multi-phase workflow
('RESIDENCIA_PRIMERA_VEZ', 'Permiso de Residencia Primera Vez', 'Solicitud de permiso de residencia para extranjeros', 'identite', 'EXTRANJERIA', 'multi_phase', TRUE, TRUE, FALSE, 72, 10, TRUE),
('RESIDENCIA_RENOVACION', 'Renovación de Residencia', 'Renovación de permiso de residencia', 'identite', 'EXTRANJERIA', 'multi_phase', TRUE, TRUE, FALSE, 72, 11, TRUE),
('RESIDENCIA_DUPLICADO', 'Duplicado de Residencia', 'Solicitud de duplicado por pérdida o deterioro', 'identite', 'EXTRANJERIA', 'standard', TRUE, TRUE, FALSE, 48, 12, TRUE),
('RESIDENCIA_CAMBIO_DATOS', 'Cambio de Datos Residencia', 'Modificación de datos en el permiso de residencia', 'identite', 'EXTRANJERIA', 'standard', TRUE, TRUE, FALSE, 48, 13, TRUE),
('RESIDENCIA_REAGRUPACION', 'Reagrupación Familiar', 'Solicitud de residencia por reagrupación familiar', 'identite', 'EXTRANJERIA', 'multi_phase', TRUE, TRUE, FALSE, 72, 14, TRUE),

-- VEHICULO (7 types) - RBC calculation
('VEHICULO_PRIMERA_MATRICULACION', 'Primera Matriculación', 'Matriculación de vehículo nuevo o importado', 'vehiculo', 'DGT', 'multi_phase', TRUE, TRUE, FALSE, 72, 20, TRUE),
('VEHICULO_TRANSFERENCIA', 'Transferencia de Vehículo', 'Cambio de titularidad del vehículo', 'vehiculo', 'DGT', 'multi_phase', TRUE, FALSE, FALSE, 48, 21, TRUE),
('VEHICULO_RENOVACION_CUVE', 'Renovación CUVE', 'Renovación del Certificado Único de Vehículo', 'vehiculo', 'DGT', 'standard', TRUE, FALSE, FALSE, 48, 22, TRUE),
('VEHICULO_RENOVACION_ITV', 'Renovación ITV', 'Inspección Técnica de Vehículos', 'vehiculo', 'ITVE', 'standard', TRUE, TRUE, FALSE, 48, 23, TRUE),
('VEHICULO_DUPLICADO_PERMISO', 'Duplicado Permiso Circulación', 'Duplicado del permiso de circulación', 'vehiculo', 'DGT', 'standard', TRUE, FALSE, FALSE, 48, 24, TRUE),
('VEHICULO_DUPLICADO_CUVE', 'Duplicado CUVE', 'Duplicado del Certificado Único de Vehículo', 'vehiculo', 'DGT', 'standard', TRUE, FALSE, FALSE, 48, 25, TRUE),
('VEHICULO_CAMBIO_CARACTERISTICAS', 'Cambio Características Vehículo', 'Modificación de las características del vehículo', 'vehiculo', 'DGT', 'standard', TRUE, FALSE, FALSE, 48, 26, TRUE),

-- CONTRATO (7 types) - Percentage calculation
('CONTRATO_OBRA', 'Contrato de Obra', 'Registro de contrato de obra pública', 'contrato', 'ONRC', 'standard', TRUE, FALSE, FALSE, 48, 30, TRUE),
('CONTRATO_SERVICIO', 'Contrato de Servicio', 'Registro de contrato de servicios', 'contrato', 'ONRC', 'standard', TRUE, FALSE, FALSE, 48, 31, TRUE),
('CONTRATO_SUMINISTRO', 'Contrato de Suministro', 'Registro de contrato de suministro', 'contrato', 'ONRC', 'standard', TRUE, FALSE, FALSE, 48, 32, TRUE),
('CONTRATO_CONCESION', 'Contrato de Concesión', 'Registro de contrato de concesión', 'contrato', 'ONRC', 'standard', TRUE, FALSE, FALSE, 48, 33, TRUE),
('CONTRATO_JOINT_VENTURE', 'Contrato Joint Venture', 'Registro de contrato de joint venture', 'contrato', 'ONRC', 'standard', TRUE, FALSE, FALSE, 48, 34, TRUE),
('CONTRATO_ARRENDAMIENTO', 'Contrato de Arrendamiento', 'Registro de contrato de arrendamiento', 'contrato', 'ONRC', 'standard', TRUE, FALSE, FALSE, 48, 35, TRUE),
('CONTRATO_OTRO', 'Otro Tipo de Contrato', 'Registro de otros tipos de contratos', 'contrato', 'ONRC', 'standard', TRUE, FALSE, FALSE, 48, 36, TRUE),

-- CONDUCIR (5 types)
('CONDUCIR_NUEVO', 'Permiso de Conducir Nuevo', 'Solicitud de permiso de conducir por primera vez', 'conducir', 'DGT', 'standard', TRUE, TRUE, FALSE, 48, 40, TRUE),
('CONDUCIR_CANJE', 'Canje de Permiso Extranjero', 'Canje de permiso de conducir extranjero', 'conducir', 'DGT', 'standard', TRUE, TRUE, FALSE, 48, 41, TRUE),
('CONDUCIR_RENOVACION', 'Renovación Permiso Conducir', 'Renovación del permiso de conducir', 'conducir', 'DGT', 'standard', TRUE, TRUE, FALSE, 48, 42, TRUE),
('CONDUCIR_DUPLICADO', 'Duplicado Permiso Conducir', 'Duplicado del permiso de conducir', 'conducir', 'DGT', 'standard', TRUE, FALSE, FALSE, 48, 43, TRUE),
('CONDUCIR_EXTENSION', 'Extensión de Categoría', 'Extensión de categoría del permiso de conducir', 'conducir', 'DGT', 'standard', TRUE, TRUE, FALSE, 48, 44, TRUE),

-- FUNCION PUBLICA (5 types)
('FP_VERIFICACION_FUNCIONARIO', 'Verificación de Funcionario', 'Verificación del estatus de funcionario público', 'funcion_publica', 'MINFP', 'standard', TRUE, FALSE, FALSE, 24, 50, TRUE),
('FP_CARNET_FUNCIONARIO', 'Carnet de Funcionario', 'Solicitud de carnet de funcionario público', 'funcion_publica', 'MINFP', 'standard', TRUE, TRUE, FALSE, 48, 51, TRUE),
('FP_PROMOCION_ADMINISTRATIVA', 'Promoción Administrativa', 'Solicitud de promoción administrativa', 'funcion_publica', 'MINFP', 'standard', TRUE, FALSE, FALSE, 72, 52, TRUE),
('FP_PERMISO_EXTRAORDINARIO', 'Permiso Extraordinario', 'Solicitud de permiso extraordinario', 'funcion_publica', 'MINFP', 'standard', TRUE, FALSE, FALSE, 48, 53, TRUE),
('FP_CERTIFICADO_ADMINISTRATIVO', 'Certificado Administrativo', 'Solicitud de certificado administrativo', 'funcion_publica', 'MINFP', 'standard', TRUE, FALSE, FALSE, 24, 54, TRUE)

ON CONFLICT (code) DO UPDATE SET
    name_es = EXCLUDED.name_es,
    description_es = EXCLUDED.description_es,
    category = EXCLUDED.category,
    entity_code = EXCLUDED.entity_code,
    workflow_type = EXCLUDED.workflow_type,
    requires_agent_validation = EXCLUDED.requires_agent_validation,
    requires_appointment = EXCLUDED.requires_appointment,
    is_generic = EXCLUDED.is_generic,
    sla_hours = EXCLUDED.sla_hours,
    display_order = EXCLUDED.display_order,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- ============================================================================
-- 9. SEED DEFAULT APPOINTMENT DELAY RULES
-- ============================================================================

INSERT INTO appointment_delay_rules (workflow_code, priority, delay_business_days, is_active) VALUES
-- Default rules (NULL workflow_code = applies to all)
(NULL, 'URGENT', 1, TRUE),
(NULL, 'NORMAL', 3, TRUE),
(NULL, 'LOW', 5, TRUE)
ON CONFLICT (workflow_code, priority) DO NOTHING;

-- ============================================================================
-- 10. SEED SAMPLE APPOINTMENT SLOTS (CNEDOGE example)
-- ============================================================================
-- Monday to Friday, 08:00-15:00

INSERT INTO appointment_slot_configs (entity_code, day_of_week, start_time, end_time, slot_duration_minutes, max_appointments_per_slot, location_name, location_address, is_active) VALUES
-- CNEDOGE - Lunes a Viernes
('CNEDOGE', 0, '08:00', '15:00', 30, 10, 'CNEDOGE Malabo', 'Malabo, Bioko Norte', TRUE),
('CNEDOGE', 1, '08:00', '15:00', 30, 10, 'CNEDOGE Malabo', 'Malabo, Bioko Norte', TRUE),
('CNEDOGE', 2, '08:00', '15:00', 30, 10, 'CNEDOGE Malabo', 'Malabo, Bioko Norte', TRUE),
('CNEDOGE', 3, '08:00', '15:00', 30, 10, 'CNEDOGE Malabo', 'Malabo, Bioko Norte', TRUE),
('CNEDOGE', 4, '08:00', '15:00', 30, 10, 'CNEDOGE Malabo', 'Malabo, Bioko Norte', TRUE),
-- DGT - Lunes a Viernes
('DGT', 0, '08:00', '14:00', 30, 8, 'DGT Malabo', 'Malabo, Bioko Norte', TRUE),
('DGT', 1, '08:00', '14:00', 30, 8, 'DGT Malabo', 'Malabo, Bioko Norte', TRUE),
('DGT', 2, '08:00', '14:00', 30, 8, 'DGT Malabo', 'Malabo, Bioko Norte', TRUE),
('DGT', 3, '08:00', '14:00', 30, 8, 'DGT Malabo', 'Malabo, Bioko Norte', TRUE),
('DGT', 4, '08:00', '14:00', 30, 8, 'DGT Malabo', 'Malabo, Bioko Norte', TRUE),
-- EXTRANJERIA - Lunes a Viernes
('EXTRANJERIA', 0, '09:00', '14:00', 30, 6, 'Extranjería Malabo', 'Malabo, Bioko Norte', TRUE),
('EXTRANJERIA', 1, '09:00', '14:00', 30, 6, 'Extranjería Malabo', 'Malabo, Bioko Norte', TRUE),
('EXTRANJERIA', 2, '09:00', '14:00', 30, 6, 'Extranjería Malabo', 'Malabo, Bioko Norte', TRUE),
('EXTRANJERIA', 3, '09:00', '14:00', 30, 6, 'Extranjería Malabo', 'Malabo, Bioko Norte', TRUE),
('EXTRANJERIA', 4, '09:00', '14:00', 30, 6, 'Extranjería Malabo', 'Malabo, Bioko Norte', TRUE)
ON CONFLICT (entity_code, day_of_week, start_time) DO NOTHING;

-- ============================================================================
-- 11. SEED SAMPLE BLOCKED DATES (National Holidays)
-- ============================================================================

INSERT INTO appointment_blocked_dates (entity_code, blocked_date, reason, is_recurring) VALUES
-- National holidays (recurring annually)
(NULL, '2025-01-01', 'Año Nuevo', TRUE),
(NULL, '2025-03-08', 'Día Internacional de la Mujer', TRUE),
(NULL, '2025-04-18', 'Viernes Santo', FALSE),  -- Changes each year
(NULL, '2025-05-01', 'Día del Trabajo', TRUE),
(NULL, '2025-05-25', 'Día de África', TRUE),
(NULL, '2025-06-05', 'Día del Presidente', TRUE),
(NULL, '2025-08-03', 'Día de las Fuerzas Armadas', TRUE),
(NULL, '2025-08-15', 'Día de la Constitución', TRUE),
(NULL, '2025-10-12', 'Día de la Independencia', TRUE),
(NULL, '2025-12-08', 'Día de la Inmaculada Concepción', TRUE),
(NULL, '2025-12-25', 'Navidad', TRUE)
ON CONFLICT (entity_code, blocked_date) DO NOTHING;

-- ============================================================================
-- 12. VIEW: Available slots for a given date
-- ============================================================================

CREATE OR REPLACE VIEW v_available_appointment_slots AS
SELECT
    asc_config.entity_code,
    asc_config.day_of_week,
    asc_config.start_time,
    asc_config.end_time,
    asc_config.slot_duration_minutes,
    asc_config.max_appointments_per_slot,
    asc_config.location_name,
    asc_config.location_address,
    COALESCE(reservations.booked_count, 0) as current_bookings,
    asc_config.max_appointments_per_slot - COALESCE(reservations.booked_count, 0) as available_slots
FROM appointment_slot_configs asc_config
LEFT JOIN (
    SELECT
        entity_code,
        appointment_date,
        appointment_time,
        COUNT(*) as booked_count
    FROM appointment_reservations
    WHERE status IN ('scheduled', 'confirmed')
    GROUP BY entity_code, appointment_date, appointment_time
) reservations ON
    asc_config.entity_code = reservations.entity_code
    AND asc_config.start_time = reservations.appointment_time
WHERE asc_config.is_active = TRUE;

COMMENT ON VIEW v_available_appointment_slots IS 'Shows available appointment slots with current booking counts';

-- ============================================================================
-- 13. FUNCTION: Check if date is blocked
-- ============================================================================

CREATE OR REPLACE FUNCTION is_appointment_date_blocked(
    p_entity_code VARCHAR(50),
    p_date DATE
) RETURNS BOOLEAN AS $$
DECLARE
    v_is_blocked BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM appointment_blocked_dates
        WHERE (entity_code IS NULL OR entity_code = p_entity_code)
        AND (
            blocked_date = p_date
            OR (is_recurring AND EXTRACT(MONTH FROM blocked_date) = EXTRACT(MONTH FROM p_date)
                AND EXTRACT(DAY FROM blocked_date) = EXTRACT(DAY FROM p_date))
        )
    ) INTO v_is_blocked;

    RETURN v_is_blocked;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION is_appointment_date_blocked IS 'Checks if a date is blocked for appointments (holidays, etc.)';

-- ============================================================================
-- 14. FUNCTION: Get next available appointment slot
-- ============================================================================

CREATE OR REPLACE FUNCTION get_next_available_slot(
    p_entity_code VARCHAR(50),
    p_target_date DATE,
    p_workflow_code VARCHAR(100) DEFAULT NULL
) RETURNS TABLE (
    slot_date DATE,
    slot_time TIME,
    location_name VARCHAR(255),
    location_address TEXT
) AS $$
DECLARE
    v_current_date DATE := p_target_date;
    v_max_search_days INTEGER := 60;  -- Search up to 60 days ahead
    v_day_count INTEGER := 0;
BEGIN
    WHILE v_day_count < v_max_search_days LOOP
        -- Skip blocked dates
        IF NOT is_appointment_date_blocked(p_entity_code, v_current_date) THEN
            -- Check for available slot on this day
            RETURN QUERY
            SELECT
                v_current_date as slot_date,
                asc_config.start_time as slot_time,
                asc_config.location_name,
                asc_config.location_address
            FROM appointment_slot_configs asc_config
            LEFT JOIN (
                SELECT appointment_time, COUNT(*) as cnt
                FROM appointment_reservations
                WHERE entity_code = p_entity_code
                AND appointment_date = v_current_date
                AND status IN ('scheduled', 'confirmed')
                GROUP BY appointment_time
            ) res ON asc_config.start_time = res.appointment_time
            WHERE asc_config.entity_code = p_entity_code
            AND asc_config.is_active = TRUE
            AND asc_config.day_of_week = EXTRACT(DOW FROM v_current_date)::INTEGER
            AND COALESCE(res.cnt, 0) < asc_config.max_appointments_per_slot
            ORDER BY asc_config.start_time
            LIMIT 1;

            -- If we found a slot, exit
            IF FOUND THEN
                RETURN;
            END IF;
        END IF;

        v_current_date := v_current_date + INTERVAL '1 day';
        v_day_count := v_day_count + 1;
    END LOOP;

    -- No slot found within search range
    RETURN;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_next_available_slot IS 'Finds the next available appointment slot starting from target date';

COMMIT;

-- ============================================================================
-- ROLLBACK SCRIPT (run separately if needed)
-- ============================================================================
-- BEGIN;
-- DROP FUNCTION IF EXISTS get_next_available_slot;
-- DROP FUNCTION IF EXISTS is_appointment_date_blocked;
-- DROP VIEW IF EXISTS v_available_appointment_slots;
-- DROP TABLE IF EXISTS appointment_reservations;
-- DROP TABLE IF EXISTS appointment_blocked_dates;
-- DROP TABLE IF EXISTS appointment_delay_rules;
-- DROP TABLE IF EXISTS appointment_slot_configs;
-- DROP TABLE IF EXISTS workflows;
-- COMMIT;
