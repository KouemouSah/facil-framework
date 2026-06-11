-- Migration 182: Cleanup PASAPORTE_NUEVO display_config
--
-- Now that workflow_code resolution is in place (migration 181 + backend fix),
-- PASAPORTE_NUEVO only represents first-time passport requests (expedicion).
-- Remove pasaporte_antiguo columns that were temporarily added for backwards compat.

UPDATE workflow_display_config
SET list_columns = '[
    "dip.numero_dip",
    "dip.apellidos",
    "dip.nombres",
    "dip.natural_de",
    "dip.fecha_expiracion",
    "certificado_nacimiento.nombre",
    "certificado_nacimiento.primer_apellido",
    "certificado_nacimiento.lugar_nacimiento",
    "certificado_nacimiento.hijo_de",
    "certificado_nacimiento.y_de",
    "autorizacion_parental.nombre_completo",
    "autorizacion_parental.parentesco",
    "documento_representante_1.numero_dip",
    "documento_representante_1.apellidos",
    "documento_representante_1.nombres"
]'::jsonb
WHERE workflow_code = 'PASAPORTE_NUEVO';
