import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ACCESS, REFRESH, getInstallStatus } from "@/lib/server/backend";
import { AppShell } from "@/components/app-shell";

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
  return <AppShell>{children}</AppShell>;
}
