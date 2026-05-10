"""
Event Handlers for Service Requests
===================================
Handlers that respond to events and trigger service request workflows.
"""

from .agent_queue_handler import AgentQueueEventHandler, register_agent_queue_handlers

__all__ = ["AgentQueueEventHandler", "register_agent_queue_handlers"]
