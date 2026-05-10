"""
Batch Operations Service - Business logic for accountant batch operations

This service handles:
- Batch creation of declarations for multiple clients
- Batch submission of multiple declarations
- Report generation across clients
- Background job management and progress tracking

Author: Claude Code
Date: 2025-12-03
"""

import asyncio
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from loguru import logger
import asyncpg
import json

from app.modules.declarations.models.declaration import (
    DeclarationCreate,
    DeclarationStatus,
    DeclarationType,
    DeclarationResponse,
)
from app.modules.declarations.models.batch_operations import (
    BatchCreateRequest,
    BatchCreateResponse,
    BatchCreateItemResult,
    BatchSubmitRequest,
    BatchSubmitResponse,
    BatchSubmitItemResult,
    ReportGenerateRequest,
    ReportGenerateResponse,
    BatchOperationStatus,
    BatchItemStatus,
    BatchJobStatus,
    BatchOperationSummary,
    ReportPeriod,
)
from app.modules.declarations.repositories.declaration_repository import DeclarationRepository


class BatchOperationsService:
    """
    Service for accountant batch operations

    **Architecture**: 3-tier (Routes → Services → Repositories)
    **Responsibility**: Batch processing logic, error handling, progress tracking
    """

    def __init__(self, repository: Optional[DeclarationRepository] = None):
        """Initialize batch operations service"""
        self.repository = repository or DeclarationRepository()
        logger.info("BatchOperationsService initialized")

    # ========== BATCH CREATE OPERATIONS ==========

    async def batch_create_declarations(
        self,
        conn: asyncpg.Connection,
        request: BatchCreateRequest,
        accountant_user_id: str,
    ) -> BatchCreateResponse:
        """
        Create declarations for multiple clients using a template

        **Business Logic**:
        - Validates accountant has permission to manage each company
        - Creates declarations in parallel with error isolation
        - Tracks success/failure per client
        - Optionally auto-submits after creation
        - Sends notifications if requested

        Args:
            conn: Database connection
            request: Batch create request with template and client data
            accountant_user_id: UUID of accountant performing operation

        Returns:
            BatchCreateResponse: Results with per-client success/failure

        Raises:
            ValueError: If accountant doesn't have permission
        """
        batch_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        results: List[BatchCreateItemResult] = []

        logger.info(
            f"Starting batch create operation {batch_id} for accountant {accountant_user_id}: "
            f"{len(request.clients)} declarations"
        )

        # Validate accountant has access to all companies
        company_ids = [client.company_id for client in request.clients]
        accessible_companies = await self._validate_accountant_companies_access(
            conn, accountant_user_id, company_ids
        )

        # Process each client
        for client_data in request.clients:
            start_time = datetime.now(timezone.utc)

            try:
                # Check if accountant has access to this company
                if client_data.company_id not in accessible_companies:
                    results.append(
                        BatchCreateItemResult(
                            company_id=client_data.company_id,
                            status=BatchItemStatus.FAILED,
                            error=f"Accountant does not have access to company {client_data.company_id}",
                            processing_time_ms=0,
                        )
                    )
                    continue

                # Merge template data with client-specific overrides
                declaration_data = self._merge_template_with_client_data(
                    request.template, client_data
                )

                # Get user_id for the company (find company owner or use accountant)
                user_id = await self._get_company_user_id(conn, client_data.company_id)

                # Create declaration object
                declaration_create = DeclarationCreate(
                    user_id=user_id,
                    company_id=client_data.company_id,
                    declaration_type=declaration_data["declaration_type"],
                    fiscal_year=declaration_data["fiscal_year"],
                    fiscal_period=declaration_data.get("fiscal_period"),
                    declaration_deadline=declaration_data["declaration_deadline"],
                    taxable_base=declaration_data.get("taxable_base"),
                    calculated_tax=declaration_data.get("calculated_tax"),
                    deductions=declaration_data.get("deductions"),
                    credits=declaration_data.get("credits"),
                    taxpayer_notes=declaration_data.get("taxpayer_notes"),
                    declared_data=declaration_data.get("declared_data", {}),
                    supporting_documents=declaration_data.get("supporting_documents", []),
                    status=DeclarationStatus.DRAFT,
                )

                # Create declaration in database
                created_declaration = await self.repository.create(conn, declaration_create)

                # Auto-submit if requested
                if request.auto_submit:
                    await self._submit_declaration(
                        conn, created_declaration["id"], accountant_user_id
                    )

                processing_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

                results.append(
                    BatchCreateItemResult(
                        company_id=client_data.company_id,
                        status=BatchItemStatus.SUCCESS,
                        declaration_id=created_declaration["id"],
                        declaration_number=created_declaration["declaration_number"],
                        processing_time_ms=processing_time,
                    )
                )

                logger.info(
                    f"Created declaration {created_declaration['id']} for company {client_data.company_id}"
                )

            except Exception as e:
                processing_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                error_msg = str(e)

                results.append(
                    BatchCreateItemResult(
                        company_id=client_data.company_id,
                        status=BatchItemStatus.FAILED,
                        error=error_msg,
                        processing_time_ms=processing_time,
                    )
                )

                logger.error(
                    f"Failed to create declaration for company {client_data.company_id}: {error_msg}"
                )

        # Calculate summary statistics
        completed_at = datetime.now(timezone.utc)
        total_processing_time = int((completed_at - started_at).total_seconds() * 1000)

        successful_count = sum(1 for r in results if r.status == BatchItemStatus.SUCCESS)
        failed_count = sum(1 for r in results if r.status == BatchItemStatus.FAILED)
        skipped_count = sum(1 for r in results if r.status == BatchItemStatus.SKIPPED)

        # Determine overall status
        if successful_count == len(results):
            overall_status = BatchOperationStatus.COMPLETED
        elif successful_count > 0:
            overall_status = BatchOperationStatus.PARTIAL
        else:
            overall_status = BatchOperationStatus.FAILED

        # Send notifications if requested
        if request.send_notifications and successful_count > 0:
            await self._send_batch_creation_notifications(
                conn, results, request.template.declaration_type
            )

        # Store batch operation record
        await self._store_batch_operation(
            conn,
            batch_id=batch_id,
            batch_type="batch_create",
            accountant_user_id=accountant_user_id,
            total_items=len(results),
            successful_items=successful_count,
            failed_items=failed_count,
            processing_time_ms=total_processing_time,
            metadata={
                "batch_name": request.batch_name,
                "template": request.template.dict(),
                "auto_submit": request.auto_submit,
            },
        )

        logger.info(
            f"Batch create operation {batch_id} completed: "
            f"{successful_count} success, {failed_count} failed, {skipped_count} skipped"
        )

        return BatchCreateResponse(
            batch_id=batch_id,
            batch_name=request.batch_name,
            status=overall_status,
            total_items=len(results),
            successful_items=successful_count,
            failed_items=failed_count,
            skipped_items=skipped_count,
            results=results,
            started_at=started_at,
            completed_at=completed_at,
            total_processing_time_ms=total_processing_time,
            is_async=False,
        )

    # ========== BATCH SUBMIT OPERATIONS ==========

    async def batch_submit_declarations(
        self,
        conn: asyncpg.Connection,
        request: BatchSubmitRequest,
        accountant_user_id: str,
    ) -> BatchSubmitResponse:
        """
        Submit multiple declarations at once

        **Business Logic**:
        - Validates accountant has permission to submit each declaration
        - Optionally validates declarations before submitting
        - Can skip invalid declarations or fail entire batch
        - Updates declaration status to SUBMITTED
        - Sends submission notifications if requested

        Args:
            conn: Database connection
            request: Batch submit request with declaration IDs
            accountant_user_id: UUID of accountant performing operation

        Returns:
            BatchSubmitResponse: Results with per-declaration success/failure
        """
        batch_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        results: List[BatchSubmitItemResult] = []

        logger.info(
            f"Starting batch submit operation {batch_id} for accountant {accountant_user_id}: "
            f"{len(request.declaration_ids)} declarations"
        )

        # Fetch all declarations to validate access
        declarations = await self._fetch_declarations_batch(conn, request.declaration_ids)
        declaration_map = {d["id"]: d for d in declarations}

        # Validate accountant has access to all declarations
        for declaration_id in request.declaration_ids:
            start_time = datetime.now(timezone.utc)

            try:
                # Check if declaration exists
                if declaration_id not in declaration_map:
                    results.append(
                        BatchSubmitItemResult(
                            declaration_id=declaration_id,
                            status=BatchItemStatus.FAILED,
                            error=f"Declaration {declaration_id} not found",
                            processing_time_ms=0,
                        )
                    )
                    continue

                declaration = declaration_map[declaration_id]

                # Validate accountant has access to declaration's company
                if declaration.get("company_id"):
                    has_access = await self._validate_accountant_company_access(
                        conn, accountant_user_id, declaration["company_id"]
                    )
                    if not has_access:
                        results.append(
                            BatchSubmitItemResult(
                                declaration_id=declaration_id,
                                declaration_number=declaration.get("declaration_number"),
                                company_id=declaration.get("company_id"),
                                status=BatchItemStatus.FAILED,
                                error="Accountant does not have access to this company",
                                processing_time_ms=0,
                            )
                        )
                        continue

                # Check current status
                current_status = DeclarationStatus(declaration["status"])
                if current_status != DeclarationStatus.DRAFT:
                    if request.skip_invalid:
                        results.append(
                            BatchSubmitItemResult(
                                declaration_id=declaration_id,
                                declaration_number=declaration.get("declaration_number"),
                                company_id=declaration.get("company_id"),
                                status=BatchItemStatus.SKIPPED,
                                previous_status=current_status,
                                current_status=current_status,
                                error=f"Declaration is not in DRAFT status (current: {current_status})",
                                processing_time_ms=0,
                            )
                        )
                        continue
                    else:
                        raise ValueError(
                            f"Declaration {declaration_id} is not in DRAFT status (current: {current_status})"
                        )

                # Validate declaration data if requested
                if request.validate_before_submit:
                    validation_errors = await self._validate_declaration(conn, declaration)
                    if validation_errors:
                        if request.skip_invalid:
                            results.append(
                                BatchSubmitItemResult(
                                    declaration_id=declaration_id,
                                    declaration_number=declaration.get("declaration_number"),
                                    company_id=declaration.get("company_id"),
                                    status=BatchItemStatus.SKIPPED,
                                    previous_status=current_status,
                                    current_status=current_status,
                                    validation_errors=validation_errors,
                                    processing_time_ms=0,
                                )
                            )
                            continue
                        else:
                            raise ValueError(
                                f"Declaration {declaration_id} validation failed: {', '.join(validation_errors)}"
                            )

                # Submit declaration
                submitted_declaration = await self._submit_declaration(
                    conn, declaration_id, accountant_user_id, request.processor_notes
                )

                processing_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

                results.append(
                    BatchSubmitItemResult(
                        declaration_id=declaration_id,
                        declaration_number=declaration.get("declaration_number"),
                        company_id=declaration.get("company_id"),
                        company_name=declaration.get("company_name"),
                        status=BatchItemStatus.SUCCESS,
                        previous_status=current_status,
                        current_status=DeclarationStatus.SUBMITTED,
                        processing_time_ms=processing_time,
                        submitted_at=submitted_declaration.get("submitted_at"),
                    )
                )

                logger.info(f"Submitted declaration {declaration_id}")

            except Exception as e:
                processing_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                error_msg = str(e)

                results.append(
                    BatchSubmitItemResult(
                        declaration_id=declaration_id,
                        declaration_number=declaration_map.get(declaration_id, {}).get(
                            "declaration_number"
                        ),
                        company_id=declaration_map.get(declaration_id, {}).get("company_id"),
                        status=BatchItemStatus.FAILED,
                        error=error_msg,
                        processing_time_ms=processing_time,
                    )
                )

                logger.error(f"Failed to submit declaration {declaration_id}: {error_msg}")

        # Calculate summary statistics
        completed_at = datetime.now(timezone.utc)
        total_processing_time = int((completed_at - started_at).total_seconds() * 1000)

        successful_count = sum(1 for r in results if r.status == BatchItemStatus.SUCCESS)
        failed_count = sum(1 for r in results if r.status == BatchItemStatus.FAILED)
        skipped_count = sum(1 for r in results if r.status == BatchItemStatus.SKIPPED)

        # Determine overall status
        if successful_count == len(results):
            overall_status = BatchOperationStatus.COMPLETED
        elif successful_count > 0:
            overall_status = BatchOperationStatus.PARTIAL
        else:
            overall_status = BatchOperationStatus.FAILED

        # Send notifications if requested
        if request.send_notifications and successful_count > 0:
            await self._send_batch_submission_notifications(conn, results)

        # Store batch operation record
        await self._store_batch_operation(
            conn,
            batch_id=batch_id,
            batch_type="batch_submit",
            accountant_user_id=accountant_user_id,
            total_items=len(results),
            successful_items=successful_count,
            failed_items=failed_count,
            processing_time_ms=total_processing_time,
            metadata={
                "validate_before_submit": request.validate_before_submit,
                "skip_invalid": request.skip_invalid,
            },
        )

        logger.info(
            f"Batch submit operation {batch_id} completed: "
            f"{successful_count} success, {failed_count} failed, {skipped_count} skipped"
        )

        return BatchSubmitResponse(
            batch_id=batch_id,
            status=overall_status,
            total_items=len(results),
            successful_items=successful_count,
            failed_items=failed_count,
            skipped_items=skipped_count,
            results=results,
            started_at=started_at,
            completed_at=completed_at,
            total_processing_time_ms=total_processing_time,
            is_async=False,
        )

    # ========== HELPER METHODS ==========

    def _merge_template_with_client_data(
        self, template: Any, client_data: Any
    ) -> Dict[str, Any]:
        """
        Merge template data with client-specific overrides

        Client-specific data takes precedence over template defaults
        """
        merged = {
            "declaration_type": template.declaration_type,
            "fiscal_year": template.fiscal_year,
            "fiscal_period": template.fiscal_period,
            "declaration_deadline": template.declaration_deadline,
            "declared_data": template.declared_data.copy(),
            "supporting_documents": template.supporting_documents.copy()
            if template.supporting_documents
            else [],
        }

        # Override with client-specific data
        if client_data.taxable_base is not None:
            merged["taxable_base"] = client_data.taxable_base
        elif template.default_taxable_base is not None:
            merged["taxable_base"] = template.default_taxable_base

        if client_data.calculated_tax is not None:
            merged["calculated_tax"] = client_data.calculated_tax
        elif template.default_calculated_tax is not None:
            merged["calculated_tax"] = template.default_calculated_tax

        if client_data.deductions is not None:
            merged["deductions"] = client_data.deductions
        elif template.default_deductions is not None:
            merged["deductions"] = template.default_deductions

        if client_data.credits is not None:
            merged["credits"] = client_data.credits
        elif template.default_credits is not None:
            merged["credits"] = template.default_credits

        if client_data.taxpayer_notes is not None:
            merged["taxpayer_notes"] = client_data.taxpayer_notes
        elif template.taxpayer_notes is not None:
            merged["taxpayer_notes"] = template.taxpayer_notes

        if client_data.declared_data:
            merged["declared_data"].update(client_data.declared_data)

        if client_data.supporting_documents:
            merged["supporting_documents"] = client_data.supporting_documents

        return merged

    async def _validate_accountant_companies_access(
        self, conn: asyncpg.Connection, accountant_user_id: str, company_ids: List[str]
    ) -> set:
        """
        Validate accountant has access to given companies

        Returns set of company IDs accountant has access to
        """
        # Check user_company_roles table for accountant role
        query = """
            SELECT company_id
            FROM user_company_roles
            WHERE user_id = $1
            AND company_id = ANY($2)
            AND role IN ('company_accountant', 'company_admin', 'company_owner')
            AND deleted_at IS NULL
        """

        rows = await conn.fetch(query, accountant_user_id, company_ids)
        return {row["company_id"] for row in rows}

    async def _validate_accountant_company_access(
        self, conn: asyncpg.Connection, accountant_user_id: str, company_id: str
    ) -> bool:
        """Validate accountant has access to a single company"""
        accessible = await self._validate_accountant_companies_access(
            conn, accountant_user_id, [company_id]
        )
        return company_id in accessible

    async def _get_company_user_id(self, conn: asyncpg.Connection, company_id: str) -> str:
        """
        Get primary user_id for a company (company owner)

        Falls back to first admin if no owner found
        """
        query = """
            SELECT user_id
            FROM user_company_roles
            WHERE company_id = $1
            AND deleted_at IS NULL
            ORDER BY
                CASE role
                    WHEN 'company_owner' THEN 1
                    WHEN 'company_admin' THEN 2
                    WHEN 'company_accountant' THEN 3
                    ELSE 4
                END,
                created_at ASC
            LIMIT 1
        """

        row = await conn.fetchrow(query, company_id)
        if not row:
            raise ValueError(f"No users found for company {company_id}")

        return row["user_id"]

    async def _submit_declaration(
        self,
        conn: asyncpg.Connection,
        declaration_id: str,
        submitted_by_user_id: str,
        processor_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a single declaration"""
        submitted_at = datetime.now(timezone.utc)

        query = """
            UPDATE tax_declarations
            SET
                status = 'submitted',
                submitted_at = $2,
                processor_notes = COALESCE($3, processor_notes),
                updated_at = $2
            WHERE id = $1
            RETURNING *
        """

        row = await conn.fetchrow(query, declaration_id, submitted_at, processor_notes)
        if not row:
            raise ValueError(f"Declaration {declaration_id} not found")

        return dict(row)

    async def _fetch_declarations_batch(
        self, conn: asyncpg.Connection, declaration_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Fetch multiple declarations by ID"""
        query = """
            SELECT
                d.*,
                c.name as company_name
            FROM tax_declarations d
            LEFT JOIN companies c ON d.company_id = c.id
            WHERE d.id = ANY($1)
        """

        rows = await conn.fetch(query, declaration_ids)
        return [dict(row) for row in rows]

    async def _validate_declaration(
        self, conn: asyncpg.Connection, declaration: Dict[str, Any]
    ) -> List[str]:
        """
        Validate declaration data before submission

        Returns list of validation errors (empty if valid)
        """
        errors = []

        # Check required financial data
        if declaration.get("taxable_base") is None:
            errors.append("taxable_base is required")

        if declaration.get("calculated_tax") is None:
            errors.append("calculated_tax is required")

        # Check deadline hasn't passed
        if declaration.get("declaration_deadline"):
            if declaration["declaration_deadline"] < datetime.now(timezone.utc).date():
                errors.append("declaration_deadline has passed")

        # Add more validation rules as needed

        return errors

    async def _send_batch_creation_notifications(
        self, conn: asyncpg.Connection, results: List[BatchCreateItemResult], declaration_type: DeclarationType
    ) -> None:
        """Send notifications for successful batch creations"""
        # TODO: Implement notification sending
        # This would integrate with the communications module
        logger.info(
            f"Sending batch creation notifications for {len([r for r in results if r.status == BatchItemStatus.SUCCESS])} declarations"
        )

    async def _send_batch_submission_notifications(
        self, conn: asyncpg.Connection, results: List[BatchSubmitItemResult]
    ) -> None:
        """Send notifications for successful batch submissions"""
        # TODO: Implement notification sending
        logger.info(
            f"Sending batch submission notifications for {len([r for r in results if r.status == BatchItemStatus.SUCCESS])} declarations"
        )

    async def _store_batch_operation(
        self,
        conn: asyncpg.Connection,
        batch_id: str,
        batch_type: str,
        accountant_user_id: str,
        total_items: int,
        successful_items: int,
        failed_items: int,
        processing_time_ms: int,
        metadata: Dict[str, Any],
    ) -> None:
        """Store batch operation record for audit and tracking"""
        query = """
            INSERT INTO batch_operations (
                id, batch_type, accountant_user_id,
                total_items, successful_items, failed_items,
                processing_time_ms, metadata, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
        """

        try:
            await conn.execute(
                query,
                batch_id,
                batch_type,
                accountant_user_id,
                total_items,
                successful_items,
                failed_items,
                processing_time_ms,
                json.dumps(metadata),
            )
        except asyncpg.exceptions.UndefinedTableError:
            # Table doesn't exist yet - log warning but don't fail
            logger.warning("batch_operations table not found - skipping audit record")
