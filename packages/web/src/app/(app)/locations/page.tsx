"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Rows3, Rows2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose } from "@/components/ui/dialog";

interface Org { id: string; code: string; legal_name: string; display_name?: string }
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

const selectCls =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50";

export default function LocationsPage() {
  const qc = useQueryClient();
  const [orgId, setOrgId] = useState("");
  const [page, setPage] = useState(0);
  const [dense, setDense] = useState(false);
  const [open, setOpen] = useState(false);

  // Organizations the caller can access — drives the scope selector. Sites are
  // org-scoped at the API, so we need a chosen org before listing/creating.
  const { data: orgs = [] } = useQuery<Org[]>({
    queryKey: ["orgs", "all"],
    queryFn: () => apiFetch<Org[]>(`/api/v1/modules/organization/?limit=200&offset=0`),
  });

  // Default to the first accessible org once loaded.
  useEffect(() => {
    if (!orgId && orgs.length > 0) setOrgId(orgs[0].id);
  }, [orgs, orgId]);

  const { data: rows = [], isLoading, error } = useQuery<Site[]>({
    queryKey: ["sites", orgId, page],
    enabled: !!orgId,
    queryFn: () =>
      apiFetch<Site[]>(
        `/api/v1/modules/location/sites?organization_id=${orgId}&limit=${PAGE}&offset=${page * PAGE}`,
      ),
  });

  const del = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/v1/modules/location/sites/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sites"] }),
  });

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Toolbar — fixed (does not scroll with the data) */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Sites</h1>
          <p className="text-sm text-muted-foreground">Physical sites and branches per organization.</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            className={`${selectCls} max-w-56`}
            value={orgId}
            onChange={(e) => { setOrgId(e.target.value); setPage(0); }}
            aria-label="Organization"
          >
            {orgs.length === 0 && <option value="">No organization</option>}
            {orgs.map((o) => (
              <option key={o.id} value={o.id}>{o.display_name || o.legal_name}</option>
            ))}
          </select>
          <Button variant="outline" size="icon" title="Density"
            onClick={() => setDense((d) => !d)}>
            {dense ? <Rows3 className="size-4" /> : <Rows2 className="size-4" />}
          </Button>
          <NewSiteDialog open={open} setOpen={setOpen} orgId={orgId} />
        </div>
      </div>

      {/* Data region — the ONLY scrollable part, with a sticky header */}
      <div className="min-h-0 flex-1 overflow-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Code</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>City</TableHead>
              <TableHead className="w-16 text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {!orgId && (
              <TableRow><TableCell colSpan={5} className="py-8 text-center text-muted-foreground">Select an organization.</TableCell></TableRow>
            )}
            {orgId && isLoading && (
              <TableRow><TableCell colSpan={5} className="py-8 text-center text-muted-foreground">Loading…</TableCell></TableRow>
            )}
            {orgId && error && (
              <TableRow><TableCell colSpan={5} className="py-8 text-center text-destructive">Failed to load.</TableCell></TableRow>
            )}
            {orgId && !isLoading && !error && rows.length === 0 && (
              <TableRow><TableCell colSpan={5} className="py-8 text-center text-muted-foreground">No sites.</TableCell></TableRow>
            )}
            {rows.map((s) => (
              <TableRow key={s.id} className={dense ? "[&_td]:py-1" : ""}>
                <TableCell className="font-mono text-xs">{s.code}</TableCell>
                <TableCell>{s.name}{s.is_primary && <span className="ml-2 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">primary</span>}</TableCell>
                <TableCell className="text-muted-foreground">{s.site_type}</TableCell>
                <TableCell className="text-muted-foreground">{[s.city, s.country_code].filter(Boolean).join(", ")}</TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="icon" title="Delete"
                    onClick={() => del.mutate(s.id)} disabled={del.isPending}>
                    <Trash2 className="size-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination — server-side (the scale mechanism) */}
      <div className="flex items-center justify-end gap-2 text-sm">
        <span className="text-muted-foreground">Page {page + 1}</span>
        <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Prev</Button>
        <Button variant="outline" size="sm" disabled={rows.length < PAGE} onClick={() => setPage((p) => p + 1)}>Next</Button>
      </div>
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
              <select id="type" className={selectCls} value={siteType} onChange={(e) => setSiteType(e.target.value)}>
                <option value="branch">Branch</option>
                <option value="headquarters">Headquarters</option>
                <option value="warehouse">Warehouse</option>
                <option value="office">Office</option>
                <option value="point_of_sale">Point of sale</option>
              </select>
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
