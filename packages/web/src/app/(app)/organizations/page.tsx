"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Search } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DataGrid, type DataGridColumn } from "@/components/ui/data-grid";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose } from "@/components/ui/dialog";

interface Org { id: string; code: string; legal_name: string; display_name?: string }
const PAGE = 20;

export default function OrganizationsPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("code");
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState(false);

  const { data, isLoading, error } = useQuery<{ items: Org[]; total: number }>({
    queryKey: ["orgs", q, sort, page],
    queryFn: () =>
      apiFetch<{ items: Org[]; total: number }>(
        `/api/v1/modules/organization/?q=${encodeURIComponent(q)}&sort=${sort}` +
        `&limit=${PAGE}&offset=${page * PAGE}`),
  });
  const rows = data?.items ?? [];
  const total = data?.total ?? 0;

  const del = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/v1/modules/organization/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orgs"] }),
  });

  const columns: DataGridColumn<Org>[] = [
    { key: "code", header: "Code", sortable: true, className: "font-mono text-xs" },
    {
      key: "legal_name", header: "Legal name", sortable: true,
      cell: (o) => o.display_name || o.legal_name,
    },
    {
      key: "actions", header: "Actions", align: "right", headClassName: "w-16",
      cell: (o) => (
        <Button variant="ghost" size="icon" title="Delete"
          onClick={() => del.mutate(o.id)} disabled={del.isPending}>
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
          <h1 className="text-xl font-semibold tracking-tight">Organizations</h1>
          <p className="text-sm text-muted-foreground">Tenants you can access.</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="h-9 w-56 pl-8" placeholder="Search code / name"
              value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} />
          </div>
          <NewOrgDialog open={open} setOpen={setOpen} />
        </div>
      </div>

      <DataGrid<Org>
        columns={columns}
        rows={rows}
        rowKey={(o) => o.id}
        total={total}
        page={page}
        pageSize={PAGE}
        onPageChange={setPage}
        sort={sort}
        onSortChange={(s) => { setSort(s); setPage(0); }}
        filters={{}}
        onFilterChange={() => undefined}
        isLoading={isLoading}
        error={!!error}
        emptyLabel="No organizations."
      />
    </div>
  );
}

function NewOrgDialog({ open, setOpen }: { open: boolean; setOpen: (b: boolean) => void }) {
  const qc = useQueryClient();
  const [code, setCode] = useState("");
  const [legalName, setLegalName] = useState("");
  const [error, setError] = useState("");

  const create = useMutation({
    mutationFn: () =>
      apiFetch("/api/v1/modules/organization/", {
        method: "POST",
        body: JSON.stringify({ code, legal_name: legalName }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orgs"] });
      setOpen(false);
      setCode(""); setLegalName(""); setError("");
    },
    onError: (e: Error) => setError(e.message || "Create failed"),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm"><Plus className="size-4" /> New</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>New organization</DialogTitle></DialogHeader>
        <form
          className="space-y-3"
          onSubmit={(e) => { e.preventDefault(); create.mutate(); }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="code">Code</Label>
            <Input id="code" required value={code} onChange={(e) => setCode(e.target.value)} placeholder="acme" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="legal">Legal name</Label>
            <Input id="legal" required value={legalName} onChange={(e) => setLegalName(e.target.value)} placeholder="Acme Corp" />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <DialogClose asChild><Button type="button" variant="ghost">Cancel</Button></DialogClose>
            <Button type="submit" disabled={create.isPending}>{create.isPending ? "Creating…" : "Create"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
