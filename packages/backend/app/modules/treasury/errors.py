"""
Treasury Module Error Definitions

Provides standardized error codes and user-friendly messages in Spanish
for all treasury operations.
"""

from enum import Enum
from typing import Optional
from fastapi import HTTPException, status


class TreasuryErrorCode(str, Enum):
    """Error codes for treasury operations"""

    # Authentication & Authorization
    NO_AGENT_PROFILE = "TREASURY_001"
    UNAUTHORIZED = "TREASURY_002"
    INSUFFICIENT_PERMISSIONS = "TREASURY_003"

    # Payment Errors
    PAYMENT_NOT_FOUND = "TREASURY_100"

    # Validation Errors
    VALIDATION_FAILED = "TREASURY_200"
    INVALID_PAYMENT_STATUS = "TREASURY_201"
    ALREADY_VALIDATED = "TREASURY_202"
    ALREADY_REJECTED = "TREASURY_203"

    # Rejection Errors
    REJECTION_REASON_REQUIRED = "TREASURY_300"

    # Reconciliation Errors
    TRANSACTION_NOT_FOUND = "TREASURY_400"
    RECONCILIATION_FAILED = "TREASURY_401"
    AMOUNT_MISMATCH = "TREASURY_402"

    # Anomaly Errors
    ANOMALY_NOT_FOUND = "TREASURY_500"
    ANOMALY_ALREADY_RESOLVED = "TREASURY_501"
    COMMENT_REQUIRED = "TREASURY_502"

    # Export Errors
    EXPORT_NOT_FOUND = "TREASURY_600"
    EXPORT_NOT_READY = "TREASURY_601"
    EXPORT_EXPIRED = "TREASURY_602"

    # General Errors
    INVALID_DATE_RANGE = "TREASURY_700"
    INTERNAL_ERROR = "TREASURY_999"


# User-friendly messages in Spanish (primary language for GE users)
ERROR_MESSAGES = {
    # Authentication & Authorization
    TreasuryErrorCode.NO_AGENT_PROFILE: "No tiene un perfil de agente activo. Contacte al administrador.",
    TreasuryErrorCode.UNAUTHORIZED: "No está autorizado para realizar esta acción.",
    TreasuryErrorCode.INSUFFICIENT_PERMISSIONS: "No tiene permisos suficientes para esta operación.",

    # Payment Errors
    TreasuryErrorCode.PAYMENT_NOT_FOUND: "El pago no fue encontrado. Verifique el identificador.",

    # Validation Errors
    TreasuryErrorCode.VALIDATION_FAILED: "No se pudo validar el pago. Intente nuevamente.",
    TreasuryErrorCode.INVALID_PAYMENT_STATUS: "El estado del pago no permite esta operación.",
    TreasuryErrorCode.ALREADY_VALIDATED: "Este pago ya ha sido validado anteriormente.",
    TreasuryErrorCode.ALREADY_REJECTED: "Este pago ya ha sido rechazado.",

    # Rejection Errors
    TreasuryErrorCode.REJECTION_REASON_REQUIRED: "Debe indicar el motivo del rechazo.",

    # Reconciliation Errors
    TreasuryErrorCode.TRANSACTION_NOT_FOUND: "La transacción bancaria no fue encontrada.",
    TreasuryErrorCode.RECONCILIATION_FAILED: "Error al reconciliar la transacción.",
    TreasuryErrorCode.AMOUNT_MISMATCH: "El monto no coincide con la transacción bancaria.",

    # Anomaly Errors
    TreasuryErrorCode.ANOMALY_NOT_FOUND: "La anomalía no fue encontrada.",
    TreasuryErrorCode.ANOMALY_ALREADY_RESOLVED: "Esta anomalía ya ha sido resuelta.",
    TreasuryErrorCode.COMMENT_REQUIRED: "Debe añadir un comentario para esta acción.",

    # Export Errors
    TreasuryErrorCode.EXPORT_NOT_FOUND: "La exportación no fue encontrada.",
    TreasuryErrorCode.EXPORT_NOT_READY: "La exportación aún no está lista. Intente más tarde.",
    TreasuryErrorCode.EXPORT_EXPIRED: "La exportación ha expirado. Genere una nueva.",

    # General Errors
    TreasuryErrorCode.INVALID_DATE_RANGE: "El rango de fechas es inválido.",
    TreasuryErrorCode.INTERNAL_ERROR: "Error interno del servidor. Contacte al soporte técnico.",
}


class TreasuryError(HTTPException):
    """
    Custom exception for treasury operations.

    Provides standardized error responses with:
    - Error code for frontend handling
    - User-friendly message in Spanish
    - Optional technical details for logging
    """

    def __init__(
        self,
        error_code: TreasuryErrorCode,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        detail_override: Optional[str] = None,
        extra_info: Optional[dict] = None
    ):
        message = detail_override or ERROR_MESSAGES.get(error_code, "Error desconocido")

        detail = {
            "code": error_code.value,
            "message": message,
        }

        if extra_info:
            detail["info"] = extra_info

        super().__init__(status_code=status_code, detail=detail)


def raise_treasury_error(
    error_code: TreasuryErrorCode,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    detail_override: Optional[str] = None,
    extra_info: Optional[dict] = None
):
    """Helper function to raise treasury errors"""
    raise TreasuryError(
        error_code=error_code,
        status_code=status_code,
        detail_override=detail_override,
        extra_info=extra_info
    )


# Convenience functions for common errors
def payment_not_found(payment_id: str):
    """Raise payment not found error"""
    raise TreasuryError(
        error_code=TreasuryErrorCode.PAYMENT_NOT_FOUND,
        status_code=status.HTTP_404_NOT_FOUND,
        extra_info={"payment_id": payment_id}
    )


def no_agent_profile():
    """Raise no agent profile error"""
    raise TreasuryError(
        error_code=TreasuryErrorCode.NO_AGENT_PROFILE,
        status_code=status.HTTP_403_FORBIDDEN
    )


def anomaly_not_found(anomaly_id: str):
    """Raise anomaly not found error"""
    raise TreasuryError(
        error_code=TreasuryErrorCode.ANOMALY_NOT_FOUND,
        status_code=status.HTTP_404_NOT_FOUND,
        extra_info={"anomaly_id": anomaly_id}
    )


def export_not_found(export_id: str):
    """Raise export not found error"""
    raise TreasuryError(
        error_code=TreasuryErrorCode.EXPORT_NOT_FOUND,
        status_code=status.HTTP_404_NOT_FOUND,
        extra_info={"export_id": export_id}
    )


def comment_required():
    """Raise comment required error"""
    raise TreasuryError(
        error_code=TreasuryErrorCode.COMMENT_REQUIRED,
        status_code=status.HTTP_400_BAD_REQUEST
    )
