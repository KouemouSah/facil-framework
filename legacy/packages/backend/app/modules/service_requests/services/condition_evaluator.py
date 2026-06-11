"""
Generic Condition Evaluator for Dynamic Wizard.

Evaluates conditions defined in workflow configs against a context dictionary.
The evaluator is FULLY DYNAMIC - it does NOT know about specific keys like
"solicitud_type" or "is_minor". It simply compares values from condition to context.

Condition Syntax:
    - Simple equality: {"key": "value"} → context[key] == value
    - List membership: {"key_in": [values]} → context[key] in values
    - Boolean: {"key": True/False} → context[key] == True/False
    - Multiple keys: {"k1": "v1", "k2": "v2"} → AND (all must match)
    - Explicit OR: {"OR": [cond1, cond2]} → cond1 OR cond2
    - Explicit AND: {"AND": [cond1, cond2]} → cond1 AND cond2

Examples:
    # Pasaporte workflow
    {"solicitud_type": "RENOVACION"}
    {"motivo_in": ["VENCIMIENTO", "DETERIORO"]}
    {"is_minor": True}
    {"OR": [{"solicitud_type": "EXPEDICION"}, {"is_minor": True}]}

    # Vehiculo workflow (hypothetical)
    {"tipo_vehiculo": "MOTO"}
    {"permiso_clase_in": ["A", "B"]}

    # Conducir workflow (hypothetical)
    {"edad_minima": 18}
    {"categoria_in": ["B", "C"]}

Usage:
    evaluator = ConditionEvaluator()
    context = {"solicitud_type": "RENOVACION", "motivo": "VENCIMIENTO", "is_minor": False}
    result = evaluator.evaluate({"solicitud_type": "RENOVACION"}, context)  # True
"""
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class ConditionEvaluator:
    """
    Generic condition evaluator for workflow form configs.

    Evaluates condition dicts against a context dict without
    hardcoding any specific key names.
    """

    def evaluate(self, condition: Optional[Dict[str, Any]], context: Dict[str, Any]) -> bool:
        """
        Evaluate a condition against a context.

        Args:
            condition: Condition dict or None. None/empty means always True.
            context: Context dict with values to compare against.

        Returns:
            True if condition matches context, False otherwise.

        Rules:
            - None or {} condition → True (always show)
            - {"key": value} → context.get(key) == value
            - {"key_in": [values]} → context.get(key without _in suffix) in values
            - Multiple keys → AND (all must match)
            - {"OR": [conditions]} → any condition matches
            - {"AND": [conditions]} → all conditions match
        """
        # None or empty condition = always True
        if not condition:
            return True

        # Handle OR combinator
        if "OR" in condition:
            or_conditions = condition["OR"]
            if not isinstance(or_conditions, list):
                logger.warning(f"OR condition must be a list, got: {type(or_conditions)}")
                return True
            return any(self.evaluate(c, context) for c in or_conditions)

        # Handle AND combinator
        if "AND" in condition:
            and_conditions = condition["AND"]
            if not isinstance(and_conditions, list):
                logger.warning(f"AND condition must be a list, got: {type(and_conditions)}")
                return True
            return all(self.evaluate(c, context) for c in and_conditions)

        # Evaluate all other keys (implicit AND)
        for key, expected_value in condition.items():
            if not self._evaluate_single(key, expected_value, context):
                return False

        return True

    def _evaluate_single(
        self,
        key: str,
        expected_value: Any,
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate a single key-value condition.

        Args:
            key: Condition key (e.g., "solicitud_type" or "motivo_in")
            expected_value: Expected value or list for _in suffix
            context: Context dict

        Returns:
            True if condition matches.
        """
        # Handle _in suffix (list membership)
        if key.endswith("_in"):
            actual_key = key[:-3]  # Remove "_in" suffix
            actual_value = context.get(actual_key)

            if not isinstance(expected_value, list):
                logger.warning(f"Condition {key} should have list value, got: {type(expected_value)}")
                return True

            # Handle case where actual_value is an enum
            if hasattr(actual_value, 'value'):
                actual_value = actual_value.value

            return actual_value in expected_value

        # Handle _not_in suffix (list exclusion)
        if key.endswith("_not_in"):
            actual_key = key[:-7]  # Remove "_not_in" suffix
            actual_value = context.get(actual_key)

            if not isinstance(expected_value, list):
                logger.warning(f"Condition {key} should have list value, got: {type(expected_value)}")
                return True

            if hasattr(actual_value, 'value'):
                actual_value = actual_value.value

            return actual_value not in expected_value

        # Handle _gt suffix (greater than)
        if key.endswith("_gt"):
            actual_key = key[:-3]
            actual_value = context.get(actual_key)
            if actual_value is None:
                return False
            try:
                return float(actual_value) > float(expected_value)
            except (ValueError, TypeError):
                return False

        # Handle _gte suffix (greater than or equal)
        if key.endswith("_gte"):
            actual_key = key[:-4]
            actual_value = context.get(actual_key)
            if actual_value is None:
                return False
            try:
                return float(actual_value) >= float(expected_value)
            except (ValueError, TypeError):
                return False

        # Handle _lt suffix (less than)
        if key.endswith("_lt"):
            actual_key = key[:-3]
            actual_value = context.get(actual_key)
            if actual_value is None:
                return False
            try:
                return float(actual_value) < float(expected_value)
            except (ValueError, TypeError):
                return False

        # Handle _lte suffix (less than or equal)
        if key.endswith("_lte"):
            actual_key = key[:-4]
            actual_value = context.get(actual_key)
            if actual_value is None:
                return False
            try:
                return float(actual_value) <= float(expected_value)
            except (ValueError, TypeError):
                return False

        # Handle _ne suffix (not equal)
        if key.endswith("_ne"):
            actual_key = key[:-3]
            actual_value = context.get(actual_key)
            if hasattr(actual_value, 'value'):
                actual_value = actual_value.value
            return actual_value != expected_value

        # Simple equality
        actual_value = context.get(key)

        # Handle enum values
        if hasattr(actual_value, 'value'):
            actual_value = actual_value.value

        # Handle expected enum values
        if hasattr(expected_value, 'value'):
            expected_value = expected_value.value

        return actual_value == expected_value


# Singleton instance for convenience
_evaluator: Optional[ConditionEvaluator] = None


def get_condition_evaluator() -> ConditionEvaluator:
    """Get singleton ConditionEvaluator instance."""
    global _evaluator
    if _evaluator is None:
        _evaluator = ConditionEvaluator()
    return _evaluator


def evaluate_condition(condition: Optional[Dict[str, Any]], context: Dict[str, Any]) -> bool:
    """
    Convenience function to evaluate a condition.

    Args:
        condition: Condition dict or None
        context: Context dict

    Returns:
        True if condition matches context
    """
    return get_condition_evaluator().evaluate(condition, context)


__all__ = ["ConditionEvaluator", "get_condition_evaluator", "evaluate_condition"]
