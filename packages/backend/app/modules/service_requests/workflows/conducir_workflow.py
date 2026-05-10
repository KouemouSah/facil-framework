"""
ConducirWorkflow v2 - Autonomous driving certificate workflow.

This is a PREDEFINED workflow with complete business logic.
ALIGNED WITH workflow_interface.py using PredefinedWorkflow architecture.

Types:
- NUEVO: First request (includes exam) - Available for CITIZEN_GQ and RESIDENT
- CANJE: Foreign license conversion - Only for RESIDENT
- RENOVACION: Certificate renewal
- DUPLICADO: Duplicate (loss, theft, damage)
- EXTENSION: Class extension

Entity: DGT (Direccion General de Trafico Rodado y Seguridad Vial)

License Classes:
- A: Motorcycles (18+)
- B: Light vehicles (18+)
- B+: Light vehicles + trailer (18+)
- C: Heavy vehicles (21+)
- D: Passenger transport (21+)
- E: Articulated vehicles (21+)
- F: Special vehicles (18+)

Note: Class AM (minors 16+) is deferred to Phase 2.
Note: COPIA_ADICIONAL excluded - managed by Comisaría Policía, not DGT.

@version 2.1
@date 2026-02-05
@migration Option C - Dynamic Form Review Architecture
@changelog v2.1: Corrections post-analyse critique (6 points alignement avec Pasaporte)
"""
from typing import List, Dict, Any, Optional
from enum import Enum

from .workflow_interface import (
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
from ..models.enums import (
    WorkflowCode,
    WorkflowCategory,
    EntityCode,
    TariffType,
    SolicitudType,
    DocumentConditionType
)

# Import PaymentMethod from payments module (for API parity with PasaporteWorkflow)
from ...payments.models.payment import PaymentMethod


class LicenseClass(str, Enum):
    """Driving license classes."""
    A = "A"       # Motorcycles
    B = "B"       # Light vehicles up to 3.5T
    B_PLUS = "B+"  # Light vehicles with trailer
    C = "C"       # Heavy vehicles > 3.5T
    D = "D"       # Buses > 9 seats
    E = "E"       # Articulated vehicles
    F = "F"       # Special/agricultural vehicles


class ApplicantType(str, Enum):
    """Type of applicant."""
    CITIZEN_GQ = "CITIZEN_GQ"    # Citizen with DIP
    RESIDENT = "RESIDENT"        # Foreigner with NIE


class DuplicadoMotivo(str, Enum):
    """Reason for DUPLICADO request."""
    PERDIDA = "PERDIDA"      # Lost
    ROBO = "ROBO"            # Stolen
    DETERIORO = "DETERIORO"  # Damaged


class ConducirWorkflow(PredefinedWorkflow):
    """
    Driving certificate request workflow (DGT).

    AUTONOMOUS: Defines ALL logic internally, no BaseWorkflow inheritance.

    ALIGNED WITH PredefinedWorkflow architecture (v2):
    - SolicitudType.EXPEDICION: First certificate ever (NUEVO)
    - SolicitudType.RENOVACION: Certificate renewal
    - SolicitudType.DUPLICADO: Duplicate (with motivo)
    - Sub-types: CANJE, EXTENSION via allowed_sub_types

    Key features v2:
    - form_review_1: Personal data (from DIP/NIE)
    - form_review_2: Request summary data (tipo, clases, motivo)
    - form_review_3: Document verification (conditional sections)
    - Cross-validation for foreign license name matching
    - Medical certificate only for NUEVO and EXTENSION
    - NIE holders can request NUEVO (first license in GQ)

    Condition Key Convention:
    - This workflow uses "sub_type" as the primary condition key
      (e.g., {"sub_type": "CANJE"}, {"sub_type": "DUPLICADO"})
    - The ConditionEvaluator is fully dynamic and supports any key name
    - Frontend must pass "sub_type" in context for condition evaluation
    - This differs from PasaporteWorkflow which uses "solicitud_type"
    """

    # Allowed DuplicadoMotivo values
    ALLOWED_DUPLICADO_MOTIVOS = [
        DuplicadoMotivo.PERDIDA,
        DuplicadoMotivo.ROBO,
        DuplicadoMotivo.DETERIORO,
    ]

    # Sub_type to (SolicitudType, DuplicadoMotivo) mapping
    # ALIGNED WITH PasaporteWorkflow.SUBTYPE_TO_SOLICITUD_MOTIVO pattern
    SUBTYPE_TO_SOLICITUD_MOTIVO = {
        "NUEVO": (SolicitudType.EXPEDICION, None),
        "CANJE": (SolicitudType.EXPEDICION, None),  # Treat as new GQ license
        "RENOVACION": (SolicitudType.RENOVACION, None),
        "DUPLICADO": (SolicitudType.DUPLICADO, None),  # Motivo set separately
        "EXTENSION": (SolicitudType.RENOVACION, None),  # Extension of existing
    }

    # Reverse mapping: (SolicitudType, DuplicadoMotivo) -> sub_type
    # Note: EXPEDICION → NUEVO (default), CANJE requires applicant_type=RESIDENT context
    # Note: RENOVACION → RENOVACION (default), EXTENSION requires context.sub_type
    SOLICITUD_MOTIVO_TO_SUBTYPE = {
        (SolicitudType.EXPEDICION, None): "NUEVO",
        (SolicitudType.RENOVACION, None): "RENOVACION",
        (SolicitudType.DUPLICADO, None): "DUPLICADO",
        (SolicitudType.DUPLICADO, DuplicadoMotivo.PERDIDA): "DUPLICADO",
        (SolicitudType.DUPLICADO, DuplicadoMotivo.ROBO): "DUPLICADO",
        (SolicitudType.DUPLICADO, DuplicadoMotivo.DETERIORO): "DUPLICADO",
    }

    # Legacy alias for backwards compatibility
    SUBTYPE_MAPPING = SUBTYPE_TO_SOLICITUD_MOTIVO

    # Fixed tariffs (XAF)
    TARIFFS = {
        "NUEVO": 30000,       # Includes exam fees
        "CANJE": 35000,       # Foreign license conversion
        "RENOVACION": 25000,  # Standard renewal
        "DUPLICADO": 20000,   # Replacement
        "EXTENSION": 15000    # Per additional class
    }

    # Age requirements by license class
    MIN_AGE = {
        "A": 18,
        "B": 18,
        "B+": 18,
        "C": 21,
        "D": 21,
        "E": 21,
        "F": 18
    }

    # For backwards compatibility with existing code
    @property
    def allowed_sub_types(self) -> List[str]:
        """Legacy: list of sub_type strings."""
        return list(self.SUBTYPE_TO_SOLICITUD_MOTIVO.keys())

    # === Configuration (PredefinedWorkflow required properties) ===

    def get_all_workflow_codes(self) -> List[WorkflowCode]:
        """All workflow codes this class handles (for engine registration)."""
        return [
            WorkflowCode.CONDUCIR_NUEVO,
            WorkflowCode.CONDUCIR_CANJE,
            WorkflowCode.CONDUCIR_RENOVACION,
            WorkflowCode.CONDUCIR_DUPLICADO,
            WorkflowCode.CONDUCIR_EXTENSION,
        ]

    @property
    def workflow_code(self) -> WorkflowCode:
        return WorkflowCode.CONDUCIR_NUEVO  # Base code, variant determined by sub_type

    @property
    def category(self) -> WorkflowCategory:
        return WorkflowCategory.CONDUCCION

    @property
    def entity_code(self) -> EntityCode:
        return EntityCode.DGT

    @property
    def service_name_es(self) -> str:
        return "Solicitud de Certificado para Conducir"

    def get_subtype_display_names(self) -> Dict[str, str]:
        return {
            "CONDUCIR_NUEVO": "Licencia de Conducir - Nueva",
            "CONDUCIR_CANJE": "Licencia de Conducir - Canje",
            "CONDUCIR_RENOVACION": "Licencia de Conducir - Renovación",
            "CONDUCIR_DUPLICADO": "Licencia de Conducir - Duplicado",
            "CONDUCIR_EXTENSION": "Licencia de Conducir - Extensión",
        }

    @property
    def allowed_solicitud_types(self) -> List[SolicitudType]:
        return [
            SolicitudType.EXPEDICION,   # NUEVO
            SolicitudType.RENOVACION,   # RENOVACION
            SolicitudType.DUPLICADO,    # DUPLICADO
        ]

    @property
    def requires_appointment(self) -> bool:
        return True  # For exam (NUEVO) or document retrieval

    @property
    def menu_icon(self) -> str:
        return "Car"

    @property
    def requires_agent_review(self) -> bool:
        return True

    @property
    def requires_nota_ingreso(self) -> bool:
        return False  # Direct payment via Mobile Money

    # === Workflow Setup ===

    def _setup_workflow(self) -> None:
        """
        Setup complete driving certificate workflow.

        Steps:
        0. select_type - Type selection (NUEVO/CANJE/RENOVACION/DUPLICADO/EXTENSION)
        1. select_applicant_type - Applicant type (CITIZEN_GQ/RESIDENT)
        2. select_classes - License class selection
        3. select_motivo - Motivo for DUPLICADO (conditional)
        4. upload_documents - All documents on one page
        5. form_review_1 - Personal data verification (datos personales)
        6. form_review_2 - Request summary (tipo solicitud, clases, motivo)
        7. form_review_3 - Document verification (certificado actual, permiso extranjero, aptitud)
        8. payment - Mobile Money payment
        9. appointment - Exam scheduling (for NUEVO) or pickup
        10. confirmation - Final summary
        """

        # === Step 0: Type Selection ===
        self.add_step(WorkflowStep(
            step_number=0,
            step_id="select_type",
            step_type=StepType.SELECTION,
            title_es="Tipo de Solicitud",
            description_es="Seleccione el tipo de trámite de certificado para conducir",
            config={
                "selection_type": "sub_type",
                "options": [
                    {
                        "value": "NUEVO",
                        "label_es": "Primer Certificado",
                        "description_es": "Solicito mi primer certificado para conducir (requiere examen)",
                        "tariff": 30000,
                        "icon": "license-new"
                    },
                    {
                        "value": "CANJE",
                        "label_es": "Canje de Permiso Extranjero",
                        "description_es": "Convierto mi permiso de conducir extranjero",
                        "tariff": 35000,
                        "icon": "exchange",
                        "condition": {"applicant_type": "RESIDENT"}
                    },
                    {
                        "value": "RENOVACION",
                        "label_es": "Renovación",
                        "description_es": "Renuevo mi certificado vencido o por vencer",
                        "tariff": 25000,
                        "icon": "refresh"
                    },
                    {
                        "value": "DUPLICADO",
                        "label_es": "Duplicado",
                        "description_es": "Solicito un duplicado (pérdida, robo o deterioro)",
                        "tariff": 20000,
                        "icon": "copy"
                    },
                    {
                        "value": "EXTENSION",
                        "label_es": "Extensión de Clases",
                        "description_es": "Añado nuevas clases a mi certificado actual",
                        "tariff": 15000,
                        "icon": "plus-circle"
                    }
                ]
            }
        ))

        # === Step 1: Applicant Type Selection ===
        self.add_step(WorkflowStep(
            step_number=1,
            step_id="select_applicant_type",
            step_type=StepType.SELECTION,
            title_es="Tipo de Solicitante",
            description_es="Indique su tipo de documento de identidad",
            config={
                "selection_type": "applicant_type",
                "options": [
                    {
                        "value": ApplicantType.CITIZEN_GQ.value,
                        "label_es": "Ciudadano Ecuatoguineano (DIP)",
                        "description_es": "Tengo Documento de Identidad Personal (DIP)",
                        "icon": "id-card"
                    },
                    {
                        "value": ApplicantType.RESIDENT.value,
                        "label_es": "Residente Extranjero (NIE)",
                        "description_es": "Tengo Permiso de Residencia (NIE)",
                        "icon": "passport"
                    }
                ]
            }
        ))

        # === Step 2: License Class Selection ===
        self.add_step(WorkflowStep(
            step_number=2,
            step_id="select_classes",
            step_type=StepType.CUSTOM,
            title_es="Clase(s) de Permiso",
            description_es="Seleccione las clases de permiso que desea obtener",
            config={
                "type": "multi_selection",
                "max_selection": 3,
                "options": [
                    {"id": "A", "label_es": "A - Motocicletas", "min_age": 18},
                    {"id": "B", "label_es": "B - Vehículos ligeros", "min_age": 18},
                    {"id": "B+", "label_es": "B+ - Vehículos ligeros con remolque", "min_age": 18},
                    {"id": "C", "label_es": "C - Camiones", "min_age": 21},
                    {"id": "D", "label_es": "D - Autobuses", "min_age": 21},
                    {"id": "E", "label_es": "E - Vehículos articulados", "min_age": 21},
                    {"id": "F", "label_es": "F - Vehículos especiales", "min_age": 18}
                ]
            }
        ))

        # === Step 3: Motivo Selection (only for DUPLICADO) ===
        self.add_step(WorkflowStep(
            step_number=3,
            step_id="select_motivo",
            step_type=StepType.SELECTION,
            title_es="Motivo del Duplicado",
            description_es="Indique el motivo por el que necesita un duplicado",
            config={
                "selection_type": "motivo",
                "condition": {"sub_type": "DUPLICADO"},
                "options": [
                    {
                        "value": DuplicadoMotivo.PERDIDA.value,
                        "label_es": "Pérdida",
                        "description_es": "Perdí mi certificado (requiere denuncia policial)",
                        "icon": "search-x"
                    },
                    {
                        "value": DuplicadoMotivo.ROBO.value,
                        "label_es": "Robo",
                        "description_es": "Me robaron mi certificado (requiere denuncia policial)",
                        "icon": "shield-alert"
                    },
                    {
                        "value": DuplicadoMotivo.DETERIORO.value,
                        "label_es": "Deterioro",
                        "description_es": "Mi certificado está dañado",
                        "icon": "file-warning"
                    }
                ]
            }
        ))

        # === Step 4: Document Upload (ALL documents on ONE page) ===
        self.add_step(WorkflowStep(
            step_number=4,
            step_id="upload_documents",
            step_type=StepType.DOCUMENT_UPLOAD,
            title_es="Documentos Requeridos",
            description_es="Cargue todos los documentos necesarios para su solicitud",
            config={
                "dynamic_documents": True,  # Frontend calls get_document_requirements
                "single_page": True,  # All documents on one page
                "includes_photo": True  # Photo is part of this step
            }
        ))

        # === Step 5: Form Review 1 - Datos Personales ===
        # Single section (aligned with Pasaporte pattern — no split Identificación/Datos)
        self.add_step(WorkflowStep(
            step_number=5,
            step_id="form_review_1",
            step_type=StepType.FORM_REVIEW,
            title_es="Verificar Datos (1/3)",
            description_es="Verifique sus datos personales extraídos del documento de identidad",
            config={
                "form_page": 1,
                "max_sections": 1,
                "sections": [
                    {
                        "id": "datos_personales",
                        "title_es": "Datos Personales",
                        "condition": None,  # Always visible
                        "fields": [
                            {"key": "tipo_identificacion", "label_es": "Tipo de Identificación", "type": "select", "options": ["DIP", "NIE"], "required": True, "readonly": True},
                            {"key": "numero_identificacion", "label_es": "Número de Identificación", "type": "text", "required": True, "readonly": False},
                            {"key": "apellidos", "label_es": "Apellidos", "type": "text", "required": True, "readonly": False},
                            {"key": "nombres", "label_es": "Nombres", "type": "text", "required": True, "readonly": False},
                            {"key": "fecha_nacimiento", "label_es": "Fecha de Nacimiento", "type": "date", "required": True, "readonly": False},
                            {"key": "nacionalidad", "label_es": "Nacionalidad", "type": "text", "required": True, "readonly": False},
                            {"key": "domicilio", "label_es": "Domicilio", "type": "text", "required": False, "readonly": False},
                        ]
                    }
                ]
            }
        ))

        # === Step 6: Form Review 2 - Resumen Solicitud ===
        self.add_step(WorkflowStep(
            step_number=6,
            step_id="form_review_2",
            step_type=StepType.FORM_REVIEW,
            title_es="Verificar Datos (2/3)",
            description_es="Verifique los datos de su solicitud",
            config={
                "form_page": 2,
                "max_sections": 1,
                "sections": [
                    {
                        "id": "solicitud",
                        "title_es": "Datos de la Solicitud",
                        "condition": None,  # Always visible
                        "fields": [
                            {
                                "key": "tipo_solicitud",
                                "label_es": "Tipo de Solicitud",
                                "type": "text",
                                "required": True,
                                "readonly": True
                            },
                            {
                                "key": "clases_solicitadas",
                                "label_es": "Clase(s) de Permiso Solicitadas",
                                "type": "text",
                                "required": True,
                                "readonly": True
                            },
                            {
                                "key": "motivo_duplicado",
                                "label_es": "Motivo del Duplicado",
                                "type": "text",
                                "required": True,
                                "readonly": True,
                                "condition": {"sub_type": "DUPLICADO"}
                            }
                        ]
                    }
                ]
            }
        ))

        # === Step 7: Form Review 3 - Verificación de Documentos ===
        self.add_step(WorkflowStep(
            step_number=7,
            step_id="form_review_3",
            step_type=StepType.FORM_REVIEW,
            title_es="Verificar Datos (3/3)",
            description_es="Verifique los datos extraídos de sus documentos",
            config={
                "form_page": 3,
                "max_sections": 3,
                "sections": [
                    # Section 1: Current certificate (RENOVACION/EXTENSION only)
                    {
                        "id": "certificado_actual",
                        "title_es": "Certificado para Conducir Actual",
                        "condition": {
                            "OR": [
                                {"sub_type": "RENOVACION"},
                                {"sub_type": "EXTENSION"}
                            ]
                        },
                        "fields": [
                            {
                                "key": "cert_reg_numero",
                                "label_es": "Número de Registro",
                                "type": "text",
                                "required": True,
                                "readonly": True
                            },
                            {
                                "key": "cert_clases_actuales",
                                "label_es": "Clases Actuales",
                                "type": "text",
                                "required": True,
                                "readonly": True
                            },
                            {
                                "key": "cert_fecha_expedicion",
                                "label_es": "Fecha de Expedición",
                                "type": "date",
                                "required": True,
                                "readonly": True
                            },
                            {
                                "key": "cert_valido_hasta",
                                "label_es": "Válido Hasta",
                                "type": "date",
                                "required": True,
                                "readonly": True
                            },
                            {
                                "key": "cert_antiguedad_desde",
                                "label_es": "Antigüedad Desde",
                                "type": "date",
                                "required": False,
                                "readonly": True
                            }
                        ]
                    },
                    # Section 2: Foreign license (CANJE only)
                    {
                        "id": "permiso_extranjero",
                        "title_es": "Permiso de Conducir Extranjero",
                        "condition": {"sub_type": "CANJE"},
                        "fields": [
                            {
                                "key": "perm_ext_pais_emision",
                                "label_es": "País de Emisión",
                                "type": "text",
                                "required": True,
                                "readonly": False,
                                "placeholder_es": "Ej: España, Francia, Camerún..."
                            },
                            {
                                "key": "perm_ext_numero",
                                "label_es": "Número de Permiso",
                                "type": "text",
                                "required": True,
                                "readonly": False
                            },
                            {
                                "key": "perm_ext_apellidos",
                                "label_es": "Apellidos (según permiso)",
                                "type": "text",
                                "required": True,
                                "readonly": False
                            },
                            {
                                "key": "perm_ext_nombres",
                                "label_es": "Nombres (según permiso)",
                                "type": "text",
                                "required": True,
                                "readonly": False
                            },
                            {
                                "key": "perm_ext_clases",
                                "label_es": "Clases del Permiso",
                                "type": "text",
                                "required": True,
                                "readonly": False,
                                "placeholder_es": "Ej: B, A+B, C..."
                            },
                            {
                                "key": "perm_ext_fecha_expedicion",
                                "label_es": "Fecha de Expedición",
                                "type": "date",
                                "required": True,
                                "readonly": False
                            },
                            {
                                "key": "perm_ext_fecha_expiracion",
                                "label_es": "Fecha de Expiración",
                                "type": "date",
                                "required": True,
                                "readonly": False
                            }
                        ]
                    },
                    # Section 3: Medical fitness (NUEVO/EXTENSION only)
                    {
                        "id": "aptitud_medica",
                        "title_es": "Aptitud Médica",
                        "condition": {
                            "OR": [
                                {"sub_type": "NUEVO"},
                                {"sub_type": "EXTENSION"}
                            ]
                        },
                        "fields": [
                            {
                                "key": "certificado_medico_fecha",
                                "label_es": "Fecha del Certificado Médico",
                                "type": "date",
                                "required": True,
                                "readonly": False,
                                "pdf_exclude": True
                            },
                            {
                                "key": "entidad_medica_nombre",
                                "label_es": "Nombre del Centro Médico",
                                "type": "text",
                                "required": True,
                                "readonly": False,
                                "placeholder_es": "Ej: Hospital General de Malabo, Clínica Santa Isabel...",
                                "pdf_exclude": True
                            },
                            {
                                "key": "medico_nombre",
                                "label_es": "Nombre del Médico (opcional)",
                                "type": "text",
                                "required": False,
                                "readonly": False,
                                "pdf_exclude": True
                            }
                        ]
                    }
                ]
            }
        ))

        # === Step 8: Appointment (BEFORE Payment) ===
        self.add_step(WorkflowStep(
            step_number=8,
            step_id="appointment",
            step_type=StepType.APPOINTMENT,
            title_es="Programar Cita",
            description_es="Seleccione una cita en la oficina DGT",
            config={
                "entity_via_request": True,
                "use_appointment_module": True,
                "exam_scheduling": {
                    "applies_to": ["NUEVO"],
                    "delay_min_days": 7,
                    "notification_before_days": 3,
                    "locations_from": "entity_locations"
                }
            }
        ))

        # === Step 9: Payment (AFTER Appointment) ===
        self.add_step(WorkflowStep(
            step_number=9,
            step_id="payment",
            step_type=StepType.PAYMENT,
            title_es="Pago de Tasas",
            description_es="Realice el pago mediante Mobile Money",
            config={
                "currency": "XAF",
                "show_breakdown": True,
                "dynamic_tariff": True,
            }
        ))

        # === Step 10: Confirmation ===
        self.add_step(WorkflowStep(
            step_number=10,
            step_id="confirmation",
            step_type=StepType.CONFIRMATION,
            title_es="Confirmación",
            description_es="Su solicitud ha sido completada",
            config={
                "show_summary": True,
                "show_appointment": True,
                "show_payment": True,
                "allow_download_receipt": True,
                "next_steps_es": [
                    "Preséntese en la oficina DGT en la fecha y hora indicadas",
                    "Lleve los documentos originales para verificación",
                    "Para NUEVO: el examen teórico se realizará en la cita programada"
                ]
            }
        ))

        # === Setup Tariffs ===
        self._setup_tariffs()

    def _setup_tariffs(self) -> None:
        """
        Setup tariff configuration.

        Base Tariffs (XAF):
        - NUEVO: 30,000 (includes exam fees)
        - CANJE: 35,000 (foreign license conversion)
        - RENOVACION: 25,000 (standard renewal)
        - DUPLICADO: 20,000 (replacement)
        - EXTENSION: 15,000 (per additional class)
        """
        self.set_tariff_config(TariffConfig(
            tariff_type=TariffType.FIXED,
            fixed_amounts=self.TARIFFS,
            currency="XAF",
            supplements=[]
        ))

    # === Document Requirements ===

    def get_document_requirements(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None
    ) -> List[DocumentRequirement]:
        """
        Get document requirements based on request type and applicant type.

        ALIGNED WITH PredefinedWorkflow signature.

        Document Matrix:
        | Document              | NUEVO | CANJE | RENOVACION | DUPLICADO | EXTENSION |
        |-----------------------|-------|-------|------------|-----------|-----------|
        | DIP (CITIZEN_GQ)      | ✅    | -     | ✅         | ✅        | ✅        |
        | NIE (RESIDENT)        | ✅    | ✅    | ✅         | ✅        | ✅        |
        | Certificado Actual    | -     | -     | ✅         | -         | ✅        |
        | Permiso Extranjero    | -     | ✅    | -          | -         | -         |
        | Denuncia              | -     | -     | -          | ⚠️*       | -         |
        | Certificado Médico    | ✅    | ❌    | ❌         | ❌        | ✅        |
        | Foto Carnet           | ✅    | ✅    | ✅         | ✅        | ✅        |

        *Denuncia required only if motivo = PERDIDA or ROBO
        """
        requirements = []

        # Get sub_type and applicant_type from context
        sub_type = None
        applicant_type = None
        duplicado_motivo = None

        if context:
            sub_type = context.sub_type
            applicant_type = context.form_data.get("applicant_type") if context.form_data else None
            duplicado_motivo = context.motivo

        # Map solicitud_type to sub_type if not provided
        if not sub_type:
            if solicitud_type == SolicitudType.EXPEDICION:
                sub_type = "NUEVO"
            elif solicitud_type == SolicitudType.RENOVACION:
                sub_type = "RENOVACION"
            elif solicitud_type == SolicitudType.DUPLICADO:
                sub_type = "DUPLICADO"

        # === Identity Document - based on applicant type ===
        # DIP for citizens
        requirements.append(DocumentRequirement(
            document_code="dip",
            document_name_es="DIP (Ciudadanos GQ)",
            schema_key="DIP_GQ_V2",
            is_required=True,
            display_order=1,
            condition_type=DocumentConditionType.IS_NATIONAL,
            instructions_es="Escanee ambas caras de su DIP vigente",
            faces_required=["recto", "verso"]
        ))

        # Permiso Residencia for foreigners
        requirements.append(DocumentRequirement(
            document_code="permiso_residencia",
            document_name_es="Permiso de Residencia (Extranjeros)",
            schema_key="PERMISO_RESIDENCIA_GQ_V1",
            is_required=True,
            display_order=1,
            condition_type=DocumentConditionType.IS_FOREIGN,
            instructions_es="Escanee su Permiso de Residencia vigente",
            faces_required=["recto", "verso"]
        ))

        # === Type-specific documents ===

        # Current certificate for RENOVACION/EXTENSION
        if sub_type in ["RENOVACION", "EXTENSION"]:
            requirements.append(DocumentRequirement(
                document_code="certificado_actual",
                document_name_es="Certificado para Conducir Actual",
                schema_key="CERTIFICADO_CONDUCIR_GQ_V1",
                is_required=True,
                display_order=2,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["RENOVACION", "EXTENSION"]},
                instructions_es="Escanee su certificado para conducir actual"
            ))

        # Foreign license for CANJE
        if sub_type == "CANJE":
            requirements.append(DocumentRequirement(
                document_code="permiso_extranjero",
                document_name_es="Permiso de Conducir Extranjero",
                is_required=True,
                display_order=2,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["CANJE"]},
                instructions_es="Escanee ambas caras de su permiso de conducir extranjero vigente",
                faces_required=["recto", "verso"],
                config={"best_effort_extraction": True}  # Gemini multilingual extraction, fields editable
            ))

        # Police report for DUPLICADO (loss/theft only)
        if sub_type == "DUPLICADO" and duplicado_motivo in ["PERDIDA", "ROBO"]:
            requirements.append(DocumentRequirement(
                document_code="denuncia",
                document_name_es="Denuncia Policial",
                is_required=True,
                display_order=3,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"motivo_in": ["PERDIDA", "ROBO"]},
                instructions_es="Denuncia de pérdida o robo ante la Policía Nacional"
            ))

        # Medical certificate - ONLY for NUEVO and EXTENSION
        # Optional: citizen may not have it yet at online request time
        if sub_type in ["NUEVO", "EXTENSION"]:
            requirements.append(DocumentRequirement(
                document_code="certificado_medico",
                document_name_es="Certificado Médico de Aptitud",
                schema_key="CERTIFICADO_MEDICO_GQ_V1",
                is_required=False,
                display_order=4,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["NUEVO", "EXTENSION"]},
                instructions_es="Certificado médico reciente (menos de 3 meses) que acredite aptitud para conducir",
                config={
                    "required_tipo_certificado": "APTITUD",
                    "required_resultado": ["SANO", "APTO"]
                }
            ))

        # Photo always required (x1)
        requirements.append(DocumentRequirement(
            document_code="photo_carnet",
            document_name_es="Fotografía tipo carnet",
            is_required=True,
            display_order=10,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es="1 foto de 35x45mm, fondo blanco, rostro visible",
            accepted_formats=["jpg", "jpeg", "png"],
            config={"quantity": 1}
        ))

        return requirements

    def get_document_requirements_legacy(
        self,
        sub_type: str,
        context: Optional[WorkflowContext] = None
    ) -> List[DocumentRequirement]:
        """
        Legacy method for backwards compatibility.
        Converts sub_type string to SolicitudType + DuplicadoMotivo.

        ALIGNED WITH PasaporteWorkflow.get_document_requirements_legacy pattern.
        """
        solicitud_motivo = self.SUBTYPE_TO_SOLICITUD_MOTIVO.get(sub_type)
        if solicitud_motivo:
            solicitud_type, _ = solicitud_motivo
            # For DUPLICADO, get motivo from context
            motivo = context.motivo if context else None
            return self.get_document_requirements(solicitud_type, motivo, context)
        # Default to EXPEDICION if unknown sub_type
        return self.get_document_requirements(SolicitudType.EXPEDICION, None, context)

    # === Form Field Mapping ===

    def get_form_mapping(self, context: Optional[WorkflowContext] = None) -> Dict[str, str]:
        """
        Map extracted data fields to form fields.

        ALIGNED WITH JSON SCHEMAS:
        - dip_gq.json: documento.numero_dip, titular.domiciliacion
        - permiso_residencia_gq.json: documento.numero_nie, titular.direccion_gq
        - certificado_conducir_gq.json: documento.reg_numero, permiso.clases_permiso
        """
        # Determine applicant type from context
        applicant_type = None
        if context and context.form_data:
            applicant_type = context.form_data.get("applicant_type")

        # Resolve tipo_identificacion from applicant_type selection
        tipo_id = "NIE" if applicant_type == ApplicantType.RESIDENT.value else "DIP"

        # Base mapping - common fields
        mapping = {
            # === Identification ===
            "tipo_identificacion": f"_literal:{tipo_id}",

            # === From DIP (CITIZEN_GQ) ===
            "numero_identificacion": "dip.documento.numero_dip",
            "apellidos": "dip.titular.apellidos",
            "nombres": "dip.titular.nombres",
            "fecha_nacimiento": "dip.titular.fecha_nacimiento",
            "nacionalidad": "dip.titular.nacionalidad",
            "domicilio": "dip.titular.domiciliacion",

            # === Request data (from wizard selections) ===
            "tipo_solicitud": "_form:sub_type",
            "clases_solicitadas": "_form:select_classes",
            "motivo_duplicado": "_form:motivo",

            # === From current certificate (RENOVACION/EXTENSION) ===
            "cert_reg_numero": "certificado_actual.documento.reg_numero",
            "cert_clases_actuales": "certificado_actual.permiso.clases_permiso",
            "cert_fecha_expedicion": "certificado_actual.documento.fecha_expedicion",
            "cert_valido_hasta": "certificado_actual.documento.valido_hasta",
            "cert_antiguedad_desde": "certificado_actual.permiso.antiguedad_desde",

            # === From medical certificate (NUEVO/EXTENSION) ===
            "certificado_medico_fecha": "certificado_medico.autenticacion.fecha_certificado",
            "entidad_medica_nombre": "certificado_medico.centro_medico.nombre_centro",
            "medico_nombre": "certificado_medico.medico_principal.nombre_medico",

            # === From foreign license (CANJE) - best-effort OCR extraction ===
            "perm_ext_pais_emision": "permiso_extranjero.documento.pais_emision",
            "perm_ext_apellidos": "permiso_extranjero.titular.apellidos",
            "perm_ext_nombres": "permiso_extranjero.titular.nombres",
            "perm_ext_numero": "permiso_extranjero.documento.numero",
            "perm_ext_clases": "permiso_extranjero.permiso.clases_permiso",
            "perm_ext_fecha_expedicion": "permiso_extranjero.documento.fecha_expedicion",
            "perm_ext_fecha_expiracion": "permiso_extranjero.documento.fecha_expiracion",
        }

        # If RESIDENT, override with permiso_residencia mappings
        if applicant_type == ApplicantType.RESIDENT.value:
            mapping.update({
                "numero_identificacion": "permiso_residencia.documento.numero_nie",
                "apellidos": "permiso_residencia.titular.apellidos",
                "nombres": "permiso_residencia.titular.nombres",
                "fecha_nacimiento": "permiso_residencia.titular.fecha_nacimiento",
                "nacionalidad": "permiso_residencia.titular.nacionalidad",
                "domicilio": "permiso_residencia.titular.direccion_gq",
            })

        return mapping

    # === Tariff Resolution (overrides parent) ===

    def _resolve_sub_type(
        self,
        solicitud_type: SolicitudType,
        context: Optional[WorkflowContext] = None
    ) -> str:
        """
        Resolve sub_type from context or solicitud_type.

        Priority: context.sub_type > solicitud_type fallback.
        """
        if context:
            sub_type = context.sub_type
            if sub_type and sub_type in self.SUBTYPE_TO_SOLICITUD_MOTIVO:
                return sub_type

        # Fallback: solicitud_type → default sub_type
        fallback = {
            SolicitudType.EXPEDICION: "NUEVO",
            SolicitudType.RENOVACION: "RENOVACION",
            SolicitudType.DUPLICADO: "DUPLICADO",
        }
        return fallback.get(solicitud_type, "NUEVO")

    def get_tariff(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None
    ) -> int:
        """
        Get tariff amount by resolving sub_type from context.

        Overrides parent because TARIFFS uses sub_type keys (NUEVO, CANJE, etc.)
        while parent's get_tariff uses solicitud_type keys (EXPEDICION, etc.).

        For EXTENSION: 15,000 XAF × number of new classes requested.
        """
        sub_type = self._resolve_sub_type(solicitud_type, context)

        # EXTENSION: price per new class
        if sub_type == "EXTENSION" and context and context.form_data:
            clases_solicitadas = context.form_data.get("select_classes", [])
            clases_actuales = context.form_data.get("clases_actuales", [])
            if isinstance(clases_solicitadas, str):
                clases_solicitadas = [c.strip() for c in clases_solicitadas.split(",")]
            if isinstance(clases_actuales, str):
                clases_actuales = [c.strip() for c in clases_actuales.split(",")]
            nuevas_clases = set(clases_solicitadas) - set(clases_actuales)
            if nuevas_clases:
                return len(nuevas_clases) * self.TARIFFS["EXTENSION"]

        return self.TARIFFS.get(sub_type, 30000)

    # === Utility Methods ===

    def requires_exam(self, sub_type: str) -> bool:
        """Check if this request type requires an exam."""
        return sub_type == "NUEVO"

    def get_exam_config(self) -> Dict[str, Any]:
        """Get exam configuration for NUEVO requests."""
        return {
            "required": True,
            "types": {
                "teorico": {
                    "duration_minutes": 45,
                    "questions": 40,
                    "score_minimum_percent": 80,
                    "languages": ["es", "fr"]
                },
                "practico": {
                    "duration_minutes": 30,
                    "prerequisite": "Examen teórico aprobado"
                }
            },
            "scheduling": {
                "delay_min_days": 7,
                "notification_days_before": 3,
                "locations_from": "entity_locations"
            }
        }

    def validate_request_type_eligibility(
        self,
        sub_type: str,
        applicant_type: str
    ) -> bool:
        """
        Validate if applicant type can request this sub_type.

        Rules:
        - CANJE is only for foreigners (RESIDENT) - they have a foreign license to convert
        - All other types available to both CITIZEN_GQ and RESIDENT
        """
        if sub_type == "CANJE" and applicant_type == ApplicantType.CITIZEN_GQ.value:
            return False
        return True

    def validate_class_eligibility(
        self,
        requested_classes: List[str],
        birth_date: str
    ) -> List[Dict[str, Any]]:
        """
        Validate if applicant is eligible for requested license classes.

        Returns list of validation errors (empty if all valid).
        """
        from datetime import datetime, date

        errors = []

        # Calculate age
        try:
            if isinstance(birth_date, str):
                birth = datetime.strptime(birth_date, "%Y-%m-%d").date()
            else:
                birth = birth_date

            today = date.today()
            age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        except (ValueError, TypeError):
            return [{"error": "Invalid birth date", "classes": requested_classes}]

        # Check each class and build suggestions
        eligible_classes = []
        for class_id, min_class_age in self.MIN_AGE.items():
            if age >= min_class_age:
                eligible_classes.append(class_id)

        for cls in requested_classes:
            min_age = self.MIN_AGE.get(cls, 18)
            if age < min_age:
                # Build suggestion message
                years_to_wait = min_age - age
                suggestion = ""
                if eligible_classes:
                    available = [c for c in eligible_classes if c not in requested_classes]
                    if available:
                        suggestion = f" Puede solicitar las clases: {', '.join(sorted(available))}."
                    else:
                        suggestion = f" Las clases {', '.join(sorted(eligible_classes))} están disponibles para su edad."

                errors.append({
                    "class": cls,
                    "min_age": min_age,
                    "current_age": age,
                    "years_to_wait": years_to_wait,
                    "eligible_classes": eligible_classes,
                    "error_es": f"Debe tener al menos {min_age} años para la clase {cls}. Usted tiene {age} años.{suggestion}",
                    "suggestion_es": f"Espere {years_to_wait} año(s) o seleccione otra clase." if years_to_wait > 0 else None
                })

        return errors

    def calculate_tariff(self, context: WorkflowContext, value: float = None) -> int:
        """
        Calculate tariff based on request type. Delegates to get_tariff().

        For EXTENSION: 15,000 XAF per new class.
        """
        solicitud_type, _ = self.SUBTYPE_TO_SOLICITUD_MOTIVO.get(
            context.sub_type, (SolicitudType.EXPEDICION, None)
        )
        return self.get_tariff(solicitud_type, context=context)

    # === Step Validation Override ===

    def validate_step(
        self,
        step_number: int,
        context: WorkflowContext
    ) -> List[ValidationResult]:
        """
        Validate a specific step with age eligibility checks.

        Overrides PredefinedWorkflow.validate_step to add:
        - Age validation for requested license classes
        - Blocking errors if applicant is too young

        Called by workflow_engine._execute_validation_step().
        """
        # Call parent validation first
        results = super().validate_step(step_number, context)

        # Add age validation after form_review_1 (when we have birth date)
        # or on select_classes step
        step = self.get_step(step_number)
        if not step:
            return results

        # Validate age eligibility when:
        # - After form_review_1 (step 5) - we have extracted birth date
        # - On form_review_2 (step 6) - before payment
        # - On select_classes (step 2) if birth date already known
        if step.step_id in ["form_review_1", "form_review_2", "form_review_3", "select_classes"]:
            age_errors = self._validate_age_eligibility(context)
            results.extend(age_errors)

            # EXTENSION: verify requested classes are not already on current certificate
            if context.sub_type == "EXTENSION":
                results.extend(self._validate_extension_new_class(context))

        return results

    def _validate_extension_new_class(
        self,
        context: WorkflowContext
    ) -> List[ValidationResult]:
        """Verify that requested classes are not already on the current certificate."""
        results = []
        clases_solicitadas = context.form_data.get("select_classes", [])
        if isinstance(clases_solicitadas, str):
            clases_solicitadas = [c.strip() for c in clases_solicitadas.split(",")]
        if not clases_solicitadas:
            return results

        # Get existing classes from extracted certificate data
        cert_data = context.extracted_data.get("certificado_actual", {})
        clases_existentes = cert_data.get("permiso", {}).get("clases_permiso", [])
        if not clases_existentes:
            return results

        # Check for duplicates
        duplicadas = [c for c in clases_solicitadas if c in clases_existentes]
        if duplicadas:
            results.append(ValidationResult(
                is_valid=False,
                rule_id="extension_clase_nueva",
                severity="error",
                message_es=(
                    f"Ya tiene la(s) clase(s) {', '.join(duplicadas)} "
                    f"en su certificado actual."
                ),
                field_name="clases_solicitadas"
            ))
        return results

    def _validate_age_eligibility(
        self,
        context: WorkflowContext
    ) -> List[ValidationResult]:
        """
        Validate age eligibility for requested license classes.

        Extracts birth date from form_data (populated by document extraction)
        and validates against MIN_AGE requirements for each requested class.

        Returns list of ValidationResult with blocking errors if age < minimum.
        """
        results = []

        if not context.form_data:
            return results

        # Get birth date from extracted data
        fecha_nacimiento = context.form_data.get("fecha_nacimiento")
        if not fecha_nacimiento:
            # No birth date yet - skip validation (will be validated later)
            return results

        # Get requested classes (stored by frontend as select_classes from step_id)
        clases_solicitadas = context.form_data.get("select_classes", [])

        if not clases_solicitadas:
            return results

        # Convert to list if string
        if isinstance(clases_solicitadas, str):
            clases_solicitadas = [c.strip() for c in clases_solicitadas.split(",")]

        # Call existing validation method
        age_errors = self.validate_class_eligibility(clases_solicitadas, fecha_nacimiento)

        # Convert to ValidationResult format
        for error in age_errors:
            if "error" in error and error["error"] == "Invalid birth date":
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id="invalid_birth_date",
                    severity="error",
                    message_es="La fecha de nacimiento no es válida.",
                    field_name="fecha_nacimiento"
                ))
            else:
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id=f"edad_minima_clase_{error.get('class', 'unknown')}",
                    severity="error",
                    message_es=error.get("error_es", f"No cumple con la edad mínima requerida."),
                    field_name="clases_solicitadas"
                ))

        return results


# =============================================================================
# REGISTRATION
# =============================================================================

def register_conducir_workflow():
    """Register the driving certificate workflow with the workflow engine."""
    from ..services.workflow_engine import workflow_engine

    workflow = ConducirWorkflow()
    workflow_engine.register_workflow(workflow)


# Singleton instance
_conducir_workflow: Optional[ConducirWorkflow] = None


def get_conducir_workflow() -> ConducirWorkflow:
    """Get the singleton ConducirWorkflow instance."""
    global _conducir_workflow
    if _conducir_workflow is None:
        _conducir_workflow = ConducirWorkflow()
    return _conducir_workflow
