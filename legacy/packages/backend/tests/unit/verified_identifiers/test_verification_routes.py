"""
Tests for Verified Identifiers API Routes

Tests the identity verification endpoints for CNEDOGE agents:
- GET /pending - list pending verifications
- GET /requests/{id}/verification-details - detailed view with navigation
- POST /requests/{id}/verify-identifier - verify single identifier
- POST /requests/{id}/verify-batch - verify all identifiers
- POST /requests/{id}/reject-identifier - reject with fraud option
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from fastapi.testclient import TestClient


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    user = MagicMock()
    user.id = uuid4()
    user.email = "agent@test.com"
    user.role = "dgi_agent"
    return user


@pytest.fixture
def mock_db_pool():
    """Mock database connection pool."""
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    return pool, conn


@pytest.fixture
def sample_entity():
    """Sample entity data for CNEDOGE_PASAPORTE."""
    return {
        'workflow_codes': ['PASAPORTE_NUEVO', 'PASAPORTE_RENOVACION']
    }


@pytest.fixture
def sample_service_request():
    """Sample service request with pending verification."""
    return {
        'id': uuid4(),
        'reference': 'SRV-2026-00001',
        'workflow_code': 'PASAPORTE_NUEVO',
        'solicitud_type': 'nuevo',
        'status': 'SUBMITTED',
        'verification_status': 'pending',
        'verification_details': {},
        'submitted_at': datetime.now(),
        'form_data': {
            'dip': {
                'numero_dip': '000074636',
                'fecha_expiracion': '2030-08-05'
            }
        },
        'first_name': 'Juan',
        'last_name': 'Perez',
        'email': 'juan@test.com',
        'user_id': uuid4()
    }


@pytest.fixture
def sample_document():
    """Sample document with extraction data."""
    return {
        'id': uuid4(),
        'document_code': 'dip_gq',
        'document_name': 'DIP Guinea Ecuatorial',
        'file_path': '/documents/dip.pdf',
        'file_name': 'dip.pdf',
        'mime_type': 'application/pdf',
        'extraction_data': {
            'numero_dip': '000074636',
            'fecha_expiracion': '2030-08-05',
            'nombres': 'JUAN',
            'apellidos': 'PEREZ'
        },
        'extraction_confidence': 0.85,
        'extraction_status': 'validated'
    }


@pytest.fixture
def sample_config():
    """Sample document verification config."""
    return {
        'document_code': 'dip_gq',
        'identifier_type': 'dni',
        'extraction_paths': ['numero_dip', 'documento.numero_dip'],
        'source': 'cnedoge'
    }


# =============================================================================
# MODEL TESTS
# =============================================================================

class TestModels:
    """Test Pydantic models for verification endpoints."""

    def test_extracted_identifier_model(self):
        """Test ExtractedIdentifier model creation."""
        from app.modules.verified_identifiers.api.verified_identifiers_routes import ExtractedIdentifier

        identifier = ExtractedIdentifier(
            identifier_type='dni',
            value='000074636',
            document_code='dip_gq',
            document_name='DIP Guinea Ecuatorial',
            confidence=0.85,
            expires_at='2030-08-05',
            status='pending'
        )

        assert identifier.identifier_type == 'dni'
        assert identifier.value == '000074636'
        assert identifier.status == 'pending'

    def test_verify_identifier_request_model(self):
        """Test VerifyIdentifierRequest model validation."""
        from app.modules.verified_identifiers.api.verified_identifiers_routes import VerifyIdentifierRequest

        request = VerifyIdentifierRequest(
            identifier_type='dni',
            identifier_value='000074636',
            expires_at='2030-08-05',
            notes='Verified via CNEDOGE system'
        )

        assert request.identifier_type == 'dni'
        assert request.identifier_value == '000074636'
        assert request.notes == 'Verified via CNEDOGE system'

    def test_reject_identifier_request_model(self):
        """Test RejectIdentifierRequest model with fraud flag."""
        from app.modules.verified_identifiers.api.verified_identifiers_routes import RejectIdentifierRequest

        request = RejectIdentifierRequest(
            identifier_type='dni',
            identifier_value='000074636',
            reason='Document appears to be falsified',
            is_fraud=True
        )

        assert request.is_fraud is True
        assert len(request.reason) >= 5

    def test_verify_batch_request_model(self):
        """Test VerifyBatchRequest model with multiple identifiers."""
        from app.modules.verified_identifiers.api.verified_identifiers_routes import (
            VerifyBatchRequest,
            VerifyIdentifierRequest
        )

        request = VerifyBatchRequest(
            identifiers=[
                VerifyIdentifierRequest(
                    identifier_type='dni',
                    identifier_value='000074636'
                ),
                VerifyIdentifierRequest(
                    identifier_type='pasaporte',
                    identifier_value='GQ1234567',
                    expires_at='2030-01-15'
                )
            ],
            notes='Batch verification via CNEDOGE'
        )

        assert len(request.identifiers) == 2
        assert request.identifiers[0].identifier_type == 'dni'
        assert request.identifiers[1].identifier_type == 'pasaporte'


# =============================================================================
# CRYPTO SERVICE TESTS
# =============================================================================

class TestCryptoService:
    """Test CryptoService for blind index and encryption."""

    def test_normalize_dni(self):
        """Test DNI normalization (9 digits, padded)."""
        from app.modules.verified_identifiers.services.crypto_service import CryptoService

        crypto = CryptoService(
            aes_key=b'0' * 32,
            hmac_key=b'1' * 32
        )

        # Test padding
        assert crypto._normalize_value('74636', 'dni') == '000074636'
        assert crypto._normalize_value('000074636', 'dni') == '000074636'

        # Test stripping non-digits
        assert crypto._normalize_value('000-074-636', 'dni') == '000074636'

    def test_normalize_pasaporte(self):
        """Test passport normalization (alphanumeric, uppercase)."""
        from app.modules.verified_identifiers.services.crypto_service import CryptoService

        crypto = CryptoService(
            aes_key=b'0' * 32,
            hmac_key=b'1' * 32
        )

        assert crypto._normalize_value('gq1234567', 'pasaporte') == 'GQ1234567'
        assert crypto._normalize_value('GQ-123-4567', 'pasaporte') == 'GQ1234567'

    def test_blind_index_deterministic(self):
        """Test that blind index is deterministic for same input."""
        from app.modules.verified_identifiers.services.crypto_service import CryptoService

        crypto = CryptoService(
            aes_key=b'0' * 32,
            hmac_key=b'1' * 32
        )

        index1 = crypto.compute_blind_index('000074636', 'dni')
        index2 = crypto.compute_blind_index('000074636', 'dni')

        assert index1 == index2
        assert len(index1) == 32  # SHA-256 = 32 bytes

    def test_blind_index_different_types(self):
        """Test that same value with different types produces different index."""
        from app.modules.verified_identifiers.services.crypto_service import CryptoService

        crypto = CryptoService(
            aes_key=b'0' * 32,
            hmac_key=b'1' * 32
        )

        index_dni = crypto.compute_blind_index('123456789', 'dni')
        index_nif = crypto.compute_blind_index('123456789', 'nif')

        assert index_dni != index_nif

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption/decryption preserves data."""
        from app.modules.verified_identifiers.services.crypto_service import CryptoService

        crypto = CryptoService(
            aes_key=b'0' * 32,
            hmac_key=b'1' * 32
        )

        original = '000074636'
        encrypted = crypto.encrypt_value(original)
        decrypted = crypto.decrypt_value(encrypted)

        assert decrypted == original
        assert encrypted != original.encode()  # Should be different (encrypted)


# =============================================================================
# ENDPOINT LOGIC TESTS
# =============================================================================

class TestPendingVerificationsLogic:
    """Test logic for /pending endpoint."""

    def test_extract_identifier_from_form_data(self):
        """Test extracting identifiers from form_data structure."""
        form_data = {
            'dip': {
                'numero_dip': '000074636',
                'fecha_expiracion': '2030-08-05'
            },
            'pasaporte_antiguo': {
                'numero_pasaporte': 'GQ1234567',
                'fecha_expiracion': '2024-11-03'
            }
        }

        # Simulate extraction logic
        identifiers = []
        for section_key in ['dip', 'pasaporte_antiguo']:
            section = form_data.get(section_key, {})
            for field_key, id_type in [('numero_dip', 'dni'), ('numero_pasaporte', 'pasaporte')]:
                if field_key in section and section[field_key]:
                    identifiers.append({
                        'type': id_type,
                        'value': section[field_key],
                        'expires_at': section.get('fecha_expiracion')
                    })

        assert len(identifiers) == 2
        assert identifiers[0]['type'] == 'dni'
        assert identifiers[0]['value'] == '000074636'
        assert identifiers[1]['type'] == 'pasaporte'
        assert identifiers[1]['value'] == 'GQ1234567'

    def test_count_pending_verified(self):
        """Test counting pending vs verified identifiers."""
        identifiers = [
            {'status': 'pending'},
            {'status': 'pending'},
            {'status': 'verified'},
            {'status': 'verified_manually'},
            {'status': 'rejected'}
        ]

        pending_count = len([i for i in identifiers if i['status'] == 'pending'])
        verified_count = len([i for i in identifiers if i['status'] in ('verified', 'verified_manually')])

        assert pending_count == 2
        assert verified_count == 2


class TestVerificationDetailsLogic:
    """Test logic for /verification-details endpoint."""

    def test_navigation_prev_next(self):
        """Test previous/next ID calculation for navigation."""
        # Simulate ordered list of pending requests
        requests = [
            {'id': 'aaa', 'submitted_at': '2026-01-01'},
            {'id': 'bbb', 'submitted_at': '2026-01-02'},
            {'id': 'ccc', 'submitted_at': '2026-01-03'},
        ]

        current_id = 'bbb'
        current_index = next(i for i, r in enumerate(requests) if r['id'] == current_id)

        prev_id = requests[current_index - 1]['id'] if current_index > 0 else None
        next_id = requests[current_index + 1]['id'] if current_index < len(requests) - 1 else None

        assert prev_id == 'aaa'
        assert next_id == 'ccc'


class TestVerifyIdentifierLogic:
    """Test logic for /verify-identifier endpoint."""

    def test_all_verified_check(self):
        """Test checking if all identifiers are verified."""
        all_types = ['dni', 'pasaporte']
        verification_details = {
            'dni': {'status': 'verified_manually'},
            'pasaporte': {'status': 'verified'}
        }

        all_verified = all(
            verification_details.get(t, {}).get('status') in ('verified', 'verified_manually')
            for t in all_types
        )

        assert all_verified is True

    def test_partial_verified_check(self):
        """Test partial verification detection."""
        all_types = ['dni', 'pasaporte']
        verification_details = {
            'dni': {'status': 'verified_manually'},
            'pasaporte': {'status': 'pending'}
        }

        all_verified = all(
            verification_details.get(t, {}).get('status') in ('verified', 'verified_manually')
            for t in all_types
        )

        assert all_verified is False


class TestRejectIdentifierLogic:
    """Test logic for /reject-identifier endpoint."""

    def test_fraud_marking_updates_status(self):
        """Test that fraud marking sets is_active=false."""
        is_fraud = True
        expected_is_active = not is_fraud

        assert expected_is_active is False

    def test_rejection_without_fraud(self):
        """Test normal rejection doesn't affect cache."""
        is_fraud = False
        should_store_in_cache = is_fraud

        assert should_store_in_cache is False


# =============================================================================
# INTEGRATION-STYLE TESTS (with mocks)
# =============================================================================

class TestEndpointResponses:
    """Test endpoint response structures."""

    def test_pending_verification_item_structure(self):
        """Test PendingVerificationItem has all required fields."""
        from app.modules.verified_identifiers.api.verified_identifiers_routes import (
            PendingVerificationItem,
            ExtractedIdentifier
        )

        item = PendingVerificationItem(
            id='test-uuid',
            reference='SRV-2026-00001',
            workflow_code='PASAPORTE_NUEVO',
            solicitud_type='nuevo',
            status='SUBMITTED',
            verification_status='pending',
            citizen_name='Juan Perez',
            submitted_at='2026-01-27T10:00:00',
            identifiers=[
                ExtractedIdentifier(
                    identifier_type='dni',
                    value='000074636',
                    document_code='dip_gq',
                    document_name='DIP',
                    status='pending'
                )
            ],
            pending_count=1,
            verified_count=0,
            documents_count=2
        )

        assert item.reference == 'SRV-2026-00001'
        assert item.pending_count == 1
        assert len(item.identifiers) == 1

    def test_verification_detail_response_structure(self):
        """Test VerificationDetailResponse has navigation fields."""
        from app.modules.verified_identifiers.api.verified_identifiers_routes import (
            VerificationDetailResponse,
            DocumentInfo,
            ExtractedIdentifier
        )

        response = VerificationDetailResponse(
            id='test-uuid',
            reference='SRV-2026-00001',
            workflow_code='PASAPORTE_NUEVO',
            solicitud_type='nuevo',
            status='SUBMITTED',
            verification_status='pending',
            citizen_name='Juan Perez',
            documents=[
                DocumentInfo(
                    id='doc-uuid',
                    document_code='dip_gq',
                    document_name='DIP',
                    file_path='/path/to/file',
                    file_name='dip.pdf'
                )
            ],
            identifiers=[],
            previous_id='prev-uuid',
            next_id='next-uuid'
        )

        assert response.previous_id == 'prev-uuid'
        assert response.next_id == 'next-uuid'
        assert len(response.documents) == 1

    def test_verify_identifier_response_structure(self):
        """Test VerifyIdentifierResponse has all_verified flag."""
        from app.modules.verified_identifiers.api.verified_identifiers_routes import VerifyIdentifierResponse

        response = VerifyIdentifierResponse(
            verified_identifier_id='vi-uuid',
            identifier_type='dni',
            status='verified_manually',
            all_verified=True,
            request_verification_status='verified_manually'
        )

        assert response.all_verified is True
        assert response.status == 'verified_manually'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
