"""
Template Routes - Document and Procedure Templates API

Provides CRUD operations for document and procedure templates
Used by the frontend templates module

Routes:
- /api/v1/document-templates - Document template CRUD
- /api/v1/procedure-templates - Procedure template CRUD
- /api/v1/procedure-templates/{id}/steps - Procedure steps management
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query, Path
from typing import List, Optional
from loguru import logger
from app.config import get_settings
from app.core.errors import TranslatedException, ErrorCode

from app.modules.fiscal_services.models.templates import (
    DocumentTemplateCreate,
    DocumentTemplateUpdate,
    DocumentTemplateResponse,
    DocumentTemplateListResponse,
    ProcedureTemplateCreate,
    ProcedureTemplateUpdate,
    ProcedureTemplateResponse,
    ProcedureTemplateListResponse,
    ProcedureTemplateWithSteps,
    ProcedureStepCreate,
    ProcedureStepUpdate,
    ProcedureStepResponse,
)
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.database.connection import get_database

# =============================================================================
# ROUTERS
# =============================================================================

document_template_router = APIRouter(tags=["Document Templates"])
procedure_template_router = APIRouter(tags=["Procedure Templates"])


# =============================================================================
# DOCUMENT TEMPLATES ENDPOINTS
# =============================================================================

@document_template_router.get("", response_model=DocumentTemplateListResponse)
async def list_document_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    language: str = Query("es", description="Language code for translations (es, fr, en)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=1000, description="Page size"),
    db=Depends(get_database),
):
    """
    List all document templates with pagination and i18n support

    Public endpoint - no authentication required for listing
    """
    try:
        offset = (page - 1) * page_size

        # Build WHERE clause for count (no language param needed)
        count_where_clauses = []
        count_params = []
        count_idx = 1

        if category:
            count_where_clauses.append(f"dt.category = ${count_idx}")
            count_params.append(category)
            count_idx += 1

        if is_active is not None:
            count_where_clauses.append(f"dt.is_active = ${count_idx}")
            count_params.append(is_active)
            count_idx += 1

        count_where_clause = " AND ".join(count_where_clauses) if count_where_clauses else "TRUE"

        # Count total
        count_query = f"SELECT COUNT(*) FROM document_templates dt WHERE {count_where_clause}"
        total = await db.fetchval(count_query, *count_params)

        # Build WHERE clause for data query ($1 is language)
        where_clauses = []
        params = [language]
        param_idx = 2

        if category:
            where_clauses.append(f"dt.category = ${param_idx}")
            params.append(category)
            param_idx += 1

        if is_active is not None:
            where_clauses.append(f"dt.is_active = ${param_idx}")
            params.append(is_active)
            param_idx += 1

        where_clause = " AND ".join(where_clauses) if where_clauses else "TRUE"

        # Get data with i18n support
        data_query = f"""
            SELECT
                dt.id, dt.template_code,
                COALESCE(et_name.translation_text, dt.document_name_es) as document_name_es,
                COALESCE(et_desc.translation_text, dt.description_es) as description_es,
                dt.category, dt.validity_duration_months, dt.validity_notes,
                dt.usage_count, dt.is_active, dt.created_at, dt.updated_at
            FROM document_templates dt
            LEFT JOIN entity_translations et_name ON
                et_name.entity_type = 'document_template'
                AND et_name.entity_code = dt.template_code
                AND et_name.field_name = 'name'
                AND et_name.language_code = $1
            LEFT JOIN entity_translations et_desc ON
                et_desc.entity_type = 'document_template'
                AND et_desc.entity_code = dt.template_code
                AND et_desc.field_name = 'description'
                AND et_desc.language_code = $1
            WHERE {where_clause}
            ORDER BY dt.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([page_size, offset])
        results = await db.fetch(data_query, *params)

        templates = [DocumentTemplateResponse(**dict(r)) for r in results]
        total_pages = (total + page_size - 1) // page_size

        return DocumentTemplateListResponse(
            templates=templates,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"Error listing document templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving document templates"
        )


@document_template_router.get("/{template_id}", response_model=DocumentTemplateResponse)
async def get_document_template(
    template_id: int = Path(..., description="Template ID"),
    db=Depends(get_database),
):
    """Get a single document template by ID"""
    try:
        query = "SELECT * FROM document_templates WHERE id = $1"
        result = await db.fetchrow(query, template_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document template {template_id} not found"
            )

        return DocumentTemplateResponse(**dict(result))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving document template"
        )


@document_template_router.post("", response_model=DocumentTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_document_template(
    template: DocumentTemplateCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("template.create")),
):
    """
    Create a new document template

    Requires templates.create permission
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

        # Check for duplicate template_code
        existing = await db.fetchval(
            "SELECT id FROM document_templates WHERE template_code = $1",
            template.template_code
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template with code '{template.template_code}' already exists"
            )

        query = """
            INSERT INTO document_templates (
                template_code, document_name_es, description_es, category,
                validity_duration_months, validity_notes, is_active
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
        """
        result = await db.fetchrow(
            query,
            template.template_code,
            template.document_name_es,
            template.description_es,
            template.category,
            template.validity_duration_months,
            template.validity_notes,
            template.is_active,
        )

        logger.info(f"Document template created: {template.template_code} by user {user_id}")
        return DocumentTemplateResponse(**dict(result))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating document template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating document template"
        )


@document_template_router.put("/{template_id}", response_model=DocumentTemplateResponse)
async def update_document_template(
    template_id: int = Path(..., description="Template ID"),
    template: DocumentTemplateUpdate = ...,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("template.update")),
):
    """
    Update a document template

    Requires templates.update permission
    """
    try:
        # Check exists
        existing = await db.fetchrow(
            "SELECT * FROM document_templates WHERE id = $1",
            template_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document template {template_id} not found"
            )

        # Build update
        update_data = template.dict(exclude_unset=True, exclude_none=True)
        if not update_data:
            return DocumentTemplateResponse(**dict(existing))

        set_clauses = []
        params = []
        param_idx = 1

        for key, value in update_data.items():
            set_clauses.append(f"{key} = ${param_idx}")
            params.append(value)
            param_idx += 1

        set_clauses.append(f"updated_at = NOW()")
        params.append(template_id)

        query = f"""
            UPDATE document_templates
            SET {', '.join(set_clauses)}
            WHERE id = ${param_idx}
            RETURNING *
        """
        result = await db.fetchrow(query, *params)

        logger.info(f"Document template {template_id} updated")
        return DocumentTemplateResponse(**dict(result))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating document template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating document template"
        )


@document_template_router.delete("/{template_id}", status_code=status.HTTP_200_OK)
async def delete_document_template(
    template_id: int = Path(..., description="Template ID"),
    current_user=Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("template.delete")),
):
    """
    Delete a document template

    Requires templates.delete permission
    """
    try:
        # Check exists
        existing = await db.fetchval(
            "SELECT id FROM document_templates WHERE id = $1",
            template_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document template {template_id} not found"
            )

        # Check if in use
        in_use = await db.fetchval(
            "SELECT COUNT(*) FROM service_document_assignments WHERE document_template_id = $1",
            template_id
        )
        if in_use and in_use > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete template: it is assigned to {in_use} services"
            )

        await db.execute("DELETE FROM document_templates WHERE id = $1", template_id)

        logger.info(f"Document template {template_id} deleted")
        return {"message": "Document template deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting document template"
        )


# =============================================================================
# PROCEDURE TEMPLATES ENDPOINTS
# =============================================================================

@procedure_template_router.get("", response_model=ProcedureTemplateListResponse)
async def list_procedure_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    language: str = Query("es", description="Language code for translations (es, fr, en)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=1000, description="Page size"),
    db=Depends(get_database),
):
    """
    List all procedure templates with pagination and i18n support

    Public endpoint - no authentication required for listing
    """
    try:
        offset = (page - 1) * page_size

        # Build WHERE clause for count (no language param needed)
        count_where_clauses = []
        count_params = []
        count_idx = 1

        if category:
            count_where_clauses.append(f"pt.category = ${count_idx}")
            count_params.append(category)
            count_idx += 1

        if is_active is not None:
            count_where_clauses.append(f"pt.is_active = ${count_idx}")
            count_params.append(is_active)
            count_idx += 1

        count_where_clause = " AND ".join(count_where_clauses) if count_where_clauses else "TRUE"

        # Count total
        count_query = f"SELECT COUNT(*) FROM procedure_templates pt WHERE {count_where_clause}"
        total = await db.fetchval(count_query, *count_params)

        # Build WHERE clause for data query ($1 is language)
        where_clauses = []
        params = [language]
        param_idx = 2

        if category:
            where_clauses.append(f"pt.category = ${param_idx}")
            params.append(category)
            param_idx += 1

        if is_active is not None:
            where_clauses.append(f"pt.is_active = ${param_idx}")
            params.append(is_active)
            param_idx += 1

        where_clause = " AND ".join(where_clauses) if where_clauses else "TRUE"

        # Get data with i18n support
        data_query = f"""
            SELECT
                pt.id, pt.template_code,
                COALESCE(et_name.translation_text, pt.name_es) as name_es,
                COALESCE(et_desc.translation_text, pt.description_es) as description_es,
                pt.category, pt.usage_count, pt.is_active, pt.created_at, pt.updated_at
            FROM procedure_templates pt
            LEFT JOIN entity_translations et_name ON
                et_name.entity_type = 'procedure_template'
                AND et_name.entity_code = pt.template_code
                AND et_name.field_name = 'name'
                AND et_name.language_code = $1
            LEFT JOIN entity_translations et_desc ON
                et_desc.entity_type = 'procedure_template'
                AND et_desc.entity_code = pt.template_code
                AND et_desc.field_name = 'description'
                AND et_desc.language_code = $1
            WHERE {where_clause}
            ORDER BY pt.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([page_size, offset])
        results = await db.fetch(data_query, *params)

        templates = [ProcedureTemplateResponse(**dict(r)) for r in results]
        total_pages = (total + page_size - 1) // page_size

        return ProcedureTemplateListResponse(
            templates=templates,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"Error listing procedure templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving procedure templates"
        )


@procedure_template_router.get("/{template_id}", response_model=ProcedureTemplateWithSteps)
async def get_procedure_template(
    template_id: int = Path(..., description="Template ID"),
    db=Depends(get_database),
):
    """Get a single procedure template by ID with all its steps"""
    try:
        query = "SELECT * FROM procedure_templates WHERE id = $1"
        result = await db.fetchrow(query, template_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Procedure template {template_id} not found"
            )

        # Get steps
        steps_query = """
            SELECT * FROM procedure_template_steps
            WHERE template_id = $1
            ORDER BY step_number ASC
        """
        steps = await db.fetch(steps_query, template_id)

        template_data = dict(result)
        template_data["steps"] = [ProcedureStepResponse(**dict(s)) for s in steps]

        return ProcedureTemplateWithSteps(**template_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting procedure template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving procedure template"
        )


@procedure_template_router.post("", response_model=ProcedureTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_procedure_template(
    template: ProcedureTemplateCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("template.create")),
):
    """
    Create a new procedure template

    Requires templates.create permission
    """
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

        # Check for duplicate template_code
        existing = await db.fetchval(
            "SELECT id FROM procedure_templates WHERE template_code = $1",
            template.template_code
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template with code '{template.template_code}' already exists"
            )

        query = """
            INSERT INTO procedure_templates (
                template_code, name_es, description_es, category, is_active
            )
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """
        result = await db.fetchrow(
            query,
            template.template_code,
            template.name_es,
            template.description_es,
            template.category,
            template.is_active,
        )

        logger.info(f"Procedure template created: {template.template_code} by user {user_id}")
        return ProcedureTemplateResponse(**dict(result))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating procedure template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating procedure template"
        )


@procedure_template_router.put("/{template_id}", response_model=ProcedureTemplateResponse)
async def update_procedure_template(
    template_id: int = Path(..., description="Template ID"),
    template: ProcedureTemplateUpdate = ...,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("template.update")),
):
    """
    Update a procedure template

    Requires templates.update permission
    """
    try:
        # Check exists
        existing = await db.fetchrow(
            "SELECT * FROM procedure_templates WHERE id = $1",
            template_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Procedure template {template_id} not found"
            )

        # Build update
        update_data = template.dict(exclude_unset=True, exclude_none=True)
        if not update_data:
            return ProcedureTemplateResponse(**dict(existing))

        set_clauses = []
        params = []
        param_idx = 1

        for key, value in update_data.items():
            set_clauses.append(f"{key} = ${param_idx}")
            params.append(value)
            param_idx += 1

        set_clauses.append(f"updated_at = NOW()")
        params.append(template_id)

        query = f"""
            UPDATE procedure_templates
            SET {', '.join(set_clauses)}
            WHERE id = ${param_idx}
            RETURNING *
        """
        result = await db.fetchrow(query, *params)

        logger.info(f"Procedure template {template_id} updated")
        return ProcedureTemplateResponse(**dict(result))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating procedure template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating procedure template"
        )


@procedure_template_router.delete("/{template_id}", status_code=status.HTTP_200_OK)
async def delete_procedure_template(
    template_id: int = Path(..., description="Template ID"),
    current_user=Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("template.delete")),
):
    """
    Delete a procedure template

    Requires templates.delete permission
    """
    try:
        # Check exists
        existing = await db.fetchval(
            "SELECT id FROM procedure_templates WHERE id = $1",
            template_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Procedure template {template_id} not found"
            )

        # Check if in use
        in_use = await db.fetchval(
            "SELECT COUNT(*) FROM service_procedure_assignments WHERE template_id = $1",
            template_id
        )
        if in_use and in_use > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete template: it is assigned to {in_use} services"
            )

        # Delete steps first
        await db.execute("DELETE FROM procedure_template_steps WHERE template_id = $1", template_id)
        await db.execute("DELETE FROM procedure_templates WHERE id = $1", template_id)

        logger.info(f"Procedure template {template_id} deleted")
        return {"message": "Procedure template deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting procedure template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting procedure template"
        )


# =============================================================================
# PROCEDURE STEPS ENDPOINTS
# =============================================================================

@procedure_template_router.get("/{template_id}/steps", response_model=List[ProcedureStepResponse])
async def list_procedure_steps(
    template_id: int = Path(..., description="Template ID"),
    db=Depends(get_database),
):
    """Get all steps for a procedure template"""
    try:
        # Check template exists
        existing = await db.fetchrow(
            "SELECT id, template_code FROM procedure_templates WHERE id = $1",
            template_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Procedure template {template_id} not found"
            )

        template_code = existing["template_code"]
        logger.info(f"[STEPS] Fetching steps for template_id={template_id}, template_code={template_code}")

        query = """
            SELECT * FROM procedure_template_steps
            WHERE template_id = $1
            ORDER BY step_number ASC
        """
        results = await db.fetch(query, template_id)

        logger.info(f"[STEPS] Found {len(results)} steps for template_id={template_id}")

        return [ProcedureStepResponse(**dict(r)) for r in results]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing steps for template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving procedure steps"
        )


@procedure_template_router.get("/{template_id}/steps/{step_id}", response_model=ProcedureStepResponse)
async def get_procedure_step(
    template_id: int = Path(..., description="Template ID"),
    step_id: int = Path(..., description="Step ID"),
    db=Depends(get_database),
):
    """Get a single procedure step"""
    try:
        query = """
            SELECT * FROM procedure_template_steps
            WHERE id = $1 AND template_id = $2
        """
        result = await db.fetchrow(query, step_id, template_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Step {step_id} not found in template {template_id}"
            )

        return ProcedureStepResponse(**dict(result))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting step {step_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving procedure step"
        )


@procedure_template_router.post("/{template_id}/steps", response_model=ProcedureStepResponse, status_code=status.HTTP_201_CREATED)
async def create_procedure_step(
    template_id: int = Path(..., description="Template ID"),
    step: ProcedureStepCreate = ...,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("template.update")),
):
    """
    Create a new procedure step

    Requires templates.update permission
    """
    try:
        # Check template exists
        existing = await db.fetchval(
            "SELECT id FROM procedure_templates WHERE id = $1",
            template_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Procedure template {template_id} not found"
            )

        # Validate template_id matches
        if step.template_id != template_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="template_id in body must match URL parameter"
            )

        query = """
            INSERT INTO procedure_template_steps (
                template_id, step_number, description_es, instructions_es,
                estimated_duration_minutes, location_address, office_hours,
                requires_appointment, is_optional
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING *
        """
        result = await db.fetchrow(
            query,
            template_id,
            step.step_number,
            step.description_es,
            step.instructions_es,
            step.estimated_duration_minutes,
            step.location_address,
            step.office_hours,
            step.requires_appointment,
            step.is_optional,
        )

        logger.info(f"Step {step.step_number} created for template {template_id}")
        return ProcedureStepResponse(**dict(result))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating step for template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating procedure step"
        )


@procedure_template_router.put("/{template_id}/steps/{step_id}", response_model=ProcedureStepResponse)
async def update_procedure_step(
    template_id: int = Path(..., description="Template ID"),
    step_id: int = Path(..., description="Step ID"),
    step: ProcedureStepUpdate = ...,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("template.update")),
):
    """
    Update a procedure step

    Requires templates.update permission
    """
    try:
        # Check exists
        existing = await db.fetchrow(
            "SELECT * FROM procedure_template_steps WHERE id = $1 AND template_id = $2",
            step_id, template_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Step {step_id} not found in template {template_id}"
            )

        # Build update
        update_data = step.dict(exclude_unset=True, exclude_none=True)
        if not update_data:
            return ProcedureStepResponse(**dict(existing))

        set_clauses = []
        params = []
        param_idx = 1

        for key, value in update_data.items():
            set_clauses.append(f"{key} = ${param_idx}")
            params.append(value)
            param_idx += 1

        set_clauses.append(f"updated_at = NOW()")
        params.extend([step_id, template_id])

        query = f"""
            UPDATE procedure_template_steps
            SET {', '.join(set_clauses)}
            WHERE id = ${param_idx} AND template_id = ${param_idx + 1}
            RETURNING *
        """
        result = await db.fetchrow(query, *params)

        logger.info(f"Step {step_id} updated in template {template_id}")
        return ProcedureStepResponse(**dict(result))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating step {step_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating procedure step"
        )


@procedure_template_router.delete("/{template_id}/steps/{step_id}", status_code=status.HTTP_200_OK)
async def delete_procedure_step(
    template_id: int = Path(..., description="Template ID"),
    step_id: int = Path(..., description="Step ID"),
    current_user=Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("template.update")),
):
    """
    Delete a procedure step

    Requires templates.update permission
    """
    try:
        # Check exists
        existing = await db.fetchval(
            "SELECT id FROM procedure_template_steps WHERE id = $1 AND template_id = $2",
            step_id, template_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Step {step_id} not found in template {template_id}"
            )

        await db.execute(
            "DELETE FROM procedure_template_steps WHERE id = $1 AND template_id = $2",
            step_id, template_id
        )

        logger.info(f"Step {step_id} deleted from template {template_id}")
        return {"message": "Procedure step deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting step {step_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting procedure step"
        )


@procedure_template_router.post("/{template_id}/steps/reorder", status_code=status.HTTP_200_OK)
async def reorder_procedure_steps(
    template_id: int = Path(..., description="Template ID"),
    step_ids: List[int] = ...,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("template.update")),
):
    """
    Reorder procedure steps

    Requires templates.update permission

    Body: { "step_ids": [3, 1, 2] } - New order of step IDs
    """
    try:
        # Check template exists
        existing = await db.fetchval(
            "SELECT id FROM procedure_templates WHERE id = $1",
            template_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Procedure template {template_id} not found"
            )

        # Update step_number for each step
        for idx, step_id in enumerate(step_ids, start=1):
            await db.execute(
                """
                UPDATE procedure_template_steps
                SET step_number = $1, updated_at = NOW()
                WHERE id = $2 AND template_id = $3
                """,
                idx, step_id, template_id
            )

        logger.info(f"Steps reordered for template {template_id}")
        return {"message": "Steps reordered successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reordering steps for template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error reordering procedure steps"
        )


# =============================================================================
# DIAGNOSTIC ENDPOINTS (for debugging data issues)
# =============================================================================


@procedure_template_router.get("/debug/steps-diagnostic")
async def diagnose_procedure_steps(
    db=Depends(get_database),
):
    """
    Diagnostic endpoint to check procedure_template_steps data consistency (staging only).
    Returns 404 in production.
    """
    _settings = get_settings()
    if _settings.environment == "production":
        raise TranslatedException(ErrorCode.NOT_FOUND)
    try:
        # Total steps
        total_steps = await db.fetchval("SELECT COUNT(*) FROM procedure_template_steps")

        # Steps with valid template_id
        valid_steps = await db.fetchval("""
            SELECT COUNT(*) FROM procedure_template_steps pts
            WHERE EXISTS (SELECT 1 FROM procedure_templates pt WHERE pt.id = pts.template_id)
        """)

        # Steps with orphaned template_id
        orphaned_steps = await db.fetchval("""
            SELECT COUNT(*) FROM procedure_template_steps pts
            WHERE NOT EXISTS (SELECT 1 FROM procedure_templates pt WHERE pt.id = pts.template_id)
        """)

        # Get distinct template_ids from steps
        step_template_ids = await db.fetch("""
            SELECT DISTINCT template_id FROM procedure_template_steps
            ORDER BY template_id
            LIMIT 20
        """)

        # Get procedure templates without steps (first 10)
        templates_without_steps = await db.fetch("""
            SELECT pt.id, pt.template_code, pt.name_es
            FROM procedure_templates pt
            WHERE NOT EXISTS (
                SELECT 1 FROM procedure_template_steps pts WHERE pts.template_id = pt.id
            )
            ORDER BY pt.id
            LIMIT 10
        """)

        # Get procedure templates with steps (first 10)
        templates_with_steps = await db.fetch("""
            SELECT pt.id, pt.template_code, pt.name_es, COUNT(pts.id) as step_count
            FROM procedure_templates pt
            JOIN procedure_template_steps pts ON pts.template_id = pt.id
            GROUP BY pt.id, pt.template_code, pt.name_es
            ORDER BY pt.id
            LIMIT 10
        """)

        return {
            "total_steps_in_database": total_steps,
            "steps_with_valid_template_id": valid_steps,
            "steps_with_orphaned_template_id": orphaned_steps,
            "distinct_template_ids_in_steps": [r["template_id"] for r in step_template_ids],
            "templates_without_steps": [dict(r) for r in templates_without_steps],
            "templates_with_steps": [dict(r) for r in templates_with_steps],
        }

    except Exception as e:
        logger.error(f"Error in steps diagnostic: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Diagnostic error: {str(e)}"
        )
