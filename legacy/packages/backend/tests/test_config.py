# tests/test_config.py
import re

import pytest
from app.config import settings


# VERSION is now bumped through commit history. Anchor on the SemVer shape
# instead of a literal so future bumps don't break this test for free; the
# api_version property must mirror VERSION.
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def test_config_import():
    """Test que la configuration peut être importée"""
    assert settings.PROJECT_NAME == "TaxasGE API"
    assert SEMVER_RE.match(settings.VERSION), f"VERSION not SemVer: {settings.VERSION!r}"


def test_environment_validation():
    """Test que l'environnement est valide"""
    assert settings.ENVIRONMENT in ["development", "testing", "staging", "production"]
    assert isinstance(settings.DEBUG, bool)


def test_basic_structure():
    """Test que la structure de base fonctionne"""
    # Test import config only - avoid circular import with full app.main
    from app.config import get_settings
    config = get_settings()
    assert config.PROJECT_NAME == "TaxasGE API"
    assert SEMVER_RE.match(config.VERSION), f"VERSION not SemVer: {config.VERSION!r}"
    # api_version is a backward-compat property mirroring VERSION (added
    # 2026-05-02 when main.py's local Settings class was removed).
    assert config.api_version == config.VERSION
