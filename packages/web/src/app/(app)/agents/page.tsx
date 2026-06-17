"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, KeyRound, Search } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose } from "@/components/ui/dialog";

interface Account {
  id: string;
  email?: string | null;
  account_number?: string | null;
  display_name?: string | null;
  organization_id?: string | null;
  status: string;
  is_active: boolean;
}
interface Org { id: string; legal_name: string; display_name?: string }
interface Role { id: string; code: string; name: string }
interface Assignment { id: string; role_id: string; organization_id?: string | null }

const PAGE = 20;
const STATUSES = ["pending_identity", "active", "suspended", "deactivated"];
const STATUS_STYLE: Record<string, string> = {
  active: "bg-emerald-500/10 text-emerald-600",
  pending_identity: "bg-amber-500/10 text-amber-600",
  suspended: "bg-orange-500/10 text-orange-600",
  deactivated: "bg-destructive/10 text-destructive",
};
const selectCls =
  "h-8 rounded-md border border-input bg-background px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50";

export default function AgentsPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState(false);
  const [rolesFor, setRolesFor] = useState<Account | null>(null);

  const { data: rows = [], isLoading, error } = useQuery<Account[]>({
    queryKey: ["accounts", q, page],
    queryFn: () =>
      apiFetch<Account[]>(
        `/api/v1/admin/accounts?q=${encodeURIComponent(q)}&limit=${PAGE}&offset=${page * PAGE}`,
      ),
  });

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      apiFetch(`/api/v1/admin/accounts/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Toolbar — fixed */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Agents &amp; accounts</h1>
          <p className="text-sm text-muted-foreground">Create accounts, set status, assign roles.</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="h-9 w-56 pl-8" placeholder="Search email / name / NIU"
              value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} />
          </div>
          <NewAccountDialog open={open} setOpen={setOpen} />
        </div>
      </div>

      {/* Data region — the ONLY scrollable part */}
      <div className="min-h-0 flex-1 overflow-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Identifier</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-20 text-right">Roles</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={4} className="py-8 text-center text-muted-foreground">Loading…</TableCell></TableRow>
            )}
            {error && (
              <TableRow><TableCell colSpan={4} className="py-8 text-center text-destructive">Failed to load.</TableCell></TableRow>
            )}
            {!isLoading && !error && rows.length === 0 && (
              <TableRow><TableCell colSpan={4} className="py-8 text-center text-muted-foreground">No accounts.</TableCell></TableRow>
            )}
            {rows.map((a) => (
              <TableRow key={a.id}>
                <TableCell className="font-mono text-xs">{a.email || a.account_number || a.id.slice(0, 8)}</TableCell>
                <TableCell>{a.display_name || "—"}</TableCell>
                <TableCell>
                  <select
                    className={`${selectCls} ${STATUS_STYLE[a.status] ?? ""}`}
                    value={a.status}
                    disabled={setStatus.isPending}
                    onChange={(e) => setStatus.mutate({ id: a.id, status: e.target.value })}
                  >
                    {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="icon" title="Manage roles" onClick={() => setRolesFor(a)}>
                    <KeyRound className="size-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination — server-side */}
      <div className="flex items-center justify-end gap-2 text-sm">
        <span className="text-muted-foreground">Page {page + 1}</span>
        <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Prev</Button>
        <Button variant="outline" size="sm" disabled={rows.length < PAGE} onClick={() => setPage((p) => p + 1)}>Next</Button>
      </div>

      {rolesFor && <RolesDialog account={rolesFor} onClose={() => setRolesFor(null)} />}
    </div>
  );
}

function NewAccountDialog({ open, setOpen }: { open: boolean; setOpen: (b: boolean) => void }) {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [orgId, setOrgId] = useState("");
  const [error, setError] = useState("");

  const { data: orgs = [] } = useQuery<Org[]>({
    queryKey: ["orgs", "all"],
    queryFn: () => apiFetch<Org[]>(`/api/v1/modules/organization/?limit=200&offset=0`),
  });

  function reset() { setEmail(""); setPassword(""); setDisplayName(""); setOrgId(""); setError(""); }

  const create = useMutation({
    mutationFn: () =>
      apiFetch("/api/v1/admin/accounts", {
        method: "POST",
        body: JSON.stringify({
          email, password,
          display_name: displayName || null,
          organization_id: orgId || null,
        }),
      }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["accounts"] }); setOpen(false); reset(); },
    onError: (e: Error) => setError(e.message || "Create failed"),
  });

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) reset(); }}>
      <DialogTrigger asChild>
        <Button size="sm"><Plus className="size-4" /> New account</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>New account</DialogTitle></DialogHeader>
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="agent@org.com" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pwd">Temporary password</Label>
            <Input id="pwd" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="≥ 8 chars, upper/lower/digit" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="dn">Display name</Label>
            <Input id="dn" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Jane Agent" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="org">Organization</Label>
            <select id="org" className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={orgId} onChange={(e) => setOrgId(e.target.value)}>
              <option value="">— none —</option>
              {orgs.map((o) => <option key={o.id} value={o.id}>{o.display_name || o.legal_name}</option>)}
            </select>
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

function RolesDialog({ account, onClose }: { account: Account; onClose: () => void }) {
  const qc = useQueryClient();
  const [roleId, setRoleId] = useState("");
  const [orgId, setOrgId] = useState("");
  const [error, setError] = useState("");

  const { data: assignments = [] } = useQuery<Assignment[]>({
    queryKey: ["account-roles", account.id],
    queryFn: () => apiFetch<Assignment[]>(`/api/v1/rbac/accounts/${account.id}/roles`),
  });
  const { data: roles = [] } = useQuery<Role[]>({
    queryKey: ["roles"],
    queryFn: () => apiFetch<Role[]>(`/api/v1/rbac/roles`),
  });
  const { data: orgs = [] } = useQuery<Org[]>({
    queryKey: ["orgs", "all"],
    queryFn: () => apiFetch<Org[]>(`/api/v1/modules/organization/?limit=200&offset=0`),
  });

  const roleName = (id: string) => roles.find((r) => r.id === id)?.name ?? id.slice(0, 8);
  const orgName = (id?: string | null) => id ? (orgs.find((o) => o.id === id)?.display_name || orgs.find((o) => o.id === id)?.legal_name || "org") : "Global";

  const assign = useMutation({
    mutationFn: () =>
      apiFetch(`/api/v1/rbac/accounts/${account.id}/roles`, {
        method: "POST",
        body: JSON.stringify({ role_id: roleId, organization_id: orgId || null }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["account-roles", account.id] });
      setRoleId(""); setOrgId(""); setError("");
    },
    onError: (e: Error) => setError(e.message || "Assign failed"),
  });

  const revoke = useMutation({
    mutationFn: (assignmentId: string) =>
      apiFetch(`/api/v1/rbac/accounts/${account.id}/roles/${assignmentId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["account-roles", account.id] }),
  });

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Roles — {account.display_name || account.email || account.id.slice(0, 8)}</DialogTitle>
        </DialogHeader>

        <div className="space-y-2">
          {assignments.length === 0 && <p className="text-sm text-muted-foreground">No roles assigned.</p>}
          {assignments.map((a) => (
            <div key={a.id} className="flex items-center justify-between rounded-md border px-3 py-1.5 text-sm">
              <span>
                <span className="font-medium">{roleName(a.role_id)}</span>
                <span className="ml-2 text-xs text-muted-foreground">@ {orgName(a.organization_id)}</span>
              </span>
              <Button variant="ghost" size="sm" disabled={revoke.isPending} onClick={() => revoke.mutate(a.id)}>Revoke</Button>
            </div>
          ))}
        </div>

        <form className="flex items-end gap-2 border-t pt-3"
          onSubmit={(e) => { e.preventDefault(); if (roleId) assign.mutate(); }}>
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="role">Role</Label>
            <select id="role" className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={roleId} onChange={(e) => setRoleId(e.target.value)}>
              <option value="">— select —</option>
              {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </div>
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="scope">Scope</Label>
            <select id="scope" className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={orgId} onChange={(e) => setOrgId(e.target.value)}>
              <option value="">Global</option>
              {orgs.map((o) => <option key={o.id} value={o.id}>{o.display_name || o.legal_name}</option>)}
            </select>
          </div>
          <Button type="submit" disabled={!roleId || assign.isPending}>Assign</Button>
        </form>
        {error && <p className="text-sm text-destructive">{error}</p>}

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
