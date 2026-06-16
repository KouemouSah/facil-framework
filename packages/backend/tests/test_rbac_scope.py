"""Unit tests for the pure RBAC predicates: scope coverage + permission match."""

from __future__ import annotations

import pytest

from app.rbac import verbs as v
from app.rbac.scope import Scope, covers, raw_scope_ids
from app.rbac.service import match_permission


# --- verb taxonomy -------------------------------------------------------

def test_verb_perm_composition():
    assert v.perm("organization", v.UPDATE) == "organization.update"
    assert v.perm("document", v.PRINT) == "document.print"


def test_verb_perm_rejects_unknown():
    with pytest.raises(ValueError):
        v.perm("organization", "frobnicate")


def test_verbs_include_update_and_print():
    assert {"update", "print", "export", "approve", "assign"} <= set(v.VERBS)


# --- permission matching -------------------------------------------------

def test_exact_match():
    assert match_permission("organization.read", {"organization.read"})


def test_no_match():
    assert not match_permission("organization.read", {"location.read"})


def test_global_wildcard():
    assert match_permission("anything.at_all", {"*"})


def test_resource_wildcard():
    assert match_permission("organization.delete", {"organization.*"})
    assert not match_permission("location.delete", {"organization.*"})


# --- scope coverage ------------------------------------------------------

GLOBAL = Scope()
ORG_A = Scope(organization_id="A")
ORG_B = Scope(organization_id="B")


def test_global_assignment_covers_everything():
    assert covers(GLOBAL, ORG_A)
    assert covers(GLOBAL, Scope(organization_id="X", org_unit_id="u", unit_path="/u/"))


def test_org_assignment_covers_same_org_only():
    assert covers(ORG_A, Scope(organization_id="A", org_unit_id="u", unit_path="/u/"))
    assert not covers(ORG_A, ORG_B)


def test_org_scoped_does_not_cover_global_request():
    # An org-scoped grant must NOT authorize a global (no-org) operation.
    assert not covers(ORG_A, GLOBAL)


def test_unit_assignment_covers_subtree():
    assign = Scope(organization_id="A", org_unit_id="root", unit_path="/root/")
    child = Scope(organization_id="A", org_unit_id="child", unit_path="/root/child/")
    other = Scope(organization_id="A", org_unit_id="sib", unit_path="/sib/")
    assert covers(assign, child)          # descendant
    assert covers(assign, assign)         # self
    assert not covers(assign, other)      # sibling subtree
    assert not covers(assign, ORG_A)      # org-level request is broader than unit grant


def test_site_assignment_is_exact():
    assign = Scope(organization_id="A", site_id="s1")
    assert covers(assign, Scope(organization_id="A", site_id="s1"))
    assert not covers(assign, Scope(organization_id="A", site_id="s2"))
    assert not covers(assign, ORG_A)      # org-level request broader than site grant


# --- raw scope extraction (no DB) ----------------------------------------

class _FakeReq:
    def __init__(self, path=None, query=None):
        self.path_params = path or {}
        self.query_params = query or {}


def test_raw_scope_from_path():
    r = _FakeReq(path={"org_id": "A"})
    assert raw_scope_ids(r)["organization_id"] == "A"


def test_raw_scope_unit_and_site():
    r = _FakeReq(path={"unit_id": "u"})
    assert raw_scope_ids(r)["org_unit_id"] == "u"
    r2 = _FakeReq(path={"site_id": "s"})
    assert raw_scope_ids(r2)["site_id"] == "s"


def test_raw_scope_from_query_when_no_path():
    r = _FakeReq(query={"organization_id": "A", "org_unit_id": "u"})
    raw = raw_scope_ids(r)
    assert raw["organization_id"] == "A" and raw["org_unit_id"] == "u"
