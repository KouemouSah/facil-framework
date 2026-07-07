"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LayoutDashboard, Building2, MapPin, ShieldCheck, Users, Network, Settings, Globe, Plug, SlidersHorizontal, FolderTree, Search, LogOut, Menu } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import { usePermissions } from "@/lib/use-permissions";
import { isSameOriginAsset } from "@/lib/upload";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useSession } from "@/lib/use-session";
import { EmailVerifyBanner } from "@/components/layout/email-verify-banner";

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
  const [navOpen, setNavOpen] = useState(false);
  const { data: session, isLoading } = useSession();
  const { data: branding } = useQuery<{ app_name: string; logo_url: string }>({
    queryKey: ["branding"],
    queryFn: () => apiFetch(`/api/v1/system/branding`),
    staleTime: 5 * 60 * 1000,
  });
  const appName = branding?.app_name || "Facil";

  // Effective permissions -> hide nav the user can't use (backend still enforces).
  const { can } = usePermissions();

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

  // Only routes that exist are shown, and only those the user's grants cover
  // (`perm` undefined = always visible). Backend remains the authority.
  const allNav = [
    { href: "/", label: t("dashboard"), icon: LayoutDashboard },
    { href: "/organizations", label: t("organizations"), icon: Building2, perm: "organization.read" },
    { href: "/org-units", label: t("org_units"), icon: FolderTree, perm: "organization.read" },
    { href: "/locations", label: t("locations"), icon: MapPin, perm: "location.read" },
    { href: "/agents", label: t("agents"), icon: Users, perm: "account.read" },
    { href: "/roles", label: t("roles"), icon: ShieldCheck, perm: "rbac.read" },
    { href: "/federation", label: t("federation"), icon: Network, perm: "account.read" },
    // Configuration area (master data is admin config, not a primary workspace).
    // TODO(Phase U): data-driven, module-declared, grouped nav with a "Configuration" section.
    { href: "/reference", label: t("reference"), icon: Globe, perm: "reference.read" },
    { href: "/providers", label: t("providers"), icon: Plug, perm: "provider.read" },
    { href: "/config", label: t("configuration"), icon: SlidersHorizontal, perm: "settings.read" },
    { href: "/settings", label: t("settings"), icon: Settings, perm: "branding.manage" },
  ];
  const nav = allNav.filter((i) => !i.perm || can(i.perm));

  // Brand header + nav list are shared by the desktop sidebar and the mobile
  // drawer (DRY). On mobile, navigating closes the drawer.
  const brandHeader = (
    <div className="flex h-14 items-center gap-2 border-b px-5 font-semibold">
      {branding?.logo_url ? (
        // Same-origin assets (uploaded via the pipeline, `/api/...`) are optimized;
        // an external URL stays unoptimized so it renders without a host allowlist.
        <Image src={branding.logo_url} alt={appName} width={28} height={28} className="h-7 w-7 rounded-md object-contain" unoptimized={!isSameOriginAsset(branding.logo_url)} />
      ) : (
        <span className="grid h-7 w-7 place-items-center rounded-md bg-primary text-primary-foreground">
          {appName.charAt(0).toUpperCase()}
        </span>
      )}
      {appName}
    </div>
  );

  const navList = (onNavigate?: () => void) => (
    <nav className="flex-1 space-y-1 overflow-y-auto p-3">
      {nav.map(({ href, label, icon: Icon }) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
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
  );

  return (
    <div className="grid h-screen grid-cols-1 overflow-hidden md:grid-cols-[260px_1fr]">
      {/* Skip-link (a11y): first focusable element, visible only on focus. */}
      <a
        href="#main-content"
        className="sr-only z-50 focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-sm focus:text-primary-foreground focus:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {tc("skip_to_content")}
      </a>
      {/* Sidebar — fixed on ≥ md, off-canvas drawer < md */}
      <aside className="hidden flex-col border-r bg-card md:flex">
        {brandHeader}
        {navList()}
      </aside>

      {/* Mobile navigation drawer (< md) — Radix Dialog: focus-trap + Esc + backdrop */}
      <Sheet open={navOpen} onOpenChange={setNavOpen}>
        <SheetContent side="left" closeLabel={tc("close")} className="p-0 md:hidden">
          <SheetTitle className="sr-only">{appName}</SheetTitle>
          {brandHeader}
          {navList(() => setNavOpen(false))}
        </SheetContent>
      </Sheet>

      {/* Content column: fixed topbar + the ONLY scrollable region */}
      <div className="grid grid-rows-[56px_1fr] overflow-hidden">
        <header className="flex items-center gap-3 border-b bg-background/80 px-5 backdrop-blur">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setNavOpen(true)}
            aria-label={tc("open_menu")}
          >
            <Menu className="size-4" />
          </Button>
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
            <Button variant="ghost" size="icon" onClick={logout} title={ta("logout")} aria-label={ta("logout")}>
              <LogOut className="size-4" />
            </Button>
          </div>
        </header>
        <EmailVerifyBanner />
        <main id="main-content" tabIndex={-1} className="overflow-auto p-6 focus-visible:outline-none">{children}</main>
      </div>
    </div>
  );
}
