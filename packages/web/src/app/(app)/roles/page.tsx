"use client";

import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, ShieldCheck, KeyRound, Search } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DataGrid, type DataGridColumn } from "@/components/ui/data-grid";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose } from "@/components/ui/dialog";

interface Role {
  id: string;
  code: string;
  name: string;
  description?: string | null;
  organization_id?: string | null;
  is_system: boolean;
}
interface Permission { id: string; code: string; module: string; description?: string | null }

const PAGE = 20;

export default function RolesPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("code");
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Role | null>(null);

  const { data, isLoading, error } = useQuery<{ items: Role[]; total: number }>({
    queryKey: ["roles", q, sort, page],
    queryFn: () =>
      apiFetch<{ items: Role[]; total: number }>(
        `/api/v1/rbac/roles?q=${encodeURIComponent(q)}&sort=${sort}` +
        `&limit=${PAGE}&offset=${page * PAGE}`),
  });
  const roles = data?.items ?? [];
  const total = data?.total ?? 0;

  const del = useMutation({
    mutationFn: (id: string) => apiFetch(`/api/v1/rbac/roles/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["roles"] }),
  });

  const columns: DataGridColumn<Role>[] = [
    { key: "code", header: "Code", sortable: true, className: "font-mono text-xs" },
    {
      key: "name", header: "Name", sortable: true,
      cell: (r) => (
        <>
          {r.name}
          {r.is_system && (
            <span className="ml-2 inline-flex items-center gap-1 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
              <ShieldCheck className="size-3" /> system
            </span>
          )}
        </>
      ),
    },
    {
      key: "scope", header: "Scope", className: "text-muted-foreground",
      cell: (r) => (r.organization_id ? "Organization" : "Global"),
    },
    {
      key: "actions", header: "Actions", align: "right", headClassName: "w-28",
      cell: (r) => (
        <>
          <Button variant="ghost" size="icon" title="Edit permissions" onClick={() => setEditing(r)}>
            <KeyRound className="size-4" />
          </Button>
          <Button variant="ghost" size="icon" title={r.is_system ? "System role (protected)" : "Delete"}
            disabled={r.is_system || del.isPending} onClick={() => del.mutate(r.id)}>
            <Trash2 className="size-4" />
          </Button>
        </>
      ),
    },
  ];

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Toolbar — fixed */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Roles &amp; access</h1>
          <p className="text-sm text-muted-foreground">Roles bundle permissions; assign them to accounts (scoped).</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="h-9 w-56 pl-8" placeholder="Search code / name"
              value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} />
          </div>
          <NewRoleDialog open={open} setOpen={setOpen} />
        </div>
      </div>

      <DataGrid<Role>
        columns={columns}
        rows={roles}
        rowKey={(r) => r.id}
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
        emptyLabel="No roles. Reseed a profile or create one."
      />

      {editing && <PermissionsDialog role={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function NewRoleDialog({ open, setOpen }: { open: boolean; setOpen: (b: boolean) => void }) {
  const qc = useQueryClient();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");

  function reset() { setCode(""); setName(""); setDescription(""); setError(""); }

  const create = useMutation({
    mutationFn: () =>
      apiFetch("/api/v1/rbac/roles", {
        method: "POST",
        body: JSON.stringify({ code, name, description: description || null }),
      }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["roles"] }); setOpen(false); reset(); },
    onError: (e: Error) => setError(e.message || "Create failed"),
  });

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) reset(); }}>
      <DialogTrigger asChild>
        <Button size="sm"><Plus className="size-4" /> New role</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>New role</DialogTitle></DialogHeader>
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <div className="space-y-1.5">
            <Label htmlFor="code">Code</Label>
            <Input id="code" required value={code} onChange={(e) => setCode(e.target.value)} placeholder="auditor" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="name">Name</Label>
            <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Auditor" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="desc">Description</Label>
            <Input id="desc" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Read-only access to records" />
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

function PermissionsDialog({ role, onClose }: { role: Role; onClose: () => void }) {
  const qc = useQueryClient();
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Set<string> | null>(null);

  const { data: catalog = [] } = useQuery<Permission[]>({
    queryKey: ["permissions"],
    queryFn: () => apiFetch<Permission[]>(`/api/v1/rbac/permissions`),
  });

  const { data: current } = useQuery<{ role_id: string; codes: string[] }>({
    queryKey: ["role-perms", role.id],
    queryFn: () => apiFetch(`/api/v1/rbac/roles/${role.id}/permissions`),
  });

  // Initialise the working set once the role's current grants arrive.
  const working = selected ?? (current ? new Set(current.codes) : null);

  const grouped = useMemo(() => {
    const m = new Map<string, Permission[]>();
    for (const p of catalog) {
      const list = m.get(p.module) ?? [];
      list.push(p);
      m.set(p.module, list);
    }
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [catalog]);

  function toggle(code: string) {
    const next = new Set(working ?? []);
    if (next.has(code)) next.delete(code); else next.add(code);
    setSelected(next);
  }

  const save = useMutation({
    mutationFn: () =>
      apiFetch(`/api/v1/rbac/roles/${role.id}/permissions`, {
        method: "PUT",
        body: JSON.stringify({ codes: [...(working ?? [])] }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["role-perms", role.id] });
      onClose();
    },
    onError: (e: Error) => setError(e.message || "Save failed"),
  });

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Permissions — {role.name}</DialogTitle>
        </DialogHeader>
        {role.is_system && (
          <p className="rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
            System role — permissions are protected and cannot be changed.
          </p>
        )}
        <div className="max-h-[55vh] space-y-4 overflow-auto pr-1">
          {working === null && <p className="text-sm text-muted-foreground">Loading…</p>}
          {working !== null && grouped.map(([module, perms]) => (
            <div key={module} className="space-y-1.5">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{module}</p>
              <div className="grid grid-cols-2 gap-1.5">
                {perms.map((p) => (
                  <label key={p.code} className="flex items-center gap-2 rounded-md px-2 py-1 text-sm hover:bg-accent">
                    <input
                      type="checkbox"
                      className="size-4 accent-[hsl(var(--primary))]"
                      checked={working.has(p.code)}
                      disabled={role.is_system}
                      onChange={() => toggle(p.code)}
                    />
                    <span className="font-mono text-xs">{p.code}</span>
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose}>Close</Button>
          <Button type="button" disabled={role.is_system || save.isPending || working === null}
            onClick={() => save.mutate()}>
            {save.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
