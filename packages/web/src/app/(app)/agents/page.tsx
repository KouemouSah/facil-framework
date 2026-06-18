"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Check } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { DataGrid, type DataGridColumn } from "@/components/ui/data-grid";
import { DetailPanel } from "@/components/ui/detail-panel";
import { OrgCombobox } from "@/components/ui/org-combobox";
import { ScopePicker, type Scope, EMPTY_SCOPE } from "@/components/ui/scope-picker";
import { SavedViews } from "@/components/saved-views";
import { ExportMenu } from "@/components/export-menu";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose } from "@/components/ui/dialog";
import { useOrgLabels } from "@/lib/use-organizations";
import { useServerTable, type ServerPage } from "@/lib/use-server-table";
import { emailField, passwordField, optionalText } from "@/lib/form-schemas";

interface Account {
  id: string;
  email?: string | null;
  account_number?: string | null;
  display_name?: string | null;
  organization_id?: string | null;
  status: string;
  is_active: boolean;
}
interface Role { id: string; code: string; name: string }
interface Assignment {
  id: string; role_id: string;
  organization_id?: string | null;
  org_unit_id?: string | null;
  site_id?: string | null;
}

// Build the AssignIn/BulkAssignIn scope payload from a ScopePicker value
// (empty string → null = wider scope per the backend NULL-widening rule).
function scopePayload(s: Scope) {
  return {
    organization_id: s.organization_id || null,
    org_unit_id: s.org_unit_id || null,
    site_id: s.site_id || null,
  };
}

const DEFAULT_PAGE = 20;
const STATUSES = ["pending_identity", "active", "suspended", "deactivated"];
const STATUS_STYLE: Record<string, string> = {
  active: "bg-emerald-500/10 text-emerald-600",
  pending_identity: "bg-amber-500/10 text-amber-600",
  suspended: "bg-orange-500/10 text-orange-600",
  deactivated: "bg-destructive/10 text-destructive",
};

export default function AgentsPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const sel = searchParams.get("sel") ?? "";
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkRole, setBulkRole] = useState(false);

  const selectRow = (id: string) => router.replace(`${pathname}?sel=${id}`, { scroll: false });
  const clearSel = () => router.replace(pathname, { scroll: false });

  // Server-side table: keyset cursor pagination + sort/filter/search/page-size,
  // all owned by the hook (scales to 1M+; no offset deep-scan, no full count).
  const table = useServerTable<Account>({
    resource: "accounts",
    defaultSort: "-created_at",
    defaultPageSize: DEFAULT_PAGE,
    fetchPage: ({ cursor, limit, sort, filters, q }) =>
      apiFetch<ServerPage<Account>>(
        `/api/v1/admin/accounts?q=${encodeURIComponent(q)}` +
        `&status=${filters.status ?? ""}&sort=${sort}&limit=${limit}` +
        (cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""),
      ),
  });
  const rows = table.rows;
  const selAccount = rows.find((a) => a.id === sel) ?? null;

  function clearSelection() { setSelected(new Set()); }
  function toggleRow(id: string) {
    setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }
  const allOnPage = rows.length > 0 && rows.every((r) => selected.has(r.id));
  function toggleAll() {
    setSelected((s) => {
      const n = new Set(s);
      if (allOnPage) rows.forEach((r) => n.delete(r.id));
      else rows.forEach((r) => n.add(r.id));
      return n;
    });
  }

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      apiFetch(`/api/v1/admin/accounts/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });

  const bulkStatus = useMutation({
    mutationFn: (status: string) =>
      apiFetch(`/api/v1/admin/accounts/bulk-status`, {
        method: "POST",
        body: JSON.stringify({ account_ids: [...selected], status }),
      }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["accounts"] }); clearSelection(); },
  });

  const columns: DataGridColumn<Account>[] = [
    {
      key: "email", header: "Identifier", sortable: true, className: "font-mono text-xs",
      cell: (a) => a.email || a.account_number || a.id.slice(0, 8),
    },
    {
      key: "display_name", header: "Name", sortable: true,
      cell: (a) => a.display_name || "—",
    },
    {
      key: "status", header: "Status", sortable: true, stopClick: true,
      filter: { type: "select", options: STATUSES.map((s) => ({ value: s, label: s })) },
      cell: (a) => (
        <Select
          className={`h-8 w-auto px-2 text-xs ${STATUS_STYLE[a.status] ?? ""}`}
          value={a.status}
          disabled={setStatus.isPending}
          onChange={(e) => setStatus.mutate({ id: a.id, status: e.target.value })}
        >
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </Select>
      ),
    },
  ];

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
              value={table.q} onChange={(e) => table.setQ(e.target.value)} />
          </div>
          <SavedViews
            resource="accounts"
            config={table.savedViewConfig}
            onApply={table.applySavedView}
          />
          <ExportMenu filename="accounts"
            path={`/api/v1/admin/accounts/export?q=${encodeURIComponent(table.q)}` +
              `&status=${table.filters.status ?? ""}&sort=${table.sort}`} />
          <NewAccountDialog open={open} setOpen={setOpen} />
        </div>
      </div>

      {/* Contextual bulk action bar — appears only when rows are selected */}
      {selected.size > 0 && (
        <div className="flex items-center gap-2 rounded-lg border bg-accent/40 px-3 py-2 text-sm">
          <span className="font-medium">{selected.size} selected</span>
          <div className="ml-auto flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={() => setBulkRole(true)}>Assign role</Button>
            <Button size="sm" variant="outline" disabled={bulkStatus.isPending}
              onClick={() => bulkStatus.mutate("active")}>Activate</Button>
            <Button size="sm" variant="outline" disabled={bulkStatus.isPending}
              onClick={() => bulkStatus.mutate("suspended")}>Suspend</Button>
            <Button size="sm" variant="ghost" onClick={clearSelection}>Clear</Button>
          </div>
        </div>
      )}

      {/* Master-detail: grid left (selection wired to bulk), account detail right */}
      <div className={`grid min-h-0 flex-1 gap-4 ${selAccount ? "lg:grid-cols-[1fr_minmax(360px,460px)]" : ""}`}>
        <DataGrid<Account>
          mode="cursor"
          columns={columns}
          rows={rows}
          rowKey={(a) => a.id}
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
          isLoading={table.isLoading}
          error={table.error}
          emptyLabel="No accounts."
          selection={{ selected, onToggle: toggleRow, onToggleAll: toggleAll, allOnPage }}
          onRowClick={(a) => selectRow(a.id)}
          selectedId={sel}
        />
        {selAccount && <AccountDetail account={selAccount} onClose={clearSel} />}
      </div>

      {bulkRole && (
        <BulkRoleDialog
          accountIds={[...selected]}
          onClose={() => setBulkRole(false)}
          onDone={() => { setBulkRole(false); clearSelection(); }}
        />
      )}
    </div>
  );
}

function BulkRoleDialog({ accountIds, onClose, onDone }: {
  accountIds: string[]; onClose: () => void; onDone: () => void;
}) {
  const [roleId, setRoleId] = useState("");
  const [scope, setScope] = useState<Scope>(EMPTY_SCOPE);
  const [error, setError] = useState("");

  const { data: roles = [] } = useQuery<Role[]>({
    queryKey: ["roles"],
    queryFn: () => apiFetch<{ items: Role[] }>(`/api/v1/rbac/roles?limit=200`).then((r) => r.items),
  });

  const assign = useMutation({
    mutationFn: () =>
      apiFetch(`/api/v1/rbac/accounts/bulk-roles`, {
        method: "POST",
        body: JSON.stringify({
          account_ids: accountIds, role_id: roleId, ...scopePayload(scope),
        }),
      }),
    onSuccess: () => onDone(),
    onError: (e: Error) => setError(e.message || "Assign failed"),
  });

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Assign role to {accountIds.length} account(s)</DialogTitle>
        </DialogHeader>
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (roleId) assign.mutate(); }}>
          <div className="space-y-1.5">
            <Label htmlFor="brole">Role</Label>
            <Select id="brole" value={roleId} onChange={(e) => setRoleId(e.target.value)}>
              <option value="">— select —</option>
              {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Scope</Label>
            <ScopePicker value={scope} onChange={setScope} />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <DialogClose asChild><Button type="button" variant="ghost" onClick={onClose}>Cancel</Button></DialogClose>
            <Button type="submit" disabled={!roleId || assign.isPending}>
              {assign.isPending ? "Assigning…" : "Assign"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

const accountForm = z.object({
  email: emailField,
  password: passwordField,
  display_name: optionalText(),
});
type AccountForm = z.infer<typeof accountForm>;

function NewAccountDialog({ open, setOpen }: { open: boolean; setOpen: (b: boolean) => void }) {
  const qc = useQueryClient();
  const [orgId, setOrgId] = useState(""); // OrgCombobox is controlled separately (optional, no validation)
  const [error, setError] = useState("");
  const { register, handleSubmit, reset, formState: { errors } } = useForm<AccountForm>({
    resolver: zodResolver(accountForm),
    defaultValues: { email: "", password: "", display_name: "" },
  });

  function resetAll() { reset(); setOrgId(""); setError(""); }

  const create = useMutation({
    mutationFn: (values: AccountForm) =>
      apiFetch("/api/v1/admin/accounts", {
        method: "POST",
        body: JSON.stringify({
          email: values.email, password: values.password,
          display_name: values.display_name || null,
          organization_id: orgId || null,
        }),
      }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["accounts"] }); setOpen(false); resetAll(); },
    onError: (e: Error) => setError(e.message || "Create failed"),
  });

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) resetAll(); }}>
      <DialogTrigger asChild>
        <Button size="sm"><Plus className="size-4" /> New account</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>New account</DialogTitle></DialogHeader>
        <form className="space-y-3" onSubmit={handleSubmit((v) => create.mutate(v))}>
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" {...register("email")} placeholder="agent@org.com" />
            {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pwd">Temporary password</Label>
            <Input id="pwd" type="password" {...register("password")} placeholder="≥ 8 chars, upper/lower/digit" />
            {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="dn">Display name</Label>
            <Input id="dn" {...register("display_name")} placeholder="Jane Agent" />
            {errors.display_name && <p className="text-xs text-destructive">{errors.display_name.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="org">Organization</Label>
            <OrgCombobox value={orgId} onChange={setOrgId} />
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

function AccountDetail({ account, onClose }: { account: Account; onClose: () => void }) {
  const qc = useQueryClient();
  const [roleId, setRoleId] = useState("");
  const [scope, setScope] = useState<Scope>(EMPTY_SCOPE);
  const [error, setError] = useState("");

  const { data: assignments = [] } = useQuery<Assignment[]>({
    queryKey: ["account-roles", account.id],
    queryFn: () => apiFetch<Assignment[]>(`/api/v1/rbac/accounts/${account.id}/roles`),
  });
  const { data: roles = [] } = useQuery<Role[]>({
    queryKey: ["roles"],
    queryFn: () => apiFetch<{ items: Role[] }>(`/api/v1/rbac/roles?limit=200`).then((r) => r.items),
  });
  const orgLabels = useOrgLabels(assignments.map((a) => a.organization_id));

  const roleName = (id: string) => roles.find((r) => r.id === id)?.name ?? id.slice(0, 8);
  const orgName = (id?: string | null) => {
    if (!id) return "Global";
    return orgLabels[id] ?? id.slice(0, 8);
  };

  const assign = useMutation({
    mutationFn: () =>
      apiFetch(`/api/v1/rbac/accounts/${account.id}/roles`, {
        method: "POST",
        body: JSON.stringify({ role_id: roleId, ...scopePayload(scope) }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["account-roles", account.id] });
      setRoleId(""); setScope(EMPTY_SCOPE); setError("");
    },
    onError: (e: Error) => setError(e.message || "Assign failed"),
  });

  const revoke = useMutation({
    mutationFn: (assignmentId: string) =>
      apiFetch(`/api/v1/rbac/accounts/${account.id}/roles/${assignmentId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["account-roles", account.id] }),
  });

  // Full account (with etag) for the edit form + optimistic concurrency.
  const { data: detail } = useQuery<Record<string, unknown>>({
    queryKey: ["account", account.id],
    queryFn: () => apiFetch(`/api/v1/admin/accounts/${account.id}`),
  });
  const [edit, setEdit] = useState<{ email: string; display_name: string; organization_id: string } | null>(null);
  const [savedEdit, setSavedEdit] = useState(false);
  useEffect(() => {
    if (detail && !edit) setEdit({
      email: (detail.email as string) ?? "",
      display_name: (detail.display_name as string) ?? "",
      organization_id: (detail.organization_id as string) ?? "",
    });
  }, [detail, edit]);

  const saveAccount = useMutation({
    mutationFn: () =>
      apiFetch(`/api/v1/admin/accounts/${account.id}`, {
        method: "PUT",
        headers: detail?.etag ? { "If-Match": String(detail.etag) } : undefined,
        body: JSON.stringify({
          email: edit?.email || null,
          display_name: edit?.display_name || null,
          organization_id: edit?.organization_id || null,
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["account", account.id] });
      qc.invalidateQueries({ queryKey: ["accounts"] });
      setSavedEdit(true); setError("");
    },
    onError: (e: { status?: number; message?: string }) => {
      if (e.status === 409) { setError("Changed elsewhere — reloading."); setEdit(null); qc.invalidateQueries({ queryKey: ["account", account.id] }); }
      else setError(e.message || "Save failed");
    },
  });
  function setField(k: "email" | "display_name" | "organization_id", v: string) {
    setEdit((f) => (f ? { ...f, [k]: v } : f)); setSavedEdit(false);
  }

  return (
    <DetailPanel
      title={account.display_name || account.email || account.id.slice(0, 8)}
      subtitle={account.email || account.account_number || account.id}
      onClose={onClose}
      footer={
        <div className="flex items-center gap-2">
          {savedEdit && <span className="flex items-center gap-1 text-sm text-emerald-600"><Check className="size-4" /> Saved</span>}
          <Button type="button" size="sm" className="ml-auto"
            disabled={saveAccount.isPending || edit === null} onClick={() => saveAccount.mutate()}>
            {saveAccount.isPending ? "Saving…" : "Save details"}
          </Button>
        </div>
      }
    >
      {/* Account meta */}
      <dl className="mb-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-muted-foreground">Status</dt>
        <dd><span className={`rounded px-1.5 py-0.5 text-xs ${STATUS_STYLE[account.status] ?? ""}`}>{account.status}</span></dd>
        {account.account_number && (<><dt className="text-muted-foreground">NIU</dt><dd className="font-mono text-xs">{account.account_number}</dd></>)}
      </dl>

      {/* Editable fields */}
      {edit && (
        <div className="mb-4 grid grid-cols-1 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="acc-email">Email</Label>
            <Input id="acc-email" type="email" value={edit.email} onChange={(e) => setField("email", e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="acc-name">Display name</Label>
            <Input id="acc-name" value={edit.display_name} onChange={(e) => setField("display_name", e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="acc-org">Organization</Label>
            <OrgCombobox value={edit.organization_id} onChange={(id) => setField("organization_id", id)} />
          </div>
        </div>
      )}

      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Roles</p>
      <div className="space-y-2">
        {assignments.length === 0 && <p className="text-sm text-muted-foreground">No roles assigned.</p>}
        {assignments.map((a) => (
          <div key={a.id} className="flex items-center justify-between rounded-md border px-3 py-1.5 text-sm">
            <span>
              <span className="font-medium">{roleName(a.role_id)}</span>
              <span className="ml-2 text-xs text-muted-foreground">
                @ {orgName(a.organization_id)}
                {a.site_id ? " · site" : a.org_unit_id ? " · unit" : ""}
              </span>
            </span>
            <Button variant="ghost" size="sm" disabled={revoke.isPending} onClick={() => revoke.mutate(a.id)}>Revoke</Button>
          </div>
        ))}
      </div>

      <form className="mt-3 space-y-3 border-t pt-3"
        onSubmit={(e) => { e.preventDefault(); if (roleId) assign.mutate(); }}>
        <div className="space-y-1.5">
          <Label htmlFor="role">Role</Label>
          <Select id="role" value={roleId} onChange={(e) => setRoleId(e.target.value)}>
            <option value="">— select —</option>
            {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Scope</Label>
          <ScopePicker value={scope} onChange={setScope} />
        </div>
        <Button type="submit" className="w-full" disabled={!roleId || assign.isPending}>
          {assign.isPending ? "Assigning…" : "Assign role"}
        </Button>
      </form>
      {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
    </DetailPanel>
  );
}
