-- Migration 180: Reduce display_config list_columns for split-view
--
-- Purpose: Limit split-view preview to 10-15 critical business fields per workflow
-- so agents can validate directly from the split-view without opening detail page.
--
-- Architecture: display_config.list_columns is the SINGLE source of truth for
-- the split-view "Datos de la Solicitud" section. Admin can add/remove columns
-- via /admin/menu-config/display and changes appear automatically.
--
-- Fields selected by business criticality:
--   Identity docs: numero + nombre + natural_de + fecha_expiracion
--   Certificates: resultado + key identifiers
--   Contracts: tipo + numero + monto + empresa
--   Vehicles: matricula + marca + numero_bastidor

-- ═══════════════════════════════════════════════════════════════
-- PASAPORTE (5 workflows)
-- ═══════════════════════════════════════════════════════════════

-- NOTE: ALL pasaporte sub-types (renovacion, deterioro, perdida, robo) are stored
-- as workflow_code='PASAPORTE_NUEVO' in service_requests. So this config must include
-- ALL possible document columns. Fields for non-uploaded docs are filtered (null→skipped).
UPDATE workflow_display_config SET list_columns = '[
  "dip.numero_dip", "dip.apellidos", "dip.nombres", "dip.natural_de", "dip.fecha_expiracion",
  "pasaporte_antiguo.numero_pasaporte", "pasaporte_antiguo.apellidos", "pasaporte_antiguo.fecha_expiracion",
  "certificado_nacimiento.nombre", "certificado_nacimiento.primer_apellido",
  "certificado_nacimiento.lugar_nacimiento", "certificado_nacimiento.hijo_de", "certificado_nacimiento.y_de",
  "autorizacion_parental.nombre_completo", "autorizacion_parental.parentesco",
  "documento_representante_1.numero_dip", "documento_representante_1.apellidos", "documento_representante_1.nombres"
]'::jsonb WHERE workflow_code = 'PASAPORTE_NUEVO';

UPDATE workflow_display_config SET list_columns = '[
  "dip.numero_dip", "dip.apellidos", "dip.nombres", "dip.natural_de", "dip.fecha_expiracion",
  "pasaporte_antiguo.numero_pasaporte", "pasaporte_antiguo.apellidos", "pasaporte_antiguo.fecha_expiracion",
  "certificado_nacimiento.nombre", "certificado_nacimiento.primer_apellido",
  "certificado_nacimiento.hijo_de", "certificado_nacimiento.y_de",
  "autorizacion_parental.nombre_completo", "autorizacion_parental.parentesco",
  "documento_representante_1.numero_dip"
]'::jsonb WHERE workflow_code = 'PASAPORTE_RENOVACION';

UPDATE workflow_display_config SET list_columns = '[
  "dip.numero_dip", "dip.apellidos", "dip.nombres", "dip.natural_de", "dip.fecha_expiracion",
  "pasaporte_antiguo.numero_pasaporte", "pasaporte_antiguo.apellidos", "pasaporte_antiguo.fecha_expiracion",
  "certificado_nacimiento.nombre", "certificado_nacimiento.primer_apellido",
  "certificado_nacimiento.hijo_de", "certificado_nacimiento.y_de",
  "autorizacion_parental.nombre_completo", "autorizacion_parental.parentesco",
  "documento_representante_1.numero_dip"
]'::jsonb WHERE workflow_code = 'PASAPORTE_DETERIORO';

UPDATE workflow_display_config SET list_columns = '[
  "dip.numero_dip", "dip.apellidos", "dip.nombres", "dip.natural_de", "dip.fecha_expiracion",
  "certificado_nacimiento.nombre", "certificado_nacimiento.primer_apellido",
  "certificado_nacimiento.hijo_de", "certificado_nacimiento.y_de",
  "autorizacion_parental.nombre_completo", "autorizacion_parental.parentesco",
  "documento_representante_1.numero_dip"
]'::jsonb WHERE workflow_code = 'PASAPORTE_PERDIDA';

UPDATE workflow_display_config SET list_columns = '[
  "dip.numero_dip", "dip.apellidos", "dip.nombres", "dip.natural_de", "dip.fecha_expiracion",
  "certificado_nacimiento.nombre", "certificado_nacimiento.primer_apellido",
  "certificado_nacimiento.hijo_de", "certificado_nacimiento.y_de",
  "autorizacion_parental.nombre_completo", "autorizacion_parental.parentesco",
  "documento_representante_1.numero_dip"
]'::jsonb WHERE workflow_code = 'PASAPORTE_ROBO';

-- ═══════════════════════════════════════════════════════════════
-- CONDUCIR (5 workflows)
-- ═══════════════════════════════════════════════════════════════

UPDATE workflow_display_config SET list_columns = '[
  "dip.numero_dip", "dip.apellidos", "dip.nombres", "dip.natural_de", "dip.fecha_expiracion",
  "permiso_residencia.numero_nie", "permiso_residencia.apellidos", "permiso_residencia.nombres", "permiso_residencia.fecha_expiracion",
  "certificado_medico.resultado", "certificado_medico.nombre_centro", "certificado_medico.nombre_medico"
]'::jsonb WHERE workflow_code = 'CONDUCIR_NUEVO';

UPDATE workflow_display_config SET list_columns = '[
  "dip.numero_dip", "dip.apellidos", "dip.nombres", "dip.natural_de", "dip.fecha_expiracion",
  "permiso_residencia.numero_nie", "permiso_residencia.fecha_expiracion",
  "certificado_actual.reg_numero", "certificado_actual.nombre", "certificado_actual.apellidos", "certificado_actual.clase_principal"
]'::jsonb WHERE workflow_code = 'CONDUCIR_RENOVACION';

UPDATE workflow_display_config SET list_columns = '[
  "dip.numero_dip", "dip.apellidos", "dip.nombres", "dip.natural_de", "dip.fecha_expiracion",
  "permiso_residencia.numero_nie", "permiso_residencia.fecha_expiracion",
  "certificado_actual.reg_numero", "certificado_actual.nombre", "certificado_actual.apellidos", "certificado_actual.clase_principal",
  "certificado_medico.resultado", "certificado_medico.nombre_centro", "certificado_medico.nombre_medico"
]'::jsonb WHERE workflow_code = 'CONDUCIR_EXTENSION';

UPDATE workflow_display_config SET list_columns = '[
  "dip.numero_dip", "dip.apellidos", "dip.nombres", "dip.natural_de", "dip.fecha_expiracion",
  "permiso_residencia.numero_nie", "permiso_residencia.apellidos", "permiso_residencia.nombres", "permiso_residencia.fecha_expiracion"
]'::jsonb WHERE workflow_code = 'CONDUCIR_CANJE';

UPDATE workflow_display_config SET list_columns = '[
  "dip.numero_dip", "dip.apellidos", "dip.nombres", "dip.natural_de", "dip.fecha_expiracion",
  "permiso_residencia.numero_nie", "permiso_residencia.apellidos", "permiso_residencia.nombres", "permiso_residencia.fecha_expiracion"
]'::jsonb WHERE workflow_code = 'CONDUCIR_DUPLICADO';

-- ═══════════════════════════════════════════════════════════════
-- CONTRATO (7 workflows)
-- ═══════════════════════════════════════════════════════════════

UPDATE workflow_display_config SET list_columns = '[
  "contrato.tipo_contrato", "contrato.numero_contrato", "contrato.monto_total", "contrato.nombre_empresa",
  "certificado_nif.nif", "certificado_nif.denominacion_social",
  "identidad_representante.numero_dip", "identidad_representante.apellidos", "identidad_representante.nombres",
  "escritura_constitucion.sociedad_nombre", "escritura_constitucion.nombre_notario",
  "licencia_comercio.numero_licencia", "licencia_comercio.denominacion_social"
]'::jsonb WHERE workflow_code IN (
  'CONTRATO_ARRENDAMIENTO', 'CONTRATO_OBRA', 'CONTRATO_SUMINISTRO',
  'CONTRATO_JOINT_VENTURE', 'CONTRATO_OTRO', 'CONTRATO_SERVICIO'
);

UPDATE workflow_display_config SET list_columns = '[
  "contrato.tipo_contrato", "contrato.numero_contrato", "contrato.monto_total", "contrato.nombre_empresa",
  "certificado_nif.nif", "certificado_nif.denominacion_social",
  "identidad_representante.numero_dip", "identidad_representante.apellidos", "identidad_representante.nombres",
  "escritura_constitucion.sociedad_nombre", "escritura_constitucion.nombre_notario",
  "licencia_comercio.numero_licencia", "licencia_comercio.denominacion_social",
  "autorizacion_gubernativa.numero_autorizacion", "autorizacion_gubernativa.actividad"
]'::jsonb WHERE workflow_code = 'CONTRATO_CONCESION';

-- ═══════════════════════════════════════════════════════════════
-- RESIDENCIA (2 workflows)
-- ═══════════════════════════════════════════════════════════════

UPDATE workflow_display_config SET list_columns = '[
  "pasaporte.numero_pasaporte", "pasaporte.apellidos", "pasaporte.nombres", "pasaporte.nacionalidad", "pasaporte.fecha_expiracion",
  "sello_entrada.fecha_entrada", "sello_entrada.puesto_fronterizo",
  "visado_entrada.numero_visado", "visado_entrada.tipo_visado",
  "permiso_trabajo.tipo_permiso", "permiso_trabajo.razon_social",
  "certificado_conducta.resultado",
  "antecedentes_penales.resultado",
  "solvencia_tributaria.resultado", "solvencia_tributaria.nif"
]'::jsonb WHERE workflow_code = 'RESIDENCIA_PRIMERA_VEZ';

UPDATE workflow_display_config SET list_columns = '[
  "pasaporte.numero_pasaporte", "pasaporte.apellidos", "pasaporte.nombres", "pasaporte.nacionalidad", "pasaporte.fecha_expiracion",
  "residencia_anterior.numero_nie", "residencia_anterior.apellidos", "residencia_anterior.nombres", "residencia_anterior.fecha_expiracion",
  "permiso_trabajo.tipo_permiso", "permiso_trabajo.razon_social",
  "certificado_conducta.resultado",
  "antecedentes_penales.resultado",
  "solvencia_tributaria.resultado", "solvencia_tributaria.nif"
]'::jsonb WHERE workflow_code = 'RESIDENCIA_RENOVACION';

-- ═══════════════════════════════════════════════════════════════
-- VISADO / EXTRANJERIA (4 workflows)
-- ═══════════════════════════════════════════════════════════════

UPDATE workflow_display_config SET list_columns = '[
  "pasaporte.numero_pasaporte", "pasaporte.apellidos", "pasaporte.nombres", "pasaporte.nacionalidad", "pasaporte.fecha_expiracion",
  "sello_entrada.fecha_entrada", "sello_entrada.puesto_fronterizo",
  "visado_entrada.numero_visado", "visado_entrada.tipo_visado", "visado_entrada.fecha_expedicion"
]'::jsonb WHERE workflow_code IN (
  'PRORROGA_VISADO', 'PERMANENCIA_EXTRANJERIA', 'SALIDA_VISADO_VENCIDO', 'VISADO_ALTERNATIVO'
);

-- ═══════════════════════════════════════════════════════════════
-- VEHICULO (7 workflows)
-- ═══════════════════════════════════════════════════════════════

UPDATE workflow_display_config SET list_columns = '[
  "certificado_reconocimiento.nombre_completo", "certificado_reconocimiento.marca",
  "certificado_reconocimiento.numero_bastidor", "certificado_reconocimiento.tipo_combustible",
  "identidad_propietario.numero_dip", "identidad_propietario.apellidos", "identidad_propietario.nombres", "identidad_propietario.fecha_expiracion"
]'::jsonb WHERE workflow_code = 'VEHICULO_PRIMERA_MATRICULACION';

UPDATE workflow_display_config SET list_columns = '[
  "cuve.matricula", "cuve.marca", "cuve.numero_bastidor",
  "identidad_propietario.numero_dip", "identidad_propietario.apellidos", "identidad_propietario.nombres",
  "permiso_circulacion.matricula", "permiso_circulacion.nombre", "permiso_circulacion.apellidos", "permiso_circulacion.marca"
]'::jsonb WHERE workflow_code IN (
  'VEHICULO_CAMBIO_CARACTERISTICAS', 'VEHICULO_DUPLICADO_CUVE', 'VEHICULO_DUPLICADO_PERMISO'
);

UPDATE workflow_display_config SET list_columns = '[
  "cuve_antigua.matricula", "cuve_antigua.marca", "cuve_antigua.numero_bastidor",
  "identidad_propietario.numero_dip", "identidad_propietario.apellidos", "identidad_propietario.nombres",
  "itv.resultado", "itv.matricula", "itv.valedero_hasta",
  "permiso_circulacion.matricula", "permiso_circulacion.nombre", "permiso_circulacion.apellidos"
]'::jsonb WHERE workflow_code = 'VEHICULO_RENOVACION_CUVE';

UPDATE workflow_display_config SET list_columns = '[
  "itv_antigua.resultado", "itv_antigua.matricula", "itv_antigua.valedero_hasta",
  "identidad_propietario.numero_dip", "identidad_propietario.apellidos", "identidad_propietario.nombres",
  "permiso_circulacion.matricula", "permiso_circulacion.nombre", "permiso_circulacion.apellidos", "permiso_circulacion.marca"
]'::jsonb WHERE workflow_code = 'VEHICULO_RENOVACION_ITV';

UPDATE workflow_display_config SET list_columns = '[
  "contrato_compraventa.matricula", "contrato_compraventa.monto", "contrato_compraventa.fecha", "contrato_compraventa.nombre_completo",
  "cuve.matricula", "cuve.marca", "cuve.numero_bastidor",
  "identidad_comprador.numero_dip", "identidad_comprador.apellidos", "identidad_comprador.nombres",
  "identidad_vendedor.numero_dip", "identidad_vendedor.apellidos", "identidad_vendedor.nombres",
  "permiso_circulacion.matricula"
]'::jsonb WHERE workflow_code = 'VEHICULO_TRANSFERENCIA';

-- ═══════════════════════════════════════════════════════════════
-- FUNCION PUBLICA (5 workflows)
-- ═══════════════════════════════════════════════════════════════

UPDATE workflow_display_config SET list_columns = '[
  "dip.numero_dip", "dip.apellidos", "dip.nombres", "dip.natural_de", "dip.fecha_expiracion"
]'::jsonb WHERE workflow_code = 'FP_VERIFICACION_FUNCIONARIO';

UPDATE workflow_display_config SET list_columns = '[
  "carnet_funcionario.matricula", "carnet_funcionario.cargo", "carnet_funcionario.ministerio"
]'::jsonb WHERE workflow_code = 'FP_PERMISO_EXTRAORDINARIO';

UPDATE workflow_display_config SET list_columns = '[
  "dip.numero_dip", "dip.apellidos", "dip.nombres", "dip.natural_de", "dip.fecha_expiracion",
  "carnet_expirado.matricula", "carnet_expirado.cargo", "carnet_expirado.ministerio"
]'::jsonb WHERE workflow_code = 'FP_CARNET_FUNCIONARIO';

UPDATE workflow_display_config SET list_columns = '[
  "dip.numero_dip", "dip.apellidos", "dip.nombres", "dip.natural_de", "dip.fecha_expiracion",
  "carnet_funcionario.matricula", "carnet_funcionario.cargo", "carnet_funcionario.ministerio"
]'::jsonb WHERE workflow_code IN ('FP_PROMOCION_ADMINISTRATIVA', 'FP_CERTIFICADO_ADMINISTRATIVO');
