"""
Funcionario Module - Civil Servant Verification and Services.

This module handles:
- Verification of civil servant status (matricula verification)
- Civil servant specific services (carnet, certificado, permiso, promocion)
- Integration with Ministry of Public Function (MINFP)
"""

from .api.verificacion_routes import router as verificacion_router

__all__ = ["verificacion_router"]
