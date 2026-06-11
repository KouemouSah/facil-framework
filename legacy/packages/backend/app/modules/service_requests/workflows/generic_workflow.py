"""
Generic Workflows - Data-driven workflow implementations (V2 architecture).

Two types of generic workflows:
1. GenericWorkflowStandard - Agent validation BEFORE payment (default)
2. GenericWorkflowDirectPayment - Direct payment WITHOUT agent validation

These workflows load their configuration from the database (workflows table)
instead of hardcoding it in Python classes. They extend PredefinedWorkflow (V2)
with DB-backed properties.

Usage:
    # Load from database
    workflow = await GenericWorkflowStandard.from_database(db, "WORKFLOW_CODE")

    # Or create with config dict
    workflow = GenericWorkflowStandard(config={
        "code": "MY_WORKFLOW",
        "name_es": "My Workflow",
        "entity_code": "CNEDOGE",
        ...
    })
"""
import asyncpg
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from uuid import UUID
import logging

from app.core.jsonb import ensure_dict
from .workflow_interface import (
    PredefinedWorkflow,
    WorkflowStep,
    WorkflowContext,
    TariffConfig,
    DocumentRequirement,
    ValidationResult,
    StepType,
    RenovacionMotivo,
)
from ..models.enums import (
    WorkflowCode,
    WorkflowCategory,
    EntityCode,
    TariffType,
    ServiceRequestStatus,
    SolicitudType,
    DocumentConditionType
)

logger = logging.getLogger(__name__)


class _GenericCode:
    """Wrapper for generic workflow codes that don't have a WorkflowCode enum entry.

    Mimics enum interface (.value, __eq__, __hash__) so that existing code
    calling self.workflow_code.value works transparently for DB-driven workflows.
    """

    def __init__(self, value: str):
        self.value = value

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return getattr(other, 'value', other) == self.value

    def __hash__(self):
        return hash(self.value)

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"_GenericCode({self.value!r})"


@dataclass
class WorkflowConfig:
    """Configuration loaded from workflows table."""
    code: str
    name_es: str
    description_es: Optional[str] = None
    category: str = "general"
    entity_code: str = "GENERAL"
    workflow_type: str = "standard"
    requires_agent_validation: bool = True
    requires_appointment: bool = False
    is_generic: bool = True
    appointment_delay_days: Optional[int] = None
    appointment_entity_code: Optional[str] = None
    sla_hours: int = 48
    max_processing_days: int = 30
    display_order: int = 0
    is_active: bool = True
    config: Dict[str, Any] = field(default_factory=dict)


class GenericWorkflowStandard(PredefinedWorkflow):
    """
    Generic workflow with agent validation BEFORE payment.

    Flow:
    DRAFT → SUBMITTED → UNDER_REVIEW → DOSSIER_VALIDE → PAYMENT_PENDING → PAID
                              │
                              ├── REJECTED (if agent rejects)
                              └── DOCUMENTS_REQUIRED (if more docs needed)

    If requires_appointment:
        ... → PAID → CITA_SCHEDULED → IN_PROGRESS → COMPLETED

    If NOT requires_appointment:
        ... → PAID → IN_PROGRESS → COMPLETED
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        workflow_config: Optional[WorkflowConfig] = None,
    ):
        """
        Initialize generic workflow from configuration.

        Args:
            config: Dict configuration (legacy)
            workflow_config: WorkflowConfig dataclass (preferred)
        """
        # Set instance attributes BEFORE super().__init__() which calls _setup_workflow()
        self._config = workflow_config or self._parse_config(config or {})
        self._document_requirements: List[DocumentRequirement] = []
        self._tariff_data: Optional[Dict[str, Any]] = None

        # Set backing attributes for abstract properties
        self._workflow_code = None
        self._category = WorkflowCategory.GENERAL
        self._entity_code = EntityCode.GENERAL
        self._service_name_es = "Servicio Genérico"
        self._requires_appointment_flag = False
        self._requires_agent_review_flag = True

        # Apply config to backing attributes
        self._apply_config()

        # PredefinedWorkflow.__init__ calls _setup_workflow()
        super().__init__()

    # === Abstract Properties (backed by instance attributes from DB) ===

    @property
    def workflow_code(self) -> WorkflowCode:
        return self._workflow_code

    @property
    def category(self) -> WorkflowCategory:
        return self._category

    @property
    def entity_code(self) -> EntityCode:
        return self._entity_code

    @property
    def service_name_es(self) -> str:
        return self._service_name_es

    @property
    def allowed_solicitud_types(self) -> List[SolicitudType]:
        return [SolicitudType.EXPEDICION]

    @property
    def requires_appointment(self) -> bool:
        return self._requires_appointment_flag

    @property
    def requires_agent_review(self) -> bool:
        return self._requires_agent_review_flag

    @property
    def allowed_sub_types(self) -> List[str]:
        return []

    @property
    def is_generic(self) -> bool:
        """Marker for tariff_calculator: use DB tariffs, not hardcoded."""
        return True

    # === Config Helpers ===

    def _parse_config(self, config: Dict[str, Any]) -> WorkflowConfig:
        """Parse dict config into WorkflowConfig."""
        return WorkflowConfig(
            code=config.get("code", "GENERIC"),
            name_es=config.get("name_es", "Workflow Genérico"),
            description_es=config.get("description_es"),
            category=config.get("category", "general"),
            entity_code=config.get("entity_code", "GENERAL"),
            workflow_type=config.get("workflow_type", "standard"),
            requires_agent_validation=config.get("requires_agent_validation", True),
            requires_appointment=config.get("requires_appointment", False),
            is_generic=config.get("is_generic", True),
            appointment_delay_days=config.get("appointment_delay_days"),
            appointment_entity_code=config.get("appointment_entity_code"),
            sla_hours=config.get("sla_hours", 48),
            max_processing_days=config.get("max_processing_days", 30),
            display_order=config.get("display_order", 0),
            is_active=config.get("is_active", True),
            config=config.get("config", {})
        )

    def _apply_config(self) -> None:
        """Apply configuration to backing attributes."""
        try:
            self._workflow_code = WorkflowCode(self._config.code)
        except ValueError:
            # Non-enum code (admin-created) — wrap so .value works everywhere
            self._workflow_code = _GenericCode(self._config.code)

        try:
            self._category = WorkflowCategory(self._config.category)
        except ValueError:
            self._category = WorkflowCategory.GENERAL

        try:
            self._entity_code = EntityCode(self._config.entity_code)
        except ValueError:
            self._entity_code = EntityCode.GENERAL

        self._service_name_es = self._config.name_es
        self._requires_appointment_flag = self._config.requires_appointment
        self._requires_agent_review_flag = self._config.requires_agent_validation

    # === Database Loading ===

    @classmethod
    async def from_database(
        cls,
        db: asyncpg.Connection,
        workflow_code: str,
    ) -> "GenericWorkflowStandard":
        """
        Load workflow configuration from database.

        Args:
            db: Database connection
            workflow_code: Workflow code to load

        Returns:
            Configured GenericWorkflowStandard instance
        """
        row = await db.fetchrow(
            """
            SELECT code, name_es, description_es, category, entity_code,
                   workflow_type, requires_agent_validation, requires_appointment,
                   is_generic, appointment_delay_days, appointment_entity_code,
                   sla_hours, max_processing_days, display_order, is_active, config
            FROM workflows
            WHERE code = $1 AND is_active = TRUE
            """,
            workflow_code
        )

        if not row:
            raise ValueError(f"Workflow not found or inactive: {workflow_code}")

        config = WorkflowConfig(
            code=row["code"],
            name_es=row["name_es"],
            description_es=row["description_es"],
            category=row["category"],
            entity_code=row["entity_code"],
            workflow_type=row["workflow_type"],
            requires_agent_validation=row["requires_agent_validation"],
            requires_appointment=row["requires_appointment"],
            is_generic=row["is_generic"],
            appointment_delay_days=row["appointment_delay_days"],
            appointment_entity_code=row["appointment_entity_code"],
            sla_hours=row["sla_hours"],
            max_processing_days=row["max_processing_days"],
            display_order=row["display_order"],
            is_active=row["is_active"],
            config=ensure_dict(row["config"])
        )

        instance = cls(workflow_config=config)

        # Populate docs and tariffs AFTER construction
        await instance._load_document_requirements(db, workflow_code)
        await instance._load_tariff_data(db, workflow_code)

        return instance

    async def _load_document_requirements(
        self,
        db: asyncpg.Connection,
        workflow_code: str
    ) -> None:
        """Load document requirements from database."""
        rows = await db.fetch(
            """
            SELECT document_code, document_name_es, is_required, display_order,
                   extraction_schema_key, instructions_es, condition_type, condition_value
            FROM workflow_document_requirements
            WHERE workflow_code = $1 AND is_active = TRUE
            ORDER BY display_order
            """,
            workflow_code
        )

        self._document_requirements = []
        for row in rows:
            try:
                condition_type = DocumentConditionType(row["condition_type"])
            except ValueError:
                condition_type = DocumentConditionType.ALWAYS

            self._document_requirements.append(DocumentRequirement(
                document_code=row["document_code"],
                document_name_es=row["document_name_es"],
                schema_key=row["extraction_schema_key"],
                is_required=row["is_required"] if row["is_required"] is not None else True,
                display_order=row["display_order"] or 0,
                condition_type=condition_type,
                condition_value=ensure_dict(row["condition_value"]),
                instructions_es=row["instructions_es"]
            ))

    async def _load_tariff_data(
        self,
        db: asyncpg.Connection,
        workflow_code: str
    ) -> None:
        """Load tariff configuration from database."""
        row = await db.fetchrow(
            """
            SELECT workflow_code, solicitud_type, amount, currency,
                   tariff_type, percentage_rate, legal_reference
            FROM workflow_tariffs
            WHERE workflow_code = $1 AND is_active = TRUE
            AND (effective_to IS NULL OR effective_to >= CURRENT_DATE)
            ORDER BY effective_from DESC
            LIMIT 1
            """,
            workflow_code
        )

        if row:
            self._tariff_data = dict(row)
            # Update tariff config with DB data
            self._setup_tariff_from_data()

    def _setup_tariff_from_data(self) -> None:
        """Update tariff config from loaded DB data."""
        if not self._tariff_data:
            return
        tariff_type_str = self._tariff_data.get("tariff_type", "FIXED")
        try:
            tariff_type = TariffType(tariff_type_str)
        except ValueError:
            tariff_type = TariffType.FIXED

        self._tariff_config = TariffConfig(
            tariff_type=tariff_type,
            fixed_amounts={"DEFAULT": int(self._tariff_data.get("amount", 0))},
            percentage=self._tariff_data.get("percentage_rate"),
            currency=self._tariff_data.get("currency", "XAF")
        )

    # === V2 Abstract Method Implementations ===

    def _setup_workflow(self) -> None:
        """
        Setup ALL steps explicitly (V2 = autonomous, no inherited steps).

        Standard flow: 0:Selection → 1:Upload → 2:Form Review
        → 3:Appointment (optional) → 4:Payment → 5:Confirmation

        Agent review happens at the status transition level
        (SUBMITTED → UNDER_REVIEW → DOSSIER_VALIDE), not as a wizard step.
        """
        # Step 0: Selection
        self.add_step(WorkflowStep(
            step_number=0,
            step_id="select_type",
            step_type=StepType.SELECTION,
            title_es="Tipo de Solicitud",
            description_es="Seleccione el tipo de trámite que desea realizar",
            requires_previous=False
        ))

        # Step 1: Document Upload
        self.add_step(WorkflowStep(
            step_number=1,
            step_id="upload_documents",
            step_type=StepType.DOCUMENT_UPLOAD,
            title_es="Documentos Requeridos",
            description_es="Cargue los documentos necesarios para su solicitud",
        ))

        # Step 2: Form Review
        self.add_step(WorkflowStep(
            step_number=2,
            step_id="form_review_1",
            step_type=StepType.FORM_REVIEW,
            title_es="Verificar Datos",
            description_es="Verifique y corrija los datos extraídos de sus documentos",
        ))

        step_num = 3

        # Step 3 (optional): Appointment — BEFORE payment (Doctolib pattern)
        if self._config.requires_appointment:
            self.add_step(WorkflowStep(
                step_number=step_num,
                step_id="appointment",
                step_type=StepType.APPOINTMENT,
                title_es="Cita",
                description_es="Seleccione una cita para completar el trámite",
            ))
            step_num += 1

        # Step 3/4: Payment
        self.add_step(WorkflowStep(
            step_number=step_num,
            step_id="payment",
            step_type=StepType.PAYMENT,
            title_es="Pago",
            description_es="Realice el pago de las tasas correspondientes",
        ))
        step_num += 1

        # Final: Confirmation
        self.add_step(WorkflowStep(
            step_number=step_num,
            step_id="confirmation",
            step_type=StepType.CONFIRMATION,
            title_es="Confirmación",
            description_es="Su solicitud ha sido procesada",
        ))

        # Default tariff (overwritten by from_database → _load_tariff_data)
        self.set_tariff_config(TariffConfig(
            tariff_type=TariffType.FIXED,
            fixed_amounts={"DEFAULT": 0}
        ))

    def get_document_requirements(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None
    ) -> List[DocumentRequirement]:
        """Get document requirements, filtered by context."""
        if context:
            return [
                doc for doc in self._document_requirements
                if doc.should_show(context)
            ]
        # No context: build minimal one for filtering
        minimal_context = WorkflowContext(
            service_request_id=UUID("00000000-0000-0000-0000-000000000000"),
            user_id=UUID("00000000-0000-0000-0000-000000000000"),
            workflow_code=self.workflow_code if isinstance(self.workflow_code, WorkflowCode) else WorkflowCode.GENERIC_STANDARD,
            solicitud_type=solicitud_type,
            motivo=motivo,
        )
        return [
            doc for doc in self._document_requirements
            if doc.should_show(minimal_context)
        ]

    def get_form_mapping(self, context: Optional[WorkflowContext] = None) -> Dict[str, str]:
        """Generic workflows have no predefined form mappings."""
        return {}

    def _get_status_transitions(self) -> Dict[ServiceRequestStatus, ServiceRequestStatus]:
        """
        Status transitions for standard workflow.

        Flow: DRAFT → SUBMITTED → UNDER_REVIEW → DOSSIER_VALIDE → PAYMENT_PENDING → PAID
        """
        transitions = {
            ServiceRequestStatus.DRAFT: ServiceRequestStatus.SUBMITTED,
            ServiceRequestStatus.SUBMITTED: ServiceRequestStatus.UNDER_REVIEW,
            ServiceRequestStatus.UNDER_REVIEW: ServiceRequestStatus.DOSSIER_VALIDE,
            ServiceRequestStatus.DOSSIER_VALIDE: ServiceRequestStatus.PAYMENT_PENDING,
            ServiceRequestStatus.PAYMENT_PENDING: ServiceRequestStatus.PAYMENT_PROCESSING,
            ServiceRequestStatus.PAYMENT_PROCESSING: ServiceRequestStatus.PAID,
        }

        if self._config.requires_appointment:
            transitions[ServiceRequestStatus.PAID] = ServiceRequestStatus.CITA_SCHEDULED
            transitions[ServiceRequestStatus.CITA_SCHEDULED] = ServiceRequestStatus.IN_PROGRESS
        else:
            transitions[ServiceRequestStatus.PAID] = ServiceRequestStatus.IN_PROGRESS

        transitions[ServiceRequestStatus.IN_PROGRESS] = ServiceRequestStatus.COMPLETED

        return transitions


class GenericWorkflowDirectPayment(PredefinedWorkflow):
    """
    Generic workflow with direct payment WITHOUT agent validation.

    Flow:
    DRAFT → SUBMITTED → PAYMENT_PENDING → PAID → IN_PROGRESS → COMPLETED

    No agent review step - payment happens immediately after submission.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        workflow_config: Optional[WorkflowConfig] = None,
    ):
        """Initialize direct payment workflow."""
        self._config = workflow_config or self._parse_config(config or {})
        self._document_requirements: List[DocumentRequirement] = []
        self._tariff_data: Optional[Dict[str, Any]] = None

        # Force no agent validation
        self._config.requires_agent_validation = False

        # Set backing attributes for abstract properties
        self._workflow_code = None
        self._category = WorkflowCategory.GENERAL
        self._entity_code = EntityCode.GENERAL
        self._service_name_es = "Servicio con Pago Directo"
        self._requires_appointment_flag = False
        self._requires_agent_review_flag = False

        self._apply_config()
        super().__init__()

    # === Abstract Properties ===

    @property
    def workflow_code(self) -> WorkflowCode:
        return self._workflow_code

    @property
    def category(self) -> WorkflowCategory:
        return self._category

    @property
    def entity_code(self) -> EntityCode:
        return self._entity_code

    @property
    def service_name_es(self) -> str:
        return self._service_name_es

    @property
    def allowed_solicitud_types(self) -> List[SolicitudType]:
        return [SolicitudType.EXPEDICION]

    @property
    def requires_appointment(self) -> bool:
        return self._requires_appointment_flag

    @property
    def requires_agent_review(self) -> bool:
        return False  # Always false for direct payment

    @property
    def allowed_sub_types(self) -> List[str]:
        return []

    @property
    def is_generic(self) -> bool:
        return True

    # === Config Helpers ===

    def _parse_config(self, config: Dict[str, Any]) -> WorkflowConfig:
        """Parse dict config into WorkflowConfig."""
        return WorkflowConfig(
            code=config.get("code", "GENERIC_DIRECT"),
            name_es=config.get("name_es", "Workflow Pago Directo"),
            description_es=config.get("description_es"),
            category=config.get("category", "general"),
            entity_code=config.get("entity_code", "GENERAL"),
            workflow_type="direct_payment",
            requires_agent_validation=False,
            requires_appointment=config.get("requires_appointment", False),
            is_generic=True,
            appointment_delay_days=config.get("appointment_delay_days"),
            appointment_entity_code=config.get("appointment_entity_code"),
            sla_hours=config.get("sla_hours", 24),
            max_processing_days=config.get("max_processing_days", 7),
            display_order=config.get("display_order", 0),
            is_active=config.get("is_active", True),
            config=config.get("config", {})
        )

    def _apply_config(self) -> None:
        """Apply configuration to backing attributes."""
        try:
            self._workflow_code = WorkflowCode(self._config.code)
        except ValueError:
            # Non-enum code (admin-created) — wrap so .value works everywhere
            self._workflow_code = _GenericCode(self._config.code)

        try:
            self._category = WorkflowCategory(self._config.category)
        except ValueError:
            self._category = WorkflowCategory.GENERAL

        try:
            self._entity_code = EntityCode(self._config.entity_code)
        except ValueError:
            self._entity_code = EntityCode.GENERAL

        self._service_name_es = self._config.name_es
        self._requires_appointment_flag = self._config.requires_appointment
        self._requires_agent_review_flag = False

    # === Database Loading ===

    @classmethod
    async def from_database(
        cls,
        db: asyncpg.Connection,
        workflow_code: str,
    ) -> "GenericWorkflowDirectPayment":
        """Load workflow configuration from database."""
        row = await db.fetchrow(
            """
            SELECT code, name_es, description_es, category, entity_code,
                   workflow_type, requires_agent_validation, requires_appointment,
                   is_generic, appointment_delay_days, appointment_entity_code,
                   sla_hours, max_processing_days, display_order, is_active, config
            FROM workflows
            WHERE code = $1 AND is_active = TRUE
            """,
            workflow_code
        )

        if not row:
            raise ValueError(f"Workflow not found or inactive: {workflow_code}")

        if row["workflow_type"] != "direct_payment" and row["requires_agent_validation"]:
            logger.warning(
                f"Workflow {workflow_code} is not configured as direct_payment, "
                f"but loading as GenericWorkflowDirectPayment anyway"
            )

        config = WorkflowConfig(
            code=row["code"],
            name_es=row["name_es"],
            description_es=row["description_es"],
            category=row["category"],
            entity_code=row["entity_code"],
            workflow_type="direct_payment",
            requires_agent_validation=False,
            requires_appointment=row["requires_appointment"],
            is_generic=row["is_generic"],
            appointment_delay_days=row["appointment_delay_days"],
            appointment_entity_code=row["appointment_entity_code"],
            sla_hours=row["sla_hours"],
            max_processing_days=row["max_processing_days"],
            display_order=row["display_order"],
            is_active=row["is_active"],
            config=ensure_dict(row["config"])
        )

        instance = cls(workflow_config=config)
        await instance._load_document_requirements(db, workflow_code)
        await instance._load_tariff_data(db, workflow_code)

        return instance

    async def _load_document_requirements(
        self,
        db: asyncpg.Connection,
        workflow_code: str
    ) -> None:
        """Load document requirements from database."""
        rows = await db.fetch(
            """
            SELECT document_code, document_name_es, is_required, display_order,
                   extraction_schema_key, instructions_es, condition_type, condition_value
            FROM workflow_document_requirements
            WHERE workflow_code = $1 AND is_active = TRUE
            ORDER BY display_order
            """,
            workflow_code
        )

        self._document_requirements = []
        for row in rows:
            try:
                condition_type = DocumentConditionType(row["condition_type"])
            except ValueError:
                condition_type = DocumentConditionType.ALWAYS

            self._document_requirements.append(DocumentRequirement(
                document_code=row["document_code"],
                document_name_es=row["document_name_es"],
                schema_key=row["extraction_schema_key"],
                is_required=row["is_required"] if row["is_required"] is not None else True,
                display_order=row["display_order"] or 0,
                condition_type=condition_type,
                condition_value=ensure_dict(row["condition_value"]),
                instructions_es=row["instructions_es"]
            ))

    async def _load_tariff_data(
        self,
        db: asyncpg.Connection,
        workflow_code: str
    ) -> None:
        """Load tariff configuration from database."""
        row = await db.fetchrow(
            """
            SELECT workflow_code, solicitud_type, amount, currency,
                   tariff_type, percentage_rate, legal_reference
            FROM workflow_tariffs
            WHERE workflow_code = $1 AND is_active = TRUE
            AND (effective_to IS NULL OR effective_to >= CURRENT_DATE)
            ORDER BY effective_from DESC
            LIMIT 1
            """,
            workflow_code
        )

        if row:
            self._tariff_data = dict(row)
            self._setup_tariff_from_data()

    def _setup_tariff_from_data(self) -> None:
        """Update tariff config from loaded DB data."""
        if not self._tariff_data:
            return
        tariff_type_str = self._tariff_data.get("tariff_type", "FIXED")
        try:
            tariff_type = TariffType(tariff_type_str)
        except ValueError:
            tariff_type = TariffType.FIXED

        self._tariff_config = TariffConfig(
            tariff_type=tariff_type,
            fixed_amounts={"DEFAULT": int(self._tariff_data.get("amount", 0))},
            percentage=self._tariff_data.get("percentage_rate"),
            currency=self._tariff_data.get("currency", "XAF")
        )

    # === V2 Abstract Method Implementations ===

    def _setup_workflow(self) -> None:
        """
        Setup ALL steps explicitly (V2 = autonomous).

        Direct payment flow: 0:Selection → 1:Upload → 2:Form Review
        → 3:Appointment (optional) → 4:Payment → 5:Confirmation

        No agent review — payment is direct (citizen pays immediately).
        """
        # Step 0: Selection
        self.add_step(WorkflowStep(
            step_number=0,
            step_id="select_type",
            step_type=StepType.SELECTION,
            title_es="Tipo de Solicitud",
            description_es="Seleccione el tipo de trámite que desea realizar",
            requires_previous=False
        ))

        # Step 1: Document Upload
        self.add_step(WorkflowStep(
            step_number=1,
            step_id="upload_documents",
            step_type=StepType.DOCUMENT_UPLOAD,
            title_es="Documentos Requeridos",
            description_es="Cargue los documentos necesarios para su solicitud",
        ))

        # Step 2: Form Review
        self.add_step(WorkflowStep(
            step_number=2,
            step_id="form_review_1",
            step_type=StepType.FORM_REVIEW,
            title_es="Verificar Datos",
            description_es="Verifique y corrija los datos extraídos de sus documentos",
        ))

        step_num = 3

        # Step 3 (optional): Appointment — BEFORE payment (Doctolib pattern)
        if self._config.requires_appointment:
            self.add_step(WorkflowStep(
                step_number=step_num,
                step_id="appointment",
                step_type=StepType.APPOINTMENT,
                title_es="Cita",
                description_es="Seleccione una cita para completar el trámite",
            ))
            step_num += 1

        # Step 3/4: Payment
        self.add_step(WorkflowStep(
            step_number=step_num,
            step_id="payment",
            step_type=StepType.PAYMENT,
            title_es="Pago",
            description_es="Realice el pago de las tasas correspondientes",
        ))
        step_num += 1

        # Final step: Confirmation
        self.add_step(WorkflowStep(
            step_number=step_num,
            step_id="confirmation",
            step_type=StepType.CONFIRMATION,
            title_es="Confirmación",
            description_es="Su solicitud ha sido procesada",
        ))

        # Default tariff (overwritten by from_database → _load_tariff_data)
        self.set_tariff_config(TariffConfig(
            tariff_type=TariffType.FIXED,
            fixed_amounts={"DEFAULT": 0}
        ))

    def get_document_requirements(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None
    ) -> List[DocumentRequirement]:
        """Get document requirements, filtered by context."""
        if context:
            return [
                doc for doc in self._document_requirements
                if doc.should_show(context)
            ]
        minimal_context = WorkflowContext(
            service_request_id=UUID("00000000-0000-0000-0000-000000000000"),
            user_id=UUID("00000000-0000-0000-0000-000000000000"),
            workflow_code=self.workflow_code if isinstance(self.workflow_code, WorkflowCode) else WorkflowCode.GENERIC_DIRECT_PAYMENT,
            solicitud_type=solicitud_type,
            motivo=motivo,
        )
        return [
            doc for doc in self._document_requirements
            if doc.should_show(minimal_context)
        ]

    def get_form_mapping(self, context: Optional[WorkflowContext] = None) -> Dict[str, str]:
        """Generic workflows have no predefined form mappings."""
        return {}

    def _get_status_transitions(self) -> Dict[ServiceRequestStatus, ServiceRequestStatus]:
        """
        Status transitions for direct payment workflow.

        Flow: DRAFT → SUBMITTED → PAYMENT_PENDING → PAID → ...
        NO UNDER_REVIEW or DOSSIER_VALIDE states!
        """
        transitions = {
            ServiceRequestStatus.DRAFT: ServiceRequestStatus.SUBMITTED,
            ServiceRequestStatus.SUBMITTED: ServiceRequestStatus.PAYMENT_PENDING,
            ServiceRequestStatus.PAYMENT_PENDING: ServiceRequestStatus.PAYMENT_PROCESSING,
            ServiceRequestStatus.PAYMENT_PROCESSING: ServiceRequestStatus.PAID,
        }

        if self._config.requires_appointment:
            transitions[ServiceRequestStatus.PAID] = ServiceRequestStatus.CITA_SCHEDULED
            transitions[ServiceRequestStatus.CITA_SCHEDULED] = ServiceRequestStatus.IN_PROGRESS
        else:
            transitions[ServiceRequestStatus.PAID] = ServiceRequestStatus.IN_PROGRESS

        transitions[ServiceRequestStatus.IN_PROGRESS] = ServiceRequestStatus.COMPLETED

        return transitions


# === Factory Function ===

async def load_generic_workflow(
    db: asyncpg.Connection,
    workflow_code: str,
) -> PredefinedWorkflow:
    """
    Factory function to load the appropriate generic workflow.

    Automatically selects GenericWorkflowStandard or GenericWorkflowDirectPayment
    based on the workflow_type in the database.

    Args:
        db: Database connection
        workflow_code: Workflow code to load

    Returns:
        Appropriate PredefinedWorkflow subclass instance
    """
    row = await db.fetchrow(
        "SELECT workflow_type, requires_agent_validation FROM workflows WHERE code = $1",
        workflow_code
    )

    if not row:
        raise ValueError(f"Workflow not found: {workflow_code}")

    if row["workflow_type"] == "direct_payment" or not row["requires_agent_validation"]:
        return await GenericWorkflowDirectPayment.from_database(db, workflow_code)
    else:
        return await GenericWorkflowStandard.from_database(db, workflow_code)
