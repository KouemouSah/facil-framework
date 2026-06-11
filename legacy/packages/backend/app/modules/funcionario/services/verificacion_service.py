"""
Verificacion Funcionario Service.

Handles the business logic for civil servant verification:
- Document extraction using GeminiDocumentProcessor
- Cross-validation between DIP and proof document
- Storage in Firebase + database
- Required documents definition
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Optional, Dict, Any, List
from uuid import UUID

from loguru import logger

from app.modules.service_requests.services.gemini_document_processor import gemini_document_processor as gemini_processor
from ..repositories.verificacion_repository import verificacion_repository
from ..models.verificacion import DocumentoTipoPrueba


# =============================================================================
# DOCUMENT REQUIREMENT DEFINITION
# =============================================================================

@dataclass
class FuncionarioDocumentRequirement:
    """
    Document required for funcionario verification.

    Aligned with service_requests.workflows.workflow_interface.DocumentRequirement
    but simplified for funcionario use case.
    """
    document_code: str
    document_name_es: str
    schema_key: Optional[str] = None
    is_required: bool = True
    display_order: int = 0
    instructions_es: Optional[str] = None
    faces_required: List[str] = field(default_factory=list)
    accepted_formats: List[str] = field(default_factory=lambda: ["pdf", "jpg", "jpeg", "png"])
    max_size_mb: int = 10
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "document_code": self.document_code,
            "document_name_es": self.document_name_es,
            "schema_key": self.schema_key,
            "is_required": self.is_required,
            "display_order": self.display_order,
            "instructions_es": self.instructions_es,
            "faces_required": self.faces_required,
            "accepted_formats": self.accepted_formats,
            "max_size_mb": self.max_size_mb,
            "config": self.config,
        }


class VerificacionService:
    """Service for civil servant verification."""

    # Schema mapping for proof documents
    SCHEMA_MAP = {
        DocumentoTipoPrueba.NOMBRAMIENTO: "NOMBRAMIENTO_GQ_V1",
        DocumentoTipoPrueba.CARNET_FUNCIONARIO: "CARNET_FUNCIONARIO_GQ_V1",
        DocumentoTipoPrueba.CONTRATO_FUNCIONARIO: "CONTRATO_FUNCIONARIO_GQ_V1",
    }

    # ==========================================================================
    # FORM REVIEW CONFIGURATION
    # Pattern aligned with pasaporte_workflow_v2.py
    # Single form_review with 3 sections (total ~15 fields)
    # ==========================================================================

    FORM_REVIEW_CONFIG = {
        "step_id": "form_review",
        "title_es": "Verificar Datos Extraídos",
        "description_es": "Revise y corrija los datos extraídos de sus documentos antes de enviar la solicitud",
        "sections": [
            # === Section 1: Datos Personales (from DIP) ===
            {
                "id": "datos_personales",
                "title_es": "Datos Personales (DIP)",
                "source_document": "dip",
                "fields": [
                    {"key": "numero_dip", "label_es": "Número DIP", "required": True, "editable": True, "critical": True},
                    {"key": "apellidos", "label_es": "Apellidos", "required": True, "editable": True},
                    {"key": "nombres", "label_es": "Nombres", "required": True, "editable": True},
                    {"key": "fecha_nacimiento", "label_es": "Fecha de Nacimiento", "required": False, "editable": True, "type": "date"},
                    {"key": "lugar_nacimiento", "label_es": "Lugar de Nacimiento", "required": False, "editable": True},
                    {"key": "sexo", "label_es": "Sexo", "required": False, "editable": True, "type": "select", "options": ["M", "F"]},
                    {"key": "nacionalidad", "label_es": "Nacionalidad", "required": False, "editable": True},
                ]
            },
            # === Section 2: Datos Funcionario (from Documento Prueba) ===
            {
                "id": "datos_funcionario",
                "title_es": "Datos Funcionario",
                "source_document": "documento_prueba",  # Dynamic: nombramiento, carnet_funcionario, or contrato_funcionario
                "fields": [
                    {"key": "matricula", "label_es": "Matrícula", "required": True, "editable": True, "critical": True},
                    {"key": "nombre_completo", "label_es": "Nombre Completo", "required": False, "editable": False},  # Readonly for comparison
                    {"key": "cargo", "label_es": "Cargo", "required": False, "editable": True},
                    {"key": "ministerio", "label_es": "Ministerio/Entidad", "required": False, "editable": True},
                    {"key": "fecha_nombramiento", "label_es": "Fecha de Nombramiento", "required": False, "editable": True, "type": "date"},
                    {"key": "categoria", "label_es": "Categoría", "required": False, "editable": True},
                ]
            },
            # === Section 3: Validación Cruzada (readonly) ===
            {
                "id": "validacion_cruzada",
                "title_es": "Validación Cruzada",
                "readonly": True,
                "fields": [
                    {"key": "nombre_dip", "label_es": "Nombre en DIP", "editable": False, "type": "text"},
                    {"key": "nombre_documento", "label_es": "Nombre en Documento", "editable": False, "type": "text"},
                    {"key": "similitud_nombre", "label_es": "Similitud de Nombres", "editable": False, "type": "percentage_badge"},
                    {"key": "matricula_ingresada", "label_es": "Matrícula Ingresada", "editable": False, "type": "text"},
                    {"key": "matricula_documento", "label_es": "Matrícula en Documento", "editable": False, "type": "text"},
                    {"key": "matriculas_coinciden", "label_es": "Matrículas Coinciden", "editable": False, "type": "validation_badge"},
                    {"key": "validacion_automatica_posible", "label_es": "Auto-validable", "editable": False, "type": "validation_badge"},
                ]
            }
        ]
    }

    # ==========================================================================
    # FIELD MAPPING: form_field_key -> extraction_path
    # Pattern aligned with pasaporte_workflow_v2.get_form_field_mapping()
    # ==========================================================================

    FORM_FIELD_MAPPING = {
        # === DIP fields ===
        # Aligned with dip_gq.json schema
        "numero_dip": "dip.documento.numero_dip",
        "apellidos": "dip.titular.apellidos",
        "nombres": "dip.titular.nombres",
        "fecha_nacimiento": "dip.titular.fecha_nacimiento",
        "lugar_nacimiento": "dip.titular.lugar_nacimiento",
        "sexo": "dip.titular.sexo",
        "nacionalidad": "dip.titular.nacionalidad",

        # === Documento Prueba fields ===
        # These have multiple possible paths depending on document type
        # The get_field_value method handles the dynamic resolution

        # Nombramiento paths (nombramiento_gq.json)
        "matricula_nombramiento": "nombramiento.funcionario.matricula",
        "nombre_completo_nombramiento": "nombramiento.funcionario.nombre_completo",
        "cargo_nombramiento": "nombramiento.nombramiento.cargo",
        "ministerio_nombramiento": "nombramiento.destino.ministerio",
        "fecha_nombramiento_nombramiento": "nombramiento.nombramiento.fecha_nombramiento",
        "categoria_nombramiento": "nombramiento.funcionario.categoria",

        # Carnet Funcionario paths (carnet_funcionario_gq.json)
        "matricula_carnet": "carnet_funcionario.titular.matricula",
        "nombre_completo_carnet": "carnet_funcionario.titular.nombre_completo",
        "cargo_carnet": "carnet_funcionario.puesto.puesto",
        "ministerio_carnet": "carnet_funcionario.empleador.nombre",
        "categoria_carnet": "carnet_funcionario.titular.categoria",

        # Contrato Funcionario paths (contrato_funcionario_gq.json)
        "matricula_contrato": "contrato_funcionario.empleado.matricula",
        "nombre_completo_contrato": "contrato_funcionario.empleado.nombre_completo",
        "cargo_contrato": "contrato_funcionario.puesto.cargo",
        "ministerio_contrato": "contrato_funcionario.empleador.ministerio",
        "fecha_nombramiento_contrato": "contrato_funcionario.contrato.fecha_inicio",
        "categoria_contrato": "contrato_funcionario.empleado.categoria",

        # === Validación Cruzada fields (from calculated cross-validation) ===
        "nombre_dip": "validacion_cruzada.nombre_dip",
        "nombre_documento": "validacion_cruzada.nombre_documento",
        "similitud_nombre": "validacion_cruzada.similitud_nombre",
        "matricula_ingresada": "validacion_cruzada.matricula_ingresada",
        "matricula_documento": "validacion_cruzada.matricula_documento",
        "matriculas_coinciden": "validacion_cruzada.matriculas_coinciden",
        "validacion_automatica_posible": "validacion_cruzada.validacion_automatica_posible",
    }

    # ==========================================================================
    # DOCUMENT REQUIREMENTS
    # ==========================================================================

    def get_required_documents(
        self,
        tipo_prueba: Optional[DocumentoTipoPrueba] = None
    ) -> List[FuncionarioDocumentRequirement]:
        """
        Get required documents for funcionario verification.

        This centralizes document definitions for:
        - Frontend wizard (display requirements)
        - Backend validation (check all required docs uploaded)
        - OCR extraction (schema keys)

        Args:
            tipo_prueba: Proof document type (nombramiento, carnet, contrato)
                        If None, returns ALL proof document options as alternatives.

        Returns:
            List of required documents with schema keys and instructions
        """
        logger.debug(f"[Verificacion] get_required_documents called with tipo_prueba={tipo_prueba}")

        requirements = []

        # 1. DIP - Always required
        requirements.append(FuncionarioDocumentRequirement(
            document_code="dip",
            document_name_es="Documento de Identidad Personal (DIP)",
            schema_key="DIP_GQ_V2",
            is_required=True,
            display_order=1,
            instructions_es=(
                "Escanee ambas caras de su DIP vigente (recto y verso). "
                "Asegúrese que el documento sea legible y no esté vencido."
            ),
            faces_required=["recto", "verso"],
            config={"single_file": True, "is_reference_document": True}
        ))

        # 2. Proof document - specific type or all three as alternatives
        if tipo_prueba == DocumentoTipoPrueba.NOMBRAMIENTO:
            requirements.append(FuncionarioDocumentRequirement(
                document_code="nombramiento",
                document_name_es="Acta de Nombramiento",
                schema_key="NOMBRAMIENTO_GQ_V1",
                is_required=True,
                display_order=2,
                instructions_es=(
                    "Escanee el acta de nombramiento oficial. "
                    "Debe contener su nombre completo, matrícula y cargo."
                ),
                config={"requires_signature": True, "requires_seal": True}
            ))
        elif tipo_prueba == DocumentoTipoPrueba.CARNET_FUNCIONARIO:
            requirements.append(FuncionarioDocumentRequirement(
                document_code="carnet_funcionario",
                document_name_es="Carnet de Funcionario",
                schema_key="CARNET_FUNCIONARIO_GQ_V1",
                is_required=True,
                display_order=2,
                instructions_es=(
                    "Escanee ambas caras del carnet de funcionario vigente. "
                    "Debe mostrar su nombre completo y matrícula."
                ),
                faces_required=["recto", "verso"],
                config={"single_file": True}
            ))
        elif tipo_prueba == DocumentoTipoPrueba.CONTRATO_FUNCIONARIO:
            requirements.append(FuncionarioDocumentRequirement(
                document_code="contrato_funcionario",
                document_name_es="Contrato de Funcionario",
                schema_key="CONTRATO_FUNCIONARIO_GQ_V1",
                is_required=True,
                display_order=2,
                instructions_es=(
                    "Escanee el contrato de funcionario firmado. "
                    "Debe contener su nombre completo, matrícula y firma del empleador."
                ),
                config={"requires_signature": True}
            ))
        else:
            # No specific type selected - return ALL THREE as alternatives
            # User must upload ONE of these (validated by validate_required_documents)
            logger.debug("[Verificacion] No tipo_prueba specified, returning all proof options as alternatives")

            requirements.append(FuncionarioDocumentRequirement(
                document_code="nombramiento",
                document_name_es="Acta de Nombramiento",
                schema_key="NOMBRAMIENTO_GQ_V1",
                is_required=False,  # Not individually required, ONE of three is required
                display_order=2,
                instructions_es=(
                    "Escanee el acta de nombramiento oficial. "
                    "Debe contener su nombre completo, matrícula y cargo."
                ),
                config={
                    "requires_signature": True,
                    "requires_seal": True,
                    "is_alternative": True,
                    "alternative_group": "documento_prueba"
                }
            ))
            requirements.append(FuncionarioDocumentRequirement(
                document_code="carnet_funcionario",
                document_name_es="Carnet de Funcionario",
                schema_key="CARNET_FUNCIONARIO_GQ_V1",
                is_required=False,  # Not individually required, ONE of three is required
                display_order=3,
                instructions_es=(
                    "Escanee ambas caras del carnet de funcionario vigente. "
                    "Debe mostrar su nombre completo y matrícula."
                ),
                faces_required=["recto", "verso"],
                config={
                    "single_file": True,
                    "is_alternative": True,
                    "alternative_group": "documento_prueba"
                }
            ))
            requirements.append(FuncionarioDocumentRequirement(
                document_code="contrato_funcionario",
                document_name_es="Contrato de Funcionario",
                schema_key="CONTRATO_FUNCIONARIO_GQ_V1",
                is_required=False,  # Not individually required, ONE of three is required
                display_order=4,
                instructions_es=(
                    "Escanee el contrato de funcionario firmado. "
                    "Debe contener su nombre completo, matrícula y firma del empleador."
                ),
                config={
                    "requires_signature": True,
                    "is_alternative": True,
                    "alternative_group": "documento_prueba"
                }
            ))

        logger.debug(f"[Verificacion] Returning {len(requirements)} document requirements")
        return sorted(requirements, key=lambda d: d.display_order)

    def get_proof_document_options(self) -> List[Dict[str, Any]]:
        """
        Get available proof document options for frontend display.

        Returns:
            List of proof document types with their display info
        """
        return [
            {
                "code": DocumentoTipoPrueba.NOMBRAMIENTO.value,
                "name_es": "Acta de Nombramiento",
                "description_es": "Resolución o decreto oficial de nombramiento",
                "schema_key": self.SCHEMA_MAP[DocumentoTipoPrueba.NOMBRAMIENTO],
            },
            {
                "code": DocumentoTipoPrueba.CARNET_FUNCIONARIO.value,
                "name_es": "Carnet de Funcionario",
                "description_es": "Carnet de identificación de funcionario público",
                "schema_key": self.SCHEMA_MAP[DocumentoTipoPrueba.CARNET_FUNCIONARIO],
            },
            {
                "code": DocumentoTipoPrueba.CONTRATO_FUNCIONARIO.value,
                "name_es": "Contrato de Funcionario",
                "description_es": "Contrato laboral como funcionario público",
                "schema_key": self.SCHEMA_MAP[DocumentoTipoPrueba.CONTRATO_FUNCIONARIO],
            },
        ]

    def validate_required_documents(
        self,
        verification_data: Dict[str, Any],
        tipo_prueba: Optional[DocumentoTipoPrueba] = None
    ) -> List[Dict[str, Any]]:
        """
        Validate that all required documents are present and valid.

        Handles two scenarios:
        1. tipo_prueba specified: DIP + specific proof doc must be present
        2. tipo_prueba not specified: DIP + ONE of the three proof docs must be present

        Args:
            verification_data: The verification_data dict with document extractions
            tipo_prueba: Type of proof document expected (optional)

        Returns:
            List of validation errors (empty if all OK)
        """
        logger.debug(f"[Verificacion] validate_required_documents called, tipo_prueba={tipo_prueba}")
        logger.debug(f"[Verificacion] verification_data keys: {list(verification_data.keys())}")

        errors = []
        alternative_groups: Dict[str, List[str]] = {}  # Track alternative groups

        requirements = self.get_required_documents(tipo_prueba)

        for req in requirements:
            doc_code = req.document_code
            is_alternative = req.config.get("is_alternative", False)
            alternative_group = req.config.get("alternative_group")

            # Track alternatives for group validation later
            if is_alternative and alternative_group:
                if alternative_group not in alternative_groups:
                    alternative_groups[alternative_group] = []
                alternative_groups[alternative_group].append(doc_code)
                continue  # Don't validate individually, will validate group

            # Validate required (non-alternative) documents
            doc_data = verification_data.get(doc_code, {})
            if not doc_data:
                if req.is_required:
                    logger.warning(f"[Verificacion] Missing required document: {doc_code}")
                    errors.append({
                        "document_code": doc_code,
                        "error": "missing_document",
                        "message_es": f"Falta el {req.document_name_es}",
                    })
                continue

            # Check if extraction was successful
            extraction = doc_data.get("extraction")
            if not extraction:
                logger.warning(f"[Verificacion] Extraction failed for document: {doc_code}")
                errors.append({
                    "document_code": doc_code,
                    "error": "extraction_failed",
                    "message_es": f"No se pudieron extraer datos del {req.document_name_es}",
                })

        # Validate alternative groups (user must provide ONE of the alternatives)
        for group_name, doc_codes in alternative_groups.items():
            logger.debug(f"[Verificacion] Validating alternative group '{group_name}': {doc_codes}")

            # Check if at least one alternative has valid extraction
            has_valid_alternative = False
            for doc_code in doc_codes:
                doc_data = verification_data.get(doc_code, {})
                if doc_data and doc_data.get("extraction"):
                    has_valid_alternative = True
                    logger.debug(f"[Verificacion] Found valid alternative: {doc_code}")
                    break

            if not has_valid_alternative:
                logger.warning(f"[Verificacion] No valid document in alternative group: {group_name}")
                errors.append({
                    "document_code": group_name,
                    "error": "missing_alternative",
                    "message_es": (
                        "Debe subir uno de los siguientes documentos: "
                        "Acta de Nombramiento, Carnet de Funcionario, o Contrato de Funcionario."
                    ),
                    "alternatives": doc_codes,
                })

        logger.debug(f"[Verificacion] Validation complete, {len(errors)} errors found")
        return errors

    # =========================================================================
    # FORM REVIEW - Build structured data for auto-fill
    # Pattern aligned with pasaporte_workflow_v2.py
    # =========================================================================

    def _resolve_field_value(
        self,
        path: str,
        verification_data: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Resolve a field value from a dot-notation path.

        Examples:
            "dip.titular.apellidos" -> verification_data["dip"]["extraction"]["titular"]["apellidos"]
            "validacion_cruzada.similitud_nombre" -> verification_data["validacion_cruzada"]["similitud_nombre"]

        Args:
            path: Dot-notation path (e.g., "dip.titular.apellidos")
            verification_data: The verification_data dict

        Returns:
            Resolved value or None if not found
        """
        parts = path.split(".")
        if not parts:
            return None

        # First part is the document key or special key
        root_key = parts[0]

        if root_key == "validacion_cruzada":
            # Special case: validacion_cruzada is at root level
            current = verification_data.get("validacion_cruzada", {})
            for part in parts[1:]:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None
            return current

        # For documents (dip, nombramiento, carnet_funcionario, contrato_funcionario)
        doc_data = verification_data.get(root_key, {})
        extraction = doc_data.get("extraction", {})

        # Navigate the rest of the path
        current = extraction
        for part in parts[1:]:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

        return current

    def _get_proof_document_type(self, verification_data: Dict[str, Any]) -> Optional[str]:
        """Get the type of proof document that was uploaded."""
        for t in DocumentoTipoPrueba:
            if t.value in verification_data and verification_data[t.value].get("extraction"):
                return t.value
        return None

    def _get_funcionario_field_value(
        self,
        field_key: str,
        proof_doc_type: str,
        verification_data: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Get a funcionario field value, resolving the correct path based on document type.

        Different document types have different extraction structures:
        - nombramiento: funcionario.matricula, nombramiento.cargo, destino.ministerio
        - carnet_funcionario: titular.matricula, puesto.puesto, empleador.nombre
        - contrato_funcionario: empleado.matricula, puesto.cargo, empleador.ministerio
        """
        proof_data = verification_data.get(proof_doc_type, {})
        extraction = proof_data.get("extraction", {})

        # Define field mappings per document type
        field_paths = {
            "nombramiento": {
                "matricula": ["funcionario", "matricula"],
                "nombre_completo": ["funcionario", "nombre_completo"],
                "cargo": ["nombramiento", "cargo"],
                "ministerio": ["destino", "ministerio"],
                "fecha_nombramiento": ["nombramiento", "fecha_nombramiento"],
                "categoria": ["funcionario", "categoria"],
            },
            "carnet_funcionario": {
                "matricula": ["titular", "matricula"],
                "nombre_completo": ["titular", "nombre_completo"],
                "cargo": ["puesto", "puesto"],
                "ministerio": ["empleador", "nombre"],
                "fecha_nombramiento": None,  # Not available in carnet
                "categoria": ["titular", "categoria"],
            },
            "contrato_funcionario": {
                "matricula": ["empleado", "matricula"],
                "nombre_completo": ["empleado", "nombre_completo"],
                "cargo": ["puesto", "cargo"],
                "ministerio": ["empleador", "ministerio"],
                "fecha_nombramiento": ["contrato", "fecha_inicio"],
                "categoria": ["empleado", "categoria"],
            },
        }

        # Get the path for this field and document type
        doc_fields = field_paths.get(proof_doc_type, {})
        path_parts = doc_fields.get(field_key)

        if not path_parts:
            return None

        # Navigate to the value
        current = extraction
        for part in path_parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

        return current

    def build_form_review_data(
        self,
        verificacion_id: UUID,
        verification_data: Dict[str, Any],
        status: str,
    ) -> Dict[str, Any]:
        """
        Build form_review data using FORM_REVIEW_CONFIG and FORM_FIELD_MAPPING.

        This method constructs a structured response for the frontend to:
        1. Auto-fill form fields with extracted values
        2. Display validation status (warnings, cross-validation)
        3. Allow user to review and correct data

        Args:
            verificacion_id: Verification ID
            verification_data: The verification_data dict with extractions
            status: Verification status

        Returns:
            Dict with sections, fields, values, and validation info
        """
        logger.info(f"[Verificacion] Building form_review data for {verificacion_id}")

        validacion = verification_data.get("validacion_cruzada", {})
        proof_doc_type = self._get_proof_document_type(verification_data)

        sections = []
        config = self.FORM_REVIEW_CONFIG

        for section_config in config["sections"]:
            section_id = section_config["id"]
            section_fields = []

            for field_config in section_config["fields"]:
                field_key = field_config["key"]
                value = None
                source_document = section_config.get("source_document")
                confidence = None

                # Resolve value based on section type
                if section_id == "datos_personales":
                    # DIP fields
                    path = self.FORM_FIELD_MAPPING.get(field_key)
                    if path:
                        value = self._resolve_field_value(path, verification_data)
                    source_document = "dip"
                    dip_data = verification_data.get("dip", {})
                    confidence = dip_data.get("extraction_confidence")

                elif section_id == "datos_funcionario":
                    # Proof document fields - dynamic resolution
                    if proof_doc_type:
                        value = self._get_funcionario_field_value(field_key, proof_doc_type, verification_data)
                        source_document = proof_doc_type
                        proof_data = verification_data.get(proof_doc_type, {})
                        confidence = proof_data.get("extraction_confidence")

                elif section_id == "validacion_cruzada":
                    # Cross-validation fields
                    value = validacion.get(field_key)
                    source_document = None

                    # Format special types
                    if field_config.get("type") == "percentage_badge" and isinstance(value, (int, float)):
                        value = f"{int(value * 100)}%"
                    elif field_config.get("type") == "validation_badge" and isinstance(value, bool):
                        value = "✓ Sí" if value else "✗ No"

                section_fields.append({
                    "field_name": field_key,
                    "field_label_es": field_config["label_es"],
                    "value": str(value) if value is not None else None,
                    "source_document": source_document,
                    "confidence": confidence,
                    "is_editable": field_config.get("editable", True),
                    "is_required": field_config.get("required", False),
                    "is_critical": field_config.get("critical", False),
                    "field_type": field_config.get("type", "text"),
                    "options": field_config.get("options"),
                })

            # Update section title for datos_funcionario to show actual document type
            section_title = section_config["title_es"]
            if section_id == "datos_funcionario" and proof_doc_type:
                doc_names = {
                    "nombramiento": "Nombramiento",
                    "carnet_funcionario": "Carnet Funcionario",
                    "contrato_funcionario": "Contrato Funcionario",
                }
                section_title = f"Datos Funcionario ({doc_names.get(proof_doc_type, proof_doc_type)})"

            sections.append({
                "section_id": section_id,
                "section_title_es": section_title,
                "readonly": section_config.get("readonly", False),
                "source_document": section_config.get("source_document"),
                "fields": section_fields,
            })

        # Build warnings from cross-validation
        warnings = []
        if validacion:
            similitud = validacion.get("similitud_nombre", 0)
            if similitud < 0.85:
                warnings.append({
                    "code": "LOW_NAME_SIMILARITY",
                    "message": f"El nombre en el DIP no coincide bien con el documento de prueba (similitud: {int(similitud * 100)}%)",
                    "severity": "warning",
                    "field": "nombre_completo",
                })
            if not validacion.get("matriculas_coinciden", False):
                warnings.append({
                    "code": "MATRICULA_MISMATCH",
                    "message": "La matrícula ingresada no coincide con la del documento",
                    "severity": "warning",
                    "field": "matricula",
                })

        cross_validation_passed = (
            validacion.get("nombres_coinciden", False) and
            validacion.get("matriculas_coinciden", False)
        )
        auto_validable = validacion.get("validacion_automatica_posible", False)

        logger.info(
            f"[Verificacion] Form review built for {verificacion_id}: "
            f"sections={len(sections)}, warnings={len(warnings)}, "
            f"cross_validation_passed={cross_validation_passed}, auto_validable={auto_validable}"
        )

        return {
            "verificacion_id": str(verificacion_id),
            "status": status,
            "step_id": config["step_id"],
            "title_es": config["title_es"],
            "description_es": config["description_es"],
            "proof_document_type": proof_doc_type,
            "cross_validation_passed": cross_validation_passed,
            "auto_validable": auto_validable,
            "warnings": warnings,
            "sections": sections,
            "raw_extractions": {
                "dip": verification_data.get("dip", {}).get("extraction", {}),
                "documento_prueba": verification_data.get(proof_doc_type, {}).get("extraction", {}) if proof_doc_type else {},
                "validacion_cruzada": validacion,
            },
        }

    def get_form_review_config(self) -> Dict[str, Any]:
        """
        Get the form_review configuration for frontend initialization.

        Returns the static configuration without any data, useful for
        frontend to know the structure before documents are uploaded.
        """
        return self.FORM_REVIEW_CONFIG

    # =========================================================================
    # EXTRACTION - Delegates to GeminiDocumentProcessor
    # =========================================================================

    async def extract_dip(
        self,
        file_content: bytes,
        mime_type: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Extract data from DIP using Gemini with risk analysis.

        Args:
            file_content: File bytes
            mime_type: MIME type (image/*, application/pdf)
            user_id: User ID for tracking

        Returns:
            Extraction result dict with risk_analysis
        """
        logger.info(f"[Verificacion] Starting DIP extraction for user {user_id}")
        logger.debug(f"[Verificacion] DIP file size: {len(file_content)} bytes, mime_type: {mime_type}")

        try:
            result = await gemini_processor.process(
                content=file_content,
                mime_type=mime_type,
                document_code="dip",
                user_id=user_id,
                extraction_schema_key="DIP_GQ_V2",
                workflow_code="VERIFICACION_FUNCIONARIO",  # Use funcionario config for identity fields
            )

            confidence = result.get("confidence", 0)
            status = result.get("status", "error")
            risk_analysis = result.get("risk_analysis", {})

            logger.info(
                f"[Verificacion] DIP extraction complete for user {user_id}: "
                f"status={status}, confidence={confidence:.2f}, "
                f"risk_level={risk_analysis.get('risk_level', 'unknown')}"
            )

            # Log risk factors if any
            if risk_analysis.get("risk_factors"):
                logger.debug(
                    f"[Verificacion] DIP risk factors: "
                    f"{risk_analysis.get('factors_count', {})}"
                )

            return {
                "extraction": result.get("extraction", {}),
                "confidence": confidence,
                "processor": result.get("processor", "unknown"),
                "status": status,
                "schema_used": "DIP_GQ_V2",
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                # Risk analysis from Gemini processor
                "risk_analysis": risk_analysis,
            }

        except Exception as e:
            logger.error(f"[Verificacion] DIP extraction failed for user {user_id}: {e}", exc_info=True)
            return {
                "extraction": {},
                "confidence": 0,
                "processor": "error",
                "status": "error",
                "error": str(e),
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                "risk_analysis": {
                    "risk_level": "high",
                    "risk_score": 80,
                    "risk_factors": [{
                        "code": "EXTRACTION_FAILED",
                        "severity": "high",
                        "message": f"Error al extraer datos del DIP: {str(e)}"
                    }],
                    "requires_review": True,
                },
            }

    async def extract_documento_prueba(
        self,
        file_content: bytes,
        mime_type: str,
        tipo_documento: DocumentoTipoPrueba,
        user_id: str,
        existing_dip_extraction: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extract data from proof document (nombramiento/carnet/contrato) with risk analysis.

        Uses FUNCIONARIO_IDENTITY_FIELDS from gemini_document_processor for:
        - Matricula comparison (BLOCKING if mismatch)
        - Name comparison (WARNING with 85% similarity threshold)
        - DIP number comparison (WARNING)

        Args:
            file_content: File bytes
            mime_type: MIME type
            tipo_documento: Type of proof document
            user_id: User ID for tracking
            existing_dip_extraction: Previous DIP extraction for cross-validation

        Returns:
            Extraction result dict with risk_analysis
        """
        schema_key = self.SCHEMA_MAP.get(tipo_documento)

        logger.info(
            f"[Verificacion] Starting {tipo_documento.value} extraction for user {user_id}, "
            f"schema={schema_key}"
        )
        logger.debug(
            f"[Verificacion] File size: {len(file_content)} bytes, mime_type: {mime_type}, "
            f"has_dip_extraction: {existing_dip_extraction is not None}"
        )

        # Prepare existing documents for cross-validation by Gemini
        existing_documents = None
        if existing_dip_extraction:
            existing_documents = {"dip": existing_dip_extraction}
            logger.debug("[Verificacion] Will perform cross-validation with existing DIP extraction")

        try:
            result = await gemini_processor.process(
                content=file_content,
                mime_type=mime_type,
                document_code=tipo_documento.value,
                user_id=user_id,
                extraction_schema_key=schema_key,
                existing_documents=existing_documents,
                workflow_code="VERIFICACION_FUNCIONARIO",  # Use funcionario config
            )

            confidence = result.get("confidence", 0)
            status = result.get("status", "error")
            risk_analysis = result.get("risk_analysis", {})

            logger.info(
                f"[Verificacion] {tipo_documento.value} extraction complete for user {user_id}: "
                f"status={status}, confidence={confidence:.2f}, "
                f"risk_level={risk_analysis.get('risk_level', 'unknown')}"
            )

            # Log identity mismatches if any (from cross-validation)
            if risk_analysis.get("identity_mismatches"):
                identity_mismatches = risk_analysis["identity_mismatches"]
                has_blocking = risk_analysis.get("has_blocking_mismatches", False)
                logger.warning(
                    f"[Verificacion] Identity mismatches found for {tipo_documento.value}: "
                    f"count={len(identity_mismatches)}, has_blocking={has_blocking}"
                )
                for mismatch in identity_mismatches:
                    logger.debug(
                        f"[Verificacion] Mismatch: {mismatch.get('field_name')} - "
                        f"blocking={mismatch.get('is_blocking')}, "
                        f"ref='{mismatch.get('reference_value')}', "
                        f"doc='{mismatch.get('document_value')}'"
                    )

            # Log risk factors
            if risk_analysis.get("risk_factors"):
                factors_count = risk_analysis.get("factors_count", {})
                logger.debug(
                    f"[Verificacion] {tipo_documento.value} risk factors: {factors_count}"
                )

            return {
                "tipo": tipo_documento.value,
                "extraction": result.get("extraction", {}),
                "confidence": confidence,
                "processor": result.get("processor", "unknown"),
                "status": status,
                "schema_used": schema_key,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                # Risk analysis from Gemini processor
                "risk_analysis": risk_analysis,
            }

        except Exception as e:
            logger.error(
                f"[Verificacion] {tipo_documento.value} extraction failed for user {user_id}: {e}",
                exc_info=True
            )
            return {
                "tipo": tipo_documento.value,
                "extraction": {},
                "confidence": 0,
                "processor": "error",
                "status": "error",
                "error": str(e),
                "schema_used": schema_key,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                "risk_analysis": {
                    "risk_level": "high",
                    "risk_score": 80,
                    "risk_factors": [{
                        "code": "EXTRACTION_FAILED",
                        "severity": "high",
                        "message": f"Error al extraer datos del {tipo_documento.value}: {str(e)}"
                    }],
                    "requires_review": True,
                },
            }

    # =========================================================================
    # CROSS-VALIDATION - Funcionario-specific logic
    # =========================================================================

    def calculate_cross_validation(self, verification_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate cross-validation between DIP and proof document.

        This is funcionario-specific validation logic that calculates:
        - Name similarity between DIP and proof document (85% minimum for pass)
        - Matricula match between user input and document extraction
        - Auto-validation eligibility (90% name + matricula match)

        Args:
            verification_data: The complete verification_data with DIP and proof document

        Returns:
            Cross-validation result dict with:
            - nombre_dip, nombre_documento: Extracted names
            - nombres_coinciden: True if similarity >= 85%
            - similitud_nombre: Similarity ratio (0.0-1.0)
            - matricula_documento, matricula_ingresada: Matriculas
            - matriculas_coinciden: True if exact match
            - validacion_automatica_posible: True if agent work can be reduced
        """
        logger.debug("[Verificacion] Calculating cross-validation")

        dip_data = verification_data.get("dip", {})
        dip_ext = dip_data.get("extraction", {})

        # Get proof document (could be nombramiento, carnet, or contrato)
        prueba_data = None
        prueba_ext = {}
        for doc_type in [e.value for e in DocumentoTipoPrueba]:
            if doc_type in verification_data:
                prueba_data = verification_data[doc_type]
                prueba_ext = prueba_data.get("extraction", {})
                break

        matricula_ingresada = verification_data.get("matricula", "")

        # Extract name from DIP
        titular = dip_ext.get("titular", {})
        apellidos_dip = titular.get("apellidos", "") or dip_ext.get("apellidos", "")
        nombres_dip = titular.get("nombres", "") or dip_ext.get("nombres", "")
        nombre_dip = f"{apellidos_dip} {nombres_dip}".upper().strip()

        # Extract name from proof document (varies by document type)
        nombre_prueba = ""
        matricula_doc = ""

        # Try different extraction paths based on document structure
        if "funcionario" in prueba_ext:
            # Nombramiento structure
            func = prueba_ext["funcionario"]
            nombre_prueba = func.get("nombre_completo", "")
            if not nombre_prueba:
                nombre_prueba = f"{func.get('apellidos', '')} {func.get('nombres', '')}".strip()
            matricula_doc = func.get("matricula", "")

        elif "titular" in prueba_ext:
            # Carnet structure
            tit = prueba_ext["titular"]
            nombre_prueba = tit.get("nombre_completo", "")
            if not nombre_prueba:
                nombre_prueba = f"{tit.get('apellidos', '')} {tit.get('nombres', '')}".strip()
            matricula_doc = tit.get("matricula", "")

        elif "empleado" in prueba_ext:
            # Contrato structure
            emp = prueba_ext["empleado"]
            nombre_prueba = emp.get("nombre_completo", "")
            if not nombre_prueba:
                nombre_prueba = f"{emp.get('apellidos', '')} {emp.get('nombres', '')}".strip()
            matricula_doc = emp.get("matricula", "")

        else:
            # Fallback: try root level fields
            nombre_prueba = prueba_ext.get("nombre_completo", "")
            if not nombre_prueba:
                nombre_prueba = f"{prueba_ext.get('apellidos', '')} {prueba_ext.get('nombres', '')}".strip()
            matricula_doc = prueba_ext.get("matricula", "")

        nombre_prueba = nombre_prueba.upper().strip()
        matricula_doc = matricula_doc.upper().strip()
        matricula_ingresada_norm = matricula_ingresada.upper().strip()

        # Calculate name similarity
        similitud = 0.0
        if nombre_dip and nombre_prueba:
            similitud = SequenceMatcher(None, nombre_dip, nombre_prueba).ratio()

        # Determine matches
        nombres_coinciden = similitud >= 0.85
        matriculas_coinciden = matricula_doc == matricula_ingresada_norm if matricula_doc else False

        # Auto-validation possible if both match well
        validacion_automatica_posible = (
            similitud >= 0.90 and
            matriculas_coinciden and
            matricula_doc != "" and
            nombre_dip != "" and
            nombre_prueba != ""
        )

        logger.info(
            f"[Verificacion] Cross-validation complete: "
            f"similitud={similitud:.2f}, nombres_coinciden={nombres_coinciden}, "
            f"matriculas_coinciden={matriculas_coinciden}, auto_validable={validacion_automatica_posible}"
        )
        logger.debug(
            f"[Verificacion] Cross-validation details: "
            f"nombre_dip='{nombre_dip}', nombre_prueba='{nombre_prueba}', "
            f"matricula_doc='{matricula_doc}', matricula_ingresada='{matricula_ingresada_norm}'"
        )

        return {
            "nombre_dip": nombre_dip,
            "nombre_documento": nombre_prueba,
            "nombres_coinciden": nombres_coinciden,
            "similitud_nombre": round(similitud, 2),
            "matricula_documento": matricula_doc,
            "matricula_ingresada": matricula_ingresada_norm,
            "matriculas_coinciden": matriculas_coinciden,
            "validacion_automatica_posible": validacion_automatica_posible,
        }

    # =========================================================================
    # VERIFICATION WORKFLOW
    # =========================================================================

    async def create_verification(
        self,
        user_id: UUID,
        matricula: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new verification request.

        Returns:
            Created verification record
        """
        logger.info(f"[Verificacion] Creating verification for user {user_id}, matricula={matricula}")

        # Check if user already has a pending request
        existing = await verificacion_repository.get_pending_by_user(user_id)
        if existing:
            logger.warning(f"[Verificacion] User {user_id} already has pending verification {existing['id']}")
            raise ValueError("Ya tiene una solicitud de verificación pendiente")

        # Check if user is already verified
        status = await verificacion_repository.get_user_funcionario_status(user_id)
        if status.get("is_verified_funcionario"):
            logger.warning(f"[Verificacion] User {user_id} is already verified as funcionario")
            raise ValueError("Ya está verificado como funcionario")

        # Create initial verification_data
        verification_data = {
            "matricula": matricula.upper().strip(),
        }

        result = await verificacion_repository.create(
            user_id=user_id,
            matricula=matricula,
            verification_data=verification_data,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(f"[Verificacion] Created verification {result['id']} for user {user_id}")
        return result

    async def update_document_data(
        self,
        verificacion_id: UUID,
        document_type: str,
        document_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update verification with document extraction data.

        Triggers cross-validation calculation when both DIP and proof document are present.

        Args:
            verificacion_id: Verification ID
            document_type: "dip" or DocumentoTipoPrueba value
            document_data: Document data including extraction

        Returns:
            Updated verification record
        """
        logger.info(f"[Verificacion] Updating document data for verification {verificacion_id}, type={document_type}")

        # Get current verification
        current = await verificacion_repository.get_by_id(verificacion_id)
        if not current:
            logger.error(f"[Verificacion] Verification {verificacion_id} not found")
            raise ValueError("Verificación no encontrada")

        if current["status"] != "pendiente":
            logger.warning(f"[Verificacion] Cannot modify processed verification {verificacion_id}")
            raise ValueError("No se puede modificar una verificación ya procesada")

        # Merge new document data
        verification_data = current.get("verification_data", {}) or {}
        verification_data[document_type] = document_data

        logger.debug(f"[Verificacion] Current documents: {list(verification_data.keys())}")

        # Recalculate cross-validation if we have both documents
        has_dip = "dip" in verification_data and verification_data["dip"].get("extraction")
        has_proof = any(
            t.value in verification_data and verification_data[t.value].get("extraction")
            for t in DocumentoTipoPrueba
        )

        if has_dip and has_proof:
            logger.info(f"[Verificacion] Both documents present, calculating cross-validation")
            verification_data["validacion_cruzada"] = self.calculate_cross_validation(verification_data)
        else:
            logger.debug(f"[Verificacion] Skipping cross-validation: has_dip={has_dip}, has_proof={has_proof}")

        result = await verificacion_repository.update_verification_data(verificacion_id, verification_data)
        logger.info(f"[Verificacion] Document data updated for verification {verificacion_id}")

        return result

    async def save_form_review_data(
        self,
        verificacion_id: UUID,
        user_id: UUID,
        form_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Save user-corrected form_review data.

        This endpoint is called after the user reviews and corrects the auto-filled
        form_review data. The corrected data is stored in verification_data["form_review_confirmed"]
        and will be used during submission.

        **IMPORTANT:** This method MERGES the user's corrections with the extracted data,
        similar to pasaporte's form_data merge pattern. This ensures all data (modified
        and unmodified) is preserved.

        Args:
            verificacion_id: Verification ID
            user_id: User ID (for authorization)
            form_data: User-corrected form data (flat dict of field_name -> value)
                      Can contain only modified fields - will be merged with extracted data

        Returns:
            Updated verification with form_review_confirmed data
        """
        logger.info(f"[Verificacion] Saving form_review data for verification {verificacion_id}")

        # Get current verification
        current = await verificacion_repository.get_by_id(verificacion_id)
        if not current:
            raise ValueError("Verificación no encontrada")

        if str(current["user_id"]) != str(user_id):
            raise ValueError("No autorizado")

        if current["status"] != "pendiente":
            raise ValueError("No se puede modificar una verificación ya procesada")

        verification_data = current.get("verification_data", {}) or {}

        # =====================================================================
        # STEP 1: Build base data from extractions (like pasaporte form_mapping)
        # =====================================================================
        extracted_form_data = self._build_extracted_form_data(verification_data)
        logger.debug(f"[Verificacion] Extracted {len(extracted_form_data)} fields from documents")

        # =====================================================================
        # STEP 2: Merge with user corrections (user data takes precedence)
        # This is the key pattern from pasaporte: {**extracted, **user_edits}
        # =====================================================================
        merged_data = {**extracted_form_data, **form_data}
        logger.debug(f"[Verificacion] Merged data: {len(merged_data)} total fields")

        # Validate critical fields in merged data
        critical_fields = ["numero_dip", "matricula"]
        missing_critical = [f for f in critical_fields if not merged_data.get(f)]
        if missing_critical:
            raise ValueError(f"Campos críticos faltantes: {', '.join(missing_critical)}")

        # =====================================================================
        # STEP 3: Store merged data with metadata
        # =====================================================================
        verification_data["form_review_confirmed"] = {
            "data": merged_data,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
            "fields_count": len(merged_data),
            "user_modified_fields": list(form_data.keys()),  # Track what user changed
            "extracted_fields_count": len(extracted_form_data),
        }

        # Update matricula if changed (important for cross-validation)
        new_matricula = merged_data.get("matricula", "").upper().strip()
        old_matricula = verification_data.get("matricula", "").upper().strip()

        if new_matricula and new_matricula != old_matricula:
            logger.info(f"[Verificacion] Matricula updated: {old_matricula} -> {new_matricula}")
            verification_data["matricula"] = new_matricula
            # Recalculate cross-validation with new matricula
            verification_data["validacion_cruzada"] = self.calculate_cross_validation(verification_data)

        result = await verificacion_repository.update_verification_data(verificacion_id, verification_data)

        logger.info(
            f"[Verificacion] Form review data saved for {verificacion_id}, "
            f"total_fields={len(merged_data)}, user_modified={len(form_data)}, "
            f"matricula_updated={new_matricula != old_matricula}"
        )

        return {
            "success": True,
            "verificacion_id": str(verificacion_id),
            "fields_saved": len(merged_data),
            "user_modified_count": len(form_data),
            "extracted_count": len(extracted_form_data),
            "matricula_updated": new_matricula != old_matricula,
            "validacion_cruzada": verification_data.get("validacion_cruzada"),
        }

    def _build_extracted_form_data(self, verification_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build flat form data from document extractions.

        This is equivalent to pasaporte's _apply_form_mapping but simplified
        for funcionario's 2-document structure.

        Returns:
            Flat dict of field_name -> value from extractions
        """
        form_data = {}

        # === Extract from DIP ===
        dip_data = verification_data.get("dip", {})
        dip_ext = dip_data.get("extraction", {})
        titular = dip_ext.get("titular", {})
        documento = dip_ext.get("documento", {})

        # DIP fields
        if titular.get("apellidos") or dip_ext.get("apellidos"):
            form_data["apellidos"] = titular.get("apellidos") or dip_ext.get("apellidos")
        if titular.get("nombres") or dip_ext.get("nombres"):
            form_data["nombres"] = titular.get("nombres") or dip_ext.get("nombres")
        if titular.get("fecha_nacimiento") or dip_ext.get("fecha_nacimiento"):
            form_data["fecha_nacimiento"] = titular.get("fecha_nacimiento") or dip_ext.get("fecha_nacimiento")
        if titular.get("lugar_nacimiento") or dip_ext.get("lugar_nacimiento"):
            form_data["lugar_nacimiento"] = titular.get("lugar_nacimiento") or dip_ext.get("lugar_nacimiento")
        if titular.get("sexo") or dip_ext.get("sexo"):
            form_data["sexo"] = titular.get("sexo") or dip_ext.get("sexo")
        if titular.get("nacionalidad") or dip_ext.get("nacionalidad"):
            form_data["nacionalidad"] = titular.get("nacionalidad") or dip_ext.get("nacionalidad")
        if documento.get("numero_dip") or titular.get("numero_dip"):
            form_data["numero_dip"] = documento.get("numero_dip") or titular.get("numero_dip")

        # === Extract from proof document ===
        proof_doc_type = self._get_proof_document_type(verification_data)
        if proof_doc_type:
            # Get funcionario fields using dynamic resolution
            for field_key in ["matricula", "nombre_completo", "cargo", "ministerio", "fecha_nombramiento", "categoria"]:
                value = self._get_funcionario_field_value(field_key, proof_doc_type, verification_data)
                if value:
                    form_data[field_key] = value

        # === Add cross-validation data (readonly) ===
        validacion = verification_data.get("validacion_cruzada", {})
        if validacion:
            form_data["nombre_dip"] = validacion.get("nombre_dip")
            form_data["nombre_documento"] = validacion.get("nombre_documento")
            form_data["similitud_nombre"] = validacion.get("similitud_nombre")
            form_data["matricula_ingresada"] = validacion.get("matricula_ingresada")
            form_data["matricula_documento"] = validacion.get("matricula_documento")
            form_data["matriculas_coinciden"] = validacion.get("matriculas_coinciden")
            form_data["validacion_automatica_posible"] = validacion.get("validacion_automatica_posible")

        # Remove None values
        form_data = {k: v for k, v in form_data.items() if v is not None}

        return form_data

    async def submit_verification(
        self,
        verificacion_id: UUID,
        user_id: UUID,
        force_submit: bool = False,
    ) -> Dict[str, Any]:
        """
        Submit verification for agent review.

        BLOCKING validations:
        - DIP document must be uploaded and validated
        - Proof document (nombramiento/carnet/contrato) must be uploaded and validated
        - Cross-validation must have been calculated

        NON-BLOCKING warnings (requires force_submit=True to proceed):
        - Name similarity < 85%
        - Matriculas don't match

        Args:
            verificacion_id: Verification ID
            user_id: User ID (for authorization)
            force_submit: If True, allows submission despite cross-validation warnings

        Returns:
            Updated verification with warnings if applicable
        """
        current = await verificacion_repository.get_by_id(verificacion_id)
        if not current:
            raise ValueError("Verificación no encontrada")

        if str(current["user_id"]) != str(user_id):
            raise ValueError("No autorizado")

        if current["status"] != "pendiente":
            raise ValueError("Verificación ya procesada")

        verification_data = current.get("verification_data", {}) or {}

        # =====================================================================
        # BLOCKING VALIDATIONS - Cannot proceed without these
        # =====================================================================

        # 1. DIP document must be uploaded and validated
        dip_data = verification_data.get("dip", {})
        if not dip_data:
            raise ValueError("Debe subir y validar el DIP antes de enviar la solicitud")

        if not dip_data.get("extraction"):
            raise ValueError("El DIP no ha sido procesado correctamente. Por favor, súbalo de nuevo.")

        # 2. Proof document must be uploaded and validated
        proof_type = None
        proof_data = None
        for t in DocumentoTipoPrueba:
            if t.value in verification_data:
                proof_type = t.value
                proof_data = verification_data[t.value]
                break

        if not proof_data:
            raise ValueError(
                "Debe subir y validar un documento de prueba (Nombramiento, Carnet o Contrato) "
                "antes de enviar la solicitud"
            )

        if not proof_data.get("extraction"):
            raise ValueError(
                f"El documento {proof_type} no ha sido procesado correctamente. "
                "Por favor, súbalo de nuevo."
            )

        # 3. Cross-validation must exist (calculated during document validation)
        validacion_cruzada = verification_data.get("validacion_cruzada", {})
        if not validacion_cruzada:
            raise ValueError(
                "Error interno: la validación cruzada no fue calculada. "
                "Por favor, vuelva a subir los documentos."
            )

        # 4. Form review must be confirmed (user reviewed and saved the data)
        form_review_confirmed = verification_data.get("form_review_confirmed", {})
        if not form_review_confirmed or not form_review_confirmed.get("data"):
            raise ValueError(
                "Debe revisar y confirmar los datos extraídos antes de enviar la solicitud. "
                "Por favor, revise el formulario y guarde los datos."
            )

        # Validate critical fields in confirmed data
        confirmed_data = form_review_confirmed.get("data", {})
        if not confirmed_data.get("numero_dip"):
            raise ValueError("El número de DIP es obligatorio. Por favor, verifique el formulario.")
        if not confirmed_data.get("matricula"):
            raise ValueError("La matrícula es obligatoria. Por favor, verifique el formulario.")

        # =====================================================================
        # NON-BLOCKING WARNINGS - Can proceed with force_submit=True
        # =====================================================================

        warnings = []

        # Check name similarity (minimum 85%)
        similitud = validacion_cruzada.get("similitud_nombre", 0)
        if similitud < 0.85:
            warnings.append({
                "code": "LOW_NAME_SIMILARITY",
                "message": f"El nombre en el DIP no coincide bien con el documento de prueba "
                           f"(similitud: {int(similitud * 100)}%). Verifique que los documentos "
                           f"corresponden a la misma persona.",
                "severity": "warning",
                "details": {
                    "nombre_dip": validacion_cruzada.get("nombre_dip"),
                    "nombre_documento": validacion_cruzada.get("nombre_documento"),
                    "similitud": similitud,
                    "minimo_requerido": 0.85,
                }
            })

        # Check matricula match
        if not validacion_cruzada.get("matriculas_coinciden", False):
            matricula_doc = validacion_cruzada.get("matricula_documento", "")
            matricula_ingresada = validacion_cruzada.get("matricula_ingresada", "")
            warnings.append({
                "code": "MATRICULA_MISMATCH",
                "message": f"La matrícula ingresada ({matricula_ingresada}) no coincide con "
                           f"la matrícula en el documento ({matricula_doc or 'no encontrada'}). "
                           f"Verifique que la matrícula es correcta.",
                "severity": "warning",
                "details": {
                    "matricula_ingresada": matricula_ingresada,
                    "matricula_documento": matricula_doc,
                }
            })

        # If there are warnings and force_submit is False, return warnings without submitting
        if warnings and not force_submit:
            return {
                "success": False,
                "submitted": False,
                "requires_confirmation": True,
                "warnings": warnings,
                "message": "Se encontraron problemas con la validación. "
                           "Revise los avisos y confirme para continuar.",
                "verification_data": verification_data,
            }

        # =====================================================================
        # PROCEED WITH SUBMISSION
        # =====================================================================

        # Add user confirmation with acknowledgment of warnings
        verification_data["confirmacion_usuario"] = {
            "datos_correctos": True,
            "confirmado_at": datetime.now(timezone.utc).isoformat(),
            "warnings_acknowledged": len(warnings) > 0,
            "warnings_count": len(warnings),
        }

        # No need to recalculate cross-validation - it was done during document validation
        # Just ensure it's up to date by NOT overwriting it

        result = await verificacion_repository.update_verification_data(verificacion_id, verification_data)

        # Add submission metadata to response
        result["submitted"] = True
        result["warnings"] = warnings
        result["auto_validable"] = validacion_cruzada.get("validacion_automatica_posible", False)

        logger.info(
            f"[VerificacionService] Submitted verification {verificacion_id}, "
            f"auto_validable={result['auto_validable']}, warnings={len(warnings)}"
        )

        return result

    # =========================================================================
    # AGENT OPERATIONS
    # =========================================================================

    async def process_verification(
        self,
        verificacion_id: UUID,
        agent_id: UUID,
        action: str,
        matricula_existe: bool = False,
        nombre_coincide: bool = False,
        dip_coincide: bool = False,
        rejection_reason: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a verification (approve or reject).

        Uses the PostgreSQL function for atomic update.
        If approved, also adds the matricula to verified_identifiers table.
        """
        result = await verificacion_repository.process(
            verificacion_id=verificacion_id,
            agent_id=agent_id,
            action=action,
            matricula_existe=matricula_existe,
            nombre_coincide=nombre_coincide,
            dip_coincide=dip_coincide,
            rejection_reason=rejection_reason,
            notes=notes,
        )

        # If approval was successful, add matricula to verified_identifiers
        if result.get("success") and action == "aprobar":
            await self._add_matricula_to_verified_identifiers(
                verificacion_id=verificacion_id,
                user_id=result.get("user_id"),
                matricula=result.get("matricula"),
                agent_id=agent_id,
            )

        return result

    async def _add_matricula_to_verified_identifiers(
        self,
        verificacion_id: UUID,
        user_id: Optional[str],
        matricula: Optional[str],
        agent_id: UUID,
    ) -> bool:
        """
        Add approved matricula to verified_identifiers table.

        This enables future auto-verification for the same matricula.

        Args:
            verificacion_id: The verification request ID
            user_id: User who was verified
            matricula: The matricula that was approved
            agent_id: Agent who approved

        Returns:
            True if successfully added
        """
        if not matricula:
            logger.warning(
                f"[VerificacionService] Cannot add to verified_identifiers: no matricula for {verificacion_id}"
            )
            return False

        try:
            from app.database.connection import db_manager
            from app.modules.verified_identifiers.services.crypto_service import get_crypto_service
            from app.modules.verified_identifiers.repositories.verified_identifiers_repository import VerifiedIdentifiersRepository

            async with db_manager.get_connection() as db:
                crypto = get_crypto_service()
                repo = VerifiedIdentifiersRepository(pool=db, crypto=crypto)

                # Upsert the matricula into verified_identifiers
                identifier_id = await repo.upsert(
                    value=matricula.upper().strip(),
                    identifier_type="matricula_funcionario",
                    source="ministerio_funcion_publica",
                    expires_at=None,  # Matriculas don't expire
                    metadata={
                        "verificacion_id": str(verificacion_id),
                        "approved_at": datetime.now(timezone.utc).isoformat(),
                        "verification_type": "agent_manual",
                    },
                    verified_by=str(agent_id),
                    user_id=user_id,
                    verification_request_id=str(verificacion_id),
                )

            logger.info(
                f"[VerificacionService] Matricula {matricula} added to verified_identifiers: "
                f"id={identifier_id}, user={user_id}, agent={agent_id}"
            )

            # Update verificacion_funcionario with the verified_identifiers reference
            await verificacion_repository.merge_verification_data(
                verificacion_id=verificacion_id,
                new_data={
                    "verified_identifiers_entry": {
                        "id": identifier_id,
                        "added_at": datetime.now(timezone.utc).isoformat(),
                        "added_by": str(agent_id),
                    }
                },
            )

            return True

        except Exception as e:
            logger.error(
                f"[VerificacionService] Failed to add matricula to verified_identifiers: "
                f"verificacion={verificacion_id}, matricula={matricula}, error={e}",
                exc_info=True
            )
            # Don't fail the approval, just log the error
            return False

    async def batch_approve(
        self,
        verificacion_ids: list,
        agent_id: UUID,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Batch approve multiple verifications.

        Only approves auto-validable verifications.
        Also adds approved matriculas to verified_identifiers.
        """
        result = await verificacion_repository.batch_approve(
            verificacion_ids=verificacion_ids,
            agent_id=agent_id,
            notes=notes,
        )

        # Add matriculas to verified_identifiers for each approved verification
        approved_ids = result.get("approved_ids", [])
        verified_count = 0

        for verified_id in approved_ids:
            try:
                # Get the verification to get matricula and user_id
                verification = await verificacion_repository.get_by_id(verified_id)
                if verification:
                    success = await self._add_matricula_to_verified_identifiers(
                        verificacion_id=verified_id,
                        user_id=str(verification.get("user_id")),
                        matricula=verification.get("matricula"),
                        agent_id=agent_id,
                    )
                    if success:
                        verified_count += 1
            except Exception as e:
                logger.error(
                    f"[VerificacionService] Batch: Failed to add matricula for {verified_id}: {e}"
                )

        result["verified_identifiers_added"] = verified_count

        return result

    # =========================================================================
    # STATUS & QUERIES
    # =========================================================================

    async def get_my_status(self, user_id: UUID) -> Dict[str, Any]:
        """Get user's verification status."""
        return await verificacion_repository.get_user_funcionario_status(user_id)

    async def get_verification(self, verificacion_id: UUID) -> Optional[Dict[str, Any]]:
        """Get verification by ID."""
        return await verificacion_repository.get_by_id(verificacion_id)

    async def list_pending(
        self,
        page: int = 1,
        page_size: int = 20,
        auto_validable_only: bool = False,
        pre_verified_only: bool = False,
    ) -> Dict[str, Any]:
        """List pending verifications for agent dashboard."""
        result = await verificacion_repository.list_pending(
            page=page,
            page_size=page_size,
            auto_validable_only=auto_validable_only,
            pre_verified_only=pre_verified_only,
        )

        # Add stats
        stats = await verificacion_repository.get_stats()
        result.update(stats)

        return result


# Singleton instance
verificacion_service = VerificacionService()
