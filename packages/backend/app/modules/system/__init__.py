"""system — first real business module + reference template (Phase A.5).

Minimal, genuinely-useful module exercising the real Module Loader path:
exposes platform info (branding name, version, enabled/available modules) for
ops and the D5 web installer. OFF by default (add `system` to MODULES_ENABLED).

Module layout convention (this one only needs `api`):
    app/modules/<name>/
        __init__.py
        api/__init__.py      -> `router: APIRouter`   (required entrypoint)
        models/ services/ handlers/                    (as the module grows)
"""
