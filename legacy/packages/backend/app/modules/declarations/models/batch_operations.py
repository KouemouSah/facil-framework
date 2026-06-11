"""
Batch Operations Models - Pydantic schemas for accountant batch operations

This module provides models for accountants managing multiple clients:
- Batch creation of similar declarations
- Batch submission of multiple declarations
- Report generation across clients

Author: Claude Code
Date: 2025-12-03
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, date
from decimal import Decimal
from enum import Enum

from app.modules.declarations.models.declaration import DeclarationType, DeclarationStatus


class BatchOperationStatus(str, Enum):
    """Status for batch operations"""
    PENDING = "pending"           # Batch job created, waiting to start
    PROCESSING = "processing"     # Currently processing items
    COMPLETED = "completed"       # All items processed successfully
    PARTIAL = "partial"          # Some items succeeded, some failed
    FAILED = "failed"            # All items failed


class BatchItemStatus(str, Enum):
    """Status for individual items in a batch"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


# ========== BATCH CREATE MODELS ==========

class BatchDeclarationTemplate(BaseModel):
    """
    Template for creating similar declarations across multiple clients

    Used when accountant wants to create similar declarations (e.g., monthly IVA)
    for multiple clients at once.
    """
    # Declaration type and period
    declaration_type: DeclarationType = Field(..., description="Type of declaration to create")
    fiscal_year: int = Field(..., ge=2000, le=2100, description="Fiscal year (YYYY)")
    fiscal_period: Optional[str] = Field(None, max_length=20, description="Fiscal period (e.g., 'Q1', 'January')")
    declaration_deadline: date = Field(..., description="Declaration deadline")

    # Common financial data (can be overridden per client)
    default_taxable_base: Optional[Decimal] = Field(None, ge=0, description="Default taxable base")
    default_calculated_tax: Optional[Decimal] = Field(None, ge=0, description="Default calculated tax")
    default_deductions: Optional[Decimal] = Field(None, ge=0, description="Default deductions")
    default_credits: Optional[Decimal] = Field(None, ge=0, description="Default credits")

    # Common metadata
    taxpayer_notes: Optional[str] = Field(None, max_length=1000, description="Common notes for all declarations")
    declared_data: Dict[str, Any] = Field(default_factory=dict, description="Common declared data (JSONB)")
    supporting_documents: Optional[List[str]] = Field(default_factory=list, description="Common document URLs")


class ClientDeclarationData(BaseModel):
    """
    Per-client specific data that overrides template defaults
    """
    company_id: str = Field(..., description="Company UUID")

    # Override financial data (optional)
    taxable_base: Optional[Decimal] = Field(None, ge=0, description="Client-specific taxable base")
    calculated_tax: Optional[Decimal] = Field(None, ge=0, description="Client-specific calculated tax")
    deductions: Optional[Decimal] = Field(None, ge=0, description="Client-specific deductions")
    credits: Optional[Decimal] = Field(None, ge=0, description="Client-specific credits")

    # Override metadata (optional)
    taxpayer_notes: Optional[str] = Field(None, max_length=1000, description="Client-specific notes")
    declared_data: Optional[Dict[str, Any]] = Field(None, description="Client-specific declared data")
    supporting_documents: Optional[List[str]] = Field(None, description="Client-specific document URLs")


class BatchCreateRequest(BaseModel):
    """
    Request to create declarations for multiple clients using a template

    Example use case: Accountant creates monthly IVA declarations for 50 clients
    """
    template: BatchDeclarationTemplate = Field(..., description="Template with common declaration data")
    clients: List[ClientDeclarationData] = Field(..., min_length=1, max_length=100, description="Client-specific data (max 100)")

    # Batch metadata
    batch_name: Optional[str] = Field(None, max_length=200, description="Name for this batch (e.g., 'IVA November 2025')")
    send_notifications: bool = Field(default=True, description="Send notifications to clients when created")
    auto_submit: bool = Field(default=False, description="Automatically submit declarations after creation")

    @validator('clients')
    def validate_unique_companies(cls, v):
        """Ensure no duplicate company IDs in batch"""
        company_ids = [c.company_id for c in v]
        if len(company_ids) != len(set(company_ids)):
            raise ValueError("Duplicate company IDs found in batch")
        return v


class BatchCreateItemResult(BaseModel):
    """Result for a single item in batch create operation"""
    company_id: str = Field(..., description="Company UUID")
    status: BatchItemStatus = Field(..., description="Processing status")
    declaration_id: Optional[str] = Field(None, description="Created declaration UUID (if successful)")
    declaration_number: Optional[str] = Field(None, description="Created declaration number (if successful)")
    error: Optional[str] = Field(None, description="Error message (if failed)")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")


class BatchCreateResponse(BaseModel):
    """Response for batch create operation"""
    batch_id: str = Field(..., description="Batch operation UUID")
    batch_name: Optional[str] = Field(None, description="Batch name")
    status: BatchOperationStatus = Field(..., description="Overall batch status")

    # Summary statistics
    total_items: int = Field(..., ge=0, description="Total number of items in batch")
    successful_items: int = Field(..., ge=0, description="Number of successful items")
    failed_items: int = Field(..., ge=0, description="Number of failed items")
    skipped_items: int = Field(..., ge=0, description="Number of skipped items")

    # Detailed results
    results: List[BatchCreateItemResult] = Field(..., description="Detailed results per client")

    # Timing information
    started_at: datetime = Field(..., description="Batch start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Batch completion timestamp")
    total_processing_time_ms: int = Field(..., description="Total processing time in milliseconds")

    # Background job info
    is_async: bool = Field(default=False, description="Whether batch is processing asynchronously")
    progress_url: Optional[str] = Field(None, description="URL to check progress (for async batches)")


# ========== BATCH SUBMIT MODELS ==========

class BatchSubmitRequest(BaseModel):
    """
    Request to submit multiple declarations at once

    Example use case: Accountant reviews 30 declarations and submits them all
    """
    declaration_ids: List[str] = Field(..., min_length=1, max_length=100, description="Declaration UUIDs to submit (max 100)")

    # Submission options
    validate_before_submit: bool = Field(default=True, description="Validate declarations before submitting")
    skip_invalid: bool = Field(default=False, description="Skip invalid declarations instead of failing entire batch")

    # Notifications
    send_notifications: bool = Field(default=True, description="Send submission notifications to clients")

    # Notes
    processor_notes: Optional[str] = Field(None, max_length=1000, description="Common processor notes for all submissions")

    @validator('declaration_ids')
    def validate_unique_declarations(cls, v):
        """Ensure no duplicate declaration IDs"""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate declaration IDs found in batch")
        return v


class BatchSubmitItemResult(BaseModel):
    """Result for a single item in batch submit operation"""
    declaration_id: str = Field(..., description="Declaration UUID")
    declaration_number: Optional[str] = Field(None, description="Declaration number")
    company_id: Optional[str] = Field(None, description="Company UUID")
    company_name: Optional[str] = Field(None, description="Company name")

    status: BatchItemStatus = Field(..., description="Processing status")
    previous_status: Optional[DeclarationStatus] = Field(None, description="Status before submission")
    current_status: Optional[DeclarationStatus] = Field(None, description="Status after submission")

    error: Optional[str] = Field(None, description="Error message (if failed)")
    validation_errors: Optional[List[str]] = Field(None, description="Validation errors (if any)")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    submitted_at: Optional[datetime] = Field(None, description="Submission timestamp (if successful)")


class BatchSubmitResponse(BaseModel):
    """Response for batch submit operation"""
    batch_id: str = Field(..., description="Batch operation UUID")
    status: BatchOperationStatus = Field(..., description="Overall batch status")

    # Summary statistics
    total_items: int = Field(..., ge=0, description="Total number of items in batch")
    successful_items: int = Field(..., ge=0, description="Number of successful submissions")
    failed_items: int = Field(..., ge=0, description="Number of failed submissions")
    skipped_items: int = Field(..., ge=0, description="Number of skipped items")

    # Detailed results
    results: List[BatchSubmitItemResult] = Field(..., description="Detailed results per declaration")

    # Timing information
    started_at: datetime = Field(..., description="Batch start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Batch completion timestamp")
    total_processing_time_ms: int = Field(..., description="Total processing time in milliseconds")

    # Background job info
    is_async: bool = Field(default=False, description="Whether batch is processing asynchronously")
    progress_url: Optional[str] = Field(None, description="URL to check progress (for async batches)")


# ========== REPORT GENERATION MODELS ==========

class ReportFormat(str, Enum):
    """Supported report export formats"""
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"


class ReportPeriod(BaseModel):
    """Time period for report"""
    start_date: date = Field(..., description="Report start date")
    end_date: date = Field(..., description="Report end date")

    @validator('end_date')
    def validate_end_after_start(cls, v, values):
        """Ensure end date is after start date"""
        if 'start_date' in values and v < values['start_date']:
            raise ValueError("end_date must be after start_date")
        return v


class ReportFilter(BaseModel):
    """Filters for report generation"""
    # Client filters
    company_ids: Optional[List[str]] = Field(None, description="Specific companies to include (if None, include all managed companies)")

    # Declaration filters
    declaration_types: Optional[List[DeclarationType]] = Field(None, description="Filter by declaration types")
    declaration_statuses: Optional[List[DeclarationStatus]] = Field(None, description="Filter by statuses")

    # Fiscal period filters
    fiscal_years: Optional[List[int]] = Field(None, description="Filter by fiscal years")
    fiscal_periods: Optional[List[str]] = Field(None, description="Filter by fiscal periods")

    # Financial filters
    min_tax_amount: Optional[Decimal] = Field(None, ge=0, description="Minimum tax amount")
    max_tax_amount: Optional[Decimal] = Field(None, ge=0, description="Maximum tax amount")


class ReportGenerateRequest(BaseModel):
    """
    Request to generate consolidated report across clients

    Example use case: Accountant generates quarterly report for all clients
    """
    # Report configuration
    report_type: Literal["summary", "detailed", "client_breakdown", "tax_breakdown", "timeline"] = Field(
        ...,
        description="Type of report to generate"
    )
    format: ReportFormat = Field(..., description="Export format")

    # Time period
    period: ReportPeriod = Field(..., description="Report period")

    # Filters
    filters: Optional[ReportFilter] = Field(None, description="Additional filters")

    # Report options
    include_charts: bool = Field(default=True, description="Include charts/graphs (PDF only)")
    include_raw_data: bool = Field(default=False, description="Include raw data sheet (Excel only)")
    group_by_client: bool = Field(default=True, description="Group results by client")
    group_by_type: bool = Field(default=False, description="Group results by declaration type")

    # Metadata
    report_title: Optional[str] = Field(None, max_length=200, description="Custom report title")
    report_notes: Optional[str] = Field(None, max_length=1000, description="Notes to include in report")


class ReportGenerateResponse(BaseModel):
    """Response for report generation"""
    report_id: str = Field(..., description="Report UUID")
    status: Literal["generating", "completed", "failed"] = Field(..., description="Generation status")

    # Report metadata
    report_type: str = Field(..., description="Report type")
    format: ReportFormat = Field(..., description="Export format")
    period: ReportPeriod = Field(..., description="Report period")

    # Report statistics
    total_declarations: int = Field(..., ge=0, description="Total declarations in report")
    total_clients: int = Field(..., ge=0, description="Total clients in report")
    total_tax_amount: Decimal = Field(..., description="Total tax amount across all declarations")

    # File information
    file_url: Optional[str] = Field(None, description="Download URL (if completed)")
    file_size_bytes: Optional[int] = Field(None, description="File size in bytes (if completed)")
    expires_at: Optional[datetime] = Field(None, description="URL expiration timestamp")

    # Timing
    generated_at: datetime = Field(..., description="Generation timestamp")
    processing_time_ms: Optional[int] = Field(None, description="Processing time in milliseconds (if completed)")

    # Background job info
    is_async: bool = Field(default=False, description="Whether report is generating asynchronously")
    progress_url: Optional[str] = Field(None, description="URL to check progress (for async reports)")
    error: Optional[str] = Field(None, description="Error message (if failed)")


# ========== BATCH JOB TRACKING MODELS ==========

class BatchJobStatus(BaseModel):
    """
    Status information for a background batch job

    Used to track progress of async batch operations
    """
    job_id: str = Field(..., description="Job UUID")
    job_type: Literal["batch_create", "batch_submit", "report_generate"] = Field(..., description="Type of job")
    status: BatchOperationStatus = Field(..., description="Current job status")

    # Progress tracking
    total_items: int = Field(..., ge=0, description="Total items to process")
    processed_items: int = Field(..., ge=0, description="Items processed so far")
    successful_items: int = Field(..., ge=0, description="Successful items")
    failed_items: int = Field(..., ge=0, description="Failed items")
    progress_percentage: float = Field(..., ge=0, le=100, description="Progress percentage")

    # Timing
    started_at: datetime = Field(..., description="Job start timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    estimated_completion_at: Optional[datetime] = Field(None, description="Estimated completion (if processing)")

    # Error information
    error_count: int = Field(..., ge=0, description="Number of errors encountered")
    last_error: Optional[str] = Field(None, description="Most recent error message")

    # Results (when available)
    result_data: Optional[Dict[str, Any]] = Field(None, description="Job results (when completed)")


class BatchOperationSummary(BaseModel):
    """
    Summary of batch operations for accountant dashboard
    """
    # Recent operations
    total_operations_30d: int = Field(..., description="Total batch operations in last 30 days")
    successful_operations: int = Field(..., description="Successful operations")
    failed_operations: int = Field(..., description="Failed operations")

    # Declarations created/submitted
    declarations_created_30d: int = Field(..., description="Declarations created via batch in last 30 days")
    declarations_submitted_30d: int = Field(..., description="Declarations submitted via batch in last 30 days")

    # Reports generated
    reports_generated_30d: int = Field(..., description="Reports generated in last 30 days")

    # Efficiency metrics
    avg_declarations_per_batch: float = Field(..., description="Average declarations per batch operation")
    avg_batch_processing_time_seconds: float = Field(..., description="Average batch processing time")
    time_saved_hours: float = Field(..., description="Estimated time saved vs. manual operations")

    # Active jobs
    active_jobs: List[BatchJobStatus] = Field(default_factory=list, description="Currently running batch jobs")
