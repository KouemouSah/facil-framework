"""
Shared validation types for schema_validation_engine and mrz_validator.

Extracted to break circular import:
  schema_validation_engine -> mrz_validator -> schema_validation_engine
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class ValidationResult:
    """Result of evaluating a single schema validation rule."""
    rule_id: str
    passed: bool
    severity: str
    message_es: str
    message_fr: str
    rule: str
    document_code: str

    def to_risk_factor(self) -> Dict[str, Any]:
        """Convert to risk_factor dict for RiskAnalyzer compatibility."""
        return {
            "code": "SCHEMA_VALIDATION_FAILED",
            "severity": "medium" if self.severity == "error" else "low",
            "message": self.message_es,
            "detail": {
                "validation_id": self.rule_id,
                "rule": self.rule,
                "document_code": self.document_code,
                "error_fr": self.message_fr,
            },
            "action": "warn"
        }
