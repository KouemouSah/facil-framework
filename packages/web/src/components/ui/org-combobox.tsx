"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronsUpDown, X } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { type Org, orgLabel } from "@/lib/use-organizations";

/**
 * Server-side searchable organization picker (backlog ERP item 3). Replaces the
 * 200-capped <Select>: it queries the backend `q` so it scales to any tenant
 * count. Lightweight (no combobox dependency): debounced search, click-to-select,
 * click-outside to close. `value` is the org id ("" = none).
 */
export function OrgCombobox({ value, onChange, placeholder = "Search organization…", allowNone = true, noneLabel = "— none —", disabled = false }: {
  value: string;
  onChange: (id: string) => void;
  placeholder?: string;
  allowNone?: boolean;
  noneLabel?: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [term, setTerm] = useState("");
  const [debounced, setDebounced] = useState("");
  const boxRef = useRef<HTMLDivElement>(null);

  // Debounce the search term (250ms).
  useEffect(() => {
    const t = setTimeout(() => setDebounced(term), 250);
    return () => clearTimeout(t);
  }, [term]);

  // Close on click outside.
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  // Resolve the current value's label (single fetch by id when set).
  const { data: current } = useQuery<Org | null>({
    queryKey: ["org-one", value],
    enabled: !!value,
    queryFn: () => apiFetch<Org>(`/api/v1/modules/organization/${value}`).catch(() => null),
  });

  const { data, isFetching } = useQuery<{ items: Org[]; total: number }>({
    queryKey: ["org-search", debounced],
    enabled: open,
    queryFn: () => apiFetch(`/api/v1/modules/organization/?q=${encodeURIComponent(debounced)}&limit=20`),
  });
  const results = data?.items ?? [];

  const selectedLabel = value ? (current ? orgLabel(current) : "…") : "";

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

      {open && (
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
          {results.map((o) => (
            <button key={o.id} type="button"
              className={cn("block w-full truncate rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent",
                o.id === value && "bg-accent")}
              onClick={() => { onChange(o.id); setOpen(false); }}>
              {orgLabel(o)} <span className="text-xs text-muted-foreground">· {o.code}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
