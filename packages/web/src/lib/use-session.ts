"use client";
import { useQuery } from "@tanstack/react-query";

export interface AccountRole {
  role_id: string;
  organization_id: string | null;
  org_unit_id: string | null;
  site_id: string | null;
}
export interface Session {
  authenticated: boolean;
  break_glass?: boolean;
  account?: { id: string; email?: string; display_name?: string; account_number?: string };
  roles?: AccountRole[];
  idp?: string | null;
}

/** Whoami via the BFF /api/auth/session (refreshes the token if needed). */
export function useSession() {
  return useQuery<Session>({
    queryKey: ["session"],
    queryFn: async () => {
      const r = await fetch("/api/auth/session", { credentials: "same-origin" });
      if (!r.ok) return { authenticated: false };
      return r.json();
    },
    retry: false,
    staleTime: 60_000,
  });
}
