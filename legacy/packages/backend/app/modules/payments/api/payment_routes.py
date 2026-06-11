"""
Payment Routes - BANGE Mobile Payment API

Endpoints pour paiements mobiles intégrés avec BANGE:
- CRUD payments (polymorphe: tax_declarations OU fiscal_services)
- Payment plans (échéanciers)
- BANGE integration
- Idempotency support (prevent double-click)
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.security import HTTPBearer
from typing import Dict, Any
from loguru import logger

from app.modules.payments.models import (
    PaymentCreate,
    PaymentUpdate,
    PaymentResponse,
    PaymentListResponse,
    PaymentPlanCreate,
    PaymentPlanResponse,
)
from app.modules.payments.repositories import PaymentRepository
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.modules.permissions.services.permission_service import create_permission_service
from app.database.connection import get_database

router = APIRouter(tags=["Payments"])
security = HTTPBearer()
repository = PaymentRepository()


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payment: PaymentCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """
    Create payment (idempotent)

    Polymorphic: Must provide EITHER tax_declaration_id OR fiscal_service_id (XOR)
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    # Verify user_id matches
    if payment.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User ID mismatch")

    # Check idempotency (prevent double-click duplicates)
    existing = await repository.get_by_idempotency_key(db, payment.idempotency_key)
    if existing:
        logger.info(f"Idempotency key {payment.idempotency_key} already used, returning existing payment")
        return PaymentResponse(**existing)

    # Validate polymorphic constraint (XOR)
    if payment.tax_declaration_id and payment.fiscal_service_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot set both tax_declaration_id and fiscal_service_id"
        )
    if not payment.tax_declaration_id and not payment.fiscal_service_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must set either tax_declaration_id or fiscal_service_id"
        )

    result = await repository.create(db, payment)
    logger.info(f"User {user_id} created payment {result['id']}")
    return PaymentResponse(**result)


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Get payment by ID"""
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    payment = await repository.get_by_id(db, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    # Check ownership
    if payment["user_id"] != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your payment")

    return PaymentResponse(**payment)


@router.get("", response_model=PaymentListResponse)
async def list_payments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """List user payments"""
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")
    offset = (page - 1) * page_size

    payments, total = await repository.list_by_user(db, user_id, page_size, offset)
    return PaymentListResponse(
        payments=[PaymentResponse(**p) for p in payments],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.put("/{payment_id}", response_model=PaymentResponse)
async def update_payment(
    payment_id: str,
    update_data: PaymentUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """
    Update payment status

    Users can update their own payments (limited fields)
    Admins with payments.update permission can update any payment (all fields)
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    payment = await repository.get_by_id(db, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    # Check if user has admin permission
    perm_service = create_permission_service(db)
    has_admin_perm = await perm_service.has_permission(user_id, "payments.update")

    # Check ownership OR admin permission
    if payment["user_id"] != user_id and not has_admin_perm:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    updated = await repository.update(db, payment_id, update_data)
    logger.info(f"Payment {payment_id} updated by {user_id}")
    return PaymentResponse(**updated)


# ========== PAYMENT PLANS ==========

@router.post("/{payment_id}/plan", response_model=PaymentPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_payment_plan(
    payment_id: str,
    plan: PaymentPlanCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Create payment plan (échéancier) for a payment"""
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    # Verify payment ownership
    payment = await repository.get_by_id(db, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    if payment["user_id"] != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your payment")

    # Ensure payment_id matches
    plan.payment_id = payment_id

    result = await repository.create_payment_plan(db, plan)
    logger.info(f"User {user_id} created payment plan {result['id']} for payment {payment_id}")
    return PaymentPlanResponse(**result)


@router.get("/plans/{plan_id}", response_model=PaymentPlanResponse)
async def get_payment_plan(
    plan_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Get payment plan with installments"""
    plan = await repository.get_payment_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment plan not found")

    # Get payment to check ownership
    payment = await repository.get_by_id(db, plan["payment_id"])
    owner_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")
    if payment["user_id"] != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your payment plan")

    return PaymentPlanResponse(**plan)
