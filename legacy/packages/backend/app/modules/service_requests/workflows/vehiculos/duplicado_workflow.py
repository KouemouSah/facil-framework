"""
DuplicadoVehiculoWorkflow v2 - Vehicle document duplicate workflow.

Migrated to PredefinedWorkflow architecture (Option C - Dynamic Form Review).

Handles:
- DUPLICADO_PERMISO: Duplicate of Permiso de Circulación (lost/stolen/damaged)
- DUPLICADO_CUVE: Duplicate of CUVE (lost/stolen/damaged)

Entity: DGT (Dirección General de Tráfico Rodado y Seguridad Vial)
- DUPLICADO_PERMISO → DGT
- DUPLICADO_CUVE → OFIVE (issued by OFIVE, processed via DGT)

Tarification: Fixed (only vehicle workflow with fixed tariffs)
- DUPLICADO_PERMISO: 50,000 XAF
- DUPLICADO_CUVE: 35,000 XAF

Documents:
- DUPLICADO_PERMISO: DIP, CUVE (required), Permiso (optional copy), Denuncia policial
- DUPLICADO_CUVE: DIP, Permiso (required), CUVE (optional copy), Denuncia policial

Identity: DIP (DIP_GQ_V2), NIE (PERMISO_RESIDENCIA_GQ_V1), Pasaporte (PASAPORTE_GQ_V1)

OCR schemas:
- DIP_GQ_V2, PERMISO_RESIDENCIA_GQ_V1, PASAPORTE_GQ_V1, CUVE_GQ_V1, PERMISO_CIRCULACION_GQ_V1

@version 2.1
@date 2026-02-07
@migration v1 vehiculo_workflow.py → 3 workflows v2
"""
from typing import List, Dict, Optional

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


class DuplicadoVehiculoWorkflow(PredefinedWorkflow):
    """
    Vehicle document duplicate workflow (DGT / OFIVE).

    Sub-types:
    - DUPLICADO_PERMISO: Duplicate Permiso de Circulación → DGT
    - DUPLICADO_CUVE: Duplicate CUVE → OFIVE

    Steps:
    0. select_type: Choose DUPLICADO_PERMISO or DUPLICADO_CUVE
    1. upload_documents: Identity (DIP/NIE/Pasaporte) + remaining doc + optional lost doc copy + denuncia
    2. form_review_1: Owner data (identity doc) + vehicle data (from remaining doc)
    3. payment: Fixed tariff
    4. confirmation: Summary + agent_checklist

    Both sub-types require a police report (denuncia) for loss/theft.
    The lost document can optionally be uploaded (digital copy) for cross-validation.
    """

    # === Properties ===

    @property
    def workflow_code(self) -> WorkflowCode:
        return WorkflowCode.VEHICULO_DUPLICADO_PERMISO

    @property
    def category(self) -> WorkflowCategory:
        return WorkflowCategory.VEHICULOS

    @property
    def entity_code(self) -> EntityCode:
        return EntityCode.DGT

    @property
    def service_name_es(self) -> str:
        return "Duplicado de Documentos de Vehículos"

    def get_subtype_display_names(self) -> Dict[str, str]:
        return {
            "VEHICULO_DUPLICADO_PERMISO": "Vehículo - Duplicado Permiso",
            "VEHICULO_DUPLICADO_CUVE": "Vehículo - Duplicado CUVE",
        }

    @property
    def allowed_solicitud_types(self) -> List[SolicitudType]:
        return [SolicitudType.DUPLICADO]

    @property
    def allowed_sub_types(self) -> List[str]:
        return ["DUPLICADO_PERMISO", "DUPLICADO_CUVE"]

    @property
    def requires_appointment(self) -> bool:
        return False

    @property
    def menu_icon(self) -> str:
        return "Truck"

    @property
    def requires_agent_review(self) -> bool:
        return True

    @property
    def requires_nota_ingreso(self) -> bool:
        return False

    # === Multi-code registration ===

    def get_all_workflow_codes(self) -> List[WorkflowCode]:
        return [
            WorkflowCode.VEHICULO_DUPLICADO_PERMISO,
            WorkflowCode.VEHICULO_DUPLICADO_CUVE,
        ]

    # === Setup ===

    def _setup_workflow(self) -> None:
        self._setup_steps()
        self._setup_tariffs()

    def _setup_steps(self) -> None:
        # Step 0: Selection
        self.add_step(WorkflowStep(
            step_number=0,
            step_id="select_type",
            step_type=StepType.SELECTION,
            title_es="Tipo de Duplicado",
            description_es="Seleccione el documento a duplicar",
            config={
                "options": [
                    {
                        "value": "DUPLICADO_PERMISO",
                        "label_es": "Duplicado Permiso de Circulación",
                        "description_es": "Solicitar un duplicado del Permiso de Circulación (pérdida, robo o deterioro)",
                    },
                    {
                        "value": "DUPLICADO_CUVE",
                        "label_es": "Duplicado CUVE",
                        "description_es": "Solicitar un duplicado de la Cartilla Única de Vehículos (pérdida, robo o deterioro)",
                    },
                ],
                "selection_type": "sub_type",
            }
        ))

        # Step 1: Upload documents
        self.add_step(WorkflowStep(
            step_number=1,
            step_id="upload_documents",
            step_type=StepType.DOCUMENT_UPLOAD,
            title_es="Documentos Requeridos",
            description_es="Cargue su documento de identidad, el documento vehicular restante, la denuncia policial y, si disponible, una copia del documento perdido",
            config={
                "dynamic_documents": True,
                "max_file_size_mb": 10,
            }
        ))

        # Step 2: Form Review 1 - Owner + Vehicle
        self.add_step(WorkflowStep(
            step_number=2,
            step_id="form_review_1",
            step_type=StepType.FORM_REVIEW,
            title_es="Datos del Propietario y Vehículo",
            description_es="Verifique los datos extraídos de sus documentos",
            config={
                "sections": [
                    {
                        "id": "propietario",
                        "title_es": "Datos del Propietario",
                        "fields": [
                            {"key": "propietario_apellidos", "label_es": "Apellidos", "type": "text",
                             "required": True, "readonly": True,
                             "help_text_es": "Extraído del documento de identidad"},
                            {"key": "propietario_nombres", "label_es": "Nombres", "type": "text",
                             "required": True, "readonly": True,
                             "help_text_es": "Extraído del documento de identidad"},
                            {"key": "propietario_numero_id", "label_es": "Número de Documento", "type": "text",
                             "required": True, "readonly": True,
                             "help_text_es": "N° de DIP, NIE o Pasaporte del propietario"},
                        ]
                    },
                    {
                        "id": "vehiculo_permiso",
                        "title_es": "Datos del Vehículo (del Permiso de Circulación)",
                        "condition": {"sub_type": "DUPLICADO_CUVE"},
                        "fields": [
                            {"key": "matricula", "label_es": "Matrícula", "type": "text",
                             "required": True, "readonly": True,
                             "help_text_es": "Extraída del Permiso de Circulación"},
                            {"key": "numero_bastidor", "label_es": "VIN / Número de Bastidor", "type": "text",
                             "required": True, "readonly": True,
                             "help_text_es": "17 caracteres alfanuméricos"},
                            {"key": "marca", "label_es": "Marca", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "modelo", "label_es": "Modelo", "type": "text",
                             "required": True, "readonly": True},
                        ]
                    },
                    {
                        "id": "vehiculo_cuve",
                        "title_es": "Datos del Vehículo (de la CUVE)",
                        "condition": {"sub_type": "DUPLICADO_PERMISO"},
                        "fields": [
                            {"key": "matricula", "label_es": "Matrícula", "type": "text",
                             "required": True, "readonly": True,
                             "help_text_es": "Extraída de la CUVE"},
                            {"key": "numero_bastidor", "label_es": "VIN / Número de Bastidor", "type": "text",
                             "required": True, "readonly": True,
                             "help_text_es": "17 caracteres alfanuméricos"},
                            {"key": "color", "label_es": "Color", "type": "text",
                             "required": False, "readonly": True},
                            {"key": "potencia_fiscal", "label_es": "Potencia Fiscal (CVF)", "type": "number",
                             "required": False, "readonly": True,
                             "help_text_es": "Puissance fiscale en chevaux vapeur fiscaux"},
                        ]
                    },
                ]
            }
        ))

        # Step 3: Payment (fixed tariff)
        self.add_step(WorkflowStep(
            step_number=3,
            step_id="payment",
            step_type=StepType.PAYMENT,
            title_es="Pago de Tasas",
            description_es="Pague las tasas del duplicado",
            config={
                "currency": "XAF",
            }
        ))

        # Step 4: Confirmation
        self.add_step(WorkflowStep(
            step_number=4,
            step_id="confirmation",
            step_type=StepType.CONFIRMATION,
            title_es="Confirmación y Envío",
            description_es="Verifique todos los datos antes de enviar",
            config={
                "show_summary": True,
                "agent_checklist": [
                    {"id": "documents_verified", "label_es": "He verificado la autenticidad de todos los documentos", "required": True},
                    {"id": "denuncia_verified", "label_es": "He verificado la denuncia policial (pérdida/robo)", "required": True},
                    {"id": "owner_verified", "label_es": "He verificado la identidad del propietario", "required": True},
                    {"id": "vehicle_data_verified", "label_es": "He verificado los datos del vehículo", "required": True},
                    {"id": "payment_verified", "label_es": "He verificado el pago de las tasas", "required": True},
                ],
                "rejection_reasons": [
                    {"id": "documents_invalid", "label_es": "Documentos inválidos o ilegibles"},
                    {"id": "denuncia_missing", "label_es": "Denuncia policial no válida o ausente"},
                    {"id": "owner_mismatch", "label_es": "Propietario no coincide con los registros"},
                    {"id": "vehicle_not_registered", "label_es": "Vehículo no encontrado en el registro"},
                    {"id": "other", "label_es": "Otro (especificar)"},
                ],
            }
        ))

    def _setup_tariffs(self) -> None:
        """Fixed tariffs for duplicates - only vehicle workflow with fixed pricing."""
        self.set_tariff_config(TariffConfig(
            tariff_type=TariffType.FIXED,
            fixed_amounts={
                "DUPLICADO": 50000,  # Default for SolicitudType.DUPLICADO
            },
            currency="XAF",
        ))

    def get_tariff(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None,
    ) -> int:
        """Override to return sub-type-specific fixed tariffs."""
        sub_type = context.sub_type if context else None
        tariffs = {
            "DUPLICADO_PERMISO": 50000,
            "DUPLICADO_CUVE": 35000,
        }
        if sub_type and sub_type in tariffs:
            return tariffs[sub_type]
        return 50000  # Default

    # === Document Requirements ===

    def get_document_requirements(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None,
    ) -> List[DocumentRequirement]:
        sub_type = context.sub_type if context else "DUPLICADO_PERMISO"

        requirements = []

        # Identity document - always required (multi-schema: DIP, NIE, Pasaporte)
        requirements.append(DocumentRequirement(
            document_code="identidad_propietario",
            document_name_es="Documento de Identidad del Propietario",
            schema_key="DIP_GQ_V2",
            is_required=True,
            display_order=1,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es="Escanee ambas caras de su DIP, NIE o Pasaporte en vigor",
            faces_required=["recto", "verso"],
            config={
                "accepted_schemas": ["DIP_GQ_V2", "PERMISO_RESIDENCIA_GQ_V1", "PASAPORTE_GQ_V1", "PASAPORTE_INTERNATIONAL_V1"],
            },
        ))

        if sub_type == "DUPLICADO_PERMISO":
            # CUVE (remaining document - always available)
            requirements.append(DocumentRequirement(
                document_code="cuve",
                document_name_es="CUVE del Vehículo",
                schema_key="CUVE_GQ_V1",
                is_required=True,
                display_order=2,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["DUPLICADO_PERMISO"]},
                instructions_es="CUVE vigente del vehículo. Escanee recto y verso.",
                faces_required=["recto", "verso"],
            ))
            # Permiso (optional copy of lost document for cross-validation)
            requirements.append(DocumentRequirement(
                document_code="permiso_circulacion",
                document_name_es="Copia del Permiso de Circulación (si disponible)",
                schema_key="PERMISO_CIRCULACION_GQ_V1",
                is_required=False,
                display_order=3,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["DUPLICADO_PERMISO"]},
                instructions_es="Si dispone de una copia digital del Permiso perdido/robado, adjúntela para agilizar el trámite.",
                faces_required=["recto", "verso"],
            ))

        elif sub_type == "DUPLICADO_CUVE":
            # Permiso (remaining document - always available)
            requirements.append(DocumentRequirement(
                document_code="permiso_circulacion",
                document_name_es="Permiso de Circulación del Vehículo",
                schema_key="PERMISO_CIRCULACION_GQ_V1",
                is_required=True,
                display_order=2,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["DUPLICADO_CUVE"]},
                instructions_es="Permiso de Circulación vigente. Escanee recto y verso.",
                faces_required=["recto", "verso"],
            ))
            # CUVE (optional copy of lost document for cross-validation)
            requirements.append(DocumentRequirement(
                document_code="cuve",
                document_name_es="Copia de la CUVE (si disponible)",
                schema_key="CUVE_GQ_V1",
                is_required=False,
                display_order=3,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["DUPLICADO_CUVE"]},
                instructions_es="Si dispone de una copia digital de la CUVE perdida/robada, adjúntela para agilizar el trámite.",
                faces_required=["recto", "verso"],
            ))

        # Denuncia policial - always required for duplicates (no OCR schema)
        requirements.append(DocumentRequirement(
            document_code="denuncia",
            document_name_es="Denuncia Policial",
            is_required=True,
            display_order=4,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es="Denuncia de pérdida, robo o deterioro de la Policía Nacional",
        ))

        return requirements

    # === Form Mapping ===

    def get_form_mapping(
        self,
        context: Optional[WorkflowContext] = None,
    ) -> Dict[str, str]:
        """Map extracted data to form fields (context-aware per sub_type).

        DUPLICADO_PERMISO uploads: Identity, CUVE (required), Permiso (optional copy), Denuncia
        → Vehicle data from CUVE (remaining doc)

        DUPLICADO_CUVE uploads: Identity, Permiso (required), CUVE (optional copy), Denuncia
        → Vehicle data from Permiso (remaining doc)

        Identity: DIP preferred, falls back to NIE/Pasaporte.
        """
        sub_type = context.sub_type if context else "DUPLICADO_PERMISO"

        # Common: owner from identity document (multi-schema)
        mapping: Dict[str, str] = {
            "propietario_numero_id": "identidad_propietario.documento.numero_dip",
            "propietario_apellidos": "identidad_propietario.titular.apellidos",
            "propietario_nombres": "identidad_propietario.titular.nombres",
        }

        if sub_type == "DUPLICADO_PERMISO":
            # Vehicle data from CUVE (remaining doc, always required)
            mapping.update({
                "matricula": "cuve.vehiculo.matricula",
                "numero_bastidor": "cuve.vehiculo.numero_bastidor",
                "color": "cuve.vehiculo.color",
                "potencia_fiscal": "cuve.motor.potencia_fiscal",
            })
        else:
            # DUPLICADO_CUVE: vehicle data from Permiso (remaining doc, always required)
            mapping.update({
                "matricula": "permiso_circulacion.vehiculo.matricula",
                "numero_bastidor": "permiso_circulacion.vehiculo.numero_bastidor",
                "marca": "permiso_circulacion.vehiculo.marca",
                "modelo": "permiso_circulacion.vehiculo.modelo",
            })

        # Cross-doc validation uses context.get_extracted_field() directly,
        # no phantom mapping keys needed.

        return mapping

    # === Step Validation ===

    def validate_step(
        self,
        step_number: int,
        context: WorkflowContext,
    ) -> List[ValidationResult]:
        """Cross-document validations for duplicates.

        Layer 1 (upload): SchemaValidationEngine validates document format.
        Layer 2 (form review): validate_step() validates cross-doc coherence
        using context.get_extracted_field() (raw OCR data, not form_data).

        Rules (form_review_1, only when optional lost doc is provided):
        - matricula_coherente: matricula from remaining doc == lost doc copy
        - bastidor_coherente: VIN from remaining doc == lost doc copy
        """
        results = super().validate_step(step_number, context)

        step = self.get_step(step_number)
        if not step or step.step_id != "form_review_1":
            return results

        sub_type = context.sub_type or "DUPLICADO_PERMISO"

        # Cross-doc coherence via get_extracted_field (raw OCR, no phantom form keys)
        if sub_type == "DUPLICADO_PERMISO":
            # Primary vehicle data from CUVE (required), cross-check with Permiso (optional copy)
            cuve_matricula = context.get_extracted_field("cuve", "vehiculo.matricula")
            permiso_matricula = context.get_extracted_field("permiso_circulacion", "vehiculo.matricula")
            if cuve_matricula and permiso_matricula:
                if str(cuve_matricula).strip().upper() != str(permiso_matricula).strip().upper():
                    results.append(ValidationResult(
                        is_valid=False,
                        rule_id="matricula_coherente",
                        severity="warning",
                        message_es=(
                            f"La matrícula de la CUVE ({cuve_matricula}) no coincide "
                            f"con la del Permiso ({permiso_matricula}). Verifique los documentos."
                        ),
                        field_name="matricula",
                    ))

            cuve_vin = context.get_extracted_field("cuve", "vehiculo.numero_bastidor")
            permiso_vin = context.get_extracted_field("permiso_circulacion", "vehiculo.numero_bastidor")
            if cuve_vin and permiso_vin:
                if str(cuve_vin).strip().upper() != str(permiso_vin).strip().upper():
                    results.append(ValidationResult(
                        is_valid=False,
                        rule_id="bastidor_coherente",
                        severity="warning",
                        message_es=(
                            f"El VIN de la CUVE ({cuve_vin}) no coincide "
                            f"con el del Permiso ({permiso_vin}). Verifique los documentos."
                        ),
                        field_name="numero_bastidor",
                    ))

        elif sub_type == "DUPLICADO_CUVE":
            # Primary vehicle data from Permiso (required), cross-check with CUVE (optional copy)
            permiso_matricula = context.get_extracted_field("permiso_circulacion", "vehiculo.matricula")
            cuve_matricula = context.get_extracted_field("cuve", "vehiculo.matricula")
            if permiso_matricula and cuve_matricula:
                if str(permiso_matricula).strip().upper() != str(cuve_matricula).strip().upper():
                    results.append(ValidationResult(
                        is_valid=False,
                        rule_id="matricula_coherente",
                        severity="warning",
                        message_es=(
                            f"La matrícula del Permiso ({permiso_matricula}) no coincide "
                            f"con la de la CUVE ({cuve_matricula}). Verifique los documentos."
                        ),
                        field_name="matricula",
                    ))

            permiso_vin = context.get_extracted_field("permiso_circulacion", "vehiculo.numero_bastidor")
            cuve_vin = context.get_extracted_field("cuve", "vehiculo.numero_bastidor")
            if permiso_vin and cuve_vin:
                if str(permiso_vin).strip().upper() != str(cuve_vin).strip().upper():
                    results.append(ValidationResult(
                        is_valid=False,
                        rule_id="bastidor_coherente",
                        severity="warning",
                        message_es=(
                            f"El VIN del Permiso ({permiso_vin}) no coincide "
                            f"con el de la CUVE ({cuve_vin}). Verifique los documentos."
                        ),
                        field_name="numero_bastidor",
                    ))

        return results


# =============================================================================
# Singleton & Registration
# =============================================================================

_workflow: Optional[DuplicadoVehiculoWorkflow] = None


def get_duplicado_vehiculo_workflow() -> DuplicadoVehiculoWorkflow:
    """Get or create the singleton workflow instance."""
    global _workflow
    if _workflow is None:
        _workflow = DuplicadoVehiculoWorkflow()
    return _workflow
