"""
PasaporteWorkflow v2 - Autonomous passport request workflow.

This is a PREDEFINED workflow with complete business logic.
ALIGNED WITH workflow_interface.py using SolicitudType + RenovacionMotivo.

Types (aligned with workflow_interface.py):

SolicitudType.EXPEDICION (First passport):
    - Never had a passport before
    - Requires: DIP + Certificado de Nacimiento + Foto
    - Tariff: 7,500 XAF

SolicitudType.RENOVACION with RenovacionMotivo:
    - VENCIMIENTO: Passport expired/expiring
      Requires: DIP + Pasaporte antiguo + Foto
      Tariff: 5,000 XAF

    - PERDIDA: Lost passport
      Requires: DIP + Denuncia policial + Foto
      Tariff: 10,000 XAF (includes penalty)

    - ROBO: Stolen passport
      Requires: DIP + Denuncia policial + Foto
      Tariff: 10,000 XAF (includes penalty)

    - DETERIORO: Damaged passport
      Requires: DIP + Pasaporte danado + Foto
      Tariff: 7,500 XAF

Entity: CNEDOGE (Centro Nacional de Expedicion de Documentos)
Requires: Appointment (cita) + Agent Review
"""
from typing import List, Dict, Any, Optional

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

# Import PaymentMethod from payments module
from ...payments.models.payment import PaymentMethod


class PasaporteWorkflow(PredefinedWorkflow):
    """
    Passport request workflow.

    AUTONOMOUS: Defines ALL logic internally, no BaseWorkflow inheritance.

    ALIGNED WITH workflow_interface.py:
    - SolicitudType.EXPEDICION: First passport ever
    - SolicitudType.RENOVACION with RenovacionMotivo:
      - VENCIMIENTO: Passport expired/expiring
      - PERDIDA: Lost passport
      - ROBO: Stolen passport
      - DETERIORO: Damaged passport
    """

    # Allowed motivos for RENOVACION
    ALLOWED_MOTIVOS = [
        RenovacionMotivo.VENCIMIENTO,
        RenovacionMotivo.PERDIDA,
        RenovacionMotivo.ROBO,
        RenovacionMotivo.DETERIORO,
    ]

    # Legacy sub_type mapping for backwards compatibility
    SUBTYPE_TO_SOLICITUD_MOTIVO = {
        "NUEVO": (SolicitudType.EXPEDICION, None),
        "RENOVACION": (SolicitudType.RENOVACION, RenovacionMotivo.VENCIMIENTO),
        "PERDIDA": (SolicitudType.RENOVACION, RenovacionMotivo.PERDIDA),
        "ROBO": (SolicitudType.RENOVACION, RenovacionMotivo.ROBO),
        "DETERIORO": (SolicitudType.RENOVACION, RenovacionMotivo.DETERIORO),
    }

    # Reverse mapping
    SOLICITUD_MOTIVO_TO_SUBTYPE = {
        (SolicitudType.EXPEDICION, None): "NUEVO",
        (SolicitudType.RENOVACION, RenovacionMotivo.VENCIMIENTO): "RENOVACION",
        (SolicitudType.RENOVACION, RenovacionMotivo.PERDIDA): "PERDIDA",
        (SolicitudType.RENOVACION, RenovacionMotivo.ROBO): "ROBO",
        (SolicitudType.RENOVACION, RenovacionMotivo.DETERIORO): "DETERIORO",
    }

    # For backwards compatibility with existing code
    @property
    def allowed_sub_types(self) -> List[str]:
        """Legacy: list of sub_type strings."""
        return list(self.SUBTYPE_TO_SOLICITUD_MOTIVO.keys())

    # === Configuration ===

    def get_all_workflow_codes(self) -> List[WorkflowCode]:
        """All workflow codes this class handles (for engine registration)."""
        return [
            WorkflowCode.PASAPORTE_NUEVO,
            WorkflowCode.PASAPORTE_RENOVACION,
            WorkflowCode.PASAPORTE_PERDIDA,
            WorkflowCode.PASAPORTE_ROBO,
            WorkflowCode.PASAPORTE_DETERIORO,
        ]

    @property
    def workflow_code(self) -> WorkflowCode:
        return WorkflowCode.PASAPORTE_NUEVO  # Base code, variant determined by sub_type

    @property
    def category(self) -> WorkflowCategory:
        return WorkflowCategory.IDENTIDAD

    @property
    def entity_code(self) -> EntityCode:
        return EntityCode.CNEDOGE

    @property
    def service_name_es(self) -> str:
        return "Solicitud de Pasaporte"

    def get_subtype_display_names(self) -> Dict[str, str]:
        return {
            "PASAPORTE_NUEVO": "Pasaporte - Primera Expedición",
            "PASAPORTE_RENOVACION": "Pasaporte - Renovación por Vencimiento",
            "PASAPORTE_PERDIDA": "Pasaporte - Renovación por Pérdida",
            "PASAPORTE_ROBO": "Pasaporte - Renovación por Robo",
            "PASAPORTE_DETERIORO": "Pasaporte - Renovación por Deterioro",
        }

    @property
    def allowed_solicitud_types(self) -> List[SolicitudType]:
        # We use EXPEDICION and RENOVACION for generic typing
        # but actual sub_type is determined by ALLOWED_SUB_TYPES
        return [SolicitudType.EXPEDICION, SolicitudType.RENOVACION]

    @property
    def requires_appointment(self) -> bool:
        return True  # Passport requires cita at CNEDOGE

    @property
    def menu_icon(self) -> str:
        return "Plane"

    @property
    def requires_agent_review(self) -> bool:
        return True

    @property
    def requires_nota_ingreso(self) -> bool:
        return False  # Direct payment via Mobile Money

    # === Workflow Setup ===

    def _setup_workflow(self) -> None:
        """
        Setup complete passport workflow.

        12 steps (4 conditional), all step_numbers unique and sequential.

        Steps:
        0.  is_minor                  - SELECTION: Adulte ou mineur
        1.  select_type               - SELECTION: EXPEDICION ou RENOVACION
        2.  select_motivo             - SELECTION: Motivo RENOVACION [condition: solicitud_type=RENOVACION]
        3.  representantes_legales    - SELECTION: 1 ou 2 representants [condition: is_minor=True]
        4.  select_motivo_rep_unico   - SELECTION: Motivo rep. unique [condition: is_minor+representante_unico]
        5.  upload_documents          - DOCUMENT_UPLOAD: Tous documents sur une page
        6.  form_review_1             - FORM_REVIEW: Datos Personales + Domicilio
        7.  form_review_2             - FORM_REVIEW: Filiacion + Pasaporte Anterior
        8.  form_review_representantes- FORM_REVIEW: Representants legaux [condition: is_minor=True]
        9.  payment                   - PAYMENT: Mobile Money (AVANT RDV)
        10. appointment               - APPOINTMENT: Selection RDV (APRES paiement, hold 15min)
        11. confirmation              - CONFIRMATION: Resume final

        Visible steps by scenario:
        - Adulte EXPEDICION: 0,1,5,6,7,9,10,11 (8 steps)
        - Adulte RENOVACION: 0,1,2,5,6,7,9,10,11 (9 steps)
        - Mineur EXPEDICION (dual): 0,1,3,5,6,7,8,9,10,11 (10 steps)
        - Mineur RENOVACION (unique): 0,1,2,3,4,5,6,7,8,9,10,11 (12 steps)
        """

        # === Step 0: Minor Selection (FIRST) ===
        self.add_step(WorkflowStep(
            step_number=0,
            step_id="is_minor",
            step_type=StepType.SELECTION,
            title_es="Tipo de Solicitante",
            description_es="Indique si la solicitud es para un adulto o un menor de edad",
            requires_previous=False,
            config={
                "selection_type": "is_minor",
                "options": [
                    {
                        "value": "false",
                        "label_es": "Mayor de Edad",
                        "description_es": "Persona de 18 anos o mas",
                        "icon": "user"
                    },
                    {
                        "value": "true",
                        "label_es": "Menor de Edad",
                        "description_es": "Persona menor de 18 anos (requiere autorizacion parental)",
                        "icon": "user-child"
                    }
                ]
            }
        ))

        # === Step 1: Type Selection (EXPEDICION/RENOVACION) ===
        self.add_step(WorkflowStep(
            step_number=1,  # sequential
            step_id="select_type",
            step_type=StepType.SELECTION,
            title_es="Tipo de Solicitud",
            description_es="Seleccione el tipo de tramite de pasaporte",
            config={
                "selection_type": "solicitud_type",
                "options": [
                    {
                        "value": SolicitudType.EXPEDICION.value,
                        "label_es": "Primera Expedicion",
                        "description_es": "Solicito mi primer pasaporte",
                        "tariff": 7500,
                        "icon": "passport-new"
                    },
                    {
                        "value": SolicitudType.RENOVACION.value,
                        "label_es": "Renovacion",
                        "description_es": "Ya tengo un pasaporte (vencido, perdido, robado o danado)",
                        "has_sub_options": True,  # Indicates motivo selection follows
                        "icon": "passport-renew"
                    }
                ]
            }
        ))

        # === Step 2: Motivo Selection (only for RENOVACION) ===
        self.add_step(WorkflowStep(
            step_number=2,  # sequential — condition filters visibility
            step_id="select_motivo",
            step_type=StepType.SELECTION,
            title_es="Motivo de Renovacion",
            description_es="Seleccione el motivo de la renovacion",
            config={
                "selection_type": "motivo",
                "condition": {"solicitud_type": SolicitudType.RENOVACION.value},
                "options": [
                    {
                        "value": RenovacionMotivo.VENCIMIENTO.value,
                        "label_es": "Vencimiento",
                        "description_es": "Mi pasaporte esta vencido o por vencer",
                        "tariff": 5000,
                        "icon": "calendar-expired"
                    },
                    {
                        "value": RenovacionMotivo.PERDIDA.value,
                        "label_es": "Perdida",
                        "description_es": "Perdi mi pasaporte (requiere denuncia policial)",
                        "tariff": 10000,
                        "icon": "document-lost"
                    },
                    {
                        "value": RenovacionMotivo.ROBO.value,
                        "label_es": "Robo",
                        "description_es": "Me robaron mi pasaporte (requiere denuncia policial)",
                        "tariff": 10000,
                        "icon": "shield-alert"
                    },
                    {
                        "value": RenovacionMotivo.DETERIORO.value,
                        "label_es": "Deterioro",
                        "description_es": "Mi pasaporte esta danado",
                        "tariff": 7500,
                        "icon": "document-damaged"
                    }
                ]
            }
        ))

        # === Step 3: Representantes Legales (only for MINORS) ===
        # Format B: simple binary selection — 1 or 2 representatives
        self.add_step(WorkflowStep(
            step_number=3,  # sequential — condition filters visibility
            step_id="representantes_legales",
            step_type=StepType.SELECTION,
            title_es="Representantes Legales",
            description_es="Indique si uno o ambos padres/tutores realizaran el tramite",
            config={
                "selection_type": "representante_unico",
                "condition": {"is_minor": "true"},
                "options": [
                    {
                        "value": "false",
                        "label_es": "Ambos padres/tutores",
                        "description_es": "Ambos representantes legales realizaran el tramite",
                        "icon": "users"
                    },
                    {
                        "value": "true",
                        "label_es": "Representante unico",
                        "description_es": "Solo un padre/tutor realizara el tramite (custodia exclusiva, fallecimiento, etc.)",
                        "icon": "user"
                    }
                ]
            }
        ))

        # === Step 4: Motivo Representante Unico (only if single representative) ===
        # Format B: reason for single representative
        self.add_step(WorkflowStep(
            step_number=4,  # sequential — condition filters visibility
            step_id="select_motivo_rep_unico",
            step_type=StepType.SELECTION,
            title_es="Motivo de Representante Unico",
            description_es="Indique el motivo por el cual solo un representante realiza el tramite",
            config={
                "selection_type": "motivo_representante_unico",
                "condition": {"is_minor": "true", "representante_unico": "true"},
                "options": [
                    {
                        "value": "CUSTODIA_EXCLUSIVA",
                        "label_es": "Custodia exclusiva",
                        "description_es": "Tiene la custodia exclusiva del menor"
                    },
                    {
                        "value": "FALLECIMIENTO",
                        "label_es": "Fallecimiento del otro progenitor",
                        "description_es": "El otro padre/madre ha fallecido"
                    },
                    {
                        "value": "PADRE_DESCONOCIDO",
                        "label_es": "Padre/Madre desconocido",
                        "description_es": "Uno de los progenitores es desconocido"
                    },
                    {
                        "value": "OTRO",
                        "label_es": "Otro motivo",
                        "description_es": "Otro motivo legal documentado"
                    }
                ]
            }
        ))

        # === Step 5: Document Upload (ALL documents on ONE page) ===
        self.add_step(WorkflowStep(
            step_number=5,
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

        # === Step 6: Form Review 1 - Datos Personales + Domicilio ===
        # CONDITIONAL: Different fields for adults (DIP) vs minors (certificado_nacimiento)
        self.add_step(WorkflowStep(
            step_number=6,
            step_id="form_review_1",
            step_type=StepType.FORM_REVIEW,
            title_es="Verificar Datos (1/2)",
            description_es="Verifique sus datos personales y domicilio",
            config={
                "form_page": 1,
                "max_sections": 2,
                "conditional_sections": True,  # Frontend checks is_minor to select section set
                "sections_adult": [
                    {
                        "id": "personal",
                        "title_es": "Datos Personales",
                        "source_document": "dip",
                        "fields": [
                            {"key": "numero_dip", "label_es": "Numero DIP", "required": True},
                            {"key": "apellidos", "label_es": "Apellidos", "required": True},
                            {"key": "nombres", "label_es": "Nombres", "required": True},
                            {"key": "sexo", "label_es": "Sexo", "required": True, "type": "select", "options": ["M", "F"]},
                            {"key": "fecha_nacimiento", "label_es": "Fecha de Nacimiento", "required": True, "type": "date"},
                            {"key": "lugar_nacimiento", "label_es": "Lugar de Nacimiento", "required": True},
                            {"key": "natural_de", "label_es": "Natural de", "required": False},
                            {"key": "nacionalidad", "label_es": "Nacionalidad", "required": True},
                            {"key": "estado_civil", "label_es": "Estado Civil", "required": True},
                            {"key": "profesion", "label_es": "Profesion", "required": True},
                            {"key": "grupo_sanguineo", "label_es": "Grupo Sanguineo", "required": False}
                        ]
                    },
                    {
                        "id": "domicilio",
                        "title_es": "Domicilio",
                        "fields": [
                            {"key": "domicilio_barrio", "label_es": "Barrio", "required": True},
                            {"key": "domicilio_ciudad", "label_es": "Ciudad", "required": True},
                            {"key": "distrito_provincia", "label_es": "Distrito/Provincia", "required": True, "pdf_exclude": True}
                        ]
                    }
                ],
                "sections_minor": [
                    {
                        "id": "personal_menor",
                        "title_es": "Datos del Menor",
                        "source_document": "certificado_nacimiento",
                        "fields": [
                            {"key": "cert_nombre", "label_es": "Nombre", "required": True},
                            {"key": "cert_primer_apellido", "label_es": "Primer Apellido", "required": True},
                            {"key": "cert_segundo_apellido", "label_es": "Segundo Apellido", "required": False},
                            {"key": "cert_sexo", "label_es": "Sexo", "required": True, "type": "select", "options": ["M", "F"]},
                            {"key": "cert_fecha_nacimiento", "label_es": "Fecha de Nacimiento", "required": True, "type": "date"},
                            {"key": "cert_lugar_nacimiento", "label_es": "Lugar de Nacimiento", "required": True}
                        ]
                    },
                    {
                        "id": "registro_civil",
                        "title_es": "Datos del Registro Civil",
                        "source_document": "certificado_nacimiento",
                        "fields": [
                            {"key": "registro_civil", "label_es": "Registro Civil de", "required": True},
                            {"key": "provincia_registro", "label_es": "Provincia", "required": False},
                            {"key": "tomo_nacimiento", "label_es": "Tomo", "required": False},
                            {"key": "pagina_nacimiento", "label_es": "Pagina", "required": False}
                        ]
                    }
                ],
                # Legacy: sections field for backwards compatibility (defaults to adult)
                "sections": [
                    {
                        "id": "personal",
                        "title_es": "Datos Personales",
                        "fields": [
                            {"key": "numero_dip", "label_es": "Numero DIP", "required": True},
                            {"key": "apellidos", "label_es": "Apellidos", "required": True},
                            {"key": "nombres", "label_es": "Nombres", "required": True},
                            {"key": "sexo", "label_es": "Sexo", "required": True, "type": "select", "options": ["M", "F"]},
                            {"key": "fecha_nacimiento", "label_es": "Fecha de Nacimiento", "required": True, "type": "date"},
                            {"key": "lugar_nacimiento", "label_es": "Lugar de Nacimiento", "required": True},
                            {"key": "natural_de", "label_es": "Natural de", "required": False},
                            {"key": "nacionalidad", "label_es": "Nacionalidad", "required": True},
                            {"key": "estado_civil", "label_es": "Estado Civil", "required": True},
                            {"key": "profesion", "label_es": "Profesion", "required": True},
                            {"key": "grupo_sanguineo", "label_es": "Grupo Sanguineo", "required": False}
                        ]
                    },
                    {
                        "id": "domicilio",
                        "title_es": "Domicilio",
                        "fields": [
                            {"key": "domicilio_barrio", "label_es": "Barrio", "required": True},
                            {"key": "domicilio_ciudad", "label_es": "Ciudad", "required": True},
                            {"key": "distrito_provincia", "label_es": "Distrito/Provincia", "required": True, "pdf_exclude": True}
                        ]
                    }
                ]
            }
        ))

        # === Step 7: Form Review 2 - Filiacion + Pasaporte Anterior ===
        self.add_step(WorkflowStep(
            step_number=7,
            step_id="form_review_2",
            step_type=StepType.FORM_REVIEW,
            title_es="Verificar Datos (2/2)",
            description_es="Verifique los datos de filiacion y pasaporte anterior",
            config={
                "form_page": 2,
                "max_sections": 2,
                "sections": [
                    {
                        "id": "filiacion",
                        "title_es": "Filiacion",
                        "fields": [
                            {"key": "nombre_padre", "label_es": "Nombre del Padre", "required": True},
                            # Profesion only available from certificado_nacimiento (EXPEDICION or minors)
                            {"key": "profesion_padre", "label_es": "Profesion del Padre", "required": False,
                             "condition": {"OR": [{"solicitud_type": SolicitudType.EXPEDICION.value}, {"is_minor": "true"}]}},
                            {"key": "nombre_madre", "label_es": "Nombre de la Madre", "required": True},
                            {"key": "profesion_madre", "label_es": "Profesion de la Madre", "required": False,
                             "condition": {"OR": [{"solicitud_type": SolicitudType.EXPEDICION.value}, {"is_minor": "true"}]}}
                        ]
                    },
                    {
                        "id": "pasaporte_anterior",
                        "title_es": "Pasaporte Anterior",
                        "condition": {
                            "solicitud_type": SolicitudType.RENOVACION.value,
                            "motivo_in": [RenovacionMotivo.VENCIMIENTO.value, RenovacionMotivo.DETERIORO.value]
                        },
                        "fields": [
                            {"key": "numero_pasaporte_antiguo", "label_es": "Numero Pasaporte Antiguo", "required": True},
                            {"key": "fecha_expedicion_antiguo", "label_es": "Fecha de Expedicion", "required": True, "type": "date"},
                            {"key": "fecha_expiracion_antiguo", "label_es": "Fecha de Expiracion", "required": True, "type": "date"}
                        ]
                    }
                ]
            }
        ))

        # === Step 8: Form Review Representantes (MINORS ONLY) ===
        # Shows data from autorizacion_parental + cross-validation status
        self.add_step(WorkflowStep(
            step_number=8,
            step_id="form_review_representantes",
            step_type=StepType.FORM_REVIEW,
            title_es="Verificar Representantes Legales",
            description_es="Verifique los datos de los representantes legales y el estado de validacion",
            config={
                "form_page": 3,
                "condition": {"is_minor": "true"},  # Only shown for minors
                "max_sections": 3,
                "source_document": "autorizacion_parental",
                "sections": [
                    {
                        "id": "representante_1",
                        "title_es": "Representante 1",
                        "fields": [
                            {"key": "rep1_nombre", "label_es": "Nombre Completo", "required": True},
                            {"key": "rep1_parentesco", "label_es": "Parentesco", "required": False, "type": "select", "options": ["PADRE", "MADRE", "TUTOR_LEGAL", "OTRO"]},
                            {"key": "rep1_documento_tipo", "label_es": "Tipo de Documento", "required": True, "type": "select", "options": ["DIP", "NIE", "PASAPORTE"]},
                            {"key": "rep1_documento_numero", "label_es": "Numero de Documento", "required": True},
                            {"key": "rep1_validacion_status", "label_es": "Estado de Validacion", "required": False, "type": "validation_badge", "readonly": True}
                        ]
                    },
                    {
                        "id": "representante_2",
                        "title_es": "Representante 2",
                        "condition": {"representante_unico": "false"},  # Only if dual-parent (string: RadioGroup stores strings)
                        "fields": [
                            {"key": "rep2_nombre", "label_es": "Nombre Completo", "required": True},
                            {"key": "rep2_parentesco", "label_es": "Parentesco", "required": False, "type": "select", "options": ["PADRE", "MADRE", "TUTOR_LEGAL", "OTRO"]},
                            {"key": "rep2_documento_tipo", "label_es": "Tipo de Documento", "required": True, "type": "select", "options": ["DIP", "NIE", "PASAPORTE"]},
                            {"key": "rep2_documento_numero", "label_es": "Numero de Documento", "required": True},
                            {"key": "rep2_validacion_status", "label_es": "Estado de Validacion", "required": False, "type": "validation_badge", "readonly": True}
                        ]
                    },
                    {
                        "id": "validacion_cruzada",
                        "title_es": "Resumen de Validacion",
                        "readonly": True,
                        "fields": [
                            {"key": "cross_validation_passed", "label_es": "Validacion Cruzada", "type": "validation_badge", "readonly": True},
                            {"key": "authorization_date_valid", "label_es": "Fecha Autorizacion Valida", "type": "validation_badge", "readonly": True},
                            {"key": "signatures_valid", "label_es": "Firmas Validas", "type": "validation_badge", "readonly": True},
                            {"key": "blocking_errors", "label_es": "Errores Bloqueantes", "type": "error_list", "readonly": True}
                        ]
                    }
                ]
            }
        ))

        # === Step 9: Appointment (BEFORE Payment) ===
        # Selection cached in wizard session, hold created atomically during payment
        self.add_step(WorkflowStep(
            step_number=9,
            step_id="appointment",
            step_type=StepType.APPOINTMENT,
            title_es="Programar Cita",
            description_es="Seleccione una cita en la oficina CNEDOGE",
            config={
                "entity_via_request": True,
                "use_appointment_module": True,
            }
        ))

        # === Step 10: Payment (AFTER Appointment) ===
        # Payment methods loaded dynamically via GET /payment/methods endpoint
        self.add_step(WorkflowStep(
            step_number=10,
            step_id="payment",
            step_type=StepType.PAYMENT,
            title_es="Pago de Tasas",
            description_es="Realice el pago mediante Mobile Money o en efectivo",
            config={
                "currency": "XAF",
                "show_breakdown": True,
                "dynamic_tariff": True,
            }
        ))

        # === Step 11: Confirmation ===
        self.add_step(WorkflowStep(
            step_number=11,
            step_id="confirmation",
            step_type=StepType.CONFIRMATION,
            title_es="Confirmacion",
            description_es="Su solicitud ha sido completada",
            config={
                "show_summary": True,
                "show_appointment": True,
                "show_payment": True,
                "allow_download_receipt": True,
                "next_steps_es": [
                    "Presentese en la oficina CNEDOGE en la fecha y hora indicadas",
                    "Lleve los documentos originales para verificacion",
                    "El tiempo estimado de entrega es de 5 dias habiles"
                ]
            }
        ))

        # === Setup Tariffs ===
        self._setup_tariffs()

    def _setup_tariffs(self) -> None:
        """
        Setup tariff configuration.

        Base Tariffs (ALIGNED WITH SolicitudType + RenovacionMotivo):
        - SolicitudType.EXPEDICION: 7,500 XAF
        - RenovacionMotivo.VENCIMIENTO: 5,000 XAF
        - RenovacionMotivo.PERDIDA: 10,000 XAF (includes penalty)
        - RenovacionMotivo.ROBO: 10,000 XAF (includes penalty)
        - RenovacionMotivo.DETERIORO: 7,500 XAF

        Supplements: None for pasaporte (quantity=0)
        """
        self.set_tariff_config(TariffConfig(
            tariff_type=TariffType.FIXED,
            fixed_amounts={
                # SolicitudType enum values
                SolicitudType.EXPEDICION.value: 7500,      # 7,500 XAF
                # RenovacionMotivo enum values
                RenovacionMotivo.VENCIMIENTO.value: 5000,  # 5,000 XAF
                RenovacionMotivo.PERDIDA.value: 10000,     # 10,000 XAF (penalty)
                RenovacionMotivo.ROBO.value: 10000,        # 10,000 XAF (penalty)
                RenovacionMotivo.DETERIORO.value: 7500,    # 7,500 XAF
            },
            currency="XAF",
            # No supplements for pasaporte (quantity=0 in DB config)
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
        Get document requirements based on SolicitudType and RenovacionMotivo.

        ALIGNED WITH workflow_interface.py signat ure.

        Common to all types:
        - DIP (always required)
        - Photos (always required)

        Type-specific:
        - EXPEDICION: + Certificado de Nacimiento
        - RENOVACION/VENCIMIENTO: + Pasaporte antiguo
        - RENOVACION/DETERIORO: + Pasaporte danado
        - RENOVACION/PERDIDA: + Denuncia policial
        - RENOVACION/ROBO: + Denuncia policial

        Conditional (for minors):
        - Minor (<18): + Autorizacion Parental + DIP del padre/madre/tutor
        """
        requirements = []

        # is_minor from context (set at SELECTION step)
        is_minor = context.is_minor if context else False

        # === DIP - Required for ADULTS only (minors use certificado_nacimiento) ===
        if not is_minor:
            requirements.append(DocumentRequirement(
                document_code="dip",
                document_name_es="Documento de Identidad Personal (DIP)",
                schema_key="DIP_GQ_V2",
                is_required=True,
                display_order=1,
                condition_type=DocumentConditionType.IS_ADULT,
                instructions_es="Escanee ambas caras de su DIP vigente (recto y verso en un solo archivo)",
                faces_required=["recto", "verso"],
                config={"single_file": True}  # Both sides in one file
            ))

        # === Type-specific documents ===

        # === Certificado de Nacimiento ===
        # Required for: EXPEDICION (all) + RENOVACION (minors only)
        if solicitud_type == SolicitudType.EXPEDICION:
            # First passport: need birth certificate (adults and minors)
            requirements.append(DocumentRequirement(
                document_code="certificado_nacimiento",
                document_name_es="Certificado de Nacimiento",
                schema_key="CERTIFICACION_NACIMIENTO_GQ_V1",
                is_required=True,
                display_order=2,
                condition_type=DocumentConditionType.IS_NEW,
                instructions_es="Certificacion literal de inscripcion de nacimiento (original o copia certificada)"
            ))
        elif solicitud_type == SolicitudType.RENOVACION and is_minor:
            # Renovation for minors: need birth certificate (replaces DIP)
            requirements.append(DocumentRequirement(
                document_code="certificado_nacimiento",
                document_name_es="Certificado de Nacimiento",
                schema_key="CERTIFICACION_NACIMIENTO_GQ_V1",
                is_required=True,
                display_order=2,
                condition_type=DocumentConditionType.IS_MINOR,
                instructions_es="Certificacion literal de nacimiento del menor (original o copia certificada)"
            ))

        # === RENOVACION motivo-specific documents (applies to adults AND minors) ===
        if solicitud_type == SolicitudType.RENOVACION and motivo:
            if motivo in [RenovacionMotivo.VENCIMIENTO, RenovacionMotivo.DETERIORO]:
                # Need old passport
                doc_name = "Pasaporte Danado" if motivo == RenovacionMotivo.DETERIORO else "Pasaporte Antiguo"
                instructions = (
                    "Presente el pasaporte danado para verificacion"
                    if motivo == RenovacionMotivo.DETERIORO
                    else "Escanee la pagina de datos de su pasaporte vencido o por vencer"
                )
                requirements.append(DocumentRequirement(
                    document_code="pasaporte_antiguo",
                    document_name_es=doc_name,
                    schema_key="PASAPORTE_GQ_V1",
                    is_required=True,
                    display_order=2,
                    condition_type=DocumentConditionType.CUSTOM,
                    condition_value={"motivos": ["VENCIMIENTO", "DETERIORO"]},
                    instructions_es=instructions
                ))

            elif motivo in [RenovacionMotivo.PERDIDA, RenovacionMotivo.ROBO]:
                # Need police report
                reason = "robo" if motivo == RenovacionMotivo.ROBO else "perdida"
                requirements.append(DocumentRequirement(
                    document_code="denuncia_policial",
                    document_name_es="Denuncia Policial",
                    is_required=True,
                    display_order=2,
                    condition_type=DocumentConditionType.CUSTOM,
                    condition_value={"motivos": ["PERDIDA", "ROBO"]},
                    instructions_es=f"Denuncia de {reason} emitida por la Policia Nacional (maximo 30 dias)"
                ))

        # === Photo (1 required) ===
        requirements.append(DocumentRequirement(
            document_code="photo_carnet",
            document_name_es="Fotografia tipo pasaporte",
            is_required=True,
            display_order=10,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es="1 foto de 35x45mm, fondo blanco, rostro visible",
            accepted_formats=["jpg", "jpeg", "png"],  # Only image formats for photos
            config={
                "quantity": 1,
                "max_size_mb": 2,  # Photos should be small
                "min_dimensions": {"width": 350, "height": 450}  # 35x45mm at ~254dpi
            }
        ))

        # === Minor-specific requirements ===
        if is_minor:
            # Check if single representative (from context — RadioGroup stores strings)
            representante_unico = False
            if context and context.form_data:
                rep_flag = context.form_data.get("representante_unico", "false")
                representante_unico = (rep_flag is True or rep_flag == "true")

            # Parental authorization (with OCR schema)
            requirements.append(DocumentRequirement(
                document_code="autorizacion_parental",
                document_name_es="Autorizacion Parental",
                schema_key="AUTORIZACION_PARENTAL_GQ_V1",
                is_required=True,
                display_order=5,
                condition_type=DocumentConditionType.IS_MINOR,
                instructions_es="Autorizacion parental firmada. Cualquier formato aceptado."
            ))

            # Document of representative 1 (ALWAYS required for minors)
            # Accepts DIP, NIE (permiso residencia), or Passport
            requirements.append(DocumentRequirement(
                document_code="documento_representante_1",
                document_name_es="Documento de Identidad del Representante 1",
                is_required=True,
                display_order=6,
                condition_type=DocumentConditionType.IS_MINOR,
                instructions_es="DIP, NIE o Pasaporte del padre, madre o tutor que realiza el tramite",
                faces_required=["recto", "verso"],
                config={
                    "single_file": True,
                    "accepted_schemas": {
                        "DIP": "DIP_GQ_V2",
                        "NIE": "PERMISO_RESIDENCIA_GQ_V1",
                        "PASAPORTE_GQ": "PASAPORTE_GQ_V1",
                        "PASAPORTE_INTERNATIONAL": "PASAPORTE_INTERNATIONAL_V1"
                    }
                }
            ))

            # Document of representative 2 (CONDITIONAL - only if not single representative)
            if not representante_unico:
                requirements.append(DocumentRequirement(
                    document_code="documento_representante_2",
                    document_name_es="Documento de Identidad del Representante 2",
                    is_required=False,  # Conditional based on representante_unico
                    display_order=7,
                    condition_type=DocumentConditionType.CUSTOM,
                    condition_value={"is_minor": "true", "representante_unico": "false"},
                    instructions_es="DIP, NIE o Pasaporte del segundo padre, madre o tutor",
                    faces_required=["recto", "verso"],
                    config={
                        "single_file": True,
                        "accepted_schemas": {
                            "DIP": "DIP_GQ_V2",
                            "NIE": "PERMISO_RESIDENCIA_GQ_V1",
                            "PASAPORTE_GQ": "PASAPORTE_GQ_V1",
                            "PASAPORTE_INTERNATIONAL": "PASAPORTE_INTERNATIONAL_V1"
                        }
                    }
                ))

        return requirements

    def get_document_requirements_legacy(
        self,
        sub_type: str,
        context: Optional[WorkflowContext] = None
    ) -> List[DocumentRequirement]:
        """
        Legacy method for backwards compatibility.
        Converts sub_type string to SolicitudType + RenovacionMotivo.
        """
        solicitud_motivo = self.SUBTYPE_TO_SOLICITUD_MOTIVO.get(sub_type)
        if solicitud_motivo:
            solicitud_type, motivo = solicitud_motivo
            return self.get_document_requirements(solicitud_type, motivo, context)
        # Default to EXPEDICION if unknown sub_type
        return self.get_document_requirements(SolicitudType.EXPEDICION, None, context)

    def _is_minor(self, fecha_nacimiento: str) -> bool:
        """Check if person is minor based on birth date."""
        from datetime import datetime, date
        try:
            if isinstance(fecha_nacimiento, str):
                # Parse date string (expecting YYYY-MM-DD or DD/MM/YYYY)
                if "-" in fecha_nacimiento:
                    birth_date = datetime.strptime(fecha_nacimiento, "%Y-%m-%d").date()
                else:
                    birth_date = datetime.strptime(fecha_nacimiento, "%d/%m/%Y").date()
            else:
                birth_date = fecha_nacimiento

            today = date.today()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            return age < 18
        except Exception:
            return False

    # === Form Field Mapping ===

    def get_form_mapping(self, context: Optional[WorkflowContext] = None) -> Dict[str, str]:
        """
        Map extracted data fields to form fields.

        ALIGNED WITH JSON SCHEMAS (source of truth):
        - dip_gq.json: documento.fecha_emision (NOT fecha_expedicion)
        - certificacion_nacimiento_gq.json:
          - inscrito.nombre (NOT nombres), inscrito.primer_apellido + segundo_apellido
          - padre.hijo_de, madre.hija_de (NOT natural_de)
          - declarante.calidad (NOT relacion), declarante.nombre (NOT nombre_completo)
          - NO hora_nacimiento, NO numero_acta, NO edad, NO domicilio_padre

        For minors: Extract ALL available data from certificado_nacimiento.
        For adults: Add padre.profesion and madre.profesion from certificado_nacimiento.
        """
        # is_minor from context (set at SELECTION step)
        is_minor = context.is_minor if context else False

        mapping = {
            # === DIP Fields (per dip_gq.json schema) ===
            "numero_dip": "dip.documento.numero_dip",
            "apellidos": "dip.titular.apellidos",
            "nombres": "dip.titular.nombres",
            "sexo": "dip.titular.sexo",
            "fecha_nacimiento": "dip.titular.fecha_nacimiento",
            "lugar_nacimiento": "dip.titular.lugar_nacimiento",
            "natural_de": "dip.titular.natural_de",
            "distrito_provincia": "dip.titular.distrito_provincia",
            "nacionalidad": "dip.titular.nacionalidad",
            "estado_civil": "dip.titular.estado_civil",
            "profesion": "dip.titular.profesion",
            # Address fields - parsed from domiciliacion by _post_process_extraction()
            "domicilio_barrio": "dip.domiciliacion_barrio",
            "domicilio_ciudad": "dip.domiciliacion_ciudad",
            "grupo_sanguineo": "dip.titular.grupo_sanguineo",

            # === DIP Filiation (bloc HIJO DE on verso) ===
            # For adults RENOVACION: filiation comes from DIP, not certificado_nacimiento
            "nombre_padre": "dip.filiacion.nombre_padre",
            "nombre_madre": "dip.filiacion.nombre_madre",

            # === DIP document metadata (fecha_EMISION per schema) ===
            "dip_fecha_emision": "dip.documento.fecha_emision",
            "dip_fecha_expiracion": "dip.documento.fecha_expiracion",
            "dip_lugar_emision": "dip.documento.lugar_emision",

            # === Old passport fields (for RENOVACION/DETERIORO) ===
            "numero_pasaporte_antiguo": "pasaporte_antiguo.documento.numero_pasaporte",
            "fecha_expedicion_antiguo": "pasaporte_antiguo.documento.fecha_expedicion",
            "fecha_expiracion_antiguo": "pasaporte_antiguo.documento.fecha_expiracion",
        }

        if is_minor:
            # === For MINORS: Extract ALL data from certificado_nacimiento ===
            # ALIGNED with certificacion_nacimiento_gq.json schema
            mapping.update({
                # Document metadata
                "registro_civil": "certificado_nacimiento.documento.registro_civil_de",
                "provincia_registro": "certificado_nacimiento.documento.provincia",
                "seccion_registro": "certificado_nacimiento.documento.seccion",
                "tomo_nacimiento": "certificado_nacimiento.documento.tomo",
                "pagina_nacimiento": "certificado_nacimiento.documento.pagina",
                "folio_nacimiento": "certificado_nacimiento.documento.folio",

                # Inscrito data - CORRECT field names per schema
                "cert_nombre": "certificado_nacimiento.inscrito.nombre",
                "cert_primer_apellido": "certificado_nacimiento.inscrito.primer_apellido",
                "cert_segundo_apellido": "certificado_nacimiento.inscrito.segundo_apellido",
                "cert_sexo": "certificado_nacimiento.inscrito.sexo",
                "cert_fecha_nacimiento": "certificado_nacimiento.inscrito.fecha_nacimiento",
                "cert_lugar_nacimiento": "certificado_nacimiento.inscrito.lugar_nacimiento",

                # Father data - CORRECT field names per schema
                "nombre_padre": "certificado_nacimiento.padre.nombre_completo",
                "nacionalidad_padre": "certificado_nacimiento.padre.nacionalidad",
                "lugar_nacimiento_padre": "certificado_nacimiento.padre.lugar_nacimiento",
                "estado_civil_padre": "certificado_nacimiento.padre.estado_civil",
                "profesion_padre": "certificado_nacimiento.padre.profesion",
                # Grandparents (paternal) - in padre.hijo_de and padre.y_de
                "abuelo_paterno": "certificado_nacimiento.padre.hijo_de",
                "abuela_paterna": "certificado_nacimiento.padre.y_de",

                # Mother data - CORRECT field names per schema
                "nombre_madre": "certificado_nacimiento.madre.nombre_completo",
                "nacionalidad_madre": "certificado_nacimiento.madre.nacionalidad",
                "lugar_nacimiento_madre": "certificado_nacimiento.madre.lugar_nacimiento",
                "estado_civil_madre": "certificado_nacimiento.madre.estado_civil",
                "profesion_madre": "certificado_nacimiento.madre.profesion",
                "domicilio_madre": "certificado_nacimiento.madre.domicilio",
                # Grandparents (maternal) - in madre.hija_de and madre.y_de
                "abuelo_materno": "certificado_nacimiento.madre.hija_de",
                "abuela_materna": "certificado_nacimiento.madre.y_de",

                # Marriage info
                "matrimonio_padres": "certificado_nacimiento.matrimonio_padres.informacion",

                # Declarant info - CORRECT field names per schema
                "declarante_nombre": "certificado_nacimiento.declarante.nombre",
                "declarante_calidad": "certificado_nacimiento.declarante.calidad",
                "declarante_domicilio": "certificado_nacimiento.declarante.domicilio",

                # === Autorizacion Parental fields (for form_review_representantes) ===
                # ALIGNED with autorizacion_parental_gq.json schema
                # Representante 1
                "rep1_nombre": "autorizacion_parental.representante_1.nombre_completo",
                "rep1_parentesco": "autorizacion_parental.representante_1.parentesco",
                "rep1_documento_tipo": "autorizacion_parental.representante_1.documento_tipo",
                "rep1_documento_numero": "autorizacion_parental.representante_1.documento_numero",

                # Representante 2 (if applicable)
                "rep2_nombre": "autorizacion_parental.representante_2.nombre_completo",
                "rep2_parentesco": "autorizacion_parental.representante_2.parentesco",
                "rep2_documento_tipo": "autorizacion_parental.representante_2.documento_tipo",
                "rep2_documento_numero": "autorizacion_parental.representante_2.documento_numero",

                # Authorization metadata
                "fecha_autorizacion": "autorizacion_parental.documento.fecha_autorizacion",
                "es_representante_unico": "autorizacion_parental.documento.es_representante_unico",
                "motivo_representante_unico": "autorizacion_parental.documento.motivo_representante_unico",

                # Minor data from authorization (for cross-check)
                "menor_nombre_autorizacion": "autorizacion_parental.menor.nombre_completo",
                "menor_fecha_nacimiento_autorizacion": "autorizacion_parental.menor.fecha_nacimiento",

                # Cross-validation results (populated by gemini_processor, stored in form_data)
                "rep1_validacion_status": "form_data.parental_authorization_validation.representante_1.match",
                "rep2_validacion_status": "form_data.parental_authorization_validation.representante_2.match",
                "cross_validation_passed": "form_data.parental_authorization_validation.cross_validation_passed",
                "authorization_date_valid": "form_data.parental_authorization_validation.authorization_date_valid",
                "signatures_valid": "form_data.parental_authorization_validation.signatures_valid",
                "blocking_errors": "form_data.parental_authorization_validation.blocking_errors",
            })
        else:
            # === For ADULTS: Add parent info from certificado ONLY for NUEVO ===
            # For RENOVACION/DETERIORO/PERDIDA/ROBO: filiation stays from DIP (lines 887-888)
            # certificado_nacimiento is not required for these motivos
            motivo = context.motivo if context else None
            solicitud = context.solicitud_type if context else None
            is_nuevo = (solicitud and solicitud.value == "EXPEDICION") or (not motivo)
            if is_nuevo:
                mapping.update({
                    "registro_civil": "certificado_nacimiento.documento.registro_civil_de",
                    "nombre_padre": "certificado_nacimiento.padre.nombre_completo",
                    "profesion_padre": "certificado_nacimiento.padre.profesion",
                    "nombre_madre": "certificado_nacimiento.madre.nombre_completo",
                    "profesion_madre": "certificado_nacimiento.madre.profesion",
                })

        return mapping

    # === Workflow Code Resolution ===

    @property
    def _subtype_code_aliases(self) -> Dict[str, WorkflowCode]:
        """VENCIMIENTO is a semantic alias — expired passport = renewal."""
        return {
            "VENCIMIENTO": WorkflowCode.PASAPORTE_RENOVACION,
        }


# =============================================================================
# REGISTRATION
# =============================================================================

def register_pasaporte_workflow():
    """Register the passport workflow with the workflow engine."""
    from ..services.workflow_engine import workflow_engine

    workflow = PasaporteWorkflow()
    workflow_engine.register_workflow(workflow)


# Singleton instance
_pasaporte_workflow: Optional[PasaporteWorkflow] = None


def get_pasaporte_workflow() -> PasaporteWorkflow:
    """Get the singleton PasaporteWorkflow instance."""
    global _pasaporte_workflow
    if _pasaporte_workflow is None:
        _pasaporte_workflow = PasaporteWorkflow()
    return _pasaporte_workflow
