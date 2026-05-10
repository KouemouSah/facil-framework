"""
Homepage Module - Pydantic Models
Defines request/response models for homepage statistics and category directory
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class HomepageStats(BaseModel):
    """Dynamic homepage statistics calculated from database"""
    total_services: int = Field(..., description="Total number of active fiscal services")
    total_ministries: int = Field(..., description="Total number of active ministries")
    total_categories: int = Field(..., description="Total number of active categories")
    total_sectors: int = Field(..., description="Total number of active sectors")
    last_updated: str = Field(..., description="ISO timestamp of when stats were calculated")


class CategoryWithServices(BaseModel):
    """Category with service count and translations"""
    id: int = Field(..., description="Category ID")
    category_code: str = Field(..., description="Category code")
    name: str = Field(..., description="Category name (translated)")
    description: Optional[str] = Field(None, description="Category description (translated)")
    icon: Optional[str] = Field(None, description="Category icon")
    color: Optional[str] = Field(None, description="Category color")
    service_count: int = Field(..., description="Number of active services in this category")
    ministry_name: Optional[str] = Field(None, description="Associated ministry name")
    sector_name: Optional[str] = Field(None, description="Associated sector name")


class CategoryDirectory(BaseModel):
    """Category directory response"""
    total_categories: int = Field(..., description="Total number of categories")
    total_services: int = Field(..., description="Total number of services across all categories")
    categories: List[CategoryWithServices] = Field(..., description="List of categories with service counts")
    last_updated: str = Field(..., description="ISO timestamp")


class ServiceByType(BaseModel):
    """Service details for services-by-type endpoint"""
    id: int = Field(..., description="Service ID")
    service_code: str = Field(..., description="Service code")
    name_es: str = Field(..., description="Service name (Spanish)")
    name_fr: Optional[str] = Field(None, description="Service name (French)")
    name_en: Optional[str] = Field(None, description="Service name (English)")
    tasa_expedicion: Optional[float] = Field(None, description="Expedition fee in GNF")


class ServicesByTypeResponse(BaseModel):
    """Response for services grouped by type and letter"""
    type: str = Field(..., description="Service type filter")
    letter: Optional[str] = Field(None, description="First letter filter (A-Z)")
    services: List[ServiceByType] = Field(..., description="List of services")
    total: int = Field(..., description="Total services for this type/letter")
    has_more: bool = Field(..., description="Whether there are more services beyond limit")


# ============================================================================
# MINISTRY MODELS
# ============================================================================

class MinistryItem(BaseModel):
    """Ministry item with service count"""
    id: int = Field(..., description="Ministry ID")
    ministry_code: str = Field(..., description="Ministry code")
    name: str = Field(..., description="Ministry name (translated)")
    description: Optional[str] = Field(None, description="Ministry description (translated)")
    icon: Optional[str] = Field(None, description="Ministry icon")
    color: Optional[str] = Field(None, description="Ministry color")
    is_active: bool = Field(True, description="Whether ministry is active")
    service_count: int = Field(0, description="Number of services under this ministry")
    sector_count: int = Field(0, description="Number of sectors under this ministry")
    category_count: int = Field(0, description="Number of categories under this ministry")


class MinistryDirectory(BaseModel):
    """Ministry directory response"""
    total_ministries: int = Field(..., description="Total number of ministries")
    total_services: int = Field(..., description="Total number of services across all ministries")
    ministries: List[MinistryItem] = Field(..., description="List of ministries with service counts")


class MinistryServiceItem(BaseModel):
    """Service item for ministry details"""
    id: int = Field(..., description="Service ID")
    service_code: str = Field(..., description="Service code")
    name: str = Field(..., description="Service name (translated)")
    description: Optional[str] = Field(None, description="Service description (translated)")
    expedition_price: float = Field(0, description="Expedition price")
    renewal_price: float = Field(0, description="Renewal price")
    category_name: Optional[str] = Field(None, description="Category name")
    sector_name: Optional[str] = Field(None, description="Sector name")
    service_type: str = Field(..., description="Service type")


class MinistryDetails(BaseModel):
    """Complete ministry details with services"""
    id: int = Field(..., description="Ministry ID")
    ministry_code: str = Field(..., description="Ministry code")
    name: str = Field(..., description="Ministry name (translated)")
    description: Optional[str] = Field(None, description="Ministry description (translated)")
    icon: Optional[str] = Field(None, description="Ministry icon")
    color: Optional[str] = Field(None, description="Ministry color")
    is_active: bool = Field(True, description="Whether ministry is active")
    service_count: int = Field(0, description="Total services")
    sector_count: int = Field(0, description="Total sectors")
    category_count: int = Field(0, description="Total categories")
    services: List[MinistryServiceItem] = Field([], description="Services list (paginated)")
    total_pages: int = Field(1, description="Total pages")
    current_page: int = Field(1, description="Current page")


# ============================================================================
# SEARCH MODELS
# ============================================================================

class SearchRequest(BaseModel):
    """Search request payload"""
    q: Optional[str] = Field(None, description="Search query")
    category_id: Optional[int] = Field(None, description="Filter by category ID")
    category_code: Optional[str] = Field(None, description="Filter by category code")
    ministry_id: Optional[int] = Field(None, description="Filter by ministry ID")
    service_type: Optional[str] = Field(None, description="Filter by service type")
    min_price: Optional[float] = Field(None, description="Minimum price filter")
    max_price: Optional[float] = Field(None, description="Maximum price filter")
    calculation_methods: Optional[List[str]] = Field(None, description="Filter by calculation methods (e.g., ['percentage_based', 'formula_based'])")
    sort_by: str = Field("relevance", description="Sort by: relevance, name, price")
    sort_order: str = Field("asc", description="Sort order: asc, desc")
    page: int = Field(1, ge=1, description="Page number")
    limit: int = Field(20, ge=1, le=100, description="Results per page")
    include_facets: bool = Field(True, description="Include facets in response")
    language: str = Field("es", description="Language code")


class SearchResultItem(BaseModel):
    """Single search result"""
    id: int
    name: str
    description: Optional[str] = None
    category_name: str
    ministry_name: Optional[str] = None
    sector_name: Optional[str] = None
    service_type: str
    expedition_price: float = 0
    renewal_price: float = 0
    processing_time_days: int = 30
    status: str = "active"
    calculation_method: str = "fixed_expedition"


class FacetItem(BaseModel):
    """Facet item for filtering"""
    id: Optional[int] = None
    code: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    count: int = 0


class SearchFacets(BaseModel):
    """Search facets"""
    categories: List[FacetItem] = []
    ministries: List[FacetItem] = []
    service_types: List[FacetItem] = []
    price_ranges: List[FacetItem] = []


class BundleResultItem(BaseModel):
    """Bundle search result (commercial license package)"""
    id: str
    name: str
    description: Optional[str] = None
    bundle_code: str
    commerce_type: str
    item_count: int = 0


class SearchResponse(BaseModel):
    """Search response"""
    success: bool = True
    query: str = ""
    total_results: int = 0
    page: int = 1
    limit: int = 20
    total_pages: int = 0
    results: List[SearchResultItem] = []
    bundles: List[BundleResultItem] = []
    facets: Optional[SearchFacets] = None
    suggestions: List[str] = []
    execution_time_ms: float = 0
    cached: bool = False


# ============================================================================
# SEMANTIC SEARCH MODELS
# ============================================================================

class SemanticResultItem(BaseModel):
    """Single semantic search result with similarity score"""
    id: int
    name: str
    description: Optional[str] = None
    category_name: str = ""
    ministry_name: Optional[str] = None
    service_type: str
    expedition_price: float = 0
    renewal_price: float = 0
    similarity: float = Field(0, description="Cosine similarity score (0-1)")


class SemanticSearchResponse(BaseModel):
    """Semantic search response"""
    success: bool = True
    query: str = ""
    results: List[SemanticResultItem] = []
    total_results: int = 0
    execution_time_ms: float = 0
    embedding_model: str = ""
    cached: bool = False
