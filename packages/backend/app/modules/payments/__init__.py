"""
Payments Module - BANGE Mobile Payment Integration

Module critique de paiement mobile intégré avec BANGE:
- Paiement de déclarations fiscales (tax_declarations)
- Paiement de services fiscaux (fiscal_services)
- Plans de paiement échelonnés
- Génération de reçus PDF
- Workflow validation agents (auto-assignment)
- Webhooks BANGE

8 Tables DB:
1. payments (table centrale polymorphe - liens tax_declarations OU fiscal_services)
2. payment_plans (échéanciers de paiement)
3. payment_installments (acomptes individuels)
4. payment_receipts (reçus PDF générés)
5. payment_lock_history (historique verrouillage - DEPRECATED)
6. payment_validation_audit (audit trail validation)
7. service_payments (workflow agents avec auto-assignment)
8. bank_transactions (transactions BANGE)

Relations clés:
- payments.tax_declaration_id → tax_declarations (XOR fiscal_service_id)
- payments.fiscal_service_id → fiscal_services (XOR tax_declaration_id)
- payments.user_id → users (REQUIRED)
- service_payments.assigned_agent_id → agent_profiles (UUID)
- service_payments.validated_by_agent_id → agent_profiles (UUID)
- bank_transactions → intégration BANGE API

Endpoints: ~18
- CRUD payments
- Create payment plan (échéancier)
- Process payment (BANGE API)
- Generate receipt (PDF)
- Agent workflow (validate, reject) - lock removed with auto-assignment
- Webhooks callbacks BANGE

Priorité: 🔴 CRITIQUE P1 (requis par DECLARATIONS et WEBHOOKS)
"""

from app.modules.payments.api.payment_routes import router as payment_router

__all__ = ["payment_router"]
