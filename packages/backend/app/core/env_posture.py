"""Shared env-posture helpers — fail-secure 'required' resolution.

Several boot-time fallbacks (vault hydration, cache backend, secrets-provider
enrollment) share the same posture rule: a resource is REQUIRED when the operator
says so explicitly, otherwise it is required in production and relaxed in dev. A
prod deploy that forgets the knob fails *closed*, not open. Keeping this in one
place avoids the rule drifting between call sites.
"""

from __future__ import annotations

from collections.abc import Mapping

_DEV_ENVS = {"development", "dev", "test", "local"}


def is_dev(env: Mapping[str, str]) -> bool:
    """True for development/test-like environments (ENVIRONMENT absent => dev)."""
    return env.get("ENVIRONMENT", "development").lower() in _DEV_ENVS


def is_required(env: Mapping[str, str], knob: str) -> bool:
    """Whether a resource is required. An explicit knob ("1"/"0") always wins;
    otherwise required in non-dev (prod) environments — fail-secure by default."""
    val = env.get(knob)
    if val is not None:
        return val == "1"
    return not is_dev(env)
