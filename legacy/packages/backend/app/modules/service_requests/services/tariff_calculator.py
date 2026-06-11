"""
TariffCalculator - Unified tariff calculation with explicit logic.

This module provides a unified interface for tariff calculation that handles
both PredefinedWorkflows (hardcoded tariffs) and GenericWorkflows (DB-based).

Key principle: NO SILENT FALLBACKS. Explicit logic determines the source:
- PredefinedWorkflow → Use workflow.get_tariff_breakdown() (hardcoded in code)
- GenericWorkflow → Use TariffService.calculate() (from database)

This prevents the bug where TariffService returns 0 for workflows
that have tariffs defined in code rather than database.
"""

import asyncpg
from typing import Dict, Any, Optional
import logging

from ..workflows.workflow_interface import (
    PredefinedWorkflow,
    WorkflowContext,
    RenovacionMotivo,
)
from ..models.enums import SolicitudType
from .tariff_service import tariff_service

logger = logging.getLogger(__name__)

# All workflows are now v2 (PredefinedWorkflow)
AnyWorkflow = PredefinedWorkflow


class TariffCalculator:
    """
    Unified tariff calculator with explicit workflow type handling.

    Usage:
        calculator = TariffCalculator()
        breakdown = await calculator.calculate(db, workflow, context)
    """

    async def calculate(
        self,
        db: asyncpg.Connection,
        workflow: AnyWorkflow,
        context: WorkflowContext,
        include_penalties: bool = False,
        days_late: int = 0
    ) -> Dict[str, Any]:
        """
        Calculate tariff with explicit workflow type handling.

        Args:
            db: Database connection
            workflow: The workflow instance (Predefined or Generic)
            context: Workflow context with solicitud_type, motivo, etc.
            include_penalties: Whether to include late penalties
            days_late: Days late for penalty calculation

        Returns:
            TariffBreakdown dict:
            {
                "base_amount": int,
                "base_description": str,
                "supplements": [{"code", "name_es", "unit_price", "quantity", "subtotal"}],
                "supplements_total": int,
                "penalties_amount": int,
                "penalty_reason": str | None,
                "total_amount": int,
                "currency": str,
                "tariff_type": str,
                "workflow_code": str,
                "solicitud_type": str,
                "source": str  # "predefined" or "database"
            }
        """
        # Determine workflow type and calculate accordingly
        # GenericWorkflow (DB-driven) sets is_generic=True; all others use hardcoded tariffs
        if getattr(workflow, 'is_generic', False):
            breakdown = await self._calculate_from_database(db, workflow, context)
            breakdown["source"] = "database"
        else:
            breakdown = self._calculate_from_predefined(workflow, context)
            breakdown["source"] = "predefined"

        # Add penalties if requested
        if include_penalties and days_late > 0:
            breakdown = self._apply_penalties(breakdown, days_late)

        logger.debug(
            f"Tariff calculated for {context.workflow_code.value}: "
            f"{breakdown['total_amount']} XAF (source: {breakdown['source']})"
        )

        return breakdown

    def _calculate_from_predefined(
        self,
        workflow: PredefinedWorkflow,
        context: WorkflowContext
    ) -> Dict[str, Any]:
        """
        Calculate tariff from PredefinedWorkflow (hardcoded in code).

        Uses workflow.get_tariff_breakdown() which includes:
        - Base amount from TariffConfig.fixed_amounts
        - Supplements from TariffConfig.supplements
        """
        # Get solicitud_type and motivo from context
        solicitud_type = context.solicitud_type or SolicitudType.EXPEDICION
        motivo = context.motivo

        # Use the workflow's get_tariff_breakdown method
        breakdown = workflow.get_tariff_breakdown(
            solicitud_type=solicitud_type,
            motivo=motivo,
            context=context,
            base_description=workflow.service_name_es
        )

        return breakdown

    async def _calculate_from_database(
        self,
        db: asyncpg.Connection,
        workflow: AnyWorkflow,
        context: WorkflowContext
    ) -> Dict[str, Any]:
        """
        Calculate tariff from database (GenericWorkflow).

        Uses TariffService.calculate() which queries:
        - workflow_tariffs table for base amount
        - workflow_supplement_config + tariff_supplements for supplements
        """
        workflow_code = context.workflow_code.value
        solicitud_type = context.solicitud_type.value if context.solicitud_type else "expedicion"

        # Call TariffService
        result = await tariff_service.calculate(
            db=db,
            workflow_code=workflow_code,
            solicitud_type=solicitud_type,
            extracted_data=context.form_data
        )

        # Ensure all required fields are present
        breakdown = {
            "base_amount": result.get("base_amount", 0),
            "base_description": result.get("base_description", ""),
            "supplements": result.get("supplements", []),
            "supplements_total": result.get("supplements_total", 0),
            "penalties_amount": result.get("penalties_amount", 0),
            "penalty_reason": result.get("penalty_reason"),
            "total_amount": result.get("total_amount", 0),
            "currency": result.get("currency", "XAF"),
            "tariff_type": result.get("tariff_type", "FIXED"),
            "workflow_code": workflow_code,
            "solicitud_type": solicitud_type,
        }

        # Log warning if no tariff found
        if breakdown["total_amount"] == 0:
            logger.warning(
                f"No tariff found in database for {workflow_code}/{solicitud_type}. "
                f"Consider adding to workflow_tariffs table or using PredefinedWorkflow."
            )

        return breakdown

    def _apply_penalties(
        self,
        breakdown: Dict[str, Any],
        days_late: int
    ) -> Dict[str, Any]:
        """
        Apply late penalties to tariff breakdown.

        Penalty tiers:
        - 1-30 days: 10% of base
        - 31-60 days: 20% of base
        - 61-90 days: 30% of base
        - 90+ days: 50% of base
        """
        if days_late <= 0:
            return breakdown

        base_amount = breakdown.get("base_amount", 0)

        # Determine penalty rate
        if days_late <= 30:
            rate = 10
            tier = "1-30 dias"
        elif days_late <= 60:
            rate = 20
            tier = "31-60 dias"
        elif days_late <= 90:
            rate = 30
            tier = "61-90 dias"
        else:
            rate = 50
            tier = "90+ dias"

        penalty_amount = int(base_amount * rate / 100)

        # Update breakdown
        breakdown["penalties_amount"] = penalty_amount
        breakdown["penalty_reason"] = f"Recargo por renovacion tardia ({tier}): {rate}%"
        breakdown["total_amount"] = (
            breakdown["base_amount"] +
            breakdown["supplements_total"] +
            penalty_amount
        )

        return breakdown

    async def get_payment_info(
        self,
        db: asyncpg.Connection,
        workflow: AnyWorkflow,
        context: WorkflowContext
    ) -> Dict[str, Any]:
        """
        Get complete payment information for payment step.

        Returns tariff breakdown plus payment configuration.
        """
        breakdown = await self.calculate(db, workflow, context)

        return {
            "amount": breakdown["total_amount"],
            "currency": breakdown["currency"],
            "tariff_breakdown": breakdown,
            "requires_payment": breakdown["total_amount"] > 0,
        }


# Singleton instance
tariff_calculator = TariffCalculator()
