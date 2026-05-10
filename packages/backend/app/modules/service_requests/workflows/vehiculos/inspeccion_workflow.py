"""
InspeccionVehiculoWorkflow v2 - Vehicle inspection and CUVE renewal workflow.

Migrated to PredefinedWorkflow architecture (Option C - Dynamic Form Review).

Handles:
- RENOVACION_ITV: ITV renewal (Inspección Técnica de Vehículos)
- RENOVACION_CUVE: CUVE renewal (Cartilla Única de Vehículos)
- CAMBIO_CARACTERISTICAS: Vehicle modification (reforma)

Entities:
- RENOVACION_ITV: ITVE (Inspección Técnica de Vehículos)
- RENOVACION_CUVE: OFIVE (Oficina de Inspección de Vehículos)
- CAMBIO_CARACTERISTICAS: ITVE + OFIVE

Tarification:
- RENOVACION_ITV / RENOVACION_CUVE: RBC Calculator (dynamic based on vehicle characteristics)
- CAMBIO_CARACTERISTICAS: Fixed 50,000 XAF

Documents:
- RENOVACION_ITV: Identidad propietario (DIP/NIE/Pasaporte), ITV antigua, Permiso Circulación
- RENOVACION_CUVE: Identidad propietario, CUVE antigua, Permiso Circulación, ITV
- CAMBIO: Identidad propietario, Permiso Circulación, CUVE, Certificado Reforma

OCR schemas:
- DIP_GQ_V2, ITV_GQ_V1, CUVE_GQ_V1, PERMISO_CIRCULACION_GQ_V1

@version 2.0
@date 2026-02-07
@migration v1 vehiculo_workflow.py → 3 workflows v2
"""
from typing import List, Dict, Optional
from datetime import datetime

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


class InspeccionVehiculoWorkflow(PredefinedWorkflow):
    """
    Vehicle inspection workflow (ITVE / OFIVE).

    Sub-types:
    - RENOVACION_ITV: Renew ITV card (annual vehicle safety inspection)
    - RENOVACION_CUVE: Renew CUVE card (vehicle registration certificate)
    - CAMBIO_CARACTERISTICAS: Vehicle modification requiring new inspection

    Steps:
    0. select_type: Choose sub-type
    1. upload_documents: Upload documents (dynamic per sub-type)
    2. form_review_1: Vehicle data + owner data (DIP)
    3. form_review_2: ITV/CUVE data + reforma (conditional)
    4. payment: RBC tariff
    5. confirmation: Summary + agent_checklist

    Entity routing:
    - RENOVACION_ITV → ITVE
    - RENOVACION_CUVE → OFIVE
    - CAMBIO_CARACTERISTICAS → ITVE + OFIVE
    """

    # === Properties ===

    @property
    def workflow_code(self) -> WorkflowCode:
        return WorkflowCode.VEHICULO_RENOVACION_ITV

    @property
    def category(self) -> WorkflowCategory:
        return WorkflowCategory.VEHICULOS

    @property
    def entity_code(self) -> EntityCode:
        return EntityCode.ITVE

    @property
    def service_name_es(self) -> str:
        return "Inspección y Renovación de Documentos de Vehículos"

    def get_subtype_display_names(self) -> Dict[str, str]:
        return {
            "VEHICULO_RENOVACION_ITV": "Vehículo - Inspección Técnica (ITV)",
            "VEHICULO_RENOVACION_CUVE": "Vehículo - Renovación CUVE",
            "VEHICULO_CAMBIO_CARACTERISTICAS": "Vehículo - Cambio Características",
        }

    @property
    def allowed_solicitud_types(self) -> List[SolicitudType]:
        return [SolicitudType.RENOVACION]

    @property
    def allowed_sub_types(self) -> List[str]:
        return ["RENOVACION_ITV", "RENOVACION_CUVE", "CAMBIO_CARACTERISTICAS"]

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
            WorkflowCode.VEHICULO_RENOVACION_ITV,
            WorkflowCode.VEHICULO_RENOVACION_CUVE,
            WorkflowCode.VEHICULO_CAMBIO_CARACTERISTICAS,
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
            title_es="Tipo de Trámite",
            description_es="Seleccione el tipo de renovación o modificación",
            config={
                "options": [
                    {
                        "value": "RENOVACION_ITV",
                        "label_es": "Renovación ITV",
                        "description_es": "Renovar la tarjeta de Inspección Técnica del Vehículo",
                    },
                    {
                        "value": "RENOVACION_CUVE",
                        "label_es": "Renovación CUVE",
                        "description_es": "Renovar la Cartilla Única de Vehículos (OFIVE)",
                    },
                    {
                        "value": "CAMBIO_CARACTERISTICAS",
                        "label_es": "Cambio de Características",
                        "description_es": "Registrar una reforma o modificación del vehículo",
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
            title_es="Documentos del Vehículo",
            description_es="Cargue los documentos requeridos",
            config={
                "dynamic_documents": True,
                "max_file_size_mb": 10,
            }
        ))

        # Step 2: Form Review 1 - Vehicle + Owner
        self.add_step(WorkflowStep(
            step_number=2,
            step_id="form_review_1",
            step_type=StepType.FORM_REVIEW,
            title_es="Datos del Vehículo y Propietario",
            description_es="Verifique los datos extraídos de los documentos",
            config={
                "sections": [
                    {
                        "id": "vehiculo",
                        "title_es": "Datos del Vehículo",
                        "fields": [
                            {"key": "matricula", "label_es": "Matrícula", "type": "text",
                             "required": True, "readonly": True,
                             "pattern": r"^[A-Z]{2}-[0-9]{3}-[A-Z0-9]{1,2}$"},
                            {"key": "numero_bastidor", "label_es": "Número de Bastidor (VIN)", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "marca", "label_es": "Marca", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "modelo", "label_es": "Modelo", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "tipo_vehiculo", "label_es": "Tipo de Vehículo", "type": "select",
                             "required": True, "readonly": False,
                             "options": [
                                 {"value": "TURISMO", "label_es": "Turismo"},
                                 {"value": "CAMION", "label_es": "Camión"},
                                 {"value": "MOTOCICLETA", "label_es": "Motocicleta"},
                                 {"value": "AUTOBUS", "label_es": "Autobús"},
                                 {"value": "FURGONETA", "label_es": "Furgoneta"},
                                 {"value": "REMOLQUE", "label_es": "Remolque"},
                             ]},
                        ]
                    },
                    {
                        "id": "propietario",
                        "title_es": "Datos del Propietario",
                        "fields": [
                            {"key": "propietario_apellidos", "label_es": "Apellidos", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "propietario_nombres", "label_es": "Nombres", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "propietario_numero_id", "label_es": "N° Identificación (DIP/NIE/Pasaporte)",
                             "type": "text", "required": True, "readonly": False,
                             "help_text_es": "Número de DIP, NIE o Pasaporte del propietario"},
                        ]
                    },
                ]
            }
        ))

        # Step 3: Form Review 2 - ITV/CUVE/Reforma specific data
        self.add_step(WorkflowStep(
            step_number=3,
            step_id="form_review_2",
            step_type=StepType.FORM_REVIEW,
            title_es="Datos Técnicos",
            description_es="Verifique los datos técnicos del vehículo",
            config={
                "sections": [
                    {
                        "id": "itv_antigua",
                        "title_es": "ITV Actual (a renovar)",
                        "condition": {"sub_type": "RENOVACION_ITV"},
                        "fields": [
                            {"key": "itv_fecha_inspeccion", "label_es": "Última Inspección", "type": "date",
                             "required": True, "readonly": True},
                            {"key": "itv_valedero_hasta", "label_es": "Válido Hasta", "type": "date",
                             "required": True, "readonly": True},
                            {"key": "itv_resultado", "label_es": "Resultado Anterior", "type": "text",
                             "required": True, "readonly": True},
                        ]
                    },
                    {
                        "id": "cuve_antigua",
                        "title_es": "Datos de la CUVE Actual",
                        "condition": {"sub_type_in": ["RENOVACION_CUVE", "CAMBIO_CARACTERISTICAS"]},
                        "fields": [
                            {"key": "cuve_referencia", "label_es": "Referencia CUVE", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "cuve_fecha_validez", "label_es": "Válido Hasta", "type": "date",
                             "required": True, "readonly": True},
                            {"key": "color", "label_es": "Color del Vehículo", "type": "text",
                             "required": False, "readonly": True},
                            {"key": "potencia_fiscal", "label_es": "Potencia Fiscal (CV)", "type": "number",
                             "required": False, "readonly": True},
                            {"key": "tipo_combustible", "label_es": "Combustible", "type": "text",
                             "required": False, "readonly": True},
                        ]
                    },
                    {
                        "id": "reforma",
                        "title_es": "Datos de la Reforma",
                        "condition": {"sub_type": "CAMBIO_CARACTERISTICAS"},
                        "fields": [
                            {"key": "reforma_descripcion", "label_es": "Descripción de la Reforma", "type": "textarea",
                             "required": True, "readonly": False,
                             "help_text_es": "Describa las modificaciones realizadas al vehículo"},
                        ]
                    },
                ]
            }
        ))

        # Step 4: Payment
        self.add_step(WorkflowStep(
            step_number=4,
            step_id="payment",
            step_type=StepType.PAYMENT,
            title_es="Pago de Tasas",
            description_es="El monto se calcula según las características del vehículo",
            config={
                "currency": "XAF",
                "tariff_source": "rbc-calculator",
            }
        ))

        # Step 5: Confirmation
        self.add_step(WorkflowStep(
            step_number=5,
            step_id="confirmation",
            step_type=StepType.CONFIRMATION,
            title_es="Confirmación y Envío",
            description_es="Verifique todos los datos antes de enviar",
            config={
                "show_summary": True,
                "agent_checklist": [
                    {"id": "documents_verified", "label_es": "He verificado la autenticidad de todos los documentos", "required": True},
                    {"id": "matricula_coherence", "label_es": "He verificado la coherencia de matrícula entre documentos", "required": True},
                    {"id": "renewal_eligible", "label_es": "He verificado que el documento está vencido o próximo a vencer (< 60 días)", "required": True},
                    {"id": "vehicle_inspected", "label_es": "He verificado que el vehículo pasó la inspección (si aplica)", "required": False},
                    {"id": "reforma_authorized", "label_es": "He verificado la autorización de reforma ITVE (cambio características)", "required": False},
                    {"id": "payment_verified", "label_es": "He verificado el pago de las tasas", "required": True},
                ],
                "rejection_reasons": [
                    {"id": "documents_invalid", "label_es": "Documentos inválidos o ilegibles"},
                    {"id": "matricula_mismatch", "label_es": "Matrícula no coincide entre documentos"},
                    {"id": "not_eligible", "label_es": "Documento no está vencido ni próximo a vencer"},
                    {"id": "inspection_failed", "label_es": "Vehículo no aprobó la inspección"},
                    {"id": "reforma_not_authorized", "label_es": "Reforma no autorizada por ITVE"},
                    {"id": "other", "label_es": "Otro (especificar)"},
                ],
            }
        ))

    def _setup_tariffs(self) -> None:
        """RBC tariff for ITV/CUVE, fixed for CAMBIO."""
        self.set_tariff_config(TariffConfig(
            tariff_type=TariffType.RBC,
            currency="XAF",
        ))

    # === Tariff ===

    def get_tariff(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None,
    ) -> int:
        """RENOVACION_ITV/CUVE: RBC dynamic. CAMBIO_CARACTERISTICAS: fixed 50,000 XAF."""
        sub_type = context.sub_type if context else None
        if sub_type == "CAMBIO_CARACTERISTICAS":
            return 50000
        return super().get_tariff(solicitud_type, motivo, context)

    # === Document Requirements ===

    def get_document_requirements(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None,
    ) -> List[DocumentRequirement]:
        sub_type = context.sub_type if context else "RENOVACION_ITV"

        requirements = []

        # Identity document - always required (DIP, NIE or Pasaporte)
        requirements.append(DocumentRequirement(
            document_code="identidad_propietario",
            document_name_es="Documento de Identidad del Propietario",
            schema_key="DIP_GQ_V2",
            is_required=True,
            display_order=1,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es=(
                "DIP, NIE o Pasaporte en vigor del propietario. "
                "Escanee ambas caras del documento."
            ),
            faces_required=["recto", "verso"],
            config={
                "accepted_schemas": [
                    "DIP_GQ_V2",
                    "PERMISO_RESIDENCIA_GQ_V1",
                    "PASAPORTE_GQ_V1",
                    "PASAPORTE_INTERNATIONAL_V1",
                ],
            },
        ))

        # Permiso de Circulación - always required
        requirements.append(DocumentRequirement(
            document_code="permiso_circulacion",
            document_name_es="Permiso de Circulación",
            schema_key="PERMISO_CIRCULACION_GQ_V1",
            is_required=True,
            display_order=2,
            condition_type=DocumentConditionType.ALWAYS,
            instructions_es="Permiso de Circulación vigente. Escanee recto y verso.",
            faces_required=["recto", "verso"],
        ))

        if sub_type == "RENOVACION_ITV":
            requirements.append(DocumentRequirement(
                document_code="itv_antigua",
                document_name_es="Tarjeta ITV actual (a renovar)",
                schema_key="ITV_GQ_V1",
                is_required=True,
                display_order=3,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["RENOVACION_ITV"]},
                instructions_es="Tarjeta ITV vencida o próxima a vencer",
                faces_required=["recto", "verso"],
            ))

        elif sub_type == "RENOVACION_CUVE":
            requirements.append(DocumentRequirement(
                document_code="cuve_antigua",
                document_name_es="CUVE actual (a renovar)",
                schema_key="CUVE_GQ_V1",
                is_required=True,
                display_order=3,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["RENOVACION_CUVE"]},
                instructions_es="CUVE vencida o próxima a vencer",
                faces_required=["recto", "verso"],
            ))
            requirements.append(DocumentRequirement(
                document_code="itv",
                document_name_es="Tarjeta ITV en vigor",
                schema_key="ITV_GQ_V1",
                is_required=True,
                display_order=4,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["RENOVACION_CUVE"]},
                instructions_es="ITV vigente con resultado FAVORABLE",
                faces_required=["recto", "verso"],
            ))

        elif sub_type == "CAMBIO_CARACTERISTICAS":
            requirements.append(DocumentRequirement(
                document_code="cuve",
                document_name_es="CUVE actual",
                schema_key="CUVE_GQ_V1",
                is_required=True,
                display_order=3,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["CAMBIO_CARACTERISTICAS"]},
                instructions_es="CUVE actual del vehículo",
                faces_required=["recto", "verso"],
            ))
            requirements.append(DocumentRequirement(
                document_code="certificado_reforma",
                document_name_es="Certificado de Reforma (ITVE)",
                is_required=True,
                display_order=4,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["CAMBIO_CARACTERISTICAS"]},
                instructions_es="Certificado oficial de ITVE autorizando la reforma del vehículo",
            ))

        return requirements

    # === Form Mapping ===

    def get_form_mapping(
        self,
        context: Optional[WorkflowContext] = None,
    ) -> Dict[str, str]:
        """Map extracted data to form fields (context-aware per sub_type).

        RENOVACION_ITV uploads: DIP, itv_antigua, Permiso
        RENOVACION_CUVE uploads: DIP, cuve_antigua, Permiso, ITV
        CAMBIO_CARACTERISTICAS uploads: DIP, Permiso, CUVE, Certificado Reforma
        """
        sub_type = context.sub_type if context else "RENOVACION_ITV"

        # Common: owner from identity doc (DIP/NIE/Pasaporte) + vehicle from Permiso
        mapping: Dict[str, str] = {
            "propietario_numero_id": "identidad_propietario.documento.numero_dip",
            "propietario_apellidos": "identidad_propietario.titular.apellidos",
            "propietario_nombres": "identidad_propietario.titular.nombres",
            "matricula": "permiso_circulacion.vehiculo.matricula",
            "numero_bastidor": "permiso_circulacion.vehiculo.numero_bastidor",
            "marca": "permiso_circulacion.vehiculo.marca",
            "modelo": "permiso_circulacion.vehiculo.modelo",
            "tipo_vehiculo": "permiso_circulacion.vehiculo.tipo",
        }

        if sub_type == "RENOVACION_ITV":
            # ITV data from itv_antigua (doc being renewed)
            mapping.update({
                "itv_fecha_inspeccion": "itv_antigua.inspeccion_actual.fecha_inspeccion",
                "itv_valedero_hasta": "itv_antigua.inspeccion_actual.valedero_hasta",
                "itv_resultado": "itv_antigua.inspeccion_actual.resultado",
            })
        elif sub_type == "RENOVACION_CUVE":
            # CUVE data from cuve_antigua (doc being renewed)
            mapping.update({
                "cuve_referencia": "cuve_antigua.documento.numero_referencia",
                "cuve_fecha_validez": "cuve_antigua.validez.fecha_validez",
                "color": "cuve_antigua.vehiculo.color",
                "potencia_fiscal": "cuve_antigua.motor.potencia_fiscal",
                "tipo_combustible": "cuve_antigua.motor.tipo_combustible",
            })
        elif sub_type == "CAMBIO_CARACTERISTICAS":
            # CUVE data from cuve (current, not _antigua - different doc code)
            mapping.update({
                "cuve_referencia": "cuve.documento.numero_referencia",
                "cuve_fecha_validez": "cuve.validez.fecha_validez",
                "color": "cuve.vehiculo.color",
                "potencia_fiscal": "cuve.motor.potencia_fiscal",
                "tipo_combustible": "cuve.motor.tipo_combustible",
            })

        return mapping

    # === Step Validation ===

    def validate_step(
        self,
        step_number: int,
        context: WorkflowContext,
    ) -> List[ValidationResult]:
        """Validate form review steps with renewal eligibility checks.

        4 unique rules (not covered by SchemaValidationEngine/RiskAnalyzer):
        1. cuve_renovable (RENOVACION_CUVE): CUVE expires < 60 days or already expired (warning)
        1b. itv_caducidad_renovacion_cuve (RENOVACION_CUVE): ITV expired > 90 days (warning)
        2. itv_renovable (RENOVACION_ITV): ITV expires < 60 days or already expired (warning)
        3. matricula_coherente: cross-doc matricula coherence (permiso vs cuve/itv) (error)
        """
        results = super().validate_step(step_number, context)

        step = self.get_step(step_number)
        if not step:
            return results

        sub_type = context.sub_type

        # Validations on form_review_2 (technical data)
        if step.step_id == "form_review_2":
            if sub_type == "RENOVACION_CUVE":
                # Rule 1: CUVE must be expiring (< 60 days) or expired
                cuve_validez_str = context.get_extracted_field("cuve_antigua", "validez.fecha_validez")
                if cuve_validez_str:
                    try:
                        fecha_s = str(cuve_validez_str).strip()
                        if "/" in fecha_s:
                            cuve_validez = datetime.strptime(fecha_s, "%d/%m/%Y")
                        else:
                            cuve_validez = datetime.strptime(fecha_s, "%Y-%m-%d")
                        days_until_expiry = (cuve_validez - datetime.today()).days
                        if days_until_expiry > 60:
                            results.append(ValidationResult(
                                is_valid=False,
                                rule_id="cuve_renovable",
                                severity="warning",
                                message_es=(
                                    f"La CUVE no expira hasta dentro de {days_until_expiry} días. "
                                    "Solo puede renovar si expira en menos de 60 días."
                                ),
                                field_name="cuve_fecha_validez",
                            ))
                    except (ValueError, TypeError):
                        pass

                # Rule 1b: ITV not expired > 90 days
                itv_validez_str = context.get_extracted_field("itv", "inspeccion_actual.valedero_hasta")
                if itv_validez_str:
                    try:
                        fecha_s = str(itv_validez_str).strip()
                        if "/" in fecha_s:
                            itv_validez = datetime.strptime(fecha_s, "%d/%m/%Y")
                        else:
                            itv_validez = datetime.strptime(fecha_s, "%Y-%m-%d")
                        days_expired = (datetime.today() - itv_validez).days
                        if days_expired > 90:
                            results.append(ValidationResult(
                                is_valid=False,
                                rule_id="itv_caducidad_renovacion_cuve",
                                severity="warning",
                                message_es=(
                                    f"La ITV presentada lleva {days_expired} días caducada "
                                    "(máximo tolerado: 90 días). "
                                    "Se recomienda renovar la ITV antes de renovar la CUVE."
                                ),
                                field_name="itv_valedero_hasta",
                            ))
                    except (ValueError, TypeError):
                        pass

            elif sub_type == "RENOVACION_ITV":
                # Rule 2: ITV must be expiring (< 60 days) or expired
                itv_validez_str = context.get_extracted_field("itv_antigua", "inspeccion_actual.valedero_hasta")
                if itv_validez_str:
                    try:
                        fecha_s = str(itv_validez_str).strip()
                        if "/" in fecha_s:
                            itv_validez = datetime.strptime(fecha_s, "%d/%m/%Y")
                        else:
                            itv_validez = datetime.strptime(fecha_s, "%Y-%m-%d")
                        days_until_expiry = (itv_validez - datetime.today()).days
                        if days_until_expiry > 60:
                            results.append(ValidationResult(
                                is_valid=False,
                                rule_id="itv_renovable",
                                severity="warning",
                                message_es=(
                                    f"La ITV no expira hasta dentro de {days_until_expiry} días. "
                                    "Solo puede renovar si expira en menos de 60 días."
                                ),
                                field_name="itv_valedero_hasta",
                            ))
                    except (ValueError, TypeError):
                        pass

        # Validations on form_review_1 (vehicle data)
        if step.step_id == "form_review_1":
            # Rule 3: Matricula coherence across documents
            permiso_matricula = context.get_extracted_field("permiso_circulacion", "vehiculo.matricula")

            cuve_matricula = context.get_extracted_field("cuve_antigua", "vehiculo.matricula")
            if not cuve_matricula:
                cuve_matricula = context.get_extracted_field("cuve", "vehiculo.matricula")

            itv_matricula = context.get_extracted_field("itv_antigua", "vehiculo.matricula")
            if not itv_matricula:
                itv_matricula = context.get_extracted_field("itv", "vehiculo.matricula")

            if permiso_matricula:
                pm = str(permiso_matricula).strip().upper()
                if cuve_matricula and str(cuve_matricula).strip().upper() != pm:
                    results.append(ValidationResult(
                        is_valid=False,
                        rule_id="matricula_coherente_cuve",
                        severity="error",
                        message_es="La matrícula de la CUVE no coincide con el Permiso de Circulación.",
                        field_name="matricula",
                    ))
                if itv_matricula and str(itv_matricula).strip().upper() != pm:
                    results.append(ValidationResult(
                        is_valid=False,
                        rule_id="matricula_coherente_itv",
                        severity="error",
                        message_es="La matrícula de la ITV no coincide con el Permiso de Circulación.",
                        field_name="matricula",
                    ))

        return results


# =============================================================================
# Singleton & Registration
# =============================================================================

_workflow: Optional[InspeccionVehiculoWorkflow] = None


def get_inspeccion_vehiculo_workflow() -> InspeccionVehiculoWorkflow:
    """Get or create the singleton workflow instance."""
    global _workflow
    if _workflow is None:
        _workflow = InspeccionVehiculoWorkflow()
    return _workflow
