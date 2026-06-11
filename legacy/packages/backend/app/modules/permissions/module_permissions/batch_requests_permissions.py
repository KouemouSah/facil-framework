"""
Batch Requests Module Permissions

Defines permissions for batch service requests (Demandes en Lot):
- Create batch requests
- View own batches
- Manage batches (supervisor)
- Admin operations

These permissions are auto-synced at startup via initialize_permissions().
Without this file, cleanup_obsolete=True deletes them from the DB.
"""

MODULE_NAME = "batch_requests"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    (
        "batch_requests.create",
        "batch_requests",
        "create",
        "Crear solicitudes en lote",
        False,
    ),
    (
        "batch_requests.read",
        "batch_requests",
        "read",
        "Ver solicitudes en lote propias",
        False,
    ),
    (
        "batch_requests.manage",
        "batch_requests",
        "manage",
        "Gestionar solicitudes en lote",
        False,
    ),
    (
        "batch_requests.admin",
        "batch_requests",
        "all",
        "Administrar todos los lotes (admin)",
        True,
    ),
]

# Role-permission mappings — auto-synced at startup
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All batch_requests permissions

    # Citizens, businesses, accountants: create + read own batches
    "citizen": [
        "batch_requests.create",
        "batch_requests.read",
    ],
    "business": [
        "batch_requests.create",
        "batch_requests.read",
    ],
    "accountant": [
        "batch_requests.create",
        "batch_requests.read",
    ],
}
