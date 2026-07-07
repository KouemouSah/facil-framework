"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Org {
  id: string;
  code: string;
  legal_name: string;
  display_name?: string;
}

export function orgLabel(o: Org): string {
  return o.display_name || o.legal_name;
}

/**
 * Resolve org labels by id in ONE request (backend batch endpoint
 * `GET /modules/organization/labels?ids=`), instead of the former N `useQueries`
 * fan-out (E6, N+1 removal). Used to render an org name where we only hold the id
 * (e.g. role-assignment scopes) — without ever fetching the whole org list.
 *
 * Degrades gracefully: ids the caller can't read (scope) or that don't exist are
 * simply absent from the map, and the caller falls back to the id. Keyed on the
 * sorted id set so the same set hits the cache regardless of order.
 */
export function useOrgLabels(ids: (string | null | undefined)[]): Record<string, string> {
  const unique = Array.from(new Set(ids.filter((x): x is string => !!x))).sort();
  const q = useQuery<Record<string, string>>({
    queryKey: ["org-labels", unique.join(",")],
    queryFn: () => apiFetch<Record<string, string>>(
      `/api/v1/modules/organization/labels?ids=${unique.map(encodeURIComponent).join(",")}`),
    enabled: unique.length > 0,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  return q.data ?? {};
}

/** The first organization the caller can access (for defaulting a picker).
 * Fetches a single row server-side — never the whole list. */
export function useFirstOrg(): string {
  const q = useQuery<{ items: Org[] }>({
    queryKey: ["org", "first"],
    queryFn: () => apiFetch<{ items: Org[] }>(
      `/api/v1/modules/organization/?limit=1&offset=0`),
    staleTime: 60 * 1000,
  });
  return q.data?.items?.[0]?.id ?? "";
}
