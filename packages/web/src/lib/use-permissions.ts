"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { hasPerm } from "@/lib/perm";

/**
 * Effective permissions of the signed-in principal (`/auth/me/permissions`),
 * shared across the app via the `["my-permissions"]` cache key (nav + per-page
 * action gating hit the same query — one fetch). `can("resource.verb")` mirrors
 * the backend match (exact / `resource.*` / `*`).
 *
 * UI gating ONLY — the backend still enforces (and scope-checks) every mutation;
 * this just hides/disables actions the user definitely cannot perform.
 */
export function usePermissions() {
  const { data } = useQuery<{ permissions: string[] }>({
    queryKey: ["my-permissions"],
    queryFn: () => apiFetch(`/api/v1/auth/me/permissions`),
    staleTime: 5 * 60 * 1000,
  });
  const granted = data?.permissions ?? [];
  return {
    granted,
    can: (perm: string) => hasPerm(granted, perm),
  };
}
