"""
CertificadoAdministrativoWorkflow v2 - Administrative certificate workflow.

Migrated to PredefinedWorkflow architecture (Option C - Dynamic Form Review).

Handles issuance of various administrative certificates for civil servants:
- SERVICIOS_PRESTADOS: Service record (3,000 XAF, ~5 days)
- SITUACION_ADMINISTRATIVA: Administrative status (2,500 XAF, ~3 days)
- HABERES: Salary certificate (3,500 XAF, ~3 days)
- TIEMPO_SERVICIO: Time of service (2,500 XAF, ~3 days)
- BUENA_CONDUCTA: Good conduct certificate (2,000 XAF, ~5 days)

Entity: MINFP (Ministerio de la Funcion Publica y Reforma Administrativa)

Prerequisite: User must have role 'funcionario' (verified via VerificacionFuncionario).

Process:
1. Select certificate type (CertificadoTipo)
2. Enter purpose, copies, urgency (form_review)
3. Upload documents (carnet + DIP + conditional)
4. Review extracted data (readonly form_review)
5. Payment (variable by type: 2,000-3,500 XAF)
6. Confirmation + agent review

Payment: Variable by certificate type (see TARIFFS_BY_TYPE).
Appointment: NOT required.
Agent review: REQUIRED (SIGEF verification + certificate generation).
Nota de Ingreso: NOT required.

OCR schemas:
- carnet_funcionario_gq.json (CARNET_FUNCIONARIO_GQ_V1) - Civil servant card
- dip_gq.json (DIP_GQ_V2) - Identity document

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

class CertificadoTipo(str, Enum):
    """Types of administrative certificates."""
    SERVICIOS_PRESTADOS = "SERVICIOS_PRESTADOS"
    SITUACION_ADMINISTRATIVA = "SITUACION_ADMINISTRATIVA"
    HABERES = "HABERES"
    TIEMPO_SERVICIO = "TIEMPO_SERVICIO"
    BUENA_CONDUCTA = "BUENA_CONDUCTA"


# =============================================================================
# Configuration
# =============================================================================

# Tariffs per certificate type (XAF)
TARIFFS_BY_TYPE: Dict[str, int] = {
    "SERVICIOS_PRESTADOS": 3000,
    "SITUACION_ADMINISTRATIVA": 2500,
    "HABERES": 3500,
    "TIEMPO_SERVICIO": 2500,
    "BUENA_CONDUCTA": 2000,
}

# Estimated processing time in business days
PROCESSING_DAYS: Dict[str, int] = {
    "SERVICIOS_PRESTADOS": 5,
    "SITUACION_ADMINISTRATIVA": 3,
    "HABERES": 3,
    "TIEMPO_SERVICIO": 3,
    "BUENA_CONDUCTA": 5,
}

# Certificate generation templates
CERTIFICATE_TEMPLATES: Dict[str, str] = {
    "SERVICIOS_PRESTADOS": "CERT_FP_SERVICIOS_V1",
    "SITUACION_ADMINISTRATIVA": "CERT_FP_SITUACION_V1",
    "HABERES": "CERT_FP_HABERES_V1",
    "TIEMPO_SERVICIO": "CERT_FP_TIEMPO_V1",
    "BUENA_CONDUCTA": "CERT_FP_CONDUCTA_V1",
}


class CertificadoAdministrativoWorkflow(PredefinedWorkflow):
    """
    Administrative certificate workflow (MINFP).

    Steps:
    0. select_certificate_type: Choose certificate type (CertificadoTipo)
    1. form_review_1: Purpose, copies, urgency (manual input)
    2. upload_documents: Carnet + DIP + conditional docs
    3. form_review_2: Review extracted data (readonly)
    4. payment: Variable by type (2,000-3,500 XAF)
    5. confirmation: Summary + submit for agent review
    """

    # === Properties (PredefinedWorkflow interface) ===

    @property
    def workflow_code(self) -> WorkflowCode:
        return WorkflowCode.FP_CERTIFICADO_ADMINISTRATIVO

    @property
    def category(self) -> WorkflowCategory:
        return WorkflowCategory.FUNCION_PUBLICA

    @property
    def entity_code(self) -> EntityCode:
        return EntityCode.MINFP

    @property
    def service_name_es(self) -> str:
        return "Certificado Administrativo"

    def get_parent_mapping(self) -> Dict[str, Optional[str]]:
        return {"FP_CERTIFICADO_ADMINISTRATIVO": "FP_VERIFICACION_FUNCIONARIO"}

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
        return [t.value for t in CertificadoTipo]

    # === Workflow Setup ===

    def _setup_workflow(self) -> None:
        """Setup the complete certificate workflow."""
        self._setup_steps()
        self._setup_tariffs()

    def _setup_steps(self) -> None:
        """Define all workflow steps."""

        # Step 0: Select Certificate Type
        self.add_step(WorkflowStep(
            step_number=0,
            step_id="select_certificate_type",
            step_type=StepType.SELECTION,
            title_es="Tipo de Certificado",
            description_es="Seleccione el tipo de certificado que necesita",
            config={
                "selection_type": "sub_type",
                "options": [
                    {
                        "id": CertificadoTipo.SERVICIOS_PRESTADOS.value,
                        "label_es": "Certificado de Servicios Prestados",
                        "description_es": "Historial completo de servicios en la Administración",
                    },
                    {
                        "id": CertificadoTipo.SITUACION_ADMINISTRATIVA.value,
                        "label_es": "Certificado de Situación Administrativa",
                        "description_es": "Estado actual: activo, excedencia, comisión de servicio, etc.",
                    },
                    {
                        "id": CertificadoTipo.HABERES.value,
                        "label_es": "Certificado de Haberes",
                        "description_es": "Certificado de salario y complementos",
                    },
                    {
                        "id": CertificadoTipo.TIEMPO_SERVICIO.value,
                        "label_es": "Certificado de Tiempo de Servicio",
                        "description_es": "Cálculo de años, meses y días de servicio efectivo",
                    },
                    {
                        "id": CertificadoTipo.BUENA_CONDUCTA.value,
                        "label_es": "Certificado de Buena Conducta",
                        "description_es": "Certificado de ausencia de sanciones disciplinarias",
                    },
                ],
            }
        ))

        # Step 1: Certificate Details (manual input)
        self.add_step(WorkflowStep(
            step_number=1,
            step_id="form_review_1",
            step_type=StepType.FORM_REVIEW,
            title_es="Detalles del Certificado",
            description_es="Indique la finalidad del certificado y opciones adicionales",
            config={
                "sections": [
                    {
                        "id": "finalidad_certificado",
                        "title_es": "Finalidad",
                        "fields": [
                            {
                                "key": "finalidad",
                                "label_es": "Finalidad del Certificado",
                                "type": "select",
                                "required": True,
                                "readonly": False,
                                "options": [
                                    {"value": "JUBILACION", "label_es": "Trámites de Jubilación"},
                                    {"value": "PROMOCION", "label_es": "Promoción Interna"},
                                    {"value": "CONCURSO", "label_es": "Concurso/Oposición"},
                                    {"value": "BANCARIO", "label_es": "Trámites Bancarios"},
                                    {"value": "VIVIENDA", "label_es": "Solicitud de Vivienda"},
                                    {"value": "BECA", "label_es": "Solicitud de Beca"},
                                    {"value": "OTRO", "label_es": "Otro"},
                                ],
                            },
                            {
                                "key": "finalidad_detalle",
                                "label_es": "Especifique (si seleccionó 'Otro')",
                                "type": "textarea",
                                "required": False,
                                "readonly": False,
                                "condition": {"finalidad": "OTRO"},
                            },
                        ]
                    },
                    {
                        "id": "opciones_certificado",
                        "title_es": "Opciones",
                        "fields": [
                            {
                                "key": "num_copias",
                                "label_es": "Número de Copias",
                                "type": "number",
                                "required": True,
                                "readonly": False,
                                "min": 1,
                                "max": 5,
                                "default": 1,
                            },
                            {
                                "key": "urgente",
                                "label_es": "Trámite Urgente (Recargo del 50%)",
                                "type": "checkbox",
                                "required": False,
                                "readonly": False,
                                "help_text_es": "El certificado se emitirá en 24-48 horas laborables",
                            },
                        ]
                    }
                ]
            }
        ))

        # Step 2: Upload Documents
        self.add_step(WorkflowStep(
            step_number=2,
            step_id="upload_documents",
            step_type=StepType.DOCUMENT_UPLOAD,
            title_es="Documentos",
            description_es="Cargue los documentos requeridos",
            config={
                "dynamic_documents": True,
            }
        ))

        # Step 3: Review Extracted Data (readonly)
        self.add_step(WorkflowStep(
            step_number=3,
            step_id="form_review_2",
            step_type=StepType.FORM_REVIEW,
            title_es="Datos del Funcionario",
            description_es="Verifique que los datos extraídos son correctos",
            config={
                "sections": [
                    {
                        "id": "datos_carnet",
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
                                "key": "apellidos",
                                "label_es": "Apellidos",
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
                                "key": "categoria",
                                "label_es": "Categoría",
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
                    },
                    {
                        "id": "datos_dip",
                        "title_es": "Datos del DIP",
                        "source_document": "dip",
                        "fields": [
                            {
                                "key": "numero_dip",
                                "label_es": "Número de DIP",
                                "type": "text",
                                "required": True,
                                "readonly": True,
                            },
                        ]
                    }
                ]
            }
        ))

        # Step 4: Payment (variable by certificate type)
        self.add_step(WorkflowStep(
            step_number=4,
            step_id="payment",
            step_type=StepType.PAYMENT,
            title_es="Pago de Tasas",
            description_es="Tasa de emisión del certificado",
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
                "show_estimated_time": True,
                "info_message_es": (
                    "Su solicitud será revisada por un agente del "
                    "Ministerio de la Función Pública.\n"
                    "Una vez verificados los datos en SIGEF, se generará "
                    "su certificado.\n\n"
                    "Recibirá una notificación por email una vez listo."
                ),
                "agent_checklist": [
                    {
                        "id": "matricula_verified",
                        "label_es": "He verificado la matrícula en SIGEF",
                        "required": True,
                    },
                    {
                        "id": "datos_actualizados",
                        "label_es": "He verificado que los datos están actualizados en el sistema",
                        "required": True,
                    },
                ],
                "rejection_reasons": [
                    {"id": "matricula_not_found", "label_es": "Matrícula no existe en SIGEF"},
                    {"id": "datos_incorrectos", "label_es": "Datos del funcionario incorrectos o desactualizados"},
                    {"id": "documentos_invalidos", "label_es": "Documentos inválidos o ilegibles"},
                    {"id": "expediente_disciplinario", "label_es": "Expediente disciplinario pendiente (Buena Conducta)"},
                    {"id": "other", "label_es": "Otro (especificar)"},
                ],
            }
        ))

    def _setup_tariffs(self) -> None:
        """Setup variable tariffs per certificate type.

        Uses CertificadoTipo values as keys since all map to EXPEDICION.
        get_tariff() is overridden to use sub_type as lookup key.
        """
        self.set_tariff_config(TariffConfig(
            tariff_type=TariffType.FIXED,
            fixed_amounts=TARIFFS_BY_TYPE,
            currency="XAF",
        ))

    # === Tariff Override ===

    def get_tariff(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None,
    ) -> int:
        """Get tariff by certificate type including copies and urgency surcharge.

        All certificate types map to EXPEDICION, but each has a different price.
        The sub_type (CertificadoTipo) is the actual tariff key.
        Additional copies (+50% base each) and urgent (+50% total) are factored in.
        """
        config = self.get_tariff_config()

        cert_type = context.sub_type if context else None
        if not cert_type:
            return config.get_amount("BUENA_CONDUCTA")

        # Read copies and urgency from form_data
        num_copias = 1
        urgente = False
        if context and context.form_data:
            try:
                num_copias = int(context.form_data.get("num_copias", 1))
            except (ValueError, TypeError):
                num_copias = 1
            urgente = bool(context.form_data.get("urgente", False))

        return self.calculate_total_tariff(cert_type, num_copias, urgente)

    def get_tariff_breakdown(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None,
        base_description: str = "",
    ) -> Dict[str, Any]:
        """Get itemized tariff breakdown with copies and urgency surcharges."""
        config = self.get_tariff_config()

        cert_type = context.sub_type if context else None
        base_tariff = config.get_amount(cert_type) if cert_type else config.get_amount("BUENA_CONDUCTA")

        num_copias = 1
        urgente = False
        if context and context.form_data:
            try:
                num_copias = int(context.form_data.get("num_copias", 1))
            except (ValueError, TypeError):
                num_copias = 1
            urgente = bool(context.form_data.get("urgente", False))

        supplements = []

        # Additional copies at 50% of base each
        if num_copias > 1:
            copy_price = int(base_tariff * 0.5)
            supplements.append({
                "code": "COPIAS_ADICIONALES",
                "name_es": f"Copias adicionales ({num_copias - 1})",
                "unit_price": copy_price,
                "quantity": num_copias - 1,
                "subtotal": copy_price * (num_copias - 1),
                "is_required": True,
            })

        subtotal = base_tariff + sum(s["subtotal"] for s in supplements)

        # Urgent surcharge: +50% on subtotal
        if urgente:
            urgency_surcharge = int(subtotal * 0.5)
            supplements.append({
                "code": "RECARGO_URGENTE",
                "name_es": "Recargo trámite urgente (+50%)",
                "unit_price": urgency_surcharge,
                "quantity": 1,
                "subtotal": urgency_surcharge,
                "is_required": False,
            })

        supplements_total = sum(s["subtotal"] for s in supplements)
        total_amount = base_tariff + supplements_total

        return {
            "base_amount": base_tariff,
            "base_description": base_description or self.service_name_es,
            "supplements": supplements,
            "supplements_total": supplements_total,
            "penalties_amount": 0,
            "penalty_reason": None,
            "total_amount": total_amount,
            "currency": config.currency,
            "tariff_type": config.tariff_type.value,
            "workflow_code": self.workflow_code.value,
            "solicitud_type": solicitud_type.value,
        }

    # === Document Requirements ===

    def get_document_requirements(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None,
    ) -> List[DocumentRequirement]:
        """Get document requirements for certificate request.

        Always: Carnet de Funcionario + DIP.
        Conditional by certificate type: nombramiento, nomina, declaracion jurada.
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
            # DIP - always required
            DocumentRequirement(
                document_code="dip",
                document_name_es="Documento de Identidad Personal (DIP)",
                schema_key="DIP_GQ_V2",
                is_required=True,
                display_order=2,
                condition_type=DocumentConditionType.ALWAYS,
                faces_required=["recto", "verso"],
                instructions_es="DIP en vigor (ambas caras)",
                accepted_formats=["pdf", "jpg", "jpeg", "png"],
            ),
        ]

        # Conditional documents by certificate type

        # Nombramiento for SERVICIOS_PRESTADOS
        requirements.append(DocumentRequirement(
            document_code="nombramiento",
            document_name_es="Acto de Nombramiento",
            is_required=True,
            display_order=3,
            condition_type=DocumentConditionType.CUSTOM,
            condition_value={"types": ["SERVICIOS_PRESTADOS"]},
            instructions_es="Primer nombramiento o contrato",
            accepted_formats=["pdf", "jpg", "jpeg", "png"],
        ))

        # Last payslip for HABERES (optional)
        requirements.append(DocumentRequirement(
            document_code="nomina_reciente",
            document_name_es="Última Nómina",
            is_required=False,
            display_order=3,
            condition_type=DocumentConditionType.CUSTOM,
            condition_value={"types": ["HABERES"]},
            instructions_es="Nómina del último mes (opcional, para verificación)",
            accepted_formats=["pdf", "jpg", "jpeg", "png"],
        ))

        # Sworn declaration for BUENA_CONDUCTA
        requirements.append(DocumentRequirement(
            document_code="declaracion_jurada",
            document_name_es="Declaración Jurada",
            is_required=True,
            display_order=3,
            condition_type=DocumentConditionType.CUSTOM,
            condition_value={"types": ["BUENA_CONDUCTA"]},
            instructions_es="Declaración de no tener procedimientos disciplinarios pendientes",
            accepted_formats=["pdf", "jpg", "jpeg", "png"],
        ))

        return requirements

    # === Form Mapping ===

    def get_form_mapping(
        self,
        context: Optional[WorkflowContext] = None,
    ) -> Dict[str, str]:
        """Get mapping from extracted data to form fields.

        Paths verified against schemas:
        CARNET_FUNCIONARIO_GQ_V1:
        - carnet_funcionario.titular.matricula ✓
        - carnet_funcionario.titular.apellidos ✓
        - carnet_funcionario.titular.nombre_completo ✓
        - carnet_funcionario.puesto.cargo ✓
        - carnet_funcionario.puesto.categoria ✓
        - carnet_funcionario.puesto.ministerio ✓
        - carnet_funcionario.puesto.direccion_general ✓
        DIP_GQ_V2:
        - dip.documento.numero_dip ✓
        """
        return {
            "matricula": "carnet_funcionario.titular.matricula",
            "apellidos": "carnet_funcionario.titular.apellidos",
            "nombre_completo": "carnet_funcionario.titular.nombre_completo",
            "cargo": "carnet_funcionario.puesto.cargo",
            "categoria": "carnet_funcionario.puesto.categoria",
            "ministerio": "carnet_funcionario.puesto.ministerio",
            "direccion_general": "carnet_funcionario.puesto.direccion_general",
            "numero_dip": "dip.documento.numero_dip",
        }

    # === Step Validation ===

    def validate_step(
        self,
        step_number: int,
        context: WorkflowContext,
    ) -> List[ValidationResult]:
        """Validate step with certificate-specific rules."""
        results = super().validate_step(step_number, context)

        step = self.get_step(step_number)
        if not step:
            return results

        # Validate certificate options on form_review_1
        if step.step_id == "form_review_1":
            results.extend(self._validate_certificate_options(context))

        return results

    def _validate_certificate_options(
        self,
        context: WorkflowContext,
    ) -> List[ValidationResult]:
        """Validate number of copies is within limits."""
        results: List[ValidationResult] = []
        form_data = context.form_data or {}

        num_copias = form_data.get("num_copias")
        if num_copias is not None:
            try:
                n = int(num_copias)
                if n < 1 or n > 5:
                    results.append(ValidationResult(
                        is_valid=False,
                        rule_id="copias_limite",
                        severity="error",
                        message_es="El número de copias debe estar entre 1 y 5.",
                        field_name="num_copias",
                    ))
            except (ValueError, TypeError):
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id="copias_invalidas",
                    severity="error",
                    message_es="El número de copias debe ser un número válido.",
                    field_name="num_copias",
                ))

        return results

    # === Business Logic ===

    def calculate_total_tariff(
        self,
        certificate_type: str,
        num_copies: int = 1,
        urgente: bool = False,
    ) -> int:
        """Calculate total tariff including copies and urgency surcharge.

        Business rules:
        - Additional copies: 50% of base price each
        - Urgent processing: +50% surcharge on total

        Args:
            certificate_type: CertificadoTipo value
            num_copies: Number of copies (1-5)
            urgente: Whether urgent processing is requested

        Returns:
            Total amount in XAF
        """
        base_tariff = TARIFFS_BY_TYPE.get(certificate_type, 2500)

        # Additional copies at 50% of base
        additional_copies_cost = (num_copies - 1) * int(base_tariff * 0.5)
        total = base_tariff + additional_copies_cost

        # Urgent surcharge: +50%
        if urgente:
            total = int(total * 1.5)

        return total

    def get_estimated_processing_days(
        self,
        certificate_type: str,
        urgente: bool = False,
    ) -> int:
        """Get estimated processing time in business days.

        Args:
            certificate_type: CertificadoTipo value
            urgente: Whether urgent processing is requested

        Returns:
            Estimated business days
        """
        if urgente:
            return 1  # 24-48 hours
        return PROCESSING_DAYS.get(certificate_type, 3)

    def get_certificate_template(self, certificate_type: str) -> str:
        """Get template identifier for certificate generation.

        Args:
            certificate_type: CertificadoTipo value

        Returns:
            Template ID string (e.g., "CERT_FP_SERVICIOS_V1")
        """
        return CERTIFICATE_TEMPLATES.get(certificate_type, "CERT_FP_GENERICO_V1")

    def get_agent_verification_items(
        self,
        certificate_type: str,
    ) -> List[Dict[str, Any]]:
        """Get verification checklist for agent review.

        Args:
            certificate_type: CertificadoTipo value

        Returns:
            List of checklist items with id, label_es, required
        """
        items: List[Dict[str, Any]] = [
            {
                "id": "matricula_verified",
                "label_es": "He verificado la matrícula en SIGEF",
                "required": True,
            },
            {
                "id": "datos_actualizados",
                "label_es": "He verificado que los datos están actualizados en el sistema",
                "required": True,
            },
        ]

        if certificate_type == "SERVICIOS_PRESTADOS":
            items.append({
                "id": "historial_completo",
                "label_es": "He generado el historial completo de servicios",
                "required": True,
            })

        if certificate_type == "HABERES":
            items.append({
                "id": "nomina_verificada",
                "label_es": "He verificado la nómina vigente en el sistema de haberes",
                "required": True,
            })

        if certificate_type == "BUENA_CONDUCTA":
            items.extend([
                {
                    "id": "expedientes_revisados",
                    "label_es": "He revisado la existencia de expedientes disciplinarios",
                    "required": True,
                },
                {
                    "id": "sin_sanciones",
                    "label_es": "Confirmo ausencia de sanciones no canceladas",
                    "required": True,
                },
            ])

        return items


# =============================================================================
# Singleton & Registration
# =============================================================================

_workflow: Optional[CertificadoAdministrativoWorkflow] = None


def get_certificado_administrativo_workflow() -> CertificadoAdministrativoWorkflow:
    """Get or create the singleton CertificadoAdministrativo workflow instance."""
    global _workflow
    if _workflow is None:
        _workflow = CertificadoAdministrativoWorkflow()
    return _workflow
