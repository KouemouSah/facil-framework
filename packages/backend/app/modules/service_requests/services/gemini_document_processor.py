"""
Gemini Document Processor for Service Requests.

Production-ready document classification, extraction, and RISK ANALYSIS using:
1. Google Vertex AI Gemini 2.0 (primary) - Confidence threshold: 70%
2. Tesseract OCR fallback - Confidence threshold: 60%

RISK ANALYSIS CAPABILITIES:
- Document duplication detection (hash-based)
- Document type mismatch detection
- Identity consistency across documents
- Amount range validation
- Coherence and fraud detection
- Document expiry checks
- Data quality assessment

This processor is STANDALONE and only imports:
- Vertex AI SDK (Gemini)
- ocr_service from documents module (utility service)
- schema_loader from this module

Author: Claude Code
Date: 2025-12-27
"""

import asyncio
import hashlib
import json
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, date, timezone
from enum import Enum
from loguru import logger

# Vertex AI imports
try:
    from vertexai.generative_models import (
        GenerativeModel,
        GenerationConfig,
        HarmCategory,
        HarmBlockThreshold,
        Part
    )
    import vertexai
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    logger.warning("Vertex AI SDK not installed - Gemini extraction disabled")

from uuid import UUID
from app.config import settings
from app.core.ai_telemetry import traced_generate_sync
from .schema_loader import schema_loader
from .schema_validation_engine import SchemaValidationEngine

# Database pool for audit logging (fire-and-forget)
try:
    from app.database.connection import get_db_pool
    DB_POOL_AVAILABLE = True
except ImportError:
    DB_POOL_AVAILABLE = False
    logger.warning("Database pool not available - Gemini audit logging disabled")

# Tesseract OCR service REMOVED - Gemini handles ALL documents exclusively.
# If Gemini fails, error is propagated to user for retry.
OCR_SERVICE_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS & ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

# Confidence thresholds
GEMINI_CONFIDENCE_THRESHOLD = 0.70  # 70% - Accept Gemini extraction
# TESSERACT_CONFIDENCE_THRESHOLD removed - Tesseract no longer used

# Risk thresholds
RISK_SCORE_LOW = 30
RISK_SCORE_MEDIUM = 60
RISK_SCORE_HIGH = 80

# Document category mapping for audit logs and vault classification
DOCUMENT_CATEGORY_MAP: Dict[str, str] = {
    # Identity
    "dip": "identity", "dip_gq": "identity",
    "pasaporte": "identity", "pasaporte_gq": "identity",
    "pasaporte_antiguo": "identity", "pasaporte_danado": "identity",
    "pasaporte_entrada": "identity", "pasaporte_international": "identity",
    "permiso_residencia": "identity", "certificado_nacimiento": "identity",
    "certificacion_nacimiento": "identity", "declaracion_nacimiento": "identity",
    "carnet_funcionario": "identity", "nombramiento": "identity",
    "cedula_personal": "identity", "carnet_empadronamiento": "identity",
    "acte_naissance": "identity", "nie": "identity",
    # Vehicle
    "itv": "vehicle", "itv_antigua": "vehicle", "tarjeta_itv": "vehicle",
    "cuve": "vehicle", "cuve_antigua": "vehicle",
    "permiso_circulacion": "vehicle", "certificado_registro_vue": "vehicle",
    "certificado_reconocimiento_vehiculo": "vehicle",
    # Legal
    "contrato": "legal", "contrato_compraventa": "legal",
    "contrato_onrc": "legal", "escritura_constitucion": "legal",
    "poder_notarial": "legal", "autorizacion_parental": "legal",
    "autorizacion_gubernativa": "legal", "declaracion_jurada": "legal",
    # Financial
    "certificado_nif": "financial", "solvencia_tributaria": "financial",
    "nota_ingreso": "financial", "nota_ingreso_dgi": "financial",
    "nota_ingreso_residencia": "financial", "atestacion_bancaria": "financial",
    "extracto_bancario": "financial", "nif_autorizacion": "financial",
    "factura": "financial",
    # Business
    "certificado_padron": "business", "licencia_comercio": "business",
    "licencia_comercio_municipal": "business",
    "certificado_actualizacion_empresarial": "business",
    "certificado_conciso_mercantil": "business",
    "certificado_registro_comercio": "business",
    "certificado_registro_empresarial": "business",
    "certificado_registro_onrc": "business",
    "nif_empresa": "business",
    # Administrative
    "instancia_solicitud": "administrative", "oficio_destino": "administrative",
    "toma_posesion": "administrative", "certificado_administrativo": "administrative",
    "permiso_extraordinario": "administrative", "promocion_administrativa": "administrative",
    "certificado_servicios": "administrative", "certificado_reforma": "administrative",
    "certificado_autenticidad": "administrative", "certificado_actual": "administrative",
    "solicitud": "administrative",
    # Employment
    "contrato_trabajo": "employment", "contrato_funcionario": "employment",
    "permiso_trabajo": "employment", "nomina_reciente": "employment",
    "autorizacion_reclutamiento": "employment",
    # Driving
    "certificado_conducir": "vehicle", "licencia_conducir": "vehicle",
    "permiso_conducir": "vehicle", "permiso_actual": "vehicle",
    "certificado_medico_conducir": "medical",
    # Police/Legal
    "denuncia_policial": "legal", "denuncia": "legal",
    "antecedentes_penales": "legal",
    "certificado_buena_conducta": "legal",
    "extrait_casier_judiciaire_international": "legal",
    "certificado_conducta_policia": "legal",
    "certificado_conducta_empresa": "legal",
    # Medical
    "certificado_medico": "medical",
    # Education
    "titulo_academico": "education", "titulos_academicos": "education",
    "matricula_estudios": "education", "calendario_estudios": "education",
    "homologacion": "education",
    # Photo
    "photo_carnet": "photo", "foto_carnet": "photo",
    "fotografias": "photo", "foto_biometrica": "photo",
    # Travel/Visa
    "visado": "identity", "visado_entrada": "identity",
    "sello_entrada": "identity", "permanencia_previa": "identity",
    "visa_control_financiero": "identity",
    # Certificate defaults
    "certificado_defuncion": "administrative",
    "certificado_perdida": "administrative",
}


class RiskLevel(str, Enum):
    """Risk level enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskFactorCode(str, Enum):
    """Standardized risk factor codes"""
    # Document Validity
    DOC_EXPIRED = "DOC_EXPIRED"
    DOC_NEAR_EXPIRY = "DOC_NEAR_EXPIRY"
    DOC_NOT_YET_VALID = "DOC_NOT_YET_VALID"

    # Document Quality
    LOW_IMAGE_QUALITY = "LOW_IMAGE_QUALITY"
    UNREADABLE_FIELDS = "UNREADABLE_FIELDS"
    INCOMPLETE_DOCUMENT = "INCOMPLETE_DOCUMENT"

    # Document Type
    DOC_TYPE_MISMATCH = "DOC_TYPE_MISMATCH"
    UNEXPECTED_FORMAT = "UNEXPECTED_FORMAT"

    # Duplication
    DUPLICATE_DOCUMENT = "DUPLICATE_DOCUMENT"
    SIMILAR_DOCUMENT = "SIMILAR_DOCUMENT"
    REUSED_ACROSS_REQUESTS = "REUSED_ACROSS_REQUESTS"

    # Identity Consistency
    NAME_MISMATCH = "NAME_MISMATCH"
    ID_NUMBER_MISMATCH = "ID_NUMBER_MISMATCH"
    BIRTHDATE_MISMATCH = "BIRTHDATE_MISMATCH"
    NATIONALITY_MISMATCH = "NATIONALITY_MISMATCH"
    PHOTO_MISMATCH = "PHOTO_MISMATCH"

    # Data Validation
    INVALID_DATE_FORMAT = "INVALID_DATE_FORMAT"
    FUTURE_BIRTHDATE = "FUTURE_BIRTHDATE"
    IMPOSSIBLE_AGE = "IMPOSSIBLE_AGE"
    INVALID_ID_FORMAT = "INVALID_ID_FORMAT"

    # Amount Validation
    AMOUNT_OUT_OF_RANGE = "AMOUNT_OUT_OF_RANGE"
    SUSPICIOUS_AMOUNT = "SUSPICIOUS_AMOUNT"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"

    # Fraud Indicators
    DIGITAL_MANIPULATION = "DIGITAL_MANIPULATION"
    INCONSISTENT_FONTS = "INCONSISTENT_FONTS"
    ALTERED_DATES = "ALTERED_DATES"
    SUSPICIOUS_PATTERNS = "SUSPICIOUS_PATTERNS"
    KNOWN_FRAUD_TEMPLATE = "KNOWN_FRAUD_TEMPLATE"

    # Coherence
    LOGICAL_INCONSISTENCY = "LOGICAL_INCONSISTENCY"
    CROSS_FIELD_MISMATCH = "CROSS_FIELD_MISMATCH"
    TEMPORAL_ANOMALY = "TEMPORAL_ANOMALY"

    # Missing Data
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    MISSING_SIGNATURE = "MISSING_SIGNATURE"
    MISSING_STAMP = "MISSING_STAMP"

    # Parental Authorization (for minors passport)
    AUTHORIZATION_EXPIRED = "AUTHORIZATION_EXPIRED"
    AUTHORIZATION_MISSING_SIGNATURE = "AUTHORIZATION_MISSING_SIGNATURE"
    AUTHORIZATION_PARENT_ID_MISMATCH = "AUTHORIZATION_PARENT_ID_MISMATCH"
    AUTHORIZATION_DUAL_REQUIRES_BOTH = "AUTHORIZATION_DUAL_REQUIRES_BOTH"
    AUTHORIZATION_MINOR_NAME_MISMATCH = "AUTHORIZATION_MINOR_NAME_MISMATCH"

    # License/Permit Age Requirements (for Conducir workflow)
    MIN_AGE_FOR_LICENSE = "MIN_AGE_FOR_LICENSE"
    UNDERAGE_FOR_CLASS = "UNDERAGE_FOR_CLASS"

    # Schema Validation (validations[] from JSON schemas)
    SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"


# Risk factor severity mapping
RISK_FACTOR_SEVERITY: Dict[RiskFactorCode, str] = {
    # Critical (immediate rejection)
    RiskFactorCode.DOC_TYPE_MISMATCH: "critical",
    RiskFactorCode.DUPLICATE_DOCUMENT: "critical",
    RiskFactorCode.DIGITAL_MANIPULATION: "critical",
    RiskFactorCode.KNOWN_FRAUD_TEMPLATE: "critical",

    # High (requires manual review)
    RiskFactorCode.DOC_EXPIRED: "high",
    RiskFactorCode.NAME_MISMATCH: "high",
    RiskFactorCode.ID_NUMBER_MISMATCH: "high",
    RiskFactorCode.ALTERED_DATES: "high",
    RiskFactorCode.SUSPICIOUS_PATTERNS: "high",
    RiskFactorCode.FUTURE_BIRTHDATE: "high",
    RiskFactorCode.IMPOSSIBLE_AGE: "high",
    RiskFactorCode.REUSED_ACROSS_REQUESTS: "high",

    # Medium (warning)
    RiskFactorCode.DOC_NEAR_EXPIRY: "medium",
    RiskFactorCode.LOW_IMAGE_QUALITY: "medium",
    RiskFactorCode.UNREADABLE_FIELDS: "medium",
    RiskFactorCode.BIRTHDATE_MISMATCH: "medium",
    RiskFactorCode.AMOUNT_OUT_OF_RANGE: "medium",
    RiskFactorCode.SUSPICIOUS_AMOUNT: "medium",
    RiskFactorCode.INCONSISTENT_FONTS: "medium",
    RiskFactorCode.LOGICAL_INCONSISTENCY: "medium",
    RiskFactorCode.CROSS_FIELD_MISMATCH: "medium",
    RiskFactorCode.SIMILAR_DOCUMENT: "medium",

    # Low (informational)
    RiskFactorCode.DOC_NOT_YET_VALID: "low",
    RiskFactorCode.INCOMPLETE_DOCUMENT: "low",
    RiskFactorCode.UNEXPECTED_FORMAT: "low",
    RiskFactorCode.NATIONALITY_MISMATCH: "low",
    RiskFactorCode.INVALID_DATE_FORMAT: "low",
    RiskFactorCode.CURRENCY_MISMATCH: "low",
    RiskFactorCode.TEMPORAL_ANOMALY: "low",
    RiskFactorCode.MISSING_REQUIRED_FIELD: "low",
    RiskFactorCode.MISSING_SIGNATURE: "low",
    RiskFactorCode.MISSING_STAMP: "low",
    RiskFactorCode.INVALID_ID_FORMAT: "low",
    RiskFactorCode.PHOTO_MISMATCH: "low",

    # Parental Authorization
    RiskFactorCode.AUTHORIZATION_EXPIRED: "high",
    RiskFactorCode.AUTHORIZATION_MISSING_SIGNATURE: "high",
    RiskFactorCode.AUTHORIZATION_PARENT_ID_MISMATCH: "critical",  # BLOCKING
    RiskFactorCode.AUTHORIZATION_DUAL_REQUIRES_BOTH: "high",
    RiskFactorCode.AUTHORIZATION_MINOR_NAME_MISMATCH: "medium",  # Warning only

    # License/Permit Age Requirements (Conducir)
    RiskFactorCode.MIN_AGE_FOR_LICENSE: "high",  # BLOCKING - requires manual override
    RiskFactorCode.UNDERAGE_FOR_CLASS: "critical",  # BLOCKING - cannot proceed
}

# Document type mapping (expected document code -> acceptable detected types)
DOCUMENT_TYPE_MAPPING: Dict[str, List[str]] = {
    "dip_gq": ["dni", "dip", "documento_identidad", "carnet_identidad", "cedula"],
    "pasaporte_gq": ["pasaporte", "passport"],
    "pasaporte_extranjero": ["pasaporte", "passport", "travel_document"],
    "certificado_nacimiento": ["acta_nacimiento", "partida_nacimiento", "certificado_nacimiento", "birth_certificate"],
    "certificado_matrimonio": ["acta_matrimonio", "certificado_matrimonio", "marriage_certificate"],
    "certificado_medico": ["certificado_medico", "medical_certificate", "informe_medico"],
    "justificante_pago": ["recibo", "comprobante_pago", "justificante", "receipt"],
    "foto_carnet": ["foto", "fotografia", "photo"],
    "certificado_residencia": ["certificado_residencia", "residence_certificate"],
    "contrato_trabajo": ["contrato", "contract", "contrato_trabajo"],
    "declaracion_renta": ["declaracion", "tax_declaration", "irpf"],
    "extracto_bancario": ["extracto", "bank_statement", "estado_cuenta"],
    # Parent/Guardian documents for minors
    "autorizacion_parental": ["autorizacion", "autorizacion_parental", "consentimiento", "permiso_parental", "authorization"],
    "documento_representante_1": ["dni", "dip", "pasaporte", "passport", "nie", "permiso_residencia"],
    "documento_representante_2": ["dni", "dip", "pasaporte", "passport", "nie", "permiso_residencia"],
}

# Amount ranges by document/service type (in XAF)
AMOUNT_RANGES: Dict[str, Tuple[float, float]] = {
    "justificante_pago": (1000, 50_000_000),  # 1K - 50M XAF
    "extracto_bancario": (0, 1_000_000_000),  # 0 - 1B XAF
    "declaracion_renta": (0, 500_000_000),  # 0 - 500M XAF
    "default": (0, 100_000_000),  # Default range
}


# ═══════════════════════════════════════════════════════════════════════════════
# IDENTITY VERIFICATION CONFIGURATION (Per-Workflow)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class IdentityFieldConfig:
    """Configuration for an identity field to compare."""
    field_name: str  # Field name in extraction (e.g., "apellidos")
    field_paths: List[str]  # Possible paths to find the field (e.g., ["titular.apellidos", "apellidos"])
    is_blocking: bool = True  # If True, mismatch blocks progress
    label_es: str = ""  # Display label in Spanish
    label_fr: str = ""  # Display label in French
    label_en: str = ""  # Display label in English


@dataclass
class WorkflowIdentityConfig:
    """
    Identity verification configuration for a workflow.

    Defines which documents to compare and which fields must match.
    """
    reference_document: str  # Main document to compare against (e.g., "dip")
    compare_documents: List[str]  # Documents to compare with reference (e.g., ["pasaporte", "pasaporte_danado"])
    critical_fields: List[IdentityFieldConfig]  # Fields that must match
    is_blocking: bool = True  # If True, any critical mismatch blocks progress
    workflow_patterns: List[str] = None  # Workflow patterns this config applies to (e.g., ["PASAPORTE_*"])


# Default identity fields for all workflows
# STRATEGY: Document numbers and dates are BLOCKING (reliable OCR)
#           Names are WARNING only (prone to OCR errors like mixing with adjacent fields)
DEFAULT_IDENTITY_FIELDS = [
    # ══════════════════════════════════════════════════════════════════════════
    # BLOCKING FIELDS (reliable extraction, must match exactly)
    # ══════════════════════════════════════════════════════════════════════════
    IdentityFieldConfig(
        field_name="numero_dip",
        # DIP: documento.numero_dip | Passport: titular.numero_identidad_nacional (Personal No.)
        field_paths=["documento.numero_dip", "titular.numero_identidad_nacional", "numero_identidad_nacional", "titular.numero_dip", "numero_dip"],
        is_blocking=True,
        label_es="N° DIP",
        label_fr="N° DIP",
        label_en="DIP Number"
    ),
    IdentityFieldConfig(
        field_name="fecha_nacimiento",
        field_paths=["titular.fecha_nacimiento", "fecha_nacimiento"],
        is_blocking=True,
        label_es="Fecha de nacimiento",
        label_fr="Date de naissance",
        label_en="Date of birth"
    ),
    # ══════════════════════════════════════════════════════════════════════════
    # WARNING FIELDS (prone to OCR errors, informational only)
    # ══════════════════════════════════════════════════════════════════════════
    IdentityFieldConfig(
        field_name="apellidos",
        field_paths=["titular.apellidos", "apellidos"],
        is_blocking=False,  # WARNING only - OCR can mix with adjacent fields
        label_es="Apellidos",
        label_fr="Nom de famille",
        label_en="Surname"
    ),
    IdentityFieldConfig(
        field_name="nombres",
        field_paths=["titular.nombres", "nombres"],
        is_blocking=False,  # WARNING only - OCR can mix with lugar_emision on DIP
        label_es="Nombres",
        label_fr="Prénoms",
        label_en="First names"
    ),
    IdentityFieldConfig(
        field_name="nacionalidad",
        field_paths=["titular.nacionalidad", "nacionalidad"],
        is_blocking=False,
        label_es="Nacionalidad",
        label_fr="Nationalité",
        label_en="Nationality"
    ),
]

# Identity fields for minors passport (no DIP, uses certificado_nacimiento)
MINOR_IDENTITY_FIELDS = [
    # ══════════════════════════════════════════════════════════════════════════
    # BLOCKING FIELDS - date of birth from birth certificate
    # ══════════════════════════════════════════════════════════════════════════
    IdentityFieldConfig(
        field_name="fecha_nacimiento",
        field_paths=["menor.fecha_nacimiento", "titular.fecha_nacimiento", "fecha_nacimiento"],
        is_blocking=True,
        label_es="Fecha de nacimiento",
        label_fr="Date de naissance",
        label_en="Date of birth"
    ),
    # ══════════════════════════════════════════════════════════════════════════
    # WARNING FIELDS - names (prone to OCR errors)
    # ══════════════════════════════════════════════════════════════════════════
    IdentityFieldConfig(
        field_name="nombre_completo",
        field_paths=["menor.nombre_completo", "titular.nombre_completo", "nombre_completo"],
        is_blocking=False,  # WARNING only
        label_es="Nombre completo",
        label_fr="Nom complet",
        label_en="Full name"
    ),
    IdentityFieldConfig(
        field_name="apellidos",
        field_paths=["menor.apellidos", "titular.apellidos", "apellidos"],
        is_blocking=False,  # WARNING only
        label_es="Apellidos",
        label_fr="Nom de famille",
        label_en="Surname"
    ),
    IdentityFieldConfig(
        field_name="nombres",
        field_paths=["menor.nombres", "titular.nombres", "nombres"],
        is_blocking=False,  # WARNING only
        label_es="Nombres",
        label_fr="Prénoms",
        label_en="First names"
    ),
]

# Per-workflow identity verification configurations
WORKFLOW_IDENTITY_CONFIGS: Dict[str, WorkflowIdentityConfig] = {
    # Passport workflows for MINORS - certificado_nacimiento is reference
    # Special case: uses parental authorization cross-validation instead of DIP
    "PASAPORTE_MENOR": WorkflowIdentityConfig(
        reference_document="certificado_nacimiento",
        compare_documents=["pasaporte_antiguo", "pasaporte_danado", "autorizacion_parental"],
        critical_fields=MINOR_IDENTITY_FIELDS,
        is_blocking=True,
        workflow_patterns=["PASAPORTE_MENOR_*"]
    ),
    # Passport workflows - DIP is reference, compare with old passport
    "PASAPORTE": WorkflowIdentityConfig(
        reference_document="dip",
        compare_documents=["pasaporte", "pasaporte_antiguo", "pasaporte_danado"],
        critical_fields=DEFAULT_IDENTITY_FIELDS,
        is_blocking=True,
        workflow_patterns=["PASAPORTE_*", "PASAPORTE_NUEVO", "PASAPORTE_RENOVACION", "PASAPORTE_DETERIORO"]
    ),
    # Driver's license workflows
    "CONDUCIR": WorkflowIdentityConfig(
        reference_document="dip",
        compare_documents=["licencia_conducir", "permiso_conducir"],
        critical_fields=DEFAULT_IDENTITY_FIELDS,
        is_blocking=True,
        workflow_patterns=["CONDUCIR_*", "PERMISO_CONDUCIR_*"]
    ),
    # Residence permit workflows
    "RESIDENCIA": WorkflowIdentityConfig(
        reference_document="pasaporte",
        compare_documents=["certificado_nacimiento", "contrato_trabajo"],
        critical_fields=DEFAULT_IDENTITY_FIELDS,
        is_blocking=True,
        workflow_patterns=["RESIDENCIA_*", "PERMISO_RESIDENCIA_*"]
    ),
    # Default fallback for any workflow
    "DEFAULT": WorkflowIdentityConfig(
        reference_document="dip",
        compare_documents=[],  # Compare with any other identity document
        critical_fields=DEFAULT_IDENTITY_FIELDS,
        is_blocking=True,
        workflow_patterns=["*"]
    ),
}


def get_identity_config_for_workflow(workflow_code: Optional[str] = None) -> WorkflowIdentityConfig:
    """
    Get identity verification configuration for a workflow.

    Args:
        workflow_code: Workflow code (e.g., "PASAPORTE_NUEVO", "CONDUCIR_RENOVACION")

    Returns:
        Matching WorkflowIdentityConfig or default config
    """
    if not workflow_code:
        return WORKFLOW_IDENTITY_CONFIGS["DEFAULT"]

    workflow_upper = workflow_code.upper()

    # Check for exact match first
    if workflow_upper in WORKFLOW_IDENTITY_CONFIGS:
        return WORKFLOW_IDENTITY_CONFIGS[workflow_upper]

    # Check for pattern match (e.g., "PASAPORTE_NUEVO" matches "PASAPORTE")
    for config_key, config in WORKFLOW_IDENTITY_CONFIGS.items():
        if config_key == "DEFAULT":
            continue
        if workflow_upper.startswith(config_key):
            return config
        if config.workflow_patterns:
            for pattern in config.workflow_patterns:
                if pattern.endswith("*"):
                    prefix = pattern[:-1]
                    if workflow_upper.startswith(prefix):
                        return config
                elif pattern == workflow_upper:
                    return config

    return WORKFLOW_IDENTITY_CONFIGS["DEFAULT"]


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# NAME MATCHING UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def normalize_name(name: str) -> str:
    """Normalize a name for comparison: uppercase, remove accents, remove prefixes."""
    if not name:
        return ""
    name = name.upper()
    # Remove accents (é→E, ñ→N, etc.)
    name = "".join(
        c for c in unicodedata.normalize("NFKD", name)
        if not unicodedata.combining(c)
    )
    name = " ".join(name.split())
    # Remove common Spanish name prefixes
    for prefix in ("DE LOS ", "DE LAS ", "DE LA ", "DEL ", "DE "):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.strip()


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


LEVENSHTEIN_THRESHOLD = 0.85  # 1-2 char errors tolerated on typical GQ names


# ═══════════════════════════════════════════════════════════════════════════════
# RISK ANALYZER
# ═══════════════════════════════════════════════════════════════════════════════

class RiskAnalyzer:
    """
    Comprehensive risk analysis for documents.

    Analyzes:
    - Document validity (expiry, format)
    - Identity consistency across documents
    - Data coherence and logical checks
    - Fraud indicators
    - Amount validation
    - Duplication detection
    """

    def analyze(
        self,
        extraction: Dict[str, Any],
        document_code: str,
        detected_type: str,
        content: bytes,
        request_id: str,
        user_id: str,
        existing_documents: Optional[Dict[str, Dict[str, Any]]] = None,
        form_data: Optional[Dict[str, Any]] = None,
        gemini_risk_hints: Optional[Dict[str, Any]] = None,
        workflow_code: Optional[str] = None,
        hash_matches: Optional[List[Dict[str, Any]]] = None,
        document_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive risk analysis.

        Args:
            extraction: Extracted document data
            document_code: Expected document type code
            detected_type: AI-detected document type
            content: Raw document bytes
            request_id: Service request ID
            user_id: User ID
            existing_documents: Previously uploaded documents for this request
            form_data: User-submitted form data
            gemini_risk_hints: Risk hints from Gemini analysis
            workflow_code: Workflow code for identity verification config (e.g., "PASAPORTE_NUEVO")
            hash_matches: Pre-fetched DB matches for document hash (from process())
            document_constraints: Workflow-specific constraints from DocumentRequirement.config
                (e.g., {"required_tipo_certificado": "APTITUD", "required_resultado": ["SANO", "APTO"]})

        Returns:
            Complete risk analysis result including identity_mismatches
        """
        # Defense layer 3: coerce extraction at analyze() entry so ALL
        # downstream helpers (_check_data_validation, _check_coherence, etc.)
        # can safely call extraction.get() / extraction[key] / 'key' in extraction.
        if not isinstance(extraction, dict):
            logger.warning(
                f"analyze() received non-dict extraction "
                f"({type(extraction).__name__} for {document_code}), "
                f"coercing to empty dict"
            )
            extraction = {}

        risk_factors: List[Dict[str, Any]] = []

        # 1. Document Type Mismatch Detection
        type_risk = self._check_document_type_mismatch(document_code, detected_type)
        if type_risk:
            risk_factors.append(type_risk)

        # 2. Duplication Detection (using pre-fetched DB results)
        dup_risk = self._check_duplication(
            request_id, document_code, user_id, hash_matches
        )
        if dup_risk:
            risk_factors.append(dup_risk)

        # 3. Document Validity (Expiry)
        validity_risks = self._check_document_validity(extraction)
        risk_factors.extend(validity_risks)

        # 4. Identity Consistency with workflow-specific config
        # Returns both risk_factors AND structured identity_mismatches
        identity_result = self._check_identity_consistency_v2(
            extraction=extraction,
            document_code=document_code,
            existing_documents=existing_documents or {},
            workflow_code=workflow_code
        )
        risk_factors.extend(identity_result["risk_factors"])
        identity_mismatches = identity_result["identity_mismatches"]
        has_blocking_mismatches = identity_result["has_blocking_mismatches"]

        # 5. Form Data Consistency (always check - compares with user form data if available)
        form_risks = self._check_form_consistency(extraction, form_data or {})
        risk_factors.extend(form_risks)

        # 6. Data Validation (with workflow context for conditional rules)
        data_risks = self._check_data_validation(extraction, document_code, workflow_code)
        risk_factors.extend(data_risks)

        # 7. Amount Validation
        amount_risks = self._check_amount_validation(extraction, document_code)
        risk_factors.extend(amount_risks)

        # 8. Coherence Checks
        coherence_risks = self._check_coherence(extraction)
        risk_factors.extend(coherence_risks)

        # 9. Gemini-detected fraud indicators (always process, even if empty)
        # This ensures we check for low authenticity scores, altered dates, etc.
        fraud_risks = self._process_gemini_risk_hints(gemini_risk_hints or {})
        risk_factors.extend(fraud_risks)

        # 10. Parental Authorization Cross-Validation (for minor passport workflows)
        # Only runs when autorizacion_parental document is present
        parental_auth_validation = None
        if existing_documents and "autorizacion_parental" in existing_documents:
            parental_auth_validation = self._check_parental_authorization_cross_validation(
                existing_documents=existing_documents,
                form_data=form_data
            )
            # Add blocking errors as critical risk factors
            for error in parental_auth_validation.get("blocking_errors", []):
                risk_factors.append({
                    "code": error.get("code", RiskFactorCode.AUTHORIZATION_PARENT_ID_MISMATCH.value),
                    "severity": "critical",
                    "message": error.get("message_es", "Error de validación cruzada"),
                    "detail": error,
                    "action": "block"
                })
            # Update blocking flag if parental auth validation failed
            if not parental_auth_validation.get("cross_validation_passed", True):
                has_blocking_mismatches = True
                logger.warning("Parental authorization cross-validation FAILED - blocking submission")

        # 11. Schema-defined validations (non-blocking)
        try:
            schema_engine = SchemaValidationEngine()
            schema_results = schema_engine.validate(extraction, document_code)
            for result in schema_results:
                if not result.passed:
                    risk_factors.append(result.to_risk_factor())
        except Exception as e:
            logger.warning(f"Schema validation check failed: {e}")

        # 12. Workflow-specific document constraints (from DocumentRequirement.config)
        if document_constraints:
            constraint_risks = self._check_document_constraints(extraction, document_constraints)
            risk_factors.extend(constraint_risks)

        # Calculate overall risk score and level
        risk_score, risk_level = self._calculate_risk_score(risk_factors)

        # Generate recommendations
        recommendations = self._generate_recommendations(risk_factors, risk_level)

        # Determine if document should be rejected or needs review
        requires_rejection = any(
            rf["severity"] == "critical" for rf in risk_factors
        )
        requires_review = risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] or any(
            rf["severity"] == "high" for rf in risk_factors
        )

        return {
            "risk_level": risk_level.value,
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "recommendations": recommendations,
            "requires_rejection": requires_rejection,
            "requires_review": requires_review,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "factors_count": {
                "critical": sum(1 for rf in risk_factors if rf["severity"] == "critical"),
                "high": sum(1 for rf in risk_factors if rf["severity"] == "high"),
                "medium": sum(1 for rf in risk_factors if rf["severity"] == "medium"),
                "low": sum(1 for rf in risk_factors if rf["severity"] == "low")
            },
            # New: Structured identity mismatch data for frontend blocking
            "identity_mismatches": identity_mismatches,
            "has_blocking_mismatches": has_blocking_mismatches,
            # New: Parental authorization cross-validation result (for minor passport)
            # Should be stored in form_data.parental_authorization_validation
            "parental_authorization_validation": parental_auth_validation
        }

    def _check_document_type_mismatch(
        self,
        expected_code: str,
        detected_type: str
    ) -> Optional[Dict[str, Any]]:
        """Check if detected document type matches expected type"""
        if not detected_type:
            return None

        detected_lower = detected_type.lower().strip()
        expected_lower = expected_code.lower().strip()

        # Get acceptable types for expected document
        acceptable_types = DOCUMENT_TYPE_MAPPING.get(expected_lower, [expected_lower])

        # Check if detected type is acceptable
        is_match = any(
            acc_type in detected_lower or detected_lower in acc_type
            for acc_type in acceptable_types
        )

        if not is_match:
            return {
                "code": RiskFactorCode.DOC_TYPE_MISMATCH.value,
                "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.DOC_TYPE_MISMATCH],
                "message": f"Document type mismatch: expected '{expected_code}', detected '{detected_type}'",
                "detail": {
                    "expected": expected_code,
                    "detected": detected_type,
                    "acceptable_types": acceptable_types
                },
                "action": "reject"
            }

        return None

    def _check_duplication(
        self,
        request_id: str,
        document_code: str,
        user_id: str,
        hash_matches: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """Check for document duplication using pre-fetched PostgreSQL results.

        hash_matches contains documents from OTHER requests that have the same
        SHA-256 hash (pre-fetched in process() via document_repository.find_by_hash).
        """
        if not hash_matches:
            return None

        # First match = oldest duplicate
        first_match = hash_matches[0]
        match_user_id = str(first_match.get("user_id", ""))
        match_request_id = str(first_match.get("service_request_id", ""))
        match_date = first_match.get("created_at")
        match_date_str = (
            match_date.isoformat() if hasattr(match_date, "isoformat")
            else str(match_date or "")
        )

        if match_user_id == user_id:
            # Same user, different request - document reuse
            return {
                "code": RiskFactorCode.REUSED_ACROSS_REQUESTS.value,
                "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.REUSED_ACROSS_REQUESTS],
                "message": "Same document was used in a different service request",
                "detail": {
                    "original_request": match_request_id,
                    "original_date": match_date_str,
                    "original_document_code": first_match.get("document_code", ""),
                    "match_count": len(hash_matches)
                },
                "action": "review"
            }
        else:
            # Different user - potential fraud
            return {
                "code": RiskFactorCode.DUPLICATE_DOCUMENT.value,
                "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.DUPLICATE_DOCUMENT],
                "message": "This document was previously submitted by another user",
                "detail": {
                    "original_request": match_request_id,
                    "original_date": match_date_str,
                    "match_count": len(hash_matches)
                },
                "action": "reject"
            }


    def _check_document_validity(
        self,
        extraction: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check document validity dates"""
        risks = []
        today = date.today()

        # Check expiry date
        expiry_fields = ["fecha_caducidad", "fecha_expiracion", "expiry_date", "valid_until", "vigencia_hasta"]
        for field in expiry_fields:
            if field in extraction and extraction[field]:
                try:
                    expiry = self._parse_date(extraction[field])
                    if expiry:
                        if expiry < today:
                            risks.append({
                                "code": RiskFactorCode.DOC_EXPIRED.value,
                                "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.DOC_EXPIRED],
                                "message": f"Document expired on {expiry.isoformat()}",
                                "detail": {"expiry_date": expiry.isoformat(), "days_expired": (today - expiry).days},
                                "action": "reject"
                            })
                        elif (expiry - today).days < 90:
                            risks.append({
                                "code": RiskFactorCode.DOC_NEAR_EXPIRY.value,
                                "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.DOC_NEAR_EXPIRY],
                                "message": f"Document expires soon: {expiry.isoformat()}",
                                "detail": {"expiry_date": expiry.isoformat(), "days_remaining": (expiry - today).days},
                                "action": "warn"
                            })
                except Exception as e:
                    logger.warning(f"Error parsing expiry date: {e}")

        # Check issue date (not in future)
        issue_fields = ["fecha_expedicion", "fecha_emision", "issue_date", "date_issued"]
        for field in issue_fields:
            if field in extraction and extraction[field]:
                try:
                    issue_date = self._parse_date(extraction[field])
                    if issue_date and issue_date > today:
                        risks.append({
                            "code": RiskFactorCode.DOC_NOT_YET_VALID.value,
                            "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.DOC_NOT_YET_VALID],
                            "message": f"Document has future issue date: {issue_date.isoformat()}",
                            "detail": {"issue_date": issue_date.isoformat()},
                            "action": "review"
                        })
                except Exception as e:
                    logger.warning(f"Error parsing issue date: {e}")

        return risks

    def _check_identity_consistency(
        self,
        extraction: Dict[str, Any],
        existing_documents: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Check identity consistency across documents (legacy method)"""
        # Use v2 method for backwards compatibility
        result = self._check_identity_consistency_v2(extraction, "", existing_documents, None)
        return result["risk_factors"]

    def _check_identity_consistency_v2(
        self,
        extraction: Dict[str, Any],
        document_code: str,
        existing_documents: Dict[str, Dict[str, Any]],
        workflow_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check identity consistency across documents with workflow-specific configuration.

        Returns structured data for frontend blocking:
        - risk_factors: List of risk factors (same as before)
        - identity_mismatches: List of detailed mismatch info with sources
        - has_blocking_mismatches: Boolean flag indicating if critical mismatches were found

        Args:
            extraction: Current document extraction data
            document_code: Current document code (e.g., "dip", "pasaporte")
            existing_documents: Previously uploaded documents for this request
            workflow_code: Workflow code for identity verification config

        Returns:
            Dict with risk_factors, identity_mismatches, and has_blocking_mismatches
        """
        risks: List[Dict[str, Any]] = []
        identity_mismatches: List[Dict[str, Any]] = []
        has_blocking_mismatches = False

        # Get workflow-specific identity config
        identity_config = get_identity_config_for_workflow(workflow_code)

        # Helper function to extract value from nested dict using dot notation
        def get_nested_value(data: Dict[str, Any], paths: List[str]) -> Optional[str]:
            for path in paths:
                parts = path.split(".")
                current = data
                for part in parts:
                    if isinstance(current, dict):
                        current = current.get(part)
                    else:
                        current = None
                        break
                if current is not None and current != "":
                    return str(current).strip().upper()
            return None

        # Helper function for fuzzy name matching
        # Handles cases where extraction adds extra data (e.g., city in name field)
        def names_match_fuzzy(value1: str, value2: str, field_name: str) -> bool:
            """
            Fuzzy matching for name fields.
            Returns True if names are considered equivalent despite minor differences.

            Rules:
            1. Exact match → True
            2. One value contains the other → True (handles extraction adding extra data)
            3. All words of shorter value are in longer value → True
            4. Normalized match → True (accents, prefixes DE/DEL removed)
            5. Levenshtein similarity >= 0.85 → True (OCR typos)
            6. Otherwise → False
            """
            if value1 == value2:
                return True

            # Only apply fuzzy matching to name-related fields
            name_fields = ["nombres", "apellidos", "nombre", "apellido", "name", "surname"]
            if field_name.lower() not in name_fields:
                return False

            # Normalize: remove extra spaces, convert to uppercase
            v1 = " ".join(value1.split()).upper()
            v2 = " ".join(value2.split()).upper()

            # Step 2: Check if one contains the other
            if v1 in v2 or v2 in v1:
                logger.info(f"Fuzzy name match: '{v1}' ≈ '{v2}' (containment)")
                return True

            # Step 3: Check if all words of shorter value are in longer value
            words1 = set(v1.split())
            words2 = set(v2.split())
            shorter = words1 if len(words1) <= len(words2) else words2
            longer = words2 if len(words1) <= len(words2) else words1

            if shorter.issubset(longer):
                logger.info(f"Fuzzy name match: '{v1}' ≈ '{v2}' (word subset)")
                return True

            # Step 4: Normalize (remove accents + prefixes) and re-check
            n1 = normalize_name(value1)
            n2 = normalize_name(value2)
            if n1 == n2:
                logger.info(f"Fuzzy name match: '{v1}' ≈ '{v2}' (normalized exact)")
                return True

            # Step 5: Levenshtein similarity for OCR typos
            if n1 and n2:
                max_len = max(len(n1), len(n2))
                dist = levenshtein_distance(n1, n2)
                similarity = 1 - (dist / max_len)
                if similarity >= LEVENSHTEIN_THRESHOLD:
                    logger.info(
                        f"Fuzzy name match: '{n1}' ≈ '{n2}' "
                        f"(levenshtein: {similarity:.2f})"
                    )
                    return True

            return False

        # Iterate over all existing documents and compare
        logger.info(f"Identity check: comparing {document_code} with existing docs: {list(existing_documents.keys())}")

        for doc_code, doc_data in existing_documents.items():
            # Skip if comparing document with itself
            if doc_code.lower() == document_code.lower():
                continue

            # Defensive: existing_documents values must be dicts. Older code
            # paths (workflow_orchestrator passing through json.loads of a
            # potentially double-JSON-encoded extraction_data) could leave
            # a bare string in the dict. Skip + warn instead of crashing
            # the whole identity check (and therefore the entire wizard
            # auto_prepare flow).
            if not isinstance(doc_data, dict):
                logger.warning(
                    f"Identity check skipping {doc_code}: doc_data is "
                    f"{type(doc_data).__name__}, expected dict"
                )
                continue

            # Support both formats:
            # Legacy/DB flow: {"extraction": {"apellidos": ...}, "confidence": ...}
            # Cache-first wizard: {"apellidos": ...} (flat, no wrapper)
            existing_extraction = doc_data.get("extraction", None)
            if existing_extraction is None:
                # Flat format from wizard session - doc_data IS the extraction
                existing_extraction = doc_data
            if not existing_extraction or not isinstance(existing_extraction, dict):
                logger.warning(
                    f"No usable extraction for {doc_code} "
                    f"(type={type(existing_extraction).__name__})"
                )
                continue

            logger.info(f"Comparing {document_code} with {doc_code}")

            # Check each configured identity field
            for field_config in identity_config.critical_fields:
                # Get current document value
                current_value = get_nested_value(extraction, field_config.field_paths)

                # Get existing document value
                existing_value = get_nested_value(existing_extraction, field_config.field_paths)

                # Log the comparison for debugging
                logger.debug(
                    f"Field '{field_config.field_name}': "
                    f"{document_code}='{current_value}' vs {doc_code}='{existing_value}'"
                )

                # Compare if both exist - use fuzzy matching for name fields
                if current_value and existing_value:
                    # Check if values match (exact or fuzzy for names)
                    if current_value == existing_value:
                        logger.debug(f"  → MATCH (exact)")
                        continue  # Exact match, no mismatch

                    if names_match_fuzzy(current_value, existing_value, field_config.field_name):
                        logger.debug(f"  → MATCH (fuzzy)")
                        continue  # Fuzzy match for names, no mismatch

                    logger.warning(
                        f"  → MISMATCH: {field_config.field_name} - "
                        f"'{current_value}' != '{existing_value}'"
                    )
                    # Values don't match - this is a real mismatch
                    # Determine risk code based on field name
                    risk_code = {
                        "nombres": RiskFactorCode.NAME_MISMATCH,
                        "apellidos": RiskFactorCode.NAME_MISMATCH,
                        "numero_documento": RiskFactorCode.ID_NUMBER_MISMATCH,
                        "fecha_nacimiento": RiskFactorCode.BIRTHDATE_MISMATCH,
                        "nacionalidad": RiskFactorCode.NATIONALITY_MISMATCH
                    }.get(field_config.field_name, RiskFactorCode.CROSS_FIELD_MISMATCH)

                    # Create risk factor
                    severity = RISK_FACTOR_SEVERITY.get(risk_code, "high")
                    risks.append({
                        "code": risk_code.value,
                        "severity": severity,
                        "message": f"{field_config.field_name.title()} mismatch between {document_code} and {doc_code}",
                        "detail": {
                            "field": field_config.field_name,
                            "current_document": document_code,
                            "current_value": current_value,
                            "compared_document": doc_code,
                            "compared_value": existing_value,
                            "is_blocking": field_config.is_blocking
                        },
                        "action": "block" if field_config.is_blocking else "review"
                    })

                    # Create structured identity mismatch
                    identity_mismatches.append({
                        "field_name": field_config.field_name,
                        "field_label": {
                            "es": field_config.label_es or field_config.field_name,
                            "fr": field_config.label_fr or field_config.field_name,
                            "en": field_config.label_en or field_config.field_name
                        },
                        "is_blocking": field_config.is_blocking,
                        "source_document": {
                            "code": document_code,
                            "value": current_value
                        },
                        "compared_document": {
                            "code": doc_code,
                            "value": existing_value
                        },
                        "risk_code": risk_code.value,
                        "severity": severity
                    })

                    # Update blocking flag
                    if field_config.is_blocking and identity_config.is_blocking:
                        has_blocking_mismatches = True
                        logger.warning(
                            f"BLOCKING identity mismatch: {field_config.field_name} - "
                            f"{document_code}:{current_value} vs {doc_code}:{existing_value}"
                        )

        return {
            "risk_factors": risks,
            "identity_mismatches": identity_mismatches,
            "has_blocking_mismatches": has_blocking_mismatches
        }

    def _check_parental_authorization_cross_validation(
        self,
        existing_documents: Dict[str, Dict[str, Any]],
        form_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Cross-validate parental authorization document with parent/guardian identity documents.

        For minor passport workflows:
        - autorizacion_parental.representante_1.documento_numero MUST match documento_representante_1
        - autorizacion_parental.representante_2.documento_numero MUST match documento_representante_2 (if not representante_unico)
        - Document number mismatches are BLOCKING

        Returns:
            Dict with:
            - cross_validation_passed: bool
            - blocking_errors: List of blocking errors
            - warnings: List of non-blocking warnings
            - validation_details: Detailed comparison results
        """
        result = {
            "cross_validation_passed": True,
            "blocking_errors": [],
            "warnings": [],
            "validation_details": {
                "representante_1": {"validated": False, "match": None, "error": None},
                "representante_2": {"validated": False, "match": None, "error": None}
            }
        }

        # Get autorizacion_parental extraction
        # Support both formats: {"extraction": {...}} (legacy) and {...} (wizard flat)
        auth_doc = existing_documents.get("autorizacion_parental", {})
        auth_extraction = auth_doc.get("extraction", None)
        if auth_extraction is None:
            auth_extraction = auth_doc

        if not auth_extraction:
            logger.warning("No autorizacion_parental extraction found for cross-validation")
            return result

        # Get parent document extractions (same dual-format support)
        rep1_doc = existing_documents.get("documento_representante_1", {})
        rep1_extraction = rep1_doc.get("extraction", None)
        if rep1_extraction is None:
            rep1_extraction = rep1_doc

        rep2_doc = existing_documents.get("documento_representante_2", {})
        rep2_extraction = rep2_doc.get("extraction", None)
        if rep2_extraction is None:
            rep2_extraction = rep2_doc

        # Check if representante_unico (single parent)
        es_representante_unico = auth_extraction.get("documento", {}).get("es_representante_unico", False)
        if form_data and "representante_unico" in form_data:
            es_representante_unico = form_data.get("representante_unico", False)

        logger.info(f"Parental authorization cross-validation: representante_unico={es_representante_unico}")

        # ══════════════════════════════════════════════════════════════════════════
        # Representante 1 validation (ALWAYS required)
        # ══════════════════════════════════════════════════════════════════════════
        auth_rep1_num = (
            auth_extraction.get("representante_1", {}).get("documento_numero", "") or ""
        ).strip().upper()

        if rep1_extraction:
            # Get document number from parent's identity document
            # Works for DIP, NIE (permiso_residencia), or Passport
            rep1_doc_num = (
                rep1_extraction.get("documento", {}).get("numero_dip") or
                rep1_extraction.get("documento", {}).get("numero_nie") or
                rep1_extraction.get("documento", {}).get("numero_pasaporte") or
                rep1_extraction.get("numero_documento") or
                rep1_extraction.get("numero") or
                ""
            ).strip().upper()

            if auth_rep1_num and rep1_doc_num:
                if auth_rep1_num == rep1_doc_num:
                    result["validation_details"]["representante_1"] = {
                        "validated": True,
                        "match": True,
                        "auth_value": auth_rep1_num,
                        "doc_value": rep1_doc_num,
                        "error": None
                    }
                    logger.info(f"✓ Representante 1 document number MATCH: {auth_rep1_num}")
                else:
                    # BLOCKING ERROR - document numbers don't match
                    result["cross_validation_passed"] = False
                    error = {
                        "code": RiskFactorCode.AUTHORIZATION_PARENT_ID_MISMATCH.value,
                        "field": "representante_1.documento_numero",
                        "auth_value": auth_rep1_num,
                        "doc_value": rep1_doc_num,
                        "message_es": f"N° documento en autorización ({auth_rep1_num}) no coincide con documento del representante 1 ({rep1_doc_num})",
                        "message_fr": f"N° document dans l'autorisation ({auth_rep1_num}) ne correspond pas au document du représentant 1 ({rep1_doc_num})",
                        "message_en": f"Document number in authorization ({auth_rep1_num}) doesn't match representative 1's document ({rep1_doc_num})"
                    }
                    result["blocking_errors"].append(error)
                    result["validation_details"]["representante_1"] = {
                        "validated": True,
                        "match": False,
                        "auth_value": auth_rep1_num,
                        "doc_value": rep1_doc_num,
                        "error": error
                    }
                    logger.error(f"✗ Representante 1 document number MISMATCH: auth={auth_rep1_num} vs doc={rep1_doc_num}")
            else:
                # Missing data warning
                result["warnings"].append({
                    "code": "MISSING_DATA_FOR_VALIDATION",
                    "field": "representante_1.documento_numero",
                    "message_es": "No se pudo validar el número de documento del representante 1",
                    "message_fr": "Impossible de valider le numéro de document du représentant 1",
                    "message_en": "Could not validate representative 1's document number"
                })
        else:
            result["warnings"].append({
                "code": "DOCUMENT_NOT_UPLOADED",
                "field": "documento_representante_1",
                "message_es": "Documento del representante 1 no subido",
                "message_fr": "Document du représentant 1 non téléchargé",
                "message_en": "Representative 1's document not uploaded"
            })

        # ══════════════════════════════════════════════════════════════════════════
        # Representante 2 validation (only if NOT representante_unico)
        # ══════════════════════════════════════════════════════════════════════════
        if not es_representante_unico:
            auth_rep2_num = (
                auth_extraction.get("representante_2", {}).get("documento_numero", "") or ""
            ).strip().upper()

            if rep2_extraction:
                rep2_doc_num = (
                    rep2_extraction.get("documento", {}).get("numero_dip") or
                    rep2_extraction.get("documento", {}).get("numero_nie") or
                    rep2_extraction.get("documento", {}).get("numero_pasaporte") or
                    rep2_extraction.get("numero_documento") or
                    rep2_extraction.get("numero") or
                    ""
                ).strip().upper()

                if auth_rep2_num and rep2_doc_num:
                    if auth_rep2_num == rep2_doc_num:
                        result["validation_details"]["representante_2"] = {
                            "validated": True,
                            "match": True,
                            "auth_value": auth_rep2_num,
                            "doc_value": rep2_doc_num,
                            "error": None
                        }
                        logger.info(f"✓ Representante 2 document number MATCH: {auth_rep2_num}")
                    else:
                        # BLOCKING ERROR
                        result["cross_validation_passed"] = False
                        error = {
                            "code": RiskFactorCode.AUTHORIZATION_PARENT_ID_MISMATCH.value,
                            "field": "representante_2.documento_numero",
                            "auth_value": auth_rep2_num,
                            "doc_value": rep2_doc_num,
                            "message_es": f"N° documento en autorización ({auth_rep2_num}) no coincide con documento del representante 2 ({rep2_doc_num})",
                            "message_fr": f"N° document dans l'autorisation ({auth_rep2_num}) ne correspond pas au document du représentant 2 ({rep2_doc_num})",
                            "message_en": f"Document number in authorization ({auth_rep2_num}) doesn't match representative 2's document ({rep2_doc_num})"
                        }
                        result["blocking_errors"].append(error)
                        result["validation_details"]["representante_2"] = {
                            "validated": True,
                            "match": False,
                            "auth_value": auth_rep2_num,
                            "doc_value": rep2_doc_num,
                            "error": error
                        }
                        logger.error(f"✗ Representante 2 document number MISMATCH: auth={auth_rep2_num} vs doc={rep2_doc_num}")
                else:
                    result["warnings"].append({
                        "code": "MISSING_DATA_FOR_VALIDATION",
                        "field": "representante_2.documento_numero",
                        "message_es": "No se pudo validar el número de documento del representante 2",
                        "message_fr": "Impossible de valider le numéro de document du représentant 2",
                        "message_en": "Could not validate representative 2's document number"
                    })
            elif auth_rep2_num:
                # Authorization has rep2 but no document uploaded
                result["cross_validation_passed"] = False
                result["blocking_errors"].append({
                    "code": RiskFactorCode.AUTHORIZATION_DUAL_REQUIRES_BOTH.value,
                    "field": "documento_representante_2",
                    "message_es": "La autorización tiene 2 firmantes pero falta el documento del representante 2",
                    "message_fr": "L'autorisation a 2 signataires mais le document du représentant 2 est manquant",
                    "message_en": "Authorization has 2 signatories but representative 2's document is missing"
                })

        return result

    def _check_form_consistency(
        self,
        extraction: Dict[str, Any],
        form_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check consistency between extracted data and form data"""
        risks = []

        # Mapping of form fields to extraction fields
        field_mapping = {
            "nombre": ["nombres", "nombre", "first_name"],
            "apellido": ["apellidos", "apellido", "last_name"],
            "dni": ["numero_documento", "dni", "id_number"],
            "fecha_nacimiento": ["fecha_nacimiento", "birthdate"]
        }

        for form_field, extraction_fields in field_mapping.items():
            if form_field in form_data and form_data[form_field]:
                form_value = str(form_data[form_field]).strip().upper()

                for ext_field in extraction_fields:
                    if ext_field in extraction and extraction[ext_field]:
                        ext_value = str(extraction[ext_field]).strip().upper()

                        # Allow partial match for names
                        if form_field in ["nombre", "apellido"]:
                            if form_value not in ext_value and ext_value not in form_value:
                                risks.append({
                                    "code": RiskFactorCode.CROSS_FIELD_MISMATCH.value,
                                    "severity": "medium",
                                    "message": f"Form {form_field} doesn't match document",
                                    "detail": {
                                        "form_value": form_value,
                                        "document_value": ext_value
                                    },
                                    "action": "review"
                                })
                        else:
                            if form_value != ext_value:
                                risks.append({
                                    "code": RiskFactorCode.CROSS_FIELD_MISMATCH.value,
                                    "severity": "medium",
                                    "message": f"Form {form_field} doesn't match document",
                                    "detail": {
                                        "form_value": form_value,
                                        "document_value": ext_value
                                    },
                                    "action": "review"
                                })
                        break

        return risks

    def _check_document_constraints(
        self,
        extraction: Dict[str, Any],
        constraints: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Validate extracted data against workflow-specific constraints from DocumentRequirement.config.

        Supports constraint keys:
        - required_{field_name}: str  → extraction[field_name] must equal value
        - required_{field_name}: list → extraction[field_name] must be in list

        Example constraints:
            {"required_tipo_certificado": "APTITUD", "required_resultado": ["SANO", "APTO"]}
        """
        risks = []

        for constraint_key, expected_value in constraints.items():
            if not constraint_key.startswith("required_"):
                continue

            # Extract field name: "required_tipo_certificado" → "tipo_certificado"
            field_name = constraint_key[len("required_"):]
            actual_value = extraction.get(field_name)

            if actual_value is None:
                # Field not extracted - warning (might be OCR miss)
                risks.append({
                    "code": "WORKFLOW_CONSTRAINT_MISSING_FIELD",
                    "severity": "medium",
                    "message": f"Required field '{field_name}' not found in extraction",
                    "detail": {
                        "field": field_name,
                        "expected": expected_value
                    },
                    "action": "review"
                })
                continue

            # Normalize for comparison
            actual_normalized = str(actual_value).strip().upper()

            if isinstance(expected_value, list):
                expected_normalized = [str(v).strip().upper() for v in expected_value]
                if actual_normalized not in expected_normalized:
                    risks.append({
                        "code": "WORKFLOW_CONSTRAINT_VIOLATION",
                        "severity": "high",
                        "message": (
                            f"Document field '{field_name}' has value '{actual_value}' "
                            f"but workflow requires one of: {expected_value}"
                        ),
                        "detail": {
                            "field": field_name,
                            "actual": actual_value,
                            "expected_values": expected_value
                        },
                        "action": "reject"
                    })
            else:
                expected_normalized = str(expected_value).strip().upper()
                if actual_normalized != expected_normalized:
                    risks.append({
                        "code": "WORKFLOW_CONSTRAINT_VIOLATION",
                        "severity": "high",
                        "message": (
                            f"Document field '{field_name}' has value '{actual_value}' "
                            f"but workflow requires '{expected_value}'"
                        ),
                        "detail": {
                            "field": field_name,
                            "actual": actual_value,
                            "expected": expected_value
                        },
                        "action": "reject"
                    })

        if risks:
            logger.warning(
                f"Document constraint violations: {len(risks)} "
                f"(constraints: {list(constraints.keys())})"
            )

        return risks

    def _check_data_validation(
        self,
        extraction: Dict[str, Any],
        document_code: str,
        workflow_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Validate extracted data formats and logical constraints.

        Includes workflow-aware validations:
        - DIP number format (9 digits for GQ)
        - Denuncia policial date (< 30 days for PERDIDA/ROBO)
        - Passport expiry (< 12 months for RENOVACION)
        """
        risks = []
        today = date.today()
        workflow_upper = (workflow_code or "").upper()

        # Birthdate validation
        birthdate_fields = ["fecha_nacimiento", "birthdate", "date_of_birth"]
        for field in birthdate_fields:
            if field in extraction and extraction[field]:
                try:
                    birthdate = self._parse_date(extraction[field])
                    if birthdate:
                        if birthdate > today:
                            risks.append({
                                "code": RiskFactorCode.FUTURE_BIRTHDATE.value,
                                "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.FUTURE_BIRTHDATE],
                                "message": "Birthdate is in the future",
                                "detail": {"birthdate": birthdate.isoformat()},
                                "action": "reject"
                            })
                        else:
                            age = (today - birthdate).days // 365
                            if age < 0 or age > 150:
                                risks.append({
                                    "code": RiskFactorCode.IMPOSSIBLE_AGE.value,
                                    "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.IMPOSSIBLE_AGE],
                                    "message": f"Impossible age calculated: {age} years",
                                    "detail": {"birthdate": birthdate.isoformat(), "calculated_age": age},
                                    "action": "review"
                                })
                            elif age < 16 and document_code in ["contrato_trabajo", "declaracion_renta"]:
                                risks.append({
                                    "code": RiskFactorCode.LOGICAL_INCONSISTENCY.value,
                                    "severity": "high",
                                    "message": f"Person is {age} years old - too young for this document type",
                                    "detail": {"age": age, "document_type": document_code},
                                    "action": "review"
                                })
                except Exception as e:
                    logger.warning(f"Error validating birthdate: {e}")

        # ID number format validation (GQ DNI format)
        id_fields = ["numero_documento", "dni", "id_number"]
        for field in id_fields:
            if field in extraction and extraction[field]:
                id_value = str(extraction[field]).strip()
                # GQ DNI typically follows patterns like "12345678A" or similar
                if document_code == "dip_gq":
                    if not re.match(r'^[A-Z0-9]{6,12}$', id_value.upper()):
                        risks.append({
                            "code": RiskFactorCode.INVALID_ID_FORMAT.value,
                            "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.INVALID_ID_FORMAT],
                            "message": "ID number format appears invalid",
                            "detail": {"id_value": id_value, "expected_pattern": "6-12 alphanumeric characters"},
                            "action": "review"
                        })

        # ══════════════════════════════════════════════════════════════════════════
        # WORKFLOW-SPECIFIC VALIDATIONS (moved from Step 6 validation)
        # ══════════════════════════════════════════════════════════════════════════

        # 1. DIP Number Format: Must be exactly 9 digits (GQ requirement)
        if document_code in ["dip", "dip_gq"]:
            numero_dip = None
            # Check nested paths
            if "documento" in extraction and isinstance(extraction["documento"], dict):
                numero_dip = extraction["documento"].get("numero_dip")
            if not numero_dip:
                numero_dip = extraction.get("numero_dip")

            if numero_dip:
                numero_str = str(numero_dip).strip()
                if not re.match(r'^\d{9}$', numero_str):
                    risks.append({
                        "code": RiskFactorCode.INVALID_ID_FORMAT.value,
                        "severity": "error",
                        "message": "El número de DIP debe tener exactamente 9 dígitos",
                        "detail": {
                            "numero_dip": numero_str,
                            "expected_format": "9 dígitos numéricos"
                        },
                        "action": "reject"
                    })

        # 2. Denuncia Policial: Must be issued within last 30 days (for PERDIDA/ROBO)
        if document_code in ["denuncia_policial", "denuncia"]:
            fecha_emision = None
            # Check various possible field names
            for field in ["fecha_emision", "fecha", "fecha_denuncia", "date"]:
                if field in extraction and extraction[field]:
                    fecha_emision = self._parse_date(extraction[field])
                    if fecha_emision:
                        break

            if fecha_emision:
                days_old = (today - fecha_emision).days
                if days_old > 30:
                    risks.append({
                        "code": RiskFactorCode.DOC_EXPIRED.value,
                        "severity": "error",
                        "message": f"La denuncia policial tiene más de 30 días ({days_old} días)",
                        "detail": {
                            "fecha_emision": fecha_emision.isoformat(),
                            "dias_antiguedad": days_old,
                            "maximo_permitido": 30
                        },
                        "action": "reject"
                    })

        # 3. Passport Expiry for RENOVACION: Must expire within 12 months
        if document_code in ["pasaporte", "pasaporte_antiguo", "pasaporte_danado"]:
            # Only check for RENOVACION workflows
            is_renovacion = "RENOVACION" in workflow_upper or "VENCIMIENTO" in workflow_upper

            if is_renovacion:
                fecha_expiracion = None
                for field in ["fecha_expiracion", "fecha_caducidad", "expiry_date", "valid_until"]:
                    if "documento" in extraction and isinstance(extraction["documento"], dict):
                        fecha_expiracion = self._parse_date(extraction["documento"].get(field))
                    if not fecha_expiracion and field in extraction:
                        fecha_expiracion = self._parse_date(extraction[field])
                    if fecha_expiracion:
                        break

                if fecha_expiracion:
                    months_until_expiry = (fecha_expiracion - today).days / 30
                    if months_until_expiry > 12:
                        risks.append({
                            "code": RiskFactorCode.LOGICAL_INCONSISTENCY.value,
                            "severity": "warning",
                            "message": f"El pasaporte no expira en los próximos 12 meses (expira en {int(months_until_expiry)} meses)",
                            "detail": {
                                "fecha_expiracion": fecha_expiracion.isoformat(),
                                "meses_hasta_expiracion": int(months_until_expiry),
                                "requisito": "Debe expirar en menos de 12 meses para renovación"
                            },
                            "action": "warn"
                        })

        # ══════════════════════════════════════════════════════════════════════════
        # 4. CONDUCIR WORKFLOW: Minimum Age for License Classes
        # ══════════════════════════════════════════════════════════════════════════
        if "CONDUCIR" in workflow_upper:
            # Define minimum ages for license classes
            license_min_ages = {
                "A": 18, "B": 18, "B+": 18, "F": 18,  # Standard classes
                "C": 21, "D": 21, "E": 21  # Heavy/passenger vehicles
            }

            # Extract birth date from DIP or Permiso Residencia
            if document_code in ["dip", "dip_gq", "permiso_residencia"]:
                birthdate = None
                # Try various paths for birth date
                if "titular" in extraction and isinstance(extraction["titular"], dict):
                    birthdate = self._parse_date(extraction["titular"].get("fecha_nacimiento"))
                if not birthdate:
                    birthdate = self._parse_date(extraction.get("fecha_nacimiento"))

                if birthdate:
                    age = (today - birthdate).days // 365

                    # Minimum age for ANY license is 18
                    if age < 18:
                        risks.append({
                            "code": RiskFactorCode.MIN_AGE_FOR_LICENSE.value,
                            "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.MIN_AGE_FOR_LICENSE],
                            "message": f"Edad insuficiente para obtener certificado de conducir. Debe tener al menos 18 años.",
                            "detail": {
                                "fecha_nacimiento": birthdate.isoformat(),
                                "edad_actual": age,
                                "edad_minima_requerida": 18,
                                "clases_elegibles": []
                            },
                            "action": "reject"
                        })
                    elif age < 21:
                        # Can get A, B, B+, F but not C, D, E
                        eligible_classes = [c for c, min_age in license_min_ages.items() if age >= min_age]
                        restricted_classes = [c for c, min_age in license_min_ages.items() if age < min_age]

                        risks.append({
                            "code": RiskFactorCode.UNDERAGE_FOR_CLASS.value,
                            "severity": "warning",  # Warning, not blocking - user can choose eligible classes
                            "message": f"Con {age} años, solo puede solicitar las clases: {', '.join(sorted(eligible_classes))}",
                            "detail": {
                                "fecha_nacimiento": birthdate.isoformat(),
                                "edad_actual": age,
                                "clases_elegibles": eligible_classes,
                                "clases_restringidas": restricted_classes,
                                "mensaje_sugerencia": f"Para las clases {', '.join(sorted(restricted_classes))} debe tener 21 años."
                            },
                            "action": "warn"
                        })

        return risks

    def _check_amount_validation(
        self,
        extraction: Dict[str, Any],
        document_code: str
    ) -> List[Dict[str, Any]]:
        """Validate monetary amounts"""
        risks = []

        amount_fields = ["monto", "importe", "cantidad", "total", "amount", "valor"]
        min_amount, max_amount = AMOUNT_RANGES.get(document_code, AMOUNT_RANGES["default"])

        for field in amount_fields:
            if field in extraction and extraction[field]:
                try:
                    # Parse amount (handle different formats)
                    amount_str = str(extraction[field])
                    amount_str = re.sub(r'[^\d.,]', '', amount_str)
                    amount_str = amount_str.replace(',', '.')
                    amount = float(amount_str)

                    if amount < min_amount or amount > max_amount:
                        risks.append({
                            "code": RiskFactorCode.AMOUNT_OUT_OF_RANGE.value,
                            "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.AMOUNT_OUT_OF_RANGE],
                            "message": f"Amount {amount:,.0f} XAF is outside expected range",
                            "detail": {
                                "amount": amount,
                                "min_expected": min_amount,
                                "max_expected": max_amount,
                                "currency": "XAF"
                            },
                            "action": "review"
                        })

                    # Check for suspicious round numbers (potential fabrication)
                    if amount >= 1_000_000 and amount % 1_000_000 == 0:
                        risks.append({
                            "code": RiskFactorCode.SUSPICIOUS_AMOUNT.value,
                            "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.SUSPICIOUS_AMOUNT],
                            "message": "Suspiciously round amount detected",
                            "detail": {"amount": amount},
                            "action": "review"
                        })

                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing amount: {e}")

        # Check for currency mismatch (expected XAF for GQ documents)
        currency_fields = ["moneda", "currency", "divisa"]
        for field in currency_fields:
            if field in extraction and extraction[field]:
                currency = str(extraction[field]).upper().strip()
                if currency not in ["XAF", "FCFA", "CFA", "FRANCS CFA"]:
                    risks.append({
                        "code": RiskFactorCode.CURRENCY_MISMATCH.value,
                        "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.CURRENCY_MISMATCH],
                        "message": f"Unexpected currency: {currency} (expected XAF)",
                        "detail": {
                            "detected_currency": currency,
                            "expected_currency": "XAF"
                        },
                        "action": "review"
                    })

        return risks

    def _check_coherence(
        self,
        extraction: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check logical coherence of extracted data"""
        risks = []

        # Check issue date < expiry date
        issue_date = None
        expiry_date = None

        for field in ["fecha_expedicion", "fecha_emision", "issue_date"]:
            if field in extraction and extraction[field]:
                issue_date = self._parse_date(extraction[field])
                break

        for field in ["fecha_caducidad", "fecha_expiracion", "expiry_date"]:
            if field in extraction and extraction[field]:
                expiry_date = self._parse_date(extraction[field])
                break

        if issue_date and expiry_date and issue_date >= expiry_date:
            risks.append({
                "code": RiskFactorCode.TEMPORAL_ANOMALY.value,
                "severity": "high",
                "message": "Issue date is not before expiry date",
                "detail": {
                    "issue_date": issue_date.isoformat(),
                    "expiry_date": expiry_date.isoformat()
                },
                "action": "review"
            })

        # Check birthdate < issue date
        birthdate = None
        for field in ["fecha_nacimiento", "birthdate"]:
            if field in extraction and extraction[field]:
                birthdate = self._parse_date(extraction[field])
                break

        if birthdate and issue_date and birthdate >= issue_date:
            risks.append({
                "code": RiskFactorCode.TEMPORAL_ANOMALY.value,
                "severity": "high",
                "message": "Birthdate is not before document issue date",
                "detail": {
                    "birthdate": birthdate.isoformat(),
                    "issue_date": issue_date.isoformat()
                },
                "action": "review"
            })

        return risks

    def _process_gemini_risk_hints(
        self,
        gemini_hints: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Process fraud/risk indicators detected by Gemini"""
        risks = []

        # Defense: gemini_hints must be a dict. Gemini may return
        # _risk_hints as a string or list instead of a dict.
        if not isinstance(gemini_hints, dict):
            logger.warning(
                f"_process_gemini_risk_hints received "
                f"{type(gemini_hints).__name__}, expected dict"
            )
            return risks

        # Digital manipulation detection
        if gemini_hints.get("digital_manipulation_detected"):
            risks.append({
                "code": RiskFactorCode.DIGITAL_MANIPULATION.value,
                "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.DIGITAL_MANIPULATION],
                "message": "AI detected signs of digital manipulation",
                "detail": gemini_hints.get("manipulation_details", {}),
                "action": "reject"
            })

        # Font inconsistencies
        if gemini_hints.get("inconsistent_fonts"):
            risks.append({
                "code": RiskFactorCode.INCONSISTENT_FONTS.value,
                "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.INCONSISTENT_FONTS],
                "message": "Document shows inconsistent fonts/typography",
                "detail": gemini_hints.get("font_details", {}),
                "action": "review"
            })

        # Suspicious patterns — Gemini may return either:
        #   [{"description": "blurry"}, ...] (expected) or
        #   ["blurry text", ...] (string list, observed in production)
        if gemini_hints.get("suspicious_patterns"):
            for pattern in gemini_hints["suspicious_patterns"]:
                if isinstance(pattern, dict):
                    desc = pattern.get("description", "Unknown")
                    detail = pattern
                else:
                    desc = str(pattern)
                    detail = {"description": desc}
                risks.append({
                    "code": RiskFactorCode.SUSPICIOUS_PATTERNS.value,
                    "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.SUSPICIOUS_PATTERNS],
                    "message": f"Suspicious pattern detected: {desc}",
                    "detail": detail,
                    "action": "review"
                })

        # Low quality indicators
        if gemini_hints.get("low_quality"):
            risks.append({
                "code": RiskFactorCode.LOW_IMAGE_QUALITY.value,
                "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.LOW_IMAGE_QUALITY],
                "message": "Document image quality is poor",
                "detail": gemini_hints.get("quality_details", {}),
                "action": "warn"
            })

        # Missing elements
        if gemini_hints.get("missing_signature"):
            risks.append({
                "code": RiskFactorCode.MISSING_SIGNATURE.value,
                "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.MISSING_SIGNATURE],
                "message": "Document appears to be missing a signature",
                "detail": {},
                "action": "review"
            })

        if gemini_hints.get("missing_stamp"):
            risks.append({
                "code": RiskFactorCode.MISSING_STAMP.value,
                "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.MISSING_STAMP],
                "message": "Document appears to be missing an official stamp",
                "detail": {},
                "action": "review"
            })

        # Altered dates detection
        if gemini_hints.get("altered_dates_detected"):
            risks.append({
                "code": RiskFactorCode.ALTERED_DATES.value,
                "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.ALTERED_DATES],
                "message": "Dates on document appear to have been altered",
                "detail": gemini_hints.get("altered_dates_details", {}),
                "action": "reject"
            })

        # Photo manipulation detection
        if gemini_hints.get("photo_appears_manipulated"):
            risks.append({
                "code": RiskFactorCode.PHOTO_MISMATCH.value,
                "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.PHOTO_MISMATCH],
                "message": "Photo on document appears manipulated or altered",
                "detail": {"source": "gemini_visual_analysis"},
                "action": "review"
            })

        # Document expiry from visual analysis
        if gemini_hints.get("document_appears_expired"):
            expiry_date = gemini_hints.get("expiry_date_detected")
            risks.append({
                "code": RiskFactorCode.DOC_EXPIRED.value,
                "severity": RISK_FACTOR_SEVERITY[RiskFactorCode.DOC_EXPIRED],
                "message": "Document appears to be expired based on visual analysis",
                "detail": {"expiry_date_detected": expiry_date},
                "action": "reject"
            })

        # Low authenticity score
        authenticity_score = gemini_hints.get("authenticity_score", 1.0)
        if isinstance(authenticity_score, (int, float)) and authenticity_score < 0.6:
            risks.append({
                "code": RiskFactorCode.SUSPICIOUS_PATTERNS.value,
                "severity": "high" if authenticity_score < 0.4 else "medium",
                "message": f"Document has low authenticity score: {authenticity_score:.0%}",
                "detail": {
                    "authenticity_score": authenticity_score,
                    "notes": gemini_hints.get("notes", "")
                },
                "action": "review"
            })

        return risks

    def _calculate_risk_score(
        self,
        risk_factors: List[Dict[str, Any]]
    ) -> Tuple[int, RiskLevel]:
        """Calculate overall risk score and level"""
        if not risk_factors:
            return 0, RiskLevel.LOW

        # Severity weights
        severity_weights = {
            "critical": 40,
            "high": 25,
            "medium": 10,
            "low": 3
        }

        total_score = sum(
            severity_weights.get(rf["severity"], 5)
            for rf in risk_factors
        )

        # Cap at 100
        total_score = min(100, total_score)

        # Determine level
        if any(rf["severity"] == "critical" for rf in risk_factors):
            level = RiskLevel.CRITICAL
        elif total_score >= RISK_SCORE_HIGH:
            level = RiskLevel.HIGH
        elif total_score >= RISK_SCORE_MEDIUM:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        return total_score, level

    def _generate_recommendations(
        self,
        risk_factors: List[Dict[str, Any]],
        risk_level: RiskLevel
    ) -> List[str]:
        """Generate actionable recommendations based on risk factors"""
        recommendations = []

        # Critical issues
        critical_factors = [rf for rf in risk_factors if rf["severity"] == "critical"]
        if critical_factors:
            recommendations.append("URGENT: Document requires immediate rejection or escalation")
            for cf in critical_factors:
                if cf["code"] == RiskFactorCode.DOC_TYPE_MISMATCH.value:
                    recommendations.append(f"Request correct document type: {cf['detail'].get('expected', 'unknown')}")
                elif cf["code"] == RiskFactorCode.DUPLICATE_DOCUMENT.value:
                    recommendations.append("Investigate potential document fraud - same document used by another user")
                elif cf["code"] == RiskFactorCode.DIGITAL_MANIPULATION.value:
                    recommendations.append("Escalate to fraud investigation team")

        # High severity
        high_factors = [rf for rf in risk_factors if rf["severity"] == "high"]
        if high_factors:
            recommendations.append("Manual verification required by agent")
            for hf in high_factors:
                if hf["code"] == RiskFactorCode.DOC_EXPIRED.value:
                    recommendations.append("Request a valid, non-expired document")
                elif hf["code"] == RiskFactorCode.NAME_MISMATCH.value:
                    recommendations.append("Verify identity across all submitted documents")
                elif hf["code"] == RiskFactorCode.ID_NUMBER_MISMATCH.value:
                    recommendations.append("Cross-check ID numbers with official records")

        # Medium severity
        medium_factors = [rf for rf in risk_factors if rf["severity"] == "medium"]
        if medium_factors and not high_factors and not critical_factors:
            recommendations.append("Review flagged items before approval")

        # Expiry warning
        if any(rf["code"] == RiskFactorCode.DOC_NEAR_EXPIRY.value for rf in risk_factors):
            recommendations.append("Document expires soon - consider requesting renewal")

        # Quality issues
        if any(rf["code"] == RiskFactorCode.LOW_IMAGE_QUALITY.value for rf in risk_factors):
            recommendations.append("Request higher quality document scan")

        if not recommendations:
            recommendations.append("No significant risks detected - proceed with standard processing")

        return recommendations

    def _parse_date(self, date_value: Any) -> Optional[date]:
        """Parse various date formats into date object"""
        if isinstance(date_value, date):
            return date_value

        if not date_value:
            return None

        date_str = str(date_value).strip()

        # Common formats
        formats = [
            "%Y-%m-%d",      # ISO format
            "%d/%m/%Y",      # European format
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%d.%m.%Y",
            "%Y%m%d",        # Compact format
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        return None


# Global risk analyzer instance
_risk_analyzer = RiskAnalyzer()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN PROCESSOR CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class GeminiDocumentProcessor:
    """
    Production document processor using Gemini AI + Tesseract fallback + Risk Analysis.

    Flow:
    1. Try Gemini extraction with multimodal vision (includes fraud detection)
    2. If confidence < 70% or error, fallback to Tesseract OCR
    3. If Tesseract confidence < 60%, mark for manual review
    4. Perform comprehensive risk analysis on extracted data
    5. Return complete result with extraction, confidence, and risk assessment

    Usage:
        processor = GeminiDocumentProcessor()
        result = await processor.process(
            content=file_bytes,
            mime_type="application/pdf",
            document_code="dip_gq",
            request_id="uuid",
            user_id="uuid",
            existing_documents={...},
            form_data={...}
        )
    """

    def __init__(self):
        """Initialize Gemini processor with Vertex AI"""
        self.enabled = False
        self.model = None
        self.risk_analyzer = _risk_analyzer

        if not VERTEX_AI_AVAILABLE:
            logger.error("Vertex AI SDK not available - processor disabled")
            return

        try:
            # Initialize Vertex AI
            vertexai.init(
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.GOOGLE_CLOUD_LOCATION
            )

            # Use Gemini for vision/multimodal tasks
            self.model = GenerativeModel(settings.GEMINI_PRO_MODEL)

            # Generation config optimized for extraction + risk analysis.
            # response_mime_type="application/json" forces Gemini to return
            # ONLY valid JSON — no surrounding text, no markdown, no
            # explanations. This eliminates the fragile regex parsing and
            # prevents format drift when Google updates the model.
            self.generation_config = GenerationConfig(
                temperature=0.1,  # Low for consistent extraction
                top_p=0.8,
                top_k=20,
                max_output_tokens=8192,  # Increased for risk analysis
                response_mime_type="application/json",
            )

            # Safety settings
            self.safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            }

            self.enabled = True
            logger.info(f"Gemini Document Processor initialized (model: {settings.GEMINI_PRO_MODEL})")

        except Exception as e:
            logger.error(f"Failed to initialize Gemini Document Processor: {e}")
            self.enabled = False

    async def process(
        self,
        content: bytes,
        mime_type: str,
        document_code: str,
        request_id: str = "",
        user_id: str = "",
        existing_documents: Optional[Dict[str, Dict[str, Any]]] = None,
        form_data: Optional[Dict[str, Any]] = None,
        extraction_schema_key: Optional[str] = None,
        workflow_code: Optional[str] = None,
        document_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process document for classification, extraction, and RISK ANALYSIS.

        Args:
            content: Document file bytes
            mime_type: MIME type (image/*, application/pdf)
            document_code: Expected document type code
            request_id: Service request ID for duplication tracking
            user_id: User ID for duplication tracking
            existing_documents: Previously uploaded documents for identity consistency
            form_data: User form data for consistency checks
            extraction_schema_key: Database key for schema lookup (e.g., 'DIP_GQ_V1')
            workflow_code: Workflow code for identity verification config (e.g., 'PASAPORTE_NUEVO')
            document_constraints: Workflow-specific constraints from DocumentRequirement.config
                (e.g., {"required_tipo_certificado": "APTITUD", "required_resultado": ["SANO", "APTO"]})

        Returns:
            Dict with:
            - extraction: Dict of extracted fields
            - confidence: Float 0-1
            - processor: "gemini", "tesseract", or "hybrid"
            - status: "success", "low_confidence", "manual_review", "rejected", "error"
            - document_type: Detected document type
            - processing_time_ms: Processing time
            - has_error: Boolean
            - error_message: Optional error message
            - risk_analysis: Complete risk assessment with identity_mismatches
        """
        start_time = time.time()

        # Get schema for document type (prefer extraction_schema_key if provided)
        schema = schema_loader.get_schema_for_document(document_code, extraction_schema_key)
        if not schema:
            logger.warning(f"No schema found for document_code: {document_code}")

        extraction_result = None
        gemini_risk_hints = None

        # Audit tracking variables
        gemini_latency_ms: Optional[int] = None
        used_fallback = False
        fallback_reason: Optional[str] = None
        input_tokens: Optional[int] = None
        output_tokens: Optional[int] = None

        # Gemini EXCLUSIVE: Always use Gemini, accept all confidence levels.
        # Tesseract is ONLY used as emergency fallback if Gemini is unavailable.
        if self.enabled:
            try:
                gemini_start = time.time()
                gemini_result = await self._process_with_gemini(
                    content, mime_type, document_code, schema
                )
                gemini_latency_ms = int((time.time() - gemini_start) * 1000)

                gemini_risk_hints = gemini_result.get("risk_hints", {})
                input_tokens = gemini_result.get("input_tokens")
                output_tokens = gemini_result.get("output_tokens")

                # Accept Gemini result at any confidence (even low confidence
                # Gemini is better than Tesseract based on production observation)
                extraction_result = gemini_result
                if gemini_result["confidence"] >= GEMINI_CONFIDENCE_THRESHOLD:
                    extraction_result["status"] = "success"
                else:
                    extraction_result["status"] = "low_confidence"
                logger.info(
                    f"Gemini extraction: {document_code} "
                    f"(confidence: {gemini_result['confidence']:.2%}, "
                    f"status: {extraction_result['status']})"
                )

            except Exception as e:
                used_fallback = True
                fallback_reason = "gemini_error"
                logger.error(f"Gemini extraction failed: {e}")

        # If Gemini failed or is unavailable, return error (NO Tesseract fallback)
        if not extraction_result:
            used_fallback = True
            if not fallback_reason:
                fallback_reason = "gemini_unavailable"
            extraction_result = {
                "extraction": {},
                "confidence": 0.0,
                "processor": "none",
                "status": "error",
                "document_type": document_code,
                "has_error": True,
                "error_message": "Gemini extraction failed. Please retry or upload a clearer document."
            }

        # ═══════════════════════════════════════════════════════════════════
        # POST-PROCESSING (address separation, field normalization)
        # ═══════════════════════════════════════════════════════════════════
        extraction_result["extraction"] = self._post_process_extraction(
            extraction_result.get("extraction", {}),
            document_code
        )

        # ═══════════════════════════════════════════════════════════════════
        # DUPLICATION PRE-CHECK (async DB lookup before sync analyze)
        # ═══════════════════════════════════════════════════════════════════
        doc_hash = hashlib.sha256(content).hexdigest()
        hash_matches: List[Dict[str, Any]] = []
        if DB_POOL_AVAILABLE:
            try:
                from .document_repository_helper import find_documents_by_hash
                hash_matches = await find_documents_by_hash(
                    doc_hash, request_id  # request_id can be "" (wizard preview)
                )
            except Exception as e:
                logger.warning(f"Hash duplicate lookup failed (non-blocking): {e}")

        # ═══════════════════════════════════════════════════════════════════
        # RISK ANALYSIS
        # ═══════════════════════════════════════════════════════════════════
        risk_analysis = self.risk_analyzer.analyze(
            extraction=extraction_result.get("extraction", {}),
            document_code=document_code,
            detected_type=extraction_result.get("document_type", document_code),
            content=content,
            request_id=request_id,
            user_id=user_id,
            existing_documents=existing_documents,
            form_data=form_data,
            gemini_risk_hints=gemini_risk_hints,
            workflow_code=workflow_code,
            hash_matches=hash_matches,
            document_constraints=document_constraints
        )

        # Attach doc_hash to result for storage during persist
        extraction_result["doc_hash"] = doc_hash

        # Update status based on risk analysis
        if risk_analysis["requires_rejection"]:
            extraction_result["status"] = "rejected"
        elif risk_analysis["requires_review"]:
            extraction_result["status"] = "requires_review"

        # Add processing time and risk analysis
        extraction_result["processing_time_ms"] = int((time.time() - start_time) * 1000)
        extraction_result["risk_analysis"] = risk_analysis

        # ═══════════════════════════════════════════════════════════════════
        # AUDIT LOGGING (fire-and-forget)
        # ═══════════════════════════════════════════════════════════════════
        await self._log_to_audit(
            request_id=request_id,
            user_id=user_id,
            document_code=document_code,
            mime_type=mime_type,
            file_size=len(content),
            result=extraction_result,
            risk_analysis=risk_analysis,
            schema=schema,
            workflow_code=workflow_code,
            gemini_latency_ms=gemini_latency_ms,
            used_fallback=used_fallback,
            fallback_reason=fallback_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        return extraction_result

    # ═══════════════════════════════════════════════════════════════════════════════
    # POST-PROCESSING METHODS
    # ═══════════════════════════════════════════════════════════════════════════════

    def _post_process_extraction(
        self,
        extraction: Dict[str, Any],
        document_code: str
    ) -> Dict[str, Any]:
        """
        Post-process extraction to normalize and separate composite fields.

        Args:
            extraction: Raw extraction dict from Gemini/Tesseract
            document_code: Document type code (e.g., 'DIP', 'PASAPORTE')

        Returns:
            Processed extraction with separated fields
        """
        if not extraction:
            return extraction if isinstance(extraction, dict) else {}

        # Defense layer 2: guard against non-dict input from upstream
        if not isinstance(extraction, dict):
            logger.warning(
                f"_post_process_extraction received "
                f"{type(extraction).__name__}, returning empty dict"
            )
            return {}

        result = extraction.copy()

        # DIP-specific: Parse domiciliacion into address components
        if document_code.upper() in ("DIP", "DIP_GQ", "DNI"):
            domiciliacion = extraction.get("domiciliacion") or extraction.get("domiciliación")
            if domiciliacion:
                address_parts = self._parse_domiciliacion(domiciliacion)
                result.update(address_parts)
                logger.debug(f"Parsed domiciliacion: {domiciliacion} -> {address_parts}")

        return result

    def _parse_domiciliacion(self, domiciliacion: str) -> Dict[str, str]:
        """
        Parse domiciliacion field into address components.

        DIP format: "B/[BARRIO]\n[CIUDAD], [DEPARTAMENTO]"
        Example: "B/ TIMBABE\nMALABO, BIOKO NORTE"

        Sometimes Gemini extracts without newline:
        "B/ TIMBABEMALABO, BIOKO NORTE"

        Args:
            domiciliacion: Raw domiciliacion string from DIP

        Returns:
            Dict with keys: domiciliacion_barrio, domiciliacion_ciudad, domiciliacion_departamento
        """
        result = {
            "domiciliacion_barrio": "",
            "domiciliacion_ciudad": "",
            "domiciliacion_departamento": ""
        }

        if not domiciliacion or not isinstance(domiciliacion, str):
            return result

        # Clean and normalize
        domiciliacion = domiciliacion.strip()

        # Case 1: Has newline separator (ideal case)
        if '\n' in domiciliacion:
            parts = domiciliacion.split('\n', 1)
            result["domiciliacion_barrio"] = parts[0].strip()
            city_dept = parts[1].strip() if len(parts) > 1 else ""
        else:
            # Case 2: No newline - try to detect pattern
            # Pattern: "B/XXXXX" followed by city name (usually all caps)
            # Known cities in GQ: MALABO, BATA, ELA NGUEMA, MONGOMO, EBIBEYIN, etc.
            known_cities = [
                "MALABO", "BATA", "ELA NGUEMA", "MONGOMO", "EBIBEYIN",
                "LUBA", "RIABA", "ANNOBON", "ACONIBE", "ANISOK", "NIEFANG",
                "EBEBIYIN", "MICOMESENG", "NSORK", "EVINAYONG"
            ]

            # Try to find a known city in the string
            city_found = None
            city_pos = -1
            for city in known_cities:
                pos = domiciliacion.upper().find(city)
                if pos > 0:  # Must not be at start
                    if city_pos == -1 or pos < city_pos:
                        city_pos = pos
                        city_found = city

            if city_found and city_pos > 0:
                result["domiciliacion_barrio"] = domiciliacion[:city_pos].strip()
                city_dept = domiciliacion[city_pos:].strip()
            else:
                # Fallback: Look for comma as separator between city and department
                # If there's a comma, split there and assume last part is city,dept
                if ',' in domiciliacion:
                    # Try regex: capture everything before a capitalized word followed by comma
                    match = re.match(
                        r'^(.*?)\s*([A-Z][A-Z\s]+,\s*[A-Z][A-Z\s]+)$',
                        domiciliacion,
                        re.IGNORECASE
                    )
                    if match:
                        result["domiciliacion_barrio"] = match.group(1).strip()
                        city_dept = match.group(2).strip()
                    else:
                        # Just use the whole thing as barrio
                        result["domiciliacion_barrio"] = domiciliacion
                        return result
                else:
                    # No comma, no newline, no known city - keep as barrio
                    result["domiciliacion_barrio"] = domiciliacion
                    return result

        # Parse city and department from "CIUDAD, DEPARTAMENTO"
        if ',' in city_dept:
            parts = city_dept.split(',', 1)
            result["domiciliacion_ciudad"] = parts[0].strip()
            result["domiciliacion_departamento"] = parts[1].strip() if len(parts) > 1 else ""
        else:
            # No comma - entire string is city
            result["domiciliacion_ciudad"] = city_dept.strip()

        return result

    # ═══════════════════════════════════════════════════════════════════════════════
    # AUDIT LOGGING
    # ═══════════════════════════════════════════════════════════════════════════════

    async def _log_to_audit(
        self,
        request_id: str,
        user_id: str,
        document_code: str,
        mime_type: str,
        file_size: int,
        result: Dict[str, Any],
        risk_analysis: Dict[str, Any],
        schema: Optional[Dict],
        workflow_code: Optional[str],
        gemini_latency_ms: Optional[int],
        used_fallback: bool,
        fallback_reason: Optional[str],
        input_tokens: Optional[int],
        output_tokens: Optional[int],
    ) -> None:
        """
        Log processing result to gemini_processing_logs via SQL function.

        Fire-and-forget: NEVER raises exceptions, NEVER blocks the caller.
        Uses the existing log_gemini_processing() SQL function (migration 026).
        """
        if not DB_POOL_AVAILABLE:
            return

        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                # Convert string IDs to UUID or None
                sr_id = None
                if request_id:
                    try:
                        sr_id = UUID(request_id)
                    except (ValueError, AttributeError):
                        pass

                uid = None
                if user_id:
                    try:
                        uid = UUID(user_id)
                    except (ValueError, AttributeError):
                        pass

                # Count extracted fields
                extraction = result.get("extraction", {})
                fields_extracted = sum(
                    1 for k, v in extraction.items()
                    if v is not None and v != "" and not k.startswith("_")
                )

                # Count total fields from schema
                total_fields = 0
                if schema:
                    for section in schema.get("extraction", {}).values():
                        total_fields += len(section.get("fields", {}))
                fields_missing = max(0, total_fields - fields_extracted)

                # Derive document category
                doc_base = document_code.lower().split("_gq")[0].split("_v")[0]
                category = DOCUMENT_CATEGORY_MAP.get(doc_base, "other")

                # Normalize risk_score to 0.0-1.0
                risk_score = risk_analysis.get("risk_score", 0)
                risk_score_normalized = min(1.0, max(0.0, risk_score / 100.0))

                # Derive recommendation
                if risk_analysis.get("requires_rejection"):
                    recommendation = "reject"
                elif risk_analysis.get("requires_review"):
                    recommendation = "manual_review"
                elif risk_analysis.get("risk_level") in ("high", "critical"):
                    recommendation = "manual_review"
                else:
                    recommendation = "auto_approve"

                # Check coherence validity (no coherence-related risk factors)
                coherence_codes = {
                    RiskFactorCode.LOGICAL_INCONSISTENCY.value,
                    RiskFactorCode.CROSS_FIELD_MISMATCH.value,
                    RiskFactorCode.TEMPORAL_ANOMALY.value,
                }
                coherence_valid = not any(
                    rf.get("code") in coherence_codes
                    for rf in risk_analysis.get("risk_factors", [])
                )

                # Document type match
                is_match = (
                    result.get("document_type", "").lower() == document_code.lower()
                )

                # Error details
                error_type = None
                error_message = result.get("error_message")
                if result.get("has_error"):
                    error_type = "extraction_error"

                await conn.fetchval(
                    "SELECT log_gemini_processing("
                    "$1,$2,$3,$4,$5,$6,$7,$8,$9,$10,"
                    "$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,"
                    "$21,$22,$23,$24,$25,$26,$27,$28,$29,$30,$31"
                    ")",
                    sr_id,                                          # p_service_request_id
                    None,                                           # p_document_id
                    uid,                                            # p_user_id
                    document_code,                                  # p_document_code
                    mime_type,                                      # p_mime_type
                    file_size,                                      # p_file_size
                    result.get("processor", "unknown"),             # p_processor
                    settings.GEMINI_PRO_MODEL if self.enabled else None,  # p_gemini_model
                    result.get("document_type"),                    # p_document_type
                    category,                                       # p_document_category
                    result.get("confidence", 0.0),                  # p_classification_confidence
                    json.dumps(extraction),                         # p_extraction_result
                    result.get("confidence", 0.0),                  # p_extraction_confidence
                    fields_extracted,                               # p_fields_extracted
                    fields_missing,                                 # p_fields_missing
                    risk_score_normalized,                          # p_risk_score
                    risk_analysis.get("risk_level", "low"),         # p_risk_level
                    json.dumps(risk_analysis.get("risk_factors", [])),  # p_risk_factors
                    coherence_valid,                                # p_coherence_valid
                    recommendation,                                 # p_recommendation
                    is_match,                                       # p_is_match
                    result.get("processing_time_ms", 0),            # p_processing_time_ms
                    gemini_latency_ms,                              # p_gemini_latency_ms
                    used_fallback,                                  # p_used_fallback
                    fallback_reason,                                # p_fallback_reason
                    result.get("has_error", False),                 # p_has_error
                    error_type,                                     # p_error_type
                    error_message,                                  # p_error_message
                    workflow_code,                                  # p_workflow_code
                    input_tokens,                                   # p_input_tokens
                    output_tokens,                                  # p_output_tokens
                )

                logger.debug(
                    f"[GeminiAudit] Logged {document_code} "
                    f"(processor={result.get('processor')}, "
                    f"risk={risk_analysis.get('risk_level')}, "
                    f"rec={recommendation})"
                )

        except Exception as e:
            # Fire-and-forget: NEVER propagate logging errors
            logger.warning(f"[GeminiAudit] Failed to log processing: {e}")

    # ═══════════════════════════════════════════════════════════════════════════════
    # GEMINI / TESSERACT PROCESSING METHODS
    # ═══════════════════════════════════════════════════════════════════════════════

    async def _process_with_gemini(
        self,
        content: bytes,
        mime_type: str,
        document_code: str,
        schema: Optional[Dict]
    ) -> Dict[str, Any]:
        """
        Process document using Gemini multimodal vision.
        Includes fraud detection and risk indicator extraction.

        Retries once on parse failure (empty extraction) to handle
        transient Gemini response format issues.
        """
        # Build extraction + risk analysis prompt
        prompt = self._build_gemini_prompt(document_code, schema)

        # Prepare image/document part
        document_part = Part.from_data(data=content, mime_type=mime_type)

        # Build content for Gemini
        contents = [document_part, Part.from_text(prompt)]

        max_attempts = 2
        last_response_text = ""
        input_tokens = None
        output_tokens = None

        for attempt in range(1, max_attempts + 1):
            # Call Gemini
            response = await traced_generate_sync(
                self.model, contents,
                feature="ocr",
                generation_config=self.generation_config,
                safety_settings=self.safety_settings,
            )

            # Capture token usage from Vertex AI response
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                input_tokens = getattr(response.usage_metadata, 'prompt_token_count', None)
                output_tokens = getattr(response.usage_metadata, 'candidates_token_count', None)

            # Parse response
            response_text = response.text if response.text else ""
            last_response_text = response_text

            # Extract JSON from response
            extraction, confidence, risk_hints = self._parse_gemini_response(response_text, schema)

            # Defense layer 1: Gemini may return non-dict (string, list, None)
            if not isinstance(extraction, dict):
                logger.warning(
                    f"Gemini attempt {attempt}/{max_attempts}: non-dict extraction "
                    f"({type(extraction).__name__}), coercing to empty dict. "
                    f"document_code={document_code}"
                )
                extraction = {}

            # If we got actual extraction data, stop retrying
            if extraction:
                if attempt > 1:
                    logger.info(
                        f"Gemini retry succeeded on attempt {attempt} "
                        f"for {document_code}"
                    )
                break

            # Empty extraction — retry if we have attempts left
            if attempt < max_attempts:
                logger.warning(
                    f"Gemini attempt {attempt}/{max_attempts}: empty extraction "
                    f"for {document_code}, retrying. "
                    f"response_preview={response_text[:200]}"
                )
                await asyncio.sleep(1)  # Brief backoff

        # Detect document type from response
        detected_type = extraction.pop("_document_type", document_code)

        return {
            "extraction": extraction,
            "confidence": confidence,
            "processor": "gemini",
            "document_type": detected_type,
            "has_error": False,
            "risk_hints": risk_hints,
            "raw_response": last_response_text[:500],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    def _build_gemini_prompt(
        self,
        document_code: str,
        schema: Optional[Dict]
    ) -> str:
        """
        Build extraction + risk analysis prompt for Gemini.
        """
        critical_separation_text = ""

        if schema:
            hints = schema.get("gemini_hints", {})
            doc_description = hints.get("document_description", document_code)
            language = hints.get("language", "es")
            date_format = hints.get("date_format", "DD/MM/YYYY")

            # Build field list from schema
            fields_description = []
            extraction_schema = schema.get("extraction", {})

            for section_name, section in extraction_schema.items():
                section_fields = section.get("fields", {})
                for field_name, field_config in section_fields.items():
                    required = "OBLIGATORIO" if field_config.get("required") else "opcional"
                    field_type = field_config.get("type", "string")
                    pattern = field_config.get("pattern", "")
                    description = field_config.get("description", "")

                    field_desc = f"- {field_name} ({required}, {field_type})"
                    if pattern:
                        field_desc += f" [formato: {pattern}]"
                    if description:
                        field_desc += f": {description}"
                    fields_description.append(field_desc)

            fields_text = "\n".join(fields_description)

            # Build visual zones guidance if present
            visual_zones = hints.get("visual_zones", {})
            visual_zones_text = ""
            if visual_zones:
                vz_lines = [
                    "\n═══════════════════════════════════════════════════════════════════════════════",
                    "📍 GUÍA DE ZONAS (REFERENCIA, NO RESTRICCIÓN):",
                    "═══════════════════════════════════════════════════════════════════════════════",
                    "IMPORTANTE: Estas zonas son indicativas del formato TÍPICO.",
                    "→ PRIORIZA siempre las ETIQUETAS visibles (ej: 'HIJO DE', 'NATURAL DE')",
                    "→ Si un campo no está en la zona indicada, BÚSCALO en todo el documento",
                    "→ Extrae los datos según su CONTEXTO SEMÁNTICO, no solo por posición",
                    ""
                ]
                if isinstance(visual_zones, dict):
                    for face, zones in visual_zones.items():
                        face_label = "CARA FRONTAL (RECTO)" if face == "recto" else "CARA TRASERA (VERSO)"
                        vz_lines.append(f"\n{face_label} (ubicación típica):")
                        for zone in zones:
                            vz_lines.append(f"  • {zone}")
                elif isinstance(visual_zones, list):
                    vz_lines.append("\nZONAS DEL DOCUMENTO (ubicación típica):")
                    for zone in visual_zones:
                        vz_lines.append(f"  • {zone}")
                vz_lines.append("")

                # Add OCR challenges if present
                ocr_challenges = hints.get("ocr_challenges", [])
                if ocr_challenges:
                    vz_lines.append("⚠️ DESAFÍOS COMUNES DE LECTURA:")
                    for challenge in ocr_challenges:
                        vz_lines.append(f"  - {challenge}")
                    vz_lines.append("")

                visual_zones_text = "\n".join(vz_lines)

            # Build critical field separation warnings if present
            critical_sep = hints.get("critical_field_separation", {})
            if critical_sep:
                sep_lines = [
                    "\n═══════════════════════════════════════════════════════════════════════════════",
                    "⚠️  SEPARACIÓN CRÍTICA DE CAMPOS - MUY IMPORTANTE:",
                    "═══════════════════════════════════════════════════════════════════════════════",
                    critical_sep.get("description", ""),
                    ""
                ]
                for field_info in critical_sep.get("same_line_fields", []):
                    sep_lines.append(f"LÍNEA: {field_info.get('line', '')}")
                    sep_lines.append(f"  Ejemplo raw: \"{field_info.get('example_raw', '')}\"")
                    extract_as = field_info.get("extract_as", {})
                    for field, instruction in extract_as.items():
                        sep_lines.append(f"  → {field}: {instruction}")
                    if field_info.get("warning"):
                        sep_lines.append(f"  ⚠️ {field_info.get('warning')}")
                    sep_lines.append("")

                known_cities = critical_sep.get("known_emission_cities", [])
                if known_cities:
                    sep_lines.append(f"Ciudades de emisión conocidas (NO incluir en nombres): {', '.join(known_cities)}")
                    sep_lines.append("")

                # Verso filiation layout (structural hints for parent names)
                verso_layout = critical_sep.get("verso_filiation_layout")
                if verso_layout:
                    sep_lines.append("═══════════════════════════════════════════════════════════════════════════════")
                    sep_lines.append(verso_layout.get("description", ""))
                    for step in verso_layout.get("fixed_order", []):
                        sep_lines.append(f"  {step}")
                    sep_lines.append("")
                    recognition = verso_layout.get("recognition_pattern", "")
                    if recognition:
                        sep_lines.append(f"PATRÓN DE RECONOCIMIENTO: {recognition}")
                        sep_lines.append("")
                    example = verso_layout.get("example")
                    if example:
                        sep_lines.append("EJEMPLO (label visible):")
                        sep_lines.append(f"  {example.get('label_visible', '').replace(chr(10), chr(10) + '  ')}")
                        sep_lines.append("EJEMPLO (label ABSENT - mismo resultado):")
                        sep_lines.append(f"  {example.get('label_absent', '').replace(chr(10), chr(10) + '  ')}")
                        extract_as = example.get("extract_as", {})
                        for field, instruction in extract_as.items():
                            sep_lines.append(f"  → {field}: {instruction}")
                        sep_lines.append("")

                critical_separation_text = "\n".join(sep_lines)
        else:
            doc_description = document_code
            language = "es"
            fields_text = "- Extrae todos los campos visibles del documento"
            visual_zones_text = ""
            critical_separation_text = ""

        prompt = f"""Eres un experto en análisis de documentos oficiales. Analiza este documento para:
1. EXTRACCIÓN de datos
2. CLASIFICACIÓN del tipo de documento
3. DETECCIÓN DE FRAUDE y anomalías

═══════════════════════════════════════════════════════════════════════════════
TIPO DE DOCUMENTO ESPERADO: {doc_description}
IDIOMA DEL DOCUMENTO: {language}
═══════════════════════════════════════════════════════════════════════════════

🎯 ESTRATEGIA DE EXTRACCIÓN (PRIORIDAD):
1. BUSCA las ETIQUETAS/LABELS visibles en el documento (ej: "HIJO DE", "APELLIDOS")
2. EXTRAE el valor asociado a cada etiqueta encontrada
3. Si una etiqueta está parcialmente oculta pero el VALOR es visible, extráelo
4. Las zonas visuales son GUÍAS, no restricciones - busca en TODO el documento
5. Usa el CONTEXTO para inferir campos si las etiquetas no son claras

CAMPOS A EXTRAER:
{fields_text}
{visual_zones_text}
{critical_separation_text}
═══════════════════════════════════════════════════════════════════════════════
ANÁLISIS DE RIESGO Y FRAUDE - DETECTAR:
═══════════════════════════════════════════════════════════════════════════════

1. MANIPULACIÓN DIGITAL:
   - Signos de edición con Photoshop/software
   - Píxeles irregulares o artefactos
   - Inconsistencias en la resolución

2. TIPOGRAFÍA:
   - Fuentes inconsistentes
   - Caracteres mal alineados
   - Texto añadido posteriormente

3. ELEMENTOS OFICIALES:
   - ¿Tiene firma? ¿Parece auténtica?
   - ¿Tiene sello oficial? ¿Es legible?
   - ¿Tiene holograma o elementos de seguridad?

4. CALIDAD DEL DOCUMENTO:
   - ¿Es legible?
   - ¿Hay zonas borrosas o cortadas?
   - ¿Se ve completo?

5. PATRONES SOSPECHOSOS:
   - Fechas ilógicas
   - Números de documento con formato inválido
   - Información que no corresponde al tipo de documento

═══════════════════════════════════════════════════════════════════════════════
RESPONDE ÚNICAMENTE con JSON válido (sin explicaciones):
═══════════════════════════════════════════════════════════════════════════════

{{
    "_document_type": "tipo_detectado_real",
    "_confidence": 0.85,
    "_risk_hints": {{
        "digital_manipulation_detected": false,
        "manipulation_details": {{}},
        "inconsistent_fonts": false,
        "font_details": {{}},
        "low_quality": false,
        "quality_details": {{}},
        "missing_signature": false,
        "missing_stamp": false,
        "suspicious_patterns": [],
        "altered_dates_detected": false,
        "altered_dates_details": {{}},
        "photo_appears_manipulated": false,
        "document_appears_expired": false,
        "expiry_date_detected": null,
        "overall_authenticity": "high|medium|low",
        "authenticity_score": 0.9,
        "notes": ""
    }},
    "campo1": "valor1",
    "campo2": "valor2"
}}

INSTRUCCIONES CRÍTICAS:
- _risk_hints es OBLIGATORIO - SIEMPRE debe estar presente con TODOS los campos
- Si un campo no es visible o legible, usa null
- Para fechas, usa formato ISO (YYYY-MM-DD)
- Para números de documento, elimina espacios
- Sé conservador con _confidence: baja si hay dudas
- authenticity_score: 0.0 (muy sospechoso) a 1.0 (completamente auténtico)
- Si detectas CUALQUIER indicio de fraude, marca los campos correspondientes en _risk_hints
- altered_dates_detected: true si las fechas parecen modificadas visualmente
- photo_appears_manipulated: true si la foto parece editada o pegada
- document_appears_expired: true si la fecha de expiración ya pasó
- expiry_date_detected: la fecha de expiración si es visible (formato ISO)

IMPORTANTE: Analiza TODOS los aspectos de seguridad del documento, incluso si parece legítimo.
"""

        return prompt

    def _parse_gemini_response(
        self,
        response_text: str,
        schema: Optional[Dict]
    ) -> Tuple[Dict[str, Any], float, Dict[str, Any]]:
        """
        Parse Gemini response and extract JSON including risk hints.

        Returns:
            Tuple of (extraction_dict, confidence, risk_hints)
        """
        risk_hints = {}

        try:
            # Try to find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                logger.warning("No JSON found in Gemini response")
                return {}, 0.0, {}

            json_str = json_match.group()
            extraction = json.loads(json_str)

            # Extract confidence
            confidence = extraction.pop("_confidence", 0.5)
            if isinstance(confidence, str):
                confidence = float(confidence)

            # Extract risk hints
            risk_hints = extraction.pop("_risk_hints", {})

            # Validate extraction if schema provided
            if schema:
                confidence = self._validate_extraction(extraction, schema, confidence)

            return extraction, confidence, risk_hints

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini JSON response: {e}")
            return {}, 0.0, {}
        except Exception as e:
            logger.error(f"Error parsing Gemini response: {e}")
            return {}, 0.0, {}

    def _validate_extraction(
        self,
        extraction: Dict[str, Any],
        schema: Dict,
        base_confidence: float
    ) -> float:
        """Validate extraction against schema and adjust confidence."""
        extraction_schema = schema.get("extraction", {})
        required_fields = []
        total_fields = 0

        # Collect required fields
        for section_name, section in extraction_schema.items():
            section_fields = section.get("fields", {})
            for field_name, field_config in section_fields.items():
                total_fields += 1
                if field_config.get("required"):
                    required_fields.append(field_name)

        # Count extracted fields
        extracted_count = sum(
            1 for k, v in extraction.items()
            if v is not None and v != "" and not k.startswith("_")
        )

        # Count required fields extracted
        required_extracted = sum(
            1 for field in required_fields
            if field in extraction and extraction[field]
        )

        # Adjust confidence based on completeness
        if required_fields:
            required_ratio = required_extracted / len(required_fields)
            base_confidence = base_confidence * (0.5 + 0.5 * required_ratio)

        # Validate patterns
        for section_name, section in extraction_schema.items():
            section_fields = section.get("fields", {})
            for field_name, field_config in section_fields.items():
                if field_name in extraction and extraction[field_name]:
                    pattern = field_config.get("pattern")
                    if pattern:
                        if not re.match(pattern, str(extraction[field_name])):
                            base_confidence *= 0.9

        return min(1.0, max(0.0, base_confidence))

    async def _process_with_tesseract(
        self,
        content: bytes,
        mime_type: str,
        document_code: str,
        schema: Optional[Dict]
    ) -> Dict[str, Any]:
        """Process document using Tesseract OCR + regex extraction."""
        # Extract text using OCR service
        ocr_result = await ocr_service.extract_text(
            file_content=content,
            file_type=mime_type,
            provider="tesseract_server",
            language="spa",
            document_type=document_code
        )

        if not ocr_result.success or not ocr_result.text:
            return {
                "extraction": {},
                "confidence": 0.0,
                "processor": "tesseract",
                "document_type": document_code,
                "has_error": True,
                "error_message": "OCR extraction failed"
            }

        # Extract fields using regex patterns from schema
        extraction = {}
        pattern_matches = 0
        total_patterns = 0

        if schema:
            tesseract_patterns = schema.get("tesseract_patterns", {})

            for field_name, patterns in tesseract_patterns.items():
                total_patterns += 1

                for pattern in patterns:
                    try:
                        match = re.search(pattern, ocr_result.text, re.IGNORECASE | re.MULTILINE)
                        if match:
                            value = match.group(1) if match.groups() else match.group()
                            extraction[field_name] = value.strip()
                            pattern_matches += 1
                            break
                    except re.error as e:
                        logger.warning(f"Invalid regex pattern for {field_name}: {e}")

        # Calculate confidence
        ocr_confidence = ocr_result.confidence
        pattern_confidence = pattern_matches / total_patterns if total_patterns > 0 else 0.5
        confidence = (ocr_confidence * 0.4) + (pattern_confidence * 0.6)

        return {
            "extraction": extraction,
            "confidence": confidence,
            "processor": "tesseract",
            "document_type": document_code,
            "has_error": False,
            "ocr_confidence": ocr_confidence,
            "pattern_matches": pattern_matches,
            "total_patterns": total_patterns,
            "raw_text_length": len(ocr_result.text)
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # VAULT POST-PROCESSING METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def post_process_for_vault(
        self,
        extraction_result: Dict[str, Any],
        document_code: str,
        user_id: str,
        db  # asyncpg.Connection
    ) -> Dict[str, Any]:
        """
        Post-process extraction results for the user document vault.

        Takes raw Gemini extraction output and derives structured metadata
        suitable for vault storage: category, dates, holder info, document
        number, and workflow tags.

        Args:
            extraction_result: Raw extraction dict from Gemini (must contain 'extraction' key)
            document_code: The document type code (e.g., 'dip', 'pasaporte', 'contrato_onrc')
            user_id: UUID of the document owner
            db: asyncpg connection for workflow tag derivation

        Returns:
            Dict with keys: category, expiry_date, issue_date, holder_name,
            document_number, workflow_tags, detected_type
        """
        extraction = extraction_result.get("extraction", {})
        detected_type = extraction_result.get("document_type", document_code)
        code_lower = document_code.lower()

        # 1. Category from DOCUMENT_CATEGORY_MAP
        category = DOCUMENT_CATEGORY_MAP.get(code_lower, "other")

        # 2. Expiry date
        expiry_date = self._extract_date_from_paths(extraction, [
            "fecha_caducidad", "fecha_expiracion", "fecha_vencimiento",
            "validity.fecha_caducidad", "validity.expiry_date",
            "datos_personales.fecha_caducidad",
            "vigencia.fecha_fin", "vigencia.hasta",
            "date_expiration", "expiry_date", "valid_until",
        ])

        # 3. Issue date
        issue_date = self._extract_date_from_paths(extraction, [
            "fecha_expedicion", "fecha_emision", "fecha_otorgamiento",
            "datos_personales.fecha_expedicion",
            "vigencia.fecha_inicio", "vigencia.desde",
            "date_emission", "issue_date", "fecha",
            "certificacion.fecha", "datos_documento.fecha",
        ])

        # 4. Holder name
        holder_name = self._extract_text_from_paths(extraction, [
            "nombre_completo", "full_name", "titular",
            "datos_personales.nombre_completo",
            "datos_personales.apellidos_nombre",
            "datos_personales.nombres", "datos_personales.apellidos",
            "nombre", "apellidos_nombre",
            "contratante.nombre", "solicitante.nombre",
            "interesado.nombre_completo",
        ])

        # 5. Document number
        document_number = self._extract_text_from_paths(extraction, [
            "numero_documento", "numero", "numero_pasaporte",
            "datos_personales.numero_documento",
            "datos_personales.numero_pasaporte",
            "datos_personales.nie", "datos_personales.nif",
            "numero_contrato", "numero_certificado",
            "numero_expediente", "referencia",
            "matricula", "numero_matricula",
        ])

        # 6. Workflow tags (which workflows require this document)
        workflow_tags = await self._derive_workflow_tags(db, document_code, detected_type)

        return {
            "category": category,
            "expiry_date": expiry_date.isoformat() if expiry_date else None,
            "issue_date": issue_date.isoformat() if issue_date else None,
            "holder_name": holder_name,
            "document_number": document_number,
            "workflow_tags": workflow_tags,
            "detected_type": detected_type,
        }

    def _extract_date_from_paths(
        self, extraction: Dict[str, Any], paths: List[str]
    ) -> Optional[date]:
        """
        Try to extract a date from multiple possible field paths in extraction data.

        Supports nested dict access via dot notation (e.g., 'datos_personales.fecha_caducidad').
        Handles common date formats: DD/MM/YYYY, YYYY-MM-DD, DD-MM-YYYY, DD.MM.YYYY.

        Returns:
            A date object if successfully parsed, None otherwise.
        """
        for path in paths:
            value = self._resolve_nested_path(extraction, path)
            if not value or not isinstance(value, str):
                continue

            value = value.strip()
            if not value or value.lower() in ("n/a", "no disponible", "-", ""):
                continue

            # Try multiple date formats
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
                try:
                    parsed = datetime.strptime(value, fmt).date()
                    # Sanity check: year between 1900 and 2100
                    if 1900 <= parsed.year <= 2100:
                        return parsed
                except ValueError:
                    continue

            # Try partial date match with regex (e.g., "12 de enero de 2025")
            match = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", value)
            if match:
                try:
                    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                        return date(year, month, day)
                except (ValueError, OverflowError):
                    pass

        return None

    def _extract_text_from_paths(
        self, extraction: Dict[str, Any], paths: List[str]
    ) -> Optional[str]:
        """
        Extract first non-empty text value from multiple possible paths.

        Supports nested dict access via dot notation.

        Returns:
            The first non-empty string found, or None.
        """
        for path in paths:
            value = self._resolve_nested_path(extraction, path)
            if value and isinstance(value, str):
                cleaned = value.strip()
                if cleaned and cleaned.lower() not in ("n/a", "no disponible", "-"):
                    return cleaned
        return None

    @staticmethod
    def _resolve_nested_path(data: Dict[str, Any], path: str) -> Optional[Any]:
        """
        Resolve a dot-separated path in a nested dict.

        Example: _resolve_nested_path({"a": {"b": "val"}}, "a.b") -> "val"
        """
        parts = path.split(".")
        current = data
        for part in parts:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
            if current is None:
                return None
        return current

    async def _derive_workflow_tags(
        self,
        db,
        document_code: str,
        detected_type: str
    ) -> List[Dict[str, str]]:
        """
        Derive workflow tags from workflow_document_requirements table.

        Finds all workflows that require a document matching this document_code,
        returning a list of {workflow_code, workflow_name} dicts.

        Args:
            db: asyncpg connection
            document_code: The document type code
            detected_type: The detected document type from extraction

        Returns:
            List of dicts with workflow_code and workflow_name keys.
        """
        if not db:
            return []

        try:
            query = """
                SELECT DISTINCT
                    wdr.workflow_code,
                    wdr.document_code,
                    wdr.is_required
                FROM workflow_document_requirements wdr
                WHERE wdr.is_active = TRUE
                  AND (wdr.document_code = $1 OR wdr.document_code = $2)
                ORDER BY wdr.workflow_code
            """
            rows = await db.fetch(query, document_code, detected_type)
            return [
                {
                    "workflow_code": row["workflow_code"],
                    "document_code": row["document_code"],
                    "is_required": row["is_required"],
                    "relevance": 1.0,
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning(
                f"Failed to derive workflow tags for {document_code}: {e}"
            )
            return []


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

gemini_document_processor = GeminiDocumentProcessor()
