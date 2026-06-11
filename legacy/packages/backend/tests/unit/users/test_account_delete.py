"""
Unit tests for AccountDeleteRequest Pydantic validator.

The route handler itself (DELETE /users/profile) requires a live database +
authenticated user, so its end-to-end behavior is exercised by the integration
suite. Here we lock down the input contract so a future refactor cannot relax
the double-confirmation safeguard.
"""

import pytest
from pydantic import ValidationError

from app.modules.users.models import AccountDeleteRequest


class TestAccountDeleteRequest:
    """Defense-in-depth: misclick / replay protection on body shape."""

    def test_valid_body_is_accepted(self):
        req = AccountDeleteRequest(password="my-password", confirmation="DELETE")
        assert req.password == "my-password"
        assert req.confirmation == "DELETE"

    def test_missing_password_is_rejected(self):
        with pytest.raises(ValidationError):
            AccountDeleteRequest(confirmation="DELETE")  # type: ignore[call-arg]

    def test_empty_password_is_rejected(self):
        with pytest.raises(ValidationError) as exc:
            AccountDeleteRequest(password="", confirmation="DELETE")
        assert "min_length" in str(exc.value).lower() or "at least" in str(exc.value).lower()

    def test_missing_confirmation_is_rejected(self):
        with pytest.raises(ValidationError):
            AccountDeleteRequest(password="my-password")  # type: ignore[call-arg]

    @pytest.mark.parametrize(
        "bad_value",
        [
            "delete",            # lowercase — rejected
            "Delete",            # mixed-case
            "DELETE ",           # trailing whitespace
            " DELETE",           # leading whitespace
            "DELETE!",           # extra punctuation
            "DELET",             # truncated
            "yes",               # different word entirely
            "",                  # empty
        ],
    )
    def test_confirmation_must_be_exact_literal_DELETE(self, bad_value: str):
        with pytest.raises(ValidationError) as exc:
            AccountDeleteRequest(password="my-password", confirmation=bad_value)
        assert "literal string 'DELETE'" in str(exc.value)

    def test_confirmation_is_case_sensitive(self):
        # Belt-and-braces — same as the parametrized case but explicit.
        with pytest.raises(ValidationError):
            AccountDeleteRequest(password="my-password", confirmation="delete")
