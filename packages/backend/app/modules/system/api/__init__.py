"""system module API — platform info endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.module_registry import discover, enabled_from_env

router = APIRouter(prefix="/api/v1/modules/system", tags=["system"])


@router.get("/info")
async def info(request: Request) -> dict:
    """Branding + version + module activation state (consumed by the installer)."""
    resolver = getattr(request.app.state, "resolver", None)
    app_name = (resolver.resolve("branding.app_name", "Facil")
                if resolver is not None else "Facil")
    return {
        "app_name": app_name,
        "version": request.app.version,
        "modules": {"enabled": enabled_from_env(), "available": discover()},
    }
