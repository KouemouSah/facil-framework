"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
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
 * Resolve org labels by id (server-side, cached per id). Used to render an org
 * name where we only hold the id (e.g. role-assignment scopes) — without ever
 * fetching the whole org list. Picking is done by OrgCombobox (server search);
 * this is the read-side counterpart, so neither path relies on a client-side cap.
 *
 * Degrades gracefully: if an id can't be resolved (org module disabled, deleted
 * org…), it's simply absent from the map and the caller falls back to the id.
 */
export function useOrgLabels(ids: (string | null | undefined)[]): Record<string, string> {
  const unique = Array.from(new Set(ids.filter((x): x is string => !!x)));
  const results = useQueries({
    queries: unique.map((id) => ({
      queryKey: ["org-label", id],
      queryFn: () => apiFetch<Org>(`/api/v1/modules/organization/${id}`),
      staleTime: 5 * 60 * 1000,
      retry: false,
    })),
  });
  const labels: Record<string, string> = {};
  unique.forEach((id, i) => {
    const data = results[i]?.data;
    if (data) labels[id] = orgLabel(data);
  });
  return labels;
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
