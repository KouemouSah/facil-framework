"""RBAC — generic, scope-aware role-based access control (D4.3).

Core (always-on) authorization layer, sibling to identity/auth. Fixes the legacy
gaps: scope enforced by default (org -> unit -> site subtree), multi-tenant
(every assignment is scoped), roles seeded per profile (YAML, no hardcoded gov
roles), admin scopable. The `require_permission` dependency is imported by every
module, so this lives in core (not as a loadable module router).
"""
