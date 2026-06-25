"""Shared env-posture helpers — fail-secure 'required' resolution (A1a)."""

from __future__ import annotations

from app.core.env_posture import is_dev, is_required


def test_is_dev_recognises_dev_like_envs():
    for v in ("development", "dev", "test", "local", "DEV", "Test"):
        assert is_dev({"ENVIRONMENT": v}) is True


def test_is_dev_default_is_dev_when_unset():
    assert is_dev({}) is True  # absent ENVIRONMENT => treated as development


def test_is_dev_false_in_production():
    assert is_dev({"ENVIRONMENT": "production"}) is False


def test_is_required_explicit_knob_wins_over_env():
    # Explicit "1"/"0" always wins, regardless of ENVIRONMENT.
    assert is_required({"ENVIRONMENT": "development", "X_REQUIRED": "1"}, "X_REQUIRED") is True
    assert is_required({"ENVIRONMENT": "production", "X_REQUIRED": "0"}, "X_REQUIRED") is False


def test_is_required_defaults_to_prod_posture_when_knob_unset():
    # No knob => required in prod (fail-secure), relaxed in dev.
    assert is_required({"ENVIRONMENT": "production"}, "X_REQUIRED") is True
    assert is_required({"ENVIRONMENT": "development"}, "X_REQUIRED") is False
    assert is_required({}, "X_REQUIRED") is False  # default env is dev
