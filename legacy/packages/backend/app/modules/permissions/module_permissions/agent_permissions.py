"""
Agent Module Permissions

Defines all permissions for agent management, assignments, workloads,
and work queue operations.

Note: Uses SINGULAR resource names (agent, assignment) per convention.
"""

MODULE_NAME = "agent"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # AGENT PROFILE MANAGEMENT
    # =========================================================================
    (
        "agent.create",
        "agent",
        "create",
        "Crear perfil de agente",
        False
    ),
    (
        "agent.view",
        "agent",
        "view",
        "Ver detalles de agente",
        False
    ),
    (
        "agent.list",
        "agent",
        "list",
        "Listar agentes",
        False
    ),
    (
        "agent.update",
        "agent",
        "update",
        "Modificar configuración de agente",
        False
    ),
    (
        "agent.deactivate",
        "agent",
        "deactivate",
        "Desactivar agente (acción crítica)",
        True  # Critical - affects agent's ability to work
    ),
    (
        "agent.reactivate",
        "agent",
        "reactivate",
        "Reactivar agente",
        False
    ),

    # =========================================================================
    # ASSIGNMENT MANAGEMENT
    # =========================================================================
    (
        "assignment.create",
        "assignment",
        "create",
        "Crear asignación manual",
        False
    ),
    (
        "assignment.view",
        "assignment",
        "view",
        "Ver detalles de asignación",
        False
    ),
    (
        "assignment.list",
        "assignment",
        "list",
        "Listar asignaciones",
        False
    ),
    (
        "assignment.update",
        "assignment",
        "update",
        "Modificar asignaciones existentes",
        False
    ),
    (
        "assignment.auto_assign",
        "assignment",
        "auto_assign",
        "Ejecutar asignación automática",
        False
    ),
    (
        "assignment.start",
        "assignment",
        "start",
        "Iniciar procesamiento de asignación",
        False
    ),
    (
        "assignment.complete",
        "assignment",
        "complete",
        "Marcar asignación como completada",
        False
    ),
    (
        "assignment.reassign",
        "assignment",
        "reassign",
        "Reasignar declaración a nuevo agente",
        True  # Critical - affects agent workloads
    ),
    (
        "assignment.reassign_in_progress",
        "assignment",
        "reassign_in_progress",
        "Reasignar tarea EN CURSO (crítico)",
        True  # Critical - requires special approval
    ),
    (
        "assignment.cancel",
        "assignment",
        "cancel",
        "Cancelar asignación",
        True  # Critical
    ),
    (
        "assignment.update_priority",
        "assignment",
        "update_priority",
        "Actualizar prioridad de asignación",
        False
    ),
    (
        "assignment.extend_deadline",
        "assignment",
        "extend_deadline",
        "Extender fecha límite de asignación",
        False
    ),
    (
        "assignment.update_notes",
        "assignment",
        "update_notes",
        "Actualizar notas de asignación",
        False
    ),
    (
        "assignment.view_stats",
        "assignment",
        "view_stats",
        "Ver estadísticas de asignaciones",
        False
    ),

    # =========================================================================
    # WORKLOAD MANAGEMENT
    # =========================================================================
    (
        "agent.view_workload",
        "agent",
        "view_workload",
        "Ver carga de trabajo de agentes",
        False
    ),
    (
        "agent.manage_workload",
        "agent",
        "manage_workload",
        "Gestionar carga de trabajo (modificar límites)",
        False
    ),
    (
        "agent.set_availability",
        "agent",
        "set_availability",
        "Cambiar disponibilidad de agente",
        False
    ),
    (
        "agent.view_available",
        "agent",
        "view_available",
        "Ver agentes disponibles por entidad",
        False
    ),
    (
        "agent.rebalance_workload",
        "agent",
        "rebalance_workload",
        "Ver y ejecutar rebalanceo de carga",
        False
    ),

    # =========================================================================
    # PERFORMANCE & STATISTICS
    # =========================================================================
    (
        "agent.view_performance",
        "agent",
        "view_performance",
        "Ver estadísticas de rendimiento",
        False
    ),
    (
        "agent.view_capacity_prediction",
        "agent",
        "view_capacity_prediction",
        "Ver predicción de capacidad",
        False
    ),
    (
        "agent.export_stats",
        "agent",
        "export_stats",
        "Exportar estadísticas de agentes",
        False
    ),

    # =========================================================================
    # WORK QUEUE MANAGEMENT
    # =========================================================================
    (
        "queue.view",
        "queue",
        "view",
        "Ver cola de trabajo",
        False
    ),
    (
        "queue.add",
        "queue",
        "add",
        "Agregar elemento a la cola",
        False
    ),
    (
        "queue.assign",
        "queue",
        "assign",
        "Asignar elemento de cola a agente",
        False
    ),
    (
        "queue.complete",
        "queue",
        "complete",
        "Marcar elemento de cola como completado",
        False
    ),
    (
        "queue.escalate",
        "queue",
        "escalate",
        "Escalar elemento de cola",
        False
    ),
    (
        "queue.release",
        "queue",
        "release",
        "Liberar elemento de cola",
        False
    ),
    (
        "queue.review",
        "queue",
        "review",
        "Revisar elementos de cola (supervisor)",
        False
    ),

    # =========================================================================
    # TEAM & ESCALATION VISIBILITY
    # =========================================================================
    (
        "agent.view_team",
        "agent",
        "view_team",
        "Ver equipo de agentes",
        False
    ),
    (
        "agent.view_escalations",
        "agent",
        "view_escalations",
        "Ver escalaciones del equipo",
        False
    ),

    # =========================================================================
    # ANALYST (AI-powered agent analytics)
    # =========================================================================
    (
        "analyst.ask",
        "analyst",
        "ask",
        "Consultar el analista IA sobre rendimiento",
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
        # All agent permissions
        "agent.create",
        "agent.view",
        "agent.list",
        "agent.update",
        "agent.deactivate",
        "agent.reactivate",
        "agent.view_workload",
        "agent.manage_workload",
        "agent.set_availability",
        "agent.view_available",
        "agent.rebalance_workload",
        "agent.view_performance",
        "agent.view_capacity_prediction",
        "agent.export_stats",
        # All assignment permissions
        "assignment.create",
        "assignment.view",
        "assignment.list",
        "assignment.update",
        "assignment.auto_assign",
        "assignment.start",
        "assignment.complete",
        "assignment.reassign",
        "assignment.reassign_in_progress",
        "assignment.cancel",
        "assignment.update_priority",
        "assignment.extend_deadline",
        "assignment.update_notes",
        "assignment.view_stats",
        # All queue permissions
        "queue.view",
        "queue.add",
        "queue.assign",
        "queue.complete",
        "queue.escalate",
        "queue.release",
    ],

    # Generic agent role - specific type determined by agent_profiles
    # Applies to all agent types: dgi, ministry, treasury, entity
    "agent": [
        "agent.view",
        "agent.view_workload",
        "agent.view_performance",  # Personal stats on /dashboard/agent/stats
        "agent.set_availability",
        "assignment.view",
        "assignment.list",
        "assignment.start",
        "assignment.complete",
        "assignment.update_notes",
        "queue.view",
        "queue.complete",
    ],
}
