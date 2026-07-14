#!/usr/bin/env python3
"""Tests for deploy/scripts/restore_backup.py.

No live cluster required: every kubectl invocation goes through
`restore_backup.subprocess.run`, monkeypatched here (same convention as
deploy/providers/test_k3s.py) -- calls are dispatched by inspecting the argv
each test builds, never a real cluster.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR.parent / "providers"))

import restore_backup as rb  # noqa: E402
import k3s  # noqa: E402

POSTGRES_JSONPATH_OUT = "pgvector/pgvector:pg16|facil|facil"
MINIO_JSONPATH_OUT = "minio/minio@sha256:" + "a" * 64 + "|facil"


def _cp(cmd, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)


def _make_fake_run(*, postgres_ok=True, minio_ok=True, list_output="",
                   restore_logs="", wait_rc=0, restore_wait_rc=None, apply_rc=0,
                   calls=None, container_statuses=""):
    """Builds a dispatching fake for `subprocess.run`, keyed on argv content --
    mirrors deploy/providers/test_k3s.py's fake_run pattern (capture + branch).

    `wait_rc` keeps its old meaning (0=Job succeeds, 1=Job fails), now
    translated into the polled `.status.succeeded`/`.status.failed` jsonpath
    output `_wait_for_job_completion()` reads (A3: no more `kubectl wait
    --for=condition=complete`) -- applied to the LIST_JOB (list_backups()'s
    own Job). `restore_wait_rc` (defaults to `wait_rc` when unset) applies
    independently to the RESTORE_JOB, so a test can simulate the restore Job
    failing WITHOUT starving `list_backups()`'s own "available backups"
    check (called first, from `--restore`, to validate the requested
    timestamp even exists).
    `container_statuses` is the raw jsonpath stdout `_container_exit_summary()`
    reads (e.g. "restore-postgres=0\\nrestore-minio=1\\n")."""
    if calls is None:
        calls = []
    if restore_wait_rc is None:
        restore_wait_rc = wait_rc

    def fake_run(cmd, **kw):
        calls.append((list(cmd), kw.get("input")))
        joined = " ".join(cmd)
        if "get" in cmd and f"statefulset/{rb.POSTGRES_STS}" in cmd:
            if not postgres_ok:
                return _cp(cmd, 1, stderr="not found")
            return _cp(cmd, 0, stdout=POSTGRES_JSONPATH_OUT)
        if "get" in cmd and f"statefulset/{rb.MINIO_STS}" in cmd:
            if not minio_ok:
                return _cp(cmd, 1, stderr="not found")
            return _cp(cmd, 0, stdout=MINIO_JSONPATH_OUT)
        if "get" in cmd and "pods" in cmd:
            return _cp(cmd, 0, stdout=container_statuses)
        if "get" in cmd and any(a.startswith("job/") for a in cmd):
            if f"job/{rb.LIST_JOB}" in joined:
                return _cp(cmd, 0, stdout="1|" if wait_rc == 0 else "|1")
            return _cp(cmd, 0, stdout="1|" if restore_wait_rc == 0 else "|1")
        if "delete" in cmd:
            return _cp(cmd, 0)
        if "apply" in cmd:
            return _cp(cmd, apply_rc)
        if "logs" in cmd:
            if rb.LIST_JOB in joined:
                return _cp(cmd, 0, stdout=list_output)
            return _cp(cmd, 0, stdout=restore_logs)
        raise AssertionError(f"unexpected kubectl invocation: {cmd}")

    return fake_run, calls


def _patch_kubectl(monkeypatch, fake_run):
    monkeypatch.setattr(rb.subprocess, "run", fake_run)
    monkeypatch.setattr(rb, "find_kubectl", lambda: "kubectl")


# --- A3: _parse_timeout_seconds / _wait_for_job_completion / per-container --

def test_parse_timeout_seconds_parses_seconds_minutes_hours():
    assert rb._parse_timeout_seconds("120s") == 120
    assert rb._parse_timeout_seconds("15m") == 900
    assert rb._parse_timeout_seconds("1h") == 3600


def test_parse_timeout_seconds_rejects_bad_format():
    with pytest.raises(ValueError):
        rb._parse_timeout_seconds("not-a-timeout")


def test_wait_for_job_completion_detects_failure_without_waiting_full_timeout(monkeypatch):
    # BUG REEL CORRIGE (A3) : `kubectl wait --for=condition=complete` seul
    # n'ecoute PAS `condition=failed` -- l'operateur attendait le timeout
    # COMPLET avant d'apprendre l'echec. La preuve directe : un `sleep_fn`
    # qui leve si jamais appele -- si le code pollait au lieu de rapporter
    # l'echec des le premier `.status.failed`, ce test planterait.
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, stdout="|1", stderr="")

    def sleep_must_not_be_called(_seconds):
        raise AssertionError("ne doit jamais dormir : l'echec est deja connu au 1er poll")

    monkeypatch.setattr(rb.subprocess, "run", fake_run)
    ok = rb._wait_for_job_completion(
        "kubectl", "facil", "some-job", timeout_seconds=900,
        sleep_fn=sleep_must_not_be_called)
    assert ok is False


def test_wait_for_job_completion_succeeds_immediately_on_succeeded_field(monkeypatch):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, stdout="1|", stderr="")

    def sleep_must_not_be_called(_seconds):
        raise AssertionError("ne doit jamais dormir : le succes est deja connu au 1er poll")

    monkeypatch.setattr(rb.subprocess, "run", fake_run)
    ok = rb._wait_for_job_completion(
        "kubectl", "facil", "some-job", timeout_seconds=900,
        sleep_fn=sleep_must_not_be_called)
    assert ok is True


def test_wait_for_job_completion_fails_closed_on_timeout(monkeypatch):
    # Ni succeeded ni failed ne se presentent jamais (Job coince en Running) :
    # doit finir par renvoyer False, jamais bloquer indefiniment ni supposer
    # un succes par defaut.
    fake_now = [0.0]

    def fake_monotonic():
        return fake_now[0]

    def fake_sleep(seconds):
        fake_now[0] += seconds

    monkeypatch.setattr(rb.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(
        rb.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="|", stderr=""))
    ok = rb._wait_for_job_completion(
        "kubectl", "facil", "some-job", timeout_seconds=10,
        poll_interval=3, sleep_fn=fake_sleep)
    assert ok is False


def test_container_exit_summary_reports_which_container_failed(monkeypatch):
    monkeypatch.setattr(
        rb.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 0, stdout="restore-postgres=0\nrestore-minio=1\n", stderr=""))
    summary = rb._container_exit_summary("kubectl", "facil", rb.RESTORE_JOB)
    assert "restore-postgres=OK (exit 0)" in summary
    assert "restore-minio=ECHEC (exit 1)" in summary


def test_container_exit_summary_empty_when_introspection_fails(monkeypatch):
    monkeypatch.setattr(
        rb.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="denied"))
    assert rb._container_exit_summary("kubectl", "facil", rb.RESTORE_JOB) == ""


def test_restore_failure_reports_per_container_status_in_stderr(monkeypatch, capsys):
    # Integration : le Job de restauration echoue (restore-minio a plante),
    # postgres OK -- le rapport d'erreur doit dire LAQUELLE des deux moities
    # a reellement ete appliquee, pas juste "le Job a echoue".
    ts = "20260701T000000Z"
    fake_run, calls = _make_fake_run(
        list_output=f"{ts}\n", restore_wait_rc=1,
        container_statuses="restore-postgres=0\nrestore-minio=1\n")
    _patch_kubectl(monkeypatch, fake_run)
    monkeypatch.setattr("builtins.input", lambda prompt="": ts)
    rc = rb.main(["--restore", ts])
    assert rc == 2
    err = capsys.readouterr().err
    assert "restore-postgres=OK (exit 0)" in err
    assert "restore-minio=ECHEC (exit 1)" in err


# --- list_backups() ----------------------------------------------------------

def test_list_backups_parses_and_sorts_timestamps(monkeypatch):
    fake_run, calls = _make_fake_run(
        list_output="20260701T000000Z\n20260601T000000Z\n20260801T000000Z\n")
    _patch_kubectl(monkeypatch, fake_run)
    result = rb.list_backups("kubectl", "facil")
    assert result == ["20260601T000000Z", "20260701T000000Z", "20260801T000000Z"]


def test_list_backups_ignores_non_timestamp_lines(monkeypatch):
    # ls could in principle emit stray output; only strict-format lines count.
    fake_run, calls = _make_fake_run(
        list_output="20260701T000000Z\nsome-noise\n\n20260801T000000Z\n")
    _patch_kubectl(monkeypatch, fake_run)
    assert rb.list_backups("kubectl", "facil") == ["20260701T000000Z", "20260801T000000Z"]


def test_list_backups_empty_when_postgres_statefulset_missing(monkeypatch):
    fake_run, calls = _make_fake_run(postgres_ok=False)
    _patch_kubectl(monkeypatch, fake_run)
    assert rb.list_backups("kubectl", "facil") == []
    # Never even tries to run the list Job without knowing which image to use.
    assert not any("apply" in c for c, _ in calls)


def test_list_backups_empty_when_job_fails(monkeypatch):
    # wait_rc=1 (Job failed/timed out) but the logs happen to contain
    # well-formed timestamp lines anyway (e.g. a partial run before it died) --
    # a naive implementation that only ever looks at the logs, ignoring
    # `kubectl wait`'s own exit code, would return them regardless. Non-empty
    # list_output makes this a REAL fail-closed proof, not one confounded by
    # empty logs (which would pass whether or not the wait_rc check exists).
    fake_run, calls = _make_fake_run(wait_rc=1, list_output="20260701T000000Z\n")
    _patch_kubectl(monkeypatch, fake_run)
    assert rb.list_backups("kubectl", "facil") == []


def test_list_backups_empty_when_apply_fails(monkeypatch):
    # `kubectl apply -f -` itself can fail (e.g. RBAC, PVC not bound yet) --
    # must fail closed WITHOUT ever calling `kubectl wait`/`kubectl logs` on a
    # Job that was never actually created.
    fake_run, calls = _make_fake_run(apply_rc=1)
    _patch_kubectl(monkeypatch, fake_run)
    assert rb.list_backups("kubectl", "facil") == []
    assert not any("wait" in c for c, _ in calls)
    assert not any("logs" in c for c, _ in calls)


def test_list_job_manifest_reuses_postgres_image_no_new_image(monkeypatch):
    # backup-job.yaml's own principle ("aucune image nouvelle") -- the list Job
    # must reuse the ALREADY-pinned postgres image, never pull something new.
    fake_run, calls = _make_fake_run(list_output="20260701T000000Z\n")
    _patch_kubectl(monkeypatch, fake_run)
    rb.list_backups("kubectl", "facil")
    apply_call = next(manifest for cmd, manifest in calls if "apply" in cmd and manifest)
    assert 'image: "pgvector/pgvector:pg16"' in apply_call


def test_list_job_mounts_backups_pvc_read_only(monkeypatch):
    fake_run, calls = _make_fake_run(list_output="20260701T000000Z\n")
    _patch_kubectl(monkeypatch, fake_run)
    rb.list_backups("kubectl", "facil")
    apply_call = next(manifest for cmd, manifest in calls if "apply" in cmd and manifest)
    assert "claimName: facil-backups" in apply_call
    assert "readOnly: true" in apply_call


def test_run_job_cleans_up_job_before_and_after(monkeypatch):
    fake_run, calls = _make_fake_run(list_output="20260701T000000Z\n")
    _patch_kubectl(monkeypatch, fake_run)
    rb.list_backups("kubectl", "facil")
    delete_calls = [c for c, _ in calls if "delete" in c and "job" in c]
    assert len(delete_calls) == 2, "cleanup must run BOTH before (idempotent rerun) and after"


# --- main(): --list -----------------------------------------------------------

def test_main_list_prints_available_backups(monkeypatch, capsys):
    fake_run, _ = _make_fake_run(list_output="20260701T000000Z\n")
    _patch_kubectl(monkeypatch, fake_run)
    rc = rb.main(["--list"])
    assert rc == 0
    assert "20260701T000000Z" in capsys.readouterr().out


def test_main_list_reports_none_found_without_crashing(monkeypatch, capsys):
    fake_run, _ = _make_fake_run(postgres_ok=False)
    _patch_kubectl(monkeypatch, fake_run)
    rc = rb.main(["--list"])
    assert rc == 0
    assert "Aucune sauvegarde" in capsys.readouterr().out


def test_main_fails_closed_when_kubectl_missing(monkeypatch):
    monkeypatch.setattr(rb, "find_kubectl", lambda: None)
    assert rb.main(["--list"]) == 2


# --- main(): --restore — validation before any destructive action -----------

def test_main_restore_rejects_malformed_timestamp_without_touching_cluster(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        raise AssertionError("must not invoke kubectl on a malformed timestamp")

    monkeypatch.setattr(rb.subprocess, "run", fake_run)
    monkeypatch.setattr(rb, "find_kubectl", lambda: "kubectl")
    rc = rb.main(["--restore", "not-a-timestamp; rm -rf /"])
    assert rc == 1
    assert calls == []


def test_main_restore_rejects_timestamp_not_in_available_list(monkeypatch, capsys):
    fake_run, _ = _make_fake_run(list_output="20260701T000000Z\n")
    _patch_kubectl(monkeypatch, fake_run)
    rc = rb.main(["--restore", "20260801T000000Z"])
    assert rc == 1
    assert "introuvable" in capsys.readouterr().err.lower()


# --- main(): --restore — confirmation must be an EXACT retype, not y/N ------

def test_restore_refuses_when_retyped_timestamp_does_not_match(monkeypatch, capsys):
    ts = "20260701T000000Z"
    fake_run, calls = _make_fake_run(list_output=f"{ts}\n")
    _patch_kubectl(monkeypatch, fake_run)
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")  # reflex y/N-style answer
    rc = rb.main(["--restore", ts])
    assert rc == 1
    assert "annul" in capsys.readouterr().err.lower()
    # No restore Job must ever have been applied.
    assert not any(rb.RESTORE_JOB in " ".join(c) for c, _ in calls)


def test_restore_proceeds_when_retyped_timestamp_matches_exactly(monkeypatch, capsys):
    ts = "20260701T000000Z"
    fake_run, calls = _make_fake_run(list_output=f"{ts}\n", restore_logs="restore ok\n")
    _patch_kubectl(monkeypatch, fake_run)
    monkeypatch.setattr("builtins.input", lambda prompt="": ts)
    rc = rb.main(["--restore", ts])
    assert rc == 0
    assert any(rb.RESTORE_JOB in " ".join(c) for c, _ in calls)


def test_restore_success_message_survives_cp1252_console(tmp_path, monkeypatch):
    """Reproduces the exact crash found on a real k3d smoke (task-E1,
    2026-07-14): `mc mirror`'s box-drawing summary table, returned verbatim by
    `kubectl logs`, is not encodable in cp1252 (Windows console default).
    Before main() reconfigured stdout/stderr to utf-8/replace, `print(f"[OK]
    ... {logs}")` raised UnicodeEncodeError RIGHT AFTER the restore had
    already succeeded -- the operator saw a traceback instead of "[OK]"."""
    ts = "20260701T000000Z"
    box_drawing_logs = "┌─┐ restore ok"  # not representable in cp1252
    fake_run, _ = _make_fake_run(list_output=f"{ts}\n", restore_logs=box_drawing_logs)
    _patch_kubectl(monkeypatch, fake_run)
    monkeypatch.setattr("builtins.input", lambda prompt="": ts)

    out_path = tmp_path / "stdout.txt"
    cp1252_stdout = open(out_path, "w", encoding="cp1252", errors="strict")
    monkeypatch.setattr(rb.sys, "stdout", cp1252_stdout)
    try:
        rc = rb.main(["--restore", ts])
    finally:
        cp1252_stdout.close()
    assert rc == 0
    assert "[OK]" in out_path.read_text(encoding="utf-8", errors="replace")


def test_restore_confirmation_is_case_and_whitespace_sensitive(monkeypatch):
    # Proves it's a real string-equality retype, not a fuzzy/normalized match.
    ts = "20260701T000000Z"
    fake_run, calls = _make_fake_run(list_output=f"{ts}\n")
    _patch_kubectl(monkeypatch, fake_run)
    monkeypatch.setattr("builtins.input", lambda prompt="": ts.lower())
    rc = rb.main(["--restore", ts])
    assert rc == 1
    assert not any(rb.RESTORE_JOB in " ".join(c) for c, _ in calls)


# --- main(): --restore — actual restore Job shape ----------------------------

def test_restore_job_includes_pg_restore_via_secretkeyref_not_literal(monkeypatch):
    ts = "20260701T000000Z"
    fake_run, calls = _make_fake_run(list_output=f"{ts}\n")
    _patch_kubectl(monkeypatch, fake_run)
    monkeypatch.setattr("builtins.input", lambda prompt="": ts)
    rb.main(["--restore", ts])
    manifest = next(m for c, m in calls if "apply" in c and m and rb.RESTORE_JOB in m)
    assert "pg_restore" in manifest
    assert "secretKeyRef" in manifest
    assert "name: facil-backup-secret" in manifest
    assert "key: POSTGRES_PASSWORD" in manifest


def test_restore_job_includes_mc_mirror_when_minio_deployed(monkeypatch):
    ts = "20260701T000000Z"
    fake_run, calls = _make_fake_run(list_output=f"{ts}\n", minio_ok=True)
    _patch_kubectl(monkeypatch, fake_run)
    monkeypatch.setattr("builtins.input", lambda prompt="": ts)
    rb.main(["--restore", ts])
    manifest = next(m for c, m in calls if "apply" in c and m and rb.RESTORE_JOB in m)
    assert "mc mirror" in manifest
    assert "MC_HOST_facil" in manifest
    assert "key: MINIO_ROOT_PASSWORD" in manifest


def test_restore_job_carries_backup_component_label_for_networkpolicy(monkeypatch):
    # BUG REEL CORRIGE (smoke k3d task-E1, 2026-07-14) : sans le label
    # `facil.component: backup` sur le pod-template, ce Job recevait
    # "Connection refused" sur Postgres ET MinIO -- la NetworkPolicy
    # default-deny (infra/helm/facil/templates/networkpolicy.yaml, SEC-012)
    # n'autorise l'ingress sur les datastores QU'aux pods portant
    # `facil.component in [backend, db-init, db-role, backup]`, et ce Job n'en
    # portait aucun (seuls les labels Kubernetes auto-generes : job-name/
    # controller-uid). Verifie en conditions reelles (helm+kubectl+k3d), pas
    # seulement ici : ce test protege la regression future, pas la preuve
    # initiale (qui exige un vrai cluster).
    ts = "20260701T000000Z"
    fake_run, calls = _make_fake_run(list_output=f"{ts}\n", minio_ok=True)
    _patch_kubectl(monkeypatch, fake_run)
    monkeypatch.setattr("builtins.input", lambda prompt="": ts)
    rb.main(["--restore", ts])
    manifest = next(m for c, m in calls if "apply" in c and m and rb.RESTORE_JOB in m)
    assert "facil.component: backup" in manifest


def test_restore_skips_minio_when_not_deployed(monkeypatch, capsys):
    ts = "20260701T000000Z"
    fake_run, calls = _make_fake_run(list_output=f"{ts}\n", minio_ok=False)
    _patch_kubectl(monkeypatch, fake_run)
    monkeypatch.setattr("builtins.input", lambda prompt="": ts)
    rc = rb.main(["--restore", ts])
    assert rc == 0
    manifest = next(m for c, m in calls if "apply" in c and m and rb.RESTORE_JOB in m)
    assert "mc mirror" not in manifest
    assert "restore-minio" not in manifest
    assert "restauration Postgres SEULEMENT" in capsys.readouterr().err


def test_restore_fails_closed_when_postgres_statefulset_disappears_after_confirm(monkeypatch):
    # Pathological but real race: available at --list time, gone by the time the
    # operator finishes typing the confirmation. Must fail closed, not crash into
    # a manifest built from a None postgres dict.
    ts = "20260701T000000Z"
    calls = []
    state = {"postgres_ok": True}

    def fake_run(cmd, **kw):
        calls.append((list(cmd), kw.get("input")))
        if "get" in cmd and f"statefulset/{rb.POSTGRES_STS}" in cmd:
            if not state["postgres_ok"]:
                return _cp(cmd, 1, stderr="not found")
            return _cp(cmd, 0, stdout=POSTGRES_JSONPATH_OUT)
        if "delete" in cmd:
            return _cp(cmd, 0)
        if "apply" in cmd:
            return _cp(cmd, 0)
        if "get" in cmd and any(a.startswith("job/") for a in cmd):
            return _cp(cmd, 0, stdout="1|")
        if "logs" in cmd:
            return _cp(cmd, 0, stdout=f"{ts}\n" if rb.LIST_JOB in " ".join(cmd) else "")
        raise AssertionError(cmd)

    monkeypatch.setattr(rb.subprocess, "run", fake_run)
    monkeypatch.setattr(rb, "find_kubectl", lambda: "kubectl")

    def fake_input(prompt=""):
        state["postgres_ok"] = False  # disappears the instant the operator confirms
        return ts

    monkeypatch.setattr("builtins.input", fake_input)
    rc = rb.main(["--restore", ts])
    assert rc == 2
    assert not any(rb.RESTORE_JOB in " ".join(c) for c, _ in calls)


# --- CWE-214 : no secret VALUE ever appears in a subprocess argv -------------

def test_no_secret_value_appears_in_any_subprocess_argv(monkeypatch):
    # This script never even READS a secret value (unlike k3s.py's --apply):
    # PGPASSWORD/MINIO_ROOT_PASSWORD are resolved by the kubelet from
    # `secretKeyRef`, never by this process. Structural proof: nothing
    # resembling a credential VALUE (only the key NAME "POSTGRES_PASSWORD" /
    # "MINIO_ROOT_PASSWORD", which is not a secret) ever appears in an argv.
    ts = "20260701T000000Z"
    fake_run, calls = _make_fake_run(list_output=f"{ts}\n")
    _patch_kubectl(monkeypatch, fake_run)
    monkeypatch.setattr("builtins.input", lambda prompt="": ts)
    rb.main(["--restore", ts])
    for cmd, _ in calls:
        for arg in cmd:
            assert "PGPASSWORD=" not in arg
            assert "MINIO_ROOT_PASSWORD=" not in arg


def test_mutually_exclusive_list_and_restore():
    with pytest.raises(SystemExit):
        rb.main(["--list", "--restore", "20260701T000000Z"])


def test_reuses_k3s_secret_names_no_duplication():
    # DRY: the backup Secret name has ONE source of truth (k3s.SECRET_NAMES),
    # never re-hardcoded here as a second literal that could drift.
    assert rb.BACKUP_SECRET == k3s.SECRET_NAMES["backup"] == "facil-backup-secret"
