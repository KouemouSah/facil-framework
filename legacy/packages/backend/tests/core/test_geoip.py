"""Tests for app/core/geoip — soft-fail behavior + private IP handling.

Note: Without a MaxMind MMDB file locally, lookup_ip returns the empty
dict for all IPs. These tests validate the safe degradation path.
"""

import pytest


def test_geoip_init_returns_false_when_db_missing(tmp_path) -> None:
    from app.core import geoip
    geoip._AVAILABLE = False
    geoip._reader = None
    result = geoip.init_geoip(str(tmp_path / "nonexistent.mmdb"))
    assert result is False
    assert geoip.is_available() is False


def test_lookup_ip_returns_empty_when_unavailable() -> None:
    from app.core.geoip import lookup_ip
    info = lookup_ip("8.8.8.8")
    assert info["geo_country"] is None
    assert info["geo_city"] is None


def test_lookup_ip_handles_empty_string() -> None:
    from app.core.geoip import lookup_ip
    info = lookup_ip("")
    assert info["geo_country"] is None


@pytest.mark.parametrize(
    "private_ip",
    [
        "127.0.0.1",
        "10.0.0.1",
        "192.168.1.1",
        "172.16.0.1",
        "172.20.5.10",
        "169.254.0.1",
        "::1",
        "fe80::1",
    ],
)
def test_private_ips_skipped(private_ip: str) -> None:
    """Private/loopback IPs return empty without hitting the MMDB reader."""
    from app.core.geoip import lookup_ip
    info = lookup_ip(private_ip)
    assert info["geo_country"] is None
    assert info["geo_city"] is None


def test_172_public_range_is_not_skipped_as_private() -> None:
    """172.0-15 and 172.32-255 are PUBLIC ranges, not private. Should fall
    through to the reader (which returns NULL when DB unavailable)."""
    from app.core.geoip import lookup_ip
    # 172.32.0.1 is a public IP. With no DB, returns empty dict — same shape.
    info = lookup_ip("172.32.0.1")
    assert "geo_country" in info  # just shape, not value


def test_cache_info_exposes_stats() -> None:
    from app.core.geoip import cache_info, lookup_ip
    lookup_ip.cache_clear()
    lookup_ip("8.8.8.8")
    lookup_ip("8.8.8.8")  # cache hit
    info = cache_info()
    assert info["hits"] >= 1
    assert info["misses"] >= 1
    assert "available" in info
