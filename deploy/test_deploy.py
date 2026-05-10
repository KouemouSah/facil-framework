"""Tests for deploy/deploy.py orchestrator.

These tests use mocks for subprocess.run so they verify orchestration
logic without invoking real validate_config / render_env / gcp scripts.

Run from repo root:
    pytest deploy/test_deploy.py -v --no-cov
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

DEPLOY_DIR = Path(__file__).parent
sys.path.insert(0, str(DEPLOY_DIR))

import deploy as deploy_mod  # noqa: E402


def make_completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    cp = MagicMock()
    cp.returncode = returncode
    cp.stdout = stdout
    cp.stderr = stderr
    return cp


@pytest.fixture
def fake_config(tmp_path: Path) -> Path:
    """A non-empty config file (content unused — sub-scripts are mocked)."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("meta:\n  config_version: 1\n")
    return cfg


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

class TestPreflight:
    def test_missing_config_returns_3(self, tmp_path: Path) -> None:
        rc = deploy_mod.main([
            "--config", str(tmp_path / "nonexistent.yaml"),
            "--provider=gcp",
            "--action=validate",
        ])
        assert rc == 3

    def test_unknown_provider_caught_by_argparse(
        self, fake_config: Path, capsys: pytest.CaptureFixture
    ) -> None:
        with pytest.raises(SystemExit):
            deploy_mod.main([
                "--config", str(fake_config),
                "--provider=azure",  # not in SUPPORTED_PROVIDERS
                "--action=validate",
            ])

    def test_missing_provider_script_returns_3(
        self,
        fake_config: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        # Point PROVIDERS_DIR to an empty directory.
        empty = tmp_path / "providers_empty"
        empty.mkdir()
        monkeypatch.setattr(deploy_mod, "PROVIDERS_DIR", empty)
        rc = deploy_mod.main([
            "--config", str(fake_config),
            "--provider=docker-local",
            "--action=validate",
        ])
        assert rc == 3


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

class TestPipelineOrchestration:
    def test_validate_stops_after_step3(
        self, fake_config: Path
    ) -> None:
        """--action=validate should run steps 1-3 and skip step 4."""
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return make_completed(0)

        with patch("deploy.subprocess.run", side_effect=fake_run):
            rc = deploy_mod.main([
                "--config", str(fake_config),
                "--provider=gcp",
                "--action=validate",
            ])

        assert rc == 0
        # 3 sub-script invocations: validate_config, render_env, gcp.py --validate
        assert len(calls) == 3
        # Last call must be the provider --validate
        assert "--validate" in calls[-1]

    def test_plan_runs_step4_with_plan_flag(self, fake_config: Path) -> None:
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return make_completed(0)

        with patch("deploy.subprocess.run", side_effect=fake_run):
            rc = deploy_mod.main([
                "--config", str(fake_config),
                "--provider=gcp",
                "--action=plan",
            ])

        assert rc == 0
        assert len(calls) == 4
        # The 4th call must use --plan, not --apply.
        assert "--plan" in calls[-1]
        assert "--apply" not in calls[-1]

    def test_apply_runs_step4_with_apply_flag(self, fake_config: Path) -> None:
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return make_completed(0)

        with patch("deploy.subprocess.run", side_effect=fake_run):
            rc = deploy_mod.main([
                "--config", str(fake_config),
                "--provider=gcp",
                "--action=apply",
            ])

        assert rc == 0
        assert len(calls) == 4
        assert "--apply" in calls[-1]


# ---------------------------------------------------------------------------
# Failure propagation
# ---------------------------------------------------------------------------

class TestFailurePropagation:
    def test_step1_fail_returns_1_no_step2(self, fake_config: Path) -> None:
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            # validate_config fails.
            return make_completed(1)

        with patch("deploy.subprocess.run", side_effect=fake_run):
            rc = deploy_mod.main([
                "--config", str(fake_config),
                "--provider=gcp",
                "--action=apply",
            ])

        assert rc == 1
        assert len(calls) == 1  # stopped at step 1

    def test_step2_fail_returns_1_no_step3(self, fake_config: Path) -> None:
        call_count = [0]

        def fake_run(cmd, **kwargs):
            call_count[0] += 1
            # validate_config OK, render_env fails.
            return make_completed(0 if call_count[0] == 1 else 1)

        with patch("deploy.subprocess.run", side_effect=fake_run):
            rc = deploy_mod.main([
                "--config", str(fake_config),
                "--provider=gcp",
                "--action=apply",
            ])

        assert rc == 1
        assert call_count[0] == 2

    def test_provider_validate_fail_returns_2(self, fake_config: Path) -> None:
        call_count = [0]

        def fake_run(cmd, **kwargs):
            call_count[0] += 1
            # First two pass, provider validate fails.
            return make_completed(0 if call_count[0] < 3 else 1)

        with patch("deploy.subprocess.run", side_effect=fake_run):
            rc = deploy_mod.main([
                "--config", str(fake_config),
                "--provider=gcp",
                "--action=apply",
            ])

        assert rc == 2
        assert call_count[0] == 3

    def test_provider_apply_fail_returns_2(self, fake_config: Path) -> None:
        call_count = [0]

        def fake_run(cmd, **kwargs):
            call_count[0] += 1
            # All pass except the final --apply step.
            return make_completed(0 if call_count[0] < 4 else 2)

        with patch("deploy.subprocess.run", side_effect=fake_run):
            rc = deploy_mod.main([
                "--config", str(fake_config),
                "--provider=gcp",
                "--action=apply",
            ])

        assert rc == 2
        assert call_count[0] == 4
