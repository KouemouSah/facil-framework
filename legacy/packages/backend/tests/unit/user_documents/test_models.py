"""
Tests for user_documents Pydantic models.

Validates all request/response models, type aliases, constants,
and edge cases for the Coffre-fort documentaire module.
"""
import pytest
from datetime import date, datetime
from uuid import uuid4, UUID

from pydantic import ValidationError

from app.modules.user_documents.models.user_document import (
    # Constants
    VAULT_QUOTA_BYTES,
    MAX_FILE_SIZE_BYTES,
    MAX_BULK_UPLOAD,
    SIGNED_URL_EXPIRY_SECONDS,
    ALLOWED_MIME_TYPES,
    # Request models
    UserDocumentUpload,
    UserDocumentUpdate,
    UserDocumentBulkAction,
    # Response models
    UserDocumentResponse,
    UserDocumentListItem,
    UserDocumentListResponse,
    UserDocumentStats,
    GeneratedDocumentResponse,
    AlertResponse,
    DuplicateInfo,
    UploadResult,
    # Readiness models
    ReadinessItem,
    ReadinessResult,
)


# =============================================================================
# CONSTANTS
# =============================================================================


class TestConstants:
    """Validate configuration constants have expected values."""

    def test_vault_quota_is_100mb(self):
        assert VAULT_QUOTA_BYTES == 100 * 1024 * 1024

    def test_max_file_size_is_10mb(self):
        assert MAX_FILE_SIZE_BYTES == 10 * 1024 * 1024

    def test_max_bulk_upload_is_5(self):
        assert MAX_BULK_UPLOAD == 5

    def test_signed_url_expiry_is_15_minutes(self):
        assert SIGNED_URL_EXPIRY_SECONDS == 900

    def test_allowed_mime_types_contains_pdf(self):
        assert "application/pdf" in ALLOWED_MIME_TYPES

    def test_allowed_mime_types_contains_jpeg(self):
        assert "image/jpeg" in ALLOWED_MIME_TYPES

    def test_allowed_mime_types_contains_png(self):
        assert "image/png" in ALLOWED_MIME_TYPES

    def test_allowed_mime_types_contains_webp(self):
        assert "image/webp" in ALLOWED_MIME_TYPES

    def test_allowed_mime_types_does_not_contain_exe(self):
        assert "application/exe" not in ALLOWED_MIME_TYPES

    def test_allowed_mime_types_does_not_contain_zip(self):
        assert "application/zip" not in ALLOWED_MIME_TYPES

    def test_allowed_mime_types_count_is_4(self):
        assert len(ALLOWED_MIME_TYPES) == 4


# =============================================================================
# REQUEST MODELS
# =============================================================================


class TestUserDocumentUpload:
    """Test UserDocumentUpload request model validation."""

    def test_valid_upload_with_all_fields(self):
        doc = UserDocumentUpload(
            document_type_hint="passport",
            notes="Mon passeport GE",
        )
        assert doc.document_type_hint == "passport"
        assert doc.notes == "Mon passeport GE"

    def test_valid_upload_minimal(self):
        doc = UserDocumentUpload()
        assert doc.document_type_hint is None
        assert doc.notes is None

    def test_upload_only_hint(self):
        doc = UserDocumentUpload(document_type_hint="dip")
        assert doc.document_type_hint == "dip"
        assert doc.notes is None

    def test_upload_only_notes(self):
        doc = UserDocumentUpload(notes="Important document")
        assert doc.document_type_hint is None
        assert doc.notes == "Important document"

    def test_upload_hint_max_length_100(self):
        """document_type_hint must be <= 100 characters."""
        long_hint = "x" * 101
        with pytest.raises(ValidationError) as exc_info:
            UserDocumentUpload(document_type_hint=long_hint)
        assert "document_type_hint" in str(exc_info.value)

    def test_upload_hint_max_length_boundary(self):
        """Exactly 100 characters should be valid."""
        doc = UserDocumentUpload(document_type_hint="x" * 100)
        assert len(doc.document_type_hint) == 100

    def test_upload_notes_max_length_1000(self):
        """notes must be <= 1000 characters."""
        long_notes = "y" * 1001
        with pytest.raises(ValidationError) as exc_info:
            UserDocumentUpload(notes=long_notes)
        assert "notes" in str(exc_info.value)

    def test_upload_notes_max_length_boundary(self):
        """Exactly 1000 characters should be valid."""
        doc = UserDocumentUpload(notes="y" * 1000)
        assert len(doc.notes) == 1000


class TestUserDocumentUpdate:
    """Test UserDocumentUpdate partial update model."""

    def test_valid_full_update(self):
        update = UserDocumentUpdate(
            display_name="Mon DNI",
            notes="Important",
            color_label="blue",
            category="identity",
        )
        assert update.display_name == "Mon DNI"
        assert update.notes == "Important"
        assert update.color_label == "blue"
        assert update.category == "identity"

    def test_partial_update_only_notes(self):
        update = UserDocumentUpdate(notes="Just notes")
        assert update.display_name is None
        assert update.notes == "Just notes"
        assert update.color_label is None
        assert update.category is None

    def test_partial_update_only_color_label(self):
        update = UserDocumentUpdate(color_label="red")
        assert update.color_label == "red"

    def test_empty_update_all_none(self):
        update = UserDocumentUpdate()
        assert update.display_name is None
        assert update.notes is None
        assert update.color_label is None
        assert update.category is None

    def test_display_name_min_length_1(self):
        """display_name must be at least 1 character."""
        with pytest.raises(ValidationError) as exc_info:
            UserDocumentUpdate(display_name="")
        assert "display_name" in str(exc_info.value)

    def test_display_name_max_length_255(self):
        """display_name must be <= 255 characters."""
        with pytest.raises(ValidationError) as exc_info:
            UserDocumentUpdate(display_name="z" * 256)
        assert "display_name" in str(exc_info.value)

    def test_display_name_boundary_valid(self):
        update = UserDocumentUpdate(display_name="z" * 255)
        assert len(update.display_name) == 255

    def test_invalid_category_literal(self):
        """category must be one of the allowed DocumentCategory literals."""
        with pytest.raises(ValidationError):
            UserDocumentUpdate(category="weapons")

    def test_all_valid_categories(self):
        """Test all valid document categories are accepted."""
        valid_categories = [
            "identity", "vehicle", "legal", "financial", "administrative",
            "medical", "education", "photo", "business", "employment", "other",
        ]
        for cat in valid_categories:
            update = UserDocumentUpdate(category=cat)
            assert update.category == cat


class TestUserDocumentBulkAction:
    """Test UserDocumentBulkAction request model."""

    def test_valid_archive_action(self):
        ids = [uuid4(), uuid4()]
        action = UserDocumentBulkAction(action="archive", document_ids=ids)
        assert action.action == "archive"
        assert len(action.document_ids) == 2

    def test_valid_delete_action(self):
        action = UserDocumentBulkAction(action="delete", document_ids=[uuid4()])
        assert action.action == "delete"

    def test_valid_download_action(self):
        action = UserDocumentBulkAction(action="download", document_ids=[uuid4()])
        assert action.action == "download"

    def test_invalid_action_literal(self):
        """action must be 'archive', 'delete', or 'download'."""
        with pytest.raises(ValidationError):
            UserDocumentBulkAction(action="destroy", document_ids=[uuid4()])

    def test_empty_document_ids_rejected(self):
        """At least 1 document_id is required (min_length=1)."""
        with pytest.raises(ValidationError):
            UserDocumentBulkAction(action="archive", document_ids=[])

    def test_max_50_document_ids(self):
        """At most 50 document_ids allowed (max_length=50)."""
        ids = [uuid4() for _ in range(51)]
        with pytest.raises(ValidationError):
            UserDocumentBulkAction(action="archive", document_ids=ids)

    def test_max_50_boundary_valid(self):
        """Exactly 50 document_ids should be accepted."""
        ids = [uuid4() for _ in range(50)]
        action = UserDocumentBulkAction(action="archive", document_ids=ids)
        assert len(action.document_ids) == 50

    def test_document_ids_are_uuid_type(self):
        """document_ids must be valid UUIDs."""
        with pytest.raises(ValidationError):
            UserDocumentBulkAction(action="archive", document_ids=["not-a-uuid"])

    def test_document_ids_accept_uuid_strings(self):
        """UUID strings should be coerced to UUID objects."""
        uid = uuid4()
        action = UserDocumentBulkAction(
            action="archive",
            document_ids=[str(uid)],
        )
        assert action.document_ids[0] == uid


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class TestUploadResult:
    """Test UploadResult response model."""

    def test_basic_processing_result(self):
        uid = uuid4()
        result = UploadResult(
            id=uid,
            status="processing",
            file_name="doc.pdf",
            file_size_bytes=1024,
        )
        assert result.id == uid
        assert result.status == "processing"
        assert result.file_name == "doc.pdf"
        assert result.file_size_bytes == 1024
        assert result.duplicate is None

    def test_result_with_duplicate_info(self):
        uid = uuid4()
        existing_id = uuid4()
        result = UploadResult(
            id=uid,
            status="processing",
            file_name="doc.pdf",
            file_size_bytes=2048,
            duplicate=DuplicateInfo(existing_document_id=existing_id),
        )
        assert result.duplicate is not None
        assert result.duplicate.existing_document_id == existing_id

    def test_file_size_must_be_non_negative(self):
        """file_size_bytes has ge=0 constraint."""
        with pytest.raises(ValidationError):
            UploadResult(
                id=uuid4(),
                status="processing",
                file_name="doc.pdf",
                file_size_bytes=-1,
            )

    def test_status_must_be_processing(self):
        """Status is Literal['processing'] -- no other value allowed."""
        with pytest.raises(ValidationError):
            UploadResult(
                id=uuid4(),
                status="completed",
                file_name="doc.pdf",
                file_size_bytes=0,
            )


class TestDuplicateInfo:
    """Test DuplicateInfo nested model."""

    def test_valid_duplicate_info(self):
        uid = uuid4()
        dup = DuplicateInfo(existing_document_id=uid)
        assert dup.existing_document_id == uid

    def test_invalid_uuid_rejected(self):
        with pytest.raises(ValidationError):
            DuplicateInfo(existing_document_id="not-a-uuid")


class TestUserDocumentResponse:
    """Test the full document detail response model."""

    @pytest.fixture
    def valid_response_data(self):
        """Minimal valid data for UserDocumentResponse."""
        return {
            "id": uuid4(),
            "user_id": uuid4(),
            "document_type": "pasaporte",
            "category": "identity",
            "source": "personal",
            "status": "active",
            "file_name": "passport.pdf",
            "file_path": "user_documents/abc/passport.pdf",
            "file_size_bytes": 524288,
            "mime_type": "application/pdf",
            "file_hash": "abcdef1234567890" * 4,
            "created_at": datetime.utcnow(),
        }

    def test_valid_minimal_response(self, valid_response_data):
        resp = UserDocumentResponse(**valid_response_data)
        assert resp.document_type == "pasaporte"
        assert resp.status == "active"
        assert resp.workflow_tags == []
        assert resp.expiry_status == "no_expiry"
        assert resp.days_until_expiry is None

    def test_all_optional_fields(self, valid_response_data):
        valid_response_data.update({
            "display_name": "Mi pasaporte",
            "thumbnail_path": "/thumbs/abc.jpg",
            "classification_method": "gemini",
            "classification_confidence": 0.95,
            "extraction_status": "completed",
            "extracted_data": {"nombre": "Juan"},
            "expiry_date": date(2027, 12, 31),
            "issue_date": date(2022, 1, 15),
            "notes": "Important",
            "color_label": "blue",
            "is_verified": True,
            "source_request_id": uuid4(),
            "days_until_expiry": 365,
            "expiry_status": "valid",
            "workflow_tags": ["pasaporte_nuevo", "pasaporte_renovacion"],
            "updated_at": datetime.utcnow(),
        })
        resp = UserDocumentResponse(**valid_response_data)
        assert resp.display_name == "Mi pasaporte"
        assert resp.classification_confidence == 0.95
        assert resp.is_verified is True
        assert len(resp.workflow_tags) == 2

    def test_classification_confidence_range(self, valid_response_data):
        """classification_confidence must be between 0.0 and 1.0."""
        valid_response_data["classification_confidence"] = 1.5
        with pytest.raises(ValidationError):
            UserDocumentResponse(**valid_response_data)

    def test_classification_confidence_lower_bound(self, valid_response_data):
        valid_response_data["classification_confidence"] = -0.1
        with pytest.raises(ValidationError):
            UserDocumentResponse(**valid_response_data)

    def test_invalid_source_literal(self, valid_response_data):
        valid_response_data["source"] = "external_api"
        with pytest.raises(ValidationError):
            UserDocumentResponse(**valid_response_data)

    def test_valid_source_values(self, valid_response_data):
        for source in ("personal", "wizard_import", "platform_generated"):
            valid_response_data["source"] = source
            resp = UserDocumentResponse(**valid_response_data)
            assert resp.source == source

    def test_valid_status_values(self, valid_response_data):
        for status in ("active", "archived", "expired", "deleted"):
            valid_response_data["status"] = status
            resp = UserDocumentResponse(**valid_response_data)
            assert resp.status == status

    def test_invalid_status_literal(self, valid_response_data):
        valid_response_data["status"] = "suspended"
        with pytest.raises(ValidationError):
            UserDocumentResponse(**valid_response_data)

    def test_valid_extraction_status_values(self, valid_response_data):
        for es in ("pending", "processing", "completed", "failed"):
            valid_response_data["extraction_status"] = es
            resp = UserDocumentResponse(**valid_response_data)
            assert resp.extraction_status == es

    def test_valid_expiry_status_values(self, valid_response_data):
        for es in ("valid", "expiring_soon", "expired", "no_expiry"):
            valid_response_data["expiry_status"] = es
            resp = UserDocumentResponse(**valid_response_data)
            assert resp.expiry_status == es


class TestUserDocumentListItem:
    """Test the lightweight list item model."""

    def test_minimal_list_item(self):
        item = UserDocumentListItem(
            id=uuid4(),
            document_type="dip",
            category="identity",
            file_name="dip_scan.jpg",
            created_at=datetime.utcnow(),
        )
        assert item.document_type == "dip"
        assert item.display_name is None
        assert item.expiry_date is None
        assert item.status == "active"
        assert item.source == "personal"
        assert item.is_verified is False
        assert item.workflow_tags == []
        assert item.file_size_bytes == 0

    def test_list_item_with_all_fields(self):
        item = UserDocumentListItem(
            id=uuid4(),
            document_type="pasaporte",
            category="identity",
            file_name="passport.pdf",
            display_name="Mi pasaporte",
            expiry_date=date(2027, 6, 15),
            days_until_expiry=450,
            expiry_status="valid",
            status="active",
            source="wizard_import",
            is_verified=True,
            workflow_tags=["pasaporte_nuevo"],
            thumbnail_path="/thumbs/abc.jpg",
            file_size_bytes=524288,
            created_at=datetime.utcnow(),
        )
        assert item.display_name == "Mi pasaporte"
        assert item.expiry_status == "valid"
        assert item.source == "wizard_import"


class TestUserDocumentListResponse:
    """Test the paginated list response model."""

    def test_empty_list_response(self):
        resp = UserDocumentListResponse(
            items=[],
            next_cursor=None,
            total_count=0,
            quota_used_bytes=0,
        )
        assert resp.items == []
        assert resp.total_count == 0
        assert resp.quota_max_bytes == VAULT_QUOTA_BYTES

    def test_list_response_with_cursor(self):
        item = UserDocumentListItem(
            id=uuid4(),
            document_type="dip",
            category="identity",
            file_name="dip.pdf",
            created_at=datetime.utcnow(),
        )
        resp = UserDocumentListResponse(
            items=[item],
            next_cursor="eyJpZCI6ICIuLi4ifQ==",
            total_count=42,
            quota_used_bytes=15_728_640,
        )
        assert len(resp.items) == 1
        assert resp.next_cursor is not None
        assert resp.total_count == 42

    def test_negative_total_count_rejected(self):
        with pytest.raises(ValidationError):
            UserDocumentListResponse(
                items=[], next_cursor=None, total_count=-1, quota_used_bytes=0,
            )

    def test_negative_quota_used_rejected(self):
        with pytest.raises(ValidationError):
            UserDocumentListResponse(
                items=[], next_cursor=None, total_count=0, quota_used_bytes=-1,
            )


class TestUserDocumentStats:
    """Test the aggregate stats model."""

    def test_valid_stats(self):
        stats = UserDocumentStats(
            total_active=10,
            personal_count=5,
            wizard_count=3,
            generated_count=2,
            quota_used_bytes=5_000_000,
            quota_max_bytes=VAULT_QUOTA_BYTES,
            quota_percentage=4.8,
            expired_count=1,
            expiring_count=2,
        )
        assert stats.total_active == 10
        assert stats.quota_percentage == 4.8
        assert stats.quota_max_bytes == VAULT_QUOTA_BYTES

    def test_default_values(self):
        stats = UserDocumentStats()
        assert stats.total_active == 0
        assert stats.personal_count == 0
        assert stats.wizard_count == 0
        assert stats.generated_count == 0
        assert stats.quota_used_bytes == 0
        assert stats.quota_max_bytes == VAULT_QUOTA_BYTES
        assert stats.quota_percentage == 0.0
        assert stats.expired_count == 0
        assert stats.expiring_count == 0

    def test_negative_count_rejected(self):
        with pytest.raises(ValidationError):
            UserDocumentStats(total_active=-1)

    def test_quota_percentage_upper_bound(self):
        """quota_percentage has le=100.0 constraint."""
        with pytest.raises(ValidationError):
            UserDocumentStats(quota_percentage=100.1)

    def test_quota_percentage_100_valid(self):
        stats = UserDocumentStats(quota_percentage=100.0)
        assert stats.quota_percentage == 100.0

    def test_quota_percentage_negative_rejected(self):
        with pytest.raises(ValidationError):
            UserDocumentStats(quota_percentage=-0.1)


# =============================================================================
# READINESS MODELS
# =============================================================================


class TestReadinessItem:
    """Test individual readiness item."""

    def test_ready_item(self):
        item = ReadinessItem(
            code="national_id",
            name="DIP",
            status="ready",
            days_until_expiry=365,
        )
        assert item.code == "national_id"
        assert item.status == "ready"
        assert item.days_until_expiry == 365

    def test_missing_item(self):
        item = ReadinessItem(
            code="birth_certificate",
            name="Acta de nacimiento",
            status="missing",
        )
        assert item.status == "missing"
        assert item.days_until_expiry is None

    def test_expiring_item(self):
        item = ReadinessItem(
            code="photo",
            name="Photo d'identite",
            status="expiring",
            days_until_expiry=15,
        )
        assert item.status == "expiring"
        assert item.days_until_expiry == 15

    def test_invalid_status_literal(self):
        with pytest.raises(ValidationError):
            ReadinessItem(code="x", name="X", status="unknown")


class TestReadinessResult:
    """Test workflow readiness result."""

    def test_can_start_all_ready(self):
        result = ReadinessResult(
            workflow_code="pasaporte_nuevo",
            readiness_score=100.0,
            total_required=3,
            available=3,
            missing_count=0,
            ready=[
                ReadinessItem(code="dip", name="DIP", status="ready", days_until_expiry=365),
                ReadinessItem(code="photo", name="Photo", status="ready"),
                ReadinessItem(code="birth_cert", name="Acta nacimiento", status="ready"),
            ],
            missing=[],
            expiring=[],
            can_start=True,
        )
        assert result.can_start is True
        assert result.readiness_score == 100.0
        assert len(result.ready) == 3
        assert len(result.missing) == 0

    def test_cannot_start_missing_docs(self):
        result = ReadinessResult(
            workflow_code="pasaporte_nuevo",
            readiness_score=33.3,
            total_required=3,
            available=1,
            missing_count=2,
            ready=[
                ReadinessItem(code="dip", name="DIP", status="ready"),
            ],
            missing=[
                ReadinessItem(code="photo", name="Photo", status="missing"),
                ReadinessItem(code="birth_cert", name="Acta nacimiento", status="missing"),
            ],
            expiring=[],
            can_start=False,
        )
        assert result.can_start is False
        assert result.missing_count == 2
        assert len(result.missing) == 2

    def test_readiness_with_expiring_docs(self):
        result = ReadinessResult(
            workflow_code="conducir_renovacion",
            readiness_score=100.0,
            total_required=2,
            available=2,
            missing_count=0,
            ready=[ReadinessItem(code="dip", name="DIP", status="ready")],
            missing=[],
            expiring=[
                ReadinessItem(code="licencia", name="Licencia de conducir", status="expiring", days_until_expiry=10),
            ],
            can_start=True,
        )
        assert result.can_start is True
        assert len(result.expiring) == 1

    def test_readiness_score_must_be_0_100(self):
        with pytest.raises(ValidationError):
            ReadinessResult(
                workflow_code="test",
                readiness_score=150.0,
                total_required=1,
                available=0,
                missing_count=0,
                can_start=False,
            )

    def test_readiness_score_negative_rejected(self):
        with pytest.raises(ValidationError):
            ReadinessResult(
                workflow_code="test",
                readiness_score=-10.0,
                total_required=1,
                available=0,
                missing_count=0,
                can_start=False,
            )


# =============================================================================
# GENERATED DOCUMENT & ALERT MODELS
# =============================================================================


class TestGeneratedDocumentResponse:
    """Test platform-generated document response."""

    def test_valid_receipt(self):
        resp = GeneratedDocumentResponse(
            id=uuid4(),
            generation_type="receipt",
            title="Recibo de pago",
            file_name="recibo_12345.pdf",
            created_at=datetime.utcnow(),
        )
        assert resp.generation_type == "receipt"
        assert resp.reference_number is None
        assert resp.verification_code is None

    def test_with_reference_and_verification(self):
        resp = GeneratedDocumentResponse(
            id=uuid4(),
            generation_type="certificate",
            title="Certificado de residencia",
            file_name="cert_res_2025.pdf",
            created_at=datetime.utcnow(),
            reference_number="REF-2025-001",
            service_request_id=uuid4(),
            verification_code="QR-ABC123",
        )
        assert resp.reference_number == "REF-2025-001"
        assert resp.verification_code == "QR-ABC123"

    def test_all_generation_types(self):
        for gtype in ("receipt", "certificate", "attestation", "summary", "confirmation"):
            resp = GeneratedDocumentResponse(
                id=uuid4(),
                generation_type=gtype,
                title="Test",
                file_name="test.pdf",
                created_at=datetime.utcnow(),
            )
            assert resp.generation_type == gtype

    def test_invalid_generation_type(self):
        with pytest.raises(ValidationError):
            GeneratedDocumentResponse(
                id=uuid4(),
                generation_type="invoice",
                title="Test",
                file_name="test.pdf",
                created_at=datetime.utcnow(),
            )


class TestAlertResponse:
    """Test document alert response model."""

    def test_expiry_warning_alert(self):
        alert = AlertResponse(
            id=uuid4(),
            alert_type="expiry_warning",
            severity="warning",
            title="Pasaporte expire bientot",
            message="Votre passeport expire dans 25 jours",
            is_read=False,
            is_dismissed=False,
            trigger_date=date(2026, 5, 1),
            created_at=datetime.utcnow(),
        )
        assert alert.alert_type == "expiry_warning"
        assert alert.severity == "warning"
        assert alert.is_read is False

    def test_alert_with_action(self):
        alert = AlertResponse(
            id=uuid4(),
            alert_type="renewal_suggestion",
            severity="info",
            title="Suggestion de renouvellement",
            message="Renouveler votre DIP",
            suggested_action="Renew now",
            action_params={"workflow_code": "verificacion_funcionario", "document_id": str(uuid4())},
            created_at=datetime.utcnow(),
        )
        assert alert.suggested_action == "Renew now"
        assert "workflow_code" in alert.action_params

    def test_all_alert_types(self):
        alert_types = [
            "expiry_warning", "expiry_critical", "expired",
            "renewal_suggestion", "duplicate_detected", "missing_for_workflow",
        ]
        for atype in alert_types:
            alert = AlertResponse(
                id=uuid4(),
                alert_type=atype,
                severity="info",
                title="Test",
                message="Test message",
                created_at=datetime.utcnow(),
            )
            assert alert.alert_type == atype

    def test_all_severity_levels(self):
        for sev in ("info", "warning", "critical"):
            alert = AlertResponse(
                id=uuid4(),
                alert_type="expired",
                severity=sev,
                title="Test",
                message="Test",
                created_at=datetime.utcnow(),
            )
            assert alert.severity == sev

    def test_invalid_alert_type(self):
        with pytest.raises(ValidationError):
            AlertResponse(
                id=uuid4(),
                alert_type="system_error",
                severity="info",
                title="Test",
                message="Test",
                created_at=datetime.utcnow(),
            )

    def test_invalid_severity(self):
        with pytest.raises(ValidationError):
            AlertResponse(
                id=uuid4(),
                alert_type="expired",
                severity="fatal",
                title="Test",
                message="Test",
                created_at=datetime.utcnow(),
            )
