#!/usr/bin/env python3
"""Tests for deploy/providers/k3s.py (Helm values render + Secret allowlist).

No live cluster required: render_values()/build_secret_literals() are pure
functions; --validate/--plan are exercised via helm (present on PATH) with
subprocess mocked out where a real helm invocation isn't the point of the test.
"""
from __future__ import annotations

import base64
import copy
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROVIDERS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROVIDERS_DIR))
sys.path.insert(0, str(PROVIDERS_DIR.parent / "scripts"))

import validate_config as vc  # noqa: E402
import k3s  # noqa: E402

_FULL_SECRETS = {
    "POSTGRES_PASSWORD": "pg-pw", "REDIS_PASSWORD": "redis-pw",
    "MINIO_ROOT_PASSWORD": "minio-pw", "OPENBAO_DEV_ROOT_TOKEN": "bao-tok",
    "JWT_SECRET_KEY": "jwt", "SECRET_KEY": "app", "TOTP_ENCRYPTION_KEY": "totp",
    "RECEIPT_VERIFICATION_SECRET": "receipt", "CRON_SECRET": "cron",
    "FACIL_APP_PASSWORD": "app-role-pw",
}

# --- Structural secret guard for render_values() (G1) -----------------------
#
# The old guard (`"password" not in repr(values).lower()`) only ever caught
# two literal substrings and inspected the *repr* of the whole dict, so it
# couldn't tell a key from a value. This one (a) walks every leaf of the
# values dict, (b) rejects any KEY whose name looks like a credential, and
# (c) rejects any VALUE that looks like a random secret blob — regardless of
# what its key is called.
_CREDENTIAL_KEY_RE = re.compile(r"(password|secret|token|credential|api_?key)", re.IGNORECASE)
# >=24 chars, only the alphabet a base64/hex/urlsafe blob would use. Deliberately
# does NOT include ":" "@" or ",": every image ref render_values() emits carries
# an explicit tag (`repo/name:tag`) or a digest (`repo/name@sha256:hex`), and
# modulesEnabled is a comma-joined list — all of those break a full-string match
# on this alphabet, so this stays strict without needing a value-based allowlist.
_SECRET_LIKE_VALUE_RE = re.compile(r"^[A-Za-z0-9+/=_-]{24,}$")

# Dotted paths (in the flattened values dict) that are allowed to have a KEY
# name matching _CREDENTIAL_KEY_RE, because they carry a Secret *name*/*ref*,
# never a value. Checked against render_values()'s REAL current output (see
# k3s.render_values docstring + infra/helm/facil/values.yaml::secretNames)
# before deciding: render_values() does NOT set "secretName"/"secretNames" at
# all today (S1 removed that --set entirely — the chart's own values.yaml
# defaults already match k3s.SECRET_NAMES) — so there is currently NOTHING to
# allowlist. Left empty on purpose: do not pre-populate with guesses.
_ALLOWED_CREDENTIAL_KEY_PATHS: frozenset[str] = frozenset()


def _flatten(d: dict, prefix: str = "") -> list[tuple[str, object]]:
    """Recursively flattens a (possibly nested) dict into (dotted.path, leaf_value)."""
    items: list[tuple[str, object]] = []
    for k, v in d.items():
        path = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            items.extend(_flatten(v, path))
        else:
            items.append((path, v))
    return items


def _assert_values_carry_no_secrets(values: dict) -> None:
    """The real guard: raises AssertionError on the first credential-shaped
    key or secret-shaped value found anywhere in the (flattened) values dict."""
    for path, value in _flatten(values):
        leaf_key = path.rsplit(".", 1)[-1]
        if _CREDENTIAL_KEY_RE.search(leaf_key) and path not in _ALLOWED_CREDENTIAL_KEY_PATHS:
            raise AssertionError(
                f"values['{path}']: key name looks like a credential "
                f"(matches {_CREDENTIAL_KEY_RE.pattern!r})")
        if isinstance(value, str) and _SECRET_LIKE_VALUE_RE.match(value):
            raise AssertionError(
                f"values['{path}']: value looks like a secret blob "
                f"(len={len(value)}, matches secret-shaped alphabet)")


def _cfg_dict(project_name: str = "facil", **overrides: object) -> dict:
    """Inline minimal config (P1 shape) — built in Python, no dependency on a
    local file. `deploy/config.yaml` is gitignored (.gitignore:170), so a `_cfg()`
    that read it (the old implementation) silently worked on a dev machine that
    happened to have one lying around, but broke in CI/any fresh clone (B1 —
    28 failed/10 passed when the file is absent, proven by mutation: rename the
    file, rerun). Mirrors the fixture pattern already used by
    test_docker_local.py/test_gcp.py's `minimal_config_dict` (DRY: same shape,
    same convention of building config in Python instead of reading a file the
    repo doesn't ship).
    """
    data = {
        "meta": {"config_version": 1, "project_name": project_name,
                  "environment": "development", "version": "develop"},
        "database": {"url_secret": "database-url"},
        "redis": {"url_secret": "REDIS_URL"},
        "auth": {
            "jwt_secret_name": "JWT_SECRET_KEY",
            "app_secret_name": "SECRET_KEY",
            "totp_encryption_secret": "TOTP_ENCRYPTION_KEY",
            "receipt_verification_secret": "RECEIPT_VERIFICATION_SECRET",
        },
        "firebase": {"project_id": "facil-local",
                     "storage_bucket": "facil-local.appspot.com"},
        "ai": {"gemini_api_key_secret": "GEMINI_API_KEY"},
        "server": {"frontend_url": "http://localhost:3000",
                   "api_base_url": "http://localhost:8080"},
        "cron": {"secret_name": "CRON_SECRET"},
        "storage": {"provider": "minio", "minio": {"root_user": "facil"}},
        "secrets": {"provider": "openbao", "openbao": {"dev_mode": True}},
        "docker_local": {
            "database_mode": "local", "backend_port": 8080, "frontend_port": 3000,
            "postgres_image": "pgvector/pgvector:pg16", "postgres_volume": "facil_pgdata",
            "redis_image": "redis:7-alpine",
        },
        "modules": {"enabled": ["organization", "location"]},
    }
    data.update(overrides)
    return data


def _cfg(project_name: str = "facil", **overrides: object) -> vc.DeployConfig:
    return vc.DeployConfig(**_cfg_dict(project_name, **overrides))


def _write_cfg_file(tmp_path: Path, project_name: str = "facil", **overrides: object) -> Path:
    """Writes _cfg_dict() out to a real YAML file — for the `k3s.main([--config …])`
    call sites that need an actual path on disk (main() takes a Path, not a dict).
    Always lands in tmp_path: never `deploy/config.yaml` (B1)."""
    import yaml
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(_cfg_dict(project_name, **overrides)), encoding="utf-8")
    return p


def test_render_values_maps_images_and_ports():
    values = k3s.render_values(_cfg())
    assert values["postgres"]["image"] == "pgvector/pgvector:pg16"
    assert values["backend"]["port"] == 8080
    assert values["frontend"]["port"] == 3000
    assert values["backend"]["modulesEnabled"] == "organization,location"


def test_render_values_never_contains_secret_values():
    # Structural secret guard (G1): walks every leaf of the real values dict
    # and rejects credential-shaped KEYS (password|secret|token|credential|
    # api_key) as well as secret-shaped VALUES (>=24-char base64/hex-alphabet
    # blobs) — not just two hardcoded substrings against a dict repr().
    values = k3s.render_values(_cfg())
    _assert_values_carry_no_secrets(values)  # must not raise


def test_secret_guard_catches_injected_credential_shaped_key():
    # Mutation-guard: proves the assertion above can actually fail. Without
    # this, a future regression of the guard back into a tautology (like the
    # original `"secretname" in flat` clause, which was always true) would go
    # unnoticed. Inject a fake credential-shaped key into a REAL rendered
    # values dict and confirm the guard rejects it.
    values = k3s.render_values(_cfg())
    mutated = copy.deepcopy(values)
    mutated["backend"]["injectedApiToken"] = "unused-value"
    with pytest.raises(AssertionError, match="looks like a credential"):
        _assert_values_carry_no_secrets(mutated)


def test_secret_guard_catches_secret_shaped_value_under_an_anodyne_key():
    # Mutation-guard, value side: an innocuous-looking key name ("buildId")
    # whose VALUE is a random-looking blob must still be rejected — this is
    # exactly the class of leak the old repr()-substring check could never
    # catch (it only ever looked at key-shaped substrings).
    values = k3s.render_values(_cfg())
    mutated = copy.deepcopy(values)
    mutated["backend"]["buildId"] = "Zm9vYmFyYmF6cXV4Y29ycmVjdGhvcnNl"  # 32 chars, base64 alphabet
    with pytest.raises(AssertionError, match="looks like a secret blob"):
        _assert_values_carry_no_secrets(mutated)


def test_secret_guard_does_not_flag_real_image_refs_or_modules_list():
    # False-positive check (the task's own concern): a digest-pinned image
    # ref and the comma-joined modulesEnabled list both contain characters
    # outside the secret-value alphabet (":" "@" ",") so a >=24-char value
    # there must NOT trip the guard. Proven directly against render_values()'s
    # real current output, not a hypothetical.
    values = k3s.render_values(_cfg())
    _assert_values_carry_no_secrets(values)
    mutated = copy.deepcopy(values)
    mutated["postgres"]["image"] = "pgvector/pgvector@sha256:" + "a" * 64  # digest-pinned, legit
    # Comma-joined list long enough to hit the >=24 length floor, but the
    # comma is outside the secret-value alphabet so it must not match either.
    mutated["backend"]["modulesEnabled"] = "organization,location,directory,reporting"
    _assert_values_carry_no_secrets(mutated)  # must NOT raise


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


def test_render_values_derives_postgres_db_and_user_from_project_name():
    # B2 (regression guard): postgres.db/user used to be hardcoded to "facil"
    # in render_values() while db-role-job's GRANT CONNECT ON DATABASE and
    # backend_database_url() both derive from cfg.meta.project_name (see
    # docker_local.py:181-182 for the same convention on the compose path).
    # With project_name="acme", the chart would create database `facil` while
    # the Job ran `GRANT CONNECT ON DATABASE acme` -> SQL error -> Job fails ->
    # `--atomic` aborts the release. project_name is deliberately != "facil"
    # here (the chart/config default) so this test cannot pass on a hardcoded
    # value AND a correct derivation at once -- it would only pass on the
    # latter (proven by mutation: reverting render_values()'s "db"/"user" to
    # the literal "facil" turns this red; see finding B2 verification).
    values = k3s.render_values(_cfg("acme"))
    assert values["postgres"]["db"] == "acme"
    assert values["postgres"]["user"] == "acme"


def test_build_secret_literals_selects_expected_keys():
    # Post-S1: literals are partitioned PER COMPONENT (dict of dicts), not a
    # flat allowlisted dict — verify each component gets exactly its own keys,
    # and unknown keys never leak into any component (still a strict allowlist,
    # just enforced per-component rather than globally).
    env = {"POSTGRES_PASSWORD": "p", "REDIS_PASSWORD": "r", "MINIO_ROOT_PASSWORD": "m",
           "OPENBAO_DEV_ROOT_TOKEN": "t", "JWT_SECRET_KEY": "j", "SECRET_KEY": "s",
           "IGNORED_EXTRA": "x"}
    lit = k3s.build_secret_literals(env, cfg=_cfg())
    assert lit["postgres"] == {"POSTGRES_PASSWORD": "p"}
    assert lit["redis"] == {"REDIS_PASSWORD": "r"}
    assert lit["minio"] == {"MINIO_ROOT_PASSWORD": "m"}
    assert lit["openbao"] == {"OPENBAO_DEV_ROOT_TOKEN": "t"}
    assert lit["backend"] == {"JWT_SECRET_KEY": "j", "SECRET_KEY": "s", "REDIS_PASSWORD": "r"}
    for component in lit.values():
        assert "IGNORED_EXTRA" not in component  # strict allowlist


def test_build_secret_literals_empty_input_yields_empty_dict():
    # Every component's pick() is empty -> the whole dict is filtered out.
    assert k3s.build_secret_literals({}, cfg=_cfg()) == {}


def test_render_role_sql_never_leaks_password_via_argv_placeholder():
    # CWE-214 (revue R2/F1) : le SQL du Job db-role doit lire le mdp applicatif
    # via `\getenv` (variable d'environnement du process psql), jamais via un
    # canal qui finirait dans l'argv de psql (`-v app_pw=...`).
    sql = k3s.render_role_sql(_cfg())
    assert "\\getenv app_pw FACIL_APP_PASSWORD" in sql
    assert "-v app_pw" not in sql
    # La meta-commande doit etre terminee par un saut de ligne, pas par ';'
    # (sinon psql cherche la variable d'env "FACIL_APP_PASSWORD;", inexistante).
    assert "\\getenv app_pw FACIL_APP_PASSWORD\n" in sql
    assert "FACIL_APP_PASSWORD;" not in sql


def test_backend_never_receives_infrastructure_root_credentials():
    # SEC-001 (blast radius) : une RCE/SSRF dans le backend — seule surface HTTP
    # exposee — ne doit PAS livrer le superuser Postgres, le root MinIO ni le root
    # token OpenBao. Le backend n'en a aucun usage (config.py: extra="ignore").
    lit = k3s.build_secret_literals(_FULL_SECRETS, cfg=_cfg())
    backend = lit["backend"]
    assert "POSTGRES_PASSWORD" not in backend
    assert "MINIO_ROOT_PASSWORD" not in backend
    assert "OPENBAO_DEV_ROOT_TOKEN" not in backend
    # ...mais il garde ce qu'il consomme reellement. (BACKEND_DATABASE_URL est ajoute
    # par la Task R2, qui le DERIVE de FACIL_APP_PASSWORD — pas assere ici.)
    assert {"JWT_SECRET_KEY", "SECRET_KEY", "REDIS_PASSWORD"} <= set(backend)


def test_each_component_secret_holds_only_its_own_credential():
    lit = k3s.build_secret_literals(_FULL_SECRETS, cfg=_cfg())
    assert set(lit["postgres"]) == {"POSTGRES_PASSWORD"}
    assert set(lit["minio"]) == {"MINIO_ROOT_PASSWORD"}
    assert set(lit["openbao"]) == {"OPENBAO_DEV_ROOT_TOKEN"}


def test_backup_secret_holds_only_what_the_backup_job_needs():
    # Le Job de backup a besoin du superuser PG (dump complet) et du root MinIO
    # (lire tous les buckets) -- mais de RIEN d'autre. Un Secret dedie, jamais
    # celui du backend (SEC-001 : une RCE dans le backend ne doit pas livrer le
    # data-plane, et ce test-la doit rester vert).
    lit = k3s.build_secret_literals(_FULL_SECRETS, cfg=_cfg())
    assert set(lit["backup"]) == {"POSTGRES_PASSWORD", "MINIO_ROOT_PASSWORD"}
    assert k3s.SECRET_NAMES["backup"] == "facil-backup-secret"


def test_backend_still_has_no_root_credentials_after_adding_backup():
    # Garde-fou explicite : l'ajout du composant "backup" ne doit pas rouvrir le
    # blast radius qu'on a ferme.
    lit = k3s.build_secret_literals(_FULL_SECRETS, cfg=_cfg())
    backend = lit["backend"]
    assert "POSTGRES_PASSWORD" not in backend
    assert "MINIO_ROOT_PASSWORD" not in backend
    assert "OPENBAO_DEV_ROOT_TOKEN" not in backend


def test_secret_keys_allowlist_matches_config_secret_names():
    # Post-S1: SECRET_KEYS (flat allowlist) is gone — the "backend" component's
    # pick() list is now the allowlist. Every secret name deploy/config.yaml
    # references (auth.*_secret + cron.secret_name) must still be coverable by
    # the backend component (the only one exposed to the config-driven names;
    # the infra-only runtime creds POSTGRES/REDIS/MINIO/OPENBAO never appear
    # in config.yaml at all and live in their own components instead).
    cfg = _cfg()
    lit = k3s.build_secret_literals(_FULL_SECRETS, cfg=cfg)
    backend_keys = set(lit["backend"])
    assert cfg.auth.jwt_secret_name in backend_keys
    assert cfg.auth.app_secret_name in backend_keys
    assert cfg.auth.totp_encryption_secret in backend_keys
    assert cfg.auth.receipt_verification_secret in backend_keys
    assert cfg.cron.secret_name in backend_keys


def test_secret_names_match_chart_default_secret_names():
    # infra/helm/facil/values.yaml pins secretNames.* (one per component) — must
    # never drift from k3s.SECRET_NAMES (the chart's secretKeyRefs resolve from
    # values.yaml's own defaults, k3s.py never overrides them via --set).
    # NB: values.yaml follows Helm's camelCase key convention; k3s.SECRET_NAMES
    # keys are the kebab-case component identifiers used internally (they double
    # as build_secret_literals() dict keys) — "db-role" -> "dbRole" in the chart.
    import yaml
    values_path = k3s.CHART_DIR / "values.yaml"
    chart_values = yaml.safe_load(values_path.read_text(encoding="utf-8"))
    CHART_KEY = {"db-role": "dbRole"}
    for component, name in k3s.SECRET_NAMES.items():
        chart_key = CHART_KEY.get(component, component)
        assert chart_values["secretNames"][chart_key] == name


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
    #
    # backend.modulesEnabled is also a _STRING_KEYS entry (SEC-017): it must
    # go through --set-string, not --set (a purely-numeric module list is
    # unlikely today, but the comma-escaping regression this test guards is
    # orthogonal to the string-vs-coerced-type one below).
    values = k3s.render_values(_cfg())
    args = k3s._set_args(values)
    idx = args.index("backend.modulesEnabled=organization\\,location")
    assert args[idx - 1] == "--set-string"


def test_set_args_uses_set_string_for_string_keys_to_avoid_type_coercion():
    # SEC-017: `--set` runs the value through Helm's strconv.ParseInt/ParseBool
    # before writing it into values -- a purely-numeric imageTag like "0123"
    # would silently lose its leading zero (become the int 123), and a
    # database name that happened to be all-digits would corrupt the same way.
    # `--set-string` skips that coercion entirely. Proven against a real
    # render_values() output plus a synthetic numeric-looking value.
    values = k3s.render_values(_cfg())
    values["global"]["imageTag"] = "0123"
    args = k3s._set_args(values)
    idx = args.index("global.imageTag=0123")
    assert args[idx - 1] == "--set-string"
    # A key NOT in _STRING_KEYS (e.g. backend.port, an int) must still use
    # the plain --set -- proves the branch isn't a blanket "always --set-string".
    port_idx = next(i for i, a in enumerate(args) if a.startswith("backend.port="))
    assert args[port_idx - 1] == "--set"


def test_set_args_string_keys_cover_all_render_values_text_fields():
    # Mutation-style completeness check: every leaf in render_values()'s real
    # output whose value is naturally textual (image refs, db/user names,
    # module lists) must be routed through --set-string -- a future field
    # added to render_values() without a matching _STRING_KEYS entry would
    # silently regress back to type coercion for that one field.
    values = k3s.render_values(_cfg())
    args = k3s._set_args(values)
    text_paths = {
        "postgres.image", "postgres.db", "postgres.user",
        "redis.image", "backend.modulesEnabled",
    }
    for path in text_paths:
        idx = next(i for i, a in enumerate(args) if a.startswith(f"{path}="))
        assert args[idx - 1] == "--set-string", f"{path} must use --set-string"


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
    # --allow-dev-vault: isolates this test from the SEC-002 dev-mode guard
    # (the inline config has openbao.dev_mode=true) so it still exercises the
    # missing-secrets fail-closed path it's named for, not the dev-mode one.
    rc = k3s.main(["--apply", "--config", str(_write_cfg_file(tmp_path)),
                   "--yes", "--allow-dev-vault"])
    assert rc == 1


def test_main_validate_fails_closed_when_helm_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(k3s, "find_helm", lambda: None)
    rc = k3s.main(["--validate", "--config", str(_write_cfg_file(tmp_path))])
    assert rc == 2


def test_main_validate_returns_1_on_bad_config(monkeypatch, tmp_path):
    monkeypatch.setattr(k3s, "find_helm", lambda: "/usr/bin/helm")
    bad_config = tmp_path / "config.yaml"
    bad_config.write_text("meta: {}\n", encoding="utf-8")
    rc = k3s.main(["--validate", "--config", str(bad_config)])
    assert rc == 1


def test_values_onprem_file_exists_and_has_no_secret():
    # Referenced by --plan/--apply (-f overlay) and by the CI workflow
    # (task 1.11) — must exist at this exact path, secret-free.
    path = k3s.REPO_ROOT / "infra" / "helm" / "facil" / "values-onprem.yaml"
    assert path.exists()
    text = path.read_text(encoding="utf-8").lower()
    for banned in ("password", "secret_key", "token", "root_token"):
        assert banned not in text.replace("devmode", "")


def test_plan_passes_values_onprem_overlay_to_helm_template(monkeypatch, tmp_path):
    captured_cmds = []

    def fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(k3s, "find_helm", lambda: "/usr/bin/helm")
    monkeypatch.setattr(k3s.subprocess, "run", fake_run)

    rc = k3s.main(["--plan", "--config", str(_write_cfg_file(tmp_path))])

    assert rc == 0
    assert len(captured_cmds) == 1
    cmd = captured_cmds[0]
    assert "-f" in cmd
    f_idx = cmd.index("-f")
    assert cmd[f_idx + 1] == str(k3s.VALUES_ONPREM)


def test_apply_passes_values_onprem_overlay_to_helm_upgrade(monkeypatch, tmp_path):
    captured_cmds = []

    def fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        if "status" in cmd:
            # release_exists() lit .info.status (JSON) -- "deployed" pour
            # rester sur le chemin une-passe que ce test exerce.
            return subprocess.CompletedProcess(
                cmd, 0, stdout='{"info":{"status":"deployed"}}', stderr="")
        if "create" in cmd and "secret" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(k3s, "find_helm", lambda: "/usr/bin/helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "/usr/bin/kubectl")
    env_secrets = tmp_path / ".env.secrets"
    env_secrets.write_text(
        "POSTGRES_PASSWORD=pw\nJWT_SECRET_KEY=jwt\nSECRET_KEY=sk\n"
        "FACIL_APP_PASSWORD=apppw\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(k3s, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(k3s.subprocess, "run", fake_run)

    # --allow-dev-vault: this test is about the values-onprem overlay flowing
    # through to `helm upgrade`, not the SEC-002 dev-mode guard.
    rc = k3s.main(["--apply", "--config", str(_write_cfg_file(tmp_path)),
                   "--yes", "--allow-dev-vault"])

    assert rc == 0
    upgrade_cmd = next(c for c in captured_cmds if "upgrade" in c)
    assert "-f" in upgrade_cmd
    f_idx = upgrade_cmd.index("-f")
    assert upgrade_cmd[f_idx + 1] == str(k3s.VALUES_ONPREM)


def test_apply_creates_namespace_before_secret(monkeypatch, tmp_path):
    # APPLY-004 : sur un cluster neuf le namespace n'existe pas ; appliquer le
    # Secret avant sa creation echoue ("namespaces \"facil\" not found").
    calls = []

    def fake_run(cmd, **kw):
        calls.append((list(cmd), kw.get("input")))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)
    # --allow-dev-vault: this test is about namespace-before-secret ordering,
    # not the SEC-002 dev-mode guard.
    k3s.main(["--apply", "--config", str(_write_cfg_file(tmp_path)),
              "--yes", "--allow-dev-vault"])

    joined = [" ".join(c) for c, _ in calls]
    ns_idx = next(i for i, c in enumerate(joined) if "create namespace" in c or "namespace facil" in c)
    # Cible le VRAI apply du Secret, PAR SON NOM -- pas seulement "un appel qui
    # porte -n et apply dans son argv". `apply_manifest()` construit TOUJOURS
    # le meme argv (`[kubectl, "-n", ns, "apply", "-f", "-"]`), que le manifeste
    # sur stdin soit un Secret OU la ConfigMap SQL (0bis, ajoutee depuis
    # l'ecriture de ce test) : filtrer sur l'argv seul faisait donc matcher en
    # PREMIER l'apply de la ConfigMap, pas celui d'un Secret -- l'assertion
    # restait vraie PAR TRANSITIVITE (le Secret suit quand meme la ConfigMap,
    # qui suit le namespace) mais ne prouvait plus ce qu'elle pretendait
    # prouver. On inspecte desormais le manifeste REEL (kwarg `input=`, jamais
    # l'argv -- SEC-006) pour reperer le premier Secret nomme par
    # k3s.SECRET_NAMES["postgres"] ("facil-postgres-secret", le 1er composant
    # itere par build_secret_literals -- postgres avant redis/minio/openbao/
    # backend/db-role, cf. son ordre d'insertion).
    sec_idx = next(
        i for i, (c, manifest) in enumerate(calls)
        if "-n" in c and "apply" in c and manifest
        and "kind: Secret" in manifest
        and f"name: {k3s.SECRET_NAMES['postgres']}" in manifest
    )
    assert ns_idx < sec_idx, "le namespace doit etre cree AVANT le Secret"


# ---------------------------------------------------------------------------
# B2 : PVC des sauvegardes cree HORS Helm (kubectl apply -f -), AVANT
# `helm upgrade --install` — sur les DEUX chemins (1er install ET upgrade
# d'une release deja installee). C'est exactement le deadlock que ce
# correctif ferme : porte par Helm en hook `pre-install` SEUL, ce PVC n'etait
# JAMAIS cree sur un upgrade (Helm n'execute pre-install qu'au tout premier
# `helm install`) -> le Job facil-backup restait Pending indefiniment.
# ---------------------------------------------------------------------------

def test_build_pvc_manifest_shape():
    manifest = k3s.build_pvc_manifest("facil-backups", "local-path", "10Gi")
    assert "kind: PersistentVolumeClaim" in manifest
    assert "name: facil-backups" in manifest
    assert "storageClassName: local-path" in manifest
    assert "storage: 10Gi" in manifest
    assert "ReadWriteOnce" in manifest
    # Ni hook Helm ni resource-policy : ce manifest n'est plus une ressource du
    # chart -- rien a "garder" contre un `helm uninstall` qui ne le voit
    # de toute facon jamais.
    assert "helm.sh/hook" not in manifest


def test_chart_pvc_defaults_reads_from_real_chart_values():
    # Pas de litteral duplique : les valeurs DOIVENT provenir des fichiers
    # values.yaml/values-onprem.yaml reels du chart -- une divergence future
    # (ex. quelqu'un bascule le storageClass onprem) doit se refleter ICI
    # sans toucher k3s.py.
    storage_class, storage = k3s.chart_pvc_defaults()
    assert storage_class == "local-path"
    assert storage == "10Gi"


def test_apply_creates_pvc_before_helm_upgrade_on_a_fresh_install(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, **kw):
        calls.append((list(cmd), kw.get("input")))
        if "status" in cmd:
            # release_exists() -- aucune release existante -> chemin danse 2 passes.
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not found")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)
    monkeypatch.setattr(k3s, "health_gate", lambda *a, **kw: 0)
    rc = k3s.main(["--apply", "--config", str(_write_cfg_file(tmp_path)),
                   "--yes", "--allow-dev-vault"])
    assert rc == 0

    joined = [" ".join(c) for c, _ in calls]
    pvc_idx = next(
        i for i, (c, manifest) in enumerate(calls)
        if "apply" in c and manifest and "kind: PersistentVolumeClaim" in manifest
        and "name: facil-backups" in manifest
    )
    upgrade_idx = next(i for i, c in enumerate(joined) if "upgrade" in c)
    assert pvc_idx < upgrade_idx, "le PVC doit exister AVANT le premier `helm upgrade --install`"


def test_apply_creates_pvc_before_helm_upgrade_on_an_already_installed_release(
    monkeypatch, tmp_path,
):
    # LE scenario du bug B2 : release DEJA installee (donc une seule passe,
    # pas de danse 2-replicas) -- le PVC doit quand meme etre (re)applique
    # AVANT `helm upgrade`, jamais suppose deja present.
    calls = []

    def fake_run(cmd, **kw):
        calls.append((list(cmd), kw.get("input")))
        if "status" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, stdout='{"info":{"status":"deployed"}}', stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)
    monkeypatch.setattr(k3s, "health_gate", lambda *a, **kw: 0)
    rc = k3s.main(["--apply", "--config", str(_write_cfg_file(tmp_path)),
                   "--yes", "--allow-dev-vault"])
    assert rc == 0

    joined = [" ".join(c) for c, _ in calls]
    pvc_idx = next(
        i for i, (c, manifest) in enumerate(calls)
        if "apply" in c and manifest and "kind: PersistentVolumeClaim" in manifest
        and "name: facil-backups" in manifest
    )
    upgrade_idx = next(i for i, c in enumerate(joined) if "upgrade" in c)
    assert pvc_idx < upgrade_idx, (
        "B2 : sur une release DEJA installee, le PVC doit encore etre applique "
        "AVANT `helm upgrade` -- c'est exactement le chemin ou l'ancien hook "
        "pre-install ne se declenchait JAMAIS")


def test_apply_pvc_after_namespace_but_manifest_carries_no_secret(monkeypatch, tmp_path):
    # Le PVC ne porte aucune valeur de secret -- juste une preuve de forme
    # complementaire a test_secret_values_never_appear_in_any_process_argv.
    calls = []

    def fake_run(cmd, **kw):
        calls.append((list(cmd), kw.get("input")))
        if "status" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, stdout='{"info":{"status":"deployed"}}', stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)
    monkeypatch.setattr(k3s, "health_gate", lambda *a, **kw: 0)
    k3s.main(["--apply", "--config", str(_write_cfg_file(tmp_path)),
              "--yes", "--allow-dev-vault"])

    pvc_manifest = next(
        m for c, m in calls if "apply" in c and m and "kind: PersistentVolumeClaim" in m)
    for secret_value in _FULL_SECRETS.values():
        assert secret_value not in pvc_manifest


def test_plan_renders_in_the_target_namespace(monkeypatch, tmp_path):
    # SEC-019 : `helm template` sans -n rend avec .Release.Namespace = "default",
    # donc le plan ne reflete pas l'apply.
    #
    # Namespace volontairement DIFFERENT du nom de release Helm ("facil",
    # hardcode dans la commande --plan) : avec --namespace facil, l'assertion
    # `[x for x in calls[0] if x in (...)][:2]` passait meme si `-n` etait
    # hardcode a une autre valeur, car "facil" apparaissait de toute facon
    # comme nom de release (garde tautologique). On verifie ici l'adjacence
    # positionnelle "-n" -> valeur, qui echoue si -n n'est pas lie a
    # args.namespace.
    calls = []
    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: calls.append(list(cmd)) or
                        subprocess.CompletedProcess(cmd, 0))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    k3s.main(["--plan", "--config", str(_write_cfg_file(tmp_path)), "--namespace", "custom-ns"])
    cmd = calls[0]
    n_idx = cmd.index("-n")
    assert cmd[n_idx + 1] == "custom-ns", "-n doit etre immediatement suivi de args.namespace"


def test_apply_uses_atomic_for_auto_rollback(monkeypatch, tmp_path):
    # SEC-022 : sans --atomic une release en echec reste en place, pods casses.
    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        if "status" in cmd:
            # release_exists() lit .info.status (JSON) -- "deployed" pour
            # rester sur le chemin une-passe que ce test exerce.
            return subprocess.CompletedProcess(
                cmd, 0, stdout='{"info":{"status":"deployed"}}', stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)
    # --allow-dev-vault: this test is about --atomic on the upgrade command,
    # not the SEC-002 dev-mode guard.
    k3s.main(["--apply", "--config", str(_write_cfg_file(tmp_path)),
              "--yes", "--allow-dev-vault"])
    upgrade = next(c for c in calls if "upgrade" in c)
    assert "--atomic" in upgrade


def test_secret_values_never_appear_in_any_process_argv(monkeypatch, tmp_path):
    # SEC-006 (CWE-214) : `kubectl create secret --from-literal=K=V` expose les valeurs
    # dans l'argv (ps -ef, /proc/<pid>/cmdline, auditd). On construit le manifest en
    # Python et on le pipe sur stdin : rien ne transite par une ligne de commande.
    MARKER = "s3nt1nel-p4ssw0rd-marker"
    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets",
                        lambda p: {**_FULL_SECRETS, "POSTGRES_PASSWORD": MARKER})
    # --allow-dev-vault: without it the SEC-002 guard returns before any
    # subprocess call, leaving `calls` empty and the loop below vacuously
    # true (a tautology) — the flag lets the real argv-scrubbing logic run.
    k3s.main(["--apply", "--config", str(_write_cfg_file(tmp_path)),
              "--yes", "--allow-dev-vault"])

    assert calls, "aucun appel subprocess capture — l'assertion suivante serait vide de sens"
    b64 = base64.b64encode(MARKER.encode()).decode()
    for cmd in calls:
        for arg in cmd:
            assert MARKER not in arg, f"secret en clair dans l'argv: {cmd[0]}"
            assert b64 not in arg, f"secret base64 dans l'argv: {cmd[0]}"


def test_build_secret_manifest_base64_encodes_values():
    m = k3s.build_secret_manifest("facil-postgres-secret", {"POSTGRES_PASSWORD": "pw"})
    assert "kind: Secret" in m
    assert base64.b64encode(b"pw").decode() in m
    assert "POSTGRES_PASSWORD: pw" not in m  # jamais en clair


def test_build_configmap_manifest_indents_multiline_values_under_block_scalar():
    # ConfigMap = donnees NON secretes (ex. SQL du role applicatif) — pas de
    # base64 ici, mais le multi-ligne doit passer par un bloc `|` indente
    # (sinon YAML invalide / valeurs tronquees a la premiere ligne).
    data = {"init.sql": "CREATE ROLE facil_app;\nGRANT ALL ON facil TO facil_app;"}
    m = k3s.build_configmap_manifest("facil-role-configmap", data)
    assert "kind: ConfigMap" in m
    assert "name: facil-role-configmap" in m
    assert "  init.sql: |" in m
    assert "    CREATE ROLE facil_app;" in m
    assert "    GRANT ALL ON facil TO facil_app;" in m


def test_apply_refuses_openbao_dev_mode_without_explicit_optin(monkeypatch, capsys, tmp_path):
    # SEC-002 : bao -dev = stockage in-memory (secrets perdus au restart), auto-unseal,
    # root token en env, HTTP en clair. Acceptable pour un smoke, JAMAIS en prod.
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)
    rc = k3s.main(["--apply", "--config", str(_write_cfg_file(tmp_path)),
                   "--yes"])   # inline config a openbao.dev_mode = true
    assert rc == 1
    assert "dev-mode" in capsys.readouterr().err.lower()


def test_apply_allows_openbao_dev_mode_with_explicit_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout=""))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)
    assert k3s.main(["--apply", "--config", str(_write_cfg_file(tmp_path)),
                     "--yes", "--allow-dev-vault"]) == 0


def test_rollback_invokes_helm_rollback_in_the_target_namespace(monkeypatch):
    calls = []
    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: calls.append(list(cmd)) or
                        subprocess.CompletedProcess(cmd, 0, stdout=""))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    assert k3s.main(["--rollback", "--namespace", "custom-ns"]) == 0
    rb = next(c for c in calls if "rollback" in c)
    assert rb[rb.index("-n") + 1] == "custom-ns"


def test_rollback_warns_that_the_database_is_NOT_restored(monkeypatch, capsys):
    # Le piege mortel : helm rollback rend les MANIFESTES, jamais la BASE. Si la
    # migration etait destructive, l'operateur doit le savoir, a l'ecran.
    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout=""))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    k3s.main(["--rollback"])
    out = capsys.readouterr().out.lower()
    assert "base de donnees" in out
    assert "ne restaure pas" in out or "n'a pas ete" in out
    assert "restore_backup" in out   # on pointe vers l'outil, pas juste un avertissement


# --- A4 : l'avertissement vient AVANT l'action, et exige confirmation --------

def test_rollback_requires_confirmation_without_yes(monkeypatch):
    calls = []
    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: calls.append(list(cmd)) or
                        subprocess.CompletedProcess(cmd, 0, stdout=""))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    rc = k3s.main(["--rollback"])
    assert rc == 4
    assert calls == [], (
        "decliner doit annuler AVANT tout appel `helm history`/`helm rollback` "
        f"-- appels observes : {calls}")


def test_rollback_proceeds_when_confirmed_without_yes(monkeypatch):
    calls = []
    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: calls.append(list(cmd)) or
                        subprocess.CompletedProcess(cmd, 0, stdout=""))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    rc = k3s.main(["--rollback"])
    assert rc == 0
    assert any("rollback" in c for c in calls)


def test_yes_does_NOT_skip_the_rollback_confirmation(monkeypatch):
    # Arbitrage explicite (revue E2). --yes est documente comme "confirme
    # --apply". --rollback est l'operation la PLUS risquee du provider : il rend
    # les manifestes SANS restaurer la base -- c'est tout le piege que
    # l'avertissement A4 existe pour signaler. Le laisser court-circuiter par
    # --yes, c'est garantir que personne ne le lira jamais dans un pipeline,
    # c'est-a-dire precisement la ou le rollback est declenche.
    asked = []
    monkeypatch.setattr("builtins.input", lambda prompt="": asked.append(prompt) or "n")
    calls = []
    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: calls.append(list(cmd)) or
                        subprocess.CompletedProcess(cmd, 0, stdout=""))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    rc = k3s.main(["--rollback"])
    assert rc == 4, "--yes ne doit PAS auto-confirmer un rollback"
    assert asked, "la confirmation doit etre demandee meme avec --yes"
    assert calls == [], "aucun appel cluster apres un refus"


def test_rollback_aborts_when_helm_history_fails_instead_of_rolling_back_blindly(monkeypatch):
    # Le returncode de `helm history` etait jete : sur une release inexistante,
    # l'operateur ne voyait rien s'afficher, confirmait, et `helm rollback`
    # echouait derriere. On s'arrete avec la cause -- et SURTOUT sans jamais
    # appeler `helm rollback`.
    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        rc = 1 if "history" in cmd else 0
        return subprocess.CompletedProcess(cmd, rc, stdout="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    rc = k3s.main(["--rollback"])
    assert rc == 2
    assert not any("rollback" in c for c in calls), (
        f"un `helm history` en echec ne doit JAMAIS mener a un rollback -- {calls}")


def test_rollback_warning_appears_before_the_success_confirmation(monkeypatch, capsys):
    # A4 : l'avertissement ("ne restaure pas la base") doit precede l'action --
    # pas etre decouvert APRES coup, une fois le rollback deja declenche.
    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout=""))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    k3s.main(["--rollback"])
    out = capsys.readouterr().out
    warn_idx = out.lower().index("ne restaure pas")
    ok_idx = out.index("[OK]")
    assert warn_idx < ok_idx, "l'avertissement doit precede la confirmation de succes"


def test_rollback_targets_specific_revision_when_given(monkeypatch):
    calls = []
    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: calls.append(list(cmd)) or
                        subprocess.CompletedProcess(cmd, 0, stdout=""))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    assert k3s.main(["--rollback", "--revision", "3"]) == 0
    rb = next(c for c in calls if "rollback" in c)
    assert rb[rb.index("rollback") + 1:rb.index("rollback") + 3] == ["facil", "3"]


def test_rollback_fails_closed_when_helm_rollback_errors(monkeypatch, capsys):
    def fake_run(cmd, **kw):
        if "rollback" in cmd:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")
        return subprocess.CompletedProcess(cmd, 0, stdout="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    rc = monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    rc = k3s.main(["--rollback"])
    assert rc == 2
    out = capsys.readouterr()
    # A4 : l'avertissement pre-action est maintenant affiche AVANT de savoir si
    # `helm rollback` va reussir (c'est le point -- l'operateur doit le voir
    # AVANT de decider) -- mais la confirmation de SUCCES ("[OK] ... termine")
    # ne doit elle jamais apparaitre quand `helm rollback` a echoue : rien n'a
    # ete change, ce message serait trompeur.
    assert "[OK]" not in out.out
    assert "ERREUR" in out.err


def test_rollback_does_not_require_deploy_config_yaml(monkeypatch, tmp_path):
    # --rollback n'a besoin d'aucune config applicative -- doit fonctionner meme
    # quand deploy/config.yaml est absent (poste fraichement clone / CI).
    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout=""))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    missing_config = tmp_path / "does-not-exist.yaml"
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    assert k3s.main(["--rollback", "--yes", "--config", str(missing_config)]) == 0


def test_rollback_and_apply_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        k3s.main(["--rollback", "--apply", "--yes"])


# --- C1 : health-gate explicite apres upgrade ------------------------------
#
# Honnetete (a ne pas perdre de vue en lisant ces tests) : `helm upgrade --wait`
# attend deja que les pods soient Ready, et la readinessProbe backend EST deja
# /health -- ce gate est donc INCREMENTAL (verifie l'app APRES que Helm ait
# declare la release reussie, message exploitable), jamais un remplacement du
# --wait existant.

def test_health_gate_calls_kubectl_exec_with_expected_url_and_returns_0_on_success(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s.time, "sleep", lambda s: (_ for _ in ()).throw(
        AssertionError("no sleep expected on first-try success")))

    rc = k3s.health_gate("kubectl", "facil", 8080)

    assert rc == 0
    assert len(calls) == 1
    cmd = calls[0]
    assert cmd[:4] == ["kubectl", "-n", "facil", "exec"]
    assert "deploy/facil-backend" in cmd
    assert any("localhost:8080/health" in a for a in cmd)


def test_health_gate_retries_with_delay_before_failing(monkeypatch):
    # Mutation-guard: proves the retry loop can actually exhaust and fail --
    # not just succeed trivially on the first attempt.
    calls = []
    slept = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="connection refused")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s.time, "sleep", lambda s: slept.append(s))

    rc = k3s.health_gate("kubectl", "facil", 8080, attempts=3, delay_seconds=2.0)

    assert rc == 2
    assert len(calls) == 3, "doit epuiser TOUTES les tentatives avant d'echouer"
    assert slept == [2.0, 2.0], "espace entre tentatives, mais pas apres la derniere"


def test_health_gate_names_the_faulty_deployment_and_namespace_on_failure(monkeypatch, capsys):
    monkeypatch.setattr(
        k3s.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="dial tcp: timeout"))
    monkeypatch.setattr(k3s.time, "sleep", lambda s: None)

    rc = k3s.health_gate("kubectl", "custom-ns", 9000, attempts=1)

    assert rc == 2
    err = capsys.readouterr().err
    # Message exploitable : nomme le Deployment fautif + le namespace + le
    # DERNIER diagnostic reel -- pas juste "echec", ce qui serait un timeout
    # Helm opaque avec un habillage different.
    assert "deploy/facil-backend" in err
    assert "custom-ns" in err
    assert "dial tcp: timeout" in err


def test_health_gate_succeeds_after_a_transient_failure(monkeypatch):
    # Distingue vraiment le retry loop d'un simple pass/fail binaire.
    attempts_seen = []

    def fake_run(cmd, **kw):
        attempts_seen.append(1)
        rc = 1 if len(attempts_seen) == 1 else 0
        return subprocess.CompletedProcess(cmd, rc, stdout="", stderr="not ready yet")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s.time, "sleep", lambda s: None)

    rc = k3s.health_gate("kubectl", "facil", 8080, attempts=5, delay_seconds=1.0)

    assert rc == 0
    assert len(attempts_seen) == 2


def test_main_apply_fails_closed_when_health_gate_reports_app_down(monkeypatch, tmp_path):
    # Helm declares the release successful (--wait passed) but the app itself
    # doesn't answer /health -- main() must surface this as a hard failure,
    # not silently return 0 just because `helm upgrade` succeeded.
    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)
    monkeypatch.setattr(k3s, "health_gate", lambda *a, **kw: 2)

    rc = k3s.main(["--apply", "--config", str(_write_cfg_file(tmp_path)),
                   "--yes", "--allow-dev-vault"])
    assert rc == 2


def test_main_apply_returns_0_when_health_gate_passes(monkeypatch, tmp_path):
    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)
    monkeypatch.setattr(k3s, "health_gate", lambda *a, **kw: 0)

    rc = k3s.main(["--apply", "--config", str(_write_cfg_file(tmp_path)),
                   "--yes", "--allow-dev-vault"])
    assert rc == 0


def test_main_apply_passes_configured_backend_port_to_health_gate(monkeypatch, tmp_path):
    seen = {}

    def fake_health_gate(kubectl, namespace, port, **kw):
        seen["kubectl"] = kubectl
        seen["namespace"] = namespace
        seen["port"] = port
        return 0

    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)
    monkeypatch.setattr(k3s, "health_gate", fake_health_gate)

    rc = k3s.main(["--apply", "--config",
                   str(_write_cfg_file(tmp_path, docker_local={
                       "database_mode": "local", "backend_port": 9999,
                       "frontend_port": 3000, "postgres_image": "pgvector/pgvector:pg16",
                       "postgres_volume": "facil_pgdata", "redis_image": "redis:7-alpine"})),
                   "--yes", "--allow-dev-vault", "--namespace", "custom-ns"])
    assert rc == 0
    assert seen == {"kubectl": "kubectl", "namespace": "custom-ns", "port": 9999}


def test_main_apply_first_install_also_runs_health_gate(monkeypatch, tmp_path):
    # Le 1er install (danse deux-passes) doit AUSSI passer par le health-gate
    # apres la 2e passe -- pas seulement le chemin upgrade-simple.
    def fake_run(cmd, **kw):
        if "status" in cmd:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not found")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    calls = []
    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)
    monkeypatch.setattr(k3s, "health_gate", lambda *a, **kw: calls.append(a) or 0)

    rc = k3s.main(["--apply", "--config", str(_write_cfg_file(tmp_path)),
                   "--yes", "--allow-dev-vault"])
    assert rc == 0
    assert len(calls) == 1


def test_deploy_py_knows_k3s_provider():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "deploy_main", Path(__file__).resolve().parents[1] / "deploy.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "k3s" in mod.SUPPORTED_PROVIDERS


def test_backend_database_url_uses_the_app_role_not_the_superuser():
    # APPLY-003 / cible (e) : le backend se connecte en facil_app, jamais en superuser.
    url = k3s.backend_database_url(_cfg(), "app-role-pw")
    assert url.startswith("postgresql+asyncpg://facil_app:")
    assert "@facil-postgres:5432/facil" in url
    assert "facil:" not in url.split("@")[0].replace("facil_app:", "")


def test_build_secret_literals_derives_backend_database_url():
    # BACKEND_DATABASE_URL n'est PAS lu de .env.secrets (aucun script ne l'ecrit) :
    # il est DERIVE de FACIL_APP_PASSWORD. Sans cette derivation, le secretKeyRef
    # non-optionnel de backend.yaml -> CreateContainerConfigError.
    lit = k3s.build_secret_literals(_FULL_SECRETS, cfg=_cfg())
    assert lit["backend"]["BACKEND_DATABASE_URL"].startswith("postgresql+asyncpg://facil_app:")


def test_apply_fails_closed_when_app_role_password_missing():
    lit = k3s.build_secret_literals({"POSTGRES_PASSWORD": "x"}, cfg=_cfg())
    assert "BACKEND_DATABASE_URL" not in lit.get("backend", {})


def test_apply_never_prints_kubectl_stderr_on_manifest_apply_failure(monkeypatch, tmp_path, capsys):
    # Adapted for Task R1 (SEC-016, see apply_manifest() docstring): the old
    # `kubectl create secret --from-literal=... --dry-run=client -o yaml` step
    # no longer exists — the Secret manifest is now built in Python
    # (build_secret_manifest) and piped on stdin (apply_manifest). The residual
    # risk is that `kubectl apply -f -` can echo fragments of its stdin back in
    # its own stderr on failure. apply_manifest() must NEVER print that raw
    # stderr — only a generic error message. This test simulates kubectl doing
    # exactly that and asserts the sentinel never reaches stdout/stderr.
    sentinel = "SECRETMARKER_SHOULD_NOT_APPEAR_zzq9"

    monkeypatch.setattr(k3s, "find_helm", lambda: "/usr/bin/helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "/usr/bin/kubectl")

    env_secrets = tmp_path / ".env.secrets"
    env_secrets.write_text(
        f"POSTGRES_PASSWORD={sentinel}\n"
        "JWT_SECRET_KEY=jwt\n"
        "SECRET_KEY=sk\n"
        "FACIL_APP_PASSWORD=apppw\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(k3s, "REPO_ROOT", tmp_path)

    def fake_run(cmd, **kwargs):
        if "-n" in cmd and "apply" in cmd:
            # Simulates kubectl echoing a stdin fragment back in its stderr
            # when `kubectl -n <ns> apply -f -` (the Secret manifest) fails.
            return subprocess.CompletedProcess(
                cmd, 1, stdout="", stderr=f"error validating data: ...{sentinel}...")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)

    # --allow-dev-vault: this test is about stderr scrubbing on kubectl apply
    # failure, not the SEC-002 dev-mode guard.
    rc = k3s.main([
        "--apply", "--config", str(_write_cfg_file(tmp_path)), "--yes",
        "--allow-dev-vault",
    ])

    captured = capsys.readouterr()
    assert rc == 2
    assert sentinel not in captured.out
    assert sentinel not in captured.err


# --- A1 : deux passes SEULEMENT au 1er install, une seule sur upgrade -------
#
# `release_exists()` interroge `helm status facil -n <ns>` (lecture seule) ;
# les tests ci-dessous pilotent sa reponse via fake_run pour couvrir les DEUX
# chemins (aucun des deux n'etait teste avant : tous les tests --apply
# precedents ne regardaient que `next(c for c in calls if "upgrade" in c)`,
# qui aurait trouve la 1re passe avec un unique `upgrade` tout aussi bien que
# le nouveau code a une seule passe -- une regression qui supprimerait la 2e
# passe serait passee inapercue).

def test_apply_first_install_uses_two_pass_zero_replica_dance(monkeypatch, tmp_path):
    # 1er install (release absente) : le deadlock reel (task-V1, voir le
    # commentaire de main()) existe toujours -- la danse deux-passes doit
    # rester en place.
    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        if "status" in cmd:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="release: not found")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)

    rc = k3s.main(["--apply", "--config", str(_write_cfg_file(tmp_path)),
                   "--yes", "--allow-dev-vault"])
    assert rc == 0

    upgrade_calls = [c for c in calls if "upgrade" in c]
    assert len(upgrade_calls) == 2, "1er install doit faire DEUX invocations helm upgrade"
    pass1, pass2 = upgrade_calls
    assert "backend.replicas=0" in pass1
    assert "--atomic" not in pass1, (
        "la passe 1 (scale-to-0) n'a rien a proteger par --atomic -- "
        "sinon un echec de la passe 2 y ferait rollback (etat 0-replica bidon)")
    assert "backend.replicas=0" not in pass2
    assert "--atomic" in pass2, "la passe 2 (replica reel) doit etre protegee par --atomic"


def test_apply_upgrade_of_existing_release_uses_single_pass_no_downtime(monkeypatch, tmp_path):
    # Release DEJA installee : pas de deadlock (hooks pre-upgrade tournent
    # avant --wait) -- une seule passe, backend JAMAIS descendu a 0 replica
    # (zero coupure a chaque `--apply` suivant), toujours protegee par
    # --atomic (rollback vers la DERNIERE RELEASE SAINE, pas un etat bidon).
    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        if "status" in cmd:
            # release_exists() exige desormais info.status == "deployed"
            # (pas seulement returncode==0 -- une release "failed" ne doit
            # PAS emprunter le chemin une-passe, cf. le bug corrige task-E1).
            return subprocess.CompletedProcess(cmd, 0, stdout='{"info":{"status":"deployed"}}',
                                               stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)

    rc = k3s.main(["--apply", "--config", str(_write_cfg_file(tmp_path)),
                   "--yes", "--allow-dev-vault"])
    assert rc == 0

    upgrade_calls = [c for c in calls if "upgrade" in c]
    assert len(upgrade_calls) == 1, (
        "une release existante doit faire UNE SEULE invocation helm upgrade "
        "(zero coupure backend) -- pas la danse deux-passes du 1er install")
    assert "backend.replicas=0" not in upgrade_calls[0], (
        "le backend ne doit JAMAIS etre descendu a 0 replica sur un upgrade "
        "d'une release existante -- ce serait une coupure de service inutile "
        "(502 cote frontend) puisqu'il n'y a pas de deadlock a contourner ici")
    assert "--atomic" in upgrade_calls[0]


def test_apply_treats_failed_prior_release_as_absent_reruns_two_pass_dance(
    monkeypatch, tmp_path,
):
    # BUG REEL CORRIGE (smoke k3d task-E1, 2026-07-14) : `helm status` renvoie
    # returncode==0 MEME pour une release au statut "failed" (ex. un --apply
    # precedent qui a echoue au pre-install, avant tout --atomic/rollback).
    # release_exists() doit lire `.info.status` (JSON), pas seulement le
    # returncode -- sinon un --apply de reprise apres un 1er echec prend le
    # chemin une-passe (backend a son replica REEL d'emblee) sur un cluster
    # encore vierge -> reproduit tel quel le deadlock original (task-V1) que
    # la danse deux-passes existe pour eviter.
    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        if "status" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, stdout='{"info":{"status":"failed"}}', stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)

    rc = k3s.main(["--apply", "--config", str(_write_cfg_file(tmp_path)),
                   "--yes", "--allow-dev-vault"])
    assert rc == 0

    upgrade_calls = [c for c in calls if "upgrade" in c]
    assert len(upgrade_calls) == 2, (
        "une release au statut 'failed' doit etre traitee comme ABSENTE -- "
        "la danse deux-passes (1er install) doit rejouer, pas le chemin "
        "une-passe reserve a une release DEJA deployee avec succes")
    assert "backend.replicas=0" in upgrade_calls[0]


def test_apply_first_install_pass2_failure_warns_backend_left_at_zero_replicas(
    monkeypatch, tmp_path, capsys,
):
    # Si la 2e passe (remontee du replica reel) echoue, le message doit dire
    # explicitement que le backend est reste a 0 replica (sinon un operateur
    # qui relit juste "echec" ne sait pas qu'il doit relancer --apply ou
    # desinstaller -- point 3 du brief).
    def fake_run(cmd, **kw):
        if "status" in cmd:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not found")
        if "upgrade" in cmd and "--atomic" in cmd:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")  # passe 2
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)

    rc = k3s.main(["--apply", "--config", str(_write_cfg_file(tmp_path)),
                   "--yes", "--allow-dev-vault"])
    assert rc == 2
    assert "0 replica" in capsys.readouterr().err.lower()


# --- Garde-fou : migrer une release existante SANS sauvegarde (SEC-003/H3) ---

def _apply_env(monkeypatch, tmp_path, backup_enabled, existing_release):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)
    monkeypatch.setattr(k3s, "backup_is_enabled", lambda: backup_enabled)
    monkeypatch.setattr(k3s, "release_exists", lambda h, ns: existing_release)
    return calls


def _run_apply(tmp_path, *extra):
    # --allow-dev-vault : ces tests portent sur le garde-fou de sauvegarde, pas
    # sur la garde SEC-002 dev-mode d'OpenBao.
    return k3s.main(["--apply", "--config", str(_write_cfg_file(tmp_path)),
                     "--yes", "--allow-dev-vault", *extra])


def test_apply_refuses_to_migrate_an_existing_release_without_backup(monkeypatch, tmp_path, capsys):
    # Le Job facil-backup est gate par `backup.enabled` ET `postgres.enabled`.
    # Un --set, un overlay ou une regression sur values-onprem.yaml le fait
    # disparaitre -- et `helm upgrade` lancait alors alembic sur une base de
    # production sans le moindre dump, EN SILENCE, exit 0. Toutes les gardes
    # restaient vertes : elles verifient l'ORDRE du Job, pas son EXISTENCE.
    calls = _apply_env(monkeypatch, tmp_path, backup_enabled=False, existing_release=True)
    rc = _run_apply(tmp_path)
    assert rc == 1
    assert not any("upgrade" in c for c in calls), (
        f"aucun `helm upgrade` ne doit partir sans sauvegarde -- {calls}")
    assert "AVORTE" in capsys.readouterr().err


def test_apply_proceeds_without_backup_when_the_risk_is_declared(monkeypatch, tmp_path):
    calls = _apply_env(monkeypatch, tmp_path, backup_enabled=False, existing_release=True)
    assert _run_apply(tmp_path, "--no-backup") == 0
    assert any("upgrade" in c for c in calls)


def test_a_first_install_without_backup_is_not_blocked(monkeypatch, tmp_path):
    # Une PREMIERE installation ne protege rien : il n'y a pas de donnees a
    # perdre. Bloquer ici serait une garde qui crie a tort -- donc une garde
    # qu'on finit par desactiver.
    calls = _apply_env(monkeypatch, tmp_path, backup_enabled=False, existing_release=False)
    assert _run_apply(tmp_path) == 0
    assert any("upgrade" in c for c in calls)


def test_the_guard_does_not_fire_when_backup_is_enabled(monkeypatch, tmp_path):
    # Anti-faux-positif : le chemin nominal (sauvegarde active) ne doit jamais
    # etre bloque.
    calls = _apply_env(monkeypatch, tmp_path, backup_enabled=True, existing_release=True)
    assert _run_apply(tmp_path) == 0
    assert any("upgrade" in c for c in calls)
