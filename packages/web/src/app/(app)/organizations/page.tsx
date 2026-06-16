"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Rows3, Rows2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose } from "@/components/ui/dialog";

interface Org { id: string; code: string; legal_name: string; display_name?: string }
const PAGE = 20;

export default function OrganizationsPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(0);
  const [dense, setDense] = useState(false);
  const [open, setOpen] = useState(false);

  const { data: rows = [], isLoading, error } = useQuery<Org[]>({
    queryKey: ["orgs", page],
    queryFn: () =>
      apiFetch<Org[]>(`/api/v1/modules/organization/?limit=${PAGE}&offset=${page * PAGE}`),
  });

  const del = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/v1/modules/organization/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orgs"] }),
  });

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Toolbar — fixed (does not scroll with the data) */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Organizations</h1>
          <p className="text-sm text-muted-foreground">Tenants you can access.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" title="Density"
            onClick={() => setDense((d) => !d)}>
            {dense ? <Rows3 className="size-4" /> : <Rows2 className="size-4" />}
          </Button>
          <NewOrgDialog open={open} setOpen={setOpen} />
        </div>
      </div>

      {/* Data region — the ONLY scrollable part, with a sticky header */}
      <div className="min-h-0 flex-1 overflow-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Code</TableHead>
              <TableHead>Legal name</TableHead>
              <TableHead className="w-16 text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={3} className="py-8 text-center text-muted-foreground">Loading…</TableCell></TableRow>
            )}
            {error && (
              <TableRow><TableCell colSpan={3} className="py-8 text-center text-destructive">Failed to load.</TableCell></TableRow>
            )}
            {!isLoading && !error && rows.length === 0 && (
              <TableRow><TableCell colSpan={3} className="py-8 text-center text-muted-foreground">No organizations.</TableCell></TableRow>
            )}
            {rows.map((o) => (
              <TableRow key={o.id} className={dense ? "[&_td]:py-1" : ""}>
                <TableCell className="font-mono text-xs">{o.code}</TableCell>
                <TableCell>{o.display_name || o.legal_name}</TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="icon" title="Delete"
                    onClick={() => del.mutate(o.id)} disabled={del.isPending}>
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
