"""
Schema Validation Engine for Service Requests.

Executes validation rules defined in JSON schemas (validations[] arrays)
against document extractions. Results are non-blocking risk factors.

Covers 109/114 rules across 22 schemas.
Excluded: cross-document validations, MRZ checksums (ICAO 9303), NLP text matching.

Author: Claude Code
Date: 2026-02-06
"""

import re
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List, Tuple

from loguru import logger

from .schema_loader import schema_loader
from .validation_types import ValidationResult  # noqa: F401 - re-exported
from .mrz_validator import mrz_validator


# ═══════════════════════════════════════════════════════════════════════════════
# RULE PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

# Order is CRITICAL: specific patterns BEFORE generic ones.
# AND/OR must be LAST (they split recursively).
RULE_PATTERNS: List[Tuple[str, str]] = [
    # MRZ checksums: delegate to MRZValidator (not SKIP)
    (r'.*validate_mrz_checksums\((\w+)\)', 'MRZ_CHECKSUMS'),
    # Skip patterns (function calls, NLP) - use .* prefix since re.match anchors at start
    (r'.*VALIDATE_AMOUNT_TEXT', 'SKIP'),
    (r'.*monto_letras\s+(?:EXISTS|MATCHES)\s+monto', 'SKIP'),

    # Date comparisons (specific before generic)
    (r'^(\S+)\s*>\s*TODAY\s*\+\s*(\d+)\s*(MONTHS?|DAYS?)$', 'DATE_AFTER_FUTURE'),
    (r'^(\S+)\s*>\s*TODAY$', 'DATE_AFTER_TODAY'),
    (r'^(\S+)\s*<=\s*TODAY$', 'DATE_BEFORE_EQUAL_TODAY'),
    (r'^(\S+)\s*<\s*TODAY\s*\+\s*(\d+)\s*(MONTHS?|DAYS?)$', 'DATE_BEFORE_FUTURE'),
    (r'^(\S+)\s*>=\s*TODAY\s*-\s*(\d+)\s*(MONTHS?|DAYS?|YEARS?)$', 'DATE_AFTER_PAST'),
    (r'^(\S+)\s*<\s*TODAY\s*-\s*(\d+)\s*(MONTHS?|DAYS?|YEARS?)$', 'DATE_BEFORE_PAST'),
    (r'^(\S+)\s*\+\s*(\d+)\s*[Dd][Aa][Yy][Ss]?\s*>\s*TODAY$', 'DATE_PLUS_DAYS'),
    (r'^(\S+)\s*<=\s*(\S+)\s*\+\s*(\d+)\s*DAYS$', 'DATE_WITHIN_RANGE'),

    # IS NULL OR (before OR)
    (r'^(\S+)\s+IS\s+NULL\s+OR\s+(.+)$', 'IS_NULL_OR'),

    # NOT NULL variants (before AND)
    (r'^(\S+)\s+IS\s+NOT\s+NULL\s+AND\s+LENGTH\((\S+)\)\s*>=\s*(\d+)$', 'NOT_NULL_LENGTH'),
    (r'^(\S+)\s+IS\s+NOT\s+NULL$', 'NOT_NULL'),
    (r'^(\S+)\s*!=\s*null\s+AND\s+\1\s*!=\s*\'\'$', 'NOT_NULL'),
    (r'^(\S+)\s*!=\s*null$', 'NOT_NULL'),

    # Conditionals (before AND)
    (r'^IF\s+!(\S+)\s+THEN\s+(.+)$', 'IF_NOT_THEN'),
    (r'^IF\s+(.+?)\s+THEN\s+(.+)$', 'IF_THEN'),

    # IMPLIES (before AND)
    (r'^(.+?)\s+IMPLIES\s+(.+)$', 'IMPLIES'),

    # Numeric comparison
    (r'^(\S+)\s*>\s*(\d+)$', 'GREATER_THAN'),
    (r'^(\S+)\s*>=\s*(\d+)$', 'GREATER_EQUAL'),

    # String/field comparisons
    (r'^(\S+)\s*!=\s*\'([^\']+)\'$', 'NOT_EQUALS'),
    (r'^(\S+)\s*==\s*\'([^\']+)\'$', 'EQUALS_STR'),
    (r'^(\S+)\s+IN\s+\[(.+)\]$', 'IN_LIST'),
    (r'^(\S+)\s+MATCHES\s+\'(.+)\'$', 'REGEX_MATCH'),
    (r'^(\S+)\s+CONTAINS\s+(\S+)$', 'CONTAINS'),
    (r'^(\S+)\s+IN\s+(\S+)\[(\d+):(\d+)\]$', 'IN_SUBSTRING'),
    (r'^(\S+)\s*==\s*(\S+)\[(\d+)\]$', 'EQUALS_CHAR_AT'),
    (r'^(\S+)\s+IN\s+(\S+)$', 'IN_FIELD'),

    # Logical operators (BEFORE generic equals - must split AND/OR first)
    (r'^(.+?)\s+OR\s+(.+)$', 'OR'),
    (r'^(.+?)\s+AND\s+(.+)$', 'AND'),

    # Boolean equals (after AND/OR)
    (r'^(\S+)\s*==\s*(true|false)$', 'EQUALS_BOOL'),

    # Generic equals (catch-all, LAST)
    (r'^(\S+)\s*==\s*(.+)$', 'EQUALS'),
]


# ═══════════════════════════════════════════════════════════════════════════════
# ENGINE
# ═══════════════════════════════════════════════════════════════════════════════


class SchemaValidationEngine:
    """
    Executes validation rules from JSON schemas against document extractions.

    Usage:
        engine = SchemaValidationEngine()
        results = engine.validate(extraction, "dip")
        failed = [r for r in results if not r.passed]
    """

    # ─── Public API ───────────────────────────────────────────────────────

    def validate(
        self,
        extraction: Dict[str, Any],
        document_code: str,
    ) -> List[ValidationResult]:
        """
        Validate extraction against schema-defined rules.

        Returns ALL results (passed and failed). Caller filters on .passed.
        Never raises - returns empty list on any error.
        """
        try:
            schema = schema_loader.get_schema_for_document(document_code)
            if not schema:
                return []

            validations = schema.get("validations", [])
            if not validations:
                return []

            results: List[ValidationResult] = []
            for v in validations:
                # Skip cross-document validations
                if v.get("cross_document_validation"):
                    continue

                rule_str = v.get("rule", "")
                if not rule_str:
                    continue

                rule_type, params = self._parse_rule(rule_str)

                # Skip unparseable or explicitly skipped rules
                if rule_type is None or rule_type == "SKIP":
                    continue

                # MRZ Checksums: delegate to MRZValidator
                if rule_type == "MRZ_CHECKSUMS":
                    mrz_results = mrz_validator.validate(
                        extraction, document_code, schema
                    )
                    results.extend(mrz_results)
                    continue

                passed = self._evaluate_rule(extraction, rule_type, params)

                results.append(ValidationResult(
                    rule_id=v.get("id", "unknown"),
                    passed=passed,
                    severity=v.get("severity", "warning"),
                    message_es=v.get("error_es", v.get("id", "")),
                    message_fr=v.get("error_fr", ""),
                    rule=rule_str,
                    document_code=document_code,
                ))

            return results

        except Exception as e:
            logger.warning(f"Schema validation engine error for '{document_code}': {e}")
            return []

    # ─── Rule Parser ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_rule(rule_str: str) -> Tuple[Optional[str], Optional[tuple]]:
        """
        Parse a rule string into (rule_type, match_groups).
        Returns (None, None) if no pattern matches.
        Returns ("SKIP", None) for rules that should be skipped.
        """
        rule_str = rule_str.strip()
        for pattern, rule_type in RULE_PATTERNS:
            m = re.match(pattern, rule_str, re.IGNORECASE)
            if m:
                if rule_type == "SKIP":
                    return ("SKIP", None)
                return (rule_type, m.groups())

        logger.debug(f"Schema validation: unparseable rule: {rule_str}")
        return (None, None)

    # ─── Field Resolution ─────────────────────────────────────────────────

    def _resolve_field(self, extraction: Dict, field_path: str) -> Any:
        """
        Resolve field.path from nested extraction dict.
        Falls back to flat key lookup if nested resolution fails.
        """
        parts = field_path.split(".")
        current = extraction
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        if current is not None:
            return current
        # Flat fallback: try last segment directly
        return extraction.get(parts[-1])

    # ─── Date Parsing ─────────────────────────────────────────────────────

    @staticmethod
    def _parse_date(date_value: Any) -> Optional[date]:
        """Parse various date formats into date object."""
        if isinstance(date_value, date) and not isinstance(date_value, datetime):
            return date_value
        if isinstance(date_value, datetime):
            return date_value.date()
        if not date_value:
            return None

        date_str = str(date_value).strip()
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y", "%Y%m%d"]:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _make_timedelta(amount: int, unit: str) -> timedelta:
        """Create timedelta from amount and unit string (DAYS/MONTHS/YEARS)."""
        unit_upper = unit.upper().rstrip("S")  # Normalize: MONTH -> MONTH, MONTHS -> MONTH
        if unit_upper == "DAY":
            return timedelta(days=amount)
        elif unit_upper == "MONTH":
            return timedelta(days=amount * 30)
        elif unit_upper == "YEAR":
            return timedelta(days=amount * 365)
        return timedelta(days=amount)

    # ─── Rule Evaluator ───────────────────────────────────────────────────

    def _evaluate_rule(
        self,
        extraction: Dict[str, Any],
        rule_type: str,
        params: tuple,
    ) -> bool:
        """
        Evaluate a parsed rule against extraction data.
        Returns True if rule passes (OK), False if violated.
        Never raises exceptions.
        """
        try:
            # ── Date Rules ────────────────────────────────────────────
            if rule_type == "DATE_AFTER_TODAY":
                # field > TODAY
                field_path = params[0]
                val = self._resolve_field(extraction, field_path)
                if val is None:
                    return True  # skip
                parsed = self._parse_date(val)
                if parsed is None:
                    return True  # unparseable = skip
                return parsed > date.today()

            elif rule_type == "DATE_AFTER_FUTURE":
                # field > TODAY + N DAYS/MONTHS (e.g., expiry must be > 6 months away)
                field_path, amount_str, unit = params[0], params[1], params[2]
                val = self._resolve_field(extraction, field_path)
                if val is None:
                    return True
                parsed = self._parse_date(val)
                if parsed is None:
                    return True
                delta = self._make_timedelta(int(amount_str), unit)
                return parsed > date.today() + delta

            elif rule_type == "DATE_BEFORE_EQUAL_TODAY":
                # field <= TODAY
                field_path = params[0]
                val = self._resolve_field(extraction, field_path)
                if val is None:
                    return True
                parsed = self._parse_date(val)
                if parsed is None:
                    return True
                return parsed <= date.today()

            elif rule_type == "DATE_BEFORE_FUTURE":
                # field < TODAY + N DAYS/MONTHS
                field_path, amount_str, unit = params[0], params[1], params[2]
                val = self._resolve_field(extraction, field_path)
                if val is None:
                    return True
                parsed = self._parse_date(val)
                if parsed is None:
                    return True
                delta = self._make_timedelta(int(amount_str), unit)
                return parsed < date.today() + delta

            elif rule_type == "DATE_AFTER_PAST":
                # field >= TODAY - N DAYS/MONTHS/YEARS
                field_path, amount_str, unit = params[0], params[1], params[2]
                val = self._resolve_field(extraction, field_path)
                if val is None:
                    return True
                parsed = self._parse_date(val)
                if parsed is None:
                    return True
                delta = self._make_timedelta(int(amount_str), unit)
                return parsed >= date.today() - delta

            elif rule_type == "DATE_BEFORE_PAST":
                # field < TODAY - N YEARS
                field_path, amount_str, unit = params[0], params[1], params[2]
                val = self._resolve_field(extraction, field_path)
                if val is None:
                    return True
                parsed = self._parse_date(val)
                if parsed is None:
                    return True
                delta = self._make_timedelta(int(amount_str), unit)
                return parsed < date.today() - delta

            elif rule_type == "DATE_PLUS_DAYS":
                # field + N days > TODAY
                field_path, amount_str = params[0], params[1]
                val = self._resolve_field(extraction, field_path)
                if val is None:
                    return True
                parsed = self._parse_date(val)
                if parsed is None:
                    return True
                return parsed + timedelta(days=int(amount_str)) > date.today()

            elif rule_type == "DATE_WITHIN_RANGE":
                # field1 <= field2 + N DAYS
                field1, field2, days_str = params[0], params[1], params[2]
                val1 = self._resolve_field(extraction, field1)
                val2 = self._resolve_field(extraction, field2)
                if val1 is None or val2 is None:
                    return True
                parsed1 = self._parse_date(val1)
                parsed2 = self._parse_date(val2)
                if parsed1 is None or parsed2 is None:
                    return True
                return parsed1 <= parsed2 + timedelta(days=int(days_str))

            # ── Null Checks ───────────────────────────────────────────
            elif rule_type == "NOT_NULL":
                field_path = params[0]
                val = self._resolve_field(extraction, field_path)
                return val is not None and str(val).strip() != ""

            elif rule_type == "NOT_NULL_LENGTH":
                field_path, length_field, min_len_str = params[0], params[1], params[2]
                val = self._resolve_field(extraction, field_path)
                if val is None or str(val).strip() == "":
                    return False
                return len(str(val)) >= int(min_len_str)

            elif rule_type == "IS_NULL_OR":
                field_path, rest_rule = params[0], params[1]
                val = self._resolve_field(extraction, field_path)
                if val is None or str(val).strip() == "":
                    return True  # IS NULL → vacuously true
                # Evaluate the rest
                sub_type, sub_params = self._parse_rule(rest_rule)
                if sub_type is None or sub_type == "SKIP":
                    return True
                return self._evaluate_rule(extraction, sub_type, sub_params)

            # ── Equality Checks ───────────────────────────────────────
            elif rule_type in ("EQUALS", "EQUALS_STR"):
                field_path, expected = params[0], params[1]
                val = self._resolve_field(extraction, field_path)
                if val is None:
                    return True  # skip
                return str(val).strip().lower() == expected.strip().strip("'\"").lower()

            elif rule_type == "EQUALS_BOOL":
                field_path, expected = params[0], params[1]
                val = self._resolve_field(extraction, field_path)
                if val is None:
                    return True
                # Handle both bool and string representations
                val_bool = str(val).strip().lower() in ("true", "1", "yes", "si", "sí")
                expected_bool = expected.strip().lower() == "true"
                return val_bool == expected_bool

            elif rule_type == "NOT_EQUALS":
                field_path, expected = params[0], params[1]
                val = self._resolve_field(extraction, field_path)
                if val is None:
                    return True
                return str(val).strip().upper() != expected.strip().upper()

            # ── Numeric Checks ────────────────────────────────────────
            elif rule_type == "GREATER_THAN":
                field_path, threshold_str = params[0], params[1]
                val = self._resolve_field(extraction, field_path)
                if val is None:
                    return True
                try:
                    return float(val) > float(threshold_str)
                except (ValueError, TypeError):
                    return True  # unparseable = skip

            elif rule_type == "GREATER_EQUAL":
                field_path, threshold_str = params[0], params[1]
                val = self._resolve_field(extraction, field_path)
                if val is None:
                    return True
                try:
                    return float(val) >= float(threshold_str)
                except (ValueError, TypeError):
                    return True

            # ── Collection Checks ─────────────────────────────────────
            elif rule_type == "IN_LIST":
                field_path, list_str = params[0], params[1]
                val = self._resolve_field(extraction, field_path)
                if val is None:
                    return True
                # Parse list: "'FCFA', 'XAF'" → ["FCFA", "XAF"]
                items = [
                    item.strip().strip("'\"").upper()
                    for item in list_str.split(",")
                ]
                return str(val).strip().upper() in items

            # ── Pattern Checks ────────────────────────────────────────
            elif rule_type == "REGEX_MATCH":
                field_path, pattern = params[0], params[1]
                val = self._resolve_field(extraction, field_path)
                if val is None:
                    return True
                try:
                    return bool(re.match(pattern, str(val).strip()))
                except re.error:
                    logger.warning(f"Invalid regex in schema validation: {pattern}")
                    return True

            # ── String Checks ─────────────────────────────────────────
            elif rule_type == "CONTAINS":
                field_a, field_b = params[0], params[1]
                val_a = self._resolve_field(extraction, field_a)
                val_b = self._resolve_field(extraction, field_b)
                if val_a is None or val_b is None:
                    return True
                return str(val_b).strip().upper() in str(val_a).strip().upper()

            elif rule_type == "IN_SUBSTRING":
                field_path, target_field, start_str, end_str = params
                val = self._resolve_field(extraction, field_path)
                target = self._resolve_field(extraction, target_field)
                if val is None or target is None:
                    return True
                start, end = int(start_str), int(end_str)
                target_str = str(target)
                if end > len(target_str):
                    return True  # target too short = skip
                return str(val).strip().upper() in target_str[start:end].upper()

            elif rule_type == "IN_FIELD":
                field_path, target_field = params[0], params[1]
                val = self._resolve_field(extraction, field_path)
                target = self._resolve_field(extraction, target_field)
                if val is None or target is None:
                    return True
                return str(val).strip().upper() in str(target).strip().upper()

            elif rule_type == "EQUALS_CHAR_AT":
                field_path, target_field, index_str = params
                val = self._resolve_field(extraction, field_path)
                target = self._resolve_field(extraction, target_field)
                if val is None or target is None:
                    return True
                idx = int(index_str)
                target_str = str(target)
                if idx >= len(target_str):
                    return True  # index out of bounds = skip
                return str(val).strip().upper() == target_str[idx].upper()

            # ── Logical Operators ─────────────────────────────────────
            elif rule_type == "AND":
                left_str, right_str = params[0], params[1]
                left_type, left_params = self._parse_rule(left_str)
                right_type, right_params = self._parse_rule(right_str)
                left_result = True
                right_result = True
                if left_type and left_type != "SKIP":
                    left_result = self._evaluate_rule(extraction, left_type, left_params)
                if right_type and right_type != "SKIP":
                    right_result = self._evaluate_rule(extraction, right_type, right_params)
                return left_result and right_result

            elif rule_type == "OR":
                left_str, right_str = params[0], params[1]
                left_type, left_params = self._parse_rule(left_str)
                right_type, right_params = self._parse_rule(right_str)
                left_result = False
                right_result = False
                if left_type and left_type != "SKIP":
                    left_result = self._evaluate_rule(extraction, left_type, left_params)
                if right_type and right_type != "SKIP":
                    right_result = self._evaluate_rule(extraction, right_type, right_params)
                return left_result or right_result

            # ── Conditional Operators ─────────────────────────────────
            elif rule_type == "IF_NOT_THEN":
                condition_field, consequence_str = params[0], params[1]
                cond_val = self._resolve_field(extraction, condition_field)
                # If condition is truthy → rule doesn't apply → pass
                cond_truthy = (
                    cond_val is not None
                    and str(cond_val).strip().lower() not in ("", "false", "0", "no", "null")
                )
                if cond_truthy:
                    return True  # condition is true, so !condition is false → skip
                # Condition is falsy → evaluate consequence
                sub_type, sub_params = self._parse_rule(consequence_str)
                if sub_type is None or sub_type == "SKIP":
                    return True
                return self._evaluate_rule(extraction, sub_type, sub_params)

            elif rule_type in ("IF_THEN", "IMPLIES"):
                condition_str, consequence_str = params[0], params[1]
                # Try to parse condition as an expression first
                cond_type, cond_params = self._parse_rule(condition_str)
                if cond_type and cond_type != "SKIP":
                    cond_truthy = self._evaluate_rule(extraction, cond_type, cond_params)
                else:
                    # Fallback: treat as simple field path (truthy check)
                    cond_val = self._resolve_field(extraction, condition_str.strip())
                    cond_truthy = (
                        cond_val is not None
                        and str(cond_val).strip().lower() not in ("", "false", "0", "no", "null")
                    )

                if not cond_truthy:
                    return True  # vacuously true
                # Condition is true → evaluate consequence
                sub_type, sub_params = self._parse_rule(consequence_str)
                if sub_type is None or sub_type == "SKIP":
                    return True
                return self._evaluate_rule(extraction, sub_type, sub_params)

            else:
                logger.debug(f"Schema validation: unknown rule type: {rule_type}")
                return True

        except Exception as e:
            logger.debug(f"Schema validation rule evaluation error ({rule_type}): {e}")
            return True  # On error, skip (don't produce false positive)
