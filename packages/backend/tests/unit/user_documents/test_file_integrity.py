"""
Tests for file integrity validation (OWASP A08).

Validates the magic bytes detection, dangerous extension blacklist,
MIME type matching, and edge cases in validate_file_integrity().
"""
import pytest

from app.modules.user_documents.services.user_documents_service import (
    validate_file_integrity,
    DANGEROUS_EXTENSIONS,
    ALLOWED_MIME_TYPES_SET,
)


# =============================================================================
# DANGEROUS EXTENSIONS BLACKLIST
# =============================================================================


class TestDangerousExtensions:
    """Verify the dangerous extensions blacklist is comprehensive."""

    def test_exe_blocked(self):
        assert ".exe" in DANGEROUS_EXTENSIONS

    def test_bat_blocked(self):
        assert ".bat" in DANGEROUS_EXTENSIONS

    def test_dll_blocked(self):
        assert ".dll" in DANGEROUS_EXTENSIONS

    def test_cmd_blocked(self):
        assert ".cmd" in DANGEROUS_EXTENSIONS

    def test_ps1_blocked(self):
        assert ".ps1" in DANGEROUS_EXTENSIONS

    def test_vbs_blocked(self):
        assert ".vbs" in DANGEROUS_EXTENSIONS

    def test_js_blocked(self):
        assert ".js" in DANGEROUS_EXTENSIONS

    def test_msi_blocked(self):
        assert ".msi" in DANGEROUS_EXTENSIONS

    def test_sh_blocked(self):
        assert ".sh" in DANGEROUS_EXTENSIONS

    def test_scr_blocked(self):
        assert ".scr" in DANGEROUS_EXTENSIONS

    def test_pdf_not_blocked(self):
        assert ".pdf" not in DANGEROUS_EXTENSIONS

    def test_jpg_not_blocked(self):
        assert ".jpg" not in DANGEROUS_EXTENSIONS

    def test_png_not_blocked(self):
        assert ".png" not in DANGEROUS_EXTENSIONS


# =============================================================================
# VALID FILES — Magic Bytes
# =============================================================================


class TestValidMagicBytes:
    """Test that valid files with correct magic bytes pass validation."""

    def test_valid_pdf(self):
        content = b"%PDF-1.4 this is a valid pdf content..."
        is_valid, error = validate_file_integrity(content, "report.pdf", "application/pdf")
        assert is_valid is True
        assert error == ""

    def test_valid_pdf_version_1_7(self):
        content = b"%PDF-1.7 another valid pdf version..."
        is_valid, error = validate_file_integrity(content, "doc.pdf", "application/pdf")
        assert is_valid is True

    def test_valid_jpeg(self):
        content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        is_valid, error = validate_file_integrity(content, "photo.jpg", "image/jpeg")
        assert is_valid is True
        assert error == ""

    def test_valid_jpeg_exif(self):
        """JPEG with EXIF marker (0xFFE1)."""
        content = b"\xff\xd8\xff\xe1" + b"\x00" * 100
        is_valid, error = validate_file_integrity(content, "camera.jpg", "image/jpeg")
        assert is_valid is True

    def test_valid_png(self):
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        is_valid, error = validate_file_integrity(content, "image.png", "image/png")
        assert is_valid is True
        assert error == ""

    def test_valid_webp(self):
        content = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
        is_valid, error = validate_file_integrity(content, "photo.webp", "image/webp")
        assert is_valid is True
        assert error == ""

    def test_valid_webp_with_size_bytes(self):
        """WEBP with actual size bytes in RIFF header."""
        content = b"RIFF\x10\x00\x01\x00WEBP" + b"\x00" * 100
        is_valid, error = validate_file_integrity(content, "compressed.webp", "image/webp")
        assert is_valid is True

    def test_jpeg_with_jpg_extension_and_image_jpg_mime(self):
        """image/jpg (non-standard) should be treated as image/jpeg."""
        content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        is_valid, error = validate_file_integrity(content, "photo.jpg", "image/jpg")
        assert is_valid is True


# =============================================================================
# DANGEROUS EXTENSION REJECTION
# =============================================================================


class TestDangerousExtensionRejection:
    """Test that dangerous file extensions are rejected regardless of content."""

    def test_exe_with_pdf_content(self):
        content = b"%PDF-1.4 valid pdf content"
        is_valid, error = validate_file_integrity(content, "report.exe", "application/pdf")
        assert is_valid is False
        assert "extension" in error.lower()

    def test_bat_rejected(self):
        is_valid, error = validate_file_integrity(
            b"@echo off\ntest", "run.bat", "text/plain"
        )
        assert is_valid is False

    def test_dll_rejected(self):
        is_valid, error = validate_file_integrity(
            b"MZ\x90\x00" + b"\x00" * 100, "lib.dll", "application/octet-stream"
        )
        assert is_valid is False

    def test_cmd_rejected(self):
        is_valid, error = validate_file_integrity(
            b"dir /s", "cleanup.cmd", "text/plain"
        )
        assert is_valid is False

    def test_ps1_rejected(self):
        is_valid, error = validate_file_integrity(
            b"Write-Host hello", "script.ps1", "text/plain"
        )
        assert is_valid is False

    def test_vbs_rejected(self):
        is_valid, error = validate_file_integrity(
            b"MsgBox hello", "macro.vbs", "text/plain"
        )
        assert is_valid is False

    def test_msi_rejected(self):
        is_valid, error = validate_file_integrity(
            b"\xd0\xcf\x11\xe0" + b"\x00" * 100, "installer.msi", "application/octet-stream"
        )
        assert is_valid is False

    def test_sh_rejected(self):
        is_valid, error = validate_file_integrity(
            b"#!/bin/bash\necho test", "install.sh", "text/plain"
        )
        assert is_valid is False

    def test_inf_rejected(self):
        is_valid, error = validate_file_integrity(
            b"[Version]\nSignature", "autorun.inf", "text/plain"
        )
        assert is_valid is False

    def test_reg_rejected(self):
        is_valid, error = validate_file_integrity(
            b"Windows Registry Editor", "hack.reg", "text/plain"
        )
        assert is_valid is False

    def test_extension_case_insensitive(self):
        """Extension check should be case insensitive (.EXE == .exe)."""
        content = b"%PDF-1.4 valid pdf content"
        is_valid, error = validate_file_integrity(content, "report.EXE", "application/pdf")
        assert is_valid is False


# =============================================================================
# MIME TYPE MISMATCH — Content-Type Spoofing
# =============================================================================


class TestMimeMismatch:
    """Test detection of Content-Type spoofing via magic bytes mismatch."""

    def test_jpeg_content_declared_as_pdf(self):
        """JPEG magic bytes but declared as PDF should fail."""
        content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        is_valid, error = validate_file_integrity(content, "doc.pdf", "application/pdf")
        assert is_valid is False
        assert "does not match" in error.lower()

    def test_png_content_declared_as_jpeg(self):
        """PNG magic bytes but declared as JPEG should fail."""
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        is_valid, error = validate_file_integrity(content, "photo.jpg", "image/jpeg")
        assert is_valid is False
        assert "does not match" in error.lower()

    def test_pdf_content_declared_as_jpeg(self):
        """PDF magic bytes but declared as JPEG should fail."""
        content = b"%PDF-1.4 content here" + b"\x00" * 100
        is_valid, error = validate_file_integrity(content, "photo.jpg", "image/jpeg")
        assert is_valid is False

    def test_pdf_content_declared_as_png(self):
        """PDF magic bytes but declared as PNG should fail."""
        content = b"%PDF-1.4 content here" + b"\x00" * 100
        is_valid, error = validate_file_integrity(content, "image.png", "image/png")
        assert is_valid is False

    def test_webp_content_declared_as_pdf(self):
        """WEBP magic bytes but declared as PDF should fail."""
        content = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
        is_valid, error = validate_file_integrity(content, "doc.pdf", "application/pdf")
        assert is_valid is False

    def test_jpeg_content_declared_as_webp(self):
        """JPEG magic bytes but declared as WEBP should fail."""
        content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        is_valid, error = validate_file_integrity(content, "photo.webp", "image/webp")
        assert is_valid is False


# =============================================================================
# EMPTY / TOO SMALL FILES
# =============================================================================


class TestFileSize:
    """Test minimum file size validation (need >= 4 bytes for magic detection)."""

    def test_empty_file(self):
        is_valid, error = validate_file_integrity(b"", "empty.pdf", "application/pdf")
        assert is_valid is False
        assert "too small" in error.lower()

    def test_1_byte_file(self):
        is_valid, error = validate_file_integrity(b"x", "tiny.pdf", "application/pdf")
        assert is_valid is False
        assert "too small" in error.lower()

    def test_2_byte_file(self):
        is_valid, error = validate_file_integrity(b"ab", "tiny.pdf", "application/pdf")
        assert is_valid is False
        assert "too small" in error.lower()

    def test_3_byte_file(self):
        is_valid, error = validate_file_integrity(b"abc", "tiny.pdf", "application/pdf")
        assert is_valid is False
        assert "too small" in error.lower()

    def test_4_byte_boundary_valid_pdf(self):
        """4 bytes is the minimum; if it's a valid PDF header, it should pass."""
        is_valid, error = validate_file_integrity(b"%PDF", "min.pdf", "application/pdf")
        assert is_valid is True


# =============================================================================
# DISALLOWED MIME TYPES
# =============================================================================


class TestDisallowedMimeTypes:
    """Test that non-allowed MIME types are rejected."""

    def test_unknown_mime_type(self):
        content = b"some random content bytes here"
        is_valid, error = validate_file_integrity(content, "doc.xyz", "application/xyz")
        assert is_valid is False
        assert "not allowed" in error.lower()

    def test_octet_stream_rejected(self):
        content = b"binary data here more content"
        is_valid, error = validate_file_integrity(
            content, "file.bin", "application/octet-stream"
        )
        assert is_valid is False
        assert "not allowed" in error.lower()

    def test_text_plain_rejected(self):
        content = b"Just plain text content"
        is_valid, error = validate_file_integrity(content, "notes.txt", "text/plain")
        assert is_valid is False
        assert "not allowed" in error.lower()

    def test_html_rejected(self):
        content = b"<html><body>test</body></html>"
        is_valid, error = validate_file_integrity(content, "page.html", "text/html")
        assert is_valid is False

    def test_zip_rejected(self):
        content = b"PK\x03\x04" + b"\x00" * 100
        is_valid, error = validate_file_integrity(content, "archive.zip", "application/zip")
        assert is_valid is False


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_unrecognized_magic_bytes_allowed_mime(self):
        """File with unknown magic bytes but allowed MIME should pass
        (no magic byte match to contradict the declaration)."""
        content = b"\x00\x00\x00\x00" + b"random data" * 10
        is_valid, error = validate_file_integrity(content, "doc.pdf", "application/pdf")
        # No known magic byte pattern detected, so no mismatch.
        # Declared MIME is in the allowed list, so it passes.
        assert is_valid is True

    def test_exe_magic_bytes_as_pdf(self):
        """EXE header (MZ) with .pdf extension and PDF MIME.
        MZ is NOT one of the recognized magic byte patterns,
        so no mismatch is detected. The extension .pdf is not dangerous."""
        content = b"MZ\x90\x00" + b"\x00" * 100
        is_valid, error = validate_file_integrity(content, "malware.pdf", "application/pdf")
        # No magic byte match for MZ => passes (extension ok, MIME ok)
        assert is_valid is True

    def test_double_extension_last_checked(self):
        """Double extensions: Python pathlib.Path.suffix returns last ext."""
        content = b"%PDF-1.4 valid content here"
        # .pdf.exe -> suffix is .exe
        is_valid, error = validate_file_integrity(content, "report.pdf.exe", "application/pdf")
        assert is_valid is False

    def test_no_extension(self):
        """File without extension should pass if MIME is allowed and content ok."""
        content = b"%PDF-1.4 valid pdf content here"
        is_valid, error = validate_file_integrity(content, "document", "application/pdf")
        assert is_valid is True

    def test_hidden_file_unix_style(self):
        """Unix hidden file (.report) should pass if content and MIME are valid."""
        content = b"%PDF-1.4 valid pdf content here"
        is_valid, error = validate_file_integrity(content, ".report.pdf", "application/pdf")
        assert is_valid is True

    def test_unicode_filename(self):
        """Unicode characters in filename should not break validation."""
        content = b"%PDF-1.4 valid content here..."
        is_valid, error = validate_file_integrity(
            content, "documento_espanol.pdf", "application/pdf"
        )
        assert is_valid is True

    def test_very_long_filename(self):
        """Very long filename should still work (extension check at the end)."""
        content = b"%PDF-1.4 valid content..."
        long_name = "a" * 250 + ".pdf"
        is_valid, error = validate_file_integrity(content, long_name, "application/pdf")
        assert is_valid is True

    def test_mime_case_normalization(self):
        """MIME type comparison should be case insensitive after normalization."""
        content = b"%PDF-1.4 valid pdf content"
        is_valid, error = validate_file_integrity(content, "doc.pdf", "Application/PDF")
        # The code does declared_mime.lower(), so this should normalize correctly
        assert is_valid is True

    def test_allowed_mime_types_set_matches_list(self):
        """ALLOWED_MIME_TYPES_SET should contain exactly the same entries as the list."""
        from app.modules.user_documents.models.user_document import ALLOWED_MIME_TYPES
        assert ALLOWED_MIME_TYPES_SET == set(ALLOWED_MIME_TYPES)
