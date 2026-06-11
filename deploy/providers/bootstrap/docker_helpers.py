#!/usr/bin/env python3
"""Thin docker CLI helpers for the bootstrap provisioners.

Why subprocess over an SDK? The provisioners only need three primitives:

  1. resolve the container + network of a running stack service,
  2. wait until services report healthy,
  3. run a one-shot tool container (``minio/mc``) ON the stack network, or
     ``exec`` a command inside a running container (``psql``).

These are exactly the things ``docker`` already does well and that the docker
SDK would add a heavy dependency (+ Windows named-pipe quirks) to replicate.
Every call is funnelled through :func:`run` so tests can mock one seam.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass


class DockerError(RuntimeError):
    """Raised when a docker invocation fails in a way the caller must handle."""


def docker_bin() -> str:
    exe = shutil.which("docker")
    if not exe:
        raise DockerError("docker not found on PATH")
    return exe


def run(args: list[str], *, timeout: int = 60, check: bool = True) -> subprocess.CompletedProcess:
    """Run ``docker <args>`` capturing output. The single mockable seam."""
    proc = subprocess.run(
        [docker_bin(), *args],
        capture_output=True, text=True, check=False,
        timeout=timeout, encoding="utf-8", errors="replace",
    )
    if check and proc.returncode != 0:
        raise DockerError(
            f"docker {' '.join(args)} failed (exit {proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc


# ---------------------------------------------------------------------------
# Service discovery
# ---------------------------------------------------------------------------

@dataclass
class ContainerInfo:
    name: str
    network: str          # first non-default user network the container is on
    health: str | None    # 'healthy' | 'unhealthy' | 'starting' | None (no hc)
    running: bool


def find_container(service: str, *, project: str | None = None) -> ContainerInfo | None:
    """Locate a running compose service container by its compose label.

    Resolves by the ``com.docker.compose.service`` label rather than guessing
    the ``<project>-<service>-1`` name, so it is robust to the compose project
    name differing from ``cfg.meta.project_name`` (the dir basename wins:
    e.g. project ``facil`` but stack ``facil_framework``).
    """
    filt = [f"label=com.docker.compose.service={service}"]
    if project:
        filt.append(f"label=com.docker.compose.project={project}")
    args = ["ps", "-a", "--no-trunc", "--format", "{{.Names}}"]
    for f in filt:
        args += ["--filter", f]
    proc = run(args)
    names = [n for n in proc.stdout.splitlines() if n.strip()]
    if not names:
        return None
    name = names[0]
    return inspect_container(name)


def inspect_container(name: str) -> ContainerInfo:
    proc = run(["inspect", name])
    data = json.loads(proc.stdout)[0]
    state = data.get("State", {})
    running = bool(state.get("Running"))
    health = (state.get("Health") or {}).get("Status")
    networks = data.get("NetworkSettings", {}).get("Networks", {}) or {}
    # Prefer the user-defined network (anything other than the default bridge).
    net = next((n for n in networks if n != "bridge"), None) or next(iter(networks), "")
    return ContainerInfo(name=name, network=net, health=health, running=running)


def wait_for_healthy(
    services: list[str],
    *,
    project: str | None = None,
    timeout: int = 120,
    interval: float = 2.0,
    sleep=time.sleep,
) -> dict[str, ContainerInfo]:
    """Block until every named service is running and (if it has a healthcheck)
    healthy. Returns the resolved {service: ContainerInfo}.

    A service with no healthcheck is considered ready as soon as it is running.
    Raises :class:`DockerError` on timeout, naming the laggards — never hangs
    silently. ``sleep`` is injectable so tests run instantly.
    """
    deadline = time.monotonic() + timeout
    resolved: dict[str, ContainerInfo] = {}
    while True:
        pending: list[str] = []
        for svc in services:
            info = find_container(svc, project=project)
            if info is None or not info.running:
                pending.append(svc)
                continue
            if info.health in (None, "healthy"):
                resolved[svc] = info
            else:
                pending.append(svc)
        if not pending:
            return resolved
        if time.monotonic() >= deadline:
            raise DockerError(
                f"timed out after {timeout}s waiting for: {', '.join(pending)}"
            )
        sleep(interval)


# ---------------------------------------------------------------------------
# Execution primitives used by provisioners
# ---------------------------------------------------------------------------

def exec_in(container: str, cmd: list[str], *, timeout: int = 60,
            check: bool = True) -> subprocess.CompletedProcess:
    """``docker exec <container> <cmd...>`` — used for in-container psql."""
    return run(["exec", container, *cmd], timeout=timeout, check=check)


def run_oneshot(
    image: str,
    cmd: list[str],
    *,
    network: str,
    env: dict[str, str] | None = None,
    entrypoint: str | None = None,
    timeout: int = 120,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run a throwaway tool container attached to the stack network.

    Used for ``minio/mc`` admin operations: the container joins ``network`` so
    it can reach ``minio:9000`` by service DNS, runs one command, and is removed
    (``--rm``).
    """
    args = ["run", "--rm", "--network", network]
    if entrypoint is not None:
        args += ["--entrypoint", entrypoint]
    for k, v in (env or {}).items():
        args += ["-e", f"{k}={v}"]
    args += [image, *cmd]
    return run(args, timeout=timeout, check=check)
