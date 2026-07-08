"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { ChevronsUpDown, X } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

/**
 * Server-side searchable picker for an existing `address` (party module). Mirrors
 * PartyCombobox but WITHOUT inline-create — an address needs a full form (line/
 * city/country), so creation is done via AddressField, not a one-field create.
 * Built on the Popover primitive (portaled → never clipped). `value` is the id.
 */
interface Addr { id: string; label: string | null; line1: string | null; city: string | null }

const ABASE = "/api/v1/modules/party/addresses";
const addrLabel = (a: Addr) => a.label || a.line1 || a.city || `#${a.id.slice(0, 8)}`;

export function AddressCombobox({ value, onChange, placeholder, disabled = false }: {
  value: string;
  onChange: (id: string) => void;
  placeholder?: string;
  disabled?: boolean;
}) {
  const t = useTranslations("combobox");
  const ph = placeholder ?? t("search_address");
  const [open, setOpen] = useState(false);
  const [term, setTerm] = useState("");
  const [debounced, setDebounced] = useState("");

  useEffect(() => { const h = setTimeout(() => setDebounced(term), 250); return () => clearTimeout(h); }, [term]);

  const { data: current } = useQuery<Addr | null>({
    queryKey: ["address-one", value], enabled: !!value,
    queryFn: () => apiFetch<Addr>(`${ABASE}/${value}`).catch(() => null),
  });
  const { data, isFetching } = useQuery<{ items: Addr[] }>({
    queryKey: ["address-search", debounced], enabled: open && !disabled,
    queryFn: () => apiFetch(`${ABASE}?q=${encodeURIComponent(debounced)}&limit=20`),
  });
  const results = data?.items ?? [];

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild disabled={disabled}>
        <button type="button"
          className="flex h-9 w-full items-center justify-between rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50">
          <span className={cn("truncate", !value && "text-muted-foreground")}>
            {value ? (current ? addrLabel(current) : "…") : ph}
          </span>
          <span className="flex items-center gap-1">
            {value && !disabled && (
              <X className="size-3.5 text-muted-foreground hover:text-foreground"
                onClick={(e) => { e.stopPropagation(); e.preventDefault(); onChange(""); }} />
            )}
            <ChevronsUpDown className="size-4 opacity-50" />
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="max-h-64 w-[var(--radix-popover-trigger-width)] overflow-auto">
        <input autoFocus value={term} onChange={(e) => setTerm(e.target.value)} placeholder={ph}
          className="mb-1 h-8 w-full rounded-sm border border-input bg-background px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" />
        {isFetching && <p className="px-2 py-1.5 text-xs text-muted-foreground">{t("searching")}</p>}
        {!isFetching && results.length === 0 && <p className="px-2 py-1.5 text-xs text-muted-foreground">{t("no_matches")}</p>}
        {results.map((a) => (
          <button key={a.id} type="button"
            className={cn("block w-full truncate rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent", a.id === value && "bg-accent")}
            onClick={() => { onChange(a.id); setOpen(false); }}>
            {addrLabel(a)}{a.city ? ` · ${a.city}` : ""}
          </button>
        ))}
      </PopoverContent>
    </Popover>
  );
}
