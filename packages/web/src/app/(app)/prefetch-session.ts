import { QueryClient, dehydrate, type DehydratedState } from "@tanstack/react-query";
import { readForPrefetch } from "@/lib/server/backend";

// Same keys the client hooks use (use-session.ts -> ["session"],
// use-permissions.ts -> ["my-permissions"]). Seeding these means useSession /
// usePermissions find data at hydration -> no permission pop-in in the first paint.
export async function dehydratedAuthState(): Promise<DehydratedState> {
  const [me, perms] = await Promise.all([
    readForPrefetch<{ break_glass: boolean; account?: unknown }>("/api/v1/auth/me"),
    readForPrefetch<{ permissions: string[] }>("/api/v1/auth/me/permissions"),
  ]);
  const qc = new QueryClient();
  // `{authenticated:true, ...me}` mirrors what the /api/auth/session route returns
  // (and what parseSession/useSession expect); /auth/me itself omits `authenticated`.
  if (me) qc.setQueryData(["session"], { authenticated: true, ...me });
  if (perms) qc.setQueryData(["my-permissions"], perms);
  return dehydrate(qc);
}
