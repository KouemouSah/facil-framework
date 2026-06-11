"""Tests for app/core/otel_sampler.py (Phase B.9 noise filter).

Covers the _should_drop predicate (no OTEL SDK dependency in these tests)
plus the FacilNoiseFilterSampler integration when the SDK is available.
"""

from __future__ import annotations

import pytest

from app.core import otel_sampler
from app.core.otel_sampler import _should_drop


class TestShouldDrop:
    """Pure-logic tests on _should_drop, independent of opentelemetry SDK."""

    @pytest.mark.parametrize("path", [
        "/healthz",
        "/ready",
        "/readyz",
        "/livez",
        "/metrics",
        "/favicon.ico",
    ])
    def test_drops_exact_paths(self, path: str):
        assert _should_drop({"http.target": path}) is True
        assert _should_drop({"http.route": path}) is True
        assert _should_drop({"url.path": path}) is True

    @pytest.mark.parametrize("path", [
        "/static/css/main.css",
        "/static/js/app.bundle.js",
        "/static/",
    ])
    def test_drops_static_prefix(self, path: str):
        assert _should_drop({"http.target": path}) is True

    def test_drops_options_method_any_path(self):
        # CORS preflight — drop regardless of route
        assert _should_drop({"http.method": "OPTIONS", "http.target": "/api/v1/users"}) is True
        assert _should_drop({"http.request.method": "OPTIONS"}) is True

    @pytest.mark.parametrize("path", [
        "/api/v1/users",
        "/api/v1/healthz",  # business endpoint, NOT root /healthz — must keep
        "/admin/dashboards",
        "/login",
        "/",
    ])
    def test_keeps_business_paths(self, path: str):
        assert _should_drop({"http.target": path, "http.method": "GET"}) is False

    def test_handles_query_string(self):
        # /healthz?check=db should still drop
        assert _should_drop({"http.target": "/healthz?check=db"}) is True

    def test_handles_full_url(self):
        # http.url comes with full scheme+host
        assert _should_drop({"http.url": "https://api.example.com/healthz"}) is True
        assert _should_drop({"http.url": "https://api.example.com/api/v1/users"}) is False

    def test_keeps_when_no_attributes(self):
        # No HTTP context at all (e.g. internal worker span) — never drop
        assert _should_drop(None) is False
        assert _should_drop({}) is False
        assert _should_drop({"db.system": "postgresql"}) is False

    def test_keeps_post_to_healthz_business_logic(self):
        # Note: we drop /healthz regardless of method (treating it as a probe).
        # This is intentional — if your /healthz accepts POST for some reason,
        # rename it.
        assert _should_drop({"http.target": "/healthz", "http.method": "POST"}) is True


@pytest.mark.skipif(
    not otel_sampler._OTEL_AVAILABLE, reason="opentelemetry SDK not installed"
)
class TestSamplerIntegration:
    """End-to-end sampler tests requiring the OTEL SDK."""

    def test_build_sampler_default_returns_parent_based(self):
        from opentelemetry.sdk.trace.sampling import ParentBased
        sampler = otel_sampler.build_sampler()
        assert sampler is not None
        assert isinstance(sampler, ParentBased)
        # Description should mention our filter
        assert "FacilNoiseFilterSampler" in sampler.get_description()

    def test_build_sampler_with_ratio(self):
        sampler = otel_sampler.build_sampler(ratio=0.25)
        assert sampler is not None
        # The TraceIdRatioBased is the inner delegate — description shows ratio
        assert "0.25" in sampler.get_description() or "TraceIdRatioBased" in sampler.get_description()

    def test_drops_healthz_span(self):
        from opentelemetry.sdk.trace.sampling import Decision
        sampler = otel_sampler.build_sampler()
        # ParentBased.should_sample takes parent_context first
        result = sampler.should_sample(
            parent_context=None,
            trace_id=0x1234,
            name="GET /healthz",
            attributes={"http.target": "/healthz", "http.method": "GET"},
        )
        assert result.decision == Decision.DROP

    def test_records_business_span(self):
        from opentelemetry.sdk.trace.sampling import Decision
        sampler = otel_sampler.build_sampler()
        result = sampler.should_sample(
            parent_context=None,
            trace_id=0x1234,
            name="GET /api/v1/users",
            attributes={"http.target": "/api/v1/users", "http.method": "GET"},
        )
        # Default ratio=None → ALWAYS_ON delegate → RECORD_AND_SAMPLE
        assert result.decision == Decision.RECORD_AND_SAMPLE

    def test_drops_options_preflight(self):
        from opentelemetry.sdk.trace.sampling import Decision
        sampler = otel_sampler.build_sampler()
        result = sampler.should_sample(
            parent_context=None,
            trace_id=0x1234,
            name="OPTIONS /api/v1/auth/login",
            attributes={"http.target": "/api/v1/auth/login", "http.method": "OPTIONS"},
        )
        assert result.decision == Decision.DROP
