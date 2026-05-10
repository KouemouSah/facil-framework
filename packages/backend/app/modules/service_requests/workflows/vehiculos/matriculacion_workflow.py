"""
MatriculacionTransferenciaWorkflow v2 - Vehicle registration and transfer workflow.

Migrated to PredefinedWorkflow architecture (Option C - Dynamic Form Review).

Handles:
- PRIMERA_MATRICULACION: First registration (new or imported vehicle)
- TRANSFERENCIA: Ownership transfer

Entity: DGT (Dirección General de Tráfico Rodado y Seguridad Vial)

Tarification:
- PRIMERA_MATRICULACION: RBC Calculator (dynamic pricing based on vehicle characteristics)
- TRANSFERENCIA: Fixed 30,000 XAF

Documents:
- PRIMERA_MATRICULACION: Identidad, Certificado Reconocimiento Vehículo (ITVE), Factura
- TRANSFERENCIA: Identidad comprador, Identidad vendedor, Permiso Circulación, CUVE, Contrato Compraventa

OCR schemas:
- DIP_GQ_V2, PERMISO_RESIDENCIA_GQ_V1, PASAPORTE_GQ_V1 (identity)
- CERTIFICADO_RECONOCIMIENTO_VEHICULO_GQ_V1 (PRIMERA)
- PERMISO_CIRCULACION_GQ_V1, CUVE_GQ_V1, CONTRATO_COMPRAVENTA_GQ_V1 (TRANSFERENCIA)

@version 2.1
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


class MatriculacionTransferenciaWorkflow(PredefinedWorkflow):
    """
    Vehicle registration and transfer workflow (DGT).

    Sub-types:
    - PRIMERA_MATRICULACION: First registration (new or imported vehicle)
      Documents: Certificado Reconocimiento Vehículo (ITVE) + Factura
      No matricula (vehicle not yet registered).
      Favorable = texto "reúne las condiciones mínimas" in certificado.
    - TRANSFERENCIA: Ownership transfer between parties
      Documents: Permiso Circulación + CUVE + Contrato Compraventa

    Steps:
    0. select_type: Choose PRIMERA_MATRICULACION or TRANSFERENCIA
    1. upload_documents: Upload documents (dynamic per sub-type)
    2. form_review_1: Vehicle data (conditional sections per sub-type)
    3. form_review_2: Owner data + seller (TRANSFERENCIA) + compraventa (TRANSFERENCIA)
    4. payment: RBC (PRIMERA) / Fixed 30,000 (TRANSFERENCIA)
    5. confirmation: Summary + agent_checklist + rejection_reasons
    """

    # === Properties ===

    @property
    def workflow_code(self) -> WorkflowCode:
        return WorkflowCode.VEHICULO_PRIMERA_MATRICULACION

    @property
    def category(self) -> WorkflowCategory:
        return WorkflowCategory.VEHICULOS

    @property
    def entity_code(self) -> EntityCode:
        return EntityCode.DGT

    @property
    def service_name_es(self) -> str:
        return "Matriculación y Transferencia de Vehículos"

    def get_subtype_display_names(self) -> Dict[str, str]:
        return {
            "VEHICULO_PRIMERA_MATRICULACION": "Vehículo - Primera Matriculación",
            "VEHICULO_TRANSFERENCIA": "Vehículo - Transferencia",
        }

    @property
    def allowed_solicitud_types(self) -> List[SolicitudType]:
        return [SolicitudType.EXPEDICION]

    @property
    def allowed_sub_types(self) -> List[str]:
        return ["PRIMERA_MATRICULACION", "TRANSFERENCIA"]

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
        """Register under both PRIMERA_MATRICULACION and TRANSFERENCIA codes."""
        return [
            WorkflowCode.VEHICULO_PRIMERA_MATRICULACION,
            WorkflowCode.VEHICULO_TRANSFERENCIA,
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
            description_es="Seleccione el tipo de trámite vehicular",
            config={
                "options": [
                    {
                        "value": "PRIMERA_MATRICULACION",
                        "label_es": "Primera Matriculación",
                        "description_es": "Registrar un vehículo nuevo o importado por primera vez",
                    },
                    {
                        "value": "TRANSFERENCIA",
                        "label_es": "Transferencia de Propiedad",
                        "description_es": "Cambio de propietario de un vehículo ya matriculado",
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
            description_es="Cargue los documentos requeridos según el tipo de trámite",
            config={
                "dynamic_documents": True,
                "max_file_size_mb": 10,
            }
        ))

        # Step 2: Form Review 1 - Vehicle data (conditional sections per sub-type)
        self.add_step(WorkflowStep(
            step_number=2,
            step_id="form_review_1",
            step_type=StepType.FORM_REVIEW,
            title_es="Datos del Vehículo",
            description_es="Verifique los datos del vehículo extraídos de los documentos",
            config={
                "sections": [
                    # PRIMERA_MATRICULACION: vehicle data from Certificado Reconocimiento
                    # No matricula (vehicle not yet registered)
                    {
                        "id": "vehiculo_primera",
                        "title_es": "Identificación del Vehículo",
                        "condition": {"sub_type": "PRIMERA_MATRICULACION"},
                        "fields": [
                            {"key": "numero_bastidor", "label_es": "Número de Bastidor (VIN)", "type": "text",
                             "required": True, "readonly": True,
                             "help_text_es": "Extraído del Certificado de Reconocimiento"},
                            {"key": "marca", "label_es": "Marca", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "modelo", "label_es": "Denominación Comercial", "type": "text",
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
                                 {"value": "OTRO", "label_es": "Otro (especificar)"},
                             ],
                             "help_text_es": "Pre-relleno desde la forma de carruaje del certificado. Seleccione 'Otro' si no corresponde."},
                            {"key": "tipo_vehiculo_otro", "label_es": "Tipo de Vehículo (especificar)", "type": "text",
                             "required": False, "readonly": False,
                             "show_when": {"field": "tipo_vehiculo", "value": "OTRO"},
                             "help_text_es": "Especifique el tipo de vehículo si no figura en la lista"},
                            {"key": "potencia_fiscal", "label_es": "Potencia Fiscal (CVF)", "type": "number",
                             "required": False, "readonly": True},
                            {"key": "tipo_combustible", "label_es": "Combustible", "type": "text",
                             "required": False, "readonly": True},
                            {"key": "vehiculo_estado", "label_es": "Estado del Vehículo", "type": "text",
                             "required": False, "readonly": True,
                             "help_text_es": "VEHICULO NUEVO o VEHICULO USADO"},
                        ]
                    },
                    # Certificado Reconocimiento data (PRIMERA only)
                    {
                        "id": "certificado_data",
                        "title_es": "Certificado de Primer Reconocimiento",
                        "condition": {"sub_type": "PRIMERA_MATRICULACION"},
                        "fields": [
                            {"key": "numero_certificado", "label_es": "N° Certificado", "type": "text",
                             "required": True, "readonly": True,
                             "help_text_es": "Número del certificado (ej: 25496/48762)"},
                            {"key": "cumple_condiciones_minimas", "label_es": "Cumple Condiciones Mínimas",
                             "type": "boolean", "required": True, "readonly": True,
                             "pdf_exclude": True,
                             "help_text_es": (
                                 "Determinado por el texto del certificado: "
                                 "'reúne las condiciones mínimas necesarias para circular'"
                             )},
                            {"key": "tiene_firma", "label_es": "Firma del Ingeniero", "type": "boolean",
                             "required": True, "readonly": True, "pdf_exclude": True},
                            {"key": "tiene_sello", "label_es": "Sello Oficial", "type": "boolean",
                             "required": True, "readonly": True, "pdf_exclude": True},
                            {"key": "fecha_certificado", "label_es": "Fecha del Certificado", "type": "date",
                             "required": True, "readonly": True},
                        ]
                    },
                    # TRANSFERENCIA: vehicle data from Permiso + CUVE
                    {
                        "id": "vehiculo_transferencia",
                        "title_es": "Identificación del Vehículo",
                        "condition": {"sub_type": "TRANSFERENCIA"},
                        "fields": [
                            {"key": "matricula", "label_es": "Matrícula", "type": "text",
                             "required": True, "readonly": True,
                             "pattern": r"^[A-Z]{2}-[0-9]{3}-[A-Z0-9]{1,2}$",
                             "help_text_es": "Formato: XX-NNN-Y (ej: BN-123-A)"},
                            {"key": "numero_bastidor", "label_es": "Número de Bastidor (VIN)", "type": "text",
                             "required": True, "readonly": True,
                             "pattern": r"^[A-HJ-NPR-Z0-9]{17}$",
                             "help_text_es": "17 caracteres alfanuméricos"},
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
                            {"key": "color", "label_es": "Color", "type": "text",
                             "required": False, "readonly": True},
                            {"key": "potencia_fiscal", "label_es": "Potencia Fiscal (CV)", "type": "number",
                             "required": False, "readonly": True},
                            {"key": "tipo_combustible", "label_es": "Combustible", "type": "text",
                             "required": False, "readonly": True},
                        ]
                    },
                ]
            }
        ))

        # Step 3: Form Review 2 - Owner + seller data
        self.add_step(WorkflowStep(
            step_number=3,
            step_id="form_review_2",
            step_type=StepType.FORM_REVIEW,
            title_es="Datos del Propietario",
            description_es="Verifique los datos del propietario y del vendedor (si aplica)",
            config={
                "sections": [
                    {
                        "id": "propietario_primera",
                        "title_es": "Datos del Propietario",
                        "condition": {"sub_type": "PRIMERA_MATRICULACION"},
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
                    {
                        "id": "comprador",
                        "title_es": "Datos del Comprador (Nuevo Propietario)",
                        "condition": {"sub_type": "TRANSFERENCIA"},
                        "fields": [
                            {"key": "propietario_apellidos", "label_es": "Apellidos del Comprador", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "propietario_nombres", "label_es": "Nombres del Comprador", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "propietario_numero_id", "label_es": "N° Identificación del Comprador (DIP/NIE/Pasaporte)",
                             "type": "text", "required": True, "readonly": False,
                             "help_text_es": "Número de DIP, NIE o Pasaporte del comprador"},
                        ]
                    },
                    {
                        "id": "vendedor",
                        "title_es": "Datos del Vendedor",
                        "condition": {"sub_type": "TRANSFERENCIA"},
                        "fields": [
                            {"key": "vendedor_apellidos", "label_es": "Apellidos del Vendedor", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "vendedor_nombres", "label_es": "Nombres del Vendedor", "type": "text",
                             "required": True, "readonly": True},
                            {"key": "vendedor_numero_id", "label_es": "N° Identificación del Vendedor (DIP/NIE/Pasaporte)",
                             "type": "text", "required": True, "readonly": False,
                             "help_text_es": "Número de DIP, NIE o Pasaporte del vendedor"},
                        ]
                    },
                    {
                        "id": "compraventa",
                        "title_es": "Datos de la Compraventa",
                        "condition": {"sub_type": "TRANSFERENCIA"},
                        "fields": [
                            {"key": "fecha_compraventa", "label_es": "Fecha de Firma", "type": "date",
                             "required": True, "readonly": True},
                            {"key": "precio_venta", "label_es": "Precio de Venta (XAF)", "type": "number",
                             "required": True, "readonly": True},
                            {"key": "contrato_matricula", "label_es": "Matrícula (según contrato)", "type": "text",
                             "required": True, "readonly": True,
                             "help_text_es": "Debe coincidir con la matrícula del Permiso de Circulación"},
                            {"key": "contrato_bastidor", "label_es": "N° Bastidor (según contrato)", "type": "text",
                             "required": True, "readonly": True,
                             "help_text_es": "Debe coincidir con el VIN del Permiso de Circulación"},
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
            description_es="El monto se calcula según el tipo y características del vehículo",
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
            description_es="Verifique todos los datos antes de enviar su solicitud",
            config={
                "show_summary": True,
                "agent_checklist": [
                    {"id": "documents_verified", "label_es": "He verificado la autenticidad de todos los documentos", "required": True},
                    {"id": "matricula_vin_match", "label_es": "He verificado que matrícula y VIN coinciden entre documentos", "required": True},
                    {"id": "owner_identity_verified", "label_es": "He verificado la identidad del propietario", "required": True},
                    {"id": "reconocimiento_favorable", "label_es": "He verificado que el Certificado de Reconocimiento confirma condiciones mínimas (primera matriculación)", "required": False},
                    {"id": "seller_owner_match", "label_es": "He verificado que vendedor = propietario en Permiso (transferencia)", "required": False},
                    {"id": "transfer_deadline", "label_es": "He verificado el plazo de transferencia (< 10 días)", "required": False},
                    {"id": "payment_verified", "label_es": "He verificado el pago de las tasas", "required": True},
                ],
                "rejection_reasons": [
                    {"id": "documents_invalid", "label_es": "Documentos inválidos o ilegibles"},
                    {"id": "matricula_mismatch", "label_es": "Matrícula no coincide entre documentos"},
                    {"id": "vin_mismatch", "label_es": "Número de bastidor no coincide"},
                    {"id": "owner_mismatch", "label_es": "Identidad del propietario no verificada"},
                    {"id": "seller_not_owner", "label_es": "El vendedor no es el propietario registrado"},
                    {"id": "reconocimiento_not_favorable", "label_es": "El Certificado de Reconocimiento no confirma condiciones mínimas"},
                    {"id": "transfer_expired", "label_es": "Plazo de transferencia expirado"},
                    {"id": "other", "label_es": "Otro (especificar)"},
                ],
            }
        ))

    def _setup_tariffs(self) -> None:
        """RBC tariff for PRIMERA, fixed for TRANSFERENCIA."""
        self.set_tariff_config(TariffConfig(
            tariff_type=TariffType.RBC,
            currency="XAF",
        ))

    def get_tariff(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None,
    ) -> int:
        """PRIMERA: RBC dynamic. TRANSFERENCIA: fixed 30,000 XAF."""
        sub_type = context.sub_type if context else None
        if sub_type == "TRANSFERENCIA":
            return 30000
        # PRIMERA_MATRICULACION: delegate to parent (RBC calculator)
        return super().get_tariff(solicitud_type, motivo, context)

    # === Document Requirements ===

    def get_document_requirements(
        self,
        solicitud_type: SolicitudType,
        motivo: Optional[RenovacionMotivo] = None,
        context: Optional[WorkflowContext] = None,
    ) -> List[DocumentRequirement]:
        sub_type = context.sub_type if context else "PRIMERA_MATRICULACION"

        requirements = []

        # Identity document of owner - DIP, NIE or Pasaporte accepted
        id_code = "identidad_comprador" if sub_type == "TRANSFERENCIA" else "identidad_propietario"
        requirements.append(DocumentRequirement(
            document_code=id_code,
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
                "accepted_schemas": ["DIP_GQ_V2", "PERMISO_RESIDENCIA_GQ_V1", "PASAPORTE_GQ_V1", "PASAPORTE_INTERNATIONAL_V1"],
            },
        ))

        if sub_type == "PRIMERA_MATRICULACION":
            # Certificado de Primer Reconocimiento de Vehículo (ITVE)
            requirements.append(DocumentRequirement(
                document_code="certificado_reconocimiento",
                document_name_es="Certificado de Primer Reconocimiento de Vehículo",
                schema_key="CERTIFICADO_RECONOCIMIENTO_VEHICULO_GQ_V1",
                is_required=True,
                display_order=2,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["PRIMERA_MATRICULACION"]},
                instructions_es=(
                    "Certificado expedido por la Estación ITV (ITVE) tras el primer "
                    "reconocimiento del vehículo. Documento de una sola cara."
                ),
                faces_required=["recto"],
            ))

            # Factura - primera matriculación (no OCR schema)
            requirements.append(DocumentRequirement(
                document_code="factura",
                document_name_es="Factura o Contrato de Adquisición",
                is_required=True,
                display_order=3,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["PRIMERA_MATRICULACION"]},
                instructions_es="Factura de compra del vehículo nuevo o importado",
            ))

        elif sub_type == "TRANSFERENCIA":
            # Identity document vendedor
            requirements.append(DocumentRequirement(
                document_code="identidad_vendedor",
                document_name_es="Documento de Identidad del Vendedor",
                schema_key="DIP_GQ_V2",
                is_required=True,
                display_order=2,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["TRANSFERENCIA"]},
                instructions_es=(
                    "DIP, NIE o Pasaporte en vigor del vendedor. "
                    "Escanee ambas caras del documento."
                ),
                faces_required=["recto", "verso"],
                config={
                    "accepted_schemas": ["DIP_GQ_V2", "PERMISO_RESIDENCIA_GQ_V1", "PASAPORTE_GQ_V1", "PASAPORTE_INTERNATIONAL_V1"],
                },
            ))

            # Permiso de Circulación
            requirements.append(DocumentRequirement(
                document_code="permiso_circulacion",
                document_name_es="Permiso de Circulación",
                schema_key="PERMISO_CIRCULACION_GQ_V1",
                is_required=True,
                display_order=3,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["TRANSFERENCIA"]},
                instructions_es="Permiso de Circulación vigente. Escanee recto y verso.",
                faces_required=["recto", "verso"],
            ))

            # CUVE (optionnelle pour transferencia)
            requirements.append(DocumentRequirement(
                document_code="cuve",
                document_name_es="CUVE (Cartilla Única de Vehículos)",
                schema_key="CUVE_GQ_V1",
                is_required=False,
                display_order=4,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["TRANSFERENCIA"]},
                instructions_es="CUVE expedida por OFIVE (optionnel). Escanee recto y verso.",
                faces_required=["recto", "verso"],
            ))

            # Contrato de Compraventa (FIX: correct schema key)
            requirements.append(DocumentRequirement(
                document_code="contrato_compraventa",
                document_name_es="Contrato de Compraventa",
                schema_key="CONTRATO_COMPRAVENTA_GQ_V1",
                is_required=True,
                display_order=5,
                condition_type=DocumentConditionType.CUSTOM,
                condition_value={"types": ["TRANSFERENCIA"]},
                instructions_es="Contrato de compraventa firmado por ambas partes",
            ))

        return requirements

    # === Form Mapping ===

    def get_form_mapping(
        self,
        context: Optional[WorkflowContext] = None,
    ) -> Dict[str, str]:
        """Map extracted data to form fields (context-aware per sub_type).

        PRIMERA_MATRICULACION uploads: Identidad, Certificado Reconocimiento, Factura
        → Vehicle data from Certificado (no matricula — vehicle not yet registered)

        TRANSFERENCIA uploads: Identidad comprador+vendedor, Permiso, CUVE, Contrato
        → Vehicle data from Permiso + CUVE
        """
        sub_type = context.sub_type if context else "PRIMERA_MATRICULACION"

        # Common: owner from identity document
        id_prefix = "identidad_comprador" if sub_type == "TRANSFERENCIA" else "identidad_propietario"
        mapping: Dict[str, str] = {
            # numero_identificacion resolved by pipeline (numero_dip / numero_nie / numero_pasaporte)
            "propietario_numero_id": f"{id_prefix}.documento.numero_dip",
            "propietario_apellidos": f"{id_prefix}.titular.apellidos",
            "propietario_nombres": f"{id_prefix}.titular.nombres",
        }

        if sub_type == "PRIMERA_MATRICULACION":
            # Vehicle data from Certificado de Primer Reconocimiento (ITVE)
            # NO matricula: vehicle not yet registered, plate assigned after approval
            mapping.update({
                "numero_bastidor": "certificado_reconocimiento.caracteristicas_tecnicas.numero_bastidor",
                "marca": "certificado_reconocimiento.caracteristicas_tecnicas.marca",
                "modelo": "certificado_reconocimiento.caracteristicas_tecnicas.denominacion_comercial",
                "tipo_vehiculo": "certificado_reconocimiento.caracteristicas_tecnicas.forma_carruaje",
                "potencia_fiscal": "certificado_reconocimiento.caracteristicas_tecnicas.potencia_fiscal_cvf",
                "tipo_combustible": "certificado_reconocimiento.caracteristicas_tecnicas.tipo_combustible",
                "vehiculo_estado": "certificado_reconocimiento.caracteristicas_tecnicas.vehiculo_estado",
                # Certificado data
                "numero_certificado": "certificado_reconocimiento.documento.numero_certificado",
                "cumple_condiciones_minimas": "certificado_reconocimiento.certificacion.cumple_condiciones_minimas",
                "tiene_firma": "certificado_reconocimiento.firma.tiene_firma",
                "tiene_sello": "certificado_reconocimiento.firma.tiene_sello",
                "fecha_certificado": "certificado_reconocimiento.certificacion.fecha",
            })
        else:
            # TRANSFERENCIA: vehicle from Permiso + CUVE
            mapping.update({
                "matricula": "permiso_circulacion.vehiculo.matricula",
                "numero_bastidor": "permiso_circulacion.vehiculo.numero_bastidor",
                "marca": "permiso_circulacion.vehiculo.marca",
                "modelo": "permiso_circulacion.vehiculo.modelo",
                "tipo_vehiculo": "permiso_circulacion.vehiculo.tipo",
                "color": "cuve.vehiculo.color",
                "potencia_fiscal": "cuve.motor.potencia_fiscal",
                "tipo_combustible": "cuve.motor.tipo_combustible",
                # Contrato Compraventa
                "fecha_compraventa": "contrato_compraventa.contrato.fecha",
                "precio_venta": "contrato_compraventa.precio.monto",
                "contrato_matricula": "contrato_compraventa.vehiculo.matricula",
                "contrato_bastidor": "contrato_compraventa.vehiculo.numero_bastidor",
                # Seller from identity document
                "vendedor_numero_id": "identidad_vendedor.documento.numero_dip",
                "vendedor_apellidos": "identidad_vendedor.titular.apellidos",
                "vendedor_nombres": "identidad_vendedor.titular.nombres",
            })

        return mapping

    # === Step Validation ===

    def validate_step(
        self,
        step_number: int,
        context: WorkflowContext,
    ) -> List[ValidationResult]:
        """Validate form review steps with cross-document coherence checks.

        Rules (not covered by SchemaValidationEngine/RiskAnalyzer):

        form_review_1 (PRIMERA):
        0a. reconocimiento_favorable: cumple_condiciones_minimas must be True
        0b. certificado_firma: tiene_firma must be True
        0c. certificado_sello: tiene_sello must be True

        form_review_2 (TRANSFERENCIA):
        1. matricula_coherente: permiso.matricula == cuve.matricula (if CUVE provided)
        2. bastidor_coherente: permiso.VIN == cuve.VIN (if CUVE provided)
        3. propietario_vendedor_coherente: permiso owner == vendedor
        4. transferencia_plazo: fecha_compraventa < 10 days (warning)
        5. contrato_matricula_coherente: contrato.matricula == permiso.matricula
        6. contrato_bastidor_coherente: contrato.VIN == permiso.VIN
        """
        results = super().validate_step(step_number, context)

        step = self.get_step(step_number)
        if not step:
            return results

        sub_type = context.sub_type

        # === form_review_1 validations ===
        if step.step_id == "form_review_1" and sub_type == "PRIMERA_MATRICULACION":
            # Rule 0: Certificado must confirm vehicle meets minimum conditions
            cumple = context.get_extracted_field("certificado_reconocimiento", "certificacion.cumple_condiciones_minimas")
            if cumple is not None and not cumple:
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id="reconocimiento_favorable",
                    severity="error",
                    message_es=(
                        "El Certificado de Primer Reconocimiento no confirma que el vehículo "
                        "reúne las condiciones mínimas necesarias para circular. "
                        "No se puede proceder a la matriculación."
                    ),
                    field_name="cumple_condiciones_minimas",
                ))

            # Rule 0b: Certificado must have official signature
            tiene_firma = context.get_extracted_field("certificado_reconocimiento", "firma.tiene_firma")
            if tiene_firma is not None and not tiene_firma:
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id="certificado_firma",
                    severity="error",
                    message_es=(
                        "El Certificado de Primer Reconocimiento no tiene firma del ingeniero. "
                        "El documento no es válido sin firma."
                    ),
                    field_name="tiene_firma",
                ))

            # Rule 0c: Certificado must have official stamp
            tiene_sello = context.get_extracted_field("certificado_reconocimiento", "firma.tiene_sello")
            if tiene_sello is not None and not tiene_sello:
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id="certificado_sello",
                    severity="error",
                    message_es=(
                        "El Certificado de Primer Reconocimiento no tiene sello oficial "
                        "de la estación ITV. El documento no es válido sin sello."
                    ),
                    field_name="tiene_sello",
                ))

        # === form_review_2 validations ===
        if step.step_id != "form_review_2":
            return results

        # Rule 1: Matricula coherence (permiso vs cuve)
        permiso_matricula = context.get_extracted_field("permiso_circulacion", "vehiculo.matricula")
        cuve_matricula = context.get_extracted_field("cuve", "vehiculo.matricula")
        if permiso_matricula and cuve_matricula:
            if str(permiso_matricula).strip().upper() != str(cuve_matricula).strip().upper():
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id="matricula_coherente",
                    severity="error",
                    message_es="La matrícula del Permiso de Circulación no coincide con la CUVE.",
                    field_name="matricula",
                ))

        # Rule 2: VIN/Bastidor coherence (permiso vs cuve)
        permiso_vin = context.get_extracted_field("permiso_circulacion", "vehiculo.numero_bastidor")
        cuve_vin = context.get_extracted_field("cuve", "vehiculo.numero_bastidor")
        if permiso_vin and cuve_vin:
            if str(permiso_vin).strip().upper() != str(cuve_vin).strip().upper():
                results.append(ValidationResult(
                    is_valid=False,
                    rule_id="bastidor_coherente",
                    severity="error",
                    message_es="El número de bastidor del Permiso no coincide con la CUVE.",
                    field_name="numero_bastidor",
                ))

        if sub_type == "TRANSFERENCIA":
            # Rule 5: Contrato matricula must match permiso matricula
            contrato_matricula = context.get_extracted_field("contrato_compraventa", "vehiculo.matricula")
            if permiso_matricula and contrato_matricula:
                if str(contrato_matricula).strip().upper() != str(permiso_matricula).strip().upper():
                    results.append(ValidationResult(
                        is_valid=False,
                        rule_id="contrato_matricula_coherente",
                        severity="error",
                        message_es=(
                            "La matrícula del contrato de compraventa no coincide "
                            "con el Permiso de Circulación."
                        ),
                        field_name="contrato_matricula",
                    ))

            # Rule 6: Contrato VIN must match permiso VIN
            contrato_vin = context.get_extracted_field("contrato_compraventa", "vehiculo.numero_bastidor")
            if permiso_vin and contrato_vin:
                if str(contrato_vin).strip().upper() != str(permiso_vin).strip().upper():
                    results.append(ValidationResult(
                        is_valid=False,
                        rule_id="contrato_bastidor_coherente",
                        severity="error",
                        message_es=(
                            "El número de bastidor del contrato de compraventa no coincide "
                            "con el Permiso de Circulación."
                        ),
                        field_name="contrato_bastidor",
                    ))

            # Rule 3: Owner == Seller (permiso owner must match seller identity doc)
            permiso_apellidos = context.get_extracted_field("permiso_circulacion", "propietario.apellidos")
            vendedor_apellidos = context.get_extracted_field("identidad_vendedor", "titular.apellidos")
            if permiso_apellidos and vendedor_apellidos:
                if str(permiso_apellidos).strip().upper() != str(vendedor_apellidos).strip().upper():
                    results.append(ValidationResult(
                        is_valid=False,
                        rule_id="propietario_vendedor_coherente",
                        severity="error",
                        message_es=(
                            "El propietario registrado en el Permiso de Circulación "
                            "no coincide con el vendedor (DIP)."
                        ),
                        field_name="vendedor_apellidos",
                    ))

            # Rule 4: Transfer deadline (10 days from contract date)
            fecha_str = context.get_extracted_field("contrato_compraventa", "contrato.fecha")
            if fecha_str:
                try:
                    fecha_s = str(fecha_str).strip()
                    # Support both ISO (YYYY-MM-DD) and GQ format (DD/MM/YYYY)
                    if "/" in fecha_s:
                        fecha = datetime.strptime(fecha_s, "%d/%m/%Y")
                    else:
                        fecha = datetime.strptime(fecha_s, "%Y-%m-%d")
                    days_since = (datetime.today() - fecha).days
                    if days_since > 10:
                        results.append(ValidationResult(
                            is_valid=False,
                            rule_id="transferencia_plazo",
                            severity="warning",
                            message_es=(
                                f"Han pasado {days_since} días desde la firma del contrato. "
                                "El plazo legal para la transferencia es de 10 días."
                            ),
                            field_name="fecha_compraventa",
                        ))
                except (ValueError, TypeError):
                    pass

        return results


# =============================================================================
# Singleton & Registration
# =============================================================================

_workflow: Optional[MatriculacionTransferenciaWorkflow] = None


def get_matriculacion_transferencia_workflow() -> MatriculacionTransferenciaWorkflow:
    """Get or create the singleton workflow instance."""
    global _workflow
    if _workflow is None:
        _workflow = MatriculacionTransferenciaWorkflow()
    return _workflow
