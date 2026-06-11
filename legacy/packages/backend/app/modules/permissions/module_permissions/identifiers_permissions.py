"""
Verified Identifiers Module Permissions

Defines permissions for the verified identifiers system
(DIP/passport validation against official registries).
"""

MODULE_NAME = "identifiers"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    (
        "identifiers.config",
        "identifiers",
        "config",
        "Configurar reglas de validación de identificadores",
        True
    ),
    (
        "identifiers.import",
        "identifiers",
        "import",
        "Importar lotes de identificadores verificados",
        True
    ),
    (
        "identifiers.stats",
        "identifiers",
        "stats",
        "Ver estadísticas de verificación de identificadores",
        False
    ),
]

ROLE_PERMISSIONS = {
    "admin": ["*"],
}
