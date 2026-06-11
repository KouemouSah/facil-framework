"""
PermisoExtraordinarioWorkflow v2 - Extraordinary leave request workflow.

Migrated to PredefinedWorkflow architecture (Option C - Dynamic Form Review).

Handles civil servant extraordinary leave requests including:
- Personal matters (ASUNTOS_PROPIOS, max 5 days)
- Medical reasons (MEDICO, max 30 days, extendable with medical board)
- Family matters (FAMILIAR, max 10 days)
- Studies/Training (ESTUDIOS, max 15 days)
- Other authorized reasons (OTRO, max 3 days)

Entity: MINFP (Ministerio de la Funcion Publica y Reforma Administrativa)

Prerequisite: User must have role 'funcionario' (verified via VerificacionFuncionario).

Process:
1. Select leave reason (PermisoMotivo)
2. Enter dates + justification (form_review)
3. Upload supporting documents (conditional by motivo)
4. Review carnet data (OCR extracted, readonly)
5. Payment (2,500 XAF fixed)
6. Confirmation + agent review

Payment: 2,500 XAF fixed (all motivos).
Appointment: NOT required.
Agent review: REQUIRED.
Nota de Ingreso: NOT required.

OCR schemas:
- carnet_funcionario_gq.json (CARNET_FUNCIONARIO_GQ_V1) - Civil servant card
- Other docs: best_effort_extraction (no schemas)

@version 2.0
@date 2026-02-07
@migration Option C - Dynamic Form Review Architecture
"""
from typing import List, Dict, Any, Optional
from enum import Enum

from ..workflow_interface import (
    PredefinedWorkflow,
    WorkflowStep,
    WorkflowContext,
    ValidationResult,
    DocumentRequirement,
    TariffConfig,
    StepType,
    RenovacionMotivo,
)
from ...models.enums import (
    WorkflowCode,
    WorkflowCategory,
    EntityCode,
    SolicitudType,
    TariffType,
    DocumentConditionType,
)


# =============================================================================
# Enums
# =============================================================================

class PermisoMotivo(str, Enum):
    """Reasons for extraordinary leave."""
    ASUNTOS_PROPIOS = "ASUNTOS_PROPIOS"   # Personal matters (max 5 days)
    MEDICO = "MEDICO"                      # Medical reasons (max 30 days)
    FAMILIAR = "FAMILIAR"                  # Family matters (max 10 days)
    ESTUDIOS = "ESTUDIOS"                  # Studies/Training (max 15 days)
    OTRO = "OTRO"                          # Other (max 3 days)


# =============================================================================
# Configuration
# =============================================================================

# Fixed processing fee for all leave types
TARIFF_PERMISO = 2500  # XAF

# Maximum days by leave motivo
MAX_DAYS_BY_MOTIVO: Dict[str, int] = {
    "ASUNTOS_PROPIOS": 5,
    "MEDICO": 30,
    "FAMILIAR": 10,
    "ESTUDIOS": 15,
    "OTRO": 3,
}


class PermisoExtraordinarioWorkflow(PredefinedWorkflow):
    """
    Extraordinary leave request workflow (MINFP).

    Steps:
    0. select_motivo: Choose leave reason (PermisoMotivo)
    1. form_review_1: Enter dates + justification (manual input)
    2. upload_documents: Carnet + conditional docs by motivo
    3. form_review_2: Review carnet data (OCR extracted, readonly)
    4. payment: 2,500 XAF
    5. confirmation: Summary + submit for agent review
    """

    # === Properties (PredefinedWorkflow interface) ===

    @property
    def workflow_code(self) -> WorkflowCode:
        return WorkflowCode.FP_PERMISO_EXTRAORDINARIO

    @property
    def category(self) -> WorkflowCategory:
        return WorkflowCategory.FUNCION_PUBLICA

    @property
    def entity_code(self) -> EntityCode:
        return EntityCode.MINFP

    @property
    def service_name_es(self) -> str:
        return "Permiso Extraordinario"

    def get_parent_mapping(self) -> Dict[str, Optional[str]]:
        return {"FP_PERMISO_EXTRAORDINARIO": "FP_VERIFICACION_FUNCIONARIO"}

    @property
    def allowed_solicitud_types(self) -> List[SolicitudType]:
        return [SolicitudType.EXPEDICION]

    @property
    def requires_appointment(self) -> bool:
        return False

    @property
    def menu_icon(self) -> str:
        return "Briefcase"

    @property
    def requires_agent_review(self) -> bool:
        return True

    @property
    def requires_nota_ingreso(self) -> bool:
        return False

    @property
    def allowed_sub_types(self) -> List[str]:
        return [m.value for m in PermisoMotivo]

    # === Workflow Setup ===

    def _setup_workflow(self) -> None:
        """Setup the complete extraordinary leave workflow."""
        self._setup_steps()
        self._setup_tariffs()

    def _setup_steps(self) -> None:
        """Define all workflow steps."""

        # Step 0: Select Leave Reason
        self.add_step(WorkflowStep(
            step_number=0,
            step_id="select_motivo",
            step_type=StepType.SELECTION,
            title_es="Motivo del Permiso",
            description_es="Seleccione el motivo de su solicitud de permiso extraordinario",
            config={
                "selection_type": "sub_type",
                "options": [
                    {
                        "id": PermisoMotivo.ASUNTOS_PROPIOS.value,
                        "label_es": "Asuntos Propios (máx. 5 días)",
                        "description_es": "Permiso por asuntos personales",
                    },
                    {
                        "id": PermisoMotivo.MEDICO.value,
                        "label_es": "Motivos Médicos (máx. 30 días)",
                        "description_es": "Permiso por razones médicas. Requiere certificado médico.",
                    },
                    {
                        "id": PermisoMotivo.FAMILIAR.value,
                        "label_es": "Asuntos Familiares (máx. 10 días)",
                        "description_es": "Defunción, enfermedad grave o nacimiento de familiar directo.",
                    },
                    {
                        "id": PermisoMotivo.ESTUDIOS.value,
                        "label_es": "Estudios/Formación (máx. 15 días)",
                        "description_es": "Permiso para formación profesional. Requiere comprobante de matrícula.",
                    },
                    {
                        "id": PermisoMotivo.OTRO.value,
                        "label_es": "Otro Motivo (máx. 3 días)",
                        "description_es": "Otros motivos autorizados. Requiere documento justificativo.",
                    },
                ],
            }
        ))

        # Step 1: Enter Leave Details (manual input)
        self.add_step(WorkflowStep(
            step_number=1,
            step_id="form_review_1",
            step_type=StepType.FORM_REVIEW,
            title_es="Detalles del Permiso",
            description_es="Indique las fechas y la justificación de su solicitud",
            config={
                "sections": [
                    {
                        "id": "fechas_permiso",
                        "title_es": "Fechas del Permiso",
                        "fields": [
                            {
                                "key": "fecha_inicio",
                                "label_es": "Fecha de Inicio",
                                "type": "date",
                                "required": True,
                                "readonly": False,
                                "help_text_es": "La fecha debe ser hoy o posterior",
                            },
                            {
                                "key": "fecha_fin",
                                "label_es": "Fecha de Fin",
                                "type": "date",
                                "required": True,
                                "readonly": False,
                                "help_text_es": "La fecha de fin debe ser igual o posterior a la de inicio",
                            },
                        ]
                    },
                    {
                        "id": "justificacion_permiso",
                        "title_es": "Justificación",
                        "fields": [
                            {
                                "key": "justificacion",
                                "label_es": "Justificación de la Solicitud",
                                "type": "textarea",
                                "required": True,
                                "readonly": False,
                                "placeholder_es": "Explique brevemente el motivo de su solicitud",
                            },
                        ]
                    }
                ]
            }
        ))

        # Step 2: Upload Documents (conditional by motivo)
        self.add_step(WorkflowStep(
            step_number=2,
            step_id="upload_documents",
            step_type=StepType.DOCUMENT_UPLOAD,
            title_es="Documentos Justificativos",
            description_es="Cargue los documentos que justifican el permiso",
            config={
                "dynamic_documents": True,
            }
        ))

        # Step 3: Review Carnet Data (OCR extracted, readonly)
        self.add_step(WorkflowStep(
            step_number=3,
            step_id="form_review_2",
            step_type=StepType.FORM_REVIEW,
            title_es="Datos del Funcionario",
            description_es="Verifique que los datos extraídos de su carnet son correctos",
            config={
                "sections": [
                    {
                        "id": "datos_funcionario",
                        "title_es": "Datos del Carnet de Funcionario",
                        "source_document": "carnet_funcionario",
                        "fields": [
                            {
                                "key": "matricula",
                                "label_es": "Matrícula",
                                "type": "text",
                                "required": True,
                                "readonly": True,
                            },
                            {
                                "key": "nombre_completo",
                                "label_es": "Nombre Completo",
                                "type": "text",
                                "required": True,
                                "readonly": True,
                            },
                            {
                                "key": "cargo",
                                "label_es": "Cargo",
                                "type": "text",
                                "required": False,
                                "readonly": True,
                            },
                            {
                                "key": "ministerio",
                                "label_es": "Ministerio",
                                "type": "text",
                                "required": True,
                                "readonly": True,
                            },
                            {
                                "key": "direccion_general",
                                "label_es": "Dirección General",
                                "type": "text",
                                "required": False,
                                "readonly": True,
                            },
                        ]
                    }
                ]
            }
        ))

        # Step 4: Payment
        self.add_step(WorkflowStep(
            step_number=4,
            step_id="payment",
            step_type=StepType.PAYMENT,
            title_es="Pago de Tasas",
            description_es=f"Tasa de tramitación: {TARIFF_PERMISO:,} XAF",
            config={
                "dynamic_tariff": True,
            }
        ))

        # Step 5: Confirmation
        self.add_step(WorkflowStep(
            step_number=5,
            step_id="confirmation",
            step_type=StepType.CONFIRMATION,
            title_es="Confirmación y Envío",
            description_es="Verifique todos los datos y envíe su solicitud",
            config={
                "show_summary": True,
                "info_message_es": (
                    "Su solicitud será revisada por un agente del "
                    "Ministerio de la Función Pública.\n"
                    "Si procede, se generará la resolución de permiso.\n\n"
                    "Recibirá una notificación por email una vez procesada."
                ),
                "agent_checklist": [
                    {
                        "id": "matricula_verified",
                        "label_es": "He verificado la matrícula en SIGEF",
                        "required": True,
                    },
                    {
                        "id": "fechas_verificadas",
                        "label_es": "He verificado que las fechas solicitadas son correctas y dentro del límite",
                        "required": True,
                    },
                    {
                        "id": "justificacion_revisada",
                        "label_es": "He revisado la justificación y los documentos adjuntos",
                        "required": True,
                    },
                    {
                        "id": "disponibilidad_verificada",
                        "label_es": "He verificado que el funcionario no tiene otro permiso pendiente",
                        "required": False,
                    },
                ],
                "rejection_reasons": [
                    {"id": "matricula_not_found", "label_es": "Matrícula no existe en SIGEF"},
                    {"id": "fechas_invalidas", "label_es": "Fechas solicitadas inválidas o fuera de límite"},
                    {"id": "justificacion_insuficiente", "label_es": "Justificación insuficiente"},
                    {"id": "documentos_invalidos", "label_es": "Documentos justificativos inválidos o ilegibles"},
                    {"id": "permiso_pendiente", "label_es": "Ya existe un permiso pendiente para este funcionario"},
                    {"id": "other", "label_es": "Otro (especificar)"},
                ],
            }
        ))

    def _setup_tariffs(self) -> None:
        """Setup fixed tariff for leave request processing."""
        self.set_tariff_config(TariffConfig(
            tariff_type=TariffType.FIXED,
            fixed_amounts={"EXPEDICION": TARIFF_PERMISO},
            currency="XAF",
        ))

    # === Document Requirements ===

    def get_document_requirements(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None,
    ) -> List[DocumentRequirement]:
        """Get document requirements based on leave motivo.

        Carnet de Funcionario is always required.
        Additional documents depend on the selected motivo (stored in context.sub_type).
        """
        requirements = [
            # Carnet de Funcionario - always required
            DocumentRequirement(
                document_code="carnet_funcionario",
                document_name_es="Carnet de Funcionario",
                schema_key="CARNET_FUNCIONARIO_GQ_V1",
                is_required=True,
                display_order=1,
                condition_type=DocumentConditionType.ALWAYS,
                faces_required=["recto", "verso"],
                instructions_es="Carnet de funcionario vigente (ambas caras)",
                accepted_formats=["pdf", "jpg", "jpeg", "png"],
            ),
        ]

        # Conditional documents based on motivo (context.sub_type)
        # These use CUSTOM condition with types=[motivo] so the frontend
        # can dynamically show/hide based on selected motivo

        # Medical certificate for MEDICO
        requirements.append(DocumentRequirement(
            document_code="certificado_medico",
            document_name_es="Certificado Médico",
            is_required=True,
            display_order=2,
            condition_type=DocumentConditionType.CUSTOM,
            condition_value={"types": ["MEDICO"]},
            instructions_es="Certificado médico que justifique la necesidad del permiso",
            accepted_formats=["pdf", "jpg", "jpeg", "png"],
        ))

        # Family justification document for FAMILIAR
        requirements.append(DocumentRequirement(
            document_code="documento_familiar",
            document_name_es="Documento Justificativo Familiar",
            is_required=True,
            display_order=2,
            condition_type=DocumentConditionType.CUSTOM,
            condition_value={"types": ["FAMILIAR"]},
            instructions_es=(
                "Acta de defunción, certificado médico familiar, "
                "acta de nacimiento, etc."
            ),
            accepted_formats=["pdf", "jpg", "jpeg", "png"],
        ))

        # Enrollment proof for ESTUDIOS
        requirements.append(DocumentRequirement(
            document_code="matricula_estudios",
            document_name_es="Comprobante de Matrícula",
            is_required=True,
            display_order=2,
            condition_type=DocumentConditionType.CUSTOM,
            condition_value={"types": ["ESTUDIOS"]},
            instructions_es="Certificado de matrícula o inscripción en el curso/formación",
            accepted_formats=["pdf", "jpg", "jpeg", "png"],
        ))

        requirements.append(DocumentRequirement(
            document_code="calendario_estudios",
            document_name_es="Calendario del Curso",
            is_required=True,
            display_order=3,
            condition_type=DocumentConditionType.CUSTOM,
            condition_value={"types": ["ESTUDIOS"]},
            instructions_es="Horario o calendario que muestre las fechas del curso",
            accepted_formats=["pdf", "jpg", "jpeg", "png"],
        ))

        # Generic justification for OTRO
        requirements.append(DocumentRequirement(
            document_code="documento_justificativo",
            document_name_es="Documento Justificativo",
            is_required=True,
            display_order=2,
            condition_type=DocumentConditionType.CUSTOM,
            condition_value={"types": ["OTRO"]},
            instructions_es="Cualquier documento que justifique la solicitud",
            accepted_formats=["pdf", "jpg", "jpeg", "png"],
        ))

        return requirements

    # === Form Mapping ===

    def get_form_mapping(
        self,
        context: Optional[WorkflowContext] = None,
    ) -> Dict[str, str]:
        """Get mapping from extracted carnet data to form fields.

        All paths verified against CARNET_FUNCIONARIO_GQ_V1 schema:
        - carnet_funcionario.titular.matricula ✓
        - carnet_funcionario.titular.nombre_completo ✓
        - carnet_funcionario.puesto.cargo ✓
        - carnet_funcionario.puesto.ministerio ✓
        - carnet_funcionario.puesto.direccion_general ✓
        """
        return {
            "matricula": "carnet_funcionario.titular.matricula",
            "nombre_completo": "carnet_funcionario.titular.nombre_completo",
            "cargo": "carnet_funcionario.puesto.cargo",
            "ministerio": "carnet_funcionario.puesto.ministerio",
            "direccion_general": "carnet_funcionario.puesto.direccion_general",
        }

    # === Step Validation ===

    def validate_step(
        self,
        step_number: int,
        context: WorkflowContext,
    ) -> List[ValidationResult]:
        """Validate step with leave-specific rules."""
        results = super().validate_step(step_number, context)

        step = self.get_step(step_number)
        if not step:
            return results

        # Validate dates + duration on form_review_1
        if step.step_id == "form_review_1":
            results.extend(self._validate_leave_dates(context))

        return results

    def _validate_leave_dates(
        self,
        context: WorkflowContext,
    ) -> List[ValidationResult]:
        """Validate leave dates: future, coherent, within MAX_DAYS."""
        from datetime import datetime, date

        results: List[ValidationResult] = []
        form_data = context.form_data or {}

        fecha_inicio_str = form_data.get("fecha_inicio")
        fecha_fin_str = form_data.get("fecha_fin")

        if not fecha_inicio_str or not fecha_fin_str:
            return results  # Required field validation handles missing dates

        try:
            fecha_inicio = datetime.strptime(str(fecha_inicio_str), "%Y-%m-%d").date()
            fecha_fin = datetime.strptime(str(fecha_fin_str), "%Y-%m-%d").date()
            today = date.today()

            # Start date must be today or future
            if fecha_inicio < today:
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id="fecha_inicio_futura",
                    severity="error",
                    message_es="La fecha de inicio debe ser hoy o posterior.",
                    field_name="fecha_inicio",
                ))

            # End date >= start date
            if fecha_fin < fecha_inicio:
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id="fechas_coherentes",
                    severity="error",
                    message_es="La fecha de fin debe ser igual o posterior a la fecha de inicio.",
                    field_name="fecha_fin",
                ))

            # Duration within MAX_DAYS for this motivo
            if fecha_fin >= fecha_inicio:
                duration = (fecha_fin - fecha_inicio).days + 1
                motivo = context.sub_type
                max_days = self.get_max_days(motivo) if motivo else 3
                if duration > max_days:
                    results.append(ValidationResult(
                        is_valid=False,
                        rule_id="duracion_permitida",
                        severity="error",
                        message_es=(
                            f"La duración del permiso ({duration} días) excede "
                            f"el máximo permitido ({max_days} días) para este motivo."
                        ),
                        field_name="fecha_fin",
                    ))

            # 3-day advance notice (except MEDICO)
            if context.sub_type != PermisoMotivo.MEDICO.value:
                from datetime import timedelta
                if fecha_inicio < today + timedelta(days=3):
                    results.append(ValidationResult(
                        is_valid=False,
                        rule_id="solicitud_anticipada",
                        severity="warning",
                        message_es="Debe solicitar el permiso con al menos 3 días de antelación.",
                        field_name="fecha_inicio",
                    ))

        except (ValueError, TypeError):
            pass  # Date parsing failed - skip validation

        return results

    # === Business Logic ===

    def get_max_days(self, motivo: str) -> int:
        """Get maximum allowed days for a leave type.

        Args:
            motivo: PermisoMotivo value (ASUNTOS_PROPIOS, MEDICO, etc.)

        Returns:
            Maximum number of days allowed for this leave type.
        """
        return MAX_DAYS_BY_MOTIVO.get(motivo, 3)


# =============================================================================
# Singleton & Registration
# =============================================================================

_workflow: Optional[PermisoExtraordinarioWorkflow] = None


def get_permiso_extraordinario_workflow() -> PermisoExtraordinarioWorkflow:
    """Get or create the singleton PermisoExtraordinario workflow instance."""
    global _workflow
    if _workflow is None:
        _workflow = PermisoExtraordinarioWorkflow()
    return _workflow
