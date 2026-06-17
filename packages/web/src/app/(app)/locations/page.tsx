"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { DataGrid, type DataGridColumn } from "@/components/ui/data-grid";
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
  const [orgId, setOrgId] = useState("");
  const [sort, setSort] = useState("code");
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState(false);

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
      key: "actions", header: "Actions", align: "right", headClassName: "w-16",
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
        emptyLabel={orgId ? "No sites." : "Select an organization."}
      />
    </div>
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
