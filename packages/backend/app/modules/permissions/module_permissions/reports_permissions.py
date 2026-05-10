"""
Reports Module Permissions

Defines permissions for reporting and analytics:
- View reports
- Generate reports
- Export data
- Comparison metrics

Uses SINGULAR resource names and DOT notation per convention.
NEVER use colon format (reports:view is WRONG)
"""

MODULE_NAME = "reports"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # REPORT VIEWING
    # =========================================================================
    (
        "reports.view",
        "reports",
        "view",
        "Ver informes y analiticas",
        False
    ),
    (
        "reports.view_comparison",
        "reports",
        "view_comparison",
        "Ver comparaciones entre periodos",
        False
    ),
    (
        "reports.view_trends",
        "reports",
        "view_trends",
        "Ver tendencias historicas",
        False
    ),

    # =========================================================================
    # REPORT GENERATION
    # =========================================================================
    (
        "reports.generate",
        "reports",
        "generate",
        "Generar nuevos informes",
        False
    ),
    (
        "reports.schedule",
        "reports",
        "schedule",
        "Programar informes automaticos",
        False
    ),

    # =========================================================================
    # DATA EXPORT
    # =========================================================================
    (
        "reports.export_pdf",
        "reports",
        "export_pdf",
        "Exportar informes en PDF",
        False
    ),
    (
        "reports.export_excel",
        "reports",
        "export_excel",
        "Exportar informes en Excel",
        False
    ),
    (
        "reports.export_json",
        "reports",
        "export_json",
        "Exportar datos en JSON",
        False
    ),

    # =========================================================================
    # ADVANCED ANALYTICS
    # =========================================================================
    (
        "reports.view_financial",
        "reports",
        "view_financial",
        "Ver informes financieros",
        True  # Critical - sensitive financial data
    ),
    (
        "reports.view_performance",
        "reports",
        "view_performance",
        "Ver informes de rendimiento",
        False
    ),
]


# Default role permissions mapping
# NOTE: After Migration 051, agent types are determined by agent_profiles
# Treasury-specific access (reports.view_financial) handled via agent_category check
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # Supervisors (agent_profiles.is_supervisor = true)
    "supervisor": [
        "reports.view",
        "reports.view_comparison",
        "reports.view_trends",
        "reports.generate",
        "reports.schedule",
        "reports.export_pdf",
        "reports.export_excel",
        "reports.export_json",
        "reports.view_performance",
    ],

    # Generic agent role - all agent types
    "agent": [
        "reports.view",
        "reports.view_trends",
    ],
}
