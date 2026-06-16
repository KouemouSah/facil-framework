"""Canonical RBAC permission verbs (D4.3 hardening).

A generic platform needs a consistent verb vocabulary so every module declares
permissions the same way (`<resource>.<verb>`). These are the standard actions;
a module declares only the verbs it actually needs. `MANAGE` is the super-verb
(grant it via the `<resource>.*` wildcard to cover every verb on a resource).

Industry parallel: Django model perms, Odoo ir.model.access, Azure RBAC actions.
"""

from __future__ import annotations

READ = "read"        # view / list
CREATE = "create"    # add a new record
UPDATE = "update"    # modify an existing record
DELETE = "delete"    # remove a record
MANAGE = "manage"    # full control (use the `<resource>.*` wildcard in grants)
APPROVE = "approve"  # workflow approval / validation
EXPORT = "export"    # bulk data export
PRINT = "print"      # render / print a document or report
ASSIGN = "assign"    # assign ownership / roles / responsibility

# The full vocabulary — used to validate declared/granted codes.
VERBS: tuple[str, ...] = (READ, CREATE, UPDATE, DELETE, MANAGE, APPROVE,
                          EXPORT, PRINT, ASSIGN)


def perm(resource: str, verb: str) -> str:
    """Compose a permission code `<resource>.<verb>` (verb must be canonical)."""
    if verb not in VERBS:
        raise ValueError(f"unknown verb '{verb}'; expected one of {VERBS}")
    return f"{resource}.{verb}"
