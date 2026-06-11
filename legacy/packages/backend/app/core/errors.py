"""
Internationalized Error System — Standardized error codes + multilingual messages.

Architecture:
1. ErrorCode enum — stable codes returned in API responses
2. ERROR_CATALOG — translations for each code (es/fr/en)
3. TranslatedException — HTTPException subclass with error code
4. translate_error_detail() — translates known messages for legacy code
5. error_translation_handler — exception handler middleware

Usage (new code):
    from app.core.errors import TranslatedException, ErrorCode
    raise TranslatedException(ErrorCode.NOT_FOUND, entity="service request")

Usage (legacy — automatic via middleware):
    raise HTTPException(status_code=404, detail="Service request not found")
    # Middleware will translate based on Accept-Language header
"""

from enum import Enum
from typing import Optional
from fastapi import HTTPException


class ErrorCode(str, Enum):
    """Stable error codes returned in API response body."""

    # --- Generic ---
    NOT_FOUND = "ERR_NOT_FOUND"
    ACCESS_DENIED = "ERR_ACCESS_DENIED"
    UNAUTHORIZED = "ERR_UNAUTHORIZED"
    FORBIDDEN = "ERR_FORBIDDEN"
    VALIDATION_FAILED = "ERR_VALIDATION"
    CONFLICT = "ERR_CONFLICT"
    RATE_LIMITED = "ERR_RATE_LIMITED"
    SERVER_ERROR = "ERR_SERVER_ERROR"
    SERVICE_UNAVAILABLE = "ERR_SERVICE_UNAVAILABLE"
    BAD_REQUEST = "ERR_BAD_REQUEST"

    # --- Auth ---
    AUTH_REQUIRED = "ERR_AUTH_REQUIRED"
    TOKEN_EXPIRED = "ERR_TOKEN_EXPIRED"
    INVALID_CREDENTIALS = "ERR_INVALID_CREDENTIALS"
    INVALID_VERIFICATION = "ERR_INVALID_VERIFICATION"
    TOO_MANY_ATTEMPTS = "ERR_TOO_MANY_ATTEMPTS"
    ACCOUNT_SUSPENDED = "ERR_ACCOUNT_SUSPENDED"
    ACCOUNT_EXISTS = "ERR_ACCOUNT_EXISTS"

    # --- Entity ---
    USER_NOT_FOUND = "ERR_USER_NOT_FOUND"
    AGENT_NOT_FOUND = "ERR_AGENT_NOT_FOUND"
    SERVICE_NOT_FOUND = "ERR_SERVICE_NOT_FOUND"
    DECLARATION_NOT_FOUND = "ERR_DECLARATION_NOT_FOUND"
    PAYMENT_NOT_FOUND = "ERR_PAYMENT_NOT_FOUND"
    DOCUMENT_NOT_FOUND = "ERR_DOCUMENT_NOT_FOUND"
    COMPANY_NOT_FOUND = "ERR_COMPANY_NOT_FOUND"
    REQUEST_NOT_FOUND = "ERR_REQUEST_NOT_FOUND"
    BUNDLE_NOT_FOUND = "ERR_BUNDLE_NOT_FOUND"
    TEMPLATE_NOT_FOUND = "ERR_TEMPLATE_NOT_FOUND"
    INSPECTION_NOT_FOUND = "ERR_INSPECTION_NOT_FOUND"
    TRANSLATION_NOT_FOUND = "ERR_TRANSLATION_NOT_FOUND"

    # --- Business Logic ---
    NO_FIELDS_TO_UPDATE = "ERR_NO_FIELDS"
    STATUS_CHANGED = "ERR_STATUS_CHANGED"
    ALREADY_PROCESSED = "ERR_ALREADY_PROCESSED"
    NOT_ASSIGNED = "ERR_NOT_ASSIGNED"
    SUPERVISOR_REQUIRED = "ERR_SUPERVISOR_REQUIRED"
    ADMIN_REQUIRED = "ERR_ADMIN_REQUIRED"
    PERMISSION_DENIED = "ERR_PERMISSION_DENIED"
    PDF_FAILED = "ERR_PDF_FAILED"
    UPLOAD_FAILED = "ERR_UPLOAD_FAILED"
    NOT_MEMBER = "ERR_NOT_MEMBER"
    PROVIDER_NOT_CONFIGURED = "ERR_PROVIDER_NOT_CONFIGURED"

    # --- Database (asyncpg mapping, Phase 4) ---
    DB_UNIQUE_VIOLATION = "ERR_DB_UNIQUE_VIOLATION"
    DB_CHECK_VIOLATION = "ERR_DB_CHECK_VIOLATION"
    DB_FK_VIOLATION = "ERR_DB_FK_VIOLATION"
    DB_NOT_NULL_VIOLATION = "ERR_DB_NOT_NULL_VIOLATION"
    DB_SERIALIZATION_FAILURE = "ERR_DB_SERIALIZATION"
    DB_DEADLOCK = "ERR_DB_DEADLOCK"
    DB_LOCK_TIMEOUT = "ERR_DB_LOCK_TIMEOUT"
    DB_STATEMENT_TIMEOUT = "ERR_DB_STATEMENT_TIMEOUT"
    DB_CONNECTION_ERROR = "ERR_DB_CONNECTION"


# ---------------------------------------------------------------------------
# Multilingual message catalog
# ---------------------------------------------------------------------------

_T = dict[str, str]  # { "es": "...", "fr": "...", "en": "..." }

ERROR_CATALOG: dict[ErrorCode, _T] = {
    # Generic
    ErrorCode.NOT_FOUND: {
        "es": "Recurso no encontrado",
        "fr": "Ressource introuvable",
        "en": "Resource not found",
    },
    ErrorCode.ACCESS_DENIED: {
        "es": "Acceso denegado",
        "fr": "Accès refusé",
        "en": "Access denied",
    },
    ErrorCode.UNAUTHORIZED: {
        "es": "No autorizado",
        "fr": "Non autorisé",
        "en": "Unauthorized",
    },
    ErrorCode.FORBIDDEN: {
        "es": "No tienes permiso para esta acción",
        "fr": "Vous n'avez pas la permission pour cette action",
        "en": "You don't have permission for this action",
    },
    ErrorCode.VALIDATION_FAILED: {
        "es": "Error de validación. Verifica los datos.",
        "fr": "Erreur de validation. Vérifiez les données.",
        "en": "Validation error. Please check the data.",
    },
    ErrorCode.CONFLICT: {
        "es": "Conflicto con el estado actual del recurso",
        "fr": "Conflit avec l'état actuel de la ressource",
        "en": "Conflict with the current resource state",
    },
    ErrorCode.RATE_LIMITED: {
        "es": "Demasiadas solicitudes. Espera un momento.",
        "fr": "Trop de requêtes. Veuillez patienter.",
        "en": "Too many requests. Please wait.",
    },
    ErrorCode.SERVER_ERROR: {
        "es": "Error del servidor. Inténtelo más tarde.",
        "fr": "Erreur du serveur. Réessayez plus tard.",
        "en": "Server error. Please try again later.",
    },
    ErrorCode.SERVICE_UNAVAILABLE: {
        "es": "Servicio temporalmente no disponible. Inténtelo de nuevo.",
        "fr": "Service temporairement indisponible. Réessayez.",
        "en": "Service temporarily unavailable. Please try again.",
    },
    ErrorCode.BAD_REQUEST: {
        "es": "Solicitud inválida",
        "fr": "Requête invalide",
        "en": "Invalid request",
    },

    # Auth
    ErrorCode.AUTH_REQUIRED: {
        "es": "Autenticación requerida",
        "fr": "Authentification requise",
        "en": "Authentication required",
    },
    ErrorCode.TOKEN_EXPIRED: {
        "es": "Tu sesión ha expirado. Inicia sesión de nuevo.",
        "fr": "Votre session a expiré. Veuillez vous reconnecter.",
        "en": "Your session has expired. Please sign in again.",
    },
    ErrorCode.INVALID_CREDENTIALS: {
        "es": "Credenciales inválidas",
        "fr": "Identifiants invalides",
        "en": "Invalid credentials",
    },
    ErrorCode.INVALID_VERIFICATION: {
        "es": "Código de verificación inválido o expirado",
        "fr": "Code de vérification invalide ou expiré",
        "en": "Invalid or expired verification code",
    },
    ErrorCode.TOO_MANY_ATTEMPTS: {
        "es": "Demasiados intentos. Espera unos minutos.",
        "fr": "Trop de tentatives. Veuillez patienter.",
        "en": "Too many attempts. Please wait a few minutes.",
    },
    ErrorCode.ACCOUNT_SUSPENDED: {
        "es": "Cuenta suspendida. Contacta al administrador.",
        "fr": "Compte suspendu. Contactez l'administrateur.",
        "en": "Account suspended. Contact the administrator.",
    },
    ErrorCode.ACCOUNT_EXISTS: {
        "es": "Ya existe una cuenta con este correo",
        "fr": "Un compte existe déjà avec cet email",
        "en": "An account already exists with this email",
    },

    # Entity not found
    ErrorCode.USER_NOT_FOUND: {
        "es": "Usuario no encontrado",
        "fr": "Utilisateur introuvable",
        "en": "User not found",
    },
    ErrorCode.AGENT_NOT_FOUND: {
        "es": "Perfil de agente no encontrado",
        "fr": "Profil d'agent introuvable",
        "en": "Agent profile not found",
    },
    ErrorCode.SERVICE_NOT_FOUND: {
        "es": "Servicio no encontrado",
        "fr": "Service introuvable",
        "en": "Service not found",
    },
    ErrorCode.DECLARATION_NOT_FOUND: {
        "es": "Declaración no encontrada",
        "fr": "Déclaration introuvable",
        "en": "Declaration not found",
    },
    ErrorCode.PAYMENT_NOT_FOUND: {
        "es": "Pago no encontrado",
        "fr": "Paiement introuvable",
        "en": "Payment not found",
    },
    ErrorCode.DOCUMENT_NOT_FOUND: {
        "es": "Documento no encontrado",
        "fr": "Document introuvable",
        "en": "Document not found",
    },
    ErrorCode.COMPANY_NOT_FOUND: {
        "es": "Empresa no encontrada",
        "fr": "Entreprise introuvable",
        "en": "Company not found",
    },
    ErrorCode.REQUEST_NOT_FOUND: {
        "es": "Solicitud no encontrada",
        "fr": "Demande introuvable",
        "en": "Service request not found",
    },
    ErrorCode.BUNDLE_NOT_FOUND: {
        "es": "Paquete no encontrado",
        "fr": "Forfait introuvable",
        "en": "Bundle not found",
    },
    ErrorCode.TEMPLATE_NOT_FOUND: {
        "es": "Plantilla no encontrada",
        "fr": "Modèle introuvable",
        "en": "Template not found",
    },
    ErrorCode.INSPECTION_NOT_FOUND: {
        "es": "Inspección no encontrada",
        "fr": "Inspection introuvable",
        "en": "Inspection not found",
    },
    ErrorCode.TRANSLATION_NOT_FOUND: {
        "es": "Traducción no encontrada",
        "fr": "Traduction introuvable",
        "en": "Translation not found",
    },

    # Business Logic
    ErrorCode.NO_FIELDS_TO_UPDATE: {
        "es": "No hay campos para actualizar",
        "fr": "Aucun champ à mettre à jour",
        "en": "No fields to update",
    },
    ErrorCode.STATUS_CHANGED: {
        "es": "El estado fue modificado por otro agente",
        "fr": "Le statut a été modifié par un autre agent",
        "en": "Status changed by another agent",
    },
    ErrorCode.ALREADY_PROCESSED: {
        "es": "Ya fue procesado",
        "fr": "Déjà traité",
        "en": "Already processed",
    },
    ErrorCode.NOT_ASSIGNED: {
        "es": "La solicitud no está asignada a usted",
        "fr": "La demande ne vous est pas assignée",
        "en": "Request is not assigned to you",
    },
    ErrorCode.SUPERVISOR_REQUIRED: {
        "es": "Acceso de supervisor requerido",
        "fr": "Accès superviseur requis",
        "en": "Supervisor access required",
    },
    ErrorCode.ADMIN_REQUIRED: {
        "es": "Acceso de administrador requerido",
        "fr": "Accès administrateur requis",
        "en": "Admin access required",
    },
    ErrorCode.PERMISSION_DENIED: {
        "es": "No tienes los permisos necesarios",
        "fr": "Vous n'avez pas les permissions nécessaires",
        "en": "You don't have the required permissions",
    },
    ErrorCode.PDF_FAILED: {
        "es": "Error al generar el PDF",
        "fr": "Erreur lors de la génération du PDF",
        "en": "PDF generation failed",
    },
    ErrorCode.UPLOAD_FAILED: {
        "es": "Error al subir el archivo",
        "fr": "Erreur lors du téléchargement du fichier",
        "en": "File upload failed",
    },
    ErrorCode.NOT_MEMBER: {
        "es": "No es miembro de esta empresa",
        "fr": "Vous n'êtes pas membre de cette entreprise",
        "en": "Not a member of this company",
    },
    ErrorCode.PROVIDER_NOT_CONFIGURED: {
        "es": "Proveedor no configurado",
        "fr": "Fournisseur non configuré",
        "en": "Provider not configured",
    },

    # Database (Phase 4) — generic messages that NEVER leak table/constraint names
    ErrorCode.DB_UNIQUE_VIOLATION: {
        "es": "Ya existe un registro con estos datos",
        "fr": "Un enregistrement avec ces données existe déjà",
        "en": "A record with these data already exists",
    },
    ErrorCode.DB_CHECK_VIOLATION: {
        "es": "Los datos no cumplen las reglas de validación",
        "fr": "Les données ne respectent pas les règles de validation",
        "en": "The data do not meet the validation rules",
    },
    ErrorCode.DB_FK_VIOLATION: {
        "es": "Referencia a un registro inexistente",
        "fr": "Référence à un enregistrement inexistant",
        "en": "Reference to a non-existent record",
    },
    ErrorCode.DB_NOT_NULL_VIOLATION: {
        "es": "Falta un campo obligatorio",
        "fr": "Un champ obligatoire est manquant",
        "en": "A required field is missing",
    },
    ErrorCode.DB_SERIALIZATION_FAILURE: {
        "es": "La transacción entró en conflicto con otra. Reintente.",
        "fr": "La transaction est entrée en conflit avec une autre. Réessayez.",
        "en": "The transaction conflicted with another one. Please retry.",
    },
    ErrorCode.DB_DEADLOCK: {
        "es": "Conflicto de bloqueo detectado. Reintente.",
        "fr": "Conflit de verrouillage détecté. Réessayez.",
        "en": "Lock conflict detected. Please retry.",
    },
    ErrorCode.DB_LOCK_TIMEOUT: {
        "es": "El recurso está siendo utilizado. Reintente en unos segundos.",
        "fr": "La ressource est en cours d'utilisation. Réessayez dans quelques secondes.",
        "en": "The resource is currently in use. Retry in a few seconds.",
    },
    ErrorCode.DB_STATEMENT_TIMEOUT: {
        "es": "La operación tardó demasiado. Reintente.",
        "fr": "L'opération a pris trop de temps. Réessayez.",
        "en": "The operation took too long. Please retry.",
    },
    ErrorCode.DB_CONNECTION_ERROR: {
        "es": "No se pudo conectar a la base de datos. Inténtelo más tarde.",
        "fr": "Impossible de se connecter à la base de données. Réessayez plus tard.",
        "en": "Could not connect to the database. Please try again later.",
    },
}


def get_error_message(code: ErrorCode, language: str = "es") -> str:
    """Get translated error message for an error code."""
    lang = language if language in ("es", "fr", "en") else "es"
    entry = ERROR_CATALOG.get(code, {})
    return entry.get(lang, entry.get("en", code.value))


# ---------------------------------------------------------------------------
# TranslatedException — preferred way to raise errors
# ---------------------------------------------------------------------------

class TranslatedException(HTTPException):
    """HTTPException with error code and automatic translation.

    Usage:
        raise TranslatedException(ErrorCode.NOT_FOUND, entity="solicitud")
        raise TranslatedException(ErrorCode.ACCESS_DENIED)
        raise TranslatedException(ErrorCode.VALIDATION_FAILED, detail="Custom msg")
    """

    def __init__(
        self,
        code: ErrorCode,
        status_code: Optional[int] = None,
        detail: Optional[str] = None,
        language: str = "es",
        entity: Optional[str] = None,
    ):
        # Infer status code from error code if not provided
        if status_code is None:
            status_code = _CODE_TO_STATUS.get(code, 500)

        # Get translated message or use custom detail
        if detail is None:
            msg = get_error_message(code, language)
            if entity:
                # Replace generic "Resource" with specific entity name
                msg = msg.replace("Recurso", entity).replace("Resource", entity).replace("Ressource", entity)
        else:
            msg = detail

        super().__init__(status_code=status_code, detail=msg)
        self.error_code = code


_CODE_TO_STATUS: dict[ErrorCode, int] = {
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.ACCESS_DENIED: 403,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.VALIDATION_FAILED: 422,
    ErrorCode.CONFLICT: 409,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.SERVER_ERROR: 500,
    ErrorCode.SERVICE_UNAVAILABLE: 503,
    ErrorCode.BAD_REQUEST: 400,
    ErrorCode.AUTH_REQUIRED: 401,
    ErrorCode.TOKEN_EXPIRED: 401,
    ErrorCode.INVALID_CREDENTIALS: 401,
    ErrorCode.INVALID_VERIFICATION: 400,
    ErrorCode.TOO_MANY_ATTEMPTS: 429,
    ErrorCode.ACCOUNT_SUSPENDED: 403,
    ErrorCode.ACCOUNT_EXISTS: 409,
    ErrorCode.USER_NOT_FOUND: 404,
    ErrorCode.AGENT_NOT_FOUND: 404,
    ErrorCode.SERVICE_NOT_FOUND: 404,
    ErrorCode.DECLARATION_NOT_FOUND: 404,
    ErrorCode.PAYMENT_NOT_FOUND: 404,
    ErrorCode.DOCUMENT_NOT_FOUND: 404,
    ErrorCode.COMPANY_NOT_FOUND: 404,
    ErrorCode.REQUEST_NOT_FOUND: 404,
    ErrorCode.BUNDLE_NOT_FOUND: 404,
    ErrorCode.TEMPLATE_NOT_FOUND: 404,
    ErrorCode.INSPECTION_NOT_FOUND: 404,
    ErrorCode.TRANSLATION_NOT_FOUND: 404,
    ErrorCode.NO_FIELDS_TO_UPDATE: 400,
    ErrorCode.STATUS_CHANGED: 409,
    ErrorCode.ALREADY_PROCESSED: 409,
    ErrorCode.NOT_ASSIGNED: 403,
    ErrorCode.SUPERVISOR_REQUIRED: 403,
    ErrorCode.ADMIN_REQUIRED: 403,
    ErrorCode.PERMISSION_DENIED: 403,
    ErrorCode.PDF_FAILED: 500,
    ErrorCode.UPLOAD_FAILED: 500,
    ErrorCode.NOT_MEMBER: 403,
    ErrorCode.PROVIDER_NOT_CONFIGURED: 503,
}


# ---------------------------------------------------------------------------
# Legacy translation — auto-translate known HTTPException messages
# ---------------------------------------------------------------------------

# Maps English detail strings → (ErrorCode, pattern)
# Used by the middleware to translate legacy errors without code changes
_LEGACY_PATTERNS: dict[str, ErrorCode] = {
    "Service request not found": ErrorCode.REQUEST_NOT_FOUND,
    "Access denied": ErrorCode.ACCESS_DENIED,
    "User not found": ErrorCode.USER_NOT_FOUND,
    "Bundle not found": ErrorCode.BUNDLE_NOT_FOUND,
    "Translation not found": ErrorCode.TRANSLATION_NOT_FOUND,
    "Service temporarily unavailable. Please try again.": ErrorCode.SERVICE_UNAVAILABLE,
    "An unexpected error occurred. Please try again.": ErrorCode.SERVER_ERROR,
    "Entity not found": ErrorCode.NOT_FOUND,
    "Company not found": ErrorCode.COMPANY_NOT_FOUND,
    "Supervisor access required": ErrorCode.SUPERVISOR_REQUIRED,
    "License not found": ErrorCode.NOT_FOUND,
    "Document not found": ErrorCode.DOCUMENT_NOT_FOUND,
    "Declaration not found": ErrorCode.DECLARATION_NOT_FOUND,
    "Agent profile not found": ErrorCode.AGENT_NOT_FOUND,
    "Service not found": ErrorCode.SERVICE_NOT_FOUND,
    "Obligation not found": ErrorCode.NOT_FOUND,
    "No fields to update": ErrorCode.NO_FIELDS_TO_UPDATE,
    "Authentication required": ErrorCode.AUTH_REQUIRED,
    "Target agent not found": ErrorCode.AGENT_NOT_FOUND,
    "Slot configuration not found": ErrorCode.NOT_FOUND,
    "Payment not found": ErrorCode.PAYMENT_NOT_FOUND,
    "Entity location not found": ErrorCode.NOT_FOUND,
    "Admin access required": ErrorCode.ADMIN_REQUIRED,
    "Workflow tariff not found": ErrorCode.NOT_FOUND,
    "Supervisor only": ErrorCode.SUPERVISOR_REQUIRED,
    "Request status changed by another agent": ErrorCode.STATUS_CHANGED,
    "Permission service not available": ErrorCode.SERVICE_UNAVAILABLE,
    "PDF generation failed": ErrorCode.PDF_FAILED,
    "Not found": ErrorCode.NOT_FOUND,
    "No agent profile found for current user": ErrorCode.AGENT_NOT_FOUND,
    "Invalid or expired verification code": ErrorCode.INVALID_VERIFICATION,
    "Inspection not found": ErrorCode.INSPECTION_NOT_FOUND,
    "Config rule not found": ErrorCode.NOT_FOUND,
    "City not found": ErrorCode.NOT_FOUND,
    "Category not found": ErrorCode.NOT_FOUND,
    "Sector not found": ErrorCode.NOT_FOUND,
    "Ministry not found": ErrorCode.NOT_FOUND,
    "Role not found": ErrorCode.NOT_FOUND,
    "Permission not found": ErrorCode.NOT_FOUND,
    "Ticket not found": ErrorCode.NOT_FOUND,
    "Session not found": ErrorCode.NOT_FOUND,
    "Assignment not found": ErrorCode.NOT_FOUND,
    "Zone not found": ErrorCode.NOT_FOUND,
    "Item not found": ErrorCode.NOT_FOUND,
    "Not a member": ErrorCode.NOT_MEMBER,
    "Too many invitations. Please wait before sending more.": ErrorCode.RATE_LIMITED,
    "Too many verification attempts. Please wait 5 minutes.": ErrorCode.TOO_MANY_ATTEMPTS,
    "Too many activation attempts. Please wait.": ErrorCode.TOO_MANY_ATTEMPTS,
    "Too many activation attempts for this email. Please wait.": ErrorCode.TOO_MANY_ATTEMPTS,
    # Spanish legacy messages
    "No autorizado": ErrorCode.UNAUTHORIZED,
    "Verificación no encontrada": ErrorCode.NOT_FOUND,
    "Verificación ya procesada": ErrorCode.ALREADY_PROCESSED,
    "Lote no encontrado": ErrorCode.NOT_FOUND,
    "Error de verificacion / Verification error": ErrorCode.VALIDATION_FAILED,
}


def translate_error_detail(detail: str, language: str) -> tuple[str, Optional[str]]:
    """Translate a legacy HTTPException detail string.

    Returns (translated_detail, error_code) if pattern matches,
    or (original_detail, None) if no match.
    """
    if not isinstance(detail, str):
        return str(detail), None

    # Exact match
    code = _LEGACY_PATTERNS.get(detail)
    if code:
        return get_error_message(code, language), code.value

    # Suffix match: "X not found" pattern
    if detail.endswith(" not found"):
        return get_error_message(ErrorCode.NOT_FOUND, language), ErrorCode.NOT_FOUND.value

    # Suffix match: "X no encontrado/a"
    if detail.endswith(" no encontrado") or detail.endswith(" no encontrada"):
        return get_error_message(ErrorCode.NOT_FOUND, language), ErrorCode.NOT_FOUND.value

    return detail, None
