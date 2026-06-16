"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  LayoutDashboard, Building2, MapPin, Users, ShieldCheck, Settings, Search,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

/**
 * Fixed application shell (ergonomics doctrine, D5): the sidebar + topbar NEVER
 * scroll — only the <main> data region does. Overview/detail views fit the
 * viewport (no-scroll feel); long lists scroll inside main with sticky headers.
 * Grid layout => no JS for sizing; responsive (sidebar hidden < md).
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("nav");
  const tc = useTranslations("common");
  const pathname = usePathname();

  const nav = [
    { href: "/", label: t("dashboard"), icon: LayoutDashboard },
    { href: "/organizations", label: t("organizations"), icon: Building2 },
    { href: "/locations", label: t("locations"), icon: MapPin },
    { href: "/agents", label: t("agents"), icon: Users },
    { href: "/roles", label: t("roles"), icon: ShieldCheck },
    { href: "/settings", label: t("settings"), icon: Settings },
  ];

  return (
    <div className="grid h-screen grid-cols-1 overflow-hidden md:grid-cols-[260px_1fr]">
      {/* Sidebar — fixed, hidden on mobile (drawer comes in D5.1) */}
      <aside className="hidden flex-col border-r bg-card md:flex">
        <div className="flex h-14 items-center gap-2 border-b px-5 font-semibold">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-primary text-primary-foreground">
            F
          </span>
          Facil
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
          <div className="ml-auto" />
          <Button variant="ghost" size="sm">Admin</Button>
        </header>
        <main className="overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}
