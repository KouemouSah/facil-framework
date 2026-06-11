"""
Search Models for Fiscal Services
Pydantic models for the /search-db endpoint with facets support
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class SortByEnum(str, Enum):
    """Sort options for search results"""
    relevance = "relevance"
    name = "name"
    price = "price"
    popular = "popular"


class SortOrderEnum(str, Enum):
    """Sort order"""
    asc = "asc"
    desc = "desc"


# ===================================================================================================
# REQUEST MODELS
# ===================================================================================================

class SearchDBRequest(BaseModel):
    """Request model for /search-db endpoint"""
    # Search text
    q: Optional[str] = Field(None, description="Search query text")

    # Filters
    category_id: Optional[int] = Field(None, description="Filter by category ID")
    category_code: Optional[str] = Field(None, description="Filter by category code")
    ministry_id: Optional[int] = Field(None, description="Filter by ministry ID")
    service_type: Optional[str] = Field(None, description="Filter by service type")

    # Price filters
    min_price: Optional[float] = Field(None, ge=0, description="Minimum price (any)")
    max_price: Optional[float] = Field(None, ge=0, description="Maximum price (any)")
    min_expedition_price: Optional[float] = Field(None, ge=0, description="Minimum expedition price")
    max_expedition_price: Optional[float] = Field(None, ge=0, description="Maximum expedition price")
    min_renewal_price: Optional[float] = Field(None, ge=0, description="Minimum renewal price")
    max_renewal_price: Optional[float] = Field(None, ge=0, description="Maximum renewal price")

    # Sorting
    sort_by: SortByEnum = Field(SortByEnum.relevance, description="Sort field")
    sort_order: SortOrderEnum = Field(SortOrderEnum.asc, description="Sort order")

    # Pagination
    page: int = Field(1, ge=1, description="Page number")
    limit: int = Field(20, ge=1, le=100, description="Results per page")

    # Options
    include_facets: bool = Field(True, description="Include facets in response")
    language: str = Field("es", pattern="^(es|fr|en)$", description="Language for translations")


# ===================================================================================================
# RESPONSE MODELS
# ===================================================================================================

class ServiceResultItem(BaseModel):
    """Single service result item"""
    id: int
    name: str
    description: Optional[str] = None
    category_name: str
    ministry_name: Optional[str] = None
    sector_name: Optional[str] = None
    service_type: str
    expedition_price: float
    renewal_price: float
    processing_time_days: int
    status: str


class FacetItem(BaseModel):
    """Single facet item"""
    id: Optional[int] = None
    code: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    range: Optional[str] = None
    count: int
    min: Optional[float] = None
    max: Optional[float] = None


class SearchFacets(BaseModel):
    """Facets for filtering"""
    categories: List[FacetItem] = []
    ministries: List[FacetItem] = []
    service_types: List[FacetItem] = []
    price_ranges: List[FacetItem] = []


class SearchDBResponse(BaseModel):
    """Response model for /search-db endpoint"""
    success: bool = True
    query: str = ""
    total_results: int
    page: int
    limit: int
    total_pages: int
    results: List[ServiceResultItem]
    facets: Optional[SearchFacets] = None
    suggestions: List[str] = []
    execution_time_ms: float = 0
    cached: bool = False
