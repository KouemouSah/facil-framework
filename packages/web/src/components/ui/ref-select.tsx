"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronsUpDown, Plus, X } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Server-side searchable picker for reference master data (country / currency /
 * region). Generalises OrgCombobox over the reference module endpoints, so geo &
 * currency become managed dropdowns (vs the old free-text inputs) that scale to
 * the full ISO sets. Supports a dependent `filter` (e.g. regions of a country)
 * and `disabled` (e.g. region until a country is picked). `value` is the id.
 */
export interface RefItem {
  id: string;
  code: string;
  name: string;
  symbol?: string | null;
}

const REF_BASE = "/api/v1/modules/reference";

function defaultLabel(it: RefItem): string {
  // Currencies read better as "USD — US Dollar"; geo as "Name · CODE".
  return it.symbol !== undefined && it.symbol !== null
    ? `${it.code} — ${it.name}`
    : `${it.name} · ${it.code}`;
}

export function RefSelect({
  value, onChange, resource, filter, placeholder = "Search…",
  allowNone = true, noneLabel = "— none —", disabled = false, labelOf = defaultLabel,
  onRequestCreate,
}: {
  value: string;
  onChange: (id: string) => void;
  resource: "countries" | "currencies" | "regions";
  filter?: Record<string, string>;
  placeholder?: string;
  allowNone?: boolean;
  noneLabel?: string;
  disabled?: boolean;
  labelOf?: (item: RefItem) => string;
  /** Inline quick-create (Odoo "Create and Edit"): shows "+ Create '<term>'" when
   * the search has no exact match. The consumer opens its create form pre-filled. */
  onRequestCreate?: (term: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [term, setTerm] = useState("");
  const [debounced, setDebounced] = useState("");
  const boxRef = useRef<HTMLDivElement>(null);
  const filterKey = JSON.stringify(filter ?? {});

  useEffect(() => {
    const t = setTimeout(() => setDebounced(term), 250);
    return () => clearTimeout(t);
  }, [term]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  // Resolve the current value's label (single fetch by id).
  const { data: current } = useQuery<RefItem | null>({
    queryKey: ["ref-one", resource, value],
    enabled: !!value,
    queryFn: () => apiFetch<RefItem>(`${REF_BASE}/${resource}/${value}`).catch(() => null),
  });

  const { data, isFetching } = useQuery<{ items: RefItem[] }>({
    queryKey: ["ref-search", resource, debounced, filterKey],
    enabled: open && !disabled,
    queryFn: () => {
      const p = new URLSearchParams({ q: debounced, active: "1", limit: "20", ...(filter ?? {}) });
      return apiFetch(`${REF_BASE}/${resource}?${p.toString()}`);
    },
  });
  const results = data?.items ?? [];
  const selectedLabel = value ? (current ? labelOf(current) : "…") : "";

  return (
    <div className="relative" ref={boxRef}>
      <button type="button" disabled={disabled}
        className="flex h-9 w-full items-center justify-between rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        onClick={() => setOpen((o) => !o)}>
        <span className={cn("truncate", !value && "text-muted-foreground")}>
          {value ? selectedLabel : (allowNone ? noneLabel : placeholder)}
        </span>
        <span className="flex items-center gap-1">
          {value && !disabled && (
            <X className="size-3.5 text-muted-foreground hover:text-foreground"
              onClick={(e) => { e.stopPropagation(); onChange(""); }} />
          )}
          <ChevronsUpDown className="size-4 opacity-50" />
        </span>
      </button>

      {open && !disabled && (
        <div className="absolute z-40 mt-1 max-h-64 w-full overflow-auto rounded-md border bg-popover p-1 shadow-md">
          <input autoFocus value={term} onChange={(e) => setTerm(e.target.value)}
            placeholder={placeholder}
            className="mb-1 h-8 w-full rounded-sm border border-input bg-background px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" />
          {allowNone && (
            <button type="button" className="block w-full rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent"
              onClick={() => { onChange(""); setOpen(false); }}>{noneLabel}</button>
          )}
          {isFetching && <p className="px-2 py-1.5 text-xs text-muted-foreground">Searching…</p>}
          {!isFetching && results.length === 0 && (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">No matches.</p>
          )}
          {results.map((it) => (
            <button key={it.id} type="button"
              className={cn("block w-full truncate rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent",
                it.id === value && "bg-accent")}
              onClick={() => { onChange(it.id); setOpen(false); }}>
              {labelOf(it)}
            </button>
          ))}
          {onRequestCreate && term.trim() && !results.some(
            (it) => it.code.toLowerCase() === term.trim().toLowerCase()
              || it.name.toLowerCase() === term.trim().toLowerCase()) && (
            <button type="button"
              className="mt-1 flex w-full items-center gap-1.5 rounded-sm border-t px-2 py-1.5 text-left text-sm text-primary hover:bg-accent"
              onClick={() => { onRequestCreate(term.trim()); setOpen(false); }}>
              <Plus className="size-3.5" /> Create “{term.trim()}”
            </button>
          )}
        </div>
      )}
    </div>
  );
}
