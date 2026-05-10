"""
Declaration Routes - Tax Declarations API

Module critique gérant 28 types de déclarations fiscales.

Endpoints MVP (Phase 3.1):
- POST /declarations - Create new declaration
- GET /declarations - List user's declarations
- GET /declarations/{id} - Get declaration by ID
- PUT /declarations/{id} - Update declaration
- DELETE /declarations/{id} - Delete declaration (soft)
- POST /declarations/{id}/submit - Submit declaration

Future endpoints (Phase 3.2):
- GET /declarations/stats - User statistics
- GET /declarations/search - Advanced search
- POST /declarations/{id}/calculate - Recalculate taxes
- POST /declarations/{id}/amend - Create amendment
- GET /declarations/{id}/history - Audit trail
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Dict, Any
from loguru import logger

from datetime import datetime

from app.core.events import EventBus, EventType
from app.modules.declarations.models import (
    DeclarationCreate,
    DeclarationUpdate,
    DeclarationResponse,
    DeclarationListResponse,
    DeclarationStatus,
    DeclarationWorkflowStatus,
)
from app.modules.declarations.repositories import DeclarationRepository
from app.modules.declarations.services import get_declaration_service
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.modules.permissions.services.permission_service import create_permission_service
from app.database.connection import get_database

# Create router
router = APIRouter(tags=["Declarations"])
security = HTTPBearer()

# Initialize repository and service
declaration_repository = DeclarationRepository()
declaration_service = get_declaration_service()


@router.get("/", response_model=Dict[str, Any])
async def get_declarations_info():
    """
    Get declarations API information

    Returns API metadata and available endpoints.
    """
    return {
        "message": "TaxasGE Tax Declarations API",
        "version": "1.0.0 (MVP - Phase 3.1)",
        "declaration_types": 28,
        "tables": 9,
        "endpoints": {
            "create": "POST /declarations - Create new declaration",
            "list": "GET /declarations - List user's declarations",
            "get": "GET /declarations/{id} - Get declaration by ID",
            "update": "PUT /declarations/{id} - Update declaration",
            "delete": "DELETE /declarations/{id} - Delete declaration",
            "submit": "POST /declarations/{id}/submit - Submit declaration",
        },
        "supported_types": [
            "iva_destajo", "iva_real", "income_tax", "corporate_tax",
            "retencion_3pct_petrolero", "retencion_5pct_petrolero",
            "retencion_10pct_petrolero", "petroleo_gas", "petroleo_diesel",
            "petroleo_essence", "retencion_3pct", "retencion_5pct",
            "retencion_10pct", "vat_declaration", "sales_tax",
            "property_tax", "payroll_tax", "excise_tax",
            "customs_declaration", "special_tax", "quarterly_return",
            "annual_return", "amended_return", "estimated_tax",
            "withholding_tax", "capital_gains", "inheritance_tax"
        ],
        "note": "MVP version - Additional endpoints (stats, search, calculate) coming in Phase 3.2"
    }


@router.post("", response_model=DeclarationResponse, status_code=status.HTTP_201_CREATED)
async def create_declaration(
    declaration: DeclarationCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """
    Create new tax declaration

    Creates a new declaration in DRAFT status.
    User can then update and submit it.

    **Authentication**: Required (Bearer token)

    **Permissions**: Any authenticated user

    **Business Rules**:
    - Declaration starts in DRAFT status
    - User ID from token (cannot create for others)
    - OCR confidence score optional (if created from document)
    - Metadata field for extensibility

    Returns:
        DeclarationResponse: Created declaration with UUID
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

        # Override user_id from token (security)
        declaration.user_id = user_id

        # Create declaration
        result = await declaration_repository.create(db, declaration)

        logger.info(f"User {user_id} created declaration {result['id']}")

        return DeclarationResponse(**result)

    except Exception as e:
        logger.error(f"Error creating declaration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create declaration: {str(e)}",
        )


@router.get("", response_model=DeclarationListResponse)
async def list_declarations(
    status_filter: Optional[DeclarationStatus] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """
    List user's tax declarations with pagination

    Returns all declarations for the authenticated user.

    **Authentication**: Required (Bearer token)

    **Permissions**: Any authenticated user (own declarations only)

    **Query Parameters**:
    - status_filter: Optional filter (draft, submitted, processing, accepted, rejected, amended)
    - page: Page number (starts at 1)
    - page_size: Items per page (1-100, default 20)

    Returns:
        DeclarationListResponse: Paginated list with metadata
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

        offset = (page - 1) * page_size

        declarations, total = await declaration_repository.list_by_user(
            db,
            user_id,
            status=status_filter,
            limit=page_size,
            offset=offset,
        )

        total_pages = (total + page_size - 1) // page_size

        return DeclarationListResponse(
            declarations=[DeclarationResponse(**d) for d in declarations],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"Error listing declarations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list declarations: {str(e)}",
        )


@router.get("/{declaration_id}", response_model=DeclarationResponse)
async def get_declaration(
    declaration_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """
    Get tax declaration by ID

    **Authentication**: Required (Bearer token)

    **Permissions**:
    - Users can view their own declarations
    - declarations.view permission allows viewing any declaration (admin)

    **Security**:
    - Validates ownership (user_id) OR admin permission
    - Returns 404 if not found or not authorized

    Returns:
        DeclarationResponse: Declaration with related data
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

        declaration = await declaration_repository.get_by_id(db, declaration_id)

        if not declaration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Declaration not found",
            )

        # Security: Check ownership OR admin permission
        if declaration["user_id"] != user_id:
            # Check if user has admin permission to view any declaration
            perm_service = create_permission_service(db)
            has_admin_perm = await perm_service.has_permission(user_id, "declaration.view_all")

            if not has_admin_perm:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view this declaration",
                )

        return DeclarationResponse(**declaration)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching declaration {declaration_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch declaration: {str(e)}",
        )


@router.put("/{declaration_id}", response_model=DeclarationResponse)
async def update_declaration(
    declaration_id: str,
    update_data: DeclarationUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """
    Update tax declaration

    **Authentication**: Required (Bearer token)

    **Permissions**:
    - Users can update their own DRAFT declarations
    - declarations.update permission allows updating any declaration (admin)

    **Business Rules**:
    - Only DRAFT declarations can be updated by users
    - Admins with declarations.update can update any status
    - Partial updates supported (only changed fields)

    Returns:
        DeclarationResponse: Updated declaration
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

        # Check ownership and status
        declaration = await declaration_repository.get_by_id(db, declaration_id)

        if not declaration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Declaration not found",
            )

        # Check if user has admin permission
        perm_service = create_permission_service(db)
        has_admin_perm = await perm_service.has_permission(user_id, "declaration.update")

        # Security: Check ownership OR admin permission
        if declaration["user_id"] != user_id and not has_admin_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this declaration",
            )

        # Business rule: Only DRAFT can be updated by regular users
        # Admins can update any status
        if declaration["status"] != "draft" and not has_admin_perm:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only DRAFT declarations can be updated by users",
            )

        # Update declaration
        updated = await declaration_repository.update(db, declaration_id, update_data)

        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Declaration not found after update",
            )

        logger.info(f"User {user_id} updated declaration {declaration_id}")

        return DeclarationResponse(**updated)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating declaration {declaration_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update declaration: {str(e)}",
        )


@router.delete("/{declaration_id}", status_code=status.HTTP_200_OK)
async def delete_declaration(
    declaration_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """
    Delete tax declaration (soft delete)

    **Authentication**: Required (Bearer token)

    **Permissions**:
    - Users can delete their own DRAFT declarations
    - declarations.delete permission allows deleting any declaration (admin)

    **Business Rules**:
    - Only DRAFT declarations can be deleted by regular users
    - Admins can delete any status
    - Soft delete (status = cancelled)
    - Audit trail preserved

    Returns:
        Dict: Success message
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

        # Check ownership and status
        declaration = await declaration_repository.get_by_id(db, declaration_id)

        if not declaration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Declaration not found",
            )

        # Check if user has admin permission
        perm_service = create_permission_service(db)
        has_admin_perm = await perm_service.has_permission(user_id, "declaration.delete")

        # Security: Check ownership OR admin permission
        if declaration["user_id"] != user_id and not has_admin_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this declaration",
            )

        # Business rule: Only DRAFT can be deleted by regular users
        # Admins can delete any status
        if declaration["status"] != "draft" and not has_admin_perm:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only DRAFT declarations can be deleted by users",
            )

        # Soft delete
        deleted = await declaration_repository.delete(db, declaration_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Declaration not found",
            )

        logger.info(f"User {user_id} deleted declaration {declaration_id}")

        return {
            "message": "Declaration deleted successfully",
            "declaration_id": declaration_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting declaration {declaration_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete declaration: {str(e)}",
        )


@router.post("/{declaration_id}/submit", response_model=DeclarationResponse)
async def submit_declaration(
    declaration_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """
    Submit tax declaration for processing

    Changes status from DRAFT to SUBMITTED.
    Declaration enters agent validation workflow.

    **Authentication**: Required (Bearer token)

    **Permissions**: User can only submit own declarations

    **Business Rules**:
    - Only DRAFT declarations can be submitted
    - Must have required financial data filled
    - Sets submitted_at timestamp
    - Triggers agent assignment (future integration)

    Returns:
        DeclarationResponse: Submitted declaration
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

        # Check ownership and status
        declaration = await declaration_repository.get_by_id(db, declaration_id)

        if not declaration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Declaration not found",
            )

        # Security: Check ownership
        if declaration["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to submit this declaration",
            )

        # Business rule: Only DRAFT can be submitted
        if declaration["status"] != "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only DRAFT declarations can be submitted",
            )

        # Validation: Check required fields
        if not declaration.get("taxable_amount") or not declaration.get("calculated_tax"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required financial data (taxable_amount, calculated_tax)",
            )

        # Submit declaration
        submitted = await declaration_repository.submit(db, declaration_id)

        if not submitted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Declaration could not be submitted",
            )

        logger.info(f"User {user_id} submitted declaration {declaration_id}")

        # Publish DECLARATION_SUBMITTED event for notifications
        try:
            user_info = await db.fetchrow(
                "SELECT id, email, first_name, last_name, phone_number, preferred_language FROM users WHERE id = $1",
                user_id
            )
            if user_info:
                EventBus.publish_nowait(
                    EventType.DECLARATION_SUBMITTED,
                    {
                        "declaration_id": declaration_id,
                        "user_id": str(user_id),
                        "user_email": user_info['email'],
                        "user_name": f"{user_info['first_name']} {user_info['last_name']}",
                        "user_phone": user_info['phone_number'],
                        "preferred_language": user_info['preferred_language'] or 'es',
                        "declaration_type": submitted.get("declaration_type"),
                        "reference": submitted.get("reference"),
                        "amount": float(submitted.get("calculated_tax", 0)),
                        "timestamp": datetime.now().isoformat(),
                    }
                )
        except Exception:
            pass  # Non-blocking

        return DeclarationResponse(**submitted)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting declaration {declaration_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit declaration: {str(e)}",
        )


@router.get("/{declaration_id}/workflow", response_model=DeclarationWorkflowStatus)
async def get_declaration_workflow_status(
    declaration_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """
    Get workflow status for a declaration

    Returns current stage, completed stages, and available next actions.

    **Authentication**: Required (Bearer token)

    **Permissions**:
    - Users can view workflow for their own declarations
    - declarations.view permission allows viewing any workflow (admin)

    **Business Logic** (Service Layer):
    - Determines current stage based on status
    - Calculates completion for each stage
    - Provides context-aware next actions

    Returns:
        DeclarationWorkflowStatus: Workflow state with stages and actions
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

        # Check ownership and authorization
        declaration = await declaration_repository.get_by_id(db, declaration_id)

        if not declaration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Declaration not found",
            )

        # Security: Check ownership OR admin permission
        if declaration["user_id"] != user_id:
            perm_service = create_permission_service(db)
            has_admin_perm = await perm_service.has_permission(user_id, "declaration.view_all")

            if not has_admin_perm:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view this declaration workflow",
                )

        # Get workflow status from service (business logic)
        workflow_status = await declaration_service.get_workflow_status(db, declaration_id)

        logger.info(f"User {user_id} retrieved workflow status for declaration {declaration_id}")

        return workflow_status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow status for declaration {declaration_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workflow status: {str(e)}",
        )
