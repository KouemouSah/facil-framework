"""
Unit tests for WizardInitiatePaymentRequest.return_url validator.

Validates that the return_url field accepts:
- None / empty (fallback to web FRONTEND_URL)
- Mobile deep link schemes (whitelisted via MOBILE_DEEP_LINK_SCHEMES)
- HTTP(S) URLs sharing the same origin as FRONTEND_URL

And rejects:
- Foreign HTTP(S) origins (open-redirect attempts)
- Unknown schemes
- Malformed values
"""

import pytest
from pydantic import ValidationError

from app.modules.service_requests.models.wizard_session import WizardInitiatePaymentRequest


def _build(payment_method: str = "mobile_money", **kwargs) -> WizardInitiatePaymentRequest:
    return WizardInitiatePaymentRequest(payment_method=payment_method, **kwargs)


class TestReturnUrlValidator:
    """Whitelist-based return_url validation guards against open-redirect."""

    def test_return_url_none_is_accepted(self):
        req = _build(return_url=None)
        assert req.return_url is None

    def test_return_url_empty_string_is_normalized_to_none(self):
        req = _build(return_url="")
        assert req.return_url is None

    def test_return_url_facil_scheme_is_accepted(self):
        url = "facil://wizard/payment-result?session_id=abc&service_request_id=def"
        req = _build(return_url=url)
        assert req.return_url == url

    def test_return_url_facil_scheme_with_query_only_is_accepted(self):
        url = "facil://payment-result"
        req = _build(return_url=url)
        assert req.return_url == url

    def test_return_url_same_origin_https_is_accepted(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "FRONTEND_URL", "https://taxasge.emacsah.com")
        url = "https://taxasge.emacsah.com/dashboard/service-requests/abc/payment/result"
        req = _build(return_url=url)
        assert req.return_url == url

    def test_return_url_foreign_https_origin_is_rejected(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "FRONTEND_URL", "https://taxasge.emacsah.com")
        with pytest.raises(ValidationError) as exc:
            _build(return_url="https://attacker.example.com/steal?ref=abc")
        assert "origin is not allowed" in str(exc.value)

    def test_return_url_unknown_scheme_is_rejected(self):
        with pytest.raises(ValidationError) as exc:
            _build(return_url="javascript:alert(1)")
        assert "scheme" in str(exc.value).lower()

    def test_return_url_unknown_custom_scheme_is_rejected(self):
        with pytest.raises(ValidationError) as exc:
            _build(return_url="malicious-app://exfiltrate?ref=abc")
        assert "scheme" in str(exc.value).lower()

    def test_return_url_without_scheme_is_rejected(self):
        with pytest.raises(ValidationError) as exc:
            _build(return_url="/dashboard/relative-path")
        assert "scheme" in str(exc.value).lower()

    def test_return_url_too_long_is_rejected(self):
        long_url = "facil://" + ("x" * 600)
        with pytest.raises(ValidationError):
            _build(return_url=long_url)

    def test_return_url_respects_multi_scheme_whitelist(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "MOBILE_DEEP_LINK_SCHEMES", "facil,facil-staging")
        # Re-validate: facil-staging should now be accepted
        req = _build(return_url="facil-staging://payment-result")
        assert req.return_url == "facil-staging://payment-result"
        # facil still works
        req2 = _build(return_url="facil://payment-result")
        assert req2.return_url == "facil://payment-result"
