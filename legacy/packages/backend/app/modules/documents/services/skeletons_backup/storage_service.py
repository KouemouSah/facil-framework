"""
Storage Service - Firebase Storage (GCP) Integration

Service for uploading, downloading, and managing files in Firebase Storage
Configured buckets (see storage.rules):
- user-documents/{userId}/{applicationId}/{fileName} - User tax documents (5MB, PDF/Office/Excel)
- profile-pictures/{userId}/{fileName} - Profile images (2MB, images only)
- official-documents/{category}/{fileName} - Official docs (read-only for users)
- tax-forms/{formId}/{fileName} - Tax form templates
- application-attachments/{applicationId}/{fileName} - Supporting documents
- temp-uploads/{userId}/{sessionId}/{fileName} - Temporary uploads (expire after processing)
- reports/{reportType}/{fileName} - Analytics exports (officials only)
- audit-documents/{year}/{month}/{fileName} - Audit trail (admin only)

Project: taxasge-dev (dev), taxasge-pro (prod)
"""

from typing import Dict, Any, Optional
from loguru import logger
import os
from pathlib import Path


class StorageService:
    """Service for Firebase Storage (GCP) operations"""

    def __init__(self, project_id: str = "taxasge-dev"):
        """
        Initialize Firebase Storage service

        Args:
            project_id: Firebase/GCP project ID (taxasge-dev or taxasge-pro)
        """
        self.project_id = project_id
        # TODO: Initialize Firebase Storage client
        # from firebase_admin import storage, credentials, initialize_app
        # if not firebase_admin._apps:
        #     cred = credentials.Certificate('path/to/serviceAccountKey.json')
        #     initialize_app(cred, {'storageBucket': f'{project_id}.appspot.com'})
        # self.bucket = storage.bucket()

    async def upload_file(
        self,
        file_path: str,
        filename: str,
        user_id: str,
        storage_type: str = "user-documents",
        application_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Upload file to Firebase Storage

        Args:
            file_path: Local file path to upload
            filename: Original filename
            user_id: User ID (for auth and path)
            storage_type: Storage bucket path type (user-documents, profile-pictures, temp-uploads, etc.)
            application_id: Required for user-documents and application-attachments
            metadata: Custom metadata (uploadedBy, uploadedAt, category, etc.)

        Returns:
            {
                "url": str,
                "path": str,
                "size": int,
                "content_type": str,
                "bucket": str
            }

        Storage paths (from storage.rules):
        - user-documents/{userId}/{applicationId}/{fileName}
        - profile-pictures/{userId}/{fileName}
        - temp-uploads/{userId}/{sessionId}/{fileName}
        - application-attachments/{applicationId}/{fileName}
        """
        # Build storage path based on storage_type (following storage.rules)
        if storage_type == "user-documents":
            if not application_id:
                raise ValueError("application_id required for user-documents")
            storage_path = f"user-documents/{user_id}/{application_id}/{filename}"
        elif storage_type == "profile-pictures":
            storage_path = f"profile-pictures/{user_id}/{filename}"
        elif storage_type == "temp-uploads":
            import uuid
            session_id = metadata.get("sessionId") or str(uuid.uuid4())
            storage_path = f"temp-uploads/{user_id}/{session_id}/{filename}"
        elif storage_type == "application-attachments":
            if not application_id:
                raise ValueError("application_id required for application-attachments")
            storage_path = f"application-attachments/{application_id}/{filename}"
        elif storage_type == "tax-forms":
            form_id = metadata.get("formId", "default")
            storage_path = f"tax-forms/{form_id}/{filename}"
        elif storage_type == "official-documents":
            category = metadata.get("category", "general")
            storage_path = f"official-documents/{category}/{filename}"
        else:
            raise ValueError(f"Invalid storage_type: {storage_type}")

        try:
            # Get file size
            file_size = os.path.getsize(file_path)

            # Determine content type
            content_type = self._get_content_type(filename)

            # Validate size limits (from storage.rules)
            if storage_type == "user-documents" and file_size > 5 * 1024 * 1024:  # 5MB
                raise ValueError("File size exceeds 5MB limit for documents")
            elif storage_type == "profile-pictures" and file_size > 2 * 1024 * 1024:  # 2MB
                raise ValueError("File size exceeds 2MB limit for images")

            # Prepare metadata (required by storage.rules)
            upload_metadata = {
                "uploadedBy": user_id,
                "uploadedAt": str(os.path.getmtime(file_path)),
                "contentType": content_type,
            }
            if application_id:
                upload_metadata["applicationId"] = application_id
            if metadata:
                upload_metadata.update(metadata)

            # TODO: Implement actual Firebase Storage upload
            # blob = self.bucket.blob(storage_path)
            # blob.metadata = upload_metadata
            # blob.upload_from_filename(file_path, content_type=content_type)
            # blob.make_public()  # Or generate signed URL for private access
            # public_url = blob.public_url

            # Mock result for now
            bucket_name = f"{self.project_id}.appspot.com"
            public_url = f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{storage_path.replace('/', '%2F')}?alt=media"

            logger.info(f"Uploaded file {filename} to {storage_path} ({file_size} bytes)")

            return {
                "url": public_url,
                "path": storage_path,
                "bucket": bucket_name,
                "size": file_size,
                "content_type": content_type,
                "metadata": upload_metadata,
            }

        except Exception as e:
            logger.error(f"Failed to upload file {filename}: {e}")
            raise

    async def download_file(
        self,
        storage_path: str,
        destination_path: str,
    ) -> str:
        """
        Download file from Firebase Storage

        Args:
            storage_path: Path in storage bucket (e.g., "user-documents/user123/app456/file.pdf")
            destination_path: Local path to save file

        Returns:
            Local file path
        """
        try:
            # TODO: Implement actual Firebase Storage download
            # blob = self.bucket.blob(storage_path)
            # blob.download_to_filename(destination_path)

            logger.info(f"Downloaded {storage_path} to {destination_path}")

            return destination_path

        except Exception as e:
            logger.error(f"Failed to download file {storage_path}: {e}")
            raise

    async def delete_file(
        self,
        storage_path: str,
    ) -> bool:
        """
        Delete file from Firebase Storage

        Args:
            storage_path: Path in storage bucket

        Returns:
            True if deleted successfully
        """
        try:
            # TODO: Implement actual Firebase Storage delete
            # blob = self.bucket.blob(storage_path)
            # blob.delete()

            logger.info(f"Deleted file {storage_path}")

            return True

        except Exception as e:
            logger.error(f"Failed to delete file {storage_path}: {e}")
            raise

    async def get_signed_url(
        self,
        storage_path: str,
        expires_in: Optional[int] = None,
    ) -> str:
        """
        Get signed URL for private file access (Firebase Storage)

        Args:
            storage_path: Path in storage bucket
            expires_in: Expiration time in seconds (default: 3600 = 1 hour)

        Returns:
            Signed URL
        """
        from datetime import timedelta

        expiry = expires_in or 3600

        try:
            # TODO: Implement actual Firebase Storage signed URL
            # blob = self.bucket.blob(storage_path)
            # signed_url = blob.generate_signed_url(
            #     version="v4",
            #     expiration=timedelta(seconds=expiry),
            #     method="GET"
            # )

            # Mock result for now
            bucket_name = f"{self.project_id}.appspot.com"
            signed_url = f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{storage_path.replace('/', '%2F')}?alt=media&token=MOCK"

            logger.info(f"Generated signed URL for {storage_path} (expires in {expiry}s)")

            return signed_url

        except Exception as e:
            logger.error(f"Failed to generate signed URL for {storage_path}: {e}")
            raise

    async def list_files(
        self,
        prefix: str,
    ) -> list[Dict[str, Any]]:
        """
        List files in Firebase Storage with prefix

        Args:
            prefix: Folder prefix (e.g., "user-documents/user123/")

        Returns:
            List of file metadata
        """
        try:
            # TODO: Implement actual Firebase Storage list
            # blobs = self.bucket.list_blobs(prefix=prefix)
            # files = [
            #     {
            #         "name": blob.name,
            #         "size": blob.size,
            #         "content_type": blob.content_type,
            #         "created": blob.time_created,
            #         "updated": blob.updated,
            #         "metadata": blob.metadata,
            #     }
            #     for blob in blobs
            # ]

            # Mock result for now
            files = []

            logger.info(f"Listed {len(files)} files with prefix {prefix}")

            return files

        except Exception as e:
            logger.error(f"Failed to list files with prefix {prefix}: {e}")
            raise

    def _get_content_type(self, filename: str) -> str:
        """
        Determine content type from filename extension

        Args:
            filename: File name with extension

        Returns:
            MIME type
        """
        extension = Path(filename).suffix.lower()

        content_types = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
            ".csv": "text/csv",
            ".txt": "text/plain",
            ".json": "application/json",
            ".xml": "application/xml",
        }

        return content_types.get(extension, "application/octet-stream")

    async def move_file(
        self,
        source_path: str,
        destination_path: str,
    ) -> Dict[str, Any]:
        """
        Move/rename file in Firebase Storage

        Args:
            source_path: Current file path
            destination_path: New file path

        Returns:
            New file metadata
        """
        try:
            # TODO: Implement actual Firebase Storage move
            # source_blob = self.bucket.blob(source_path)
            # new_blob = self.bucket.rename_blob(source_blob, destination_path)
            # Or: self.bucket.copy_blob(source_blob, self.bucket, destination_path)
            #     source_blob.delete()

            # Get new public URL
            bucket_name = f"{self.project_id}.appspot.com"
            new_url = f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{destination_path.replace('/', '%2F')}?alt=media"

            logger.info(f"Moved file from {source_path} to {destination_path}")

            return {
                "url": new_url,
                "path": destination_path,
                "bucket": bucket_name,
            }

        except Exception as e:
            logger.error(f"Failed to move file {source_path}: {e}")
            raise

    async def get_file_metadata(
        self,
        storage_path: str,
    ) -> Dict[str, Any]:
        """
        Get file metadata from Firebase Storage

        Args:
            storage_path: Path in storage bucket

        Returns:
            File metadata (size, content-type, created, updated, custom metadata)
        """
        try:
            # TODO: Implement actual Firebase Storage metadata retrieval
            # blob = self.bucket.blob(storage_path)
            # blob.reload()
            # return {
            #     "path": blob.name,
            #     "size": blob.size,
            #     "content_type": blob.content_type,
            #     "created": blob.time_created,
            #     "updated": blob.updated,
            #     "metadata": blob.metadata,
            # }

            logger.info(f"Getting metadata for {storage_path}")

            bucket_name = f"{self.project_id}.appspot.com"
            return {
                "path": storage_path,
                "bucket": bucket_name,
                "size": 0,
                "content_type": "application/octet-stream",
            }

        except Exception as e:
            logger.error(f"Failed to get metadata for {storage_path}: {e}")
            raise
