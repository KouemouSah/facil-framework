"""Fiscal Service Routes - 850 tax services catalog API

Includes Redis cache for frequently accessed data (ministries, sectors, categories).
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer
from typing import Dict, Any, List, Optional
from loguru import logger
from pydantic import BaseModel
import time
import csv
import io
from io import BytesIO
from PIL import Image

from app.core.cache import get_services_cache, CacheKeys, invalidate_services_cache

from app.modules.fiscal_services.models import (
    MinistryCreate,
    MinistryUpdate,
    MinistryResponse,
    SectorCreate,
    SectorUpdate,
    SectorResponse,
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    FiscalServiceCreate,
    FiscalServiceUpdate,
    FiscalServiceResponse,
    FiscalServiceListResponse,
    FiscalServiceSearchRequest,
    CalculateServiceRequest,
    CalculateServiceResponse,
    FiscalServiceStats,
)
from app.modules.fiscal_services.models.search import (
    SearchDBRequest,
    SearchDBResponse,
    ServiceResultItem,
    SearchFacets,
    FacetItem,
)
from app.modules.fiscal_services.models.service_details import (
    ServiceDetailsResponse,
    DocumentDetailItem,
    ProcedureDetailItem,
    ProcedureStepDetailItem,
    CategoryDetailItem,
    SectorDetailItem,
    MinistryDetailItem,
    PricingInfo,
    RelatedServiceItem,
    KeywordItem,
)
from app.modules.fiscal_services.models.templates import (
    ServiceDocumentAssignmentCreate,
    ServiceDocumentAssignmentResponse,
    ServiceProcedureAssignmentCreate,
    ServiceProcedureAssignmentResponse,
)
from app.modules.fiscal_services.repositories import FiscalServiceRepository
from app.modules.fiscal_services.repositories.search_repository import SearchRepository
from app.modules.fiscal_services.repositories.service_details_repository import ServiceDetailsRepository
from app.modules.fiscal_services.services import CalculationService
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.database.connection import get_database
from app.core.errors import TranslatedException, ErrorCode

router = APIRouter(tags=["Fiscal Services"])
security = HTTPBearer()
repository = FiscalServiceRepository()
search_repository = SearchRepository()
details_repository = ServiceDetailsRepository()
calculation_service = CalculationService()


# ========== HIERARCHY ENDPOINTS ==========

@router.get("/ministries", response_model=List[MinistryResponse])
async def list_ministries(
    language: str = Query("es", pattern="^(es|fr|en)$", description="Language code for translations"),
    db=Depends(get_database),
):
    """List all ministries (Ministères) with i18n support. Cached for 1 hour."""
    cache = get_services_cache()
    cache_key = CacheKeys.custom("ministries", language)

    # Try cache first
    cached = await cache.get(cache_key)
    if cached is not None:
        logger.debug(f"Cache HIT for ministries:{language}")
        return [MinistryResponse(**m) for m in cached]

    # Cache miss - fetch from database
    ministries = await repository.list_ministries(db, language=language)

    # Store in cache (1 hour TTL)
    await cache.set(cache_key, ministries, ttl=3600)

    return [MinistryResponse(**m) for m in ministries]


@router.get("/sectors", response_model=List[SectorResponse])
async def list_sectors(
    ministry_id: int = Query(None, description="Filter by ministry ID"),
    language: str = Query("es", pattern="^(es|fr|en)$", description="Language code for translations"),
    db=Depends(get_database),
):
    """List sectors (Secteurs), optionally filtered by ministry, with i18n support. Cached for 1 hour."""
    cache = get_services_cache()
    cache_key = CacheKeys.custom("sectors", language, str(ministry_id or "all"))

    # Try cache first
    cached = await cache.get(cache_key)
    if cached is not None:
        logger.debug(f"Cache HIT for sectors:{language}:{ministry_id}")
        return [SectorResponse(**s) for s in cached]

    # Cache miss - fetch from database
    sectors = await repository.list_sectors(db, ministry_id=ministry_id, language=language)

    # Store in cache (1 hour TTL)
    await cache.set(cache_key, sectors, ttl=3600)

    return [SectorResponse(**s) for s in sectors]


@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(
    sector_id: int = Query(None, description="Filter by sector ID"),
    language: str = Query("es", pattern="^(es|fr|en)$", description="Language code for translations"),
    db=Depends(get_database),
):
    """List categories (Catégories), optionally filtered by sector, with i18n support. Cached for 1 hour."""
    cache = get_services_cache()
    cache_key = CacheKeys.custom("categories", language, str(sector_id or "all"))

    # Try cache first
    cached = await cache.get(cache_key)
    if cached is not None:
        logger.debug(f"Cache HIT for categories:{language}:{sector_id}")
        return [CategoryResponse(**c) for c in cached]

    # Cache miss - fetch from database
    categories = await repository.list_categories(db, sector_id=sector_id, language=language)

    # Store in cache (1 hour TTL)
    await cache.set(cache_key, categories, ttl=3600)

    return [CategoryResponse(**c) for c in categories]


# ========== FISCAL SERVICES PUBLIC ENDPOINTS ==========

@router.get("", response_model=FiscalServiceListResponse)
async def list_fiscal_services(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: Optional[int] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status (active, inactive, draft, deprecated)"),
    ministry_id: Optional[int] = Query(None, description="Filter by ministry"),
    sector_id: Optional[int] = Query(None, description="Filter by sector"),
    search: Optional[str] = Query(None, min_length=1, max_length=200, description="Search by name or code"),
    sort_by: str = Query("service_code", description="Sort field: service_code, name, price, status, popular, updated"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$", description="Sort direction"),
    language: str = Query("es", pattern="^(es|fr|en)$", description="Language for translations"),
    db=Depends(get_database),
):
    """List fiscal services with server-side filtering, search, sorting, and pagination"""
    offset = (page - 1) * page_size
    # TODO: repository.list() does not yet accept language for i18n translations
    # of category_name, sector_name, ministry_name (currently hardcoded to name_es).
    # Once the repository supports it, pass language=language here.
    services, total = await repository.list(
        db, category_id=category_id, status=status,
        ministry_id=ministry_id, sector_id=sector_id, search=search,
        sort_by=sort_by, sort_order=sort_order,
        limit=page_size, offset=offset,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return FiscalServiceListResponse(
        services=[FiscalServiceResponse(**s) for s in services],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{service_id}", response_model=FiscalServiceResponse)
async def get_fiscal_service(
    service_id: int,
    language: str = Query("es", pattern="^(es|fr|en)$", description="Language for translations"),
    db=Depends(get_database),
):
    """Get fiscal service by ID with i18n support"""
    # TODO: repository.get_by_id() does not yet accept language for i18n translations
    # of category_name, sector_name, ministry_name (currently hardcoded to name_es).
    # Once the repository supports it, pass language=language here.
    service = await repository.get_by_id(db, service_id)
    if not service:
        raise TranslatedException(ErrorCode.SERVICE_NOT_FOUND)
    return FiscalServiceResponse(**service)


@router.get("/{service_id}/details", response_model=ServiceDetailsResponse)
async def get_service_details(
    service_id: int,
    language: str = Query("es", pattern="^(es|fr|en)$", description="Language for translations"),
    include_related: bool = Query(True, description="Include related services"),
    include_keywords: bool = Query(False, description="Include search keywords"),
    db=Depends(get_database),
):
    """
    Get complete service details with documents, procedures, and related info.
    Cached for 1 hour.

    This endpoint provides:
    - Full service information with translations
    - Required documents list with details
    - Procedures with all steps
    - Pricing information (expedition/renewal)
    - Category, sector, ministry hierarchy
    - Related services in same category
    - Parent and child services (if any)
    - Keywords (optional, for SEO)

    **Used by:** Frontend /services/[id] page
    """
    try:
        # Get main service details
        service = await details_repository.get_service_details(db, service_id, language)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service with ID {service_id} not found"
            )

        # Get documents
        documents = await details_repository.get_service_documents(db, service_id, language)

        # Get procedures
        procedures = await details_repository.get_service_procedures(db, service_id, language)

        # Calculate total procedure steps
        total_steps = sum(len(p.get("steps", [])) for p in procedures)

        # Get related services
        related_services = []
        parent_service = None
        child_services = []

        if include_related and service.get("category_id"):
            related_services = await details_repository.get_related_services(
                db, service_id, service["category_id"], language
            )

        # Get parent service if exists
        if service.get("parent_service_id"):
            parent_service = await details_repository.get_parent_service(
                db, service["parent_service_id"], language
            )

        # Get child services
        child_services = await details_repository.get_child_services(db, service_id, language)

        # Get keywords if requested
        keywords = []
        if include_keywords:
            keywords = await details_repository.get_service_keywords(db, service_id)

        # Build pricing info
        expedition_price = service.get("expedition_price", 0) or 0
        renewal_price = service.get("renewal_price", 0) or 0
        pricing = PricingInfo(
            expedition_price=expedition_price,
            renewal_price=renewal_price,
            calculation_method=service.get("calculation_method", "fixed_both"),
            percentage_rate=service.get("percentage_rate"),
            unit_price=service.get("unit_price"),
            validity_period_months=service.get("validity_period_months"),
            renewal_frequency_months=service.get("renewal_frequency_months"),
            currency="XAF",
        )

        # Build category
        category = None
        if service.get("category_id"):
            category = CategoryDetailItem(
                id=service["category_id"],
                category_code=service.get("category_code", ""),
                name=service.get("category_name", ""),
                description=service.get("category_description"),
                icon=service.get("category_icon"),
                color=service.get("category_color"),
            )

        # Build sector
        sector = None
        if service.get("sector_id"):
            sector = SectorDetailItem(
                id=service["sector_id"],
                code=service.get("sector_code", ""),
                name=service.get("sector_name", ""),
                description=service.get("sector_description"),
            )

        # Build ministry
        ministry = None
        if service.get("ministry_id"):
            ministry = MinistryDetailItem(
                id=service["ministry_id"],
                code=service.get("ministry_code", ""),
                name=service.get("ministry_name", ""),
                description=service.get("ministry_description"),
            )

        # Build response
        return ServiceDetailsResponse(
            id=service["id"],
            service_code=service.get("service_code", ""),
            name=service.get("name", ""),
            description=service.get("description"),
            service_type=service.get("service_type", ""),
            status=service.get("status", "active"),
            pricing=pricing,
            processing_time_days=service.get("processing_time_days"),
            legal_reference=service.get("legal_reference"),
            notes=service.get("notes"),
            category=category,
            sector=sector,
            ministry=ministry,
            documents=[DocumentDetailItem(**d) for d in documents],
            documents_count=len(documents),
            procedures=[
                ProcedureDetailItem(
                    id=p["id"],
                    template_code=p.get("template_code", ""),
                    name=p.get("name", ""),
                    description=p.get("description"),
                    category=p.get("category"),
                    applies_to=p.get("applies_to"),
                    display_order=p.get("display_order", 1),
                    custom_notes=p.get("custom_notes"),
                    steps=[ProcedureStepDetailItem(**s) for s in p.get("steps", [])],
                    total_estimated_minutes=p.get("total_estimated_minutes", 0),
                )
                for p in procedures
            ],
            procedures_count=len(procedures),
            total_procedure_steps=total_steps,
            related_services=[RelatedServiceItem(**r) for r in related_services],
            parent_service=RelatedServiceItem(**parent_service) if parent_service else None,
            child_services=[RelatedServiceItem(**c) for c in child_services],
            keywords=[KeywordItem(**k) for k in keywords],
            view_count=service.get("view_count", 0) or 0,
            calculation_count=service.get("calculation_count", 0) or 0,
            last_updated=service.get("last_updated"),
            has_documents=len(documents) > 0,
            has_procedures=len(procedures) > 0,
            is_free=expedition_price == 0 and renewal_price == 0,
            requires_renewal=service.get("renewal_frequency_months") is not None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching service details for {service_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching service details: {str(e)}"
        )


@router.post("/search", response_model=FiscalServiceListResponse)
async def search_fiscal_services(
    search: FiscalServiceSearchRequest,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db=Depends(get_database),
):
    """Advanced search for fiscal services"""
    offset = (page - 1) * page_size
    services, total = await repository.search(db, search, page_size, offset)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return FiscalServiceListResponse(
        services=[FiscalServiceResponse(**s) for s in services],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/search-db", response_model=SearchDBResponse)
async def search_services_db(
    request: SearchDBRequest,
    db=Depends(get_database),
):
    """
    Advanced search for fiscal services with facets (Public endpoint for Services page)

    This endpoint provides:
    - Full-text search across service names, descriptions, and keywords
    - Filtering by category, ministry, service type, and price ranges
    - Faceted search results for dynamic filtering UI
    - Multilingual support (es, fr, en)
    - Pagination and sorting

    **Used by:** Frontend /services page
    """
    start_time = time.time()

    try:
        # Search services
        results, total = await search_repository.search_services(
            conn=db,
            q=request.q,
            category_id=request.category_id,
            category_code=request.category_code,
            ministry_id=request.ministry_id,
            service_type=request.service_type,
            min_price=request.min_price,
            max_price=request.max_price,
            min_expedition_price=request.min_expedition_price,
            max_expedition_price=request.max_expedition_price,
            min_renewal_price=request.min_renewal_price,
            max_renewal_price=request.max_renewal_price,
            sort_by=request.sort_by.value,
            sort_order=request.sort_order.value,
            page=request.page,
            limit=request.limit,
            language=request.language,
        )

        # Get facets if requested
        facets = None
        if request.include_facets:
            facets_data = await search_repository.get_facets(db, request.language)
            facets = SearchFacets(
                categories=[FacetItem(**f) for f in facets_data["categories"]],
                ministries=[FacetItem(**f) for f in facets_data["ministries"]],
                service_types=[FacetItem(**f) for f in facets_data["service_types"]],
                price_ranges=[FacetItem(**f) for f in facets_data["price_ranges"]],
            )

        # Get suggestions
        suggestions = await search_repository.get_suggestions(db, request.q, request.language)

        # Calculate execution time
        execution_time_ms = (time.time() - start_time) * 1000

        # Calculate total pages
        total_pages = (total + request.limit - 1) // request.limit if total > 0 else 0

        return SearchDBResponse(
            success=True,
            query=request.q or "",
            total_results=total,
            page=request.page,
            limit=request.limit,
            total_pages=total_pages,
            results=[ServiceResultItem(**r) for r in results],
            facets=facets,
            suggestions=suggestions,
            execution_time_ms=round(execution_time_ms, 2),
            cached=False,
        )

    except Exception as e:
        logger.error(f"Search-db error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/popular/list", response_model=List[FiscalServiceResponse])
async def get_popular_services(
    limit: int = Query(10, ge=1, le=50, description="Number of popular services"),
    db=Depends(get_database),
):
    """Get most used fiscal services"""
    services = await repository.get_popular(db, limit)
    return [FiscalServiceResponse(**s) for s in services]


@router.get("/recent/list", response_model=List[FiscalServiceResponse])
async def get_recent_services(
    limit: int = Query(10, ge=1, le=50, description="Number of recent services"),
    db=Depends(get_database),
):
    """Get recently used fiscal services"""
    services = await repository.get_recent(db, limit)
    return [FiscalServiceResponse(**s) for s in services]


@router.post("/calculate", response_model=CalculateServiceResponse)
async def calculate_service_amount(
    request: CalculateServiceRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Calculate amount for a fiscal service"""
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    # Verify service exists
    service = await repository.get_by_id(db, request.fiscal_service_id)
    if not service:
        raise TranslatedException(ErrorCode.SERVICE_NOT_FOUND)

    try:
        # Calculate
        result = await calculation_service.calculate(db, request)

        # Increment usage counter
        await repository.increment_usage(db, request.fiscal_service_id)

        logger.info(f"User {user_id} calculated service {request.fiscal_service_id}")
        return result

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ========== ADMIN ENDPOINTS ==========

# ============================================================================
# ADMIN: MINISTRY MANAGEMENT
# ============================================================================

@router.post("/admin/ministries", response_model=MinistryResponse, status_code=status.HTTP_201_CREATED)
async def create_ministry(
    data: MinistryCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.manage_hierarchy"))
):
    """
    Create a new ministry

    Requires fiscal_service.manage_hierarchy permission

    - **ministry_code**: Unique ministry code (max 10 chars)
    - **name_es**: Ministry name in Spanish
    - **description_es**: Optional description
    - **display_order**: Display order for sorting (default 0)
    - **icon**: Optional icon identifier
    - **color**: Optional hex color code (#RRGGBB)
    - **website_url**: Optional ministry website
    - **contact_email**: Optional contact email
    - **contact_phone**: Optional contact phone
    - **is_active**: Whether ministry is active (default True)
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    try:
        # Check if ministry code already exists
        existing = await repository.get_ministry_by_code(db, data.ministry_code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ministry with code '{data.ministry_code}' already exists"
            )

        # Create ministry
        ministry_data = data.dict()
        result = await repository.create_ministry(db, ministry_data)

        logger.info(f"Admin {user_id} created ministry {result['id']} ({data.ministry_code})")
        return MinistryResponse(**result)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating ministry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating ministry: {str(e)}"
        )


@router.get("/admin/ministries/{ministry_id}", response_model=MinistryResponse)
async def get_ministry_by_id(
    ministry_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.manage_hierarchy"))
):
    """Get ministry by ID - Requires fiscal_service.manage_hierarchy permission"""
    ministry = await repository.get_ministry_by_id(db, ministry_id)
    if not ministry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ministry with ID {ministry_id} not found"
        )
    return MinistryResponse(**ministry)


@router.put("/admin/ministries/{ministry_id}", response_model=MinistryResponse)
async def update_ministry(
    ministry_id: int,
    data: MinistryUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.manage_hierarchy"))
):
    """
    Update a ministry

    Requires fiscal_service.manage_hierarchy permission

    All fields are optional. Only provided fields will be updated.
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    try:
        # Check if ministry exists
        existing = await repository.get_ministry_by_id(db, ministry_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ministry with ID {ministry_id} not found"
            )

        # Update ministry
        update_data = data.dict(exclude_unset=True)
        if not update_data:
            return MinistryResponse(**existing)

        result = await repository.update_ministry(db, ministry_id, update_data)

        logger.info(f"Admin {user_id} updated ministry {ministry_id}")
        return MinistryResponse(**result)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating ministry {ministry_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating ministry: {str(e)}"
        )


@router.delete("/admin/ministries/{ministry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ministry(
    ministry_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.manage_hierarchy"))
):
    """
    Delete a ministry

    Requires fiscal_service.manage_hierarchy permission

    Will fail if the ministry has dependent sectors.
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    try:
        # Check if ministry exists
        existing = await repository.get_ministry_by_id(db, ministry_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ministry with ID {ministry_id} not found"
            )

        # Delete ministry
        deleted = await repository.delete_ministry(db, ministry_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete ministry"
            )

        logger.info(f"Admin {user_id} deleted ministry {ministry_id}")
        return None

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error deleting ministry {ministry_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting ministry: {str(e)}"
        )


# ============================================================================
# ADMIN: MINISTRY IMAGE MANAGEMENT
# ============================================================================

# Constants for ministry images
MINISTRY_IMAGE_FOLDER = "application-attachments/ministerios"
MINISTRY_IMAGE_MAX_SIZE = 5 * 1024 * 1024  # 5MB
MINISTRY_IMAGE_TARGET_SIZE = (800, 600)


class MinistryImageResponse(BaseModel):
    """Response model for ministry image operations"""
    success: bool
    url: Optional[str] = None
    message: Optional[str] = None


def resize_image_to_target(image_bytes: bytes, target_size: tuple = (800, 600)) -> bytes:
    """Resize image to target dimensions (800x600) with center crop"""
    img = Image.open(BytesIO(image_bytes))

    # Convert to RGB if necessary
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    # Calculate scaling to cover target dimensions
    target_width, target_height = target_size
    source_width, source_height = img.size

    source_aspect = source_width / source_height
    target_aspect = target_width / target_height

    if source_aspect > target_aspect:
        # Image is wider - scale by height, crop width
        new_height = target_height
        new_width = int(source_width * (target_height / source_height))
    else:
        # Image is taller - scale by width, crop height
        new_width = target_width
        new_height = int(source_height * (target_width / source_width))

    # Resize
    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Center crop
    left = (new_width - target_width) // 2
    top = (new_height - target_height) // 2
    right = left + target_width
    bottom = top + target_height
    img = img.crop((left, top, right, bottom))

    # Save to bytes
    output = BytesIO()
    img.save(output, format='JPEG', quality=85, optimize=True)
    return output.getvalue()


@router.post("/admin/ministries/{ministry_id}/image", response_model=MinistryImageResponse)
async def upload_ministry_image(
    ministry_id: int,
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.manage_hierarchy"))
):
    """
    Upload or replace ministry image

    - Accepts JPEG, PNG, WebP images
    - Auto-resizes to 800x600 pixels
    - Saves as {ministry_code}.jpg

    Requires fiscal_service.manage_hierarchy permission
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    try:
        # Lazy import to avoid module-level import errors
        from app.modules.documents.services.storage_service import firebase_storage_service

        # Get ministry to get the code
        ministry = await repository.get_ministry_by_id(db, ministry_id)
        if not ministry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ministry with ID {ministry_id} not found"
            )

        ministry_code = ministry.get("ministry_code")
        if not ministry_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ministry has no code"
            )

        # Validate file type
        content_type = file.content_type or ""
        if not content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File must be an image (JPEG, PNG, or WebP)"
            )

        # Read file content
        content = await file.read()

        # Validate file size
        if len(content) > MINISTRY_IMAGE_MAX_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Max size: {MINISTRY_IMAGE_MAX_SIZE / (1024*1024)}MB"
            )

        # Resize image to 800x600
        resized_content = resize_image_to_target(content, MINISTRY_IMAGE_TARGET_SIZE)

        # Initialize storage if needed
        if not firebase_storage_service._initialized:
            await firebase_storage_service.initialize()

        # Upload to Firebase Storage
        file_path = f"{MINISTRY_IMAGE_FOLDER}/{ministry_code}.jpg"
        blob = firebase_storage_service.bucket.blob(file_path)

        # Set metadata
        blob.metadata = {
            "uploadedBy": user_id,
            "uploadedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ministryId": str(ministry_id),
            "ministryCode": ministry_code,
        }

        # Upload
        blob.upload_from_string(
            resized_content,
            content_type="image/jpeg",
            timeout=300
        )

        # Generate signed URL (7 days - max allowed by GCS)
        from datetime import timedelta
        signed_url = firebase_storage_service.generate_signed_url(
            blob,
            expiration=timedelta(days=7),  # Max allowed by GCS
            method="GET"
        )

        logger.info(f"Admin {user_id} uploaded image for ministry {ministry_id} ({ministry_code})")

        return MinistryImageResponse(
            success=True,
            url=signed_url,
            message="Image uploaded successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading ministry image for {ministry_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading image: {str(e)}"
        )


@router.get("/admin/ministries/{ministry_id}/image", response_model=MinistryImageResponse)
async def get_ministry_image_url(
    ministry_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Get signed URL for ministry image

    Returns a URL valid for 24 hours
    """
    try:
        # Lazy import to avoid module-level import errors
        from app.modules.documents.services.storage_service import firebase_storage_service

        # Get ministry to get the code
        ministry = await repository.get_ministry_by_id(db, ministry_id)
        if not ministry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ministry with ID {ministry_id} not found"
            )

        ministry_code = ministry.get("ministry_code")
        if not ministry_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ministry has no code"
            )

        # Initialize storage if needed
        if not firebase_storage_service._initialized:
            await firebase_storage_service.initialize()

        # Check if image exists
        file_path = f"{MINISTRY_IMAGE_FOLDER}/{ministry_code}.jpg"
        blob = firebase_storage_service.bucket.blob(file_path)

        if not blob.exists():
            return MinistryImageResponse(
                success=False,
                url=None,
                message="Image not found"
            )

        # Generate signed URL (24 hours)
        from datetime import timedelta
        signed_url = firebase_storage_service.generate_signed_url(
            blob,
            expiration=timedelta(hours=24),
            method="GET"
        )

        return MinistryImageResponse(
            success=True,
            url=signed_url,
            message="Image URL generated"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ministry image URL for {ministry_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting image URL: {str(e)}"
        )


@router.get("/ministries/{ministry_id}/image", response_model=MinistryImageResponse)
async def get_ministry_image_url_public(
    ministry_id: int,
    db=Depends(get_database)
):
    """
    Get signed URL for ministry image (public endpoint)

    Returns a URL valid for 24 hours
    No authentication required
    """
    try:
        # Lazy import to avoid module-level import errors
        from app.modules.documents.services.storage_service import firebase_storage_service

        # Get ministry to get the code
        ministry = await repository.get_ministry_by_id(db, ministry_id)
        if not ministry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ministry with ID {ministry_id} not found"
            )

        ministry_code = ministry.get("ministry_code")
        if not ministry_code:
            return MinistryImageResponse(
                success=False,
                url=None,
                message="Ministry has no code"
            )

        # Initialize storage if needed
        if not firebase_storage_service._initialized:
            await firebase_storage_service.initialize()

        # Check if image exists
        file_path = f"{MINISTRY_IMAGE_FOLDER}/{ministry_code}.jpg"
        blob = firebase_storage_service.bucket.blob(file_path)

        if not blob.exists():
            return MinistryImageResponse(
                success=False,
                url=None,
                message="Image not found"
            )

        # Generate signed URL (24 hours)
        from datetime import timedelta
        signed_url = firebase_storage_service.generate_signed_url(
            blob,
            expiration=timedelta(hours=24),
            method="GET"
        )

        return MinistryImageResponse(
            success=True,
            url=signed_url,
            message="Image URL generated"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting public ministry image URL for {ministry_id}: {e}")
        return MinistryImageResponse(
            success=False,
            url=None,
            message="Error getting image"
        )


@router.delete("/admin/ministries/{ministry_id}/image", response_model=MinistryImageResponse)
async def delete_ministry_image(
    ministry_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.manage_hierarchy"))
):
    """
    Delete ministry image

    Requires fiscal_service.manage_hierarchy permission
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    try:
        # Lazy import to avoid module-level import errors
        from app.modules.documents.services.storage_service import firebase_storage_service

        # Get ministry to get the code
        ministry = await repository.get_ministry_by_id(db, ministry_id)
        if not ministry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ministry with ID {ministry_id} not found"
            )

        ministry_code = ministry.get("ministry_code")
        if not ministry_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ministry has no code"
            )

        # Initialize storage if needed
        if not firebase_storage_service._initialized:
            await firebase_storage_service.initialize()

        # Delete image
        file_path = f"{MINISTRY_IMAGE_FOLDER}/{ministry_code}.jpg"
        blob = firebase_storage_service.bucket.blob(file_path)

        if blob.exists():
            blob.delete()
            logger.info(f"Admin {user_id} deleted image for ministry {ministry_id} ({ministry_code})")
            return MinistryImageResponse(
                success=True,
                message="Image deleted successfully"
            )
        else:
            return MinistryImageResponse(
                success=True,
                message="Image was already deleted"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting ministry image for {ministry_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting image: {str(e)}"
        )


# ============================================================================
# ADMIN: SECTOR MANAGEMENT
# ============================================================================

@router.post("/admin/sectors", response_model=SectorResponse, status_code=status.HTTP_201_CREATED)
async def create_sector(
    data: SectorCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.manage_hierarchy"))
):
    """
    Create a new sector

    Requires fiscal_service.manage_hierarchy permission

    - **sector_code**: Unique sector code (max 10 chars)
    - **ministry_id**: Parent ministry ID (required)
    - **name_es**: Sector name in Spanish
    - **description_es**: Optional description
    - **display_order**: Display order for sorting (default 0)
    - **icon**: Optional icon identifier
    - **color**: Optional hex color code (#RRGGBB)
    - **is_active**: Whether sector is active (default True)
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    try:
        # Check if sector code already exists
        existing = await repository.get_sector_by_code(db, data.sector_code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Sector with code '{data.sector_code}' already exists"
            )

        # Create sector
        sector_data = data.dict()
        result = await repository.create_sector(db, sector_data)

        logger.info(f"Admin {user_id} created sector {result['id']} ({data.sector_code})")
        return SectorResponse(**result)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating sector: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating sector: {str(e)}"
        )


@router.get("/admin/sectors/{sector_id}", response_model=SectorResponse)
async def get_sector_by_id(
    sector_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.manage_hierarchy"))
):
    """Get sector by ID - Requires fiscal_service.manage_hierarchy permission"""
    sector = await repository.get_sector_by_id(db, sector_id)
    if not sector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sector with ID {sector_id} not found"
        )
    return SectorResponse(**sector)


@router.put("/admin/sectors/{sector_id}", response_model=SectorResponse)
async def update_sector(
    sector_id: int,
    data: SectorUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.manage_hierarchy"))
):
    """
    Update a sector

    Requires fiscal_service.manage_hierarchy permission

    All fields are optional. Only provided fields will be updated.
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    try:
        # Check if sector exists
        existing = await repository.get_sector_by_id(db, sector_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sector with ID {sector_id} not found"
            )

        # Update sector
        update_data = data.dict(exclude_unset=True)
        if not update_data:
            return SectorResponse(**existing)

        result = await repository.update_sector(db, sector_id, update_data)

        logger.info(f"Admin {user_id} updated sector {sector_id}")
        return SectorResponse(**result)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating sector {sector_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating sector: {str(e)}"
        )


@router.delete("/admin/sectors/{sector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sector(
    sector_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.manage_hierarchy"))
):
    """
    Delete a sector

    Requires fiscal_service.manage_hierarchy permission

    Will fail if the sector has dependent categories.
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    try:
        # Check if sector exists
        existing = await repository.get_sector_by_id(db, sector_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sector with ID {sector_id} not found"
            )

        # Delete sector
        deleted = await repository.delete_sector(db, sector_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete sector"
            )

        logger.info(f"Admin {user_id} deleted sector {sector_id}")
        return None

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error deleting sector {sector_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting sector: {str(e)}"
        )


# ============================================================================
# ADMIN: CATEGORY MANAGEMENT
# ============================================================================

@router.post("/admin/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.manage_hierarchy"))
):
    """
    Create a new category

    Requires fiscal_service.manage_hierarchy permission

    - **category_code**: Unique category code (max 10 chars)
    - **sector_id**: Optional parent sector ID
    - **ministry_id**: Optional parent ministry ID
    - **service_type**: Optional service type classification
    - **name_es**: Category name in Spanish
    - **description_es**: Optional description
    - **display_order**: Display order for sorting (default 0)
    - **icon**: Optional icon identifier
    - **color**: Optional hex color code (#RRGGBB)
    - **is_active**: Whether category is active (default True)
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    try:
        # Check if category code already exists
        existing = await repository.get_category_by_code(db, data.category_code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Category with code '{data.category_code}' already exists"
            )

        # Create category
        category_data = data.dict()
        result = await repository.create_category(db, category_data)

        logger.info(f"Admin {user_id} created category {result['id']} ({data.category_code})")
        return CategoryResponse(**result)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating category: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating category: {str(e)}"
        )


@router.get("/admin/categories/{category_id}", response_model=CategoryResponse)
async def get_category_by_id(
    category_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.manage_hierarchy"))
):
    """Get category by ID - Requires fiscal_service.manage_hierarchy permission"""
    category = await repository.get_category_by_id(db, category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with ID {category_id} not found"
        )
    return CategoryResponse(**category)


@router.put("/admin/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    data: CategoryUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.manage_hierarchy"))
):
    """
    Update a category

    Requires fiscal_service.manage_hierarchy permission

    All fields are optional. Only provided fields will be updated.
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    try:
        # Check if category exists
        existing = await repository.get_category_by_id(db, category_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category with ID {category_id} not found"
            )

        # Update category
        update_data = data.dict(exclude_unset=True)
        if not update_data:
            return CategoryResponse(**existing)

        result = await repository.update_category(db, category_id, update_data)

        logger.info(f"Admin {user_id} updated category {category_id}")
        return CategoryResponse(**result)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating category {category_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating category: {str(e)}"
        )


@router.delete("/admin/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.manage_hierarchy"))
):
    """
    Delete a category

    Requires fiscal_service.manage_hierarchy permission

    Will fail if the category has dependent fiscal services.
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    try:
        # Check if category exists
        existing = await repository.get_category_by_id(db, category_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category with ID {category_id} not found"
            )

        # Delete category
        deleted = await repository.delete_category(db, category_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete category"
            )

        logger.info(f"Admin {user_id} deleted category {category_id}")
        return None

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error deleting category {category_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting category: {str(e)}"
        )


# ============================================================================
# ADMIN: FISCAL SERVICE MANAGEMENT
# ============================================================================

@router.post("/admin/services", response_model=FiscalServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_fiscal_service(
    service: FiscalServiceCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.create"))
):
    """Create new fiscal service - Requires fiscal_service.create permission"""
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    # Check if code already exists
    existing = await repository.get_by_code(db, service.service_code)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Service code already exists")

    result = await repository.create(db, service)
    # Refresh materialized view + invalidate cache
    try:
        await db.execute("SELECT refresh_fiscal_services_catalog()")
    except Exception:
        logger.warning("mv_fiscal_services_catalog refresh skipped (view may not exist yet)")
    await invalidate_services_cache()
    # Auto-enqueue Gemini enrichment (non-blocking)
    try:
        from app.modules.enrichment.services.enrichment_service import EnrichmentService
        await EnrichmentService.auto_enqueue(
            db, result['id'], result.get('description_es'), result.get('description_source')
        )
    except Exception as enrich_err:
        logger.warning(f"Enrichment enqueue failed (non-blocking): {enrich_err}")
    logger.info(f"Admin {user_id} created fiscal service {result['id']}")
    return FiscalServiceResponse(**result)


@router.put("/admin/services/{service_id}", response_model=FiscalServiceResponse)
async def update_fiscal_service(
    service_id: int,
    update_data: FiscalServiceUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.update"))
):
    """Update fiscal service - Requires fiscal_service.update permission"""
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    updated = await repository.update(db, service_id, update_data, updated_by=user_id)
    if not updated:
        raise TranslatedException(ErrorCode.SERVICE_NOT_FOUND)

    # Refresh materialized view + invalidate cache
    try:
        await db.execute("SELECT refresh_fiscal_services_catalog()")
    except Exception:
        logger.warning("mv_fiscal_services_catalog refresh skipped (view may not exist yet)")
    await invalidate_services_cache()
    # Auto-enqueue Gemini enrichment (non-blocking)
    try:
        from app.modules.enrichment.services.enrichment_service import EnrichmentService
        await EnrichmentService.auto_enqueue(
            db, service_id, updated.get('description_es'), updated.get('description_source')
        )
    except Exception as enrich_err:
        logger.warning(f"Enrichment enqueue failed (non-blocking): {enrich_err}")
    logger.info(f"Admin {user_id} updated fiscal service {service_id}")
    return FiscalServiceResponse(**updated)


@router.delete("/admin/services/{service_id}", status_code=status.HTTP_200_OK)
async def delete_fiscal_service(
    service_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.delete"))
):
    """Delete fiscal service - Requires fiscal_service.delete permission"""
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    deleted = await repository.delete(db, service_id)
    if not deleted:
        raise TranslatedException(ErrorCode.SERVICE_NOT_FOUND)

    # Refresh materialized view + invalidate cache
    try:
        await db.execute("SELECT refresh_fiscal_services_catalog()")
    except Exception:
        logger.warning("mv_fiscal_services_catalog refresh skipped (view may not exist yet)")
    await invalidate_services_cache()
    logger.info(f"Admin {user_id} deleted fiscal service {service_id}")
    return {"message": "Fiscal service deleted successfully"}


# ========== STATISTICS & ADMIN UTILITIES ==========

@router.get("/admin/stats", response_model=FiscalServiceStats)
async def get_fiscal_services_statistics(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.view_stats"))
):
    """
    Get comprehensive fiscal services statistics

    Requires fiscal_service.view_stats permission

    **Migrated from legacy /api/v1/taxes/stats/overview**

    Returns:
        - Total services count
        - Active/inactive breakdown
        - Services by type, category, ministry, status
        - Average processing time
        - Most used services (top 10)
        - Total calculations and views
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    try:
        stats = await repository.get_statistics(db)

        logger.info(f"Admin {user_id} retrieved fiscal services statistics")
        return FiscalServiceStats(**stats)

    except Exception as e:
        logger.error(f"Error getting fiscal services statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving statistics: {str(e)}"
        )


@router.get("/admin/export/csv")
async def export_fiscal_services_csv(
    category_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    ministry_id: Optional[int] = Query(None),
    sector_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.view_stats"))
):
    """Export fiscal services as CSV (max 5000 rows). Requires fiscal_service.view_stats permission."""
    services, total = await repository.list(
        db, category_id=category_id, status=status_filter,
        ministry_id=ministry_id, sector_id=sector_id, search=search,
        limit=5000, offset=0,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "service_code", "name_es", "service_type", "calculation_method",
        "status", "tasa_expedicion", "tasa_renovacion",
        "processing_time_days", "category_name", "sector_name", "ministry_name",
        "view_count", "calculation_count",
    ])
    for s in services:
        writer.writerow([
            s.get("service_code", ""), s.get("name_es", ""),
            s.get("service_type", ""), s.get("calculation_method", ""),
            s.get("status", ""), s.get("tasa_expedicion", 0), s.get("tasa_renovacion", 0),
            s.get("processing_time_days", ""), s.get("category_name", ""),
            s.get("sector_name", ""), s.get("ministry_name", ""),
            s.get("view_count", 0), s.get("calculation_count", 0),
        ])

    output.seek(0)
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")
    logger.info(f"Admin {user_id} exported {len(services)} fiscal services as CSV")

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=fiscal_services_export_{total}.csv"},
    )


@router.post("/admin/bulk/import", status_code=status.HTTP_201_CREATED)
async def bulk_import_fiscal_services(
    services: List[FiscalServiceCreate],
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.bulk_import"))
):
    """
    Bulk import fiscal services

    Requires fiscal_service.bulk_import permission

    **Migrated from legacy /api/v1/taxes/bulk/import**

    Limits:
        - Maximum 100 services per request

    Returns:
        - successful_imports: Number of successfully imported services
        - failed_imports: Number of failed imports
        - Details of failed services
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    if len(services) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bulk import limited to 100 services per request"
        )

    try:
        results = await repository.bulk_create(db, services, user_id)

        logger.info(
            f"Admin {user_id} bulk imported {results['successful']}/{len(services)} services"
        )

        return {
            "success": True,
            "total_processed": len(services),
            "successful_imports": results["successful"],
            "failed_imports": results["failed"],
            "failed_services": results.get("errors", []),
            "message": f"Successfully imported {results['successful']}/{len(services)} services"
        }

    except Exception as e:
        logger.error(f"Error in bulk import: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing bulk import: {str(e)}"
        )


@router.post("/admin/bulk/update-status")
async def bulk_update_service_status(
    service_ids: List[str],
    new_status: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.bulk_update"))
):
    """
    Bulk update service status

    Requires fiscal_service.bulk_update permission

    **Migrated from legacy /api/v1/taxes/bulk/update-status**

    Limits:
        - Maximum 50 services per request

    Args:
        service_ids: List of service IDs to update
        new_status: New status (active, inactive, deprecated, under_review)

    Returns:
        - updated_count: Number of successfully updated services
        - failed_updates: Number of failed updates
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    if len(service_ids) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bulk status update limited to 50 services per request"
        )

    # Validate status
    from app.modules.fiscal_services.models import ServiceStatusEnum
    try:
        status_enum = ServiceStatusEnum(new_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {new_status}. Valid values: {[s.value for s in ServiceStatusEnum]}"
        )

    try:
        results = await repository.bulk_update_status(db, service_ids, status_enum, user_id)

        logger.info(
            f"Admin {user_id} bulk updated status for {results['updated']}/{len(service_ids)} services to {new_status}"
        )

        return {
            "success": True,
            "total_requested": len(service_ids),
            "updated_count": results["updated"],
            "failed_updates": results["failed"],
            "new_status": new_status,
            "message": f"Successfully updated {results['updated']}/{len(service_ids)} services"
        }

    except Exception as e:
        logger.error(f"Error in bulk status update: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing bulk update: {str(e)}"
        )


# ============================================================================
# SERVICE DOCUMENT ASSIGNMENTS
# ============================================================================

@router.get("/{service_id}/documents", response_model=List[ServiceDocumentAssignmentResponse])
async def list_service_documents(
    service_id: int,
    language: str = Query("es", pattern="^(es|fr|en)$", description="Language for translations"),
    db=Depends(get_database),
):
    """
    List all document assignments for a fiscal service

    Returns documents with translated names based on the language parameter.
    """
    try:
        # Verify service exists
        service = await repository.get_by_id(db, service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service with ID {service_id} not found"
            )

        documents = await repository.list_document_assignments(db, service_id, language)
        return [ServiceDocumentAssignmentResponse(**d) for d in documents]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing documents for service {service_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing documents: {str(e)}"
        )


@router.post("/{service_id}/documents", response_model=ServiceDocumentAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_document_to_service(
    service_id: int,
    data: ServiceDocumentAssignmentCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.update"))
):
    """
    Assign a document template to a fiscal service

    Requires fiscal_service.update permission

    - **document_template_id**: ID of the document template to assign
    - **is_required_expedition**: Whether document is required for initial issuance
    - **is_required_renewal**: Whether document is required for renewal
    - **display_order**: Order in which document appears in the list
    - **custom_notes**: Optional custom notes for this assignment
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    try:
        # Verify service exists
        service = await repository.get_by_id(db, service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service with ID {service_id} not found"
            )

        # Ensure service_id matches
        if data.fiscal_service_id != service_id:
            data.fiscal_service_id = service_id

        # Note: assigned_by is integer column but user_id is UUID, passing None for now
        assignment = await repository.create_document_assignment(db, data.model_dump(), None)
        logger.info(f"User {user_id} assigned document {data.document_template_id} to service {service_id}")
        return ServiceDocumentAssignmentResponse(**assignment)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        if "unique constraint" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This document is already assigned to this service"
            )
        logger.error(f"Error assigning document to service {service_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error assigning document: {str(e)}"
        )


@router.delete("/{service_id}/documents/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_document_from_service(
    service_id: int,
    assignment_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.update"))
):
    """
    Remove a document assignment from a fiscal service

    Requires fiscal_service.update permission
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    try:
        deleted = await repository.delete_document_assignment(db, service_id, assignment_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document assignment {assignment_id} not found for service {service_id}"
            )

        logger.info(f"User {user_id} removed document assignment {assignment_id} from service {service_id}")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing document assignment {assignment_id} from service {service_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error removing document assignment: {str(e)}"
        )


# ============================================================================
# SERVICE PROCEDURE ASSIGNMENTS
# ============================================================================

@router.get("/{service_id}/procedures", response_model=List[ServiceProcedureAssignmentResponse])
async def list_service_procedures(
    service_id: int,
    language: str = Query("es", pattern="^(es|fr|en)$", description="Language for translations"),
    db=Depends(get_database),
):
    """
    List all procedure assignments for a fiscal service

    Returns procedures with translated names based on the language parameter.
    """
    try:
        # Verify service exists
        service = await repository.get_by_id(db, service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service with ID {service_id} not found"
            )

        procedures = await repository.list_procedure_assignments(db, service_id, language)
        return [ServiceProcedureAssignmentResponse(**p) for p in procedures]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing procedures for service {service_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing procedures: {str(e)}"
        )


@router.post("/{service_id}/procedures", response_model=ServiceProcedureAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_procedure_to_service(
    service_id: int,
    data: ServiceProcedureAssignmentCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.update"))
):
    """
    Assign a procedure template to a fiscal service

    Requires fiscal_service.update permission

    - **template_id**: ID of the procedure template to assign
    - **applies_to**: When procedure applies: 'expedition', 'renewal', or 'both'
    - **display_order**: Order in which procedure appears in the list
    - **custom_notes**: Optional custom notes for this assignment
    - **override_steps**: Optional JSONB to override specific steps for this service
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    try:
        # Verify service exists
        service = await repository.get_by_id(db, service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service with ID {service_id} not found"
            )

        # Ensure service_id matches
        if data.fiscal_service_id != service_id:
            data.fiscal_service_id = service_id

        # Note: assigned_by is integer column but user_id is UUID, passing None for now
        assignment = await repository.create_procedure_assignment(db, data.model_dump(), None)
        logger.info(f"User {user_id} assigned procedure {data.template_id} to service {service_id}")
        return ServiceProcedureAssignmentResponse(**assignment)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        if "unique constraint" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This procedure is already assigned to this service"
            )
        logger.error(f"Error assigning procedure to service {service_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error assigning procedure: {str(e)}"
        )


@router.delete("/{service_id}/procedures/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_procedure_from_service(
    service_id: int,
    assignment_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("fiscal_service.update"))
):
    """
    Remove a procedure assignment from a fiscal service

    Requires fiscal_service.update permission
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    try:
        deleted = await repository.delete_procedure_assignment(db, service_id, assignment_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Procedure assignment {assignment_id} not found for service {service_id}"
            )

        logger.info(f"User {user_id} removed procedure assignment {assignment_id} from service {service_id}")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing procedure assignment {assignment_id} from service {service_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error removing procedure assignment: {str(e)}"
        )


