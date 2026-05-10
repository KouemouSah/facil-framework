-- Migration 077: Populate workflows.config for PASAPORTE workflows
-- Purpose: Define form display schema and agent verification checklist
-- Scope: CNEDOGE PASAPORTE workflows (5 workflows)
--
-- IMPORTANT: Schema based on ACTUAL form_data stored in service_requests table
-- Real form_data keys discovered from DB:
--   dip, sexo, ciudad, motivo, nombres, is_minor, sub_type, apellidos, domicilio,
--   profesion, numero_dip, departamento, estado_civil, nacionalidad, nombre_madre,
--   nombre_padre, photo_carnet, solicitud_type, grupo_sanguineo, fecha_nacimiento,
--   lugar_nacimiento, pasaporte_antiguo, representante_unico, fecha_expedicion_antiguo,
--   fecha_expiracion_antiguo, numero_pasaporte_antiguo, motivo_representante_unico
--
-- NOTE: This config is used by the AGENT dashboard for displaying submitted requests.
--       The citizen wizard uses the Python workflow class (pasaporte_workflow_v2.py).

BEGIN;

-- =============================================================================
-- PASAPORTE_NUEVO (First passport - Expedición)
-- Based on actual form_data keys from service_requests table
-- =============================================================================
UPDATE workflows
SET config = '{
  "formDisplaySchema": {
    "title": "DETALLES DE SOLICITUD DE PASAPORTE - PRIMERA EXPEDICIÓN",
    "photoField": "photo_carnet.url",
    "layout": "two-column",
    "sections": [
      {
        "id": "solicitud",
        "title": "Solicitud",
        "column": "left",
        "fields": [
          {"key": "reference", "label": "Código de solicitud", "type": "text", "source": "request"},
          {"key": "created_at", "label": "Fecha de solicitud", "type": "datetime", "source": "request"},
          {"key": "solicitud_type", "label": "Tipo de solicitud", "type": "text"},
          {"key": "sub_type", "label": "Subtipo", "type": "text"},
          {"key": "is_minor", "label": "Menor de edad", "type": "boolean"},
          {"key": "status", "label": "Estado", "type": "status", "source": "request"},
          {"key": "cita_location", "label": "Ubicación cita", "type": "text", "source": "request"}
        ]
      },
      {
        "id": "titular",
        "title": "Datos del Titular",
        "column": "right",
        "fields": [
          {"key": "nombres", "label": "Nombres", "type": "text"},
          {"key": "apellidos", "label": "Apellidos", "type": "text"},
          {"key": "fecha_nacimiento", "label": "Fecha de nacimiento", "type": "date"},
          {"key": "lugar_nacimiento", "label": "Lugar de nacimiento", "type": "text"},
          {"key": "sexo", "label": "Sexo", "type": "text"},
          {"key": "nacionalidad", "label": "Nacionalidad", "type": "text"},
          {"key": "estado_civil", "label": "Estado civil", "type": "text"},
          {"key": "profesion", "label": "Profesión", "type": "text"},
          {"key": "grupo_sanguineo", "label": "Grupo sanguíneo", "type": "text"}
        ]
      },
      {
        "id": "filiacion",
        "title": "Filiación",
        "column": "left",
        "fields": [
          {"key": "nombre_padre", "label": "Nombre del padre", "type": "text"},
          {"key": "nombre_madre", "label": "Nombre de la madre", "type": "text"}
        ]
      },
      {
        "id": "domicilio",
        "title": "Domicilio",
        "column": "right",
        "fields": [
          {"key": "domicilio", "label": "Dirección", "type": "text"},
          {"key": "ciudad", "label": "Ciudad", "type": "text"},
          {"key": "departamento", "label": "Departamento/Provincia", "type": "text"}
        ]
      },
      {
        "id": "documento_identidad",
        "title": "Documento de Identidad (DIP)",
        "column": "left",
        "fields": [
          {"key": "numero_dip", "label": "Número DIP", "type": "text"},
          {"key": "dip.fecha_emision", "label": "Fecha emisión DIP", "type": "date"},
          {"key": "dip.fecha_expiracion", "label": "Fecha expiración DIP", "type": "date"},
          {"key": "dip.lugar_emision", "label": "Lugar emisión", "type": "text"}
        ]
      }
    ]
  },
  "agentChecklist": [
    {"id": "identity_verified", "label": "Identidad del solicitante verificada con DIP", "required": true},
    {"id": "dip_valid", "label": "DIP vigente y datos coinciden", "required": true},
    {"id": "birth_certificate_valid", "label": "Certificado de nacimiento válido", "required": true},
    {"id": "photo_valid", "label": "Foto carnet conforme a requisitos", "required": true},
    {"id": "payment_confirmed", "label": "Pago confirmado", "required": true},
    {"id": "data_matches", "label": "Datos del formulario coinciden con documentos", "required": true},
    {"id": "no_duplicates", "label": "Sin solicitudes duplicadas en sistema", "required": false}
  ]
}'::jsonb,
updated_at = NOW()
WHERE code = 'PASAPORTE_NUEVO';

-- =============================================================================
-- PASAPORTE_RENOVACION (Renewal - VENCIMIENTO)
-- Includes pasaporte_antiguo nested object
-- =============================================================================
UPDATE workflows
SET config = '{
  "formDisplaySchema": {
    "title": "DETALLES DE SOLICITUD DE RENOVACIÓN DE PASAPORTE",
    "photoField": "photo_carnet.url",
    "layout": "two-column",
    "sections": [
      {
        "id": "solicitud",
        "title": "Solicitud",
        "column": "left",
        "fields": [
          {"key": "reference", "label": "Código de solicitud", "type": "text", "source": "request"},
          {"key": "created_at", "label": "Fecha de solicitud", "type": "datetime", "source": "request"},
          {"key": "solicitud_type", "label": "Tipo de solicitud", "type": "text"},
          {"key": "motivo", "label": "Motivo", "type": "text"},
          {"key": "is_minor", "label": "Menor de edad", "type": "boolean"},
          {"key": "status", "label": "Estado", "type": "status", "source": "request"},
          {"key": "cita_location", "label": "Ubicación cita", "type": "text", "source": "request"}
        ]
      },
      {
        "id": "titular",
        "title": "Datos del Titular",
        "column": "right",
        "fields": [
          {"key": "nombres", "label": "Nombres", "type": "text"},
          {"key": "apellidos", "label": "Apellidos", "type": "text"},
          {"key": "fecha_nacimiento", "label": "Fecha de nacimiento", "type": "date"},
          {"key": "lugar_nacimiento", "label": "Lugar de nacimiento", "type": "text"},
          {"key": "sexo", "label": "Sexo", "type": "text"},
          {"key": "nacionalidad", "label": "Nacionalidad", "type": "text"},
          {"key": "estado_civil", "label": "Estado civil", "type": "text"},
          {"key": "profesion", "label": "Profesión", "type": "text"},
          {"key": "grupo_sanguineo", "label": "Grupo sanguíneo", "type": "text"}
        ]
      },
      {
        "id": "filiacion",
        "title": "Filiación",
        "column": "left",
        "fields": [
          {"key": "nombre_padre", "label": "Nombre del padre", "type": "text"},
          {"key": "nombre_madre", "label": "Nombre de la madre", "type": "text"}
        ]
      },
      {
        "id": "domicilio",
        "title": "Domicilio",
        "column": "right",
        "fields": [
          {"key": "domicilio", "label": "Dirección", "type": "text"},
          {"key": "ciudad", "label": "Ciudad", "type": "text"},
          {"key": "departamento", "label": "Departamento/Provincia", "type": "text"}
        ]
      },
      {
        "id": "documento_identidad",
        "title": "Documento de Identidad (DIP)",
        "column": "left",
        "fields": [
          {"key": "numero_dip", "label": "Número DIP", "type": "text"},
          {"key": "dip.fecha_emision", "label": "Fecha emisión DIP", "type": "date"},
          {"key": "dip.fecha_expiracion", "label": "Fecha expiración DIP", "type": "date"}
        ]
      },
      {
        "id": "pasaporte_anterior",
        "title": "Pasaporte Anterior",
        "column": "right",
        "fields": [
          {"key": "numero_pasaporte_antiguo", "label": "Número pasaporte", "type": "text"},
          {"key": "fecha_expedicion_antiguo", "label": "Fecha expedición", "type": "date"},
          {"key": "fecha_expiracion_antiguo", "label": "Fecha expiración", "type": "date"},
          {"key": "pasaporte_antiguo.lugar_nacimiento", "label": "Lugar nacimiento (pasaporte)", "type": "text"}
        ]
      }
    ]
  },
  "agentChecklist": [
    {"id": "identity_verified", "label": "Identidad del solicitante verificada con DIP", "required": true},
    {"id": "dip_valid", "label": "DIP vigente y datos coinciden", "required": true},
    {"id": "previous_passport_verified", "label": "Pasaporte anterior presentado y verificado", "required": true},
    {"id": "photo_valid", "label": "Foto carnet conforme a requisitos", "required": true},
    {"id": "payment_confirmed", "label": "Pago confirmado", "required": true},
    {"id": "data_matches", "label": "Datos del formulario coinciden con documentos", "required": true}
  ]
}'::jsonb,
updated_at = NOW()
WHERE code = 'PASAPORTE_RENOVACION';

-- =============================================================================
-- PASAPORTE_PERDIDA (Lost passport)
-- Requires denuncia policial - adds specific checklist item
-- =============================================================================
UPDATE workflows
SET config = '{
  "formDisplaySchema": {
    "title": "DETALLES DE SOLICITUD DE PASAPORTE POR PÉRDIDA",
    "photoField": "photo_carnet.url",
    "layout": "two-column",
    "sections": [
      {
        "id": "solicitud",
        "title": "Solicitud",
        "column": "left",
        "fields": [
          {"key": "reference", "label": "Código de solicitud", "type": "text", "source": "request"},
          {"key": "created_at", "label": "Fecha de solicitud", "type": "datetime", "source": "request"},
          {"key": "solicitud_type", "label": "Tipo de solicitud", "type": "text"},
          {"key": "motivo", "label": "Motivo", "type": "text", "default": "PERDIDA"},
          {"key": "is_minor", "label": "Menor de edad", "type": "boolean"},
          {"key": "status", "label": "Estado", "type": "status", "source": "request"},
          {"key": "cita_location", "label": "Ubicación cita", "type": "text", "source": "request"}
        ]
      },
      {
        "id": "titular",
        "title": "Datos del Titular",
        "column": "right",
        "fields": [
          {"key": "nombres", "label": "Nombres", "type": "text"},
          {"key": "apellidos", "label": "Apellidos", "type": "text"},
          {"key": "fecha_nacimiento", "label": "Fecha de nacimiento", "type": "date"},
          {"key": "lugar_nacimiento", "label": "Lugar de nacimiento", "type": "text"},
          {"key": "sexo", "label": "Sexo", "type": "text"},
          {"key": "nacionalidad", "label": "Nacionalidad", "type": "text"},
          {"key": "estado_civil", "label": "Estado civil", "type": "text"},
          {"key": "profesion", "label": "Profesión", "type": "text"},
          {"key": "grupo_sanguineo", "label": "Grupo sanguíneo", "type": "text"}
        ]
      },
      {
        "id": "filiacion",
        "title": "Filiación",
        "column": "left",
        "fields": [
          {"key": "nombre_padre", "label": "Nombre del padre", "type": "text"},
          {"key": "nombre_madre", "label": "Nombre de la madre", "type": "text"}
        ]
      },
      {
        "id": "domicilio",
        "title": "Domicilio",
        "column": "right",
        "fields": [
          {"key": "domicilio", "label": "Dirección", "type": "text"},
          {"key": "ciudad", "label": "Ciudad", "type": "text"},
          {"key": "departamento", "label": "Departamento/Provincia", "type": "text"}
        ]
      },
      {
        "id": "documento_identidad",
        "title": "Documento de Identidad (DIP)",
        "column": "left",
        "fields": [
          {"key": "numero_dip", "label": "Número DIP", "type": "text"},
          {"key": "dip.fecha_emision", "label": "Fecha emisión DIP", "type": "date"},
          {"key": "dip.fecha_expiracion", "label": "Fecha expiración DIP", "type": "date"}
        ]
      }
    ]
  },
  "agentChecklist": [
    {"id": "identity_verified", "label": "Identidad del solicitante verificada con DIP", "required": true},
    {"id": "dip_valid", "label": "DIP vigente y datos coinciden", "required": true},
    {"id": "police_report_valid", "label": "Denuncia policial de pérdida válida (menos de 30 días)", "required": true},
    {"id": "photo_valid", "label": "Foto carnet conforme a requisitos", "required": true},
    {"id": "payment_confirmed", "label": "Pago confirmado (incluye penalización)", "required": true},
    {"id": "data_matches", "label": "Datos del formulario coinciden con documentos", "required": true}
  ]
}'::jsonb,
updated_at = NOW()
WHERE code = 'PASAPORTE_PERDIDA';

-- =============================================================================
-- PASAPORTE_ROBO (Stolen passport)
-- Same as PERDIDA but specifies "robo" in checklist
-- =============================================================================
UPDATE workflows
SET config = '{
  "formDisplaySchema": {
    "title": "DETALLES DE SOLICITUD DE PASAPORTE POR ROBO",
    "photoField": "photo_carnet.url",
    "layout": "two-column",
    "sections": [
      {
        "id": "solicitud",
        "title": "Solicitud",
        "column": "left",
        "fields": [
          {"key": "reference", "label": "Código de solicitud", "type": "text", "source": "request"},
          {"key": "created_at", "label": "Fecha de solicitud", "type": "datetime", "source": "request"},
          {"key": "solicitud_type", "label": "Tipo de solicitud", "type": "text"},
          {"key": "motivo", "label": "Motivo", "type": "text", "default": "ROBO"},
          {"key": "is_minor", "label": "Menor de edad", "type": "boolean"},
          {"key": "status", "label": "Estado", "type": "status", "source": "request"},
          {"key": "cita_location", "label": "Ubicación cita", "type": "text", "source": "request"}
        ]
      },
      {
        "id": "titular",
        "title": "Datos del Titular",
        "column": "right",
        "fields": [
          {"key": "nombres", "label": "Nombres", "type": "text"},
          {"key": "apellidos", "label": "Apellidos", "type": "text"},
          {"key": "fecha_nacimiento", "label": "Fecha de nacimiento", "type": "date"},
          {"key": "lugar_nacimiento", "label": "Lugar de nacimiento", "type": "text"},
          {"key": "sexo", "label": "Sexo", "type": "text"},
          {"key": "nacionalidad", "label": "Nacionalidad", "type": "text"},
          {"key": "estado_civil", "label": "Estado civil", "type": "text"},
          {"key": "profesion", "label": "Profesión", "type": "text"},
          {"key": "grupo_sanguineo", "label": "Grupo sanguíneo", "type": "text"}
        ]
      },
      {
        "id": "filiacion",
        "title": "Filiación",
        "column": "left",
        "fields": [
          {"key": "nombre_padre", "label": "Nombre del padre", "type": "text"},
          {"key": "nombre_madre", "label": "Nombre de la madre", "type": "text"}
        ]
      },
      {
        "id": "domicilio",
        "title": "Domicilio",
        "column": "right",
        "fields": [
          {"key": "domicilio", "label": "Dirección", "type": "text"},
          {"key": "ciudad", "label": "Ciudad", "type": "text"},
          {"key": "departamento", "label": "Departamento/Provincia", "type": "text"}
        ]
      },
      {
        "id": "documento_identidad",
        "title": "Documento de Identidad (DIP)",
        "column": "left",
        "fields": [
          {"key": "numero_dip", "label": "Número DIP", "type": "text"},
          {"key": "dip.fecha_emision", "label": "Fecha emisión DIP", "type": "date"},
          {"key": "dip.fecha_expiracion", "label": "Fecha expiración DIP", "type": "date"}
        ]
      }
    ]
  },
  "agentChecklist": [
    {"id": "identity_verified", "label": "Identidad del solicitante verificada con DIP", "required": true},
    {"id": "dip_valid", "label": "DIP vigente y datos coinciden", "required": true},
    {"id": "police_report_valid", "label": "Denuncia policial de ROBO válida (menos de 30 días)", "required": true},
    {"id": "photo_valid", "label": "Foto carnet conforme a requisitos", "required": true},
    {"id": "payment_confirmed", "label": "Pago confirmado (incluye penalización)", "required": true},
    {"id": "data_matches", "label": "Datos del formulario coinciden con documentos", "required": true}
  ]
}'::jsonb,
updated_at = NOW()
WHERE code = 'PASAPORTE_ROBO';

-- =============================================================================
-- PASAPORTE_DETERIORO (Damaged passport)
-- Requires presentation of damaged passport
-- =============================================================================
UPDATE workflows
SET config = '{
  "formDisplaySchema": {
    "title": "DETALLES DE SOLICITUD DE PASAPORTE POR DETERIORO",
    "photoField": "photo_carnet.url",
    "layout": "two-column",
    "sections": [
      {
        "id": "solicitud",
        "title": "Solicitud",
        "column": "left",
        "fields": [
          {"key": "reference", "label": "Código de solicitud", "type": "text", "source": "request"},
          {"key": "created_at", "label": "Fecha de solicitud", "type": "datetime", "source": "request"},
          {"key": "solicitud_type", "label": "Tipo de solicitud", "type": "text"},
          {"key": "motivo", "label": "Motivo", "type": "text", "default": "DETERIORO"},
          {"key": "is_minor", "label": "Menor de edad", "type": "boolean"},
          {"key": "status", "label": "Estado", "type": "status", "source": "request"},
          {"key": "cita_location", "label": "Ubicación cita", "type": "text", "source": "request"}
        ]
      },
      {
        "id": "titular",
        "title": "Datos del Titular",
        "column": "right",
        "fields": [
          {"key": "nombres", "label": "Nombres", "type": "text"},
          {"key": "apellidos", "label": "Apellidos", "type": "text"},
          {"key": "fecha_nacimiento", "label": "Fecha de nacimiento", "type": "date"},
          {"key": "lugar_nacimiento", "label": "Lugar de nacimiento", "type": "text"},
          {"key": "sexo", "label": "Sexo", "type": "text"},
          {"key": "nacionalidad", "label": "Nacionalidad", "type": "text"},
          {"key": "estado_civil", "label": "Estado civil", "type": "text"},
          {"key": "profesion", "label": "Profesión", "type": "text"},
          {"key": "grupo_sanguineo", "label": "Grupo sanguíneo", "type": "text"}
        ]
      },
      {
        "id": "filiacion",
        "title": "Filiación",
        "column": "left",
        "fields": [
          {"key": "nombre_padre", "label": "Nombre del padre", "type": "text"},
          {"key": "nombre_madre", "label": "Nombre de la madre", "type": "text"}
        ]
      },
      {
        "id": "domicilio",
        "title": "Domicilio",
        "column": "right",
        "fields": [
          {"key": "domicilio", "label": "Dirección", "type": "text"},
          {"key": "ciudad", "label": "Ciudad", "type": "text"},
          {"key": "departamento", "label": "Departamento/Provincia", "type": "text"}
        ]
      },
      {
        "id": "documento_identidad",
        "title": "Documento de Identidad (DIP)",
        "column": "left",
        "fields": [
          {"key": "numero_dip", "label": "Número DIP", "type": "text"},
          {"key": "dip.fecha_emision", "label": "Fecha emisión DIP", "type": "date"},
          {"key": "dip.fecha_expiracion", "label": "Fecha expiración DIP", "type": "date"}
        ]
      },
      {
        "id": "pasaporte_anterior",
        "title": "Pasaporte Deteriorado",
        "column": "right",
        "fields": [
          {"key": "numero_pasaporte_antiguo", "label": "Número pasaporte", "type": "text"},
          {"key": "fecha_expedicion_antiguo", "label": "Fecha expedición", "type": "date"},
          {"key": "fecha_expiracion_antiguo", "label": "Fecha expiración", "type": "date"}
        ]
      }
    ]
  },
  "agentChecklist": [
    {"id": "identity_verified", "label": "Identidad del solicitante verificada con DIP", "required": true},
    {"id": "dip_valid", "label": "DIP vigente y datos coinciden", "required": true},
    {"id": "damaged_passport_presented", "label": "Pasaporte deteriorado presentado físicamente", "required": true},
    {"id": "photo_valid", "label": "Foto carnet conforme a requisitos", "required": true},
    {"id": "payment_confirmed", "label": "Pago confirmado", "required": true},
    {"id": "data_matches", "label": "Datos del formulario coinciden con documentos", "required": true}
  ]
}'::jsonb,
updated_at = NOW()
WHERE code = 'PASAPORTE_DETERIORO';

COMMIT;

-- =============================================================================
-- Verification query (run separately to verify)
-- =============================================================================
-- SELECT code, name_es,
--        config->'formDisplaySchema'->>'title' as form_title,
--        jsonb_array_length(config->'agentChecklist') as checklist_items,
--        jsonb_array_length(config->'formDisplaySchema'->'sections') as sections_count
-- FROM workflows
-- WHERE code LIKE 'PASAPORTE%'
-- ORDER BY code;
