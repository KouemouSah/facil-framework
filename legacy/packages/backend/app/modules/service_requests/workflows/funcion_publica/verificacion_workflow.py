"""
VerificacionFuncionarioWorkflow v2 - Civil servant verification workflow.

Migrated to PredefinedWorkflow architecture (Option C - Dynamic Form Review).

This is a PREREQUISITE workflow that must be completed before accessing
any other FuncionPublica services. It verifies that a user is a registered
civil servant in the Ministry of Public Function (SIGEF system).

Entity: MINFP (Ministerio de la Funcion Publica y Reforma Administrativa)

Security: Matricula alone is NOT sufficient. Identity must be verified
by comparing with an official identity document (DIP).

Process:
1. User enters matricula (e.g., FP-12345) via form_review
2. User uploads identity document (DIP)
3. System extracts data from DIP (Gemini OCR)
4. User reviews extracted data (readonly form_review)
5. User confirms submission
6. Agent verifies in SIGEF that matricula exists and name matches
7. If approved: user gains 'funcionario' access

Payment: FREE (0 XAF) - No payment step.
Appointment: NOT required.
Agent review: REQUIRED (SIGEF verification).
Nota de Ingreso: NOT required.

OCR schemas:
- dip_gq.json (DIP_GQ_V2) - Identity document

@version 2.0
@date 2026-02-07
@migration Option C - Dynamic Form Review Architecture
"""
from typing import List, Dict, Any, Optional

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
    SolicitudType,
    TariffType,
    DocumentConditionType,
)


class VerificacionFuncionarioWorkflow(PredefinedWorkflow):
    """
    Civil servant verification workflow (MINFP).

    Verifies that a user is a registered civil servant in the SIGEF system.
    Once verified, the user gains access to the "Funcion Publica" menu
    with services like:
    - Carnet de Funcionario
    - Reconocimiento de Trienios
    - Corrida de Nivel/Escala
    - Permisos Extraordinarios
    - Certificados Administrativos

    Steps:
    0. form_review_1: Enter matricula (manual input)
    1. upload_documents: Upload DIP
    2. form_review_2: Review extracted personal data (readonly)
    3. confirmation: Summary + agent review info
    """

    # === Properties (PredefinedWorkflow interface) ===

    @property
    def workflow_code(self) -> WorkflowCode:
        return WorkflowCode.FP_VERIFICACION_FUNCIONARIO

    @property
    def category(self) -> WorkflowCategory:
        return WorkflowCategory.FUNCION_PUBLICA

    @property
    def entity_code(self) -> EntityCode:
        return EntityCode.MINFP

    @property
    def service_name_es(self) -> str:
        return "Verificación de Funcionario"

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

    # === Workflow Setup ===

    def _setup_workflow(self) -> None:
        """Setup the complete verification workflow."""
        self._setup_steps()
        self._setup_tariffs()

    def _setup_steps(self) -> None:
        """Define all workflow steps."""

        # Step 0: Enter Matricula (manual form input)
        self.add_step(WorkflowStep(
            step_number=0,
            step_id="form_review_1",
            step_type=StepType.FORM_REVIEW,
            title_es="Matrícula de Funcionario",
            description_es="Introduzca su matrícula de funcionario público",
            config={
                "sections": [
                    {
                        "id": "matricula",
                        "title_es": "Datos de Funcionario",
                        "description_es": "Introduzca su matrícula tal como aparece en su nombramiento o carnet",
                        "fields": [
                            {
                                "key": "matricula",
                                "label_es": "Matrícula",
                                "type": "text",
                                "required": True,
                                "readonly": False,
                                "pattern": r"^[A-Z]{0,3}-?\d{4,10}$",
                                "placeholder_es": "FP-12345",
                                "help_text_es": "Formato: letras-números (ej: FP-12345)"
                            }
                        ]
                    }
                ]
            }
        ))

        # Step 1: Upload Identity Document (DIP)
        self.add_step(WorkflowStep(
            step_number=1,
            step_id="upload_documents",
            step_type=StepType.DOCUMENT_UPLOAD,
            title_es="Documento de Identidad",
            description_es="Suba su DIP (Documento de Identidad Personal) en vigor",
            config={
                "dynamic_documents": True,
                "max_file_size_mb": 5,
            }
        ))

        # Step 2: Review Extracted Data (readonly from DIP)
        self.add_step(WorkflowStep(
            step_number=2,
            step_id="form_review_2",
            step_type=StepType.FORM_REVIEW,
            title_es="Datos Personales",
            description_es="Verifique que los datos extraídos de su DIP son correctos",
            config={
                "sections": [
                    {
                        "id": "datos_personales",
                        "title_es": "Datos del Documento de Identidad",
                        "source_document": "dip",
                        "fields": [
                            {
                                "key": "apellidos",
                                "label_es": "Apellidos",
                                "type": "text",
                                "required": True,
                                "readonly": True,
                            },
                            {
                                "key": "nombres",
                                "label_es": "Nombres",
                                "type": "text",
                                "required": True,
                                "readonly": True,
                            },
                            {
                                "key": "numero_dip",
                                "label_es": "Número de DIP",
                                "type": "text",
                                "required": True,
                                "readonly": True,
                            },
                            {
                                "key": "fecha_nacimiento",
                                "label_es": "Fecha de Nacimiento",
                                "type": "date",
                                "required": True,
                                "readonly": True,
                            },
                        ]
                    }
                ]
            }
        ))

        # Step 3: Confirmation
        self.add_step(WorkflowStep(
            step_number=3,
            step_id="confirmation",
            step_type=StepType.CONFIRMATION,
            title_es="Confirmación",
            description_es=(
                "Su solicitud será revisada por un agente del "
                "Ministerio de la Función Pública"
            ),
            config={
                "show_summary": True,
                "info_message_es": (
                    "Su solicitud será revisada por un agente del "
                    "Ministerio de la Función Pública, quien verificará que:\n"
                    "1. Su matrícula existe en el sistema oficial (SIGEF)\n"
                    "2. Su nombre coincide con el registrado\n\n"
                    "Recibirá una notificación por email una vez procesada."
                ),
                "agent_checklist": [
                    {
                        "id": "matricula_exists",
                        "label_es": "He verificado que la matrícula EXISTE en el sistema SIGEF",
                        "required": True,
                    },
                    {
                        "id": "name_matches",
                        "label_es": (
                            "He verificado que el NOMBRE del solicitante COINCIDE "
                            "con el nombre registrado en SIGEF para esta matrícula"
                        ),
                        "required": True,
                    },
                    {
                        "id": "dip_verified",
                        "label_es": "He verificado el número de DIP (opcional si disponible en SIGEF)",
                        "required": False,
                    },
                ],
                "rejection_reasons": [
                    {"id": "matricula_not_found", "label_es": "Matrícula no existe en SIGEF"},
                    {"id": "name_mismatch", "label_es": "Nombre no coincide con el registrado"},
                    {"id": "document_illegible", "label_es": "Documento ilegible o inválido"},
                    {"id": "other", "label_es": "Otro (especificar)"},
                ],
            }
        ))

    def _setup_tariffs(self) -> None:
        """No payment required for verification (free service)."""
        self.set_tariff_config(TariffConfig(
            tariff_type=TariffType.FIXED,
            fixed_amounts={"EXPEDICION": 0},
            currency="XAF",
        ))

    # === Document Requirements ===

    def get_document_requirements(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None,
    ) -> List[DocumentRequirement]:
        """Get document requirements for verification.

        Only one document required: DIP (identity document).
        """
        return [
            DocumentRequirement(
                document_code="dip",
                document_name_es="Documento de Identidad Personal (DIP)",
                schema_key="DIP_GQ_V2",
                is_required=True,
                display_order=1,
                condition_type=DocumentConditionType.ALWAYS,
                faces_required=["recto", "verso"],
                instructions_es=(
                    "DIP en vigor. Suba las dos caras (recto y verso). Máximo 5MB."
                ),
                accepted_formats=["pdf", "jpg", "jpeg", "png"],
                max_size_mb=5,
            ),
        ]

    # === Form Mapping ===

    def get_form_mapping(
        self,
        context: Optional[WorkflowContext] = None,
    ) -> Dict[str, str]:
        """Get mapping from extracted DIP data to form fields.

        All paths verified against DIP_GQ_V2 schema:
        - dip.titular.apellidos ✓
        - dip.titular.nombres ✓
        - dip.documento.numero_dip ✓
        - dip.titular.fecha_nacimiento ✓
        """
        return {
            "apellidos": "dip.titular.apellidos",
            "nombres": "dip.titular.nombres",
            "numero_dip": "dip.documento.numero_dip",
            "fecha_nacimiento": "dip.titular.fecha_nacimiento",
        }

    # === Step Validation ===

    def validate_step(
        self,
        step_number: int,
        context: WorkflowContext
    ) -> List[ValidationResult]:
        """Validate matricula format on form_review_1 (manual input)."""
        import re

        results = super().validate_step(step_number, context)

        step = self.get_step(step_number)
        if not step or step.step_id != "form_review_1":
            return results

        matricula = context.form_data.get("matricula", "")
        if matricula and not re.match(r'^[A-Z]{0,3}-?\d{4,10}$', str(matricula)):
            results.append(ValidationResult(
                is_valid=False,
                rule_id="matricula_formato",
                severity="error",
                message_es="El formato de la matrícula es inválido. Ejemplo: FP-12345",
                field_name="matricula"
            ))

        return results


# =============================================================================
# Singleton & Registration
# =============================================================================

_workflow: Optional[VerificacionFuncionarioWorkflow] = None


def get_verificacion_funcionario_workflow() -> VerificacionFuncionarioWorkflow:
    """Get or create the singleton VerificacionFuncionario workflow instance."""
    global _workflow
    if _workflow is None:
        _workflow = VerificacionFuncionarioWorkflow()
    return _workflow
