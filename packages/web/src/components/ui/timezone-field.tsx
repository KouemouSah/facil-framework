"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { ChevronsUpDown, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

/**
 * Searchable IANA time-zone picker (P2.5) — replaces the free-text timezone input.
 * Zones come from `Intl.supportedValuesOf("timeZone")` (all runtimes we target),
 * with a small fallback for older ones. Built on the Popover primitive. Value is
 * the tz id string ("" = none).
 */
function allZones(): string[] {
  try {
    const fn = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf;
    if (fn) return fn("timeZone");
  } catch {
    /* fall through */
  }
  return ["UTC", "Europe/Paris", "Europe/Madrid", "Europe/London", "America/New_York",
    "America/Los_Angeles", "Africa/Malabo", "Asia/Tokyo"];
}

export function TimezoneField({ value, onChange, disabled = false }: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  const t = useTranslations("combobox");
  const [open, setOpen] = useState(false);
  const [term, setTerm] = useState("");
  const zones = useMemo(allZones, []);
  const filtered = useMemo(() => {
    const q = term.trim().toLowerCase();
    return (q ? zones.filter((z) => z.toLowerCase().includes(q)) : zones).slice(0, 80);
  }, [zones, term]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild disabled={disabled}>
        <button type="button"
          className="flex h-9 w-full items-center justify-between rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50">
          <span className={cn("truncate", !value && "text-muted-foreground")}>{value || t("search")}</span>
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
        <input autoFocus value={term} onChange={(e) => setTerm(e.target.value)} placeholder={t("search")}
          className="mb-1 h-8 w-full rounded-sm border border-input bg-background px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" />
        {filtered.length === 0 && <p className="px-2 py-1.5 text-xs text-muted-foreground">{t("no_matches")}</p>}
        {filtered.map((z) => (
          <button key={z} type="button"
            className={cn("block w-full truncate rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent", z === value && "bg-accent")}
            onClick={() => { onChange(z); setOpen(false); }}>{z}</button>
        ))}
      </PopoverContent>
    </Popover>
  );
}
