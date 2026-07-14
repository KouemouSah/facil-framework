"""richtext sanitisation + the secret guard.

`richtext` is the single most dangerous type in SP1: HTML authored through the
admin UI is CODE. Unsanitised, it is a stored XSS today — and a later
sub-project (SP2) renders that same HTML SERVER-SIDE into a PDF, so a remote
`<img src="http://169.254.169.254/...">` becomes an SSRF reaching the cloud
metadata endpoint from inside the network. Allowlist, never a denylist, both
at write time and at render time.

Sanitiser: `nh3` (Rust binding to Mozilla's `ammonia`) — no C toolchain
dependency, actively maintained, ships a manylinux/win_amd64 wheel. Verified
empirically (see `test_schema_guards.py`) that with `url_schemes=set()` a
disallowed remote `<img>` is stripped ENTIRELY (the tag is not in the
allowlist, so nh3 removes it outright rather than just filtering `src`).
"""

from __future__ import annotations

import nh3

# Reused, not copied: `app.models.provider._SECRET_INDICATORS` is the existing
# guard on config-store settings (admin_settings.py imports its siblings from
# the same module). No circular import: app.models.provider only imports from
# app.db.base, never from app.core.schema.
from app.models.provider import _SECRET_INDICATORS

# Formatting only. No <script>, no <style>, no <iframe>, no <object>, no forms,
# no event handlers (nh3 strips `on*` attributes unconditionally — they are
# never offered as an allowed attribute below).
#
# `img` is DELIBERATELY excluded. Document images come from the `file`/`image`
# field type, which already goes through /api/v1/assets (magic-byte sniffed,
# SVG refused, size-capped). A remote `<img>` in richtext has no legitimate
# use and is exactly the SSRF vector described above.
ALLOWED_TAGS: set[str] = {
    "p", "br", "strong", "b", "em", "i", "u", "s",
    "ul", "ol", "li", "blockquote",
    "h1", "h2", "h3", "h4",
    "table", "thead", "tbody", "tr", "th", "td",
    "span", "div", "a",
}
ALLOWED_ATTRS: dict[str, set[str]] = {"a": {"href", "title"}, "*": {"class"}}
# Empty set => nh3 accepts NO url scheme at all on href (relative-only would
# need "url_relative", not "url_schemes"); this strips javascript:/data:/http(s)
# hrefs alike, which is intentional — richtext has no legitimate use for a
# scheme'd link that a document reviewer's "formatting only" would ever need,
# and it removes any ambiguity for the SP2 server-side PDF renderer.
ALLOWED_URL_SCHEMES: set[str] = set()


def clean_richtext(html: str) -> str:
    """Sanitise HTML to the allowlist above. Called at BOTH write time (this
    module) and render time (SP2 PDF renderer) — defence in depth, since a row
    written before a tightened allowlist must still be safe to render."""
    if not html:
        return ""
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer",
    )


def assert_not_secretish(key: str) -> None:
    """A custom field must never become a plaintext credential store — mirrors
    the `_SECRET_INDICATORS` guard already enforced on config-store settings
    (`app/models/provider.py`, used by `admin_settings.py`)."""
    low = key.lower()
    if any(indicator in low for indicator in _SECRET_INDICATORS):
        raise ValueError(
            f"key {key!r} looks like a secret; custom fields must never hold "
            f"credentials (use the secret store)")
