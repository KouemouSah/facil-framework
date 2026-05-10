"""
Webhook Repository - Bank transactions and configurations

Handles:
- bank_configurations table
- bank_transactions table
- Reconciliation avec module SERVICE_PAYMENTS
"""

from typing import Optional, List, Dict, Any
from loguru import logger
import asyncpg

from app.modules.webhooks.models import (
    BankConfigurationCreate,
    BankConfigurationUpdate,
    BankTransactionCreate,
)


class WebhookRepository:
    """Repository for webhooks and bank transactions"""

    # C6: Allowlist of fields that can be updated via dynamic SQL
    ALLOWED_CONFIG_UPDATE_FIELDS = frozenset({
        "bank_name", "api_endpoint", "api_version",
        "api_key_encrypted", "webhook_secret",
        "treasury_account_number", "is_active",
        "supports_webhooks", "supports_direct_integration",
        "gateway_type", "supported_payment_methods", "is_primary",
    })

    # ========== BANK CONFIGURATIONS ==========

    async def create_bank_config(
        self, conn: asyncpg.Connection, config: BankConfigurationCreate
    ) -> Dict[str, Any]:
        """Create bank configuration (admin only)"""
        import json
        query = """
            INSERT INTO bank_configurations (
                bank_code, bank_name, api_endpoint, api_version,
                api_key_encrypted, webhook_secret, treasury_account_number,
                is_active, supports_webhooks, supports_direct_integration,
                gateway_type, supported_payment_methods, is_primary,
                created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, $13, NOW(), NOW())
            RETURNING *
        """
        result = await conn.fetchrow(
            query,
            config.bank_code.value,
            config.bank_name,
            config.api_endpoint,
            config.api_version,
            config.api_key_encrypted,
            config.webhook_secret,
            config.treasury_account_number,
            config.is_active,
            config.supports_webhooks,
            config.supports_direct_integration,
            config.gateway_type,
            json.dumps(config.supported_payment_methods or []),
            config.is_primary,
        )
        return dict(result)

    async def get_bank_config_by_code(
        self, conn: asyncpg.Connection, bank_code: str
    ) -> Optional[Dict[str, Any]]:
        """Get bank configuration by code"""
        result = await conn.fetchrow(
            "SELECT * FROM bank_configurations WHERE bank_code = $1", bank_code
        )
        return dict(result) if result else None

    async def list_bank_configs(
        self, conn: asyncpg.Connection, active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """List bank configurations"""
        if active_only:
            query = "SELECT * FROM bank_configurations WHERE is_active = true ORDER BY bank_name"
        else:
            query = "SELECT * FROM bank_configurations ORDER BY bank_name"

        results = await conn.fetch(query)
        return [dict(r) for r in results]

    async def update_bank_config(
        self, conn: asyncpg.Connection, config_id: int, update_data: BankConfigurationUpdate
    ) -> Optional[Dict[str, Any]]:
        """Update bank configuration"""
        import json
        updates = []
        params = [config_id]
        param_idx = 2

        for field, value in update_data.model_dump(exclude_unset=True).items():
            if value is not None:
                if field not in self.ALLOWED_CONFIG_UPDATE_FIELDS:
                    logger.warning(f"Rejected unknown field in bank config update: {field}")
                    continue
                # JSONB fields need json.dumps + cast
                if field == "supported_payment_methods":
                    updates.append(f"{field} = ${param_idx}::jsonb")
                    params.append(json.dumps(value))
                else:
                    updates.append(f"{field} = ${param_idx}")
                    params.append(value)
                param_idx += 1

        if not updates:
            result = await conn.fetchrow("SELECT * FROM bank_configurations WHERE id = $1", config_id)
            return dict(result) if result else None

        updates.append("updated_at = NOW()")

        query = f"UPDATE bank_configurations SET {', '.join(updates)} WHERE id = $1 RETURNING *"
        result = await conn.fetchrow(query, *params)
        return dict(result) if result else None

    # ========== BANK TRANSACTIONS ==========

    async def create_bank_transaction(
        self, conn: asyncpg.Connection, transaction: BankTransactionCreate
    ) -> Dict[str, Any]:
        """Create bank transaction (from webhook)"""
        query = """
            INSERT INTO bank_transactions (
                bank_code, bank_reference, bank_transaction_date,
                amount, currency, account_number, account_holder_name,
                status, raw_data, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'unreconciled', $8, NOW())
            RETURNING *
        """
        result = await conn.fetchrow(
            query,
            transaction.bank_code.value,
            transaction.bank_reference,
            transaction.bank_transaction_date,
            transaction.amount,
            transaction.currency,
            transaction.account_number,
            transaction.account_holder_name,
            transaction.raw_data,
        )
        return dict(result)

    async def get_by_bank_reference(
        self, conn: asyncpg.Connection, bank_code: str, bank_reference: str
    ) -> Optional[Dict[str, Any]]:
        """Get transaction by bank reference (idempotency)"""
        query = """
            SELECT * FROM bank_transactions
            WHERE bank_code = $1 AND bank_reference = $2
        """
        result = await conn.fetchrow(query, bank_code, bank_reference)
        return dict(result) if result else None

    async def get_transaction_by_id(
        self, conn: asyncpg.Connection, transaction_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get transaction by ID with related data"""
        query = """
            SELECT
                bt.*,
                sp.payment_reference,
                u.email as user_email
            FROM bank_transactions bt
            LEFT JOIN service_payments sp ON bt.service_payment_id = sp.id
            LEFT JOIN users u ON sp.user_id = u.id
            WHERE bt.id = $1
        """
        result = await conn.fetchrow(query, transaction_id)
        return dict(result) if result else None

    async def list_transactions(
        self, conn: asyncpg.Connection, limit: int = 50, offset: int = 0,
        search: Optional[str] = None, status: Optional[str] = None,
    ) -> tuple[List[Dict[str, Any]], int]:
        """List bank transactions with optional status and search filters.

        Args:
            status: None = all statuses, 'unreconciled', 'reconciled', 'failed'
            search: ILIKE filter on bank_reference, account_holder_name, account_number
        """
        where_clauses: list[str] = []
        params: list = []
        param_idx = 1

        if status:
            where_clauses.append(f"bt.status = ${param_idx}")
            params.append(status)
            param_idx += 1

        if search:
            search_pattern = f"%{search}%"
            where_clauses.append(f"""(
                bt.bank_reference ILIKE ${param_idx}
                OR bt.account_holder_name ILIKE ${param_idx}
                OR bt.account_number ILIKE ${param_idx}
            )""")
            params.append(search_pattern)
            param_idx += 1

        where = " AND ".join(where_clauses) if where_clauses else "TRUE"

        count_query = f"SELECT COUNT(*) FROM bank_transactions bt WHERE {where}"
        total = await conn.fetchval(count_query, *params)

        data_query = f"""
            SELECT
                bt.*,
                sp.payment_reference,
                u.email as user_email
            FROM bank_transactions bt
            LEFT JOIN service_payments sp ON bt.service_payment_id = sp.id
            LEFT JOIN users u ON sp.user_id = u.id
            WHERE {where}
            ORDER BY bt.bank_transaction_date DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        results = await conn.fetch(data_query, *params, limit, offset)
        return [dict(r) for r in results], total

    async def list_unreconciled(
        self, conn: asyncpg.Connection, limit: int = 50, offset: int = 0,
        search: Optional[str] = None,
    ) -> tuple[List[Dict[str, Any]], int]:
        """Backward-compatible alias for list_transactions(status='unreconciled')."""
        return await self.list_transactions(conn, limit, offset, search, status='unreconciled')

    async def reconcile(
        self, conn: asyncpg.Connection, transaction_id: str, service_payment_id: str, reconciled_by: str
    ) -> Dict[str, Any]:
        """
        Reconcile bank transaction with service_payment

        IMPORTANT: Cohérence bidirectionnelle avec module SERVICE_PAYMENTS
        - Met à jour bank_transactions.service_payment_id
        - Met à jour service_payments.bank_transaction_id
        Uses explicit transaction for atomicity.
        """
        # M6: Validate payment exists before starting transaction
        payment_exists = await conn.fetchval(
            "SELECT id FROM service_payments WHERE id = $1",
            service_payment_id,
        )
        if not payment_exists:
            raise ValueError(f"Service payment {service_payment_id} not found")

        async with conn.transaction():
            # 1. Update bank_transaction
            tx_query = """
                UPDATE bank_transactions
                SET service_payment_id = $2, status = 'reconciled',
                    reconciled_at = NOW(), reconciled_by = $3
                WHERE id = $1 AND status = 'unreconciled'
                RETURNING *
            """
            tx_result = await conn.fetchrow(tx_query, transaction_id, service_payment_id, reconciled_by)

            if not tx_result:
                raise ValueError(f"Transaction {transaction_id} not found or already reconciled")

            # 2. Update service_payment (bidirectional link)
            await conn.execute("""
                UPDATE service_payments
                SET bank_transaction_id = $2, updated_at = NOW()
                WHERE id = $1
            """, service_payment_id, transaction_id)

            logger.info(
                "Reconciliation completed | "
                "transaction_id={} service_payment_id={} reconciled_by={} action=manual_reconcile",
                transaction_id, service_payment_id, reconciled_by,
            )
            return dict(tx_result)

    async def auto_reconcile_by_reference(
        self, conn: asyncpg.Connection, bank_reference: str
    ) -> Optional[Dict[str, Any]]:
        """
        Auto-reconcile transaction by matching payment_reference in service_payments
        """
        # Find service_payment with matching payment_reference
        payment_query = "SELECT id FROM service_payments WHERE payment_reference = $1 AND workflow_status = 'completed'"
        payment = await conn.fetchrow(payment_query, bank_reference)

        if not payment:
            logger.warning(f"No service_payment found with payment_reference {bank_reference}")
            return None

        service_payment_id = str(payment["id"])

        # Find unreconciled transaction with this reference
        tx_query = """
            SELECT * FROM bank_transactions
            WHERE bank_reference = $1 AND status = 'unreconciled'
        """
        transaction = await conn.fetchrow(tx_query, bank_reference)

        if not transaction:
            logger.warning(f"No unreconciled transaction found with reference {bank_reference}")
            return None

        # Reconcile atomically
        return await self.reconcile(conn, str(transaction["id"]), service_payment_id, None)
