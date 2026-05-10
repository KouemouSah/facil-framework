"""
Batch Import Service

Handles importing verified identifiers from external sources
via CSV or JSON files.
"""

import csv
import json
import io
from datetime import datetime
from typing import Optional, List, Dict, Any, Iterator

import asyncpg
from loguru import logger

from .crypto_service import CryptoService, get_crypto_service
from ..repositories.verified_identifiers_repository import VerifiedIdentifiersRepository
from ..models.verified_identifier import BatchImportResult


class BatchImportError(Exception):
    """Exception for batch import errors."""
    pass


class BatchImportService:
    """
    Service for batch importing verified identifiers.

    Supports CSV and JSON formats with streaming for large files.
    """

    SUPPORTED_FORMATS = ["csv", "json"]
    DEFAULT_BATCH_SIZE = 100  # Records per batch insert

    def __init__(
        self,
        pool: asyncpg.Pool,
        crypto: Optional[CryptoService] = None,
        repo: Optional[VerifiedIdentifiersRepository] = None
    ):
        """
        Initialize batch import service.

        Args:
            pool: asyncpg connection pool
            crypto: CryptoService instance
            repo: Repository instance
        """
        self.pool = pool
        self.crypto = crypto or get_crypto_service()
        self.repo = repo or VerifiedIdentifiersRepository(pool, self.crypto)

    async def import_batch(
        self,
        file_content: bytes,
        file_format: str,
        source: str,
        identifier_type: str,
        imported_by: str,
        batch_size: int = DEFAULT_BATCH_SIZE
    ) -> BatchImportResult:
        """
        Import batch of identifiers from file content.

        Args:
            file_content: Raw file content (bytes)
            file_format: File format ("csv" or "json")
            source: Source of verification (cnedoge, trafico, etc.)
            identifier_type: Type of identifiers (dni, pasaporte, etc.)
            imported_by: UUID of admin user performing import
            batch_size: Number of records per batch insert

        Returns:
            BatchImportResult with statistics

        Expected CSV format:
            identifier,expires_at,metadata
            123456789,2030-12-31,"{""name"":""JUAN""}"

        Expected JSON format:
            {"identifiers": [{"identifier": "123456789", "expires_at": "2030-12-31"}]}
        """
        if file_format.lower() not in self.SUPPORTED_FORMATS:
            raise BatchImportError(f"Unsupported format: {file_format}. Use: {self.SUPPORTED_FORMATS}")

        # Parse records
        if file_format.lower() == "csv":
            records = list(self._parse_csv(file_content))
        else:
            records = list(self._parse_json(file_content))

        logger.info(f"Importing {len(records)} records from {file_format} (source={source}, type={identifier_type})")

        # Process in batches
        imported = 0
        skipped = 0
        errors: List[Dict[str, str]] = []

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            batch_result = await self._process_batch(
                batch=batch,
                source=source,
                identifier_type=identifier_type,
                imported_by=imported_by
            )
            imported += batch_result["imported"]
            skipped += batch_result["skipped"]
            errors.extend(batch_result["errors"])

        result = BatchImportResult(
            total=len(records),
            imported=imported,
            skipped=skipped,
            errors=errors
        )

        logger.info(f"Import complete: {result.imported}/{result.total} imported, {result.skipped} skipped, {len(result.errors)} errors")

        return result

    async def _process_batch(
        self,
        batch: List[Dict[str, Any]],
        source: str,
        identifier_type: str,
        imported_by: str
    ) -> Dict[str, Any]:
        """
        Process a batch of records.

        Args:
            batch: List of record dictionaries
            source: Source of verification
            identifier_type: Type of identifiers
            imported_by: UUID of admin user

        Returns:
            Dictionary with imported count, skipped count, and errors
        """
        imported = 0
        skipped = 0
        errors: List[Dict[str, str]] = []

        for record in batch:
            try:
                identifier = record.get("identifier", "").strip()
                if not identifier:
                    skipped += 1
                    continue

                # Parse expires_at
                expires_at = None
                if record.get("expires_at"):
                    try:
                        expires_at = datetime.fromisoformat(record["expires_at"].replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        try:
                            expires_at = datetime.strptime(record["expires_at"], "%Y-%m-%d")
                        except ValueError:
                            logger.warning(f"Invalid expires_at for {identifier}: {record['expires_at']}")

                # Parse metadata
                metadata = record.get("metadata")
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except json.JSONDecodeError:
                        metadata = None

                # Upsert the identifier
                await self.repo.upsert(
                    value=identifier,
                    identifier_type=identifier_type,
                    source=source,
                    expires_at=expires_at,
                    metadata=metadata,
                    verified_by=imported_by
                )
                imported += 1

            except Exception as e:
                identifier = record.get("identifier", "unknown")
                errors.append({
                    "identifier": identifier[:20],  # Truncate for safety
                    "error": str(e)
                })
                logger.error(f"Failed to import {identifier}: {e}")

        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors
        }

    def _parse_csv(self, content: bytes) -> Iterator[Dict[str, Any]]:
        """
        Parse CSV content into records.

        Expected columns: identifier, expires_at (optional), metadata (optional)

        Args:
            content: Raw CSV bytes

        Yields:
            Record dictionaries
        """
        # Try different encodings
        for encoding in ["utf-8", "utf-8-sig", "latin-1"]:
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise BatchImportError("Unable to decode CSV content")

        # Parse CSV
        reader = csv.DictReader(io.StringIO(text))

        # Normalize field names
        for row in reader:
            record = {}

            # Find identifier field
            for key in ["identifier", "Identifier", "IDENTIFIER", "id", "ID", "numero", "number"]:
                if key in row and row[key]:
                    record["identifier"] = row[key]
                    break

            if not record.get("identifier"):
                # Skip rows without identifier
                continue

            # Find expires_at field
            for key in ["expires_at", "expiry", "expiration", "fecha_expiracion", "validity"]:
                if key in row and row[key]:
                    record["expires_at"] = row[key]
                    break

            # Find metadata field
            for key in ["metadata", "extra", "data", "info"]:
                if key in row and row[key]:
                    record["metadata"] = row[key]
                    break

            yield record

    def _parse_json(self, content: bytes) -> Iterator[Dict[str, Any]]:
        """
        Parse JSON content into records.

        Expected format:
            {"identifiers": [{"identifier": "...", "expires_at": "...", "metadata": {...}}]}
        Or:
            [{"identifier": "...", ...}]

        Args:
            content: Raw JSON bytes

        Yields:
            Record dictionaries
        """
        try:
            data = json.loads(content.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise BatchImportError(f"Invalid JSON: {e}")

        # Support both formats
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            records = data.get("identifiers", data.get("records", data.get("data", [])))
        else:
            raise BatchImportError("JSON must be an array or object with 'identifiers' key")

        for record in records:
            if not isinstance(record, dict):
                continue

            # Normalize field names
            normalized = {}

            # Find identifier
            for key in ["identifier", "id", "numero", "number", "value"]:
                if key in record and record[key]:
                    normalized["identifier"] = str(record[key])
                    break

            if not normalized.get("identifier"):
                continue

            # Copy other fields
            if "expires_at" in record:
                normalized["expires_at"] = record["expires_at"]
            elif "expiry" in record:
                normalized["expires_at"] = record["expiry"]

            if "metadata" in record:
                normalized["metadata"] = record["metadata"]

            yield normalized

    async def validate_file(self, file_content: bytes, file_format: str) -> Dict[str, Any]:
        """
        Validate import file without actually importing.

        Args:
            file_content: Raw file content
            file_format: File format

        Returns:
            Validation result with record count and sample
        """
        if file_format.lower() not in self.SUPPORTED_FORMATS:
            return {"valid": False, "error": f"Unsupported format: {file_format}"}

        try:
            if file_format.lower() == "csv":
                records = list(self._parse_csv(file_content))
            else:
                records = list(self._parse_json(file_content))

            return {
                "valid": True,
                "record_count": len(records),
                "sample": records[:5] if records else [],
                "fields_found": list(records[0].keys()) if records else []
            }

        except BatchImportError as e:
            return {"valid": False, "error": str(e)}
        except Exception as e:
            return {"valid": False, "error": f"Parse error: {e}"}
