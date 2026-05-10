"""
Regression tests for the `tool_registry.py` AttributeError on
`FunctionDeclaration.name` (production crash recovered from Cloud Run
logs at `Documentations/workflow/debug/error.md`).

Bug summary:
    /api/v1/agents/analyst/agents → 500
    AttributeError: 'FunctionDeclaration' object has no attribute 'name'

Fix summary:
    `agent_decision_tools.py` now exports `DECISION_FUNC_DECLS_BY_NAME`
    (dict) alongside `DECISION_FUNC_DECLS` (list). Both are derived from
    a single source of truth (`_DECISION_DECLS_SOURCE` tuples).
    `tool_registry.py` uses the dict for O(1) lookups instead of
    introspecting `.name` on protobuf wrappers.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_tool_registry_singleton():
    """`ToolRegistry` is a process-wide singleton — both the instance
    AND its class-level state must be reset between tests in this file
    so each test exercises a clean initialization path."""
    from app.modules.shared.services.tool_registry import ToolRegistry
    ToolRegistry._instance = None
    ToolRegistry._registry = {}
    ToolRegistry._initialized = False
    yield
    ToolRegistry._instance = None
    ToolRegistry._registry = {}
    ToolRegistry._initialized = False


class TestDecisionFuncDecls:
    """Verify the source-of-truth contracts."""

    def test_by_name_dict_keys_match_function_map(self):
        from app.modules.shared.services.agent_decision_tools import (
            DECISION_FUNCTION_MAP,
            DECISION_FUNC_DECLS_BY_NAME,
        )
        assert set(DECISION_FUNC_DECLS_BY_NAME.keys()) == set(
            DECISION_FUNCTION_MAP.keys()
        ), (
            "DECISION_FUNC_DECLS_BY_NAME and DECISION_FUNCTION_MAP must have "
            "identical keys — both must be kept in sync via the same source"
        )

    def test_by_name_dict_length_matches_list(self):
        from app.modules.shared.services.agent_decision_tools import (
            DECISION_FUNC_DECLS,
            DECISION_FUNC_DECLS_BY_NAME,
        )
        assert len(DECISION_FUNC_DECLS) == len(DECISION_FUNC_DECLS_BY_NAME)

    def test_expected_8_decision_tools_present(self):
        from app.modules.shared.services.agent_decision_tools import (
            DECISION_FUNC_DECLS_BY_NAME,
        )
        expected = {
            "ai_decision_support",
            "assess_request_risk",
            "find_similar_cases",
            "summarize_request",
            "predict_sla_risk",
            "suggest_reassignment",
            "get_system_health",
            "optimize_workload",
        }
        assert set(DECISION_FUNC_DECLS_BY_NAME.keys()) == expected


class TestToolRegistryInitialization:
    """The bug crashed `_register_admin` / `_register_supervisor` /
    `_register_entity_agent`. Each registers an agent_type that depends
    on `DECISION_FUNC_DECLS_BY_NAME`. After the fix, all three must
    initialize without raising AttributeError."""

    def test_admin_agent_registers_without_crash(self):
        from app.modules.shared.services.tool_registry import ToolRegistry
        registry = ToolRegistry()
        registry._ensure_initialized()
        agent_types = registry.list_agent_types()
        assert "admin" in agent_types

    def test_supervisor_agent_registers_without_crash(self):
        from app.modules.shared.services.tool_registry import ToolRegistry
        registry = ToolRegistry()
        registry._ensure_initialized()
        assert "supervisor" in registry.list_agent_types()

    def test_entity_agent_registers_without_crash(self):
        from app.modules.shared.services.tool_registry import ToolRegistry
        registry = ToolRegistry()
        registry._ensure_initialized()
        assert "entity_agent" in registry.list_agent_types()

    def test_admin_toolset_includes_decision_tools(self):
        """Verify the merge actually picked up the decision tools, not
        just an empty list (which would also pass the crash test)."""
        from app.modules.shared.services.tool_registry import ToolRegistry
        registry = ToolRegistry()
        registry._ensure_initialized()
        admin_set = registry.get("admin")
        assert "get_system_health" in admin_set.function_map
        assert "optimize_workload" in admin_set.function_map
