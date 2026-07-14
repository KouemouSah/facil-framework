"""Interdit le retour de la course « broken pipe » dans test_render.sh.

Bug reel (CI develop, 2026-07-14) :

    infra/helm/facil/tests/test_render.sh: line 37: echo: write error: Broken pipe
    ##[error]Process completed with exit code 1.

`grep -q` (comme `awk ... { exit }`) s'arrete des la premiere correspondance et
ferme son entree. L'ecrivain en amont (`echo "$OUT"`, `printf '%s' "$OUT"`) n'a
pas fini d'ecrire : il recoit un EPIPE. Sous `set -euo pipefail`, le pipeline
entier est declare en echec.

Le declenchement depend de la taille des tampons et du timing -- donc le test
echouait AU HASARD : vert sur la PR, rouge sur develop, sur exactement le meme
code. Un test qui echoue aleatoirement finit par etre relance sans reflechir :
il ne garde plus rien, tout en coutant du temps a chaque fois.

Correctif : le rendu `helm template` est ecrit UNE FOIS dans un fichier
(`$OUT_FILE`) et toutes les assertions lisent ce fichier. Pas d'ecrivain, donc
pas de course.

Ce test empeche la reintroduction du motif.
"""
from __future__ import annotations

import re
from pathlib import Path

RENDER_SH = Path(__file__).resolve().parent / "test_render.sh"

# Un ecrivain qui alimente un consommateur susceptible de sortir tot.
# `grep -q`, `grep -m N`, `head`, `awk ... exit` ferment tous l'entree d'un coup.
PIPE_WRITER_RE = re.compile(
    r'(?:echo|printf|cat)\s+[^|\n]*"\$OUT"[^|\n]*\|',
)


def test_render_sh_never_pipes_the_render_into_a_command() -> None:
    body = RENDER_SH.read_text(encoding="utf-8")
    offenders = [
        f"{i}: {line.strip()}"
        for i, line in enumerate(body.splitlines(), start=1)
        # Les commentaires ne s'executent pas : ceux qui CITENT le motif interdit
        # (pour expliquer pourquoi il l'est) ne doivent pas faire rougir la garde.
        # Sinon on est pousse a supprimer l'explication pour faire passer le test --
        # exactement le reflexe qui fait perdre la memoire d'un bug.
        if not line.lstrip().startswith("#") and PIPE_WRITER_RE.search(line)
    ]
    assert not offenders, (
        "test_render.sh repipe le rendu dans une commande — course EPIPE possible "
        "(`grep -q` sort tot et ferme le tuyau ; sous `set -euo pipefail` le script "
        "meurt, de facon NON DETERMINISTE). Lire \"$OUT_FILE\" a la place.\n  "
        + "\n  ".join(offenders)
    )


def test_render_sh_materialises_the_render_into_a_file() -> None:
    # Le corollaire : le fichier doit bien exister, sinon les assertions lisent du vide
    # et passent toutes... pour de mauvaises raisons.
    body = RENDER_SH.read_text(encoding="utf-8")
    assert 'OUT_FILE="$(mktemp)"' in body
    assert 'printf \'%s\\n\' "$OUT" > "$OUT_FILE"' in body
    assert 'trap \'rm -f "$OUT_FILE"\' EXIT' in body, "le fichier temporaire doit etre nettoye"
