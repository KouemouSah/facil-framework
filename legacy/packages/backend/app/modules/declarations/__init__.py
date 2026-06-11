"""
Declarations Module - Tax Declarations Management

Module critique gérant les déclarations fiscales:
- 28 types de déclarations (IVA, IRPF, Pétrolifères, Retenciones, etc.)
- 9 tables DB (2 principales + 5 détails + 2 audit)
- Workflow complet: draft → submitted → processing → accepted/rejected
- Support OCR extraction via Documents module
- Intégration Payments pour règlement
- Intégration Agents pour validation

9 Tables DB:
1. tax_declarations (déclarations fiscales principales - 28 types)
2. fiscal_service_data (déclarations services fiscaux - Nota de Ingreso, etc.)
3. declaration_iva_details (détails IVA - 90% volume)
4. declaration_irpf_data (détails IRPF - 5% volume)
5. declaration_petroliferos_details (détails Pétrolifères - 4% volume, gros montants)
6. declaration_retencion_details (détails Retenciones 3%, 5%, 10%)
7. declaration_other_details (détails 7 autres types - <1% volume, JSONB)
8. declaration_amount_adjustments (audit trail ajustements montants)
9. declaration_corrections (audit trail corrections/rectificatives)

Endpoints: ~25
Priorité: CRITIQUE P1

Note: Permissions are managed via module_permissions/declaration_permissions.py
      using SINGULAR names (declaration.*)
"""

from app.modules.declarations.api.declaration_routes import router as declaration_router

__all__ = ["declaration_router"]
