"""
User Documents Export Service — ZIP archive generation.

Runs as background task (asyncio.create_task) to generate a ZIP archive
of the user's vault documents and upload it to Firebase Storage.

Status tracking uses Redis cache (1-hour TTL).
Download URLs are signed (1-hour expiry).
"""

import asyncio
import json
import re
import zipfile
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg
from loguru import logger


class UserDocumentsExportService:
    """Service for exporting user vault documents as a ZIP archive."""

    # Hard limits to protect memory and avoid abuse
    MAX_ZIP_SIZE_BYTES: int = 200 * 1024 * 1024  # 200 MB
    MAX_DOCUMENTS_PER_EXPORT: int = 500
    DOWNLOAD_TIMEOUT_SECONDS: int = 30
    UPLOAD_TIMEOUT_SECONDS: int = 300
    STATUS_CACHE_TTL_SECONDS: int = 3600  # 1 hour

    async def generate_export(
        self,
        user_id: UUID,
        export_id: str,
        category: Optional[str],
        db_pool: asyncpg.Pool,
    ) -> None:
        """
        Background task: generate ZIP of user's documents.

        Pipeline:
        1. Fetch documents list from DB
        2. Download each file from Firebase Storage
        3. Create ZIP in memory (BytesIO) organized by category folders
        4. Add metadata.json with document manifest
        5. Upload ZIP to Firebase Storage
        6. Update status in Redis cache
        """
        try:
            async with db_pool.acquire() as db:
                # Mark as processing
                await self._update_export_status(
                    export_id, str(user_id), "processing"
                )

                # Fetch documents to export
                docs = await self._fetch_documents(db, user_id, category)

                if not docs:
                    await self._update_export_status(
                        export_id, str(user_id), "failed",
                        error="No documents found",
                    )
                    return

                # Generate ZIP in memory
                zip_buffer = BytesIO()
                metadata_entries: List[Dict[str, Any]] = []
                downloaded_count = 0
                total_zip_bytes = 0

                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for doc in docs:
                        try:
                            file_content = await self._download_from_firebase(
                                doc["file_path"]
                            )
                            if not file_content:
                                logger.debug(
                                    f"Export {export_id}: skip file {doc['id']} "
                                    f"(download returned None)"
                                )
                                continue

                            # Guard against exceeding memory limit
                            total_zip_bytes += len(file_content)
                            if total_zip_bytes > self.MAX_ZIP_SIZE_BYTES:
                                logger.warning(
                                    f"Export {export_id}: ZIP size limit reached "
                                    f"({total_zip_bytes} bytes), stopping"
                                )
                                break

                            # Organize in folders by category
                            cat = doc.get("document_category") or "other"
                            safe_name = self._safe_filename(
                                doc.get("display_name") or doc.get("file_name") or "document"
                            )
                            zip_path = f"{cat}/{safe_name}"

                            # Handle duplicate names within the ZIP
                            existing_names = set(zf.namelist())
                            if zip_path in existing_names:
                                name_parts = safe_name.rsplit(".", 1)
                                base = name_parts[0]
                                ext = f".{name_parts[1]}" if len(name_parts) > 1 else ""
                                counter = 1
                                while zip_path in existing_names:
                                    zip_path = f"{cat}/{base}_{counter}{ext}"
                                    counter += 1

                            zf.writestr(zip_path, file_content)
                            downloaded_count += 1

                            # Build metadata entry
                            metadata_entries.append({
                                "id": str(doc["id"]),
                                "file_name": doc.get("file_name"),
                                "document_type": doc.get("document_type"),
                                "category": cat,
                                "holder_name": doc.get("holder_name"),
                                "document_number": doc.get("document_number"),
                                "issue_date": (
                                    str(doc["issue_date"]) if doc.get("issue_date") else None
                                ),
                                "expiry_date": (
                                    str(doc["expiry_date"]) if doc.get("expiry_date") else None
                                ),
                                "source": doc.get("source"),
                                "zip_path": zip_path,
                                "created_at": str(doc["created_at"]),
                            })

                        except Exception as file_err:
                            logger.warning(
                                f"Export {export_id}: skip file {doc['id']}: {file_err}"
                            )
                            continue

                    # Add metadata manifest
                    metadata = {
                        "export_id": export_id,
                        "user_id": str(user_id),
                        "exported_at": datetime.now(timezone.utc).isoformat(),
                        "total_documents": downloaded_count,
                        "category_filter": category,
                        "documents": metadata_entries,
                    }
                    zf.writestr(
                        "metadata.json",
                        json.dumps(metadata, indent=2, ensure_ascii=False),
                    )

                zip_content = zip_buffer.getvalue()
                zip_size = len(zip_content)

                if downloaded_count == 0:
                    await self._update_export_status(
                        export_id, str(user_id), "failed",
                        error="No files could be downloaded from storage",
                    )
                    return

                # Upload ZIP to Firebase Storage
                firebase_path = await self._upload_zip_to_firebase(
                    user_id=str(user_id),
                    export_id=export_id,
                    zip_content=zip_content,
                )

                # Mark as completed
                await self._update_export_status(
                    export_id, str(user_id), "completed",
                    file_path=firebase_path,
                    file_size=zip_size,
                    document_count=downloaded_count,
                )

                logger.info(
                    f"Export {export_id} completed: "
                    f"{downloaded_count} docs, {zip_size} bytes"
                )

        except Exception as e:
            logger.error(f"Export {export_id} failed: {e}")
            try:
                await self._update_export_status(
                    export_id, str(user_id), "failed",
                    error=str(e)[:500],
                )
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────

    async def _fetch_documents(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        category: Optional[str],
    ) -> List[asyncpg.Record]:
        """Fetch active documents for the user, optionally filtered by category."""
        filters = ["user_id = $1", "status = 'active'", "deleted_at IS NULL"]
        params: list = [user_id]

        if category:
            filters.append(f"document_category = ${len(params) + 1}")
            params.append(category)

        query = f"""
            SELECT id, document_type, document_category, file_path, file_name,
                   file_size_bytes, mime_type, display_name, holder_name,
                   document_number, issue_date, expiry_date, source,
                   created_at
            FROM user_documents
            WHERE {' AND '.join(filters)}
            ORDER BY document_category, created_at DESC
            LIMIT {self.MAX_DOCUMENTS_PER_EXPORT}
        """
        return await db.fetch(query, *params)

    async def _download_from_firebase(self, file_path: str) -> Optional[bytes]:
        """Download a file from Firebase Storage. Returns None on failure."""
        try:
            from app.modules.documents.services.storage_service import (
                firebase_storage_service,
            )

            if not firebase_storage_service._initialized:
                await firebase_storage_service.initialize()

            blob = firebase_storage_service.bucket.blob(file_path)
            if not blob.exists():
                logger.debug(f"Firebase blob not found: {file_path}")
                return None

            return blob.download_as_bytes(timeout=self.DOWNLOAD_TIMEOUT_SECONDS)
        except Exception as e:
            logger.debug(f"Firebase download failed for {file_path}: {e}")
            return None

    async def _upload_zip_to_firebase(
        self,
        user_id: str,
        export_id: str,
        zip_content: bytes,
    ) -> str:
        """Upload ZIP archive to Firebase Storage. Returns the storage path."""
        from app.modules.documents.services.storage_service import (
            firebase_storage_service,
        )

        if not firebase_storage_service._initialized:
            await firebase_storage_service.initialize()

        storage_path = f"user-documents/{user_id}/exports/{export_id}.zip"
        blob = firebase_storage_service.bucket.blob(storage_path)
        blob.metadata = {
            "uploadedBy": user_id,
            "uploadedAt": datetime.now(timezone.utc).isoformat(),
            "exportId": export_id,
            "assetType": "vault-export",
        }
        blob.upload_from_string(
            zip_content,
            content_type="application/zip",
            timeout=self.UPLOAD_TIMEOUT_SECONDS,
        )
        return storage_path

    async def _update_export_status(
        self,
        export_id: str,
        user_id: str,
        status: str,
        file_path: Optional[str] = None,
        file_size: Optional[int] = None,
        document_count: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        """Store export status in Redis cache (1-hour TTL)."""
        try:
            from app.core.cache import get_cache

            cache = get_cache()
            if cache:
                data = {
                    "export_id": export_id,
                    "user_id": user_id,
                    "status": status,
                    "file_path": file_path,
                    "file_size": file_size,
                    "document_count": document_count,
                    "error": error,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                await cache.set(
                    f"vault_export:{export_id}",
                    data,
                    ttl=self.STATUS_CACHE_TTL_SECONDS,
                )
        except Exception as e:
            logger.debug(f"Export status update failed for {export_id}: {e}")

    async def get_export_status(self, export_id: str) -> Optional[Dict[str, Any]]:
        """Get export status from Redis cache."""
        try:
            from app.core.cache import get_cache

            cache = get_cache()
            if cache:
                return await cache.get(f"vault_export:{export_id}")
        except Exception:
            pass
        return None

    async def get_export_download_url(
        self,
        export_id: str,
        user_id: str,
    ) -> Optional[str]:
        """
        Generate a signed download URL for a completed export.

        Enforces ownership: only the user who started the export can download.
        Returns None if export is not completed or ownership fails.
        """
        status_data = await self.get_export_status(export_id)
        if not status_data or status_data.get("status") != "completed":
            return None

        # Ownership check (OWASP A01)
        if status_data.get("user_id") != user_id:
            return None

        file_path = status_data.get("file_path")
        if not file_path:
            return None

        try:
            from app.modules.documents.services.storage_service import (
                firebase_storage_service,
            )

            if not firebase_storage_service._initialized:
                await firebase_storage_service.initialize()

            blob = firebase_storage_service.bucket.blob(file_path)
            url = firebase_storage_service.generate_signed_url(
                blob=blob,
                expiration=timedelta(hours=1),
                method="GET",
            )
            return url
        except Exception as e:
            logger.error(f"Export download URL generation failed for {export_id}: {e}")
            return None

    @staticmethod
    def _safe_filename(name: str) -> str:
        """Sanitize filename for ZIP archive (strip unsafe characters)."""
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
        safe = safe.strip(". ")
        if not safe:
            return "document"
        return safe[:200]


# Module-level singleton
export_service = UserDocumentsExportService()
