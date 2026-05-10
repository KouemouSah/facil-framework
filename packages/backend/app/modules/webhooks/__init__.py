"""
Webhooks Module - BANGE Bank Integration & Transaction Reconciliation

Module critique pour réception des callbacks BANGE:
- Webhooks BANGE (confirmations paiements)
- Réconciliation automatique transactions ↔ payments
- Configuration multi-banques (BANGE, BGFI, ECOBANK, etc.)
- Validation HMAC signature
- Retry logic et dead letter queue

2 Tables DB:
1. bank_configurations (config intégrations bancaires)
   - bank_code, bank_name (BANGE, BGFI, CCEIBANK, SGBGE, ECOBANK)
   - api_endpoint, api_key_encrypted, webhook_secret
   - treasury_account_number (compte Trésor Public)
   - supports_webhooks, supports_direct_integration
   - is_active (enable/disable par banque)

2. bank_transactions (transactions reçues webhooks)
   - bank_code, bank_reference (UNIQUE composite)
   - amount, currency, bank_transaction_date
   - service_payment_id (FK → service_payments - réconciliation)
   - status: unreconciled, reconciled, disputed
   - raw_data JSONB (payload complet pour audit)
   - reconciled_at, reconciled_by

Relations clés:
- bank_transactions.service_payment_id → service_payments.id (réconciliation)
- service_payments.bank_transaction_id → bank_transactions.id (bidirectionnelle)
- bank_transactions.reconciled_by → users.id (qui a réconcilié)

Endpoints: ~10
- POST /webhooks/bange (callback BANGE - HMAC validation)
- GET /bank-transactions (list non réconciliées)
- POST /bank-transactions/{id}/reconcile (manual reconciliation)
- GET /bank-configurations (list banques actives)
- POST /bank-configurations (admin - add bank)
- PUT /bank-configurations/{id} (admin - update config)
- GET /reconciliation/pending (dashboard)
- POST /reconciliation/auto (trigger auto-reconciliation)

Features:
- HMAC signature validation (webhook_secret)
- Idempotency (bank_code + bank_reference UNIQUE)
- Auto-reconciliation (match bank_reference → service_payment.payment_reference)
- Manual reconciliation (admin override)
- Raw data JSONB (audit trail complet)
- Multi-bank support (5 banques Guinée)

Priorité: 🔴 CRITIQUE P1 (Sans webhooks BANGE, revenus bloqués)
"""

from app.modules.webhooks.api.webhook_routes import router as webhook_router

__all__ = ["webhook_router"]
