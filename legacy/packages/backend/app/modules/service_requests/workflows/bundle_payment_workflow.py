"""BundlePaymentWorkflow — Payment of annual fiscal obligations for autonomo companies.

This workflow handles the complete lifecycle of paying bundle obligations:
  Step 0: company_identification (SELECTION) — search or select company
  Step 1: document_upload (DOCUMENT_UPLOAD) — upload certificado padrón (new companies only)
  Step 2: obligations_review (FORM_REVIEW) — review obligations, select mode A/B
  Step 3: payment (PAYMENT) — pay selected obligations
  Step 4: confirmation (CONFIRMATION) — summary + next steps

Key differences from standard workflows (Pasaporte, Residencia, etc.):
  - Tariff is DYNAMIC (comes from bundle_items × zone pricing, not a fixed schedule)
  - Payment creates 1 service_payment for N obligations (multi-entity routing post-payment)
  - No appointment required
  - Conditional document upload (only for NEW companies)
  - Annual recurrence (same workflow, same company, next fiscal year)

Architecture decision: This is a LIGHTWEIGHT PredefinedWorkflow. Complex business logic
(license creation, obligation management, multi-payment) lives in BundleWorkflowService,
NOT in this class. This class provides:
  - Registration in WorkflowEngine (agents see it in menus)
  - Step definitions (stepper UI)
  - Document requirements (1 conditional document)
  - Workflow info for API responses

See: .claude/plans/design_bundle_workflow.md for complete data flow schema.
"""

import logging
from typing import Any, Dict, List, Optional

from app.modules.service_requests.models.enums import (
    EntityCode,
    SolicitudType,
    TariffType,
    WorkflowCategory,
    WorkflowCode,
)
from app.modules.service_requests.workflows.workflow_interface import (
    DocumentRequirement,
    PredefinedWorkflow,
    RenovacionMotivo,
    StepType,
    TariffConfig,
    ValidationResult,
    WorkflowContext,
    WorkflowStep,
)

logger = logging.getLogger(__name__)


class BundlePaymentWorkflow(PredefinedWorkflow):
    """Bundle payment workflow for autonomo companies.

    Steps:
      0. company_identification → SELECTION (search or upload trigger)
      1. document_upload        → DOCUMENT_UPLOAD (certificado padrón, conditional)
      2. obligations_review     → FORM_REVIEW (obligations table + mode A/B)
      3. payment                → PAYMENT (BANGE or cash)
      4. confirmation           → CONFIRMATION (receipt + next steps)
    """

    # === Abstract Properties ===

    @property
    def workflow_code(self) -> WorkflowCode:
        return WorkflowCode.BUNDLE_PAYMENT

    @property
    def category(self) -> WorkflowCategory:
        return WorkflowCategory.COMERCIO

    @property
    def entity_code(self) -> EntityCode:
        return EntityCode.TESORO

    @property
    def service_name_es(self) -> str:
        return "Pago de Obligaciones Fiscales"

    @property
    def allowed_solicitud_types(self) -> List[SolicitudType]:
        return [SolicitudType.EXPEDICION]

    # === Override Properties ===

    @property
    def requires_appointment(self) -> bool:
        return False

    @property
    def requires_agent_review(self) -> bool:
        return True  # Tesoro agent validates cash payments

    @property
    def requires_nota_ingreso(self) -> bool:
        return False

    @property
    def menu_icon(self) -> str:
        return "Receipt"

    @property
    def menu_group(self) -> str:
        return "BUNDLE"

    @property
    def menu_title_key(self) -> str:
        """Override to return bundle-specific i18n key."""
        return "agent.nav.bundles"

    # === Setup ===

    def _setup_workflow(self) -> None:
        """Define the 5-step workflow."""

        # Step 0: Company identification (search existing or trigger upload)
        self.add_step(WorkflowStep(
            step_number=0,
            step_id="company_identification",
            step_type=StepType.SELECTION,
            title_es="Identificación de la Empresa",
            description_es=(
                "Busque su empresa por NIF, número de registro (PE-XXXX) "
                "o nombre comercial"
            ),
            config={
                "selection_type": "company_search",
                "allows_new_company": True,
            },
        ))

        # Step 1: Document upload (conditional: only for new companies)
        self.add_step(WorkflowStep(
            step_number=1,
            step_id="document_upload",
            step_type=StepType.DOCUMENT_UPLOAD,
            title_es="Documentos de la Empresa",
            description_es=(
                "Suba el Certificado de Actualización del Padrón Empresarial "
                "para registrar automáticamente su empresa"
            ),
            is_optional=True,  # Skipped if company already exists
            config={
                "condition": {"company_exists": "false"},
            },
        ))

        # Step 2: Obligations review (license verification + mode selection)
        self.add_step(WorkflowStep(
            step_number=2,
            step_id="obligations_review",
            step_type=StepType.FORM_REVIEW,
            title_es="Revisión de Obligaciones",
            description_es=(
                "Revise las obligaciones fiscales y seleccione "
                "el modo de pago"
            ),
            config={
                "form_type": "obligations_table",
                "allows_mode_selection": True,
                "modes": ["per_line", "consolidated"],
            },
        ))

        # Step 3: Payment
        self.add_step(WorkflowStep(
            step_number=3,
            step_id="payment",
            step_type=StepType.PAYMENT,
            title_es="Pago",
            description_es=(
                "Realice el pago de las obligaciones seleccionadas"
            ),
        ))

        # Step 4: Confirmation
        self.add_step(WorkflowStep(
            step_number=4,
            step_id="confirmation",
            step_type=StepType.CONFIRMATION,
            title_es="Confirmación",
            description_es="Resumen del pago y próximos pasos",
        ))

        # Tariff config: DYNAMIC — computed from bundle_items, not a fixed schedule.
        # get_tariff() returns 0; actual amount comes from BundleWorkflowService.
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
        """Documents required only for NEW companies (no existing record in BD).

        For existing companies (80%+ of cases), no document is needed.
        """
        # Check if company already exists (set by wizard at Step 0)
        company_exists = True
        if context and context.form_data:
            company_exists = context.form_data.get("company_exists", "true") == "true"

        if company_exists:
            return []

        return [
            DocumentRequirement(
                document_code="certificado_padron",
                document_name_es=(
                    "Certificado de Actualización del Padrón Empresarial"
                ),
                schema_key="CERTIFICADO_ACTUALIZACION_PADRON_EMPRESARIAL_GQ_V1",
                is_required=True,
                faces_required=["recto"],
                instructions_es=(
                    "Suba el certificado emitido por la DGPE o la VUE "
                    "que acredita la inscripción al Padrón Empresarial"
                ),
            ),
        ]

    # === Form Mapping (minimal — no OCR→form mapping for this workflow) ===

    def get_form_mapping(
        self, context: Optional[WorkflowContext] = None
    ) -> Dict[str, str]:
        """No form mapping needed — obligations come from BundleService, not OCR."""
        return {}

    # === Status Transitions (simplified for bundle) ===

    def _get_status_transitions(self):
        """Bundle-specific transitions: SUBMITTED → PAID → IN_PROGRESS → COMPLETED.

        No UNDER_REVIEW/DOSSIER_VALIDE steps — payment validation is per-obligation
        via ObligationRoutingService, not per-request.
        """
        from app.modules.service_requests.models.enums import ServiceRequestStatus

        return {
            ServiceRequestStatus.DRAFT: ServiceRequestStatus.SUBMITTED,
            ServiceRequestStatus.SUBMITTED: ServiceRequestStatus.PAYMENT_PENDING,
            ServiceRequestStatus.PAYMENT_PENDING: ServiceRequestStatus.PAYMENT_PROCESSING,
            ServiceRequestStatus.PAYMENT_PROCESSING: ServiceRequestStatus.PAID,
            ServiceRequestStatus.PAID: ServiceRequestStatus.IN_PROGRESS,
            ServiceRequestStatus.IN_PROGRESS: ServiceRequestStatus.COMPLETED,
        }


def get_bundle_payment_workflow() -> BundlePaymentWorkflow:
    """Factory function for BundlePaymentWorkflow."""
    return BundlePaymentWorkflow()
