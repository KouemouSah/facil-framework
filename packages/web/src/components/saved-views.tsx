"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bookmark, X } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";

interface SavedView { id: string; resource: string; name: string; config: Record<string, unknown> }

/**
 * Per-user saved views for a table (backlog ERP item 4). Save the current query
 * state (q/filters/sort) under a name, re-apply it, or delete it — backed by
 * /api/v1/me/views. Lightweight dropdown (click-outside to close).
 */
export function SavedViews({ resource, config, onApply }: {
  resource: string;
  config: Record<string, unknown>;
  onApply: (config: Record<string, unknown>) => void;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const f = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", f);
    return () => document.removeEventListener("mousedown", f);
  }, []);

  const { data: views = [] } = useQuery<SavedView[]>({
    queryKey: ["views", resource],
    queryFn: () => apiFetch<SavedView[]>(`/api/v1/me/views?resource=${resource}`),
  });

  const save = useMutation({
    mutationFn: (name: string) =>
      apiFetch(`/api/v1/me/views`, { method: "POST", body: JSON.stringify({ resource, name, config }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["views", resource] }),
  });
  const del = useMutation({
    mutationFn: (id: string) => apiFetch(`/api/v1/me/views/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["views", resource] }),
  });

  return (
    <div className="relative" ref={ref}>
      <Button variant="outline" size="sm" onClick={() => setOpen((o) => !o)}>
        <Bookmark className="size-4" /> Views
      </Button>
      {open && (
        <div className="absolute right-0 z-40 mt-1 w-60 rounded-md border bg-popover p-1 shadow-md">
          {views.length === 0 && <p className="px-2 py-1.5 text-xs text-muted-foreground">No saved views.</p>}
          {views.map((v) => (
            <div key={v.id} className="flex items-center justify-between rounded-sm px-2 py-1 text-sm hover:bg-accent">
              <button type="button" className="flex-1 truncate text-left"
                onClick={() => { onApply(v.config); setOpen(false); }}>{v.name}</button>
              <X className="size-3.5 cursor-pointer text-muted-foreground hover:text-destructive"
                onClick={() => del.mutate(v.id)} />
            </div>
          ))}
          <button type="button"
            className="mt-1 block w-full rounded-sm border-t px-2 py-1.5 text-left text-sm hover:bg-accent"
            onClick={() => { const name = window.prompt("Save current view as:"); if (name) { save.mutate(name); setOpen(false); } }}>
            + Save current view…
          </button>
        </div>
      )}
    </div>
  );
}
