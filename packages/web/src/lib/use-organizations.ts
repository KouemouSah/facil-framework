"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Org {
  id: string;
  code: string;
  legal_name: string;
  display_name?: string;
}

// Backend caps the org list at 200. Until a server-side searchable org endpoint
// lands, fetch that page and SURFACE truncation (no silent cap) so the operator
// knows the picker isn't exhaustive at scale.
const CAP = 200;

export function useOrganizations() {
  const q = useQuery<Org[]>({
    queryKey: ["orgs", "all"],
    queryFn: () => apiFetch<Org[]>(`/api/v1/modules/organization/?limit=${CAP}&offset=0`),
    staleTime: 60 * 1000,
  });
  const orgs = q.data ?? [];
  return { orgs, truncated: orgs.length >= CAP, isLoading: q.isLoading };
}

export function orgLabel(o: Org): string {
  return o.display_name || o.legal_name;
}
