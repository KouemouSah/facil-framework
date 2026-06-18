"use client";

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, MapPin } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RefSelect } from "@/components/ui/ref-select";

/**
 * Reusable editor for the first-class `address` entity (party module). It owns
 * its own persistence — load (GET), then upsert (POST new / PUT existing with
 * If-Match) — and emits the resulting `address_id` via `onChange`. Consumers
 * (org HQ, sites, parties) just store the id as an FK; the address is reusable
 * master data, so an unlinked one is harmless.
 *
 * Country & region are managed pickers (RefSelect over the reference module);
 * region is filtered by the chosen country and disabled until one is picked —
 * clearing the country clears the region (keeps the region→country FK coherent).
 */
const ADDR = "/api/v1/modules/party/addresses";

interface AddressData {
  id?: string;
  line1?: string | null;
  line2?: string | null;
  city?: string | null;
  postal_code?: string | null;
  country_id?: string | null;
  country_region_id?: string | null;
  etag?: string;
}

const EMPTY: AddressData = {};

export function AddressField({ value, onChange, label = "Address", disabled = false }: {
  value: string;
  onChange: (addressId: string) => void;
  label?: string;
  disabled?: boolean;
}) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState<AddressData>(EMPTY);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const { data } = useQuery<AddressData>({
    queryKey: ["address", value],
    enabled: !!value,
    queryFn: () => apiFetch(`${ADDR}/${value}`),
  });

  // Seed the local draft once per linked address; reset when unlinked.
  useEffect(() => {
    if (value && data && loadedFor !== value) {
      setDraft(data); setLoadedFor(value); setDirty(false); setSaved(false); setError("");
    } else if (!value && loadedFor !== null) {
      setDraft(EMPTY); setLoadedFor(null); setDirty(false);
    }
  }, [value, data, loadedFor]);

  function set<K extends keyof AddressData>(key: K, v: AddressData[K]) {
    setDraft((d) => {
      const next = { ...d, [key]: v };
      if (key === "country_id" && !v) next.country_region_id = null;
      return next;
    });
    setDirty(true); setSaved(false);
  }

  async function save() {
    setSaving(true); setError("");
    const body = {
      line1: draft.line1 || null, line2: draft.line2 || null,
      city: draft.city || null, postal_code: draft.postal_code || null,
      country_id: draft.country_id || null,
      country_region_id: draft.country_region_id || null,
    };
    try {
      if (value) {
        await apiFetch(`${ADDR}/${value}`, {
          method: "PUT",
          headers: draft.etag ? { "If-Match": String(draft.etag) } : undefined,
          body: JSON.stringify(body),
        });
        setLoadedFor(null); // force reseed with the rotated etag
        await qc.invalidateQueries({ queryKey: ["address", value] });
      } else {
        const created = await apiFetch<{ id: string }>(ADDR, {
          method: "POST", body: JSON.stringify(body),
        });
        onChange(created.id);
      }
      setDirty(false); setSaved(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  const fieldDisabled = disabled || saving;

  return (
    <div className="space-y-2 rounded-md border p-3">
      <div className="flex items-center gap-1.5">
        <MapPin className="size-3.5 text-muted-foreground" />
        <Label className="text-xs font-medium text-muted-foreground">{label}</Label>
        {saved && (
          <span className="ml-auto flex items-center gap-1 text-xs text-emerald-600">
            <Check className="size-3" /> Saved
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <div className="space-y-1 sm:col-span-2">
          <Label htmlFor="addr-line1" className="text-xs">Line 1</Label>
          <Input id="addr-line1" value={draft.line1 ?? ""} disabled={fieldDisabled}
            onChange={(e) => set("line1", e.target.value)} />
        </div>
        <div className="space-y-1 sm:col-span-2">
          <Label htmlFor="addr-line2" className="text-xs">Line 2</Label>
          <Input id="addr-line2" value={draft.line2 ?? ""} disabled={fieldDisabled}
            onChange={(e) => set("line2", e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="addr-city" className="text-xs">City</Label>
          <Input id="addr-city" value={draft.city ?? ""} disabled={fieldDisabled}
            onChange={(e) => set("city", e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="addr-postal" className="text-xs">Postal code</Label>
          <Input id="addr-postal" value={draft.postal_code ?? ""} disabled={fieldDisabled}
            onChange={(e) => set("postal_code", e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Country</Label>
          <RefSelect resource="countries" value={draft.country_id ?? ""}
            disabled={fieldDisabled}
            onChange={(id) => set("country_id", id || null)} />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Region</Label>
          <RefSelect resource="regions" value={draft.country_region_id ?? ""}
            disabled={fieldDisabled || !draft.country_id}
            filter={draft.country_id ? { country_id: draft.country_id } : undefined}
            placeholder={draft.country_id ? "Search…" : "Pick a country first"}
            onChange={(id) => set("country_region_id", id || null)} />
        </div>
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}
      <div className="flex items-center gap-2">
        {dirty && !disabled && (
          <Button type="button" size="sm" variant="secondary" disabled={saving}
            onClick={save}>
            {saving ? "Saving…" : value ? "Save address" : "Create address"}
          </Button>
        )}
        {value && !dirty && (
          <span className="text-xs text-muted-foreground">Linked address #{value.slice(0, 8)}</span>
        )}
      </div>
    </div>
  );
}
