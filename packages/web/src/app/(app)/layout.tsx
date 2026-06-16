import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ACCESS, REFRESH } from "@/lib/server/backend";
import { AppShell } from "@/components/app-shell";

// Protected area. Cheap server-side gate: with neither token cookie there is no
// session -> straight to /login (no flash). The client (AppShell) then confirms
// via /api/auth/session, which refreshes the access token if it expired.
export default async function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const jar = await cookies();
  if (!jar.get(ACCESS) && !jar.get(REFRESH)) {
    redirect("/login");
  }
  return <AppShell>{children}</AppShell>;
}
