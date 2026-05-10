"""Funcionario module models."""

from .verificacion import (
    VerificacionCreate,
    VerificacionResponse,
    VerificacionStatus,
    VerificacionListResponse,
    VerificacionProcessRequest,
    BatchApproveRequest,
    BatchApproveResponse,
    DocumentoTipoPrueba,
)

__all__ = [
    "VerificacionCreate",
    "VerificacionResponse",
    "VerificacionStatus",
    "VerificacionListResponse",
    "VerificacionProcessRequest",
    "BatchApproveRequest",
    "BatchApproveResponse",
    "DocumentoTipoPrueba",
]
