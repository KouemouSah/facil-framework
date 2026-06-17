"use client";

import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, ShieldCheck, KeyRound } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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

export default function RolesPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Role | null>(null);

  const { data: roles = [], isLoading, error } = useQuery<Role[]>({
    queryKey: ["roles"],
    queryFn: () => apiFetch<Role[]>(`/api/v1/rbac/roles`),
  });

  const del = useMutation({
    mutationFn: (id: string) => apiFetch(`/api/v1/rbac/roles/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["roles"] }),
  });

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Toolbar — fixed */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Roles &amp; access</h1>
          <p className="text-sm text-muted-foreground">Roles bundle permissions; assign them to accounts (scoped).</p>
        </div>
        <NewRoleDialog open={open} setOpen={setOpen} />
      </div>

      {/* Data region — the ONLY scrollable part */}
      <div className="min-h-0 flex-1 overflow-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Code</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Scope</TableHead>
              <TableHead className="w-28 text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={4} className="py-8 text-center text-muted-foreground">Loading…</TableCell></TableRow>
            )}
            {error && (
              <TableRow><TableCell colSpan={4} className="py-8 text-center text-destructive">Failed to load.</TableCell></TableRow>
            )}
            {!isLoading && !error && roles.length === 0 && (
              <TableRow><TableCell colSpan={4} className="py-8 text-center text-muted-foreground">No roles. Reseed a profile or create one.</TableCell></TableRow>
            )}
            {roles.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="font-mono text-xs">{r.code}</TableCell>
                <TableCell>
                  {r.name}
                  {r.is_system && (
                    <span className="ml-2 inline-flex items-center gap-1 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                      <ShieldCheck className="size-3" /> system
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-muted-foreground">{r.organization_id ? "Organization" : "Global"}</TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="icon" title="Edit permissions" onClick={() => setEditing(r)}>
                    <KeyRound className="size-4" />
                  </Button>
                  <Button variant="ghost" size="icon" title={r.is_system ? "System role (protected)" : "Delete"}
                    disabled={r.is_system || del.isPending} onClick={() => del.mutate(r.id)}>
                    <Trash2 className="size-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

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
