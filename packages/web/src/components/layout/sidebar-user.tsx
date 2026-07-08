"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { LogOut, PanelLeftClose, PanelLeftOpen, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

/**
 * Signed-in account, docked at the sidebar foot (P2.0) — the conventional place
 * for identity + sign-out, replacing the lone "collapse" button. Avatar + name
 * open a menu (collapse toggle + sign out). In the icon rail only the avatar
 * shows. Built on the Popover primitive.
 */
export function SidebarUser({ name, email, rail, collapsed, onLogout, onToggleCollapse }: {
  name: string;
  email?: string;
  /** Desktop icon-rail: show only the avatar. (Always false in the mobile drawer.) */
  rail: boolean;
  collapsed: boolean;
  onLogout: () => void;
  onToggleCollapse: () => void;
}) {
  const tc = useTranslations("common");
  const ta = useTranslations("auth");
  const [open, setOpen] = useState(false);
  const initial = (name || "?").trim().charAt(0).toUpperCase() || "?";
  const hasEmail = !!email && email !== name;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          title={rail ? name : undefined}
          aria-label={name}
          className={cn(
            "flex w-full items-center gap-2.5 rounded-md p-2 text-left transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            rail && "justify-center p-1.5",
          )}
        >
          <span className="grid size-8 shrink-0 place-items-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
            {initial}
          </span>
          {!rail && (
            <>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{name}</span>
                {hasEmail && <span className="block truncate text-xs text-muted-foreground">{email}</span>}
              </span>
              <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" />
            </>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" side="top" className="w-56">
        <div className="border-b px-2 pb-1.5 pt-1">
          <p className="truncate text-sm font-medium">{name}</p>
          {hasEmail && <p className="truncate text-xs text-muted-foreground">{email}</p>}
        </div>
        <button
          type="button"
          onClick={() => { setOpen(false); onToggleCollapse(); }}
          className="mt-1 flex w-full items-center gap-2.5 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent"
        >
          {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
          {collapsed ? tc("expand_sidebar") : tc("collapse_sidebar")}
        </button>
        <button
          type="button"
          onClick={() => { setOpen(false); onLogout(); }}
          className="flex w-full items-center gap-2.5 rounded-sm px-2 py-1.5 text-left text-sm text-destructive hover:bg-destructive/10"
        >
          <LogOut className="size-4" /> {ta("logout")}
        </button>
      </PopoverContent>
    </Popover>
  );
}
