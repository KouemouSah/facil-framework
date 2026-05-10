"""
Unit tests for ConducirWorkflow v2 (Option C - Dynamic Form Review Architecture)

Tests the migration from BaseWorkflow to PredefinedWorkflow architecture:
1. Workflow initialization and properties
2. form_review_1 and form_review_2 configuration
3. Conditional sections based on sub_type
4. Document requirements by type
5. Cross-validation rules
6. Tariff calculation

@date 2026-02-05
@migration Phase 5 - Conducir Workflow
"""
import pytest
from datetime import date, timedelta

from app.modules.service_requests.workflows.conducir_workflow import (
    ConducirWorkflow,
    LicenseClass,
    ApplicantType,
    DuplicadoMotivo,
    get_conducir_workflow
)
from app.modules.service_requests.workflows.workflow_interface import (
    WorkflowContext,
    StepType,
)
from app.modules.service_requests.models.enums import (
    SolicitudType,
    WorkflowCode,
    WorkflowCategory,
    EntityCode,
)


class TestConducirWorkflowV2Properties:
    """Test workflow properties are correctly defined."""

    def test_workflow_code(self):
        workflow = ConducirWorkflow()
        assert workflow.workflow_code == WorkflowCode.CONDUCIR_NUEVO

    def test_category(self):
        workflow = ConducirWorkflow()
        assert workflow.category == WorkflowCategory.CONDUCCION

    def test_entity_code(self):
        workflow = ConducirWorkflow()
        assert workflow.entity_code == EntityCode.DGT

    def test_service_name_es(self):
        workflow = ConducirWorkflow()
        assert workflow.service_name_es == "Solicitud de Certificado para Conducir"

    def test_allowed_solicitud_types(self):
        workflow = ConducirWorkflow()
        types = workflow.allowed_solicitud_types
        assert SolicitudType.EXPEDICION in types
        assert SolicitudType.RENOVACION in types
        assert SolicitudType.DUPLICADO in types

    def test_requires_appointment(self):
        workflow = ConducirWorkflow()
        assert workflow.requires_appointment is True

    def test_requires_agent_review(self):
        workflow = ConducirWorkflow()
        assert workflow.requires_agent_review is True

    def test_requires_nota_ingreso(self):
        workflow = ConducirWorkflow()
        assert workflow.requires_nota_ingreso is False


class TestConducirWorkflowV2Steps:
    """Test workflow steps are correctly defined."""

    def test_total_steps(self):
        workflow = ConducirWorkflow()
        assert workflow.get_total_steps() == 10  # Steps 0-9

    def test_form_review_steps_exist(self):
        workflow = ConducirWorkflow()
        form_review_1 = workflow.get_step_by_id("form_review_1")
        form_review_2 = workflow.get_step_by_id("form_review_2")

        assert form_review_1 is not None
        assert form_review_2 is not None
        assert form_review_1.step_type == StepType.FORM_REVIEW
        assert form_review_2.step_type == StepType.FORM_REVIEW

    def test_step_order(self):
        workflow = ConducirWorkflow()
        steps = workflow.get_steps()
        step_ids = [s.step_id for s in steps]

        expected_order = [
            "select_type",
            "select_applicant_type",
            "select_classes",
            "select_motivo",
            "upload_documents",
            "form_review_1",
            "form_review_2",
            "payment",
            "appointment",
            "confirmation"
        ]
        assert step_ids == expected_order


class TestFormReview1Config:
    """Test form_review_1 configuration (personal data)."""

    def test_form_review_1_has_sections(self):
        workflow = ConducirWorkflow()
        step = workflow.get_step_by_id("form_review_1")
        sections = step.config.get("sections", [])

        assert len(sections) == 2  # identificacion + datos_personales

    def test_form_review_1_section_ids(self):
        workflow = ConducirWorkflow()
        step = workflow.get_step_by_id("form_review_1")
        sections = step.config.get("sections", [])
        section_ids = [s["id"] for s in sections]

        assert "identificacion" in section_ids
        assert "datos_personales" in section_ids

    def test_identificacion_section_fields(self):
        workflow = ConducirWorkflow()
        step = workflow.get_step_by_id("form_review_1")
        sections = step.config.get("sections", [])
        identificacion = next(s for s in sections if s["id"] == "identificacion")

        field_keys = [f["key"] for f in identificacion["fields"]]
        assert "tipo_identificacion" in field_keys
        assert "numero_identificacion" in field_keys

    def test_datos_personales_section_fields(self):
        workflow = ConducirWorkflow()
        step = workflow.get_step_by_id("form_review_1")
        sections = step.config.get("sections", [])
        datos_personales = next(s for s in sections if s["id"] == "datos_personales")

        field_keys = [f["key"] for f in datos_personales["fields"]]
        assert "apellidos" in field_keys
        assert "nombres" in field_keys
        assert "fecha_nacimiento" in field_keys
        assert "nacionalidad" in field_keys
        assert "domicilio" in field_keys


class TestFormReview2Config:
    """Test form_review_2 configuration (request-specific data)."""

    def test_form_review_2_has_sections(self):
        workflow = ConducirWorkflow()
        step = workflow.get_step_by_id("form_review_2")
        sections = step.config.get("sections", [])

        assert len(sections) == 4  # solicitud + certificado_actual + permiso_extranjero + aptitud_medica

    def test_form_review_2_section_ids(self):
        workflow = ConducirWorkflow()
        step = workflow.get_step_by_id("form_review_2")
        sections = step.config.get("sections", [])
        section_ids = [s["id"] for s in sections]

        assert "solicitud" in section_ids
        assert "certificado_actual" in section_ids
        assert "permiso_extranjero" in section_ids
        assert "aptitud_medica" in section_ids

    def test_certificado_actual_condition(self):
        """certificado_actual should only show for RENOVACION/EXTENSION."""
        workflow = ConducirWorkflow()
        step = workflow.get_step_by_id("form_review_2")
        sections = step.config.get("sections", [])
        cert_section = next(s for s in sections if s["id"] == "certificado_actual")

        condition = cert_section.get("condition")
        assert condition is not None
        assert "OR" in condition
        or_conditions = condition["OR"]
        sub_types = [c.get("sub_type") for c in or_conditions]
        assert "RENOVACION" in sub_types
        assert "EXTENSION" in sub_types

    def test_permiso_extranjero_condition(self):
        """permiso_extranjero should only show for CANJE."""
        workflow = ConducirWorkflow()
        step = workflow.get_step_by_id("form_review_2")
        sections = step.config.get("sections", [])
        perm_section = next(s for s in sections if s["id"] == "permiso_extranjero")

        condition = perm_section.get("condition")
        assert condition is not None
        assert condition.get("sub_type") == "CANJE"

    def test_aptitud_medica_condition(self):
        """aptitud_medica should only show for NUEVO/EXTENSION."""
        workflow = ConducirWorkflow()
        step = workflow.get_step_by_id("form_review_2")
        sections = step.config.get("sections", [])
        aptitud_section = next(s for s in sections if s["id"] == "aptitud_medica")

        condition = aptitud_section.get("condition")
        assert condition is not None
        assert "OR" in condition
        or_conditions = condition["OR"]
        sub_types = [c.get("sub_type") for c in or_conditions]
        assert "NUEVO" in sub_types
        assert "EXTENSION" in sub_types


class TestDocumentRequirements:
    """Test document requirements by request type."""

    def test_nuevo_requires_medical_certificate(self):
        """NUEVO should require medical certificate."""
        workflow = ConducirWorkflow()
        context = WorkflowContext(
            request_id="test",
            user_id="test",
            sub_type="NUEVO",
            form_data={"sub_type": "NUEVO", "applicant_type": "CITIZEN_GQ"}
        )
        reqs = workflow.get_document_requirements(SolicitudType.EXPEDICION, context=context)
        doc_codes = [r.document_code for r in reqs]

        assert "certificado_medico" in doc_codes

    def test_canje_no_medical_certificate(self):
        """CANJE should NOT require medical certificate."""
        workflow = ConducirWorkflow()
        context = WorkflowContext(
            request_id="test",
            user_id="test",
            sub_type="CANJE",
            form_data={"sub_type": "CANJE", "applicant_type": "RESIDENT"}
        )
        reqs = workflow.get_document_requirements(SolicitudType.RENOVACION, context=context)
        doc_codes = [r.document_code for r in reqs]

        assert "certificado_medico" not in doc_codes
        assert "permiso_extranjero" in doc_codes

    def test_renovacion_no_medical_certificate(self):
        """RENOVACION should NOT require medical certificate."""
        workflow = ConducirWorkflow()
        context = WorkflowContext(
            request_id="test",
            user_id="test",
            sub_type="RENOVACION",
            form_data={"sub_type": "RENOVACION", "applicant_type": "CITIZEN_GQ"}
        )
        reqs = workflow.get_document_requirements(SolicitudType.RENOVACION, context=context)
        doc_codes = [r.document_code for r in reqs]

        assert "certificado_medico" not in doc_codes
        assert "certificado_actual" in doc_codes

    def test_duplicado_perdida_requires_denuncia(self):
        """DUPLICADO with PERDIDA motivo should require denuncia."""
        workflow = ConducirWorkflow()
        context = WorkflowContext(
            request_id="test",
            user_id="test",
            sub_type="DUPLICADO",
            form_data={"sub_type": "DUPLICADO", "applicant_type": "CITIZEN_GQ", "motivo": "PERDIDA"}
        )
        reqs = workflow.get_document_requirements(SolicitudType.DUPLICADO, context=context)
        doc_codes = [r.document_code for r in reqs]

        assert "denuncia" in doc_codes

    def test_duplicado_deterioro_no_denuncia(self):
        """DUPLICADO with DETERIORO motivo should NOT require denuncia."""
        workflow = ConducirWorkflow()
        context = WorkflowContext(
            request_id="test",
            user_id="test",
            sub_type="DUPLICADO",
            form_data={"sub_type": "DUPLICADO", "applicant_type": "CITIZEN_GQ", "motivo": "DETERIORO"}
        )
        reqs = workflow.get_document_requirements(SolicitudType.DUPLICADO, context=context)
        doc_codes = [r.document_code for r in reqs]

        assert "denuncia" not in doc_codes

    def test_extension_requires_medical_and_current_certificate(self):
        """EXTENSION should require both medical certificate and current certificate."""
        workflow = ConducirWorkflow()
        context = WorkflowContext(
            request_id="test",
            user_id="test",
            sub_type="EXTENSION",
            form_data={"sub_type": "EXTENSION", "applicant_type": "CITIZEN_GQ"}
        )
        reqs = workflow.get_document_requirements(SolicitudType.RENOVACION, context=context)
        doc_codes = [r.document_code for r in reqs]

        assert "certificado_medico" in doc_codes
        assert "certificado_actual" in doc_codes


class TestTariffCalculation:
    """Test tariff calculation."""

    def test_nuevo_tariff(self):
        workflow = ConducirWorkflow()
        context = WorkflowContext(
            request_id="test",
            user_id="test",
            sub_type="NUEVO",
            form_data={}
        )
        assert workflow.calculate_tariff(context) == 30000

    def test_canje_tariff(self):
        workflow = ConducirWorkflow()
        context = WorkflowContext(
            request_id="test",
            user_id="test",
            sub_type="CANJE",
            form_data={}
        )
        assert workflow.calculate_tariff(context) == 35000

    def test_renovacion_tariff(self):
        workflow = ConducirWorkflow()
        context = WorkflowContext(
            request_id="test",
            user_id="test",
            sub_type="RENOVACION",
            form_data={}
        )
        assert workflow.calculate_tariff(context) == 25000

    def test_duplicado_tariff(self):
        workflow = ConducirWorkflow()
        context = WorkflowContext(
            request_id="test",
            user_id="test",
            sub_type="DUPLICADO",
            form_data={}
        )
        assert workflow.calculate_tariff(context) == 20000

    def test_extension_tariff_per_class(self):
        """EXTENSION should be 15,000 XAF per new class."""
        workflow = ConducirWorkflow()
        context = WorkflowContext(
            request_id="test",
            user_id="test",
            sub_type="EXTENSION",
            form_data={
                "clases_solicitadas": ["B", "C", "D"],
                "clases_actuales": ["B"]
            }
        )
        # 2 new classes (C, D) x 15,000 = 30,000
        assert workflow.calculate_tariff(context) == 30000


class TestRequestTypeEligibility:
    """Test request type eligibility by applicant type."""

    def test_canje_not_allowed_for_citizen(self):
        """CANJE should not be allowed for CITIZEN_GQ."""
        workflow = ConducirWorkflow()
        assert workflow.validate_request_type_eligibility(
            "CANJE",
            ApplicantType.CITIZEN_GQ.value
        ) is False

    def test_canje_allowed_for_resident(self):
        """CANJE should be allowed for RESIDENT."""
        workflow = ConducirWorkflow()
        assert workflow.validate_request_type_eligibility(
            "CANJE",
            ApplicantType.RESIDENT.value
        ) is True

    def test_nuevo_allowed_for_both(self):
        """NUEVO should be allowed for both CITIZEN_GQ and RESIDENT."""
        workflow = ConducirWorkflow()
        assert workflow.validate_request_type_eligibility(
            "NUEVO",
            ApplicantType.CITIZEN_GQ.value
        ) is True
        assert workflow.validate_request_type_eligibility(
            "NUEVO",
            ApplicantType.RESIDENT.value
        ) is True


class TestAgeValidation:
    """Test age validation for license classes."""

    def test_class_b_requires_18(self):
        """Class B should require age 18."""
        workflow = ConducirWorkflow()
        birth_17_years_ago = (date.today() - timedelta(days=17*365)).strftime("%Y-%m-%d")
        errors = workflow.validate_class_eligibility(["B"], birth_17_years_ago)
        assert len(errors) == 1
        assert errors[0]["class"] == "B"

    def test_class_c_requires_21(self):
        """Class C should require age 21."""
        workflow = ConducirWorkflow()
        birth_20_years_ago = (date.today() - timedelta(days=20*365)).strftime("%Y-%m-%d")
        errors = workflow.validate_class_eligibility(["C"], birth_20_years_ago)
        assert len(errors) == 1
        assert errors[0]["class"] == "C"
        assert errors[0]["min_age"] == 21

    def test_valid_age_for_class_b(self):
        """Person 18+ should be eligible for class B."""
        workflow = ConducirWorkflow()
        birth_25_years_ago = (date.today() - timedelta(days=25*365)).strftime("%Y-%m-%d")
        errors = workflow.validate_class_eligibility(["B"], birth_25_years_ago)
        assert len(errors) == 0


class TestValidateStepAgeBlocking:
    """Test validate_step integration with age validation."""

    def test_validate_step_blocks_underage_for_class_c(self):
        """validate_step should return errors for underage applicant requesting class C."""
        from packages.backend.app.modules.service_requests.workflows.workflow_interface import WorkflowContext

        workflow = ConducirWorkflow()

        # Create context with underage person (20 years old) requesting class C (21+)
        birth_20_years_ago = (date.today() - timedelta(days=20*365)).strftime("%Y-%m-%d")
        context = WorkflowContext(
            request_id="test-123",
            user_id="user-456",
            workflow_code="CONDUCIR_NUEVO",
            form_data={
                "fecha_nacimiento": birth_20_years_ago,
                "clases_solicitadas": ["C", "D"]
            }
        )

        # Validate form_review_1 step (step 5)
        results = workflow.validate_step(5, context)

        # Should have blocking errors
        errors = [r for r in results if r.is_error]
        assert len(errors) >= 1
        assert any("edad_minima" in e.rule_id for e in errors)

    def test_validate_step_allows_eligible_age(self):
        """validate_step should pass for eligible age."""
        from packages.backend.app.modules.service_requests.workflows.workflow_interface import WorkflowContext

        workflow = ConducirWorkflow()

        # Create context with 25-year-old requesting class B (18+)
        birth_25_years_ago = (date.today() - timedelta(days=25*365)).strftime("%Y-%m-%d")
        context = WorkflowContext(
            request_id="test-123",
            user_id="user-456",
            workflow_code="CONDUCIR_NUEVO",
            form_data={
                "fecha_nacimiento": birth_25_years_ago,
                "clases_solicitadas": ["B"]
            }
        )

        # Validate form_review_1 step
        results = workflow.validate_step(5, context)

        # Should have no age-related errors
        age_errors = [r for r in results if r.is_error and "edad_minima" in r.rule_id]
        assert len(age_errors) == 0


class TestSingleton:
    """Test singleton pattern."""

    def test_get_conducir_workflow_returns_same_instance(self):
        """get_conducir_workflow should return the same instance."""
        w1 = get_conducir_workflow()
        w2 = get_conducir_workflow()
        assert w1 is w2

    def test_singleton_is_conducir_workflow(self):
        """Singleton should be a ConducirWorkflow instance."""
        workflow = get_conducir_workflow()
        assert isinstance(workflow, ConducirWorkflow)
