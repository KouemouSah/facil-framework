"""
Enums for service_requests module.
Must match database enums from migration 020.
"""
from enum import Enum


class ServiceRequestStatus(str, Enum):
    """
    Status enum matching database service_request_status_enum.
    See migration 020_service_requests_base.sql
    """
    # Phase initiale
    DRAFT = "DRAFT"
    TIMBRES_PENDING = "TIMBRES_PENDING"
    TIMBRES_PAID = "TIMBRES_PAID"

    # Phase soumission
    SUBMITTED = "SUBMITTED"
    DOCUMENTS_REQUIRED = "DOCUMENTS_REQUIRED"

    # Phase validation
    UNDER_REVIEW = "UNDER_REVIEW"
    DOSSIER_VALIDE = "DOSSIER_VALIDE"
    REJECTED = "REJECTED"

    # Phase Nota de Ingreso
    PENDING_NOTA_INGRESO = "PENDING_NOTA_INGRESO"
    NOTA_UPLOADED = "NOTA_UPLOADED"

    # Phase paiement principal
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAYMENT_PROCESSING = "PAYMENT_PROCESSING"
    PAID = "PAID"
    PAYMENT_FAILED = "PAYMENT_FAILED"

    # Phase finale
    CITA_SCHEDULED = "CITA_SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class ServiceRequestPriority(str, Enum):
    """Priority enum matching database service_request_priority_enum"""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class SolicitudType(str, Enum):
    """Type of request: new, renewal, or duplicate"""
    EXPEDICION = "expedicion"
    RENOVACION = "renovacion"
    DUPLICADO = "duplicado"


class ExtractionStatus(str, Enum):
    """Document extraction status"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"


class WorkflowCode(str, Enum):
    """
    Workflow codes for all service request types.
    APPLICATION-LEVEL: DB stores as varchar(100), enum for type safety and validation.
    Values must match entries in workflow_tariffs.workflow_code.
    """
    # === PASAPORTE (5 types) - Entité: CNEDOGE ===
    PASAPORTE_NUEVO = "PASAPORTE_NUEVO"
    PASAPORTE_RENOVACION = "PASAPORTE_RENOVACION"
    PASAPORTE_PERDIDA = "PASAPORTE_PERDIDA"
    PASAPORTE_ROBO = "PASAPORTE_ROBO"
    PASAPORTE_DETERIORO = "PASAPORTE_DETERIORO"

    # === RESIDENCIA (2 types) - Entité: EXTRANJERIA ===
    RESIDENCIA_PRIMERA_VEZ = "RESIDENCIA_PRIMERA_VEZ"
    RESIDENCIA_RENOVACION = "RESIDENCIA_RENOVACION"

    # === TRAMITES VISADO (4 types) - Entité: EXTRANJERIA ===
    PRORROGA_VISADO = "PRORROGA_VISADO"
    VISADO_ALTERNATIVO = "VISADO_ALTERNATIVO"
    PERMANENCIA_EXTRANJERIA = "PERMANENCIA_EXTRANJERIA"
    SALIDA_VISADO_VENCIDO = "SALIDA_VISADO_VENCIDO"

    # === VEHICULO (7 types) - Entités: DGT + OFIVE + ITVE ===
    VEHICULO_PRIMERA_MATRICULACION = "VEHICULO_PRIMERA_MATRICULACION"
    VEHICULO_TRANSFERENCIA = "VEHICULO_TRANSFERENCIA"
    VEHICULO_RENOVACION_CUVE = "VEHICULO_RENOVACION_CUVE"
    VEHICULO_RENOVACION_ITV = "VEHICULO_RENOVACION_ITV"
    VEHICULO_DUPLICADO_PERMISO = "VEHICULO_DUPLICADO_PERMISO"
    VEHICULO_DUPLICADO_CUVE = "VEHICULO_DUPLICADO_CUVE"
    VEHICULO_CAMBIO_CARACTERISTICAS = "VEHICULO_CAMBIO_CARACTERISTICAS"

    # === CONTRATO (7 types) - Entité: ONRC ===
    CONTRATO_OBRA = "CONTRATO_OBRA"
    CONTRATO_SERVICIO = "CONTRATO_SERVICIO"
    CONTRATO_SUMINISTRO = "CONTRATO_SUMINISTRO"
    CONTRATO_CONCESION = "CONTRATO_CONCESION"
    CONTRATO_JOINT_VENTURE = "CONTRATO_JOINT_VENTURE"
    CONTRATO_ARRENDAMIENTO = "CONTRATO_ARRENDAMIENTO"
    CONTRATO_OTRO = "CONTRATO_OTRO"

    # === CONDUCIR (5 types) - Entité: DGT ===
    CONDUCIR_NUEVO = "CONDUCIR_NUEVO"
    CONDUCIR_CANJE = "CONDUCIR_CANJE"
    CONDUCIR_RENOVACION = "CONDUCIR_RENOVACION"
    CONDUCIR_DUPLICADO = "CONDUCIR_DUPLICADO"
    CONDUCIR_EXTENSION = "CONDUCIR_EXTENSION"

    # === FUNCION PUBLICA (5 workflows) - Entité: MINFP ===
    FP_VERIFICACION_FUNCIONARIO = "FP_VERIFICACION_FUNCIONARIO"
    FP_CARNET_FUNCIONARIO = "FP_CARNET_FUNCIONARIO"
    FP_PROMOCION_ADMINISTRATIVA = "FP_PROMOCION_ADMINISTRATIVA"
    FP_PERMISO_EXTRAORDINARIO = "FP_PERMISO_EXTRAORDINARIO"
    FP_CERTIFICADO_ADMINISTRATIVO = "FP_CERTIFICADO_ADMINISTRATIVO"

    # === BUNDLE / OMS (1 type) - Entité: TESORO ===
    BUNDLE_PAYMENT = "BUNDLE_PAYMENT"


class DocumentConditionType(str, Enum):
    """
    Document requirement condition types.
    MAPS TO DATABASE: document_condition_type_enum
    """
    ALWAYS = "always"
    AGE_LESS_THAN = "age_less_than"
    AGE_GREATER_THAN = "age_greater_than"
    IS_RENEWAL = "is_renewal"
    IS_NEW = "is_new"
    IS_DUPLICATE = "is_duplicate"
    HAS_PREVIOUS = "has_previous"
    IS_MINOR = "is_minor"
    IS_ADULT = "is_adult"
    IS_FOREIGN = "is_foreign"
    IS_NATIONAL = "is_national"
    CUSTOM = "custom"


# === APPLICATION-LEVEL ENUMS (not in DB, for validation only) ===

class WorkflowCategory(str, Enum):
    """
    Categories for grouping workflows in citizen UI.
    APPLICATION-LEVEL: Not stored as DB enum (DB = varchar(50)), for UI grouping and filtering.
    Must stay aligned with:
      - Admin dropdown: packages/web/src/modules/service-requests-admin/types/index.ts (WORKFLOW_CATEGORIES_MAP)
      - Citizen UI: packages/web/src/app/[locale]/(dashboard)/dashboard/service-requests/new/page.tsx (CATEGORY_CONFIG)
    """
    IDENTIDAD = "IDENTIDAD"
    EXTRANJERIA = "EXTRANJERIA"
    VEHICULOS = "VEHICULOS"
    CONTRATOS = "CONTRATOS"
    CONDUCCION = "CONDUCCION"
    FUNCION_PUBLICA = "FUNCION_PUBLICA"
    REGISTRO_CIVIL = "REGISTRO_CIVIL"
    COMERCIO = "COMERCIO"
    GENERAL = "GENERAL"  # Fallback for generic workflows
    OTROS = "OTROS"      # Other uncategorized services


class EntityCode(str, Enum):
    """
    Entity codes responsible for processing workflows.
    APPLICATION-LEVEL: DB stores as varchar(50), enum for validation.
    Must stay aligned with `entities` table codes in database.
    """
    CNEDOGE = "CNEDOGE"                    # Centro Nacional de Expedición de Documentos
    EXTRANJERIA = "EXTRANJERIA"            # Dirección General de Extranjería
    DGT = "DGT"                            # Dirección General de Tráfico
    OFIVE = "OFIVE"                        # Oficina de Vehículos
    ITVE = "ITVE"                          # Inspección Técnica de Vehículos
    ONRC = "ONRC"                          # Oficina Nacional de Registro de Contratos
    MINFP = "MINFP"                        # Ministerio de Función Pública
    TESORO = "TESORO"                      # Tesoro Público (OMS bundle payments)
    AYUNTAMIENTO = "AYUNTAMIENTO"          # Ayuntamiento (municipal obligations)
    CAMARA_COMERCIO = "CAMARA_COMERCIO"    # Cámara de Comercio (chamber obligations)
    GENERAL = "GENERAL"                    # Generic/unassigned entity for generic workflows


class TariffType(str, Enum):
    """
    Types of tariff calculation.
    APPLICATION-LEVEL: Not a DB column, used for service layer logic.
    """
    FIXED = "FIXED"              # Montant fixe (amount in workflow_tariffs)
    RBC = "RBC"                  # Risk-Based Calculator (véhicules)
    PERCENTAGE = "PERCENTAGE"    # Pourcentage de la valeur
    NOTA_INGRESO = "NOTA_INGRESO"  # Basé sur Nota de Ingreso (Trésor)
