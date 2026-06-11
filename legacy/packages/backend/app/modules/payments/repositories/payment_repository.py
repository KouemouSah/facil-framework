"""
Payment Repository - Data access layer for payments

Handles:
- payments table (polymorphe: tax_declarations XOR fiscal_services)
- payment_plans table
- payment_installments table
- Relations avec DECLARATIONS et FISCAL_SERVICES
"""

from typing import Optional, List, Dict, Any
from loguru import logger
import asyncpg
from decimal import Decimal

from app.modules.payments.models import (
    PaymentCreate,
    PaymentUpdate,
    PaymentPlanCreate,
)


class PaymentRepository:
    """Repository for payments, plans, and installments"""

    async def create(self, conn: asyncpg.Connection, payment: PaymentCreate) -> Dict[str, Any]:
        """Create payment (polymorphic: tax_declaration XOR fiscal_service)"""
        # Calculate total amount
        total_amount = payment.base_amount + payment.penalties + payment.interest

        query = """
            INSERT INTO payments (
                user_id, tax_declaration_id, fiscal_service_id,
                payment_plan_id, installment_id,
                base_amount, penalties, interest, amount, currency,
                payment_type, status, payment_method,
                bank_reference, idempotency_key,
                created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, NOW(), NOW())
            RETURNING *
        """

        result = await conn.fetchrow(
            query,
            payment.user_id,
            payment.tax_declaration_id,
            payment.fiscal_service_id,
            payment.payment_plan_id,
            payment.installment_id,
            payment.base_amount,
            payment.penalties,
            payment.interest,
            total_amount,
            payment.currency,
            payment.payment_type.value,
            "pending",  # initial status
            payment.payment_method.value,
            payment.bank_reference,
            payment.idempotency_key,
        )

        return dict(result)

    async def get_by_id(self, conn: asyncpg.Connection, payment_id: str) -> Optional[Dict[str, Any]]:
        """Get payment by ID with related data"""
        query = """
            SELECT
                p.*,
                td.declaration_type,
                fs.name_es as fiscal_service_name,
                u.email as user_email
            FROM payments p
            LEFT JOIN tax_declarations td ON p.tax_declaration_id = td.id
            LEFT JOIN fiscal_services fs ON p.fiscal_service_id = fs.id
            LEFT JOIN users u ON p.user_id = u.id
            WHERE p.id = $1
        """
        result = await conn.fetchrow(query, payment_id)
        return dict(result) if result else None

    async def get_by_idempotency_key(self, conn: asyncpg.Connection, key: str) -> Optional[Dict[str, Any]]:
        """Get payment by idempotency key (prevent duplicates)"""
        result = await conn.fetchrow("SELECT * FROM payments WHERE idempotency_key = $1", key)
        return dict(result) if result else None

    async def list_by_user(
        self, conn: asyncpg.Connection, user_id: str, limit: int = 50, offset: int = 0
    ) -> tuple[List[Dict[str, Any]], int]:
        """List user payments"""
        count_query = "SELECT COUNT(*) FROM payments WHERE user_id = $1"
        total = await conn.fetchval(count_query, user_id)

        data_query = """
            SELECT
                p.*,
                td.declaration_type,
                fs.name_es as fiscal_service_name,
                u.email as user_email
            FROM payments p
            LEFT JOIN tax_declarations td ON p.tax_declaration_id = td.id
            LEFT JOIN fiscal_services fs ON p.fiscal_service_id = fs.id
            LEFT JOIN users u ON p.user_id = u.id
            WHERE p.user_id = $1
            ORDER BY p.created_at DESC
            LIMIT $2 OFFSET $3
        """
        results = await conn.fetch(data_query, user_id, limit, offset)
        return [dict(r) for r in results], total

    async def update(self, conn: asyncpg.Connection, payment_id: str, update_data: PaymentUpdate) -> Optional[Dict[str, Any]]:
        """Update payment"""
        updates = []
        params = [payment_id]
        param_idx = 2

        for field, value in update_data.dict(exclude_unset=True).items():
            if value is not None:
                if field == "status":
                    updates.append(f"status = ${param_idx}")
                    params.append(value.value)
                else:
                    updates.append(f"{field} = ${param_idx}")
                    params.append(value)
                param_idx += 1

        if not updates:
            return await self.get_by_id(conn, payment_id)

        updates.append("updated_at = NOW()")

        query = f"UPDATE payments SET {', '.join(updates)} WHERE id = $1 RETURNING *"
        result = await conn.fetchrow(query, *params)
        return dict(result) if result else None

    # ========== PAYMENT PLANS ==========

    async def create_payment_plan(
        self, conn: asyncpg.Connection, plan: PaymentPlanCreate
    ) -> Dict[str, Any]:
        """Create payment plan with installments"""
        # Get payment details
        payment = await self.get_by_id(conn, plan.payment_id)
        if not payment:
            raise ValueError(f"Payment {plan.payment_id} not found")

        total_amount = payment["amount"]
        installment_amount = total_amount / plan.number_of_installments

        # Create plan
        plan_query = """
            INSERT INTO payment_plans (payment_id, total_amount, number_of_installments, installment_frequency, status, created_at)
            VALUES ($1, $2, $3, $4, 'active', NOW())
            RETURNING *
        """
        plan_result = await conn.fetchrow(
            plan_query,
            plan.payment_id,
            total_amount,
            plan.number_of_installments,
            plan.installment_frequency,
        )
        plan_dict = dict(plan_result)

        # Create installments
        from datetime import timedelta
        installments = []
        current_date = plan.first_installment_date

        for i in range(1, plan.number_of_installments + 1):
            inst_query = """
                INSERT INTO payment_installments (payment_plan_id, installment_number, amount, due_date, status, created_at)
                VALUES ($1, $2, $3, $4, 'pending', NOW())
                RETURNING *
            """
            inst_result = await conn.fetchrow(
                inst_query,
                plan_dict["id"],
                i,
                installment_amount,
                current_date,
            )
            installments.append(dict(inst_result))

            # Next installment date
            if plan.installment_frequency == "monthly":
                current_date += timedelta(days=30)
            elif plan.installment_frequency == "bi_monthly":
                current_date += timedelta(days=60)
            elif plan.installment_frequency == "quarterly":
                current_date += timedelta(days=90)

        plan_dict["installments"] = installments
        return plan_dict

    async def get_payment_plan(self, conn: asyncpg.Connection, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get payment plan with installments"""
        plan_query = "SELECT * FROM payment_plans WHERE id = $1"
        plan = await conn.fetchrow(plan_query, plan_id)
        if not plan:
            return None

        plan_dict = dict(plan)

        # Get installments
        inst_query = "SELECT * FROM payment_installments WHERE payment_plan_id = $1 ORDER BY installment_number"
        installments = await conn.fetch(inst_query, plan_id)
        plan_dict["installments"] = [dict(i) for i in installments]

        return plan_dict

    # ========================================================================
    # METHODS USING DATABASE VIEWS - Optimized queries with pre-joined data
    # ========================================================================

    async def list_payments_with_declarations(
        self,
        conn: asyncpg.Connection,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        payment_method: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        List payments with declaration details using v_payments_with_declarations view

        This view includes:
        - Payment info
        - Declaration details (type, amounts, status)
        - User info
        - Bank reconciliation status

        Args:
            conn: Database connection
            user_id: Optional filter by user
            status: Optional filter by payment status
            payment_method: Optional filter by payment method
            limit: Max results
            offset: Pagination offset

        Returns:
            Tuple of (payments list, total count)
        """
        try:
            where_conditions = []
            params = []

            if user_id:
                where_conditions.append(f"user_id = ${len(params) + 1}")
                params.append(user_id)

            if status:
                # Cast enum to text for comparison
                where_conditions.append(f"status::text = ${len(params) + 1}")
                params.append(status)

            if payment_method:
                where_conditions.append(f"payment_method = ${len(params) + 1}")
                params.append(payment_method)

            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

            # Count query
            count_query = f"""
                SELECT COUNT(*) FROM v_payments_with_declarations
                {where_clause}
            """
            total = await conn.fetchval(count_query, *params)

            # Data query
            params.extend([limit, offset])
            data_query = f"""
                SELECT * FROM v_payments_with_declarations
                {where_clause}
                ORDER BY payment_date DESC
                LIMIT ${len(params) - 1} OFFSET ${len(params)}
            """

            results = await conn.fetch(data_query, *params)
            payments = [dict(r) for r in results]

            return payments, total

        except Exception as e:
            logger.error(f"Error listing payments with declarations: {str(e)}")
            raise

    async def get_payment_plan_with_status(
        self,
        conn: asyncpg.Connection,
        plan_id: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Get payment plans with installment status using v_payment_plan_installment_status view

        This view includes:
        - Payment plan details
        - Installment summary (paid/pending/overdue counts)
        - Payment status calculations
        - Recent payments and upcoming installments (as JSON)

        Args:
            conn: Database connection
            plan_id: Optional specific plan ID
            user_id: Optional filter by user
            status: Optional filter by plan status
            limit: Max results
            offset: Pagination offset

        Returns:
            Tuple of (payment plans list, total count)
        """
        try:
            where_conditions = []
            params = []

            if plan_id:
                where_conditions.append(f"plan_id = ${len(params) + 1}")
                params.append(plan_id)

            if user_id:
                where_conditions.append(f"user_id = ${len(params) + 1}")
                params.append(user_id)

            if status:
                where_conditions.append(f"plan_status = ${len(params) + 1}")
                params.append(status)

            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

            # Count query
            count_query = f"""
                SELECT COUNT(*) FROM v_payment_plan_installment_status
                {where_clause}
            """
            total = await conn.fetchval(count_query, *params)

            # Data query
            params.extend([limit, offset])
            data_query = f"""
                SELECT * FROM v_payment_plan_installment_status
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ${len(params) - 1} OFFSET ${len(params)}
            """

            results = await conn.fetch(data_query, *params)
            plans = [dict(r) for r in results]

            return plans, total

        except Exception as e:
            logger.error(f"Error fetching payment plans with status: {str(e)}")
            raise
