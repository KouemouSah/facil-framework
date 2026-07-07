"""Secure asset (image) validation + serving — Phase 3a.

The security core is `validate_asset` / `sniff_image`: a pure, dependency-free
magic-bytes check that NEVER trusts the client-declared content-type or the file
extension. SVG is deliberately rejected (it can carry script => stored XSS). This
module is split so the validation is unit-tested without MinIO or a DB; the upload
router below composes these helpers with the default storage provider, the
`branding.manage` RBAC permission, and the audit log.

Serving is public but structurally prefix-locked: keys are always built as
``assets/public/<uuid>.<ext>`` and the GET route matches a strict name regex
*before* any storage lookup, so it can never address a future private/scoped key
(anti-traversal by construction). The content-type served is re-derived from the
stored bytes (never the extension), consistent with the upload-time sniff.
"""

from __future__ import annotations

import re
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.auth import audit
from app.security.auth_dep import require_auth
from app.security.permission_dep import require_permission

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


# --- Router -----------------------------------------------------------------

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])

_MANAGE = Depends(require_permission("branding.manage"))

#: Public prefix every served asset lives under (the GET route can reach nothing
#: else). Private/scoped documents are a deliberately separate future subsystem.
_PUBLIC_PREFIX = "assets/public/"

#: A served name is exactly a uuid4 hex (32 lowercase hex) + an allowed extension.
#: Anything else (traversal, wrong ext, non-hex) never reaches storage → 404.
_NAME_RE = re.compile(r"^[0-9a-f]{32}\.(" + "|".join(ALLOWED_EXTENSIONS) + r")$")


@router.post("", status_code=201, dependencies=[_MANAGE])
async def upload_asset(request: Request,
                       file: UploadFile = File(...),
                       principal: dict = Depends(require_auth),
                       session: AsyncSession = Depends(get_session)) -> dict:
    """Upload a public image asset. Validated by magic bytes (client-declared type
    and filename are ignored), stored under the public prefix, and audited."""
    # Bound the read at the cap + 1: validate_asset rejects anything over the cap,
    # so we never buffer an unbounded payload (DoS guard).
    data = await file.read(MAX_ASSET_BYTES + 1)
    try:
        content_type, ext = validate_asset(data)
    except AssetValidationError as exc:
        raise HTTPException(422, str(exc))

    name = f"{uuid4().hex}.{ext}"
    key = f"{_PUBLIC_PREFIX}{name}"
    storage = await request.app.state.registry.get_default("storage", session)
    await storage.put(key, data, content_type=content_type)

    await audit.record(session, audit.ASSET_UPLOADED,
                       account_id=principal.get("sub"),
                       detail={"key": key, "content_type": content_type,
                               "bytes": len(data)})
    await session.commit()
    return {"asset_id": name, "url": f"/api/v1/assets/{name}"}


@router.get("/{name}")
async def serve_asset(name: str, request: Request,
                      session: AsyncSession = Depends(get_session)) -> Response:
    """Serve a public asset by name. The strict name regex is checked first, so a
    malformed/traversal name is a 404 before any storage access. The content-type
    is re-sniffed from the stored bytes (never trusted from the extension)."""
    if not _NAME_RE.match(name):
        raise HTTPException(404, "asset not found")
    storage = await request.app.state.registry.get_default("storage", session)
    try:
        data = await storage.get(f"{_PUBLIC_PREFIX}{name}")
    except FileNotFoundError:
        raise HTTPException(404, "asset not found")
    sniffed = sniff_image(data)
    if sniffed is None:  # stored bytes are not a valid image → never serve them
        raise HTTPException(404, "asset not found")
    content_type, _ = sniffed
    # nosniff: the type we emit is re-derived from magic bytes and is always a known
    # raster image — forbid the browser from MIME-sniffing it into anything else.
    return Response(content=data, media_type=content_type,
                    headers={"Cache-Control": "public, max-age=3600",
                             "X-Content-Type-Options": "nosniff"})
