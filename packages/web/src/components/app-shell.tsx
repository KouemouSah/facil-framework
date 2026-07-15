"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LayoutDashboard, Building2, MapPin, ShieldCheck, Users, Network, Settings, Globe, Plug, SlidersHorizontal, FolderTree, BookUser, Search, Menu, ChevronDown, PencilRuler } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import { usePermissions } from "@/lib/use-permissions";
import { BrandLogo } from "@/components/shared/brand-logo";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useSession } from "@/lib/use-session";
import { EmailVerifyBanner } from "@/components/layout/email-verify-banner";
import { LocaleSwitcher } from "@/components/layout/locale-switcher";
import { SidebarUser } from "@/components/layout/sidebar-user";

const COLLAPSE_KEY = "nav:collapsed";
const GROUPS_KEY = "nav:groups";

/**
 * Fixed application shell (ergonomics doctrine, D5): the sidebar + topbar NEVER
 * scroll — only the <main> data region does. Overview/detail views fit the
 * viewport (no-scroll feel); long lists scroll inside main with sticky headers.
 * Grid layout => no JS for sizing; responsive (sidebar hidden < md).
 *
 * Nav is grouped by family (P1.2) — Overview / Organization / Access & Identity /
 * System — and the desktop sidebar is collapsible to an icon rail (persisted).
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("nav");
  const tc = useTranslations("common");
  const pathname = usePathname();
  const router = useRouter();
  const qc = useQueryClient();
  const [navOpen, setNavOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  // Per-group accordion state (key → open). Missing key = open by default.
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  const { data: session, isLoading } = useSession();
  const { data: branding } = useQuery<{ app_name: string; logo_url: string; logo_dark_url: string; supported_locales: string[]; support_url: string; support_email: string }>({
    queryKey: ["branding"],
    queryFn: () => apiFetch(`/api/v1/system/branding`),
    staleTime: 5 * 60 * 1000,
  });
  const appName = branding?.app_name || "Facil";

  // Effective permissions -> hide nav the user can't use (backend still enforces).
  const { can } = usePermissions();

  // Hydrate the collapsed + group-accordion preferences on the client (avoids SSR mismatch).
  useEffect(() => {
    setCollapsed(localStorage.getItem(COLLAPSE_KEY) === "1");
    try {
      setOpenGroups(JSON.parse(localStorage.getItem(GROUPS_KEY) || "{}"));
    } catch {
      /* ignore corrupt pref */
    }
  }, []);
  function toggleCollapse() {
    setCollapsed((c) => {
      const next = !c;
      localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      return next;
    });
  }
  function toggleGroup(key: string) {
    setOpenGroups((prev) => {
      const next = { ...prev, [key]: prev[key] === false };  // toggle (default open → collapse)
      localStorage.setItem(GROUPS_KEY, JSON.stringify(next));
      return next;
    });
  }

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

  // `?? undefined`: session account fields are now nullable (backend sends null),
  // and SidebarUser's `email` prop is `string | undefined` — coalesce null away.
  const email = session?.account?.email ?? undefined;
  const who =
    session?.account?.display_name || email ||
    (session?.break_glass ? "Admin" : "");

  // Nav grouped by family. Only routes that exist are shown, and only those the
  // user's grants cover (`perm` undefined = always visible); a group with no
  // visible item is dropped. Backend remains the authority.
  const groups: { key: string; items: { href: string; label: string; icon: typeof LayoutDashboard; perm?: string }[] }[] = [
    { key: "overview", items: [
      { href: "/", label: t("dashboard"), icon: LayoutDashboard },
    ] },
    { key: "organization", items: [
      { href: "/organizations", label: t("organizations"), icon: Building2, perm: "organization.read" },
      { href: "/org-units", label: t("org_units"), icon: FolderTree, perm: "organization.read" },
      { href: "/locations", label: t("locations"), icon: MapPin, perm: "location.read" },
      { href: "/directory", label: t("directory"), icon: BookUser, perm: "party.read" },
    ] },
    { key: "access", items: [
      { href: "/agents", label: t("agents"), icon: Users, perm: "account.read" },
      { href: "/roles", label: t("roles"), icon: ShieldCheck, perm: "rbac.read" },
      { href: "/federation", label: t("federation"), icon: Network, perm: "account.read" },
    ] },
    { key: "system", items: [
      { href: "/reference", label: t("reference"), icon: Globe, perm: "reference.read" },
      { href: "/providers", label: t("providers"), icon: Plug, perm: "provider.read" },
      { href: "/fields", label: t("fields"), icon: PencilRuler, perm: "fields.manage" },
      { href: "/config", label: t("configuration"), icon: SlidersHorizontal, perm: "settings.read" },
      { href: "/settings", label: t("settings"), icon: Settings, perm: "branding.manage" },
    ] },
  ];
  const visibleGroups = groups
    .map((g) => ({ ...g, items: g.items.filter((i) => !i.perm || can(i.perm)) }))
    .filter((g) => g.items.length > 0);

  // Brand header + nav list are shared by the desktop sidebar and the mobile
  // drawer (DRY). On mobile, navigating closes the drawer.
  const brandHeader = (rail: boolean) => (
    <div className={cn("flex h-14 items-center gap-2 border-b font-semibold", rail ? "justify-center px-0" : "px-5")}>
      {/* White-label logo with light/dark swap (Phase A2). Default = the
          framework's own icon (P2.4), not a generic letter tile. Same-origin
          assets are optimized; external URLs stay unoptimized (no host allowlist). */}
      <BrandLogo
        light={branding?.logo_url}
        dark={branding?.logo_dark_url}
        fallback="/brand-icon.png"
        alt={appName}
        width={28}
        height={28}
        className="h-7 w-7 rounded-md object-contain"
      />
      {!rail && <span className="truncate">{appName}</span>}
    </div>
  );

  const navList = (rail: boolean, onNavigate?: () => void) => (
    // min-h-0 lets this flex child shrink below its content so overflow-y-auto
    // actually scrolls (without it the nav overflows the sidebar — P2.0 fix).
    <nav className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
      {visibleGroups.map((g) => {
        // Accordion only for real groups on the full sidebar; the icon rail and the
        // header-less "overview" group are always shown.
        const grouped = !rail && g.key !== "overview";
        const open = !grouped || openGroups[g.key] !== false;
        return (
          <div key={g.key} className="space-y-1">
            {grouped && (
              <button
                type="button"
                onClick={() => toggleGroup(g.key)}
                aria-expanded={open}
                className="flex w-full items-center gap-1 rounded-md px-3 py-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground/70 transition-colors hover:text-foreground"
              >
                <ChevronDown className={cn("size-3 shrink-0 transition-transform", !open && "-rotate-90")} />
                <span className="truncate">{t(`group.${g.key}`)}</span>
              </button>
            )}
            {open && g.items.map(({ href, label, icon: Icon }) => {
              const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={onNavigate}
                  title={rail ? label : undefined}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    rail && "justify-center px-0",
                    active
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                  )}
                >
                  <Icon className="size-4 shrink-0" />
                  {!rail && <span className="truncate">{label}</span>}
                </Link>
              );
            })}
          </div>
        );
      })}
    </nav>
  );

  return (
    <div className={cn("grid h-screen grid-cols-1 overflow-hidden", collapsed ? "md:grid-cols-[64px_1fr]" : "md:grid-cols-[260px_1fr]")}>
      {/* Skip-link (a11y): first focusable element, visible only on focus. */}
      <a
        href="#main-content"
        className="sr-only z-50 focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-sm focus:text-primary-foreground focus:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {tc("skip_to_content")}
      </a>
      {/* Sidebar — fixed on ≥ md (collapsible to an icon rail), off-canvas drawer < md */}
      <aside className="hidden flex-col border-r bg-card md:flex">
        {brandHeader(collapsed)}
        {navList(collapsed)}
        <div className="border-t p-2">
          <SidebarUser name={who} email={email} rail={collapsed} collapsed={collapsed}
            onLogout={logout} onToggleCollapse={toggleCollapse} />
        </div>
      </aside>

      {/* Mobile navigation drawer (< md) — Radix Dialog: focus-trap + Esc + backdrop.
          Always the full (non-rail) nav. */}
      <Sheet open={navOpen} onOpenChange={setNavOpen}>
        <SheetContent side="left" closeLabel={tc("close")} className="flex flex-col p-0 md:hidden">
          <SheetTitle className="sr-only">{appName}</SheetTitle>
          {brandHeader(false)}
          {navList(false, () => setNavOpen(false))}
          <div className="border-t p-2">
            <SidebarUser name={who} email={email} rail={false} collapsed={collapsed}
              onLogout={logout} onToggleCollapse={toggleCollapse} />
          </div>
        </SheetContent>
      </Sheet>

      {/* Content column: fixed topbar + (optional) verify-email banner + the ONLY
          scrollable region. 3 explicit rows so the banner keeps its natural height
          (was landing in the 1fr row → stretched/collapsed per page content). */}
      <div className="grid grid-rows-[56px_auto_1fr_auto] overflow-hidden">
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
            <LocaleSwitcher supported={branding?.supported_locales ?? ["en", "fr", "es"]} />
          </div>
        </header>
        <EmailVerifyBanner />
        <main id="main-content" tabIndex={-1} className="overflow-auto p-6 focus-visible:outline-none">{children}</main>
        {/* Console footer (P2.0) — thin, persistent: identity + license + support. */}
        <footer className="flex items-center justify-between gap-3 border-t bg-card/40 px-5 py-2 text-xs text-muted-foreground">
          <span>{appName} · <span className="uppercase tracking-wide">AGPL-3.0</span></span>
          <div className="flex items-center gap-3">
            {/* support_email was a PHANTOM branding field (editable, never rendered) —
                now surfaced as a mailto next to the support link (Phase A4). */}
            {branding?.support_email && (
              <a href={`mailto:${branding.support_email}`} className="hover:text-foreground">
                {tc("contact")}
              </a>
            )}
            {branding?.support_url && (
              <a href={branding.support_url} target="_blank" rel="noreferrer" className="hover:text-foreground">
                {tc("support")}
              </a>
            )}
          </div>
        </footer>
      </div>
    </div>
  );
}
