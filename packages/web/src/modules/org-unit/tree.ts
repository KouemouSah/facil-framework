import type { OrgUnit } from "./api";

/** Pre-order tree traversal from `parent_id` (roots = parent_id null/absent),
 *  children sorted by name, with a computed `level` for indentation — independent
 *  of the backend `depth` so a stale depth can't misalign the tree. */
export function orderForTree(units: OrgUnit[]): { unit: OrgUnit; level: number }[] {
  const byParent = new Map<string | null, OrgUnit[]>();
  const ids = new Set(units.map((u) => u.id));
  for (const u of units) {
    // A unit whose parent isn't in the set is treated as a root (defensive).
    const key = u.parent_id && ids.has(u.parent_id) ? u.parent_id : null;
    const arr = byParent.get(key) ?? [];
    arr.push(u);
    byParent.set(key, arr);
  }
  for (const arr of byParent.values()) arr.sort((a, b) => a.name.localeCompare(b.name));

  const out: { unit: OrgUnit; level: number }[] = [];
  const walk = (parent: string | null, level: number) => {
    for (const u of byParent.get(parent) ?? []) {
      out.push({ unit: u, level });
      walk(u.id, level + 1);
    }
  };
  walk(null, 0);
  return out;
}

/** Ids of a unit's whole subtree (itself + all descendants) via the parent graph —
 *  the invalid parent choices when reparenting (a unit can't be its own ancestor). */
export function subtreeIds(units: OrgUnit[], rootId: string): Set<string> {
  const childrenOf = new Map<string, string[]>();
  for (const u of units) {
    if (!u.parent_id) continue;
    const arr = childrenOf.get(u.parent_id) ?? [];
    arr.push(u.id);
    childrenOf.set(u.parent_id, arr);
  }
  const out = new Set<string>();
  const stack = [rootId];
  while (stack.length) {
    const id = stack.pop()!;
    if (out.has(id)) continue;
    out.add(id);
    for (const c of childrenOf.get(id) ?? []) stack.push(c);
  }
  return out;
}

/** Valid parent options for a unit form: all units, minus the editing unit's own
 *  subtree (self + descendants). For create (editingId undefined) = all. */
export function validParents(units: OrgUnit[], editingId?: string): OrgUnit[] {
  if (!editingId) return units;
  const blocked = subtreeIds(units, editingId);
  return units.filter((u) => !blocked.has(u.id));
}
