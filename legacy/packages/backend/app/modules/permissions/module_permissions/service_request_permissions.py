"""
Service Request Module Permissions

Defines all permissions for service request processing by agents,
including queue management, approvals, and appointment scheduling.

Note: Uses SINGULAR resource names and DOT notation per convention.
      NEVER use colon format (agent:view_queue is WRONG)
"""

MODULE_NAME = "service_request"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # QUEUE OPERATIONS (for agents processing service requests)
    # =========================================================================
    (
        "service_request.view_queue",
        "service_request",
        "view_queue",
        "Ver cola de solicitudes pendientes",
        False
    ),
    (
        "service_request.view_queue_stats",
        "service_request",
        "view_queue_stats",
        "Ver estadísticas de la cola",
        False
    ),
    (
        "service_request.view_my_queue",
        "service_request",
        "view_my_queue",
        "Ver mis solicitudes asignadas",
        False
    ),
    (
        "service_request.assign_to_self",
        "service_request",
        "assign_to_self",
        "Auto-asignar solicitud de la cola",
        False
    ),
    (
        "service_request.release",
        "service_request",
        "release",
        "Liberar solicitud asignada",
        False
    ),

    # =========================================================================
    # REQUEST VIEWING & PROCESSING
    # =========================================================================
    (
        "service_request.view",
        "service_request",
        "view",
        "Ver detalles de solicitud (vista agente)",
        False
    ),
    (
        "service_request.view_documents",
        "service_request",
        "view_documents",
        "Ver documentos adjuntos",
        False
    ),
    (
        "service_request.view_extraction",
        "service_request",
        "view_extraction",
        "Ver datos extraídos por OCR",
        False
    ),
    (
        "service_request.process",
        "service_request",
        "process",
        "Procesar solicitud (aprobar/rechazar/pedir docs)",
        False
    ),

    # =========================================================================
    # DECISION MAKING
    # =========================================================================
    (
        "service_request.approve",
        "service_request",
        "approve",
        "Aprobar solicitud de servicio",
        True  # Critical - changes request status
    ),
    (
        "service_request.reject",
        "service_request",
        "reject",
        "Rechazar solicitud de servicio",
        True  # Critical - changes request status
    ),
    (
        "service_request.request_documents",
        "service_request",
        "request_documents",
        "Solicitar documentos adicionales",
        False
    ),
    (
        "service_request.escalate",
        "service_request",
        "escalate",
        "Escalar solicitud a supervisor",
        False
    ),

    # =========================================================================
    # APPOINTMENT MANAGEMENT
    # =========================================================================
    (
        "service_request.view_appointments",
        "service_request",
        "view_appointments",
        "Ver citas programadas",
        False
    ),
    (
        "service_request.schedule_appointment",
        "service_request",
        "schedule_appointment",
        "Programar cita manualmente",
        False
    ),
    (
        "service_request.reschedule_appointment",
        "service_request",
        "reschedule_appointment",
        "Reprogramar cita",
        False
    ),
    (
        "service_request.cancel_appointment",
        "service_request",
        "cancel_appointment",
        "Cancelar cita",
        False
    ),
    (
        "service_request.view_available_slots",
        "service_request",
        "view_available_slots",
        "Ver slots de cita disponibles",
        False
    ),

    # =========================================================================
    # VERIFICATION
    # =========================================================================
    (
        "service_request.verify_manually",
        "service_request",
        "verify_manually",
        "Verificar identidad manualmente",
        True  # Critical - bypasses automatic verification
    ),

    # =========================================================================
    # ADMINISTRATION
    # =========================================================================
    (
        "service_request.view_all",
        "service_request",
        "view_all",
        "Ver todas las solicitudes (admin)",
        False
    ),
    (
        "service_request.reassign",
        "service_request",
        "reassign",
        "Reasignar solicitud a otro agente",
        True  # Critical - affects agent workload
    ),
    (
        "service_request.export",
        "service_request",
        "export",
        "Exportar datos de solicitudes",
        False
    ),
    (
        "service_request.view_audit_log",
        "service_request",
        "view_audit_log",
        "Ver historial de acciones",
        False
    ),
    (
        "service_request.review",
        "service_request",
        "review",
        "Revisar solicitud de servicio (supervisor)",
        False
    ),
    (
        "service_request.update",
        "service_request",
        "update",
        "Actualizar solicitud de servicio",
        False
    ),
]


# Default role permissions mapping
# NOTE: After Migration 051, agent types (dgi, ministry, treasury) are determined
# by agent_profiles.agent_type and ministry_code, not by user role.
# Supervisor status is via agent_profiles.is_supervisor flag.
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # Supervisors (agent_profiles.is_supervisor = true)
    "supervisor": [
        # All permissions for supervisors
        "service_request.view_queue",
        "service_request.view_queue_stats",
        "service_request.view_my_queue",
        "service_request.assign_to_self",
        "service_request.release",
        "service_request.view",
        "service_request.view_documents",
        "service_request.view_extraction",
        "service_request.process",
        "service_request.approve",
        "service_request.reject",
        "service_request.request_documents",
        "service_request.escalate",
        "service_request.view_appointments",
        "service_request.schedule_appointment",
        "service_request.reschedule_appointment",
        "service_request.cancel_appointment",
        "service_request.view_available_slots",
        "service_request.verify_manually",
        "service_request.view_all",
        "service_request.reassign",
        "service_request.export",
        "service_request.view_audit_log",
    ],

    # Generic agent role - specific permissions may vary by agent_category
    # (dgi, ministry, treasury, entity) determined at runtime via agent_profiles
    "agent": [
        "service_request.view_queue",
        "service_request.view_queue_stats",
        "service_request.view_my_queue",
        "service_request.assign_to_self",
        "service_request.release",
        "service_request.view",
        "service_request.view_documents",
        "service_request.view_extraction",
        "service_request.process",
        "service_request.approve",
        "service_request.reject",
        "service_request.request_documents",
        "service_request.escalate",
        "service_request.view_appointments",
        "service_request.schedule_appointment",
        "service_request.cancel_appointment",
        "service_request.view_available_slots",
    ],
}
