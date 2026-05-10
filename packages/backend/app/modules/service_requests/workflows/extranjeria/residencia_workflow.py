"""
ResidenciaWorkflow v2.3 - Residence permit workflow for foreigners.

Migrated to PredefinedWorkflow architecture (v2).
ALIGNED WITH Orden Ministerial 01/2021, Art. 3 Section A.

Handles:
- RESIDENCIA_PRIMERA_VEZ (Art. 3.A.1): First residence permit (13-14 documents)
- RESIDENCIA_RENOVACION (Art. 3.A.2): Residence permit renewal (11-12 documents)

NO sub-types — solicitud_type (EXPEDICION/RENOVACION) suffices.
workflow_code determines the type at wizard start:
  - RESIDENCIA_PRIMERA_VEZ → SolicitudType.EXPEDICION
  - RESIDENCIA_RENOVACION → SolicitudType.RENOVACION

Step 0 SELECTION: persona type (física/jurídica) chosen BEFORE upload
  so documents are immediately filtered by persona type.

Entity: EXTRANJERIA (Dirección General de Extranjería y Fronteras)

CEMAC Free Movement:
  CEMAC member states (CMR, CAF, COG, GAB, GNQ, TCD) have free movement.
  CEMAC nationals do NOT need a visa, but their entry must be < 90 days.
  Non-CEMAC nationals MUST provide a valid visa (VISADO_GQ_V1).
  CEMAC logic applies only to EXPEDICION (first time).

Entry stamp verification (v2.2):
  ALL applicants (CEMAC and non-CEMAC) for EXPEDICION must upload the passport
  stamp page containing the official GQ entry stamp (SELLO_ENTRADA_GQ_V1).
  This replaces manual date entry: the entry date is OCR-extracted from the
  oval stamp (ENTRADA / DD MMM. YYYY / AEROPUERTO INTERNACIONAL DE ...) and
  displayed in form_review_1 as readonly+editable (user can correct if OCR wrong).

Tariffs: Nota de Ingreso (official amounts validated by OCR)
  - EXPEDICION: 200,000 XAF
  - RENOVACION: 100,000 XAF
  - Supplements: Cédula Personal (1,500 XAF) + Póliza (1,000 XAF) = 2,500 XAF stamps

Condition persona_juridica / persona_fisica:
  Art. 3 distinguishes documents required for enterprises (personas jurídicas) vs individuals.
  Implemented via form_data field "es_persona_juridica" set in step 0 SELECTION.

Validation architecture:
  - Layer 1 (SchemaValidationEngine): Document-level validations (resultado, signatures,
    formats, NIF coherence, name coherence). Centralized in JSON schemas, runs at upload.
  - Layer 2 (validate_step): Workflow business logic that schemas cannot express: timing
    conditions, CEMAC rules, cross-step state, persona_juridica context.

Support document verification (v2.3):
  Form review 3 displays OCR-extracted key fields from support documents:
  buena_conducta, antecedentes penales, NIF/autorización gubernativa.
  This lets users verify extraction accuracy before submission.

Legal source: Documentations/workflow/menu/residencia.md (Orden Ministerial 01/2021)
Real documents: Documentations/workflow/menu/residencia/ (9 files analyzed)

OCR Schemas (12):
- PASAPORTE_INTERNATIONAL_V1 (generic passport for foreigners)
- SELLO_ENTRADA_GQ_V1 (passport entry stamp page — v2.2)
- PERMISO_RESIDENCIA_GQ_V1 (previous residence permit)
- CERTIFICADO_NIF_GQ_V1 (company NIF — alternative 1 for nif_autorizacion)
- AUTORIZACION_GUBERNATIVA_GQ_V1 (alternative 2 for nif_autorizacion)
- CERTIFICADO_BUENA_CONDUCTA_GQ_V1 (community conduct certificate)
- EXTRAIT_CASIER_JUDICIAIRE_INTERNATIONAL_V1 (primera vez: home country criminal record)
- ANTECEDENTES_PENALES_GQ_V1 (renovacion: GQ Ministry of Justice criminal record)
- SOLVENCIA_TRIBUTARIA_GQ_V1 (tax solvency certificate — warning-only for NO_SOLVENTE)
- ATESTACION_BANCARIA_GQ_V1 (bank attestation)
- PERMISO_TRABAJO_GQ_V1 (work permit)
- VISADO_GQ_V1 (entry visa, non-CEMAC nationals only)

@version 2.3
@date 2026-02-07
@migration v1 residencia_workflow.py (578 lines, BaseWorkflow) → v2 PredefinedWorkflow
@legal Orden Ministerial 01/2021 de fecha 02 de diciembre
"""
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta

from ..workflow_interface import (
    PredefinedWorkflow,
    WorkflowStep,
    WorkflowContext,
    DocumentRequirement,
    TariffConfig,
    SupplementDefinition,
    ValidationResult,
    StepType,
    RenovacionMotivo,
)
from ...models.enums import (
    WorkflowCode,
    WorkflowCategory,
    EntityCode,
    TariffType,
    SolicitudType,
    DocumentConditionType,
)

# =============================================================================
# CEMAC Free Movement Zone
# =============================================================================
# Communauté Économique et Monétaire de l'Afrique Centrale
# Members have free movement — no visa required, but entry must be < 90 days.
# ISO 3166-1 alpha-3 codes:
CEMAC_COUNTRY_CODES: Set[str] = {
    "CMR",  # Cameroun
    "CAF",  # République centrafricaine
    "COG",  # République du Congo (Brazzaville)
    "GAB",  # Gabon
    "GNQ",  # Guinée Équatoriale (host — excluded by nacionalidad_extranjero rule)
    "TCD",  # Tchad
}


class ResidenciaWorkflow(PredefinedWorkflow):
    """
    Residence permit workflow for foreigners in Equatorial Guinea.

    AUTONOMOUS: Defines ALL logic internally, aligned with Orden Ministerial 01/2021.

    Two workflow codes, one class:
    - RESIDENCIA_PRIMERA_VEZ → SolicitudType.EXPEDICION (Art. 3.A.1, 13-14 documents)
    - RESIDENCIA_RENOVACION → SolicitudType.RENOVACION (Art. 3.A.2, 11-12 documents)

    Two phases, conditional on "con_nota_ingreso" (set in step 0 SELECTION):
    - Phase 1 (sin nota): Full dossier → Extranjería validation → stamps (2,500 XAF)
    - Phase 2 (con nota): User has Nota from Extranjería → upload nota + identity → CNEDOGE payment

    Steps (13, conditional visibility):
    0.  selection: solicitud_type + persona_type + con_nota_ingreso + duracion (if renovacion+nota)
    --- Phase 1 (sin nota) steps 1-7: condition {con_nota_ingreso: "false"} ---
    1.  upload_documents: Dynamic documents (13-14 EXPEDICION / 11-12 RENOVACION)
    2.  form_review_1: Passport identity + entry stamp / previous residence
    3.  form_review_2: Professional data + company data (persona_juridica)
    4.  form_review_3: Support docs verification (buena_conducta, antecedentes, NIF)
    5.  appointment: Cita en Extranjería
    6.  stamp_payment: Stamps Cédula + Póliza (2,500 XAF)
    7.  payment: Phase 1 stamps payment
    --- Phase 2 (con nota) steps 8-11: condition {con_nota_ingreso: "true"} ---
    8.  upload_nota: Nota de Ingreso + identity document (pasaporte/residencia)
    9.  form_review_nota: OCR verification of nota data + identity
    10. appointment_cnedoge: Cita CNEDOGE (permit collection)
    11. payment_phase2: Main payment (200K EXPEDICION / 100K×años RENOVACION)
    --- Common ---
    12. confirmation: Summary + agent_checklist + rejection_reasons

    Tariffs:
    - Phase 1: TariffType.NOTA_INGRESO → returns 0 (stamps only)
    - Phase 2 EXPEDICION: 200,000 XAF (fixed)
    - Phase 2 RENOVACION: 100,000 XAF × duracion_anos (1, 2, or 5 years)
    - Stamps (Phase 1 only): Cédula (1,500) + Póliza (1,000) = 2,500 XAF

    Validate_step rules (11 — workflow business logic only):

    form_review_1 (step 2, Phase 1):
     1. entrada_legal_fecha: Entry date must exist
     2. cemac_90_dias: CEMAC entry < 90 days (warning)
     3. visado_requerido: Non-CEMAC → visa must exist + date coherence
     4. nacionalidad_extranjero: NOT Equatoguinean
     5. residencia_renovable: Residence expiring < 90 days (RENOVACION, warning)
     6. nombres_coherentes: Name match passport ↔ residence (Levenshtein)
    form_review_2 (step 3, Phase 1):
     7. solvencia_resultado: NO_SOLVENTE → warning (persona_juridica)
    form_review_3 (step 4, Phase 1):
     8. buena_conducta_resultado: DESFAVORABLE → warning
     9. antecedentes_resultado: POSITIVO/HAS_CONVICTIONS → error
    form_review_nota (step 9, Phase 2):
     10. nota_amount_coherent: OCR amount vs expected tariff (warning)
     11. nota_expired: date_emission + dias_validez < today (error)
    """

    # === Properties ===

    @property
    def workflow_code(self) -> WorkflowCode:
        return WorkflowCode.RESIDENCIA_PRIMERA_VEZ

    @property
    def category(self) -> WorkflowCategory:
        return WorkflowCategory.EXTRANJERIA

    @property
    def entity_code(self) -> EntityCode:
        return EntityCode.EXTRANJERIA

    @property
    def service_name_es(self) -> str:
        return "Permiso de Residencia para Extranjeros"

    def get_subtype_display_names(self) -> Dict[str, str]:
        return {
            "RESIDENCIA_PRIMERA_VEZ": "Residencia - Primera Vez",
            "RESIDENCIA_RENOVACION": "Residencia - Renovación",
        }

    @property
    def allowed_solicitud_types(self) -> List[SolicitudType]:
        return [SolicitudType.EXPEDICION, SolicitudType.RENOVACION]

    @property
    def allowed_sub_types(self) -> List[str]:
        return []

    @property
    def requires_appointment(self) -> bool:
        return True

    @property
    def menu_icon(self) -> str:
        return "Globe"

    @property
    def requires_agent_review(self) -> bool:
        return True

    @property
    def requires_nota_ingreso(self) -> bool:
        return True

    # === Multi-code registration ===

    def get_all_workflow_codes(self) -> List[WorkflowCode]:
        return [
            WorkflowCode.RESIDENCIA_PRIMERA_VEZ,
            WorkflowCode.RESIDENCIA_RENOVACION,
        ]

    @property
    def _subtype_code_aliases(self) -> Dict[str, WorkflowCode]:
        """EXPEDICION is a semantic alias — first-time = primera vez."""
        return {
            "EXPEDICION": WorkflowCode.RESIDENCIA_PRIMERA_VEZ,
        }

    # === Setup ===

    def _setup_workflow(self) -> None:
        self._setup_steps()
        self._setup_tariffs()

    def _setup_steps(self) -> None:
        # Step 0: Selection — solicitud type + persona type (before upload to filter documents)
        self.add_step(WorkflowStep(
            step_number=0,
            step_id="selection",
            step_type=StepType.SELECTION,
            title_es="Tipo de Solicitud",
            description_es="Seleccione el tipo de solicitud y si tramita como persona física o jurídica",
            config={
                "sections": [
                    {
                        "id": "tipo_solicitud",
                        "title_es": "Tipo de Solicitud",
                        "fields": [
                            {"key": "solicitud_type",
                             "label_es": "¿Qué tipo de permiso de residencia solicita?",
                             "type": "select", "required": True,
                             "options": [
                                 {"value": "expedicion",
                                  "label_es": "Primera vez — Solicitud de Permiso de Residencia"},
                                 {"value": "renovacion",
                                  "label_es": "Renovación — Renovación de Permiso de Residencia"},
                             ],
                             "help_text_es": (
                                 "Art. 3.A.1: Primera solicitud de residencia. "
                                 "Art. 3.A.2: Renovación de un permiso de residencia existente. "
                                 "Los documentos requeridos varían según el tipo de solicitud."
                             )},
                        ]
                    },
                    {
                        "id": "tipo_persona",
                        "title_es": "Tipo de Persona",
                        "fields": [
                            {"key": "es_persona_juridica",
                             "label_es": "¿Solicita a través de empresa (persona jurídica)?",
                             "type": "select", "required": True,
                             "options": [
                                 {"value": "false", "label_es": "No — Persona física (particular)"},
                                 {"value": "true", "label_es": "Sí — Persona jurídica (empresa)"},
                             ],
                             "help_text_es": (
                                 "Según Art. 3 Orden Ministerial 01/2021, ciertos documentos son "
                                 "requeridos solo para personas jurídicas (NIF, solvencia tributaria, "
                                 "cédula personal del representante) o físicas (cédula personal del "
                                 "solicitante en renovación)."
                             )},
                        ]
                    },
                    {
                        "id": "modo_tramite",
                        "title_es": "Modo de Trámite",
                        "fields": [
                            {"key": "con_nota_ingreso",
                             "label_es": "¿Dispone de una Nota de Ingreso emitida por Extranjería?",
                             "type": "select", "required": True,
                             "options": [
                                 {"value": "false",
                                  "label_es": "No — Solicitud completa (documentos + validación + timbres)"},
                                 {"value": "true",
                                  "label_es": "Sí — Tengo la Nota de Ingreso (pago principal + cita CNEDOGE)"},
                             ],
                             "help_text_es": (
                                 "Si ya tramitó su expediente en Extranjería y recibió la Nota de Ingreso, "
                                 "seleccione 'Sí'. Si necesita iniciar el trámite desde cero, seleccione 'No'."
                             )},
                        ],
                    },
                    {
                        "id": "duracion_residencia",
                        "title_es": "Duración del Permiso de Residencia",
                        "show_when": {"con_nota_ingreso": "true", "solicitud_type": "renovacion"},
                        "fields": [
                            {"key": "duracion_anos",
                             "label_es": "Duración solicitada para la renovación",
                             "type": "select", "required": True,
                             "options": [
                                 {"value": "1", "label_es": "1 año — 100 000 XAF"},
                                 {"value": "2", "label_es": "2 años — 200 000 XAF"},
                                 {"value": "5", "label_es": "5 años — 500 000 XAF"},
                             ],
                             "help_text_es": (
                                 "El monto del permiso de residencia se calcula en función de la duración: "
                                 "100 000 XAF × número de años. Primera vez: siempre 200 000 XAF fijo."
                             )},
                        ],
                    },
                ]
            }
        ))

        # Step 1: Upload documents (Phase 1 only — sin nota)
        self.add_step(WorkflowStep(
            step_number=1,
            step_id="upload_documents",
            step_type=StepType.DOCUMENT_UPLOAD,
            title_es="Documentos Requeridos",
            description_es="Cargue los documentos necesarios según la Orden Ministerial 01/2021",
            config={
                "condition": {"con_nota_ingreso": "false"},
                "dynamic_documents": True,
                "max_file_size_mb": 10,
            }
        ))

        # Step 2: Form Review 1 - Passport identity + entry data + previous residence (Phase 1 only)
        self.add_step(WorkflowStep(
            step_number=2,
            step_id="form_review_1",
            step_type=StepType.FORM_REVIEW,
            title_es="Datos de Identidad y Entrada",
            description_es="Verifique los datos extraídos del pasaporte e indique la fecha de entrada",
            config={
                "condition": {"con_nota_ingreso": "false"},
                "sections": [
                    {
                        "id": "datos_pasaporte",
                        "title_es": "Datos del Pasaporte",
                        "source_document": "pasaporte",
                        "fields": [
                            {"key": "numero_pasaporte", "label_es": "N° Pasaporte", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "apellidos", "label_es": "Apellidos", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "nombres", "label_es": "Nombres", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "nacionalidad", "label_es": "Nacionalidad", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "sexo", "label_es": "Sexo", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "fecha_nacimiento", "label_es": "Fecha de Nacimiento", "type": "date",
                             "required": True, "readonly": True},
                            {"key": "lugar_nacimiento", "label_es": "Lugar de Nacimiento", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "fecha_expiracion_pasaporte", "label_es": "Fecha de Expiración", "type": "date",
                             "required": True, "readonly": True},
                        ]
                    },
                    {
                        "id": "datos_entrada",
                        "title_es": "Datos de Entrada al País",
                        "description_es": (
                            "Datos extraídos del sello de entrada en su pasaporte. "
                            "Verifique que la fecha y el puesto fronterizo son correctos. "
                            "Si la extracción automática es incorrecta, puede corregir los valores."
                        ),
                        "source_document": "sello_entrada",
                        "condition": {"solicitud_type": "expedicion"},
                        "fields": [
                            {"key": "fecha_entrada_pais", "label_es": "Fecha de Última Entrada al País",
                             "type": "date", "required": True, "readonly": False,
                             "help_text_es": (
                                 "Fecha extraída del sello de entrada oficial. "
                                 "Nacionales CEMAC (Camerún, Gabón, Congo, Chad, Centroáfrica): "
                                 "la estancia no puede exceder 90 días sin permiso de residencia. "
                                 "Otros países: se requiere visado de entrada válido."
                             )},
                            {"key": "puesto_fronterizo", "label_es": "Puesto Fronterizo de Entrada",
                             "type": "text", "required": True, "readonly": True,
                             "help_text_es": (
                                 "Nombre del puesto fronterizo oficial donde se realizó la entrada."
                             )},
                        ]
                    },
                    {
                        "id": "datos_residencia_anterior",
                        "title_es": "Datos del Permiso de Residencia Anterior",
                        "source_document": "residencia_anterior",
                        "condition": {"solicitud_type": "renovacion"},
                        "fields": [
                            {"key": "numero_nie", "label_es": "N° N.I.E.", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "fecha_expedicion_residencia", "label_es": "Fecha Expedición", "type": "date",
                             "required": True, "readonly": True},
                            {"key": "fecha_expiracion_residencia", "label_es": "Fecha Expiración", "type": "date",
                             "required": True, "readonly": True},
                            {"key": "fecha_primera_residencia", "label_es": "Fecha Primera Residencia", "type": "date",
                             "required": False, "readonly": True},
                        ]
                    },
                ]
            }
        ))

        # Step 3: Form Review 2 - Professional data + company (Phase 1 only)
        # NOTE: es_persona_juridica moved to step 0 (SELECTION)
        self.add_step(WorkflowStep(
            step_number=3,
            step_id="form_review_2",
            step_type=StepType.FORM_REVIEW,
            title_es="Datos Profesionales",
            description_es="Complete sus datos profesionales y de empresa (si aplica)",
            config={
                "condition": {"con_nota_ingreso": "false"},
                "sections": [
                    {
                        "id": "datos_profesionales",
                        "title_es": "Datos Profesionales y Personales",
                        "fields": [
                            {"key": "profesion", "label_es": "Profesión", "type": "text",
                             "required": True},
                            {"key": "lugar_trabajo", "label_es": "Lugar de Trabajo", "type": "text",
                             "required": True},
                            {"key": "direccion_gq", "label_es": "Dirección en Guinea Ecuatorial", "type": "text",
                             "required": True},
                        ]
                    },
                    {
                        "id": "datos_empresa",
                        "title_es": "Datos de la Empresa (Persona Jurídica)",
                        "source_document": "nif_autorizacion",
                        "condition": {"es_persona_juridica": "true"},
                        "fields": [
                            {"key": "empresa_nif", "label_es": "NIF de la Empresa", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "empresa_razon_social", "label_es": "Razón Social", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "tipo_autorizacion", "label_es": "Tipo de Autorización", "type": "text",
                             "required": True, "readonly": True},
                        ]
                    },
                ]
            }
        ))

        # Step 4: Form Review 3 - Support documents verification (Phase 1 only)
        self.add_step(WorkflowStep(
            step_number=4,
            step_id="form_review_3",
            step_type=StepType.FORM_REVIEW,
            title_es="Verificación de Documentos de Soporte",
            description_es="Verifique los datos extraídos de los documentos de soporte",
            config={
                "condition": {"con_nota_ingreso": "false"},
                "sections": [
                    {
                        "id": "buena_conducta",
                        "title_es": "Certificado de Buena Conducta",
                        "source_document": "certificado_conducta",
                        "fields": [
                            {"key": "buena_conducta_numero", "label_es": "N° Certificado",
                             "type": "text", "required": False, "readonly": True, "pdf_exclude": True},
                            {"key": "buena_conducta_fecha", "label_es": "Fecha de Expedición",
                             "type": "date", "required": True, "readonly": True, "pdf_exclude": True},
                            {"key": "buena_conducta_comunidad", "label_es": "Comunidad de Vecinos",
                             "type": "text", "required": True, "readonly": True, "pdf_exclude": True},
                            {"key": "buena_conducta_municipio", "label_es": "Municipio",
                             "type": "text", "required": True, "readonly": True, "pdf_exclude": True},
                            {"key": "buena_conducta_resultado", "label_es": "Resultado",
                             "type": "text", "required": True, "readonly": True, "pdf_exclude": True},
                        ]
                    },
                    {
                        "id": "antecedentes_gq",
                        "title_es": "Antecedentes Penales (GQ)",
                        "source_document": "antecedentes_penales",
                        "condition": {"solicitud_type": "renovacion"},
                        "fields": [
                            {"key": "antecedentes_timbre", "label_es": "N° Timbre Fiscal",
                             "type": "text", "required": False, "readonly": True, "pdf_exclude": True},
                            {"key": "antecedentes_fecha", "label_es": "Fecha de Expedición",
                             "type": "date", "required": True, "readonly": True, "pdf_exclude": True},
                            {"key": "antecedentes_resultado", "label_es": "Resultado",
                             "type": "text", "required": True, "readonly": True, "pdf_exclude": True},
                        ]
                    },
                    {
                        "id": "antecedentes_intl",
                        "title_es": "Antecedentes Penales (País de Procedencia)",
                        "source_document": "antecedentes_penales",
                        "condition": {"solicitud_type": "expedicion"},
                        "fields": [
                            {"key": "antecedentes_intl_numero", "label_es": "N° Referencia",
                             "type": "text", "required": False, "readonly": True, "pdf_exclude": True},
                            {"key": "antecedentes_intl_fecha", "label_es": "Fecha de Expedición",
                             "type": "date", "required": True, "readonly": True, "pdf_exclude": True},
                            {"key": "antecedentes_intl_pais", "label_es": "País Emisor",
                             "type": "text", "required": True, "readonly": True, "pdf_exclude": True},
                            {"key": "antecedentes_intl_resultado", "label_es": "Resultado",
                             "type": "text", "required": True, "readonly": True, "pdf_exclude": True},
                        ]
                    },
                    {
                        "id": "nif_verificacion",
                        "title_es": "Datos del NIF de la Empresa",
                        "source_document": "nif_autorizacion",
                        "condition": {"es_persona_juridica": "true"},
                        "description_es": (
                            "Datos extraídos del Certificado NIF o Autorización Gubernativa. "
                            "Se muestran los campos según el tipo de documento presentado."
                        ),
                        "fields": [
                            {"key": "nif_empresa_nif", "label_es": "NIF",
                             "type": "text", "required": False, "readonly": True, "pdf_exclude": True},
                            {"key": "nif_empresa_expediente", "label_es": "N° Expediente",
                             "type": "text", "required": False, "readonly": True, "pdf_exclude": True},
                            {"key": "nif_empresa_nombre", "label_es": "Razón Social",
                             "type": "text", "required": False, "readonly": True, "pdf_exclude": True},
                            {"key": "nif_empresa_telefono", "label_es": "Teléfono",
                             "type": "text", "required": False, "readonly": True, "pdf_exclude": True},
                            {"key": "autorizacion_numero", "label_es": "N° Autorización",
                             "type": "text", "required": False, "readonly": True, "pdf_exclude": True},
                            {"key": "autorizacion_delegacion", "label_es": "Autoridad Emisora",
                             "type": "text", "required": False, "readonly": True, "pdf_exclude": True},
                            {"key": "autorizacion_provincia", "label_es": "Provincia",
                             "type": "text", "required": False, "readonly": True, "pdf_exclude": True},
                            {"key": "autorizacion_fecha", "label_es": "Fecha Autorización",
                             "type": "date", "required": False, "readonly": True, "pdf_exclude": True},
                        ]
                    },
                ]
            }
        ))

        # Step 5: Appointment Phase 1 — Extranjería (BEFORE payments, sin nota only)
        self.add_step(WorkflowStep(
            step_number=5,
            step_id="appointment",
            step_type=StepType.APPOINTMENT,
            title_es="Cita en Extranjería",
            description_es="Seleccione una fecha y lugar para entregar su expediente en Extranjería",
            config={
                "condition": {"con_nota_ingreso": "false"},
                "entity_code": "EXTRANJERIA",
                "dynamic_locations": True,
            }
        ))

        # Step 6: Stamp payment Phase 1 (Cédula + Póliza = 2,500 XAF, sin nota only)
        # Note: Filtered out in frontend, cost folded into tariff breakdown
        self.add_step(WorkflowStep(
            step_number=6,
            step_id="stamp_payment",
            step_type=StepType.PAYMENT,
            title_es="Pago de Timbres (Cédula y Póliza)",
            description_es="Pago de timbres fiscales: Cédula Personal (1,500 XAF) + Póliza (1,000 XAF)",
            config={
                "condition": {"con_nota_ingreso": "false"},
                "currency": "XAF",
                "payment_type": "stamps",
                "fixed_amount": 2500,
                "breakdown": [
                    {"code": "CEDULA_PERSONAL", "name_es": "Cédula Personal", "amount": 1500},
                    {"code": "POLIZA", "name_es": "Póliza", "amount": 1000},
                ],
            }
        ))

        # Step 7: Payment Phase 1 — stamps only (sin nota, tariff returns 0 for NOTA_INGRESO type)
        self.add_step(WorkflowStep(
            step_number=7,
            step_id="payment",
            step_type=StepType.PAYMENT,
            title_es="Pago de Timbres",
            description_es="Pago de los timbres fiscales del expediente",
            config={
                "condition": {"con_nota_ingreso": "false"},
                "currency": "XAF",
                "payment_type": "stamps_phase1",
            }
        ))

        # =====================================================================
        # Phase 2 steps — Con Nota de Ingreso (user already has nota from Extranjería)
        # =====================================================================

        # Step 8: Upload nota de ingreso + identity document
        self.add_step(WorkflowStep(
            step_number=8,
            step_id="upload_nota",
            step_type=StepType.DOCUMENT_UPLOAD,
            title_es="Nota de Ingreso y Documento de Identidad",
            description_es=(
                "Cargue la Nota de Ingreso emitida por Extranjería y su documento de identidad "
                "(pasaporte o permiso de residencia anterior)"
            ),
            config={
                "condition": {"con_nota_ingreso": "true"},
                "dynamic_documents": True,
                "max_file_size_mb": 10,
            }
        ))

        # Step 9: Form Review — Nota de Ingreso data verification
        self.add_step(WorkflowStep(
            step_number=9,
            step_id="form_review_nota",
            step_type=StepType.FORM_REVIEW,
            title_es="Verificación de la Nota de Ingreso",
            description_es="Verifique los datos extraídos de la Nota de Ingreso y su documento de identidad",
            config={
                "condition": {"con_nota_ingreso": "true"},
                "sections": [
                    {
                        "id": "datos_nota",
                        "title_es": "Datos de la Nota de Ingreso",
                        "source_document": "nota_ingreso",
                        "fields": [
                            {"key": "nota_numero", "label_es": "N° Nota", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "nota_concepto", "label_es": "Concepto de Pago", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "nota_montant", "label_es": "Monto (XAF)", "type": "number",
                             "required": True, "readonly": True},
                            {"key": "nota_date_emission", "label_es": "Fecha de Emisión", "type": "date",
                             "required": True, "readonly": True},
                            {"key": "nota_dias_validez", "label_es": "Días de Validez", "type": "number",
                             "required": False, "readonly": True},
                            {"key": "nota_organisme", "label_es": "Organismo Emisor", "type": "text",
                             "required": False, "readonly": True},
                        ],
                    },
                    {
                        "id": "datos_identidad_pasaporte",
                        "title_es": "Datos de Identidad (Pasaporte)",
                        "source_document": "pasaporte",
                        "condition": {"solicitud_type": "expedicion"},
                        "fields": [
                            {"key": "numero_pasaporte", "label_es": "N° Pasaporte", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "apellidos", "label_es": "Apellidos", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "nombres", "label_es": "Nombres", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "nacionalidad", "label_es": "Nacionalidad", "type": "text",
                             "required": True, "readonly": True},
                        ],
                    },
                    {
                        "id": "datos_identidad_residencia",
                        "title_es": "Datos de Identidad (Residencia Anterior)",
                        "source_document": "residencia_anterior",
                        "condition": {"solicitud_type": "renovacion"},
                        "fields": [
                            {"key": "numero_nie", "label_es": "N° N.I.E.", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "apellidos", "label_es": "Apellidos", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "nombres", "label_es": "Nombres", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "fecha_expiracion_residencia", "label_es": "Fecha Expiración",
                             "type": "date", "required": True, "readonly": True},
                        ],
                    },
                ],
            }
        ))

        # Step 10: Appointment Phase 2 — CNEDOGE (permit collection)
        self.add_step(WorkflowStep(
            step_number=10,
            step_id="appointment_cnedoge",
            step_type=StepType.APPOINTMENT,
            title_es="Cita para Recogida del Permiso (CNEDOGE)",
            description_es="Seleccione una fecha y lugar para recoger su permiso de residencia en CNEDOGE",
            config={
                "condition": {"con_nota_ingreso": "true"},
                "entity_code": "CNEDOGE",
                "dynamic_locations": True,
            }
        ))

        # Step 11: Payment Phase 2 — Main residence permit payment
        self.add_step(WorkflowStep(
            step_number=11,
            step_id="payment_phase2",
            step_type=StepType.PAYMENT,
            title_es="Pago Principal del Permiso de Residencia",
            description_es="Pago del permiso de residencia según la duración solicitada",
            config={
                "condition": {"con_nota_ingreso": "true"},
                "currency": "XAF",
                "payment_type": "nota_ingreso_main",
            }
        ))

        # Step 12: Confirmation (both Phase 1 and Phase 2)
        self.add_step(WorkflowStep(
            step_number=12,
            step_id="confirmation",
            step_type=StepType.CONFIRMATION,
            title_es="Confirmación y Envío",
            description_es="Verifique todos los datos antes de enviar su solicitud",
            config={
                "show_summary": True,
                "agent_checklist": [
                    {"id": "pasaporte_valido", "label_es":
                     "He verificado que el pasaporte está vigente",
                     "required": True},
                    {"id": "sello_entrada", "label_es":
                     "He verificado el sello de entrada en el pasaporte (fecha, puesto fronterizo y autenticidad del sello ovalado oficial)",
                     "required": True},
                    {"id": "cemac_o_visado", "label_es":
                     "He verificado: nacional CEMAC con entrada < 90 días O nacional fuera CEMAC con visado válido",
                     "required": True},
                    {"id": "no_ecuatoguineano", "label_es":
                     "He comprobado que el solicitante NO es ciudadano ecuatoguineano",
                     "required": True},
                    {"id": "documentos_completos", "label_es":
                     "He verificado que todos los documentos están completos según tipo (primera/renovación)",
                     "required": True},
                    {"id": "persona_juridica_docs", "label_es":
                     "Para personas jurídicas: he verificado NIF, solvencia tributaria (vigente 30 días) y cédula personal",
                     "required": False},
                    {"id": "antecedentes_vigentes", "label_es":
                     "He verificado antecedentes penales vigentes (validez 3 meses desde expedición)",
                     "required": True},
                    {"id": "timbres_pagados", "label_es":
                     "He comprobado el pago de timbres (Cédula 1,500 + Póliza 1,000 = 2,500 XAF)",
                     "required": True},
                    {"id": "nota_ingreso_correcta", "label_es":
                     "He emitido la Nota de Ingreso con el monto correcto (200,000 o 100,000 XAF)",
                     "required": True},
                ],
                "rejection_reasons": [
                    {"id": "pasaporte_expirado", "label_es":
                     "Pasaporte expirado"},
                    {"id": "sin_sello_entrada", "label_es":
                     "Sin sello de entrada legal en el pasaporte"},
                    {"id": "cemac_90_dias", "label_es":
                     "Nacional CEMAC con estancia superior a 90 días sin regularización"},
                    {"id": "sin_visado", "label_es":
                     "Nacional fuera CEMAC sin visado de entrada válido"},
                    {"id": "visado_transito", "label_es":
                     "Visado de tránsito no válido para solicitar residencia"},
                    {"id": "ciudadano_ecuatoguineano", "label_es":
                     "Ciudadano ecuatoguineano - debe usar DIP, no permiso de residencia"},
                    {"id": "documentos_incompletos", "label_es":
                     "Documentos incompletos o ilegibles"},
                    {"id": "antecedentes_caducados", "label_es":
                     "Antecedentes penales caducados (más de 3 meses desde expedición)"},
                    {"id": "solvencia_caducada", "label_es":
                     "Certificado de solvencia tributaria caducado (más de 30 días)"},
                    {"id": "empresa_no_solvente", "label_es":
                     "Empresa no solvente fiscalmente (certificado indica NO SOLVENTE)"},
                    {"id": "datos_incoherentes", "label_es":
                     "Datos incoherentes entre documentos (nombres, DIP, fechas)"},
                    {"id": "residencia_vigente", "label_es":
                     "Permiso de residencia anterior aún vigente (no renovable)"},
                    {"id": "nota_caducada", "label_es":
                     "Nota de Ingreso caducada (validez 15 días)"},
                    {"id": "buena_conducta_desfavorable", "label_es":
                     "Certificado de buena conducta con resultado desfavorable"},
                    {"id": "otro", "label_es": "Otro (especificar)"},
                ],
            }
        ))

    def _setup_tariffs(self) -> None:
        """
        Tariff configuration: Nota de Ingreso with known official amounts.

        Base amounts (Orden Ministerial 01/2021):
        - EXPEDICION (primera vez): 200,000 XAF
        - RENOVACION: 100,000 XAF

        Supplements (stamps, paid before submission):
        - Cédula Personal: 1,500 XAF
        - Póliza: 1,000 XAF
        Total stamps: 2,500 XAF
        """
        self.set_tariff_config(TariffConfig(
            tariff_type=TariffType.NOTA_INGRESO,
            fixed_amounts={
                SolicitudType.EXPEDICION.value.upper(): 200000,
                SolicitudType.RENOVACION.value.upper(): 100000,
            },
            currency="XAF",
            supplements=[
                SupplementDefinition(
                    code="CEDULA_PERSONAL",
                    name_es="Cédula Personal",
                    unit_price=1500,
                    quantity=1,
                ),
                SupplementDefinition(
                    code="POLIZA",
                    name_es="Póliza",
                    unit_price=1000,
                    quantity=1,
                ),
            ],
            extra={
                "stamp_total_per_instance": 2500,
                "nota_validation": True,
            }
        ))

    # === Document Requirements ===

    def get_document_requirements(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None,
    ) -> List[DocumentRequirement]:
        """
        Get document requirements.

        Phase 1 (sin nota): Aligned with Orden Ministerial 01/2021 Art. 3 Section A.
          EXPEDICION (Art. 3.A.1): 12 documents + visado_entrada for non-CEMAC = 13 max
          RENOVACION (Art. 3.A.2): 11 documents (from law) + pasaporte (recommended)
        Phase 2 (con nota): Nota de Ingreso + identity document (2-3 docs).

        Dynamic conditions:
        - con_nota_ingreso: Phase 1 vs Phase 2 document set
        - persona_juridica/persona_fisica: based on form_data "es_persona_juridica" (set in step 0 SELECTION)
        - CEMAC/non-CEMAC: based on extracted passport "documento.codigo_pais"
        """
        # Phase 2 (con nota): simplified document set
        if self._is_con_nota(context):
            return self._get_phase2_document_requirements(solicitud_type, context)

        # Phase 1 (sin nota): full dossier — existing logic below

        # Resolve persona_juridica from form_data
        es_persona_juridica = None
        if context and context.form_data:
            pj_val = context.form_data.get("es_persona_juridica")
            if pj_val is not None:
                es_persona_juridica = str(pj_val).lower() == "true"

        # Resolve CEMAC status from passport OCR (EXPEDICION only)
        is_cemac = None
        if context and solicitud_type == SolicitudType.EXPEDICION:
            codigo_pais = context.get_extracted_field("pasaporte", "documento.codigo_pais")
            if codigo_pais:
                is_cemac = str(codigo_pais).strip().upper() in CEMAC_COUNTRY_CODES

        requirements: List[DocumentRequirement] = []
        order = 1

        # --- COMMON DOCUMENTS (both EXPEDICION and RENOVACION) ---

        # Art. 3.A.1.a / 3.A.2.a - Instancia de Solicitud
        requirements.append(DocumentRequirement(
            document_code="instancia_solicitud",
            document_name_es="Instancia de Solicitud",
            is_required=True,
            display_order=order,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es=(
                "Instancia de solicitud dirigida al Excmo. Sr. Ministro de Estado, "
                "Encargado de Seguridad Nacional"
            ),
        ))
        order += 1

        # Art. 3.A.1.b / 3.A.2.b - Fotografía digital
        requirements.append(DocumentRequirement(
            document_code="fotografias",
            document_name_es="Fotografía Digital Tamaño Carnet",
            is_required=True,
            display_order=order,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es=(
                "Una (1) fotografía digital reciente tamaño carnet con fondo blanco. "
                "Plataforma digital: una sola foto suficiente."
            ),
            config={"quantity": 1, "max_size_mb": 5},
        ))
        order += 1

        # --- EXPEDICION-ONLY DOCUMENTS ---

        if solicitud_type == SolicitudType.EXPEDICION:
            # Art. 3.A.1.c - Pasaporte (página de datos)
            requirements.append(DocumentRequirement(
                document_code="pasaporte",
                document_name_es="Pasaporte (Página de Datos)",
                schema_key="PASAPORTE_INTERNATIONAL_V1",
                is_required=True,
                display_order=order,
                condition_type=DocumentConditionType.IS_NEW,
                instructions_es=(
                    "Página de datos del pasaporte en vigor (Art. 3.A.1.c). "
                    "Escanee la página con la foto, datos personales y zona MRZ."
                ),
                faces_required=["recto", "verso"],
            ))
            order += 1

            # Sello de entrada (EXPEDICION — ALL applicants, CEMAC and non-CEMAC)
            requirements.append(DocumentRequirement(
                document_code="sello_entrada",
                document_name_es="Página del Pasaporte con Sello de Entrada",
                schema_key="SELLO_ENTRADA_GQ_V1",
                is_required=True,
                display_order=order,
                condition_type=DocumentConditionType.IS_NEW,
                instructions_es=(
                    "Escanee la página de su pasaporte donde se encuentra el sello "
                    "de ENTRADA más reciente a Guinea Ecuatorial (sello ovalado del "
                    "Ministerio de Seguridad Nacional con fecha y puesto fronterizo). "
                    "La fecha de entrada será extraída automáticamente."
                ),
            ))
            order += 1

            # Visado de entrada (non-CEMAC nationals only)
            # Dynamic: shown when passport not yet processed (is_cemac=None) or non-CEMAC
            _show_visa = is_cemac is None or is_cemac is False
            if _show_visa:
                requirements.append(DocumentRequirement(
                    document_code="visado_entrada",
                    document_name_es="Visado de Entrada a Guinea Ecuatorial",
                    schema_key="VISADO_GQ_V1",
                    is_required=is_cemac is False,
                    display_order=order,
                    condition_type=DocumentConditionType.CUSTOM,
                    condition_value={"nationality": "non_cemac"},
                    instructions_es=(
                        "Visado de entrada a Guinea Ecuatorial (tipo LIMITADO o ALTERNATIVO). "
                        "Requerido para nacionales fuera de la zona CEMAC. "
                        "Escanee la página del pasaporte donde se encuentra el sticker del visado. "
                        "Nacionales CEMAC (Camerún, Gabón, Congo, Chad, Centroáfrica): no requerido."
                    ),
                ))
                order += 1

            # Art. 3.A.1.f - Permanencia previa o prórroga de visado
            # Non-obligatory: applicant may still have a valid visa (no permanencia yet)
            requirements.append(DocumentRequirement(
                document_code="permanencia_previa",
                document_name_es="Permanencia Previa o Prórroga de Visado",
                is_required=False,
                display_order=order,
                condition_type=DocumentConditionType.IS_NEW,
                instructions_es=(
                    "Documento de permanencia previa en el pasaporte o prórroga de visado, "
                    "emitido por el Ministerio de Seguridad Nacional (Art. 3.A.1.f)"
                ),
            ))
            order += 1

        # --- RENOVACION-ONLY DOCUMENTS ---

        if solicitud_type == SolicitudType.RENOVACION:
            # Pasaporte — NOT in Art. 3.A.2 but recommended for identity verification
            requirements.append(DocumentRequirement(
                document_code="pasaporte",
                document_name_es="Pasaporte en Vigor (recomendado)",
                schema_key="PASAPORTE_INTERNATIONAL_V1",
                is_required=False,
                display_order=order,
                condition_type=DocumentConditionType.IS_RENEWAL,
                instructions_es=(
                    "Pasaporte en vigor del solicitante. No obligatorio por ley pero "
                    "recomendado para verificación de identidad por el agente."
                ),
                faces_required=["recto", "verso"],
            ))
            order += 1

            # Art. 3.A.2.c - Residencia anterior (fotocopia + original)
            requirements.append(DocumentRequirement(
                document_code="residencia_anterior",
                document_name_es="Permiso de Residencia Anterior",
                schema_key="PERMISO_RESIDENCIA_GQ_V1",
                is_required=True,
                display_order=order,
                condition_type=DocumentConditionType.IS_RENEWAL,
                instructions_es=(
                    "Fotocopia del permiso de residencia anterior con presentación del original "
                    "(Art. 3.A.2.c). Escanee recto y verso."
                ),
                faces_required=["recto", "verso"],
            ))
            order += 1

        # --- COMMON DOCUMENTS (continued) ---

        # Art. 3.A.1.d / 3.A.2.e - Carnet de empadronamiento
        # Non-obligatory: not all applicants have this document yet at application time
        requirements.append(DocumentRequirement(
            document_code="carnet_empadronamiento",
            document_name_es="Carnet de Empadronamiento",
            is_required=False,
            display_order=order,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es="Carnet de empadronamiento vigente",
        ))
        order += 1

        # Art. 3.A.1.e / 3.A.2.f - Permiso de trabajo
        requirements.append(DocumentRequirement(
            document_code="permiso_trabajo",
            document_name_es="Permiso de Trabajo",
            schema_key="PERMISO_TRABAJO_GQ_V1",
            is_required=True,
            display_order=order,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es=(
                "Permiso de trabajo emitido por el Ministerio competente"
            ),
        ))
        order += 1

        # Art. 3.A.1.g / 3.A.2.d - Certificado de Buena Conducta
        _conducta_source = (
            "comunidad de vecinos o consejo de poblado donde reside (Art. 3.A.1.g)"
            if solicitud_type == SolicitudType.EXPEDICION
            else "consejo de poblado o comunidad de vecinos donde reside (Art. 3.A.2.d)"
        )
        requirements.append(DocumentRequirement(
            document_code="certificado_conducta",
            document_name_es="Certificado de Buena Conducta",
            schema_key="CERTIFICADO_BUENA_CONDUCTA_GQ_V1",
            is_required=True,
            display_order=order,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es=f"Certificado de buena conducta expedido por la {_conducta_source}",
        ))
        order += 1

        # Art. 3.A.1.k / 3.A.2.j - Antecedentes Penales
        if solicitud_type == SolicitudType.EXPEDICION:
            _antecedentes_schema = "EXTRAIT_CASIER_JUDICIAIRE_INTERNATIONAL_V1"
            _antecedentes_source = "del país de procedencia (Art. 3.A.1.k)"
        else:
            _antecedentes_schema = "ANTECEDENTES_PENALES_GQ_V1"
            _antecedentes_source = (
                "emitidos por el Ministerio de Justicia, Culto e "
                "Instituciones Penitenciarias de GQ (Art. 3.A.2.j)"
            )
        requirements.append(DocumentRequirement(
            document_code="antecedentes_penales",
            document_name_es="Certificado de Antecedentes Penales",
            schema_key=_antecedentes_schema,
            is_required=True,
            display_order=order,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es=(
                f"Certificado negativo de antecedentes penales {_antecedentes_source}. "
                "Validez: 3 meses desde fecha de expedición."
            ),
        ))
        order += 1

        # Art. 3.A.1.l / 3.A.2.k - Atestación bancaria
        requirements.append(DocumentRequirement(
            document_code="atestacion_bancaria",
            document_name_es="Atestación Bancaria o Tarjeta Visa Internacional",
            schema_key="ATESTACION_BANCARIA_GQ_V1",
            is_required=True,
            display_order=order,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es=(
                "Atestación bancaria de uno de los bancos locales de Guinea Ecuatorial "
                "o tarjeta visa internacional"
            ),
        ))
        order += 1

        # --- PERSONA JURIDICA DOCUMENTS ---

        # Art. 3.A.1.h / 3.A.2.g - Autorización Gubernativa o NIF
        _show_juridica = es_persona_juridica is None or es_persona_juridica is True
        if _show_juridica:
            requirements.append(DocumentRequirement(
                document_code="nif_autorizacion",
                document_name_es="Autorización Gubernativa o NIF",
                schema_key=None,
                is_required=es_persona_juridica is True,
                display_order=order,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"form_field": "es_persona_juridica", "value": True},
                instructions_es=(
                    "Certificado NIF de la empresa O Autorización Gubernativa "
                    "(solo para personas jurídicas). Art. 3.A.1.h / Art. 3.A.2.g"
                ),
                config={
                    "accepted_schemas": {
                        "NIF": "CERTIFICADO_NIF_GQ_V1",
                        "AUTORIZACION": "AUTORIZACION_GUBERNATIVA_GQ_V1",
                    },
                    "hint_es": "Puede presentar el Certificado NIF o la Autorización Gubernativa",
                },
            ))
            order += 1

        # Art. 3.A.1.i / 3.A.2.h - Solvencia Tributaria
        if _show_juridica:
            requirements.append(DocumentRequirement(
                document_code="solvencia_tributaria",
                document_name_es="Certificado de Solvencia Tributaria",
                schema_key="SOLVENCIA_TRIBUTARIA_GQ_V1",
                is_required=es_persona_juridica is True,
                display_order=order,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"form_field": "es_persona_juridica", "value": True},
                instructions_es=(
                    "Certificado de solvencia tributaria de la empresa (solo para personas jurídicas). "
                    "Validez: 30 días desde fecha de expedición. Art. 3.A.1.i / Art. 3.A.2.h"
                ),
            ))
            order += 1

        # --- CEDULA PERSONAL ---
        # Tricky inversion: persona_juridica for EXPEDICION, persona_fisica for RENOVACION

        # Art. 3.A.1.j - Cédula Personal (EXPEDICION: personas jurídicas)
        if solicitud_type == SolicitudType.EXPEDICION:
            if _show_juridica:
                requirements.append(DocumentRequirement(
                    document_code="cedula_personal",
                    document_name_es="Cédula Personal",
                    is_required=es_persona_juridica is True,
                    display_order=order,
                    condition_type=DocumentConditionType.CUSTOM,
                    condition_value={"form_field": "es_persona_juridica", "value": True},
                    instructions_es=(
                        "Cédula personal del representante legal de la empresa "
                        "(solo para personas jurídicas, Art. 3.A.1.j)"
                    ),
                ))
                order += 1

        # Art. 3.A.2.i - Cédula Personal (RENOVACION: personas físicas — inversé!)
        if solicitud_type == SolicitudType.RENOVACION:
            _show_fisica = es_persona_juridica is None or es_persona_juridica is False
            if _show_fisica:
                requirements.append(DocumentRequirement(
                    document_code="cedula_personal",
                    document_name_es="Cédula Personal",
                    is_required=es_persona_juridica is False,
                    display_order=order,
                    condition_type=DocumentConditionType.CUSTOM,
                    condition_value={"form_field": "es_persona_juridica", "value": False},
                    instructions_es=(
                        "Cédula personal del solicitante "
                        "(solo para personas físicas, Art. 3.A.2.i)"
                    ),
                ))
                order += 1

        return requirements

    def _get_phase2_document_requirements(
        self,
        solicitud_type: SolicitudType,
        context: Optional[WorkflowContext] = None,
    ) -> List[DocumentRequirement]:
        """Phase 2 document requirements: Nota de Ingreso + identity."""
        requirements: List[DocumentRequirement] = []
        order = 1

        # Nota de Ingreso (always required for Phase 2)
        requirements.append(DocumentRequirement(
            document_code="nota_ingreso",
            document_name_es="Nota de Ingreso",
            schema_key="NOTA_INGRESO_RESIDENCIA_GQ_V1",
            is_required=True,
            display_order=order,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es=(
                "Nota de Ingreso emitida por la Dirección General de Extranjería. "
                "Escanee el documento completo con el sello oficial visible."
            ),
        ))
        order += 1

        # Pasaporte (required for EXPEDICION, recommended for RENOVACION)
        requirements.append(DocumentRequirement(
            document_code="pasaporte",
            document_name_es="Pasaporte (Página de Datos)",
            schema_key="PASAPORTE_INTERNATIONAL_V1",
            is_required=solicitud_type == SolicitudType.EXPEDICION,
            display_order=order,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es=(
                "Página de datos del pasaporte en vigor. "
                "Escanee la página con la foto, datos personales y zona MRZ."
            ),
            faces_required=["recto", "verso"],
        ))
        order += 1

        # Residencia anterior (RENOVACION only — to verify previous permit)
        if solicitud_type == SolicitudType.RENOVACION:
            requirements.append(DocumentRequirement(
                document_code="residencia_anterior",
                document_name_es="Permiso de Residencia Anterior",
                schema_key="PERMISO_RESIDENCIA_GQ_V1",
                is_required=True,
                display_order=order,
                condition_type=DocumentConditionType.IS_RENEWAL,
                instructions_es=(
                    "Fotocopia del permiso de residencia anterior. "
                    "Escanee recto y verso."
                ),
                faces_required=["recto", "verso"],
            ))
            order += 1

        return requirements

    # === Form Mapping ===

    def get_form_mapping(
        self,
        context: Optional[WorkflowContext] = None,
    ) -> Dict[str, str]:
        """Map extracted OCR data to form fields."""
        # Phase 2 (con nota): simplified mapping for nota + identity
        if self._is_con_nota(context):
            return self._get_phase2_form_mapping(context)

        # Phase 1 (sin nota): full mapping
        mapping: Dict[str, str] = {
            # Passport (OCR readonly) - form_review_1 (step 2)
            "numero_pasaporte": "pasaporte.documento.numero_pasaporte",
            "apellidos": "pasaporte.titular.apellidos",
            "nombres": "pasaporte.titular.nombres",
            "nacionalidad": "pasaporte.titular.nacionalidad",
            "sexo": "pasaporte.titular.sexo",
            "fecha_nacimiento": "pasaporte.titular.fecha_nacimiento",
            "lugar_nacimiento": "pasaporte.titular.lugar_nacimiento",
            "fecha_expiracion_pasaporte": "pasaporte.documento.fecha_expiracion",
            # NIF (OCR, persona_juridica) - form_review_2 (step 3)
            "empresa_nif": "nif_autorizacion.empresa.nif",
            "empresa_razon_social": "nif_autorizacion.empresa.denominacion_social",
            # tipo_autorizacion: dual-schema path (NIF vs AUTORIZACION_GUBERNATIVA)
            # Default: NIF schema path. Overridden below if AUTORIZACION detected.
            "tipo_autorizacion": "nif_autorizacion.empresa.autorizacion",
            # Buena conducta (OCR readonly) - form_review_3 (step 4)
            "buena_conducta_numero": "certificado_conducta.documento.numero_certificado",
            "buena_conducta_fecha": "certificado_conducta.documento.fecha_expedicion",
            "buena_conducta_comunidad": "certificado_conducta.emisor.comunidad_vecinos",
            "buena_conducta_municipio": "certificado_conducta.emisor.municipio",
            "buena_conducta_resultado": "certificado_conducta.certificacion.resultado",
            # NIF verification (OCR readonly) - form_review_3 (step 4)
            # Paths for CERTIFICADO_NIF_GQ_V1 schema
            "nif_empresa_nif": "nif_autorizacion.empresa.nif",
            "nif_empresa_expediente": "nif_autorizacion.documento.numero_expediente",
            "nif_empresa_nombre": "nif_autorizacion.empresa.denominacion_social",
            "nif_empresa_telefono": "nif_autorizacion.contacto.telefono",
            # Paths for AUTORIZACION_GUBERNATIVA_GQ_V1 schema (alternative)
            "autorizacion_numero": "nif_autorizacion.documento.numero_autorizacion",
            "autorizacion_delegacion": "nif_autorizacion.organisme_emetteur.delegacion_gobierno",
            "autorizacion_provincia": "nif_autorizacion.organisme_emetteur.provincia",
            "autorizacion_fecha": "nif_autorizacion.validez.fecha_autorizacion",
        }

        # Dual-schema fallback: tipo_autorizacion lives at different paths
        # NIF: empresa.autorizacion | AUTORIZACION_GUBERNATIVA: documento.tipo_autorizacion
        if context and context.get_extracted_field("nif_autorizacion", "documento.tipo_autorizacion"):
            mapping["tipo_autorizacion"] = "nif_autorizacion.documento.tipo_autorizacion"

        solicitud_type = context.solicitud_type if context else None

        # EXPEDICION: add entry stamp + international antecedentes mappings
        if solicitud_type == SolicitudType.EXPEDICION:
            mapping.update({
                "fecha_entrada_pais": "sello_entrada.ultimo_sello_entrada.fecha_entrada",
                "puesto_fronterizo": "sello_entrada.ultimo_sello_entrada.puesto_fronterizo",
                # Antecedentes international (EXPEDICION) - form_review_3 (step 4)
                "antecedentes_intl_numero": "antecedentes_penales.documento.numero_reference",
                "antecedentes_intl_fecha": "antecedentes_penales.documento.fecha_expedicion",
                "antecedentes_intl_pais": "antecedentes_penales.documento.nom_pays",
                "antecedentes_intl_resultado": "antecedentes_penales.certificacion.resultado",
            })

        # RENOVACION: add previous residence + GQ antecedentes mappings
        if solicitud_type == SolicitudType.RENOVACION:
            mapping.update({
                "numero_nie": "residencia_anterior.documento.numero_nie",
                "fecha_expedicion_residencia": "residencia_anterior.documento.fecha_expedicion",
                "fecha_expiracion_residencia": "residencia_anterior.documento.fecha_expiracion",
                "fecha_primera_residencia": "residencia_anterior.documento.fecha_primera_residencia",
                # Antecedentes GQ (RENOVACION) - form_review_3 (step 4)
                "antecedentes_timbre": "antecedentes_penales.documento.numero_timbre_fiscal",
                "antecedentes_fecha": "antecedentes_penales.documento.fecha_expedicion",
                "antecedentes_resultado": "antecedentes_penales.certificacion.resultado",
            })

        return mapping

    def _get_phase2_form_mapping(
        self,
        context: Optional[WorkflowContext] = None,
    ) -> Dict[str, str]:
        """Phase 2 form mapping: nota de ingreso + identity document."""
        mapping: Dict[str, str] = {
            # Nota de Ingreso (OCR readonly) — form_review_nota (step 9)
            "nota_numero": "nota_ingreso.bloc_paiement.numero_nota",
            "nota_concepto": "nota_ingreso.bloc_paiement.concepto_pago",
            "nota_montant": "nota_ingreso.bloc_paiement.montant_chiffre",
            "nota_date_emission": "nota_ingreso.bloc_verification.date_emission",
            "nota_dias_validez": "nota_ingreso.bloc_verification.dias_validez",
            "nota_organisme": "nota_ingreso.bloc_administratif.departement_emetteur",
        }

        solicitud_type = context.solicitud_type if context else None

        if solicitud_type == SolicitudType.EXPEDICION:
            # Identity from passport (EXPEDICION: pasaporte required)
            mapping.update({
                "numero_pasaporte": "pasaporte.documento.numero_pasaporte",
                "apellidos": "pasaporte.titular.apellidos",
                "nombres": "pasaporte.titular.nombres",
                "nacionalidad": "pasaporte.titular.nacionalidad",
            })
        elif solicitud_type == SolicitudType.RENOVACION:
            # Identity from previous residence permit (RENOVACION: residencia required)
            mapping.update({
                "numero_nie": "residencia_anterior.documento.numero_nie",
                "apellidos": "residencia_anterior.titular.apellidos",
                "nombres": "residencia_anterior.titular.nombres",
                "fecha_expiracion_residencia": "residencia_anterior.documento.fecha_expiracion",
            })

        return mapping

    # === Step Validation ===

    def validate_step(
        self,
        step_number: int,
        context: WorkflowContext,
    ) -> List[ValidationResult]:
        """
        Validate form review steps with workflow business rules.

        9 rules (Layer 2 — business logic not covered by SchemaValidationEngine):

        form_review_1 (step 2):
         1. entrada_legal_fecha: Entry date must exist (OCR or user correction)
         2. cemac_90_dias: CEMAC entry < 90 days (warning with day count)
         3. visado_requerido: Non-CEMAC + EXPEDICION → visa + date coherence
         4. nacionalidad_extranjero: NOT Equatoguinean
         5. residencia_renovable: Residence expiring < 90 days (RENOVACION, warning)
         6. nombres_coherentes: Levenshtein passport ↔ residence (RENOVACION)

        form_review_2 (step 3):
         7. solvencia_resultado: NO_SOLVENTE → warning, NOT blocking (persona_juridica)

        form_review_3 (step 4):
         8. buena_conducta_resultado: DESFAVORABLE → warning (agent evaluates)
         9. antecedentes_resultado: POSITIVO/HAS_CONVICTIONS → error (blocking)

        Document validity periods (antecedentes < 3 months, solvencia < 30 days,
        passport not expired) are handled by SchemaValidationEngine JSON rules.
        """
        results = super().validate_step(step_number, context)

        step = self.get_step(step_number)
        if not step:
            return results

        if step.step_id == "form_review_1":
            results.extend(self._validate_identity_and_entry(context))

        if step.step_id == "form_review_2":
            results.extend(self._validate_professional_data(context))

        if step.step_id == "form_review_3":
            results.extend(self._validate_support_documents(context))

        if step.step_id == "form_review_nota":
            results.extend(self._validate_nota_ingreso(context))

        return results

    def _validate_identity_and_entry(self, context: WorkflowContext) -> List[ValidationResult]:
        """
        Validate identity, entry conditions (CEMAC/visa), and previous residence.

        ONLY workflow business logic that SchemaValidationEngine cannot express:
        - CEMAC 90-day calculation (requires cross-step: passport nationality + entry date)
        - Visa requirement decision (requires passport nationality context)
        - Visa date coherence with entry (cross-document business rule)
        - Nationality check against known GQ aliases (workflow-specific list)

        Delegated to SchemaValidationEngine (NOT duplicated here):
        - pasaporte_not_expired (pasaporte_international.json)
        - fecha_entrada_not_future (sello_entrada_gq.json)
        - entrada_dentro_validez_pasaporte (sello_entrada_gq.json cross-doc)
        - tipo_sello_entrada == ENTRADA (sello_entrada_gq.json)
        - sello_oficial + texto_legible (sello_entrada_gq.json autenticacion)
        - tipo_visado_valido LIMITADO/ALTERNATIVO (visado_gq.json)
        """
        results: List[ValidationResult] = []
        today = datetime.today()

        # Determine CEMAC status from passport country code
        codigo_pais = context.get_extracted_field("pasaporte", "documento.codigo_pais")
        is_cemac = False
        if codigo_pais:
            is_cemac = str(codigo_pais).strip().upper() in CEMAC_COUNTRY_CODES

        # EXPEDICION-specific entry rules
        if context.solicitud_type == SolicitudType.EXPEDICION:
            # Rule 1: Entry date must exist (OCR-extracted from stamp, editable by user)
            # Priority: form_data (user correction) > OCR extraction
            fecha_entrada_str = context.form_data.get("fecha_entrada_pais")
            if not fecha_entrada_str:
                fecha_entrada_str = context.get_extracted_field(
                    "sello_entrada", "ultimo_sello_entrada.fecha_entrada"
                )
            if not fecha_entrada_str:
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id="entrada_legal_fecha",
                    severity="error",
                    message_es=(
                        "No se pudo determinar la fecha de entrada al país. "
                        "Cargue la página del pasaporte con el sello de entrada "
                        "o indique la fecha manualmente."
                    ),
                    field_name="fecha_entrada_pais",
                    document_code="sello_entrada",
                ))
            else:
                fecha_entrada = self._parse_date(str(fecha_entrada_str))
                if fecha_entrada and fecha_entrada <= today:
                    days_since_entry = (today - fecha_entrada).days

                    # Rule 2: CEMAC nationals — entry must be < 90 days
                    if is_cemac and days_since_entry > 90:
                        extra_days = days_since_entry - 90
                        results.append(ValidationResult(
                            is_valid=False,
                            rule_id="cemac_90_dias",
                            severity="warning",
                            message_es=(
                                f"Nacional CEMAC con estancia de {days_since_entry} días "
                                f"(excede el límite de 90 días por {extra_days} días). "
                                "El agente evaluará la situación."
                            ),
                            field_name="fecha_entrada_pais",
                        ))

            # Rule 3: Non-CEMAC must have visa document processed + date coherence
            if codigo_pais and not is_cemac:
                visado_tipo = context.get_extracted_field(
                    "visado_entrada", "visado.tipo_visado"
                )
                if not visado_tipo:
                    results.append(ValidationResult(
                        is_valid=False,
                        rule_id="visado_requerido",
                        severity="error",
                        message_es=(
                            "Los nacionales fuera de la zona CEMAC deben presentar un visado "
                            "de entrada válido a Guinea Ecuatorial. Cargue la página del pasaporte "
                            "donde se encuentra el sticker del visado."
                        ),
                        document_code="visado_entrada",
                    ))
                else:
                    # Rule 3b: Visa date coherence — entry must be after visa issue
                    visa_fecha_str = context.get_extracted_field(
                        "visado_entrada", "documento.fecha_expedicion"
                    )
                    if visa_fecha_str and fecha_entrada_str:
                        visa_fecha = self._parse_date(str(visa_fecha_str))
                        fecha_entrada_check = self._parse_date(str(fecha_entrada_str))
                        if visa_fecha and fecha_entrada_check:
                            if fecha_entrada_check < visa_fecha:
                                results.append(ValidationResult(
                                    is_valid=False,
                                    rule_id="visado_requerido",
                                    severity="error",
                                    message_es=(
                                        "La fecha de entrada al país es anterior a la fecha "
                                        "de expedición del visado. El visado debe haber sido "
                                        "emitido antes de la entrada."
                                    ),
                                    field_name="fecha_entrada_pais",
                                ))

        # Rule 5: Must NOT be Ecuatoguinean (foreigners only)
        nacionalidad = context.get_extracted_field("pasaporte", "titular.nacionalidad")
        if nacionalidad:
            nac_upper = str(nacionalidad).strip().upper()
            if nac_upper in ("GNQ", "GUINEA ECUATORIAL", "ECUATOGUINEANO", "ECUATOGUINEANA"):
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id="nacionalidad_extranjero",
                    severity="error",
                    message_es=(
                        "El solicitante es ciudadano ecuatoguineano. "
                        "El permiso de residencia es solo para extranjeros. "
                        "Los ciudadanos de GQ deben usar el DIP."
                    ),
                    field_name="nacionalidad",
                ))

        # RENOVACION-specific rules
        if context.solicitud_type == SolicitudType.RENOVACION:
            # Rule 6: Previous residence must be expiring (< 90 days) or already expired
            fecha_exp_res_str = context.get_extracted_field(
                "residencia_anterior", "documento.fecha_expiracion"
            )
            if fecha_exp_res_str:
                fecha_exp_res = self._parse_date(str(fecha_exp_res_str))
                if fecha_exp_res:
                    days_until_expiry = (fecha_exp_res - datetime.today()).days
                    if days_until_expiry > 90:
                        results.append(ValidationResult(
                            is_valid=False,
                            rule_id="residencia_renovable",
                            severity="warning",
                            message_es=(
                                f"El permiso de residencia no expira hasta dentro de "
                                f"{days_until_expiry} días. Solo puede renovar si expira "
                                "en menos de 90 días o ya está expirado."
                            ),
                            field_name="fecha_expiracion_residencia",
                        ))

            # Rule 7: Name coherence passport ↔ previous residence (Levenshtein)
            pasaporte_apellidos = context.get_extracted_field("pasaporte", "titular.apellidos")
            residencia_apellidos = context.get_extracted_field(
                "residencia_anterior", "titular.apellidos"
            )
            if pasaporte_apellidos and residencia_apellidos:
                pas_name = str(pasaporte_apellidos).strip().upper()
                res_name = str(residencia_apellidos).strip().upper()
                if pas_name and res_name:
                    similarity = self._levenshtein_similarity(pas_name, res_name)
                    if similarity < 0.85:
                        results.append(ValidationResult(
                            is_valid=False,
                            rule_id="nombres_coherentes",
                            severity="error",
                            message_es=(
                                f"Los apellidos del pasaporte ({pasaporte_apellidos}) "
                                f"no coinciden con la residencia anterior ({residencia_apellidos}). "
                                f"Similitud: {similarity:.0%}"
                            ),
                            field_name="apellidos",
                        ))

        return results

    def _validate_professional_data(self, context: WorkflowContext) -> List[ValidationResult]:
        """
        Validate solvencia resultado for persona jurídica.

        Only business logic: SchemaValidationEngine handles document validity
        (antecedentes < 3 months, solvencia < 30 days) via JSON rules.

        Delegated to SchemaValidationEngine (NOT duplicated here):
        - antecedentes_penales: certificado_vigente (< 3 months)
        - solvencia_tributaria: certificado_vigente (< 30 days)
        - solvencia_tributaria: resultado_presente (extraction check)
        """
        results: List[ValidationResult] = []

        # Rule 7: Solvencia resultado — NO_SOLVENTE = warning (agent decides)
        # SchemaValidationEngine flags resultado_no_solvente as document-level warning.
        # Here we add workflow-level context: the agent evaluates the business impact.
        es_pj = context.form_data.get("es_persona_juridica")
        if es_pj is not None and str(es_pj).lower() == "true":
            solv_resultado = context.get_extracted_field(
                "solvencia_tributaria", "certificacion.resultado"
            )
            if solv_resultado and str(solv_resultado).strip().upper() == "NO_SOLVENTE":
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id="solvencia_resultado",
                    severity="warning",
                    message_es=(
                        "El certificado de solvencia tributaria indica que la empresa "
                        "tiene obligaciones fiscales pendientes (NO SOLVENTE). "
                        "El agente evaluará si procede la solicitud."
                    ),
                    document_code="solvencia_tributaria",
                ))

        return results

    def _validate_support_documents(self, context: WorkflowContext) -> List[ValidationResult]:
        """
        Validate support document results from OCR extraction.

        Rule 8: buena_conducta_resultado — DESFAVORABLE = warning (agent decides)
        Rule 9: antecedentes_resultado — POSITIVO/HAS_CONVICTIONS = error (blocking)

        SchemaValidationEngine already handles document-level checks (signatures,
        validity periods, missing fields). These rules add workflow-level business
        context for the agent.
        """
        results: List[ValidationResult] = []

        # Rule 8: Buena conducta resultado
        bc_resultado = context.get_extracted_field(
            "certificado_conducta", "certificacion.resultado"
        )
        if bc_resultado and str(bc_resultado).strip().upper() == "DESFAVORABLE":
            results.append(ValidationResult(
                is_valid=False,
                rule_id="buena_conducta_resultado",
                severity="warning",
                message_es=(
                    "El certificado de buena conducta indica antecedentes desfavorables. "
                    "El agente evaluará la situación."
                ),
                document_code="certificado_conducta",
            ))

        # Rule 9: Antecedentes penales resultado
        # For RENOVACION: ANTECEDENTES_PENALES_GQ_V1 → resultado = NEGATIVO/POSITIVO
        # For EXPEDICION: EXTRAIT_CASIER_JUDICIAIRE → resultado = CLEAN/HAS_CONVICTIONS
        ant_resultado = context.get_extracted_field(
            "antecedentes_penales", "certificacion.resultado"
        )
        if ant_resultado:
            resultado_upper = str(ant_resultado).strip().upper()
            if resultado_upper in ("POSITIVO", "HAS_CONVICTIONS"):
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id="antecedentes_resultado",
                    severity="error",
                    message_es=(
                        "El certificado de antecedentes penales indica condenas existentes. "
                        "La solicitud de residencia no puede proceder."
                    ),
                    document_code="antecedentes_penales",
                ))

        return results

    def _validate_nota_ingreso(self, context: WorkflowContext) -> List[ValidationResult]:
        """
        Validate nota de ingreso for Phase 2 (con nota).

        Rule 10: nota_amount_coherent — extracted amount vs expected tariff (warning)
        Rule 11: nota_expired — date_emission + dias_validez < today (error)

        Other validations (tampon_officiel, organisme) are in the JSON schema
        NOTA_INGRESO_RESIDENCIA_GQ_V1.
        """
        results: List[ValidationResult] = []
        today = datetime.today()

        # Rule 10: Amount coherence — nota montant vs expected tariff
        # Priority: form_data (user correction) > OCR extraction (flat fallback)
        nota_montant_str = context.form_data.get("nota_montant")
        if not nota_montant_str:
            nota_montant_str = context.get_extracted_field(
                "nota_ingreso", "bloc_paiement.montant_chiffre"
            )
        if not nota_montant_str:
            # Flat fallback: Gemini returns flat fields
            nota_montant_str = context.extracted_data.get("nota_ingreso", {}).get("montant_chiffre")
        if nota_montant_str:
            try:
                nota_montant = int(str(nota_montant_str).replace(" ", "").replace(",", ""))
                expected = self.get_tariff(
                    context.solicitud_type, context=context
                )
                if expected > 0 and nota_montant != expected:
                    results.append(ValidationResult(
                        is_valid=False,
                        rule_id="nota_amount_coherent",
                        severity="warning",
                        message_es=(
                            f"El monto de la Nota de Ingreso ({nota_montant:,} XAF) "
                            f"no coincide con el monto esperado ({expected:,} XAF). "
                            "El agente verificará la coherencia."
                        ),
                        field_name="nota_montant",
                        document_code="nota_ingreso",
                    ))
            except (ValueError, TypeError):
                pass

        # Rule 11: Nota expired — date_emission + dias_validez < today
        # Priority: form_data (user correction) > OCR extraction (flat fallback)
        fecha_emission_str = context.form_data.get("nota_date_emission")
        if not fecha_emission_str:
            fecha_emission_str = context.get_extracted_field(
                "nota_ingreso", "bloc_verification.date_emission"
            )
        if not fecha_emission_str:
            fecha_emission_str = context.extracted_data.get("nota_ingreso", {}).get("date_emission")

        dias_validez_str = context.form_data.get("nota_dias_validez")
        if not dias_validez_str:
            dias_validez_str = context.get_extracted_field(
                "nota_ingreso", "bloc_verification.dias_validez"
            )
        if not dias_validez_str:
            dias_validez_str = context.extracted_data.get("nota_ingreso", {}).get("dias_validez")
        if fecha_emission_str:
            fecha_emission = self._parse_date(str(fecha_emission_str))
            if fecha_emission:
                dias_validez = 15  # default validity if not specified
                if dias_validez_str:
                    try:
                        dias_validez = int(str(dias_validez_str))
                    except (ValueError, TypeError):
                        pass
                fecha_expiration = fecha_emission + timedelta(days=dias_validez)
                if today > fecha_expiration:
                    days_expired = (today - fecha_expiration).days
                    results.append(ValidationResult(
                        is_valid=False,
                        rule_id="nota_expired",
                        severity="error",
                        message_es=(
                            f"La Nota de Ingreso ha caducado hace {days_expired} día(s). "
                            f"Emitida el {fecha_emission_str}, validez {dias_validez} días. "
                            "Debe obtener una nueva Nota de Ingreso."
                        ),
                        field_name="nota_date_emission",
                        document_code="nota_ingreso",
                    ))

        return results

    # === Tariff Override (Phase 2) ===

    def get_tariff(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None,
    ) -> int:
        """
        Override tariff for Phase 2 (con nota).

        Phase 1 (sin nota): Returns 0 (TariffType.NOTA_INGRESO → stamps only)
        Phase 2 (con nota):
          - EXPEDICION: 200,000 XAF (fixed)
          - RENOVACION: 100,000 XAF × duracion_anos
        """
        if not self._is_con_nota(context):
            return super().get_tariff(solicitud_type, motivo, context)

        # Phase 2: actual amounts
        if solicitud_type == SolicitudType.EXPEDICION:
            return 200000
        # RENOVACION: base × duration coefficient
        duracion = self._get_duracion_anos(context)
        return 100000 * duracion

    def get_tariff_breakdown(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None,
        base_description: str = "",
    ) -> Dict[str, Any]:
        """
        Override tariff breakdown for Phase 2 (con nota).

        Phase 1 (sin nota): Standard breakdown from TariffConfig (returns 0 base + stamps)
        Phase 2 (con nota): Fixed amount with duration label
        """
        if not self._is_con_nota(context):
            return super().get_tariff_breakdown(solicitud_type, motivo, context, base_description)

        base_amount = self.get_tariff(solicitud_type, motivo, context)
        if solicitud_type == SolicitudType.EXPEDICION:
            desc = "Permiso de Residencia — Primera vez (200 000 XAF)"
        else:
            d = self._get_duracion_anos(context)
            desc = f"Renovación de Residencia ({d} año{'s' if d > 1 else ''} × 100 000 XAF)"

        return {
            "base_amount": base_amount,
            "base_description": base_description or desc,
            "supplements": [],
            "supplements_total": 0,
            "penalties_amount": 0,
            "penalty_reason": None,
            "total_amount": base_amount,
            "currency": "XAF",
            "tariff_type": "FIXED",
            "workflow_code": self.workflow_code.value,
            "solicitud_type": solicitud_type.value,
        }

    # === Phase helpers ===

    def _is_con_nota(self, context: Optional[WorkflowContext]) -> bool:
        """Check if user selected Phase 2 (con nota de ingreso)."""
        if context and context.form_data:
            return str(context.form_data.get("con_nota_ingreso", "false")).lower() == "true"
        return False

    def _get_duracion_anos(self, context: Optional[WorkflowContext]) -> int:
        """Get duration in years for RENOVACION coefficient (1, 2, or 5)."""
        if context and context.form_data:
            try:
                val = int(context.form_data.get("duracion_anos", "1"))
                if val in (1, 2, 5):
                    return val
            except (ValueError, TypeError):
                pass
        return 1

    # === Utility Methods ===

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        """Parse date string in multiple formats."""
        date_str = date_str.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _normalize_id(id_str: str) -> str:
        """Normalize ID by removing dots, spaces, dashes for comparison."""
        return id_str.replace(".", "").replace(" ", "").replace("-", "").upper()

    @staticmethod
    def _levenshtein_similarity(s1: str, s2: str) -> float:
        """Calculate Levenshtein similarity ratio between two strings."""
        if not s1 or not s2:
            return 0.0
        if s1 == s2:
            return 1.0
        len1, len2 = len(s1), len(s2)
        max_len = max(len1, len2)
        if max_len == 0:
            return 1.0
        matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        for i in range(len1 + 1):
            matrix[i][0] = i
        for j in range(len2 + 1):
            matrix[0][j] = j
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if s1[i - 1] == s2[j - 1] else 1
                matrix[i][j] = min(
                    matrix[i - 1][j] + 1,
                    matrix[i][j - 1] + 1,
                    matrix[i - 1][j - 1] + cost,
                )
        distance = matrix[len1][len2]
        return 1.0 - (distance / max_len)


# =============================================================================
# Singleton & Registration
# =============================================================================

_workflow: Optional[ResidenciaWorkflow] = None


def get_residencia_workflow() -> ResidenciaWorkflow:
    """Get or create the singleton workflow instance."""
    global _workflow
    if _workflow is None:
        _workflow = ResidenciaWorkflow()
    return _workflow
