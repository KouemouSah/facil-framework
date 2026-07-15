"use client";

import * as React from "react";
import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useResizable } from "@/lib/use-resizable";

/**
 * Unified create/edit surface (Foundation centre of gravity). Replaces the
 * create-dialogs: it hosts a RecordForm for both create (`?new=1`) and edit
 * (`?sel=id`). Responsive by default:
 *   - ≥ lg : docked on the right edge, width persisted per resource and adjustable
 *            via a draggable divider (clamp/persist logic in `lib/resizable`).
 *   - < lg : full-screen overlay (modal), no resize (touch).
 * Fixed header (title + close) and footer (actions); only the body scrolls — the
 * "fixed shell" ergonomics doctrine. Esc closes. The parent owns open/close (URL
 * `?new` / `?sel`); this is presentation only.
 *
 * `mode="page"` (P1.3) widens the surface to the full content area (`lg:w-full`) —
 * used for field-rich creates (e.g. an Organization) where a narrow docked panel
 * cramps the form. The parent hides the list while a page-mode surface is open so
 * the form gets the whole width; edit stays `mode="panel"` (keeps list context).
 */
export function RecordSurface({
  title,
  subtitle,
  onClose,
  resourceKey,
  mode = "panel",
  footer,
  loading,
  children,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  onClose: () => void;
  resourceKey: string;
  mode?: "panel" | "page";
  footer?: React.ReactNode;
  loading?: boolean;
  children: React.ReactNode;
}) {
  const tc = useTranslations("common");
  const { width, onDragStart, isDragging } = useResizable(resourceKey);
  const titleId = `rs-title-${resourceKey}`;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (loading) return <RecordSurfaceSkeleton mode={mode} />;

  return (
    <aside
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      style={{ ["--rs-w" as string]: `${width}px` } as React.CSSProperties}
      className={cn(
        "z-30 flex min-h-0 flex-col border-l bg-card",
        // < lg : full-screen overlay. ≥ lg : right-docked column at the persisted width,
        // framed as a card (top+all borders + radius) so its top edge is visible.
        "fixed inset-0 w-full lg:static lg:inset-auto lg:z-auto lg:w-[var(--rs-w)] lg:rounded-lg lg:border",
        mode === "page" && "lg:w-full",
        isDragging && "select-none",
      )}
    >
      {/* Drag handle — left edge, pointer-only (≥ lg). */}
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label={tc("resize_panel")}
        onPointerDown={onDragStart}
        className="absolute -left-1 top-0 hidden h-full w-2 cursor-col-resize touch-none hover:bg-primary/20 lg:block"
      />
      <header className="flex items-center gap-2 border-b px-4 py-3">
        <div className="min-w-0">
          <h2 id={titleId} className="truncate text-sm font-semibold">{title}</h2>
          {subtitle && <p className="truncate text-xs text-muted-foreground">{subtitle}</p>}
        </div>
        <Button variant="ghost" size="icon" className="ml-auto" onClick={onClose} aria-label={tc("close")}>
          <X className="size-4" />
        </Button>
      </header>
      <div className="min-h-0 flex-1 overflow-auto p-4">{children}</div>
      {footer && <footer className="border-t px-4 py-3">{footer}</footer>}
    </aside>
  );
}

/** DRY loading placeholder matching RecordSurface's chrome (title + body
 * lines), for callers that mount the surface before the record/form data
 * has resolved. No resize handle (nothing to persist for a placeholder). */
export function RecordSurfaceSkeleton({ mode = "panel" }: { mode?: "panel" | "page" }) {
  return (
    <aside
      className={cn(
        "z-30 flex min-h-0 flex-col border-l bg-card",
        "fixed inset-0 w-full lg:static lg:inset-auto lg:z-auto lg:w-[420px] lg:rounded-lg lg:border",
        mode === "page" && "lg:w-full",
      )}
    >
      <header className="flex items-center gap-2 border-b px-4 py-3">
        <Skeleton className="h-4 w-1/3" />
      </header>
      <div className="min-h-0 flex-1 space-y-3 overflow-auto p-4">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-2/3" />
      </div>
    </aside>
  );
}
