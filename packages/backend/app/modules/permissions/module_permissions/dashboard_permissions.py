"""
Dashboard Module Permissions

Defines permissions for supervisor and admin dashboard access:
- Dashboard views
- Team statistics
- Real-time summary

Uses SINGULAR resource names and DOT notation per convention.
NEVER use colon format (dashboard:view is WRONG)
"""

MODULE_NAME = "dashboard"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # DASHBOARD ACCESS
    # =========================================================================
    (
        "dashboard.view",
        "dashboard",
        "view",
        "Ver dashboard de supervisor",
        False
    ),
    (
        "dashboard.view_realtime",
        "dashboard",
        "view_realtime",
        "Ver resumen en tiempo real",
        False
    ),

    # =========================================================================
    # TEAM STATISTICS
    # =========================================================================
    (
        "dashboard.team_stats",
        "dashboard",
        "team_stats",
        "Ver estadisticas del equipo",
        False
    ),
    (
        "dashboard.team_performance",
        "dashboard",
        "team_performance",
        "Ver rendimiento del equipo",
        False
    ),
    (
        "dashboard.team_workload",
        "dashboard",
        "team_workload",
        "Ver carga de trabajo del equipo",
        False
    ),

    # =========================================================================
    # AGENT DASHBOARDS (for agents' own view)
    # =========================================================================
    (
        "dashboard.view_own",
        "dashboard",
        "view_own",
        "Ver dashboard propio (agente)",
        False
    ),
    (
        "dashboard.view_own_stats",
        "dashboard",
        "view_own_stats",
        "Ver estadisticas propias",
        False
    ),
]


# Default role permissions mapping
# NOTE: After Migration 051, agent types are determined by agent_profiles
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # Supervisors (agent_profiles.is_supervisor = true)
    "supervisor": [
        "dashboard.view",
        "dashboard.view_realtime",
        "dashboard.team_stats",
        "dashboard.team_performance",
        "dashboard.team_workload",
    ],

    # Generic agent role - all agent types
    "agent": [
        "dashboard.view_own",
        "dashboard.view_own_stats",
    ],
}
