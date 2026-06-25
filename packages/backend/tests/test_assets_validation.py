"""Pure unit tests for the asset security core (no DB / no MinIO).

These pin the magic-bytes detection and the reject rules — the security-critical
part of the upload pipeline (CWE: unrestricted upload / stored XSS via SVG)."""

import pytest

from app.api.assets import (
    AssetValidationError,
    MAX_ASSET_BYTES,
    sniff_image,
    validate_asset,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
GIF = b"GIF89a" + b"\x00" * 32
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 16
ICO = b"\x00\x00\x01\x00" + b"\x00" * 32
SVG = b"<?xml version='1.0'?><svg onload='alert(1)'></svg>"
PDF = b"%PDF-1.7\n" + b"\x00" * 32


@pytest.mark.parametrize(
    "data,expected",
    [
        (PNG, ("image/png", "png")),
        (JPEG, ("image/jpeg", "jpg")),
        (GIF, ("image/gif", "gif")),
        (WEBP, ("image/webp", "webp")),
        (ICO, ("image/x-icon", "ico")),
    ],
)
def test_sniff_accepts_allowed_formats(data, expected):
    assert sniff_image(data) == expected
    assert validate_asset(data) == expected


@pytest.mark.parametrize("data", [SVG, PDF, b"plain text", b"<html></html>"])
def test_sniff_rejects_non_allowed(data):
    assert sniff_image(data) is None


def test_svg_is_rejected_xss_vector():
    # Explicit: SVG must never pass — it can carry script (stored XSS).
    with pytest.raises(AssetValidationError):
        validate_asset(SVG)


def test_rejects_empty():
    with pytest.raises(AssetValidationError):
        validate_asset(b"")


def test_rejects_oversize():
    big = PNG + b"\x00" * MAX_ASSET_BYTES
    with pytest.raises(AssetValidationError):
        validate_asset(big)


def test_size_cap_is_overridable():
    with pytest.raises(AssetValidationError):
        validate_asset(PNG, max_bytes=4)  # PNG sample is 40 bytes


def test_extension_and_declared_type_are_not_trusted():
    # A PDF renamed/declared as PNG is still rejected — we sniff bytes, not names.
    with pytest.raises(AssetValidationError):
        validate_asset(PDF)
