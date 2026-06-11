"""
PromocionAdministrativaWorkflow v2 - Administrative promotion workflow.

Migrated to PredefinedWorkflow architecture (Option C - Dynamic Form Review).

Handles civil servant promotions:
- TRIENIOS: Seniority recognition (every 3 years of service) - 5,000 XAF
- NIVEL: Level advancement within the same category - 7,500 XAF
- ESCALA: Scale advancement (change of category, requires new title) - 10,000 XAF

Entity: MINFP (Ministerio de la Función Pública y Reforma Administrativa)

Prerequisite: User must have role 'funcionario' (verified via VerificacionFuncionario).

Payment flow: Standard (citizen pays → agent reviews).
No appointment required. No Nota de Ingreso.

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
    DocumentConditionType
)


class PromocionType(str, Enum):
    """Type of administrative promotion."""
    TRIENIOS = "TRIENIOS"     # Seniority recognition (every 3 years)
    NIVEL = "NIVEL"           # Level advancement (same category)
    ESCALA = "ESCALA"         # Scale advancement (new category)


class PromocionAdministrativaWorkflow(PredefinedWorkflow):
    """
    Administrative promotion workflow (MINFP).

    AUTONOMOUS: Defines ALL logic internally, no BaseWorkflow inheritance.

    ALIGNED WITH PredefinedWorkflow architecture (v2):
    - SolicitudType.EXPEDICION: All promotion types (TRIENIOS, NIVEL, ESCALA)
    - Sub-types via allowed_sub_types determine tariff and documents

    Key features v2:
    - form_review_1: Civil servant identification (from carnet + DIP)
    - Conditional documents per promotion type (ESCALA needs academic title)
    - Fixed tariffs per sub-type
    - Standard payment flow (pay first, agent reviews after)

    Condition Key Convention:
    - Uses "sub_type" as primary condition key (TRIENIOS, NIVEL, ESCALA)
    """

    # Sub_type to (SolicitudType, Motivo) mapping
    # All promotions are "new requests" (EXPEDICION), no renewal concept
    SUBTYPE_TO_SOLICITUD_MOTIVO = {
        "TRIENIOS": (SolicitudType.EXPEDICION, None),
        "NIVEL": (SolicitudType.EXPEDICION, None),
        "ESCALA": (SolicitudType.EXPEDICION, None),
    }

    # Fixed tariffs per promotion type
    TARIFFS = {
        "TRIENIOS": 5000,   # 5,000 XAF
        "NIVEL": 7500,      # 7,500 XAF
        "ESCALA": 10000,    # 10,000 XAF
    }

    # === Configuration (PredefinedWorkflow required properties) ===

    @property
    def workflow_code(self) -> WorkflowCode:
        return WorkflowCode.FP_PROMOCION_ADMINISTRATIVA

    @property
    def category(self) -> WorkflowCategory:
        return WorkflowCategory.FUNCION_PUBLICA

    @property
    def entity_code(self) -> EntityCode:
        return EntityCode.MINFP

    @property
    def service_name_es(self) -> str:
        return "Promoción Administrativa"

    def get_parent_mapping(self) -> Dict[str, Optional[str]]:
        return {"FP_PROMOCION_ADMINISTRATIVA": "FP_VERIFICACION_FUNCIONARIO"}

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
        """Legacy: list of sub_type strings."""
        return list(self.SUBTYPE_TO_SOLICITUD_MOTIVO.keys())

    # === Workflow Setup ===

    def _setup_workflow(self) -> None:
        """
        Setup complete administrative promotion workflow.

        Steps:
        0. select_type - Promotion type (TRIENIOS/NIVEL/ESCALA)
        1. upload_documents - All documents on one page
        2. form_review_1 - Civil servant identification (1/1)
        3. payment - Fixed tariff per promotion type
        4. confirmation - Final summary
        """

        # === Step 0: Promotion Type Selection ===
        self.add_step(WorkflowStep(
            step_number=0,
            step_id="select_type",
            step_type=StepType.SELECTION,
            title_es="Tipo de Promoción",
            description_es="Seleccione el tipo de promoción que solicita",
            config={
                "selection_type": "sub_type",
                "options": [
                    {
                        "value": "TRIENIOS",
                        "label_es": "Reconocimiento de Trienios",
                        "description_es": "Reconocimiento de cada 3 años de servicio efectivo",
                        "tariff": 5000,
                        "icon": "calendar-clock"
                    },
                    {
                        "value": "NIVEL",
                        "label_es": "Corrida de Nivel",
                        "description_es": "Avance de nivel dentro de la misma categoría",
                        "tariff": 7500,
                        "icon": "arrow-up"
                    },
                    {
                        "value": "ESCALA",
                        "label_es": "Corrida de Escala",
                        "description_es": "Cambio de categoría (requiere nuevo título académico)",
                        "tariff": 10000,
                        "icon": "graduation-cap"
                    }
                ]
            }
        ))

        # === Step 1: Document Upload ===
        self.add_step(WorkflowStep(
            step_number=1,
            step_id="upload_documents",
            step_type=StepType.DOCUMENT_UPLOAD,
            title_es="Documentos Justificativos",
            description_es="Cargue los documentos que acreditan su derecho a la promoción",
            config={
                "dynamic_documents": True,
                "single_page": True,
                "includes_photo": False
            }
        ))

        # === Step 2: Form Review 1 - Civil Servant Identification (1/1) ===
        self.add_step(WorkflowStep(
            step_number=2,
            step_id="form_review_1",
            step_type=StepType.FORM_REVIEW,
            title_es="Verificar Datos del Funcionario",
            description_es="Verifique los datos extraídos de su carnet y documentos",
            config={
                "form_page": 1,
                "max_sections": 3,
                "sections": [
                    {
                        "id": "identificacion_funcionario",
                        "title_es": "Identificación del Funcionario",
                        "condition": None,  # Always visible
                        "fields": [
                            {
                                "key": "numero_dip",
                                "label_es": "Número DIP",
                                "type": "text",
                                "required": True,
                                "readonly": True
                            },
                            {
                                "key": "apellidos",
                                "label_es": "Apellidos",
                                "type": "text",
                                "required": True,
                                "readonly": True
                            },
                            {
                                "key": "nombres",
                                "label_es": "Nombres",
                                "type": "text",
                                "required": True,
                                "readonly": True
                            },
                            {
                                "key": "matricula",
                                "label_es": "Matrícula / Nº Carnet",
                                "type": "text",
                                "required": True,
                                "readonly": True
                            },
                            {
                                "key": "ministerio",
                                "label_es": "Ministerio / Organismo",
                                "type": "text",
                                "required": True,
                                "readonly": True
                            },
                            {
                                "key": "categoria_actual",
                                "label_es": "Categoría Actual",
                                "type": "text",
                                "required": True,
                                "readonly": True
                            },
                            {
                                "key": "nivel_actual",
                                "label_es": "Nivel Actual",
                                "type": "text",
                                "required": False,
                                "readonly": True
                            },
                            {
                                "key": "fecha_ingreso",
                                "label_es": "Fecha de Ingreso a la Función Pública",
                                "type": "date",
                                "required": False,
                                "readonly": True
                            }
                        ]
                    },
                    # Section 2: Trienios details (TRIENIOS only)
                    {
                        "id": "datos_trienios",
                        "title_es": "Datos del Trienio",
                        "condition": {"sub_type": "TRIENIOS"},
                        "fields": [
                            {
                                "key": "numero_trienios_reconocidos",
                                "label_es": "Trienios ya Reconocidos",
                                "type": "number",
                                "required": False,
                                "readonly": False
                            },
                            {
                                "key": "fecha_ultimo_trienio",
                                "label_es": "Fecha del Último Trienio Reconocido",
                                "type": "date",
                                "required": False,
                                "readonly": False
                            },
                            {
                                "key": "anos_servicio_efectivo",
                                "label_es": "Años de Servicio Efectivo",
                                "type": "number",
                                "required": False,
                                "readonly": False
                            }
                        ]
                    },
                    # Section 3: Escala details (ESCALA only)
                    {
                        "id": "datos_escala",
                        "title_es": "Datos del Cambio de Escala",
                        "condition": {"sub_type": "ESCALA"},
                        "fields": [
                            {
                                "key": "nuevo_titulo",
                                "label_es": "Nuevo Título Académico",
                                "type": "text",
                                "required": True,
                                "readonly": False
                            },
                            {
                                "key": "institucion_titulo",
                                "label_es": "Institución que Emitió el Título",
                                "type": "text",
                                "required": False,
                                "readonly": False
                            },
                            {
                                "key": "fecha_titulo",
                                "label_es": "Fecha de Obtención del Título",
                                "type": "date",
                                "required": False,
                                "readonly": False
                            },
                            {
                                "key": "titulo_homologado",
                                "label_es": "¿Título Homologado?",
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

        # === Step 3: Payment ===
        self.add_step(WorkflowStep(
            step_number=3,
            step_id="payment",
            step_type=StepType.PAYMENT,
            title_es="Pago de Tasas",
            description_es="Tasa de tramitación de la promoción",
            config={
                "currency": "XAF",
                "show_breakdown": True,
                "dynamic_tariff": True
            }
        ))

        # === Step 4: Confirmation ===
        self.add_step(WorkflowStep(
            step_number=4,
            step_id="confirmation",
            step_type=StepType.CONFIRMATION,
            title_es="Confirmación y Envío",
            description_es="Su solicitud de promoción ha sido completada",
            config={
                "show_summary": True,
                "show_payment": True,
                "allow_download_receipt": True,
                "next_steps_es": [
                    "Su expediente será examinado por un agente del MINFP",
                    "El agente verificará su historial en el SIGEF",
                    "Recibirá una notificación con la resolución",
                    "Si se aprueba, la actualización salarial será efectiva el mes siguiente"
                ]
            }
        ))

        # === Setup Tariffs ===
        self._setup_tariffs()

    def _setup_tariffs(self) -> None:
        """
        Setup tariff configuration for administrative promotions.

        Fixed tariffs per promotion type:
        - TRIENIOS: 5,000 XAF
        - NIVEL: 7,500 XAF
        - ESCALA: 10,000 XAF

        No supplements.
        """
        self.set_tariff_config(TariffConfig(
            tariff_type=TariffType.FIXED,
            fixed_amounts=self.TARIFFS,
            currency="XAF",
            supplements=[]
        ))

    # === Tariff Override ===

    def get_tariff(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None
    ) -> int:
        """
        Get tariff based on sub_type (promotion type), not solicitud_type.

        All promotions are EXPEDICION, so the parent's default lookup by
        solicitud_type would always return the same value. We override to
        look up by sub_type instead.
        """
        sub_type = None
        if context:
            sub_type = context.sub_type

        if sub_type and sub_type in self.TARIFFS:
            return self.TARIFFS[sub_type]

        # Default to TRIENIOS tariff if no sub_type yet
        return self.TARIFFS["TRIENIOS"]

    # === Document Requirements ===

    def get_document_requirements(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None
    ) -> List[DocumentRequirement]:
        """
        Get document requirements based on promotion type.

        Common to all types:
        - DIP (always required)
        - Carnet de Funcionario (always required)
        - Última Resolución de Nombramiento (always required)

        Type-specific:
        - TRIENIOS: + Certificado de Servicios Prestados
        - ESCALA: + Título Académico + Homologación (optional)
        """
        requirements = []

        sub_type = None
        if context:
            sub_type = context.sub_type

        # === 1. DIP - Always required ===
        requirements.append(DocumentRequirement(
            document_code="dip",
            document_name_es="Documento de Identidad Personal (DIP)",
            schema_key="DIP_GQ_V2",
            is_required=True,
            display_order=1,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es="DIP vigente del funcionario",
            faces_required=["recto", "verso"]
        ))

        # === 2. Carnet de Funcionario - Always required (has schema) ===
        requirements.append(DocumentRequirement(
            document_code="carnet_funcionario",
            document_name_es="Carnet de Funcionario",
            schema_key="CARNET_FUNCIONARIO_GQ_V1",
            is_required=True,
            display_order=2,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es="Carnet de funcionario vigente (recto y verso)",
            faces_required=["recto", "verso"]
        ))

        # === 3. Última Resolución - Always required ===
        requirements.append(DocumentRequirement(
            document_code="ultima_resolucion",
            document_name_es="Última Resolución de Nombramiento/Promoción",
            is_required=True,
            display_order=3,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es="Última resolución de nombramiento o promoción",
            config={"best_effort_extraction": True}
        ))

        # === 4. Certificado de Servicios (TRIENIOS only) ===
        if sub_type == "TRIENIOS":
            requirements.append(DocumentRequirement(
                document_code="certificado_servicios",
                document_name_es="Certificado de Servicios Prestados",
                is_required=True,
                display_order=4,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["TRIENIOS"]},
                instructions_es="Certificado emitido por la unidad de personal acreditando los años de servicio",
                config={"best_effort_extraction": True}
            ))

        # === 5. Título Académico (ESCALA only) ===
        if sub_type == "ESCALA":
            requirements.append(DocumentRequirement(
                document_code="titulo_academico",
                document_name_es="Nuevo Título Académico",
                is_required=True,
                display_order=4,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["ESCALA"]},
                instructions_es="Título académico que justifica el cambio de escala",
                config={"best_effort_extraction": True}
            ))

            # === 6. Homologación (ESCALA, optional) ===
            requirements.append(DocumentRequirement(
                document_code="homologacion",
                document_name_es="Homologación de Título (si extranjero)",
                is_required=False,
                display_order=5,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["ESCALA"]},
                instructions_es="Si el título fue emitido en el extranjero, debe estar homologado",
                config={"best_effort_extraction": True}
            ))

        return requirements

    # === Step Validation ===

    # Category hierarchy for administrative level comparison
    CATEGORY_RANK = {"D": 1, "C2": 2, "C1": 3, "B2": 4, "B1": 5, "A2": 6, "A1": 7}

    def validate_step(
        self,
        step_number: int,
        context: WorkflowContext
    ) -> List[ValidationResult]:
        """Validate promotion-specific business rules on form review.

        Unique rules:
        - trienio_elegible: 3 years since last trienio (TRIENIOS only)
        - titulo_superior: new title must be higher category (ESCALA only)
        """
        from datetime import date, timedelta

        results = super().validate_step(step_number, context)

        step = self.get_step(step_number)
        if not step or step.step_type != StepType.FORM_REVIEW:
            return results

        # --- TRIENIOS: 3 years since last trienio ---
        if context.sub_type == "TRIENIOS":
            ultima_fecha = context.form_data.get("ultima_fecha_trienio")
            if ultima_fecha:
                try:
                    from datetime import datetime as dt_cls
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                        try:
                            parsed = dt_cls.strptime(str(ultima_fecha), fmt).date()
                            break
                        except ValueError:
                            continue
                    else:
                        parsed = None
                    if parsed and parsed + timedelta(days=1095) > date.today():
                        results.append(ValidationResult(
                            is_valid=False,
                            rule_id="trienio_elegible",
                            severity="error",
                            message_es=(
                                "Debe haber transcurrido al menos 3 años "
                                "desde el último trienio reconocido."
                            ),
                            field_name="ultima_fecha_trienio"
                        ))
                except (ValueError, TypeError):
                    pass

        # --- ESCALA: new title must be higher category ---
        if context.sub_type == "ESCALA":
            nuevo_nivel = context.form_data.get("titulo_nivel")
            cat_actual = context.get_extracted_field(
                "carnet_funcionario", "puesto.categoria"
            )
            if nuevo_nivel and cat_actual:
                rank_nuevo = self.CATEGORY_RANK.get(str(nuevo_nivel).upper(), 0)
                rank_actual = self.CATEGORY_RANK.get(str(cat_actual).upper(), 0)
                if rank_nuevo > 0 and rank_actual > 0 and rank_nuevo <= rank_actual:
                    results.append(ValidationResult(
                        is_valid=False,
                        rule_id="titulo_superior",
                        severity="warning",
                        message_es=(
                            "El nuevo título debe corresponder a una "
                            "categoría superior a la actual."
                        ),
                        field_name="titulo_nivel"
                    ))

        return results

    # === Form Field Mapping ===

    def get_form_mapping(self, context: Optional[WorkflowContext] = None) -> Dict[str, str]:
        """
        Map extracted document data fields to form fields.

        Sources verified against real OCR schemas:
        - dip (DIP_GQ_V2): DIP number, names - paths verified
        - carnet_funcionario (CARNET_FUNCIONARIO_GQ_V1): matricula, categoria, ministerio - paths verified
        - ultima_resolucion: nivel (best-effort, no schema)
        - titulo_academico: titulo (best-effort, ESCALA only, no schema)
        """
        return {
            # === From DIP (schema DIP_GQ_V2) ===
            "numero_dip": "dip.documento.numero_dip",
            "apellidos": "dip.titular.apellidos",
            "nombres": "dip.titular.nombres",

            # === From Carnet de Funcionario (schema CARNET_FUNCIONARIO_GQ_V1) ===
            "matricula": "carnet_funcionario.titular.matricula",
            "categoria_actual": "carnet_funcionario.puesto.categoria",
            "ministerio": "carnet_funcionario.puesto.ministerio",
            "fecha_ingreso": "carnet_funcionario.carnet.fecha_emision",

            # === From Última Resolución (best-effort, no schema) ===
            "nivel_actual": "ultima_resolucion.nivel",

            # === From Título Académico (best-effort, ESCALA only, no schema) ===
            "nuevo_titulo": "titulo_academico.titulo",
        }


# =============================================================================
# REGISTRATION
# =============================================================================

# Singleton instance
_promocion_workflow: Optional[PromocionAdministrativaWorkflow] = None


def get_promocion_administrativa_workflow() -> PromocionAdministrativaWorkflow:
    """Get the singleton PromocionAdministrativaWorkflow instance."""
    global _promocion_workflow
    if _promocion_workflow is None:
        _promocion_workflow = PromocionAdministrativaWorkflow()
    return _promocion_workflow
