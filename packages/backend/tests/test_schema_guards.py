"""Four guards on a field definition: reserved names, secrets, richtext, relations."""

import pytest

from app.core.schema.reserved import assert_key_allowed, reserved_keys
from app.core.schema.sanitize import assert_not_secretish, clean_richtext


def test_reserved_keys_are_derived_from_the_real_columns_not_hardcoded():
    # A hardcoded list drifts on the first migration. Introspect the model.
    keys = reserved_keys("site.custom_fields")
    assert {"id", "code", "name", "organization_id", "custom_fields"} <= keys


def test_a_custom_field_cannot_shadow_a_real_column():
    with pytest.raises(ValueError, match="reserved"):
        assert_key_allowed("site.custom_fields", "organization_id")
    assert_key_allowed("site.custom_fields", "convention_no")  # does not raise


def test_secret_looking_keys_are_refused_at_definition_time():
    for key in ("api_key", "smtp_password", "client_secret", "access_token"):
        with pytest.raises(ValueError, match="secret"):
            assert_not_secretish(key)
    assert_not_secretish("convention_no")  # does not raise


def test_richtext_strips_script_handlers_and_javascript_urls():
    assert "<script>" not in clean_richtext("<p>hi</p><script>alert(1)</script>")
    assert "onerror" not in clean_richtext('<img src="x" onerror="alert(1)">')
    assert "javascript:" not in clean_richtext('<a href="javascript:alert(1)">x</a>')


def test_richtext_blocks_remote_resources_ssrf_vector():
    # In SP2 this HTML is rendered server-side into a PDF. A remote <img> would
    # make the renderer fetch an attacker-chosen URL from inside the network.
    out = clean_richtext('<img src="http://169.254.169.254/latest/meta-data/">')
    assert "169.254.169.254" not in out


def test_richtext_keeps_legitimate_formatting():
    out = clean_richtext("<p><strong>Acme</strong> — <em>SARL</em></p><ul><li>x</li></ul>")
    assert "<strong>" in out and "<em>" in out and "<li>" in out
