"""
Document Module Permissions

Defines permissions for document management:
- Document viewing and statistics
- Template management
- OCR processing

Uses SINGULAR resource names and DOT notation per convention.
"""

MODULE_NAME = "document"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # DOCUMENT MANAGEMENT
    # =========================================================================
    (
        "document.view",
        "document",
        "view",
        "Ver documentos",
        False
    ),
    (
        "document.view_stats",
        "document",
        "view_stats",
        "Ver estadisticas de documentos",
        False
    ),
    (
        "document.download",
        "document",
        "download",
        "Descargar documentos",
        False
    ),
    (
        "document.delete",
        "document",
        "delete",
        "Eliminar documentos",
        True  # Critical - permanent deletion
    ),

    # =========================================================================
    # TEMPLATE MANAGEMENT
    # =========================================================================
    (
        "template.view",
        "template",
        "view",
        "Ver plantillas de documentos",
        False
    ),
    (
        "template.create",
        "template",
        "create",
        "Crear plantillas de documentos",
        True
    ),
    (
        "template.update",
        "template",
        "update",
        "Modificar plantillas de documentos",
        True
    ),
    (
        "template.delete",
        "template",
        "delete",
        "Eliminar plantillas de documentos",
        True
    ),

    # =========================================================================
    # OCR PROCESSING
    # =========================================================================
    (
        "ocr.view_queue",
        "ocr",
        "view_queue",
        "Ver cola de procesamiento OCR",
        False
    ),
    (
        "ocr.reprocess",
        "ocr",
        "reprocess",
        "Reprocesar documento con OCR",
        False
    ),
    (
        "ocr.view_stats",
        "ocr",
        "view_stats",
        "Ver estadisticas de OCR",
        False
    ),
]


# Default role permissions mapping
# NOTE: After Migration 051, agent types are determined by agent_profiles
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # Supervisors (agent_profiles.is_supervisor = true)
    "supervisor": [
        "document.view",
        "document.view_stats",
        "document.download",
        "template.view",
        "ocr.view_queue",
        "ocr.view_stats",
    ],

    # Generic agent role - all agent types
    "agent": [
        "document.view",
        "document.download",
        "template.view",
    ],
}
