"""
TramitesVisadoWorkflow v2.2 - Comprehensive visa services for foreigners in GQ.

Migrated from ProrrogaVisadoWorkflow v2.1 to handle 4 service types.
ALIGNED WITH Orden Ministerial 01/2021, Art. 3 Section B.

4 service sub_types:
  1. PRORROGA: Extension of LIMITADO visa, 1 month fixed, 20 000 XAF
  2. ALTERNATIVO: Multi-entry visa, 3/6/12/24 months, tiered pricing
  3. PERMANENCIA: Temporary residence permit, 50 000 XAF/month
  4. SALIDA_VENCIDO: Overstayed visa exit penalty, 30 000 XAF/month (auto-calculated)

Shared requirements (all types):
  a) Instancia de solicitud
  b) Pasaporte con visado y sello de entrada (3 pages: data, visa, stamp)
  c) Pasaporte válido (validated by validate_step from OCR)

Type-specific validation:
  - PRORROGA: visa LIMITADO only + must be in vigor
  - ALTERNATIVO: any type except transit + must be in vigor
  - PERMANENCIA: any type except transit + must be in vigor
  - SALIDA_VENCIDO: any type except transit + must be EXPIRED (inverted)

Documents (4):
  1. instancia_solicitud — formulaire (no OCR)
  2. pasaporte — PASAPORTE_INTERNATIONAL_V1 (data page)
  3. visado_entrada — VISADO_GQ_V1 (visa sticker/alternativo page)
  4. sello_entrada — SELLO_ENTRADA_GQ_V1 (entry stamp page)

Real document reference: Documentations/workflow/menu/residencia/visado_prorogacion.png
  Left page: VISADO ALTERNATIVO (input — what the applicant presents)
  Right page: PERMANENCIA (output — what gets issued after approval)

Entity: EXTRANJERIA (Dirección General de Extranjería y Fronteras)
No Nota de Ingreso, No appointment.

@version 2.2
@date 2026-02-08
@legal Orden Ministerial 01/2021 de fecha 02 de diciembre, Art. 3 Section B
"""
import math
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

from ..workflow_interface import (
    PredefinedWorkflow,
    WorkflowStep,
    WorkflowContext,
    DocumentRequirement,
    TariffConfig,
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
# Constants
# =============================================================================

# Transit visas are never eligible for any visa service
_VISADO_TIPOS_TRANSIT = ("TRANSITO", "DOBLE_TRANSITO")

# Tiered pricing for Visado Alternativo (duration in months → XAF)
_ALTERNATIVO_TIERS: Dict[int, int] = {
    3: 20000,
    6: 40000,
    12: 80000,
    24: 600000,
}


class TramitesVisadoWorkflow(PredefinedWorkflow):
    """
    Comprehensive visa services workflow for foreigners in Equatorial Guinea.

    AUTONOMOUS: Defines ALL logic internally, aligned with Orden Ministerial 01/2021 Art. 3.B.

    4 sub_types via SELECTION step:
      PRORROGA — Visa extension (LIMITADO only, 1 month, 20K XAF)
      ALTERNATIVO — Multi-entry visa (3/6/12/24 months, tiered pricing)
      PERMANENCIA — Temporary residence (50K XAF/month)
      SALIDA_VENCIDO — Overstayed visa exit penalty (30K XAF/month, auto-calculated)

    Steps (5):
    0. select_type: Choose service type + duration (conditional)
    1. upload_documents: Passport data page + visa page + entry stamp + instancia
    2. form_review_1: OCR data (passport, visa, stamp)
    3. payment: Computed tariff based on type + duration
    4. confirmation: Summary with agent checklist

    Validate_step rules (5):
    1. pasaporte_valido: Passport not expired (Art. 3.B.c)
    2. nacionalidad_extranjero: Must not be Ecuatoguinean
    3. visado_tipo_elegible: Transit visas not eligible / PRORROGA requires LIMITADO
    4. visado_en_vigor: Visa in vigor (PRORROGA/ALTERNATIVO/PERMANENCIA)
       OR visado_expirado: Visa expired (SALIDA_VENCIDO — inverted)
    5. coherencia_tipo: Sub_type coherent with visa state
    """

    # === Properties ===

    @property
    def workflow_code(self) -> WorkflowCode:
        return WorkflowCode.PRORROGA_VISADO

    def get_all_workflow_codes(self) -> List[WorkflowCode]:
        """Register under all 4 visa service codes."""
        return [
            WorkflowCode.PRORROGA_VISADO,
            WorkflowCode.VISADO_ALTERNATIVO,
            WorkflowCode.PERMANENCIA_EXTRANJERIA,
            WorkflowCode.SALIDA_VISADO_VENCIDO,
        ]

    @property
    def category(self) -> WorkflowCategory:
        return WorkflowCategory.EXTRANJERIA

    @property
    def entity_code(self) -> EntityCode:
        return EntityCode.EXTRANJERIA

    @property
    def service_name_es(self) -> str:
        return "Trámites de Visado"

    def get_subtype_display_names(self) -> Dict[str, str]:
        return {
            "PRORROGA_VISADO": "Prórroga de Visado",
            "VISADO_ALTERNATIVO": "Visado Alternativo",
            "PERMANENCIA_EXTRANJERIA": "Permanencia de Extranjería",
            "SALIDA_VISADO_VENCIDO": "Salida con Visado Vencido",
        }

    @property
    def allowed_solicitud_types(self) -> List[SolicitudType]:
        return [SolicitudType.EXPEDICION]

    @property
    def allowed_sub_types(self) -> List[str]:
        return ["PRORROGA", "ALTERNATIVO", "PERMANENCIA", "SALIDA_VENCIDO"]

    @property
    def requires_appointment(self) -> bool:
        return False

    @property
    def menu_icon(self) -> str:
        return "Globe"

    @property
    def menu_group(self) -> str:
        return "VISADO"

    @property
    def menu_title_key(self) -> str:
        return "agent.nav.visas"

    @property
    def _subtype_code_aliases(self) -> Dict[str, WorkflowCode]:
        """SALIDA_VENCIDO key doesn't appear as substring in SALIDA_VISADO_VENCIDO."""
        return {
            "SALIDA_VENCIDO": WorkflowCode.SALIDA_VISADO_VENCIDO,
        }

    @property
    def requires_agent_review(self) -> bool:
        return True

    @property
    def requires_nota_ingreso(self) -> bool:
        return False

    # === Setup ===

    def _setup_workflow(self) -> None:
        self._setup_steps()
        self._setup_tariffs()

    def _setup_steps(self) -> None:
        # Step 0: SELECTION — Choose service type + conditional duration
        self.add_step(WorkflowStep(
            step_number=0,
            step_id="select_type",
            step_type=StepType.SELECTION,
            title_es="Tipo de Trámite de Visado",
            description_es="Seleccione el tipo de trámite que desea realizar",
            config={
                "sections": [
                    # Section 1: Service type
                    {
                        "id": "tipo_tramite",
                        "title_es": "Tipo de trámite",
                        "fields": [
                            {
                                "key": "sub_type",
                                "type": "select",
                                "label_es": "Seleccione el trámite",
                                "required": True,
                                "options": [
                                    {
                                        "value": "PRORROGA",
                                        "label_es": "Prórroga de visado de entrada (1 mes)",
                                        "description_es": (
                                            "Extensión de 1 mes para visa LIMITADO "
                                            "aún en vigor. Tarifa: 20 000 XAF."
                                        ),
                                    },
                                    {
                                        "value": "ALTERNATIVO",
                                        "label_es": "Visado Alternativo",
                                        "description_es": (
                                            "Visa de múltiples entradas. "
                                            "Duración y tarifa según selección."
                                        ),
                                    },
                                    {
                                        "value": "PERMANENCIA",
                                        "label_es": "Permanencia",
                                        "description_es": (
                                            "Autorización de permanencia temporal. "
                                            "Tarifa: 50 000 XAF por mes."
                                        ),
                                    },
                                    {
                                        "value": "SALIDA_VENCIDO",
                                        "label_es": "Salida con visado vencido (penalidad)",
                                        "description_es": (
                                            "Regularización para salir del país con "
                                            "visa expirada. Penalidad: 30 000 XAF por "
                                            "mes de estancia irregular. El período se "
                                            "calcula automáticamente."
                                        ),
                                    },
                                ],
                            },
                        ],
                    },
                    # Section 2: Duration for ALTERNATIVO (tiered)
                    {
                        "id": "duracion_alternativo",
                        "title_es": "Duración del Visado Alternativo",
                        "show_when": {"sub_type": "ALTERNATIVO"},
                        "fields": [
                            {
                                "key": "duracion_meses",
                                "type": "select",
                                "label_es": "Duración solicitada",
                                "required": True,
                                "options": [
                                    {"value": "3", "label_es": "3 meses — 20 000 XAF"},
                                    {"value": "6", "label_es": "6 meses — 40 000 XAF"},
                                    {"value": "12", "label_es": "12 meses — 80 000 XAF"},
                                    {"value": "24", "label_es": "24 meses — 600 000 XAF"},
                                ],
                            },
                        ],
                    },
                    # Section 3: Duration for PERMANENCIA (per month)
                    {
                        "id": "duracion_permanencia",
                        "title_es": "Duración de Permanencia",
                        "show_when": {"sub_type": "PERMANENCIA"},
                        "fields": [
                            {
                                "key": "duracion_meses",
                                "type": "number",
                                "label_es": "Número de meses solicitados",
                                "required": True,
                                "min": 1,
                                "max": 12,
                                "help_text_es": "Tarifa: 50 000 XAF por mes",
                            },
                        ],
                    },
                ],
            }
        ))

        # Step 1: Upload documents (4 documents — same for all types)
        self.add_step(WorkflowStep(
            step_number=1,
            step_id="upload_documents",
            step_type=StepType.DOCUMENT_UPLOAD,
            title_es="Documentos Requeridos",
            description_es=(
                "Cargue los documentos requeridos: instancia de solicitud, "
                "página de datos del pasaporte, página del visado, y "
                "página con el sello de entrada"
            ),
            config={
                "dynamic_documents": True,
                "max_file_size_mb": 10,
            }
        ))

        # Step 2: Form Review — Passport + Visa + Entry Stamp (OCR readonly)
        self.add_step(WorkflowStep(
            step_number=2,
            step_id="form_review_1",
            step_type=StepType.FORM_REVIEW,
            title_es="Datos del Pasaporte, Visado y Entrada",
            description_es="Verifique los datos extraídos de sus documentos",
            config={
                "sections": [
                    # Section 1: Passport data (OCR readonly)
                    {
                        "id": "datos_pasaporte",
                        "title_es": "Datos del Pasaporte",
                        "source_document": "pasaporte",
                        "fields": [
                            {"key": "numero_pasaporte", "label_es": "N° Pasaporte",
                             "type": "text", "required": True, "readonly": True},
                            {"key": "apellidos", "label_es": "Apellidos",
                             "type": "text", "required": True, "readonly": True},
                            {"key": "nombres", "label_es": "Nombres",
                             "type": "text", "required": True, "readonly": True},
                            {"key": "nacionalidad", "label_es": "Nacionalidad",
                             "type": "text", "required": True, "readonly": True},
                            {"key": "fecha_nacimiento", "label_es": "Fecha de Nacimiento",
                             "type": "date", "required": True, "readonly": True},
                            {"key": "fecha_expiracion_pasaporte",
                             "label_es": "Fecha de Expiración Pasaporte",
                             "type": "date", "required": True, "readonly": True},
                        ]
                    },
                    # Section 2: Visa data (OCR readonly from VISADO_GQ_V1)
                    {
                        "id": "datos_visado",
                        "title_es": "Datos del Visado",
                        "source_document": "visado_entrada",
                        "description_es": "Datos extraídos del visado de entrada",
                        "fields": [
                            {"key": "numero_visado", "label_es": "N° Visado",
                             "type": "text", "required": True, "readonly": True},
                            {"key": "tipo_visado", "label_es": "Tipo de Visado",
                             "type": "text", "required": True, "readonly": True,
                             "help_text_es": (
                                 "Tipo según el documento: ALTERNATIVO, LIMITADO, "
                                 "COLECTIVO, TRANSITO, etc."
                             )},
                            {"key": "duracion_dias", "label_es": "Duración Autorizada (días)",
                             "type": "number", "required": True, "readonly": True},
                            {"key": "numero_entradas", "label_es": "Entradas Autorizadas",
                             "type": "text", "required": True, "readonly": True},
                            {"key": "fecha_expedicion_visado",
                             "label_es": "Fecha de Expedición del Visado",
                             "type": "date", "required": True, "readonly": True},
                        ]
                    },
                    # Section 3: Entry stamp data (OCR readonly from SELLO_ENTRADA_GQ_V1)
                    {
                        "id": "datos_entrada",
                        "title_es": "Sello de Entrada",
                        "source_document": "sello_entrada",
                        "description_es": "Datos extraídos del sello de entrada al país",
                        "fields": [
                            {"key": "fecha_entrada", "label_es": "Fecha de Entrada al País",
                             "type": "date", "required": True, "readonly": True},
                            {"key": "puesto_fronterizo", "label_es": "Puesto Fronterizo",
                             "type": "text", "required": True, "readonly": True},
                        ]
                    },
                ]
            }
        ))

        # Step 3: Payment (computed tariff)
        self.add_step(WorkflowStep(
            step_number=3,
            step_id="payment",
            step_type=StepType.PAYMENT,
            title_es="Pago del Trámite",
            description_es="Pago de la tasa correspondiente al trámite de visado",
            config={
                "currency": "XAF",
                "payment_type": "computed",
            }
        ))

        # Step 4: Confirmation
        self.add_step(WorkflowStep(
            step_number=4,
            step_id="confirmation",
            step_type=StepType.CONFIRMATION,
            title_es="Confirmación y Envío",
            description_es="Verifique todos los datos antes de enviar su solicitud",
            config={
                "show_summary": True,
                "agent_checklist": [
                    {"id": "pasaporte_vigente", "label_es":
                     "He verificado que el pasaporte está vigente",
                     "required": True},
                    {"id": "visado_verificado", "label_es":
                     "He verificado el tipo y estado del visado según el trámite solicitado",
                     "required": True},
                    {"id": "sello_entrada_legal", "label_es":
                     "He verificado el sello de entrada por un puesto fronterizo oficial",
                     "required": True},
                    {"id": "no_ecuatoguineano", "label_es":
                     "He comprobado que el solicitante NO es ciudadano ecuatoguineano",
                     "required": True},
                    {"id": "tarifa_correcta", "label_es":
                     "He verificado que la tarifa corresponde al tipo de trámite y duración",
                     "required": True},
                ],
                "rejection_reasons": [
                    {"id": "pasaporte_expirado", "label_es":
                     "Pasaporte expirado"},
                    {"id": "visado_no_elegible", "label_es":
                     "Visado de tránsito — no elegible"},
                    {"id": "visado_estado_incorrecto", "label_es":
                     "Estado del visado incompatible con el trámite solicitado"},
                    {"id": "visado_tipo_incorrecto", "label_es":
                     "Tipo de visado incorrecto para prórroga (debe ser LIMITADO)"},
                    {"id": "sin_sello_entrada", "label_es":
                     "Sin sello de entrada oficial o sello ilegible"},
                    {"id": "ciudadano_ecuatoguineano", "label_es":
                     "Ciudadano ecuatoguineano — no requiere visado"},
                    {"id": "documentos_ilegibles", "label_es":
                     "Documentos ilegibles o incompletos"},
                    {"id": "otro", "label_es": "Otro (especificar)"},
                ],
            }
        ))

    def _setup_tariffs(self) -> None:
        """
        Tariff configuration — base config (actual computation in get_tariff override).

        Tariffs per sub_type:
          PRORROGA: 20 000 XAF (1 month, fixed)
          ALTERNATIVO: tiered {3m: 20K, 6m: 40K, 12m: 80K, 24m: 600K}
          PERMANENCIA: 50 000 XAF × months
          SALIDA_VENCIDO: 30 000 XAF × months of overstay (auto-calculated)
        """
        self.set_tariff_config(TariffConfig(
            tariff_type=TariffType.FIXED,
            fixed_amounts={
                "PRORROGA": 20000,          # 1 month, fixed
                "ALTERNATIVO": 80000,       # representative mid-tier (12 months)
                                            # tiered: 3m→20K, 6m→40K, 12m→80K, 24m→600K
                "PERMANENCIA": 50000,       # per month (default 1 month)
                "SALIDA_VENCIDO": 30000,    # per month of overstay (default 1 month)
            },
            currency="XAF",
        ))

    # === Document Requirements ===

    def get_document_requirements(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None,
    ) -> List[DocumentRequirement]:
        """
        Document requirements — same 4 documents for all sub_types.

        Orden Ministerial 01/2021 Art. 3 Section B:
        a) Instancia de solicitud
        b) Pasaporte — data page + visa page + entry stamp page
        """
        return [
            # Art. 3.B.a - Instancia de Solicitud
            DocumentRequirement(
                document_code="instancia_solicitud",
                document_name_es="Instancia de Solicitud",
                is_required=True,
                display_order=1,
                condition_type=DocumentConditionType.ALWAYS,
                instructions_es=(
                    "Instancia de solicitud dirigida al "
                    "Director General de Extranjería y Fronteras"
                ),
            ),
            # Art. 3.B.b - Pasaporte (data page)
            DocumentRequirement(
                document_code="pasaporte",
                document_name_es="Pasaporte - Página de Datos",
                schema_key="PASAPORTE_INTERNATIONAL_V1",
                is_required=True,
                display_order=2,
                condition_type=DocumentConditionType.ALWAYS,
                instructions_es=(
                    "Página de datos del pasaporte (foto, nombre, número). "
                    "Debe estar en vigor (Art. 3.B.c)."
                ),
                faces_required=["data_page"],
            ),
            # Art. 3.B.b - Visado de entrada (visa page)
            DocumentRequirement(
                document_code="visado_entrada",
                document_name_es="Visado de Entrada",
                schema_key="VISADO_GQ_V1",
                is_required=True,
                display_order=3,
                condition_type=DocumentConditionType.ALWAYS,
                instructions_es=(
                    "Página del pasaporte con el visado (sticker o alternativo)."
                ),
                faces_required=["visa_page"],
            ),
            # Art. 3.B.b - Sello de entrada (entry stamp page)
            DocumentRequirement(
                document_code="sello_entrada",
                document_name_es="Sello de Entrada",
                schema_key="SELLO_ENTRADA_GQ_V1",
                is_required=True,
                display_order=4,
                condition_type=DocumentConditionType.ALWAYS,
                instructions_es=(
                    "Página del pasaporte con el sello de entrada a Guinea Ecuatorial "
                    "del puesto fronterizo oficial (Art. 3.B.b)."
                ),
                faces_required=["stamp_page"],
            ),
        ]

    # === Form Mapping ===

    def get_form_mapping(
        self,
        context: Optional[WorkflowContext] = None,
    ) -> Dict[str, str]:
        """
        Map extracted OCR data to form fields.

        All fields are readonly OCR. No manual input fields in form_review
        (duration/type selection happens in SELECTION step 0).
        """
        return {
            # Passport (OCR readonly) — from PASAPORTE_INTERNATIONAL_V1
            "numero_pasaporte": "pasaporte.documento.numero_pasaporte",
            "apellidos": "pasaporte.titular.apellidos",
            "nombres": "pasaporte.titular.nombres",
            "nacionalidad": "pasaporte.titular.nacionalidad",
            "fecha_nacimiento": "pasaporte.titular.fecha_nacimiento",
            "fecha_expiracion_pasaporte": "pasaporte.documento.fecha_expiracion",
            # Visa (OCR readonly) — from VISADO_GQ_V1
            "numero_visado": "visado_entrada.documento.numero_visado",
            "tipo_visado": "visado_entrada.visado.tipo_visado",
            "duracion_dias": "visado_entrada.visado.duracion_dias",
            "numero_entradas": "visado_entrada.visado.numero_entradas",
            "fecha_expedicion_visado": "visado_entrada.documento.fecha_expedicion",
            # Entry stamp (OCR readonly) — from SELLO_ENTRADA_GQ_V1
            "fecha_entrada": "sello_entrada.ultimo_sello_entrada.fecha_entrada",
            "puesto_fronterizo": "sello_entrada.ultimo_sello_entrada.puesto_fronterizo",
        }

    # === Tariff Calculation ===

    def get_tariff(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None,
    ) -> int:
        """
        Compute tariff based on sub_type and duration.

        PRORROGA: 20 000 XAF (fixed, 1 month)
        ALTERNATIVO: tiered by duration {3: 20K, 6: 40K, 12: 80K, 24: 600K}
        PERMANENCIA: 50 000 × months
        SALIDA_VENCIDO: 30 000 × months_overstay (auto-calculated from OCR)
        """
        sub_type = self._resolve_sub_type(context)

        if sub_type == "PRORROGA":
            return 20000

        if sub_type == "ALTERNATIVO":
            duracion = self._get_duracion_meses(context, default=3)
            return _ALTERNATIVO_TIERS.get(duracion, 20000)

        if sub_type == "PERMANENCIA":
            meses = self._get_duracion_meses(context, default=1)
            return max(1, meses) * 50000

        if sub_type == "SALIDA_VENCIDO":
            meses_overstay = self._calculate_overstay_months(context)
            return max(1, meses_overstay) * 30000

        return 20000  # fallback

    def get_tariff_breakdown(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None,
        base_description: str = "",
    ) -> Dict[str, Any]:
        """
        Detailed tariff breakdown with sub_type-specific description.
        """
        sub_type = self._resolve_sub_type(context)
        base_amount = self.get_tariff(solicitud_type, motivo, context)

        # Build description based on sub_type
        if sub_type == "PRORROGA":
            description = "Prórroga de visado de entrada (1 mes)"
        elif sub_type == "ALTERNATIVO":
            duracion = self._get_duracion_meses(context, default=3)
            description = f"Visado Alternativo ({duracion} meses)"
        elif sub_type == "PERMANENCIA":
            meses = self._get_duracion_meses(context, default=1)
            description = f"Permanencia ({max(1, meses)} meses × 50 000 XAF)"
        elif sub_type == "SALIDA_VENCIDO":
            meses = self._calculate_overstay_months(context)
            description = (
                f"Salida con visado vencido — penalidad "
                f"({max(1, meses)} meses × 30 000 XAF)"
            )
        else:
            description = self.service_name_es

        config = self.get_tariff_config()
        return {
            "base_amount": base_amount,
            "base_description": base_description or description,
            "supplements": [],
            "supplements_total": 0,
            "penalties_amount": 0,
            "penalty_reason": None,
            "total_amount": base_amount,
            "currency": config.currency if config else "XAF",
            "tariff_type": config.tariff_type.value if config else "FIXED",
            "workflow_code": self.workflow_code.value,
            "solicitud_type": solicitud_type.value,
            "sub_type": sub_type,
        }

    # === Step Validation ===

    def validate_step(
        self,
        step_number: int,
        context: WorkflowContext,
    ) -> List[ValidationResult]:
        """
        Validate form review step — Orden Ministerial 01/2021 Art. 3.B.

        5 rules (all from OCR data):
        1. pasaporte_valido: Passport not expired (Art. 3.B.c) — all types
        2. nacionalidad_extranjero: Must be a foreigner — all types
        3. visado_tipo_elegible: Transit excluded; PRORROGA requires LIMITADO
        4. visado_en_vigor: Visa valid (PRORROGA/ALTERNATIVO/PERMANENCIA)
           OR visado_expirado: Visa expired (SALIDA_VENCIDO — inverted)
        5. coherencia_tipo: Sub_type coherent with visa state
        """
        results = super().validate_step(step_number, context)

        step = self.get_step(step_number)
        if not step:
            return results

        if step.step_id == "form_review_1":
            results.extend(self._validate_visa_conditions(context))

        return results

    def _validate_visa_conditions(
        self, context: WorkflowContext
    ) -> List[ValidationResult]:
        """Validate passport and visa conditions — all from OCR, branching by sub_type."""
        results: List[ValidationResult] = []
        sub_type = self._resolve_sub_type(context)

        # --- Rule 1: Passport must be valid (Art. 3.B.c) — all types ---
        fecha_exp_str = context.get_extracted_field(
            "pasaporte", "documento.fecha_expiracion"
        )
        if fecha_exp_str:
            fecha_exp = self._parse_date(str(fecha_exp_str))
            if fecha_exp and fecha_exp < datetime.today():
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id="pasaporte_valido",
                    severity="error",
                    message_es=(
                        "El pasaporte está expirado. Se requiere un pasaporte en vigor "
                        "para cualquier trámite de visado (Art. 3.B.c)."
                    ),
                    field_name="fecha_expiracion_pasaporte",
                ))

        # --- Rule 2: Must NOT be Ecuatoguinean — all types ---
        nacionalidad = context.get_extracted_field(
            "pasaporte", "titular.nacionalidad"
        )
        if nacionalidad:
            nac_upper = str(nacionalidad).strip().upper()
            if nac_upper in (
                "GNQ", "GUINEA ECUATORIAL", "ECUATOGUINEANO", "ECUATOGUINEANA"
            ):
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id="nacionalidad_extranjero",
                    severity="error",
                    message_es=(
                        "El solicitante es ciudadano ecuatoguineano. "
                        "Los ciudadanos de GQ no requieren visado."
                    ),
                    field_name="nacionalidad",
                ))

        # --- Rule 3: Visa type eligibility — depends on sub_type ---
        tipo_visado = context.get_extracted_field(
            "visado_entrada", "visado.tipo_visado"
        )
        if tipo_visado:
            tipo_str = str(tipo_visado).strip().upper()

            # 3a: Transit visas never eligible (all types)
            if tipo_str in _VISADO_TIPOS_TRANSIT:
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id="visado_tipo_elegible",
                    severity="error",
                    message_es=(
                        f"El visado es de tipo {tipo_str}. Los visados de tránsito "
                        "no son elegibles para ningún trámite de visado."
                    ),
                    field_name="tipo_visado",
                ))

            # 3b: PRORROGA requires LIMITADO specifically
            elif sub_type == "PRORROGA" and tipo_str != "LIMITADO":
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id="visado_tipo_prorroga",
                    severity="error",
                    message_es=(
                        f"La prórroga de visado de entrada solo es aplicable a "
                        f"visados de tipo LIMITADO. Su visado es de tipo {tipo_str}. "
                        "Si desea otra gestión, seleccione el trámite correspondiente."
                    ),
                    field_name="tipo_visado",
                ))

        # --- Rule 4: Visa validity — depends on sub_type ---
        fecha_exp_visado_str = context.get_extracted_field(
            "visado_entrada", "documento.fecha_expedicion"
        )
        duracion_dias_raw = context.get_extracted_field(
            "visado_entrada", "visado.duracion_dias"
        )
        if fecha_exp_visado_str and duracion_dias_raw:
            fecha_expedicion = self._parse_date(str(fecha_exp_visado_str))
            try:
                duracion_dias = int(duracion_dias_raw)
            except (ValueError, TypeError):
                duracion_dias = None

            if fecha_expedicion and duracion_dias:
                fecha_fin_visado = fecha_expedicion + timedelta(days=duracion_dias)
                visa_expired = fecha_fin_visado < datetime.today()

                if sub_type == "SALIDA_VENCIDO":
                    # INVERTED: visa MUST be expired for exit penalty
                    if not visa_expired:
                        results.append(ValidationResult(
                            is_valid=False,
                            rule_id="visado_debe_estar_expirado",
                            severity="error",
                            message_es=(
                                f"Su visado sigue en vigor (válido hasta aprox. "
                                f"{fecha_fin_visado.strftime('%d/%m/%Y')}). "
                                "La penalidad de salida solo aplica cuando el visado "
                                "está expirado. Si su visa es válida, no necesita "
                                "este trámite."
                            ),
                            field_name="duracion_dias",
                        ))
                    else:
                        # Info: show overstay period
                        days_overstay = (datetime.today() - fecha_fin_visado).days
                        meses = math.ceil(days_overstay / 30)
                        results.append(ValidationResult(
                            is_valid=True,
                            rule_id="overstay_info",
                            severity="info",
                            message_es=(
                                f"Período de estancia irregular: {days_overstay} días "
                                f"(~{meses} meses). Penalidad estimada: "
                                f"{max(1, meses) * 30000:,} XAF."
                            ),
                            field_name="duracion_dias",
                        ))
                else:
                    # NORMAL: visa must be in vigor for PRORROGA/ALTERNATIVO/PERMANENCIA
                    if visa_expired:
                        results.append(ValidationResult(
                            is_valid=False,
                            rule_id="visado_en_vigor",
                            severity="error",
                            message_es=(
                                f"El visado ha expirado (expedido "
                                f"{fecha_exp_visado_str}, duración {duracion_dias} "
                                f"días, vencido aprox. "
                                f"{fecha_fin_visado.strftime('%d/%m/%Y')}). "
                                "Se requiere un visado en vigor para este trámite. "
                                "Si necesita salir del país con visa vencida, "
                                "seleccione 'Salida con visado vencido'."
                            ),
                            field_name="duracion_dias",
                        ))

        return results

    # === Helper Methods ===

    def _resolve_sub_type(
        self, context: Optional[WorkflowContext] = None
    ) -> str:
        """
        Resolve sub_type from context.

        Priority: context.sub_type > fallback "PRORROGA"
        """
        if context:
            sub_type = context.sub_type
            if sub_type and sub_type in self.allowed_sub_types:
                return sub_type
        return "PRORROGA"

    def _get_duracion_meses(
        self, context: Optional[WorkflowContext], default: int = 1
    ) -> int:
        """Extract duracion_meses from form_data."""
        if context and context.form_data:
            raw = context.form_data.get("duracion_meses")
            if raw is not None:
                try:
                    return max(1, int(raw))
                except (ValueError, TypeError):
                    pass
        return default

    def _calculate_overstay_months(
        self, context: Optional[WorkflowContext]
    ) -> int:
        """
        Calculate months of visa overstay from OCR data.

        Uses: visado_entrada.documento.fecha_expedicion + visado.duracion_dias
        Returns: number of months (rounded up), minimum 1
        """
        if not context:
            return 1

        fecha_exp_str = context.get_extracted_field(
            "visado_entrada", "documento.fecha_expedicion"
        )
        duracion_raw = context.get_extracted_field(
            "visado_entrada", "visado.duracion_dias"
        )

        if not (fecha_exp_str and duracion_raw):
            return 1

        fecha_exp = self._parse_date(str(fecha_exp_str))
        try:
            duracion = int(duracion_raw)
        except (ValueError, TypeError):
            return 1

        if not fecha_exp:
            return 1

        fecha_fin = fecha_exp + timedelta(days=duracion)
        if fecha_fin >= datetime.today():
            return 0  # Not expired — shouldn't happen for SALIDA_VENCIDO

        days_overstay = (datetime.today() - fecha_fin).days
        return math.ceil(days_overstay / 30)

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


# =============================================================================
# Singleton & Registration
# =============================================================================

_workflow: Optional[TramitesVisadoWorkflow] = None


def get_tramites_visado_workflow() -> TramitesVisadoWorkflow:
    """Get or create the singleton workflow instance."""
    global _workflow
    if _workflow is None:
        _workflow = TramitesVisadoWorkflow()
    return _workflow
