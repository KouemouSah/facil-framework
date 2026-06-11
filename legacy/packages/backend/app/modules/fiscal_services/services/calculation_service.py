"""
Calculation Service - Calculate fiscal service amounts

Implements all calculation methods from CalculationMethodEnum:
- fixed_expedition, fixed_renewal, fixed_both
- percentage_based, unit_based
- tiered_rates, formula_based, fixed_plus_unit
"""

from typing import Dict, Any, Optional, List
from loguru import logger
import asyncpg

from app.modules.fiscal_services.models.fiscal_service import (
    CalculationMethodEnum,
    CalculationInput,
    CalculationResult,
    CalculationBreakdown,
    RateTier,
)


class CalculationService:
    """Service for calculating fiscal service amounts based on database configuration"""

    async def calculate(
        self,
        conn: asyncpg.Connection,
        calculation_input: CalculationInput,
    ) -> CalculationResult:
        """
        Calculate amount for fiscal service based on its configuration

        Args:
            conn: Database connection
            calculation_input: Calculation parameters

        Returns:
            CalculationResult with detailed breakdown

        Raises:
            ValueError: If service not found or invalid configuration
        """
        # Get fiscal service from database — only columns needed for calculation
        service = await conn.fetchrow(
            """
            SELECT id, service_code, name_es, calculation_method, status,
                   tasa_expedicion, tasa_renovacion,
                   base_percentage, percentage_of, unit_rate, unit_type,
                   expedition_formula, expedition_unit_measure,
                   renewal_formula, renewal_unit_measure,
                   calculation_config, rate_tiers,
                   tier_group_name, is_tier_component,
                   grace_period_days, late_penalty_percentage, late_penalty_fixed,
                   penalty_calculation_rules
            FROM fiscal_services
            WHERE id = $1 AND status = 'active'
            """,
            calculation_input.fiscal_service_id
        )

        if not service:
            raise ValueError(
                f"Fiscal service {calculation_input.fiscal_service_id} not found or inactive"
            )

        service_dict = dict(service)
        calculation_method = service_dict["calculation_method"]
        is_renewal = calculation_input.is_renewal

        logger.info(
            f"Calculating {calculation_method} for service {service_dict['service_code']} "
            f"(renewal={is_renewal})"
        )

        # Route to appropriate calculation method
        if calculation_method == CalculationMethodEnum.FIXED_EXPEDITION.value:
            breakdown = await self._calculate_fixed_expedition(service_dict, is_renewal)

        elif calculation_method == CalculationMethodEnum.FIXED_RENEWAL.value:
            breakdown = await self._calculate_fixed_renewal(service_dict, is_renewal)

        elif calculation_method == CalculationMethodEnum.FIXED_BOTH.value:
            breakdown = await self._calculate_fixed_both(service_dict, is_renewal)

        elif calculation_method == CalculationMethodEnum.PERCENTAGE_BASED.value:
            breakdown = await self._calculate_percentage_based(
                service_dict, is_renewal, calculation_input
            )

        elif calculation_method == CalculationMethodEnum.UNIT_BASED.value:
            breakdown = await self._calculate_unit_based(
                service_dict, is_renewal, calculation_input
            )

        elif calculation_method == CalculationMethodEnum.TIERED_RATES.value:
            breakdown = await self._calculate_tiered_rates(
                service_dict, is_renewal, calculation_input
            )

        elif calculation_method == CalculationMethodEnum.FORMULA_BASED.value:
            breakdown = await self._calculate_formula_based(
                service_dict, is_renewal, calculation_input
            )

        elif calculation_method == CalculationMethodEnum.FIXED_PLUS_UNIT.value:
            breakdown = await self._calculate_fixed_plus_unit(
                service_dict, is_renewal, calculation_input
            )

        else:
            raise ValueError(f"Unknown calculation method: {calculation_method}")

        # Build result
        result = CalculationResult(
            fiscal_service_id=service_dict["id"],
            service_code=service_dict["service_code"],
            service_name=service_dict["name_es"],
            calculation_method=CalculationMethodEnum(calculation_method),
            breakdown=breakdown,
            amount_gnf=breakdown.total,
            currency="GNF",
        )

        logger.info(
            f"Calculated amount for {service_dict['service_code']}: {breakdown.total} GNF"
        )

        return result

    # ═══════════════════════════════════════════════════════════════════════
    # Fixed Amount Methods
    # ═══════════════════════════════════════════════════════════════════════

    async def _calculate_fixed_expedition(
        self, service: Dict[str, Any], is_renewal: bool
    ) -> CalculationBreakdown:
        """Fixed fee for first issuance only"""
        if is_renewal:
            amount = 0.0
            note = "No fee for renewal (fixed_expedition only)"
        else:
            amount = service.get("tasa_expedicion") or 0.0
            note = "Fixed expedition fee"

        return CalculationBreakdown(
            method=CalculationMethodEnum.FIXED_EXPEDITION,
            is_renewal=is_renewal,
            base_fee=amount,
            subtotal=amount,
            total=amount,
        )

    async def _calculate_fixed_renewal(
        self, service: Dict[str, Any], is_renewal: bool
    ) -> CalculationBreakdown:
        """Fixed fee for renewal only"""
        if is_renewal:
            amount = service.get("tasa_renovacion") or 0.0
            note = "Fixed renewal fee"
        else:
            amount = 0.0
            note = "No fee for first expedition (fixed_renewal only)"

        return CalculationBreakdown(
            method=CalculationMethodEnum.FIXED_RENEWAL,
            is_renewal=is_renewal,
            base_fee=amount,
            subtotal=amount,
            total=amount,
        )

    async def _calculate_fixed_both(
        self, service: Dict[str, Any], is_renewal: bool
    ) -> CalculationBreakdown:
        """Same fixed fee for both expedition and renewal"""
        # For fixed_both, tasa_expedicion should be set
        amount = service.get("tasa_expedicion") or 0.0

        return CalculationBreakdown(
            method=CalculationMethodEnum.FIXED_BOTH,
            is_renewal=is_renewal,
            base_fee=amount,
            subtotal=amount,
            total=amount,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # Variable Amount Methods
    # ═══════════════════════════════════════════════════════════════════════

    async def _calculate_percentage_based(
        self, service: Dict[str, Any], is_renewal: bool, input_data: CalculationInput
    ) -> CalculationBreakdown:
        """Percentage of a base value"""
        if input_data.base_value is None:
            raise ValueError("base_value required for percentage_based calculation")

        percentage = service.get("base_percentage") or 0.0
        base_value = input_data.base_value

        amount = (base_value * percentage) / 100

        return CalculationBreakdown(
            method=CalculationMethodEnum.PERCENTAGE_BASED,
            is_renewal=is_renewal,
            variable_amount=amount,
            formula_used=f"{base_value} × {percentage}% = {amount}",
            subtotal=amount,
            total=amount,
        )

    async def _calculate_unit_based(
        self, service: Dict[str, Any], is_renewal: bool, input_data: CalculationInput
    ) -> CalculationBreakdown:
        """Price per unit × quantity"""
        if input_data.quantity is None:
            raise ValueError("quantity required for unit_based calculation")

        unit_rate = service.get("unit_rate") or 0.0
        quantity = input_data.quantity

        amount = unit_rate * quantity

        return CalculationBreakdown(
            method=CalculationMethodEnum.UNIT_BASED,
            is_renewal=is_renewal,
            variable_amount=amount,
            formula_used=f"{unit_rate} × {quantity} units = {amount}",
            subtotal=amount,
            total=amount,
        )

    async def _calculate_tiered_rates(
        self, service: Dict[str, Any], is_renewal: bool, input_data: CalculationInput
    ) -> CalculationBreakdown:
        """Progressive rate tiers (like income tax)"""
        if input_data.total_amount is None:
            raise ValueError("total_amount required for tiered_rates calculation")

        total_amount = input_data.total_amount
        rate_tiers = service.get("rate_tiers") or []

        if not rate_tiers:
            raise ValueError("rate_tiers not configured for this service")

        # Apply progressive tiers
        calculated_amount = 0.0
        tiers_applied = []

        for tier in rate_tiers:
            min_val = tier.get("min_value", 0)
            max_val = tier.get("max_value")  # None = unlimited
            rate = tier.get("rate", 0)

            # Determine amount in this tier
            if max_val is None:
                # Last tier - unlimited
                if total_amount > min_val:
                    tier_amount = total_amount - min_val
                    tier_tax = tier_amount * (rate / 100)
                    calculated_amount += tier_tax
                    tiers_applied.append({
                        "tier": f"{min_val}+",
                        "amount_in_tier": tier_amount,
                        "rate": rate,
                        "tax": tier_tax,
                    })
            else:
                # Regular tier with max
                if total_amount > min_val:
                    tier_amount = min(total_amount, max_val) - min_val
                    tier_tax = tier_amount * (rate / 100)
                    calculated_amount += tier_tax
                    tiers_applied.append({
                        "tier": f"{min_val}-{max_val}",
                        "amount_in_tier": tier_amount,
                        "rate": rate,
                        "tax": tier_tax,
                    })

        return CalculationBreakdown(
            method=CalculationMethodEnum.TIERED_RATES,
            is_renewal=is_renewal,
            variable_amount=calculated_amount,
            tiers_applied=tiers_applied,
            subtotal=calculated_amount,
            total=calculated_amount,
        )

    async def _calculate_formula_based(
        self, service: Dict[str, Any], is_renewal: bool, input_data: CalculationInput
    ) -> CalculationBreakdown:
        """
        Custom formula calculation

        Uses calculation_config JSONB field which should contain:
        {
            "formula": "base_value * factor + fixed_amount",
            "variables": {
                "factor": 0.05,
                "fixed_amount": 10000
            }
        }
        """
        calculation_config = service.get("calculation_config")
        if not calculation_config:
            raise ValueError("calculation_config not set for formula_based method")

        # Simple formula evaluation (extend as needed)
        variables = input_data.variables or {}
        config_vars = calculation_config.get("variables", {})

        # Merge user variables with config variables
        all_vars = {**config_vars, **variables}

        formula = calculation_config.get("formula", "")

        # Basic formula evaluation (can be extended with safe_eval or similar)
        # For now, support simple operations
        try:
            # Create local namespace with variables
            namespace = {**all_vars}
            amount = eval(formula, {"__builtins__": {}}, namespace)
        except Exception as e:
            logger.error(f"Formula evaluation error: {e}")
            raise ValueError(f"Invalid formula: {formula}")

        return CalculationBreakdown(
            method=CalculationMethodEnum.FORMULA_BASED,
            is_renewal=is_renewal,
            variable_amount=amount,
            formula_used=formula,
            subtotal=amount,
            total=amount,
        )

    async def _calculate_fixed_plus_unit(
        self, service: Dict[str, Any], is_renewal: bool, input_data: CalculationInput
    ) -> CalculationBreakdown:
        """Base fixed fee + per-unit charge"""
        if input_data.quantity is None:
            raise ValueError("quantity required for fixed_plus_unit calculation")

        # Base fee depends on expedition vs renewal
        if is_renewal:
            base_fee = service.get("tasa_renovacion") or 0.0
        else:
            base_fee = service.get("tasa_expedicion") or 0.0

        # Per-unit charge
        unit_rate = service.get("unit_rate") or 0.0
        quantity = input_data.quantity
        variable_amount = unit_rate * quantity

        total = base_fee + variable_amount

        return CalculationBreakdown(
            method=CalculationMethodEnum.FIXED_PLUS_UNIT,
            is_renewal=is_renewal,
            base_fee=base_fee,
            variable_amount=variable_amount,
            formula_used=f"{base_fee} + ({unit_rate} × {quantity}) = {total}",
            subtotal=total,
            total=total,
        )
