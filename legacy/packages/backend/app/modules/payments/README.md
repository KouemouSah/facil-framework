# Payment Architecture - TaxasGE

**Version**: 2.0
**Last Updated**: 2026-01-06
**Status**: Production Ready

---

## Overview

TaxasGE implements a unified payment system using the **Strategy Pattern** via `PaymentProcessorRegistry`. This architecture supports multiple payment methods with a clean separation between:

- **BANGE API Integration**: Mobile Money, Card, Bank Transfer
- **Manual Validation**: Cash, Check (requires Treasury Agent approval)

---

## Architecture Diagram

```
                    Frontend (wizard/page.tsx)
                              |
                              | GET /payment/methods
                              v
                    +---------------------+
                    |   routes.py         |
                    |   /payment/methods  |
                    +----------+----------+
                               |
                               v
                    +---------------------+
                    |  PaymentProcessor   |
                    |      Registry       |
                    +----------+----------+
                               |
              +----------------+----------------+
              |                |                |
              v                v                v
     +-------------+  +-------------+  +-------------+
     |   BANGE     |  |   Manual    |  |  (Future)   |
     |  Processor  |  | Processor   |  |  Processor  |
     +-------------+  +-------------+  +-------------+
     mobile_money      cash             ussd
     card              check            crypto
     bank_transfer
```

---

## Payment Methods

### Available Methods

| Code | Label (ES) | Processor | Requires Phone | Requires Redirect | Agent Validation |
|------|------------|-----------|----------------|-------------------|------------------|
| `mobile_money` | Mobile Money | BANGE API | Yes | Yes | No |
| `card` | Tarjeta | BANGE API | No | Yes | No |
| `bank_transfer` | Transferencia | BANGE API | No | No | No |
| `cash` | Efectivo | Manual | No | No | **Yes** |
| `check` | Cheque | Manual | No | No | **Yes** |

### Method Selection Flow

1. Frontend calls `GET /api/v1/service-requests/{id}/payment/methods`
2. Backend returns available methods from `PaymentProcessorRegistry`
3. User selects method in wizard
4. Frontend calls `POST /api/v1/service-requests/{id}/payment/initiate`

---

## Database Schema

### Tables

#### `service_payments` (Primary for service requests)
```sql
CREATE TABLE service_payments (
    id UUID PRIMARY KEY,
    service_request_id UUID REFERENCES service_requests(id),
    user_id UUID NOT NULL,
    payment_method payment_method_enum NOT NULL,
    payment_type VARCHAR(20) DEFAULT 'full',
    base_amount DECIMAL(15,2) NOT NULL,
    penalties DECIMAL(15,2) DEFAULT 0,
    discounts DECIMAL(15,2) DEFAULT 0,
    total_amount DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'XAF',
    status payment_status_enum DEFAULT 'pending',
    workflow_status payment_workflow_status DEFAULT 'submitted',
    payment_reference VARCHAR(100) UNIQUE,
    gateway_transaction_id VARCHAR(100),
    requires_agent_validation BOOLEAN DEFAULT true,
    -- Agent assignment (auto-assignment replaces manual locking)
    assigned_agent_id UUID REFERENCES agent_profiles(id),
    assigned_at TIMESTAMPTZ,
    validated_by_agent_id UUID,
    validated_at TIMESTAMPTZ,
    validation_comment TEXT,
    rejection_reason TEXT,
    -- Escalation
    escalated_to_agent_id UUID,
    escalation_level escalation_level,
    escalation_reason TEXT,
    escalated_at TIMESTAMPTZ,
    sla_escalated BOOLEAN DEFAULT false,
    -- Receipt
    receipt_number VARCHAR(50),
    receipt_url TEXT,
    calculation_details JSONB,  -- Tariff breakdown
    paid_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### `payments` (Legacy for tax declarations)
```sql
CREATE TABLE payments (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    tax_declaration_id UUID,  -- XOR
    fiscal_service_id INTEGER,  -- XOR
    base_amount DECIMAL(15,2),
    penalties DECIMAL(15,2),
    interest DECIMAL(15,2),
    amount DECIMAL(15,2),
    payment_method payment_method_enum,
    status payment_status_enum,
    bank_reference VARCHAR(100),
    bank_transaction_id UUID,
    idempotency_key VARCHAR(100) UNIQUE
);
```

#### `bank_transactions` (Webhook receipts)
```sql
CREATE TABLE bank_transactions (
    id UUID PRIMARY KEY,
    bank_code bank_code_enum NOT NULL,
    bank_reference VARCHAR(100) UNIQUE NOT NULL,
    payment_id UUID REFERENCES payments(id),
    amount DECIMAL(15,2),
    status transaction_status_enum DEFAULT 'unreconciled',
    reconciled_at TIMESTAMP,
    reconciled_by UUID,
    raw_data JSONB
);
```

### Enums

```sql
-- payment_method_enum
CREATE TYPE payment_method_enum AS ENUM (
    'bank_transfer', 'card', 'mobile_money', 'cash', 'check'
);

-- payment_status_enum
CREATE TYPE payment_status_enum AS ENUM (
    'pending', 'processing', 'completed', 'failed', 'cancelled', 'refunded'
);

-- payment_workflow_status (for service_payments)
CREATE TYPE payment_workflow_status AS ENUM (
    'submitted',
    'auto_processing',
    'auto_approved',
    'pending_agent_review',
    'locked_by_agent',
    'agent_reviewing',
    'requires_documents',
    'docs_resubmitted',
    'approved_by_agent',
    'rejected_by_agent',
    'escalated_supervisor',
    'supervisor_reviewing',
    'completed',
    'cancelled_by_user',
    'cancelled_by_agent',
    'expired'
);
```

---

## API Endpoints

### Citizen Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/service-requests/{id}/payment/methods` | Get available payment methods |
| POST | `/api/v1/service-requests/{id}/payment/initiate` | Start payment process |
| GET | `/api/v1/service-requests/{id}/payment/status` | Check payment status |

### Treasury Agent Endpoints

| Method | Path | Description | Permission |
|--------|------|-------------|------------|
| GET | `/api/v1/admin/service-requests/treasury/payments/pending` | List pending validations | `treasury:validate_payments` |
| POST | `/api/v1/admin/service-requests/treasury/payments/{id}/lock` | Lock for review | `treasury:validate_payments` |
| POST | `/api/v1/admin/service-requests/treasury/payments/{id}/validate` | Approve payment | `treasury:validate_payments` |
| POST | `/api/v1/admin/service-requests/treasury/payments/{id}/reject` | Reject payment | `treasury:validate_payments` |
| POST | `/api/v1/admin/service-requests/treasury/payments/{id}/unlock` | Release lock | `treasury:validate_payments` |

### Webhook Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/webhooks/bange` | BANGE callback (public, HMAC validated) |
| GET | `/api/v1/webhooks/transactions/unreconciled` | List unreconciled transactions |
| POST | `/api/v1/webhooks/transactions/reconcile` | Manual reconciliation |

---

## Payment Flows

### BANGE Payment Flow (Mobile Money, Card)

```
1. User selects payment method
   |
   v
2. POST /payment/initiate
   - Creates service_payment (status: pending)
   - Calls BANGE API
   - Returns redirect_url
   |
   v
3. User completes payment on BANGE gateway
   |
   v
4. BANGE sends webhook to POST /webhooks/bange
   - HMAC signature validated
   - Auto-reconciliation via merchant_reference
   |
   v
5. service_payment updated
   - status: completed
   - paid_at: NOW()
   |
   v
6. service_request.payment_status = 'completed'
   |
   v
7. Appointment hold confirmed (if applicable)
```

### Cash/Check Payment Flow (Manual Validation)

```
1. User selects Cash or Check
   |
   v
2. POST /payment/initiate
   - Creates service_payment
   - workflow_status: 'pending_agent_review'
   - requires_agent_validation: true
   - Returns action_type: 'agent_validation'
   |
   v
3. Treasury Agent sees in dashboard
   GET /treasury/payments/pending
   |
   v
4. Agent assigned automatically (or manually by supervisor)
   - assigned_agent_id set
   - assigned_at = now
   - workflow_status: 'locked_by_agent' → 'agent_reviewing'
   |
   v
5. Agent validates or rejects
   POST /treasury/payments/{id}/validate
   - workflow_status: 'approved_by_agent'
   - receipt_number generated
   - service_request.payment_status = 'completed'
   |
   v
6. Notification sent to user
```

---

## Tariff Calculation

### TariffBreakdown Structure

```json
{
  "base_amount": 25000,
  "base_description": "Expedicion de Pasaporte",
  "supplements": [
    {
      "code": "CEDULA_PERSONAL",
      "name_es": "Cedula de Identidad",
      "unit_price": 2500,
      "quantity": 1,
      "subtotal": 2500
    },
    {
      "code": "TIMBRE_FISCAL",
      "name_es": "Timbre Fiscal",
      "unit_price": 1000,
      "quantity": 1,
      "subtotal": 1000
    }
  ],
  "supplements_total": 3500,
  "penalties_amount": 0,
  "total_amount": 28500,
  "currency": "XAF",
  "tariff_type": "FIXED",
  "workflow_code": "PASAPORTE_EXPEDICION"
}
```

### Calculation Sources

| Workflow Type | Tariff Source |
|---------------|---------------|
| PredefinedWorkflow | `workflow.get_tariff_config()` in Python code |
| GenericWorkflow | `workflow_tariffs` table in database |

---

## Key Files

### Backend

| File | Description |
|------|-------------|
| `payments/services/processors/base.py` | PaymentProcessorBase ABC |
| `payments/services/processors/bange_processor.py` | BANGE API integration |
| `payments/services/processors/manual_processor.py` | Cash/Check handling |
| `payments/services/processors/registry.py` | PaymentProcessorRegistry |
| `payments/services/bange_service.py` | BANGE API client |
| `payments/services/receipt_service.py` | Receipt generation |
| `webhooks/api/webhook_routes.py` | BANGE webhook handler |
| `service_requests/api/routes.py` | Payment endpoints |
| `service_requests/api/admin_routes.py` | Treasury agent endpoints |

### Frontend

| File | Description |
|------|-------------|
| `modules/service-requests/types/index.ts` | PaymentMethodInfo type |
| `modules/service-requests/services/api.ts` | getPaymentMethods() |
| `modules/service-requests/hooks/useServiceRequests.ts` | Payment hook |
| `app/.../wizard/page.tsx` | Payment step UI |

---

## Configuration

### Environment Variables

```bash
# BANGE Integration
BANGE_API_URL=https://api.bange.gq
BANGE_API_KEY=xxx
BANGE_WEBHOOK_SECRET=xxx
BANGE_MERCHANT_ID=xxx

# Payment Settings
PAYMENT_LOCK_DURATION_MINUTES=15
PAYMENT_RECEIPT_PREFIX=REC
```

### Bank Configuration (Database)

```sql
INSERT INTO bank_configurations (
    bank_code, bank_name, api_endpoint, treasury_account_number,
    is_active, supports_webhooks
) VALUES (
    'BANGE', 'Banco Nacional de Guinea Ecuatorial',
    'https://api.bange.gq/v1', 'GE123456789',
    true, true
);
```

---

## Security

### HMAC Webhook Validation

```python
# webhook_routes.py
is_valid, error = await hmac_service.validate_webhook(
    body_bytes,
    x_bange_signature,  # X-Bange-Signature header
    bank_config.webhook_secret
)
```

### Idempotency

- `payments.idempotency_key`: Prevents duplicate payments
- `bank_transactions.bank_reference`: UNIQUE constraint prevents duplicate webhooks

### Agent Assignment

- Auto-assignment via rules engine (replaces manual pessimistic locking)
- `assigned_agent_id` tracks which agent is working on the payment
- Only assigned agent (or supervisor) can validate/reject
- Escalation path: agent → supervisor → admin

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-06 | 2.0 | Phase 3-4: Dynamic payment methods, Treasury endpoints |
| 2026-01-05 | 1.0 | Phase 1-2: PaymentProcessorRegistry, Tariff calculation |

---

*Documentation generated as part of Phase 4: Cleanup & Refactoring*
