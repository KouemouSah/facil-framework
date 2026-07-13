#!/usr/bin/env python3
"""Tests for deploy/providers/k3s.py (Helm values render + Secret allowlist).

No live cluster required: render_values()/build_secret_literals() are pure
functions; --validate/--plan are exercised via helm (present on PATH) with
subprocess mocked out where a real helm invocation isn't the point of the test.
"""
from __future__ import annotations

import base64
import subprocess
import sys
from pathlib import Path

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
    # Secret guard: the values dict must carry NO secret value AND no secret
    # *name* override either (SEC-001, S1): render_values() no longer sets
    # "secretName"/"secretNames" at all — the chart's own values.yaml defaults
    # (one Secret name per component) already match k3s.SECRET_NAMES, so no
    # --set is needed for them.
    values = k3s.render_values(_cfg())
    flat = repr(values).lower()
    assert "password" not in flat
    assert "secretname" not in flat


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


def test_values_onprem_file_exists_and_has_no_secret():
    # Referenced by --plan/--apply (-f overlay) and by the CI workflow
    # (task 1.11) — must exist at this exact path, secret-free.
    path = k3s.REPO_ROOT / "infra" / "helm" / "facil" / "values-onprem.yaml"
    assert path.exists()
    text = path.read_text(encoding="utf-8").lower()
    for banned in ("password", "secret_key", "token", "root_token"):
        assert banned not in text.replace("devmode", "")


def test_plan_passes_values_onprem_overlay_to_helm_template(monkeypatch):
    captured_cmds = []

    def fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(k3s, "find_helm", lambda: "/usr/bin/helm")
    monkeypatch.setattr(k3s.subprocess, "run", fake_run)

    rc = k3s.main(["--plan", "--config", str(PROVIDERS_DIR.parent / "config.yaml")])

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

    rc = k3s.main(["--apply", "--config", str(PROVIDERS_DIR.parent / "config.yaml"), "--yes"])

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
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(k3s.subprocess, "run", fake_run)
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)
    k3s.main(["--apply", "--yes"])

    joined = [" ".join(c) for c in calls]
    ns_idx = next(i for i, c in enumerate(joined) if "create namespace" in c or "namespace facil" in c)
    # Cible le VRAI apply du Secret : c'est le seul appel qui porte a la fois
    # "-n" (namespace explicite) ET "apply" dans sa liste d'argv. Le
    # `kubectl apply -f -` interne a ensure_namespace() (application du
    # Namespace rendu) n'a PAS de "-n" -- filtrer sur la liste evite de le
    # confondre avec l'apply du Secret (cf. test ci-dessous qui fait pareil).
    sec_idx = next(i for i, c in enumerate(calls) if "-n" in c and "apply" in c)
    assert ns_idx < sec_idx, "le namespace doit etre cree AVANT le Secret"


def test_plan_renders_in_the_target_namespace(monkeypatch):
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
    k3s.main(["--plan", "--namespace", "custom-ns"])
    cmd = calls[0]
    n_idx = cmd.index("-n")
    assert cmd[n_idx + 1] == "custom-ns", "-n doit etre immediatement suivi de args.namespace"


def test_apply_uses_atomic_for_auto_rollback(monkeypatch):
    # SEC-022 : sans --atomic une release en echec reste en place, pods casses.
    calls = []
    monkeypatch.setattr(k3s.subprocess, "run",
                        lambda cmd, **kw: calls.append(list(cmd)) or
                        subprocess.CompletedProcess(cmd, 0, stdout=""))
    monkeypatch.setattr(k3s, "find_helm", lambda: "helm")
    monkeypatch.setattr(k3s, "find_kubectl", lambda: "kubectl")
    monkeypatch.setattr(k3s, "_load_env_secrets", lambda p: _FULL_SECRETS)
    k3s.main(["--apply", "--yes"])
    upgrade = next(c for c in calls if "upgrade" in c)
    assert "--atomic" in upgrade


def test_secret_values_never_appear_in_any_process_argv(monkeypatch):
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
    k3s.main(["--apply", "--yes"])

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

    rc = k3s.main([
        "--apply", "--config", str(PROVIDERS_DIR.parent / "config.yaml"), "--yes",
    ])

    captured = capsys.readouterr()
    assert rc == 2
    assert sentinel not in captured.out
    assert sentinel not in captured.err
