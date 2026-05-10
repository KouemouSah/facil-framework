"""
Admin Routes for Service Requests Configuration.

RESTful endpoints for administrators to manage:
- Workflows (CRUD)
- Workflow Document Requirements
- Tariff Configurations
- Appointment Settings
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body, BackgroundTasks, Request
from app.core.errors import TranslatedException, ErrorCode
from typing import List, Mapping, Optional, Dict, Any
from enum import Enum
import asyncpg
import json
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

logger = logging.getLogger(__name__)

from pydantic import BaseModel, Field, field_validator

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required, permission_required_any
from app.core.events import EventBus, EventType
from app.modules.treasury.errors import (
    TreasuryError,
    TreasuryErrorCode,
    payment_not_found,
    no_agent_profile,
    anomaly_not_found,
    export_not_found,
    comment_required,
)


router = APIRouter(
    prefix="/admin/service-requests",
    tags=["Admin - Service Requests Configuration"]
)

def _parse_config(config_value):
    """Parse config JSONB field - handles both string and dict."""
    if config_value is None:
        return {}
    if isinstance(config_value, dict):
        return config_value
    if isinstance(config_value, str):
        try:
            return json.loads(config_value)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


async def _refresh_generic_cache(db: asyncpg.Connection, workflow_code: str) -> None:
    """Refresh generic workflow cache after config changes (documents, tariffs, etc.).

    No-op for predefined workflows or inactive generic workflows.
    """
    row = await db.fetchrow(
        "SELECT is_generic, is_active FROM workflows WHERE code = $1",
        workflow_code
    )
    if row and row["is_generic"] and row["is_active"]:
        try:
            from ..workflows.generic_workflow import load_generic_workflow
            from ..services.workflow_engine import workflow_engine
            wf = await load_generic_workflow(db, workflow_code)
            workflow_engine.register_generic(workflow_code, wf)
        except Exception as e:
            logger.warning(f"Failed to refresh generic cache for {workflow_code}: {e}")


# ═══════════════════════════════════════════════════════════════
# PYDANTIC MODELS - Aligned with DATABASE_SCHEMA_REFERENCE.md
# ═══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────
# WORKFLOWS (table: workflows - migration 028)
# ─────────────────────────────────────────────────────────────────

class WorkflowCreate(BaseModel):
    """Create a new workflow configuration - matches DB schema"""
    code: str = Field(..., pattern=r'^[A-Z][A-Z0-9_]+$', max_length=100)
    name_es: str = Field(..., max_length=255)
    description_es: Optional[str] = None
    category: str = Field(..., max_length=50)
    entity_code: str = Field(..., max_length=50)
    workflow_type: str = Field(default="standard", pattern="^(standard|direct_payment|multi_phase)$")
    requires_agent_validation: bool = True
    requires_appointment: bool = False
    is_generic: bool = True
    appointment_delay_days: Optional[int] = Field(None, ge=0, le=90)
    appointment_entity_code: Optional[str] = Field(None, max_length=50)
    sla_hours: int = Field(default=48, ge=1, le=720)
    max_processing_days: Optional[int] = Field(None, ge=1, le=365)
    display_order: int = Field(default=0, ge=0)
    icon: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, max_length=20)
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    is_active: bool = True
    # Hierarchical grouping fields (migration 049)
    parent_workflow_code: Optional[str] = Field(None, max_length=50, description="Parent workflow for UI grouping")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags for sub-categorization")
    is_parent: bool = Field(default=False, description="True = category header workflow")


class WorkflowUpdate(BaseModel):
    """Update workflow configuration"""
    name_es: Optional[str] = Field(None, max_length=255)
    description_es: Optional[str] = None
    workflow_type: Optional[str] = Field(None, pattern="^(standard|direct_payment|multi_phase)$")
    requires_agent_validation: Optional[bool] = None
    requires_appointment: Optional[bool] = None
    appointment_delay_days: Optional[int] = Field(None, ge=0, le=90)
    appointment_entity_code: Optional[str] = Field(None, max_length=50)
    sla_hours: Optional[int] = Field(None, ge=1, le=720)
    max_processing_days: Optional[int] = Field(None, ge=1, le=365)
    display_order: Optional[int] = Field(None, ge=0)
    icon: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, max_length=20)
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    # Hierarchical grouping fields (migration 049)
    parent_workflow_code: Optional[str] = Field(None, max_length=50)
    tags: Optional[List[str]] = None
    is_parent: Optional[bool] = None


class WorkflowSourceType(str, Enum):
    """
    Type de source du workflow.
    - predefined: Workflow avec classe Python hardcodée (ex: PasaporteWorkflow)
    - dynamic: Workflow créé en BD, utilise GenericWorkflow
    """
    PREDEFINED = "predefined"
    DYNAMIC = "dynamic"


class WorkflowResponse(BaseModel):
    """Workflow response - all DB fields"""
    code: str
    name_es: str
    description_es: Optional[str]
    category: str
    entity_code: str
    workflow_type: str
    requires_agent_validation: bool
    requires_appointment: bool
    is_generic: bool
    appointment_delay_days: Optional[int]
    appointment_entity_code: Optional[str]
    sla_hours: int
    max_processing_days: Optional[int]
    display_order: int
    icon: Optional[str]
    color: Optional[str]
    config: Optional[Dict[str, Any]]
    is_active: bool
    # Hierarchical grouping fields (migration 049)
    parent_workflow_code: Optional[str] = None
    tags: List[str] = []
    is_parent: bool = False
    # Computed fields (not in DB)
    documents_count: Optional[int] = None
    tariffs_count: Optional[int] = None
    # Source type: predefined (Python class) or dynamic (DB only)
    source_type: WorkflowSourceType = WorkflowSourceType.PREDEFINED

    @classmethod
    def from_row(cls, row: dict, documents_count: int = 0, tariffs_count: int = 0) -> "WorkflowResponse":
        """Create WorkflowResponse from DB row with computed source_type"""
        # Parse tags from JSONB (can be list or string)
        tags_value = row.get('tags')
        if isinstance(tags_value, list):
            tags = tags_value
        elif isinstance(tags_value, str):
            import json
            try:
                tags = json.loads(tags_value)
            except (json.JSONDecodeError, TypeError):
                tags = []
        else:
            tags = []

        return cls(
            code=row['code'],
            name_es=row['name_es'],
            description_es=row['description_es'],
            category=row['category'],
            entity_code=row['entity_code'],
            workflow_type=row['workflow_type'],
            requires_agent_validation=row['requires_agent_validation'],
            requires_appointment=row['requires_appointment'],
            is_generic=row['is_generic'],
            appointment_delay_days=row['appointment_delay_days'],
            appointment_entity_code=row['appointment_entity_code'],
            sla_hours=row['sla_hours'],
            max_processing_days=row['max_processing_days'],
            display_order=row['display_order'] or 0,
            icon=row['icon'],
            color=row['color'],
            config=_parse_config(row.get('config')),
            is_active=row['is_active'],
            parent_workflow_code=row.get('parent_workflow_code'),
            tags=tags,
            is_parent=row.get('is_parent', False) or False,
            documents_count=documents_count,
            tariffs_count=tariffs_count,
            source_type=WorkflowSourceType.DYNAMIC if row['is_generic'] else WorkflowSourceType.PREDEFINED,
        )


# ─────────────────────────────────────────────────────────────────
# WORKFLOW_DOCUMENT_REQUIREMENTS (table: workflow_document_requirements)
# ─────────────────────────────────────────────────────────────────

from enum import Enum

class DocumentConditionType(str, Enum):
    """
    Document condition type enum - matches DB enum document_condition_type_enum.
    See DATABASE_SCHEMA_REFERENCE.md for full list.
    """
    ALWAYS = "always"
    AGE_LESS_THAN = "age_less_than"
    AGE_GREATER_THAN = "age_greater_than"
    IS_RENEWAL = "is_renewal"
    IS_NEW = "is_new"
    IS_DUPLICATE = "is_duplicate"
    HAS_PREVIOUS = "has_previous"
    IS_MINOR = "is_minor"
    IS_ADULT = "is_adult"
    IS_FOREIGN = "is_foreign"
    IS_NATIONAL = "is_national"
    CUSTOM = "custom"


class DocumentRequirementCreate(BaseModel):
    """Create document requirement - matches DB schema"""
    document_code: str = Field(..., max_length=100)
    document_name_es: str = Field(..., max_length=255)
    document_template_id: Optional[int] = None
    condition_type: DocumentConditionType = DocumentConditionType.ALWAYS
    condition_value: Optional[Dict[str, Any]] = Field(default_factory=dict)
    is_required: bool = True
    display_order: int = Field(default=0, ge=0)
    instructions_es: Optional[str] = None
    extraction_schema_key: Optional[str] = Field(None, max_length=100)
    is_active: bool = True


class DocumentRequirementUpdate(BaseModel):
    """Update document requirement"""
    document_name_es: Optional[str] = Field(None, max_length=255)
    document_template_id: Optional[int] = None
    condition_type: Optional[DocumentConditionType] = None
    condition_value: Optional[Dict[str, Any]] = None
    is_required: Optional[bool] = None
    display_order: Optional[int] = Field(None, ge=0)
    instructions_es: Optional[str] = None
    extraction_schema_key: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class DocumentRequirementResponse(BaseModel):
    """Document requirement response - matches DB schema"""
    id: str  # UUID in DB
    workflow_code: str
    document_code: str
    document_name_es: str
    document_template_id: Optional[int]
    condition_type: str
    condition_value: Optional[Dict[str, Any]]
    is_required: bool
    display_order: int
    instructions_es: Optional[str]
    extraction_schema_key: Optional[str]
    is_active: bool


# ─────────────────────────────────────────────────────────────────
# WORKFLOW_TARIFFS (table: workflow_tariffs - NOT tariff_configurations)
# ─────────────────────────────────────────────────────────────────

class TariffType(str, Enum):
    """Tariff type enum - matches DB constraint"""
    FIXED = "FIXED"
    PERCENTAGE = "PERCENTAGE"
    NOTA_INGRESO = "NOTA_INGRESO"


class WorkflowTariffCreate(BaseModel):
    """Create workflow tariff - matches workflow_tariffs table"""
    workflow_code: str = Field(..., max_length=100)
    solicitud_type: str = Field(default="expedicion", max_length=50)
    tariff_type: TariffType = TariffType.FIXED
    amount: Decimal = Field(..., ge=0)
    percentage_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    currency: str = Field(default="XAF", max_length=3)
    legal_reference: Optional[str] = Field(None, max_length=255)
    effective_from: date
    effective_to: Optional[date] = None
    is_active: bool = True


class WorkflowTariffUpdate(BaseModel):
    """Update workflow tariff"""
    solicitud_type: Optional[str] = Field(None, max_length=50)
    tariff_type: Optional[TariffType] = None
    amount: Optional[Decimal] = Field(None, ge=0)
    percentage_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    currency: Optional[str] = Field(None, max_length=3)
    legal_reference: Optional[str] = Field(None, max_length=255)
    effective_to: Optional[date] = None
    is_active: Optional[bool] = None


class WorkflowTariffResponse(BaseModel):
    """Workflow tariff response - matches DB schema"""
    id: int
    workflow_code: str
    solicitud_type: str
    tariff_type: str
    amount: float
    percentage_rate: Optional[float]
    currency: str
    legal_reference: Optional[str]
    effective_from: str
    effective_to: Optional[str]
    is_active: bool


# ─────────────────────────────────────────────────────────────────
# APPOINTMENT_SLOT_CONFIGS (table: appointment_slot_configs)
# ─────────────────────────────────────────────────────────────────

from datetime import time as Time
from pydantic import field_validator


def parse_time_string(value: str) -> Time:
    """Parse time string in formats: HH:MM, HH:MM:SS, or HH:MM AM/PM"""
    if isinstance(value, Time):
        return value
    if not isinstance(value, str):
        raise ValueError(f"Invalid time format: {value}")

    value = value.strip()

    # Handle AM/PM format (e.g., "08:00 AM", "04:00 PM")
    is_pm = False
    if value.upper().endswith(' AM'):
        value = value[:-3].strip()
    elif value.upper().endswith(' PM'):
        value = value[:-3].strip()
        is_pm = True

    parts = value.split(':')
    if len(parts) == 2:
        hour, minute = int(parts[0]), int(parts[1])
        second = 0
    elif len(parts) == 3:
        hour, minute, second = int(parts[0]), int(parts[1]), int(parts[2])
    else:
        raise ValueError(f"Invalid time format: {value}")

    # Convert PM to 24-hour
    if is_pm and hour < 12:
        hour += 12
    elif not is_pm and hour == 12:
        hour = 0

    return Time(hour, minute, second)


class AppointmentSlotConfigCreate(BaseModel):
    """Create appointment slot config - aligned with migration 030 (entity_locations)"""
    entity_location_id: UUID = Field(..., description="FK to entity_locations table")
    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: str = Field(..., description="Start time in HH:MM format")
    end_time: str = Field(..., description="End time in HH:MM format")
    slot_duration_minutes: int = Field(default=30, ge=5, le=120)
    max_appointments_per_slot: int = Field(default=10, ge=1, le=100)
    is_active: bool = True
    # Note: entity_code, location_name, location_address are resolved from entity_locations FK

    @field_validator('start_time', 'end_time', mode='before')
    @classmethod
    def validate_time(cls, v):
        """Accept time as string and validate format"""
        if isinstance(v, Time):
            return v.strftime('%H:%M:%S')
        if isinstance(v, str):
            # Validate by parsing, then return normalized format
            t = parse_time_string(v)
            return t.strftime('%H:%M:%S')
        raise ValueError(f"Invalid time: {v}")


class AppointmentSlotConfigUpdate(BaseModel):
    """Update appointment slot config"""
    entity_location_id: Optional[UUID] = Field(None, description="FK to entity_locations table")
    start_time: Optional[str] = Field(None, description="Start time in HH:MM format")
    end_time: Optional[str] = Field(None, description="End time in HH:MM format")
    slot_duration_minutes: Optional[int] = Field(None, ge=5, le=120)
    max_appointments_per_slot: Optional[int] = Field(None, ge=1, le=100)
    is_active: Optional[bool] = None

    @field_validator('start_time', 'end_time', mode='before')
    @classmethod
    def validate_time(cls, v):
        """Accept time as string and validate format"""
        if v is None:
            return None
        if isinstance(v, Time):
            return v.strftime('%H:%M:%S')
        if isinstance(v, str):
            # Validate by parsing, then return normalized format
            t = parse_time_string(v)
            return t.strftime('%H:%M:%S')
        raise ValueError(f"Invalid time: {v}")


class AppointmentSlotConfigResponse(BaseModel):
    """Appointment slot config response - aligned with migration 030 schema"""
    id: str  # UUID
    entity_location_id: Optional[str] = None  # FK to entity_locations
    entity_code: str
    day_of_week: int
    start_time: str
    end_time: str
    slot_duration_minutes: int
    max_appointments_per_slot: int
    is_active: bool
    # Joined from entity_locations table via entity_location_id FK
    location_name: Optional[str] = None
    location_address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None


class AppointmentSlotConfigBatchCreate(BaseModel):
    """Batch create appointment slot configs - for multiple days at once"""
    entity_location_id: UUID = Field(..., description="FK to entity_locations table")
    days_of_week: List[int] = Field(..., min_length=1, max_length=7, description="List of days (0=Monday, 6=Sunday)")
    start_time: str = Field(..., description="Start time in HH:MM format")
    end_time: str = Field(..., description="End time in HH:MM format")
    slot_duration_minutes: int = Field(default=30, ge=5, le=120)
    max_appointments_per_slot: int = Field(default=10, ge=1, le=100)
    is_active: bool = True

    @field_validator('days_of_week')
    @classmethod
    def validate_days(cls, v):
        """Validate each day is between 0-6 and unique"""
        if not all(0 <= d <= 6 for d in v):
            raise ValueError("Each day must be between 0 (Monday) and 6 (Sunday)")
        if len(v) != len(set(v)):
            raise ValueError("Days must be unique")
        return sorted(v)

    @field_validator('start_time', 'end_time', mode='before')
    @classmethod
    def validate_time(cls, v):
        """Accept time as string and validate format"""
        if isinstance(v, Time):
            return v.strftime('%H:%M:%S')
        if isinstance(v, str):
            t = parse_time_string(v)
            return t.strftime('%H:%M:%S')
        raise ValueError(f"Invalid time: {v}")


class AppointmentSlotConfigBatchResponse(BaseModel):
    """Response for batch slot creation"""
    created: List[AppointmentSlotConfigResponse]
    skipped: List[dict] = []  # Days that were skipped (already exist)
    total_created: int
    total_skipped: int


class AppointmentSlotConfigGroupUpdate(BaseModel):
    """Atomic update of an entire group of slot configs (reconcile pattern).
    Updates existing slots, creates new ones for added days, deletes removed days."""
    slot_ids: List[UUID] = Field(..., min_length=1, description="Current slot IDs in the group")
    entity_location_id: UUID = Field(..., description="FK to entity_locations")
    days_of_week: List[int] = Field(..., min_length=1, max_length=7, description="Desired final set of days (0=Monday, 6=Sunday)")
    start_time: str = Field(..., description="Start time in HH:MM format")
    end_time: str = Field(..., description="End time in HH:MM format")
    slot_duration_minutes: int = Field(default=30, ge=5, le=120)
    max_appointments_per_slot: int = Field(default=10, ge=1, le=100)
    is_active: bool = True

    @field_validator('days_of_week')
    @classmethod
    def validate_days(cls, v):
        if not all(0 <= d <= 6 for d in v):
            raise ValueError("Each day must be between 0 (Monday) and 6 (Sunday)")
        if len(v) != len(set(v)):
            raise ValueError("Days must be unique")
        return sorted(v)

    @field_validator('start_time', 'end_time', mode='before')
    @classmethod
    def validate_time(cls, v):
        if isinstance(v, Time):
            return v.strftime('%H:%M:%S')
        if isinstance(v, str):
            t = parse_time_string(v)
            return t.strftime('%H:%M:%S')
        raise ValueError(f"Invalid time: {v}")


class AppointmentSlotConfigGroupUpdateResponse(BaseModel):
    """Response for atomic group update"""
    slots: List[AppointmentSlotConfigResponse]
    total_updated: int
    total_created: int
    total_deleted: int


# ─────────────────────────────────────────────────────────────────
# APPOINTMENT_BLOCKED_DATES (table: appointment_blocked_dates)
# ─────────────────────────────────────────────────────────────────

class AppointmentBlockedDateCreate(BaseModel):
    """Create blocked date - matches DB schema"""
    entity_code: Optional[str] = Field(None, max_length=50, description="NULL = applies to all entities")
    blocked_date: date
    reason: Optional[str] = Field(None, max_length=255)
    is_recurring: bool = Field(default=False, description="True = same date every year")


class AppointmentBlockedDateResponse(BaseModel):
    """Blocked date response"""
    id: str  # UUID
    entity_code: Optional[str]
    blocked_date: str
    reason: Optional[str]
    is_recurring: bool


class AppointmentBlockedDateUpdate(BaseModel):
    """Update blocked date"""
    reason: Optional[str] = Field(None, max_length=255)
    is_recurring: Optional[bool] = None


# ─────────────────────────────────────────────────────────────────
# APPOINTMENT_DELAY_RULES (table: appointment_delay_rules)
# ─────────────────────────────────────────────────────────────────

class AppointmentDelayRuleCreate(BaseModel):
    """Create delay rule - matches DB schema"""
    workflow_code: Optional[str] = Field(None, max_length=100, description="NULL = default for all workflows")
    priority: str = Field(..., description="URGENT, HIGH, NORMAL, LOW")
    delay_business_days: int = Field(default=3, ge=0, le=30)
    is_active: bool = True


class AppointmentDelayRuleResponse(BaseModel):
    """Delay rule response"""
    id: str  # UUID
    workflow_code: Optional[str]
    priority: str
    delay_business_days: int
    is_active: bool


class AppointmentDelayRuleUpdate(BaseModel):
    """Update delay rule"""
    delay_business_days: Optional[int] = Field(None, ge=0, le=30)
    is_active: Optional[bool] = None


# Legacy aliases for backward compatibility
TariffConfigCreate = WorkflowTariffCreate
TariffConfigUpdate = WorkflowTariffUpdate
TariffConfigResponse = WorkflowTariffResponse


# ═══════════════════════════════════════════════════════════════
# WORKFLOW CRUD
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/workflows",
    response_model=List[WorkflowResponse],
    summary="List all workflows",
    description="Get all workflow configurations with optional filtering."
)
async def list_workflows(
    category: Optional[str] = Query(None, description="Filter by category"),
    entity_code: Optional[str] = Query(None, description="Filter by entity"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_generic: Optional[bool] = Query(None, description="Filter generic workflows only"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_workflow"))
):
    query = """
        SELECT
            w.*,
            (SELECT COUNT(*) FROM workflow_document_requirements
             WHERE workflow_code = w.code) as documents_count,
            (SELECT COUNT(*) FROM workflow_tariffs
             WHERE workflow_code = w.code AND is_active = true) as tariffs_count
        FROM workflows w
        WHERE 1=1
    """
    params = []

    if category:
        params.append(category)
        query += f" AND w.category = ${len(params)}"

    if entity_code:
        params.append(entity_code)
        query += f" AND w.entity_code = ${len(params)}"

    if is_active is not None:
        params.append(is_active)
        query += f" AND w.is_active = ${len(params)}"

    if is_generic is not None:
        params.append(is_generic)
        query += f" AND w.is_generic = ${len(params)}"

    query += " ORDER BY w.display_order, w.category, w.name_es"

    rows = await db.fetch(query, *params)

    results = []
    for row in rows:
        row_dict = dict(row)
        row_dict['config'] = _parse_config(row['config'])
        results.append(WorkflowResponse.from_row(
            row_dict,
            documents_count=row['documents_count'],
            tariffs_count=row['tariffs_count']
        ))
    return results


@router.get(
    "/workflows/{code}",
    response_model=WorkflowResponse,
    summary="Get workflow details",
    description="Get a specific workflow configuration by code."
)
async def get_workflow(
    code: str = Path(..., description="Workflow code"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_workflow"))
):
    row = await db.fetchrow("""
        SELECT
            w.*,
            (SELECT COUNT(*) FROM workflow_document_requirements
             WHERE workflow_code = w.code) as documents_count,
            (SELECT COUNT(*) FROM workflow_tariffs
             WHERE workflow_code = w.code AND is_active = true) as tariffs_count
        FROM workflows w
        WHERE w.code = $1
    """, code)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {code}"
        )

    row_dict = dict(row)
    row_dict['config'] = _parse_config(row['config'])
    return WorkflowResponse.from_row(
        row_dict,
        documents_count=row['documents_count'],
        tariffs_count=row['tariffs_count']
    )


@router.post(
    "/workflows",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create workflow",
    description="""
    Create a new workflow configuration.

    **Note:** Only generic workflows can be created through the API.
    Hardcoded workflows (pasaporte, residencia, etc.) are defined in Python code.
    """
)
async def create_workflow(
    workflow: WorkflowCreate = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_workflow"))
):
    # Check if code already exists
    existing = await db.fetchval(
        "SELECT 1 FROM workflows WHERE code = $1", workflow.code
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow already exists: {workflow.code}"
        )

    import json
    config_json = json.dumps(workflow.config) if workflow.config else '{}'
    tags_json = json.dumps(workflow.tags) if workflow.tags else '[]'

    row = await db.fetchrow("""
        INSERT INTO workflows (
            code, name_es, description_es, category, entity_code,
            workflow_type, requires_agent_validation, requires_appointment,
            is_generic, appointment_delay_days, appointment_entity_code,
            sla_hours, max_processing_days, display_order, icon, color,
            config, is_active, parent_workflow_code, tags, is_parent,
            created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16,
            $17::jsonb, $18, $19, $20::jsonb, $21, NOW(), NOW()
        )
        RETURNING *
    """, workflow.code, workflow.name_es, workflow.description_es,
        workflow.category, workflow.entity_code, workflow.workflow_type,
        workflow.requires_agent_validation, workflow.requires_appointment,
        workflow.is_generic, workflow.appointment_delay_days,
        workflow.appointment_entity_code, workflow.sla_hours,
        workflow.max_processing_days, workflow.display_order,
        workflow.icon, workflow.color, config_json, workflow.is_active,
        workflow.parent_workflow_code, tags_json, workflow.is_parent)

    # Hot-reload generic workflow into engine cache
    if workflow.is_generic and workflow.is_active:
        try:
            from ..workflows.generic_workflow import load_generic_workflow
            from ..services.workflow_engine import workflow_engine
            wf = await load_generic_workflow(db, workflow.code)
            workflow_engine.register_generic(workflow.code, wf)
        except Exception:
            pass  # Will be loaded at next startup

    # Auto-seed mapping + display config so workflow is visible to agents immediately
    try:
        # 1. workflow_menu_mapping (pattern = exact code, no wildcard — 1:1)
        existing_mapping = await db.fetchval(
            "SELECT 1 FROM workflow_menu_mapping WHERE workflow_pattern = $1",
            workflow.code,
        )
        if not existing_mapping:
            await db.execute("""
                INSERT INTO workflow_menu_mapping (
                    workflow_pattern, menu_group_id, menu_title_key, menu_icon,
                    display_order, include_pending, include_validation,
                    include_appointments, include_history, is_active
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, true)
            """,
                workflow.code,
                workflow.code.lower(),
                f"menu.{workflow.code.lower()}",
                workflow.icon or "file-text",
                workflow.display_order,
                True,
                True,
                workflow.requires_appointment,
                True,
            )
            logger.info(f"Auto-seeded workflow_menu_mapping for {workflow.code}")

        # 2. workflow_display_config (default system columns)
        existing_dc = await db.fetchval(
            "SELECT 1 FROM workflow_display_config WHERE workflow_code = $1",
            workflow.code,
        )
        if not existing_dc:
            await db.execute("""
                INSERT INTO workflow_display_config (
                    workflow_code, list_columns, preview_sections, labels, is_active
                ) VALUES ($1, $2::jsonb, $3::jsonb, '{}'::jsonb, true)
            """,
                workflow.code,
                json.dumps(["reference", "fullName", "createdAt", "status", "priority"]),
                json.dumps(["info", "extractedData", "documents", "contact"]),
            )
            logger.info(f"Auto-seeded workflow_display_config for {workflow.code}")

        # Invalidate caches so agents see the new workflow immediately
        from app.core.cache import invalidate_workflow_mappings_cache, invalidate_role_menu_cache
        await invalidate_workflow_mappings_cache()
        await invalidate_role_menu_cache("_all_")
    except Exception as e:
        logger.warning(f"Auto-seed for {workflow.code} failed (non-blocking): {e}")

    return WorkflowResponse.from_row(row)


@router.put(
    "/workflows/{code}",
    response_model=WorkflowResponse,
    summary="Update workflow",
    description="Update an existing workflow configuration."
)
async def update_workflow(
    code: str = Path(..., description="Workflow code"),
    workflow: WorkflowUpdate = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_workflow"))
):
    import json

    # Check if workflow exists
    existing = await db.fetchrow(
        "SELECT * FROM workflows WHERE code = $1", code
    )
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {code}"
        )

    # Build update query dynamically
    updates = []
    params = [code]
    param_idx = 2

    for field, value in workflow.model_dump(exclude_unset=True).items():
        if value is not None:
            # Handle JSONB config field
            if field == 'config':
                updates.append(f"{field} = ${param_idx}::jsonb")
                params.append(json.dumps(value))
            else:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
            param_idx += 1

    if not updates:
        return await get_workflow(code, db, current_user, _)

    updates.append(f"updated_at = NOW()")

    query = f"""
        UPDATE workflows
        SET {', '.join(updates)}
        WHERE code = $1
        RETURNING *
    """

    row = await db.fetchrow(query, *params)

    # Hot-reload generic workflow in engine cache
    if row and row["is_generic"]:
        try:
            from ..workflows.generic_workflow import load_generic_workflow
            from ..services.workflow_engine import workflow_engine
            if row["is_active"]:
                wf = await load_generic_workflow(db, code)
                workflow_engine.register_generic(code, wf)
            else:
                workflow_engine.unregister_generic(code)
        except Exception:
            pass  # Will be synced at next startup

    return WorkflowResponse.from_row(row)


@router.patch(
    "/workflows/{code}/activate",
    summary="Activate or deactivate workflow",
    description="Toggle workflow active status."
)
async def toggle_workflow_status(
    code: str = Path(..., description="Workflow code"),
    is_active: bool = Body(..., embed=True),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_workflow"))
):
    result = await db.execute("""
        UPDATE workflows
        SET is_active = $2, updated_at = NOW()
        WHERE code = $1
    """, code, is_active)

    if 'UPDATE 0' in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {code}"
        )

    # Hot-reload generic workflow in engine cache
    row = await db.fetchrow("SELECT is_generic FROM workflows WHERE code = $1", code)
    if row and row["is_generic"]:
        try:
            from ..workflows.generic_workflow import load_generic_workflow
            from ..services.workflow_engine import workflow_engine
            if is_active:
                wf = await load_generic_workflow(db, code)
                workflow_engine.register_generic(code, wf)
            else:
                workflow_engine.unregister_generic(code)
        except Exception:
            pass  # Will be synced at next startup

    return {
        "message": f"Workflow {'activated' if is_active else 'deactivated'}",
        "code": code,
        "is_active": is_active
    }


@router.delete(
    "/workflows/{code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workflow",
    description="""
    Delete a workflow configuration.

    **Warning:** This also deletes associated document requirements and tariffs.
    Hardcoded workflows cannot be deleted.
    """
)
async def delete_workflow(
    code: str = Path(..., description="Workflow code"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_workflow"))
):
    # Check if it's a generic workflow
    workflow = await db.fetchrow(
        "SELECT is_generic FROM workflows WHERE code = $1", code
    )

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {code}"
        )

    if not workflow['is_generic']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete hardcoded workflows. Deactivate instead."
        )

    # Check for existing service requests
    has_requests = await db.fetchval("""
        SELECT 1 FROM service_requests WHERE workflow_code = $1 LIMIT 1
    """, code)

    if has_requests:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete workflow with existing service requests. Deactivate instead."
        )

    # Delete in order (foreign key constraints)
    await db.execute(
        "DELETE FROM workflow_tariffs WHERE workflow_code = $1", code
    )
    await db.execute(
        "DELETE FROM workflow_document_requirements WHERE workflow_code = $1", code
    )
    await db.execute("DELETE FROM workflows WHERE code = $1", code)

    # Remove from generic workflow cache
    from ..services.workflow_engine import workflow_engine
    workflow_engine.unregister_generic(code)

    return None


# ═══════════════════════════════════════════════════════════════
# EXTRACTION SCHEMAS
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/extraction-schemas",
    summary="List available OCR extraction schemas",
    description="List all available OCR extraction schema keys for document configuration."
)
async def list_extraction_schemas(
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_workflow")),
):
    """Return available OCR schemas for admin document configuration dropdown."""
    from ..services.schema_loader import schema_loader
    keys = schema_loader.get_schema_keys()
    result = []
    for key in sorted(keys):
        schema = schema_loader.get_schema(key)
        result.append({
            "key": key,
            "name": schema.get("document_name", key) if schema else key,
            "version": schema.get("version", "1") if schema else "1",
        })
    return result


# ═══════════════════════════════════════════════════════════════
# DOCUMENT REQUIREMENTS
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/workflows/{code}/documents",
    response_model=List[DocumentRequirementResponse],
    summary="List document requirements",
    description="Get all document requirements for a workflow."
)
async def list_document_requirements(
    code: str = Path(..., description="Workflow code"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_workflow"))
):
    # First check if workflow exists and if it's predefined
    workflow_row = await db.fetchrow("""
        SELECT code, is_generic FROM workflows WHERE code = $1
    """, code)

    if not workflow_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {code}"
        )

    # For predefined workflows (is_generic=False), read from Python workflow classes
    if not workflow_row['is_generic']:
        from ..services.workflow_engine import workflow_engine

        # Extract sub_type from workflow code (e.g., PASAPORTE_NUEVO -> NUEVO)
        parts = code.split('_', 1)
        sub_type = parts[1] if len(parts) > 1 else code

        # Try to get workflow class from engine
        workflow = workflow_engine.get_workflow_by_string(code)
        if workflow:
            from ..services.workflow_sync_service import _extract_document_requirements
            doc_requirements = _extract_document_requirements(workflow, sub_type)
            result = []
            for i, doc_req in enumerate(doc_requirements):
                result.append(DocumentRequirementResponse(
                    id=f"predefined-{code}-{doc_req['document_code']}",
                    workflow_code=code,
                    document_code=doc_req['document_code'],
                    document_name_es=doc_req['document_name_es'],
                    document_template_id=None,
                    condition_type=doc_req.get('condition_type', 'always'),
                    condition_value=doc_req.get('condition_value'),
                    is_required=doc_req['is_required'],
                    display_order=doc_req.get('display_order', i + 1),
                    instructions_es=doc_req.get('instructions_es'),
                    extraction_schema_key=doc_req.get('extraction_schema_key'),
                    is_active=True
                ))
            return result
        # Predefined but not in registry — return empty, don't fall to DB
        logger.warning(f"Predefined workflow {code} not found in workflow_engine registry")
        return []

    # For dynamic workflows (is_generic=True), read from database
    rows = await db.fetch("""
        SELECT * FROM workflow_document_requirements
        WHERE workflow_code = $1
        ORDER BY display_order, document_code
    """, code)

    result = []
    for row in rows:
        # Explicit type conversions for PostgreSQL enum and JSONB
        condition_type_val = row.get('condition_type')
        condition_type_str = str(condition_type_val) if condition_type_val else 'always'

        condition_value_val = row.get('condition_value')
        # JSONB can be any type (dict, list, str, null); safely coerce to dict
        condition_value_dict = condition_value_val if isinstance(condition_value_val, dict) else None

        result.append(DocumentRequirementResponse(
            id=str(row['id']),
            workflow_code=row['workflow_code'],
            document_code=row['document_code'],
            document_name_es=row['document_name_es'],
            document_template_id=row.get('document_template_id'),
            condition_type=condition_type_str,
            condition_value=condition_value_dict,
            is_required=row['is_required'],
            display_order=row['display_order'] or 0,
            instructions_es=row.get('instructions_es'),
            extraction_schema_key=row.get('extraction_schema_key'),
            is_active=row.get('is_active', True)
        ))

    return result


@router.post(
    "/workflows/{code}/documents",
    response_model=DocumentRequirementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add document requirement",
    description="Add a new document requirement to a workflow."
)
async def add_document_requirement(
    code: str = Path(..., description="Workflow code"),
    doc: DocumentRequirementCreate = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_workflow"))
):
    import json

    # Check workflow exists
    workflow_exists = await db.fetchval(
        "SELECT 1 FROM workflows WHERE code = $1", code
    )
    if not workflow_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {code}"
        )

    # Check if document code already exists for this workflow
    existing = await db.fetchval("""
        SELECT 1 FROM workflow_document_requirements
        WHERE workflow_code = $1 AND document_code = $2
    """, code, doc.document_code)

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document {doc.document_code} already exists for workflow {code}"
        )

    condition_value_json = json.dumps(doc.condition_value) if doc.condition_value else None

    row = await db.fetchrow("""
        INSERT INTO workflow_document_requirements (
            workflow_code, document_code, document_name_es,
            document_template_id, condition_type, condition_value,
            is_required, display_order, instructions_es,
            extraction_schema_key, is_active
        ) VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11)
        RETURNING *
    """, code, doc.document_code, doc.document_name_es,
        doc.document_template_id, doc.condition_type.value,
        condition_value_json, doc.is_required, doc.display_order,
        doc.instructions_es, doc.extraction_schema_key, doc.is_active)

    await _refresh_generic_cache(db, code)

    return DocumentRequirementResponse(
        id=str(row['id']),
        workflow_code=row['workflow_code'],
        document_code=row['document_code'],
        document_name_es=row['document_name_es'],
        document_template_id=row.get('document_template_id'),
        condition_type=row.get('condition_type', 'always'),
        condition_value=row.get('condition_value'),
        is_required=row['is_required'],
        display_order=row['display_order'],
        instructions_es=row['instructions_es'],
        extraction_schema_key=row['extraction_schema_key'],
        is_active=row.get('is_active', True)
    )


@router.put(
    "/workflows/{code}/documents/{doc_code}",
    response_model=DocumentRequirementResponse,
    summary="Update document requirement",
    description="Update a document requirement."
)
async def update_document_requirement(
    code: str = Path(..., description="Workflow code"),
    doc_code: str = Path(..., description="Document code"),
    doc: DocumentRequirementUpdate = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_workflow"))
):
    import json

    # Build update query
    updates = []
    params = [code, doc_code]
    param_idx = 3

    for field, value in doc.model_dump(exclude_unset=True).items():
        if value is not None:
            # Handle enum and JSONB fields
            if field == 'condition_type':
                updates.append(f"{field} = ${param_idx}")
                params.append(value.value if hasattr(value, 'value') else value)
            elif field == 'condition_value':
                updates.append(f"{field} = ${param_idx}::jsonb")
                params.append(json.dumps(value))
            else:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
            param_idx += 1

    if not updates:
        # Return existing
        row = await db.fetchrow("""
            SELECT * FROM workflow_document_requirements
            WHERE workflow_code = $1 AND document_code = $2
        """, code, doc_code)

        if not row:
            raise TranslatedException(ErrorCode.NOT_FOUND)

        return DocumentRequirementResponse(
            id=str(row['id']),
            workflow_code=row['workflow_code'],
            document_code=row['document_code'],
            document_name_es=row['document_name_es'],
            document_template_id=row.get('document_template_id'),
            condition_type=row.get('condition_type', 'always'),
            condition_value=row.get('condition_value'),
            is_required=row['is_required'],
            display_order=row['display_order'],
            instructions_es=row['instructions_es'],
            extraction_schema_key=row['extraction_schema_key'],
            is_active=row.get('is_active', True)
        )

    query = f"""
        UPDATE workflow_document_requirements
        SET {', '.join(updates)}
        WHERE workflow_code = $1 AND document_code = $2
        RETURNING *
    """

    row = await db.fetchrow(query, *params)

    if not row:
        raise TranslatedException(ErrorCode.NOT_FOUND)

    await _refresh_generic_cache(db, code)

    return DocumentRequirementResponse(
        id=str(row['id']),
        workflow_code=row['workflow_code'],
        document_code=row['document_code'],
        document_name_es=row['document_name_es'],
        document_template_id=row.get('document_template_id'),
        condition_type=row.get('condition_type', 'always'),
        condition_value=row.get('condition_value'),
        is_required=row['is_required'],
        display_order=row['display_order'],
        instructions_es=row['instructions_es'],
        extraction_schema_key=row['extraction_schema_key'],
        is_active=row.get('is_active', True)
    )


@router.delete(
    "/workflows/{code}/documents/{doc_code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove document requirement",
    description="Remove a document requirement from a workflow."
)
async def remove_document_requirement(
    code: str = Path(..., description="Workflow code"),
    doc_code: str = Path(..., description="Document code"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_workflow"))
):
    result = await db.execute("""
        DELETE FROM workflow_document_requirements
        WHERE workflow_code = $1 AND document_code = $2
    """, code, doc_code)

    if 'DELETE 0' in result:
        raise TranslatedException(ErrorCode.NOT_FOUND)

    await _refresh_generic_cache(db, code)

    return None


@router.patch(
    "/workflows/{code}/documents/reorder",
    summary="Reorder document requirements",
    description="Update the display order of document requirements."
)
async def reorder_documents(
    code: str = Path(..., description="Workflow code"),
    order: List[Dict[str, int]] = Body(
        ...,
        description="List of {document_code: display_order} pairs"
    ),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_workflow"))
):
    for item in order:
        doc_code = item.get('document_code')
        display_order = item.get('display_order', 0)

        await db.execute("""
            UPDATE workflow_document_requirements
            SET display_order = $3
            WHERE workflow_code = $1 AND document_code = $2
        """, code, doc_code, display_order)

    return {"message": "Documents reordered successfully"}


# ═══════════════════════════════════════════════════════════════
# WORKFLOW TARIFFS (table: workflow_tariffs)
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/tariffs",
    response_model=List[WorkflowTariffResponse],
    summary="List all workflow tariffs",
    description="Get all workflow tariff configurations with optional filtering."
)
async def list_tariffs(
    workflow_code: Optional[str] = Query(None, description="Filter by workflow"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_tariff"))
):
    query = "SELECT * FROM workflow_tariffs WHERE 1=1"
    params = []

    if workflow_code:
        params.append(workflow_code)
        query += f" AND workflow_code = ${len(params)}"

    if is_active is not None:
        params.append(is_active)
        query += f" AND is_active = ${len(params)}"

    query += " ORDER BY workflow_code, effective_from DESC"

    rows = await db.fetch(query, *params)

    return [
        WorkflowTariffResponse(
            id=row['id'],
            workflow_code=row['workflow_code'],
            solicitud_type=row['solicitud_type'],
            tariff_type=row['tariff_type'],
            amount=float(row['amount']) if row['amount'] else 0,
            percentage_rate=float(row['percentage_rate']) if row['percentage_rate'] else None,
            currency=row['currency'],
            legal_reference=row['legal_reference'],
            effective_from=row['effective_from'].isoformat() if row['effective_from'] else None,
            effective_to=row['effective_to'].isoformat() if row['effective_to'] else None,
            is_active=row['is_active']
        )
        for row in rows
    ]


@router.post(
    "/tariffs",
    response_model=WorkflowTariffResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create workflow tariff",
    description="Create a new workflow tariff configuration."
)
async def create_tariff(
    tariff: WorkflowTariffCreate = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_tariff"))
):
    # Check workflow exists
    workflow_exists = await db.fetchval(
        "SELECT 1 FROM workflows WHERE code = $1", tariff.workflow_code
    )
    if not workflow_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {tariff.workflow_code}"
        )

    row = await db.fetchrow("""
        INSERT INTO workflow_tariffs (
            workflow_code, solicitud_type, tariff_type, amount,
            percentage_rate, currency, legal_reference,
            effective_from, effective_to, is_active
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING *
    """, tariff.workflow_code, tariff.solicitud_type, tariff.tariff_type.value,
        tariff.amount, tariff.percentage_rate, tariff.currency,
        tariff.legal_reference, tariff.effective_from, tariff.effective_to,
        tariff.is_active)

    await _refresh_generic_cache(db, tariff.workflow_code)

    return WorkflowTariffResponse(
        id=row['id'],
        workflow_code=row['workflow_code'],
        solicitud_type=row['solicitud_type'],
        tariff_type=row['tariff_type'],
        amount=float(row['amount']) if row['amount'] else 0,
        percentage_rate=float(row['percentage_rate']) if row['percentage_rate'] else None,
        currency=row['currency'],
        legal_reference=row['legal_reference'],
        effective_from=row['effective_from'].isoformat() if row['effective_from'] else None,
        effective_to=row['effective_to'].isoformat() if row['effective_to'] else None,
        is_active=row['is_active']
    )


@router.put(
    "/tariffs/{tariff_id}",
    response_model=WorkflowTariffResponse,
    summary="Update workflow tariff",
    description="Update an existing workflow tariff configuration."
)
async def update_tariff(
    tariff_id: int = Path(..., description="Tariff ID"),
    tariff: WorkflowTariffUpdate = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_tariff"))
):
    updates = []
    params = [tariff_id]
    param_idx = 2

    for field, value in tariff.model_dump(exclude_unset=True).items():
        if value is not None:
            # Handle enum fields
            if field == 'tariff_type':
                updates.append(f"{field} = ${param_idx}")
                params.append(value.value if hasattr(value, 'value') else value)
            else:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
            param_idx += 1

    if not updates:
        row = await db.fetchrow(
            "SELECT * FROM workflow_tariffs WHERE id = $1", tariff_id
        )
        if not row:
            raise TranslatedException(ErrorCode.NOT_FOUND)
        return WorkflowTariffResponse(
            id=row['id'],
            workflow_code=row['workflow_code'],
            solicitud_type=row['solicitud_type'],
            tariff_type=row['tariff_type'],
            amount=float(row['amount']) if row['amount'] else 0,
            percentage_rate=float(row['percentage_rate']) if row['percentage_rate'] else None,
            currency=row['currency'],
            legal_reference=row['legal_reference'],
            effective_from=row['effective_from'].isoformat() if row['effective_from'] else None,
            effective_to=row['effective_to'].isoformat() if row['effective_to'] else None,
            is_active=row['is_active']
        )

    query = f"""
        UPDATE workflow_tariffs
        SET {', '.join(updates)}
        WHERE id = $1
        RETURNING *
    """

    row = await db.fetchrow(query, *params)

    if not row:
        raise TranslatedException(ErrorCode.NOT_FOUND)

    await _refresh_generic_cache(db, row['workflow_code'])

    return WorkflowTariffResponse(
        id=row['id'],
        workflow_code=row['workflow_code'],
        solicitud_type=row['solicitud_type'],
        tariff_type=row['tariff_type'],
        amount=float(row['amount']) if row['amount'] else 0,
        percentage_rate=float(row['percentage_rate']) if row['percentage_rate'] else None,
        currency=row['currency'],
        legal_reference=row['legal_reference'],
        effective_from=row['effective_from'].isoformat() if row['effective_from'] else None,
        effective_to=row['effective_to'].isoformat() if row['effective_to'] else None,
        is_active=row['is_active']
    )


@router.delete(
    "/tariffs/{tariff_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workflow tariff",
    description="Delete a workflow tariff configuration."
)
async def delete_tariff(
    tariff_id: int = Path(..., description="Tariff ID"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_tariff"))
):
    # Get workflow_code before delete (for cache refresh)
    wf_code = await db.fetchval(
        "SELECT workflow_code FROM workflow_tariffs WHERE id = $1", tariff_id
    )

    result = await db.execute(
        "DELETE FROM workflow_tariffs WHERE id = $1", tariff_id
    )

    if 'DELETE 0' in result:
        raise TranslatedException(ErrorCode.NOT_FOUND)

    if wf_code:
        await _refresh_generic_cache(db, wf_code)

    return None


# ═══════════════════════════════════════════════════════════════
# APPOINTMENT SETTINGS
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/appointments/slot-configs",
    response_model=List[AppointmentSlotConfigResponse],
    summary="List appointment slot configurations",
    description="Get all appointment slot configurations by entity or location."
)
async def list_slot_configs(
    entity_code: Optional[str] = Query(None, description="Filter by entity code"),
    entity_location_id: Optional[str] = Query(None, description="Filter by entity location ID"),
    city: Optional[str] = Query(None, description="Filter by city (Malabo, Bata, etc.)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_appointment"))
):
    # JOIN with entity_locations to get location details
    query = """
        SELECT
            sc.id,
            sc.entity_location_id,
            sc.entity_code,
            sc.day_of_week,
            sc.start_time,
            sc.end_time,
            sc.slot_duration_minutes,
            sc.max_appointments_per_slot,
            sc.is_active,
            el.location_name,
            el.location_address,
            el.city,
            el.region
        FROM appointment_slot_configs sc
        LEFT JOIN entity_locations el ON sc.entity_location_id = el.id
        WHERE 1=1
    """
    params = []

    if entity_location_id:
        params.append(entity_location_id)
        query += f" AND sc.entity_location_id = ${len(params)}::uuid"

    if entity_code:
        params.append(entity_code)
        query += f" AND sc.entity_code = ${len(params)}"

    if city:
        params.append(city)
        query += f" AND el.city = ${len(params)}"

    if is_active is not None:
        params.append(is_active)
        query += f" AND sc.is_active = ${len(params)}"

    query += " ORDER BY sc.entity_code, sc.day_of_week, sc.start_time"

    rows = await db.fetch(query, *params)

    return [
        AppointmentSlotConfigResponse(
            id=str(row['id']),
            entity_location_id=str(row['entity_location_id']) if row.get('entity_location_id') else None,
            entity_code=row['entity_code'],
            day_of_week=row['day_of_week'],
            start_time=str(row['start_time']),
            end_time=str(row['end_time']),
            slot_duration_minutes=row['slot_duration_minutes'],
            max_appointments_per_slot=row['max_appointments_per_slot'],
            is_active=row['is_active'],
            location_name=row.get('location_name'),
            location_address=row.get('location_address'),
            city=row.get('city'),
            region=row.get('region')
        )
        for row in rows
    ]


@router.post(
    "/appointments/slot-configs",
    response_model=AppointmentSlotConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create appointment slot configuration",
    description="Create a new appointment slot configuration using entity_location_id."
)
async def create_slot_config(
    slot: AppointmentSlotConfigCreate = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_appointment"))
):
    from loguru import logger

    try:
        # Parse time strings to datetime.time objects for database
        start_time_obj = parse_time_string(slot.start_time)
        end_time_obj = parse_time_string(slot.end_time)

        # 1. Fetch entity_location to resolve entity_code and location details
        location = await db.fetchrow("""
            SELECT id, entity_code, location_name, location_address, city, region
            FROM entity_locations
            WHERE id = $1::uuid AND is_active = TRUE
        """, slot.entity_location_id)

        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity location not found or inactive: {slot.entity_location_id}"
            )

        # 2. Check for duplicate (same location + day + start_time)
        existing = await db.fetchrow("""
            SELECT id FROM appointment_slot_configs
            WHERE entity_location_id = $1::uuid AND day_of_week = $2 AND start_time = $3::time
        """, slot.entity_location_id, slot.day_of_week, start_time_obj)

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Slot configuration already exists for this location, day, and start time"
            )

        # 3. Insert the slot config (location_name/location_address removed in migration 030)
        row = await db.fetchrow("""
            INSERT INTO appointment_slot_configs (
                entity_location_id, entity_code, day_of_week, start_time, end_time,
                slot_duration_minutes, max_appointments_per_slot, is_active
            ) VALUES ($1::uuid, $2, $3, $4::time, $5::time, $6, $7, $8)
            RETURNING *
        """,
            slot.entity_location_id,
            location['entity_code'],
            slot.day_of_week,
            start_time_obj,
            end_time_obj,
            slot.slot_duration_minutes,
            slot.max_appointments_per_slot,
            slot.is_active
        )

        logger.info(f"Created slot config: {row['id']} for {location['entity_code']} day={slot.day_of_week}")

        return AppointmentSlotConfigResponse(
            id=str(row['id']),
            entity_location_id=str(row['entity_location_id']) if row.get('entity_location_id') else None,
            entity_code=row['entity_code'],
            day_of_week=row['day_of_week'],
            start_time=str(row['start_time']),
            end_time=str(row['end_time']),
            slot_duration_minutes=row['slot_duration_minutes'],
            max_appointments_per_slot=row['max_appointments_per_slot'],
            is_active=row['is_active'],
            location_name=location.get('location_name'),
            location_address=location.get('location_address'),
            city=location.get('city'),
            region=location.get('region')
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating slot config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create slot configuration: {str(e)}"
        )


@router.post(
    "/appointments/slot-configs/batch",
    response_model=AppointmentSlotConfigBatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Batch create appointment slot configurations",
    description="Create multiple appointment slot configurations for different days in a single request."
)
async def create_slot_configs_batch(
    batch: AppointmentSlotConfigBatchCreate = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_appointment"))
):
    """
    Create slot configurations for multiple days at once.

    This is more efficient than creating slots one by one when you want
    the same schedule for multiple days (e.g., Monday-Friday).

    Slots that already exist will be skipped (not cause an error).
    """
    from loguru import logger

    try:
        # Parse time strings
        start_time_obj = parse_time_string(batch.start_time)
        end_time_obj = parse_time_string(batch.end_time)

        # 1. Fetch entity_location with all details
        location = await db.fetchrow("""
            SELECT id, entity_code, location_name, location_address, city, region
            FROM entity_locations
            WHERE id = $1::uuid AND is_active = TRUE
        """, batch.entity_location_id)

        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity location not found or inactive: {batch.entity_location_id}"
            )

        created = []
        skipped = []

        # 2. Create slot for each day
        for day in batch.days_of_week:
            # Check if already exists
            existing = await db.fetchrow("""
                SELECT id FROM appointment_slot_configs
                WHERE entity_location_id = $1::uuid AND day_of_week = $2 AND start_time = $3::time
            """, batch.entity_location_id, day, start_time_obj)

            if existing:
                skipped.append({
                    "day_of_week": day,
                    "reason": "already_exists",
                    "existing_id": str(existing['id'])
                })
                continue

            # Insert
            row = await db.fetchrow("""
                INSERT INTO appointment_slot_configs (
                    entity_location_id, entity_code, day_of_week, start_time, end_time,
                    slot_duration_minutes, max_appointments_per_slot, is_active
                ) VALUES ($1::uuid, $2, $3, $4::time, $5::time, $6, $7, $8)
                RETURNING *
            """,
                batch.entity_location_id,
                location['entity_code'],
                day,
                start_time_obj,
                end_time_obj,
                batch.slot_duration_minutes,
                batch.max_appointments_per_slot,
                batch.is_active
            )

            created.append(AppointmentSlotConfigResponse(
                id=str(row['id']),
                entity_location_id=str(row['entity_location_id']) if row.get('entity_location_id') else None,
                entity_code=row['entity_code'],
                day_of_week=row['day_of_week'],
                start_time=str(row['start_time']),
                end_time=str(row['end_time']),
                slot_duration_minutes=row['slot_duration_minutes'],
                max_appointments_per_slot=row['max_appointments_per_slot'],
                is_active=row['is_active'],
                location_name=location.get('location_name'),
                location_address=location.get('location_address'),
                city=location.get('city'),
                region=location.get('region')
            ))

        logger.info(
            f"Batch created {len(created)} slot configs for {location['entity_code']}, "
            f"skipped {len(skipped)} (already exist)"
        )

        return AppointmentSlotConfigBatchResponse(
            created=created,
            skipped=skipped,
            total_created=len(created),
            total_skipped=len(skipped)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch slot config creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create slot configurations: {str(e)}"
        )


@router.put(
    "/appointments/slot-configs/batch-update",
    response_model=AppointmentSlotConfigGroupUpdateResponse,
    summary="Batch update appointment slot configurations (reconcile pattern)",
    description="Atomically update an entire group of slot configs. Updates existing slots, creates new ones for added days, deletes removed days."
)
async def batch_update_slot_configs(
    group: AppointmentSlotConfigGroupUpdate = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_appointment"))
):
    from loguru import logger

    try:
        start_time_obj = parse_time_string(group.start_time)
        end_time_obj = parse_time_string(group.end_time)

        # 1. Validate entity_location
        location = await db.fetchrow("""
            SELECT id, entity_code, location_name, location_address, city, region
            FROM entity_locations
            WHERE id = $1::uuid AND is_active = TRUE
        """, group.entity_location_id)

        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity location not found or inactive: {group.entity_location_id}"
            )

        entity_code = location['entity_code']

        # 2. Fetch existing slots by slot_ids -> build {day: slot_id} map
        existing_slots = await db.fetch("""
            SELECT id, day_of_week FROM appointment_slot_configs
            WHERE id = ANY($1::uuid[])
        """, [str(sid) for sid in group.slot_ids])

        existing_day_map = {row['day_of_week']: str(row['id']) for row in existing_slots}
        existing_days = set(existing_day_map.keys())
        desired_days = set(group.days_of_week)

        # 3. Compute reconcile sets
        days_to_update = existing_days & desired_days
        days_to_create = desired_days - existing_days
        days_to_delete = existing_days - desired_days

        total_updated = 0
        total_created = 0
        total_deleted = 0

        # 4a. UPDATE existing slots that remain
        for day in days_to_update:
            slot_id = existing_day_map[day]
            await db.execute("""
                UPDATE appointment_slot_configs
                SET entity_location_id = $1::uuid, entity_code = $2, day_of_week = $3,
                    start_time = $4::time, end_time = $5::time,
                    slot_duration_minutes = $6, max_appointments_per_slot = $7,
                    is_active = $8, updated_at = NOW()
                WHERE id = $9::uuid
            """, group.entity_location_id, entity_code, day,
                start_time_obj, end_time_obj,
                group.slot_duration_minutes, group.max_appointments_per_slot,
                group.is_active, slot_id)
            total_updated += 1

        # 4b. INSERT new slots for added days
        for day in days_to_create:
            await db.execute("""
                INSERT INTO appointment_slot_configs (
                    entity_location_id, entity_code, day_of_week, start_time, end_time,
                    slot_duration_minutes, max_appointments_per_slot, is_active
                ) VALUES ($1::uuid, $2, $3, $4::time, $5::time, $6, $7, $8)
            """, group.entity_location_id, entity_code, day,
                start_time_obj, end_time_obj,
                group.slot_duration_minutes, group.max_appointments_per_slot,
                group.is_active)
            total_created += 1

        # 4c. DELETE slots for removed days (with FK guard for appointment_holds)
        if days_to_delete:
            ids_to_delete = [existing_day_map[d] for d in days_to_delete]

            # Check for active holds on slots being deleted
            active_holds = await db.fetchval("""
                SELECT COUNT(*) FROM appointment_holds
                WHERE slot_config_id = ANY($1::uuid[])
                  AND status IN ('held', 'confirmed')
                  AND appointment_date >= CURRENT_DATE
            """, ids_to_delete)

            if active_holds and active_holds > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot remove {len(days_to_delete)} day(s): "
                           f"{active_holds} active appointment(s) exist. "
                           "Cancel the appointments first."
                )

            # Clean up expired/cancelled holds before deleting
            await db.execute("""
                DELETE FROM appointment_holds
                WHERE slot_config_id = ANY($1::uuid[])
                  AND (status NOT IN ('held', 'confirmed') OR appointment_date < CURRENT_DATE)
            """, ids_to_delete)

            await db.execute("""
                DELETE FROM appointment_slot_configs
                WHERE id = ANY($1::uuid[])
            """, ids_to_delete)
            total_deleted = len(ids_to_delete)

        # 5. Fetch all resulting slots for this location + desired days
        result_rows = await db.fetch("""
            SELECT
                sc.id, sc.entity_location_id, sc.entity_code, sc.day_of_week,
                sc.start_time, sc.end_time, sc.slot_duration_minutes,
                sc.max_appointments_per_slot, sc.is_active,
                el.location_name, el.location_address, el.city, el.region
            FROM appointment_slot_configs sc
            LEFT JOIN entity_locations el ON sc.entity_location_id = el.id
            WHERE sc.entity_location_id = $1::uuid AND sc.day_of_week = ANY($2::int[])
            ORDER BY sc.day_of_week
        """, group.entity_location_id, list(desired_days))

        result_slots = [
            AppointmentSlotConfigResponse(
                id=str(row['id']),
                entity_location_id=str(row['entity_location_id']) if row.get('entity_location_id') else None,
                entity_code=row['entity_code'],
                day_of_week=row['day_of_week'],
                start_time=str(row['start_time']),
                end_time=str(row['end_time']),
                slot_duration_minutes=row['slot_duration_minutes'],
                max_appointments_per_slot=row['max_appointments_per_slot'],
                is_active=row['is_active'],
                location_name=row.get('location_name'),
                location_address=row.get('location_address'),
                city=row.get('city'),
                region=row.get('region')
            ) for row in result_rows
        ]

        logger.info(
            f"Batch update for {entity_code}: "
            f"{total_updated} updated, {total_created} created, {total_deleted} deleted"
        )

        return AppointmentSlotConfigGroupUpdateResponse(
            slots=result_slots,
            total_updated=total_updated,
            total_created=total_created,
            total_deleted=total_deleted
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch slot config update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to batch update slot configurations: {str(e)}"
        )


@router.put(
    "/appointments/slot-configs/{slot_id}",
    response_model=AppointmentSlotConfigResponse,
    summary="Update appointment slot configuration",
    description="Update an existing appointment slot configuration."
)
async def update_slot_config(
    slot_id: str = Path(..., description="Slot config ID (UUID)"),
    slot: AppointmentSlotConfigUpdate = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_appointment"))
):
    updates = []
    params = [slot_id]
    param_idx = 2

    # Handle entity_location_id change - need to also update entity_code
    slot_data = slot.model_dump(exclude_unset=True)
    if 'entity_location_id' in slot_data and slot_data['entity_location_id']:
        # Fetch the new location data
        new_location = await db.fetchrow("""
            SELECT id, entity_code, location_name, location_address, city, region
            FROM entity_locations
            WHERE id = $1::uuid AND is_active = TRUE
        """, slot_data['entity_location_id'])

        if not new_location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity location not found or inactive: {slot_data['entity_location_id']}"
            )

        # Add entity_location_id update
        updates.append(f"entity_location_id = ${param_idx}::uuid")
        params.append(slot_data['entity_location_id'])
        param_idx += 1

        # Also update entity_code (location_name/location_address removed in migration 030)
        updates.append(f"entity_code = ${param_idx}")
        params.append(new_location['entity_code'])
        param_idx += 1

    # Handle other fields — apply type casts for asyncpg strict typing
    TIME_FIELDS = {'start_time', 'end_time'}
    for field, value in slot_data.items():
        if field != 'entity_location_id' and value is not None:
            if field in TIME_FIELDS:
                updates.append(f"{field} = ${param_idx}::time")
                params.append(parse_time_string(value) if isinstance(value, str) else value)
            else:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
            param_idx += 1

    # Helper function to fetch slot config with location details
    async def fetch_slot_with_location(slot_id: str):
        return await db.fetchrow("""
            SELECT
                sc.id, sc.entity_location_id, sc.entity_code, sc.day_of_week,
                sc.start_time, sc.end_time, sc.slot_duration_minutes,
                sc.max_appointments_per_slot, sc.is_active,
                el.location_name, el.location_address, el.city, el.region
            FROM appointment_slot_configs sc
            LEFT JOIN entity_locations el ON sc.entity_location_id = el.id
            WHERE sc.id = $1::uuid
        """, slot_id)

    if not updates:
        row = await fetch_slot_with_location(slot_id)
        if not row:
            raise TranslatedException(ErrorCode.NOT_FOUND)
        return AppointmentSlotConfigResponse(
            id=str(row['id']),
            entity_location_id=str(row['entity_location_id']) if row.get('entity_location_id') else None,
            entity_code=row['entity_code'],
            day_of_week=row['day_of_week'],
            start_time=str(row['start_time']),
            end_time=str(row['end_time']),
            slot_duration_minutes=row['slot_duration_minutes'],
            max_appointments_per_slot=row['max_appointments_per_slot'],
            is_active=row['is_active'],
            location_name=row.get('location_name'),
            location_address=row.get('location_address'),
            city=row.get('city'),
            region=row.get('region')
        )

    # Check for duplicate: same entity_location_id + day_of_week + start_time (excluding self)
    # Resolve final values (updated or existing)
    current_slot = await fetch_slot_with_location(slot_id)
    if not current_slot:
        raise TranslatedException(ErrorCode.NOT_FOUND)

    final_location_id = slot_data.get('entity_location_id', current_slot['entity_location_id'])
    final_day = slot_data.get('day_of_week', current_slot['day_of_week'])
    final_start = parse_time_string(slot_data['start_time']) if 'start_time' in slot_data else current_slot['start_time']

    duplicate = await db.fetchrow("""
        SELECT id FROM appointment_slot_configs
        WHERE entity_location_id = $1::uuid AND day_of_week = $2 AND start_time = $3::time
          AND id != $4::uuid
    """, final_location_id, final_day, final_start, slot_id)

    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A slot configuration already exists for this location, day, and start time"
        )

    updates.append("updated_at = NOW()")

    query = f"""
        UPDATE appointment_slot_configs
        SET {', '.join(updates)}
        WHERE id = $1::uuid
        RETURNING id
    """

    result = await db.fetchrow(query, *params)

    if not result:
        raise TranslatedException(ErrorCode.NOT_FOUND)

    # Fetch the updated slot with location details
    row = await fetch_slot_with_location(slot_id)

    return AppointmentSlotConfigResponse(
        id=str(row['id']),
        entity_location_id=str(row['entity_location_id']) if row.get('entity_location_id') else None,
        entity_code=row['entity_code'],
        day_of_week=row['day_of_week'],
        start_time=str(row['start_time']),
        end_time=str(row['end_time']),
        slot_duration_minutes=row['slot_duration_minutes'],
        max_appointments_per_slot=row['max_appointments_per_slot'],
        is_active=row['is_active'],
        location_name=row.get('location_name'),
        location_address=row.get('location_address'),
        city=row.get('city'),
        region=row.get('region')
    )


@router.delete(
    "/appointments/slot-configs/{slot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete appointment slot configuration",
    description="Delete an appointment slot configuration."
)
async def delete_slot_config(
    slot_id: str = Path(..., description="Slot config ID (UUID)"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_appointment"))
):
    # Check for active appointment holds (confirmed or pending with future date)
    active_holds = await db.fetchval("""
        SELECT COUNT(*) FROM appointment_holds
        WHERE slot_config_id = $1::uuid
          AND status IN ('held', 'confirmed')
          AND appointment_date >= CURRENT_DATE
    """, slot_id)

    if active_holds and active_holds > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete: {active_holds} active appointment(s) exist for this slot. "
                   "Cancel the appointments first."
        )

    # Clean up expired/cancelled holds (safe to remove)
    await db.execute("""
        DELETE FROM appointment_holds
        WHERE slot_config_id = $1::uuid
          AND (status NOT IN ('held', 'confirmed') OR appointment_date < CURRENT_DATE)
    """, slot_id)

    result = await db.execute(
        "DELETE FROM appointment_slot_configs WHERE id = $1::uuid", slot_id
    )

    if 'DELETE 0' in result:
        raise TranslatedException(ErrorCode.NOT_FOUND)

    return None


@router.get(
    "/appointments/blocked-dates",
    response_model=List[AppointmentBlockedDateResponse],
    summary="List blocked dates",
    description="Get all blocked appointment dates."
)
async def list_blocked_dates(
    entity_code: Optional[str] = Query(None, description="Filter by entity"),
    from_date: Optional[date] = Query(None, description="From date"),
    to_date: Optional[date] = Query(None, description="To date"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_appointment"))
):
    query = "SELECT * FROM appointment_blocked_dates WHERE 1=1"
    params = []

    if entity_code:
        params.append(entity_code)
        query += f" AND (entity_code = ${len(params)} OR entity_code IS NULL)"

    if from_date:
        params.append(from_date)
        query += f" AND blocked_date >= ${len(params)}"

    if to_date:
        params.append(to_date)
        query += f" AND blocked_date <= ${len(params)}"

    query += " ORDER BY blocked_date"

    rows = await db.fetch(query, *params)

    return [
        AppointmentBlockedDateResponse(
            id=str(row['id']),
            entity_code=row['entity_code'],
            blocked_date=row['blocked_date'].isoformat(),
            reason=row['reason'],
            is_recurring=row['is_recurring']
        )
        for row in rows
    ]


@router.post(
    "/appointments/blocked-dates",
    response_model=AppointmentBlockedDateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add blocked date",
    description="Block a date for appointments."
)
async def add_blocked_date(
    blocked: AppointmentBlockedDateCreate = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_appointment"))
):
    row = await db.fetchrow("""
        INSERT INTO appointment_blocked_dates (entity_code, blocked_date, reason, is_recurring)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (entity_code, blocked_date) DO UPDATE SET reason = $3, is_recurring = $4
        RETURNING *
    """, blocked.entity_code, blocked.blocked_date, blocked.reason, blocked.is_recurring)

    return AppointmentBlockedDateResponse(
        id=str(row['id']),
        entity_code=row['entity_code'],
        blocked_date=row['blocked_date'].isoformat(),
        reason=row['reason'],
        is_recurring=row['is_recurring']
    )


@router.put(
    "/appointments/blocked-dates/{blocked_date_id}",
    response_model=AppointmentBlockedDateResponse,
    summary="Update blocked date",
    description="Update a blocked appointment date."
)
async def update_blocked_date(
    blocked_date_id: str = Path(..., description="Blocked date ID (UUID)"),
    data: AppointmentBlockedDateUpdate = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_appointment"))
):
    # Build update query dynamically
    updates = []
    params = [blocked_date_id]

    if data.reason is not None:
        params.append(data.reason)
        updates.append(f"reason = ${len(params)}")

    if data.is_recurring is not None:
        params.append(data.is_recurring)
        updates.append(f"is_recurring = ${len(params)}")

    if not updates:
        raise TranslatedException(ErrorCode.NO_FIELDS_TO_UPDATE)

    query = f"""
        UPDATE appointment_blocked_dates
        SET {', '.join(updates)}
        WHERE id = $1::uuid
        RETURNING *
    """

    row = await db.fetchrow(query, *params)

    if not row:
        raise TranslatedException(ErrorCode.NOT_FOUND)

    return AppointmentBlockedDateResponse(
        id=str(row['id']),
        entity_code=row['entity_code'],
        blocked_date=str(row['blocked_date']),
        reason=row['reason'],
        is_recurring=row['is_recurring']
    )


@router.delete(
    "/appointments/blocked-dates/{blocked_date_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove blocked date",
    description="Unblock an appointment date."
)
async def remove_blocked_date(
    blocked_date_id: str = Path(..., description="Blocked date ID (UUID)"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_appointment"))
):
    result = await db.execute(
        "DELETE FROM appointment_blocked_dates WHERE id = $1::uuid", blocked_date_id
    )

    if 'DELETE 0' in result:
        raise TranslatedException(ErrorCode.NOT_FOUND)

    return None


# ═══════════════════════════════════════════════════════════════
# APPOINTMENT DELAY RULES
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/appointments/delay-rules",
    response_model=List[AppointmentDelayRuleResponse],
    summary="List delay rules",
    description="Get all appointment delay rules."
)
async def list_delay_rules(
    workflow_code: Optional[str] = Query(None, description="Filter by workflow"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_appointment"))
):
    query = "SELECT * FROM appointment_delay_rules WHERE 1=1"
    params = []

    if workflow_code:
        params.append(workflow_code)
        query += f" AND workflow_code = ${len(params)}"

    query += " ORDER BY workflow_code NULLS FIRST, priority"

    rows = await db.fetch(query, *params)

    return [
        AppointmentDelayRuleResponse(
            id=str(row['id']),
            workflow_code=row['workflow_code'],
            priority=row['priority'],
            delay_business_days=row['delay_business_days'],
            is_active=row['is_active']
        )
        for row in rows
    ]


@router.post(
    "/appointments/delay-rules",
    response_model=AppointmentDelayRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create delay rule",
    description="Create a new appointment delay rule."
)
async def create_delay_rule(
    rule: AppointmentDelayRuleCreate = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_appointment"))
):
    row = await db.fetchrow("""
        INSERT INTO appointment_delay_rules (
            workflow_code, priority, delay_business_days, is_active
        ) VALUES ($1, $2::service_request_priority_enum, $3, $4)
        ON CONFLICT (workflow_code, priority) DO UPDATE SET
            delay_business_days = EXCLUDED.delay_business_days,
            is_active = EXCLUDED.is_active
        RETURNING *
    """, rule.workflow_code, rule.priority, rule.delay_business_days, rule.is_active)

    return AppointmentDelayRuleResponse(
        id=str(row['id']),
        workflow_code=row['workflow_code'],
        priority=row['priority'],
        delay_business_days=row['delay_business_days'],
        is_active=row['is_active']
    )


@router.put(
    "/appointments/delay-rules/{rule_id}",
    response_model=AppointmentDelayRuleResponse,
    summary="Update delay rule",
    description="Update an appointment delay rule."
)
async def update_delay_rule(
    rule_id: str = Path(..., description="Delay rule ID (UUID)"),
    data: AppointmentDelayRuleUpdate = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_appointment"))
):
    # Build update query dynamically
    updates = []
    params = [rule_id]

    if data.delay_business_days is not None:
        params.append(data.delay_business_days)
        updates.append(f"delay_business_days = ${len(params)}")

    if data.is_active is not None:
        params.append(data.is_active)
        updates.append(f"is_active = ${len(params)}")

    if not updates:
        raise TranslatedException(ErrorCode.NO_FIELDS_TO_UPDATE)

    query = f"""
        UPDATE appointment_delay_rules
        SET {', '.join(updates)}
        WHERE id = $1::uuid
        RETURNING *
    """

    row = await db.fetchrow(query, *params)

    if not row:
        raise TranslatedException(ErrorCode.NOT_FOUND)

    return AppointmentDelayRuleResponse(
        id=str(row['id']),
        workflow_code=row['workflow_code'],
        priority=row['priority'],
        delay_business_days=row['delay_business_days'],
        is_active=row['is_active']
    )


@router.delete(
    "/appointments/delay-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete delay rule",
    description="Delete an appointment delay rule."
)
async def delete_delay_rule(
    rule_id: str = Path(..., description="Delay rule ID (UUID)"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_appointment"))
):
    result = await db.execute(
        "DELETE FROM appointment_delay_rules WHERE id = $1::uuid", rule_id
    )

    if 'DELETE 0' in result:
        raise TranslatedException(ErrorCode.NOT_FOUND)

    return None


# =============================================================================
# TARIFF SUPPLEMENTS MANAGEMENT
# =============================================================================

class TariffSupplementCreate(BaseModel):
    """Create a new tariff supplement"""
    code: str = Field(..., min_length=1, max_length=50, pattern=r'^[A-Z][A-Z0-9_]*$')
    name_es: str = Field(..., min_length=1, max_length=255)
    amount: float = Field(..., gt=0)
    currency: str = Field(default="XAF", max_length=3)
    legal_reference: Optional[str] = Field(None, max_length=255)
    effective_from: Optional[str] = Field(None, description="Date in YYYY-MM-DD format")
    effective_to: Optional[str] = Field(None, description="Date in YYYY-MM-DD format")
    is_active: bool = Field(default=True)


class TariffSupplementUpdate(BaseModel):
    """Update an existing tariff supplement"""
    name_es: Optional[str] = Field(None, min_length=1, max_length=255)
    amount: Optional[float] = Field(None, gt=0)
    currency: Optional[str] = Field(None, max_length=3)
    legal_reference: Optional[str] = Field(None, max_length=255)
    effective_from: Optional[str] = Field(None, description="Date in YYYY-MM-DD format")
    effective_to: Optional[str] = Field(None, description="Date in YYYY-MM-DD format")
    is_active: Optional[bool] = None


class TariffSupplementResponse(BaseModel):
    """Response model for tariff supplement"""
    id: int
    code: str
    name_es: str
    amount: float
    currency: str
    legal_reference: Optional[str]
    effective_from: str
    effective_to: Optional[str]
    is_active: bool
    created_at: Optional[str]
    updated_at: Optional[str]


class WorkflowSupplementConfigCreate(BaseModel):
    """Add supplement to a workflow"""
    supplement_code: str = Field(..., min_length=1, max_length=50)
    quantity_per_request: int = Field(default=1, ge=1, le=100)
    is_required: bool = Field(default=True)
    is_active: bool = Field(default=True)


class WorkflowSupplementConfigUpdate(BaseModel):
    """Update workflow supplement configuration"""
    quantity_per_request: Optional[int] = Field(None, ge=1, le=100)
    is_required: Optional[bool] = None
    is_active: Optional[bool] = None


class WorkflowSupplementConfigResponse(BaseModel):
    """Response model for workflow supplement configuration"""
    id: int
    workflow_code: str
    supplement_code: str
    supplement_name: Optional[str] = None
    supplement_amount: Optional[float] = None
    quantity_per_request: int
    is_required: bool
    is_active: bool
    created_at: Optional[str]
    updated_at: Optional[str]


@router.get(
    "/supplements",
    response_model=List[TariffSupplementResponse],
    summary="List all tariff supplements",
    description="Get all configured tariff supplements (cédulas, pólizas, timbres, etc.)"
)
async def list_supplements(
    active_only: bool = Query(False, description="Filter active supplements only"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_tariff"))
):
    where_clause = "WHERE is_active = true" if active_only else ""
    query = f"""
        SELECT id, code, name_es, amount, currency, legal_reference,
               effective_from::text, effective_to::text, is_active,
               created_at::text, updated_at::text
        FROM tariff_supplements
        {where_clause}
        ORDER BY code
    """
    rows = await db.fetch(query)
    return [TariffSupplementResponse(**dict(row)) for row in rows]


@router.get(
    "/supplements/{code}",
    response_model=TariffSupplementResponse,
    summary="Get a single tariff supplement",
    description="Get details of a specific tariff supplement by code."
)
async def get_supplement(
    code: str = Path(..., description="Supplement code"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_tariff"))
):
    query = """
        SELECT id, code, name_es, amount, currency, legal_reference,
               effective_from::text, effective_to::text, is_active,
               created_at::text, updated_at::text
        FROM tariff_supplements
        WHERE code = $1
    """
    row = await db.fetchrow(query, code)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplement with code '{code}' not found"
        )
    return TariffSupplementResponse(**dict(row))


@router.post(
    "/supplements",
    response_model=TariffSupplementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tariff supplement",
    description="Create a new tariff supplement configuration."
)
async def create_supplement(
    data: TariffSupplementCreate,
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_tariff"))
):
    # Check if code already exists
    existing = await db.fetchrow(
        "SELECT code FROM tariff_supplements WHERE code = $1", data.code
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Supplement with code '{data.code}' already exists"
        )

    query = """
        INSERT INTO tariff_supplements (
            code, name_es, amount, currency, legal_reference,
            effective_from, effective_to, is_active, created_by
        )
        VALUES ($1, $2, $3, $4, $5, COALESCE($6::date, CURRENT_DATE), $7::date, $8, $9)
        RETURNING id, code, name_es, amount, currency, legal_reference,
                  effective_from::text, effective_to::text, is_active,
                  created_at::text, updated_at::text
    """
    row = await db.fetchrow(
        query,
        data.code,
        data.name_es,
        data.amount,
        data.currency,
        data.legal_reference,
        data.effective_from,
        data.effective_to,
        data.is_active,
        current_user.id
    )
    return TariffSupplementResponse(**dict(row))


@router.put(
    "/supplements/{code}",
    response_model=TariffSupplementResponse,
    summary="Update a tariff supplement",
    description="Update an existing tariff supplement."
)
async def update_supplement(
    code: str = Path(..., description="Supplement code"),
    data: TariffSupplementUpdate = None,
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_tariff"))
):
    # Build dynamic update query
    params = [code]
    updates = []

    if data.name_es is not None:
        params.append(data.name_es)
        updates.append(f"name_es = ${len(params)}")

    if data.amount is not None:
        params.append(data.amount)
        updates.append(f"amount = ${len(params)}")

    if data.currency is not None:
        params.append(data.currency)
        updates.append(f"currency = ${len(params)}")

    if data.legal_reference is not None:
        params.append(data.legal_reference if data.legal_reference else None)
        updates.append(f"legal_reference = ${len(params)}")

    if data.effective_from is not None:
        params.append(data.effective_from)
        updates.append(f"effective_from = ${len(params)}::date")

    if data.effective_to is not None:
        params.append(data.effective_to if data.effective_to else None)
        updates.append(f"effective_to = ${len(params)}::date")

    if data.is_active is not None:
        params.append(data.is_active)
        updates.append(f"is_active = ${len(params)}")

    if not updates:
        raise TranslatedException(ErrorCode.NO_FIELDS_TO_UPDATE)

    # Add updated_by and updated_at
    params.append(current_user.id)
    updates.append(f"updated_by = ${len(params)}")
    updates.append("updated_at = now()")

    query = f"""
        UPDATE tariff_supplements
        SET {', '.join(updates)}
        WHERE code = $1
        RETURNING id, code, name_es, amount, currency, legal_reference,
                  effective_from::text, effective_to::text, is_active,
                  created_at::text, updated_at::text
    """
    row = await db.fetchrow(query, *params)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplement with code '{code}' not found"
        )

    return TariffSupplementResponse(**dict(row))


@router.delete(
    "/supplements/{code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a tariff supplement",
    description="Delete a tariff supplement. Will fail if supplement is used in workflows."
)
async def delete_supplement(
    code: str = Path(..., description="Supplement code"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_tariff"))
):
    # Check if supplement is used in any workflow config
    usage = await db.fetchrow(
        "SELECT COUNT(*) as count FROM workflow_supplement_config WHERE supplement_code = $1",
        code
    )
    if usage and usage['count'] > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete supplement '{code}': it is used in {usage['count']} workflow(s). Remove from workflows first."
        )

    result = await db.execute(
        "DELETE FROM tariff_supplements WHERE code = $1", code
    )

    if 'DELETE 0' in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplement with code '{code}' not found"
        )

    return None


# =============================================================================
# WORKFLOW SUPPLEMENT CONFIG MANAGEMENT
# =============================================================================

@router.get(
    "/workflows/{workflow_code}/supplements",
    response_model=List[WorkflowSupplementConfigResponse],
    summary="List workflow supplements",
    description="Get all supplements configured for a specific workflow."
)
async def list_workflow_supplements(
    workflow_code: str = Path(..., description="Workflow code"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_tariff"))
):
    query = """
        SELECT wsc.id, wsc.workflow_code, wsc.supplement_code,
               ts.name_es as supplement_name, ts.amount as supplement_amount,
               wsc.quantity_per_request, wsc.is_required, wsc.is_active,
               wsc.created_at::text, wsc.updated_at::text
        FROM workflow_supplement_config wsc
        LEFT JOIN tariff_supplements ts ON ts.code = wsc.supplement_code
        WHERE wsc.workflow_code = $1
        ORDER BY wsc.supplement_code
    """
    rows = await db.fetch(query, workflow_code)
    return [WorkflowSupplementConfigResponse(**dict(row)) for row in rows]


@router.post(
    "/workflows/{workflow_code}/supplements",
    response_model=WorkflowSupplementConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add supplement to workflow",
    description="Add a tariff supplement to a workflow configuration."
)
async def add_workflow_supplement(
    workflow_code: str = Path(..., description="Workflow code"),
    data: WorkflowSupplementConfigCreate = None,
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_tariff"))
):
    # Check if supplement exists
    supplement = await db.fetchrow(
        "SELECT code, name_es, amount FROM tariff_supplements WHERE code = $1",
        data.supplement_code
    )
    if not supplement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplement with code '{data.supplement_code}' not found"
        )

    # Check if already configured for this workflow
    existing = await db.fetchrow(
        """SELECT id FROM workflow_supplement_config
           WHERE workflow_code = $1 AND supplement_code = $2""",
        workflow_code, data.supplement_code
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Supplement '{data.supplement_code}' is already configured for workflow '{workflow_code}'"
        )

    query = """
        INSERT INTO workflow_supplement_config (
            workflow_code, supplement_code, quantity_per_request, is_required, is_active
        )
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, workflow_code, supplement_code, quantity_per_request, is_required, is_active,
                  created_at::text, updated_at::text
    """
    row = await db.fetchrow(
        query,
        workflow_code,
        data.supplement_code,
        data.quantity_per_request,
        data.is_required,
        data.is_active
    )
    result = dict(row)
    result['supplement_name'] = supplement['name_es']
    result['supplement_amount'] = float(supplement['amount'])
    return WorkflowSupplementConfigResponse(**result)


@router.put(
    "/workflows/{workflow_code}/supplements/{supplement_code}",
    response_model=WorkflowSupplementConfigResponse,
    summary="Update workflow supplement config",
    description="Update the configuration of a supplement for a workflow."
)
async def update_workflow_supplement(
    workflow_code: str = Path(..., description="Workflow code"),
    supplement_code: str = Path(..., description="Supplement code"),
    data: WorkflowSupplementConfigUpdate = None,
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_tariff"))
):
    # Build dynamic update query
    params = [workflow_code, supplement_code]
    updates = []

    if data.quantity_per_request is not None:
        params.append(data.quantity_per_request)
        updates.append(f"quantity_per_request = ${len(params)}")

    if data.is_required is not None:
        params.append(data.is_required)
        updates.append(f"is_required = ${len(params)}")

    if data.is_active is not None:
        params.append(data.is_active)
        updates.append(f"is_active = ${len(params)}")

    if not updates:
        raise TranslatedException(ErrorCode.NO_FIELDS_TO_UPDATE)

    updates.append("updated_at = now()")

    query = f"""
        UPDATE workflow_supplement_config
        SET {', '.join(updates)}
        WHERE workflow_code = $1 AND supplement_code = $2
        RETURNING id, workflow_code, supplement_code, quantity_per_request, is_required, is_active,
                  created_at::text, updated_at::text
    """
    row = await db.fetchrow(query, *params)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplement '{supplement_code}' not found for workflow '{workflow_code}'"
        )

    # Get supplement details
    supplement = await db.fetchrow(
        "SELECT name_es, amount FROM tariff_supplements WHERE code = $1",
        supplement_code
    )
    result = dict(row)
    if supplement:
        result['supplement_name'] = supplement['name_es']
        result['supplement_amount'] = float(supplement['amount'])
    return WorkflowSupplementConfigResponse(**result)


@router.delete(
    "/workflows/{workflow_code}/supplements/{supplement_code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove supplement from workflow",
    description="Remove a supplement configuration from a workflow."
)
async def remove_workflow_supplement(
    workflow_code: str = Path(..., description="Workflow code"),
    supplement_code: str = Path(..., description="Supplement code"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_tariff"))
):
    result = await db.execute(
        """DELETE FROM workflow_supplement_config
           WHERE workflow_code = $1 AND supplement_code = $2""",
        workflow_code, supplement_code
    )

    if 'DELETE 0' in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplement '{supplement_code}' not found for workflow '{workflow_code}'"
        )

    return None


# ═══════════════════════════════════════════════════════════════
# MAINTENANCE - Cleanup Operations
# ═══════════════════════════════════════════════════════════════

class CleanupResponse(BaseModel):
    """Response model for cleanup operations"""
    deleted_requests: int = Field(..., description="Number of service requests deleted")
    deleted_documents: int = Field(..., description="Number of documents deleted")
    deleted_files: int = Field(..., description="Number of files deleted from storage")
    errors: List[str] = Field(default=[], description="Any errors encountered during cleanup")


@router.post(
    "/maintenance/cleanup-abandoned",
    response_model=CleanupResponse,
    summary="Clean up abandoned service requests",
    description="""
    Delete service requests that have been in DRAFT status for too long.

    **Purpose:**
    - Free up storage space from abandoned sessions
    - Remove orphan data from users who started but never completed requests
    - Maintain database hygiene

    **Default behavior:**
    - Deletes DRAFT requests older than 2 hours
    - Deletes associated documents from database
    - Deletes files from Firebase Storage

    **Recommended:**
    - Call this endpoint via Cloud Scheduler every hour
    - Or trigger manually when needed
    """
)
async def cleanup_abandoned_requests(
    max_age_hours: int = Query(2, ge=1, le=168, description="Maximum age in hours for DRAFT requests (1-168)"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_system"))
):
    """Clean up abandoned DRAFT requests older than max_age_hours"""
    from ..services.service_request_service import service_request_service

    stats = await service_request_service.cleanup_abandoned_requests(
        db=db,
        max_age_hours=max_age_hours
    )

    return CleanupResponse(**stats)


# ═══════════════════════════════════════════════════════════════
# TREASURY AGENT - Context & Payment Validation
# ═══════════════════════════════════════════════════════════════


from dataclasses import dataclass as _dataclass


@_dataclass(frozen=True)
class TreasuryAgentContext:
    """Treasury agent profile resolved once per HTTP request.

    Scoping hierarchy (strict, enforced after P8.2 refactor):
      - has_global_scope (treasury.view_all perm): see ALL entities + ALL sites
      - has_entity_global_scope (main-office supervisor, no view_all): see OWN
        entity + ALL its sites (filter UI may restrict)
      - site supervisor (is_supervisor, not main_office): OWN entity + OWN site
      - regular agent: OWN assignments only, OWN site

    Historical note: pre-P8.2 the `has_global_scope` property returned true for
    any (supervisor AND main_office) regardless of permission. That leaked data
    cross-entity for AYUNT/CAMARA supervisors once those entities started using
    the treasury validation flow (X2 bug). The property is now strict.
    """
    profile_id: Optional[str]
    entity_id: Optional[str]
    entity_code: Optional[str]
    entity_location_id: Optional[str]
    is_supervisor: bool
    is_main_office: bool
    has_treasury_view_all: bool
    user_id: str

    @property
    def has_profile(self) -> bool:
        return self.profile_id is not None

    @property
    def has_global_scope(self) -> bool:
        """Cross-entity global view. Granted ONLY via explicit treasury.view_all
        permission (admin, super_admin, supervisor_tesoro)."""
        return self.has_treasury_view_all

    @property
    def has_entity_global_scope(self) -> bool:
        """Main-office supervisor without global perm: sees ALL sites of own
        entity. The entity filter must be applied by callers; only the
        auto-site-scoping is relaxed here."""
        return (
            self.is_supervisor
            and self.is_main_office
            and not self.has_treasury_view_all
        )

    def get_effective_location(self, explicit_location_id: Optional[str] = None) -> Optional[str]:
        """Resolve effective entity_location_id for site-scoping.

        - Global scope (treasury.view_all): explicit param wins, else None (all).
        - Entity-global scope (main-office supervisor): explicit param wins,
          else None (all sites of own entity; entity filter applied separately).
        - Site-level supervisor / regular agent: ALWAYS own site (explicit param
          ignored — users cannot escape their site).
        """
        if self.has_global_scope or self.has_entity_global_scope:
            return explicit_location_id or None
        if self.entity_location_id:
            return self.entity_location_id
        return explicit_location_id or None


async def _get_treasury_context(db: asyncpg.Connection, user_id) -> TreasuryAgentContext:
    """Resolve treasury agent context in 1 SQL query (profile + entity + permission)."""
    row = await db.fetchrow("""
        SELECT
            ap.id::text AS profile_id,
            ap.entity_id::text AS entity_id,
            e.code AS entity_code,
            ap.entity_location_id::text,
            COALESCE(ap.is_supervisor, false) AS is_supervisor,
            COALESCE(el.is_main_office, false) AS is_main_office,
            EXISTS(
                SELECT 1 FROM user_permissions up
                JOIN permissions p ON p.id = up.permission_id
                WHERE up.user_id = ap.user_id AND p.name = 'treasury.view_all'
                UNION
                SELECT 1 FROM roles r
                JOIN role_permissions rp ON rp.role_id = r.id
                JOIN permissions p ON p.id = rp.permission_id
                JOIN users u2 ON u2.role_id = r.id
                WHERE u2.id = ap.user_id AND p.name = 'treasury.view_all'
            ) AS has_treasury_view_all
        FROM agent_profiles ap
        LEFT JOIN entities e ON e.id = ap.entity_id
        LEFT JOIN entity_locations el ON el.id = ap.entity_location_id
        WHERE ap.user_id = $1::uuid AND ap.is_active = true
        LIMIT 1
    """, user_id)

    if row:
        return TreasuryAgentContext(
            profile_id=row['profile_id'],
            entity_id=row['entity_id'],
            entity_code=row['entity_code'],
            entity_location_id=row['entity_location_id'],
            is_supervisor=row['is_supervisor'],
            is_main_office=row['is_main_office'],
            has_treasury_view_all=row['has_treasury_view_all'],
            user_id=str(user_id),
        )
    return TreasuryAgentContext(
        profile_id=None,
        entity_id=None,
        entity_code=None,
        entity_location_id=None,
        is_supervisor=False,
        is_main_office=False,
        has_treasury_view_all=False,
        user_id=str(user_id),
    )


def _authorize_payment_action(tctx: TreasuryAgentContext, payment: Mapping) -> None:
    """Raise 403 if the current agent cannot act (validate/reject/escalate) on
    this payment.

    Authorization matrix (P8.2-B1 security hotfix — closes the hole exploited
    on 2026-04-14 where tesoreria.ge validated 2 AYUNT payments worth 583 650
    XAF despite being a TESORO agent without global scope):

        1. Global scope (treasury.view_all): any payment, any entity
        2. Entity supervisor: payments of own entity_code
        3. Assigned agent: only own assigned payments

    Permission check (treasury.validate_payment) is already applied via the
    FastAPI dependency. This helper adds the per-payment scope check that the
    endpoints previously lacked.
    """
    if tctx.has_global_scope:
        return

    payment_entity = payment.get("entity_code")
    assigned_agent_id = payment.get("assigned_agent_id")

    # Entity supervisor: sees/acts on anything in own entity
    if tctx.is_supervisor and payment_entity and tctx.entity_code == payment_entity:
        return

    # Regular agent: only own assigned payments
    if (
        tctx.profile_id
        and assigned_agent_id
        and str(assigned_agent_id) == str(tctx.profile_id)
    ):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"Not authorized: payment entity {payment_entity!r} is outside "
            f"your scope (role entity {tctx.entity_code!r}, "
            f"assigned={assigned_agent_id is not None})"
        ),
    )


async def _authorize_export_action(
    db: asyncpg.Connection,
    tctx: TreasuryAgentContext,
    export_id: str,
) -> None:
    """Raise 403 if the current agent cannot read/download/manage this export.

    Background (P7 hotfix — 2026-05-06):
      `treasury_exports` has no `entity_code` column. Scope is derived from
      `treasury_exports.requested_by` -> `agent_profiles.entity_id` ->
      `entities.code`. This is a best-effort check: if the requester has no
      active agent_profile (e.g. global admin without profile), the export
      is treated as global and only visible to global-scope viewers.

    Authorization matrix:
      1. Global scope (treasury.view_all): any export
      2. Entity supervisor / scoped agent: only exports whose requester
         belongs to the same entity (e.code).
    """
    if tctx.has_global_scope:
        # Verify export exists at minimum — return 404 instead of 403 if missing
        exists = await db.fetchval(
            "SELECT 1 FROM treasury_exports WHERE id = $1::uuid", export_id
        )
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Export not found: {export_id}",
            )
        return

    # Prefer the denormalized requested_by_entity_code column (mig 333).
    # Fallback to JOIN agent_profiles only when the column is NULL (legacy
    # rows pre-migration, or rows generated before the INSERT-time wiring).
    # This makes the scope check independent of the agent_profile.is_active
    # state, fixing the audit's "inactive profile -> 403" edge case.
    row = await db.fetchrow(
        """
        SELECT
            te.id,
            COALESCE(
                te.requested_by_entity_code,
                (
                    SELECT e.code
                    FROM agent_profiles ap
                    JOIN entities e ON e.id = ap.entity_id
                    WHERE ap.user_id = te.requested_by
                    ORDER BY ap.is_active DESC, ap.created_at DESC
                    LIMIT 1
                )
            ) AS owner_entity_code
        FROM treasury_exports te
        WHERE te.id = $1::uuid
        LIMIT 1
        """,
        export_id,
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export not found: {export_id}",
        )

    owner_entity_code = row["owner_entity_code"]
    if not tctx.entity_code:
        # Caller has no entity scope and no global perm: deny by default.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Not authorized: export {export_id} requires entity scope "
                f"(caller has none, owner entity {owner_entity_code!r})"
            ),
        )

    # If the requester had no agent_profile (owner_entity_code is NULL), only
    # global admins can see it — already handled above. Scoped users get 403.
    if owner_entity_code is None or owner_entity_code != tctx.entity_code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Not authorized: export entity {owner_entity_code!r} is "
                f"outside your scope (role entity {tctx.entity_code!r})"
            ),
        )


async def _authorize_anomaly_action(
    db: asyncpg.Connection,
    tctx: TreasuryAgentContext,
    anomaly_id: str,
) -> None:
    """Raise 403 if the current agent cannot read/update this anomaly.

    Polymorphic check (P7 hotfix — 2026-05-06):
      `payment_anomalies` is polymorphic (entity_type + entity_id). For
      entity_type='service_payment', the linked payment's entity_code drives
      scope. For other entity_types (bank_transaction, reconciliation),
      treasury domain is shared — only global-scope users see them, scoped
      users are denied (defensive default).
    """
    if tctx.has_global_scope:
        exists = await db.fetchval(
            "SELECT 1 FROM payment_anomalies WHERE id = $1::uuid", anomaly_id
        )
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Anomaly not found: {anomaly_id}",
            )
        return

    row = await db.fetchrow(
        """
        SELECT pa.id, pa.entity_type, pa.entity_id,
               sp.entity_code AS payment_entity_code
        FROM payment_anomalies pa
        LEFT JOIN service_payments sp
            ON pa.entity_type = 'service_payment' AND sp.id = pa.entity_id
        WHERE pa.id = $1::uuid
        LIMIT 1
        """,
        anomaly_id,
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anomaly not found: {anomaly_id}",
        )

    if not tctx.entity_code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Not authorized: anomaly {anomaly_id} requires entity scope"
            ),
        )

    # Service-payment anomaly: must share entity_code with caller
    if row["entity_type"] == "service_payment":
        payment_entity = row["payment_entity_code"]
        if payment_entity is None or payment_entity != tctx.entity_code:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Not authorized: anomaly entity {payment_entity!r} is "
                    f"outside your scope (role entity {tctx.entity_code!r})"
                ),
            )
        return

    # Non-payment anomaly (bank_transaction, reconciliation): treasury-shared
    # domain — only global-scope users may act. Scoped users denied.
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"Not authorized: anomaly type {row['entity_type']!r} is shared "
            f"treasury domain — requires treasury.view_all permission"
        ),
    )


# Backward-compat wrappers (used by endpoints not yet migrated)
async def get_agent_profile_id(db: asyncpg.Connection, user_id: str) -> Optional[str]:
    """Get agent_profile_id from user_id. Prefer _get_treasury_context for new code."""
    result = await db.fetchval(
        "SELECT id FROM agent_profiles WHERE user_id = $1::uuid AND is_active = true",
        user_id
    )
    return str(result) if result else None


    # is_treasury_supervisor() and _resolve_treasury_location_scope() removed —
    # fully replaced by _get_treasury_context() + TreasuryAgentContext methods.


class PaymentValidationRequest(BaseModel):
    """Request model for agent validation."""
    comment: Optional[str] = Field(None, max_length=500, description="Validation comment")


class PaymentRejectionRequest(BaseModel):
    """Request model for agent rejection."""
    reason: str = Field(..., min_length=10, max_length=500, description="Rejection reason")


class PaymentEscalationRequest(BaseModel):
    """Request model for manual payment escalation to supervisor."""
    reason: str = Field(..., min_length=10, max_length=500, description="Escalation reason")
    level: str = Field("medium", description="Escalation level: low, medium, high, critical")


class BatchValidateResponse(BaseModel):
    """Response for batch payment validation."""
    success: bool
    payments_validated: int
    batch_reference: Optional[str] = None
    error: Optional[str] = None


class PendingPaymentResponse(BaseModel):
    """Response for a pending payment."""
    payment_id: str
    payment_reference: str
    service_request_id: Optional[str] = None
    request_reference: Optional[str] = None
    workflow_code: Optional[str] = None
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_phone: Optional[str] = None
    payment_method: str
    total_amount: float
    currency: str = "XAF"
    calculation_details: Optional[Dict[str, Any]] = None
    workflow_status: str
    # Timestamps
    submitted_at: Optional[str] = None
    created_at: str
    hours_waiting: float
    # Additional fields for frontend compatibility
    base_amount: Optional[float] = None
    penalties: Optional[float] = None
    discounts: Optional[float] = None
    sla_target_date: Optional[str] = None
    # Assigned agent info (for supervisor view)
    assigned_agent_id: Optional[str] = None
    assigned_agent_name: Optional[str] = None
    # Site info
    location_name: Optional[str] = None
    # Batch info (for batch payment grouping)
    batch_id: Optional[str] = None
    batch_reference: Optional[str] = None
    batch_total_items: Optional[int] = None
    # Beneficiary info (from service_request form_data, distinct from account holder)
    beneficiary_name: Optional[str] = None
    # Reconciliation info
    bank_transaction_id: Optional[str] = None
    validated_at: Optional[str] = None
    # Escalation info
    escalation_level: Optional[str] = None
    escalation_reason: Optional[str] = None
    escalated_at: Optional[str] = None
    sla_escalated: Optional[bool] = None
    # Bundle-specific fields (entity split + company context)
    entity_code: Optional[str] = None
    entity_name: Optional[str] = None
    company_name: Optional[str] = None
    registration_number: Optional[str] = None
    sector_actividad: Optional[str] = None
    commerce_type: Optional[str] = None
    zone_code: Optional[str] = None
    zone_tier: Optional[str] = None
    city_name: Optional[str] = None
    obligation_count: Optional[int] = None
    obligations: Optional[List[Dict[str, Any]]] = None


class PendingPaymentsListResponse(BaseModel):
    """List of pending payments."""
    payments: List[PendingPaymentResponse]
    total: int
    page: int = 1
    page_size: int = 20
    is_supervisor: bool = False
    is_main_office: bool = False
    treasury_agents: Optional[List[Dict[str, Any]]] = None


class PaymentActionResponse(BaseModel):
    """Response for payment actions."""
    success: bool
    payment_id: str
    status: str
    message_es: Optional[str] = None
    error: Optional[str] = None
    receipt_number: Optional[str] = None
    receipt_url: Optional[str] = None


@router.get(
    "/treasury/payments/pending",
    response_model=PendingPaymentsListResponse,
    summary="Get pending payments for validation",
    description="""
    Get list of payments pending Treasury Agent validation.

    **Access Control:**
    - Treasury Agents: See only their assigned payments
    - Supervisors: See all payments (can filter by agent)

    **Filters:**
    - payment_method: 'cash' or 'check' (default: all manual methods)
    - workflow_status: Filter by workflow status
    - agent_id: (Supervisor only) Filter by assigned agent

    **Permissions:**
    - Requires 'treasury.validate_payment' permission
    """
)
async def get_pending_payments(
    payment_method: Optional[str] = Query(None, description="Filter by payment method"),
    workflow_status: Optional[str] = Query(
        "pending_agent_review",
        description="Filter by workflow status. Use 'all' for all statuses, 'processed' for non-pending statuses."
    ),
    agent_profile_id: Optional[str] = Query(None, description="(Supervisor only) Filter by assigned agent_profile_id"),
    entity_location_id: Optional[str] = Query(None, description="Filter by entity_location (site)"),
    date_from: Optional[str] = Query(None, description="Filter payments from this date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter payments up to this date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.validate_payment"))
):
    """Get payments pending Treasury Agent validation"""
    from datetime import datetime, timezone
    from loguru import logger

    try:
        user_id = current_user.id
        logger.info(f"[Treasury] get_pending_payments called by user {user_id}: method={payment_method}, status={workflow_status}, page={page}")

        # Single query: profile + permissions + site scope
        tctx = await _get_treasury_context(db, user_id)
        is_supervisor = tctx.has_global_scope or tctx.is_supervisor
        current_agent_profile_id = tctx.profile_id

        logger.info(f"[Treasury] User {user_id}: is_supervisor={is_supervisor}, agent_profile_id={current_agent_profile_id}")

        # Calculate offset from page
        offset = (page - 1) * limit

        # Build query
        where_clauses = []
        params = []
        param_idx = 1

        # workflow_status=all → no status filter (history mode)
        # workflow_status=processed → only resolved statuses (transactions history)
        effective_status = workflow_status or "pending_agent_review"
        if effective_status == "processed":
            where_clauses.append(
                "sp.workflow_status IN ('approved_by_agent', 'rejected_by_agent', 'completed', 'cancelled_by_agent', 'cancelled_by_user', 'expired')"
            )
        elif effective_status != "all":
            where_clauses.append(f"sp.workflow_status = ${param_idx}")
            params.append(effective_status)
            param_idx += 1

        if payment_method:
            where_clauses.append(f"sp.payment_method = ${param_idx}")
            params.append(payment_method)
            param_idx += 1
        elif effective_status not in ("all", "processed"):
            # Default: only manual validation methods (for pending view)
            # In history/processed mode, show all payment methods
            where_clauses.append("sp.payment_method IN ('cash', 'check')")

        # Date range filtering
        if date_from:
            where_clauses.append(f"sp.created_at >= ${param_idx}::date")
            params.append(date_from)
            param_idx += 1
        if date_to:
            where_clauses.append(f"sp.created_at < (${param_idx}::date + INTERVAL '1 day')")
            params.append(date_to)
            param_idx += 1

        # Agent-based filtering + site scoping (uses pre-resolved tctx)
        # Scope hierarchy (P8.2 refactor):
        #   - Global (treasury.view_all): all entities, all sites, filterable
        #   - Entity-global (main-office supervisor, no view_all): own entity, all
        #     its sites, filterable by site
        #   - Site-level supervisor: own entity, own site (forced)
        #   - Regular agent: own assignments only
        if is_supervisor:
            effective_location_id = tctx.get_effective_location(entity_location_id)

            # Cross-entity scoping: only view_all holders see other entities.
            # Entity-scoped supervisors (AYUNT, CAMARA, site tesoro) are pinned
            # to the payment's own entity via sp.entity_code (ownership), not
            # via assigned_ap.entity_id (current assignee). This prevents
            # visibility loss when a payment gets cross-entity reassigned and
            # keeps the filter based on the economic owner of the payment.
            if not tctx.has_global_scope and tctx.entity_code:
                where_clauses.append(f"sp.entity_code = ${param_idx}")
                params.append(tctx.entity_code)
                param_idx += 1
                logger.info(f"[Treasury] Entity-scoped supervisor: entity_code={tctx.entity_code}")

            # Supervisor can filter by specific agent or see all
            if agent_profile_id:
                where_clauses.append(f"sp.assigned_agent_id = ${param_idx}::uuid")
                params.append(agent_profile_id)
                param_idx += 1
                logger.info(f"[Treasury] Supervisor filtering by agent_profile_id: {agent_profile_id}")
            # Filter by agent location (NOT sr.entity_location_id which is the workflow entity)
            if effective_location_id:
                where_clauses.append(f"assigned_ap.entity_location_id = ${param_idx}::uuid")
                params.append(effective_location_id)
                param_idx += 1
                logger.info(f"[Treasury] Filtering by agent location: {effective_location_id}")
        else:
            # Regular agent sees only their assigned payments
            if current_agent_profile_id:
                where_clauses.append(f"sp.assigned_agent_id = ${param_idx}::uuid")
                params.append(str(current_agent_profile_id))
                param_idx += 1
                logger.info(f"[Treasury] Agent filtering by own profile: {current_agent_profile_id}")
            else:
                # User has permission but no agent profile - show nothing
                logger.warning(f"[Treasury] User {user_id} has no agent_profile, showing empty results")
                return PendingPaymentsListResponse(payments=[], total=0, page=page, page_size=limit)

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

        query = f"""
            SELECT
                sp.id AS payment_id,
                sp.payment_reference,
                sp.service_request_id,
                sr.reference AS request_reference,
                sr.workflow_code,
                sp.user_id,
                u.first_name || ' ' || u.last_name AS user_name,
                u.email AS user_email,
                u.phone_number AS user_phone,
                sp.payment_method,
                sp.total_amount,
                sp.base_amount,
                sp.penalties,
                sp.discounts,
                sp.currency,
                sp.calculation_details,
                sp.workflow_status,
                sp.sla_target_date,
                sr.submitted_at,
                sp.created_at,
                EXTRACT(EPOCH FROM (NOW() - sp.created_at)) / 3600 AS hours_waiting,
                sp.assigned_agent_id,
                COALESCE(assigned_user.full_name, assigned_user.first_name || ' ' || assigned_user.last_name) AS assigned_agent_name,
                el_site.location_name AS location_name,
                sp.batch_id,
                br.reference AS batch_reference,
                br.total_items AS batch_total_items,
                sp.escalation_level::text AS escalation_level,
                sp.escalation_reason,
                sp.escalated_at,
                sp.sla_escalated,
                sp.bank_transaction_id,
                sp.validated_at,
                COALESCE(
                    sr.form_data->>'nombre_completo',
                    NULLIF(TRIM(COALESCE(sr.form_data->>'apellidos', '') || ' ' || COALESCE(sr.form_data->>'nombres', '')), ''),
                    NULLIF(TRIM(COALESCE(sr.form_data->>'propietario_apellidos', '') || ' ' || COALESCE(sr.form_data->>'propietario_nombres', '')), ''),
                    u.first_name || ' ' || u.last_name
                ) AS beneficiary_name,
                sp.entity_code,
                ent.name AS entity_name,
                comp.legal_name AS company_name,
                comp.registration_number,
                comp.sector_actividad,
                comp.commerce_type,
                cz.zone_code,
                cz.zone_tier,
                city.name AS city_name,
                (SELECT COUNT(*) FROM license_obligations lo2
                 WHERE lo2.payment_id = sp.id) AS obligation_count
            FROM service_payments sp
            LEFT JOIN service_requests sr ON sr.id = sp.service_request_id
            LEFT JOIN users u ON u.id = sp.user_id
            LEFT JOIN agent_profiles assigned_ap ON assigned_ap.id = sp.assigned_agent_id
            LEFT JOIN users assigned_user ON assigned_user.id = assigned_ap.user_id
            LEFT JOIN entity_locations el_site ON el_site.id = assigned_ap.entity_location_id
            LEFT JOIN batch_requests br ON br.id = sp.batch_id
            LEFT JOIN entities ent ON ent.code = sp.entity_code
            LEFT JOIN companies comp ON comp.id = sr.company_id
            LEFT JOIN commercial_licenses cl ON cl.id = sr.commercial_license_id
            LEFT JOIN commerce_zones cz ON cz.id = cl.zone_id
            LEFT JOIN cities city ON city.id = cl.city_id
            WHERE {where_sql}
            ORDER BY sp.created_at ASC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])

        logger.debug(f"[Treasury] Executing query with params: {params[:3]}...")
        rows = await db.fetch(query, *params)
        logger.info(f"[Treasury] Found {len(rows)} payments")

        # Get total count (must include same JOINs as main query for where_sql references)
        count_query = f"""
            SELECT COUNT(*) FROM service_payments sp
            LEFT JOIN service_requests sr ON sr.id = sp.service_request_id
            LEFT JOIN agent_profiles assigned_ap ON assigned_ap.id = sp.assigned_agent_id
            WHERE {where_sql}
        """
        total = await db.fetchval(count_query, *params[:param_idx-1])

        payments = []
        for idx, row in enumerate(rows):
            try:
                # Log raw values for debugging
                logger.debug(f"[Treasury] Processing row {idx}: payment_id={row['payment_id']}, payment_method={row['payment_method']}, workflow_status={row['workflow_status']}")

                payment = PendingPaymentResponse(
                    payment_id=str(row["payment_id"]),
                    payment_reference=row["payment_reference"],
                    service_request_id=str(row["service_request_id"]) if row["service_request_id"] else None,
                    request_reference=row["request_reference"],
                    workflow_code=row["workflow_code"],
                    user_id=str(row["user_id"]),
                    user_name=row["user_name"],
                    user_email=row["user_email"],
                    user_phone=row.get("user_phone"),
                    payment_method=row["payment_method"],
                    total_amount=float(row["total_amount"]),
                    base_amount=float(row["base_amount"]) if row["base_amount"] else None,
                    penalties=float(row["penalties"]) if row["penalties"] else None,
                    discounts=float(row["discounts"]) if row["discounts"] else None,
                    currency=row["currency"],
                    # Parse JSON string if needed (asyncpg may return JSONB as string)
                    calculation_details=json.loads(row["calculation_details"]) if isinstance(row["calculation_details"], str) else row["calculation_details"],
                    workflow_status=row["workflow_status"],
                    submitted_at=row["submitted_at"].isoformat() if row["submitted_at"] else None,
                    sla_target_date=row["sla_target_date"].isoformat() if row["sla_target_date"] else None,
                    created_at=row["created_at"].isoformat(),
                    hours_waiting=float(row["hours_waiting"] or 0),
                    assigned_agent_id=str(row["assigned_agent_id"]) if row["assigned_agent_id"] else None,
                    assigned_agent_name=row["assigned_agent_name"],
                    location_name=row.get("location_name"),
                    batch_id=str(row["batch_id"]) if row["batch_id"] else None,
                    batch_reference=row["batch_reference"],
                    batch_total_items=row["batch_total_items"],
                    beneficiary_name=row.get("beneficiary_name"),
                    bank_transaction_id=str(row["bank_transaction_id"]) if row["bank_transaction_id"] else None,
                    validated_at=row["validated_at"].isoformat() if row["validated_at"] else None,
                    escalation_level=row["escalation_level"],
                    escalation_reason=row["escalation_reason"],
                    escalated_at=row["escalated_at"].isoformat() if row["escalated_at"] else None,
                    sla_escalated=row["sla_escalated"],
                    entity_code=row.get("entity_code"),
                    entity_name=row.get("entity_name"),
                    company_name=row.get("company_name"),
                    registration_number=row.get("registration_number"),
                    sector_actividad=row.get("sector_actividad"),
                    commerce_type=row.get("commerce_type"),
                    zone_code=row.get("zone_code"),
                    zone_tier=row.get("zone_tier"),
                    city_name=row.get("city_name"),
                    obligation_count=row.get("obligation_count"),
                )
                payments.append(payment)
            except Exception as row_error:
                logger.error(f"[Treasury] Error processing row {idx}: {row_error}")
                logger.error(f"[Treasury] Raw row data: payment_id={row['payment_id']}, payment_method={row['payment_method']}, workflow_status={row['workflow_status']}, total_amount={row['total_amount']}")
                raise

        logger.info(f"[Treasury] Successfully built {len(payments)} payment responses")

        # Batch-fetch obligations for bundle payments (single query, no N+1)
        bundle_payment_ids = [p.payment_id for p in payments if p.workflow_code == "BUNDLE_PAYMENT"]
        if bundle_payment_ids:
            obl_rows = await db.fetch("""
                SELECT lo.payment_id::text, fs.name_es, lo.amount, lo.fee_type
                FROM license_obligations lo
                LEFT JOIN fiscal_services fs ON fs.id = lo.fiscal_service_id
                WHERE lo.payment_id = ANY($1::uuid[])
                ORDER BY lo.payment_id, fs.name_es
            """, bundle_payment_ids)
            # Group by payment_id
            obl_map: Dict[str, list] = {}
            for orow in obl_rows:
                pid = orow["payment_id"]
                obl_map.setdefault(pid, []).append({
                    "name": orow["name_es"] or "—",
                    "amount": float(orow["amount"]) if orow["amount"] else 0,
                    "fee_type": orow["fee_type"],
                })
            for p in payments:
                if p.payment_id in obl_map:
                    p.obligations = obl_map[p.payment_id]

        # For supervisors, include agent list for reassign dropdown.
        # Scope:
        #   - Global supervisor (treasury.view_all): all entities (no filter)
        #   - Entity-scoped supervisor: only agents of own entity
        #   - Site supervisor: additionally restricted to own site
        agents_list = None
        if is_supervisor:
            dropdown_params: list = []
            dropdown_where = ["ap.is_active = true", "ap.is_supervisor = false"]

            if not tctx.has_global_scope and tctx.entity_id:
                dropdown_where.append(f"ap.entity_id = ${len(dropdown_params) + 1}::uuid")
                dropdown_params.append(tctx.entity_id)

            if tctx.has_profile and not tctx.is_main_office and tctx.entity_location_id:
                dropdown_where.append(f"ap.entity_location_id = ${len(dropdown_params) + 1}::uuid")
                dropdown_params.append(str(tctx.entity_location_id))

            dropdown_sql = f"""
                SELECT ap.id, u.full_name
                FROM agent_profiles ap
                JOIN users u ON u.id = ap.user_id
                WHERE {' AND '.join(dropdown_where)}
                ORDER BY u.full_name
            """
            agent_rows = await db.fetch(dropdown_sql, *dropdown_params)
            agents_list = [{"id": str(r["id"]), "name": r["full_name"]} for r in agent_rows]

        response = PendingPaymentsListResponse(
            payments=payments,
            total=total or 0,
            page=page,
            page_size=limit,
            is_supervisor=is_supervisor,
            is_main_office=tctx.is_main_office if tctx.has_profile else False,
            treasury_agents=agents_list,
        )

        logger.info(f"[Treasury] Returning response with {len(response.payments)} payments")
        return response

    except Exception as e:
        logger.error(f"[Treasury] Error in get_pending_payments: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"[Treasury] Traceback: {traceback.format_exc()}")
        raise


# ═══════════════════════════════════════════════════════════════
# MY ESCALATIONS (must be before {payment_id} to avoid path conflict)
# ═══════════════════════════════════════════════════════════════


@router.get(
    "/treasury/payments/my-escalations",
    response_model=PendingPaymentsListResponse,
    summary="Get payments escalated by current agent",
    description="""
    Get list of payments that the current agent has escalated.

    **Permissions:**
    - Requires 'treasury.validate_payment' permission
    """
)
async def get_my_payment_escalations(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.validate_payment"))
):
    """Get payments escalated by the current agent"""
    from loguru import logger

    tctx = await _get_treasury_context(db, current_user.id)
    if not tctx.has_profile:
        no_agent_profile()
    agent_profile_id = tctx.profile_id
    is_supervisor = tctx.has_global_scope or tctx.is_supervisor

    try:
        offset = (page - 1) * limit

        rows = await db.fetch("""
            SELECT
                sp.id AS payment_id,
                sp.payment_reference,
                sp.service_request_id,
                sr.reference AS request_reference,
                sr.workflow_code,
                sp.user_id,
                u.first_name || ' ' || u.last_name AS user_name,
                u.email AS user_email,
                u.phone_number AS user_phone,
                sp.payment_method,
                sp.total_amount,
                sp.base_amount,
                sp.penalties,
                sp.discounts,
                sp.currency,
                sp.calculation_details,
                sp.workflow_status,
                sp.sla_target_date,
                sr.submitted_at,
                sp.created_at,
                EXTRACT(EPOCH FROM (NOW() - sp.created_at)) / 3600 AS hours_waiting,
                sp.assigned_agent_id,
                COALESCE(assigned_user.full_name, assigned_user.first_name || ' ' || assigned_user.last_name) AS assigned_agent_name,
                el_site.location_name AS location_name,
                sp.batch_id,
                br.reference AS batch_reference,
                br.total_items AS batch_total_items,
                sp.escalation_level::text AS escalation_level,
                sp.escalation_reason,
                sp.escalated_at,
                sp.sla_escalated
            FROM service_payments sp
            LEFT JOIN service_requests sr ON sr.id = sp.service_request_id
            LEFT JOIN users u ON u.id = sp.user_id
            LEFT JOIN agent_profiles assigned_ap ON assigned_ap.id = sp.assigned_agent_id
            LEFT JOIN users assigned_user ON assigned_user.id = assigned_ap.user_id
            LEFT JOIN entity_locations el_site ON el_site.id = assigned_ap.entity_location_id
            LEFT JOIN batch_requests br ON br.id = sp.batch_id
            WHERE sp.assigned_agent_id = $1
              AND sp.escalated_to_agent_id IS NOT NULL
            ORDER BY sp.escalated_at DESC NULLS LAST, sp.created_at DESC
            LIMIT $2 OFFSET $3
        """, agent_profile_id, limit, offset)

        total = await db.fetchval("""
            SELECT COUNT(*) FROM service_payments
            WHERE assigned_agent_id = $1
              AND escalated_to_agent_id IS NOT NULL
        """, agent_profile_id)

        payments = []
        for row in rows:
            payment = PendingPaymentResponse(
                payment_id=str(row["payment_id"]),
                payment_reference=row["payment_reference"],
                service_request_id=str(row["service_request_id"]) if row["service_request_id"] else None,
                request_reference=row["request_reference"],
                workflow_code=row["workflow_code"],
                user_id=str(row["user_id"]),
                user_name=row["user_name"],
                user_email=row["user_email"],
                payment_method=row["payment_method"],
                total_amount=float(row["total_amount"]),
                base_amount=float(row["base_amount"]) if row["base_amount"] else None,
                penalties=float(row["penalties"]) if row["penalties"] else None,
                discounts=float(row["discounts"]) if row["discounts"] else None,
                currency=row["currency"],
                calculation_details=json.loads(row["calculation_details"]) if isinstance(row["calculation_details"], str) else row["calculation_details"],
                workflow_status=row["workflow_status"],
                submitted_at=row["submitted_at"].isoformat() if row["submitted_at"] else None,
                sla_target_date=row["sla_target_date"].isoformat() if row["sla_target_date"] else None,
                created_at=row["created_at"].isoformat(),
                hours_waiting=float(row["hours_waiting"] or 0),
                assigned_agent_id=str(row["assigned_agent_id"]) if row["assigned_agent_id"] else None,
                assigned_agent_name=row["assigned_agent_name"],
                location_name=row.get("location_name"),
                batch_id=str(row["batch_id"]) if row["batch_id"] else None,
                batch_reference=row["batch_reference"],
                batch_total_items=row["batch_total_items"],
                escalation_level=row["escalation_level"],
                escalation_reason=row["escalation_reason"],
                escalated_at=row["escalated_at"].isoformat() if row["escalated_at"] else None,
                sla_escalated=row["sla_escalated"],
            )
            payments.append(payment)

        return PendingPaymentsListResponse(
            payments=payments,
            total=total or 0,
            page=page,
            page_size=limit,
            is_supervisor=is_supervisor,
            is_main_office=tctx.is_main_office,
        )

    except Exception as e:
        logger.error(f"[Treasury] Error getting escalations: {e}", exc_info=True)
        raise


@router.get(
    "/treasury/payments/{payment_id}",
    response_model=PendingPaymentResponse,
    summary="Get single payment details",
    description="""
    Get details of a specific payment by ID.

    **Permissions:**
    - Requires 'treasury.validate_payment' permission
    """
)
async def get_payment_details(
    payment_id: str = Path(..., description="Payment UUID"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.validate_payment"))
):
    """Get single payment details for Treasury Agent review"""
    query = """
        SELECT
            sp.id AS payment_id,
            sp.payment_reference,
            sp.service_request_id,
            sr.reference AS request_reference,
            sr.workflow_code,
            sp.user_id,
            u.first_name || ' ' || u.last_name AS user_name,
            u.email AS user_email,
            sp.payment_method,
            sp.total_amount,
            sp.base_amount,
            sp.penalties,
            sp.discounts,
            sp.currency,
            sp.calculation_details,
            sp.workflow_status,
            sp.sla_target_date,
            sp.created_at,
            EXTRACT(EPOCH FROM (NOW() - sp.created_at)) / 3600 AS hours_waiting,
            sp.batch_id,
            br.reference AS batch_reference,
            br.total_items AS batch_total_items,
            sp.escalation_level::text AS escalation_level,
            sp.escalation_reason,
            sp.escalated_at,
            sp.sla_escalated,
            COALESCE(
                sr.form_data->>'nombre_completo',
                NULLIF(TRIM(COALESCE(sr.form_data->>'apellidos', '') || ' ' || COALESCE(sr.form_data->>'nombres', '')), ''),
                NULLIF(TRIM(COALESCE(sr.form_data->>'propietario_apellidos', '') || ' ' || COALESCE(sr.form_data->>'propietario_nombres', '')), ''),
                u.first_name || ' ' || u.last_name
            ) AS beneficiary_name,
            sp.assigned_agent_id,
            sp.entity_code,
            COALESCE(assigned_user.full_name, assigned_user.first_name || ' ' || assigned_user.last_name) AS assigned_agent_name
        FROM service_payments sp
        LEFT JOIN service_requests sr ON sr.id = sp.service_request_id
        LEFT JOIN users u ON u.id = sp.user_id
        LEFT JOIN agent_profiles assigned_ap ON assigned_ap.id = sp.assigned_agent_id
        LEFT JOIN users assigned_user ON assigned_user.id = assigned_ap.user_id
        LEFT JOIN batch_requests br ON br.id = sp.batch_id
        WHERE sp.id = $1::uuid
    """
    row = await db.fetchrow(query, payment_id)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment not found: {payment_id}"
        )

    # P7 security (2026-05-06): scope check by entity. Without this, any
    # treasury-permitted user could read any payment's details by UUID.
    tctx = await _get_treasury_context(db, current_user.id)
    _authorize_payment_action(tctx, row)

    return PendingPaymentResponse(
        payment_id=str(row["payment_id"]),
        payment_reference=row["payment_reference"],
        service_request_id=str(row["service_request_id"]) if row["service_request_id"] else None,
        request_reference=row["request_reference"],
        workflow_code=row["workflow_code"],
        user_id=str(row["user_id"]),
        user_name=row["user_name"],
        user_email=row["user_email"],
        payment_method=row["payment_method"],
        total_amount=float(row["total_amount"]),
        base_amount=float(row["base_amount"]) if row["base_amount"] else None,
        penalties=float(row["penalties"]) if row["penalties"] else None,
        discounts=float(row["discounts"]) if row["discounts"] else None,
        currency=row["currency"],
        calculation_details=json.loads(row["calculation_details"]) if isinstance(row["calculation_details"], str) else row["calculation_details"],
        workflow_status=row["workflow_status"],
        sla_target_date=row["sla_target_date"].isoformat() if row["sla_target_date"] else None,
        created_at=row["created_at"].isoformat(),
        hours_waiting=float(row["hours_waiting"] or 0),
        batch_id=str(row["batch_id"]) if row["batch_id"] else None,
        batch_reference=row["batch_reference"],
        batch_total_items=row["batch_total_items"],
        beneficiary_name=row.get("beneficiary_name"),
        assigned_agent_id=str(row["assigned_agent_id"]) if row["assigned_agent_id"] else None,
        assigned_agent_name=row["assigned_agent_name"],
        escalation_level=row["escalation_level"],
        escalation_reason=row["escalation_reason"],
        escalated_at=row["escalated_at"].isoformat() if row["escalated_at"] else None,
        sla_escalated=row["sla_escalated"],
    )


@router.post(
    "/treasury/payments/{payment_id}/validate",
    response_model=PaymentActionResponse,
    summary="Validate payment",
    description="""
    Validate (approve) a cash/check payment.

    **Behavior:**
    - Sets workflow_status to 'completed'
    - Sets validated_by_agent_id and validated_at
    - Generates receipt_number
    - Updates service_request payment_status

    **Permissions:**
    - Requires 'treasury.validate_payment' permission
    """
)
async def validate_payment(
    payment_id: str = Path(..., description="Payment UUID"),
    body: PaymentValidationRequest = Body(default=PaymentValidationRequest()),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.validate_payment"))
):
    """Validate (approve) a payment"""
    from app.modules.payments.services.processors import payment_processor_registry

    tctx = await _get_treasury_context(db, current_user.id)
    if not tctx.has_profile:
        no_agent_profile()
    agent_profile_id = tctx.profile_id

    # Get payment with workflow status + authorization fields
    payment = await db.fetchrow(
        "SELECT id, service_request_id, workflow_status, sla_target_date, "
        "assigned_agent_id, entity_code "
        "FROM service_payments WHERE id = $1::uuid",
        payment_id
    )

    if not payment:
        payment_not_found(payment_id)

    # P8.2-B1 security: scope check. Without this, any user with the
    # treasury.validate_payment permission could validate any pending payment
    # by providing its UUID — regardless of assignment or entity.
    _authorize_payment_action(tctx, payment)

    # With auto-assignment architecture, agent validates directly
    # Only pending_agent_review payments can be validated
    if payment["workflow_status"] != "pending_agent_review":
        raise TreasuryError(
            error_code=TreasuryErrorCode.INVALID_PAYMENT_STATUS,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail_override=f"El pago no está pendiente de validación (estado: {payment['workflow_status']})"
        )

    # Validate via registry (using agent_profile_id)
    result = await payment_processor_registry.validate_manual_payment(
        db=db,
        payment_id=payment_id,
        agent_profile_id=agent_profile_id,
        comment=body.comment
    )

    if not result.paid:
        return PaymentActionResponse(
            success=False,
            payment_id=payment_id,
            status=result.status.value,
            error=result.error
        )

    # Wrap post-validation updates + outbox INSERT in a single transaction
    # so the outbox item is guaranteed to exist if payment is validated.
    async with db.transaction():
        await db.execute("SET LOCAL lock_timeout = '5s'")
        await db.execute("SET LOCAL statement_timeout = '30s'")
        # Update service_request if linked
        if payment["service_request_id"]:
            await db.execute(
                """
                UPDATE service_requests
                SET payment_status = 'completed', paid_at = NOW(), updated_at = NOW()
                WHERE id = $1
                """,
                payment["service_request_id"]
            )

        # Update assignment status to COMPLETED
        await db.execute("""
            UPDATE assignments
            SET status = 'completed',
                completed_at = NOW(),
                processing_duration_hours = EXTRACT(EPOCH FROM (NOW() - COALESCE(started_at, assigned_at))) / 3600,
                updated_at = NOW()
            WHERE item_id = $1::uuid AND item_type = 'payment_validation'
              AND status NOT IN ('completed', 'cancelled', 'rejected')
        """, payment_id)

        # Insert audit record (action_duration_seconds = time from payment creation to now)
        await db.execute("""
            INSERT INTO payment_validation_audit
                (id, payment_id, agent_profile_id, agent_user_id, action,
                 from_status, to_status, comment, action_duration_seconds, created_at)
            VALUES (gen_random_uuid(), $1::uuid, $2, $3,
                    'approve'::agent_action_type,
                    'pending_agent_review'::payment_workflow_status,
                    'completed'::payment_workflow_status,
                    $4,
                    (SELECT EXTRACT(EPOCH FROM (NOW() - sp.created_at))::int FROM service_payments sp WHERE sp.id = $1::uuid),
                    NOW())
        """, payment_id, agent_profile_id, current_user.id, body.comment)

        # Update agent performance stats
        from app.modules.agents.repositories.workload_repository import WorkloadRepository
        _workload_repo = WorkloadRepository()
        await _workload_repo.increment_processed(db, str(agent_profile_id))
        await _workload_repo.increment_approved(db, str(agent_profile_id))

        # Track SLA compliance (was payment validated within SLA target?)
        sla_respected = (
            payment.get("sla_target_date") is None
            or datetime.now(timezone.utc) <= payment["sla_target_date"]
        )
        await _workload_repo.update_sla_stats(db, str(agent_profile_id), sla_respected)

        # Decrement agent workload cache
        await db.execute("""
            UPDATE agent_workloads
            SET current_assignments = GREATEST(current_assignments - 1, 0),
                last_completion_at = NOW(),
                last_updated_at = NOW()
            WHERE agent_profile_id = $1::uuid
        """, str(agent_profile_id))

        # INSERT into assignment outbox (guaranteed delivery for entity agent assignment)
        # No try/except: if enqueue fails, the entire transaction rolls back.
        # This guarantees that a validated payment ALWAYS has an outbox entry.
        if payment["service_request_id"]:
            from app.modules.service_requests.services.assignment_outbox_service import (
                assignment_outbox_service,
            )
            sr_data = await db.fetchrow(
                "SELECT workflow_code, entity_code, entity_location_id "
                "FROM service_requests WHERE id = $1",
                payment["service_request_id"],
            )
            entity_code = sr_data["entity_code"] if sr_data else None

            # Resolve entity_code from entity_location_id if NULL
            if not entity_code and sr_data and sr_data["entity_location_id"]:
                entity_code = await db.fetchval(
                    "SELECT entity_code FROM entity_locations "
                    "WHERE id = $1 AND is_active = true",
                    sr_data["entity_location_id"],
                )
                if entity_code:
                    await db.execute(
                        "UPDATE service_requests SET entity_code = $1 WHERE id = $2",
                        entity_code, payment["service_request_id"],
                    )
                    logger.info(
                        f"Resolved entity_code={entity_code} from "
                        f"entity_location_id={sr_data['entity_location_id']} "
                        f"for SR {payment['service_request_id']}"
                    )

            # Fallback: resolve from workflow_code → entities.workflow_codes
            if not entity_code and sr_data and sr_data["workflow_code"]:
                entity_code = await db.fetchval(
                    "SELECT e.code FROM entities e "
                    "WHERE e.workflow_codes ? $1 AND e.is_active = true "
                    "LIMIT 1",
                    sr_data["workflow_code"],
                )
                if entity_code:
                    await db.execute(
                        "UPDATE service_requests SET entity_code = $1 WHERE id = $2",
                        entity_code, payment["service_request_id"],
                    )
                    logger.info(
                        f"Resolved entity_code={entity_code} from "
                        f"workflow_code={sr_data['workflow_code']} "
                        f"for SR {payment['service_request_id']}"
                    )

            if entity_code:
                await assignment_outbox_service.enqueue(
                    db=db,
                    service_request_id=payment["service_request_id"],
                    workflow_code=sr_data["workflow_code"],
                    entity_code=entity_code,
                    entity_location_id=sr_data["entity_location_id"],
                    payment_id=payment_id,
                    payment_method="cash",
                )
            else:
                logger.error(
                    f"Cannot enqueue outbox: SR {payment['service_request_id']} "
                    f"entity_code unresolvable (no entity_location_id, "
                    f"no workflow_code match)"
                )
    # End of transaction block

    # Publish PAYMENT_CASH_VALIDATED event
    try:
        # Get user info for notification
        user_info = await db.fetchrow(
            """
            SELECT u.id, u.email, u.first_name, u.last_name, u.phone_number, u.preferred_language
            FROM service_payments sp
            JOIN service_requests sr ON sr.id = sp.service_request_id
            JOIN users u ON u.id = sr.user_id
            WHERE sp.id = $1
            """,
            payment_id
        )
        payment_info = await db.fetchrow(
            """
            SELECT sp.total_amount, sp.currency, sp.receipt_number, sp.payment_method,
                   sp.payment_reference, sp.paid_at, sr.reference as request_reference
            FROM service_payments sp
            JOIN service_requests sr ON sr.id = sp.service_request_id
            WHERE sp.id = $1::uuid
            """,
            payment_id
        )

        if user_info:
            # Generate receipt verification URL (HMAC-signed)
            verification_url = None
            if payment_info and payment_info["receipt_number"]:
                try:
                    from app.modules.payments.services.receipt_service import receipt_service
                    verification_url = receipt_service._generate_verification_url(
                        receipt_number=payment_info["receipt_number"],
                        amount=float(payment_info["total_amount"]) if payment_info["total_amount"] else 0,
                        paid_at=payment_info["paid_at"] or datetime.now(),
                    )
                except Exception as e:
                    logger.warning(f"Failed to generate verification URL: {e}")

            # Build attachments: attach receipt PDF if available
            attachments = None
            if result.receipt_pdf_bytes and result.receipt_number:
                attachments = [(
                    f"recibo_{result.receipt_number}.pdf",
                    result.receipt_pdf_bytes,
                    "application/pdf"
                )]
                logger.info(f"Receipt PDF attachment prepared: {result.receipt_number} ({len(result.receipt_pdf_bytes)} bytes)")
            else:
                logger.warning(
                    f"No receipt PDF attachment: receipt_number={result.receipt_number}, "
                    f"pdf_bytes={'available' if result.receipt_pdf_bytes else 'None'}"
                )

            # Build bundle context for enriched email (B7)
            bundle_section = ""
            sr_workflow = await db.fetchval(
                "SELECT workflow_code FROM service_requests WHERE id = $1",
                payment["service_request_id"],
            ) if payment.get("service_request_id") else None
            if sr_workflow == "BUNDLE_PAYMENT":
                try:
                    sp_row = await db.fetchrow(
                        "SELECT entity_code FROM service_payments WHERE id = $1",
                        payment_id,
                    )
                    entity_code = sp_row["entity_code"] if sp_row else None
                    entity_name = None
                    if entity_code:
                        entity_name = await db.fetchval(
                            "SELECT name FROM entities WHERE code = $1", entity_code
                        )
                    # Count total splits and completed splits
                    sr_id = payment["service_request_id"]
                    split_stats = await db.fetchrow("""
                        SELECT COUNT(*) as total,
                               COUNT(*) FILTER (WHERE workflow_status = 'completed') as completed
                        FROM service_payments WHERE service_request_id = $1
                    """, sr_id)
                    total_splits = split_stats["total"] if split_stats else 1
                    completed_splits = split_stats["completed"] if split_stats else 1
                    # Obligation names for this split
                    obl_rows = await db.fetch("""
                        SELECT fs.name_es, lo.amount
                        FROM license_obligations lo
                        LEFT JOIN fiscal_services fs ON fs.id = lo.fiscal_service_id
                        WHERE lo.payment_id = $1
                        ORDER BY fs.name_es
                    """, payment_id)
                    from html import escape as html_escape
                    obl_lines = "".join(
                        f'<tr><td style="padding:5px 15px;color:#6b7280;">{html_escape(r["name_es"] or "—")}</td>'
                        f'<td style="padding:5px 15px;text-align:right;">{int(r["amount"]):,} XAF</td></tr>'
                        for r in obl_rows
                    )
                    is_last = completed_splits >= total_splits
                    progress_text = f"Validación {completed_splits}/{total_splits}"
                    entity_label = html_escape(entity_name or entity_code or "")
                    bundle_section = f"""
                    <tr style="border-bottom:1px solid #e5e7eb;background-color:#f0fdf4;">
                        <td style="padding:10px 15px;color:#6b7280;font-weight:600;">Entidad</td>
                        <td style="padding:10px 15px;">{entity_label}</td>
                    </tr>
                    <tr style="border-bottom:1px solid #e5e7eb;">
                        <td style="padding:10px 15px;color:#6b7280;font-weight:600;">Progreso</td>
                        <td style="padding:10px 15px;font-weight:bold;color:{'#16a34a' if is_last else '#d97706'};">{progress_text}</td>
                    </tr>
                    <tr><td colspan="2" style="padding:10px 15px;">
                        <table style="width:100%;font-size:13px;">{obl_lines}</table>
                    </td></tr>
                    {"<tr><td colspan='2' style='padding:15px;text-align:center;background:#f0fdf4;color:#16a34a;font-weight:bold;font-size:15px;'>✓ Todas las validaciones completadas</td></tr>" if is_last else ""}
                    """
                except Exception as bs_err:
                    logger.warning(f"Could not build bundle email section: {bs_err}")

            EventBus.publish_nowait(
                EventType.PAYMENT_CASH_VALIDATED,
                {
                    "payment_id": payment_id,
                    "user_id": user_info["id"],
                    "user_email": user_info["email"],
                    "user_name": f"{user_info['first_name']} {user_info['last_name']}",
                    "user_phone": user_info["phone_number"],
                    "preferred_language": user_info["preferred_language"] or "es",
                    "request_id": payment["service_request_id"],
                    "amount": float(payment_info["total_amount"]) if payment_info["total_amount"] else None,
                    "currency": payment_info["currency"] or "XAF",
                    "receipt_number": payment_info["receipt_number"],
                    "payment_method": payment_info["payment_method"],
                    "payment_reference": payment_info["payment_reference"],
                    "request_reference": payment_info["request_reference"],
                    "agent_id": current_user.id,
                    "timestamp": datetime.now().isoformat(),
                    "attachments": attachments,
                    "verification_url": verification_url,
                    "bundle_section": bundle_section,
                }
            )
    except Exception as e:
        logger.error(f"Failed to publish PAYMENT_CASH_VALIDATED event for {payment_id}: {e}", exc_info=True)

    # NOTE: PAYMENT_COMPLETED EventBus publish removed — replaced by assignment_outbox
    # (transactional INSERT above). Cron processes outbox items every 1 minute.

    return PaymentActionResponse(
        success=True,
        payment_id=payment_id,
        status="approved",
        message_es="Pago validado correctamente. Recibo generado.",
        receipt_number=result.receipt_number,
        receipt_url=result.receipt_url,
    )


@router.post(
    "/treasury/payments/{payment_id}/reject",
    response_model=PaymentActionResponse,
    summary="Reject payment",
    description="""
    Reject a cash/check payment.

    **Behavior:**
    - Sets workflow_status to 'rejected'
    - Records rejection reason
    - Notifies user

    **Permissions:**
    - Requires 'treasury.validate_payment' permission
    """
)
async def reject_payment(
    payment_id: str = Path(..., description="Payment UUID"),
    body: PaymentRejectionRequest = ...,
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.validate_payment"))
):
    """Reject a payment"""
    from app.modules.payments.services.processors import payment_processor_registry

    tctx = await _get_treasury_context(db, current_user.id)
    if not tctx.has_profile:
        no_agent_profile()
    agent_profile_id = tctx.profile_id

    # Get payment with workflow status + authorization fields
    payment = await db.fetchrow(
        "SELECT id, workflow_status, sla_target_date, assigned_agent_id, entity_code "
        "FROM service_payments WHERE id = $1::uuid",
        payment_id
    )

    if not payment:
        payment_not_found(payment_id)

    # P8.2-B1 security: same scope check as validate_payment
    _authorize_payment_action(tctx, payment)

    # With auto-assignment architecture, agent rejects directly
    # Only pending_agent_review payments can be rejected
    if payment["workflow_status"] != "pending_agent_review":
        raise TreasuryError(
            error_code=TreasuryErrorCode.INVALID_PAYMENT_STATUS,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail_override=f"El pago no está pendiente de validación (estado: {payment['workflow_status']})"
        )

    # Reject via registry (using agent_profile_id)
    result = await payment_processor_registry.reject_manual_payment(
        db=db,
        payment_id=payment_id,
        agent_profile_id=agent_profile_id,
        reason=body.reason
    )

    # Wrap post-rejection updates in a single transaction for atomicity
    async with db.transaction():
        await db.execute("SET LOCAL lock_timeout = '5s'")
        await db.execute("SET LOCAL statement_timeout = '30s'")
        # Update assignment status to REJECTED
        await db.execute("""
            UPDATE assignments
            SET status = 'rejected',
                completed_at = NOW(),
                processing_duration_hours = EXTRACT(EPOCH FROM (NOW() - COALESCE(started_at, assigned_at))) / 3600,
                updated_at = NOW()
            WHERE item_id = $1::uuid AND item_type = 'payment_validation'
              AND status NOT IN ('completed', 'cancelled', 'rejected')
        """, payment_id)

        # Insert audit record (action_duration_seconds = time from payment creation to now)
        await db.execute("""
            INSERT INTO payment_validation_audit
                (id, payment_id, agent_profile_id, agent_user_id, action,
                 from_status, to_status, comment, action_duration_seconds, created_at)
            VALUES (gen_random_uuid(), $1::uuid, $2, $3,
                    'reject'::agent_action_type,
                    'pending_agent_review'::payment_workflow_status,
                    'rejected_by_agent'::payment_workflow_status,
                    $4,
                    (SELECT EXTRACT(EPOCH FROM (NOW() - sp.created_at))::int FROM service_payments sp WHERE sp.id = $1::uuid),
                    NOW())
        """, payment_id, agent_profile_id, current_user.id, body.reason)

        # Update agent performance stats
        from app.modules.agents.repositories.workload_repository import WorkloadRepository
        _workload_repo = WorkloadRepository()
        await _workload_repo.increment_processed(db, str(agent_profile_id))
        await _workload_repo.increment_rejected(db, str(agent_profile_id))

        # Track SLA compliance
        sla_respected = (
            payment.get("sla_target_date") is None
            or datetime.now(timezone.utc) <= payment["sla_target_date"]
        )
        await _workload_repo.update_sla_stats(db, str(agent_profile_id), sla_respected)

        # Decrement agent workload cache
        await db.execute("""
            UPDATE agent_workloads
            SET current_assignments = GREATEST(current_assignments - 1, 0),
                last_completion_at = NOW(),
                last_updated_at = NOW()
            WHERE agent_profile_id = $1::uuid
        """, str(agent_profile_id))

    # Publish PAYMENT_CASH_REJECTED event
    try:
        # Get user and payment info for notification
        user_info = await db.fetchrow(
            """
            SELECT u.id, u.email, u.first_name, u.last_name, u.phone_number, u.preferred_language,
                   sp.service_request_id, sp.total_amount, sp.currency, sp.payment_method,
                   sp.payment_reference, sr.reference as request_reference
            FROM service_payments sp
            JOIN service_requests sr ON sr.id = sp.service_request_id
            JOIN users u ON u.id = sr.user_id
            WHERE sp.id = $1
            """,
            payment_id
        )

        if user_info:
            EventBus.publish_nowait(
                EventType.PAYMENT_CASH_REJECTED,
                {
                    "payment_id": payment_id,
                    "user_id": user_info["id"],
                    "user_email": user_info["email"],
                    "user_name": f"{user_info['first_name']} {user_info['last_name']}",
                    "user_phone": user_info["phone_number"],
                    "preferred_language": user_info["preferred_language"] or "es",
                    "request_id": user_info["service_request_id"],
                    "amount": float(user_info["total_amount"]) if user_info["total_amount"] else None,
                    "currency": user_info["currency"] or "XAF",
                    "payment_method": user_info["payment_method"],
                    "payment_reference": user_info["payment_reference"],
                    "request_reference": user_info["request_reference"],
                    "reason": body.reason,
                    "agent_id": current_user.id,
                    "timestamp": datetime.now().isoformat(),
                }
            )
    except Exception as e:
        logger.error(f"Failed to publish PAYMENT_CASH_REJECTED event for {payment_id}: {e}", exc_info=True)

    return PaymentActionResponse(
        success=True,
        payment_id=payment_id,
        status="rejected",
        message_es="Pago rechazado."
    )


# ============================================================================
# TREASURY PAYMENT REASSIGNMENT (Supervisor only)
# ============================================================================


class PaymentReassignRequest(BaseModel):
    target_agent_profile_id: str = Field(..., description="Agent profile ID to reassign to")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for reassignment")


@router.post(
    "/treasury/payments/{payment_id}/reassign",
    summary="Reassign payment to another agent (supervisor only)",
    description="""
    Supervisor-only: reassign a pending payment to a different agent within the
    same entity as the calling supervisor.

    Updates both:
    - assignments table (agent_profile_id)
    - service_payments table (assigned_agent_id, assigned_at)

    **Permissions:** treasury.validate_payment + is_supervisor flag.
    **Scope:** target agent must belong to the caller's own entity (global
    supervisors with treasury.view_all may reassign across entities).
    """
)
async def reassign_payment(
    payment_id: str = Path(..., description="Payment UUID"),
    body: PaymentReassignRequest = ...,
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.validate_payment"))
):
    """Reassign a payment to another agent within the caller's entity."""
    # Resolve supervisor context upfront (before transaction)
    tctx = await _get_treasury_context(db, current_user.id)
    if not tctx.is_supervisor and not tctx.has_global_scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only supervisors can reassign payments"
        )
    supervisor_profile_id = tctx.profile_id  # may be None if admin without agent profile

    # Verify payment exists and is in actionable status
    payment = await db.fetchrow(
        "SELECT id, workflow_status, assigned_agent_id, entity_code "
        "FROM service_payments WHERE id = $1::uuid",
        payment_id
    )
    if not payment:
        payment_not_found(payment_id)

    # P7 security (2026-05-06): scope check on source payment. A non-global
    # supervisor must NOT be able to reassign payments belonging to another
    # entity (the existing target check only validated the destination agent).
    _authorize_payment_action(tctx, payment)

    if payment["workflow_status"] not in ("pending_agent_review", "escalated_supervisor"):
        raise TreasuryError(
            error_code=TreasuryErrorCode.INVALID_PAYMENT_STATUS,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail_override=f"Cannot reassign payment in status: {payment['workflow_status']}"
        )

    # Guard: prevent reassigning to the same agent
    if payment["assigned_agent_id"] and str(payment["assigned_agent_id"]) == body.target_agent_profile_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment is already assigned to this agent"
        )

    # Verify target agent is active and within caller's entity scope.
    # Global supervisor (treasury.view_all): may pick any entity.
    # Non-global supervisor: target must belong to same entity as caller.
    if tctx.has_global_scope:
        target = await db.fetchrow("""
            SELECT ap.id, ap.user_id, u.full_name
            FROM agent_profiles ap
            JOIN users u ON u.id = ap.user_id
            WHERE ap.id = $1::uuid AND ap.is_active = true
        """, body.target_agent_profile_id)
    else:
        target = await db.fetchrow("""
            SELECT ap.id, ap.user_id, u.full_name
            FROM agent_profiles ap
            JOIN users u ON u.id = ap.user_id
            WHERE ap.id = $1::uuid
              AND ap.is_active = true
              AND ap.entity_id = $2::uuid
        """, body.target_agent_profile_id, tctx.entity_id)
    if not target:
        raise HTTPException(
            status_code=404,
            detail="Target agent not found, inactive, or outside your entity scope"
        )

    async with db.transaction():
        # Update assignment record
        await db.execute("""
            UPDATE assignments SET
                agent_profile_id = $1::uuid,
                reassigned_at = NOW(),
                reassignment_reason = 'supervisor_decision'::reassignment_reason_enum,
                status = 'assigned',
                updated_at = NOW()
            WHERE item_id = $2::uuid
              AND item_type = 'payment_validation'
              AND status IN ('assigned', 'in_progress', 'pending_review')
        """, body.target_agent_profile_id, payment_id)

        # Update service_payments
        await db.execute("""
            UPDATE service_payments
            SET assigned_agent_id = $1::uuid,
                assigned_at = NOW(),
                updated_at = NOW()
            WHERE id = $2::uuid
        """, body.target_agent_profile_id, payment_id)

        # If escalated, reset to pending_agent_review
        if payment["workflow_status"] == "escalated_supervisor":
            await db.execute("""
                UPDATE service_payments
                SET workflow_status = 'pending_agent_review'
                WHERE id = $1::uuid
            """, payment_id)

        # Audit log (supervisor_profile_id resolved before transaction)
        await db.execute("""
            INSERT INTO payment_validation_audit
                (id, payment_id, agent_profile_id, agent_user_id, action,
                 from_status, to_status, comment, created_at)
            VALUES (gen_random_uuid(), $1::uuid, $2, $3,
                    'assign_to_colleague'::agent_action_type,
                    $4::payment_workflow_status,
                    'pending_agent_review'::payment_workflow_status,
                    $5, NOW())
        """, payment_id, supervisor_profile_id, current_user.id,
            payment["workflow_status"], body.reason or f"Reassigned to {target['full_name']}")

        # Update workload counters
        old_agent_id = payment["assigned_agent_id"]
        if old_agent_id:
            await db.execute("""
                UPDATE agent_workloads
                SET current_assignments = GREATEST(current_assignments - 1, 0), last_updated_at = NOW()
                WHERE agent_profile_id = $1::uuid
            """, str(old_agent_id))
        await db.execute("""
            UPDATE agent_workloads
            SET current_assignments = current_assignments + 1, last_updated_at = NOW()
            WHERE agent_profile_id = $1::uuid
        """, body.target_agent_profile_id)

    logger.info(f"Payment {payment_id} reassigned to {body.target_agent_profile_id} by supervisor {current_user.id}")

    return {
        "success": True,
        "payment_id": payment_id,
        "target_agent_name": target["full_name"],
        "message": f"Payment reassigned to {target['full_name']}"
    }


@router.get(
    "/treasury/payments/{payment_id}/receipt/download",
    summary="Download receipt PDF",
    description="""
    Regenerate and download the receipt PDF for a validated payment.

    **Behavior:**
    - Fetches payment, user, and service data from DB
    - Regenerates the PDF using the receipt template
    - Returns the PDF as a streaming response

    **Permissions:**
    - Requires 'treasury.validate_payment' permission
    """
)
async def download_receipt_pdf(
    payment_id: str = Path(..., description="Payment UUID"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.validate_payment"))
):
    """Download receipt PDF for a completed payment."""
    from fastapi.responses import StreamingResponse
    from io import BytesIO
    from app.modules.payments.services.receipt_service import receipt_service

    # Fetch all data needed for PDF generation in 2 queries (payment+service, user)
    payment = await db.fetchrow(
        """
        SELECT sp.id, sp.payment_reference, sp.total_amount, sp.currency,
               sp.payment_method, sp.calculation_details, sp.receipt_number,
               sp.paid_at, sp.created_at, sp.validated_by_agent_id, sp.validated_at,
               sp.service_request_id,
               sr.user_id, sr.reference, sr.workflow_code, sr.solicitud_type, sr.entity_code,
               el.location_name, el.city, el.location_address
        FROM service_payments sp
        JOIN service_requests sr ON sr.id = sp.service_request_id
        LEFT JOIN entity_locations el ON el.id = sr.entity_location_id
        WHERE sp.id = $1::uuid
        """,
        payment_id
    )
    if not payment:
        raise payment_not_found(payment_id)

    if not payment["receipt_number"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No receipt found for this payment"
        )

    # Fetch user data
    user_data = await db.fetchrow(
        "SELECT id, email, phone_number as phone, first_name, last_name, document_number FROM users WHERE id = $1",
        payment["user_id"]
    )

    # Fetch agent info + treasury location
    agent_name = None
    agent_location = None
    if payment["validated_by_agent_id"]:
        # validated_by_agent_id is agent_profiles.id (not users.id).
        agent_data = await db.fetchrow(
            """
            SELECT u.first_name, u.last_name,
                   ael.location_name AS treasury_location_name,
                   ael.location_address AS treasury_location_address,
                   ael.city AS treasury_city,
                   ael.phone AS treasury_phone,
                   e.name AS entity_name
            FROM agent_profiles ap
            JOIN users u ON u.id = ap.user_id
            LEFT JOIN entity_locations ael ON ael.id = ap.entity_location_id
            LEFT JOIN entities e ON e.id = ap.entity_id
            WHERE ap.id = $1::uuid
            """,
            str(payment["validated_by_agent_id"])
        )
        if agent_data:
            agent_name = f"{agent_data['first_name'] or ''} {agent_data['last_name'] or ''}".strip()
            if agent_data.get("treasury_location_name"):
                agent_location = {
                    "location_name": agent_data["treasury_location_name"],
                    "location_address": agent_data.get("treasury_location_address"),
                    "city": agent_data.get("treasury_city"),
                    "phone": agent_data.get("treasury_phone"),
                    "entity_name": agent_data.get("entity_name"),
                }

    # Build service_data dict from the joined query
    service_data = {
        "reference": payment["reference"],
        "workflow_code": payment["workflow_code"],
        "solicitud_type": payment["solicitud_type"],
        "entity_code": payment["entity_code"],
        "location_name": payment["location_name"],
        "city": payment["city"],
        "location_address": payment["location_address"],
    }

    # Generate PDF
    pdf_bytes = await receipt_service.generate_receipt_pdf(
        receipt_number=payment["receipt_number"],
        payment_data=dict(payment),
        user_data=dict(user_data) if user_data else {},
        service_data=service_data,
        validated_by=str(payment["validated_by_agent_id"]) if payment["validated_by_agent_id"] else None,
        validated_by_name=agent_name,
        validated_at=payment.get("validated_at"),
        language="es",
        agent_location=agent_location,
    )

    filename = f"recibo_{payment['receipt_number']}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        }
    )


# ═══════════════════════════════════════════════════════════════
# BATCH PAYMENT VALIDATION
# ═══════════════════════════════════════════════════════════════


@router.post(
    "/treasury/batch/{batch_id}/validate",
    response_model=BatchValidateResponse,
    summary="Validate all payments in a batch",
    description="""
    Validate (approve) all pending payments in a batch atomically.

    **Behavior:**
    - Finds all service_payments with given batch_id that are pending_agent_review
    - Validates them all atomically via fan_out_batch_completion
    - Updates service_requests and batch_requests status

    **Permissions:**
    - Requires 'treasury.validate_payment' permission
    """
)
async def validate_batch_payments(
    batch_id: str = Path(..., description="Batch UUID"),
    body: PaymentValidationRequest = Body(default=PaymentValidationRequest()),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.validate_payment"))
):
    """Validate all payments in a batch atomically"""
    from datetime import datetime, timezone
    from uuid import UUID as UUIDType
    from loguru import logger

    tctx = await _get_treasury_context(db, current_user.id)
    if not tctx.has_profile:
        no_agent_profile()
    agent_profile_id = tctx.profile_id

    try:
        # 1. Check batch exists and has pending payments
        batch = await db.fetchrow("""
            SELECT br.id, br.reference, br.total_items, br.status
            FROM batch_requests br
            WHERE br.id = $1::uuid
        """, batch_id)

        if not batch:
            raise TreasuryError(
                error_code=TreasuryErrorCode.PAYMENT_NOT_FOUND,
                status_code=status.HTTP_404_NOT_FOUND,
                detail_override=f"Lote no encontrado: {batch_id}"
            )

        # P7 security (2026-05-06): for non-global agents, every payment in
        # the batch must belong to the caller's entity. Block if any payment
        # in the batch leaks across entity scope (or has NULL entity_code).
        if not tctx.has_global_scope:
            if not tctx.entity_code:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Not authorized: batch {batch_id} requires entity scope"
                    ),
                )
            mismatched = await db.fetchval(
                """
                SELECT COUNT(*) FROM service_payments
                WHERE batch_id = $1::uuid
                  AND (entity_code IS NULL OR entity_code <> $2)
                """,
                batch_id,
                tctx.entity_code,
            )
            if mismatched and mismatched > 0:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Not authorized: batch {batch_id} contains "
                        f"{mismatched} payment(s) outside your entity scope "
                        f"({tctx.entity_code!r})"
                    ),
                )

        # 2. Count pending payments in this batch
        pending_count = await db.fetchval("""
            SELECT COUNT(*) FROM service_payments
            WHERE batch_id = $1::uuid
              AND workflow_status = 'pending_agent_review'
        """, batch_id)

        if pending_count == 0:
            return BatchValidateResponse(
                success=False,
                payments_validated=0,
                batch_reference=batch["reference"],
                error="No hay pagos pendientes de validación en este lote."
            )

        # 3. Use fan_out_batch_completion for atomic validation
        from app.modules.batch_requests.services.batch_persist_service import BatchPersistService
        result = await BatchPersistService.fan_out_batch_completion(
            db=db,
            batch_id=UUIDType(batch_id),
            paid_at=datetime.now(timezone.utc),
            agent_profile_id=str(agent_profile_id),
        )

        logger.info(
            f"[Treasury] Batch {batch['reference']} validated by agent {agent_profile_id}: "
            f"payments={result.get('payments_updated', 0)}, requests={result.get('requests_updated', 0)}"
        )

        return BatchValidateResponse(
            success=True,
            payments_validated=result.get("payments_updated", 0),
            batch_reference=batch["reference"],
        )

    except TreasuryError:
        raise
    except Exception as e:
        from loguru import logger
        logger.error(f"[Treasury] Error validating batch {batch_id}: {e}", exc_info=True)
        raise


# ═══════════════════════════════════════════════════════════════
# MANUAL PAYMENT ESCALATION
# ═══════════════════════════════════════════════════════════════


@router.post(
    "/treasury/payments/{payment_id}/escalate",
    response_model=PaymentActionResponse,
    summary="Escalate payment to supervisor",
    description="""
    Manually escalate a payment to the caller's entity supervisor.

    **Behavior:**
    - Sets workflow_status to 'escalated_supervisor'
    - Records escalation reason, level, and timestamp
    - Assigns to the supervisor of the caller's own entity (site-preferred)

    **Permissions:**
    - Requires 'treasury.validate_payment' permission
    """
)
async def escalate_payment(
    payment_id: str = Path(..., description="Payment UUID"),
    body: PaymentEscalationRequest = ...,
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.validate_payment"))
):
    """Manually escalate a payment to supervisor"""
    from datetime import datetime, timezone
    from loguru import logger

    tctx = await _get_treasury_context(db, current_user.id)
    if not tctx.has_profile:
        no_agent_profile()
    agent_profile_id = tctx.profile_id

    try:
        # 1. Verify payment exists and is in escalatable state
        payment = await db.fetchrow("""
            SELECT id, workflow_status, service_request_id,
                   assigned_agent_id, entity_code
            FROM service_payments WHERE id = $1::uuid
        """, payment_id)

        if not payment:
            payment_not_found(payment_id)

        # P8.2-B1 security: scope check (same rules as validate/reject)
        _authorize_payment_action(tctx, payment)

        escalatable_statuses = ("pending_agent_review", "agent_reviewing")
        if payment["workflow_status"] not in escalatable_statuses:
            raise TreasuryError(
                error_code=TreasuryErrorCode.INVALID_PAYMENT_STATUS,
                status_code=status.HTTP_400_BAD_REQUEST,
                detail_override=f"El pago no se puede escalar (estado: {payment['workflow_status']})"
            )

        # 2. Validate escalation level
        valid_levels = ("low", "medium", "high", "critical")
        level = body.level if body.level in valid_levels else "medium"

        # 3. Find supervisor of the caller's own entity — prefer same site as the
        # escalating agent to keep escalations site-local (TGE BATA agent → TGE
        # BATA supervisor). Falls back to main office supervisor of same entity.
        agent_location_id = tctx.entity_location_id
        supervisor_id = None
        if tctx.entity_id and agent_location_id:
            # Try same-site supervisor first (entity + location match)
            supervisor_id = await db.fetchval("""
                SELECT ap.id FROM agent_profiles ap
                WHERE ap.entity_id = $1::uuid
                  AND ap.is_supervisor = true AND ap.is_active = true
                  AND ap.entity_location_id = $2::uuid
                LIMIT 1
            """, tctx.entity_id, agent_location_id)
        if not supervisor_id and tctx.entity_id:
            # Fallback: any supervisor of same entity, prefer main office
            supervisor_id = await db.fetchval("""
                SELECT ap.id FROM agent_profiles ap
                LEFT JOIN entity_locations el ON el.id = ap.entity_location_id
                WHERE ap.entity_id = $1::uuid
                  AND ap.is_supervisor = true AND ap.is_active = true
                ORDER BY COALESCE(el.is_main_office, false) DESC
                LIMIT 1
            """, tctx.entity_id)

        if not supervisor_id:
            logger.warning(
                f"[Treasury] No active supervisor found for escalation "
                f"(entity={tctx.entity_code})"
            )

        # 4. Update payment
        await db.execute("""
            UPDATE service_payments
            SET workflow_status = 'escalated_supervisor',
                escalated_to_agent_id = $2,
                escalation_level = $3::escalation_level,
                escalation_reason = $4,
                escalated_at = NOW(),
                updated_at = NOW()
            WHERE id = $1::uuid
        """, payment_id, supervisor_id, level, body.reason)

        # 5. Update assignment status to CANCELLED (escalated away from agent)
        await db.execute("""
            UPDATE assignments
            SET status = 'cancelled',
                completed_at = NOW(),
                processing_duration_hours = EXTRACT(EPOCH FROM (NOW() - COALESCE(started_at, assigned_at))) / 3600,
                notes = COALESCE(notes || ' | ', '') || 'Escalated: ' || $2,
                updated_at = NOW()
            WHERE item_id = $1::uuid AND item_type = 'payment_validation'
              AND status NOT IN ('completed', 'cancelled', 'rejected')
        """, payment_id, body.reason)

        # 6. Insert audit record (action_duration_seconds = time from payment creation to now)
        await db.execute("""
            INSERT INTO payment_validation_audit
                (id, payment_id, agent_profile_id, agent_user_id, action,
                 from_status, to_status, comment, action_duration_seconds, created_at)
            VALUES (gen_random_uuid(), $1::uuid, $2, $3,
                    'escalate'::agent_action_type,
                    'pending_agent_review'::payment_workflow_status,
                    'escalated_supervisor'::payment_workflow_status,
                    $4,
                    (SELECT EXTRACT(EPOCH FROM (NOW() - sp.created_at))::int FROM service_payments sp WHERE sp.id = $1::uuid),
                    NOW())
        """, payment_id, agent_profile_id, current_user.id, body.reason)

        # Update agent performance stats
        from app.modules.agents.repositories.workload_repository import WorkloadRepository
        _workload_repo = WorkloadRepository()
        await _workload_repo.increment_escalated(db, str(agent_profile_id))

        # Decrement agent workload cache (escalated = no longer in this agent's queue)
        await db.execute("""
            UPDATE agent_workloads
            SET current_assignments = GREATEST(current_assignments - 1, 0),
                last_updated_at = NOW()
            WHERE agent_profile_id = $1::uuid
        """, str(agent_profile_id))

        logger.info(
            f"[Treasury] Payment {payment_id} escalated to supervisor {supervisor_id} "
            f"by agent {agent_profile_id} (level={level}, reason={body.reason[:50]}...)"
        )

        # 5. Send email notification to supervisor (non-blocking)
        try:
            if supervisor_id:
                sup_user = await db.fetchrow("""
                    SELECT u.email, u.first_name, u.last_name, u.preferred_language
                    FROM agent_profiles ap
                    JOIN users u ON u.id = ap.user_id
                    WHERE ap.id = $1
                """, supervisor_id)

                if sup_user:
                    from app.core.events import EventBus, EventType
                    EventBus.publish_nowait(
                        EventType.PAYMENT_MANUAL_ESCALATED,
                        {
                            "payment_id": payment_id,
                            "reason": body.reason,
                            "escalation_level": level,
                            # Recipient = supervisor (not citizen)
                            "user_email": sup_user["email"],
                            "user_name": f"{sup_user['first_name']} {sup_user['last_name']}",
                            "preferred_language": sup_user.get("preferred_language") or "es",
                            "agent_name": f"{current_user.first_name} {current_user.last_name}".strip(),
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
        except Exception as e:
            logger.warning(f"[Treasury] Failed to send escalation notification: {e}")

        return PaymentActionResponse(
            success=True,
            payment_id=payment_id,
            status="escalated_supervisor",
            message_es="Pago escalado al supervisor correctamente."
        )

    except TreasuryError:
        raise
    except Exception as e:
        logger.error(f"[Treasury] Error escalating payment {payment_id}: {e}", exc_info=True)
        raise


# ═══════════════════════════════════════════════════════════════
# PAYMENT METHOD CONFIGURATIONS
# ═══════════════════════════════════════════════════════════════

class PaymentMethodConfigResponse(BaseModel):
    """Response model for payment method configuration.
    Note: Translations (FR/EN) are managed via entity_translations table.
    """
    id: int
    code: str
    label_es: str
    processor_type: str
    requires_phone: bool = False
    requires_redirect: bool = False
    requires_agent_validation: bool = False
    is_active: bool = True
    display_order: int = 0
    icon: str = "credit-card"
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    fees_percentage: float = 0
    fees_fixed: float = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PaymentMethodConfigCreate(BaseModel):
    """Create model for payment method configuration.
    Note: Translations (FR/EN) are managed via entity_translations table.
    """
    code: str = Field(..., pattern=r'^[a-z_]+$', max_length=50)
    label_es: str = Field(..., max_length=100)
    processor_type: str = Field(default="manual", pattern="^(gateway_api|bange_api|manual)$")
    requires_phone: bool = False
    requires_redirect: bool = False
    requires_agent_validation: bool = False
    is_active: bool = True
    display_order: int = Field(default=0, ge=0)
    icon: str = Field(default="credit-card", max_length=50)
    min_amount: Optional[float] = Field(None, ge=0)
    max_amount: Optional[float] = Field(None, ge=0)
    fees_percentage: float = Field(default=0, ge=0, le=100)
    fees_fixed: float = Field(default=0, ge=0)


class PaymentMethodConfigUpdate(BaseModel):
    """Update model for payment method configuration.
    Note: Translations (FR/EN) are managed via entity_translations table.
    """
    label_es: Optional[str] = Field(None, max_length=100)
    processor_type: Optional[str] = Field(None, pattern="^(gateway_api|bange_api|manual)$")
    requires_phone: Optional[bool] = None
    requires_redirect: Optional[bool] = None
    requires_agent_validation: Optional[bool] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = Field(None, ge=0)
    icon: Optional[str] = Field(None, max_length=50)
    min_amount: Optional[float] = Field(None, ge=0)
    max_amount: Optional[float] = Field(None, ge=0)
    fees_percentage: Optional[float] = Field(None, ge=0, le=100)
    fees_fixed: Optional[float] = Field(None, ge=0)


class PaymentMethodReorderRequest(BaseModel):
    """Request model for reordering payment methods."""
    order: List[str] = Field(..., description="List of method codes in desired order")


@router.get(
    "/treasury/payment-methods",
    response_model=List[PaymentMethodConfigResponse],
    summary="List payment method configurations",
    description="""
    Get all payment method configurations.

    **Permissions:**
    - Requires 'treasury.view_payment' permission
    """
)
async def list_payment_methods(
    active_only: bool = Query(False, description="Show only active methods"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.view_payment"))
):
    """List all payment method configurations"""
    query = """
        SELECT
            id, code, label_es,
            processor_type, requires_phone, requires_redirect,
            requires_agent_validation, is_active, display_order,
            icon, min_amount, max_amount, fees_percentage, fees_fixed,
            created_at, updated_at
        FROM payment_method_configurations
    """
    if active_only:
        query += " WHERE is_active = TRUE"
    query += " ORDER BY display_order ASC, code ASC"

    rows = await db.fetch(query)

    return [
        PaymentMethodConfigResponse(
            id=row["id"],
            code=row["code"],
            label_es=row["label_es"],
            processor_type=row["processor_type"],
            requires_phone=row["requires_phone"],
            requires_redirect=row["requires_redirect"],
            requires_agent_validation=row["requires_agent_validation"],
            is_active=row["is_active"],
            display_order=row["display_order"],
            icon=row["icon"],
            min_amount=float(row["min_amount"]) if row["min_amount"] else None,
            max_amount=float(row["max_amount"]) if row["max_amount"] else None,
            fees_percentage=float(row["fees_percentage"]) if row["fees_percentage"] else 0,
            fees_fixed=float(row["fees_fixed"]) if row["fees_fixed"] else 0,
            created_at=row["created_at"].isoformat() if row["created_at"] else None,
            updated_at=row["updated_at"].isoformat() if row["updated_at"] else None,
        )
        for row in rows
    ]


@router.get(
    "/treasury/payment-methods/{code}",
    response_model=PaymentMethodConfigResponse,
    summary="Get payment method by code",
    description="""
    Get a specific payment method configuration by code.

    **Permissions:**
    - Requires 'treasury.view_payment' permission
    """
)
async def get_payment_method(
    code: str = Path(..., description="Payment method code"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.view_payment"))
):
    """Get payment method configuration by code"""
    query = """
        SELECT
            id, code, label_es,
            processor_type, requires_phone, requires_redirect,
            requires_agent_validation, is_active, display_order,
            icon, min_amount, max_amount, fees_percentage, fees_fixed,
            created_at, updated_at
        FROM payment_method_configurations
        WHERE code = $1
    """
    row = await db.fetchrow(query, code)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment method not found: {code}"
        )

    return PaymentMethodConfigResponse(
        id=row["id"],
        code=row["code"],
        label_es=row["label_es"],
        processor_type=row["processor_type"],
        requires_phone=row["requires_phone"],
        requires_redirect=row["requires_redirect"],
        requires_agent_validation=row["requires_agent_validation"],
        is_active=row["is_active"],
        display_order=row["display_order"],
        icon=row["icon"],
        min_amount=float(row["min_amount"]) if row["min_amount"] else None,
        max_amount=float(row["max_amount"]) if row["max_amount"] else None,
        fees_percentage=float(row["fees_percentage"]) if row["fees_percentage"] else 0,
        fees_fixed=float(row["fees_fixed"]) if row["fees_fixed"] else 0,
        created_at=row["created_at"].isoformat() if row["created_at"] else None,
        updated_at=row["updated_at"].isoformat() if row["updated_at"] else None,
    )


@router.post(
    "/treasury/payment-methods",
    response_model=PaymentMethodConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create payment method configuration",
    description="""
    Create a new payment method configuration.

    **Permissions:**
    - Requires 'treasury.manage_settings' permission
    """
)
async def create_payment_method(
    body: PaymentMethodConfigCreate,
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.manage_settings"))
):
    """Create new payment method configuration"""
    # Check if code already exists
    existing = await db.fetchval(
        "SELECT id FROM payment_method_configurations WHERE code = $1",
        body.code
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Payment method with code '{body.code}' already exists"
        )

    query = """
        INSERT INTO payment_method_configurations (
            code, label_es,
            processor_type, requires_phone, requires_redirect,
            requires_agent_validation, is_active, display_order,
            icon, min_amount, max_amount, fees_percentage, fees_fixed
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        RETURNING id, created_at, updated_at
    """
    row = await db.fetchrow(
        query,
        body.code, body.label_es,
        body.processor_type, body.requires_phone, body.requires_redirect,
        body.requires_agent_validation, body.is_active, body.display_order,
        body.icon, body.min_amount, body.max_amount, body.fees_percentage, body.fees_fixed
    )

    return PaymentMethodConfigResponse(
        id=row["id"],
        code=body.code,
        label_es=body.label_es,
        processor_type=body.processor_type,
        requires_phone=body.requires_phone,
        requires_redirect=body.requires_redirect,
        requires_agent_validation=body.requires_agent_validation,
        is_active=body.is_active,
        display_order=body.display_order,
        icon=body.icon,
        min_amount=body.min_amount,
        max_amount=body.max_amount,
        fees_percentage=body.fees_percentage,
        fees_fixed=body.fees_fixed,
        created_at=row["created_at"].isoformat() if row["created_at"] else None,
        updated_at=row["updated_at"].isoformat() if row["updated_at"] else None,
    )


@router.put(
    "/treasury/payment-methods/{code}",
    response_model=PaymentMethodConfigResponse,
    summary="Update payment method configuration",
    description="""
    Update an existing payment method configuration.

    **Permissions:**
    - Requires 'treasury.manage_settings' permission
    """
)
async def update_payment_method(
    code: str = Path(..., description="Payment method code"),
    body: PaymentMethodConfigUpdate = ...,
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.manage_settings"))
):
    """Update payment method configuration"""
    # Check if exists
    existing = await db.fetchrow(
        "SELECT id FROM payment_method_configurations WHERE code = $1",
        code
    )
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment method not found: {code}"
        )

    # Build dynamic update query
    updates = []
    params = []
    param_idx = 1

    update_fields = body.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        if value is not None:
            updates.append(f"{field} = ${param_idx}")
            params.append(value)
            param_idx += 1

    if not updates:
        raise TranslatedException(ErrorCode.NO_FIELDS_TO_UPDATE)

    updates.append(f"updated_at = NOW()")
    params.append(code)

    query = f"""
        UPDATE payment_method_configurations
        SET {', '.join(updates)}
        WHERE code = ${param_idx}
        RETURNING id, code, label_es,
            processor_type, requires_phone, requires_redirect,
            requires_agent_validation, is_active, display_order,
            icon, min_amount, max_amount, fees_percentage, fees_fixed,
            created_at, updated_at
    """
    row = await db.fetchrow(query, *params)

    return PaymentMethodConfigResponse(
        id=row["id"],
        code=row["code"],
        label_es=row["label_es"],
        processor_type=row["processor_type"],
        requires_phone=row["requires_phone"],
        requires_redirect=row["requires_redirect"],
        requires_agent_validation=row["requires_agent_validation"],
        is_active=row["is_active"],
        display_order=row["display_order"],
        icon=row["icon"],
        min_amount=float(row["min_amount"]) if row["min_amount"] else None,
        max_amount=float(row["max_amount"]) if row["max_amount"] else None,
        fees_percentage=float(row["fees_percentage"]) if row["fees_percentage"] else 0,
        fees_fixed=float(row["fees_fixed"]) if row["fees_fixed"] else 0,
        created_at=row["created_at"].isoformat() if row["created_at"] else None,
        updated_at=row["updated_at"].isoformat() if row["updated_at"] else None,
    )


@router.delete(
    "/treasury/payment-methods/{code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete payment method configuration",
    description="""
    Delete a payment method configuration.

    **Note:** Cannot delete default system methods (mobile_money, card, bank_transfer, cash, check).

    **Permissions:**
    - Requires 'treasury.manage_settings' permission
    """
)
async def delete_payment_method(
    code: str = Path(..., description="Payment method code"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.manage_settings"))
):
    """Delete payment method configuration"""
    # Prevent deletion of default methods
    default_methods = {"mobile_money", "card", "bank_transfer", "cash", "check"}
    if code in default_methods:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot delete default payment method: {code}"
        )

    result = await db.execute(
        "DELETE FROM payment_method_configurations WHERE code = $1",
        code
    )

    if result == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment method not found: {code}"
        )


@router.patch(
    "/treasury/payment-methods/reorder",
    response_model=List[PaymentMethodConfigResponse],
    summary="Reorder payment methods",
    description="""
    Update the display order of payment methods.

    **Permissions:**
    - Requires 'treasury.manage_settings' permission
    """
)
async def reorder_payment_methods(
    body: PaymentMethodReorderRequest,
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.manage_settings"))
):
    """Reorder payment methods by updating display_order"""
    # Update display_order for each method in the list
    for idx, code in enumerate(body.order):
        await db.execute(
            "UPDATE payment_method_configurations SET display_order = $1, updated_at = NOW() WHERE code = $2",
            idx + 1, code
        )

    # Return updated list
    return await list_payment_methods(active_only=False, db=db, current_user=current_user, _=None)


# ═══════════════════════════════════════════════════════════════
# TREASURY AUDIT (Phase 1A)
# ═══════════════════════════════════════════════════════════════

class AuditEntryResponse(BaseModel):
    """Response for a single audit entry."""
    id: str
    payment_id: str
    payment_reference: str
    service_request_id: Optional[str] = None
    service_request_reference: Optional[str] = None
    action: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    comment: Optional[str] = None
    agent_profile_id: Optional[str] = None  # UUID from agent_profiles table
    agent_name: Optional[str] = None
    agent_email: Optional[str] = None
    action_duration_seconds: Optional[int] = None
    ip_address: Optional[str] = None
    created_at: str


class AuditListResponse(BaseModel):
    """List of audit entries."""
    entries: List[AuditEntryResponse]
    total: int
    page: int = 1
    page_size: int = 50


class PaymentAuditDetailResponse(BaseModel):
    """Detailed audit history for a single payment."""
    payment_id: str
    payment_reference: str
    service_request_id: Optional[str] = None
    service_request_reference: Optional[str] = None
    workflow_code: Optional[str] = None
    current_status: str
    created_at: str
    timeline: List[AuditEntryResponse]
    total_processing_minutes: Optional[float] = None
    lock_count: int = 0


@router.get(
    "/treasury/audit",
    response_model=AuditListResponse,
    summary="Get Treasury audit history",
    description="""
    Get audit trail of all Treasury actions (lock, validate, reject, etc.)

    **Filters:**
    - payment_id: Filter by specific payment UUID
    - agent_profile_id: Filter by agent_profile UUID who performed action
    - action: Filter by action type (lock_for_review, approve, reject, etc.)
    - date_from / date_to: Filter by date range

    **Permissions:**
    - Requires 'treasury_audit.view' permission
    """
)
async def get_treasury_audit(
    payment_id: Optional[str] = Query(None, description="Filter by payment ID"),
    agent_profile_id: Optional[str] = Query(None, description="Filter by agent_profile UUID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    entity_location_id: Optional[str] = Query(None, description="Filter by agent site location"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_audit.view"))
):
    """Get Treasury audit trail"""
    # Resolve site scope for non-main-office supervisors
    tctx = await _get_treasury_context(db, current_user.id)
    effective_location_id = tctx.get_effective_location(entity_location_id)

    # Bug 1 fix dynamic (2026-05-06): scope by tctx.entity_code (own entity
    # for non-global supervisors, None for treasury.view_all admins meaning
    # see-all). Endpoint historically TESORO-dedicated but now reusable for
    # any payment-validating entity (AYUNTAMIENTO, CAMARA, etc.) without
    # hardcoded values. None = no filter (admin global scope).
    target_entity_code = (
        None if tctx.has_global_scope or not tctx.entity_code
        else tctx.entity_code
    )

    # Build dynamic WHERE clause
    where_clauses = []
    params = []
    param_idx = 1

    # Entity scope: only include audit entries linked to a payment of the
    # supervisor's entity. Use EXISTS (not JOIN) so the count_query that
    # doesn't join service_payments still works.
    if target_entity_code:
        where_clauses.append(
            f"EXISTS (SELECT 1 FROM service_payments sp2 "
            f"WHERE sp2.id = pva.payment_id AND sp2.entity_code = ${param_idx})"
        )
        params.append(target_entity_code)
        param_idx += 1

    # Site-scope: filter audit entries by agent location
    if effective_location_id:
        where_clauses.append(f"pva.agent_profile_id IN (SELECT id FROM agent_profiles WHERE entity_location_id = ${param_idx}::uuid AND is_active = true)")
        params.append(effective_location_id)
        param_idx += 1

    if payment_id:
        where_clauses.append(f"pva.payment_id = ${param_idx}::uuid")
        params.append(payment_id)
        param_idx += 1

    if agent_profile_id:
        where_clauses.append(f"pva.agent_profile_id = ${param_idx}::uuid")
        params.append(agent_profile_id)
        param_idx += 1

    if action:
        where_clauses.append(f"pva.action::text = ${param_idx}")
        params.append(action)
        param_idx += 1

    if date_from:
        where_clauses.append(f"pva.created_at >= ${param_idx}")
        params.append(date_from)
        param_idx += 1

    if date_to:
        where_clauses.append(f"pva.created_at < ${param_idx} + INTERVAL '1 day'")
        params.append(date_to)
        param_idx += 1

    where_sql = (" AND ".join(where_clauses)) if where_clauses else "TRUE"
    offset = (page - 1) * page_size

    query = f"""
        SELECT
            pva.id,
            pva.payment_id,
            sp.payment_reference,
            sp.service_request_id,
            sr.reference AS service_request_reference,
            pva.action::text AS action,
            pva.from_status::text AS from_status,
            pva.to_status::text AS to_status,
            pva.comment,
            pva.agent_profile_id,
            u.full_name AS agent_name,
            u.email AS agent_email,
            pva.action_duration_seconds,
            pva.ip_address::text AS ip_address,
            pva.created_at
        FROM payment_validation_audit pva
        JOIN service_payments sp ON sp.id = pva.payment_id
        LEFT JOIN service_requests sr ON sr.id = sp.service_request_id
        LEFT JOIN agent_profiles ap ON ap.id = pva.agent_profile_id
        LEFT JOIN users u ON u.id = pva.agent_user_id
        WHERE {where_sql}
        ORDER BY pva.created_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """
    params.extend([page_size, offset])

    rows = await db.fetch(query, *params)

    # Get total count (excludes the trailing LIMIT/OFFSET params)
    count_query = f"""
        SELECT COUNT(*)
        FROM payment_validation_audit pva
        WHERE {where_sql}
    """
    total = await db.fetchval(count_query, *params[:param_idx - 1])

    entries = []
    for row in rows:
        entries.append(AuditEntryResponse(
            id=str(row["id"]),
            payment_id=str(row["payment_id"]),
            payment_reference=row["payment_reference"],
            service_request_id=str(row["service_request_id"]) if row["service_request_id"] else None,
            service_request_reference=row["service_request_reference"],
            action=row["action"],
            from_status=row["from_status"],
            to_status=row["to_status"],
            comment=row["comment"],
            agent_profile_id=str(row["agent_profile_id"]) if row["agent_profile_id"] else None,
            agent_name=row["agent_name"],
            agent_email=row["agent_email"],
            action_duration_seconds=row["action_duration_seconds"],
            ip_address=row["ip_address"],
            created_at=row["created_at"].isoformat(),
        ))

    return AuditListResponse(
        entries=entries,
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/treasury/payments/{payment_id}/audit",
    response_model=PaymentAuditDetailResponse,
    summary="Get payment audit history",
    description="""
    Get complete audit history for a specific payment.

    Returns timeline of all actions with processing time metrics.

    **Permissions:**
    - Requires 'treasury.audit.view' permission
    """
)
async def get_payment_audit_history(
    payment_id: str = Path(..., description="Payment ID"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_audit.view"))
):
    """Get complete audit history for a payment"""
    # Get payment info
    payment = await db.fetchrow("""
        SELECT
            sp.id,
            sp.payment_reference,
            sp.service_request_id,
            sr.reference AS service_request_reference,
            sr.workflow_code,
            sp.workflow_status,
            sp.created_at,
            sp.assigned_agent_id,
            sp.entity_code
        FROM service_payments sp
        LEFT JOIN service_requests sr ON sr.id = sp.service_request_id
        WHERE sp.id = $1::uuid
    """, payment_id)

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment not found: {payment_id}"
        )

    # P7 security (2026-05-06): scope check by entity. Audit history is
    # sensitive (reveals validators, comments, IPs).
    tctx = await _get_treasury_context(db, current_user.id)
    _authorize_payment_action(tctx, payment)

    # Get audit entries
    audit_rows = await db.fetch("""
        SELECT
            pva.id,
            pva.payment_id,
            pva.action::text AS action,
            pva.from_status::text AS from_status,
            pva.to_status::text AS to_status,
            pva.comment,
            pva.agent_profile_id,
            u.full_name AS agent_name,
            u.email AS agent_email,
            pva.action_duration_seconds,
            pva.ip_address::text AS ip_address,
            pva.created_at
        FROM payment_validation_audit pva
        LEFT JOIN agent_profiles ap ON ap.id = pva.agent_profile_id
        LEFT JOIN users u ON u.id = pva.agent_user_id
        WHERE pva.payment_id = $1::uuid
        ORDER BY pva.created_at ASC
    """, payment_id)

    # Get lock count
    lock_count = await db.fetchval("""
        SELECT COUNT(*) FROM payment_lock_history
        WHERE payment_id = $1::uuid
    """, payment_id)

    # Calculate total processing time
    total_processing = await db.fetchval("""
        SELECT EXTRACT(EPOCH FROM (
            COALESCE(sp.validated_at, NOW()) - sp.created_at
        )) / 60
        FROM service_payments sp
        WHERE sp.id = $1::uuid
          AND sp.validated_at IS NOT NULL
    """, payment_id)

    timeline = []
    for row in audit_rows:
        timeline.append(AuditEntryResponse(
            id=str(row["id"]),
            payment_id=str(row["payment_id"]),
            payment_reference=payment["payment_reference"],
            action=row["action"],
            from_status=row["from_status"],
            to_status=row["to_status"],
            comment=row["comment"],
            agent_profile_id=str(row["agent_profile_id"]) if row["agent_profile_id"] else None,
            agent_name=row["agent_name"],
            agent_email=row["agent_email"],
            action_duration_seconds=row["action_duration_seconds"],
            ip_address=row["ip_address"],
            created_at=row["created_at"].isoformat(),
        ))

    return PaymentAuditDetailResponse(
        payment_id=str(payment["id"]),
        payment_reference=payment["payment_reference"],
        service_request_id=str(payment["service_request_id"]) if payment["service_request_id"] else None,
        service_request_reference=payment["service_request_reference"],
        workflow_code=payment["workflow_code"],
        current_status=payment["workflow_status"],
        created_at=payment["created_at"].isoformat(),
        timeline=timeline,
        total_processing_minutes=float(total_processing) if total_processing else None,
        lock_count=lock_count or 0,
    )


# ═══════════════════════════════════════════════════════════════
# TREASURY DASHBOARD STATS
# ═══════════════════════════════════════════════════════════════


class TreasuryDashboardStatsResponse(BaseModel):
    """Dashboard statistics for Treasury Agent main page."""
    pending_validation_count: int
    unreconciled_count: int
    today_validated_count: int
    today_validated_amount: float
    currency: str = "XAF"


@router.get(
    "/treasury/stats/dashboard",
    response_model=TreasuryDashboardStatsResponse,
    summary="Get Treasury Dashboard Stats",
    description="""
    Get aggregated statistics for the Treasury Agent dashboard.

    **Returns:**
    - pending_validation_count: Payments awaiting agent validation
    - unreconciled_count: Bank transactions not yet matched to payments
    - today_validated_count: Payments validated today
    - today_validated_amount: Total amount validated today

    **Permissions:**
    - Requires 'treasury.validate_payment' or 'treasury_stat.view' permission
    """
)
async def get_treasury_dashboard_stats(
    entity_location_id: Optional[str] = Query(None, description="Filter by entity_location (site)"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required_any("treasury.validate_payment", "treasury_stat.view"))
):
    """Get aggregated statistics for Treasury Agent dashboard"""
    from loguru import logger

    user_id = current_user.id

    # Single query: profile + permissions + site scope
    tctx = await _get_treasury_context(db, user_id)
    is_supervisor = tctx.has_global_scope or tctx.is_supervisor

    if not tctx.has_profile:
        return TreasuryDashboardStatsResponse(
            pending_validation_count=0,
            unreconciled_count=0,
            today_validated_count=0,
            today_validated_amount=0.0,
            currency="XAF",
        )

    current_agent_profile_id = tctx.profile_id
    location_filter_id = tctx.get_effective_location(entity_location_id)

    # Build scoped queries
    # Scope hierarchy (P8.2 refactor — prevents cross-entity leak):
    #   - Regular agent: own assigned payments only
    #   - Global supervisor (treasury.view_all): all entities + all sites
    #   - Non-global supervisor: own entity (via assigned_ap.entity_id) +
    #     optional site filter
    if not is_supervisor and current_agent_profile_id:
        # Non-supervisor agent: scope by assigned_agent_id (their own payments only)
        agent_id = current_agent_profile_id
        logger.info(f"[Treasury Stats] Scoping by agent: {agent_id}")

        pending_count = await db.fetchval("""
            SELECT COUNT(*)
            FROM service_payments
            WHERE workflow_status IN ('pending_agent_review', 'docs_resubmitted')
              AND requires_agent_validation = true
              AND assigned_agent_id = $1::uuid
        """, agent_id)

        today_stats = await db.fetchrow("""
            SELECT
                COUNT(*) AS validated_count,
                COALESCE(SUM(total_amount), 0) AS validated_amount
            FROM service_payments
            WHERE workflow_status IN ('approved_by_agent', 'completed')
              AND validated_at >= CURRENT_DATE
              AND validated_at < CURRENT_DATE + INTERVAL '1 day'
              AND assigned_agent_id = $1::uuid
        """, agent_id)
    else:
        # Supervisor branch — build entity + location filter dynamically.
        # Entity filter uses sp.entity_code (payment ownership) for stable
        # visibility even if the payment gets cross-entity reassigned.
        # Location filter still uses assigned_ap (the agent processing the
        # payment) because location is about where the work is physically
        # happening, not where the money is owed.
        filter_clauses = []
        filter_params: list = []
        needs_join_ap = False

        if not tctx.has_global_scope and tctx.entity_code:
            filter_clauses.append(f"sp.entity_code = ${len(filter_params) + 1}")
            filter_params.append(tctx.entity_code)

        if location_filter_id:
            filter_clauses.append(f"assigned_ap.entity_location_id = ${len(filter_params) + 1}::uuid")
            filter_params.append(str(location_filter_id))
            needs_join_ap = True

        join_sql = "JOIN agent_profiles assigned_ap ON assigned_ap.id = sp.assigned_agent_id" if needs_join_ap else ""
        where_extra = (" AND " + " AND ".join(filter_clauses)) if filter_clauses else ""

        logger.info(
            f"[Treasury Stats] Supervisor scope: entity_id={tctx.entity_id}, "
            f"location={location_filter_id}, global={tctx.has_global_scope}"
        )

        pending_count = await db.fetchval(f"""
            SELECT COUNT(*)
            FROM service_payments sp
            {join_sql}
            WHERE sp.workflow_status IN ('pending_agent_review', 'docs_resubmitted')
              AND sp.requires_agent_validation = true
              {where_extra}
        """, *filter_params)

        today_stats = await db.fetchrow(f"""
            SELECT
                COUNT(*) AS validated_count,
                COALESCE(SUM(sp.total_amount), 0) AS validated_amount
            FROM service_payments sp
            {join_sql}
            WHERE sp.workflow_status IN ('approved_by_agent', 'completed')
              AND sp.validated_at >= CURRENT_DATE
              AND sp.validated_at < CURRENT_DATE + INTERVAL '1 day'
              {where_extra}
        """, *filter_params)

    # Unreconciled bank transactions — supervisor-only metric
    if is_supervisor:
        unreconciled_count = await db.fetchval("""
            SELECT COUNT(*)
            FROM bank_transactions
            WHERE status = 'unreconciled'
        """)
    else:
        unreconciled_count = 0

    return TreasuryDashboardStatsResponse(
        pending_validation_count=pending_count or 0,
        unreconciled_count=unreconciled_count or 0,
        today_validated_count=today_stats["validated_count"] or 0,
        today_validated_amount=float(today_stats["validated_amount"] or 0),
        currency="XAF",
    )


# ═══════════════════════════════════════════════════════════════
# TREASURY LOCATIONS (for site filter dropdown)
# ═══════════════════════════════════════════════════════════════


@router.get(
    "/treasury/locations",
    summary="Get entity locations for site filter",
    description="""
    List active entity_locations for the caller's entity (for site filter dropdowns).

    Scope:
      - Global supervisor (treasury.view_all): all active entity_locations across all entities
      - Non-global supervisor / agent: locations of own entity only
    """,
)
async def get_treasury_locations(
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.validate_payment"))
):
    """Get active entity locations scoped to caller's entity (or all if global)."""
    tctx = await _get_treasury_context(db, current_user.id)

    if tctx.has_global_scope:
        rows = await db.fetch("""
            SELECT el.id, el.location_name, el.city, el.entity_id
            FROM entity_locations el
            WHERE el.is_active = true
            ORDER BY el.city, el.location_name
        """)
    elif tctx.entity_id:
        rows = await db.fetch("""
            SELECT el.id, el.location_name, el.city, el.entity_id
            FROM entity_locations el
            WHERE el.entity_id = $1::uuid AND el.is_active = true
            ORDER BY el.city, el.location_name
        """, tctx.entity_id)
    else:
        rows = []
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════
# TREASURY SLA STATS (Phase 1B)
# ═══════════════════════════════════════════════════════════════


class SLAStatsResponse(BaseModel):
    """SLA statistics for Treasury dashboard."""
    total_pending: int
    on_time: int
    warning: int
    critical: int
    breached: int
    avg_processing_minutes: Optional[float] = None
    max_processing_minutes: Optional[float] = None
    sla_respect_rate: float
    by_payment_method: Optional[Dict[str, Dict[str, int]]] = None


@router.get(
    "/treasury/stats/sla",
    response_model=SLAStatsResponse,
    summary="Get SLA statistics",
    description="""
    Get SLA statistics for pending payments.

    **SLA Status Categories:**
    - on_time: SLA deadline > 6 hours from now
    - warning: SLA deadline 2-6 hours from now
    - critical: SLA deadline < 2 hours from now
    - breached: SLA deadline passed

    **Permissions:**
    - Requires 'treasury.stats.view' permission
    """
)
async def get_sla_stats(
    entity_location_id: Optional[str] = Query(None, description="Filter by entity_location (site)"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_stat.view"))
):
    """Get SLA statistics for Treasury dashboard"""
    # Site-scoping
    tctx = await _get_treasury_context(db, current_user.id)
    effective_loc = tctx.get_effective_location(entity_location_id)

    # Bug 1 fix (2026-05-06): scope by entity_code (own entity for non-global
    # supervisor, all entities for treasury.view_all admins) so SLA stats
    # don't leak Ayuntamiento/Camara payments into a TESORO supervisor view.
    # Mirrors the pattern used by /treasury/stats/dashboard.
    loc_params: list = []
    entity_clause = ""
    if not tctx.has_global_scope and tctx.entity_code:
        loc_params.append(tctx.entity_code)
        entity_clause = f"AND sp.entity_code = ${len(loc_params)}"

    loc_filter = ""
    if effective_loc:
        loc_params.append(effective_loc)
        loc_filter = f"AND sp.assigned_agent_id IN (SELECT id FROM agent_profiles WHERE entity_location_id = ${len(loc_params)}::uuid AND is_active = true)"

    # Combine both clauses (entity + optional location) for query templating
    loc_filter = f"{entity_clause} {loc_filter}".strip()

    # Get SLA breakdown for pending payments
    sla_stats = await db.fetchrow(f"""
        WITH pending_payments AS (
            SELECT
                sp.id,
                sp.payment_method,
                sp.sla_target_date,
                sp.created_at,
                CASE
                    WHEN sp.sla_target_date IS NULL THEN 'on_time'
                    WHEN sp.sla_target_date < NOW() THEN 'breached'
                    WHEN sp.sla_target_date - NOW() < INTERVAL '2 hours' THEN 'critical'
                    WHEN sp.sla_target_date - NOW() < INTERVAL '6 hours' THEN 'warning'
                    ELSE 'on_time'
                END AS sla_status
            FROM service_payments sp
            WHERE sp.workflow_status NOT IN (
                'completed', 'cancelled_by_user', 'cancelled_by_agent', 'expired'
            )
            {loc_filter}
        )
        SELECT
            COUNT(*) AS total_pending,
            COUNT(*) FILTER (WHERE sla_status = 'on_time') AS on_time,
            COUNT(*) FILTER (WHERE sla_status = 'warning') AS warning,
            COUNT(*) FILTER (WHERE sla_status = 'critical') AS critical,
            COUNT(*) FILTER (WHERE sla_status = 'breached') AS breached
        FROM pending_payments
    """, *loc_params)

    # Get processing time stats for completed payments
    time_stats = await db.fetchrow(f"""
        SELECT
            AVG(EXTRACT(EPOCH FROM (sp.validated_at - sp.created_at)) / 60) AS avg_minutes,
            MAX(EXTRACT(EPOCH FROM (sp.validated_at - sp.created_at)) / 60) AS max_minutes
        FROM service_payments sp
        WHERE sp.workflow_status = 'completed'
          AND sp.validated_at IS NOT NULL
          AND sp.validated_at >= NOW() - INTERVAL '30 days'
          {loc_filter}
    """, *loc_params)

    # Calculate SLA respect rate from completed payments
    sla_rate = await db.fetchrow(f"""
        SELECT
            COUNT(*) AS total_completed,
            COUNT(*) FILTER (WHERE sp.sla_escalated = false OR sp.sla_escalated IS NULL) AS respected
        FROM service_payments sp
        WHERE sp.workflow_status = 'completed'
          AND sp.validated_at >= NOW() - INTERVAL '30 days'
          {loc_filter}
    """, *loc_params)

    # Get breakdown by payment method
    method_breakdown = await db.fetch(f"""
        WITH pending_payments AS (
            SELECT
                sp.payment_method::text AS method,
                CASE
                    WHEN sp.sla_target_date IS NULL THEN 'on_time'
                    WHEN sp.sla_target_date < NOW() THEN 'breached'
                    WHEN sp.sla_target_date - NOW() < INTERVAL '2 hours' THEN 'critical'
                    WHEN sp.sla_target_date - NOW() < INTERVAL '6 hours' THEN 'warning'
                    ELSE 'on_time'
                END AS sla_status
            FROM service_payments sp
            WHERE sp.workflow_status NOT IN (
                'completed', 'cancelled_by_user', 'cancelled_by_agent', 'expired'
            )
            {loc_filter}
        )
        SELECT
            method,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE sla_status = 'on_time') AS on_time,
            COUNT(*) FILTER (WHERE sla_status = 'warning') AS warning,
            COUNT(*) FILTER (WHERE sla_status = 'critical') AS critical,
            COUNT(*) FILTER (WHERE sla_status = 'breached') AS breached
        FROM pending_payments
        GROUP BY method
    """, *loc_params)

    by_method = {}
    for row in method_breakdown:
        by_method[row["method"]] = {
            "total": row["total"],
            "on_time": row["on_time"],
            "warning": row["warning"],
            "critical": row["critical"],
            "breached": row["breached"],
        }

    # Calculate SLA respect rate
    total_completed = sla_rate["total_completed"] or 0
    respected = sla_rate["respected"] or 0
    respect_rate = (respected / total_completed * 100) if total_completed > 0 else 100.0

    return SLAStatsResponse(
        total_pending=sla_stats["total_pending"] or 0,
        on_time=sla_stats["on_time"] or 0,
        warning=sla_stats["warning"] or 0,
        critical=sla_stats["critical"] or 0,
        breached=sla_stats["breached"] or 0,
        avg_processing_minutes=float(time_stats["avg_minutes"]) if time_stats["avg_minutes"] else None,
        max_processing_minutes=float(time_stats["max_minutes"]) if time_stats["max_minutes"] else None,
        sla_respect_rate=round(respect_rate, 2),
        by_payment_method=by_method if by_method else None,
    )


# ═══════════════════════════════════════════════════════════════
# TREASURY KPIs (Phase 4)
# ═══════════════════════════════════════════════════════════════


class PaymentMethodKPI(BaseModel):
    method: str
    count: int
    amount: float
    percentage: float
    success_rate: float
    avg_processing_minutes: Optional[float] = None


class EntityKPI(BaseModel):
    entity_code: str
    entity_name: str
    count: int
    amount: float
    percentage: float


class DailyTrend(BaseModel):
    date: str
    count: int
    amount: float


class PeriodComparison(BaseModel):
    total_collected_change: float
    transactions_change: float
    trend: str  # 'up', 'down', 'stable'


class KPIResponse(BaseModel):
    period: str
    date_from: str
    date_to: str
    total_collected: float
    total_transactions: int
    avg_transaction_amount: float
    sla_respect_rate: float
    by_payment_method: List[PaymentMethodKPI]
    by_entity: List[EntityKPI]
    daily_trend: List[DailyTrend]
    previous_period: Optional[PeriodComparison] = None


class AgentStats(BaseModel):
    agent_profile_id: str  # UUID from agent_profiles table
    agent_name: str
    agent_email: Optional[str] = None
    validations_count: int
    rejections_count: int
    avg_processing_minutes: float
    sla_respect_rate: float
    current_workload: int


class AgentPerformanceResponse(BaseModel):
    period: str
    date_from: str
    date_to: str
    agents: List[AgentStats]
    total_validations: int
    total_rejections: int


@router.get(
    "/treasury/stats/kpis",
    response_model=KPIResponse,
    summary="Get Treasury KPIs",
    description="""
    Get comprehensive Treasury KPIs for the dashboard.

    **Period Options:**
    - day: Current day
    - week: Current week (Mon-Sun)
    - month: Current month
    - year: Current year
    - custom: Use date_from and date_to

    **Returns:**
    - Total collected amount and transaction count
    - Breakdown by payment method
    - Top 10 ministries by amount
    - Daily trend for the period
    - Comparison with previous period

    **Permissions:**
    - Requires 'treasury.stats.view' permission
    """
)
async def get_treasury_kpis(
    period: str = Query("month", regex="^(day|week|month|year|custom)$"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD) for custom period"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD) for custom period"),
    entity_location_id: Optional[str] = Query(None, description="Filter by entity_location (site)"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_stat.view"))
):
    """Get Treasury KPIs for executive dashboard"""
    from datetime import datetime, timedelta

    # Site-scoping: filter by agents at a specific TESORO location
    tctx = await _get_treasury_context(db, current_user.id)
    effective_loc = tctx.get_effective_location(entity_location_id)

    # Calculate date range based on period
    now = datetime.now()
    if period == "day":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    elif period == "week":
        start_date = now - timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    elif period == "month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    elif period == "year":
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    else:  # custom
        if not date_from or not date_to:
            raise HTTPException(status_code=400, detail="date_from and date_to required for custom period")
        start_date = datetime.strptime(date_from, "%Y-%m-%d")
        end_date = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    # Build location filter for KPI queries
    kpi_loc_filter = ""
    kpi_base_params = [start_date, end_date]
    if effective_loc:
        kpi_loc_filter = "AND sp.assigned_agent_id IN (SELECT id FROM agent_profiles WHERE entity_location_id = $3::uuid AND is_active = true)"
        kpi_base_params.append(effective_loc)

    # Get main KPIs
    main_stats = await db.fetchrow(f"""
        SELECT
            COALESCE(SUM(sp.total_amount), 0) AS total_collected,
            COUNT(*) AS total_transactions,
            COALESCE(AVG(sp.total_amount), 0) AS avg_amount
        FROM service_payments sp
        WHERE sp.workflow_status = 'completed'
          AND sp.validated_at BETWEEN $1 AND $2
          {kpi_loc_filter}
    """, *kpi_base_params)

    # Get SLA respect rate
    sla_stats = await db.fetchrow(f"""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE sp.sla_escalated = false OR sp.sla_escalated IS NULL) AS respected
        FROM service_payments sp
        WHERE sp.workflow_status = 'completed'
          AND sp.validated_at BETWEEN $1 AND $2
          {kpi_loc_filter}
    """, *kpi_base_params)

    total_for_sla = sla_stats["total"] or 0
    sla_rate = (sla_stats["respected"] / total_for_sla * 100) if total_for_sla > 0 else 100.0

    # Get breakdown by payment method
    method_stats = await db.fetch(f"""
        SELECT
            sp.payment_method::text AS method,
            COUNT(*) AS count,
            COALESCE(SUM(sp.total_amount), 0) AS amount,
            AVG(EXTRACT(EPOCH FROM (sp.validated_at - sp.created_at)) / 60) AS avg_minutes,
            COUNT(*) FILTER (WHERE sp.sla_escalated = false OR sp.sla_escalated IS NULL)::float /
                NULLIF(COUNT(*), 0) * 100 AS success_rate
        FROM service_payments sp
        WHERE sp.workflow_status = 'completed'
          AND sp.validated_at BETWEEN $1 AND $2
          {kpi_loc_filter}
        GROUP BY sp.payment_method
        ORDER BY amount DESC
    """, *kpi_base_params)

    total_amount = float(main_stats["total_collected"]) or 1
    by_payment_method = [
        PaymentMethodKPI(
            method=row["method"] or "unknown",
            count=row["count"],
            amount=float(row["amount"]),
            percentage=round(float(row["amount"]) / total_amount * 100, 1),
            success_rate=round(float(row["success_rate"]) if row["success_rate"] else 100.0, 1),
            avg_processing_minutes=round(float(row["avg_minutes"]), 1) if row["avg_minutes"] else None
        )
        for row in method_stats
    ]

    # Get top 10 entities
    entity_stats = await db.fetch(f"""
        SELECT
            sp.entity_code,
            COALESCE(e.name, sp.entity_code) AS entity_name,
            COUNT(*) AS count,
            COALESCE(SUM(sp.total_amount), 0) AS amount
        FROM service_payments sp
        LEFT JOIN entities e ON e.code = sp.entity_code
        WHERE sp.workflow_status = 'completed'
          AND sp.validated_at BETWEEN $1 AND $2
          {kpi_loc_filter}
        GROUP BY sp.entity_code, e.name
        ORDER BY amount DESC
        LIMIT 10
    """, *kpi_base_params)

    by_entity = [
        EntityKPI(
            entity_code=row["entity_code"],
            entity_name=row["entity_name"],
            count=row["count"],
            amount=float(row["amount"]),
            percentage=round(float(row["amount"]) / total_amount * 100, 1) if total_amount > 0 else 0
        )
        for row in entity_stats
    ]

    # Get daily trend
    daily_stats = await db.fetch(f"""
        SELECT
            DATE(sp.validated_at) AS date,
            COUNT(*) AS count,
            COALESCE(SUM(sp.total_amount), 0) AS amount
        FROM service_payments sp
        WHERE sp.workflow_status = 'completed'
          AND sp.validated_at BETWEEN $1 AND $2
          {kpi_loc_filter}
        GROUP BY DATE(sp.validated_at)
        ORDER BY date
    """, *kpi_base_params)

    daily_trend = [
        DailyTrend(
            date=str(row["date"]),
            count=row["count"],
            amount=float(row["amount"])
        )
        for row in daily_stats
    ]

    # Get previous period comparison
    period_duration = end_date - start_date
    prev_start = start_date - period_duration - timedelta(days=1)
    prev_end = start_date - timedelta(days=1)

    prev_loc_filter = ""
    prev_params = [prev_start, prev_end]
    if effective_loc:
        prev_loc_filter = "AND sp.assigned_agent_id IN (SELECT id FROM agent_profiles WHERE entity_location_id = $3::uuid AND is_active = true)"
        prev_params.append(effective_loc)
    prev_stats = await db.fetchrow(f"""
        SELECT
            COALESCE(SUM(sp.total_amount), 0) AS total_collected,
            COUNT(*) AS total_transactions
        FROM service_payments sp
        WHERE sp.workflow_status = 'completed'
          AND sp.validated_at BETWEEN $1 AND $2
          {prev_loc_filter}
    """, *prev_params)

    prev_collected = float(prev_stats["total_collected"]) if prev_stats["total_collected"] else 0
    prev_transactions = prev_stats["total_transactions"] or 0

    previous_period = None
    if prev_collected > 0 or prev_transactions > 0:
        collected_change = ((float(main_stats["total_collected"]) - prev_collected) / prev_collected * 100) if prev_collected > 0 else 0
        trans_change = ((main_stats["total_transactions"] - prev_transactions) / prev_transactions * 100) if prev_transactions > 0 else 0

        trend = "stable"
        if collected_change > 5:
            trend = "up"
        elif collected_change < -5:
            trend = "down"

        previous_period = PeriodComparison(
            total_collected_change=round(collected_change, 1),
            transactions_change=round(trans_change, 1),
            trend=trend
        )

    return KPIResponse(
        period=period,
        date_from=str(start_date.date()),
        date_to=str(end_date.date()),
        total_collected=float(main_stats["total_collected"]),
        total_transactions=main_stats["total_transactions"],
        avg_transaction_amount=float(main_stats["avg_amount"]),
        sla_respect_rate=round(sla_rate, 1),
        by_payment_method=by_payment_method,
        by_entity=by_entity,
        daily_trend=daily_trend,
        previous_period=previous_period
    )


@router.get(
    "/treasury/stats/agents",
    response_model=AgentPerformanceResponse,
    summary="Get Agent Performance Statistics",
    description="""
    Get performance statistics for Treasury agents.

    **Returns:**
    - Validations and rejections per agent
    - Average processing time
    - SLA respect rate
    - Current workload

    **Permissions:**
    - Requires 'treasury.stats.view' permission
    """
)
async def get_agent_performance(
    period: str = Query("month", regex="^(day|week|month|year|custom)$"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    entity_location_id: Optional[str] = Query(None, description="Filter by agent site location"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_stat.view"))
):
    """Get agent performance statistics"""
    from datetime import datetime, timedelta

    # Calculate date range
    now = datetime.now()
    if period == "day":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    elif period == "week":
        start_date = now - timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    elif period == "month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    elif period == "year":
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    else:  # custom
        if not date_from or not date_to:
            raise HTTPException(status_code=400, detail="date_from and date_to required for custom period")
        start_date = datetime.strptime(date_from, "%Y-%m-%d")
        end_date = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    # Resolve site scope for non-main-office supervisors
    tctx = await _get_treasury_context(db, current_user.id)
    effective_location_id = tctx.get_effective_location(entity_location_id)

    # Bug 1 fix dynamic (2026-05-06): scope by tctx.entity_code (own entity
    # for non-global supervisors, None for treasury.view_all admins).
    target_entity_code = (
        None if tctx.has_global_scope or not tctx.entity_code
        else tctx.entity_code
    )

    # Build dynamic filters for agent site + entity scoping. Numbering of $N
    # is local to this query: $1=start_date, $2=end_date, then each filter
    # appends in order it is constructed.
    query_params = [start_date, end_date]
    entity_clause = ""
    if target_entity_code:
        query_params.append(target_entity_code)
        entity_clause = f"AND sp.entity_code = ${len(query_params)}"
    agent_loc_filter = ""
    if effective_location_id:
        query_params.append(effective_location_id)
        agent_loc_filter = (
            f"AND pva.agent_profile_id IN (SELECT id FROM agent_profiles "
            f"WHERE entity_location_id = ${len(query_params)}::uuid AND is_active = true)"
        )

    # Get agent performance from audit log
    # Note: agent_profile_id (UUID) is the current standard, agent_id (int) is deprecated
    agent_stats = await db.fetch(f"""
        WITH agent_actions AS (
            SELECT
                pva.agent_profile_id,
                pva.agent_user_id,
                u.full_name AS agent_name,
                u.email AS agent_email,
                pva.action,
                pva.action_duration_seconds,
                sp.sla_escalated
            FROM payment_validation_audit pva
            JOIN users u ON u.id = pva.agent_user_id
            JOIN service_payments sp ON sp.id = pva.payment_id
            WHERE pva.created_at BETWEEN $1 AND $2
              AND pva.agent_user_id IS NOT NULL
              {entity_clause}
              {agent_loc_filter}
        ),
        agent_summary AS (
            SELECT
                agent_profile_id,
                agent_user_id,
                agent_name,
                agent_email,
                COUNT(*) FILTER (WHERE action = 'approve') AS validations,
                COUNT(*) FILTER (WHERE action = 'reject') AS rejections,
                AVG(action_duration_seconds) / 60.0 AS avg_minutes,
                COUNT(*) FILTER (WHERE sla_escalated = false OR sla_escalated IS NULL)::float /
                    NULLIF(COUNT(*), 0) * 100 AS sla_rate
            FROM agent_actions
            GROUP BY agent_profile_id, agent_user_id, agent_name, agent_email
        )
        SELECT
            as2.agent_profile_id,
            as2.agent_user_id,
            as2.agent_name,
            as2.agent_email,
            as2.validations,
            as2.rejections,
            as2.avg_minutes,
            as2.sla_rate,
            COALESCE(aw.current_assignments, 0) AS current_workload
        FROM agent_summary as2
        LEFT JOIN agent_workloads aw ON aw.agent_profile_id = as2.agent_profile_id
        ORDER BY (as2.validations + as2.rejections) DESC
    """, *query_params)

    agents = [
        AgentStats(
            agent_profile_id=str(row["agent_profile_id"]) if row["agent_profile_id"] else str(row["agent_user_id"]) if row["agent_user_id"] else "unknown",
            agent_name=row["agent_name"] or "Unknown",
            agent_email=row["agent_email"],
            validations_count=row["validations"] or 0,
            rejections_count=row["rejections"] or 0,
            avg_processing_minutes=round(float(row["avg_minutes"]) if row["avg_minutes"] else 0, 1),
            sla_respect_rate=round(float(row["sla_rate"]) if row["sla_rate"] else 100.0, 1),
            current_workload=row["current_workload"] or 0
        )
        for row in agent_stats
    ]

    total_validations = sum(a.validations_count for a in agents)
    total_rejections = sum(a.rejections_count for a in agents)

    return AgentPerformanceResponse(
        period=period,
        date_from=str(start_date.date()),
        date_to=str(end_date.date()),
        agents=agents,
        total_validations=total_validations,
        total_rejections=total_rejections
    )


# ═══════════════════════════════════════════════════════════════
# TREASURY SUPERVISOR OVERVIEW (Phase 3 - Pilotage Dashboard)
# ═══════════════════════════════════════════════════════════════


@router.get(
    "/treasury/stats/supervisor-overview",
    summary="Get Supervisor Overview for Treasury Dashboard",
    description="""
    Combined endpoint returning all data needed for the supervisor piloting dashboard.
    Uses asyncio.gather for parallel SQL queries (6 queries).

    **Returns:**
    - payment_flow: Daily validated amounts (7d + 30d)
    - agent_load: Agent workload with capacity
    - sla_alerts: Payments at risk of SLA breach
    - method_distribution: Payment method breakdown
    - top_services: Top 5 workflow codes by amount
    - recent_activity: Last 10 agent actions

    **Permissions:** treasury.view_all
    """
)
async def get_supervisor_overview(
    days: int = Query(30, ge=7, le=90, description="Lookback period in days"),
    location_id: Optional[str] = Query(None, description="Filter by entity_location_id"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.view_all"))
):
    """Get supervisor overview for treasury piloting dashboard."""
    import asyncio
    from app.core.cache import get_cache
    from app.database.connection import db_manager

    # Resolve effective location filter via shared context
    tctx = await _get_treasury_context(db, current_user.id)
    effective_location_id = tctx.get_effective_location(location_id)
    is_main_office = tctx.is_main_office

    cache = get_cache()
    loc_suffix = f":{effective_location_id}" if effective_location_id else ""
    # v2 (2026-05-06): bumped after Bug 1 fix to invalidate stale cross-entity cache
    cache_key = f"treasury:supervisor_overview:v2:{days}{loc_suffix}"
    cached = await cache.get(cache_key)
    if cached:
        # Inject is_main_office flag for frontend to know whether to show filter
        cached["is_main_office"] = is_main_office
        return cached

    now = datetime.now(timezone.utc)
    lookback_start = now - timedelta(days=days)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 6 parallel queries — each acquires its own connection from the pool.
    # asyncpg does NOT support concurrent operations on a single connection,
    # so we must use db_manager.get_connection() per coroutine.
    async def q_payment_flow():
        async with db_manager.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT
                    DATE(validated_at) AS date,
                    COUNT(*) AS count,
                    COALESCE(SUM(total_amount), 0) AS amount
                FROM service_payments
                WHERE workflow_status = 'completed'
                  AND validated_at >= $1
                GROUP BY DATE(validated_at)
                ORDER BY date
            """, lookback_start)
            return [{"date": str(r["date"]), "count": r["count"], "amount": float(r["amount"])} for r in rows]

    async def q_agent_load():
        async with db_manager.get_connection() as conn:
            rows = await conn.fetch("""
                WITH daily_completions AS (
                    SELECT pva.agent_profile_id, COUNT(*) AS completed_today
                    FROM payment_validation_audit pva
                    WHERE pva.action IN ('approve', 'reject')
                      AND pva.created_at >= $1
                    GROUP BY pva.agent_profile_id
                )
                SELECT
                    ap.id AS agent_profile_id,
                    u.full_name AS agent_name,
                    COALESCE(aw.current_assignments, 0) AS pending,
                    COALESCE(aw.pending_declarations, 0) AS in_progress,
                    COALESCE(dc.completed_today, 0) AS completed_today,
                    aw.workload_status,
                    COALESCE(aw.max_concurrent_assignments, 5) AS max_concurrent
                FROM agent_profiles ap
                JOIN users u ON u.id = ap.user_id
                LEFT JOIN agent_workloads aw ON aw.agent_profile_id = ap.id
                LEFT JOIN daily_completions dc ON dc.agent_profile_id = ap.id
                JOIN entities e ON e.id = ap.entity_id
                WHERE e.code = 'TESORO'
                  AND ap.is_active = true
                  AND ap.is_supervisor = false
                  AND ($2::uuid IS NULL OR ap.entity_location_id = $2::uuid)
                ORDER BY u.full_name
            """, today_start, effective_location_id)
            return [{
                "agent_profile_id": str(r["agent_profile_id"]),
                "agent_name": r["agent_name"] or "Unknown",
                "pending": r["pending"],
                "in_progress": r["in_progress"],
                "completed_today": r["completed_today"],
                "capacity_pct": round(r["pending"] / max(r["max_concurrent"], 1) * 100),
                "status": r["workload_status"] or "available",
            } for r in rows]

    async def q_sla_alerts():
        async with db_manager.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT
                    sp.id, sp.payment_reference, sp.total_amount, sp.currency,
                    sp.payment_method::text AS payment_method,
                    sp.created_at, sp.sla_target_date,
                    u.full_name AS user_name,
                    sr.reference AS request_reference,
                    CASE
                        WHEN sp.sla_target_date < NOW() THEN 'breached'
                        WHEN sp.sla_target_date < NOW() + INTERVAL '2 hours' THEN 'critical'
                        WHEN sp.sla_target_date < NOW() + INTERVAL '6 hours' THEN 'warning'
                        ELSE 'ok'
                    END AS sla_status,
                    EXTRACT(EPOCH FROM (sp.sla_target_date - NOW())) / 3600 AS hours_remaining
                FROM service_payments sp
                JOIN service_requests sr ON sr.id = sp.service_request_id
                JOIN users u ON u.id = sp.user_id
                WHERE sp.workflow_status IN ('pending_agent_review', 'agent_reviewing')
                  AND sp.requires_agent_validation = true
                  AND sp.sla_target_date IS NOT NULL
                  AND sp.sla_target_date < NOW() + INTERVAL '6 hours'
                ORDER BY sp.sla_target_date ASC
                LIMIT 20
            """)
            return [{
                "payment_id": str(r["id"]),
                "payment_reference": r["payment_reference"],
                "amount": float(r["total_amount"]),
                "currency": r["currency"] or "XAF",
                "payment_method": r["payment_method"],
                "user_name": r["user_name"],
                "request_reference": r["request_reference"],
                "sla_status": r["sla_status"],
                "hours_remaining": round(float(r["hours_remaining"]), 1) if r["hours_remaining"] else 0,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            } for r in rows]

    async def q_method_distribution():
        async with db_manager.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT
                    payment_method::text AS method,
                    COUNT(*) AS count,
                    COALESCE(SUM(total_amount), 0) AS amount
                FROM service_payments
                WHERE workflow_status = 'completed'
                  AND validated_at >= $1
                GROUP BY payment_method
                ORDER BY amount DESC
            """, lookback_start)
            total = sum(float(r["amount"]) for r in rows) or 1
            return [{
                "method": r["method"] or "unknown",
                "count": r["count"],
                "amount": float(r["amount"]),
                "percentage": round(float(r["amount"]) / total * 100, 1),
            } for r in rows]

    async def q_top_services():
        async with db_manager.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT
                    sr.workflow_code,
                    COALESCE(fs.name_es, sr.workflow_code) AS service_name,
                    COUNT(*) AS count,
                    COALESCE(SUM(sp.total_amount), 0) AS amount
                FROM service_payments sp
                JOIN service_requests sr ON sr.id = sp.service_request_id
                LEFT JOIN fiscal_services fs ON fs.id = sr.fiscal_service_id
                WHERE sp.workflow_status = 'completed'
                  AND sp.validated_at >= $1
                GROUP BY sr.workflow_code, fs.name_es
                ORDER BY amount DESC
                LIMIT 5
            """, lookback_start)
            return [{
                "workflow_code": r["workflow_code"],
                "service_name": r["service_name"],
                "count": r["count"],
                "amount": float(r["amount"]),
            } for r in rows]

    async def q_recent_activity():
        async with db_manager.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT
                    pva.id, pva.action::text, pva.created_at, pva.comment,
                    u.full_name AS agent_name,
                    sp.payment_reference, sp.total_amount, sp.currency,
                    sp.payment_method::text AS payment_method
                FROM payment_validation_audit pva
                JOIN users u ON u.id = pva.agent_user_id
                JOIN service_payments sp ON sp.id = pva.payment_id
                WHERE pva.created_at >= $1
                ORDER BY pva.created_at DESC
                LIMIT 10
            """, lookback_start)
            return [{
                "action": r["action"],
                "agent_name": r["agent_name"],
                "payment_reference": r["payment_reference"],
                "amount": float(r["total_amount"]),
                "currency": r["currency"] or "XAF",
                "payment_method": r["payment_method"],
                "comment": r["comment"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            } for r in rows]

    async def q_sla_compliance():
        """Historical SLA compliance — validated payments within lookback period."""
        async with db_manager.get_connection() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) AS total_validated,
                    COUNT(*) FILTER (
                        WHERE EXTRACT(EPOCH FROM (pva.created_at - sp.created_at)) / 3600 <= 24
                    ) AS within_sla,
                    COUNT(*) FILTER (
                        WHERE EXTRACT(EPOCH FROM (pva.created_at - sp.created_at)) / 3600 > 24
                    ) AS sla_breached,
                    COALESCE(
                        ROUND(AVG(EXTRACT(EPOCH FROM (pva.created_at - sp.created_at)) / 3600)::numeric, 1),
                        0
                    ) AS avg_hours,
                    COALESCE(
                        ROUND(MIN(EXTRACT(EPOCH FROM (pva.created_at - sp.created_at)) / 3600)::numeric, 1),
                        0
                    ) AS min_hours,
                    COALESCE(
                        ROUND(MAX(EXTRACT(EPOCH FROM (pva.created_at - sp.created_at)) / 3600)::numeric, 1),
                        0
                    ) AS max_hours,
                    COUNT(*) FILTER (
                        WHERE sp.workflow_status IN ('pending_agent_review', 'agent_reviewing')
                    ) AS currently_pending
                FROM payment_validation_audit pva
                JOIN service_payments sp ON sp.id = pva.payment_id
                WHERE pva.action IN ('approve', 'reject')
                  AND pva.created_at >= $1
            """, lookback_start)
            total = row["total_validated"] or 0
            within = row["within_sla"] or 0
            return {
                "total_validated": total,
                "within_sla": within,
                "sla_breached": row["sla_breached"] or 0,
                "compliance_pct": round(within / max(total, 1) * 100, 1),
                "avg_hours": float(row["avg_hours"]),
                "min_hours": float(row["min_hours"]),
                "max_hours": float(row["max_hours"]),
                "currently_pending": row["currently_pending"] or 0,
            }

    # Execute all 7 queries in parallel — each with its own pooled connection
    payment_flow, agent_load, sla_alerts, method_dist, top_services, recent, sla_compliance = await asyncio.gather(
        q_payment_flow(),
        q_agent_load(),
        q_sla_alerts(),
        q_method_distribution(),
        q_top_services(),
        q_recent_activity(),
        q_sla_compliance(),
    )

    result = {
        "payment_flow": payment_flow,
        "agent_load": agent_load,
        "sla_alerts": sla_alerts,
        "sla_alerts_count": len(sla_alerts),
        "sla_compliance": sla_compliance,
        "method_distribution": method_dist,
        "top_services": top_services,
        "recent_activity": recent,
        "period_days": days,
        "is_main_office": is_main_office,
        "generated_at": now.isoformat(),
    }

    await cache.set(cache_key, result, ttl=300)
    return result


# ═══════════════════════════════════════════════════════════════
# TREASURY WORKLOAD DASHBOARD (Carga de Trabajo)
# ═══════════════════════════════════════════════════════════════


@router.get(
    "/treasury/stats/workload-dashboard",
    summary="Get Workload Dashboard data for Treasury agents",
    description="""
    Combined endpoint returning 7 datasets for the Carga de Trabajo page.
    Uses asyncio.gather with separate DB connections for parallel queries.

    **Returns:**
    - daily_velocity: Daily approve/reject per agent (line chart)
    - agent_load: Current load per agent with capacity (horizontal bar)
    - sla_breakdown: On-time vs breached (donut chart)
    - volume_trend: Daily incoming vs outgoing (stacked area)
    - processing_times: Min/avg/max/p50 per agent (grouped bar)
    - kpis: Summary KPIs
    - rankings: Top agents by score

    **Permissions:** treasury_stat.view
    """
)
async def get_workload_dashboard(
    days: int = Query(30, ge=7, le=90, description="Lookback period in days"),
    entity_location_id: Optional[str] = Query(None, description="Filter by agent site location"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_stat.view"))
):
    """Get workload dashboard data for Carga de Trabajo page."""
    import asyncio
    from app.core.cache import get_cache
    from app.database.connection import db_manager

    # Resolve site scope for non-main-office supervisors
    tctx = await _get_treasury_context(db, current_user.id)
    effective_location_id = tctx.get_effective_location(entity_location_id)

    # Bug 1 fix dynamic (2026-05-06): scope by tctx.entity_code (own entity
    # for non-global supervisors, None for treasury.view_all admins meaning
    # see-all). Endpoint historically TESORO-dedicated but now reusable for
    # any payment-validating entity (AYUNTAMIENTO, CAMARA, etc.) without
    # hardcoded values. None = no filter (admin global scope).
    target_entity_code = (
        None if tctx.has_global_scope or not tctx.entity_code
        else tctx.entity_code
    )

    cache = get_cache()
    loc_key = effective_location_id or "all"
    entity_key = target_entity_code or "all"
    # v2 (2026-05-06): bumped after Bug 1 fix (entity_key added) to invalidate stale data
    cache_key = f"treasury:workload_dashboard:v2:{days}:{loc_key}:{entity_key}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    lookback_start = datetime.now(timezone.utc) - timedelta(days=days)

    # 7 parallel queries — each acquires its own connection from the pool.
    # Q1/Q5/Q7 use mv_agent_daily_workload (materialized view, refreshed every 15min)
    # Q2 uses CTE pre-aggregation from MV (no correlated subqueries)
    # Q3/Q4/Q6 query raw tables with partial indexes

    async def q_daily_velocity():
        async with db_manager.get_connection() as conn:
            params = [lookback_start]
            entity_clause = ""
            if target_entity_code:
                params.append(target_entity_code)
                entity_clause = f"""AND EXISTS (
                    SELECT 1 FROM agent_profiles ap2
                    JOIN entities e2 ON e2.id = ap2.entity_id
                    WHERE ap2.id = mv.agent_profile_id
                      AND e2.code = ${len(params)}
                      AND ap2.is_active = true
                )"""
            loc_filter = ""
            if effective_location_id:
                params.append(effective_location_id)
                loc_filter = f"AND agent_profile_id IN (SELECT id FROM agent_profiles WHERE entity_location_id = ${len(params)}::uuid AND is_active = true)"
            # Bug 1 fix (2026-05-06): mv_agent_daily_workload aggregates ALL
            # agents (no entity column). Without entity filter the supervisor
            # would see other entities' agents in workload charts. Filter is
            # dynamic via tctx.entity_code (None = global admin = see all).
            rows = await conn.fetch(f"""
                SELECT
                    report_date::text as date,
                    agent_name,
                    approved,
                    rejected
                FROM mv_agent_daily_workload mv
                WHERE report_date >= $1::date
                  {entity_clause}
                  {loc_filter}
                ORDER BY report_date
            """, *params)
            return [{"date": r["date"], "agent_name": r["agent_name"],
                     "approved": r["approved"], "rejected": r["rejected"]} for r in rows]

    async def q_agent_load():
        async with db_manager.get_connection() as conn:
            params = [lookback_start]
            entity_clause = ""
            if target_entity_code:
                params.append(target_entity_code)
                entity_clause = f"AND e.code = ${len(params)}"
            loc_filter = ""
            if effective_location_id:
                params.append(effective_location_id)
                loc_filter = f"AND ap.entity_location_id = ${len(params)}::uuid"
            rows = await conn.fetch(f"""
                WITH agent_period_stats AS (
                    SELECT
                        agent_profile_id,
                        SUM(total_actions) as completed_period,
                        COALESCE(
                            SUM(avg_duration_seconds * total_actions)
                            / NULLIF(SUM(total_actions), 0) / 3600.0,
                            0
                        ) as avg_hours
                    FROM mv_agent_daily_workload
                    WHERE report_date >= $1::date
                    GROUP BY agent_profile_id
                )
                SELECT
                    u.full_name as agent_name,
                    COALESCE(aw.pending_declarations, 0) as pending,
                    COALESCE(aw.current_assignments, 0) as in_progress,
                    COALESCE(aw.max_concurrent_assignments, 10) as capacity_max,
                    CASE WHEN COALESCE(aw.max_concurrent_assignments, 10) > 0
                        THEN ROUND(COALESCE(aw.current_assignments, 0)::numeric
                            / COALESCE(aw.max_concurrent_assignments, 10) * 100, 1)
                        ELSE 0
                    END as capacity_pct,
                    CASE
                        WHEN COALESCE(aw.current_assignments, 0) = 0 THEN 'available'
                        WHEN COALESCE(aw.current_assignments, 0)::numeric
                            / NULLIF(COALESCE(aw.max_concurrent_assignments, 10), 0) >= 0.8 THEN 'overloaded'
                        WHEN COALESCE(aw.current_assignments, 0)::numeric
                            / NULLIF(COALESCE(aw.max_concurrent_assignments, 10), 0) >= 0.5 THEN 'busy'
                        ELSE 'normal'
                    END as status,
                    COALESCE(aps.completed_period, 0)::int as completed_period,
                    ROUND(COALESCE(aps.avg_hours, 0)::numeric, 1) as avg_hours
                FROM agent_profiles ap
                JOIN entities e ON e.id = ap.entity_id
                JOIN users u ON u.id = ap.user_id
                LEFT JOIN agent_workloads aw ON aw.agent_profile_id = ap.id
                LEFT JOIN agent_period_stats aps ON aps.agent_profile_id = ap.id
                WHERE ap.is_active = true
                  {entity_clause}
                  {loc_filter}
                ORDER BY completed_period DESC
            """, *params)
            return [{"agent_name": r["agent_name"], "pending": r["pending"],
                     "in_progress": r["in_progress"], "capacity_max": r["capacity_max"],
                     "capacity_pct": float(r["capacity_pct"]),
                     "status": r["status"],
                     "completed_period": r["completed_period"],
                     "avg_hours": round(float(r["avg_hours"]), 1)} for r in rows]

    async def q_sla_breakdown():
        async with db_manager.get_connection() as conn:
            params = [lookback_start]
            entity_clause = ""
            if target_entity_code:
                params.append(target_entity_code)
                entity_clause = f"""AND EXISTS (
                      SELECT 1 FROM agent_profiles ap2
                      JOIN entities e2 ON e2.id = ap2.entity_id
                      WHERE ap2.id = pva.agent_profile_id
                        AND e2.code = ${len(params)}
                        AND ap2.is_active = true
                  )"""
            loc_filter = ""
            if effective_location_id:
                params.append(effective_location_id)
                loc_filter = (
                    f"AND pva.agent_profile_id IN (SELECT id FROM agent_profiles "
                    f"WHERE entity_location_id = ${len(params)}::uuid AND is_active = true)"
                )
            row = await conn.fetchrow(f"""
                SELECT
                    COUNT(*) FILTER (WHERE
                        sp.sla_target_date IS NOT NULL
                        AND pva.created_at <= sp.sla_target_date
                    ) as on_time,
                    COUNT(*) FILTER (WHERE
                        sp.sla_target_date IS NOT NULL
                        AND pva.created_at > sp.sla_target_date
                    ) as breached,
                    COUNT(*) FILTER (WHERE sp.sla_target_date IS NULL) as no_sla,
                    CASE WHEN COUNT(*) FILTER (WHERE sp.sla_target_date IS NOT NULL) > 0
                        THEN ROUND(
                            COUNT(*) FILTER (WHERE sp.sla_target_date IS NOT NULL
                                AND pva.created_at <= sp.sla_target_date)::numeric
                            / COUNT(*) FILTER (WHERE sp.sla_target_date IS NOT NULL) * 100, 1
                        )
                        ELSE 0
                    END as compliance_pct,
                    COALESCE(AVG(EXTRACT(EPOCH FROM (pva.created_at - sp.created_at)) / 3600.0)
                        FILTER (WHERE pva.action IN ('approve','reject')), 0) as avg_resolution_hours
                FROM payment_validation_audit pva
                JOIN service_payments sp ON sp.id = pva.payment_id
                WHERE pva.action IN ('approve', 'reject')
                  AND pva.created_at >= $1
                  {entity_clause}
                  {loc_filter}
            """, *params)
            return {
                "on_time": row["on_time"],
                "breached": row["breached"],
                "no_sla": row["no_sla"],
                "compliance_pct": float(row["compliance_pct"] or 0),
                "avg_resolution_hours": round(float(row["avg_resolution_hours"]), 1),
            }

    async def q_volume_trend():
        async with db_manager.get_connection() as conn:
            params = [lookback_start]
            entity_clause_sp = ""
            entity_clause_pva = ""
            if target_entity_code:
                params.append(target_entity_code)
                entity_clause_sp = f"AND sp.entity_code = ${len(params)}"
                entity_clause_pva = f"""AND EXISTS (
                          SELECT 1 FROM agent_profiles ap2
                          JOIN entities e2 ON e2.id = ap2.entity_id
                          WHERE ap2.id = pva.agent_profile_id
                            AND e2.code = ${len(params)}
                            AND ap2.is_active = true
                      )"""
            loc_filter_sp = ""
            loc_filter_pva = ""
            if effective_location_id:
                params.append(effective_location_id)
                loc_filter_sp = (
                    f"AND sp.assigned_agent_id IN (SELECT id FROM agent_profiles "
                    f"WHERE entity_location_id = ${len(params)}::uuid AND is_active = true)"
                )
                loc_filter_pva = (
                    f"AND pva.agent_profile_id IN (SELECT id FROM agent_profiles "
                    f"WHERE entity_location_id = ${len(params)}::uuid AND is_active = true)"
                )
            rows = await conn.fetch(f"""
                SELECT d.date::date,
                    COALESCE(incoming.cnt, 0) as incoming,
                    COALESCE(outgoing.cnt, 0) as outgoing
                FROM generate_series(
                    $1::date,
                    CURRENT_DATE,
                    '1 day'::interval
                ) d(date)
                LEFT JOIN (
                    SELECT sp.created_at::date as date, COUNT(*) as cnt
                    FROM service_payments sp
                    WHERE sp.created_at >= $1
                      {entity_clause_sp}
                      {loc_filter_sp}
                    GROUP BY sp.created_at::date
                ) incoming ON incoming.date = d.date::date
                LEFT JOIN (
                    SELECT pva.created_at::date as date, COUNT(*) as cnt
                    FROM payment_validation_audit pva
                    WHERE pva.action IN ('approve','reject')
                      AND pva.created_at >= $1
                      {entity_clause_pva}
                      {loc_filter_pva}
                    GROUP BY pva.created_at::date
                ) outgoing ON outgoing.date = d.date::date
                ORDER BY d.date
            """, *params)
            return [{"date": str(r["date"]), "incoming": r["incoming"],
                     "outgoing": r["outgoing"]} for r in rows]

    async def q_processing_times():
        async with db_manager.get_connection() as conn:
            params = [lookback_start]
            entity_clause = ""
            if target_entity_code:
                params.append(target_entity_code)
                entity_clause = f"""AND EXISTS (
                      SELECT 1 FROM agent_profiles ap2
                      JOIN entities e2 ON e2.id = ap2.entity_id
                      WHERE ap2.id = mv.agent_profile_id
                        AND e2.code = ${len(params)}
                        AND ap2.is_active = true
                  )"""
            loc_filter = ""
            if effective_location_id:
                params.append(effective_location_id)
                loc_filter = (
                    f"AND agent_profile_id IN (SELECT id FROM agent_profiles "
                    f"WHERE entity_location_id = ${len(params)}::uuid AND is_active = true)"
                )
            rows = await conn.fetch(f"""
                SELECT
                    agent_name,
                    ROUND((MIN(min_duration_seconds) / 3600.0)::numeric, 2) as min_hours,
                    ROUND((SUM(avg_duration_seconds * total_actions)
                        / NULLIF(SUM(total_actions), 0) / 3600.0)::numeric, 2) as avg_hours,
                    ROUND((MAX(max_duration_seconds) / 3600.0)::numeric, 2) as max_hours,
                    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP
                        (ORDER BY COALESCE(p50_duration_seconds, 0)) / 3600.0)::numeric, 2) as p50_hours,
                    SUM(total_actions)::int as count
                FROM mv_agent_daily_workload mv
                WHERE report_date >= $1::date
                  AND avg_duration_seconds IS NOT NULL
                  {entity_clause}
                  {loc_filter}
                GROUP BY agent_profile_id, agent_name
                ORDER BY avg_hours
            """, *params)
            return [{"agent_name": r["agent_name"], "min_hours": float(r["min_hours"] or 0),
                     "avg_hours": float(r["avg_hours"] or 0), "max_hours": float(r["max_hours"] or 0),
                     "p50_hours": float(r["p50_hours"] or 0), "count": r["count"]} for r in rows]

    async def q_kpis():
        async with db_manager.get_connection() as conn:
            params = [lookback_start, days]
            entity_clause_pva = ""
            entity_clause_sp = ""
            entity_clause_ap = ""
            if target_entity_code:
                params.append(target_entity_code)
                entity_param_idx = len(params)
                entity_clause_pva = f"""AND EXISTS (
                          SELECT 1 FROM agent_profiles ap2
                          JOIN entities e2 ON e2.id = ap2.entity_id
                          WHERE ap2.id = pva.agent_profile_id
                            AND e2.code = ${entity_param_idx}
                            AND ap2.is_active = true
                      )"""
                entity_clause_sp = f"AND sp.entity_code = ${entity_param_idx}"
                entity_clause_ap = f"AND e.code = ${entity_param_idx}"
            loc_filter_pva = ""
            loc_filter_ap = ""
            loc_filter_sp = ""
            if effective_location_id:
                params.append(effective_location_id)
                loc_param_idx = len(params)
                loc_filter_pva = (
                    f"AND pva.agent_profile_id IN (SELECT id FROM agent_profiles "
                    f"WHERE entity_location_id = ${loc_param_idx}::uuid AND is_active = true)"
                )
                loc_filter_ap = f"AND ap.entity_location_id = ${loc_param_idx}::uuid"
                loc_filter_sp = (
                    f"AND sp.assigned_agent_id IN (SELECT id FROM agent_profiles "
                    f"WHERE entity_location_id = ${loc_param_idx}::uuid AND is_active = true)"
                )
            row = await conn.fetchrow(f"""
                WITH period_stats AS (
                    SELECT
                        COUNT(DISTINCT pva.agent_profile_id) as active_agents,
                        COUNT(*) as total_validated
                    FROM payment_validation_audit pva
                    WHERE pva.action IN ('approve','reject')
                      AND pva.created_at >= $1
                      {entity_clause_pva}
                      {loc_filter_pva}
                ),
                queue AS (
                    SELECT
                        COUNT(*) as queue_size,
                        COALESCE(AVG(EXTRACT(EPOCH FROM (NOW() - sp.created_at)) / 3600.0), 0)
                            as avg_wait_hours
                    FROM service_payments sp
                    WHERE sp.workflow_status IN (
                        'pending_agent_review', 'submitted', 'auto_processing'
                    )
                    {entity_clause_sp}
                    {loc_filter_sp}
                )
                SELECT
                    (SELECT COUNT(*) FROM agent_profiles ap
                     JOIN entities e ON e.id = ap.entity_id
                     WHERE ap.is_active = true
                     {entity_clause_ap}
                     {loc_filter_ap}) as total_agents,
                    ps.active_agents,
                    q.queue_size,
                    ROUND(q.avg_wait_hours::numeric, 1) as avg_queue_wait_hours,
                    CASE WHEN $2 > 0
                        THEN ROUND(ps.total_validated::numeric / $2, 1)
                        ELSE 0
                    END as velocity_per_day,
                    ps.total_validated as total_validated_period
                FROM period_stats ps, queue q
            """, *params)
            return {
                "total_agents": row["total_agents"],
                "active_agents": row["active_agents"],
                "queue_size": row["queue_size"],
                "avg_queue_wait_hours": float(row["avg_queue_wait_hours"] or 0),
                "velocity_per_day": float(row["velocity_per_day"] or 0),
                "total_validated_period": row["total_validated_period"],
            }

    async def q_rankings():
        async with db_manager.get_connection() as conn:
            params = [lookback_start]
            entity_clause = ""
            if target_entity_code:
                params.append(target_entity_code)
                entity_clause = f"""AND EXISTS (
                          SELECT 1 FROM agent_profiles ap2
                          JOIN entities e2 ON e2.id = ap2.entity_id
                          WHERE ap2.id = mv.agent_profile_id
                            AND e2.code = ${len(params)}
                            AND ap2.is_active = true
                      )"""
            loc_filter = ""
            if effective_location_id:
                params.append(effective_location_id)
                loc_filter = (
                    f"AND agent_profile_id IN (SELECT id FROM agent_profiles "
                    f"WHERE entity_location_id = ${len(params)}::uuid AND is_active = true)"
                )
            rows = await conn.fetch(f"""
                WITH agent_totals AS (
                    SELECT
                        agent_profile_id,
                        agent_name,
                        SUM(approved) as validated,
                        SUM(rejected) as rejected,
                        SUM(total_actions) as total,
                        COALESCE(
                            SUM(avg_duration_seconds * total_actions)
                            / NULLIF(SUM(total_actions), 0),
                            0
                        ) as avg_seconds
                    FROM mv_agent_daily_workload mv
                    WHERE report_date >= $1::date
                      {entity_clause}
                      {loc_filter}
                    GROUP BY agent_profile_id, agent_name
                ),
                max_validated AS (
                    SELECT GREATEST(MAX(total), 1) as max_cnt FROM agent_totals
                )
                SELECT
                    at.agent_name,
                    at.validated::int,
                    at.rejected::int,
                    at.avg_seconds,
                    ROUND((
                        at.total * 40.0 / mv.max_cnt
                        + (100 - LEAST(at.avg_seconds / 36, 100)) * 0.3
                        + CASE WHEN at.total > 0
                            THEN at.validated::numeric / at.total * 30
                            ELSE 0
                        END
                    )::numeric, 1) as score
                FROM agent_totals at
                CROSS JOIN max_validated mv
                ORDER BY score DESC
                LIMIT 10
            """, *params)
            return [{"agent_name": r["agent_name"], "validated": r["validated"],
                     "rejected": r["rejected"],
                     "avg_minutes": round(float(r["avg_seconds"]) / 60, 1),
                     "score": float(r["score"])} for r in rows]

    (daily_velocity, agent_load, sla_breakdown, volume_trend,
     processing_times, kpis, rankings) = await asyncio.gather(
        q_daily_velocity(), q_agent_load(), q_sla_breakdown(),
        q_volume_trend(), q_processing_times(), q_kpis(), q_rankings()
    )

    result = {
        "daily_velocity": daily_velocity,
        "agent_load": agent_load,
        "sla_breakdown": sla_breakdown,
        "volume_trend": volume_trend,
        "processing_times": processing_times,
        "kpis": kpis,
        "rankings": rankings,
        "period_days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    await cache.set(cache_key, result, ttl=300)
    return result


# ═══════════════════════════════════════════════════════════════
# TREASURY ANOMALIES (Phase 2A)
# ═══════════════════════════════════════════════════════════════

class AnomalyType(str):
    AMOUNT_MISMATCH = "amount_mismatch"
    DUPLICATE_SUSPECTED = "duplicate_suspected"
    RECONCILIATION_FAILED = "reconciliation_failed"
    VALIDATED_NOT_RECEIVED = "validated_not_received"
    SLA_BREACHED = "sla_breached"
    HIGH_AMOUNT = "high_amount"
    SUSPICIOUS_PATTERN = "suspicious_pattern"
    MANUAL_FLAG = "manual_flag"


class AnomalyStatus(str):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"
    ESCALATED = "escalated"


class AnomalySeverity(str):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyResponse(BaseModel):
    """Response for a single anomaly."""
    id: str
    entity_type: str
    entity_id: str
    payment_reference: Optional[str] = None
    service_request_id: Optional[str] = None
    service_request_reference: Optional[str] = None
    anomaly_type: str
    severity: str
    status: str
    title: str
    description: Optional[str] = None
    detection_rule: Optional[str] = None
    expected_amount: Optional[float] = None
    actual_amount: Optional[float] = None
    difference_amount: Optional[float] = None
    resolution_notes: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_by_name: Optional[str] = None
    detected_at: str
    detected_by: str
    updated_at: str


class AnomalySummary(BaseModel):
    """Summary counts by status."""
    open: int = 0
    investigating: int = 0
    resolved: int = 0
    false_positive: int = 0
    escalated: int = 0
    total: int = 0


class AnomalyListResponse(BaseModel):
    """List of anomalies with summary."""
    anomalies: List[AnomalyResponse]
    total: int
    page: int = 1
    page_size: int = 20
    summary: AnomalySummary


class AnomalyCreate(BaseModel):
    """Create anomaly request."""
    entity_type: str = Field(..., pattern="^(service_payment|bank_transaction|payment)$")
    entity_id: str
    anomaly_type: str
    severity: str = "medium"
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    expected_amount: Optional[float] = None
    actual_amount: Optional[float] = None


class AnomalyStatusUpdate(BaseModel):
    """Update anomaly status."""
    status: str
    comment: Optional[str] = None
    resolution_notes: Optional[str] = None


class AnomalyActionResponse(BaseModel):
    """Response after an action on anomaly."""
    id: str
    anomaly_id: str
    action: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    comment: Optional[str] = None
    performed_by_name: Optional[str] = None
    performed_at: str


@router.get(
    "/treasury/anomalies",
    response_model=AnomalyListResponse,
    summary="List payment anomalies",
    description="""
    Get list of payment anomalies with filters.

    **Filters:**
    - status: Filter by anomaly status
    - severity: Filter by severity level
    - anomaly_type: Filter by type of anomaly
    - date_from / date_to: Filter by detection date range

    **Permissions:**
    - Requires 'treasury.anomalies.view' permission
    """
)
async def list_anomalies(
    status: Optional[str] = Query(None, description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    anomaly_type: Optional[str] = Query(None, description="Filter by type"),
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    entity_location_id: Optional[str] = Query(None, description="Filter by agent site location"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_anomaly.view"))
):
    """Get list of payment anomalies."""
    # Resolve site scope for non-main-office supervisors
    tctx = await _get_treasury_context(db, current_user.id)
    effective_location_id = tctx.get_effective_location(entity_location_id)

    # Bug 1 fix dynamic (2026-05-06): scope by tctx.entity_code (own entity
    # for non-global supervisors, None for treasury.view_all admins meaning
    # see-all). Reusable for any payment-validating entity.
    target_entity_code = (
        None if tctx.has_global_scope or not tctx.entity_code
        else tctx.entity_code
    )

    # Build dynamic WHERE clause. Anomalies on service_payments must
    # reference a payment of the supervisor's entity; non-payment anomalies
    # (bank_transaction, reconciliation) remain visible since treasury owns
    # those domains too — and global admins see everything.
    where_clauses = []
    params = []
    param_idx = 1

    if target_entity_code:
        where_clauses.append(
            f"(pa.entity_type != 'service_payment' OR EXISTS ("
            f"SELECT 1 FROM service_payments sp2 "
            f"WHERE sp2.id = pa.entity_id "
            f"AND sp2.entity_code = ${param_idx}))"
        )
        params.append(target_entity_code)
        param_idx += 1

    # Site-scope: filter anomalies linked to payments handled by agents at this site
    if effective_location_id:
        where_clauses.append(f"""(pa.entity_type != 'service_payment' OR pa.entity_id IN (
            SELECT sp.id FROM service_payments sp
            WHERE sp.assigned_agent_id IN (SELECT id FROM agent_profiles WHERE entity_location_id = ${param_idx}::uuid AND is_active = true)
        ))""")
        params.append(effective_location_id)
        param_idx += 1

    if status:
        where_clauses.append(f"pa.status::text = ${param_idx}")
        params.append(status)
        param_idx += 1

    if severity:
        where_clauses.append(f"pa.severity::text = ${param_idx}")
        params.append(severity)
        param_idx += 1

    if anomaly_type:
        where_clauses.append(f"pa.anomaly_type::text = ${param_idx}")
        params.append(anomaly_type)
        param_idx += 1

    if date_from:
        where_clauses.append(f"pa.detected_at >= ${param_idx}")
        params.append(date_from)
        param_idx += 1

    if date_to:
        where_clauses.append(f"pa.detected_at < ${param_idx} + INTERVAL '1 day'")
        params.append(date_to)
        param_idx += 1

    where_sql = (" AND ".join(where_clauses)) if where_clauses else "TRUE"
    offset = (page - 1) * page_size

    # Main query
    query = f"""
        SELECT
            pa.id,
            pa.entity_type,
            pa.entity_id,
            pa.payment_reference,
            pa.service_request_id,
            sr.reference AS service_request_reference,
            pa.anomaly_type::text AS anomaly_type,
            pa.severity::text AS severity,
            pa.status::text AS status,
            pa.title,
            pa.description,
            pa.detection_rule,
            pa.expected_amount,
            pa.actual_amount,
            pa.difference_amount,
            pa.resolution_notes,
            pa.resolved_at,
            u.full_name AS resolved_by_name,
            pa.detected_at,
            pa.detected_by,
            pa.updated_at
        FROM payment_anomalies pa
        LEFT JOIN service_requests sr ON sr.id = pa.service_request_id
        LEFT JOIN users u ON u.id = pa.resolved_by
        WHERE {where_sql}
        ORDER BY
            CASE pa.status
                WHEN 'open' THEN 1
                WHEN 'investigating' THEN 2
                WHEN 'escalated' THEN 3
                ELSE 4
            END,
            CASE pa.severity
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                ELSE 4
            END,
            pa.detected_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """
    params.extend([page_size, offset])

    rows = await db.fetch(query, *params)

    # Get total count
    count_query = f"""
        SELECT COUNT(*) FROM payment_anomalies pa WHERE {where_sql}
    """
    total = await db.fetchval(count_query, *params[:param_idx - 1])

    # Get summary
    summary_query = """
        SELECT
            status::text,
            COUNT(*) as count
        FROM payment_anomalies
        GROUP BY status
    """
    summary_rows = await db.fetch(summary_query)
    summary = AnomalySummary()
    for row in summary_rows:
        setattr(summary, row["status"], row["count"])
        summary.total += row["count"]

    # Build response
    anomalies = []
    for row in rows:
        anomalies.append(AnomalyResponse(
            id=str(row["id"]),
            entity_type=row["entity_type"],
            entity_id=str(row["entity_id"]),
            payment_reference=row["payment_reference"],
            service_request_id=str(row["service_request_id"]) if row["service_request_id"] else None,
            service_request_reference=row["service_request_reference"],
            anomaly_type=row["anomaly_type"],
            severity=row["severity"],
            status=row["status"],
            title=row["title"],
            description=row["description"],
            detection_rule=row["detection_rule"],
            expected_amount=float(row["expected_amount"]) if row["expected_amount"] else None,
            actual_amount=float(row["actual_amount"]) if row["actual_amount"] else None,
            difference_amount=float(row["difference_amount"]) if row["difference_amount"] else None,
            resolution_notes=row["resolution_notes"],
            resolved_at=row["resolved_at"].isoformat() if row["resolved_at"] else None,
            resolved_by_name=row["resolved_by_name"],
            detected_at=row["detected_at"].isoformat(),
            detected_by=row["detected_by"],
            updated_at=row["updated_at"].isoformat(),
        ))

    return AnomalyListResponse(
        anomalies=anomalies,
        total=total or 0,
        page=page,
        page_size=page_size,
        summary=summary,
    )


@router.get(
    "/treasury/anomalies/{anomaly_id}",
    response_model=AnomalyResponse,
    summary="Get anomaly details",
    description="""
    Get detailed information for a specific anomaly.

    **Permissions:**
    - Requires 'treasury.anomalies.view' permission
    """
)
async def get_anomaly(
    anomaly_id: str = Path(..., description="Anomaly ID"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_anomaly.view"))
):
    """Get anomaly by ID."""
    # P7 security (2026-05-06): scope check by polymorphic entity. Without
    # this, an AYUNT supervisor could read TESORO anomalies by UUID.
    tctx = await _get_treasury_context(db, current_user.id)
    await _authorize_anomaly_action(db, tctx, anomaly_id)

    row = await db.fetchrow("""
        SELECT
            pa.id,
            pa.entity_type,
            pa.entity_id,
            pa.payment_reference,
            pa.service_request_id,
            sr.reference AS service_request_reference,
            pa.anomaly_type::text AS anomaly_type,
            pa.severity::text AS severity,
            pa.status::text AS status,
            pa.title,
            pa.description,
            pa.detection_rule,
            pa.expected_amount,
            pa.actual_amount,
            pa.difference_amount,
            pa.resolution_notes,
            pa.resolved_at,
            u.full_name AS resolved_by_name,
            pa.detected_at,
            pa.detected_by,
            pa.updated_at
        FROM payment_anomalies pa
        LEFT JOIN service_requests sr ON sr.id = pa.service_request_id
        LEFT JOIN users u ON u.id = pa.resolved_by
        WHERE pa.id = $1::uuid
    """, anomaly_id)

    if not row:
        anomaly_not_found(anomaly_id)

    return AnomalyResponse(
        id=str(row["id"]),
        entity_type=row["entity_type"],
        entity_id=str(row["entity_id"]),
        payment_reference=row["payment_reference"],
        service_request_id=str(row["service_request_id"]) if row["service_request_id"] else None,
        service_request_reference=row["service_request_reference"],
        anomaly_type=row["anomaly_type"],
        severity=row["severity"],
        status=row["status"],
        title=row["title"],
        description=row["description"],
        detection_rule=row["detection_rule"],
        expected_amount=float(row["expected_amount"]) if row["expected_amount"] else None,
        actual_amount=float(row["actual_amount"]) if row["actual_amount"] else None,
        difference_amount=float(row["difference_amount"]) if row["difference_amount"] else None,
        resolution_notes=row["resolution_notes"],
        resolved_at=row["resolved_at"].isoformat() if row["resolved_at"] else None,
        resolved_by_name=row["resolved_by_name"],
        detected_at=row["detected_at"].isoformat(),
        detected_by=row["detected_by"],
        updated_at=row["updated_at"].isoformat(),
    )


@router.post(
    "/treasury/anomalies",
    response_model=AnomalyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create manual anomaly",
    description="""
    Create a new anomaly manually (flagged by agent).

    **Permissions:**
    - Requires 'treasury.anomalies.create' permission
    """
)
async def create_anomaly(
    body: AnomalyCreate,
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_anomaly.create"))
):
    """Create manual anomaly."""
    # P7 follow-up (2026-05-06): scope check before allowing creation, so
    # a scoped supervisor cannot fabricate an anomaly on another entity's
    # payment by guessing/leaking a UUID. Mirrors _authorize_anomaly_action
    # used by the read/update endpoints.
    tctx = await _get_treasury_context(db, current_user.id)

    # Get payment reference if entity is service_payment
    payment_reference = None
    service_request_id = None
    if body.entity_type == "service_payment":
        payment = await db.fetchrow(
            "SELECT payment_reference, service_request_id, entity_code "
            "FROM service_payments WHERE id = $1::uuid",
            body.entity_id
        )
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service payment not found: {body.entity_id}",
            )
        # Cross-entity guard
        if (
            not tctx.has_global_scope
            and payment["entity_code"]
            and tctx.entity_code
            and payment["entity_code"] != tctx.entity_code
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Not authorized: payment entity {payment['entity_code']!r} "
                    f"is outside your scope (role entity {tctx.entity_code!r})"
                ),
            )
        if not tctx.has_global_scope and not tctx.entity_code:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized: caller has no entity scope",
            )
        payment_reference = payment["payment_reference"]
        service_request_id = payment["service_request_id"]
    else:
        # Non-payment anomalies (bank_transaction, reconciliation) are
        # treasury-domain shared resources — restrict creation to global scope.
        if not tctx.has_global_scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Not authorized: creating a {body.entity_type!r} anomaly "
                    f"requires treasury.view_all (global scope)"
                ),
            )

    # Insert anomaly
    row = await db.fetchrow("""
        INSERT INTO payment_anomalies (
            entity_type, entity_id, payment_reference, service_request_id,
            anomaly_type, severity, title, description,
            expected_amount, actual_amount, detected_by
        ) VALUES (
            $1, $2::uuid, $3, $4,
            $5::anomaly_type_enum, $6::anomaly_severity_enum, $7, $8,
            $9, $10, $11
        )
        RETURNING id, detected_at, updated_at
    """,
        body.entity_type,
        body.entity_id,
        payment_reference,
        service_request_id,
        body.anomaly_type,
        body.severity,
        body.title,
        body.description,
        body.expected_amount,
        body.actual_amount,
        str(current_user.id),
    )

    # Record action
    await db.execute("""
        INSERT INTO anomaly_actions (anomaly_id, action, to_status, comment, performed_by)
        VALUES ($1, 'status_change', 'open', 'Anomalia creada manualmente', $2::uuid)
    """, row["id"], current_user.id)

    return AnomalyResponse(
        id=str(row["id"]),
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        payment_reference=payment_reference,
        service_request_id=str(service_request_id) if service_request_id else None,
        service_request_reference=None,
        anomaly_type=body.anomaly_type,
        severity=body.severity,
        status="open",
        title=body.title,
        description=body.description,
        detection_rule=None,
        expected_amount=body.expected_amount,
        actual_amount=body.actual_amount,
        difference_amount=abs(body.expected_amount - body.actual_amount) if body.expected_amount and body.actual_amount else None,
        resolution_notes=None,
        resolved_at=None,
        resolved_by_name=None,
        detected_at=row["detected_at"].isoformat(),
        detected_by=str(current_user.id),
        updated_at=row["updated_at"].isoformat(),
    )


@router.patch(
    "/treasury/anomalies/{anomaly_id}/status",
    response_model=AnomalyResponse,
    summary="Update anomaly status",
    description="""
    Update the status of an anomaly.

    **Valid transitions:**
    - open → investigating, resolved, false_positive, escalated
    - investigating → resolved, false_positive, escalated
    - escalated → resolved, false_positive

    **Permissions:**
    - Requires 'treasury.anomalies.update' permission
    """
)
async def update_anomaly_status(
    anomaly_id: str = Path(..., description="Anomaly ID"),
    body: AnomalyStatusUpdate = Body(...),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_anomaly.update"))
):
    """Update anomaly status."""
    # P7 security (2026-05-06): scope check. An AYUNT supervisor must NOT
    # be able to resolve a TESORO anomaly.
    tctx = await _get_treasury_context(db, current_user.id)
    await _authorize_anomaly_action(db, tctx, anomaly_id)

    # Get current anomaly
    current = await db.fetchrow(
        "SELECT status::text as status FROM payment_anomalies WHERE id = $1::uuid",
        anomaly_id
    )
    if not current:
        anomaly_not_found(anomaly_id)

    from_status = current["status"]
    to_status = body.status

    # Validate transition
    valid_transitions = {
        "open": ["investigating", "resolved", "false_positive", "escalated"],
        "investigating": ["resolved", "false_positive", "escalated", "open"],
        "escalated": ["resolved", "false_positive", "investigating"],
        "resolved": [],
        "false_positive": [],
    }
    if to_status not in valid_transitions.get(from_status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition from {from_status} to {to_status}"
        )

    # Update anomaly
    update_fields = ["status = $2::anomaly_status_enum", "updated_at = NOW()"]
    params = [anomaly_id, to_status]
    param_idx = 3

    if to_status in ("resolved", "false_positive"):
        if not body.resolution_notes:
            raise HTTPException(
                status_code=400,
                detail="Resolution notes required when resolving anomaly"
            )
        update_fields.append(f"resolved_at = NOW()")
        update_fields.append(f"resolved_by = ${param_idx}::uuid")
        params.append(current_user.id)
        param_idx += 1
        update_fields.append(f"resolution_notes = ${param_idx}")
        params.append(body.resolution_notes)
        param_idx += 1

    await db.execute(f"""
        UPDATE payment_anomalies
        SET {', '.join(update_fields)}
        WHERE id = $1::uuid
    """, *params)

    # Record action
    await db.execute("""
        INSERT INTO anomaly_actions (anomaly_id, action, from_status, to_status, comment, performed_by)
        VALUES ($1::uuid, 'status_change', $2::anomaly_status_enum, $3::anomaly_status_enum, $4, $5::uuid)
    """, anomaly_id, from_status, to_status, body.comment, current_user.id)

    # Return updated anomaly
    return await get_anomaly(anomaly_id, db, current_user, None)


@router.get(
    "/treasury/anomalies/{anomaly_id}/actions",
    response_model=List[AnomalyActionResponse],
    summary="Get anomaly action history",
    description="""
    Get the history of actions performed on an anomaly.

    **Permissions:**
    - Requires 'treasury.anomalies.view' permission
    """
)
async def get_anomaly_actions(
    anomaly_id: str = Path(..., description="Anomaly ID"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_anomaly.view"))
):
    """Get anomaly action history."""
    # P7 security (2026-05-06): scope check.
    tctx = await _get_treasury_context(db, current_user.id)
    await _authorize_anomaly_action(db, tctx, anomaly_id)

    rows = await db.fetch("""
        SELECT
            aa.id,
            aa.anomaly_id,
            aa.action,
            aa.from_status::text AS from_status,
            aa.to_status::text AS to_status,
            aa.comment,
            u.full_name AS performed_by_name,
            aa.performed_at
        FROM anomaly_actions aa
        LEFT JOIN users u ON u.id = aa.performed_by
        WHERE aa.anomaly_id = $1::uuid
        ORDER BY aa.performed_at DESC
    """, anomaly_id)

    return [
        AnomalyActionResponse(
            id=str(row["id"]),
            anomaly_id=str(row["anomaly_id"]),
            action=row["action"],
            from_status=row["from_status"],
            to_status=row["to_status"],
            comment=row["comment"],
            performed_by_name=row["performed_by_name"],
            performed_at=row["performed_at"].isoformat(),
        )
        for row in rows
    ]


@router.post(
    "/treasury/anomalies/{anomaly_id}/comment",
    response_model=AnomalyActionResponse,
    summary="Add comment to anomaly",
    description="""
    Add a comment to an anomaly without changing its status.

    **Permissions:**
    - Requires 'treasury.anomalies.update' permission
    """
)
async def add_anomaly_comment(
    anomaly_id: str = Path(..., description="Anomaly ID"),
    body: Dict[str, str] = Body(..., example={"comment": "Comment text"}),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_anomaly.update"))
):
    """Add comment to anomaly."""
    comment = body.get("comment")
    if not comment:
        comment_required()

    # P7 security (2026-05-06): scope check (also returns 404 if not found,
    # so we can drop the redundant existence probe below).
    tctx = await _get_treasury_context(db, current_user.id)
    await _authorize_anomaly_action(db, tctx, anomaly_id)

    # Verify anomaly exists
    exists = await db.fetchval(
        "SELECT 1 FROM payment_anomalies WHERE id = $1::uuid",
        anomaly_id
    )
    if not exists:
        anomaly_not_found(anomaly_id)

    # Insert comment action
    row = await db.fetchrow("""
        INSERT INTO anomaly_actions (anomaly_id, action, comment, performed_by)
        VALUES ($1::uuid, 'comment', $2, $3::uuid)
        RETURNING id, performed_at
    """, anomaly_id, comment, current_user.id)

    return AnomalyActionResponse(
        id=str(row["id"]),
        anomaly_id=anomaly_id,
        action="comment",
        from_status=None,
        to_status=None,
        comment=comment,
        performed_by_name=f"{current_user.first_name} {current_user.last_name}".strip(),
        performed_at=row["performed_at"].isoformat(),
    )


class AnomalyDetectionRequest(BaseModel):
    """Request to run anomaly detection."""
    detection_types: Optional[List[str]] = Field(
        None,
        description="Specific detection types to run. If null, runs all.",
        example=["duplicate_payment", "amount_mismatch"]
    )


class AnomalyDetectionResponse(BaseModel):
    """Response from anomaly detection run."""
    detected_at: str
    anomalies_found: int
    by_type: Dict[str, Any]


@router.post(
    "/treasury/anomalies/detect",
    response_model=AnomalyDetectionResponse,
    summary="Run anomaly detection",
    description="""
    Trigger automatic anomaly detection algorithms.

    **Detection types:**
    - duplicate_payment: Same user, amount, service within 24h
    - amount_mismatch: >1% difference between payment and bank transaction
    - orphan_transaction: Bank transactions without matching payments
    - late_validation: Payments exceeding 24h SLA threshold
    - suspicious_pattern: Users with 5+ payments in 24 hours

    **Permissions:**
    - Requires 'treasury.anomalies.create' permission
    """
)
async def run_anomaly_detection(
    body: Optional[AnomalyDetectionRequest] = Body(None),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_anomaly.create"))
):
    """Run automatic anomaly detection."""
    from app.modules.service_requests.services.treasury_anomaly_service import treasury_anomaly_service

    detection_types = body.detection_types if body else None

    # P7 security (2026-05-06): pass entity_code so the service can scope
    # the detection. Note: the service currently accepts but does not yet
    # propagate this filter to all _detect_* methods (logged as WARN). Until
    # then, detection runs globally regardless of caller — anomaly LIST and
    # detail endpoints already enforce read-side scope. TODO P7.D.2.
    tctx = await _get_treasury_context(db, current_user.id)
    target_entity_code = (
        None if tctx.has_global_scope or not tctx.entity_code
        else tctx.entity_code
    )

    try:
        results = await treasury_anomaly_service.run_detection(
            db=db,
            detection_types=detection_types,
            entity_code=target_entity_code,
        )

        return AnomalyDetectionResponse(
            detected_at=results["detected_at"],
            anomalies_found=results["anomalies_found"],
            by_type=results["by_type"]
        )
    except Exception as e:
        logger.error(f"Anomaly detection failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Anomaly detection failed: {str(e)}"
        )


# ============================================================================
# TREASURY EXPORTS (Phase 2B)
# ============================================================================

class ExportType(str, Enum):
    """Export type enum matching DB."""
    SAGE_X3 = "sage_x3"
    MINISTRY_REPORT = "ministry_report"
    BANK_CENTRAL = "bank_central"
    AUDIT_REPORT = "audit_report"
    RECONCILIATION = "reconciliation"
    CUSTOM = "custom"


class ExportFormat(str, Enum):
    """Export format enum."""
    CSV = "csv"
    XLSX = "xlsx"
    PDF = "pdf"
    XML = "xml"
    JSON = "json"


class ExportStatus(str, Enum):
    """Export status enum matching DB."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportFilters(BaseModel):
    """Filters for export generation."""
    entity_code: Optional[str] = None
    payment_method: Optional[str] = None
    workflow_code: Optional[str] = None
    status: Optional[str] = None


class ExportCreateRequest(BaseModel):
    """Request to create a new export."""
    export_type: ExportType
    export_format: ExportFormat = ExportFormat.CSV
    period_start: str  # YYYY-MM-DD
    period_end: str  # YYYY-MM-DD
    filters: Optional[ExportFilters] = None
    template_code: Optional[str] = None

    @field_validator('period_start', 'period_end')
    @classmethod
    def validate_date_format(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError('Date must be in YYYY-MM-DD format')
        return v


class ExportResponse(BaseModel):
    """Export response model."""
    id: str
    export_type: str
    export_format: str
    period_start: str
    period_end: str
    filters: Optional[Dict[str, Any]] = None
    status: str
    progress_percentage: int = 0
    total_records: Optional[int] = None
    total_amount: Optional[float] = None
    currency: str = "XAF"
    file_name: Optional[str] = None
    file_size_bytes: Optional[int] = None
    error_message: Optional[str] = None
    requested_by_name: Optional[str] = None
    requested_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    download_count: int = 0


class ExportListResponse(BaseModel):
    """Response for export list."""
    exports: List[ExportResponse]
    total: int


class ExportTemplateResponse(BaseModel):
    """Export template response."""
    id: int
    code: str
    name: str
    export_type: str
    export_format: str
    description: Optional[str] = None
    is_active: bool = True


@router.get(
    "/treasury/exports",
    response_model=ExportListResponse,
    summary="List treasury exports",
    description="""
    List export jobs with filters.

    **Permissions:**
    - Requires 'treasury.exports.view' permission
    """
)
async def list_treasury_exports(
    status: Optional[ExportStatus] = Query(None, description="Filter by status"),
    export_type: Optional[ExportType] = Query(None, description="Filter by type"),
    period_start: Optional[str] = Query(None, description="Filter by period start (YYYY-MM-DD)"),
    period_end: Optional[str] = Query(None, description="Filter by period end (YYYY-MM-DD)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_export.view"))
):
    """List treasury exports with filters."""
    # P7 security (2026-05-06): scope by entity via requested_by JOIN. Without
    # this, supervisors of any entity could enumerate all entities' exports.
    tctx = await _get_treasury_context(db, current_user.id)
    target_entity_code = (
        None if tctx.has_global_scope or not tctx.entity_code
        else tctx.entity_code
    )

    conditions = []
    params = []
    param_count = 0

    if status:
        param_count += 1
        conditions.append(f"te.status = ${param_count}::export_status_enum")
        params.append(status.value)

    if export_type:
        param_count += 1
        conditions.append(f"te.export_type = ${param_count}::export_type_enum")
        params.append(export_type.value)

    if period_start:
        param_count += 1
        conditions.append(f"te.period_start >= ${param_count}::date")
        params.append(datetime.strptime(period_start, '%Y-%m-%d').date())

    if period_end:
        param_count += 1
        conditions.append(f"te.period_end <= ${param_count}::date")
        params.append(datetime.strptime(period_end, '%Y-%m-%d').date())

    if target_entity_code:
        param_count += 1
        conditions.append(
            f"te.requested_by IN ("
            f"SELECT ap.user_id FROM agent_profiles ap "
            f"JOIN entities e ON e.id = ap.entity_id "
            f"WHERE e.code = ${param_count} AND ap.is_active = true"
            f")"
        )
        params.append(target_entity_code)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    # Count total
    count_query = f"""
        SELECT COUNT(*) FROM treasury_exports te
        {where_clause}
    """
    total = await db.fetchval(count_query, *params)

    # Fetch exports with pagination
    offset = (page - 1) * page_size
    param_count += 1
    limit_param = param_count
    param_count += 1
    offset_param = param_count

    query = f"""
        SELECT
            te.id,
            te.export_type::text,
            te.export_format,
            te.period_start,
            te.period_end,
            te.filters,
            te.status::text,
            te.progress_percentage,
            te.total_records,
            te.total_amount,
            te.currency,
            te.file_name,
            te.file_size_bytes,
            te.error_message,
            te.requested_at,
            te.started_at,
            te.completed_at,
            te.download_count,
            u.full_name as requested_by_name
        FROM treasury_exports te
        LEFT JOIN users u ON u.id = te.requested_by
        {where_clause}
        ORDER BY te.requested_at DESC
        LIMIT ${limit_param} OFFSET ${offset_param}
    """
    params.extend([page_size, offset])
    rows = await db.fetch(query, *params)

    exports = []
    for row in rows:
        exports.append(ExportResponse(
            id=str(row["id"]),
            export_type=row["export_type"],
            export_format=row["export_format"],
            period_start=row["period_start"].isoformat() if row["period_start"] else None,
            period_end=row["period_end"].isoformat() if row["period_end"] else None,
            filters=json.loads(row["filters"]) if isinstance(row["filters"], str) else row["filters"],
            status=row["status"],
            progress_percentage=row["progress_percentage"] or 0,
            total_records=row["total_records"],
            total_amount=float(row["total_amount"]) if row["total_amount"] else None,
            currency=row["currency"] or "XAF",
            file_name=row["file_name"],
            file_size_bytes=row["file_size_bytes"],
            error_message=row["error_message"],
            requested_by_name=row["requested_by_name"],
            requested_at=row["requested_at"].isoformat() if row["requested_at"] else None,
            started_at=row["started_at"].isoformat() if row["started_at"] else None,
            completed_at=row["completed_at"].isoformat() if row["completed_at"] else None,
            download_count=row["download_count"] or 0,
        ))

    return ExportListResponse(exports=exports, total=total or 0)


@router.get(
    "/treasury/exports/templates",
    response_model=List[ExportTemplateResponse],
    summary="List export templates",
    description="""
    List available export templates.

    **Permissions:**
    - Requires 'treasury.exports.view' permission
    """
)
async def list_export_templates(
    request: Request,
    export_type: Optional[ExportType] = Query(None, description="Filter by type"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_export.view"))
):
    """List available export templates (multilingual)."""
    # Detect language from middleware
    lang = getattr(request.state, "language", None)
    lang_suffix = lang.value if lang else "es"
    if lang_suffix not in ("es", "fr", "en"):
        lang_suffix = "es"

    # Use COALESCE: preferred language → Spanish fallback
    name_col = f"COALESCE(name_{lang_suffix}, name_es)" if lang_suffix != "es" else "name_es"
    desc_col = f"COALESCE(description_{lang_suffix}, description_es)" if lang_suffix != "es" else "description_es"

    if export_type:
        rows = await db.fetch(f"""
            SELECT id, code, {name_col} AS name, export_type::text, export_format,
                   {desc_col} AS description, is_active
            FROM export_templates
            WHERE is_active = true AND export_type = $1::export_type_enum
            ORDER BY name
        """, export_type.value)
    else:
        rows = await db.fetch(f"""
            SELECT id, code, {name_col} AS name, export_type::text, export_format,
                   {desc_col} AS description, is_active
            FROM export_templates
            WHERE is_active = true
            ORDER BY export_type, name
        """)

    return [
        ExportTemplateResponse(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            export_type=row["export_type"],
            export_format=row["export_format"],
            description=row["description"],
            is_active=row["is_active"],
        )
        for row in rows
    ]


@router.post(
    "/treasury/exports/generate",
    response_model=ExportResponse,
    status_code=201,
    summary="Generate new export",
    description="""
    Request generation of a new export. The export is generated synchronously
    and the file is available for download once the response is returned.

    **Permissions:**
    - Requires 'treasury.exports.create' permission

    **Export Types:**
    - sage_x3: SAGE X3 accounting integration (CSV format)
    - ministry_report: Ministry monthly report (PDF/XLSX)
    - bank_central: BEAC format
    - audit_report: Internal audit report
    - reconciliation: Bank reconciliation export
    - custom: Custom export

    **Formats:**
    - csv: Comma-separated values (SAGE X3 compatible)
    - xlsx: Microsoft Excel
    - pdf: PDF report (ministry_report only)
    - json: JSON format
    """
)
async def generate_treasury_export(
    request: ExportCreateRequest,
    background_tasks: BackgroundTasks,
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_export.create"))
):
    """Generate a new treasury export."""
    try:
        from ..services.treasury_export_service import treasury_export_service
    except Exception as e:
        logger.error(f"Failed to import treasury_export_service: {e}")
        raise HTTPException(status_code=500, detail=f"Export service unavailable: {e}")

    # P7 security (2026-05-06): force entity_code on filters when caller is
    # scoped. Without this, a TESORO supervisor could pass filters.entity_code
    # = 'AYUNTAMIENTO' in the body and exfiltrate AYUNT data via export.
    tctx = await _get_treasury_context(db, current_user.id)
    if not tctx.has_global_scope and tctx.entity_code:
        if request.filters is None:
            request.filters = ExportFilters(entity_code=tctx.entity_code)
        else:
            # Force-overwrite any caller-supplied entity_code (defensive: don't
            # raise — silently coerce so a malformed UI cannot bypass).
            request.filters.entity_code = tctx.entity_code

    # Validate period
    start_date = datetime.strptime(request.period_start, '%Y-%m-%d').date()
    end_date = datetime.strptime(request.period_end, '%Y-%m-%d').date()

    if end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="period_end must be >= period_start"
        )

    # Validate format for export type — reject unsupported combinations
    SUPPORTED_FORMATS = {
        "sage_x3":         ["csv", "xlsx"],
        "ministry_report": ["pdf", "xlsx", "csv"],
        "bank_central":    ["xml", "xlsx"],
        "audit_report":    ["xlsx", "csv"],
        "reconciliation":  ["xlsx", "csv"],
        "custom":          ["csv", "xlsx", "pdf", "json"],
    }
    allowed = SUPPORTED_FORMATS.get(request.export_type.value, ["csv", "xlsx"])
    if request.export_format.value not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Format '{request.export_format.value}' not supported for type "
                   f"'{request.export_type.value}'. Supported: {', '.join(allowed)}"
        )

    # Generate filename using DB function
    file_name = await db.fetchval("""
        SELECT generate_export_filename($1::export_type_enum, $2::date, $3::date, $4)
    """, request.export_type.value, start_date, end_date, request.export_format.value)

    # Insert export request
    filters_json = request.filters.model_dump() if request.filters else None

    # P8 (2026-05-06, mig 333): denormalize requested_by_entity_code at INSERT
    # so the scope check in _authorize_export_action() does not depend on the
    # requester's agent_profile state at read time. tctx.entity_code is the
    # caller's own entity (already coerced into request.filters.entity_code
    # earlier when not has_global_scope).
    row = await db.fetchrow("""
        INSERT INTO treasury_exports (
            export_type, export_format, period_start, period_end,
            filters, status, requested_by, file_name,
            requested_by_entity_code
        )
        VALUES (
            $1::export_type_enum, $2, $3::date, $4::date,
            $5::jsonb, 'pending'::export_status_enum, $6::uuid, $7,
            $8
        )
        RETURNING
            id, export_type::text, export_format, period_start, period_end,
            filters, status::text, progress_percentage, requested_at
    """, request.export_type.value, request.export_format.value,
        start_date, end_date, json.dumps(filters_json) if filters_json else None,
        current_user.id, file_name,
        tctx.entity_code)

    export_id = str(row["id"])

    # Generate export file synchronously (could be moved to background task for large exports)
    try:
        result = await treasury_export_service.generate_export(
            db=db,
            export_id=export_id,
            export_type=request.export_type.value,
            export_format=request.export_format.value,
            period_start=start_date,
            period_end=end_date,
            filters=filters_json,
            requested_by=current_user.id,
        )

        # Fetch updated record
        updated_row = await db.fetchrow("""
            SELECT
                id, export_type::text, export_format, period_start, period_end,
                filters, status::text, progress_percentage, total_records,
                total_amount, currency, file_name, file_size_bytes,
                requested_at, completed_at
            FROM treasury_exports
            WHERE id = $1::uuid
        """, export_id)

        return ExportResponse(
            id=str(updated_row["id"]),
            export_type=updated_row["export_type"],
            export_format=updated_row["export_format"],
            period_start=updated_row["period_start"].isoformat(),
            period_end=updated_row["period_end"].isoformat(),
            filters=json.loads(updated_row["filters"]) if isinstance(updated_row["filters"], str) else updated_row["filters"],
            status=updated_row["status"],
            progress_percentage=updated_row["progress_percentage"] or 100,
            total_records=updated_row["total_records"],
            total_amount=float(updated_row["total_amount"]) if updated_row["total_amount"] else None,
            currency=updated_row["currency"] or "XAF",
            file_name=updated_row["file_name"],
            file_size_bytes=updated_row["file_size_bytes"],
            requested_by_name=f"{current_user.first_name} {current_user.last_name}".strip(),
            requested_at=updated_row["requested_at"].isoformat(),
            completed_at=updated_row["completed_at"].isoformat() if updated_row["completed_at"] else None,
        )

    except HTTPException:
        # Re-raise HTTP exceptions (e.g. 422 no-data warning) directly to client
        await db.execute("""
            UPDATE treasury_exports SET status = 'failed'::export_status_enum,
            error_message = 'No data for selected period'
            WHERE id = $1::uuid
        """, export_id)
        raise

    except Exception as e:
        # Return with error status
        error_row = await db.fetchrow("""
            SELECT
                id, export_type::text, export_format, period_start, period_end,
                filters, status::text, progress_percentage, error_message,
                requested_at
            FROM treasury_exports
            WHERE id = $1::uuid
        """, export_id)

        return ExportResponse(
            id=str(error_row["id"]),
            export_type=error_row["export_type"],
            export_format=error_row["export_format"],
            period_start=error_row["period_start"].isoformat(),
            period_end=error_row["period_end"].isoformat(),
            filters=json.loads(error_row["filters"]) if isinstance(error_row["filters"], str) else error_row["filters"],
            status=error_row["status"],
            progress_percentage=error_row["progress_percentage"] or 0,
            error_message=error_row["error_message"],
            requested_by_name=f"{current_user.first_name} {current_user.last_name}".strip(),
            requested_at=error_row["requested_at"].isoformat(),
        )


@router.get(
    "/treasury/exports/{export_id}",
    response_model=ExportResponse,
    summary="Get export details",
    description="""
    Get details of a specific export.

    **Permissions:**
    - Requires 'treasury.exports.view' permission
    """
)
async def get_treasury_export(
    export_id: str = Path(..., description="Export ID"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_export.view"))
):
    """Get treasury export details."""
    # P7 security (2026-05-06): scope check by export owner's entity.
    tctx = await _get_treasury_context(db, current_user.id)
    await _authorize_export_action(db, tctx, export_id)

    row = await db.fetchrow("""
        SELECT
            te.id,
            te.export_type::text,
            te.export_format,
            te.period_start,
            te.period_end,
            te.filters,
            te.status::text,
            te.progress_percentage,
            te.total_records,
            te.total_amount,
            te.currency,
            te.file_name,
            te.file_size_bytes,
            te.error_message,
            te.requested_at,
            te.started_at,
            te.completed_at,
            te.download_count,
            u.full_name as requested_by_name
        FROM treasury_exports te
        LEFT JOIN users u ON u.id = te.requested_by
        WHERE te.id = $1::uuid
    """, export_id)

    if not row:
        export_not_found(export_id)

    return ExportResponse(
        id=str(row["id"]),
        export_type=row["export_type"],
        export_format=row["export_format"],
        period_start=row["period_start"].isoformat() if row["period_start"] else None,
        period_end=row["period_end"].isoformat() if row["period_end"] else None,
        filters=json.loads(row["filters"]) if isinstance(row["filters"], str) else row["filters"],
        status=row["status"],
        progress_percentage=row["progress_percentage"] or 0,
        total_records=row["total_records"],
        total_amount=float(row["total_amount"]) if row["total_amount"] else None,
        currency=row["currency"] or "XAF",
        file_name=row["file_name"],
        file_size_bytes=row["file_size_bytes"],
        error_message=row["error_message"],
        requested_by_name=row["requested_by_name"],
        requested_at=row["requested_at"].isoformat() if row["requested_at"] else None,
        started_at=row["started_at"].isoformat() if row["started_at"] else None,
        completed_at=row["completed_at"].isoformat() if row["completed_at"] else None,
        download_count=row["download_count"] or 0,
    )


@router.get(
    "/treasury/exports/{export_id}/download",
    summary="Download export file",
    description="""
    Download the generated export file.

    **Permissions:**
    - Requires 'treasury_export.download' permission

    Returns the file directly as a streaming response with proper
    Content-Disposition header for browser download.
    """
)
async def download_treasury_export(
    export_id: str = Path(..., description="Export ID"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_export.download"))
):
    """Download treasury export file — serves file content directly."""
    from fastapi.responses import StreamingResponse
    import io as _io

    # P7 security (2026-05-06): scope check BEFORE serving file content. This
    # is the most critical leak in the export flow because the file contains
    # raw payment data of another entity.
    tctx = await _get_treasury_context(db, current_user.id)
    await _authorize_export_action(db, tctx, export_id)

    # Get export details
    row = await db.fetchrow("""
        SELECT
            id, status::text, file_path, file_name, file_mime_type, export_format
        FROM treasury_exports
        WHERE id = $1::uuid
    """, export_id)

    if not row:
        export_not_found(export_id)

    if row["status"] != "completed":
        raise TreasuryError(
            error_code=TreasuryErrorCode.EXPORT_NOT_READY,
            status_code=status.HTTP_400_BAD_REQUEST,
            extra_info={"current_status": row["status"]}
        )

    # Note: file_path may be NULL (Firebase upload failed or not yet tried).
    # Do NOT bail here — let the regeneration logic below handle it.

    # Determine MIME type
    mime_types = {
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
        "xml": "application/xml",
        "json": "application/json",
    }
    content_type = row["file_mime_type"] or mime_types.get(
        row["export_format"], "application/octet-stream"
    )
    file_name = row["file_name"] or f"export_{export_id}.{row['export_format']}"

    # Get file content
    file_path = row["file_path"]
    file_content = None

    # Case 1: Firebase Storage (path starts with "treasury-exports/")
    if file_path and file_path.startswith("treasury-exports/"):
        try:
            from app.modules.service_requests.services.treasury_export_service import (
                firebase_storage_service,
                FIREBASE_AVAILABLE,
            )
            if FIREBASE_AVAILABLE:
                if not firebase_storage_service._initialized:
                    await firebase_storage_service.initialize()
                blob = firebase_storage_service.bucket.blob(file_path)
                if blob.exists():
                    file_content = blob.download_as_bytes()
                else:
                    logger.error(f"Firebase blob not found: {file_path}")
        except Exception as e:
            logger.error(f"Failed to download from Firebase: {e}")

    # Case 2: Local /tmp/ path (legacy) OR no path → regenerate on-the-fly
    if file_content is None:
        import os
        if file_path and os.path.exists(file_path):
            # Still exists on this instance (same-instance legacy /tmp/ access)
            with open(file_path, "rb") as f:
                file_content = f.read()
        else:
            # File not found (different instance, new deployment, or never uploaded) → regenerate
            logger.info(f"Export {export_id} not in Firebase/local, regenerating on-the-fly")
            from app.modules.service_requests.services.treasury_export_service import (
                treasury_export_service,
            )
            # Fetch export params from DB
            params_row = await db.fetchrow("""
                SELECT export_type::text, export_format, period_start, period_end, filters
                FROM treasury_exports WHERE id = $1::uuid
            """, export_id)
            if not params_row:
                raise TreasuryError(
                    error_code=TreasuryErrorCode.EXPORT_EXPIRED,
                    status_code=status.HTTP_404_NOT_FOUND,
                    extra_info={"detail": "Export record not found."}
                )

            # Regenerate without updating DB status
            gen_result = await treasury_export_service.generate_export(
                db=db,
                export_id=export_id,
                export_type=params_row["export_type"],
                export_format=params_row["export_format"],
                period_start=params_row["period_start"],
                period_end=params_row["period_end"],
                filters=(
                    json.loads(params_row["filters"])
                    if isinstance(params_row["filters"], str)
                    else params_row["filters"]
                ),
                requested_by=str(current_user.id),
            )
            file_content = gen_result.get("file_content")
            # Update content_type and file_name from regenerated result
            content_type = gen_result.get("mime_type", content_type)
            if not file_content:
                raise TreasuryError(
                    error_code=TreasuryErrorCode.EXPORT_EXPIRED,
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    extra_info={"detail": "Export regeneration failed."}
                )

    # Update download count (after successful file read)
    await db.execute("""
        UPDATE treasury_exports
        SET download_count = download_count + 1,
            downloaded_at = NOW(),
            downloaded_by = $2::uuid
        WHERE id = $1::uuid
    """, export_id, current_user.id)

    # Serve file directly with Content-Disposition for browser download
    return StreamingResponse(
        _io.BytesIO(file_content),
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Content-Length": str(len(file_content)),
        },
    )


# ═══════════════════════════════════════════════════════════════
# TREASURY ANALYTICS (Phase 5)
# Advanced statistical analysis with pandas/scipy/sklearn
# ═══════════════════════════════════════════════════════════════

from app.modules.service_requests.models.analytics_models import (
    StatisticsResponse,
    CorrelationMatrix,
    TrendsResponse,
    AnomaliesResponse as AnalyticsAnomaliesResponse,
    PredictionsResponse,
    AnalyticsReport,
)
from app.modules.service_requests.services.treasury_analytics import treasury_analytics_service


@router.get(
    "/treasury/analytics/statistics",
    response_model=StatisticsResponse,
    summary="Get Descriptive Statistics",
    description="""
    Get descriptive statistics for treasury metrics.

    **Metrics analyzed:**
    - total_amount: Revenue statistics
    - transaction_count: Volume statistics
    - avg_processing_minutes: Processing time statistics

    **Returns:**
    - count, mean, median, std, min, max, q1, q3, iqr

    **Permissions:**
    - Requires 'treasury.stats.view' permission
    """
)
async def get_analytics_statistics(
    period: str = Query("month", regex="^(day|week|month|year)$"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_stat.view"))
):
    """Get descriptive statistics for treasury data."""
    # Bug 1 fix dynamic (2026-05-06): entity scope is taken from tctx.entity_code
    # when the user is not a global-scope admin. None = see everything (admin).
    tctx = await _get_treasury_context(db, current_user.id)
    target_entity_code = (
        None if tctx.has_global_scope or not tctx.entity_code
        else tctx.entity_code
    )
    return await treasury_analytics_service.get_statistics(
        db=db,
        period=period,
        date_from=date_from,
        date_to=date_to,
        entity_code=target_entity_code,
    )


@router.get(
    "/treasury/analytics/correlations",
    response_model=CorrelationMatrix,
    summary="Get Correlation Matrix",
    description="""
    Get Pearson correlations between treasury metrics.

    **Pairs analyzed:**
    - total_amount ↔ transaction_count
    - total_amount ↔ avg_processing_minutes
    - transaction_count ↔ avg_processing_minutes

    **Returns:**
    - Correlation coefficient (-1 to 1)
    - P-value (statistical significance)
    - Strength interpretation (weak/moderate/strong)

    **Permissions:**
    - Requires 'treasury.stats.view' permission
    """
)
async def get_analytics_correlations(
    period: str = Query("month", regex="^(day|week|month|year)$"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_stat.view"))
):
    """Get correlation analysis for treasury data."""
    tctx = await _get_treasury_context(db, current_user.id)
    target_entity_code = (
        None if tctx.has_global_scope or not tctx.entity_code
        else tctx.entity_code
    )
    return await treasury_analytics_service.get_correlations(
        db=db,
        period=period,
        date_from=date_from,
        date_to=date_to,
        entity_code=target_entity_code,
    )


@router.get(
    "/treasury/analytics/trends",
    response_model=TrendsResponse,
    summary="Get Trend Analysis",
    description="""
    Get trend analysis using linear regression.

    **Metrics analyzed:**
    - total_amount: Revenue trend
    - transaction_count: Volume trend

    **Returns:**
    - Slope and intercept of trend line
    - R-squared (model fit quality)
    - Direction (declining/stable/growing)
    - 7-day and 30-day projections

    **Permissions:**
    - Requires 'treasury.stats.view' permission
    """
)
async def get_analytics_trends(
    period: str = Query("month", regex="^(day|week|month|year)$"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_stat.view"))
):
    """Get trend analysis for treasury data."""
    tctx = await _get_treasury_context(db, current_user.id)
    target_entity_code = (
        None if tctx.has_global_scope or not tctx.entity_code
        else tctx.entity_code
    )
    return await treasury_analytics_service.get_trends(
        db=db,
        period=period,
        date_from=date_from,
        date_to=date_to,
        entity_code=target_entity_code,
    )


@router.get(
    "/treasury/analytics/anomalies",
    response_model=AnalyticsAnomaliesResponse,
    summary="Get Statistical Anomalies",
    description="""
    Detect statistical anomalies using Z-score method.

    **Detection method:**
    - Z-score > 2 or < -2 indicates anomaly
    - Applied to: total_amount, transaction_count

    **Returns:**
    - List of anomaly points with dates
    - Z-score and deviation percentage
    - Anomaly type (high/low)

    **Permissions:**
    - Requires 'treasury.stats.view' permission
    """
)
async def get_analytics_anomalies(
    period: str = Query("month", regex="^(day|week|month|year)$"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_stat.view"))
):
    """Get statistical anomalies in treasury data."""
    tctx = await _get_treasury_context(db, current_user.id)
    target_entity_code = (
        None if tctx.has_global_scope or not tctx.entity_code
        else tctx.entity_code
    )
    return await treasury_analytics_service.get_anomalies(
        db=db,
        period=period,
        date_from=date_from,
        date_to=date_to,
        entity_code=target_entity_code,
    )


@router.get(
    "/treasury/analytics/predictions",
    response_model=PredictionsResponse,
    summary="Get Revenue Predictions",
    description="""
    Get revenue predictions using linear regression.

    **Model:**
    - Linear regression on historical daily revenue
    - Confidence intervals at 95% level

    **Parameters:**
    - horizon_days: Number of days to predict (1-90)

    **Returns:**
    - Predicted values with confidence intervals
    - Model R-squared (quality indicator)
    - Warning if R² < 0.7

    **Permissions:**
    - Requires 'treasury.stats.view' permission
    """
)
async def get_analytics_predictions(
    period: str = Query("month", regex="^(day|week|month|year)$"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    horizon_days: int = Query(7, ge=1, le=90, description="Days to predict"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_stat.view"))
):
    """Get revenue predictions."""
    tctx = await _get_treasury_context(db, current_user.id)
    target_entity_code = (
        None if tctx.has_global_scope or not tctx.entity_code
        else tctx.entity_code
    )
    return await treasury_analytics_service.get_predictions(
        db=db,
        period=period,
        date_from=date_from,
        date_to=date_to,
        horizon_days=horizon_days,
        entity_code=target_entity_code,
    )


@router.get(
    "/treasury/analytics/report",
    response_model=AnalyticsReport,
    summary="Get Complete Analytics Report",
    description="""
    Get comprehensive analytics report with all analyses.

    **Includes:**
    - Descriptive statistics
    - Correlation analysis
    - Trend analysis with projections
    - Anomaly detection
    - Revenue predictions
    - Automated findings and recommendations

    **Fixed Variables Analyzed:**
    - total_amount (revenue)
    - transaction_count (volume)
    - avg_processing_minutes (performance)
    - sla_respect_rate (quality)

    **Report sections:**
    - Executive summary with health score
    - Detailed analysis per metric
    - Findings with severity levels
    - Business recommendations

    **Permissions:**
    - Requires 'treasury.stats.view' permission
    """
)
async def get_analytics_report(
    period: str = Query("month", regex="^(day|week|month|year)$"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    language: str = Query("es", regex="^(es|fr|en)$", description="Report language"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_stat.view"))
):
    """Get complete analytics report."""
    tctx = await _get_treasury_context(db, current_user.id)
    target_entity_code = (
        None if tctx.has_global_scope or not tctx.entity_code
        else tctx.entity_code
    )
    return await treasury_analytics_service.generate_report(
        db=db,
        period=period,
        date_from=date_from,
        date_to=date_to,
        language=language,
        entity_code=target_entity_code,
    )


@router.get(
    "/treasury/analytics/explore",
    summary="Explore Custom Variables",
    description="""
    Explore correlations and statistics for custom variable pairs.

    **Use case:**
    - Ad-hoc investigation
    - Custom correlation analysis
    - Detailed metric exploration

    **Available variables:**
    - total_amount, transaction_count, avg_processing_minutes
    - success_rate, sla_respect_rate, workload_score

    **Permissions:**
    - Requires 'treasury.stats.view' permission
    """
)
async def explore_analytics(
    primary_variable: str = Query(..., description="Primary variable to analyze"),
    secondary_variable: Optional[str] = Query(None, description="Variable for correlation"),
    period: str = Query("month", regex="^(day|week|month|year)$"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_stat.view"))
):
    """Explore custom variable analysis."""
    # Validate variables
    valid_variables = [
        "total_amount", "transaction_count", "avg_processing_minutes",
        "success_count", "failed_count"
    ]

    if primary_variable not in valid_variables:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid primary_variable. Must be one of: {valid_variables}"
        )

    if secondary_variable and secondary_variable not in valid_variables:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid secondary_variable. Must be one of: {valid_variables}"
        )

    # Bug 1 fix dynamic (2026-05-06): scope by tctx.entity_code (None = global admin)
    tctx = await _get_treasury_context(db, current_user.id)
    target_entity_code = (
        None if tctx.has_global_scope or not tctx.entity_code
        else tctx.entity_code
    )
    # Get data
    df = await treasury_analytics_service.get_kpi_data(
        db=db,
        period=period,
        date_from=date_from,
        date_to=date_to,
        entity_code=target_entity_code,
    )

    if df.empty:
        return {
            "primary_variable": primary_variable,
            "secondary_variable": secondary_variable,
            "period": period,
            "statistics": None,
            "trend": None,
            "correlation": None,
            "anomalies": [],
            "message": "No data available for the selected period"
        }

    # Calculate statistics for primary variable
    stats = treasury_analytics_service.calculate_descriptive_stats(df, [primary_variable])

    # Calculate trend for primary variable
    trend = treasury_analytics_service.analyze_trend(df, "report_date", primary_variable)

    # Calculate anomalies for primary variable
    anomalies = treasury_analytics_service.detect_anomalies(
        df, "report_date", primary_variable,
        treasury_analytics_service.THRESHOLDS["anomaly"]["z_score"]
    )

    # Calculate correlation if secondary variable provided
    correlation = None
    if secondary_variable:
        correlations = treasury_analytics_service.calculate_correlations(
            df, [primary_variable, secondary_variable]
        )
        if correlations:
            correlation = correlations[0]

    # Data quality + NL summary
    data_days = int(df["report_date"].nunique()) if not df.empty else 0
    summary = treasury_analytics_service._generate_explore_summary(
        primary=primary_variable,
        trend=trend,
        correlation=correlation,
        anomalies=anomalies,
        data_days=data_days,
        language="es",
    )

    return {
        "primary_variable": primary_variable,
        "secondary_variable": secondary_variable,
        "period": period,
        "date_from": date_from or (df["report_date"].min().strftime("%Y-%m-%d") if not df.empty else None),
        "date_to": date_to or (df["report_date"].max().strftime("%Y-%m-%d") if not df.empty else None),
        "statistics": stats[0].model_dump() if stats else None,
        "trend": trend.model_dump() if trend else None,
        "correlation": correlation.model_dump() if correlation else None,
        "anomalies": [a.model_dump() for a in anomalies],
        "total_records": len(df),
        "data_days": data_days,
        "summary": summary,
    }


# ═══════════════════════════════════════════════════════════════
# TREASURY AI ANALYST - Gemini function-calling for financial Q&A
# ═══════════════════════════════════════════════════════════════


class TreasuryAnalystRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000, description="Financial question in any language")
    previous_context: Optional[dict] = Field(
        None,
        description="Previous Q&A context for drill-down (question + tools_used)",
    )
    session_id: Optional[str] = Field(
        None,
        max_length=128,
        description="Client-generated session UUID for conversation memory (slot inheritance)",
    )


async def _get_analyst_entity_context(db, user_id: str) -> dict:
    """Extract entity context for treasury analyst from agent_profiles + entity_locations.

    Returns context dict with entity_code, entity_location_id, is_main_office.
    Main office users see all data; satellite site users see only their site.

    Bug 1 fix dynamic (2026-05-06): when the user has `treasury.view_all`
    (admin global scope), `entity_code` is intentionally set to None so the
    SQL functions skip the entity filter and return cross-entity data.
    """
    # Resolve treasury context first to check global-scope permission.
    tctx = await _get_treasury_context(db, user_id)

    row = await db.fetchrow("""
        SELECT ap.entity_location_id, e.code AS entity_code,
               COALESCE(el.is_main_office, true) AS is_main_office
        FROM agent_profiles ap
        JOIN entities e ON e.id = ap.entity_id
        LEFT JOIN entity_locations el ON el.id = ap.entity_location_id
        WHERE ap.user_id = $1
    """, user_id)
    if not row:
        return {}

    # If admin has global scope, drop the entity_code so _build_entity_kwargs
    # does not propagate `_entity_code` and the chatbot sees ALL entities.
    entity_code = None if tctx.has_global_scope else row["entity_code"]

    return {
        "entity_code": entity_code,
        "entity_location_id": str(row["entity_location_id"]) if row["entity_location_id"] else None,
        "is_main_office": row["is_main_office"],
    }


@router.post(
    "/treasury/analyst/ask",
    summary="Ask treasury financial analyst AI",
    description="Process a financial question using Gemini function calling with 17 predefined safe SQL functions.",
)
async def treasury_analyst_ask(
    request: TreasuryAnalystRequest,
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_stat.view")),
):
    """
    Ask the treasury AI analyst a financial question.
    Uses Gemini function calling — the LLM never generates SQL.
    Rate limited: 20 requests/hour per user.
    Entity-scoped: satellite sites see only their data.
    """
    from app.core.cache import check_rate_limit, get_cache
    from ..services.treasury_analyst_service import treasury_analyst_service

    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    # Rate limit: 20 requests/hour
    is_allowed, remaining = await check_rate_limit(
        str(user_id), "/treasury/analyst/ask", max_requests=20, window_seconds=3600
    )
    if not is_allowed:
        return {
            "answer": "Has alcanzado el límite de consultas (20/hora). Espera antes de intentar de nuevo.",
            "tools_used": [],
            "data": {},
            "artifacts": [],
        }

    # Build entity context (site-scoped)
    entity_ctx = await _get_analyst_entity_context(db, user_id)
    context = {
        "user_id": str(user_id),
        **entity_ctx,
    }

    # Attach session_id for conversation memory (Level 2 NLP)
    if request.session_id:
        context["session_id"] = request.session_id[:128]

    # Add previous context for drill-down if provided
    if request.previous_context:
        prev = request.previous_context
        if prev.get("question"):
            context["previous_context"] = {
                "question": str(prev["question"])[:500],
                "tools_used": prev.get("tools_used", []),
            }

    # Check cache (5 min, keyed by question hash + entity scope)
    import hashlib
    cache = get_cache()
    scope_key = entity_ctx.get("entity_location_id", "global")
    question_hash = hashlib.md5(request.question.strip().lower().encode()).hexdigest()
    # v2 (2026-05-06): bumped after Bug 1 fix (entity scope) to invalidate stale answers
    cache_key = f"treasury:analyst:ask:v2:{scope_key}:{question_hash}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    result = await treasury_analyst_service.process_question(
        db, request.question.strip(), context=context
    )

    # Cache successful results
    if result.get("tools_used"):
        await cache.set(cache_key, result, ttl=300)

    return result


@router.get(
    "/treasury/analyst/briefing",
    summary="Get automated treasury briefing",
    description="Auto-generated briefing of current financial situation with priority and recommendations.",
)
async def treasury_analyst_briefing(
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_stat.view")),
):
    """
    Get automated treasury financial briefing.
    Pre-computed data → LLM summary with priority classification.
    Cached for 5 minutes per entity scope.
    """
    from app.core.cache import get_cache
    from ..services.treasury_analyst_service import treasury_analyst_service

    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")
    entity_ctx = await _get_analyst_entity_context(db, user_id)

    cache = get_cache()
    scope_key = entity_ctx.get("entity_location_id", "global")
    # v2 (2026-05-06): bumped after Bug 1 fix to invalidate stale cross-entity briefings
    cache_key = f"treasury:analyst:briefing:v2:{scope_key}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    context = {"user_id": str(user_id), **entity_ctx}
    result = await treasury_analyst_service.generate_briefing(db, context=context)
    await cache.set(cache_key, result, ttl=300)
    return result


class AnalystExportRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    answer: str = Field(..., min_length=1)
    artifacts: Optional[List[dict]] = None
    format: str = Field("pdf", pattern="^(pdf|markdown)$")


@router.post(
    "/treasury/analyst/export",
    summary="Export analyst response as PDF or Markdown",
    description="Generate a downloadable PDF or Markdown file from an analyst Q&A response.",
)
async def export_analyst_response(
    request: AnalystExportRequest,
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury_stat.view")),
):
    """Export analyst response as PDF or Markdown."""
    from datetime import datetime, timezone
    from io import BytesIO
    from fastapi.responses import StreamingResponse

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")

    if request.format == "markdown":
        md = _build_analyst_markdown(request.question, request.answer, request.artifacts or [])
        content = md.encode("utf-8")
        return StreamingResponse(
            BytesIO(content),
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="analyst-{timestamp}.md"',
                "Content-Length": str(len(content)),
            },
        )

    # PDF
    html = _build_analyst_pdf_html(request.question, request.answer, request.artifacts or [], timestamp)
    try:
        from xhtml2pdf import pisa
    except ImportError:
        return {"error": "PDF generation not available (xhtml2pdf not installed)"}

    pdf_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=pdf_buffer)
    if pisa_status.err:
        return {"error": "PDF generation failed"}

    pdf_bytes = pdf_buffer.getvalue()
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="analyst-{timestamp}.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


def _build_analyst_markdown(question: str, answer: str, artifacts: list) -> str:
    """Build Markdown export of analyst response."""
    from datetime import datetime, timezone
    lines = [
        f"# Análisis Financiero — Tesoro Público GE",
        f"",
        f"**Pregunta**: {question}",
        f"",
        f"**Fecha**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"",
        f"---",
        f"",
    ]

    # Render artifacts as markdown tables
    for art in artifacts:
        art_type = art.get("type")
        title = art.get("title", "")

        if art_type == "kpi_grid":
            lines.append(f"## {title}")
            lines.append("")
            metrics = art.get("metrics", [])
            for m in metrics:
                val = m.get("value", "")
                change = m.get("change_pct") or m.get("changePct")
                suffix = f" ({'+' if change >= 0 else ''}{change}%)" if change is not None else ""
                lines.append(f"- **{m.get('label', '')}**: {val}{suffix}")
            lines.append("")

        elif art_type == "table":
            lines.append(f"## {title}")
            lines.append("")
            headers = art.get("headers", [])
            rows = art.get("rows", [])
            alignments = art.get("alignments", ["left"] * len(headers))
            if headers:
                lines.append("| " + " | ".join(headers) + " |")
                sep_parts = []
                for a in alignments:
                    if a == "right":
                        sep_parts.append("---:")
                    elif a == "center":
                        sep_parts.append(":---:")
                    else:
                        sep_parts.append("---")
                lines.append("| " + " | ".join(sep_parts) + " |")
                for row in rows:
                    lines.append("| " + " | ".join(str(c) for c in row) + " |")
            lines.append("")

        elif art_type == "summary":
            lines.append(f"## {title}")
            lines.append("")
            lines.append(art.get("content", ""))
            lines.append("")

    # LLM analysis
    lines.append("## Análisis")
    lines.append("")
    lines.append(answer)
    lines.append("")
    lines.append("---")
    lines.append("_Generado por Facil Analista IA_")

    return "\n".join(lines)


def _build_analyst_pdf_html(question: str, answer: str, artifacts: list, timestamp: str) -> str:
    """Build HTML for PDF export of analyst response."""
    import html as html_mod

    def esc(text: str) -> str:
        return html_mod.escape(str(text)) if text else ""

    # Build artifact HTML
    artifact_html = []
    for art in artifacts:
        art_type = art.get("type")
        title = esc(art.get("title", ""))

        if art_type == "kpi_grid":
            metrics = art.get("metrics", [])
            cells = "".join(
                f'<td style="padding:8px;text-align:center;border:1px solid #ddd;">'
                f'<div style="font-size:10px;color:#666;">{esc(m.get("label",""))}</div>'
                f'<div style="font-size:18px;font-weight:bold;">{esc(m.get("value",""))}</div>'
                f'</td>'
                for m in metrics
            )
            artifact_html.append(
                f'<h3 style="margin:12px 0 6px;font-size:13px;color:#333;">{title}</h3>'
                f'<table style="width:100%;border-collapse:collapse;margin-bottom:12px;"><tr>{cells}</tr></table>'
            )

        elif art_type == "table":
            headers = art.get("headers", [])
            rows = art.get("rows", [])
            alignments = art.get("alignments", ["left"] * len(headers))

            th_cells = "".join(
                f'<th style="padding:6px 8px;text-align:{alignments[i] if i < len(alignments) else "left"};'
                f'border:1px solid #ddd;background:#f5f5f5;font-size:10px;">{esc(h)}</th>'
                for i, h in enumerate(headers)
            )
            body_rows = ""
            for ri, row in enumerate(rows):
                bg = "#fafafa" if ri % 2 == 1 else "#fff"
                tds = "".join(
                    f'<td style="padding:4px 8px;text-align:{alignments[ci] if ci < len(alignments) else "left"};'
                    f'border:1px solid #ddd;font-size:10px;">{esc(c)}</td>'
                    for ci, c in enumerate(row)
                )
                body_rows += f'<tr style="background:{bg};">{tds}</tr>'

            artifact_html.append(
                f'<h3 style="margin:12px 0 6px;font-size:13px;color:#333;">{title}</h3>'
                f'<table style="width:100%;border-collapse:collapse;margin-bottom:12px;">'
                f'<thead><tr>{th_cells}</tr></thead><tbody>{body_rows}</tbody></table>'
            )

        elif art_type == "summary":
            artifact_html.append(
                f'<h3 style="margin:12px 0 6px;font-size:13px;color:#333;">{title}</h3>'
                f'<p style="font-size:11px;padding:8px;background:#f9f9f9;border-left:3px solid #3a7104;">'
                f'{esc(art.get("content",""))}</p>'
            )

    artifacts_block = "\n".join(artifact_html)

    # Convert markdown answer to simple HTML
    answer_html = esc(answer)
    answer_html = answer_html.replace("\n\n", "</p><p style='font-size:11px;line-height:1.5;'>")
    answer_html = answer_html.replace("\n", "<br/>")
    # Bold
    import re
    answer_html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', answer_html)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<style>
@page {{ size: A4; margin: 1.5cm; }}
body {{ font-family: Helvetica, Arial, sans-serif; font-size: 11px; color: #333; }}
.header {{ background: #3a7104; color: white; padding: 12px 16px; margin: -1.5cm -1.5cm 16px; }}
.header h1 {{ margin: 0; font-size: 16px; }}
.header p {{ margin: 4px 0 0; font-size: 10px; opacity: 0.9; }}
.question {{ background: #f0f7e6; border-left: 4px solid #3a7104; padding: 8px 12px; margin-bottom: 16px; }}
.question strong {{ font-size: 12px; }}
.footer {{ margin-top: 20px; padding-top: 8px; border-top: 1px solid #ddd; font-size: 9px; color: #999; text-align: center; }}
</style></head><body>
<div class="header">
  <h1>Análisis Financiero — Tesoro Público GE</h1>
  <p>Generado: {esc(timestamp)} | Plataforma Facil</p>
</div>
<div class="question">
  <strong>Pregunta:</strong> {esc(question)}
</div>
{artifacts_block}
<h3 style="margin:16px 0 8px;font-size:13px;color:#333;">Análisis</h3>
<p style="font-size:11px;line-height:1.5;">{answer_html}</p>
<div class="footer">Generado por Facil Analista IA — Tesoro Público de Guinea Ecuatorial</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════════
# TREASURY RECONCILIATION — Automated matching suggestions
# ═══════════════════════════════════════════════════════════════


@router.get(
    "/treasury/reconciliation/suggestions",
    summary="Get reconciliation matching suggestions",
    description="For each unreconciled bank transaction, returns top 3 matching payment candidates with confidence scores.",
)
async def get_reconciliation_suggestions(
    limit: int = Query(50, ge=1, le=200),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.reconcile")),
):
    """Get automated matching suggestions for bank reconciliation."""
    from ..services.treasury_reconciliation_service import get_matching_suggestions

    # P7 security (2026-05-06): scope candidate payments by entity. Without
    # this, a TESORO supervisor could see suggestions matching AYUNT payments.
    tctx = await _get_treasury_context(db, current_user.id)
    target_entity_code = (
        None if tctx.has_global_scope or not tctx.entity_code
        else tctx.entity_code
    )

    suggestions = await get_matching_suggestions(
        db, limit=limit, entity_code=target_entity_code
    )
    return {"suggestions": suggestions, "count": len(suggestions)}


@router.post(
    "/treasury/reconciliation/auto-match",
    summary="Auto-reconcile high-confidence matches",
    description="Automatically reconcile bank transactions where best match score >= threshold (default 80).",
)
async def auto_match_reconciliation(
    threshold: int = Query(80, ge=40, le=100),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("treasury.reconcile")),
):
    """Auto-reconcile bank transactions with high-confidence payment matches."""
    from ..services.treasury_reconciliation_service import auto_match

    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    # P7 security (2026-05-06): scope candidate payments by entity. Without
    # this, auto-match could reconcile a TESORO bank tx against an AYUNT
    # payment.
    tctx = await _get_treasury_context(db, current_user.id)
    target_entity_code = (
        None if tctx.has_global_scope or not tctx.entity_code
        else tctx.entity_code
    )

    result = await auto_match(
        db, str(user_id), threshold=threshold, entity_code=target_entity_code
    )
    return result


# ═══════════════════════════════════════════════════════════════
# WORKFLOW SYNC - Sync predefined workflows to database
# ═══════════════════════════════════════════════════════════════
# All sync logic is in workflow_sync_service.sync_all_workflows().
# This endpoint is a thin wrapper that delegates to it.


@router.post(
    "/sync/workflows",
    summary="Sync predefined workflows to database",
    description="""
    Synchronize ALL predefined workflow codes to the database.

    Reads from Python workflow classes (source of truth) and syncs:
    workflows, tariffs, document requirements, menu mapping, display config.
    Deletes orphaned workflows no longer in code.

    Use dry_run=true to preview changes without committing.
    Use delete_existing=true to wipe all data before sync (dangerous).
    """,
)
async def sync_predefined_workflows(
    dry_run: bool = Query(False, description="Preview changes without committing"),
    delete_existing: bool = Query(False, description="Delete all existing workflows before sync"),
    db: asyncpg.Connection = Depends(get_database),
    current_user=Depends(get_current_user),
    _=Depends(permission_required("admin.manage_workflow")),
):
    """Sync all predefined workflow codes to database."""
    from ..services.workflow_sync_service import sync_all_workflows

    result = await sync_all_workflows(
        db,
        dry_run=dry_run,
        delete_existing=delete_existing,
    )
    return result.to_dict()
