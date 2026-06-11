"""
WorkflowEngine - Orchestrates workflow execution for service requests.

Responsibilities:
- Register and manage available workflows
- Execute workflow steps
- Handle state transitions
- Coordinate with document processor, tariff service, and validators
"""
import asyncio
import json
from typing import Dict, List, Optional, Type, Any
from uuid import UUID
from datetime import datetime, timezone
import logging

import asyncpg

from ..models.enums import (
    WorkflowCode,
    WorkflowCategory,
    ServiceRequestStatus,
    SolicitudType
)
from ..workflows.workflow_interface import (
    WorkflowInterface,
    PredefinedWorkflow,
    WorkflowStep,
    WorkflowContext,
    ValidationResult,
    DocumentRequirement,
    RenovacionMotivo,
    StepType,
)

# All workflows are now v2 (PredefinedWorkflow)
AnyWorkflow = PredefinedWorkflow
from .schema_loader import schema_loader
from .gemini_document_processor import gemini_document_processor
from .tariff_service import tariff_service
from .tariff_calculator import tariff_calculator
from ..repositories.service_request_repository import ServiceRequestRepository

# Repository instance for audit logging
_service_request_repo = ServiceRequestRepository()
from app.core.events import EventBus, EventType

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """
    Central engine for managing and executing service request workflows.

    Usage:
        # Register workflows at startup
        workflow_engine.register(PasaporteWorkflow)
        workflow_engine.register(ResidenciaWorkflow)

        # Get workflow for a code
        workflow = workflow_engine.get_workflow(WorkflowCode.PASAPORTE_NUEVO)

        # Execute a step
        result = await workflow_engine.execute_step(context, step_number)
    """

    def __init__(self):
        self._workflows: Dict[WorkflowCode, AnyWorkflow] = {}
        self._workflow_classes: Dict[WorkflowCode, Type[AnyWorkflow]] = {}
        self._generic_cache: Dict[str, AnyWorkflow] = {}  # code_str → GenericWorkflow (DB-driven)

    def register(self, workflow_class: Type[AnyWorkflow]) -> None:
        """
        Register a workflow class.

        Supports multi-code workflows: if the workflow has get_all_workflow_codes(),
        registers the same instance under each code.

        Args:
            workflow_class: The workflow class to register
        """
        workflow = workflow_class()

        # Multi-code registration: one workflow instance → N workflow codes
        codes = workflow.get_all_workflow_codes()

        for code in codes:
            if code in self._workflows:
                logger.warning(f"Workflow {code.value} already registered, replacing")
            self._workflows[code] = workflow
            self._workflow_classes[code] = workflow_class

        logger.info(f"Registered workflow: {workflow.workflow_code.value} ({len(codes)} codes)")

    def register_many(self, workflow_classes: List[Type[AnyWorkflow]]) -> None:
        """Register multiple workflow classes."""
        for cls in workflow_classes:
            self.register(cls)

    def get_workflow(self, code: WorkflowCode) -> Optional[AnyWorkflow]:
        """Get a registered workflow by code."""
        return self._workflows.get(code)

    def get_workflow_by_string(self, code_str: str) -> Optional[AnyWorkflow]:
        """Get workflow by string code. Checks predefined first, then generic cache."""
        try:
            code = WorkflowCode(code_str)
            return self.get_workflow(code)
        except ValueError:
            # Not a predefined enum — check generic cache (DB-driven workflows)
            cached = self._generic_cache.get(code_str)
            if cached:
                return cached
            logger.warning(f"Unknown workflow code: {code_str}")
            return None

    def get_all_workflows(self) -> Dict[WorkflowCode, AnyWorkflow]:
        """Get all registered workflows."""
        return self._workflows.copy()

    def get_workflows_by_category(self, category: WorkflowCategory) -> List[AnyWorkflow]:
        """Get all workflows in a category (deduplicated, predefined + generic)."""
        seen: set = set()
        result = []
        for w in self._workflows.values():
            if w.category == category and id(w) not in seen:
                seen.add(id(w))
                result.append(w)
        # Include generic (DB-driven) workflows matching category
        for w in self._generic_cache.values():
            if w.category == category and id(w) not in seen:
                seen.add(id(w))
                result.append(w)
        return result

    def is_registered(self, code: WorkflowCode) -> bool:
        """Check if a workflow is registered."""
        return code in self._workflows

    # === Generic Workflow Cache (DB-driven) ===

    def register_generic(self, code: str, workflow: AnyWorkflow) -> None:
        """Register a generic (DB-driven) workflow in the cache."""
        self._generic_cache[code] = workflow
        logger.info(f"Registered generic workflow: {code}")

    def unregister_generic(self, code: str) -> None:
        """Remove a generic workflow from the cache."""
        if code in self._generic_cache:
            del self._generic_cache[code]
            logger.info(f"Unregistered generic workflow: {code}")

    # === Context Management ===

    def create_context(
        self,
        service_request_id: UUID,
        user_id: UUID,
        workflow_code: WorkflowCode,
        solicitud_type: SolicitudType,
        sub_type: Optional[str] = None
    ) -> WorkflowContext:
        """Create a new workflow context."""
        workflow = self.get_workflow(workflow_code)
        if not workflow:
            raise ValueError(f"Unknown workflow: {workflow_code}")

        if sub_type and sub_type not in workflow.allowed_sub_types:
            raise ValueError(
                f"Invalid sub_type '{sub_type}' for workflow {workflow_code}. "
                f"Allowed: {workflow.allowed_sub_types}"
            )

        entity_code = (
            workflow.entity_code.value
            if hasattr(workflow.entity_code, 'value')
            else str(workflow.entity_code)
        )
        context = WorkflowContext(
            service_request_id=service_request_id,
            user_id=user_id,
            workflow_code=workflow_code,
            solicitud_type=solicitud_type,
            sub_type=sub_type,
            entity_code=entity_code
        )

        return context

    async def load_context_from_db(
        self,
        db: asyncpg.Connection,
        service_request_id: UUID
    ) -> Optional[WorkflowContext]:
        """Load workflow context from database."""
        query = """
            SELECT
                sr.id,
                sr.reference,
                sr.user_id,
                sr.workflow_code,
                sr.solicitud_type,
                sr.status,
                sr.form_data,
                sr.entity_code,
                sr.assigned_to,
                sr.payment_id,
                sr.created_at,
                sr.updated_at,
                sr.submitted_at
            FROM service_requests sr
            WHERE sr.id = $1
        """
        row = await db.fetchrow(query, service_request_id)

        if not row:
            return None

        try:
            workflow_code = WorkflowCode(row["workflow_code"])
        except ValueError:
            # Generic (admin-created) workflow — not in enum, use wrapper
            from ..workflows.generic_workflow import _GenericCode
            workflow_code = _GenericCode(row["workflow_code"])

        # Get sub_type and motivo from form_data if present
        # Handle legacy double-encoded form_data (stored as JSON string instead of object)
        form_data = row["form_data"] or {}
        if isinstance(form_data, str):
            try:
                form_data = json.loads(form_data)
                # Handle double-encoding
                if isinstance(form_data, str):
                    form_data = json.loads(form_data)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse form_data for request {service_request_id}")
                form_data = {}
        if not isinstance(form_data, dict):
            form_data = {}
        sub_type = form_data.get("tipo") or form_data.get("sub_type")

        # Extract motivo for RENOVACION tariff calculation
        # motivo can be: VENCIMIENTO, PERDIDA, ROBO, DETERIORO
        motivo_value = form_data.get("motivo")
        motivo = None
        if motivo_value:
            try:
                motivo = RenovacionMotivo(motivo_value)
            except ValueError:
                logger.warning(f"Invalid motivo value: {motivo_value}")

        # Extract is_minor (stored as string "true"/"false" by RadioGroup)
        is_minor_raw = form_data.get("is_minor", False)
        is_minor = is_minor_raw is True or is_minor_raw == "true"

        context = WorkflowContext(
            service_request_id=row["id"],
            user_id=row["user_id"],
            workflow_code=workflow_code,
            solicitud_type=SolicitudType(row["solicitud_type"]) if row["solicitud_type"] else SolicitudType.EXPEDICION,
            sub_type=sub_type,
            motivo=motivo,
            is_minor=is_minor,
            status=ServiceRequestStatus(row["status"]),
            form_data=form_data,
            entity_code=row["entity_code"],
            assigned_to=row["assigned_to"],
            payment_id=row["payment_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            submitted_at=row["submitted_at"],
            reference_number=row["reference"],
        )

        # Load documents
        docs_query = """
            SELECT document_code, id
            FROM service_request_documents
            WHERE service_request_id = $1
        """
        docs = await db.fetch(docs_query, service_request_id)
        context.documents_uploaded = {doc["document_code"]: doc["id"] for doc in docs}

        # Load extracted data for each document
        for doc in docs:
            ext_query = """
                SELECT extraction_data
                FROM service_request_documents
                WHERE id = $1
            """
            ext_row = await db.fetchrow(ext_query, doc["id"])
            if ext_row and ext_row["extraction_data"]:
                # Handle both old (double-encoded string) and new (dict) formats
                data = ext_row["extraction_data"]

                # Keep parsing while data is a string (handles double-encoding)
                max_iterations = 3  # Safety limit
                iteration = 0
                while isinstance(data, str) and iteration < max_iterations:
                    try:
                        data = json.loads(data)
                        iteration += 1
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse extraction_data for doc {doc['id']}")
                        data = {}
                        break

                # Ensure we have a dict
                if not isinstance(data, dict):
                    logger.warning(f"extraction_data is not a dict for doc {doc['id']}: {type(data)}")
                    data = {}

                context.extracted_data[doc["document_code"]] = data

        return context

    async def save_context_to_db(
        self,
        db: asyncpg.Connection,
        context: WorkflowContext
    ) -> None:
        """Save workflow context to database."""
        # Merge sub_type into form_data
        form_data = context.form_data.copy()
        if context.sub_type:
            form_data["sub_type"] = context.sub_type

        query = """
            UPDATE service_requests
            SET
                status = $2,
                form_data = $3::jsonb,
                entity_code = $4,
                assigned_to = $5,
                updated_at = NOW()
            WHERE id = $1
        """
        await db.execute(
            query,
            context.service_request_id,
            context.status.value,
            json.dumps(form_data),
            context.entity_code,
            context.assigned_to
        )

    # === Step Execution ===

    async def execute_step(
        self,
        db: asyncpg.Connection,
        context: WorkflowContext,
        step_number: int,
        step_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a workflow step.

        Args:
            db: Database connection
            context: Current workflow context
            step_number: Step number to execute
            step_data: Optional data for the step (form input, selections, etc.)

        Returns:
            Result of step execution including next step, validations, etc.
        """
        workflow = self.get_workflow(context.workflow_code)
        if not workflow:
            return {"error": f"Unknown workflow: {context.workflow_code}"}

        step = workflow.get_step(step_number)
        if not step:
            return {"error": f"Unknown step: {step_number}"}

        # Check if previous step is required and completed
        if step.requires_previous and step_number > 1:
            if context.current_step < step_number - 1:
                return {
                    "error": "Previous step not completed",
                    "current_step": context.current_step
                }

        result = {
            "step_number": step_number,
            "step_id": step.step_id,
            "step_type": step.step_type.value,
            "success": True
        }

        try:
            if step.step_type == StepType.SELECTION:
                result.update(await self._execute_selection_step(workflow, context, step, step_data))

            elif step.step_type == StepType.DOCUMENT_UPLOAD:
                result.update(await self._execute_document_step(db, workflow, context, step, step_data))

            elif step.step_type == StepType.FORM_REVIEW:
                result.update(await self._execute_form_review_step(db, workflow, context, step, step_data))

            elif step.step_type == StepType.VALIDATION:
                result.update(await self._execute_validation_step(workflow, context, step))

            elif step.step_type == StepType.PAYMENT:
                result.update(await self._execute_payment_step(db, workflow, context, step, step_data))

            elif step.step_type == StepType.CONFIRMATION:
                result.update(await self._execute_confirmation_step(db, workflow, context, step))

            else:
                # Custom step - delegate to workflow
                result.update(await self._execute_custom_step(db, workflow, context, step, step_data))

            # Update context step if successful
            if result.get("success", False):
                context.current_step = step_number
                context.updated_at = datetime.now(timezone.utc)

            # Add next step info
            next_step = workflow.get_step(step_number + 1)
            if next_step:
                result["next_step"] = {
                    "number": next_step.step_number,
                    "id": next_step.step_id,
                    "type": next_step.step_type.value,
                    "title_es": next_step.title_es
                }

        except Exception as e:
            logger.exception(f"Error executing step {step_number}: {e}")
            result["success"] = False
            result["error"] = str(e)

        return result

    async def _execute_selection_step(
        self,
        workflow: AnyWorkflow,
        context: WorkflowContext,
        step: WorkflowStep,
        step_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute a selection step (e.g., choose sub-type)."""
        if not step_data or "selection" not in step_data:
            # Return available options
            return {
                "options": workflow.allowed_sub_types,
                "requires_selection": True
            }

        selection = step_data["selection"]
        if selection not in workflow.allowed_sub_types:
            return {
                "success": False,
                "error": f"Invalid selection: {selection}",
                "options": workflow.allowed_sub_types
            }

        context.sub_type = selection

        # Get documents required for this selection (V2 signature)
        docs = workflow.get_document_requirements(
            solicitud_type=SolicitudType.EXPEDICION,
            context=context
        )

        return {
            "selection": selection,
            "documents_required": [
                {
                    "code": d.document_code,
                    "name_es": d.document_name_es,
                    "is_required": d.is_required,
                    "schema_key": d.schema_key,
                    "instructions_es": d.instructions_es
                }
                for d in docs if d.should_show(context)
            ]
        }

    async def _execute_document_step(
        self,
        db: asyncpg.Connection,
        workflow: AnyWorkflow,
        context: WorkflowContext,
        step: WorkflowStep,
        step_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute document upload step with extraction."""
        # Get required documents for current context
        applicable_docs = step.get_applicable_documents(context)

        if not step_data:
            # Return what's needed
            return {
                "documents_required": [
                    {
                        "code": d.document_code,
                        "name_es": d.document_name_es,
                        "is_required": d.is_required,
                        "uploaded": d.document_code in context.documents_uploaded,
                        "schema_key": d.schema_key
                    }
                    for d in applicable_docs
                ]
            }

        # Document upload is handled by separate endpoint
        # This step just validates all required docs are uploaded

        missing = []
        for doc in applicable_docs:
            if doc.is_required and doc.document_code not in context.documents_uploaded:
                missing.append({
                    "code": doc.document_code,
                    "name_es": doc.document_name_es
                })

        if missing:
            return {
                "success": False,
                "error": "Missing required documents",
                "missing_documents": missing
            }

        return {
            "all_documents_uploaded": True,
            "documents_count": len(context.documents_uploaded)
        }

    def _apply_form_mapping(
        self,
        extracted_data: Dict[str, Any],
        form_mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Apply form mapping to transform extracted data into form fields.

        Args:
            extracted_data: Raw extracted data from documents
                Example: {"dip": {"titular": {"nombres": "JUAN", "apellidos": "PEREZ"}}}
            form_mapping: Mapping from form field to extraction path
                Example: {"nombres": "dip.titular.nombres"}

        Returns:
            Mapped form data with flat field names
                Example: {"nombres": "JUAN", "apellidos": "PEREZ"}
        """
        mapped_data: Dict[str, Any] = {}

        for form_field, extraction_path in form_mapping.items():
            try:
                # Navigate the dot path in extracted_data
                parts = extraction_path.split('.')
                value = extracted_data

                for part in parts:
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        value = None
                        break

                if value is not None:
                    mapped_data[form_field] = value
                    logger.debug(f"Mapped {extraction_path} -> {form_field}: {value}")

            except Exception as e:
                logger.warning(f"Error mapping {extraction_path} to {form_field}: {e}")
                continue

        return mapped_data

    async def _execute_form_review_step(
        self,
        db: asyncpg.Connection,
        workflow: AnyWorkflow,
        context: WorkflowContext,
        step: WorkflowStep,
        step_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute form review step.

        Applies form_mapping from workflow to transform extracted_data
        into properly mapped form_data for frontend display.
        """
        if not step_data:
            # Get form mapping from workflow and apply it to extracted data
            try:
                form_mapping = workflow.get_form_mapping(context)
                mapped_form_data = self._apply_form_mapping(context.extracted_data, form_mapping)

                # Merge with any existing form_data (preserves user-entered data)
                final_form_data = {**mapped_form_data, **context.form_data}

                logger.info(
                    f"Form mapping applied: {len(form_mapping)} mappings, "
                    f"{len(mapped_form_data)} fields populated"
                )
            except Exception as e:
                logger.warning(f"Error applying form mapping: {e}, returning raw data")
                final_form_data = context.form_data

            # === VALIDATION IMMÉDIATE après auto-fill ===
            # Valide l'éligibilité (âge, etc.) AVANT que l'utilisateur puisse continuer
            # Update context with final_form_data for validation
            context.form_data = final_form_data

            validation_results = workflow.validate_step(step.step_number, context)
            errors = [r for r in validation_results if r.is_error]
            warnings = [r for r in validation_results if r.is_warning]

            if errors:
                # Retourne les erreurs bloquantes - l'utilisateur ne peut pas continuer
                logger.warning(
                    f"Validation errors on form_review step {step.step_number}: "
                    f"{[e.rule_id for e in errors]}"
                )

                # === AUDIT TRAIL: Log validation failure ===
                try:
                    await _service_request_repo.log_validation_failure(
                        db=db,
                        request_id=context.request_id,
                        validation_type="form_review_eligibility",
                        errors=[
                            {
                                "rule_id": e.rule_id,
                                "message_es": e.message_es,
                                "field_name": e.field_name
                            }
                            for e in errors
                        ],
                        step_id=step.step_id,
                        user_id=context.user_id if hasattr(context, 'user_id') else None
                    )
                except Exception as audit_error:
                    logger.error(f"Failed to log validation failure to audit trail: {audit_error}")

                return {
                    "form_data": final_form_data,
                    "extracted_data": context.extracted_data,
                    "requires_review": True,
                    "validation_blocked": True,
                    "can_continue": False,
                    "errors": [
                        {
                            "rule_id": e.rule_id,
                            "message_es": e.message_es,
                            "field_name": e.field_name,
                            "severity": "error"
                        }
                        for e in errors
                    ],
                    "warnings": [
                        {
                            "rule_id": w.rule_id,
                            "message_es": w.message_es,
                            "field_name": w.field_name,
                            "severity": "warning"
                        }
                        for w in warnings
                    ]
                }

            # Pas d'erreurs bloquantes - l'utilisateur peut continuer
            return {
                "form_data": final_form_data,
                "extracted_data": context.extracted_data,
                "requires_review": True,
                "can_continue": True,
                "warnings": [
                    {
                        "rule_id": w.rule_id,
                        "message_es": w.message_es,
                        "field_name": w.field_name,
                        "severity": "warning"
                    }
                    for w in warnings
                ] if warnings else []
            }

        # User has confirmed/corrected data
        if "confirmed_data" in step_data:
            context.form_data.update(step_data["confirmed_data"])

            # Run step validation after data confirmation
            # This catches age eligibility errors, etc.
            validation_results = workflow.validate_step(step.step_number, context)
            errors = [r for r in validation_results if r.is_error]
            warnings = [r for r in validation_results if r.is_warning]

            if errors:
                # Return errors to block progression
                return {
                    "form_data_updated": True,
                    "validation_failed": True,
                    "has_errors": True,
                    "errors": [
                        {
                            "rule_id": e.rule_id,
                            "message_es": e.message_es,
                            "field_name": e.field_name
                        }
                        for e in errors
                    ],
                    "warnings": [
                        {
                            "rule_id": w.rule_id,
                            "message_es": w.message_es,
                            "field_name": w.field_name
                        }
                        for w in warnings
                    ],
                    "success": False
                }

            # Validation passed
            return {
                "form_data_updated": True,
                "validation_passed": True,
                "warnings": [
                    {
                        "rule_id": w.rule_id,
                        "message_es": w.message_es,
                        "field_name": w.field_name
                    }
                    for w in warnings
                ] if warnings else [],
                "success": True
            }

        return {
            "form_data_updated": True
        }

    async def _execute_validation_step(
        self,
        workflow: AnyWorkflow,
        context: WorkflowContext,
        step: WorkflowStep
    ) -> Dict[str, Any]:
        """Execute validation step with cross-document checks."""
        results = workflow.validate_step(step.step_number, context)
        context.validation_results = results

        errors = [r for r in results if r.is_error]
        warnings = [r for r in results if r.is_warning]

        return {
            "validation_complete": True,
            "has_errors": len(errors) > 0,
            "errors": [
                {
                    "rule_id": e.rule_id,
                    "message_es": e.message_es,
                    "document_code": e.document_code
                }
                for e in errors
            ],
            "warnings": [
                {
                    "rule_id": w.rule_id,
                    "message_es": w.message_es,
                    "document_code": w.document_code
                }
                for w in warnings
            ],
            "success": len(errors) == 0
        }

    async def _execute_payment_step(
        self,
        db: asyncpg.Connection,
        workflow: AnyWorkflow,
        context: WorkflowContext,
        step: WorkflowStep,
        step_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute payment step.

        Uses TariffService for unified tariff calculation.
        Checks if payment is blocked (requires agent validation first).
        """
        # Check if payment is blocked until agent validation
        requires_status = step.config.get("requires_status")
        if requires_status:
            if context.status.value != requires_status:
                blocked_message = step.config.get(
                    "blocked_message_es",
                    "El pago está bloqueado hasta que se valide su solicitud."
                )
                return {
                    "success": False,
                    "payment_blocked": True,
                    "error": blocked_message,
                    "current_status": context.status.value,
                    "required_status": requires_status
                }

        # Use TariffCalculator for explicit workflow-type handling
        # - PredefinedWorkflow: uses hardcoded tariffs from workflow code
        # - GenericWorkflow: uses database (workflow_tariffs table)
        tariff_result = await tariff_calculator.calculate(
            db=db,
            workflow=workflow,
            context=context
        )

        if not step_data:
            # Return payment info
            return {
                "amount": tariff_result.get("total_amount", 0),
                "tariff_breakdown": tariff_result,
                "currency": tariff_result.get("currency", "XAF"),
                "requires_payment": tariff_result.get("total_amount", 0) > 0
            }

        # Payment processing is handled by payment module
        # This step just verifies payment was completed
        if context.payment_status == "completed":
            return {"payment_complete": True}

        return {
            "success": False,
            "error": "Payment not completed",
            "payment_status": context.payment_status
        }

    async def _execute_confirmation_step(
        self,
        db: asyncpg.Connection,
        workflow: AnyWorkflow,
        context: WorkflowContext,
        step: WorkflowStep
    ) -> Dict[str, Any]:
        """
        Execute confirmation and submission step.

        STRICT VALIDATION: All previous steps MUST be completed before submission.
        """
        errors = []

        # 1. Check for any existing validation errors
        if context.has_errors():
            errors.extend([
                {"rule_id": e.rule_id, "message_es": e.message_es}
                for e in context.get_errors()
            ])

        # 2. Verify all required documents are uploaded
        required_docs = workflow.get_required_documents(context)
        if required_docs:
            required_codes = {d.document_code for d in required_docs if d.is_required}
            provided_codes = set(context.provided_documents.keys()) if context.provided_documents else set()
            missing_docs = required_codes - provided_codes
            if missing_docs:
                errors.append({
                    "rule_id": "MISSING_DOCUMENTS",
                    "message_es": f"Documentos requeridos no proporcionados: {', '.join(missing_docs)}"
                })

        # 3. Verify form data has been reviewed (form_data should have required fields)
        form_mapping = workflow.get_form_mapping(context) if hasattr(workflow, 'get_form_mapping') else {}
        if form_mapping:
            required_fields = list(form_mapping.keys())
            missing_fields = [f for f in required_fields if not context.form_data.get(f)]
            if missing_fields:
                errors.append({
                    "rule_id": "INCOMPLETE_FORM",
                    "message_es": f"Campos requeridos no completados: {', '.join(missing_fields[:5])}"
                })

        # 4. Verify current step is at or past confirmation step
        confirmation_step_number = step.step_number
        if context.current_step < confirmation_step_number - 1:
            errors.append({
                "rule_id": "STEPS_NOT_COMPLETED",
                "message_es": f"Debe completar todas las etapas anteriores. Etapa actual: {context.current_step}, requerida: {confirmation_step_number - 1}"
            })

        # If any errors, reject submission
        if errors:
            return {
                "success": False,
                "error": "No se puede enviar la solicitud. Complete todas las etapas requeridas.",
                "errors": errors
            }

        # All validations passed - update status to submitted
        context.status = ServiceRequestStatus.SUBMITTED
        context.submitted_at = datetime.now(timezone.utc)

        # Save to database
        await self.save_context_to_db(db, context)

        return {
            "submitted": True,
            "reference": str(context.service_request_id)[:8].upper(),
            "submitted_at": context.submitted_at.isoformat(),
            "next_status": workflow.get_next_status(context.status).value if workflow.get_next_status(context.status) else None
        }

    async def _execute_custom_step(
        self,
        db: asyncpg.Connection,
        workflow: AnyWorkflow,
        context: WorkflowContext,
        step: WorkflowStep,
        step_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute a custom workflow-specific step.

        Handles special step types like:
        - select_classes: Multi-selection with age validation (Conducir)
        """
        # === Handle select_classes step (Conducir workflow) ===
        if step.step_id == "select_classes":
            return await self._execute_select_classes_step(db, workflow, context, step, step_data)

        # Default: placeholder for other custom steps
        return {
            "custom_step": True,
            "step_id": step.step_id
        }

    async def _execute_select_classes_step(
        self,
        db: asyncpg.Connection,
        workflow: AnyWorkflow,
        context: WorkflowContext,
        step: WorkflowStep,
        step_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute the select_classes step for Conducir workflow.

        Features:
        - Returns available options with min_age info
        - Validates age eligibility if birth date is known
        - Blocks selection if age requirements not met
        - Logs validation failures to audit trail
        """
        config = step.config or {}
        options = config.get("options", [])

        if not step_data or "selected_classes" not in step_data:
            # Return available options with age requirements
            # Frontend can grey out options if user's birth date is known
            return {
                "requires_selection": True,
                "options": options,
                "max_selection": config.get("max_selection", 3),
                "user_birth_date": context.form_data.get("fecha_nacimiento") if context.form_data else None
            }

        # User has selected classes
        selected_classes = step_data["selected_classes"]

        # Validate selection
        valid_class_ids = [opt["id"] for opt in options]
        invalid_classes = [c for c in selected_classes if c not in valid_class_ids]
        if invalid_classes:
            return {
                "success": False,
                "error": f"Clases inválidas: {', '.join(invalid_classes)}",
                "options": options
            }

        # Store in context
        if not context.form_data:
            context.form_data = {}
        context.form_data["select_classes"] = selected_classes

        # === Validate age if birth date is known ===
        fecha_nacimiento = context.form_data.get("fecha_nacimiento")
        if fecha_nacimiento:
            # Call workflow validation
            validation_results = workflow.validate_step(step.step_number, context)
            errors = [r for r in validation_results if r.is_error]

            if errors:
                logger.warning(
                    f"Age validation failed on select_classes: {[e.rule_id for e in errors]}"
                )

                # === AUDIT TRAIL: Log validation failure ===
                try:
                    await _service_request_repo.log_validation_failure(
                        db=db,
                        request_id=context.request_id,
                        validation_type="age_eligibility",
                        errors=[
                            {
                                "rule_id": e.rule_id,
                                "message_es": e.message_es,
                                "field_name": e.field_name,
                                "selected_classes": selected_classes
                            }
                            for e in errors
                        ],
                        step_id=step.step_id,
                        user_id=context.user_id if hasattr(context, 'user_id') else None
                    )
                except Exception as audit_error:
                    logger.error(f"Failed to log validation failure to audit trail: {audit_error}")

                return {
                    "success": False,
                    "validation_blocked": True,
                    "can_continue": False,
                    "selected_classes": selected_classes,
                    "errors": [
                        {
                            "rule_id": e.rule_id,
                            "message_es": e.message_es,
                            "field_name": e.field_name,
                            "severity": "error"
                        }
                        for e in errors
                    ]
                }

        # Selection valid
        return {
            "success": True,
            "selected_classes": selected_classes,
            "can_continue": True
        }

    # === Status Transitions ===

    async def transition_status(
        self,
        db: asyncpg.Connection,
        context: WorkflowContext,
        new_status: ServiceRequestStatus,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transition service request to a new status.

        Args:
            db: Database connection
            context: Current workflow context
            new_status: Target status
            reason: Optional reason for transition (e.g., rejection reason)

        Returns:
            Result of transition including success status
        """
        workflow = self.get_workflow(context.workflow_code)
        if not workflow:
            return {"error": f"Unknown workflow: {context.workflow_code}"}

        if not workflow.can_transition_to(context.status, new_status):
            return {
                "success": False,
                "error": f"Cannot transition from {context.status.value} to {new_status.value}"
            }

        old_status = context.status
        context.status = new_status
        context.updated_at = datetime.now(timezone.utc)

        # Record in history
        history_query = """
            INSERT INTO service_request_history
            (service_request_id, previous_status, new_status, notes, created_at)
            VALUES ($1, $2, $3, $4, NOW())
        """
        await db.execute(
            history_query,
            context.service_request_id,
            old_status.value,
            new_status.value,
            reason
        )

        # Update service_requests table
        update_query = """
            UPDATE service_requests
            SET status = $2, updated_at = NOW()
            WHERE id = $1
        """

        # Special handling for certain statuses
        if new_status == ServiceRequestStatus.REJECTED:
            update_query = """
                UPDATE service_requests
                SET status = $2, rejection_reason = $3, updated_at = NOW()
                WHERE id = $1
            """
            await db.execute(update_query, context.service_request_id, new_status.value, reason)
        elif new_status == ServiceRequestStatus.SUBMITTED:
            update_query = """
                UPDATE service_requests
                SET status = $2, submitted_at = NOW(), updated_at = NOW()
                WHERE id = $1
            """
            await db.execute(update_query, context.service_request_id, new_status.value)
        elif new_status == ServiceRequestStatus.COMPLETED:
            update_query = """
                UPDATE service_requests
                SET status = $2, completed_at = NOW(), updated_at = NOW()
                WHERE id = $1
            """
            await db.execute(update_query, context.service_request_id, new_status.value)

            # Publish REQUEST_COMPLETED event for notifications
            try:
                # Get user data for notification
                user_data = await db.fetchrow(
                    """SELECT u.id, u.email, u.phone_number as phone, u.first_name, u.last_name, u.preferred_language,
                              sr.workflow_code, sr.reference
                       FROM users u
                       JOIN service_requests sr ON sr.user_id = u.id
                       WHERE sr.id = $1""",
                    context.service_request_id
                )
                if user_data:
                    EventBus.publish_nowait(EventType.REQUEST_COMPLETED, {
                        "request_id": str(context.service_request_id),
                        "user_id": str(user_data["id"]),
                        "user_email": user_data["email"],
                        "user_phone": user_data["phone"],
                        "user_name": f"{user_data['first_name'] or ''} {user_data['last_name'] or ''}".strip(),
                        "preferred_language": user_data.get("preferred_language", "es"),
                        "workflow_code": user_data["workflow_code"],
                        "reference": user_data["reference"],
                    })
                    logger.info(f"REQUEST_COMPLETED event published for request {context.service_request_id}")
            except Exception as e:
                logger.error(f"Failed to publish REQUEST_COMPLETED event: {e}")
        else:
            await db.execute(update_query, context.service_request_id, new_status.value)

        logger.info(
            f"Transitioned service request {context.service_request_id} "
            f"from {old_status.value} to {new_status.value}"
        )

        return {
            "success": True,
            "previous_status": old_status.value,
            "new_status": new_status.value,
            "next_status": workflow.get_next_status(new_status).value if workflow.get_next_status(new_status) else None
        }

    # === Workflow Info ===

    def _deduplicated_workflows(self) -> List[AnyWorkflow]:
        """Return unique workflow instances (multi-code workflows appear once)."""
        seen: set = set()
        result = []
        for w in self._workflows.values():
            if id(w) not in seen:
                seen.add(id(w))
                result.append(w)
        return result

    def get_available_workflows(self) -> List[Dict[str, Any]]:
        """Get list of all available workflows (predefined + generic, deduplicated)."""
        predefined = [w.get_info() for w in self._deduplicated_workflows()]
        generic = [w.get_info() for w in self._generic_cache.values()]
        return predefined + generic

    def get_workflows_for_display(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get workflows grouped by category for display (deduplicated)."""
        result: Dict[str, List[Dict[str, Any]]] = {}

        for workflow in self._deduplicated_workflows():
            category = workflow.category.value
            if category not in result:
                result[category] = []

            entity_code = (
                workflow.entity_code.value
                if hasattr(workflow.entity_code, 'value')
                else str(workflow.entity_code)
            )
            result[category].append({
                "code": workflow.workflow_code.value,
                "name_es": workflow.service_name_es,
                "entity_code": entity_code,
                "sub_types": workflow.allowed_sub_types
            })

        return result


# Singleton instance
workflow_engine = WorkflowEngine()


def register_all_workflows() -> None:
    """
    Auto-discover and register all PredefinedWorkflow subclasses.

    Uses Python's __subclasses__() to find all concrete workflow classes.
    Requires that workflow modules are imported (via __init__.py) so that
    Python knows about the subclasses.

    Filters out GenericWorkflow classes (is_generic=True) which are DB-driven.
    """
    # Force-import all workflow modules so __subclasses__() can discover them
    import app.modules.service_requests.workflows  # noqa: F401

    registered: set = set()
    for cls in PredefinedWorkflow.__subclasses__():
        if getattr(cls, 'is_generic', False):
            continue
        if cls in registered:
            continue
        try:
            workflow_engine.register(cls)
            registered.add(cls)
        except Exception as e:
            logger.error(f"Failed to register workflow {cls.__name__}: {e}")

    logger.info(f"Auto-registered {len(registered)} workflows")


async def load_generic_workflows(db) -> int:
    """Load all active generic workflows from database into engine cache.

    Called at startup (after sync) and after admin activates/deactivates a workflow.
    Uses the existing load_generic_workflow() factory which selects Standard or
    DirectPayment based on workflow_type in DB.

    Returns number of workflows loaded.
    """
    from ..workflows.generic_workflow import load_generic_workflow

    rows = await db.fetch(
        "SELECT code FROM workflows WHERE is_generic = TRUE AND is_active = TRUE"
    )

    # Clear existing generic cache before full reload
    workflow_engine._generic_cache.clear()

    loaded = 0
    for row in rows:
        try:
            wf = await load_generic_workflow(db, row["code"])
            workflow_engine.register_generic(row["code"], wf)
            loaded += 1
        except Exception as e:
            logger.error(f"Failed to load generic workflow {row['code']}: {e}")

    logger.info(f"Loaded {loaded} generic workflows from database")
    return loaded


def resolve_workflow_code(session: Dict[str, Any]) -> str:
    """Resolve base workflow_code to specific sub-type code.

    Multi-subtype workflows (Pasaporte, Conducir, Contrato, Visado) store a
    base code at session creation.  This function resolves it to the specific
    variant using motivo / sub_type / solicitud_type from the session.

    Resolution is handled by PredefinedWorkflow.get_workflow_code_for_subtype()
    which auto-matches the key against workflow code names. Workflows with
    non-standard naming define _subtype_code_aliases for edge cases.

    Safe: returns the original code if resolution is not possible.
    """
    base_code = session.get("workflow_code")
    if not base_code:
        logger.error("resolve_workflow_code called with missing workflow_code in session")
        return ""

    wf = workflow_engine.get_workflow_by_string(base_code)
    if not wf:
        return base_code

    # Single-code workflows: no resolution needed
    all_codes = wf.get_all_workflow_codes()
    if len(all_codes) <= 1:
        return base_code

    # Build resolution key (priority: sub_type > motivo > solicitud_type)
    resolution_key = session.get("sub_type") or session.get("motivo")
    if not resolution_key:
        solicitud_type = session.get("solicitud_type")
        if solicitud_type:
            resolution_key = solicitud_type
        else:
            return base_code

    # Normalize: always UPPER for matching against WorkflowCode enum values
    resolution_key = str(resolution_key).strip().upper()
    if not resolution_key:
        return base_code

    try:
        resolved = wf.get_workflow_code_for_subtype(resolution_key)
        resolved_str = resolved.value
        if resolved_str != base_code:
            logger.debug(
                f"Resolved workflow_code: {base_code} → {resolved_str} "
                f"(key={resolution_key})"
            )
        return resolved_str
    except (ValueError, KeyError, AttributeError) as e:
        logger.warning(
            f"Failed to resolve workflow_code {base_code} "
            f"with key={resolution_key}: {e}"
        )
        return base_code


async def resolve_workflow_sites(db, workflow_code: str) -> List[Dict]:
    """Resolve available sites for a workflow via entities.workflow_codes.

    Queries entities that declare this workflow_code in their workflow_codes
    JSONB array, then returns their active entity_locations.

    Returns list of dicts with: id, entity_code, city, location_name,
    location_address, is_main_office.

    Raises ValueError if no entity declares this workflow or no active sites exist.
    """
    rows = await db.fetch(
        """
        SELECT
            el.id, el.entity_code, el.city, el.location_name,
            el.location_address, el.is_main_office
        FROM entity_locations el
        INNER JOIN entities e ON el.entity_code = e.code
        WHERE e.workflow_codes @> to_jsonb($1::text)
          AND el.is_active = TRUE
          AND e.is_active = TRUE
        ORDER BY el.city, el.is_main_office DESC, el.location_name
        """,
        workflow_code,
    )

    if not rows:
        raise ValueError(
            f"No active site found for workflow '{workflow_code}'. "
            f"Check entities.workflow_codes and entity_locations configuration."
        )

    return [dict(r) for r in rows]


async def resolve_entity_code_from_location(db, entity_location_id: UUID) -> str:
    """Derive entity_code from an entity_location_id.

    Single PK lookup — O(1).
    Raises ValueError if location not found or inactive.
    """
    entity_code = await db.fetchval(
        "SELECT entity_code FROM entity_locations "
        "WHERE id = $1 AND is_active = TRUE",
        entity_location_id,
    )
    if not entity_code:
        raise ValueError(
            f"Entity location '{entity_location_id}' not found or inactive."
        )
    return entity_code


# Auto-register workflows on module import
register_all_workflows()
