"""
Verification Service

Main service for verifying document identifiers against external databases.
Handles the verification flow for service requests.
"""

import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import asyncpg
from loguru import logger

from .crypto_service import CryptoService, get_crypto_service
from ..repositories.verified_identifiers_repository import VerifiedIdentifiersRepository
from ..models.verified_identifier import (
    VerificationResult,
    VerificationStatus,
    ServiceRequestVerificationResult,
)


class VerificationError(Exception):
    """Base exception for verification errors."""
    retryable: bool = False


class TransientVerificationError(VerificationError):
    """Temporary failure - should retry."""
    retryable = True


class PermanentVerificationError(VerificationError):
    """Permanent failure - don't retry."""
    retryable = False


class VerificationService:
    """
    Service for verifying document identifiers.

    Verifies identifiers against the verified_identifiers table
    using blind index lookup (no decryption needed).
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        crypto: Optional[CryptoService] = None,
        repo: Optional[VerifiedIdentifiersRepository] = None
    ):
        """
        Initialize verification service.

        Args:
            pool: asyncpg connection pool
            crypto: CryptoService instance
            repo: Repository instance
        """
        self.pool = pool
        self.crypto = crypto or get_crypto_service()
        self.repo = repo or VerifiedIdentifiersRepository(pool, self.crypto)

    async def verify_identifier(
        self,
        value: str,
        identifier_type: str,
        request_id: Optional[str] = None,
        performed_by: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> VerificationResult:
        """
        Verify if an identifier exists in the verified_identifiers table.

        Uses blind index for search (no decryption needed).
        Auto-fails if the identifier is expired.

        Args:
            value: The identifier value to verify
            identifier_type: Type of identifier (dni, pasaporte, etc.)
            request_id: Optional service request ID for audit
            performed_by: Optional user ID for audit
            ip_address: Optional IP address for audit

        Returns:
            VerificationResult with verification status
        """
        try:
            # Compute blind index
            blind_index = self.crypto.compute_blind_index(value, identifier_type)

            # Search in database
            result = await self.repo.find_by_blind_index(
                blind_index=blind_index,
                identifier_type=identifier_type
            )

            # Log the search attempt (audit)
            await self.repo.log_search(
                blind_index=blind_index,
                identifier_type=identifier_type,
                found=result is not None,
                request_id=request_id,
                performed_by=performed_by,
                ip_address=ip_address
            )

            if result and result.get("is_active"):
                # Check expiration - Auto-fail if expired
                expires_at = result.get("expires_at")
                if expires_at and expires_at < datetime.now(timezone.utc):
                    return VerificationResult(
                        verified=False,
                        reason="expired",
                        expires_at=expires_at,
                        source=result.get("source")
                    )

                return VerificationResult(
                    verified=True,
                    source=result.get("source"),
                    verified_at=result.get("verified_at"),
                    expires_at=expires_at
                )

            return VerificationResult(verified=False, reason="not_found")

        except Exception as e:
            logger.error(f"Verification error for {identifier_type}: {e}")
            raise TransientVerificationError(f"Verification failed: {e}")

    async def verify_service_request(
        self,
        request_id: str,
        performed_by: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> ServiceRequestVerificationResult:
        """
        Verify all identifiers in a service request.

        Uses document_verification_config for dynamic mapping.
        Called after submission.

        Args:
            request_id: UUID of the service request
            performed_by: Optional user ID for audit
            ip_address: Optional IP address for audit

        Returns:
            Complete verification result for the request
        """
        results: Dict[str, VerificationResult] = {}
        errors: List[Dict[str, str]] = []

        try:
            # Get documents for this request
            documents = await self._get_request_documents(request_id)

            # Get verification configs (cached)
            configs = await self.repo.get_active_configs()
            config_by_doc_code = {c["document_code"]: c for c in configs}

            for doc in documents:
                extraction = doc.get("extraction_data", {})
                doc_code = doc.get("document_code")

                if not extraction or not doc_code:
                    continue

                # Check if this document type needs verification
                config = config_by_doc_code.get(doc_code)
                if not config:
                    logger.debug(f"No verification config for {doc_code}")
                    continue

                # Extract identifier using configured paths
                identifier_value = self._extract_field(
                    extraction,
                    config["extraction_paths"]
                )

                if not identifier_value:
                    logger.debug(f"No identifier found in {doc_code} for paths {config['extraction_paths']}")
                    continue

                try:
                    # Verify against external database
                    result = await self.verify_identifier(
                        value=identifier_value,
                        identifier_type=config["identifier_type"],
                        request_id=request_id,
                        performed_by=performed_by,
                        ip_address=ip_address
                    )

                    # Add document context
                    result.document_code = doc_code
                    result.is_required = config.get("is_required", True)

                    results[config["identifier_type"]] = result

                except Exception as e:
                    errors.append({
                        "document_code": doc_code,
                        "identifier_type": config["identifier_type"],
                        "error": str(e)
                    })

            # Calculate overall status
            status = self._calculate_overall_status(results)

            # Update service_request verification_status
            await self._update_request_verification_status(
                request_id=request_id,
                status=status,
                details={
                    "results": {k: v.model_dump(mode='json') for k, v in results.items()},
                    "errors": errors
                }
            )

            return ServiceRequestVerificationResult(
                request_id=request_id,
                status=status,
                results=results,
                errors=errors,
                verified_at=datetime.now(timezone.utc)
            )

        except Exception as e:
            logger.error(f"Failed to verify service request {request_id}: {e}")
            raise

    async def manual_verification(
        self,
        request_id: str,
        verified_by: str,
        notes: Optional[str] = None,
        identifier_types: Optional[List[str]] = None
    ) -> None:
        """
        Mark a service request as manually verified by an agent.

        Args:
            request_id: UUID of the service request
            verified_by: UUID of the agent
            notes: Optional notes for the verification
            identifier_types: Optional list of specific types to verify
        """
        details = {
            "manual_verification": True,
            "verified_by": verified_by,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "notes": notes
        }

        if identifier_types:
            details["identifier_types_verified"] = identifier_types

        await self._update_request_verification_status(
            request_id=request_id,
            status=VerificationStatus.VERIFIED_MANUALLY,
            details=details
        )

        logger.info(f"Service request {request_id} manually verified by {verified_by}")

    async def queue_for_verification(self, request_id: str) -> str:
        """
        Add a service request to the verification queue.

        Args:
            request_id: UUID of the service request

        Returns:
            UUID of the queue item
        """
        return await self.repo.queue_verification(request_id)

    def _extract_field(self, data: Dict[str, Any], paths: List[str]) -> Optional[str]:
        """
        Extract field value from nested dict using dot-notation paths.

        Tries each path in order and returns the first non-empty value.

        Args:
            data: The data dictionary to search
            paths: List of dot-notation paths to try

        Returns:
            The extracted value or None if not found
        """
        for path in paths:
            keys = path.split(".")
            value = data
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    value = None
                    break
            if value:
                return str(value).strip()
        return None

    def _calculate_overall_status(self, results: Dict[str, VerificationResult]) -> VerificationStatus:
        """
        Calculate overall verification status from individual results.

        Logic:
        - If no results: pending
        - If all required verified: verified (or partial if optional missing)
        - If some required verified: partial_verification
        - If none required verified: not_found

        Args:
            results: Dictionary of verification results by type

        Returns:
            Overall verification status
        """
        if not results:
            return VerificationStatus.PENDING

        required_results = [r for r in results.values() if r.is_required]
        optional_results = [r for r in results.values() if not r.is_required]

        # Check required documents
        required_verified = all(r.verified for r in required_results) if required_results else True
        required_not_found = any(not r.verified for r in required_results) if required_results else False

        # All required verified
        if required_verified:
            # Check optional for partial status
            if optional_results and any(not r.verified for r in optional_results):
                return VerificationStatus.PARTIAL_VERIFICATION
            return VerificationStatus.VERIFIED

        # Some required not found
        if required_not_found:
            if any(r.verified for r in required_results):
                return VerificationStatus.PARTIAL_VERIFICATION
            return VerificationStatus.NOT_FOUND

        return VerificationStatus.PENDING

    async def _get_request_documents(self, request_id: str) -> List[Dict[str, Any]]:
        """
        Get documents for a service request.

        Args:
            request_id: UUID of the service request

        Returns:
            List of document records with extraction_data
        """
        query = """
            SELECT id, document_code, extraction_data, extraction_status
            FROM service_request_documents
            WHERE service_request_id = $1
              AND extraction_data IS NOT NULL
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, request_id)
            result = []
            for row in rows:
                doc = dict(row)
                # Parse JSONB if needed
                if isinstance(doc.get("extraction_data"), str):
                    doc["extraction_data"] = json.loads(doc["extraction_data"])
                result.append(doc)
            return result

    async def _update_request_verification_status(
        self,
        request_id: str,
        status: VerificationStatus,
        details: Dict[str, Any]
    ) -> None:
        """
        Update the verification status on a service request.

        Args:
            request_id: UUID of the service request
            status: New verification status
            details: Verification details dictionary
        """
        query = """
            UPDATE service_requests
            SET verification_status = $2,
                verification_details = $3,
                updated_at = NOW()
            WHERE id = $1
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                query,
                request_id,
                status.value,
                json.dumps(details)
            )

    async def check_funcionario_status(
        self,
        matricula: str,
    ) -> Dict[str, Any]:
        """
        Check funcionario matricula status in verified_identifiers table.

        This is used to determine if the funcionario menu should be visible
        and if the user's matricula is still active.

        Args:
            matricula: The matricula to check

        Returns:
            Dict with status fields:
            - verified: bool - User has been verified as funcionario
            - is_active: bool - Matricula is active in verified_identifiers
            - is_expired: bool - Matricula has expired
            - expires_at: str|None - Expiration date if applicable
            - source: str|None - Source of verification
            - checked_at: str - Timestamp of this check
            - found_in_registry: bool - Found in verified_identifiers table
        """
        now = datetime.now(timezone.utc)

        try:
            # Compute blind index for lookup
            blind_index = self.crypto.compute_blind_index(matricula, "matricula_funcionario")

            # Search in verified_identifiers table
            result = await self.repo.find_by_blind_index(
                blind_index=blind_index,
                identifier_type="matricula_funcionario"
            )

            if not result:
                # Not found in verified_identifiers
                return {
                    "verified": True,  # User IS verified (has funcionario_verified_at)
                    "is_active": False,  # But not in registry
                    "is_expired": False,
                    "expires_at": None,
                    "source": None,
                    "checked_at": now.isoformat(),
                    "found_in_registry": False,
                }

            # Found in registry - check status
            is_active = result.get("is_active", False)
            expires_at = result.get("expires_at")

            # Check if expired
            is_expired = False
            if expires_at and expires_at < now:
                is_expired = True

            return {
                "verified": True,  # User IS verified
                "is_active": is_active and not is_expired,  # Active AND not expired
                "is_expired": is_expired,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "source": result.get("source"),
                "checked_at": now.isoformat(),
                "found_in_registry": True,
            }

        except Exception as e:
            logger.error(f"Error checking funcionario status for matricula: {e}")
            # On error, return safe default (allow access but log)
            return {
                "verified": True,
                "is_active": True,  # Fail-open: allow access on error
                "is_expired": False,
                "expires_at": None,
                "source": None,
                "checked_at": now.isoformat(),
                "found_in_registry": False,
                "error": str(e),
            }
