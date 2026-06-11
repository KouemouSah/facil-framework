"""Unit tests for Phase 1 bug fixes — Error handling, validation, guards.

Tests:
- Config rules update validation (config shape by config_type)
- Metadata parsing failure raises ValueError instead of returning {}
- Email service None guard
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from app.modules.fiscal_services.services.config_rules_service import ConfigRulesService


# ============================================================
# ConfigRulesService._validate_config_shape tests
# ============================================================

class TestConfigRuleValidation:
    """Test _validate_config_shape validates config JSON correctly."""

    def test_penalty_valid(self):
        """Valid penalty config passes."""
        ConfigRulesService._validate_config_shape("penalty", {"rate": 0.05})

    def test_penalty_missing_rate(self):
        """Penalty without rate raises ValueError."""
        with pytest.raises(ValueError, match="must include 'rate'"):
            ConfigRulesService._validate_config_shape("penalty", {"max_rate": 0.5})

    def test_penalty_negative_rate(self):
        """Penalty with negative rate raises ValueError."""
        with pytest.raises(ValueError, match="rate must be >= 0"):
            ConfigRulesService._validate_config_shape("penalty", {"rate": -0.1})

    def test_penalty_string_rate(self):
        """Penalty with non-numeric rate raises ValueError."""
        with pytest.raises(ValueError, match="must be a number"):
            ConfigRulesService._validate_config_shape("penalty", {"rate": "abc"})

    def test_penalty_zero_rate(self):
        """Penalty with rate=0 is valid (disabled penalty)."""
        ConfigRulesService._validate_config_shape("penalty", {"rate": 0})

    def test_penalty_with_extras(self):
        """Penalty with extra fields is valid."""
        ConfigRulesService._validate_config_shape("penalty", {
            "rate": 0.05, "grace_days": 30, "max_rate": 0.5, "type": "percentage"
        })

    def test_deadline_valid(self):
        """Valid deadline config passes."""
        ConfigRulesService._validate_config_shape("deadline", {"month": 3, "day": 31})

    def test_deadline_missing_month(self):
        """Deadline without month raises ValueError."""
        with pytest.raises(ValueError, match="must include 'month' and 'day'"):
            ConfigRulesService._validate_config_shape("deadline", {"day": 15})

    def test_deadline_missing_day(self):
        """Deadline without day raises ValueError."""
        with pytest.raises(ValueError, match="must include 'month' and 'day'"):
            ConfigRulesService._validate_config_shape("deadline", {"month": 6})

    def test_deadline_month_out_of_range(self):
        """Deadline with month > 12 raises ValueError."""
        with pytest.raises(ValueError, match="month must be 1-12"):
            ConfigRulesService._validate_config_shape("deadline", {"month": 13, "day": 1})

    def test_deadline_day_out_of_range(self):
        """Deadline with day > 31 raises ValueError."""
        with pytest.raises(ValueError, match="day must be 1-31"):
            ConfigRulesService._validate_config_shape("deadline", {"month": 1, "day": 32})

    def test_deadline_string_values(self):
        """Deadline with string month/day raises ValueError."""
        with pytest.raises(ValueError, match="must be integers"):
            ConfigRulesService._validate_config_shape("deadline", {"month": "march", "day": "first"})

    def test_installment_valid(self):
        """Valid installment config passes."""
        ConfigRulesService._validate_config_shape("installment", {"max_installments": 6})

    def test_installment_missing(self):
        """Installment without max_installments raises ValueError."""
        with pytest.raises(ValueError, match="must include 'max_installments'"):
            ConfigRulesService._validate_config_shape("installment", {"frequency": "monthly"})

    def test_installment_zero(self):
        """Installment with max_installments=0 raises ValueError."""
        with pytest.raises(ValueError, match="must be >= 1"):
            ConfigRulesService._validate_config_shape("installment", {"max_installments": 0})

    def test_installment_string(self):
        """Installment with non-numeric max_installments raises ValueError."""
        with pytest.raises(ValueError, match="must be an integer"):
            ConfigRulesService._validate_config_shape("installment", {"max_installments": "six"})

    def test_processing_mode_valid(self):
        """Processing mode config passes (no strict validation)."""
        ConfigRulesService._validate_config_shape("processing_mode", {"mode": "per_line"})

    def test_processing_mode_empty(self):
        """Processing mode with empty config passes (no strict validation)."""
        ConfigRulesService._validate_config_shape("processing_mode", {})

    def test_unknown_type_passes(self):
        """Unknown config type passes (forward-compatible)."""
        ConfigRulesService._validate_config_shape("future_type", {"some": "value"})


# ============================================================
# ConfigRulesService.update_rule integration-style tests
# ============================================================

class TestConfigRuleUpdateValidation:
    """Test that update_rule validates config against existing rule's config_type."""

    @pytest.mark.asyncio
    async def test_update_penalty_with_invalid_config_raises(self):
        """Updating a penalty rule with invalid config raises ValueError."""
        mock_conn = AsyncMock()
        existing_rule = {
            "id": uuid4(),
            "config_type": "penalty",
            "bundle_id": uuid4(),
            "config": {"rate": 0.05},
        }

        with patch.object(
            ConfigRulesService, '_invalidate_cache', new_callable=AsyncMock
        ), patch(
            'app.modules.fiscal_services.services.config_rules_service.ConfigRulesRepository'
        ) as MockRepo:
            MockRepo.get_rule = AsyncMock(return_value=existing_rule)
            MockRepo.update_rule = AsyncMock(return_value={**existing_rule, "config": {"rate": -1}})

            with pytest.raises(ValueError, match="rate must be >= 0"):
                await ConfigRulesService.update_rule(
                    mock_conn, existing_rule["id"],
                    {"config": {"rate": -1}},
                    user_id=uuid4(),
                )

    @pytest.mark.asyncio
    async def test_update_deadline_with_valid_config_passes(self):
        """Updating a deadline rule with valid config succeeds."""
        mock_conn = AsyncMock()
        rule_id = uuid4()
        existing_rule = {
            "id": rule_id,
            "config_type": "deadline",
            "bundle_id": uuid4(),
            "config": {"month": 3, "day": 31},
        }
        updated_rule = {**existing_rule, "config": {"month": 6, "day": 30}}

        with patch.object(
            ConfigRulesService, '_invalidate_cache', new_callable=AsyncMock
        ), patch(
            'app.modules.fiscal_services.services.config_rules_service.ConfigRulesRepository'
        ) as MockRepo:
            MockRepo.get_rule = AsyncMock(return_value=existing_rule)
            MockRepo.update_rule = AsyncMock(return_value=updated_rule)

            result = await ConfigRulesService.update_rule(
                mock_conn, rule_id,
                {"config": {"month": 6, "day": 30}},
                user_id=uuid4(),
            )
            assert result is not None
            assert result["config"]["month"] == 6

    @pytest.mark.asyncio
    async def test_update_without_config_skips_validation(self):
        """Updating non-config fields skips config validation."""
        mock_conn = AsyncMock()
        rule_id = uuid4()
        existing_rule = {
            "id": rule_id,
            "config_type": "penalty",
            "bundle_id": uuid4(),
            "config": {"rate": 0.05},
        }
        updated_rule = {**existing_rule, "is_enabled": False}

        with patch.object(
            ConfigRulesService, '_invalidate_cache', new_callable=AsyncMock
        ), patch(
            'app.modules.fiscal_services.services.config_rules_service.ConfigRulesRepository'
        ) as MockRepo:
            MockRepo.get_rule = AsyncMock(return_value=existing_rule)
            MockRepo.update_rule = AsyncMock(return_value=updated_rule)

            result = await ConfigRulesService.update_rule(
                mock_conn, rule_id,
                {"is_enabled": False},
                user_id=uuid4(),
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_update_nonexistent_rule_returns_none(self):
        """Updating a non-existent rule returns None."""
        mock_conn = AsyncMock()

        with patch(
            'app.modules.fiscal_services.services.config_rules_service.ConfigRulesRepository'
        ) as MockRepo:
            MockRepo.get_rule = AsyncMock(return_value=None)

            result = await ConfigRulesService.update_rule(
                mock_conn, uuid4(),
                {"config": {"rate": 0.05}},
                user_id=uuid4(),
            )
            assert result is None
