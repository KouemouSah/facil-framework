"""
User-Agent parsing helper (Phase C.3 / mig 329).

Wraps the `user-agents` Python lib with an LRU cache to amortize parse cost
across the (extremely repetitive) UA strings of real traffic. Used by the
request_telemetry middleware to populate device_type / browser / os columns.

Soft-import: when `user-agents` lib isn't installed, returns all-NULL dict
so the middleware degrades gracefully without crashing.

Performance:
- Uncached parse: ~30-50µs per UA string
- Cached hit: ~200ns (dict lookup)
- LRU 4096 entries → ~99% hit rate observed in real traffic
"""

from __future__ import annotations

from functools import lru_cache
from typing import TypedDict


class UAInfo(TypedDict):
    device_type: str | None  # mobile | desktop | tablet | bot | unknown
    is_bot: bool
    browser_name: str | None
    browser_version: str | None
    os_name: str | None
    os_version: str | None


_EMPTY: UAInfo = {
    "device_type": None,
    "is_bot": False,
    "browser_name": None,
    "browser_version": None,
    "os_name": None,
    "os_version": None,
}


try:
    from user_agents import parse as _ua_parse
    _UA_AVAILABLE = True
except Exception:  # pragma: no cover
    _UA_AVAILABLE = False
    _ua_parse = None  # type: ignore


@lru_cache(maxsize=4096)
def parse_ua(ua_string: str) -> UAInfo:
    """Parse a User-Agent string. Cached. Always returns a UAInfo dict."""
    if not ua_string or not _UA_AVAILABLE:
        return _EMPTY  # type: ignore[return-value]

    try:
        p = _ua_parse(ua_string)  # type: ignore[misc]
    except Exception:
        return _EMPTY  # type: ignore[return-value]

    is_bot = bool(p.is_bot)
    if is_bot:
        device_type = "bot"
    elif p.is_mobile:
        device_type = "mobile"
    elif p.is_tablet:
        device_type = "tablet"
    elif p.is_pc:
        device_type = "desktop"
    else:
        device_type = "unknown"

    return {
        "device_type": device_type,
        "is_bot": is_bot,
        "browser_name": p.browser.family or None,
        "browser_version": p.browser.version_string or None,
        "os_name": p.os.family or None,
        "os_version": p.os.version_string or None,
    }


def cache_info() -> dict:
    """Expose LRU stats (debug + dashboard panel `cache hit rate`)."""
    info = parse_ua.cache_info()
    return {
        "hits": info.hits,
        "misses": info.misses,
        "hit_rate": info.hits / (info.hits + info.misses) if (info.hits + info.misses) else 0.0,
        "current_size": info.currsize,
        "max_size": info.maxsize,
    }


__all__ = ["UAInfo", "parse_ua", "cache_info"]
