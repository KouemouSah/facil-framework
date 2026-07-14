import { describe, it, expect } from "vitest";
import { orderForTree, subtreeIds, validParents } from "./tree";
import type { OrgUnit } from "./api";

const u = (id: string, parent_id: string | null, name = id): OrgUnit => ({
  id, organization_id: "o", parent_id, code: id, name, unit_type: "department",
  description: null, path: "", depth: 0, external_ref: null, metadata: {},
  custom_fields: {}, is_active: true,
});

// root
//  ├ a
//  │  └ a1
//  └ b
const UNITS: OrgUnit[] = [u("a1", "a"), u("b", "root"), u("root", null), u("a", "root")];

describe("orderForTree", () => {
  it("pre-orders from parent_id with sorted children + computed level", () => {
    const order = orderForTree(UNITS);
    expect(order.map((o) => o.unit.id)).toEqual(["root", "a", "a1", "b"]);
    expect(order.map((o) => o.level)).toEqual([0, 1, 2, 1]);
  });
  it("treats a unit with a missing parent as a root (defensive)", () => {
    const order = orderForTree([u("orphan", "ghost")]);
    expect(order.map((o) => o.level)).toEqual([0]);
  });
});

describe("subtreeIds / validParents", () => {
  it("returns a unit's whole subtree", () => {
    expect([...subtreeIds(UNITS, "a")].sort()).toEqual(["a", "a1"]);
    expect([...subtreeIds(UNITS, "root")].sort()).toEqual(["a", "a1", "b", "root"]);
  });
  it("excludes self + descendants from valid parents (no cycle)", () => {
    expect(validParents(UNITS, "a").map((x) => x.id).sort()).toEqual(["b", "root"]);
    expect(validParents(UNITS).length).toBe(4); // create: all allowed
  });
});
