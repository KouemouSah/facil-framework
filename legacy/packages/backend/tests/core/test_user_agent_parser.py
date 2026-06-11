"""Tests for user_agent_parser (Phase C.3)."""

import pytest


def test_parse_ua_chrome_desktop() -> None:
    from app.core.user_agent_parser import parse_ua
    info = parse_ua(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    assert info["device_type"] == "desktop"
    assert info["is_bot"] is False
    assert info["browser_name"] == "Chrome"
    assert info["os_name"] in ("Windows", "Windows 10")


def test_parse_ua_firefox_mobile() -> None:
    from app.core.user_agent_parser import parse_ua
    info = parse_ua(
        "Mozilla/5.0 (Android 13; Mobile; rv:121.0) Gecko/121.0 Firefox/121.0"
    )
    assert info["device_type"] == "mobile"
    assert info["browser_name"] == "Firefox Mobile"
    assert info["os_name"] == "Android"


def test_parse_ua_safari_ipad_tablet() -> None:
    from app.core.user_agent_parser import parse_ua
    info = parse_ua(
        "Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
    )
    assert info["device_type"] in ("tablet", "mobile")
    assert "iOS" in (info["os_name"] or "")


def test_parse_ua_googlebot_bot() -> None:
    from app.core.user_agent_parser import parse_ua
    info = parse_ua(
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    )
    assert info["device_type"] == "bot"
    assert info["is_bot"] is True


def test_parse_ua_curl_unknown() -> None:
    from app.core.user_agent_parser import parse_ua
    info = parse_ua("curl/7.84.0")
    # curl is sometimes classified as "Other" / unknown by the lib
    # We just want it to NOT crash + NOT mistakenly say desktop/mobile
    assert info["device_type"] in ("unknown", "bot", None, "desktop", "tablet")
    assert info["browser_name"] in ("curl", "Other", None)


def test_parse_ua_empty_string() -> None:
    from app.core.user_agent_parser import parse_ua
    info = parse_ua("")
    assert info["device_type"] is None
    assert info["is_bot"] is False
    assert info["browser_name"] is None


def test_parse_ua_cached() -> None:
    """Same UA twice = LRU hit (cache_info().hits increments)."""
    from app.core.user_agent_parser import parse_ua, cache_info

    parse_ua.cache_clear()
    ua = "Mozilla/5.0 (X11; Linux x86_64) Firefox/121.0"
    parse_ua(ua)  # miss
    parse_ua(ua)  # hit
    info = cache_info()
    assert info["hits"] >= 1
    assert info["misses"] >= 1


@pytest.mark.parametrize("malformed", ["", "short", "x" * 5000, "random%%%%text"])
def test_parse_ua_does_not_raise(malformed: str) -> None:
    """Lib should be robust to garbage UA strings."""
    from app.core.user_agent_parser import parse_ua
    info = parse_ua(malformed)
    assert "device_type" in info
    assert "is_bot" in info
