"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Check } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { DataGrid, type DataGridColumn } from "@/components/ui/data-grid";
import { DetailPanel } from "@/components/ui/detail-panel";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose } from "@/components/ui/dialog";
import { useOrganizations, orgLabel } from "@/lib/use-organizations";

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
const PAGE = 20;

export default function LocationsPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const sel = searchParams.get("sel") ?? "";
  const [orgId, setOrgId] = useState("");
  const [sort, setSort] = useState("code");
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState(false);

  const select = (id: string) => router.replace(`${pathname}?sel=${id}`, { scroll: false });
  const clearSel = () => router.replace(pathname, { scroll: false });

  // Organizations the caller can access — drives the scope selector. Sites are
  // org-scoped at the API, so we need a chosen org before listing/creating.
  const { orgs, truncated: orgsTruncated } = useOrganizations();

  // Default to the first accessible org once loaded.
  useEffect(() => {
    if (!orgId && orgs.length > 0) setOrgId(orgs[0].id);
  }, [orgs, orgId]);

  const { data, isLoading, error } = useQuery<{ items: Site[]; total: number }>({
    queryKey: ["sites", orgId, sort, page],
    enabled: !!orgId,
    queryFn: () =>
      apiFetch<{ items: Site[]; total: number }>(
        `/api/v1/modules/location/sites?organization_id=${orgId}&sort=${sort}` +
        `&limit=${PAGE}&offset=${page * PAGE}`,
      ),
  });
  const rows = data?.items ?? [];
  const total = data?.total ?? 0;

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
          <Select
            className="max-w-56"
            value={orgId}
            onChange={(e) => { setOrgId(e.target.value); setPage(0); }}
            aria-label="Organization"
            title={orgsTruncated ? "Showing the first 200 organizations" : undefined}
          >
            {orgs.length === 0 && <option value="">No organization</option>}
            {orgs.map((o) => (
              <option key={o.id} value={o.id}>{orgLabel(o)}</option>
            ))}
          </Select>
          <NewSiteDialog open={open} setOpen={setOpen} orgId={orgId} />
        </div>
      </div>

      {/* Master-detail: list left, edit form right (deep-linkable ?sel=) */}
      <div className={`grid min-h-0 flex-1 gap-4 ${sel ? "lg:grid-cols-[1fr_minmax(380px,520px)]" : ""}`}>
        <DataGrid<Site>
          columns={columns}
          rows={rows}
          rowKey={(s) => s.id}
          total={total}
          page={page}
          pageSize={PAGE}
          onPageChange={setPage}
          sort={sort}
          onSortChange={(s) => { setSort(s); setPage(0); }}
          filters={{}}
          onFilterChange={() => undefined}
          isLoading={!!orgId && isLoading}
          error={!!error}
          onRowClick={(s) => select(s.id)}
          selectedId={sel}
          emptyLabel={orgId ? "No sites." : "Select an organization."}
        />
        {sel && <SiteDetail siteId={sel} onClose={clearSel} />}
      </div>
    </div>
  );
}

// Editable scalar fields of SiteUpdate (org_unit_id/parent_site_id refs +
// operating_hours/metadata JSON = parity follow-up).
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
    }
  }, [data, form]);

  const save = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = { is_primary: primary };
      for (const { key } of SITE_FIELDS) payload[key] = (form?.[key] ?? "") || null;
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
            disabled={save.isPending || form === null} onClick={() => save.mutate()}>
            {save.isPending ? "Saving…" : "Save"}
          </Button>
        </div>
      }
    >
      {form === null && <p className="text-sm text-muted-foreground">Loading…</p>}
      {form !== null && (
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
      )}
    </DetailPanel>
  );
}

function NewSiteDialog({ open, setOpen, orgId }: { open: boolean; setOpen: (b: boolean) => void; orgId: string }) {
  const qc = useQueryClient();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [siteType, setSiteType] = useState("branch");
  const [city, setCity] = useState("");
  const [countryCode, setCountryCode] = useState("");
  const [error, setError] = useState("");

  function reset() {
    setCode(""); setName(""); setSiteType("branch"); setCity(""); setCountryCode(""); setError("");
  }

  const create = useMutation({
    mutationFn: () =>
      apiFetch("/api/v1/modules/location/sites", {
        method: "POST",
        body: JSON.stringify({
          organization_id: orgId,
          code,
          name,
          site_type: siteType,
          city: city || null,
          country_code: countryCode ? countryCode.toUpperCase() : null,
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sites"] });
      setOpen(false);
      reset();
    },
    onError: (e: Error) => setError(e.message || "Create failed"),
  });

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) reset(); }}>
      <DialogTrigger asChild>
        <Button size="sm" disabled={!orgId}><Plus className="size-4" /> New</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>New site</DialogTitle></DialogHeader>
        <form
          className="space-y-3"
          onSubmit={(e) => { e.preventDefault(); create.mutate(); }}
        >
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="code">Code</Label>
              <Input id="code" required value={code} onChange={(e) => setCode(e.target.value)} placeholder="hq" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="type">Type</Label>
              <Select id="type" value={siteType} onChange={(e) => setSiteType(e.target.value)}>
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
            <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Head office" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="city">City</Label>
              <Input id="city" value={city} onChange={(e) => setCity(e.target.value)} placeholder="Malabo" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cc">Country (ISO-2)</Label>
              <Input id="cc" maxLength={2} value={countryCode} onChange={(e) => setCountryCode(e.target.value)} placeholder="GQ" />
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
