"use client";
import { useQuery } from "@tanstack/react-query";
import { parseSession, type Session } from "@/lib/session-schema";

// Types re-exported for existing consumers (shape now lives with its zod schema).
export type { Session, AccountRole } from "@/lib/session-schema";

/** Whoami via the BFF /api/auth/session (refreshes the token if needed). The
 *  response is validated (zod) and fails safe to unauthenticated on any mismatch. */
export function useSession() {
  return useQuery<Session>({
    queryKey: ["session"],
    queryFn: async () => {
      const r = await fetch("/api/auth/session", { credentials: "same-origin" });
      if (!r.ok) return { authenticated: false };
      return parseSession(await r.json().catch(() => null));
    },
    retry: false,
    staleTime: 60_000,
  });
}
