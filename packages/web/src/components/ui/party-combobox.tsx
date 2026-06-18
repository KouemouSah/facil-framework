"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronsUpDown, Plus, X } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Server-side searchable party picker (the directory). Used to attach an
 * Organization's legal identity (`party_id`) or any third-party reference.
 * Mirrors OrgCombobox; adds inline "Create '<term>'" (Odoo create-and-pick) that
 * POSTs a minimal party (type=organization) and selects it. `value` is the id.
 */
interface Party {
  id: string;
  name: string;
  party_type?: string;
}

const PBASE = "/api/v1/modules/party/parties";

export function PartyCombobox({ value, onChange, placeholder = "Search party…",
  allowNone = true, noneLabel = "— none —", partyType = "organization", disabled = false }: {
  value: string;
  onChange: (id: string) => void;
  placeholder?: string;
  allowNone?: boolean;
  noneLabel?: string;
  /** party_type used when inline-creating. */
  partyType?: string;
  disabled?: boolean;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [term, setTerm] = useState("");
  const [debounced, setDebounced] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const boxRef = useRef<HTMLDivElement>(null);

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

  const { data: current } = useQuery<Party | null>({
    queryKey: ["party-one", value],
    enabled: !!value,
    queryFn: () => apiFetch<Party>(`${PBASE}/${value}`).catch(() => null),
  });

  const { data, isFetching } = useQuery<{ items: Party[] }>({
    queryKey: ["party-search", debounced],
    enabled: open && !disabled,
    queryFn: () => apiFetch(`${PBASE}?q=${encodeURIComponent(debounced)}&limit=20`),
  });
  const results = data?.items ?? [];
  const selectedLabel = value ? (current ? current.name : "…") : "";

  async function createInline() {
    setCreating(true); setError("");
    try {
      const created = await apiFetch<Party>(PBASE, {
        method: "POST",
        body: JSON.stringify({ name: term.trim(), party_type: partyType }),
      });
      await qc.invalidateQueries({ queryKey: ["party-search"] });
      onChange(created.id);
      setOpen(false); setTerm("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Create failed");
    } finally {
      setCreating(false);
    }
  }

  const showCreate = term.trim() && !results.some(
    (p) => p.name.toLowerCase() === term.trim().toLowerCase());

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
          {!isFetching && results.length === 0 && !showCreate && (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">No matches.</p>
          )}
          {results.map((p) => (
            <button key={p.id} type="button"
              className={cn("block w-full truncate rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent",
                p.id === value && "bg-accent")}
              onClick={() => { onChange(p.id); setOpen(false); }}>
              {p.name}
            </button>
          ))}
          {showCreate && (
            <button type="button" disabled={creating}
              className="mt-1 flex w-full items-center gap-1.5 rounded-sm border-t px-2 py-1.5 text-left text-sm text-primary hover:bg-accent disabled:opacity-50"
              onClick={createInline}>
              <Plus className="size-3.5" /> {creating ? "Creating…" : `Create “${term.trim()}”`}
            </button>
          )}
          {error && <p className="px-2 py-1.5 text-xs text-destructive">{error}</p>}
        </div>
      )}
    </div>
  );
}
