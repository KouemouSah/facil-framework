"""
Tariff Service for calculating workflow costs.
Uses workflow_tariffs and tariff_supplements tables from migration 022.

Supports:
- FIXED: Fixed amounts from workflow_tariffs table
- PERCENTAGE: Percentage of value (e.g., ONRC 0.5% of contract value)
- RBC: Risk-Based Calculator for vehicles (based on age, type, value)
- NOTA_INGRESO: Treasury-generated amounts
"""
import asyncpg
from typing import Dict, Optional, List
from decimal import Decimal
from enum import Enum
import logging

from app.core.jsonb import ensure_list

logger = logging.getLogger(__name__)


class TariffType(str, Enum):
    """Types of tariff calculation."""
    FIXED = "FIXED"
    PERCENTAGE = "PERCENTAGE"
    RBC = "RBC"
    NOTA_INGRESO = "NOTA_INGRESO"


# Currency conversion rates (XAF is base currency)
CONVERSION_RATES = {
    "XAF": 1.0,
    "EUR": 655.957,  # Official CFA/EUR peg
    "USD": 600.0     # Approximate
}


class TariffService:
    """
    Calculate tariffs using workflow_tariffs and tariff_supplements.
    Supports FIXED, PERCENTAGE, RBC, and NOTA_INGRESO tariff types.
    """

    async def calculate(
        self,
        db: asyncpg.Connection,
        workflow_code: str,
        solicitud_type: str = "expedicion",
        extracted_data: Optional[Dict] = None,
        tariff_type: Optional[str] = None
    ) -> Dict:
        """
        Calculate total tariff for a workflow.

        Args:
            db: Database connection
            workflow_code: The workflow code (e.g., "PASAPORTE_NUEVO", "CONTRATO_OBRA")
            solicitud_type: Type of request (expedicion, renovacion, duplicado)
            extracted_data: Optional extracted data for dynamic calculations
            tariff_type: Override tariff type (FIXED, PERCENTAGE, RBC, NOTA_INGRESO)

        Returns:
            Tariff breakdown with base, supplements, and total
        """
        try:
            # Determine tariff type from workflow or override
            effective_tariff_type = tariff_type or await self._get_tariff_type(db, workflow_code, solicitud_type)

            # Calculate based on type
            if effective_tariff_type == TariffType.PERCENTAGE.value:
                return await self._calculate_percentage_tariff(
                    db, workflow_code, solicitud_type, extracted_data
                )
            elif effective_tariff_type == TariffType.RBC.value:
                return await self._calculate_rbc_tariff(
                    db, workflow_code, solicitud_type, extracted_data
                )
            elif effective_tariff_type == TariffType.NOTA_INGRESO.value:
                return await self._calculate_nota_ingreso_tariff(
                    db, workflow_code, extracted_data
                )
            else:
                # Default: FIXED tariff from database
                return await self._calculate_fixed_tariff(
                    db, workflow_code, solicitud_type
                )

        except Exception as e:
            logger.error(f"Error calculating tariff: {e}")
            return self._empty_tariff()

    async def _get_tariff_type(
        self,
        db: asyncpg.Connection,
        workflow_code: str,
        solicitud_type: str = "expedicion"
    ) -> str:
        """
        Determine tariff type for a workflow from database configuration.

        Args:
            db: Database connection
            workflow_code: The workflow code
            solicitud_type: Type of request (expedicion, renovacion, duplicado)

        Priority:
        1. Read from workflow_tariffs.tariff_type for specific solicitud_type
        2. Default to FIXED if not found
        """
        query = """
            SELECT tariff_type
            FROM workflow_tariffs
            WHERE workflow_code = $1
              AND solicitud_type = $2
              AND is_active = TRUE
              AND effective_from <= CURRENT_DATE
              AND (effective_to IS NULL OR effective_to > CURRENT_DATE)
            ORDER BY effective_from DESC
            LIMIT 1
        """
        try:
            row = await db.fetchrow(query, workflow_code, solicitud_type)
            if row and row["tariff_type"]:
                return row["tariff_type"]
        except Exception as e:
            logger.warning(f"Could not get tariff_type from DB: {e}")

        # Default to FIXED
        return TariffType.FIXED.value

    async def _calculate_fixed_tariff(
        self,
        db: asyncpg.Connection,
        workflow_code: str,
        solicitud_type: str
    ) -> Dict:
        """Calculate fixed tariff from database."""
        try:
            query = "SELECT * FROM get_workflow_tariff_total($1, $2)"
            row = await db.fetchrow(query, workflow_code, solicitud_type)

            if not row:
                logger.warning(f"No tariff found for workflow: {workflow_code}/{solicitud_type}")
                return self._empty_tariff()

            return {
                "tariff_type": row.get("tariff_type", TariffType.FIXED.value),
                "base_amount": float(row["base_amount"]),
                "supplements": ensure_list(row["supplements"]),
                "supplements_total": float(row["supplements_total"]),
                "penalties_amount": 0.0,
                "total_amount": float(row["total_amount"]),
                "currency": row["currency"] or "XAF"
            }

        except Exception as e:
            logger.error(f"Error calculating fixed tariff: {e}")
            return self._empty_tariff()

    async def _calculate_percentage_tariff(
        self,
        db: asyncpg.Connection,
        workflow_code: str,
        solicitud_type: str,
        extracted_data: Optional[Dict]
    ) -> Dict:
        """
        Calculate percentage-based tariff (e.g., ONRC contracts).

        Reads percentage_rate from workflow_tariffs table (admin configurable).
        Default: 0.5% for ONRC if not configured.
        """
        # Get percentage configuration from database
        percentage = await self._get_percentage_rate(db, workflow_code, solicitud_type)
        if percentage is None:
            percentage = 0.5  # Default ONRC rate

        # Get value from extracted data
        base_value = 0.0
        currency = "XAF"

        if extracted_data:
            # For CONTRATO workflows
            if "contrato" in extracted_data:
                contrato = extracted_data["contrato"]
                if "valor_contrato" in contrato:
                    base_value = float(contrato["valor_contrato"].get("monto_total", 0))
                    currency = contrato["valor_contrato"].get("moneda", "XAF")
            # Direct form_data
            elif "monto_total" in extracted_data:
                base_value = float(extracted_data.get("monto_total", 0))
                currency = extracted_data.get("moneda", "XAF")

        # Convert to XAF if needed
        conversion_rate = CONVERSION_RATES.get(currency, 1.0)
        base_value_xaf = base_value * conversion_rate

        # Calculate percentage (e.g., 0.5% = 0.005)
        tariff_amount = int(base_value_xaf * (percentage / 100))

        # Get supplements
        supplements = await self.get_supplements(db, workflow_code)
        supplements_total = sum(s.get("subtotal", 0) for s in supplements)

        total = tariff_amount + supplements_total

        return {
            "tariff_type": TariffType.PERCENTAGE.value,
            "percentage_rate": percentage,
            "base_value": base_value,
            "base_currency": currency,
            "base_value_xaf": base_value_xaf,
            "base_amount": float(tariff_amount),
            "supplements": supplements,
            "supplements_total": float(supplements_total),
            "penalties_amount": 0.0,
            "total_amount": float(total),
            "currency": "XAF",
            "calculation_formula": f"{base_value:,.0f} {currency} × {percentage}% = {tariff_amount:,} XAF"
        }

    async def _calculate_rbc_tariff(
        self,
        db: asyncpg.Connection,
        workflow_code: str,
        solicitud_type: str,
        extracted_data: Optional[Dict]
    ) -> Dict:
        """
        Calculate Risk-Based Calculator tariff for vehicles.

        Factors considered:
        - Vehicle type (car, motorcycle, truck, etc.)
        - Vehicle age
        - Engine capacity (cylindrée)
        - Vehicle value
        - First registration vs transfer
        """
        if not extracted_data:
            return self._empty_tariff()

        # Extract vehicle data
        vehicle_type = extracted_data.get("tipo_vehiculo", "TURISMO")
        vehicle_age = extracted_data.get("antiguedad_anos", 0)
        engine_cc = extracted_data.get("cilindrada", 0)
        vehicle_value = float(extracted_data.get("valor_vehiculo", 0))
        is_first_registration = "PRIMERA" in workflow_code

        # Base rate by vehicle type (XAF)
        base_rates = {
            "TURISMO": 50000,      # Car
            "MOTOCICLETA": 15000,  # Motorcycle
            "CAMION": 100000,      # Truck
            "AUTOBUS": 80000,      # Bus
            "REMOLQUE": 30000,     # Trailer
            "AGRICOLA": 25000,     # Agricultural
            "ESPECIAL": 75000,     # Special vehicle
        }

        base_tariff = base_rates.get(vehicle_type, 50000)

        # Age factor (older = lower)
        if vehicle_age > 10:
            age_factor = 0.7
        elif vehicle_age > 5:
            age_factor = 0.85
        else:
            age_factor = 1.0

        # Engine capacity factor
        if engine_cc > 3000:
            cc_factor = 1.5
        elif engine_cc > 2000:
            cc_factor = 1.2
        else:
            cc_factor = 1.0

        # Value-based component (1% of value, capped)
        value_component = min(vehicle_value * 0.01, 500000)

        # First registration premium
        if is_first_registration:
            registration_premium = 25000
        else:
            registration_premium = 0

        # Calculate total
        calculated_tariff = int(
            (base_tariff * age_factor * cc_factor) +
            value_component +
            registration_premium
        )

        # Get supplements
        supplements = await self.get_supplements(db, workflow_code)
        supplements_total = sum(s.get("subtotal", 0) for s in supplements)

        total = calculated_tariff + supplements_total

        return {
            "tariff_type": TariffType.RBC.value,
            "rbc_factors": {
                "vehicle_type": vehicle_type,
                "vehicle_age": vehicle_age,
                "engine_cc": engine_cc,
                "vehicle_value": vehicle_value,
                "is_first_registration": is_first_registration,
                "age_factor": age_factor,
                "cc_factor": cc_factor
            },
            "base_amount": float(calculated_tariff),
            "supplements": supplements,
            "supplements_total": float(supplements_total),
            "penalties_amount": 0.0,
            "total_amount": float(total),
            "currency": "XAF"
        }

    async def _calculate_nota_ingreso_tariff(
        self,
        db: asyncpg.Connection,
        workflow_code: str,
        extracted_data: Optional[Dict]
    ) -> Dict:
        """
        Calculate tariff from Nota de Ingreso (Treasury document).

        The amount is extracted from the uploaded Nota de Ingreso document.
        """
        nota_amount = 0.0

        if extracted_data:
            # From nota_ingreso document
            if "nota_ingreso" in extracted_data:
                nota = extracted_data["nota_ingreso"]
                nota_amount = float(nota.get("monto_total", 0))
            elif "monto_nota_ingreso" in extracted_data:
                nota_amount = float(extracted_data["monto_nota_ingreso"])

        # Get supplements (timbres for RESIDENCIA)
        supplements = await self.get_supplements(db, workflow_code)
        supplements_total = sum(s.get("subtotal", 0) for s in supplements)

        total = nota_amount + supplements_total

        return {
            "tariff_type": TariffType.NOTA_INGRESO.value,
            "nota_ingreso_amount": nota_amount,
            "base_amount": float(nota_amount),
            "supplements": supplements,
            "supplements_total": float(supplements_total),
            "penalties_amount": 0.0,
            "total_amount": float(total),
            "currency": "XAF"
        }

    async def _get_percentage_rate(
        self,
        db: asyncpg.Connection,
        workflow_code: str,
        solicitud_type: str = "expedicion"
    ) -> Optional[float]:
        """Get percentage rate from database configuration."""
        query = """
            SELECT percentage_rate
            FROM workflow_tariffs
            WHERE workflow_code = $1
              AND solicitud_type = $2
              AND tariff_type = 'PERCENTAGE'
              AND is_active = TRUE
              AND effective_from <= CURRENT_DATE
              AND (effective_to IS NULL OR effective_to > CURRENT_DATE)
            ORDER BY effective_from DESC
            LIMIT 1
        """
        try:
            row = await db.fetchrow(query, workflow_code, solicitud_type)
            if row and row["percentage_rate"]:
                return float(row["percentage_rate"])
        except Exception as e:
            logger.warning(f"Could not get percentage_rate from DB: {e}")
        return None

    async def get_base_tariff(
        self,
        db: asyncpg.Connection,
        workflow_code: str,
        solicitud_type: str = "expedicion"
    ) -> Optional[Dict]:
        """
        Get only the base tariff (without supplements).

        Args:
            db: Database connection
            workflow_code: The workflow code
            solicitud_type: Type of request

        Returns:
            Base tariff info or None
        """
        query = """
            SELECT amount, currency, legal_reference, effective_from
            FROM workflow_tariffs
            WHERE workflow_code = $1
              AND solicitud_type = $2
              AND is_active = TRUE
              AND effective_from <= CURRENT_DATE
              AND (effective_to IS NULL OR effective_to > CURRENT_DATE)
            ORDER BY effective_from DESC
            LIMIT 1
        """
        row = await db.fetchrow(query, workflow_code, solicitud_type)

        if not row:
            return None

        return {
            "amount": float(row["amount"]),
            "currency": row["currency"],
            "legal_reference": row["legal_reference"],
            "effective_from": row["effective_from"]
        }

    async def get_supplements(
        self,
        db: asyncpg.Connection,
        workflow_code: str
    ) -> List[Dict]:
        """
        Get configured supplements for a workflow.

        Args:
            db: Database connection
            workflow_code: The workflow code

        Returns:
            List of supplement configurations
        """
        query = """
            SELECT
                ts.code,
                ts.name_es,
                ts.amount,
                wsc.quantity_per_request,
                ts.amount * wsc.quantity_per_request as subtotal,
                wsc.is_required
            FROM workflow_supplement_config wsc
            JOIN tariff_supplements ts ON ts.code = wsc.supplement_code
            WHERE wsc.workflow_code = $1
              AND wsc.is_active = TRUE
              AND ts.is_active = TRUE
              AND ts.effective_from <= CURRENT_DATE
              AND (ts.effective_to IS NULL OR ts.effective_to > CURRENT_DATE)
            ORDER BY ts.name_es
        """
        rows = await db.fetch(query, workflow_code)

        return [
            {
                "code": row["code"],
                "name": row["name_es"],
                "unit_price": float(row["amount"]),
                "quantity": row["quantity_per_request"],
                "subtotal": float(row["subtotal"]),
                "is_required": row["is_required"]
            }
            for row in rows
        ]

    async def calculate_with_penalties(
        self,
        db: asyncpg.Connection,
        workflow_code: str,
        solicitud_type: str = "expedicion",
        days_late: int = 0
    ) -> Dict:
        """
        Calculate tariff including late penalties.

        Args:
            db: Database connection
            workflow_code: The workflow code
            solicitud_type: Type of request
            days_late: Number of days late (for renewals)

        Returns:
            Full tariff breakdown with penalties
        """
        # Get base calculation
        tariff = await self.calculate(db, workflow_code, solicitud_type)

        # Calculate penalties if applicable
        if days_late > 0 and solicitud_type == "renovacion":
            penalty_info = self._calculate_penalty(
                tariff["base_amount"],
                days_late
            )
            tariff["penalties_amount"] = penalty_info["amount"]
            tariff["penalty_details"] = penalty_info
            tariff["total_amount"] = (
                tariff["base_amount"] +
                tariff["supplements_total"] +
                tariff["penalties_amount"]
            )

        return tariff

    def _calculate_penalty(
        self,
        base_amount: float,
        days_late: int
    ) -> Dict:
        """
        Calculate penalty based on days late.
        Penalty tiers:
        - 1-30 days: 10% of base
        - 31-60 days: 20% of base
        - 61-90 days: 30% of base
        - 90+ days: 50% of base
        """
        if days_late <= 0:
            return {"amount": 0.0, "rate": 0, "tier": "none"}

        if days_late <= 30:
            rate = 10
            tier = "1-30 days"
        elif days_late <= 60:
            rate = 20
            tier = "31-60 days"
        elif days_late <= 90:
            rate = 30
            tier = "61-90 days"
        else:
            rate = 50
            tier = "90+ days"

        amount = base_amount * (rate / 100)

        return {
            "amount": round(amount, 2),
            "rate": rate,
            "tier": tier,
            "days_late": days_late
        }

    def _empty_tariff(self) -> Dict:
        """Return empty tariff structure"""
        return {
            "base_amount": 0.0,
            "supplements": [],
            "supplements_total": 0.0,
            "penalties_amount": 0.0,
            "total_amount": 0.0,
            "currency": "XAF"
        }


# Singleton instance
tariff_service = TariffService()
