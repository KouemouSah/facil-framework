"""Tests TDD pour la garde-secret PARSEE (SEC-009) — infra/helm/facil/tests/guard_secrets.py.

Remplace l'ancienne garde en grep (faux negatifs documentes dans
test_render.sh avant ce commit) : couverture partielle (4 cles), connection
strings jamais verifiees, `grep -A1` contournable par un commentaire YAML
intercale, style flow non matche.

Chaque invariant ci-dessous est prouve par MUTATION (on fabrique la
regression et on verifie que la garde rougit) -- pas seulement par un rendu
propre qui passe: "un test qui ne peut pas echouer est un defaut grave".
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).parent
CHART_DIR = TESTS_DIR.parent
REPO_ROOT = CHART_DIR.parent.parent.parent

sys.path.insert(0, str(TESTS_DIR))
import guard_secrets  # noqa: E402


def _helm_template(*extra_args: str) -> str:
    cmd = ["helm", "template", "rel", str(CHART_DIR), *extra_args]
    result = subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return result.stdout


@pytest.fixture(scope="module")
def default_render() -> str:
    return _helm_template()


# --- Invariant 1 : rendu reel propre -----------------------------------------

def test_clean_default_render_has_no_problems(default_render):
    assert guard_secrets.check(default_render) == []


def test_clean_onprem_overlay_render_has_no_problems():
    rendered = _helm_template("-f", str(CHART_DIR / "values-onprem.yaml"))
    assert guard_secrets.check(rendered) == []


# --- Invariant 2 : credential inline dans une connection string -------------
# Le faux negatif le plus dangereux de l'ancienne garde : REDIS_URL/DATABASE_URL
# rendent en `value:` (interpolation $(VAR)) et n'etaient JAMAIS verifies.

def test_catches_inline_credential_in_redis_url(default_render):
    mutated = default_render.replace("$(REDIS_PASSWORD)", "hunter2")
    problems = guard_secrets.check(mutated)
    assert any("REDIS_URL" in p and "credential inline" in p for p in problems), problems


def test_catches_inline_credential_in_db_init_database_url(default_render):
    mutated = default_render.replace("$(POSTGRES_PASSWORD)", "hunter2")
    problems = guard_secrets.check(mutated)
    assert any("DATABASE_URL" in p and "credential inline" in p for p in problems), problems


def test_k8s_interpolation_dollar_paren_is_not_a_false_positive(default_render):
    # $(REDIS_PASSWORD) resout depuis un secretKeyRef -- ce n'est PAS un
    # credential inline. Non-regression du test precedent : le rendu propre
    # (fixture) contient deja ce pattern et doit rester silencieux (couvert par
    # test_clean_default_render_has_no_problems, réaffirmé ici explicitement).
    assert "$(REDIS_PASSWORD)" in default_render
    assert guard_secrets.check(default_render) == []


# --- Invariant 3 : env var credential-like en `value:` litteral -------------

def test_catches_credential_like_env_var_as_literal_value():
    doc = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: evil
spec:
  template:
    spec:
      containers:
        - name: evil
          env:
            - name: API_SECRET_TOKEN
              value: "sk-literal-leak-123"
"""
    problems = guard_secrets.check(doc)
    assert any("API_SECRET_TOKEN" in p and "litteral" in p for p in problems), problems


def test_valuefrom_secretkeyref_is_never_flagged():
    doc = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fine
spec:
  template:
    spec:
      containers:
        - name: fine
          env:
            - name: API_SECRET_TOKEN
              valueFrom:
                secretKeyRef: { name: some-secret, key: API_SECRET_TOKEN }
"""
    assert guard_secrets.check(doc) == []


# --- Invariant 4 : kind: Secret interdit dans le chart ----------------------

def test_catches_kind_secret_defined_in_chart():
    doc = """
apiVersion: v1
kind: Secret
metadata:
  name: facil-leaked-secret
data:
  password: aHVudGVyMg==
"""
    problems = guard_secrets.check(doc)
    assert any("kind: Secret" in p for p in problems), problems


def test_no_kind_secret_in_real_chart(default_render):
    assert "kind: Secret" not in default_render


# --- Contournements de l'ancienne garde qui ne doivent PLUS marcher ---------

def test_yaml_comment_between_name_and_value_does_not_bypass():
    # L'ancienne garde grep -A1 ne regardait qu'UNE ligne apres `- name:` --
    # un commentaire intercale la contournait.
    doc = """
apiVersion: v1
kind: Pod
spec:
  containers:
    - name: evil
      env:
        - name: DB_PASSWORD
          # commentaire intercale -- contournait grep -A1
          value: "leaked123"
"""
    problems = guard_secrets.check(doc)
    assert any("DB_PASSWORD" in p for p in problems), problems


def test_flow_style_env_entry_is_not_bypassed():
    # Style flow ({name: X, value: y}) deja utilise ailleurs dans le chart
    # (secretKeyRef: { name: ..., key: ... }) -- yaml.safe_load normalise flow
    # et block au meme dict Python, donc aucun contournement possible ici.
    doc = "apiVersion: v1\nkind: Pod\nspec:\n  containers:\n  - {name: evil, env: [{name: DB_PASSWORD, value: leaked123}]}\n"
    problems = guard_secrets.check(doc)
    assert any("DB_PASSWORD" in p for p in problems), problems


def test_init_containers_are_checked_too():
    doc = """
apiVersion: v1
kind: Pod
spec:
  initContainers:
    - name: evil-init
      env:
        - name: DB_PASSWORD
          value: "leaked123"
  containers:
    - name: main
"""
    problems = guard_secrets.check(doc)
    assert any("DB_PASSWORD" in p for p in problems), problems


# --- Invariant 5 : aucun credential en argv (command/args), CWE-214 --------
# L'ancienne garde (test_render.sh) ne cherchait que `-v app_pw=` -- incapable
# structurellement d'attraper une AUTRE forme du meme canal (ex. redis.yaml
# portait `--requirepass "$REDIS_PASSWORD"` avant ce correctif, jamais
# detecte). Ce parseur verifie une denylist de motifs CONNUS, PAR CONTENEUR.

def test_clean_render_has_no_credential_argv_markers(default_render):
    # Non-regression explicite : le CONTENEUR redis (command/args REELLEMENT
    # parses, pas un grep texte brut -- le commentaire YAML de redis.yaml
    # mentionne lui-meme "--requirepass" en PROSE explicative, ce qui ferait
    # un faux positif sur un grep du rendu entier) ne porte plus le flag CLI.
    docs = list(yaml.safe_load_all(default_render))
    redis_deploy = next(
        d for d in docs if isinstance(d, dict) and d.get("kind") == "Deployment"
        and (d.get("metadata") or {}).get("name") == "facil-redis"
    )
    redis_container = redis_deploy["spec"]["template"]["spec"]["containers"][0]
    assert "--requirepass" not in guard_secrets._container_argv_text(redis_container)
    assert guard_secrets.check(default_render) == []


def test_catches_requirepass_flag_reintroduced_in_redis(default_render):
    # Preuve par mutation sur le rendu REEL : si redis.yaml regressait vers
    # `redis-server --requirepass "$REDIS_PASSWORD"` (l'etat AVANT ce
    # correctif), la garde doit rougir -- meme mecanisme que l'ancien bug.
    mutated = default_render.replace(
        'exec redis-server /tmp/redis.conf',
        'exec redis-server --requirepass "$REDIS_PASSWORD"',
        1,
    )
    assert "--requirepass" in mutated, "mutation non appliquee -- verifier le texte du rendu"
    problems = guard_secrets.check(mutated)
    assert any("facil-redis" in p and "--requirepass" in p for p in problems), problems


def test_catches_requirepass_via_direct_doc_mutation():
    doc = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: evil
spec:
  template:
    spec:
      containers:
        - name: evil
          command: ["sh", "-c", "exec redis-server --requirepass \\"$REDIS_PASSWORD\\""]
"""
    problems = guard_secrets.check(doc)
    assert any("evil/evil" in p and "--requirepass" in p for p in problems), problems


def test_catches_dash_a_flag_with_password():
    doc = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: evil
spec:
  template:
    spec:
      containers:
        - name: evil
          command: ["sh", "-c", "redis-cli -a \\"$REDIS_PASSWORD\\" ping"]
"""
    problems = guard_secrets.check(doc)
    assert any("evil/evil" in p and "-a " in p for p in problems), problems


def test_catches_pgpassword_inline_assignment():
    doc = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: evil
spec:
  template:
    spec:
      containers:
        - name: evil
          command: ["sh", "-c", "PGPASSWORD=\\"$POSTGRES_PASSWORD\\" psql -h db -U app"]
"""
    problems = guard_secrets.check(doc)
    assert any("evil/evil" in p and "PGPASSWORD=" in p for p in problems), problems


def test_catches_app_pw_regression_in_command_form():
    # Garde de non-regression pour le canal deja ferme (db-role-job.yaml) --
    # prouve que guard_secrets.py, et pas seulement le grep de test_render.sh,
    # attraperait aussi ce canal si le fix regressait.
    doc = """
apiVersion: batch/v1
kind: Job
metadata:
  name: evil-job
spec:
  template:
    spec:
      containers:
        - name: evil
          command: ["sh", "-c"]
          args:
            - "psql -v app_pw=\\"$FACIL_APP_PASSWORD\\" -f /sql/role.sql"
"""
    problems = guard_secrets.check(doc)
    assert any("evil-job/evil" in p and "-v app_pw=" in p for p in problems), problems


def test_conf_file_directive_requirepass_without_dashes_is_not_flagged():
    # `requirepass <valeur>` DANS un fichier de conf (ecrit via heredoc/cat,
    # jamais un argument de ligne de commande) n'est PAS le motif banni --
    # seul le flag CLI `--requirepass` (double tiret) l'est. Sans cette
    # distinction, le correctif lui-meme (redis.yaml) se flaggerait.
    doc = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fine
spec:
  template:
    spec:
      containers:
        - name: fine
          command: ["sh", "-c"]
          args:
            - |
              cat > /tmp/redis.conf <<CONF
              requirepass ${REDIS_PASSWORD}
              CONF
              exec redis-server /tmp/redis.conf
"""
    assert guard_secrets.check(doc) == []


# --- Allowlist : chaque entree doit etre load-bearing -----------------------

@pytest.mark.parametrize("entry", sorted(guard_secrets.ALLOWED_LITERAL))
def test_every_allowlist_entry_is_load_bearing(default_render, entry):
    # Si on retire cette entree, le rendu REEL doit se remettre a echouer --
    # sinon l'entree est morte (jamais exercee) et n'est qu'un faux sentiment
    # de securite (cf. CLAUDE.md: "un test qui ne peut pas echouer est un
    # defaut grave" -- s'applique symetriquement a une entree d'allowlist).
    saved = set(guard_secrets.ALLOWED_LITERAL)
    try:
        guard_secrets.ALLOWED_LITERAL.discard(entry)
        problems = guard_secrets.check(default_render)
        assert any(entry in p for p in problems), (
            f"{entry} est dans ALLOWED_LITERAL mais ne correspond a aucune env "
            f"var du rendu reel -- entree morte, a retirer."
        )
    finally:
        guard_secrets.ALLOWED_LITERAL.clear()
        guard_secrets.ALLOWED_LITERAL.update(saved)


# --- Fail-closed quand un composant est desactive ---------------------------

def test_fail_closed_when_minio_disabled_no_crash_no_silent_pass():
    rendered = _helm_template("--set", "minio.enabled=false")
    assert "facil-minio" not in rendered
    # Ne doit pas planter (pas d'exception) ; rien a signaler puisque le
    # composant est absent du rendu -- ce n'est pas "silencieux", c'est correct.
    assert guard_secrets.check(rendered) == []


# --- CLI (stdin) -------------------------------------------------------------

def test_cli_exits_nonzero_and_reports_on_mutation(default_render):
    mutated = default_render.replace("$(REDIS_PASSWORD)", "hunter2")
    result = subprocess.run(
        [sys.executable, str(TESTS_DIR / "guard_secrets.py")],
        input=mutated, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "REDIS_URL" in result.stderr


def test_cli_exits_zero_on_clean_render(default_render):
    result = subprocess.run(
        [sys.executable, str(TESTS_DIR / "guard_secrets.py")],
        input=default_render, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "OK garde-secret" in result.stdout
