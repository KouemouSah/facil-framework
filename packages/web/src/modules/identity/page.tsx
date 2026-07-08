"use client";

import { useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Plus, Search } from "lucide-react";
import { toast } from "@/lib/toast";
import { ApiError } from "@/lib/api";
import {
  DataGrid, ExportMenu, RecordForm, RecordSurface, SavedViews, ScopePicker, OrgCombobox,
} from "@/components/shared";
import { type DataGridColumn } from "@/components/ui/data-grid";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogClose,
} from "@/components/ui/dialog";
import { type Scope, EMPTY_SCOPE } from "@/components/ui/scope-picker";
import { useOrgLabels } from "@/lib/use-organizations";
import { useServerTable, type ServerPage } from "@/lib/use-server-table";
import { usePermissions } from "@/lib/use-permissions";
import { useAccountCreateFields, useAccountEditFields } from "./fields";
import {
  ACCOUNT_STATUSES, BLOCKING_STATUSES, accountsExportPath,
  assignRole, bulkAccountStatus, bulkAssignRole, createAccount, getAccount,
  listAccountRoles, listAccounts, listRoles, revokeRole, setAccountStatus, updateAccount,
  type Account, type Assignment, type Role,
} from "./api";

const DEFAULT_PAGE = 20;
const STATUS_STYLE: Record<string, string> = {
  active: "bg-emerald-500/10 text-emerald-600",
  pending_identity: "bg-amber-500/10 text-amber-600",
  suspended: "bg-orange-500/10 text-orange-600",
  deactivated: "bg-destructive/10 text-destructive",
};

// ScopePicker value → AssignIn/BulkAssignIn payload (empty → null = wider scope,
// per the backend NULL-widening rule).
function scopePayload(s: Scope) {
  return {
    organization_id: s.organization_id || null,
    org_unit_id: s.org_unit_id || null,
    site_id: s.site_id || null,
  };
}

type PendingStatus = { scope: "one" | "bulk"; id?: string; name?: string; status: string };

export default function AgentsPage() {
  const t = useTranslations("agents");
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const sel = searchParams.get("sel") ?? "";
  const isNew = searchParams.get("new") === "1";
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkRole, setBulkRole] = useState(false);
  const [pendingStatus, setPendingStatus] = useState<PendingStatus | null>(null);
  const { can } = usePermissions();
  const canManageAccounts = can("account.manage");
  const canManageRbac = can("rbac.manage");

  const openCreate = () => router.replace(`${pathname}?new=1`, { scroll: false });
  const selectRow = (id: string) => router.replace(`${pathname}?sel=${id}`, { scroll: false });
  const closeSurface = () => router.replace(pathname, { scroll: false });

  const table = useServerTable<Account>({
    resource: "accounts",
    defaultSort: "-created_at",
    defaultPageSize: DEFAULT_PAGE,
    fetchPage: ({ cursor, limit, sort, filters, q }) =>
      listAccounts({ q, status: filters.status ?? "", sort, limit, cursor }),
  });
  const rows = table.rows;

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

  // Optimistic status patch on every cached page + rollback (E5). One row (single)
  // or every selected row (bulk).
  function patchStatus(match: (id: string) => boolean, status: string) {
    qc.setQueriesData<ServerPage<Account>>({ queryKey: ["accounts"] }, (old) =>
      old ? { ...old, items: old.items.map((r) => (match(r.id) ? { ...r, status } : r)) } : old);
  }

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => setAccountStatus(id, status),
    onMutate: async ({ id, status }) => {
      await qc.cancelQueries({ queryKey: ["accounts"] });
      const prev = qc.getQueriesData<ServerPage<Account>>({ queryKey: ["accounts"] });
      patchStatus((rid) => rid === id, status);
      return { prev };
    },
    onError: (e, _v, ctx) => {
      ctx?.prev?.forEach(([key, data]) => qc.setQueryData(key, data));
      toast({ variant: "error", title: t("toast.status_failed"),
        description: e instanceof ApiError ? e.message : undefined });
    },
    onSuccess: () => toast({ variant: "success", title: t("toast.status_changed") }),
    onSettled: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });

  const bulkStatus = useMutation({
    mutationFn: (status: string) => bulkAccountStatus([...selected], status),
    onMutate: async (status) => {
      await qc.cancelQueries({ queryKey: ["accounts"] });
      const prev = qc.getQueriesData<ServerPage<Account>>({ queryKey: ["accounts"] });
      const ids = new Set(selected);
      patchStatus((rid) => ids.has(rid), status);
      return { prev };
    },
    onError: (e, _v, ctx) => {
      ctx?.prev?.forEach(([key, data]) => qc.setQueryData(key, data));
      toast({ variant: "error", title: t("toast.bulk_failed"),
        description: e instanceof ApiError ? e.message : undefined });
    },
    onSuccess: (res, status) => {
      // Bulk-status is a PARTIAL-success endpoint: it applies what it can and
      // returns per-item errors (not found / forbidden). Don't paint a partial
      // result as a clean success — the optimistic patch already flipped every
      // row and onSettled will revert the failed ones.
      const failed = res.errors?.length ?? 0;
      if (failed > 0) {
        toast({ variant: "warning",
          title: t("toast.bulk_partial", { ok: res.updated?.length ?? 0, failed }) });
      } else {
        toast({ variant: "success", title: t("toast.bulk_done", { count: selected.size, status }) });
      }
      clearSelection();
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });

  // A blocking transition (suspend/deactivate revokes sessions) is gated by a
  // ConfirmDialog; a benign one applies immediately (optimistic).
  function requestStatus(id: string, name: string, status: string) {
    if (BLOCKING_STATUSES.has(status)) setPendingStatus({ scope: "one", id, name, status });
    else setStatus.mutate({ id, status });
  }
  function requestBulk(status: string) {
    if (BLOCKING_STATUSES.has(status)) setPendingStatus({ scope: "bulk", status });
    else bulkStatus.mutate(status);
  }

  const columns: DataGridColumn<Account>[] = [
    {
      key: "email", header: t("col.identifier"), sortable: true, className: "font-mono text-xs",
      cell: (a) => a.email || a.account_number || a.id.slice(0, 8),
    },
    { key: "display_name", header: t("col.name"), sortable: true, cell: (a) => a.display_name || "—" },
    {
      key: "status", header: t("col.status"), sortable: true, stopClick: true,
      filter: { type: "select", options: ACCOUNT_STATUSES.map((s) => ({ value: s, label: s })) },
      // Editable status only with account.manage; otherwise a read-only badge.
      cell: (a) => canManageAccounts ? (
        <Select
          className={`h-8 w-auto px-2 text-xs ${STATUS_STYLE[a.status] ?? ""}`}
          value={a.status}
          disabled={setStatus.isPending}
          onChange={(e) => {
            const next = e.target.value;
            if (next !== a.status) {
              requestStatus(a.id, a.display_name || a.email || a.id.slice(0, 8), next);
            }
          }}
        >
          {ACCOUNT_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </Select>
      ) : (
        <span className={`rounded px-1.5 py-0.5 text-xs ${STATUS_STYLE[a.status] ?? ""}`}>{a.status}</span>
      ),
    },
  ];

  const surfaceOpen = isNew || !!sel;

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Toolbar — fixed */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="h-9 w-56 pl-8" placeholder={t("search_placeholder")}
              value={table.q} onChange={(e) => table.setQ(e.target.value)} />
          </div>
          <SavedViews resource="accounts" config={table.savedViewConfig} onApply={table.applySavedView} />
          <ExportMenu filename="accounts"
            path={accountsExportPath(table.q, table.filters.status ?? "", table.sort)} />
          {canManageAccounts && (
            <Button size="sm" onClick={openCreate}><Plus className="size-4" /> {t("new")}</Button>
          )}
        </div>
      </div>

      {/* Contextual bulk action bar — appears only when rows are selected.
          Wraps < md so the actions stay reachable on narrow viewports. */}
      {selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-accent/40 px-3 py-2 text-sm">
          <span className="font-medium">{t("bulk.selected", { count: selected.size })}</span>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            {canManageRbac && (
              <Button size="sm" variant="outline" onClick={() => setBulkRole(true)}>{t("bulk.assign_role")}</Button>
            )}
            {canManageAccounts && (
              <>
                <Button size="sm" variant="outline" disabled={bulkStatus.isPending}
                  onClick={() => requestBulk("active")}>{t("bulk.activate")}</Button>
                <Button size="sm" variant="outline" disabled={bulkStatus.isPending}
                  onClick={() => requestBulk("suspended")}>{t("bulk.suspend")}</Button>
              </>
            )}
            <Button size="sm" variant="ghost" onClick={clearSelection}>{t("bulk.clear")}</Button>
          </div>
        </div>
      )}

      {/* Master-detail: grid left (selection wired to bulk), docked surface right. */}
      <div className="flex min-h-0 flex-1 gap-4">
        <div className="min-w-0 flex-1">
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
            emptyLabel={t("empty")}
            // Selection (→ bulk bar) only when the user can act on a selection.
            selection={(canManageAccounts || canManageRbac)
              ? { selected, onToggle: toggleRow, onToggleAll: toggleAll, allOnPage }
              : undefined}
            onRowClick={(a) => selectRow(a.id)}
            selectedId={sel}
          />
        </div>
        {surfaceOpen && (
          isNew
            ? (canManageAccounts && <AccountCreateSurface onClose={closeSurface} onCreated={() => table.refetch()} />)
            : <AccountDetailSurface key={sel} accountId={sel} onClose={closeSurface}
                canManageAccounts={canManageAccounts} canManageRbac={canManageRbac} />
        )}
      </div>

      {bulkRole && (
        <BulkRoleDialog
          accountIds={[...selected]}
          onClose={() => setBulkRole(false)}
          onDone={() => { setBulkRole(false); clearSelection(); }}
        />
      )}

      <ConfirmDialog
        open={!!pendingStatus}
        onOpenChange={(o) => { if (!o) setPendingStatus(null); }}
        danger
        title={t("status.confirm_title", { status: pendingStatus?.status ?? "" })}
        body={pendingStatus?.scope === "bulk"
          ? t("status.bulk_confirm_body", { count: selected.size, status: pendingStatus?.status ?? "" })
          : t("status.confirm_body", { name: pendingStatus?.name ?? "", status: pendingStatus?.status ?? "" })}
        confirmLabel={t("status.confirm_label")}
        busy={setStatus.isPending || bulkStatus.isPending}
        onConfirm={() => {
          if (!pendingStatus) return;
          if (pendingStatus.scope === "bulk") bulkStatus.mutate(pendingStatus.status);
          else if (pendingStatus.id) setStatus.mutate({ id: pendingStatus.id, status: pendingStatus.status });
          setPendingStatus(null);
        }}
        onCancel={() => setPendingStatus(null)}
      />
    </div>
  );
}

function AccountCreateSurface({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const t = useTranslations("agents");
  const qc = useQueryClient();
  const fields = useAccountCreateFields();
  return (
    <RecordSurface title={t("new_title")} resourceKey="accounts" onClose={onClose}>
      <RecordForm
        fields={fields}
        mode="create"
        layout="compact"
        enableSaveNew
        submitLabel={t("new")}
        onSubmit={(payload) => createAccount(payload)}
        onSuccess={({ again }) => {
          qc.invalidateQueries({ queryKey: ["accounts"] });
          onCreated();
          toast({ variant: "success", title: t("toast.created") });
          if (!again) onClose();
        }}
        onCancel={onClose}
      />
    </RecordSurface>
  );
}

function AccountDetailSurface({ accountId, onClose, canManageAccounts, canManageRbac }: {
  accountId: string; onClose: () => void; canManageAccounts: boolean; canManageRbac: boolean;
}) {
  const t = useTranslations("agents");
  const qc = useQueryClient();
  const fields = useAccountEditFields();
  const { data: detail, isError } = useQuery<Record<string, unknown>>({
    queryKey: ["account", accountId],
    queryFn: () => getAccount(accountId),
  });

  const title = (detail?.display_name as string) || (detail?.email as string) || t("edit_title");
  const status = (detail?.status as string) ?? "";

  return (
    <RecordSurface
      title={title}
      subtitle={(detail?.email as string) || (detail?.account_number as string) || accountId}
      resourceKey="accounts"
      onClose={onClose}
    >
      {isError && <p className="text-sm text-destructive">{t("load_error")}</p>}
      {!detail && !isError && <p className="text-sm text-muted-foreground">{t("loading")}</p>}
      {detail && (
        <div className="space-y-4">
          {/* Meta */}
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="text-muted-foreground">{t("meta.status")}</dt>
            <dd><span className={`rounded px-1.5 py-0.5 text-xs ${STATUS_STYLE[status] ?? ""}`}>{status}</span></dd>
            {!!detail.account_number && (
              <>
                <dt className="text-muted-foreground">{t("meta.niu")}</dt>
                <dd className="font-mono text-xs">{String(detail.account_number)}</dd>
              </>
            )}
          </dl>

          {/* Editable fields via the shared RecordForm (audit 12, DRY) */}
          <RecordForm
            key={String(detail.etag ?? accountId)}
            fields={fields}
            mode="edit"
            layout="compact"
            readOnly={!canManageAccounts}
            initial={detail}
            etag={detail.etag ? String(detail.etag) : undefined}
            submitLabel={t("save")}
            onSubmit={(payload, etag) => updateAccount(accountId, payload, etag)}
            onSuccess={() => {
              qc.invalidateQueries({ queryKey: ["account", accountId] });
              qc.invalidateQueries({ queryKey: ["accounts"] });
              toast({ variant: "success", title: t("toast.saved") });
            }}
            onConflict={() => qc.invalidateQueries({ queryKey: ["account", accountId] })}
          />

          <RolesSection accountId={accountId} canManage={canManageRbac} />
        </div>
      )}
    </RecordSurface>
  );
}

function RolesSection({ accountId, canManage }: { accountId: string; canManage: boolean }) {
  const t = useTranslations("agents");
  const qc = useQueryClient();
  const [roleId, setRoleId] = useState("");
  const [scope, setScope] = useState<Scope>(EMPTY_SCOPE);
  const [error, setError] = useState("");

  const { data: assignments = [], isError: assignmentsError } = useQuery<Assignment[]>({
    queryKey: ["account-roles", accountId],
    queryFn: () => listAccountRoles(accountId),
  });
  const { data: roles = [] } = useQuery<Role[]>({ queryKey: ["roles"], queryFn: listRoles });
  const orgLabels = useOrgLabels(assignments.map((a) => a.organization_id));

  const roleName = (id: string) => roles.find((r) => r.id === id)?.name ?? id.slice(0, 8);
  const orgName = (id?: string | null) => (id ? orgLabels[id] ?? id.slice(0, 8) : t("roles.global"));

  const assign = useMutation({
    mutationFn: () => assignRole(accountId, { role_id: roleId, ...scopePayload(scope) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["account-roles", accountId] });
      setRoleId(""); setScope(EMPTY_SCOPE); setError("");
      toast({ variant: "success", title: t("roles.assigned") });
    },
    onError: (e: unknown) => setError(e instanceof ApiError ? e.message : t("roles.assign_failed")),
  });

  const revoke = useMutation({
    mutationFn: (assignmentId: string) => revokeRole(accountId, assignmentId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["account-roles", accountId] }),
    onError: (e: unknown) => toast({ variant: "error", title: t("roles.revoke_failed"),
      description: e instanceof ApiError ? e.message : undefined }),
  });

  return (
    <div className="border-t pt-3">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t("roles.title")}</p>
      <div className="space-y-2">
        {assignmentsError && <p className="text-sm text-destructive">{t("roles.load_error")}</p>}
        {!assignmentsError && assignments.length === 0 && (
          <p className="text-sm text-muted-foreground">{t("roles.none")}</p>
        )}
        {assignments.map((a) => (
          <div key={a.id} className="flex items-center justify-between rounded-md border px-3 py-1.5 text-sm">
            <span>
              <span className="font-medium">{roleName(a.role_id)}</span>
              <span className="ml-2 text-xs text-muted-foreground">
                @ {orgName(a.organization_id)}
                {a.site_id ? " · site" : a.org_unit_id ? " · unit" : ""}
              </span>
            </span>
            {canManage && (
              <Button variant="ghost" size="sm" disabled={revoke.isPending} onClick={() => revoke.mutate(a.id)}>
                {t("roles.revoke")}
              </Button>
            )}
          </div>
        ))}
      </div>

      {canManage && (
      <form className="mt-3 space-y-3" onSubmit={(e) => { e.preventDefault(); if (roleId) assign.mutate(); }}>
        <div className="space-y-1.5">
          <Label htmlFor="role">{t("roles.role")}</Label>
          <Select id="role" value={roleId} onChange={(e) => setRoleId(e.target.value)}>
            <option value="">{t("roles.select")}</option>
            {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>{t("roles.scope")}</Label>
          <ScopePicker value={scope} onChange={setScope} />
        </div>
        <Button type="submit" className="w-full" disabled={!roleId || assign.isPending}>
          {assign.isPending ? t("roles.assigning") : t("roles.assign")}
        </Button>
      </form>
      )}
      {canManage && error && <p className="mt-2 text-sm text-destructive">{error}</p>}
    </div>
  );
}

function BulkRoleDialog({ accountIds, onClose, onDone }: {
  accountIds: string[]; onClose: () => void; onDone: () => void;
}) {
  const t = useTranslations("agents");
  const [roleId, setRoleId] = useState("");
  const [scope, setScope] = useState<Scope>(EMPTY_SCOPE);
  const [error, setError] = useState("");

  const { data: roles = [] } = useQuery<Role[]>({ queryKey: ["roles"], queryFn: listRoles });

  const assign = useMutation({
    mutationFn: () => bulkAssignRole({ account_ids: accountIds, role_id: roleId, ...scopePayload(scope) }),
    onSuccess: (res) => {
      // Partial-success endpoint: keep the dialog open on any per-item failure so
      // the operator sees which count failed instead of a false "all assigned".
      const failed = res.errors?.length ?? 0;
      if (failed > 0) {
        setError(t("roles.assign_partial", { ok: res.assigned?.length ?? 0, failed }));
      } else {
        toast({ variant: "success", title: t("roles.assigned") });
        onDone();
      }
    },
    onError: (e: unknown) => setError(e instanceof ApiError ? e.message : t("roles.assign_failed")),
  });

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("assign_dialog.title", { count: accountIds.length })}</DialogTitle>
        </DialogHeader>
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (roleId) assign.mutate(); }}>
          <div className="space-y-1.5">
            <Label htmlFor="brole">{t("roles.role")}</Label>
            <Select id="brole" value={roleId} onChange={(e) => setRoleId(e.target.value)}>
              <option value="">{t("roles.select")}</option>
              {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>{t("roles.scope")}</Label>
            <ScopePicker value={scope} onChange={setScope} />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <DialogClose asChild><Button type="button" variant="ghost" onClick={onClose}>{t("cancel")}</Button></DialogClose>
            <Button type="submit" disabled={!roleId || assign.isPending}>
              {assign.isPending ? t("roles.assigning") : t("roles.assign")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
