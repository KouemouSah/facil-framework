DROP VIEW IF EXISTS v_verificaciones_pendientes CASCADE;
DROP VIEW IF EXISTS v_verificacion_stats CASCADE;

CREATE VIEW v_verificaciones_pendientes AS
SELECT
    vf.id,
    vf.matricula,
    vf.created_at,
    COALESCE(
        vf.verification_data->'dip'->'extraction'->'titular'->>'apellidos',
        vf.verification_data->'dip'->'extraction'->>'nombre'
    ) AS nombre_dip,
    COALESCE(
        vf.verification_data->'dip'->'extraction'->'documento'->>'numero_dip',
        vf.verification_data->'dip'->'extraction'->>'numero_dip'
    ) AS numero_dip,
    CASE
        WHEN vf.verification_data ? 'nombramiento' THEN 'nombramiento'
        WHEN vf.verification_data ? 'carnet_funcionario' THEN 'carnet_funcionario'
        WHEN vf.verification_data ? 'contrato_funcionario' THEN 'contrato_funcionario'
        ELSE 'desconocido'
    END AS tipo_documento_prueba,
    COALESCE(
        vf.verification_data->'nombramiento'->'extraction'->'funcionario'->>'matricula',
        vf.verification_data->'carnet_funcionario'->'extraction'->'titular'->>'matricula',
        vf.verification_data->'contrato_funcionario'->'extraction'->'empleado'->>'matricula'
    ) AS matricula_extraida,
    (vf.verification_data->'validacion_cruzada'->>'nombres_coinciden')::boolean AS nombres_coinciden,
    (vf.verification_data->'validacion_cruzada'->>'matriculas_coinciden')::boolean AS matriculas_coinciden,
    (vf.verification_data->'validacion_cruzada'->>'validacion_automatica_posible')::boolean AS auto_validable,
    u.id AS user_id,
    u.email AS user_email,
    u.full_name AS user_full_name,
    u.phone_number AS user_phone
FROM verificacion_funcionario vf
JOIN users u ON vf.user_id = u.id
WHERE vf.status = 'pendiente'
ORDER BY
    (vf.verification_data->'validacion_cruzada'->>'validacion_automatica_posible')::boolean DESC NULLS LAST,
    vf.created_at ASC;

CREATE VIEW v_verificacion_stats AS
SELECT
    COUNT(*) FILTER (WHERE status = 'pendiente') AS pendientes,
    COUNT(*) FILTER (WHERE status = 'pendiente'
        AND (verification_data->'validacion_cruzada'->>'validacion_automatica_posible')::boolean = true
    ) AS pendientes_auto_validables,
    COUNT(*) FILTER (WHERE status = 'aprobado') AS aprobadas,
    COUNT(*) FILTER (WHERE status = 'rechazado') AS rechazadas,
    COUNT(*) AS total,
    AVG(EXTRACT(EPOCH FROM (processed_at - created_at))/3600)
        FILTER (WHERE processed_at IS NOT NULL) AS avg_processing_hours,
    COUNT(*) FILTER (WHERE verification_data ? 'nombramiento') AS con_nombramiento,
    COUNT(*) FILTER (WHERE verification_data ? 'carnet_funcionario') AS con_carnet,
    COUNT(*) FILTER (WHERE verification_data ? 'contrato_funcionario') AS con_contrato
FROM verificacion_funcionario;

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
    v_verification_data JSONB;
BEGIN
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
    v_verification_data := v_verificacion.verification_data;

    IF p_action = 'aprobar' THEN
        IF NOT p_matricula_existe OR NOT p_nombre_coincide THEN
            RETURN jsonb_build_object(
                'success', false,
                'error', 'Debe verificar matricula y nombre para aprobar'
            );
        END IF;

        UPDATE verificacion_funcionario
        SET status = 'aprobado',
            processed_by = p_agent_id,
            processed_at = NOW(),
            verificacion_matricula_existe = p_matricula_existe,
            verificacion_nombre_coincide = p_nombre_coincide,
            verificacion_dip_coincide = p_dip_coincide,
            notes = p_notes,
            verification_data = v_verification_data || jsonb_build_object(
                'procesamiento_agente', jsonb_build_object(
                    'agent_id', p_agent_id,
                    'action', 'aprobar',
                    'processed_at', NOW(),
                    'checklist', jsonb_build_object(
                        'matricula_existe', p_matricula_existe,
                        'nombre_coincide', p_nombre_coincide,
                        'dip_coincide', p_dip_coincide
                    ),
                    'notes', p_notes
                )
            )
        WHERE id = p_verificacion_id;

        UPDATE users
        SET matricula_funcionario = v_matricula,
            funcionario_verified_at = NOW(),
            funcionario_verified_by = p_agent_id
        WHERE id = v_user_id;

        RETURN jsonb_build_object(
            'success', true,
            'status', 'aprobado',
            'user_id', v_user_id,
            'matricula', v_matricula,
            'message', 'Usuario verificado como funcionario.'
        );

    ELSIF p_action = 'rechazar' THEN
        IF p_rejection_reason IS NULL OR p_rejection_reason = '' THEN
            RETURN jsonb_build_object(
                'success', false,
                'error', 'Debe proporcionar motivo de rechazo'
            );
        END IF;

        UPDATE verificacion_funcionario
        SET status = 'rechazado',
            processed_by = p_agent_id,
            processed_at = NOW(),
            verificacion_matricula_existe = p_matricula_existe,
            verificacion_nombre_coincide = p_nombre_coincide,
            verificacion_dip_coincide = p_dip_coincide,
            rejection_reason = p_rejection_reason,
            notes = p_notes,
            verification_data = v_verification_data || jsonb_build_object(
                'procesamiento_agente', jsonb_build_object(
                    'agent_id', p_agent_id,
                    'action', 'rechazar',
                    'processed_at', NOW(),
                    'rejection_reason', p_rejection_reason,
                    'notes', p_notes
                )
            )
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

CREATE OR REPLACE FUNCTION batch_approve_verificaciones(
    p_verificacion_ids UUID[],
    p_agent_id UUID,
    p_notes TEXT DEFAULT NULL
)
RETURNS JSONB AS $$
DECLARE
    v_id UUID;
    v_result JSONB;
    v_results JSONB[] := ARRAY[]::JSONB[];
    v_success_count INT := 0;
    v_error_count INT := 0;
BEGIN
    FOREACH v_id IN ARRAY p_verificacion_ids
    LOOP
        IF EXISTS (
            SELECT 1 FROM verificacion_funcionario
            WHERE id = v_id
            AND status = 'pendiente'
            AND (verification_data->'validacion_cruzada'->>'validacion_automatica_posible')::boolean = true
        ) THEN
            v_result := process_verificacion_funcionario(
                v_id, p_agent_id, 'aprobar',
                TRUE, TRUE, TRUE, NULL,
                COALESCE(p_notes, 'Aprobacion por lote - validacion cruzada OK')
            );

            IF (v_result->>'success')::boolean THEN
                v_success_count := v_success_count + 1;
            ELSE
                v_error_count := v_error_count + 1;
            END IF;
        ELSE
            v_result := jsonb_build_object(
                'success', false,
                'verificacion_id', v_id,
                'error', 'No es auto-validable o ya procesada'
            );
            v_error_count := v_error_count + 1;
        END IF;

        v_results := array_append(v_results, v_result || jsonb_build_object('verificacion_id', v_id));
    END LOOP;

    RETURN jsonb_build_object(
        'success', v_error_count = 0,
        'total', array_length(p_verificacion_ids, 1),
        'approved', v_success_count,
        'errors', v_error_count,
        'results', to_jsonb(v_results)
    );
END;
$$ LANGUAGE plpgsql;
