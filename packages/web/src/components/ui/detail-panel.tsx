"use client";

import { useEffect } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

/**
 * Right-hand detail panel for master-detail / split-view (Lot 3). Fixed chrome
 * (title + close), the body is the only scrollable region (ergonomics doctrine),
 * an optional footer for actions. Esc closes. The parent owns open/close (URL
 * `?sel=`); this is presentation only.
 */
export function DetailPanel({ title, subtitle, onClose, children, footer }: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <aside className={cn(
      "flex min-h-0 flex-col rounded-lg border bg-card",
      // Below lg the panel overlays full-width; from lg it's the right column.
      "fixed inset-0 z-30 lg:static lg:inset-auto lg:z-auto",
    )}>
      <header className="flex items-center gap-2 border-b px-4 py-3">
        <div className="min-w-0">
          <h2 className="truncate text-sm font-semibold">{title}</h2>
          {subtitle && <p className="truncate text-xs text-muted-foreground">{subtitle}</p>}
        </div>
        <Button variant="ghost" size="icon" className="ml-auto" onClick={onClose} aria-label="Close panel">
          <X className="size-4" />
        </Button>
      </header>
      <div className="min-h-0 flex-1 overflow-auto p-4">{children}</div>
      {footer && <footer className="border-t px-4 py-3">{footer}</footer>}
    </aside>
  );
}
