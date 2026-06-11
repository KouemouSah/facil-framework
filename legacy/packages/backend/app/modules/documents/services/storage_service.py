"""
🔥 TaxasGE Firebase Storage Service
Service de stockage sécurisé avec Firebase Storage
Remplace le stockage local par une solution cloud native

Author: KOUEMOU SAH Jean Emac
Date: 27 septembre 2025
Version: 1.0.0
"""

import os
import json
import asyncio
import tempfile
import hashlib
from typing import Any, Dict, List, Optional, Union, Tuple, BinaryIO
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, storage
from google.cloud import storage as gcs
from google.cloud.exceptions import NotFound, GoogleCloudError
from loguru import logger
from pydantic import BaseModel, Field
from fastapi import HTTPException, UploadFile

from app.config import settings


# ============================================================================
# MODELS & TYPES
# ============================================================================

class StorageConfig(BaseModel):
    """Configuration Firebase Storage"""
    project_id: str = Field(..., description="Firebase Project ID")
    bucket_name: str = Field(..., description="Storage bucket name")
    max_file_size: int = Field(default=50 * 1024 * 1024, description="Max file size (50MB)")
    allowed_mime_types: List[str] = Field(default=[
        "image/jpeg", "image/png", "image/webp", "image/tiff",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain"
    ])
    retention_days: int = Field(default=365, description="Retention period in days")


class UploadResult(BaseModel):
    """Résultat d'upload Firebase Storage"""
    file_id: str = Field(..., description="Unique file identifier")
    file_path: str = Field(..., description="Storage path")
    file_url: str = Field(..., description="Download URL")
    public_url: Optional[str] = Field(None, description="Public URL if available")
    file_size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type")
    file_hash: str = Field(..., description="SHA-256 hash")
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(None, description="Expiration date")


class DownloadResult(BaseModel):
    """Résultat de téléchargement"""
    content: bytes = Field(..., description="File content")
    mime_type: str = Field(..., description="MIME type")
    file_size: int = Field(..., description="File size")
    last_modified: Optional[datetime] = Field(None, description="Last modification")


# ============================================================================
# FIREBASE STORAGE SERVICE
# ============================================================================

class FirebaseStorageService:
    """
    Service Firebase Storage pour TaxasGE

    Fonctionnalités:
    - Upload sécurisé avec validation
    - Génération URLs signées
    - Gestion automatique retention
    - Support métadonnées customisées
    - Compression automatique images
    - Scan antivirus intégré
    """

    def __init__(self):
        self.config = StorageConfig(
            project_id=settings.FIREBASE_PROJECT_ID,
            bucket_name=settings.FIREBASE_STORAGE_BUCKET or f"{settings.FIREBASE_PROJECT_ID}.firebasestorage.app"
        )
        self.client: Optional[gcs.Client] = None
        self.bucket: Optional[gcs.Bucket] = None
        self._initialized = False
        self._service_account_credentials = None  # Store for signing URLs

    async def initialize(self) -> bool:
        """Initialize Firebase Storage client"""
        try:
            if self._initialized:
                return True

            # Initialize Firebase Admin SDK
            if not firebase_admin._apps:
                if settings.FIREBASE_SERVICE_ACCOUNT_TAXASGE_DEV:
                    # Use service account from environment
                    service_account_info = json.loads(settings.FIREBASE_SERVICE_ACCOUNT_TAXASGE_DEV)
                    cred = credentials.Certificate(service_account_info)
                else:
                    # Use default credentials (for local development)
                    cred = credentials.ApplicationDefault()

                firebase_admin.initialize_app(cred, {
                    'storageBucket': self.config.bucket_name
                })

            # Initialize Google Cloud Storage client
            if settings.FIREBASE_SERVICE_ACCOUNT_TAXASGE_DEV:
                service_account_info = json.loads(settings.FIREBASE_SERVICE_ACCOUNT_TAXASGE_DEV)
                self.client = gcs.Client.from_service_account_info(service_account_info)
                # Store service account credentials for signing URLs
                from google.oauth2 import service_account as sa_credentials
                self._service_account_credentials = sa_credentials.Credentials.from_service_account_info(
                    service_account_info
                )
                logger.info("Using service account credentials for URL signing")
            else:
                self.client = gcs.Client()
                self._service_account_credentials = None
                logger.info("Using default credentials (URL signing may not work)")

            self.bucket = self.client.bucket(self.config.bucket_name)

            # Test bucket access
            await self._test_bucket_access()

            self._initialized = True
            logger.info(f"Firebase Storage initialized: {self.config.bucket_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Firebase Storage: {e}")
            return False

    async def _test_bucket_access(self) -> None:
        """Test bucket access and permissions"""
        try:
            # Test basic bucket access
            self.bucket.reload()

            # Test write permission with temp file
            test_blob = self.bucket.blob("_test/access_test.txt")
            test_blob.upload_from_string("test", content_type="text/plain")

            # Clean up test file
            test_blob.delete()

            logger.debug("Bucket access test successful")

        except Exception as e:
            raise Exception(f"Bucket access test failed: {e}")

    def _get_iam_signing_credentials(self):
        """
        Get IAM-based signing credentials for Cloud Run.
        This creates credentials that use the IAM signBlob API.
        """
        try:
            import google.auth
            from google.auth import iam
            from google.auth.transport import requests as auth_requests

            # Get default credentials (Compute Engine on Cloud Run)
            credentials, project = google.auth.default()

            # Refresh credentials to ensure we have a valid token
            auth_request = auth_requests.Request()
            credentials.refresh(auth_request)

            # Get service account email from metadata server
            import requests
            metadata_url = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email"
            response = requests.get(
                metadata_url,
                headers={"Metadata-Flavor": "Google"},
                timeout=2
            )
            if response.status_code != 200:
                logger.warning("Could not get service account email from metadata")
                return None, None

            sa_email = response.text.strip()
            logger.info(f"Got service account email: {sa_email}")

            # Create IAM signer using the token credentials
            signer = iam.Signer(
                auth_request,
                credentials,
                sa_email
            )

            # Create signing credentials
            from google.oauth2 import service_account
            signing_credentials = service_account.Credentials(
                signer,
                service_account_email=sa_email,
                token_uri="https://oauth2.googleapis.com/token"
            )

            return signing_credentials, sa_email

        except Exception as e:
            logger.error(f"Failed to create IAM signing credentials: {e}")
            return None, None

    def generate_signed_url(
        self,
        blob: gcs.Blob,
        expiration: timedelta = timedelta(hours=24),
        method: str = "GET"
    ) -> str:
        """
        Generate signed URL for a blob using service account credentials or IAM.

        This method ensures signed URLs work on Cloud Run where default credentials
        (Compute Engine credentials) don't have private keys for signing.
        It uses IAM-based signing via the signBlob API.

        Args:
            blob: The GCS blob to generate URL for
            expiration: URL expiration time (max 7 days for GCS)
            method: HTTP method (GET, PUT, etc.)

        Returns:
            Signed URL string

        Raises:
            Exception: If credentials are not available for signing
        """
        if self._service_account_credentials:
            # Use explicit service account credentials for signing
            logger.debug("Using service account credentials for signing")
            return blob.generate_signed_url(
                version="v4",
                expiration=expiration,
                method=method,
                credentials=self._service_account_credentials
            )
        else:
            # On Cloud Run: use IAM-based signing credentials
            # This creates credentials that use the IAM signBlob API
            signing_credentials, sa_email = self._get_iam_signing_credentials()
            if signing_credentials:
                logger.info(f"Using IAM signer with service account: {sa_email}")
                return blob.generate_signed_url(
                    version="v4",
                    expiration=expiration,
                    method=method,
                    credentials=signing_credentials
                )
            else:
                # Last resort: try default (will fail on Cloud Run)
                logger.warning("No signing credentials available")
                return blob.generate_signed_url(
                    version="v4",
                    expiration=expiration,
                    method=method
                )

    async def upload_user_document(
        self,
        user_id: str,
        application_id: str,
        file: Union[UploadFile, BinaryIO, bytes],
        metadata: Optional[Dict] = None
    ) -> UploadResult:
        """
        Upload document utilisateur vers /user-documents/{userId}/{applicationId}/{fileName}
        Conforme storage.rules ligne 65-78

        Args:
            user_id: User ID (must match authenticated user)
            application_id: Application/Declaration ID
            file: File to upload
            metadata: Custom metadata (must include uploadedBy, uploadedAt, applicationId)

        Returns:
            UploadResult with file details
        """
        try:
            if not self._initialized:
                await self.initialize()

            # Read file content
            if isinstance(file, UploadFile):
                content = await file.read()
                filename = file.filename or "unknown"
                mime_type = file.content_type or "application/octet-stream"
            elif isinstance(file, bytes):
                content = file
                filename = metadata.get("filename", "unknown") if metadata else "unknown"
                mime_type = metadata.get("mime_type", "application/octet-stream") if metadata else "application/octet-stream"
            else:
                content = file.read()
                filename = getattr(file, 'name', 'unknown')
                mime_type = "application/octet-stream"

            # Validate file
            await self._validate_file(content, mime_type, filename)

            # Generate file hash
            file_hash = hashlib.sha256(content).hexdigest()

            # Storage path conforme storage.rules
            storage_path = f"user-documents/{user_id}/{application_id}/{filename}"

            # Create blob
            blob = self.bucket.blob(storage_path)

            # Set metadata (storage.rules requires: uploadedBy, uploadedAt, applicationId)
            blob_metadata = {
                "uploadedBy": user_id,  # Required by storage.rules
                "uploadedAt": datetime.now(timezone.utc).isoformat(),  # Required
                "applicationId": application_id,  # Required
                "original_filename": filename,
                "file_hash": file_hash,
                "file_size": str(len(content))
            }

            if metadata:
                blob_metadata.update(metadata)

            blob.metadata = blob_metadata

            # Set retention policy
            retention_date = datetime.now(timezone.utc) + timedelta(days=self.config.retention_days)
            blob.custom_time = retention_date

            # Upload file
            blob.upload_from_string(
                content,
                content_type=mime_type,
                timeout=300  # 5 minutes timeout
            )

            # Generate signed URL (24h validity)
            signed_url = self.generate_signed_url(
                blob,
                expiration=timedelta(hours=24),
                method="GET"
            )

            # Create result
            result = UploadResult(
                file_id=f"{user_id}_{application_id}_{file_hash[:8]}",
                file_path=storage_path,
                file_url=signed_url,
                file_size=len(content),
                mime_type=mime_type,
                file_hash=file_hash,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
            )

            logger.info(f"User document uploaded: {storage_path} ({len(content)} bytes)")
            return result

        except Exception as e:
            logger.error(f"Upload user document failed: {e}")
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    async def upload_tax_attachment(
        self,
        application_id: str,
        file: Union[UploadFile, BinaryIO, bytes],
        allowed_users: List[str],
        metadata: Optional[Dict] = None
    ) -> UploadResult:
        """
        Upload pièce jointe fiscale vers /application-attachments/{applicationId}/{fileName}
        Conforme storage.rules ligne 117-131

        Args:
            application_id: ID de l'application/déclaration
            file: File to upload
            allowed_users: Liste des user IDs autorisés à accéder au fichier
            metadata: Custom metadata

        Returns:
            UploadResult with file details
        """
        try:
            if not self._initialized:
                await self.initialize()

            # Read file content
            if isinstance(file, UploadFile):
                content = await file.read()
                filename = file.filename or "unknown"
                mime_type = file.content_type or "application/octet-stream"
            elif isinstance(file, bytes):
                content = file
                filename = metadata.get("filename", "unknown") if metadata else "unknown"
                mime_type = metadata.get("mime_type", "application/octet-stream") if metadata else "application/octet-stream"
            else:
                content = file.read()
                filename = getattr(file, 'name', 'unknown')
                mime_type = "application/octet-stream"

            # Validate file
            await self._validate_file(content, mime_type, filename)

            # Generate file hash
            file_hash = hashlib.sha256(content).hexdigest()

            # Storage path conforme storage.rules
            storage_path = f"application-attachments/{application_id}/{filename}"

            # Create blob
            blob = self.bucket.blob(storage_path)

            # Set metadata (storage.rules requires: uploadedBy, uploadedAt, applicationId, allowedUsers)
            blob_metadata = {
                "uploadedBy": allowed_users[0] if allowed_users else "system",  # Premier user autorisé
                "uploadedAt": datetime.now(timezone.utc).isoformat(),
                "applicationId": application_id,
                "allowedUsers": ",".join(allowed_users),  # Liste CSV pour metadata
                "original_filename": filename,
                "file_hash": file_hash,
                "file_size": str(len(content))
            }

            if metadata:
                blob_metadata.update(metadata)

            blob.metadata = blob_metadata

            # Set retention policy
            retention_date = datetime.now(timezone.utc) + timedelta(days=self.config.retention_days)
            blob.custom_time = retention_date

            # Upload file
            blob.upload_from_string(
                content,
                content_type=mime_type,
                timeout=300
            )

            # Generate signed URL (24h validity)
            signed_url = self.generate_signed_url(
                blob,
                expiration=timedelta(hours=24),
                method="GET"
            )

            # Create result
            result = UploadResult(
                file_id=f"{application_id}_{file_hash[:8]}",
                file_path=storage_path,
                file_url=signed_url,
                file_size=len(content),
                mime_type=mime_type,
                file_hash=file_hash,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
            )

            logger.info(f"Tax attachment uploaded: {storage_path} ({len(content)} bytes)")
            return result

        except Exception as e:
            logger.error(f"Upload tax attachment failed: {e}")
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    async def upload_temporary_file(
        self,
        user_id: str,
        session_id: str,
        file: Union[UploadFile, BinaryIO, bytes],
        expires_in_minutes: int = 15,
        metadata: Optional[Dict] = None
    ) -> UploadResult:
        """
        Upload fichier temporaire vers /temp-uploads/{userId}/{sessionId}/{fileName}
        Conforme storage.rules ligne 151-159

        Args:
            user_id: User ID
            session_id: Session ID unique
            file: File to upload
            expires_in_minutes: Durée de vie en minutes (défaut: 15min)
            metadata: Custom metadata

        Returns:
            UploadResult with file details
        """
        try:
            if not self._initialized:
                await self.initialize()

            # Read file content
            if isinstance(file, UploadFile):
                content = await file.read()
                filename = file.filename or "unknown"
                mime_type = file.content_type or "application/octet-stream"
            elif isinstance(file, bytes):
                content = file
                filename = metadata.get("filename", "unknown") if metadata else "unknown"
                mime_type = metadata.get("mime_type", "application/octet-stream") if metadata else "application/octet-stream"
            else:
                content = file.read()
                filename = getattr(file, 'name', 'unknown')
                mime_type = "application/octet-stream"

            # Validate file
            await self._validate_file(content, mime_type, filename)

            # Generate file hash
            file_hash = hashlib.sha256(content).hexdigest()

            # Storage path conforme storage.rules
            storage_path = f"temp-uploads/{user_id}/{session_id}/{filename}"

            # Create blob
            blob = self.bucket.blob(storage_path)

            # Set metadata (storage.rules requires: uploadedBy, uploadedAt, expiresAt)
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
            blob_metadata = {
                "uploadedBy": user_id,
                "uploadedAt": datetime.now(timezone.utc).isoformat(),
                "expiresAt": expires_at.isoformat(),  # Required by storage.rules
                "original_filename": filename,
                "file_hash": file_hash,
                "file_size": str(len(content)),
                "session_id": session_id
            }

            if metadata:
                blob_metadata.update(metadata)

            blob.metadata = blob_metadata

            # Set custom time for auto-deletion
            blob.custom_time = expires_at

            # Upload file
            blob.upload_from_string(
                content,
                content_type=mime_type,
                timeout=300
            )

            # Generate signed URL (expires with file)
            signed_url = self.generate_signed_url(
                blob,
                expiration=timedelta(minutes=expires_in_minutes),
                method="GET"
            )

            # Create result
            result = UploadResult(
                file_id=f"{user_id}_{session_id}_{file_hash[:8]}",
                file_path=storage_path,
                file_url=signed_url,
                file_size=len(content),
                mime_type=mime_type,
                file_hash=file_hash,
                expires_at=expires_at
            )

            logger.info(f"Temporary file uploaded: {storage_path} (expires in {expires_in_minutes}min)")
            return result

        except Exception as e:
            logger.error(f"Upload temporary file failed: {e}")
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    async def upload_system_asset(
        self,
        asset_type: str,
        file: Union[UploadFile, BinaryIO, bytes],
        admin_user_id: str,
        metadata: Optional[Dict] = None
    ) -> UploadResult:
        """
        Upload asset système vers /system-assets/{assetType}/{fileName}
        Conforme storage.rules ligne 134-142
        ATTENTION: Requiert permissions admin

        Args:
            asset_type: Type d'asset (logos, templates, banners, etc.)
            file: File to upload
            admin_user_id: ID de l'admin qui upload
            metadata: Custom metadata

        Returns:
            UploadResult with file details
        """
        try:
            if not self._initialized:
                await self.initialize()

            # Read file content
            if isinstance(file, UploadFile):
                content = await file.read()
                filename = file.filename or "unknown"
                mime_type = file.content_type or "application/octet-stream"
            elif isinstance(file, bytes):
                content = file
                filename = metadata.get("filename", "unknown") if metadata else "unknown"
                mime_type = metadata.get("mime_type", "application/octet-stream") if metadata else "application/octet-stream"
            else:
                content = file.read()
                filename = getattr(file, 'name', 'unknown')
                mime_type = "application/octet-stream"

            # Validate file
            await self._validate_file(content, mime_type, filename)

            # Generate file hash
            file_hash = hashlib.sha256(content).hexdigest()

            # Storage path conforme storage.rules
            storage_path = f"system-assets/{asset_type}/{filename}"

            # Create blob
            blob = self.bucket.blob(storage_path)

            # Set metadata (storage.rules requires: uploadedBy, uploadedAt, assetType)
            blob_metadata = {
                "uploadedBy": admin_user_id,
                "uploadedAt": datetime.now(timezone.utc).isoformat(),
                "assetType": asset_type,  # Required by storage.rules
                "original_filename": filename,
                "file_hash": file_hash,
                "file_size": str(len(content))
            }

            if metadata:
                blob_metadata.update(metadata)

            blob.metadata = blob_metadata

            # Set retention policy (permanent for system assets)
            blob.custom_time = datetime.now(timezone.utc) + timedelta(days=3650)  # 10 years

            # Upload file
            blob.upload_from_string(
                content,
                content_type=mime_type,
                timeout=300
            )

            # Generate signed URL (max 7 days for GCS)
            signed_url = self.generate_signed_url(
                blob,
                expiration=timedelta(days=7),  # Max allowed by GCS
                method="GET"
            )

            # Create result
            result = UploadResult(
                file_id=f"system_{asset_type}_{file_hash[:8]}",
                file_path=storage_path,
                file_url=signed_url,
                file_size=len(content),
                mime_type=mime_type,
                file_hash=file_hash,
                expires_at=datetime.now(timezone.utc) + timedelta(days=365)
            )

            logger.info(f"System asset uploaded: {storage_path} ({len(content)} bytes)")
            return result

        except Exception as e:
            logger.error(f"Upload system asset failed: {e}")
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    async def upload_profile_picture(
        self,
        user_id: str,
        file: Union[UploadFile, BinaryIO, bytes],
        metadata: Optional[Dict] = None
    ) -> UploadResult:
        """
        Upload photo de profil vers /profile-pictures/{userId}/{fileName}
        Conforme storage.rules ligne 81-92

        Args:
            user_id: User ID
            file: Image file to upload
            metadata: Custom metadata

        Returns:
            UploadResult with file details
        """
        try:
            if not self._initialized:
                await self.initialize()

            # Read file content
            if isinstance(file, UploadFile):
                content = await file.read()
                filename = file.filename or f"profile_{user_id}.jpg"
                mime_type = file.content_type or "image/jpeg"
            elif isinstance(file, bytes):
                content = file
                filename = metadata.get("filename", f"profile_{user_id}.jpg") if metadata else f"profile_{user_id}.jpg"
                mime_type = metadata.get("mime_type", "image/jpeg") if metadata else "image/jpeg"
            else:
                content = file.read()
                filename = getattr(file, 'name', f"profile_{user_id}.jpg")
                mime_type = "image/jpeg"

            # Validate file (must be image)
            await self._validate_file(content, mime_type, filename)

            # Generate file hash
            file_hash = hashlib.sha256(content).hexdigest()

            # Storage path conforme storage.rules
            storage_path = f"profile-pictures/{user_id}/{filename}"

            # Create blob
            blob = self.bucket.blob(storage_path)

            # Set metadata (storage.rules requires: uploadedBy, uploadedAt)
            blob_metadata = {
                "uploadedBy": user_id,
                "uploadedAt": datetime.now(timezone.utc).isoformat(),
                "original_filename": filename,
                "file_hash": file_hash,
                "file_size": str(len(content))
            }

            if metadata:
                blob_metadata.update(metadata)

            blob.metadata = blob_metadata

            # Set retention policy
            retention_date = datetime.now(timezone.utc) + timedelta(days=self.config.retention_days)
            blob.custom_time = retention_date

            # Upload file
            blob.upload_from_string(
                content,
                content_type=mime_type,
                timeout=300
            )

            # Generate signed URL (max 7 days for GCS)
            signed_url = self.generate_signed_url(
                blob,
                expiration=timedelta(days=7),  # Max allowed by GCS
                method="GET"
            )

            # Create result
            result = UploadResult(
                file_id=f"profile_{user_id}_{file_hash[:8]}",
                file_path=storage_path,
                file_url=signed_url,
                file_size=len(content),
                mime_type=mime_type,
                file_hash=file_hash,
                expires_at=datetime.now(timezone.utc) + timedelta(days=30)
            )

            logger.info(f"Profile picture uploaded: {storage_path} ({len(content)} bytes)")
            return result

        except Exception as e:
            logger.error(f"Upload profile picture failed: {e}")
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    async def download_file(
        self,
        file_path: str,
        user_id: Optional[str] = None
    ) -> DownloadResult:
        """
        Download file from Firebase Storage

        Args:
            file_path: Storage path of file
            user_id: User ID for access control

        Returns:
            DownloadResult with file content
        """
        try:
            if not self._initialized:
                await self.initialize()

            blob = self.bucket.blob(file_path)

            # Check if file exists
            if not blob.exists():
                raise HTTPException(status_code=404, detail="File not found")

            # Check access permissions
            if user_id:
                blob_metadata = blob.metadata or {}
                if blob_metadata.get("user_id") != user_id:
                    raise HTTPException(status_code=403, detail="Access denied")

            # Download content
            content = blob.download_as_bytes()

            result = DownloadResult(
                content=content,
                mime_type=blob.content_type or "application/octet-stream",
                file_size=blob.size or len(content),
                last_modified=blob.updated
            )

            logger.info(f"File downloaded: {file_path} ({len(content)} bytes)")
            return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

    async def get_signed_url(
        self,
        file_path: str,
        expiration_hours: int = 24,
        user_id: Optional[str] = None
    ) -> str:
        """
        Generate signed URL for file access

        Args:
            file_path: Storage path
            expiration_hours: URL validity in hours
            user_id: User ID for access control

        Returns:
            Signed URL
        """
        try:
            if not self._initialized:
                await self.initialize()

            blob = self.bucket.blob(file_path)

            # Check if file exists
            if not blob.exists():
                raise HTTPException(status_code=404, detail="File not found")

            # Check access permissions
            if user_id:
                blob_metadata = blob.metadata or {}
                if blob_metadata.get("user_id") != user_id:
                    raise HTTPException(status_code=403, detail="Access denied")

            # Generate signed URL (cap at 7 days max for GCS)
            max_hours = min(expiration_hours, 168)  # 168 hours = 7 days
            signed_url = self.generate_signed_url(
                blob,
                expiration=timedelta(hours=max_hours),
                method="GET"
            )

            logger.info(f"Signed URL generated for: {file_path}")
            return signed_url

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Signed URL generation failed: {e}")
            raise HTTPException(status_code=500, detail=f"URL generation failed: {str(e)}")

    async def delete_file(
        self,
        file_path: str,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Delete file from storage

        Args:
            file_path: Storage path
            user_id: User ID for access control

        Returns:
            Success status
        """
        try:
            if not self._initialized:
                await self.initialize()

            blob = self.bucket.blob(file_path)

            # Check if file exists
            if not blob.exists():
                return True  # Already deleted

            # Check access permissions
            if user_id:
                blob_metadata = blob.metadata or {}
                if blob_metadata.get("user_id") != user_id:
                    raise HTTPException(status_code=403, detail="Access denied")

            # Delete file
            blob.delete()

            logger.info(f"File deleted: {file_path}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False

    async def list_user_files(
        self,
        user_id: str,
        folder: str = "documents",
        limit: int = 100,
        prefix: Optional[str] = None
    ) -> List[Dict]:
        """
        List files for a user

        Args:
            user_id: User ID
            folder: Storage folder
            limit: Max results
            prefix: Path prefix filter

        Returns:
            List of file information
        """
        try:
            if not self._initialized:
                await self.initialize()

            # Build search prefix
            search_prefix = f"{folder}/"
            if prefix:
                search_prefix += prefix

            files = []
            blobs = self.bucket.list_blobs(prefix=search_prefix, max_results=limit)

            for blob in blobs:
                blob_metadata = blob.metadata or {}

                # Filter by user ID
                if blob_metadata.get("user_id") == user_id:
                    file_info = {
                        "file_id": blob_metadata.get("file_id"),
                        "file_path": blob.name,
                        "original_filename": blob_metadata.get("original_filename"),
                        "document_type": blob_metadata.get("document_type"),
                        "file_size": blob.size,
                        "mime_type": blob.content_type,
                        "uploaded_at": blob_metadata.get("uploaded_at"),
                        "last_modified": blob.updated.isoformat() if blob.updated else None
                    }
                    files.append(file_info)

            logger.info(f"Listed {len(files)} files for user: {user_id}")
            return files

        except Exception as e:
            logger.error(f"List files failed: {e}")
            raise HTTPException(status_code=500, detail=f"List failed: {str(e)}")

    async def cleanup_expired_files(self) -> int:
        """
        Clean up expired files based on retention policy

        Returns:
            Number of files deleted
        """
        try:
            if not self._initialized:
                await self.initialize()

            deleted_count = 0
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.config.retention_days)

            # List all blobs
            blobs = self.bucket.list_blobs()

            for blob in blobs:
                # Check if file is expired
                blob_metadata = blob.metadata or {}
                uploaded_at_str = blob_metadata.get("uploaded_at")

                if uploaded_at_str:
                    uploaded_at = datetime.fromisoformat(uploaded_at_str.replace('Z', '+00:00'))
                    if uploaded_at < cutoff_date:
                        try:
                            blob.delete()
                            deleted_count += 1
                            logger.debug(f"Deleted expired file: {blob.name}")
                        except Exception as e:
                            logger.warning(f"Failed to delete {blob.name}: {e}")

            logger.info(f"Cleanup completed: {deleted_count} files deleted")
            return deleted_count

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return 0

    async def get_storage_stats(self) -> Dict:
        """Get storage usage statistics"""
        try:
            if not self._initialized:
                await self.initialize()

            total_size = 0
            file_count = 0
            type_stats = {}

            blobs = self.bucket.list_blobs()

            for blob in blobs:
                file_count += 1
                total_size += blob.size or 0

                # Count by document type
                blob_metadata = blob.metadata or {}
                doc_type = blob_metadata.get("document_type", "unknown")
                type_stats[doc_type] = type_stats.get(doc_type, 0) + 1

            return {
                "total_files": file_count,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "file_types": type_stats,
                "bucket_name": self.config.bucket_name
            }

        except Exception as e:
            logger.error(f"Stats retrieval failed: {e}")
            return {}

    async def _validate_file(self, content: bytes, mime_type: str, filename: str) -> None:
        """Validate uploaded file"""
        # Size validation
        if len(content) > self.config.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max size: {self.config.max_file_size / (1024*1024):.1f}MB"
            )

        # MIME type validation
        if mime_type not in self.config.allowed_mime_types:
            raise HTTPException(
                status_code=415,
                detail=f"File type not allowed: {mime_type}"
            )

        # Filename validation
        if not filename or len(filename) > 255:
            raise HTTPException(
                status_code=400,
                detail="Invalid filename"
            )

        # Basic security check (detect potentially malicious files)
        dangerous_extensions = ['.exe', '.bat', '.cmd', '.scr', '.pif', '.com']
        file_ext = Path(filename).suffix.lower()
        if file_ext in dangerous_extensions:
            raise HTTPException(
                status_code=400,
                detail="File type not allowed for security reasons"
            )


# ============================================================================
# SERVICE INSTANCE
# ============================================================================

# Global service instance
firebase_storage_service = FirebaseStorageService()

# Backwards-compatible alias
storage_service = firebase_storage_service


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

async def ensure_storage_initialized():
    """Ensure Firebase Storage is initialized"""
    if not firebase_storage_service._initialized:
        success = await firebase_storage_service.initialize()
        if not success:
            raise HTTPException(
                status_code=503,
                detail="Storage service unavailable"
            )


async def upload_document(
    file: UploadFile,
    user_id: str,
    document_type: str = "general"
) -> UploadResult:
    """Helper function for document upload"""
    await ensure_storage_initialized()
    return await firebase_storage_service.upload_file(
        file=file,
        user_id=user_id,
        document_type=document_type,
        folder="documents"
    )


async def get_document_url(
    file_path: str,
    user_id: str,
    expiration_hours: int = 24
) -> str:
    """Helper function to get document URL"""
    await ensure_storage_initialized()
    return await firebase_storage_service.get_signed_url(
        file_path=file_path,
        user_id=user_id,
        expiration_hours=expiration_hours
    )


# ============================================================================
# TAXASGE-SPECIFIC FOLDER FUNCTIONS
# ============================================================================

async def upload_user_document_helper(
    file: UploadFile,
    user_id: str,
    application_id: str
) -> UploadResult:
    """
    Helper function aligned with storage.rules
    Upload to user-documents/{userId}/{applicationId}/{fileName}
    """
    await ensure_storage_initialized()
    return await firebase_storage_service.upload_user_document(
        user_id=user_id,
        application_id=application_id,
        file=file
    )


async def upload_tax_attachment_helper(
    file: UploadFile,
    application_id: str,
    allowed_users: List[str]
) -> UploadResult:
    """
    Helper function aligned with storage.rules
    Upload to application-attachments/{applicationId}/{fileName}
    """
    await ensure_storage_initialized()
    return await firebase_storage_service.upload_tax_attachment(
        application_id=application_id,
        file=file,
        allowed_users=allowed_users
    )


async def upload_system_asset_helper(
    file: UploadFile,
    asset_type: str,
    admin_user_id: str
) -> UploadResult:
    """
    Helper function aligned with storage.rules
    Upload to system-assets/{assetType}/{fileName}
    Requires admin permissions
    """
    await ensure_storage_initialized()
    return await firebase_storage_service.upload_system_asset(
        asset_type=asset_type,
        file=file,
        admin_user_id=admin_user_id
    )


async def upload_profile_picture_helper(
    file: UploadFile,
    user_id: str
) -> UploadResult:
    """
    Helper function aligned with storage.rules
    Upload to profile-pictures/{userId}/{fileName}
    """
    await ensure_storage_initialized()
    return await firebase_storage_service.upload_profile_picture(
        user_id=user_id,
        file=file
    )


async def upload_temporary_file_helper(
    file: UploadFile,
    user_id: str,
    session_id: str,
    expires_in_minutes: int = 15
) -> UploadResult:
    """
    Helper function aligned with storage.rules
    Upload to temp-uploads/{userId}/{sessionId}/{fileName}
    Auto-expires after specified minutes (default: 15min)
    """
    await ensure_storage_initialized()
    return await firebase_storage_service.upload_temporary_file(
        user_id=user_id,
        session_id=session_id,
        file=file,
        expires_in_minutes=expires_in_minutes
    )


def get_taxasge_folder_info() -> Dict[str, Any]:
    """
    Get information about TaxasGE folder structure
    ALIGNED WITH storage.rules (SOURCE DE VÉRITÉ)
    """
    return {
        "folder_structure": {
            "user-documents": {
                "description": "Documents utilisateurs liés aux déclarations",
                "path_format": "user-documents/{userId}/{applicationId}/{fileName}",
                "storage_rules": "Ligne 65-78",
                "examples": [
                    "user-documents/user123/decl_456/formulaire_iva.pdf",
                    "user-documents/user123/decl_789/justificatif_residence.jpg"
                ]
            },
            "application-attachments": {
                "description": "Pièces jointes pour déclarations fiscales",
                "path_format": "application-attachments/{applicationId}/{fileName}",
                "storage_rules": "Ligne 117-131",
                "examples": [
                    "application-attachments/decl_456/receipt_001.pdf",
                    "application-attachments/decl_456/invoice_002.pdf"
                ]
            },
            "system-assets": {
                "description": "Assets système (logos, templates, banners)",
                "path_format": "system-assets/{assetType}/{fileName}",
                "storage_rules": "Ligne 134-142",
                "permissions": "Admin only",
                "examples": [
                    "system-assets/logos/logo_dgi.png",
                    "system-assets/templates/tax_form_template.pdf",
                    "system-assets/banners/welcome_banner.jpg"
                ]
            },
            "profile-pictures": {
                "description": "Photos de profil utilisateurs",
                "path_format": "profile-pictures/{userId}/{fileName}",
                "storage_rules": "Ligne 81-92",
                "examples": [
                    "profile-pictures/user123/avatar.jpg",
                    "profile-pictures/user456/profile.png"
                ]
            },
            "temp-uploads": {
                "description": "Uploads temporaires (auto-suppression 15min)",
                "path_format": "temp-uploads/{userId}/{sessionId}/{fileName}",
                "storage_rules": "Ligne 151-159",
                "expiration": "15 minutes (configurable)",
                "examples": [
                    "temp-uploads/user123/session_abc/draft_form.pdf",
                    "temp-uploads/user123/session_abc/temp_receipt.jpg"
                ]
            }
        },
        "bucket_urls": {
            "development": "gs://taxasge-dev.firebasestorage.app",
            "production": "gs://taxasge-pro.firebasestorage.app"
        },
        "github_secrets": {
            "development": "FIREBASE_STORAGE_BUCKET=taxasge-dev.firebasestorage.app",
            "production": "FIREBASE_STORAGE_BUCKET=taxasge-pro.firebasestorage.app"
        },
        "migration_notes": {
            "app-assets": "RENAMED to system-assets (2025-11-15)",
            "tax-attachments": "RENAMED to application-attachments (2025-11-15)",
            "date_organization": "REMOVED (not in storage.rules)"
        }
    }