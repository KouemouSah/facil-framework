"""Secure asset (image) validation + serving — Phase 3a.

The security core is `validate_asset` / `sniff_image`: a pure, dependency-free
magic-bytes check that NEVER trusts the client-declared content-type or the file
extension. SVG is deliberately rejected (it can carry script => stored XSS). This
module is split so the validation is unit-tested without MinIO or a DB; the upload
router (added with the chosen binary transport channel) composes these helpers
with the storage provider, RBAC permission, and audit.
"""

from __future__ import annotations

# Canonical (content_type, extension) per image format we accept. Detection is by
# leading magic bytes only — never the filename or the client Content-Type.
_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG = b"\xff\xd8\xff"
_GIF87, _GIF89 = b"GIF87a", b"GIF89a"
_ICO = b"\x00\x00\x01\x00"

#: Hard cap on accepted asset size (bytes). Override via config-store/env at the
#: router; the default keeps a logo/favicon reasonable and bounds memory/DoS.
MAX_ASSET_BYTES = 5 * 1024 * 1024  # 5 MiB

#: Extensions we allow. SVG is intentionally absent (XSS vector).
ALLOWED_EXTENSIONS = ("png", "jpg", "gif", "webp", "ico")


def sniff_image(data: bytes) -> tuple[str, str] | None:
    """Return (content_type, extension) inferred from magic bytes, or None when the
    payload is not one of our allowed raster formats. SVG/HTML/scripts => None."""
    if data[:8] == _PNG:
        return "image/png", "png"
    if data[:3] == _JPEG:
        return "image/jpeg", "jpg"
    if data[:6] in (_GIF87, _GIF89):
        return "image/gif", "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    if data[:4] == _ICO:
        return "image/x-icon", "ico"
    return None


class AssetValidationError(ValueError):
    """Raised when an uploaded asset is empty, too large, or not an allowed image.
    The router maps this to a 422 with a safe, generic message (no echo of bytes)."""


def validate_asset(data: bytes, *, max_bytes: int = MAX_ASSET_BYTES) -> tuple[str, str]:
    """Validate raw bytes as an allowed image. Returns (content_type, extension).

    Order matters: size cap first (cheap, bounds work), then non-empty, then the
    magic-bytes sniff. Raises AssetValidationError on any failure."""
    if len(data) > max_bytes:
        raise AssetValidationError("file too large")
    if not data:
        raise AssetValidationError("empty file")
    sniffed = sniff_image(data)
    if sniffed is None:
        raise AssetValidationError("unsupported or unsafe image type")
    return sniffed
