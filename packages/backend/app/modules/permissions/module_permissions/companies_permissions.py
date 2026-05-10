"""
Company Permissions — RBAC permissions for company management.

Covers:
- User-scoped company CRUD (business users via company roles)
- Admin-scoped company management (fiscal admin)
- Company verification workflow
- Member management
"""

MODULE_NAME = "company"

PERMISSIONS = [
    # --- View ---
    ("company.view",                "company", "view",                "Ver detalles de empresa",               False),
    ("company.view_all",            "company", "view_all",            "Ver todas las empresas (admin)",         False),
    ("company.view_entity_scoped",  "company", "view_entity_scoped",  "Ver empresas de mi entidad (supervisor)", False),
    ("company.view_stats",          "company", "view_stats",          "Ver estadisticas de empresas",           False),

    # --- Mutations ---
    ("company.create",         "company", "create",         "Crear nuevas empresas",                 True),
    ("company.update",         "company", "update",         "Modificar datos de empresa",            True),
    ("company.delete",         "company", "delete",         "Eliminar empresa",                      True),

    # --- Verification ---
    ("company.verify",         "company", "verify",         "Verificar/aprobar empresa",             True),

    # --- Members ---
    ("company.manage_members", "company", "manage_members", "Gestionar miembros de empresa",         True),

    # --- Classification Agent ---
    ("company.classify",              "company", "classify",              "Clasificar empresas (asignar regimen fiscal)",  True),
    ("company.validate_draft",        "company", "validate_draft",        "Validar borradores de creacion de empresas",    True),
    ("company.import_csv",            "company", "import_csv",            "Importar empresas desde CSV/Excel",             True),
    ("company.view_classification",   "company", "view_classification",   "Ver detalles de clasificacion",                 False),
]

ROLE_PERMISSIONS = {
    # Full access
    "admin": ["*"],
    "super_admin": ["*"],

    # Treasury supervisors — read-only across all companies
    "supervisor_tesoro": [
        "company.view",
        "company.view_all",
        "company.view_entity_scoped",
        "company.view_stats",
    ],

    # OMS polyvalent agent — view for license workflows (via OMS queue only)
    "agent_oms_polyvalent": [
        "company.view",
    ],

    # ONRC agents — company registration + classification entity
    "agent_onrc": [
        "company.view",
        "company.create",
        "company.update",
        "company.verify",
        "company.view_classification",
        "company.classify",
    ],
    "supervisor_onrc": [
        "company.view",
        "company.view_entity_scoped",
        "company.view_stats",
        "company.create",
        "company.update",
        "company.verify",
        "company.manage_members",
        "company.view_classification",
        "company.classify",
        "company.validate_draft",
        "company.import_csv",
    ],

    # Commerce ministry — supervisors see entity-scoped companies
    "agent_min_comercio": [
        "company.view",
    ],
    "supervisor_min_comercio": [
        "company.view",
        "company.view_entity_scoped",
        "company.view_stats",
    ],

    # All other supervisors — entity-scoped company view
    "supervisor_ayuntamiento": [
        "company.view",
        "company.view_entity_scoped",
        "company.view_stats",
    ],
    "supervisor_camara": [
        "company.view",
        "company.view_entity_scoped",
        "company.view_stats",
    ],
    "supervisor_min_hacienda": [
        "company.view",
        "company.view_entity_scoped",
        "company.view_stats",
    ],
}
