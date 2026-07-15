import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { HydrationBoundary } from "@tanstack/react-query";
import { ACCESS, REFRESH, getInstallStatus } from "@/lib/server/backend";
import { AppShell } from "@/components/app-shell";
import { dehydratedAuthState } from "./prefetch-session";

// Protected area. First-run gate: if the system isn't installed yet -> installer.
// Otherwise a cheap cookie check -> /login (no flash); the client (AppShell) then
// confirms via /api/auth/session, refreshing the access token if it expired.
export default async function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const { installed } = await getInstallStatus();
  if (!installed) redirect("/install");
  const jar = await cookies();
  if (!jar.get(ACCESS) && !jar.get(REFRESH)) {
    redirect("/login");
  }
  // Seed react-query with the principal's session + permissions so the shell nav
  // and permission-gated actions render CORRECTLY in the first paint (no pop-in).
  // Fail-safe: dehydratedAuthState() omits any key it couldn't prefetch.
  const dehydratedState = await dehydratedAuthState();
  return (
    <HydrationBoundary state={dehydratedState}>
      <AppShell>{children}</AppShell>
    </HydrationBoundary>
  );
}
