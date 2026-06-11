"""Entity Locations Module - CRUD management for entity office locations."""

from .models.entity_location import (
    EntityLocation,
    EntityLocationCreate,
    EntityLocationUpdate,
    EntityLocationResponse,
    EntityLocationListResponse,
    OperatingHours,
    DayHours,
)
from .repositories.entity_location_repository import EntityLocationRepository
from .services.entity_location_service import EntityLocationService
from .api.entity_location_routes import router as entity_location_router

__all__ = [
    # Models
    "EntityLocation",
    "EntityLocationCreate",
    "EntityLocationUpdate",
    "EntityLocationResponse",
    "EntityLocationListResponse",
    "OperatingHours",
    "DayHours",
    # Repository
    "EntityLocationRepository",
    # Service
    "EntityLocationService",
    # Router
    "entity_location_router",
]
