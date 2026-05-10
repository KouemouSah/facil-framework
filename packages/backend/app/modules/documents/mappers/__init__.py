"""
Form Mappers Module
Exports all form mappers for document extraction system

Author: Claude Code
Date: 2025-11-13
"""

from app.modules.documents.mappers.base import (
    BaseFormMapper,
    FormMappingResult
)

from app.modules.documents.mappers.declaration_mapper import (
    # Declaration mappers
    IVAFormMapper,
    IRPFFormMapper,
    RetencionServiciosFormMapper,
    PetroleumProductsFormMapper,
    PayrollTaxFormMapper,
    MinimumFiscalFeeFormMapper,
    GeneralTaxFormMapper,
    TaxSettlementFormMapper,

    # Singleton instances
    iva_form_mapper,
    irpf_form_mapper,
    retencion_servicios_mapper,
    petroleum_products_mapper,
    payroll_tax_mapper,
    minimum_fiscal_fee_mapper,
    general_tax_mapper,
    tax_settlement_mapper
)

__all__ = [
    # Base classes
    "BaseFormMapper",
    "FormMappingResult",

    # Mapper classes
    "IVAFormMapper",
    "IRPFFormMapper",
    "RetencionServiciosFormMapper",
    "PetroleumProductsFormMapper",
    "PayrollTaxFormMapper",
    "MinimumFiscalFeeFormMapper",
    "GeneralTaxFormMapper",
    "TaxSettlementFormMapper",

    # Singleton instances
    "iva_form_mapper",
    "irpf_form_mapper",
    "retencion_servicios_mapper",
    "petroleum_products_mapper",
    "payroll_tax_mapper",
    "minimum_fiscal_fee_mapper",
    "general_tax_mapper",
    "tax_settlement_mapper"
]
