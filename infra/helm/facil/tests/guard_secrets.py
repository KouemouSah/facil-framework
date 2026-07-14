#!/usr/bin/env python3
"""Garde-secret PARSEE sur le rendu `helm template` (remplace un grep contournable).

Invariants verifies sur TOUS les conteneurs (init inclus) de TOUS les manifests :
  1. toute env var dont le nom evoque un credential DOIT venir de `valueFrom`
     (secretKeyRef), jamais d'un `value:` litteral ;
  2. aucune URL ne porte de credential inline (`scheme://user:pass@host`), sauf
     interpolation k8s `$(VAR)` -- qui, elle, resout depuis un secretKeyRef ;
  3. le chart ne definit AUCUN `kind: Secret` (les Secrets sont crees hors Helm
     par deploy/providers/k3s.py -- sinon les valeurs finiraient versionnees) ;
  4. aucun `command`/`args` de conteneur ne porte un flag/assignation CONNU
     pour vehiculer un credential en clair (CWE-214 -- redis.yaml en portait
     un jusqu'a ce correctif : `redis-server --requirepass "$REDIS_PASSWORD"`
     interpole AVANT l'exec, la valeur finit dans l'argv du process resultant,
     lisible via /proc/<pid>/cmdline par tout process co-localise / EDR /
     scraper d'audit -- meme canal deja ferme trois fois sur ce projet,
     `kubectl create secret --from-literal` puis `psql -v app_pw=` puis
     `redis-server --requirepass`). L'ancienne garde (`test_render.sh`) ne
     cherchait que `-v app_pw=` -- structurellement incapable d'attraper une
     AUTRE forme du meme canal (ex. `--requirepass`). Voir
     CREDENTIAL_ARGV_MARKERS/CREDENTIAL_ARGV_FLAG_PATTERNS : denylist OUVERTE
     de motifs connus, pas une analyse exhaustive -- defense en profondeur,
     pas une preuve d'absence (un futur programme avec un flag inedit
     resterait un angle mort tant qu'il n'est pas ajoute ici). Une revue a
     d'ailleurs demontre 3 contournements de la denylist initiale (voir
     test_bypass1/2/3_* dans test_guard_secrets.py) : `-a"$VAR"` accole sans
     espace (le marqueur substring `"-a "` suppose a tort un espace litteral),
     une connection string inline dans l'argv (INLINE_CRED_RE n'etait
     applique qu'aux `env[].value`), et `--pass` (absent de la liste).

L'ancienne garde (grep) ratait : les connection strings (REDIS_URL/DATABASE_URL
rendent en `value:`, jamais verifiees -- faux negatif le plus dangereux), ne
couvrait que 4 cles figees, ne regardait qu'UNE ligne apres `- name:` (un
commentaire YAML intercale la contournait), et ne matchait pas le style flow
(`{name: X, value: y}`) que le chart utilise deja ailleurs. Voir
tests/test_guard_secrets.py pour la preuve par mutation de chaque invariant.

Usage : helm template ... | python guard_secrets.py
Exit 0 = propre, 1 = fuite.
"""
from __future__ import annotations

import re
import sys

import yaml

# Un nom d'env var qui evoque un credential. Suffisamment large pour couvrir les
# ajouts futurs (le point aveugle de l'ancienne garde : une liste de 4 cles figee).
CREDENTIAL_RE = re.compile(
    r"(PASSWORD|PASSWD|SECRET|TOKEN|_KEY$|APIKEY|API_KEY|CREDENTIAL|_URL$|_DSN$)",
    re.I,
)

# Env vars a `value:` litteral autorisees malgre un nom credential-like : ce
# sont des URLs SANS credential embarque (nom de service + port). Toute
# addition ici DOIT etre justifiee -- une entree qui ne correspond a AUCUNE env
# var du rendu reel est un defaut symetrique ("un test qui ne peut pas echouer
# est un defaut grave" s'applique aussi a une allowlist jamais exercee).
# Verifie contre le rendu reel (helm template) : voir
# test_every_allowlist_entry_is_load_bearing dans test_guard_secrets.py, qui
# echouerait si une de ces entrees devenait morte.
ALLOWED_LITERAL = {
    # frontend.yaml -> `http://facil-backend:8080` : nom de service k8s + port
    # interne, pas de user:pass@. Matche `_URL$` a cause du NOM de la variable,
    # mais ce n'est pas un secret -- c'est juste l'URL backend<->frontend, et
    # elle ne peut techniquement pas venir d'un secretKeyRef (rien a y stocker).
    "INTERNAL_API_URL",
}
# credential inline dans une URL : scheme://user:pass@host (hors interpolation
# $(VAR)). Le nom d'utilisateur est OPTIONNEL (`*`, pas `+`) : nos URLs Redis
# rendent en `redis://:PASSWORD@host` (convention redis -- pas de username),
# et un `+` laissait passer sans le detecter la mutation `redis://:hunter2@...`
# (capturee par TDD : voir test_catches_inline_credential_in_redis_url).
INLINE_CRED_RE = re.compile(r"://[^/\s:]*:(?!\$\()[^/\s@]+@")

# Denylist OUVERTE (pas une liste exhaustive) de motifs connus pour faire
# transiter un credential par l'argv d'un process (CWE-214), quel que soit le
# programme -- shell interpole la variable AVANT l'exec, la valeur finit dans
# l'argv du process resultant. Chaque entree est un substring simple (pas de
# regex) : ces scripts sont ecrits par nous, pas du texte arbitraire a
# parser -- meme convention que ALLOWED_LITERAL ci-dessus.
CREDENTIAL_ARGV_MARKERS = (
    "--requirepass",   # redis-server (CLI) -- corrige dans redis.yaml (ce commit)
    "--password",      # psql/mysqladmin/... forme longue generique
    "--pass",          # forme longue courte generique (ex. `mytool --pass "$SECRET"`)
    "-v app_pw=",      # psql -v (deja ferme dans db-role-job.yaml -- garde de non-regression)
    "PGPASSWORD=",     # assignation d'env INLINE dans la ligne de commande (PGPASSWORD=x psql ...)
)

# `-a`/`-p` sont des flags CLI courts qui vehiculent un credential quand une
# valeur les suit IMMEDIATEMENT (`redis-cli -a "$PW"`, `redis-cli -a"$PW"`,
# `mysql -p"$PW"`, `mysql -p$PW`) -- redis-cli utilise `-a`, mysql utilise
# `-p` (PAS `-a` : cote client mysql, `-a` signifie mode ANSI, pas un mdp).
# Mais `-a`/`-p` sont AUSSI des flags legitimes tres courants sans valeur
# credential qui suit immediatement (`tar -a`, `cp -a`, `ls -a`,
# `docker run -p 8080:80`) -- un simple substring `"-a "` les confondrait (et
# les confondait : voir infra-debt-report.md, contournement demontre en
# revue). On exige donc qu'un guillemet ou un `$` (forme quasi systematique
# d'une valeur credential interpolee par un shell) suive IMMEDIATEMENT le
# flag -- accole (`-a"$PW"`, `-a$PW`) ou apres un espace (`-a "$PW"`,
# `-a $PW`) -- jamais un flag isole ou suivi d'un argument/port ordinaire
# (`-a`, `-a -czf`, `-p 8080:80`, `-a /path`).
CREDENTIAL_ARGV_FLAG_PATTERNS = (
    ("-a ", re.compile(r'(?:^|\s)-a\s*["\'$]')),   # redis-cli -a"$PW" / -a $PW / -a "$PW"
    ("-p ", re.compile(r'(?:^|\s)-p\s*["\'$]')),   # mysql -p"$PW" / -p$PW / -p "$PW"
)


def _container_argv_text(c: dict) -> str:
    """Concatene `command` + `args` d'un conteneur en un seul texte -- les deux
    sont des listes de chaines (parfois un script multi-lignes complet dans un
    seul element `args[0]`, ex. redis.yaml/db-role-job.yaml)."""
    parts: list[str] = []
    for key in ("command", "args"):
        val = c.get(key)
        if isinstance(val, list):
            parts.extend(str(v) for v in val)
        elif isinstance(val, str):
            parts.append(val)
    return "\n".join(parts)


def iter_containers(doc: dict):
    spec = (doc.get("spec") or {})
    tmpl = (spec.get("template") or {}).get("spec") or spec
    for key in ("containers", "initContainers"):
        for c in (tmpl.get(key) or []):
            yield c


def check(stream: str) -> list[str]:
    problems: list[str] = []
    for doc in yaml.safe_load_all(stream):
        if not isinstance(doc, dict):
            continue
        kind = doc.get("kind", "")
        name = (doc.get("metadata") or {}).get("name", "?")

        if kind == "Secret":
            problems.append(
                f"{name}: le chart definit un `kind: Secret` -- interdit. Les Secrets "
                f"sont crees hors Helm par deploy/providers/k3s.py.")

        for c in iter_containers(doc):
            for env in (c.get("env") or []):
                ename, val = env.get("name", ""), env.get("value")
                if val is None:
                    continue  # valueFrom -> conforme
                val = str(val)
                if CREDENTIAL_RE.search(ename) and ename not in ALLOWED_LITERAL:
                    if not INLINE_CRED_RE.search(val) and "$(" not in val:
                        problems.append(
                            f"{name}/{c.get('name')}: env `{ename}` a un `value:` "
                            f"litteral alors que son nom evoque un credential.")
                if INLINE_CRED_RE.search(val):
                    problems.append(
                        f"{name}/{c.get('name')}: credential inline dans l'URL de "
                        f"`{ename}` (attendu : $(VAR) resolue depuis un secretKeyRef).")

            argv_text = _container_argv_text(c)
            for marker in CREDENTIAL_ARGV_MARKERS:
                if marker in argv_text:
                    problems.append(
                        f"{name}/{c.get('name')}: command/args contient `{marker}` "
                        f"-- motif connu pour vehiculer un credential en argv "
                        f"(CWE-214), lisible via /proc/<pid>/cmdline par tout "
                        f"process co-localise.")
            for label, pattern in CREDENTIAL_ARGV_FLAG_PATTERNS:
                if pattern.search(argv_text):
                    problems.append(
                        f"{name}/{c.get('name')}: command/args contient `{label}` "
                        f"suivi immediatement d'une valeur (guillemet/`$`) "
                        f"-- motif connu pour vehiculer un credential en argv "
                        f"(CWE-214), lisible via /proc/<pid>/cmdline par tout "
                        f"process co-localise.")
            if INLINE_CRED_RE.search(argv_text):
                problems.append(
                    f"{name}/{c.get('name')}: credential inline dans une URL "
                    f"passee en command/args (scheme://user:pass@host) -- "
                    f"meme risque CWE-214 qu'un `value:` d'env litteral.")
    return problems


if __name__ == "__main__":
    found = check(sys.stdin.read())
    if found:
        print("FAIL garde-secret (parsee) :", file=sys.stderr)
        for p in found:
            print(f"  - {p}", file=sys.stderr)
        raise SystemExit(1)
    print("OK garde-secret (parsee)")
