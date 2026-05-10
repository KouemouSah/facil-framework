-- Migration: 023_seed_workflow_documents.sql
-- Date: 2025-12-27
-- Description: Donnees initiales des documents requis par workflow (COMPLET)
-- Author: TaxasGE Development Team
-- Note: Separe de la creation de table pour maintenance facile
-- Source: Specifications workflows v2

-- ============================================================================
-- RESIDENCIA - PRIMERA EXPEDICION (13 documents)
-- Source: WORKFLOW_RESIDENCIA_CITOYEN.md
-- ============================================================================

INSERT INTO workflow_document_requirements
    (workflow_code, document_code, document_name_es, condition_type, condition_value, is_required, display_order, instructions_es, extraction_schema_key)
VALUES
    -- 1. Instancia de solicitud (genere par systeme)
    ('residencia', 'instancia_solicitud', 'Instancia dirigida al Director General de Extranjeria', 'always', '{}', TRUE, 1,
     'Formulario generado automaticamente por el sistema', NULL),

    -- 2. Fotografias
    ('residencia', 'fotografias', 'Tres Fotografias tamano carnet con fondo blanco', 'always', '{}', TRUE, 2,
     '3 fotos tamano carnet, fondo blanco', NULL),

    -- 3. Pasaporte con entrada legal
    ('residencia', 'pasaporte_entrada', 'Pasaporte con entrada legal al pais', 'always', '{}', TRUE, 3,
     'Pasaporte original con sello de entrada visible', 'PASAPORTE_GQ_V1'),

    -- 4. Declaracion jurada
    ('residencia', 'declaracion_jurada', 'Declaracion Jurada de no injerencia', 'always', '{}', TRUE, 4,
     'Declaracion jurada de no injerencia en asuntos internos del pais', NULL),

    -- 5. Autorizacion de reclutamiento
    ('residencia', 'autorizacion_reclutamiento', 'Autorizacion de Reclutamiento del Ministerio de Trabajo', 'always', '{}', TRUE, 5,
     'Expedido por el Ministerio de Trabajo y Seguridad Social', 'AUTORIZACION_RECLUTAMIENTO_GQ_V1'),

    -- 6. Contrato de trabajo
    ('residencia', 'contrato_trabajo', 'Contrato de Trabajo', 'always', '{}', TRUE, 6,
     'Contrato de trabajo para empresas y personas fisicas', 'CONTRATO_TRABAJO_GQ_V1'),

    -- 7. NIF o Autorizacion Gubernativa
    ('residencia', 'nif_autorizacion', 'NIF o Autorizacion Gubernativa de la empresa', 'always', '{}', TRUE, 7,
     'Resolucion de Presidencia o Autorizacion sobre la actividad (NIF DEFINITIVO)', 'CERTIFICADO_NIF_GQ_V1'),

    -- 8. Solvencia tributaria
    ('residencia', 'solvencia_tributaria', 'Solvencia Tributaria de la empresa', 'always', '{}', TRUE, 8,
     'Certificado de no deber al Tesoro Publico', 'SOLVENCIA_TRIBUTARIA_GQ_V1'),

    -- 9. Extracto bancario
    ('residencia', 'extracto_bancario', 'Extracto y Atestacion Bancaria de la empresa', 'always', '{}', TRUE, 9,
     'Extracto bancario reciente de la empresa', NULL),

    -- 10. Certificado conducta policia
    ('residencia', 'certificado_conducta_policia', 'Certificado de Buena Conducta de la Policia Judicial', 'always', '{}', TRUE, 10,
     'Expedido por la Policia Judicial', 'CERTIFICADO_CONDUCTA_GQ_V1'),

    -- 11. Certificado conducta empresa
    ('residencia', 'certificado_conducta_empresa', 'Certificado de Buena Conducta de la Empresa', 'always', '{}', TRUE, 11,
     'Certificado emitido por la empresa empleadora', NULL),

    -- 12. Certificado medico
    ('residencia', 'certificado_medico', 'Certificado Medico (VIH, Hepatitis C, Tuberculosis)', 'always', '{}', TRUE, 12,
     'Expedido por Clinica Virgen de Guadalupe o Centro Medico La Paz', 'CERTIFICADO_MEDICO_GQ_V1'),

    -- 13. Cedula y Poliza (pago timbres)
    ('residencia', 'cedula_poliza', 'Cedula Personal y Poliza (1500 + 1000 XAF)', 'always', '{}', TRUE, 13,
     'Recibo de pago de timbres fiscales', NULL)

ON CONFLICT (workflow_code, document_code) DO UPDATE SET
    document_name_es = EXCLUDED.document_name_es,
    condition_type = EXCLUDED.condition_type,
    is_required = EXCLUDED.is_required,
    display_order = EXCLUDED.display_order,
    instructions_es = EXCLUDED.instructions_es,
    extraction_schema_key = EXCLUDED.extraction_schema_key;

-- ============================================================================
-- RESIDENCIA RENOVACION (12 documents)
-- Source: WORKFLOW_RESIDENCIA_CITOYEN.md
-- ============================================================================

INSERT INTO workflow_document_requirements
    (workflow_code, document_code, document_name_es, condition_type, condition_value, is_required, display_order, instructions_es, extraction_schema_key)
VALUES
    -- 1. Instancia de solicitud
    ('residencia_renovacion', 'instancia_solicitud', 'Instancia dirigida al Director General de Extranjeria', 'always', '{}', TRUE, 1,
     'Formulario generado automaticamente por el sistema', NULL),

    -- 2. Fotografias
    ('residencia_renovacion', 'fotografias', 'Tres Fotografias tamano carnet con fondo blanco', 'always', '{}', TRUE, 2,
     '3 fotos tamano carnet, fondo blanco', NULL),

    -- 3. Contrato de trabajo
    ('residencia_renovacion', 'contrato_trabajo', 'Contrato de Trabajo', 'always', '{}', TRUE, 3,
     'Contrato de trabajo para empresas o personas fisicas', 'CONTRATO_TRABAJO_GQ_V1'),

    -- 4. NIF o Autorizacion Gubernativa
    ('residencia_renovacion', 'nif_autorizacion', 'NIF o Autorizacion Gubernativa', 'always', '{}', TRUE, 4,
     'Resolucion de Presidencia o Autorizacion sobre la actividad', 'CERTIFICADO_NIF_GQ_V1'),

    -- 5. Solvencia tributaria
    ('residencia_renovacion', 'solvencia_tributaria', 'Solvencia Tributaria de la empresa', 'always', '{}', TRUE, 5,
     'Certificado de no deber al Tesoro Publico', 'SOLVENCIA_TRIBUTARIA_GQ_V1'),

    -- 6. Extracto bancario
    ('residencia_renovacion', 'extracto_bancario', 'Extracto y Atestacion Bancaria de la empresa', 'always', '{}', TRUE, 6,
     'Extracto bancario reciente de la empresa', NULL),

    -- 7. Certificado conducta policia
    ('residencia_renovacion', 'certificado_conducta_policia', 'Certificado de Buena Conducta de la Policia Judicial', 'always', '{}', TRUE, 7,
     'Expedido por la Policia Judicial', 'CERTIFICADO_CONDUCTA_GQ_V1'),

    -- 8. Certificado conducta empresa
    ('residencia_renovacion', 'certificado_conducta_empresa', 'Certificado de Buena Conducta de la Empresa', 'always', '{}', TRUE, 8,
     'Certificado emitido por la empresa empleadora', NULL),

    -- 9. Certificado medico
    ('residencia_renovacion', 'certificado_medico', 'Certificado Medico (VIH, Hepatitis C, Tuberculosis)', 'always', '{}', TRUE, 9,
     'Expedido por Clinica Virgen de Guadalupe o Centro Medico La Paz', 'CERTIFICADO_MEDICO_GQ_V1'),

    -- 10. Residencia anterior
    ('residencia_renovacion', 'residencia_anterior', 'Copia y original de la Residencia anterior', 'always', '{}', TRUE, 10,
     'Permiso de residencia actual a renovar (recto y verso)', 'PERMISO_RESIDENCIA_GQ_V1'),

    -- 11. Certificado autenticidad CNEDOGE
    ('residencia_renovacion', 'certificado_autenticidad', 'Certificado de autenticidad expedido por CNEDOGE', 'always', '{}', TRUE, 11,
     'Documento que certifica la autenticidad del permiso actual', NULL),

    -- 12. Cedula y Poliza
    ('residencia_renovacion', 'cedula_poliza', 'Cedula Personal y Poliza (1500 + 1000 XAF)', 'always', '{}', TRUE, 12,
     'Recibo de pago de timbres fiscales', NULL)

ON CONFLICT (workflow_code, document_code) DO UPDATE SET
    document_name_es = EXCLUDED.document_name_es,
    condition_type = EXCLUDED.condition_type,
    is_required = EXCLUDED.is_required,
    display_order = EXCLUDED.display_order,
    instructions_es = EXCLUDED.instructions_es,
    extraction_schema_key = EXCLUDED.extraction_schema_key;

-- ============================================================================
-- PASAPORTE NUEVO (documents pour mineurs et adultes)
-- Source: WORKFLOW_PASAPORTE_CITOYEN.md
-- ============================================================================

INSERT INTO workflow_document_requirements
    (workflow_code, document_code, document_name_es, condition_type, condition_value, is_required, display_order, instructions_es, extraction_schema_key)
VALUES
    -- Documents pour TOUS
    ('pasaporte_nuevo', 'dip', 'Documento de Identidad Personal (DIP)', 'always', '{}', TRUE, 1,
     'DIP vigente del solicitante', 'DIP_GQ_V1'),

    ('pasaporte_nuevo', 'acte_naissance', 'Acta de Nacimiento', 'always', '{}', TRUE, 2,
     'Acta de nacimiento original o copia certificada', 'CERTIFICACION_NACIMIENTO_GQ_V1'),

    ('pasaporte_nuevo', 'foto_biometrica', 'Foto Biometrica', 'always', '{}', TRUE, 3,
     'Foto reciente fondo blanco, tamano pasaporte', NULL),

    -- Documents pour MINEURS
    ('pasaporte_nuevo', 'autorizacion_parental', 'Autorizacion Parental', 'is_minor', '{}', TRUE, 10,
     'Autorizacion firmada por ambos padres o tutor legal', NULL),

    ('pasaporte_nuevo', 'dip_padre', 'DIP del Padre', 'is_minor', '{}', TRUE, 11,
     'DIP vigente del padre', 'DIP_GQ_V1'),

    ('pasaporte_nuevo', 'dip_madre', 'DIP de la Madre', 'is_minor', '{}', TRUE, 12,
     'DIP vigente de la madre', 'DIP_GQ_V1')

ON CONFLICT (workflow_code, document_code) DO UPDATE SET
    document_name_es = EXCLUDED.document_name_es,
    condition_type = EXCLUDED.condition_type,
    is_required = EXCLUDED.is_required,
    display_order = EXCLUDED.display_order,
    instructions_es = EXCLUDED.instructions_es,
    extraction_schema_key = EXCLUDED.extraction_schema_key;

-- ============================================================================
-- PASAPORTE RENOVACION
-- ============================================================================

INSERT INTO workflow_document_requirements
    (workflow_code, document_code, document_name_es, condition_type, condition_value, is_required, display_order, instructions_es, extraction_schema_key)
VALUES
    ('pasaporte_renovacion', 'dip', 'Documento de Identidad Personal (DIP)', 'always', '{}', TRUE, 1,
     'DIP vigente del solicitante', 'DIP_GQ_V1'),

    ('pasaporte_renovacion', 'pasaporte_anterior', 'Pasaporte Anterior', 'always', '{}', TRUE, 2,
     'Pasaporte a renovar', 'PASAPORTE_GQ_V1'),

    ('pasaporte_renovacion', 'foto_biometrica', 'Foto Biometrica', 'always', '{}', TRUE, 3,
     'Foto reciente fondo blanco', NULL)

ON CONFLICT (workflow_code, document_code) DO UPDATE SET
    document_name_es = EXCLUDED.document_name_es,
    condition_type = EXCLUDED.condition_type,
    is_required = EXCLUDED.is_required,
    display_order = EXCLUDED.display_order,
    instructions_es = EXCLUDED.instructions_es,
    extraction_schema_key = EXCLUDED.extraction_schema_key;

-- ============================================================================
-- CARNET FUNCIONARIO
-- Source: SPECIFICATION_WORKFLOW_CARNET_FUNCIONARIO.md
-- ============================================================================

INSERT INTO workflow_document_requirements
    (workflow_code, document_code, document_name_es, condition_type, condition_value, is_required, display_order, instructions_es, extraction_schema_key)
VALUES
    -- Documents pour tous
    ('carnet_funcionario', 'dip', 'Documento de Identidad Personal', 'always', '{}', TRUE, 1,
     'DIP vigente del funcionario', 'DIP_GQ_V1'),

    ('carnet_funcionario', 'nombramiento', 'Acto de Nombramiento o Contrato', 'always', '{}', TRUE, 2,
     'Documento oficial de nombramiento', NULL),

    ('carnet_funcionario', 'foto_carnet', 'Foto Tamano Carnet', 'always', '{}', TRUE, 5,
     'Foto reciente fondo blanco', NULL),

    -- Documents pour nouvelle expedition
    ('carnet_funcionario', 'oficio_destino', 'Oficio de Destino', 'is_new', '{}', TRUE, 3,
     'Avis d''affectation (primera expedicion)', NULL),

    ('carnet_funcionario', 'toma_posesion', 'Toma de Posesion', 'is_new', '{}', TRUE, 4,
     'Certificat de prise de fonction', NULL),

    -- Documents pour renouvellement
    ('carnet_funcionario', 'carnet_anterior', 'Carnet de Funcionario Anterior', 'is_renewal', '{}', TRUE, 6,
     'Carnet expirado a renovar', NULL),

    -- Documents pour duplicata
    ('carnet_funcionario', 'certificado_perdida', 'Certificado de Perdida', 'is_duplicate', '{}', TRUE, 7,
     'Declaracion oficial de perdida', NULL)

ON CONFLICT (workflow_code, document_code) DO UPDATE SET
    document_name_es = EXCLUDED.document_name_es,
    condition_type = EXCLUDED.condition_type,
    is_required = EXCLUDED.is_required,
    display_order = EXCLUDED.display_order,
    instructions_es = EXCLUDED.instructions_es,
    extraction_schema_key = EXCLUDED.extraction_schema_key;

-- ============================================================================
-- CERTIFICADO CONDUCIR NUEVO
-- Source: SPECIFICATION_WORKFLOW_CERTIFICADO_CONDUCIR_GQ.md
-- ============================================================================

INSERT INTO workflow_document_requirements
    (workflow_code, document_code, document_name_es, condition_type, condition_value, is_required, display_order, instructions_es, extraction_schema_key)
VALUES
    ('certificado_conducir_nuevo', 'dip', 'Documento de Identidad Personal', 'always', '{}', TRUE, 1,
     'DIP vigente del solicitante', 'DIP_GQ_V1'),

    ('certificado_conducir_nuevo', 'certificado_medico', 'Certificado Medico de Aptitud', 'always', '{}', TRUE, 2,
     'Certificado medico de aptitud para conducir', 'CERTIFICADO_MEDICO_CONDUCIR_GQ_V1'),

    ('certificado_conducir_nuevo', 'foto_carnet', 'Foto Tamano Carnet', 'always', '{}', TRUE, 3,
     'Foto reciente fondo blanco', NULL)

ON CONFLICT (workflow_code, document_code) DO UPDATE SET
    document_name_es = EXCLUDED.document_name_es,
    condition_type = EXCLUDED.condition_type,
    is_required = EXCLUDED.is_required,
    display_order = EXCLUDED.display_order,
    instructions_es = EXCLUDED.instructions_es,
    extraction_schema_key = EXCLUDED.extraction_schema_key;

-- ============================================================================
-- CERTIFICADO CONDUCIR RENOVACION
-- ============================================================================

INSERT INTO workflow_document_requirements
    (workflow_code, document_code, document_name_es, condition_type, condition_value, is_required, display_order, instructions_es, extraction_schema_key)
VALUES
    ('certificado_conducir_renovacion', 'dip', 'Documento de Identidad Personal', 'always', '{}', TRUE, 1,
     'DIP vigente', 'DIP_GQ_V1'),

    ('certificado_conducir_renovacion', 'permiso_actual', 'Permiso de Conducir Actual', 'always', '{}', TRUE, 2,
     'Permiso a renovar', 'PERMISO_CONDUCIR_GQ_V1'),

    ('certificado_conducir_renovacion', 'certificado_medico', 'Certificado Medico de Aptitud', 'always', '{}', TRUE, 3,
     'Certificado medico de aptitud', 'CERTIFICADO_MEDICO_CONDUCIR_GQ_V1')

ON CONFLICT (workflow_code, document_code) DO UPDATE SET
    document_name_es = EXCLUDED.document_name_es,
    condition_type = EXCLUDED.condition_type,
    is_required = EXCLUDED.is_required,
    display_order = EXCLUDED.display_order,
    instructions_es = EXCLUDED.instructions_es,
    extraction_schema_key = EXCLUDED.extraction_schema_key;

-- ============================================================================
-- TRANSFERENCIA VEHICULO (5 documents - SANS CUVE/ITV)
-- Source: SPECIFICATION_WORKFLOW_TRANSFERENCIA_VEHICULO.md
-- ============================================================================

INSERT INTO workflow_document_requirements
    (workflow_code, document_code, document_name_es, condition_type, condition_value, is_required, display_order, instructions_es, extraction_schema_key)
VALUES
    ('transferencia_vehiculo', 'nota_ingreso', 'Nota de Ingreso', 'always', '{}', FALSE, 1,
     'Preuve de paiement des frais de transfert (optionnel)', 'NOTA_INGRESO_GQ_V1'),

    ('transferencia_vehiculo', 'contrato_compraventa', 'Contrato de Compraventa', 'always', '{}', TRUE, 2,
     'Contrato firmado por vendedor y comprador, precio en FCFA', 'CONTRATO_COMPRAVENTA_GQ_V1'),

    ('transferencia_vehiculo', 'dip_vendedor', 'Documento de Identidad del Vendedor', 'always', '{}', TRUE, 3,
     'DIP/Residencia/Pasaporte del vendedor', 'DIP_GQ_V1'),

    ('transferencia_vehiculo', 'dip_comprador', 'Documento de Identidad del Comprador', 'always', '{}', TRUE, 4,
     'DIP/Residencia/Pasaporte del comprador', 'DIP_GQ_V1'),

    ('transferencia_vehiculo', 'permiso_circulacion', 'Permiso de Circulacion', 'always', '{}', TRUE, 5,
     'Permiso de circulacion actual del vehiculo', 'PERMISO_CIRCULACION_GQ_V1')

ON CONFLICT (workflow_code, document_code) DO UPDATE SET
    document_name_es = EXCLUDED.document_name_es,
    condition_type = EXCLUDED.condition_type,
    is_required = EXCLUDED.is_required,
    display_order = EXCLUDED.display_order,
    instructions_es = EXCLUDED.instructions_es,
    extraction_schema_key = EXCLUDED.extraction_schema_key;

-- ============================================================================
-- RENOVACION VEHICULO (5 documents - CUVE, ITV ici)
-- Source: SPECIFICATION_WORKFLOW_RENOVACION_VEHICULO.md
-- ============================================================================

INSERT INTO workflow_document_requirements
    (workflow_code, document_code, document_name_es, condition_type, condition_value, is_required, display_order, instructions_es, extraction_schema_key)
VALUES
    ('renovacion_vehiculo', 'nota_ingreso', 'Nota de Ingreso', 'always', '{}', TRUE, 1,
     'Preuve de paiement des frais de renouvellement', 'NOTA_INGRESO_GQ_V1'),

    ('renovacion_vehiculo', 'dip_propietario', 'Documento de Identidad del Propietario', 'always', '{}', TRUE, 2,
     'DIP/Residencia/Pasaporte del propietario actual', 'DIP_GQ_V1'),

    ('renovacion_vehiculo', 'permiso_circulacion', 'Permiso de Circulacion', 'always', '{}', TRUE, 3,
     'Permiso de circulacion vigente del vehiculo', 'PERMISO_CIRCULACION_GQ_V1'),

    ('renovacion_vehiculo', 'cuve', 'CUVE (Cartilla Unica de Vehiculos)', 'always', '{}', TRUE, 4,
     'Recto: fechas validez, Verso: datos propietario y vehiculo', 'CUVE_GQ_V1'),

    ('renovacion_vehiculo', 'tarjeta_itv', 'Tarjeta ITV (Inspeccion Tecnica)', 'always', '{}', TRUE, 5,
     'Recto: historico inspecciones, Verso: caracteristicas tecnicas', 'ITV_GQ_V1')

ON CONFLICT (workflow_code, document_code) DO UPDATE SET
    document_name_es = EXCLUDED.document_name_es,
    condition_type = EXCLUDED.condition_type,
    is_required = EXCLUDED.is_required,
    display_order = EXCLUDED.display_order,
    instructions_es = EXCLUDED.instructions_es,
    extraction_schema_key = EXCLUDED.extraction_schema_key;

-- ============================================================================
-- CONTRATO ONRC (4 documents)
-- Source: SPECIFICATION_WORKFLOW_REGISTRO_CONTRATOS_GQ.md
-- ============================================================================

INSERT INTO workflow_document_requirements
    (workflow_code, document_code, document_name_es, condition_type, condition_value, is_required, display_order, instructions_es, extraction_schema_key)
VALUES
    ('contrato_onrc', 'contrato', 'Contrato a Registrar', 'always', '{}', TRUE, 1,
     'Contrato original firmado por las partes', 'CONTRATO_ONRC_GQ_V1'),

    ('contrato_onrc', 'dip_parte_a', 'Documento de Identidad Parte A', 'always', '{}', TRUE, 2,
     'DIP del primer firmante', 'DIP_GQ_V1'),

    ('contrato_onrc', 'dip_parte_b', 'Documento de Identidad Parte B', 'always', '{}', TRUE, 3,
     'DIP del segundo firmante', 'DIP_GQ_V1'),

    ('contrato_onrc', 'nif_empresa', 'NIF de la Empresa', 'always', '{}', FALSE, 4,
     'Si una parte es persona juridica', 'CERTIFICADO_NIF_GQ_V1')

ON CONFLICT (workflow_code, document_code) DO UPDATE SET
    document_name_es = EXCLUDED.document_name_es,
    condition_type = EXCLUDED.condition_type,
    is_required = EXCLUDED.is_required,
    display_order = EXCLUDED.display_order,
    instructions_es = EXCLUDED.instructions_es,
    extraction_schema_key = EXCLUDED.extraction_schema_key;

-- ============================================================================
-- CERTIFICADO ADMINISTRATIVO
-- Source: SPECIFICATION_WORKFLOW_CERTIFICADO_ADMINISTRATIVO.md
-- ============================================================================

INSERT INTO workflow_document_requirements
    (workflow_code, document_code, document_name_es, condition_type, condition_value, is_required, display_order, instructions_es, extraction_schema_key)
VALUES
    ('certificado_administrativo', 'dip', 'Documento de Identidad Personal', 'always', '{}', TRUE, 1,
     'DIP vigente del funcionario', 'DIP_GQ_V1'),

    ('certificado_administrativo', 'solicitud', 'Solicitud del Certificado', 'always', '{}', TRUE, 2,
     'Formulario de solicitud del certificado', NULL),

    ('certificado_administrativo', 'nombramiento', 'Acto de Nombramiento', 'always', '{}', TRUE, 3,
     'Documento oficial de nombramiento en el cargo', NULL)

ON CONFLICT (workflow_code, document_code) DO UPDATE SET
    document_name_es = EXCLUDED.document_name_es,
    condition_type = EXCLUDED.condition_type,
    is_required = EXCLUDED.is_required,
    display_order = EXCLUDED.display_order,
    instructions_es = EXCLUDED.instructions_es,
    extraction_schema_key = EXCLUDED.extraction_schema_key;

-- ============================================================================
-- PERMISO EXTRAORDINARIO
-- Source: SPECIFICATION_WORKFLOW_PERMISO_EXTRAORDINARIO.md
-- ============================================================================

INSERT INTO workflow_document_requirements
    (workflow_code, document_code, document_name_es, condition_type, condition_value, is_required, display_order, instructions_es, extraction_schema_key)
VALUES
    ('permiso_extraordinario', 'dip', 'Documento de Identidad Personal', 'always', '{}', TRUE, 1,
     'DIP vigente del funcionario', 'DIP_GQ_V1'),

    ('permiso_extraordinario', 'solicitud', 'Solicitud del Permiso', 'always', '{}', TRUE, 2,
     'Formulario de solicitud del permiso extraordinario', NULL),

    ('permiso_extraordinario', 'justificativo', 'Documento Justificativo', 'always', '{}', TRUE, 3,
     'Justificacion del motivo del permiso', NULL)

ON CONFLICT (workflow_code, document_code) DO UPDATE SET
    document_name_es = EXCLUDED.document_name_es,
    condition_type = EXCLUDED.condition_type,
    is_required = EXCLUDED.is_required,
    display_order = EXCLUDED.display_order,
    instructions_es = EXCLUDED.instructions_es,
    extraction_schema_key = EXCLUDED.extraction_schema_key;

-- ============================================================================
-- PROMOCION ADMINISTRATIVA
-- Source: SPECIFICATION_WORKFLOW_PROMOCION_ADMINISTRATIVA.md
-- ============================================================================

INSERT INTO workflow_document_requirements
    (workflow_code, document_code, document_name_es, condition_type, condition_value, is_required, display_order, instructions_es, extraction_schema_key)
VALUES
    ('promocion_administrativa', 'dip', 'Documento de Identidad Personal', 'always', '{}', TRUE, 1,
     'DIP vigente del funcionario', 'DIP_GQ_V1'),

    ('promocion_administrativa', 'carnet_funcionario', 'Carnet de Funcionario', 'always', '{}', TRUE, 2,
     'Carnet de funcionario vigente', NULL),

    ('promocion_administrativa', 'certificado_servicios', 'Certificado de Servicios Prestados', 'always', '{}', TRUE, 3,
     'Certificado de los anos de servicio', NULL),

    ('promocion_administrativa', 'titulos_academicos', 'Titulos Academicos', 'always', '{}', FALSE, 4,
     'Diplomas y certificados de formacion', NULL)

ON CONFLICT (workflow_code, document_code) DO UPDATE SET
    document_name_es = EXCLUDED.document_name_es,
    condition_type = EXCLUDED.condition_type,
    is_required = EXCLUDED.is_required,
    display_order = EXCLUDED.display_order,
    instructions_es = EXCLUDED.instructions_es,
    extraction_schema_key = EXCLUDED.extraction_schema_key;

-- ============================================================================
-- NETTOYAGE: Supprimer les anciennes entrees incorrectes
-- ============================================================================

-- Supprimer CUVE et ITV de transferencia_vehiculo (erreur corrigee)
DELETE FROM workflow_document_requirements
WHERE workflow_code = 'transferencia_vehiculo'
  AND document_code IN ('cuve', 'itv');

-- ============================================================================
-- END OF SEED DATA
-- ============================================================================
