/**
 * Client-side permission match, mirroring the backend (`rbac.service.
 * match_permission`): a granted set covers a needed `resource.verb` if it holds
 * `*` (all), the exact code, or the resource wildcard `resource.*`.
 *
 * UI gating ONLY — the backend remains the authority and enforces scope. This
 * just hides nav/actions the user definitely cannot use.
 */
export function hasPerm(granted: string[], needed: string): boolean {
  if (!needed) return true;
  if (granted.includes("*") || granted.includes(needed)) return true;
  const resource = needed.split(".")[0];
  return granted.includes(`${resource}.*`);
}
