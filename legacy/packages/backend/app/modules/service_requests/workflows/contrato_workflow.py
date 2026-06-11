"""
ContratoWorkflow v2 - Contract registration workflow (ONRC).

Migrated to PredefinedWorkflow architecture (Option C - Dynamic Form Review).

Solicitud Types:
- REGISTRO_NUEVO: First registration of a commercial contract
- ADENDA: Amendment to a registered contract (value/scope change)
- PRORROGA: Extension of contract duration
- CESION: Transfer of contract to another party
- RESCISION: Early termination/cancellation registration

Contract Types (for REGISTRO_NUEVO):
- OBRA: Construction/Infrastructure contracts
- SERVICIO: Service contracts
- SUMINISTRO: Supply contracts
- CONCESION: Concession contracts
- JOINT_VENTURE: Partnership contracts
- ARRENDAMIENTO: Lease contracts
- OTRO: Other contracts

Entity: ONRC (Oficina Nacional de Registro de Contratos)

Tariff: 0.5% of contract value in XAF (percentage-based).
Late penalty: 10%/month after 30 days (controlled by PENALTY_MULTIPLIER).
Minimum tariff: 50,000 XAF (controlled by MINIMUM_TARIFF_MULTIPLIER).
Supplements: TIMBRE_FISCAL 500 XAF/page + CEDULA_REGISTRO 5,000 XAF (quantity=0).

Payment flow: Standard (citizen pays → then agent reviews).
Agent can set monto_validado_por_agente during review.

Document philosophy: All documents listed, most non-mandatory.
When regulations evolve, flip is_required=True without code change.

@version 2.0
@date 2026-02-06
@migration Option C - Dynamic Form Review Architecture
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

# Import PaymentMethod for API parity with other workflows
from ...payments.models.payment import PaymentMethod


class ContratoSolicitudType(str, Enum):
    """Type of contract registration request."""
    REGISTRO_NUEVO = "REGISTRO_NUEVO"   # First registration
    ADENDA = "ADENDA"                   # Amendment
    PRORROGA = "PRORROGA"               # Duration extension
    CESION = "CESION"                   # Transfer to third party
    RESCISION = "RESCISION"             # Early termination


class ContratoType(str, Enum):
    """Type of commercial contract."""
    OBRA = "OBRA"                       # Construction
    SERVICIO = "SERVICIO"               # Services
    SUMINISTRO = "SUMINISTRO"           # Supply
    CONCESION = "CONCESION"             # Concession
    JOINT_VENTURE = "JOINT_VENTURE"     # Partnership
    ARRENDAMIENTO = "ARRENDAMIENTO"     # Lease
    OTRO = "OTRO"                       # Other


class ContratoWorkflow(PredefinedWorkflow):
    """
    Contract registration workflow (ONRC).

    AUTONOMOUS: Defines ALL logic internally, no BaseWorkflow inheritance.

    ALIGNED WITH PredefinedWorkflow architecture (v2):
    - SolicitudType.EXPEDICION: New contract registration (REGISTRO_NUEVO)
    - SolicitudType.RENOVACION: Modifications (ADENDA, PRORROGA, CESION, RESCISION)
    - Sub-types via allowed_sub_types

    Key features v2:
    - form_review_1: Contractor identification (NIF + DIP extraction)
    - form_review_2: Contract details + Contratante + Vigencia
    - form_review_3: Financial data (monto from extraction, editable)
    - Late registration penalty: 10%/month after 30 days (PENALTY_MULTIPLIER controls activation)
    - Supplement: TIMBRE_FISCAL 500 XAF/page (quantity dynamic from contract pages)
    - Most documents non-mandatory (progressive enforcement)
    - Standard payment flow (pay first, agent reviews after)

    Condition Key Convention:
    - Uses "sub_type" as primary condition key
    - Uses "contract_type" for contract-type-specific conditions
    """

    # Sub_type to (SolicitudType, Motivo) mapping
    SUBTYPE_TO_SOLICITUD_MOTIVO = {
        "REGISTRO_NUEVO": (SolicitudType.EXPEDICION, None),
        "ADENDA": (SolicitudType.RENOVACION, None),
        "PRORROGA": (SolicitudType.RENOVACION, None),
        "CESION": (SolicitudType.RENOVACION, None),
        "RESCISION": (SolicitudType.RENOVACION, None),
    }

    # Tariff: 0.5% of contract value
    TARIFF_PERCENTAGE = 0.005  # 0.5%

    # Late registration penalty
    # Rule: After 30 days from signature, 10%/month penalty, max 100%
    # Set PENALTY_MULTIPLIER = 1 to activate
    PENALTY_MULTIPLIER = 0
    PENALTY_RATE_PER_MONTH = 0.10       # 10% per month
    PENALTY_MAX_RATE = 1.0              # 100% max
    REGISTRATION_DELAY_DAYS = 30        # Grace period in days

    # Minimum tariff: 50,000 XAF
    # Set MINIMUM_TARIFF_MULTIPLIER = 1 to activate
    MINIMUM_TARIFF_MULTIPLIER = 0
    MINIMUM_TARIFF_XAF = 50000

    # Exchange rates (official BEAC rates)
    EXCHANGE_RATES = {
        "XAF": 1,
        "EUR": 655.957,     # 1 EUR = 655.957 XAF (fixed parity)
        "USD": 600,          # 1 USD ≈ 600 XAF (approximate)
    }

    # Legacy alias
    SUBTYPE_MAPPING = SUBTYPE_TO_SOLICITUD_MOTIVO

    # === Configuration (PredefinedWorkflow required properties) ===

    @property
    def workflow_code(self) -> WorkflowCode:
        return WorkflowCode.CONTRATO_OBRA  # Base code, variant by contract_type

    @property
    def category(self) -> WorkflowCategory:
        return WorkflowCategory.CONTRATOS

    @property
    def entity_code(self) -> EntityCode:
        return EntityCode.ONRC

    @property
    def service_name_es(self) -> str:
        return "Registro de Contrato Comercial"

    def get_subtype_display_names(self) -> Dict[str, str]:
        return {
            "CONTRATO_OBRA": "Contrato - Obra",
            "CONTRATO_SERVICIO": "Contrato - Servicio",
            "CONTRATO_SUMINISTRO": "Contrato - Suministro",
            "CONTRATO_CONCESION": "Contrato - Concesión",
            "CONTRATO_JOINT_VENTURE": "Contrato - Joint Venture",
            "CONTRATO_ARRENDAMIENTO": "Contrato - Arrendamiento",
            "CONTRATO_OTRO": "Contrato - Otro",
        }

    @property
    def allowed_solicitud_types(self) -> List[SolicitudType]:
        return [SolicitudType.EXPEDICION, SolicitudType.RENOVACION]

    @property
    def requires_appointment(self) -> bool:
        return False  # No appointment needed for contract registration

    @property
    def menu_icon(self) -> str:
        return "FileSignature"

    @property
    def requires_agent_review(self) -> bool:
        return True

    @property
    def requires_nota_ingreso(self) -> bool:
        return False  # Direct payment via Mobile Money

    @property
    def allowed_sub_types(self) -> List[str]:
        """Legacy: list of sub_type strings."""
        return list(self.SUBTYPE_TO_SOLICITUD_MOTIVO.keys())

    # === Workflow Setup ===

    def _setup_workflow(self) -> None:
        """
        Setup complete contract registration workflow.

        Steps:
        0. select_type - Solicitud type (REGISTRO_NUEVO/ADENDA/PRORROGA/CESION/RESCISION)
        1. select_contract_type - Contract type (conditional: REGISTRO_NUEVO only)
        2. upload_documents - All documents on one page
        3. form_review_1 - Contractor identification (1/3)
        4. form_review_2 - Contract details + Contratante + Vigencia (2/3)
        5. form_review_3 - Financial data (3/3)
        6. payment - Mobile Money payment (0.5% of contract value)
        7. confirmation - Final summary
        """

        # === Step 0: Solicitud Type Selection ===
        self.add_step(WorkflowStep(
            step_number=0,
            step_id="select_type",
            step_type=StepType.SELECTION,
            title_es="Tipo de Solicitud",
            description_es="Seleccione el tipo de trámite de registro de contrato",
            config={
                "selection_type": "sub_type",
                "options": [
                    {
                        "value": "REGISTRO_NUEVO",
                        "label_es": "Registro de Nuevo Contrato",
                        "description_es": "Registrar un nuevo contrato comercial ante la ONRC",
                        "icon": "file-plus"
                    },
                    {
                        "value": "ADENDA",
                        "label_es": "Adenda / Modificación",
                        "description_es": "Registrar una modificación o avenant a un contrato ya registrado",
                        "icon": "file-edit"
                    },
                    {
                        "value": "PRORROGA",
                        "label_es": "Prórroga",
                        "description_es": "Registrar la extensión de duración de un contrato existente",
                        "icon": "calendar-plus"
                    },
                    {
                        "value": "CESION",
                        "label_es": "Cesión de Contrato",
                        "description_es": "Registrar la transferencia de un contrato a un tercero",
                        "icon": "arrow-right-left"
                    },
                    {
                        "value": "RESCISION",
                        "label_es": "Rescisión / Resolución",
                        "description_es": "Registrar la terminación anticipada de un contrato",
                        "icon": "file-x"
                    }
                ]
            }
        ))

        # === Step 1: Contract Type Selection (REGISTRO_NUEVO only) ===
        self.add_step(WorkflowStep(
            step_number=1,
            step_id="select_contract_type",
            step_type=StepType.SELECTION,
            title_es="Tipo de Contrato",
            description_es="Seleccione el tipo de contrato comercial",
            config={
                "selection_type": "contract_type",
                "condition": {"sub_type": "REGISTRO_NUEVO"},
                "options": [
                    {
                        "value": "OBRA",
                        "label_es": "Contrato de Obra",
                        "description_es": "Construcción, infraestructura, obras públicas",
                        "icon": "building"
                    },
                    {
                        "value": "SERVICIO",
                        "label_es": "Contrato de Servicio",
                        "description_es": "Prestación de servicios profesionales o técnicos",
                        "icon": "briefcase"
                    },
                    {
                        "value": "SUMINISTRO",
                        "label_es": "Contrato de Suministro",
                        "description_es": "Provisión de bienes, equipos o materiales",
                        "icon": "package"
                    },
                    {
                        "value": "CONCESION",
                        "label_es": "Contrato de Concesión",
                        "description_es": "Concesión de explotación de recursos o servicios públicos",
                        "icon": "landmark"
                    },
                    {
                        "value": "JOINT_VENTURE",
                        "label_es": "Joint-Venture / Asociación",
                        "description_es": "Acuerdo de asociación empresarial o consorcio",
                        "icon": "handshake"
                    },
                    {
                        "value": "ARRENDAMIENTO",
                        "label_es": "Contrato de Arrendamiento",
                        "description_es": "Arrendamiento de bienes inmuebles o equipos",
                        "icon": "key"
                    },
                    {
                        "value": "OTRO",
                        "label_es": "Otro Tipo",
                        "description_es": "Otro tipo de contrato comercial",
                        "icon": "file-text"
                    }
                ]
            }
        ))

        # === Step 2: Document Upload ===
        self.add_step(WorkflowStep(
            step_number=2,
            step_id="upload_documents",
            step_type=StepType.DOCUMENT_UPLOAD,
            title_es="Documentos Requeridos",
            description_es="Cargue los documentos necesarios para el registro del contrato",
            config={
                "dynamic_documents": True,
                "single_page": True,
                "includes_photo": False
            }
        ))

        # === Step 3: Form Review 1 - Identification Contratiste (1/3) ===
        self.add_step(WorkflowStep(
            step_number=3,
            step_id="form_review_1",
            step_type=StepType.FORM_REVIEW,
            title_es="Verificar Datos (1/3)",
            description_es="Verifique los datos del contratista extraídos de los documentos",
            config={
                "form_page": 1,
                "max_sections": 1,
                "sections": [
                    {
                        "id": "identificacion_contratista",
                        "title_es": "Identificación del Contratista",
                        "condition": None,  # Always visible
                        "fields": [
                            {
                                "key": "nif_contratista",
                                "label_es": "NIF del Contratista",
                                "type": "text",
                                "required": True,
                                "readonly": True,
                                "placeholder_es": "Ej: 12345AB-01"
                            },
                            {
                                "key": "denominacion_social",
                                "label_es": "Denominación Social",
                                "type": "text",
                                "required": True,
                                "readonly": True
                            },
                            {
                                "key": "autorizacion_tipo",
                                "label_es": "Tipo de Autorización NIF",
                                "type": "text",
                                "required": False,
                                "readonly": True,
                                "pdf_exclude": True
                            },
                            {
                                "key": "representante_legal",
                                "label_es": "Representante Legal",
                                "type": "text",
                                "required": True,
                                "readonly": False
                            },
                            {
                                "key": "identidad_representante_numero",
                                "label_es": "Nº de Identificación del Representante",
                                "type": "text",
                                "required": True,
                                "readonly": True
                            },
                            {
                                "key": "apellidos_representante",
                                "label_es": "Apellidos del Representante",
                                "type": "text",
                                "required": True,
                                "readonly": True,
                                "pdf_exclude": True
                            },
                            {
                                "key": "nombres_representante",
                                "label_es": "Nombres del Representante",
                                "type": "text",
                                "required": True,
                                "readonly": True,
                                "pdf_exclude": True
                            },
                            {
                                "key": "domicilio_social",
                                "label_es": "Domicilio Social",
                                "type": "text",
                                "required": False,
                                "readonly": False
                            },
                            {
                                "key": "telefono_contratista",
                                "label_es": "Teléfono de Contacto",
                                "type": "text",
                                "required": False,
                                "readonly": False,
                                "pdf_exclude": True
                            },
                            {
                                "key": "email_contratista",
                                "label_es": "Email de Contacto",
                                "type": "email",
                                "required": False,
                                "readonly": False,
                                "pdf_exclude": True
                            }
                        ]
                    }
                ]
            }
        ))

        # === Step 4: Form Review 2 - Contract Details + Contratante (2/3) ===
        self.add_step(WorkflowStep(
            step_number=4,
            step_id="form_review_2",
            step_type=StepType.FORM_REVIEW,
            title_es="Verificar Datos (2/3)",
            description_es="Verifique los datos del contrato y de la parte contratante",
            config={
                "form_page": 2,
                "max_sections": 4,
                "sections": [
                    # Section 1: Contract metadata
                    {
                        "id": "datos_contrato",
                        "title_es": "Datos del Contrato",
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
                                "key": "tipo_contrato",
                                "label_es": "Tipo de Contrato",
                                "type": "select",
                                "options": [t.value for t in ContratoType],
                                "required": True,
                                "readonly": False,
                                "condition": {"sub_type": "REGISTRO_NUEVO"}
                            },
                            {
                                "key": "numero_contrato",
                                "label_es": "Número / Referencia del Contrato",
                                "type": "text",
                                "required": False,
                                "readonly": False
                            },
                            {
                                "key": "titulo_contrato",
                                "label_es": "Título del Contrato",
                                "type": "text",
                                "required": False,
                                "readonly": False
                            },
                            {
                                "key": "numero_registro_original",
                                "label_es": "Nº de Registro ONRC del Contrato Original",
                                "type": "text",
                                "required": True,
                                "readonly": False,
                                "condition": {
                                    "OR": [
                                        {"sub_type": "ADENDA"},
                                        {"sub_type": "PRORROGA"},
                                        {"sub_type": "CESION"},
                                        {"sub_type": "RESCISION"}
                                    ]
                                },
                                "placeholder_es": "Nº de registro del contrato original"
                            },
                            {
                                "key": "fecha_firma",
                                "label_es": "Fecha de Firma",
                                "type": "date",
                                "required": True,
                                "readonly": False
                            },
                            {
                                "key": "lugar_firma",
                                "label_es": "Lugar de Firma",
                                "type": "text",
                                "required": False,
                                "readonly": False,
                                "pdf_exclude": True
                            },
                            {
                                "key": "objeto_contrato",
                                "label_es": "Objeto del Contrato",
                                "type": "textarea",
                                "required": True,
                                "readonly": False
                            },
                            {
                                "key": "sector",
                                "label_es": "Sector Económico",
                                "type": "select",
                                "options": [
                                    "PETROLEO_GAS", "CONSTRUCCION", "TELECOMUNICACIONES",
                                    "SERVICIOS_IT", "SERVICIOS_PROFESIONALES", "COMERCIO",
                                    "AGRICULTURA", "TURISMO", "TRANSPORTE", "ENERGIA",
                                    "MINERIA", "SALUD", "EDUCACION", "OTRO"
                                ],
                                "required": False,
                                "readonly": False
                            }
                        ]
                    },
                    # Section 2: Contratante (contracting party / client)
                    {
                        "id": "contratante",
                        "title_es": "Parte Contratante",
                        "condition": None,  # Always visible
                        "fields": [
                            {
                                "key": "tipo_entidad_contratante",
                                "label_es": "Tipo de Entidad",
                                "type": "select",
                                "options": [
                                    "GOBIERNO", "MINISTERIO", "EMPRESA_PUBLICA",
                                    "EMPRESA_PRIVADA", "PERSONA_FISICA",
                                    "ORGANISMO_INTERNACIONAL"
                                ],
                                "required": True,
                                "readonly": False
                            },
                            {
                                "key": "nombre_contratante",
                                "label_es": "Nombre / Razón Social",
                                "type": "text",
                                "required": True,
                                "readonly": False
                            },
                            {
                                "key": "representante_contratante",
                                "label_es": "Representante",
                                "type": "text",
                                "required": False,
                                "readonly": False
                            },
                            {
                                "key": "cargo_representante_contratante",
                                "label_es": "Cargo del Representante",
                                "type": "text",
                                "required": False,
                                "readonly": False,
                                "placeholder_es": "Ej: Ministro, Director General...",
                                "pdf_exclude": True
                            },
                            {
                                "key": "nif_contratante",
                                "label_es": "NIF de la Entidad Contratante",
                                "type": "text",
                                "required": False,
                                "readonly": False
                            }
                        ]
                    },
                    # Section 3: Vigencia (validity/duration)
                    {
                        "id": "vigencia",
                        "title_es": "Vigencia del Contrato",
                        "condition": None,  # Always visible
                        "fields": [
                            {
                                "key": "fecha_inicio",
                                "label_es": "Fecha de Inicio",
                                "type": "date",
                                "required": False,
                                "readonly": False
                            },
                            {
                                "key": "fecha_fin",
                                "label_es": "Fecha de Finalización",
                                "type": "date",
                                "required": False,
                                "readonly": False
                            },
                            {
                                "key": "duracion_meses",
                                "label_es": "Duración (meses)",
                                "type": "number",
                                "required": False,
                                "readonly": False
                            },
                            {
                                "key": "renovable",
                                "label_es": "¿Renovable?",
                                "type": "select",
                                "options": ["SI", "NO"],
                                "required": False,
                                "readonly": False
                            }
                        ]
                    },
                    # Section 4: Cesion details (CESION only)
                    {
                        "id": "cesion",
                        "title_es": "Datos de la Cesión",
                        "condition": {"sub_type": "CESION"},
                        "fields": [
                            {
                                "key": "cesionario_nombre",
                                "label_es": "Nombre del Cesionario (nuevo titular)",
                                "type": "text",
                                "required": True,
                                "readonly": False
                            },
                            {
                                "key": "cesionario_nif",
                                "label_es": "NIF del Cesionario",
                                "type": "text",
                                "required": True,
                                "readonly": False,
                                "placeholder_es": "Ej: 12345AB-01"
                            }
                        ]
                    }
                ]
            }
        ))

        # === Step 5: Form Review 3 - Financial Data (3/3) ===
        self.add_step(WorkflowStep(
            step_number=5,
            step_id="form_review_3",
            step_type=StepType.FORM_REVIEW,
            title_es="Verificar Datos (3/3)",
            description_es="Verifique el valor del contrato (extraído del documento)",
            config={
                "form_page": 3,
                "max_sections": 1,
                "sections": [
                    {
                        "id": "valor_contrato",
                        "title_es": "Valor del Contrato",
                        "condition": None,  # Always visible
                        "fields": [
                            {
                                "key": "monto_total",
                                "label_es": "Monto Total del Contrato",
                                "type": "number",
                                "required": True,
                                "readonly": False,
                                "help_es": "Valor extraído del contrato. Verifique y corrija si es necesario."
                            },
                            {
                                "key": "moneda",
                                "label_es": "Moneda",
                                "type": "select",
                                "options": ["XAF", "EUR", "USD"],
                                "required": True,
                                "readonly": False
                            },
                            {
                                "key": "monto_en_letras",
                                "label_es": "Monto en Letras (verificación)",
                                "type": "text",
                                "required": False,
                                "readonly": True,
                                "pdf_exclude": True,
                                "help_es": "Extraído del contrato para verificación cruzada"
                            },
                            {
                                "key": "incluye_iva",
                                "label_es": "¿Incluye IVA?",
                                "type": "select",
                                "options": ["SI", "NO", "NO_APLICA"],
                                "required": False,
                                "readonly": False
                            }
                        ]
                    }
                ]
            }
        ))

        # === Step 6: Payment ===
        self.add_step(WorkflowStep(
            step_number=6,
            step_id="payment",
            step_type=StepType.PAYMENT,
            title_es="Pago de Tasas de Registro",
            description_es="Tasa de registro: 0.5% del valor del contrato",
            config={
                "currency": "XAF",
                "show_breakdown": True,
                "dynamic_tariff": True,
                "tariff_note_es": "Tarifa de registro ONRC: 0.5% del valor del contrato en XAF"
            }
        ))

        # === Step 7: Confirmation ===
        self.add_step(WorkflowStep(
            step_number=7,
            step_id="confirmation",
            step_type=StepType.CONFIRMATION,
            title_es="Confirmación",
            description_es="Su solicitud de registro ha sido completada",
            config={
                "show_summary": True,
                "show_payment": True,
                "allow_download_receipt": True,
                "next_steps_es": [
                    "Su dossier será examinado por un agente de la ONRC",
                    "El agente verificará el contrato y los documentos originales",
                    "Recibirá una notificación cuando el registro esté completo",
                    "En caso de observaciones, el agente le contactará para correcciones"
                ]
            }
        ))

        # === Setup Tariffs ===
        self._setup_tariffs()

    def _setup_tariffs(self) -> None:
        """
        Setup tariff configuration for contract registration.

        Base: 0.5% of contract value in XAF.

        Supplements:
        - TIMBRE_FISCAL: 500 XAF per page of contract (Ley de Tasas Fiscales)
          quantity=1 by default, updated dynamically via get_tariff_breakdown()
          based on actual number of contract pages.
        - CEDULA_REGISTRO: 5,000 XAF fixed fee per registration (quantity=0,
          set quantity=1 to activate).
        """
        supplements = [
            SupplementDefinition(
                code="TIMBRE_FISCAL",
                name_es="Timbre Fiscal",
                unit_price=500,
                quantity=1,         # Updated dynamically per contract pages
                is_required=True
            ),
            SupplementDefinition(
                code="CEDULA_REGISTRO",
                name_es="Cédula de Registro",
                unit_price=5000,
                quantity=0,         # Set to 1 to activate
                is_required=True
            ),
        ]

        self.set_tariff_config(TariffConfig(
            tariff_type=TariffType.PERCENTAGE,
            percentage=0.5,     # 0.5% of contract value
            currency="XAF",
            supplements=supplements
        ))

    # === Document Requirements ===

    def get_document_requirements(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None
    ) -> List[DocumentRequirement]:
        """
        Get document requirements for contract registration.

        Philosophy: All documents listed, most non-mandatory.
        When regulations evolve, flip is_required=True.

        Document Matrix:
        | Document                    | REGISTRO | ADENDA | PRORROGA | CESION | RESCISION | Required |
        |-----------------------------|----------|--------|----------|--------|-----------|----------|
        | Contrato                    | ✅       | ✅     | ✅       | ✅     | ✅        | YES      |
        | Certificado NIF             | ✅       | ✅     | ✅       | ✅     | ✅        | YES      |
        | DIP Representante           | ✅       | ✅     | ✅       | ✅     | ✅        | YES      |
        | Escritura Constitución      | ✅       | ✅     | ✅       | ✅     | ✅        | no*      |
        | Certificado Registro VUE    | ✅       | ✅     | ✅       | ✅     | ✅        | no*      |
        | Poder Notarial              | ✅       | ✅     | ✅       | ✅     | ✅        | no*      |
        | Licencia Comercio Municipal | ✅       | -      | -        | -      | -         | no*      |
        | Permiso Construcción        | OBRA     | -      | -        | -      | -         | YES      |
        | Autorizacion Gubernativa    | CONC     | -      | -        | -      | -         | YES      |
        | Acuerdo Joint-Venture       | JV       | -      | -        | -      | -         | no*      |
        | Certificado Registro ONRC   | -        | ✅     | ✅       | ✅     | ✅        | YES      |
        | Acta Adjudicación (GOB)     | GOB      | GOB    | -        | -      | -         | no*      |
        | Visa Control Financiero     | GOB      | GOB    | -        | -      | -         | no*      |

        *no = listed but non-mandatory (progressive enforcement)
        """
        requirements = []
        sub_type = None
        contract_type = None

        if context:
            sub_type = context.sub_type
            contract_type = context.form_data.get("contract_type") if context.form_data else None

        if not sub_type:
            sub_type = "REGISTRO_NUEVO" if solicitud_type == SolicitudType.EXPEDICION else "ADENDA"

        is_modification = sub_type in ["ADENDA", "PRORROGA", "CESION", "RESCISION"]

        # === 1. Contract document - ALWAYS REQUIRED ===
        instructions = "Escanee todas las páginas del contrato firmado por ambas partes"
        if is_modification:
            instructions = f"Escanee el documento de {sub_type.lower()} firmado por ambas partes"

        requirements.append(DocumentRequirement(
            document_code="contrato",
            document_name_es="Contrato Comercial" if not is_modification else f"Documento de {sub_type.title()}",
            schema_key="CONTRATO_ONRC_GQ_V1",
            is_required=True,
            display_order=1,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es=instructions,
            accepted_formats=["pdf", "jpg", "jpeg", "png"]
        ))

        # === 2. NIF Certificate - ALWAYS REQUIRED ===
        requirements.append(DocumentRequirement(
            document_code="certificado_nif",
            document_name_es="Certificado NIF del Contratista",
            schema_key="CERTIFICADO_NIF_GQ_V1",
            is_required=True,
            display_order=2,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es="Certificado NIF vigente de la empresa contratista"
        ))

        # === 3. Identity of legal representative - ALWAYS REQUIRED ===
        # DIP (citizens), NIE/Permiso Residencia (foreign residents), or international passport
        requirements.append(DocumentRequirement(
            document_code="identidad_representante",
            document_name_es="Documento de Identidad del Representante Legal",
            schema_key="DIP_GQ_V2",
            is_required=True,
            display_order=3,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es=(
                "DIP, Permiso de Residencia o Pasaporte en vigor del representante legal "
                "de la empresa contratista. Escanee ambas caras del documento."
            ),
            faces_required=["recto", "verso"],
            config={
                "accepted_schemas": [
                    "DIP_GQ_V2",
                    "PERMISO_RESIDENCIA_GQ_V1",
                    "PASAPORTE_INTERNATIONAL_V1",
                ],
            },
        ))

        # === 4. Escritura de Constitución - LISTED, NOT REQUIRED ===
        requirements.append(DocumentRequirement(
            document_code="escritura_constitucion",
            document_name_es="Escritura de Constitución",
            schema_key="ESCRITURA_CONSTITUCION_GQ_V1",
            is_required=False,
            display_order=4,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es="Escritura de constitución de la empresa (si disponible)"
        ))

        # === 5. Certificado Registro VUE - LISTED, NOT REQUIRED ===
        requirements.append(DocumentRequirement(
            document_code="certificado_registro_vue",
            document_name_es="Certificado de Registro VUE",
            schema_key="CERTIFICADO_REGISTRO_VUE_GQ_V1",
            is_required=False,
            display_order=5,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es="Certificado de registro en la Ventanilla Única Empresarial (si disponible)"
        ))

        # === 6. Poder Notarial - LISTED, NOT REQUIRED ===
        requirements.append(DocumentRequirement(
            document_code="poder_notarial",
            document_name_es="Poder Notarial",
            is_required=False,
            display_order=6,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es="Poder notarial si el firmante no es el representante legal inscrito",
            config={"best_effort_extraction": True}
        ))

        # === 7. Licencia Comercio Municipal - LISTED, NOT REQUIRED (REGISTRO_NUEVO) ===
        if not is_modification:
            requirements.append(DocumentRequirement(
                document_code="licencia_comercio",
                document_name_es="Licencia de Comercio Municipal",
                schema_key="LICENCIA_COMERCIO_MUNICIPAL_GQ_V1",
                is_required=False,
                display_order=7,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["REGISTRO_NUEVO"]},
                instructions_es="Licencia municipal de comercio vigente (si disponible)"
            ))

        # === Conditional documents by contract type (REGISTRO_NUEVO) ===

        # Permiso Construcción - REQUIRED for OBRA
        if not is_modification and contract_type == "OBRA":
            requirements.append(DocumentRequirement(
                document_code="permiso_construccion",
                document_name_es="Permiso de Construcción",
                is_required=True,
                display_order=8,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"contract_types": ["OBRA"]},
                instructions_es="Permiso de construcción vigente emitido por la autoridad competente",
                config={"best_effort_extraction": True}
            ))

        # Autorización Gubernativa - REQUIRED for CONCESION
        if not is_modification and contract_type == "CONCESION":
            requirements.append(DocumentRequirement(
                document_code="autorizacion_gubernativa",
                document_name_es="Autorización Gubernativa de Concesión",
                schema_key="AUTORIZACION_GUBERNATIVA_GQ_V1",
                is_required=True,
                display_order=8,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"contract_types": ["CONCESION"]},
                instructions_es="Autorización gubernativa que otorga la concesión"
            ))

        # Acuerdo JV - LISTED, NOT REQUIRED for JOINT_VENTURE
        if not is_modification and contract_type == "JOINT_VENTURE":
            requirements.append(DocumentRequirement(
                document_code="acuerdo_jv",
                document_name_es="Acuerdo de Joint-Venture",
                is_required=False,
                display_order=8,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"contract_types": ["JOINT_VENTURE"]},
                instructions_es="Acuerdo constitutivo del joint-venture (si disponible)",
                config={"best_effort_extraction": True}
            ))

        # === Certificado de Registro ONRC original (modifications) ===
        if is_modification:
            requirements.append(DocumentRequirement(
                document_code="certificado_registro_onrc",
                document_name_es="Certificado de Registro ONRC del Contrato Original",
                is_required=True,
                display_order=8,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["ADENDA", "PRORROGA", "CESION", "RESCISION"]},
                instructions_es="Certificado de registro ONRC del contrato original que se modifica",
                config={"best_effort_extraction": True}
            ))

        # === Government-specific documents (non-mandatory, non-blocking) ===
        # Listed for GOBIERNO/MINISTERIO/EMPRESA_PUBLICA as contratante
        requirements.append(DocumentRequirement(
            document_code="acta_adjudicacion",
            document_name_es="Acta de Adjudicación / Resolución",
            is_required=False,
            display_order=20,
            condition_type=DocumentConditionType.CUSTOM,
            condition_value={"contratante_types": ["GOBIERNO", "MINISTERIO", "EMPRESA_PUBLICA"]},
            instructions_es="Resolución o acta de adjudicación del contrato público (si contratante es entidad gubernamental)",
            config={"best_effort_extraction": True}
        ))

        requirements.append(DocumentRequirement(
            document_code="visa_control_financiero",
            document_name_es="Visa de Control Financiero",
            is_required=False,
            display_order=21,
            condition_type=DocumentConditionType.CUSTOM,
            condition_value={"contratante_types": ["GOBIERNO", "MINISTERIO", "EMPRESA_PUBLICA"]},
            instructions_es="Visa del control financiero del presupuesto (si contratante es entidad gubernamental)",
            config={"best_effort_extraction": True}
        ))

        return requirements

    # === Step Validation ===

    def validate_step(
        self,
        step_number: int,
        context: WorkflowContext
    ) -> List[ValidationResult]:
        """Validate form review steps with contract-specific business rules.

        Unique rules (not covered by SchemaValidationEngine or RiskAnalyzer):
        - nif_coherente_contrato: NIF on certificado_nif == NIF on contrato
        - registro_tardio: contract signed > 30 days ago (warning)
        - escritura_denominacion_coherente: denominacion social matches
        """
        from datetime import date, timedelta

        results = super().validate_step(step_number, context)

        step = self.get_step(step_number)
        if not step or step.step_type != StepType.FORM_REVIEW:
            return results

        # --- NIF coherence: certificado_nif.nif == contrato.nif_contratista ---
        nif_cert = context.get_extracted_field("certificado_nif", "empresa.nif")
        nif_contrato = context.get_extracted_field("contrato", "parte_contratista.nif_contratista")
        if nif_cert and nif_contrato and nif_cert != nif_contrato:
            results.append(ValidationResult(
                is_valid=False,
                rule_id="nif_coherente_contrato",
                severity="error",
                message_es=(
                    f"El NIF del certificado ({nif_cert}) no coincide "
                    f"con el NIF del contratista ({nif_contrato})."
                ),
            ))

        # --- Late registration: contract signed > 30 days ago ---
        fecha_firma_str = context.get_extracted_field("contrato", "documento.fecha_firma")
        if fecha_firma_str:
            try:
                from datetime import datetime as dt_cls
                for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                    try:
                        fecha_firma = dt_cls.strptime(str(fecha_firma_str), fmt).date()
                        break
                    except ValueError:
                        continue
                else:
                    fecha_firma = None
                if fecha_firma and fecha_firma < date.today() - timedelta(days=30):
                    results.append(ValidationResult(
                        is_valid=False,
                        rule_id="registro_tardio",
                        severity="warning",
                        message_es=(
                            "El contrato fue firmado hace más de 30 días. "
                            "Puede aplicarse una penalidad por registro tardío."
                        ),
                    ))
            except (ValueError, TypeError):
                pass

        # --- Escritura denomination coherence (cross-document) ---
        denom_escritura = context.get_extracted_field(
            "escritura_constitucion", "empresa.denominacion_social"
        )
        denom_nif = context.get_extracted_field(
            "certificado_nif", "empresa.denominacion_social"
        )
        if denom_escritura and denom_nif:
            # Normalize: uppercase, strip whitespace
            norm_esc = " ".join(denom_escritura.upper().split())
            norm_nif = " ".join(denom_nif.upper().split())
            if norm_esc != norm_nif:
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id="escritura_denominacion_coherente",
                    severity="warning",
                    message_es=(
                        "La denominación social de la escritura no coincide "
                        "con el certificado NIF."
                    ),
                ))

        return results

    # === Form Field Mapping ===

    def get_form_mapping(self, context: Optional[WorkflowContext] = None) -> Dict[str, str]:
        """
        Map extracted document data fields to form fields.

        Sources:
        - contrato (CONTRATO_ONRC_GQ_V1): contract details, value, parties
        - certificado_nif (CERTIFICADO_NIF_GQ_V1): NIF, denomination, authorization
        - identidad_representante (DIP_GQ_V2 / PERMISO_RESIDENCIA_GQ_V1 / PASAPORTE_INTERNATIONAL_V1): representative identity
        """
        return {
            # === From NIF Certificate ===
            "nif_contratista": "certificado_nif.empresa.nif",
            "denominacion_social": "certificado_nif.empresa.denominacion_social",
            "autorizacion_tipo": "certificado_nif.empresa.autorizacion",

            # === From Identity Document (DIP/NIE/Pasaporte) ===
            # numero_dip is the default path; pipeline resolves to numero_nie/numero_pasaporte
            # based on the actual schema detected during OCR extraction
            "identidad_representante_numero": "identidad_representante.documento.numero_dip",
            "apellidos_representante": "identidad_representante.titular.apellidos",
            "nombres_representante": "identidad_representante.titular.nombres",

            # === From Contract - Contratista ===
            "representante_legal": "contrato.parte_contratista.representante_legal",
            "domicilio_social": "contrato.parte_contratista.domicilio_social",
            "telefono_contratista": "contrato.parte_contratista.telefono",
            "email_contratista": "contrato.parte_contratista.email",

            # === From Contract - Metadata ===
            "tipo_solicitud": "_form:sub_type",
            "tipo_contrato": "contrato.documento.tipo_contrato",
            "numero_contrato": "contrato.documento.numero_contrato",
            "titulo_contrato": "contrato.documento.titulo_contrato",
            "fecha_firma": "contrato.documento.fecha_firma",
            "lugar_firma": "contrato.documento.lugar_firma",
            "objeto_contrato": "contrato.objeto_contrato.descripcion",
            "sector": "contrato.objeto_contrato.sector",

            # === From Contract - Contratante ===
            "tipo_entidad_contratante": "contrato.parte_contratante.tipo_entidad",
            "nombre_contratante": "contrato.parte_contratante.nombre_entidad",
            "representante_contratante": "contrato.parte_contratante.representante",
            "cargo_representante_contratante": "contrato.parte_contratante.cargo_representante",
            "nif_contratante": "contrato.parte_contratante.nif_contratante",

            # === From Contract - Vigencia ===
            "fecha_inicio": "contrato.vigencia.fecha_inicio",
            "fecha_fin": "contrato.vigencia.fecha_fin",
            "duracion_meses": "contrato.vigencia.duracion_meses",
            "renovable": "contrato.vigencia.renovable",

            # === From Contract - Financial ===
            "monto_total": "contrato.valor_contrato.monto_total",
            "moneda": "contrato.valor_contrato.moneda",
            "monto_en_letras": "contrato.valor_contrato.monto_en_letras",
            "incluye_iva": "contrato.valor_contrato.incluye_iva",

            # === From Certificate of Registration (for modifications) ===
            "numero_registro_original": "certificado_registro_onrc.numero_registro",

            # === From Contract - Metadata (for tariff calculation) ===
            "numero_paginas": "contrato.metadatos_documento.numero_paginas",
        }

    # === Workflow Code Resolution ===

    def get_all_workflow_codes(self) -> List[WorkflowCode]:
        """All 7 contract type codes managed by this workflow."""
        return [
            WorkflowCode.CONTRATO_OBRA,
            WorkflowCode.CONTRATO_SERVICIO,
            WorkflowCode.CONTRATO_SUMINISTRO,
            WorkflowCode.CONTRATO_CONCESION,
            WorkflowCode.CONTRATO_JOINT_VENTURE,
            WorkflowCode.CONTRATO_ARRENDAMIENTO,
            WorkflowCode.CONTRATO_OTRO,
        ]

    # === Tariff Calculation ===

    def calculate_tariff(self, context: WorkflowContext, value: float = None) -> int:
        """
        Calculate tariff based on contract value.

        Formula: monto_xaf × 0.5% + penalties + supplements
        - Minimum tariff: 50,000 XAF (controlled by MINIMUM_TARIFF_MULTIPLIER)
        - Late penalty: 10%/month after 30 days (controlled by PENALTY_MULTIPLIER)

        The value is extracted from the contract by Gemini (not declared by citizen).
        The agent can later set monto_validado_por_agente during review.
        """
        if not value and context.form_data:
            value = context.form_data.get("monto_total", 0)
            currency = context.form_data.get("moneda", "XAF")

            # Convert to XAF if needed
            rate = self.EXCHANGE_RATES.get(currency, 1)
            if currency != "XAF":
                value = value * rate

        if not value:
            return 0

        # Base tariff: 0.5%
        base = int(value * self.TARIFF_PERCENTAGE)

        # Minimum tariff
        minimum = int(self.MINIMUM_TARIFF_XAF * self.MINIMUM_TARIFF_MULTIPLIER)
        if minimum > 0 and base < minimum:
            base = minimum

        # Late registration penalty
        penalty = self._calculate_late_penalty(context, base)

        return base + penalty

    def _calculate_late_penalty(self, context: WorkflowContext, base_tariff: int) -> int:
        """
        Calculate late registration penalty.

        Rule: If contract signed > 30 days ago, apply 10%/month (max 100%).
        Controlled by PENALTY_MULTIPLIER (0 = off, 1 = on).

        Args:
            context: Workflow context with form_data containing fecha_firma
            base_tariff: Base tariff amount in XAF

        Returns:
            Penalty amount in XAF (0 if multiplier is 0 or within grace period)
        """
        if self.PENALTY_MULTIPLIER == 0:
            return 0

        from datetime import datetime, date

        fecha_firma_str = context.form_data.get("fecha_firma") if context.form_data else None
        if not fecha_firma_str:
            return 0

        try:
            if isinstance(fecha_firma_str, str):
                fecha_firma = datetime.strptime(fecha_firma_str, "%Y-%m-%d").date()
            else:
                fecha_firma = fecha_firma_str

            today = date.today()
            days_since = (today - fecha_firma).days

            if days_since <= self.REGISTRATION_DELAY_DAYS:
                return 0

            # Calculate months of delay (rounded up)
            months_late = max(1, (days_since - self.REGISTRATION_DELAY_DAYS + 29) // 30)

            # Penalty rate: 10% per month, max 100%
            penalty_rate = min(
                months_late * self.PENALTY_RATE_PER_MONTH,
                self.PENALTY_MAX_RATE
            )

            return int(base_tariff * penalty_rate * self.PENALTY_MULTIPLIER)

        except (ValueError, TypeError):
            return 0

    def get_tariff_breakdown(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None,
        base_description: str = ""
    ) -> Dict[str, Any]:
        """
        Get detailed tariff breakdown for payment display.

        Overrides PredefinedWorkflow.get_tariff_breakdown with contract-specific
        logic: percentage-based tariff + late penalties + timbre fiscal per page.

        The number of contract pages (numero_paginas) is extracted from the
        uploaded contract document and stored in form_data. The TIMBRE_FISCAL
        quantity is dynamically set based on this value.
        """
        monto = 0.0
        currency = "XAF"
        numero_paginas = 1

        if context and context.form_data:
            monto = context.form_data.get("monto_total", 0) or 0
            currency = context.form_data.get("moneda", "XAF")
            rate = self.EXCHANGE_RATES.get(currency, 1)
            if currency != "XAF":
                monto = monto * rate
            # Number of pages for timbre fiscal calculation
            numero_paginas = max(1, int(context.form_data.get("numero_paginas", 1) or 1))

        base_amount = int(monto * self.TARIFF_PERCENTAGE)
        minimum = int(self.MINIMUM_TARIFF_XAF * self.MINIMUM_TARIFF_MULTIPLIER)
        if minimum > 0 and base_amount < minimum:
            base_amount = minimum

        penalties_amount = self._calculate_late_penalty(context, base_amount) if context else 0

        # Build supplements with dynamic quantity for TIMBRE_FISCAL
        tariff_cfg = self.get_tariff_config()
        supplements_defs = tariff_cfg.supplements if tariff_cfg else []
        supplements = []
        for s in supplements_defs:
            quantity = numero_paginas if s.code == "TIMBRE_FISCAL" else s.quantity
            supplements.append({
                "code": s.code,
                "name_es": s.name_es,
                "unit_price": s.unit_price,
                "quantity": quantity,
                "subtotal": s.unit_price * quantity,
                "is_required": s.is_required
            })
        supplements_total = sum(s["subtotal"] for s in supplements)

        total_amount = base_amount + penalties_amount + supplements_total

        return {
            "base_amount": base_amount,
            "base_description": base_description or f"Tasa de registro de contrato ({solicitud_type})",
            "supplements": supplements,
            "supplements_total": supplements_total,
            "penalties_amount": penalties_amount,
            "penalty_reason": "Registro tardío (más de 30 días)" if penalties_amount > 0 else None,
            "total_amount": total_amount,
            "currency": tariff_cfg.currency if tariff_cfg else "XAF",
            "tariff_type": tariff_cfg.tariff_type.value if tariff_cfg else "percentage_based",
            "workflow_code": self.workflow_code.value,
            "solicitud_type": solicitud_type.value if hasattr(solicitud_type, 'value') else str(solicitud_type),
            # Contract-specific extras
            "monto_contrato_xaf": int(monto),
            "moneda_original": currency,
            "tasa_porcentaje": "0.5%",
            "minimum_applied": minimum > 0 and base_amount == minimum,
            "numero_paginas": numero_paginas,
        }

    # === Legacy Compatibility ===

    def get_document_requirements_legacy(
        self,
        sub_type: str,
        context: Optional[WorkflowContext] = None
    ) -> List[DocumentRequirement]:
        """
        Legacy method for backwards compatibility.
        Converts sub_type string to SolicitudType.
        """
        solicitud_motivo = self.SUBTYPE_TO_SOLICITUD_MOTIVO.get(sub_type)
        if solicitud_motivo:
            solicitud_type, _ = solicitud_motivo
            return self.get_document_requirements(solicitud_type, None, context)
        return self.get_document_requirements(SolicitudType.EXPEDICION, None, context)


# =============================================================================
# REGISTRATION
# =============================================================================

def register_contrato_workflow():
    """Register the contract workflow with the workflow engine."""
    from ..services.workflow_engine import workflow_engine

    workflow = ContratoWorkflow()
    workflow_engine.register_workflow(workflow)


# Singleton instance
_contrato_workflow: Optional[ContratoWorkflow] = None


def get_contrato_workflow() -> ContratoWorkflow:
    """Get the singleton ContratoWorkflow instance."""
    global _contrato_workflow
    if _contrato_workflow is None:
        _contrato_workflow = ContratoWorkflow()
    return _contrato_workflow
