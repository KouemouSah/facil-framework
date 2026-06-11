"""
Tariff Breakdown Models.

Provides standardized structures for tariff calculations including
base amounts, supplements, and penalties.

Structure aligned with DB tables:
- tariff_supplements (code, name_es, amount)
- workflow_supplement_config (workflow_code, supplement_code, quantity_per_request)

ARCHITECTURE:
- Supplements ALWAYS come from DB (workflow_supplement_config)
- TariffService handles ALL tariff calculation (base + supplements)
- PredefinedWorkflows only define base tariff in code
- PaymentContext receives TariffBreakdown from TariffService
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal


@dataclass
class SupplementItem:
    """
    A supplement/fee item - aligned with tariff_supplements table.

    DB columns mapped:
    - code: tariff_supplements.code (TIMBRE_FISCAL, CEDULA_PERSONAL, POLIZA)
    - name_es: tariff_supplements.name_es
    - unit_price: tariff_supplements.amount
    - quantity: workflow_supplement_config.quantity_per_request
    - is_required: workflow_supplement_config.is_required
    """
    code: str                           # e.g., "TIMBRE_FISCAL", "CEDULA_PERSONAL"
    name_es: str                        # Display name in Spanish
    unit_price: Decimal                 # Price per unit in XAF
    quantity: int = 1                   # Number of units (quantity_per_request)
    is_required: bool = True            # Whether this supplement is mandatory

    @property
    def subtotal(self) -> Decimal:
        """Calculate subtotal for this supplement."""
        return self.unit_price * self.quantity

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "name_es": self.name_es,
            "unit_price": float(self.unit_price),
            "quantity": self.quantity,
            "subtotal": float(self.subtotal),
            "is_required": self.is_required
        }


@dataclass
class TariffBreakdown:
    """
    Complete breakdown of tariff calculation.

    Used for:
    - Displaying itemized costs to users
    - Storing calculation details in service_payments.calculation_details
    - Generating detailed receipts

    Structure aligned with:
    - TariffService.calculate() output
    - get_workflow_tariff_total() SQL function output
    """
    # Base tariff (from workflow_tariffs.amount or TariffConfig.fixed_amounts)
    base_amount: Decimal                # Base service fee
    base_description: str = ""          # e.g., "Expedicion de Pasaporte"

    # Supplements (from workflow_supplement_config + tariff_supplements)
    supplements: List[SupplementItem] = field(default_factory=list)

    # Penalties (for late renewals)
    penalties_amount: Decimal = Decimal("0")
    penalty_reason: Optional[str] = None

    # Currency
    currency: str = "XAF"

    # Metadata
    tariff_type: str = "FIXED"          # FIXED, PERCENTAGE, RBC, NOTA_INGRESO
    workflow_code: Optional[str] = None
    solicitud_type: Optional[str] = None
    calculation_date: datetime = field(default_factory=datetime.utcnow)

    @property
    def supplements_total(self) -> Decimal:
        """Calculate total of all supplements."""
        return sum(s.subtotal for s in self.supplements)

    @property
    def total_amount(self) -> Decimal:
        """Calculate grand total: base + supplements + penalties."""
        return self.base_amount + self.supplements_total + self.penalties_amount

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage in calculation_details."""
        return {
            "base_amount": float(self.base_amount),
            "base_description": self.base_description,
            "supplements": [s.to_dict() for s in self.supplements],
            "supplements_total": float(self.supplements_total),
            "penalties_amount": float(self.penalties_amount),
            "penalty_reason": self.penalty_reason,
            "total_amount": float(self.total_amount),
            "currency": self.currency,
            "tariff_type": self.tariff_type,
            "workflow_code": self.workflow_code,
            "solicitud_type": self.solicitud_type,
            "calculation_date": self.calculation_date.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TariffBreakdown":
        """Create TariffBreakdown from dictionary (e.g., from DB JSONB)."""
        supplements = [
            SupplementItem(
                code=s["code"],
                name_es=s["name_es"],
                unit_price=Decimal(str(s["unit_price"])),
                quantity=s.get("quantity", 1),
                is_required=s.get("is_required", True)
            )
            for s in data.get("supplements", [])
        ]
        return cls(
            base_amount=Decimal(str(data.get("base_amount", 0))),
            base_description=data.get("base_description", ""),
            supplements=supplements,
            penalties_amount=Decimal(str(data.get("penalties_amount", 0))),
            penalty_reason=data.get("penalty_reason"),
            currency=data.get("currency", "XAF"),
            tariff_type=data.get("tariff_type", "FIXED"),
            workflow_code=data.get("workflow_code"),
            solicitud_type=data.get("solicitud_type")
        )

    @classmethod
    def from_tariff_service(cls, tariff_data: Dict[str, Any]) -> "TariffBreakdown":
        """
        Create TariffBreakdown from TariffService.calculate() output.

        TariffService returns:
        {
            "base_amount": float,
            "supplements": [{"code", "name", "unit_price", "quantity", "subtotal"}],
            "supplements_total": float,
            "penalties_amount": float,
            "total_amount": float,
            "currency": str,
            "tariff_type": str (optional)
        }
        """
        supplements = [
            SupplementItem(
                code=s.get("code", "UNKNOWN"),
                name_es=s.get("name", s.get("name_es", "")),
                unit_price=Decimal(str(s.get("unit_price", 0))),
                quantity=s.get("quantity", 1),
                is_required=s.get("is_required", True)
            )
            for s in tariff_data.get("supplements", [])
        ]
        return cls(
            base_amount=Decimal(str(tariff_data.get("base_amount", 0))),
            supplements=supplements,
            penalties_amount=Decimal(str(tariff_data.get("penalties_amount", 0))),
            currency=tariff_data.get("currency", "XAF"),
            tariff_type=tariff_data.get("tariff_type", "FIXED")
        )

    def format_for_display(self, locale: str = "es") -> Dict[str, Any]:
        """
        Format breakdown for frontend display.

        Returns a structure suitable for rendering in UI:
        - Formatted amounts with currency
        - Localized descriptions
        """
        def format_amount(amount: Decimal) -> str:
            return f"{int(amount):,} {self.currency}".replace(",", " ")

        items = [
            {
                "label": self.base_description or "Tarifa base",
                "amount": format_amount(self.base_amount),
                "raw_amount": float(self.base_amount)
            }
        ]

        for s in self.supplements:
            label = s.name_es
            if s.quantity > 1:
                label = f"{s.name_es} (x{s.quantity})"
            items.append({
                "label": label,
                "amount": format_amount(s.subtotal),
                "raw_amount": float(s.subtotal)
            })

        if self.penalties_amount > 0:
            items.append({
                "label": self.penalty_reason or "Recargo",
                "amount": format_amount(self.penalties_amount),
                "raw_amount": float(self.penalties_amount),
                "is_penalty": True
            })

        return {
            "items": items,
            "total": {
                "label": "Total a pagar",
                "amount": format_amount(self.total_amount),
                "raw_amount": float(self.total_amount)
            },
            "currency": self.currency
        }
