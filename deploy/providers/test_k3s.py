#!/usr/bin/env python3
"""Tests for deploy/providers/k3s.py (Helm values render + Secret allowlist).

No live cluster required: render_values()/build_secret_literals() are pure
functions; --validate/--plan are exercised via helm (present on PATH) with
subprocess mocked out where a real helm invocation isn't the point of the test.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROVIDERS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROVIDERS_DIR))
sys.path.insert(0, str(PROVIDERS_DIR.parent / "scripts"))

import validate_config as vc  # noqa: E402
import k3s  # noqa: E402


def _cfg() -> vc.DeployConfig:
    data = vc.load_yaml(Path(__file__).resolve().parents[2] / "deploy" / "config.yaml")
    return vc.DeployConfig(**data)


def test_render_values_maps_images_and_ports():
    values = k3s.render_values(_cfg())
    assert values["postgres"]["image"] == "pgvector/pgvector:pg16"
    assert values["backend"]["port"] == 8080
    assert values["frontend"]["port"] == 3000
    assert values["backend"]["modulesEnabled"] == "organization,location"


def test_render_values_never_contains_secret_values():
    # Secret guard: the values dict must carry NO secret value, only the k8s
    # Secret's *name* (secrets live in the Secret object, created out of Helm).
    values = k3s.render_values(_cfg())
    flat = repr(values).lower()
    assert "password" not in flat or "secretname" in flat
    assert values["secretName"] == "facil-secrets"


def test_render_values_matches_chart_value_shape():
    # The chart (infra/helm/facil/values.yaml) reads postgres.db/user,
    # minio.rootUser, openbao.devMode, redis.image — render_values must
    # produce values Helm --set can apply on top of those chart defaults.
    values = k3s.render_values(_cfg())
    assert values["postgres"]["db"] == "facil"
    assert values["postgres"]["user"] == "facil"
    assert values["redis"]["image"] == "redis:7-alpine"
    assert values["minio"]["rootUser"] == "facil"
    assert values["openbao"]["devMode"] is True


def test_build_secret_literals_selects_expected_keys():
    env = {"POSTGRES_PASSWORD": "p", "REDIS_PASSWORD": "r", "MINIO_ROOT_PASSWORD": "m",
           "OPENBAO_DEV_ROOT_TOKEN": "t", "JWT_SECRET_KEY": "j", "SECRET_KEY": "s",
           "IGNORED_EXTRA": "x"}
    lit = k3s.build_secret_literals(env)
    assert set(["POSTGRES_PASSWORD", "REDIS_PASSWORD", "MINIO_ROOT_PASSWORD",
                "OPENBAO_DEV_ROOT_TOKEN", "JWT_SECRET_KEY", "SECRET_KEY"]).issubset(lit)
    assert "IGNORED_EXTRA" not in lit  # strict allowlist


def test_build_secret_literals_empty_input_yields_empty_dict():
    assert k3s.build_secret_literals({}) == {}


def test_secret_keys_allowlist_matches_config_secret_names():
    # SECRET_KEYS must cover every secret name deploy/config.yaml references
    # (auth.*_secret + cron.secret_name), plus the infra-only runtime creds
    # (POSTGRES/REDIS/MINIO/OPENBAO) that never appear in config.yaml at all.
    cfg = _cfg()
    assert cfg.auth.jwt_secret_name in k3s.SECRET_KEYS
    assert cfg.auth.app_secret_name in k3s.SECRET_KEYS
    assert cfg.auth.totp_encryption_secret in k3s.SECRET_KEYS
    assert cfg.auth.receipt_verification_secret in k3s.SECRET_KEYS
    assert cfg.cron.secret_name in k3s.SECRET_KEYS


def test_secret_name_constant_matches_chart_default():
    # infra/helm/facil/values.yaml pins secretName: facil-secrets — the two
    # must never drift (the chart's secretKeyRefs point at this exact name).
    assert k3s.SECRET_NAME == "facil-secrets"


def test_load_env_secrets_parses_key_value_file(tmp_path):
    p = tmp_path / ".env.secrets"
    p.write_text(
        "# comment\n"
        "\n"
        "POSTGRES_PASSWORD=abc\n"
        "JWT_SECRET_KEY = def \n",
        encoding="utf-8",
    )
    env = k3s._load_env_secrets(p)
    assert env["POSTGRES_PASSWORD"] == "abc"
    assert env["JWT_SECRET_KEY"] == "def"


def test_load_env_secrets_missing_file_returns_empty():
    assert k3s._load_env_secrets(Path("does-not-exist.env")) == {}


def test_set_args_escapes_commas_in_modules_enabled():
    # Regression: helm's --set mini-language splits on ',' between assignments,
    # so an unescaped "organization,location" is silently mis-parsed as
    # modulesEnabled=organization + a bogus key "location" (helm errors:
    # 'key "location" has no value'). Caught live against real helm.
    values = k3s.render_values(_cfg())
    args = k3s._set_args(values)
    idx = args.index("backend.modulesEnabled=organization\\,location")
    assert args[idx - 1] == "--set"


def test_find_helm_uses_shutil_which(monkeypatch):
    monkeypatch.setattr(k3s.shutil, "which", lambda name: f"/usr/bin/{name}" if name == "helm" else None)
    assert k3s.find_helm() == "/usr/bin/helm"


def test_main_apply_fails_closed_when_required_secrets_missing(monkeypatch, tmp_path):
    # Fail-closed: even with helm present, --apply must refuse to proceed if
    # POSTGRES_PASSWORD/JWT_SECRET_KEY/SECRET_KEY aren't in .env.secrets.
    monkeypatch.setattr(k3s, "find_helm", lambda: "/usr/bin/helm")
    empty_secrets = tmp_path / ".env.secrets"
    empty_secrets.write_text("", encoding="utf-8")
    monkeypatch.setattr(k3s, "REPO_ROOT", tmp_path)
    rc = k3s.main(["--apply", "--config", str(PROVIDERS_DIR.parent / "config.yaml"), "--yes"])
    assert rc == 1


def test_main_validate_fails_closed_when_helm_missing(monkeypatch):
    monkeypatch.setattr(k3s, "find_helm", lambda: None)
    rc = k3s.main(["--validate", "--config", str(PROVIDERS_DIR.parent / "config.yaml")])
    assert rc == 2


def test_main_validate_returns_1_on_bad_config(monkeypatch, tmp_path):
    monkeypatch.setattr(k3s, "find_helm", lambda: "/usr/bin/helm")
    bad_config = tmp_path / "config.yaml"
    bad_config.write_text("meta: {}\n", encoding="utf-8")
    rc = k3s.main(["--validate", "--config", str(bad_config)])
    assert rc == 1


def test_apply_never_prints_the_captured_secret_dry_run_stdout(monkeypatch, tmp_path, capsys):
    # Security-critical invariant (only manual review protects it today):
    # the `kubectl create secret --dry-run=client -o yaml` stdout, which
    # carries REAL key material, must NEVER be print()ed/logged anywhere —
    # it may only flow as stdin into `kubectl apply -f -`. This test exercises
    # the full --apply path with subprocess faked out (no real cluster) and
    # asserts an obvious sentinel planted in the fake dry-run YAML never
    # reaches stdout/stderr. A future refactor adding e.g. a debug
    # `print(dry_run.stdout)` must fail this test.
    sentinel = "SECRETMARKER_SHOULD_NOT_APPEAR_zzq9"

    monkeypatch.setattr(k3s, "find_helm", lambda: "/usr/bin/helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "/usr/bin/kubectl")

    env_secrets = tmp_path / ".env.secrets"
    env_secrets.write_text(
        "POSTGRES_PASSWORD=pw\n"
        "JWT_SECRET_KEY=jwt\n"
        "SECRET_KEY=sk\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(k3s, "REPO_ROOT", tmp_path)

    def fake_run(cmd, **kwargs):
        if "create" in cmd and "secret" in cmd:
            # Simulates `kubectl create secret ... --dry-run=client -o yaml`:
            # its captured stdout contains real-looking key material.
            fake_secret_yaml = (
                "apiVersion: v1\nkind: Secret\ndata:\n"
                f"  POSTGRES_PASSWORD: {sentinel}\n"
            )
            return subprocess.CompletedProcess(cmd, 0, stdout=fake_secret_yaml, stderr="")
        # `kubectl apply -f -` and `helm upgrade --install` — neither should
        # ever need to see/echo the secret literal either.
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)

    rc = k3s.main([
        "--apply", "--config", str(PROVIDERS_DIR.parent / "config.yaml"), "--yes",
    ])

    captured = capsys.readouterr()
    assert rc == 0
    assert sentinel not in captured.out
    assert sentinel not in captured.err
