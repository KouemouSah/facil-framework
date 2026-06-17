"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Check } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { codeField, requiredText, optionalText } from "@/lib/form-schemas";
import { ExportMenu } from "@/components/export-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { DataGrid, type DataGridColumn } from "@/components/ui/data-grid";
import { DetailPanel } from "@/components/ui/detail-panel";
import { JsonField } from "@/components/ui/json-field";
import { OrgCombobox } from "@/components/ui/org-combobox";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose } from "@/components/ui/dialog";
import { useFirstOrg } from "@/lib/use-organizations";
import { useServerTable, type ServerPage } from "@/lib/use-server-table";

interface Site {
  id: string;
  code: string;
  name: string;
  site_type: string;
  city?: string | null;
  country_code?: string | null;
  is_primary: boolean;
  is_active: boolean;
}
const DEFAULT_PAGE = 20;

export default function LocationsPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const sel = searchParams.get("sel") ?? "";
  const [orgId, setOrgId] = useState("");
  const [open, setOpen] = useState(false);

  const select = (id: string) => router.replace(`${pathname}?sel=${id}`, { scroll: false });
  const clearSel = () => router.replace(pathname, { scroll: false });

  // Sites are org-scoped at the API, so we need a chosen org before
  // listing/creating. The picker is OrgCombobox (server search); we default to
  // the caller's first accessible org (fetched as a single row, never the list).
  const firstOrgId = useFirstOrg();
  useEffect(() => {
    if (!orgId && firstOrgId) setOrgId(firstOrgId);
  }, [firstOrgId, orgId]);

  const table = useServerTable<Site>({
    resource: "sites",
    defaultSort: "code",
    defaultPageSize: DEFAULT_PAGE,
    enabled: !!orgId,
    fetchPage: ({ cursor, limit, sort, filters }) =>
      apiFetch<ServerPage<Site>>(
        `/api/v1/modules/location/sites?organization_id=${filters.organization_id ?? ""}` +
        `&sort=${sort}&limit=${limit}` + (cursor ? `&cursor=${encodeURIComponent(cursor)}` : "")),
  });
  // Mirror the org gate into the table filter so the query re-keys + the cursor
  // stack resets when the org changes (org is a resource-specific gate, not a
  // column filter; the hook's reset machinery handles it).
  const setTableFilter = table.onFilterChange;
  useEffect(() => { setTableFilter("organization_id", orgId); }, [orgId, setTableFilter]);
  const rows = table.rows;

  const del = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/v1/modules/location/sites/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sites"] }),
  });

  const columns: DataGridColumn<Site>[] = [
    { key: "code", header: "Code", sortable: true, className: "font-mono text-xs" },
    {
      key: "name", header: "Name", sortable: true,
      cell: (s) => (
        <>{s.name}{s.is_primary && <span className="ml-2 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">primary</span>}</>
      ),
    },
    { key: "site_type", header: "Type", sortable: true, className: "text-muted-foreground" },
    {
      key: "city", header: "City", sortable: true, className: "text-muted-foreground",
      cell: (s) => [s.city, s.country_code].filter(Boolean).join(", "),
    },
    {
      key: "actions", header: "Actions", align: "right", headClassName: "w-16", stopClick: true,
      cell: (s) => (
        <Button variant="ghost" size="icon" title="Delete"
          onClick={() => del.mutate(s.id)} disabled={del.isPending}>
          <Trash2 className="size-4" />
        </Button>
      ),
    },
  ];

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Toolbar — fixed (does not scroll with the data) */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Sites</h1>
          <p className="text-sm text-muted-foreground">Physical sites and branches per organization.</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-64">
            <OrgCombobox value={orgId} allowNone={false}
              placeholder="Search organization…"
              onChange={(id) => setOrgId(id)} />
          </div>
          <ExportMenu filename="sites" disabled={!orgId}
            path={`/api/v1/modules/location/sites/export?organization_id=${orgId}&sort=${table.sort}`} />
          <NewSiteDialog open={open} setOpen={setOpen} orgId={orgId} />
        </div>
      </div>

      {/* Master-detail: list left, edit form right (deep-linkable ?sel=) */}
      <div className={`grid min-h-0 flex-1 gap-4 ${sel ? "lg:grid-cols-[1fr_minmax(380px,520px)]" : ""}`}>
        <DataGrid<Site>
          mode="cursor"
          columns={columns}
          rows={rows}
          rowKey={(s) => s.id}
          pageSize={table.pageSize}
          onPageSizeChange={table.onPageSizeChange}
          sort={table.sort}
          onSortChange={table.onSortChange}
          filters={table.filters}
          onFilterChange={table.onFilterChange}
          hasPrev={table.hasPrev}
          hasNext={table.hasNext}
          onPrev={table.onPrev}
          onNext={table.onNext}
          count={table.count}
          capped={table.capped}
          isLoading={!!orgId && table.isLoading}
          error={table.error}
          onRowClick={(s) => select(s.id)}
          selectedId={sel}
          emptyLabel={orgId ? "No sites." : "Select an organization."}
        />
        {sel && <SiteDetail siteId={sel} onClose={clearSel} />}
      </div>
    </div>
  );
}

// Editable scalar fields of SiteUpdate (org_unit_id/parent_site_id refs;
// operating_hours/metadata JSON are edited via the JsonField editors below).
const SITE_FIELDS: { key: string; label: string }[] = [
  { key: "name", label: "Name" },
  { key: "site_type", label: "Type" },
  { key: "address_line1", label: "Address line 1" },
  { key: "address_line2", label: "Address line 2" },
  { key: "city", label: "City" },
  { key: "region", label: "Region" },
  { key: "country_code", label: "Country (ISO-2)" },
  { key: "postal_code", label: "Postal code" },
  { key: "phone", label: "Phone" },
  { key: "email", label: "Email" },
  { key: "timezone", label: "Timezone" },
  { key: "notes", label: "Notes" },
];

function SiteDetail({ siteId, onClose }: { siteId: string; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState<Record<string, string> | null>(null);
  const [primary, setPrimary] = useState(false);
  const [operatingHours, setOperatingHours] = useState<unknown>({});
  const [metadata, setMetadata] = useState<unknown>({});
  const [jsonOk, setJsonOk] = useState({ operating_hours: true, metadata: true });
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const { data } = useQuery<Record<string, unknown>>({
    queryKey: ["site", siteId],
    queryFn: () => apiFetch(`/api/v1/modules/location/sites/${siteId}`),
  });

  useEffect(() => {
    if (data && !form) {
      const f: Record<string, string> = {};
      for (const { key } of SITE_FIELDS) f[key] = (data[key] as string) ?? "";
      setForm(f);
      setPrimary(Boolean(data.is_primary));
      setOperatingHours(data.operating_hours ?? {});
      setMetadata(data.metadata ?? {});
      setJsonOk({ operating_hours: true, metadata: true });
    }
  }, [data, form]);

  const save = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = { is_primary: primary };
      for (const { key } of SITE_FIELDS) payload[key] = (form?.[key] ?? "") || null;
      payload.operating_hours = operatingHours;
      payload.metadata = metadata;
      return apiFetch(`/api/v1/modules/location/sites/${siteId}`, {
        method: "PUT",
        headers: data?.etag ? { "If-Match": String(data.etag) } : undefined,
        body: JSON.stringify(payload),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["site", siteId] });
      qc.invalidateQueries({ queryKey: ["sites"] });
      setSaved(true);
    },
    onError: (e: { status?: number; message?: string }) => {
      if (e.status === 409) {
        setError("Changed elsewhere — reloading the latest.");
        setForm(null);
        qc.invalidateQueries({ queryKey: ["site", siteId] });
      } else { setError(e.message || "Save failed"); }
    },
  });

  function set(k: string, v: string) {
    setForm((f) => (f ? { ...f, [k]: v } : f));
    setSaved(false);
  }

  return (
    <DetailPanel
      title={(data?.name as string) || "Site"}
      subtitle={data?.code ? `code ${data.code}` : undefined}
      onClose={onClose}
      footer={
        <div className="flex items-center gap-2">
          {saved && <span className="flex items-center gap-1 text-sm text-emerald-600"><Check className="size-4" /> Saved</span>}
          {error && <span className="text-sm text-destructive">{error}</span>}
          <Button type="button" size="sm" className="ml-auto"
            disabled={save.isPending || form === null || !jsonOk.operating_hours || !jsonOk.metadata}
            onClick={() => save.mutate()}>
            {save.isPending ? "Saving…" : "Save"}
          </Button>
        </div>
      }
    >
      {form === null && <p className="text-sm text-muted-foreground">Loading…</p>}
      {form !== null && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {SITE_FIELDS.map(({ key, label }) => (
              <div key={key} className="space-y-1.5">
                <Label htmlFor={`site-${key}`}>{label}</Label>
                <Input id={`site-${key}`} value={form[key]} onChange={(e) => set(key, e.target.value)} />
              </div>
            ))}
            <label className="flex items-center gap-2 pt-2 text-sm">
              <input type="checkbox" className="size-4 accent-[hsl(var(--primary))]"
                checked={primary} onChange={(e) => { setPrimary(e.target.checked); setSaved(false); }} />
              Primary site
            </label>
          </div>
          <JsonField id="site-operating_hours" label="Operating hours (JSON)"
            value={data?.operating_hours}
            hint='e.g. {"mon": ["09:00-17:00"], "sat": []}'
            onChange={(v, ok) => { setJsonOk((s) => ({ ...s, operating_hours: ok })); if (ok) setOperatingHours(v); setSaved(false); }} />
          <JsonField id="site-metadata" label="Metadata (JSON)"
            value={data?.metadata}
            hint="Free-form site metadata."
            onChange={(v, ok) => { setJsonOk((s) => ({ ...s, metadata: ok })); if (ok) setMetadata(v); setSaved(false); }} />
        </div>
      )}
    </DetailPanel>
  );
}

const siteForm = z.object({
  code: codeField,
  name: requiredText("Name"),
  site_type: z.enum(["branch", "headquarters", "warehouse", "office", "point_of_sale"]),
  city: optionalText(120),
  country_code: z.string().trim().regex(/^[A-Za-z]{2}$/, "Two-letter ISO code")
    .optional().or(z.literal("")),
});
type SiteForm = z.infer<typeof siteForm>;

function NewSiteDialog({ open, setOpen, orgId }: { open: boolean; setOpen: (b: boolean) => void; orgId: string }) {
  const qc = useQueryClient();
  const [error, setError] = useState("");
  const { register, handleSubmit, reset, formState: { errors } } = useForm<SiteForm>({
    resolver: zodResolver(siteForm),
    defaultValues: { code: "", name: "", site_type: "branch", city: "", country_code: "" },
  });

  const create = useMutation({
    mutationFn: (values: SiteForm) =>
      apiFetch("/api/v1/modules/location/sites", {
        method: "POST",
        body: JSON.stringify({
          organization_id: orgId,
          code: values.code,
          name: values.name,
          site_type: values.site_type,
          city: values.city || null,
          country_code: values.country_code ? values.country_code.toUpperCase() : null,
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sites"] });
      setOpen(false);
      reset(); setError("");
    },
    onError: (e: Error) => setError(e.message || "Create failed"),
  });

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) { reset(); setError(""); } }}>
      <DialogTrigger asChild>
        <Button size="sm" disabled={!orgId}><Plus className="size-4" /> New</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>New site</DialogTitle></DialogHeader>
        <form className="space-y-3" onSubmit={handleSubmit((v) => create.mutate(v))}>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="code">Code</Label>
              <Input id="code" {...register("code")} placeholder="hq" />
              {errors.code && <p className="text-xs text-destructive">{errors.code.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="type">Type</Label>
              <Select id="type" {...register("site_type")}>
                <option value="branch">Branch</option>
                <option value="headquarters">Headquarters</option>
                <option value="warehouse">Warehouse</option>
                <option value="office">Office</option>
                <option value="point_of_sale">Point of sale</option>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="name">Name</Label>
            <Input id="name" {...register("name")} placeholder="Head office" />
            {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="city">City</Label>
              <Input id="city" {...register("city")} placeholder="Malabo" />
              {errors.city && <p className="text-xs text-destructive">{errors.city.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cc">Country (ISO-2)</Label>
              <Input id="cc" maxLength={2} {...register("country_code")} placeholder="GQ" />
              {errors.country_code && <p className="text-xs text-destructive">{errors.country_code.message}</p>}
            </div>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <DialogClose asChild><Button type="button" variant="ghost">Cancel</Button></DialogClose>
            <Button type="submit" disabled={create.isPending || !orgId}>{create.isPending ? "Creating…" : "Create"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
