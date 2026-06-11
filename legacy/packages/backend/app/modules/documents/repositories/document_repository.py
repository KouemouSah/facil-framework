"""
Document Repository for TaxasGE Backend
Handles document persistence with PostgreSQL and Supabase
Aligned with uploaded_files and ocr_extraction_results tables

Author: Claude Code
Date: 2025-11-13
Version: 2.0 - Reorganized with core/documents/
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from uuid import UUID
from loguru import logger
import json

from app.repositories.base import BaseRepository
from app.modules.documents.models.document import (
    Document, DocumentCreate, DocumentUpdate, DocumentSearchFilter,
    DocumentProcessingStats, DocumentOCRStatus, DocumentExtractionStatus,
    DocumentValidationStatus, DocumentAccessLevel, DocumentType
)
from app.modules.documents.extractors import TemplateBasedExtractor, DeclarationDatabaseMapper
from app.modules.documents.extractors.template_loader import template_loader
from app.modules.documents.services.ocr_service import ocr_service
from app.modules.documents.services.storage_service import firebase_storage_service


class DocumentRepository(BaseRepository[Document]):
    """Repository for document management operations"""

    def __init__(self):
        super().__init__("uploaded_files")

    def _map_to_model(self, data: Dict[str, Any]) -> Document:
        """Map database row to Document model"""

        # Parse JSONB fields that come as strings from asyncpg
        extracted_data = data.get("extracted_data")
        if extracted_data and isinstance(extracted_data, str):
            try:
                extracted_data = json.loads(extracted_data)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse extracted_data for document {data.get('id')}")
                extracted_data = None

        form_mapping = data.get("form_mapping")
        if form_mapping and isinstance(form_mapping, str):
            try:
                form_mapping = json.loads(form_mapping)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse form_mapping for document {data.get('id')}")
                form_mapping = None

        # Map database columns to Document model
        return Document(
            id=data["id"] if isinstance(data["id"], UUID) else UUID(data["id"]),
            user_id=data["user_id"] if isinstance(data["user_id"], UUID) else UUID(data["user_id"]),
            original_filename=data["original_filename"],
            document_type=DocumentType(data["document_type"]) if data.get("document_type") else DocumentType.other,
            document_subtype=data.get("document_subtype"),
            description=data.get("description"),

            # Firebase Storage
            file_path=data["file_path"],
            file_url=data["file_url"],
            file_size_bytes=data["file_size_bytes"],
            mime_type=data["mime_type"],
            file_hash=data["file_hash"],

            # Processing configuration
            processing_mode=data.get("processing_mode", "server_processing"),

            # OCR status
            ocr_status=DocumentOCRStatus(data.get("ocr_status", "pending")),
            ocr_text=data.get("ocr_text"),
            ocr_confidence=data.get("ocr_confidence"),
            ocr_provider=data.get("ocr_provider"),

            # Extraction status
            extraction_status=DocumentExtractionStatus(data.get("extraction_status", "pending")),
            extracted_data=extracted_data,
            extraction_confidence=data.get("extraction_confidence"),

            # Form mapping (NEW)
            form_mapping=form_mapping,

            # Validation
            validation_status=DocumentValidationStatus(data.get("validation_status", "pending")),

            # Relationships
            related_to_type=data.get("related_to_type"),
            related_to_id=UUID(data["related_to_id"]) if data.get("related_to_id") else None,

            # Access control
            access_level=DocumentAccessLevel(data.get("access_level", "private")),

            # Metadata
            processing_started_at=data.get("processing_started_at"),
            processing_completed_at=data.get("processing_completed_at"),
            processing_duration_ms=data.get("processing_duration_ms"),
            uploaded_at=data.get("uploaded_at", datetime.now(timezone.utc)),
            updated_at=data.get("updated_at", datetime.now(timezone.utc))
        )

    def _map_from_model(self, model: Document) -> Dict[str, Any]:
        """Map Document model to database row"""
        return {
            "id": str(model.id),
            "user_id": str(model.user_id),
            "original_filename": model.original_filename,
            "document_type": model.document_type.value,
            "document_subtype": model.document_subtype,
            "description": model.description,

            # Firebase Storage
            "file_path": model.file_path,
            "file_url": model.file_url,
            "file_size_bytes": model.file_size_bytes,
            "mime_type": model.mime_type,
            "file_hash": model.file_hash,

            # Processing configuration
            "processing_mode": model.processing_mode.value if hasattr(model.processing_mode, 'value') else model.processing_mode,

            # OCR status
            "ocr_status": model.ocr_status.value,
            "ocr_text": model.ocr_text,
            "ocr_confidence": model.ocr_confidence,
            "ocr_provider": model.ocr_provider,

            # Extraction status
            "extraction_status": model.extraction_status.value,
            "extracted_data": model.extracted_data,
            "extraction_confidence": model.extraction_confidence,

            # Form mapping
            "form_mapping": model.form_mapping,

            # Validation
            "validation_status": model.validation_status.value,

            # Relationships
            "related_to_type": model.related_to_type,
            "related_to_id": str(model.related_to_id) if model.related_to_id else None,

            # Access control
            "access_level": model.access_level.value,

            # Metadata
            "processing_started_at": model.processing_started_at,
            "processing_completed_at": model.processing_completed_at,
            "processing_duration_ms": model.processing_duration_ms,
            "uploaded_at": model.uploaded_at,
            "updated_at": model.updated_at
        }

    async def create_document(
        self,
        document_data: DocumentCreate
    ) -> Optional[Document]:
        """
        Create new document record

        Args:
            document_data: Document creation data

        Returns:
            Created Document or None
        """
        try:
            from uuid import uuid4
            from datetime import datetime, timezone

            # Generate ID and timestamps
            doc_id = uuid4()
            now = datetime.now(timezone.utc)

            # Prepare data for insertion
            data = {
                "id": str(doc_id),
                "user_id": str(document_data.user_id),
                "original_filename": document_data.original_filename,
                "document_type": document_data.document_type.value,
                "document_subtype": document_data.document_subtype,
                "description": document_data.description,

                # Firebase Storage
                "file_path": document_data.file_path,
                "file_url": document_data.file_url,
                "file_size_bytes": document_data.file_size_bytes,
                "mime_type": document_data.mime_type,
                "file_hash": document_data.file_hash,

                # Processing configuration
                "processing_mode": document_data.processing_mode.value,

                # Initial status
                "ocr_status": DocumentOCRStatus.pending.value,
                "extraction_status": DocumentExtractionStatus.pending.value,
                "validation_status": DocumentValidationStatus.pending.value,

                # Relationships
                "related_to_type": document_data.related_to_type,
                "related_to_id": str(document_data.related_to_id) if document_data.related_to_id else None,

                # Access control
                "access_level": DocumentAccessLevel.private.value,

                # Timestamps
                "uploaded_at": now,
                "updated_at": now
            }

            # Build INSERT query
            columns = list(data.keys())
            placeholders = [f"${i+1}" for i in range(len(columns))]
            values = list(data.values())

            query = f"""
                INSERT INTO {self.table_name} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                RETURNING *
            """

            result = await self.db_manager.execute_single(query, *values)
            if result:
                return self._map_to_model(dict(result))

            return None

        except Exception as e:
            logger.error(f"Error creating document: {e}")
            return None

    async def update_ocr_results(
        self,
        document_id: UUID,
        ocr_text: str,
        ocr_confidence: float,
        ocr_provider: str,
        processing_duration_ms: int,
        use_supabase: bool = True
    ) -> Optional[Document]:
        """
        Update document with OCR results

        Args:
            document_id: Document UUID
            ocr_text: Extracted OCR text
            ocr_confidence: Confidence score (0-1)
            ocr_provider: OCR provider used (tesseract, google_vision)
            processing_duration_ms: Processing time
            use_supabase: Use Supabase client

        Returns:
            Updated Document or None
        """
        try:
            updates = {
                "ocr_status": DocumentOCRStatus.completed.value,
                "ocr_text": ocr_text,
                "ocr_confidence": ocr_confidence,
                "ocr_provider": ocr_provider,
                "processing_completed_at": datetime.now(timezone.utc),
                "processing_duration_ms": processing_duration_ms,
                "updated_at": datetime.now(timezone.utc)
            }

            return await self.update(str(document_id), updates, use_supabase)

        except Exception as e:
            logger.error(f"Error updating OCR results for document {document_id}: {e}")
            return None

    async def update_ocr_failed(
        self,
        document_id: UUID,
        error_message: str,
        use_supabase: bool = True
    ) -> Optional[Document]:
        """Mark document OCR as failed"""
        try:
            updates = {
                "ocr_status": DocumentOCRStatus.failed.value,
                "ocr_text": f"ERROR: {error_message}",
                "processing_completed_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }

            return await self.update(str(document_id), updates, use_supabase)

        except Exception as e:
            logger.error(f"Error marking OCR as failed for document {document_id}: {e}")
            return None

    async def update_extracted_data(
        self,
        document_id: UUID,
        extracted_data: Dict[str, Any],
        extraction_confidence: float,
        form_mapping: Optional[Dict[str, Any]] = None,
        use_supabase: bool = True
    ) -> Optional[Document]:
        """
        Update document with extracted structured data

        Args:
            document_id: Document UUID
            extracted_data: Structured extracted data
            extraction_confidence: Confidence score (0-1)
            form_mapping: Form mapping for frontend pre-fill
            use_supabase: Use Supabase client

        Returns:
            Updated Document or None
        """
        try:
            updates = {
                "extraction_status": DocumentExtractionStatus.completed.value,
                "extracted_data": json.dumps(extracted_data) if isinstance(extracted_data, dict) else extracted_data,
                "extraction_confidence": extraction_confidence,
                "updated_at": datetime.now(timezone.utc)
            }

            # Add form mapping if provided
            if form_mapping:
                updates["form_mapping"] = json.dumps(form_mapping) if isinstance(form_mapping, dict) else form_mapping

            return await self.update(str(document_id), updates, use_supabase)

        except Exception as e:
            logger.error(f"Error updating extracted data for document {document_id}: {e}")
            return None

    async def update_extraction_failed(
        self,
        document_id: UUID,
        error_message: str,
        use_supabase: bool = True
    ) -> Optional[Document]:
        """Mark document extraction as failed"""
        try:
            updates = {
                "extraction_status": DocumentExtractionStatus.failed.value,
                "extracted_data": json.dumps({"error": error_message}),
                "updated_at": datetime.now(timezone.utc)
            }

            return await self.update(str(document_id), updates, use_supabase)

        except Exception as e:
            logger.error(f"Error marking extraction as failed for document {document_id}: {e}")
            return None

    async def update_validation_status(
        self,
        document_id: UUID,
        validation_status: DocumentValidationStatus,
        use_supabase: bool = True
    ) -> Optional[Document]:
        """Update document validation status"""
        try:
            updates = {
                "validation_status": validation_status.value,
                "updated_at": datetime.now(timezone.utc)
            }

            return await self.update(str(document_id), updates, use_supabase)

        except Exception as e:
            logger.error(f"Error updating validation status for document {document_id}: {e}")
            return None

    async def find_by_user(
        self,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
        use_supabase: bool = True
    ) -> List[Document]:
        """Find all documents for a user"""
        try:
            filters = {"user_id": str(user_id)}
            return await self.find_all(
                filters=filters,
                order_by="uploaded_at DESC",
                limit=limit,
                offset=offset,
                use_supabase=use_supabase
            )

        except Exception as e:
            logger.error(f"Error finding documents for user {user_id}: {e}")
            return []

    async def search_documents(
        self,
        filters: DocumentSearchFilter,
        use_supabase: bool = True
    ) -> Tuple[List[Document], int]:
        """
        Advanced document search with filters

        Args:
            filters: Search filters
            use_supabase: Use Supabase client

        Returns:
            Tuple of (documents, total_count)
        """
        try:
            # Build filter conditions
            query_filters = {}

            if filters.user_id:
                query_filters["user_id"] = str(filters.user_id)

            if filters.document_type:
                query_filters["document_type"] = filters.document_type.value

            if filters.document_subtype:
                query_filters["document_subtype"] = filters.document_subtype

            if filters.ocr_status:
                query_filters["ocr_status"] = filters.ocr_status.value

            if filters.extraction_status:
                query_filters["extraction_status"] = filters.extraction_status.value

            if filters.validation_status:
                query_filters["validation_status"] = filters.validation_status.value

            # Get total count
            total_count = await self.count(filters=query_filters, use_supabase=use_supabase)

            # Get paginated results
            offset = (filters.page - 1) * filters.size
            documents = await self.find_all(
                filters=query_filters,
                order_by="uploaded_at DESC",
                limit=filters.size,
                offset=offset,
                use_supabase=use_supabase
            )

            return documents, total_count

        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return [], 0

    async def get_processing_stats(
        self,
        user_id: Optional[UUID] = None,
        use_supabase: bool = True
    ) -> DocumentProcessingStats:
        """
        Get document processing statistics

        Args:
            user_id: Filter by user (None for all users)
            use_supabase: Use Supabase client

        Returns:
            Document processing statistics
        """
        try:
            # Build base query
            base_filters = {"user_id": str(user_id)} if user_id else {}

            # Total documents
            total_documents = await self.count(filters=base_filters, use_supabase=False)

            # OCR stats
            pending_ocr = await self.count(
                filters={**base_filters, "ocr_status": DocumentOCRStatus.pending.value},
                use_supabase=False
            )
            completed_ocr = await self.count(
                filters={**base_filters, "ocr_status": DocumentOCRStatus.completed.value},
                use_supabase=False
            )
            failed_ocr = await self.count(
                filters={**base_filters, "ocr_status": DocumentOCRStatus.failed.value},
                use_supabase=False
            )

            # Extraction stats
            pending_extraction = await self.count(
                filters={**base_filters, "extraction_status": DocumentExtractionStatus.pending.value},
                use_supabase=False
            )
            completed_extraction = await self.count(
                filters={**base_filters, "extraction_status": DocumentExtractionStatus.completed.value},
                use_supabase=False
            )

            # Averages (parameterized)
            if user_id:
                avg_query = f"""
                    SELECT
                        AVG(processing_duration_ms) as avg_processing_time_ms,
                        AVG(ocr_confidence) as avg_ocr_confidence,
                        AVG(extraction_confidence) as avg_extraction_confidence
                    FROM {self.table_name}
                    WHERE user_id = $1 AND ocr_status = 'completed'
                """
                avg_result = await self.db_manager.execute_single(avg_query, user_id)
            else:
                avg_query = f"""
                    SELECT
                        AVG(processing_duration_ms) as avg_processing_time_ms,
                        AVG(ocr_confidence) as avg_ocr_confidence,
                        AVG(extraction_confidence) as avg_extraction_confidence
                    FROM {self.table_name}
                    WHERE ocr_status = 'completed'
                """
                avg_result = await self.db_manager.execute_single(avg_query)

            # Documents by type
            type_query = f"""
                SELECT document_type, COUNT(*) as count
                FROM {self.table_name}
                {where_clause}
                GROUP BY document_type
            """
            type_results = await self.db_manager.execute_query(type_query)
            documents_by_type = {row["document_type"]: row["count"] for row in type_results}

            return DocumentProcessingStats(
                total_documents=total_documents,
                pending_ocr=pending_ocr,
                completed_ocr=completed_ocr,
                failed_ocr=failed_ocr,
                pending_extraction=pending_extraction,
                completed_extraction=completed_extraction,
                avg_processing_time_ms=avg_result.get("avg_processing_time_ms") if avg_result else None,
                avg_ocr_confidence=avg_result.get("avg_ocr_confidence") if avg_result else None,
                avg_extraction_confidence=avg_result.get("avg_extraction_confidence") if avg_result else None,
                documents_by_type=documents_by_type
            )

        except Exception as e:
            logger.error(f"Error getting processing stats: {e}")
            # Return empty stats on error
            return DocumentProcessingStats(
                total_documents=0,
                pending_ocr=0,
                completed_ocr=0,
                failed_ocr=0,
                pending_extraction=0,
                completed_extraction=0,
                documents_by_type={}
            )

    async def find_pending_ocr(
        self,
        limit: int = 10,
        use_supabase: bool = True
    ) -> List[Document]:
        """Find documents pending OCR processing"""
        try:
            filters = {"ocr_status": DocumentOCRStatus.pending.value}
            return await self.find_all(
                filters=filters,
                order_by="uploaded_at ASC",  # FIFO order
                limit=limit,
                use_supabase=use_supabase
            )

        except Exception as e:
            logger.error(f"Error finding pending OCR documents: {e}")
            return []

    async def find_pending_extraction(
        self,
        limit: int = 10,
        use_supabase: bool = True
    ) -> List[Document]:
        """Find documents pending extraction (OCR completed but extraction pending)"""
        try:
            # Need raw SQL for complex WHERE with AND
            query = f"""
                SELECT * FROM {self.table_name}
                WHERE ocr_status = $1
                  AND extraction_status = $2
                ORDER BY uploaded_at ASC
                LIMIT $3
            """

            results = await self.db_manager.execute_query(
                query,
                DocumentOCRStatus.completed.value,
                DocumentExtractionStatus.pending.value,
                limit
            )

            return [self._map_to_model(dict(row)) for row in results]

        except Exception as e:
            logger.error(f"Error finding pending extraction documents: {e}")
            return []

    async def process_document_extraction(
        self,
        document_id: UUID,
        template_name: str,
        template_type: str = "declaration"
    ) -> Dict[str, Any]:
        """
        Process document extraction using Phase 2 template-based architecture

        Pipeline: Download → OCR → Extract → Map → Update

        Args:
            document_id: Document UUID
            template_name: Template name (e.g., "iva_destajo", "nota_ingreso")
            template_type: "declaration" or "fiscal_service"

        Returns:
            Dict with extraction results and statistics
        """
        try:
            logger.info(f"📄 Processing document extraction: {document_id} (template: {template_name})")

            # Step 1: Get document from database
            document = await self.get_by_id(document_id)
            if not document:
                logger.error(f"Document not found: {document_id}")
                return {
                    "success": False,
                    "error": f"Document not found: {document_id}"
                }

            # Mark OCR as processing
            await self.update(document_id, {
                "ocr_status": DocumentOCRStatus.processing.value,
                "processing_started_at": datetime.now(timezone.utc)
            })

            # Step 2: Download document from Firebase Storage
            logger.debug(f"Downloading document from Firebase: {document.file_path}")
            download_result = await firebase_storage_service.download_file(
                file_path=document.file_path,
                user_id=str(document.user_id)
            )

            # Step 3: Run OCR extraction
            logger.debug("Running OCR extraction...")
            ocr_result = await ocr_service.extract_text(
                file_content=download_result.content,
                file_type=document.mime_type,
                provider="tesseract_server"
            )

            if not ocr_result.success:
                logger.error(f"OCR failed: {ocr_result.errors}")
                await self.update_ocr_failed(
                    document_id=document_id,
                    error_message=str(ocr_result.errors)
                )
                return {
                    "success": False,
                    "error": "OCR extraction failed",
                    "details": ocr_result.errors
                }

            # Update OCR results
            await self.update_ocr_results(
                document_id=document_id,
                ocr_text=ocr_result.text,
                confidence=ocr_result.confidence,
                provider="tesseract_server",
                processing_time_ms=ocr_result.processing_time_ms
            )

            # Step 4: Load template
            logger.debug(f"Loading template: {template_name} (type: {template_type})")
            template = template_loader.load(template_name, template_type=template_type)

            if not template:
                logger.error(f"Template not found: {template_name}")
                await self.update_extraction_failed(
                    document_id=document_id,
                    error_message=f"Template not found: {template_name}"
                )
                return {
                    "success": False,
                    "error": f"Template not found: {template_name}"
                }

            # Step 5: Extract structured data
            logger.debug("Extracting structured data with TemplateBasedExtractor...")
            extractor = TemplateBasedExtractor(template)
            extraction_result = await extractor.extract(ocr_result.text)

            if not extraction_result.success:
                logger.error(f"Extraction failed: {extraction_result.errors}")
                await self.update_extraction_failed(
                    document_id=document_id,
                    error_message=str(extraction_result.errors)
                )
                return {
                    "success": False,
                    "error": "Structured extraction failed",
                    "details": extraction_result.errors
                }

            # Step 6: Map to database format
            logger.debug("Mapping extracted data to database format...")
            mapper = DeclarationDatabaseMapper(template)
            mapped_data = mapper.map_to_database(extraction_result)

            # Step 7: Update document with extracted data
            logger.debug(f"Updating document {document_id} with extracted data...")
            await self.update_extracted_data(
                document_id=document_id,
                extracted_data=extraction_result.data,
                confidence=extraction_result.confidence,
                processing_time_ms=extraction_result.metadata.get("processing_time_ms", 0)
            )

            # Update processing completion
            await self.update(document_id, {
                "processing_completed_at": datetime.now(timezone.utc),
                "form_mapping": mapped_data
            })

            logger.info(f"✅ Document extraction completed successfully: {document_id}")

            return {
                "success": True,
                "document_id": str(document_id),
                "template_name": template_name,
                "template_type": template_type,
                "ocr_confidence": ocr_result.confidence,
                "extraction_confidence": extraction_result.confidence,
                "fields_extracted": len(extraction_result.data),
                "extracted_data": extraction_result.data,
                "mapped_data": mapped_data,
                "warnings": extraction_result.warnings
            }

        except Exception as e:
            logger.error(f"❌ Error processing document extraction: {e}")
            import traceback
            traceback.print_exc()

            # Mark extraction as failed
            try:
                await self.update_extraction_failed(
                    document_id=document_id,
                    error_message=str(e)
                )
            except:
                pass

            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }

    async def delete(self, document_id: str) -> bool:
        """
        Delete document from database (hard delete)

        Args:
            document_id: Document UUID

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            query = """
                DELETE FROM uploaded_files
                WHERE id = $1
                RETURNING id
            """
            result = await self.db.fetchrow(query, document_id)

            if result:
                logger.info(f"Deleted document {document_id} from database")
                return True
            else:
                logger.warning(f"Document {document_id} not found for deletion")
                return False

        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return False


# Singleton instance
document_repository = DocumentRepository()
