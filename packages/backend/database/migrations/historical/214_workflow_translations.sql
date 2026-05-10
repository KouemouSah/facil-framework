-- Migration: 214_workflow_translations.sql
-- Description: Add workflow translations (step titles, option labels, option descriptions,
--              workflow names, generic labels) for all 14+ workflows — es/fr/en.
-- Author: Claude Code
-- Date: 2026-03-27
--
-- Category: 'workflow'
-- Context: 'workflow_ui'
-- Key codes:
--   workflow.name.{CODE}               — Workflow service names
--   workflow.step.{title}              — Generic step titles shared across workflows
--   workflow.label.{key}               — Generic UI labels (e.g., continue, back, minor)
--   workflow.option.{workflow}.{value}  — Option labels per workflow
--   workflow.option.{workflow}.{value}.desc — Option descriptions
--   workflow.motivo.{MOTIVO}           — Motivo labels shared across workflows

-- =============================================================================
-- 1. WORKFLOW SERVICE NAMES
-- =============================================================================

INSERT INTO translations (category, key_code, context, es, fr, en, description, translation_source)
VALUES
    -- PASAPORTE
    ('workflow', 'workflow.name.PASAPORTE', 'workflow_ui',
     'Solicitud de Pasaporte', 'Demande de Passeport', 'Passport Application',
     'Workflow: Pasaporte service name', 'manual'),

    -- CONDUCIR
    ('workflow', 'workflow.name.CONDUCIR', 'workflow_ui',
     'Solicitud de Certificado para Conducir', 'Demande de Permis de Conduire', 'Driving License Application',
     'Workflow: Conducir service name', 'manual'),

    -- CONTRATO
    ('workflow', 'workflow.name.CONTRATO', 'workflow_ui',
     'Registro de Contrato Comercial', 'Enregistrement de Contrat Commercial', 'Commercial Contract Registration',
     'Workflow: Contrato service name', 'manual'),

    -- RESIDENCIA
    ('workflow', 'workflow.name.RESIDENCIA', 'workflow_ui',
     'Permiso de Residencia para Extranjeros', 'Permis de Résidence pour Étrangers', 'Residence Permit for Foreigners',
     'Workflow: Residencia service name', 'manual'),

    -- TRAMITES_VISADO
    ('workflow', 'workflow.name.TRAMITES_VISADO', 'workflow_ui',
     'Trámites de Visado', 'Formalités de Visa', 'Visa Procedures',
     'Workflow: TramitesVisado service name', 'manual'),

    -- MATRICULACION
    ('workflow', 'workflow.name.MATRICULACION', 'workflow_ui',
     'Matriculación y Transferencia de Vehículos', 'Immatriculation et Transfert de Véhicules', 'Vehicle Registration and Transfer',
     'Workflow: Matriculacion service name', 'manual'),

    -- INSPECCION
    ('workflow', 'workflow.name.INSPECCION', 'workflow_ui',
     'Inspección y Renovación de Documentos de Vehículos', 'Inspection et Renouvellement de Documents de Véhicules', 'Vehicle Document Inspection and Renewal',
     'Workflow: Inspeccion service name', 'manual'),

    -- DUPLICADO_VEHICULO
    ('workflow', 'workflow.name.DUPLICADO_VEHICULO', 'workflow_ui',
     'Duplicado de Documentos de Vehículos', 'Duplicata de Documents de Véhicules', 'Duplicate Vehicle Documents',
     'Workflow: Duplicado vehiculo service name', 'manual'),

    -- FP_VERIFICACION_FUNCIONARIO
    ('workflow', 'workflow.name.FP_VERIFICACION_FUNCIONARIO', 'workflow_ui',
     'Verificación de Funcionario', 'Vérification de Fonctionnaire', 'Civil Servant Verification',
     'Workflow: Verificacion service name', 'manual'),

    -- FP_CARNET_FUNCIONARIO
    ('workflow', 'workflow.name.FP_CARNET_FUNCIONARIO', 'workflow_ui',
     'Carnet de Funcionario', 'Carte de Fonctionnaire', 'Civil Servant Card',
     'Workflow: Carnet funcionario service name', 'manual'),

    -- FP_PROMOCION_ADMINISTRATIVA
    ('workflow', 'workflow.name.FP_PROMOCION_ADMINISTRATIVA', 'workflow_ui',
     'Promoción Administrativa', 'Promotion Administrative', 'Administrative Promotion',
     'Workflow: Promocion administrativa service name', 'manual'),

    -- FP_PERMISO_EXTRAORDINARIO
    ('workflow', 'workflow.name.FP_PERMISO_EXTRAORDINARIO', 'workflow_ui',
     'Permiso Extraordinario', 'Permission Extraordinaire', 'Extraordinary Leave',
     'Workflow: Permiso extraordinario service name', 'manual'),

    -- FP_CERTIFICADO_ADMINISTRATIVO
    ('workflow', 'workflow.name.FP_CERTIFICADO_ADMINISTRATIVO', 'workflow_ui',
     'Certificado Administrativo', 'Certificat Administratif', 'Administrative Certificate',
     'Workflow: Certificado administrativo service name', 'manual'),

    -- BUNDLE_PAYMENT
    ('workflow', 'workflow.name.BUNDLE_PAYMENT', 'workflow_ui',
     'Pago de Obligaciones Fiscales', 'Paiement des Obligations Fiscales', 'Tax Obligation Payment',
     'Workflow: Bundle payment service name', 'manual')

ON CONFLICT (category, key_code, context) DO UPDATE SET
    es = EXCLUDED.es,
    fr = EXCLUDED.fr,
    en = EXCLUDED.en,
    description = EXCLUDED.description,
    updated_at = NOW();


-- =============================================================================
-- 2. GENERIC STEP TITLES (shared across many workflows)
-- =============================================================================

INSERT INTO translations (category, key_code, context, es, fr, en, description, translation_source)
VALUES
    -- Selection steps
    ('workflow', 'workflow.step.tipo_solicitud', 'workflow_ui',
     'Tipo de Solicitud', 'Type de Demande', 'Application Type',
     'Step: selection type', 'manual'),

    ('workflow', 'workflow.step.tipo_solicitante', 'workflow_ui',
     'Tipo de Solicitante', 'Type de Demandeur', 'Applicant Type',
     'Step: applicant type', 'manual'),

    ('workflow', 'workflow.step.tipo_tramite', 'workflow_ui',
     'Tipo de Trámite', 'Type de Procédure', 'Procedure Type',
     'Step: procedure type', 'manual'),

    ('workflow', 'workflow.step.tipo_contrato', 'workflow_ui',
     'Tipo de Contrato', 'Type de Contrat', 'Contract Type',
     'Step: contract type', 'manual'),

    ('workflow', 'workflow.step.tipo_certificado', 'workflow_ui',
     'Tipo de Certificado', 'Type de Certificat', 'Certificate Type',
     'Step: certificate type', 'manual'),

    ('workflow', 'workflow.step.tipo_promocion', 'workflow_ui',
     'Tipo de Promoción', 'Type de Promotion', 'Promotion Type',
     'Step: promotion type', 'manual'),

    ('workflow', 'workflow.step.tipo_duplicado', 'workflow_ui',
     'Tipo de Duplicado', 'Type de Duplicata', 'Duplicate Type',
     'Step: duplicate type', 'manual'),

    ('workflow', 'workflow.step.tipo_tramite_visado', 'workflow_ui',
     'Tipo de Trámite de Visado', 'Type de Formalité de Visa', 'Visa Procedure Type',
     'Step: visa procedure type', 'manual'),

    -- Motivo steps
    ('workflow', 'workflow.step.motivo_renovacion', 'workflow_ui',
     'Motivo de Renovación', 'Motif de Renouvellement', 'Renewal Reason',
     'Step: renewal reason', 'manual'),

    ('workflow', 'workflow.step.motivo_duplicado', 'workflow_ui',
     'Motivo del Duplicado', 'Motif du Duplicata', 'Duplicate Reason',
     'Step: duplicate reason', 'manual'),

    ('workflow', 'workflow.step.motivo_permiso', 'workflow_ui',
     'Motivo del Permiso', 'Motif de la Permission', 'Leave Reason',
     'Step: leave reason', 'manual'),

    ('workflow', 'workflow.step.motivo_representante_unico', 'workflow_ui',
     'Motivo de Representante Único', 'Motif du Représentant Unique', 'Single Representative Reason',
     'Step: single representative reason', 'manual'),

    -- Minor-related
    ('workflow', 'workflow.step.representantes_legales', 'workflow_ui',
     'Representantes Legales', 'Représentants Légaux', 'Legal Representatives',
     'Step: legal representatives', 'manual'),

    -- Permit classes (conducir)
    ('workflow', 'workflow.step.clases_permiso', 'workflow_ui',
     'Clase(s) de Permiso', 'Classe(s) de Permis', 'Permit Class(es)',
     'Step: permit classes', 'manual'),

    -- Detalles steps
    ('workflow', 'workflow.step.detalles_permiso', 'workflow_ui',
     'Detalles del Permiso', 'Détails de la Permission', 'Leave Details',
     'Step: leave details', 'manual'),

    ('workflow', 'workflow.step.detalles_certificado', 'workflow_ui',
     'Detalles del Certificado', 'Détails du Certificat', 'Certificate Details',
     'Step: certificate details', 'manual'),

    -- Document upload
    ('workflow', 'workflow.step.documentos_requeridos', 'workflow_ui',
     'Documentos Requeridos', 'Documents Requis', 'Required Documents',
     'Step: required documents', 'manual'),

    ('workflow', 'workflow.step.documentos_vehiculo', 'workflow_ui',
     'Documentos del Vehículo', 'Documents du Véhicule', 'Vehicle Documents',
     'Step: vehicle documents', 'manual'),

    ('workflow', 'workflow.step.documentos_justificativos', 'workflow_ui',
     'Documentos Justificativos', 'Pièces Justificatives', 'Supporting Documents',
     'Step: supporting documents', 'manual'),

    ('workflow', 'workflow.step.documentos_empresa', 'workflow_ui',
     'Documentos de la Empresa', 'Documents de l''Entreprise', 'Company Documents',
     'Step: company documents', 'manual'),

    ('workflow', 'workflow.step.documento_identidad', 'workflow_ui',
     'Documento de Identidad', 'Document d''Identité', 'Identity Document',
     'Step: identity document', 'manual'),

    ('workflow', 'workflow.step.documentos', 'workflow_ui',
     'Documentos', 'Documents', 'Documents',
     'Step: generic documents', 'manual'),

    -- Form review steps
    ('workflow', 'workflow.step.verificar_datos_1_2', 'workflow_ui',
     'Verificar Datos (1/2)', 'Vérifier les Données (1/2)', 'Verify Data (1/2)',
     'Step: verify data 1 of 2', 'manual'),

    ('workflow', 'workflow.step.verificar_datos_2_2', 'workflow_ui',
     'Verificar Datos (2/2)', 'Vérifier les Données (2/2)', 'Verify Data (2/2)',
     'Step: verify data 2 of 2', 'manual'),

    ('workflow', 'workflow.step.verificar_datos_1_3', 'workflow_ui',
     'Verificar Datos (1/3)', 'Vérifier les Données (1/3)', 'Verify Data (1/3)',
     'Step: verify data 1 of 3', 'manual'),

    ('workflow', 'workflow.step.verificar_datos_2_3', 'workflow_ui',
     'Verificar Datos (2/3)', 'Vérifier les Données (2/3)', 'Verify Data (2/3)',
     'Step: verify data 2 of 3', 'manual'),

    ('workflow', 'workflow.step.verificar_datos_3_3', 'workflow_ui',
     'Verificar Datos (3/3)', 'Vérifier les Données (3/3)', 'Verify Data (3/3)',
     'Step: verify data 3 of 3', 'manual'),

    ('workflow', 'workflow.step.verificar_datos', 'workflow_ui',
     'Verificar Datos', 'Vérifier les Données', 'Verify Data',
     'Step: generic verify data', 'manual'),

    ('workflow', 'workflow.step.verificar_representantes_legales', 'workflow_ui',
     'Verificar Representantes Legales', 'Vérifier les Représentants Légaux', 'Verify Legal Representatives',
     'Step: verify legal representatives', 'manual'),

    ('workflow', 'workflow.step.verificar_datos_funcionario', 'workflow_ui',
     'Verificar Datos del Funcionario', 'Vérifier les Données du Fonctionnaire', 'Verify Civil Servant Data',
     'Step: verify civil servant data', 'manual'),

    ('workflow', 'workflow.step.datos_vehiculo', 'workflow_ui',
     'Datos del Vehículo', 'Données du Véhicule', 'Vehicle Data',
     'Step: vehicle data', 'manual'),

    ('workflow', 'workflow.step.datos_propietario', 'workflow_ui',
     'Datos del Propietario', 'Données du Propriétaire', 'Owner Data',
     'Step: owner data', 'manual'),

    ('workflow', 'workflow.step.datos_propietario_vehiculo', 'workflow_ui',
     'Datos del Propietario y Vehículo', 'Données du Propriétaire et Véhicule', 'Owner and Vehicle Data',
     'Step: owner and vehicle data', 'manual'),

    ('workflow', 'workflow.step.datos_tecnicos', 'workflow_ui',
     'Datos Técnicos', 'Données Techniques', 'Technical Data',
     'Step: technical data', 'manual'),

    ('workflow', 'workflow.step.datos_personales', 'workflow_ui',
     'Datos Personales', 'Données Personnelles', 'Personal Data',
     'Step: personal data', 'manual'),

    ('workflow', 'workflow.step.datos_identidad_entrada', 'workflow_ui',
     'Datos de Identidad y Entrada', 'Données d''Identité et d''Entrée', 'Identity and Entry Data',
     'Step: identity and entry data', 'manual'),

    ('workflow', 'workflow.step.datos_profesionales', 'workflow_ui',
     'Datos Profesionales', 'Données Professionnelles', 'Professional Data',
     'Step: professional data', 'manual'),

    ('workflow', 'workflow.step.datos_pasaporte_visado_entrada', 'workflow_ui',
     'Datos del Pasaporte, Visado y Entrada', 'Données du Passeport, Visa et Entrée', 'Passport, Visa and Entry Data',
     'Step: passport, visa and entry data', 'manual'),

    ('workflow', 'workflow.step.datos_funcionario', 'workflow_ui',
     'Datos del Funcionario', 'Données du Fonctionnaire', 'Civil Servant Data',
     'Step: civil servant data', 'manual'),

    ('workflow', 'workflow.step.datos_administrativos_contacto', 'workflow_ui',
     'Datos Administrativos y Contacto', 'Données Administratives et Contact', 'Administrative Data and Contact',
     'Step: administrative data and contact', 'manual'),

    ('workflow', 'workflow.step.verificacion_documentos_soporte', 'workflow_ui',
     'Verificación de Documentos de Soporte', 'Vérification des Documents de Support', 'Support Document Verification',
     'Step: support document verification', 'manual'),

    ('workflow', 'workflow.step.revision_obligaciones', 'workflow_ui',
     'Revisión de Obligaciones', 'Révision des Obligations', 'Obligations Review',
     'Step: obligations review', 'manual'),

    ('workflow', 'workflow.step.identificacion_empresa', 'workflow_ui',
     'Identificación de la Empresa', 'Identification de l''Entreprise', 'Company Identification',
     'Step: company identification', 'manual'),

    ('workflow', 'workflow.step.matricula_funcionario', 'workflow_ui',
     'Matrícula de Funcionario', 'Matricule du Fonctionnaire', 'Civil Servant ID Number',
     'Step: civil servant ID number', 'manual'),

    -- Appointment & site steps
    ('workflow', 'workflow.step.programar_cita', 'workflow_ui',
     'Programar Cita', 'Programmer un Rendez-vous', 'Schedule Appointment',
     'Step: schedule appointment', 'manual'),

    ('workflow', 'workflow.step.cita_extanjeria', 'workflow_ui',
     'Cita en Extranjería', 'Rendez-vous à l''Immigration', 'Immigration Appointment',
     'Step: immigration appointment', 'manual'),

    ('workflow', 'workflow.step.cita_biometrica', 'workflow_ui',
     'Cita para Captura Biométrica', 'Rendez-vous pour Capture Biométrique', 'Biometric Capture Appointment',
     'Step: biometric capture appointment', 'manual'),

    ('workflow', 'workflow.step.cita_recogida_permiso', 'workflow_ui',
     'Cita para Recogida del Permiso (CNEDOGE)', 'Rendez-vous pour Récupération du Permis (CNEDOGE)', 'Appointment for Permit Collection (CNEDOGE)',
     'Step: permit collection appointment', 'manual'),

    ('workflow', 'workflow.step.sitio_tramitacion', 'workflow_ui',
     'Sitio de Tramitación', 'Lieu de Traitement', 'Processing Location',
     'Step: processing location', 'manual'),

    ('workflow', 'workflow.step.cita', 'workflow_ui',
     'Cita', 'Rendez-vous', 'Appointment',
     'Step: generic appointment', 'manual'),

    -- Payment steps
    ('workflow', 'workflow.step.pago_tasas', 'workflow_ui',
     'Pago de Tasas', 'Paiement des Frais', 'Fee Payment',
     'Step: fee payment', 'manual'),

    ('workflow', 'workflow.step.pago_tasas_registro', 'workflow_ui',
     'Pago de Tasas de Registro', 'Paiement des Frais d''Enregistrement', 'Registration Fee Payment',
     'Step: registration fee payment', 'manual'),

    ('workflow', 'workflow.step.pago_tramite', 'workflow_ui',
     'Pago del Trámite', 'Paiement de la Procédure', 'Procedure Payment',
     'Step: procedure payment', 'manual'),

    ('workflow', 'workflow.step.pago_timbres', 'workflow_ui',
     'Pago de Timbres', 'Paiement des Timbres', 'Stamp Payment',
     'Step: stamp payment', 'manual'),

    ('workflow', 'workflow.step.pago_timbres_cedula_poliza', 'workflow_ui',
     'Pago de Timbres (Cédula y Póliza)', 'Paiement des Timbres (Cédule et Police)', 'Stamp Payment (Cedula and Policy)',
     'Step: stamp payment cedula and policy', 'manual'),

    ('workflow', 'workflow.step.pago_principal_permiso_residencia', 'workflow_ui',
     'Pago Principal del Permiso de Residencia', 'Paiement Principal du Permis de Résidence', 'Main Residence Permit Payment',
     'Step: main residence permit payment', 'manual'),

    ('workflow', 'workflow.step.pago', 'workflow_ui',
     'Pago', 'Paiement', 'Payment',
     'Step: generic payment', 'manual'),

    -- Confirmation steps
    ('workflow', 'workflow.step.confirmacion', 'workflow_ui',
     'Confirmación', 'Confirmation', 'Confirmation',
     'Step: confirmation', 'manual'),

    ('workflow', 'workflow.step.confirmacion_envio', 'workflow_ui',
     'Confirmación y Envío', 'Confirmation et Envoi', 'Confirmation and Submission',
     'Step: confirmation and submission', 'manual'),

    -- Residencia-specific
    ('workflow', 'workflow.step.nota_ingreso_identidad', 'workflow_ui',
     'Nota de Ingreso y Documento de Identidad', 'Note d''Entrée et Document d''Identité', 'Entry Note and Identity Document',
     'Step: entry note and identity document', 'manual'),

    ('workflow', 'workflow.step.verificacion_nota_ingreso', 'workflow_ui',
     'Verificación de la Nota de Ingreso', 'Vérification de la Note d''Entrée', 'Entry Note Verification',
     'Step: entry note verification', 'manual')

ON CONFLICT (category, key_code, context) DO UPDATE SET
    es = EXCLUDED.es,
    fr = EXCLUDED.fr,
    en = EXCLUDED.en,
    description = EXCLUDED.description,
    updated_at = NOW();


-- =============================================================================
-- 3. GENERIC UI LABELS
-- =============================================================================

INSERT INTO translations (category, key_code, context, es, fr, en, description, translation_source)
VALUES
    ('workflow', 'workflow.label.continue', 'workflow_ui',
     'Continuar', 'Continuer', 'Continue',
     'UI: continue button', 'manual'),

    ('workflow', 'workflow.label.previous', 'workflow_ui',
     'Anterior', 'Précédent', 'Previous',
     'UI: previous button', 'manual'),

    ('workflow', 'workflow.label.cancel', 'workflow_ui',
     'Cancelar', 'Annuler', 'Cancel',
     'UI: cancel button', 'manual'),

    ('workflow', 'workflow.label.loading', 'workflow_ui',
     'Cargando...', 'Chargement...', 'Loading...',
     'UI: loading', 'manual'),

    ('workflow', 'workflow.label.session_expired', 'workflow_ui',
     'Sesión expirada', 'Session expirée', 'Session expired',
     'UI: session expired', 'manual'),

    ('workflow', 'workflow.label.select_at_least_one', 'workflow_ui',
     'Seleccione al menos una opción', 'Sélectionnez au moins une option', 'Select at least one option',
     'UI: select at least one', 'manual'),

    ('workflow', 'workflow.label.error_loading', 'workflow_ui',
     'Error al cargar la configuración', 'Erreur de chargement de la configuration', 'Error loading configuration',
     'UI: error loading workflow config', 'manual'),

    ('workflow', 'workflow.label.retry', 'workflow_ui',
     'Reintentar', 'Réessayer', 'Retry',
     'UI: retry button', 'manual')

ON CONFLICT (category, key_code, context) DO UPDATE SET
    es = EXCLUDED.es,
    fr = EXCLUDED.fr,
    en = EXCLUDED.en,
    description = EXCLUDED.description,
    updated_at = NOW();


-- =============================================================================
-- 4. PASAPORTE OPTION LABELS & DESCRIPTIONS
-- =============================================================================

INSERT INTO translations (category, key_code, context, es, fr, en, description, translation_source)
VALUES
    -- solicitud_type options
    ('workflow', 'workflow.option.pasaporte.expedicion', 'workflow_ui',
     'Primera Expedición', 'Première Délivrance', 'First Issue',
     'Pasaporte option: first issuance', 'manual'),
    ('workflow', 'workflow.option.pasaporte.expedicion.desc', 'workflow_ui',
     'Solicito mi primer pasaporte', 'Je demande mon premier passeport', 'I am applying for my first passport',
     'Pasaporte option desc: first issuance', 'manual'),

    ('workflow', 'workflow.option.pasaporte.renovacion', 'workflow_ui',
     'Renovación', 'Renouvellement', 'Renewal',
     'Pasaporte option: renewal', 'manual'),
    ('workflow', 'workflow.option.pasaporte.renovacion.desc', 'workflow_ui',
     'Ya tengo un pasaporte (vencido, perdido, robado o dañado)', 'J''ai déjà un passeport (expiré, perdu, volé ou endommagé)', 'I already have a passport (expired, lost, stolen or damaged)',
     'Pasaporte option desc: renewal', 'manual'),

    -- motivo options (shared pattern)
    ('workflow', 'workflow.motivo.VENCIMIENTO', 'workflow_ui',
     'Vencimiento', 'Expiration', 'Expiration',
     'Motivo: expiration', 'manual'),
    ('workflow', 'workflow.motivo.VENCIMIENTO.desc', 'workflow_ui',
     'Mi pasaporte está vencido o por vencer', 'Mon passeport est expiré ou va expirer', 'My passport is expired or about to expire',
     'Motivo desc: expiration', 'manual'),

    ('workflow', 'workflow.motivo.PERDIDA', 'workflow_ui',
     'Pérdida', 'Perte', 'Loss',
     'Motivo: loss', 'manual'),
    ('workflow', 'workflow.motivo.PERDIDA.desc', 'workflow_ui',
     'Perdí mi documento (requiere denuncia policial)', 'J''ai perdu mon document (nécessite un rapport de police)', 'I lost my document (requires police report)',
     'Motivo desc: loss', 'manual'),

    ('workflow', 'workflow.motivo.ROBO', 'workflow_ui',
     'Robo', 'Vol', 'Theft',
     'Motivo: theft', 'manual'),
    ('workflow', 'workflow.motivo.ROBO.desc', 'workflow_ui',
     'Me robaron mi documento (requiere denuncia policial)', 'Mon document a été volé (nécessite un rapport de police)', 'My document was stolen (requires police report)',
     'Motivo desc: theft', 'manual'),

    ('workflow', 'workflow.motivo.DETERIORO', 'workflow_ui',
     'Deterioro', 'Détérioration', 'Deterioration',
     'Motivo: deterioration', 'manual'),
    ('workflow', 'workflow.motivo.DETERIORO.desc', 'workflow_ui',
     'Mi documento está dañado', 'Mon document est endommagé', 'My document is damaged',
     'Motivo desc: deterioration', 'manual'),

    -- Representantes legales options
    ('workflow', 'workflow.option.pasaporte.ambos_representantes', 'workflow_ui',
     'Ambos padres/tutores', 'Les deux parents/tuteurs', 'Both parents/guardians',
     'Pasaporte option: both representatives', 'manual'),
    ('workflow', 'workflow.option.pasaporte.ambos_representantes.desc', 'workflow_ui',
     'Ambos representantes legales realizarán el trámite', 'Les deux représentants légaux effectueront la procédure', 'Both legal representatives will carry out the procedure',
     'Pasaporte option desc: both representatives', 'manual'),

    ('workflow', 'workflow.option.pasaporte.representante_unico', 'workflow_ui',
     'Representante único', 'Représentant unique', 'Single representative',
     'Pasaporte option: single representative', 'manual'),
    ('workflow', 'workflow.option.pasaporte.representante_unico.desc', 'workflow_ui',
     'Solo un padre/tutor realizará el trámite (custodia exclusiva, fallecimiento, etc.)', 'Seul un parent/tuteur effectuera la procédure (garde exclusive, décès, etc.)', 'Only one parent/guardian will carry out the procedure (exclusive custody, death, etc.)',
     'Pasaporte option desc: single representative', 'manual'),

    -- Motivo representante unico options
    ('workflow', 'workflow.option.pasaporte.CUSTODIA_EXCLUSIVA', 'workflow_ui',
     'Custodia exclusiva', 'Garde exclusive', 'Exclusive custody',
     'Pasaporte option: exclusive custody', 'manual'),
    ('workflow', 'workflow.option.pasaporte.CUSTODIA_EXCLUSIVA.desc', 'workflow_ui',
     'Tiene la custodia exclusiva del menor', 'Vous avez la garde exclusive du mineur', 'You have exclusive custody of the minor',
     'Pasaporte option desc: exclusive custody', 'manual'),

    ('workflow', 'workflow.option.pasaporte.FALLECIMIENTO', 'workflow_ui',
     'Fallecimiento del otro progenitor', 'Décès de l''autre parent', 'Death of the other parent',
     'Pasaporte option: death of other parent', 'manual'),
    ('workflow', 'workflow.option.pasaporte.FALLECIMIENTO.desc', 'workflow_ui',
     'El otro padre/madre ha fallecido', 'L''autre parent est décédé', 'The other parent has passed away',
     'Pasaporte option desc: death of other parent', 'manual'),

    ('workflow', 'workflow.option.pasaporte.PADRE_DESCONOCIDO', 'workflow_ui',
     'Padre/Madre desconocido', 'Parent inconnu', 'Unknown parent',
     'Pasaporte option: unknown parent', 'manual'),
    ('workflow', 'workflow.option.pasaporte.PADRE_DESCONOCIDO.desc', 'workflow_ui',
     'Uno de los progenitores es desconocido', 'L''un des parents est inconnu', 'One of the parents is unknown',
     'Pasaporte option desc: unknown parent', 'manual'),

    ('workflow', 'workflow.option.pasaporte.OTRO', 'workflow_ui',
     'Otro motivo', 'Autre motif', 'Other reason',
     'Pasaporte option: other reason', 'manual'),
    ('workflow', 'workflow.option.pasaporte.OTRO.desc', 'workflow_ui',
     'Otro motivo legal documentado', 'Autre motif légal documenté', 'Other documented legal reason',
     'Pasaporte option desc: other reason', 'manual'),

    -- Applicant type (shared pasaporte/conducir)
    ('workflow', 'workflow.option.applicant.citizen_gq', 'workflow_ui',
     'Ciudadano Ecuatoguineano (DIP)', 'Citoyen Équatoguinéen (DIP)', 'Equatoguinean Citizen (DIP)',
     'Applicant type: citizen GQ', 'manual'),
    ('workflow', 'workflow.option.applicant.citizen_gq.desc', 'workflow_ui',
     'Tengo Documento de Identidad Personal (DIP)', 'J''ai un Document d''Identité Personnel (DIP)', 'I have a Personal Identity Document (DIP)',
     'Applicant type desc: citizen GQ', 'manual'),

    ('workflow', 'workflow.option.applicant.resident', 'workflow_ui',
     'Residente Extranjero (NIE)', 'Résident Étranger (NIE)', 'Foreign Resident (NIE)',
     'Applicant type: resident', 'manual'),
    ('workflow', 'workflow.option.applicant.resident.desc', 'workflow_ui',
     'Tengo Permiso de Residencia (NIE)', 'J''ai un Permis de Résidence (NIE)', 'I have a Residence Permit (NIE)',
     'Applicant type desc: resident', 'manual'),

    -- is_minor options (pasaporte)
    ('workflow', 'workflow.option.pasaporte.adulto', 'workflow_ui',
     'Adulto (18 años o más)', 'Adulte (18 ans ou plus)', 'Adult (18 years or older)',
     'Pasaporte option: adult', 'manual'),
    ('workflow', 'workflow.option.pasaporte.menor', 'workflow_ui',
     'Menor de edad', 'Mineur', 'Minor',
     'Pasaporte option: minor', 'manual')

ON CONFLICT (category, key_code, context) DO UPDATE SET
    es = EXCLUDED.es,
    fr = EXCLUDED.fr,
    en = EXCLUDED.en,
    description = EXCLUDED.description,
    updated_at = NOW();


-- =============================================================================
-- 5. CONDUCIR OPTION LABELS & DESCRIPTIONS
-- =============================================================================

INSERT INTO translations (category, key_code, context, es, fr, en, description, translation_source)
VALUES
    ('workflow', 'workflow.option.conducir.NUEVO', 'workflow_ui',
     'Primer Certificado', 'Premier Certificat', 'First Certificate',
     'Conducir option: first certificate', 'manual'),
    ('workflow', 'workflow.option.conducir.NUEVO.desc', 'workflow_ui',
     'Solicito mi primer certificado para conducir (requiere examen)', 'Je demande mon premier certificat de conduite (examen requis)', 'I am applying for my first driving certificate (exam required)',
     'Conducir option desc: first certificate', 'manual'),

    ('workflow', 'workflow.option.conducir.CANJE', 'workflow_ui',
     'Canje de Permiso Extranjero', 'Échange de Permis Étranger', 'Foreign License Exchange',
     'Conducir option: foreign exchange', 'manual'),
    ('workflow', 'workflow.option.conducir.CANJE.desc', 'workflow_ui',
     'Convierto mi permiso de conducir extranjero', 'Je convertis mon permis de conduire étranger', 'I am converting my foreign driving license',
     'Conducir option desc: foreign exchange', 'manual'),

    ('workflow', 'workflow.option.conducir.RENOVACION', 'workflow_ui',
     'Renovación', 'Renouvellement', 'Renewal',
     'Conducir option: renewal', 'manual'),
    ('workflow', 'workflow.option.conducir.RENOVACION.desc', 'workflow_ui',
     'Renuevo mi certificado vencido o por vencer', 'Je renouvelle mon certificat expiré ou expirant', 'I am renewing my expired or expiring certificate',
     'Conducir option desc: renewal', 'manual'),

    ('workflow', 'workflow.option.conducir.DUPLICADO', 'workflow_ui',
     'Duplicado', 'Duplicata', 'Duplicate',
     'Conducir option: duplicate', 'manual'),
    ('workflow', 'workflow.option.conducir.DUPLICADO.desc', 'workflow_ui',
     'Solicito un duplicado (pérdida, robo o deterioro)', 'Je demande un duplicata (perte, vol ou détérioration)', 'I am requesting a duplicate (loss, theft or deterioration)',
     'Conducir option desc: duplicate', 'manual'),

    ('workflow', 'workflow.option.conducir.EXTENSION', 'workflow_ui',
     'Extensión de Clases', 'Extension de Classes', 'Class Extension',
     'Conducir option: class extension', 'manual'),
    ('workflow', 'workflow.option.conducir.EXTENSION.desc', 'workflow_ui',
     'Añado nuevas clases a mi certificado actual', 'J''ajoute de nouvelles classes à mon certificat actuel', 'I am adding new classes to my current certificate',
     'Conducir option desc: class extension', 'manual'),

    -- Permit classes
    ('workflow', 'workflow.option.conducir.clase_A', 'workflow_ui',
     'A - Motocicletas', 'A - Motos', 'A - Motorcycles',
     'Conducir class: A motorcycles', 'manual'),
    ('workflow', 'workflow.option.conducir.clase_B', 'workflow_ui',
     'B - Vehículos ligeros', 'B - Véhicules légers', 'B - Light vehicles',
     'Conducir class: B light vehicles', 'manual'),
    ('workflow', 'workflow.option.conducir.clase_B_plus', 'workflow_ui',
     'B+ - Vehículos ligeros con remolque', 'B+ - Véhicules légers avec remorque', 'B+ - Light vehicles with trailer',
     'Conducir class: B+ light vehicles with trailer', 'manual'),
    ('workflow', 'workflow.option.conducir.clase_C', 'workflow_ui',
     'C - Camiones', 'C - Camions', 'C - Trucks',
     'Conducir class: C trucks', 'manual'),
    ('workflow', 'workflow.option.conducir.clase_D', 'workflow_ui',
     'D - Autobuses', 'D - Autobus', 'D - Buses',
     'Conducir class: D buses', 'manual'),
    ('workflow', 'workflow.option.conducir.clase_E', 'workflow_ui',
     'E - Vehículos articulados', 'E - Véhicules articulés', 'E - Articulated vehicles',
     'Conducir class: E articulated vehicles', 'manual'),
    ('workflow', 'workflow.option.conducir.clase_F', 'workflow_ui',
     'F - Vehículos especiales', 'F - Véhicules spéciaux', 'F - Special vehicles',
     'Conducir class: F special vehicles', 'manual')

ON CONFLICT (category, key_code, context) DO UPDATE SET
    es = EXCLUDED.es,
    fr = EXCLUDED.fr,
    en = EXCLUDED.en,
    description = EXCLUDED.description,
    updated_at = NOW();


-- =============================================================================
-- 6. CONTRATO OPTION LABELS & DESCRIPTIONS
-- =============================================================================

INSERT INTO translations (category, key_code, context, es, fr, en, description, translation_source)
VALUES
    ('workflow', 'workflow.option.contrato.OBRA', 'workflow_ui',
     'Contrato de Obra', 'Contrat de Travaux', 'Construction Contract',
     'Contrato option: construction', 'manual'),
    ('workflow', 'workflow.option.contrato.SERVICIO', 'workflow_ui',
     'Contrato de Servicio', 'Contrat de Service', 'Service Contract',
     'Contrato option: service', 'manual'),
    ('workflow', 'workflow.option.contrato.SUMINISTRO', 'workflow_ui',
     'Contrato de Suministro', 'Contrat de Fourniture', 'Supply Contract',
     'Contrato option: supply', 'manual'),
    ('workflow', 'workflow.option.contrato.CONCESION', 'workflow_ui',
     'Contrato de Concesión', 'Contrat de Concession', 'Concession Contract',
     'Contrato option: concession', 'manual'),
    ('workflow', 'workflow.option.contrato.JOINT_VENTURE', 'workflow_ui',
     'Joint Venture', 'Joint-Venture', 'Joint Venture',
     'Contrato option: joint venture', 'manual'),
    ('workflow', 'workflow.option.contrato.ARRENDAMIENTO', 'workflow_ui',
     'Contrato de Arrendamiento', 'Contrat de Location', 'Lease Contract',
     'Contrato option: lease', 'manual'),
    ('workflow', 'workflow.option.contrato.OTRO', 'workflow_ui',
     'Otro Tipo de Contrato', 'Autre Type de Contrat', 'Other Contract Type',
     'Contrato option: other', 'manual')

ON CONFLICT (category, key_code, context) DO UPDATE SET
    es = EXCLUDED.es,
    fr = EXCLUDED.fr,
    en = EXCLUDED.en,
    description = EXCLUDED.description,
    updated_at = NOW();


-- =============================================================================
-- 7. VEHICULO OPTION LABELS
-- =============================================================================

INSERT INTO translations (category, key_code, context, es, fr, en, description, translation_source)
VALUES
    ('workflow', 'workflow.option.vehiculo.PRIMERA_MATRICULACION', 'workflow_ui',
     'Primera Matriculación', 'Première Immatriculation', 'First Registration',
     'Vehiculo option: first registration', 'manual'),
    ('workflow', 'workflow.option.vehiculo.TRANSFERENCIA', 'workflow_ui',
     'Transferencia de Titularidad', 'Transfert de Propriété', 'Ownership Transfer',
     'Vehiculo option: transfer', 'manual'),
    ('workflow', 'workflow.option.vehiculo.RENOVACION_CUVE', 'workflow_ui',
     'Renovación de CUVE', 'Renouvellement du CUVE', 'CUVE Renewal',
     'Vehiculo option: CUVE renewal', 'manual'),
    ('workflow', 'workflow.option.vehiculo.RENOVACION_ITV', 'workflow_ui',
     'Renovación de ITV', 'Renouvellement de l''ITV', 'ITV Renewal',
     'Vehiculo option: ITV renewal', 'manual'),
    ('workflow', 'workflow.option.vehiculo.DUPLICADO_PERMISO', 'workflow_ui',
     'Duplicado del Permiso de Circulación', 'Duplicata du Permis de Circulation', 'Duplicate Circulation Permit',
     'Vehiculo option: duplicate circulation permit', 'manual'),
    ('workflow', 'workflow.option.vehiculo.DUPLICADO_CUVE', 'workflow_ui',
     'Duplicado del CUVE', 'Duplicata du CUVE', 'Duplicate CUVE',
     'Vehiculo option: duplicate CUVE', 'manual'),
    ('workflow', 'workflow.option.vehiculo.CAMBIO_CARACTERISTICAS', 'workflow_ui',
     'Cambio de Características', 'Changement de Caractéristiques', 'Change of Characteristics',
     'Vehiculo option: change characteristics', 'manual')

ON CONFLICT (category, key_code, context) DO UPDATE SET
    es = EXCLUDED.es,
    fr = EXCLUDED.fr,
    en = EXCLUDED.en,
    description = EXCLUDED.description,
    updated_at = NOW();


-- =============================================================================
-- 8. RESIDENCIA & VISADO OPTION LABELS
-- =============================================================================

INSERT INTO translations (category, key_code, context, es, fr, en, description, translation_source)
VALUES
    ('workflow', 'workflow.option.residencia.PRIMERA_VEZ', 'workflow_ui',
     'Primera vez', 'Première fois', 'First time',
     'Residencia option: first time', 'manual'),
    ('workflow', 'workflow.option.residencia.RENOVACION', 'workflow_ui',
     'Renovación', 'Renouvellement', 'Renewal',
     'Residencia option: renewal', 'manual'),

    -- Tramites visado sub_types
    ('workflow', 'workflow.option.visado.PRORROGA', 'workflow_ui',
     'Prórroga de Visado', 'Prolongation de Visa', 'Visa Extension',
     'Visado option: extension', 'manual'),
    ('workflow', 'workflow.option.visado.ALTERNATIVO', 'workflow_ui',
     'Visado Alternativo', 'Visa Alternatif', 'Alternative Visa',
     'Visado option: alternative', 'manual'),
    ('workflow', 'workflow.option.visado.PERMANENCIA', 'workflow_ui',
     'Permanencia en Extranjería', 'Permanence à l''Immigration', 'Stay at Immigration',
     'Visado option: stay', 'manual'),
    ('workflow', 'workflow.option.visado.SALIDA_VENCIDO', 'workflow_ui',
     'Salida con Visado Vencido', 'Sortie avec Visa Expiré', 'Exit with Expired Visa',
     'Visado option: exit with expired visa', 'manual')

ON CONFLICT (category, key_code, context) DO UPDATE SET
    es = EXCLUDED.es,
    fr = EXCLUDED.fr,
    en = EXCLUDED.en,
    description = EXCLUDED.description,
    updated_at = NOW();


-- =============================================================================
-- 9. FUNCION PUBLICA OPTION LABELS
-- =============================================================================

INSERT INTO translations (category, key_code, context, es, fr, en, description, translation_source)
VALUES
    -- Carnet funcionario
    ('workflow', 'workflow.option.carnet.expedicion', 'workflow_ui',
     'Primera Expedición', 'Première Délivrance', 'First Issue',
     'Carnet option: first issuance', 'manual'),
    ('workflow', 'workflow.option.carnet.renovacion', 'workflow_ui',
     'Renovación', 'Renouvellement', 'Renewal',
     'Carnet option: renewal', 'manual'),
    ('workflow', 'workflow.option.carnet.duplicado', 'workflow_ui',
     'Duplicado', 'Duplicata', 'Duplicate',
     'Carnet option: duplicate', 'manual'),

    -- Promocion administrativa
    ('workflow', 'workflow.option.promocion.ASCENSO', 'workflow_ui',
     'Ascenso de Categoría', 'Promotion de Catégorie', 'Category Promotion',
     'Promocion option: category promotion', 'manual'),
    ('workflow', 'workflow.option.promocion.CAMBIO_DESTINO', 'workflow_ui',
     'Cambio de Destino', 'Changement d''Affectation', 'Post Transfer',
     'Promocion option: post transfer', 'manual'),
    ('workflow', 'workflow.option.promocion.RECLASIFICACION', 'workflow_ui',
     'Reclasificación', 'Reclassification', 'Reclassification',
     'Promocion option: reclassification', 'manual'),

    -- Permiso extraordinario motivos
    ('workflow', 'workflow.option.permiso.MATRIMONIO', 'workflow_ui',
     'Matrimonio', 'Mariage', 'Marriage',
     'Permiso motivo: marriage', 'manual'),
    ('workflow', 'workflow.option.permiso.NACIMIENTO', 'workflow_ui',
     'Nacimiento de Hijo', 'Naissance d''un Enfant', 'Birth of Child',
     'Permiso motivo: birth', 'manual'),
    ('workflow', 'workflow.option.permiso.FALLECIMIENTO_FAMILIAR', 'workflow_ui',
     'Fallecimiento de Familiar', 'Décès d''un Proche', 'Death of Family Member',
     'Permiso motivo: family death', 'manual'),
    ('workflow', 'workflow.option.permiso.MUDANZA', 'workflow_ui',
     'Mudanza', 'Déménagement', 'Moving',
     'Permiso motivo: moving', 'manual'),
    ('workflow', 'workflow.option.permiso.EXAMEN', 'workflow_ui',
     'Examen Oficial', 'Examen Officiel', 'Official Exam',
     'Permiso motivo: exam', 'manual'),
    ('workflow', 'workflow.option.permiso.OTRO', 'workflow_ui',
     'Otro Motivo', 'Autre Motif', 'Other Reason',
     'Permiso motivo: other', 'manual'),

    -- Certificado administrativo tipos
    ('workflow', 'workflow.option.certificado.SERVICIO_ACTIVO', 'workflow_ui',
     'Certificado de Servicio Activo', 'Certificat de Service Actif', 'Active Service Certificate',
     'Certificado type: active service', 'manual'),
    ('workflow', 'workflow.option.certificado.HABERES', 'workflow_ui',
     'Certificado de Haberes', 'Certificat de Salaire', 'Salary Certificate',
     'Certificado type: salary', 'manual'),
    ('workflow', 'workflow.option.certificado.ANTIGUEDAD', 'workflow_ui',
     'Certificado de Antigüedad', 'Certificat d''Ancienneté', 'Seniority Certificate',
     'Certificado type: seniority', 'manual'),
    ('workflow', 'workflow.option.certificado.BUENA_CONDUCTA', 'workflow_ui',
     'Certificado de Buena Conducta', 'Certificat de Bonne Conduite', 'Good Conduct Certificate',
     'Certificado type: good conduct', 'manual'),
    ('workflow', 'workflow.option.certificado.OTRO', 'workflow_ui',
     'Otro Certificado', 'Autre Certificat', 'Other Certificate',
     'Certificado type: other', 'manual')

ON CONFLICT (category, key_code, context) DO UPDATE SET
    es = EXCLUDED.es,
    fr = EXCLUDED.fr,
    en = EXCLUDED.en,
    description = EXCLUDED.description,
    updated_at = NOW();
