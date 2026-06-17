"use client";

import { useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LayoutDashboard, Building2, MapPin, ShieldCheck, Users, Network, Settings, Search, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { useSession } from "@/lib/use-session";

/**
 * Fixed application shell (ergonomics doctrine, D5): the sidebar + topbar NEVER
 * scroll — only the <main> data region does. Overview/detail views fit the
 * viewport (no-scroll feel); long lists scroll inside main with sticky headers.
 * Grid layout => no JS for sizing; responsive (sidebar hidden < md).
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("nav");
  const tc = useTranslations("common");
  const ta = useTranslations("auth");
  const pathname = usePathname();
  const router = useRouter();
  const qc = useQueryClient();
  const { data: session, isLoading } = useSession();
  const { data: branding } = useQuery<{ app_name: string; logo_url: string }>({
    queryKey: ["branding"],
    queryFn: () => apiFetch(`/api/v1/system/branding`),
    staleTime: 5 * 60 * 1000,
  });
  const appName = branding?.app_name || "Facil";

  // Client guard: if the session check resolves unauthenticated (e.g. refresh
  // failed server-side), leave the protected area.
  useEffect(() => {
    if (!isLoading && session && session.authenticated === false) {
      router.replace("/login");
    }
  }, [isLoading, session, router]);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => undefined);
    qc.clear();
    router.replace("/login");
  }

  const who =
    session?.account?.display_name || session?.account?.email ||
    (session?.break_glass ? "Admin" : "");

  // Only routes that exist are shown (no dead nav).
  const nav = [
    { href: "/", label: t("dashboard"), icon: LayoutDashboard },
    { href: "/organizations", label: t("organizations"), icon: Building2 },
    { href: "/locations", label: t("locations"), icon: MapPin },
    { href: "/agents", label: t("agents"), icon: Users },
    { href: "/roles", label: t("roles"), icon: ShieldCheck },
    { href: "/federation", label: t("federation"), icon: Network },
    { href: "/settings", label: t("settings"), icon: Settings },
  ];

  return (
    <div className="grid h-screen grid-cols-1 overflow-hidden md:grid-cols-[260px_1fr]">
      {/* Sidebar — fixed, hidden on mobile (drawer comes in D5.1) */}
      <aside className="hidden flex-col border-r bg-card md:flex">
        <div className="flex h-14 items-center gap-2 border-b px-5 font-semibold">
          {branding?.logo_url ? (
            <Image src={branding.logo_url} alt={appName} width={28} height={28} className="h-7 w-7 rounded-md object-contain" unoptimized />
          ) : (
            <span className="grid h-7 w-7 place-items-center rounded-md bg-primary text-primary-foreground">
              {appName.charAt(0).toUpperCase()}
            </span>
          )}
          {appName}
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {nav.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )}
              >
                <Icon className="size-4" />
                {label}
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Content column: fixed topbar + the ONLY scrollable region */}
      <div className="grid grid-rows-[56px_1fr] overflow-hidden">
        <header className="flex items-center gap-3 border-b bg-background/80 px-5 backdrop-blur">
          <div className="relative max-w-md flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              placeholder={tc("search")}
              className="h-9 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          <div className="ml-auto flex items-center gap-2">
            {who && <span className="text-sm text-muted-foreground">{who}</span>}
            <Button variant="ghost" size="icon" onClick={logout} title={ta("logout")} aria-label="logout">
              <LogOut className="size-4" />
            </Button>
          </div>
        </header>
        <main className="overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}
