"""
Funcionario Module Permissions

Defines permissions for funcionario verification processing by AGENTS.

IMPORTANT: These permissions are for AGENTS who process verification requests,
NOT for funcionarios themselves. Funcionarios have the same base permissions
as citizens - they only have access to an extra frontend menu.

Flow:
1. Citizen submits verificacion request (no special permissions needed)
2. Agent with funcionario.verificacion.* permissions processes the request
3. If approved, citizen's role changes to 'funcionario'

Uses SINGULAR resource names and DOT notation per convention.
"""

MODULE_NAME = "funcionario"

# Format: (name, resource, action, description_es, is_critical)
# Note: Uses funcionario_verificacion (underscore) as compound resource name
# to follow the convention of treasury_audit, treasury_stat, etc.
PERMISSIONS = [
    # =========================================================================
    # VERIFICATION MANAGEMENT (Agent operations)
    # =========================================================================
    (
        "funcionario_verificacion.read_all",
        "funcionario_verificacion",
        "read_all",
        "Ver todas las solicitudes de verificacion de funcionario",
        False
    ),
    (
        "funcionario_verificacion.process",
        "funcionario_verificacion",
        "process",
        "Procesar solicitudes de verificacion (aprobar/rechazar)",
        True  # Critical - changes user role
    ),
    (
        "funcionario_verificacion.view_stats",
        "funcionario_verificacion",
        "view_stats",
        "Ver estadisticas de verificaciones",
        False
    ),
    (
        "funcionario_verificacion.export",
        "funcionario_verificacion",
        "export",
        "Exportar datos de verificaciones",
        False
    ),
]


# Default role permissions mapping
# NOTE: After Migration 051, agent types are determined by agent_profiles
# These permissions are for AGENTS to process verification requests
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # Supervisors (agent_profiles.is_supervisor = true)
    "supervisor": [
        "funcionario_verificacion.read_all",
        "funcionario_verificacion.process",
        "funcionario_verificacion.view_stats",
        "funcionario_verificacion.export",
    ],

    # Generic agent role - agents can process verifications
    # Specific ministry agents may have additional restrictions at runtime
    "agent": [
        "funcionario_verificacion.read_all",
        "funcionario_verificacion.process",
    ],
}
