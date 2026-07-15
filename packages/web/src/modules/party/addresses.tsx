"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Plus, Trash2, Search } from "lucide-react";
import { toast } from "@/lib/toast";
import { ApiError } from "@/lib/api";
import { DataGrid, RecordSurface } from "@/components/shared";
import { type DataGridColumn } from "@/components/ui/data-grid";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { RefSelect } from "@/components/ui/ref-select";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useServerTable } from "@/lib/use-server-table";
import { usePermissions } from "@/lib/use-permissions";
import type { TabProps } from "./page";
import {
  createAddress, deleteAddress, getAddress, listAddresses, updateAddress, type Address,
} from "./api";

const addressLine = (a: Address) => a.label || a.line1 || a.city || "—";

export function AddressesTab({ sel, isNew, openCreate, openEdit, closeSurface }: TabProps) {
  const t = useTranslations("directory");
  const qc = useQueryClient();
  const { can } = usePermissions();
  const canCreate = can("party.create");
  const canUpdate = can("party.update");
  const canDelete = can("party.delete");
  const [pendingDelete, setPendingDelete] = useState<Address | null>(null);

  const table = useServerTable<Address>({
    resource: "addresses", defaultSort: "-created_at", defaultPageSize: 20,
    fetchPage: ({ cursor, limit, sort, filters, q }) => listAddresses({ q, sort, limit, cursor, filters }),
  });

  const del = useMutation({
    mutationFn: (a: Address) => deleteAddress(a.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["addresses"] }); toast({ variant: "success", title: t("toast.deleted") }); },
    onError: (e: unknown) => toast({ variant: "error", title: t("toast.delete_failed"), description: e instanceof ApiError ? e.message : undefined }),
  });

  const columns: DataGridColumn<Address>[] = [
    { key: "address", header: t("a.address"), cell: (a) => addressLine(a) },
    { key: "city", header: t("a.city"), sortable: true, className: "text-muted-foreground", cell: (a) => a.city || "—" },
    { key: "postal_code", header: t("a.postal_code"), className: "text-muted-foreground", cell: (a) => a.postal_code || "—" },
    {
      key: "status", header: t("status"), stopClick: true,
      filter: { type: "select", options: [{ value: "1", label: t("active") }, { value: "0", label: t("inactive") }] },
      cell: (a) => <Badge variant={a.is_active ? "secondary" : "outline"}>{a.is_active ? t("active") : t("inactive")}</Badge>,
    },
    ...(canDelete ? [{
      key: "actions", header: "", align: "right" as const, headClassName: "w-12", stopClick: true,
      cell: (a: Address) => (
        <Button variant="ghost" size="icon" title={t("delete.confirm")} disabled={del.isPending}
          onClick={() => setPendingDelete(a)}><Trash2 className="size-4" /></Button>
      ),
    }] : []),
  ];

  const surfaceOpen = (isNew && canCreate) || !!sel;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex items-center gap-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="h-9 w-56 pl-8" placeholder={t("a.search")} value={table.q} onChange={(e) => table.setQ(e.target.value)} />
        </div>
        {canCreate && <Button size="sm" className="ml-auto" onClick={openCreate}><Plus className="size-4" /> {t("a.new")}</Button>}
      </div>
      <div className="flex min-h-0 flex-1 gap-4">
        <div className="min-w-0 flex-1">
          <DataGrid<Address> mode="cursor" columns={columns} rows={table.rows} rowKey={(a) => a.id}
            pageSize={table.pageSize} onPageSizeChange={table.onPageSizeChange} sort={table.sort} onSortChange={table.onSortChange}
            filters={table.filters} onFilterChange={table.onFilterChange} hasPrev={table.hasPrev} hasNext={table.hasNext}
            onPrev={table.onPrev} onNext={table.onNext} count={table.count} capped={table.capped}
            isLoading={table.isLoading} error={table.error} onRowClick={(a) => openEdit(a.id)} selectedId={sel} emptyLabel={t("a.empty")} />
        </div>
        {surfaceOpen && (
          isNew
            ? (canCreate && <AddressCreateSurface onClose={closeSurface} onSaved={() => table.refetch()} />)
            : <AddressEditSurface key={sel} addressId={sel} readOnly={!canUpdate} onClose={closeSurface} />
        )}
      </div>
      <ConfirmDialog open={!!pendingDelete} onOpenChange={(o) => { if (!o) setPendingDelete(null); }} danger
        title={t("a.delete_title")} body={t("a.delete_body", { name: pendingDelete ? addressLine(pendingDelete) : "" })} confirmLabel={t("delete.confirm")}
        busy={del.isPending}
        onConfirm={() => { if (pendingDelete) del.mutate(pendingDelete); setPendingDelete(null); }}
        onCancel={() => setPendingDelete(null)} />
    </div>
  );
}

function AddressCreateSurface({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const t = useTranslations("directory");
  return (
    <RecordSurface title={t("a.new_title")} resourceKey="addresses" onClose={onClose}>
      <AddressForm mode="create" initial={null} readOnly={false} onClose={onClose} onSaved={onSaved} />
    </RecordSurface>
  );
}

function AddressEditSurface({ addressId, readOnly, onClose }: { addressId: string; readOnly: boolean; onClose: () => void }) {
  const t = useTranslations("directory");
  const { data, isError, isLoading } = useQuery({ queryKey: ["address", addressId], queryFn: () => getAddress(addressId) });
  return (
    <RecordSurface title={data ? addressLine(data) : t("a.edit_title")} resourceKey="addresses" onClose={onClose} loading={isLoading}>
      {isError && <p className="text-sm text-destructive">{t("load_error")}</p>}
      {/* Remount on reload (save OR 409 refetch) so stale edits never re-save. */}
      {data && <AddressForm key={data.etag ?? addressId} mode="edit" initial={data} readOnly={readOnly} onClose={onClose} onSaved={() => undefined} />}
    </RecordSurface>
  );
}

function AddressForm({ mode, initial, readOnly, onClose, onSaved }: {
  mode: "create" | "edit"; initial: Address | null; readOnly: boolean; onClose: () => void; onSaved: () => void;
}) {
  const t = useTranslations("directory");
  const qc = useQueryClient();
  const [label, setLabel] = useState(initial?.label ?? "");
  const [line1, setLine1] = useState(initial?.line1 ?? "");
  const [line2, setLine2] = useState(initial?.line2 ?? "");
  const [city, setCity] = useState(initial?.city ?? "");
  const [postal, setPostal] = useState(initial?.postal_code ?? "");
  const [countryId, setCountryId] = useState(initial?.country_id ?? "");
  const [regionId, setRegionId] = useState(initial?.country_region_id ?? "");
  const [lat, setLat] = useState(initial?.latitude != null ? String(initial.latitude) : "");
  const [lng, setLng] = useState(initial?.longitude != null ? String(initial.longitude) : "");
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [errors, setErrors] = useState<{ lat?: string; lng?: string; form?: string }>({});

  const save = useMutation({
    mutationFn: () => {
      const next: typeof errors = {};
      if (lat.trim() && Number.isNaN(Number(lat))) next.lat = t("a.err_number");
      if (lng.trim() && Number.isNaN(Number(lng))) next.lng = t("a.err_number");
      if (Object.keys(next).length) { setErrors(next); throw new Error("validation"); }
      setErrors({});
      const body = {
        label: label || null, line1: line1 || null, line2: line2 || null, city: city || null,
        postal_code: postal || null, country_id: countryId || null, country_region_id: regionId || null,
        latitude: lat.trim() ? Number(lat) : null, longitude: lng.trim() ? Number(lng) : null, is_active: isActive,
      };
      return mode === "create" ? createAddress(body) : updateAddress(initial!.id, body, initial?.etag);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["addresses"] });
      if (initial) qc.invalidateQueries({ queryKey: ["address", initial.id] });
      toast({ variant: "success", title: mode === "create" ? t("toast.created") : t("toast.saved") });
      onSaved();
      if (mode === "create") onClose();
    },
    onError: (e: unknown) => {
      if (e instanceof Error && e.message === "validation") return;
      if (e instanceof ApiError && e.status === 409) {
        toast({ variant: "error", title: t("conflict") });
        if (initial) qc.invalidateQueries({ queryKey: ["address", initial.id] });
      } else {
        setErrors({ form: e instanceof ApiError ? e.message : t("toast.save_failed") });
      }
    },
  });

  const set = (fn: (v: string) => void) => (e: React.ChangeEvent<HTMLInputElement>) => fn(e.target.value);

  return (
    <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (!readOnly) save.mutate(); }}>
      <div className="space-y-1.5">
        <Label htmlFor="a-label">{t("a.f_label")}</Label>
        <Input id="a-label" value={label} disabled={readOnly} onChange={set(setLabel)} placeholder={t("a.f_label_hint")} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="a-line1">{t("a.f_line1")}</Label>
        <Input id="a-line1" value={line1} disabled={readOnly} onChange={set(setLine1)} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="a-line2">{t("a.f_line2")}</Label>
        <Input id="a-line2" value={line2} disabled={readOnly} onChange={set(setLine2)} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="a-city">{t("a.city")}</Label>
          <Input id="a-city" value={city} disabled={readOnly} onChange={set(setCity)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="a-postal">{t("a.postal_code")}</Label>
          <Input id="a-postal" value={postal} disabled={readOnly} onChange={set(setPostal)} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label>{t("a.country")}</Label>
          {/* Country/region come from the reference module → this form also needs the
              `reference.read` permission; without it RefSelect shows no matches. */}
          {/* Region cascades off the chosen country (RefSelect dependent filter). */}
          <RefSelect resource="countries" value={countryId} disabled={readOnly}
            onChange={(id) => { setCountryId(id); setRegionId(""); }} placeholder={t("a.country_hint")} />
        </div>
        <div className="space-y-1.5">
          <Label>{t("a.region")}</Label>
          <RefSelect resource="regions" value={regionId} disabled={readOnly || !countryId}
            filter={countryId ? { country_id: countryId } : undefined}
            onChange={setRegionId} placeholder={t("a.region_hint")} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="a-lat">{t("a.latitude")}</Label>
          <Input id="a-lat" value={lat} disabled={readOnly} onChange={set(setLat)} inputMode="decimal" />
          {errors.lat && <p className="text-xs text-destructive">{errors.lat}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="a-lng">{t("a.longitude")}</Label>
          <Input id="a-lng" value={lng} disabled={readOnly} onChange={set(setLng)} inputMode="decimal" />
          {errors.lng && <p className="text-xs text-destructive">{errors.lng}</p>}
        </div>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" className="size-4 accent-[hsl(var(--primary))]" checked={isActive} disabled={readOnly}
          onChange={(e) => setIsActive(e.target.checked)} />
        {t("a.is_active")}
      </label>

      {errors.form && <p className="text-sm text-destructive">{errors.form}</p>}
      {!readOnly && (
        <div className="flex items-center justify-end gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>{t("cancel")}</Button>
          <Button type="submit" size="sm" disabled={save.isPending}>{save.isPending ? t("saving") : t("save")}</Button>
        </div>
      )}
    </form>
  );
}
