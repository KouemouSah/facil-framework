"""Regression guard: no constant-delimiter heredoc writing to $GITHUB_OUTPUT.

Background (do not weaken this test to make it pass):

Several PR-triggered workflows build a multiline step output like this:

    STAT=$(git diff ... )
    {
      echo "stat<<EOF"
      echo "$STAT"
      echo "EOF"
    } >> $GITHUB_OUTPUT

`$STAT` (and similar variables holding diff content or the PR body) is
attacker-controlled on any repo that runs workflows against pull requests: an
external contributor fully controls both the PR body and every byte of the
diff. If the opening/closing marker is a constant word such as `EOF`, an
attacker only has to make one line of the diff (or the PR body) read exactly
`EOF` to close the block early. Every line after that is then parsed by the
Actions runner as a *new* step output assignment — i.e. an attacker can forge
arbitrary `key=value` outputs for that step (GitHub Actions "output
injection"; see GitHub's own hardening guide, which mandates a random
delimiter whenever untrusted content is written to $GITHUB_OUTPUT:
https://docs.github.com/actions/security-guides/security-hardening-for-github-actions#preventing-script-injection).

The fix is to derive the delimiter from a value generated at run time (e.g.
``DELIM="ghout_$(openssl rand -hex 16)"``) so an attacker cannot predict, and
therefore cannot forge, the closing marker.

This test scans every workflow file for the vulnerable pattern and fails if
it reappears. It intentionally skips comment lines (lines whose stripped form
starts with ``#``) so that prose explaining this exact bug class (which must
say words like "EOF" to be readable) never trips the guard.
"""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"

# Captures the token immediately following `<<` (optionally quoted), whether
# it's a bare word (constant delimiter, e.g. EOF) or a shell variable
# reference (e.g. $DELIM, ${DELIM}) -- the latter is fine, the former is not.
_HEREDOC_MARKER_RE = re.compile(r'<<-?\s*"?(\$\{?\w+\}?|\w+)"?')


def _workflow_files() -> list[Path]:
    if not WORKFLOWS_DIR.is_dir():
        return []
    return sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.yaml"))


def _code_lines(text: str):
    """Yield (lineno, line) skipping pure comment lines (YAML or shell both
    use '#'), so this guard never fires on prose that merely *mentions* the
    bug pattern to explain it."""
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.strip().startswith("#"):
            continue
        yield lineno, line


def _find_constant_delimiter_offenses(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if "GITHUB_OUTPUT" not in text:
        return []  # this file never writes step outputs -- irrelevant

    offenses = []
    for lineno, line in _code_lines(text):
        if "<<" not in line:
            continue
        for marker in _HEREDOC_MARKER_RE.findall(line):
            if marker.startswith("$"):
                continue  # derived from a variable at run time: safe
            offenses.append(
                f"{path.name}:{lineno}: constant heredoc delimiter {marker!r} "
                f"used alongside $GITHUB_OUTPUT -> {line.strip()!r}"
            )
    return offenses


def test_no_constant_delimiter_writes_to_github_output():
    workflows = _workflow_files()
    assert workflows, f"expected workflow files under {WORKFLOWS_DIR}"

    offenders: list[str] = []
    for path in workflows:
        offenders.extend(_find_constant_delimiter_offenses(path))

    assert not offenders, (
        "Constant heredoc delimiter found writing to $GITHUB_OUTPUT (output "
        "injection risk -- PR diff/body content can forge step outputs). "
        "Use a per-run random delimiter instead, e.g. "
        'DELIM="ghout_$(openssl rand -hex 16)" and reference it as $DELIM:\n'
        + "\n".join(offenders)
    )
