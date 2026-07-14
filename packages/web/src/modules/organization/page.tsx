"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Plus, Trash2, Search } from "lucide-react";
import { toast } from "@/lib/toast";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { DataGrid, ExportMenu, RecordForm, RecordSurface } from "@/components/shared";
import { type DataGridColumn } from "@/components/ui/data-grid";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useServerTable, type ServerPage } from "@/lib/use-server-table";
import { usePermissions } from "@/lib/use-permissions";
import { useState } from "react";
import { useOrgFields } from "./fields";
import { DocumentIdentityForm } from "./document-identity-form";
import { OrganizationSettingsForm } from "./settings-form";
import {
  ORG_BASE, createOrg, deleteOrg, getOrg, listOrgs, updateOrg, type Org,
} from "./api";

const DEFAULT_PAGE = 20;

export default function OrganizationsPage() {
  const t = useTranslations("organizations");
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const sel = searchParams.get("sel") ?? "";
  const isNew = searchParams.get("new") === "1";
  const [pendingDelete, setPendingDelete] = useState<Org | null>(null);
  // Permission-driven actions (backend still enforces + scope-checks).
  const { can } = usePermissions();
  const canCreate = can("organization.create");
  const canUpdate = can("organization.update");
  const canDelete = can("organization.delete");

  // `?new` (create) and `?sel` (edit) are mutually exclusive: opening one clears
  // the other so a single RecordSurface is docked at a time.
  const openCreate = () => router.replace(`${pathname}?new=1`, { scroll: false });
  const select = (id: string) => router.replace(`${pathname}?sel=${id}`, { scroll: false });
  const closeSurface = () => router.replace(pathname, { scroll: false });

  const table = useServerTable<Org>({
    resource: "orgs",
    defaultSort: "code",
    defaultPageSize: DEFAULT_PAGE,
    fetchPage: ({ cursor, limit, sort, q }) => listOrgs({ q, sort, limit, cursor }),
  });

  // Optimistic delete + rollback (E5): drop the row from every cached page
  // immediately, restore the snapshots on error, and reconcile on settle.
  const del = useMutation({
    mutationFn: (id: string) => deleteOrg(id),
    onMutate: async (id: string) => {
      await qc.cancelQueries({ queryKey: ["orgs"] });
      const prev = qc.getQueriesData<ServerPage<Org>>({ queryKey: ["orgs"] });
      qc.setQueriesData<ServerPage<Org>>({ queryKey: ["orgs"] }, (old) =>
        old
          ? { ...old, items: old.items.filter((r) => r.id !== id), count: Math.max(0, old.count - 1) }
          : old);
      return { prev };
    },
    onError: (e, _id, ctx) => {
      ctx?.prev?.forEach(([key, data]) => qc.setQueryData(key, data));
      // Surface the (sanitized) backend reason — e.g. 409 "has dependent sites"
      // or 403 — instead of a dead-end generic message the operator can't act on.
      toast({ variant: "error", title: t("toast.delete_failed"),
        description: e instanceof ApiError ? e.message : undefined });
    },
    onSuccess: () => toast({ variant: "success", title: t("toast.deleted") }),
    onSettled: () => qc.invalidateQueries({ queryKey: ["orgs"] }),
  });

  const columns: DataGridColumn<Org>[] = [
    { key: "code", header: t("col.code"), sortable: true, className: "font-mono text-xs" },
    {
      key: "legal_name", header: t("col.name"), sortable: true,
      cell: (o) => o.display_name || o.legal_name,
    },
    // Row delete only when the user may delete (backend still enforces).
    ...(canDelete ? [{
      key: "actions", header: t("col.actions"), align: "right" as const, headClassName: "w-16", stopClick: true,
      cell: (o: Org) => (
        <Button variant="ghost" size="icon" title={t("delete.confirm")}
          onClick={() => setPendingDelete(o)} disabled={del.isPending}>
          <Trash2 className="size-4" />
        </Button>
      ),
    }] : []),
  ];

  const surfaceOpen = isNew || !!sel;

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Toolbar — fixed (does not scroll with the data) */}
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
          <ExportMenu filename="organizations"
            path={`${ORG_BASE}/export?q=${encodeURIComponent(table.q)}&sort=${table.sort}`} />
          {canCreate && (
            <Button size="sm" onClick={openCreate}><Plus className="size-4" /> {t("new")}</Button>
          )}
        </div>
      </div>

      {/* Master-detail: list + docked RecordSurface (edit) or full-width create page
          (P1.3). A field-rich create takes the whole area (list hidden); edit keeps
          the split-view for list context. */}
      <div className="flex min-h-0 flex-1 gap-4">
        {!(surfaceOpen && isNew) && (
        <div className="min-w-0 flex-1">
          <DataGrid<Org>
            mode="cursor"
            columns={columns}
            rows={table.rows}
            rowKey={(o) => o.id}
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
            onRowClick={(o) => select(o.id)}
            selectedId={sel}
            emptyLabel={t("empty")}
          />
        </div>
        )}
        {surfaceOpen && (
          isNew
            ? (canCreate && <OrgCreateSurface onClose={closeSurface} onCreated={() => { table.refetch(); }} />)
            : <OrgEditSurface key={sel} orgId={sel} onClose={closeSurface} readOnly={!canUpdate} />
        )}
      </div>

      <ConfirmDialog
        open={!!pendingDelete}
        onOpenChange={(o) => { if (!o) setPendingDelete(null); }}
        danger
        requireText={pendingDelete?.code}
        title={t("delete.title")}
        body={t("delete.body", { name: pendingDelete?.display_name || pendingDelete?.legal_name || "" })}
        confirmLabel={t("delete.confirm")}
        busy={del.isPending}
        onConfirm={() => {
          if (pendingDelete) del.mutate(pendingDelete.id);
          setPendingDelete(null);
        }}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}

function OrgCreateSurface({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const t = useTranslations("organizations");
  const qc = useQueryClient();
  const fields = useOrgFields();
  return (
    <RecordSurface title={t("new_title")} resourceKey="orgs" mode="page" onClose={onClose}>
      <RecordForm
        fields={fields}
        mode="create"
        layout="rich"
        enableSaveNew
        submitLabel={t("new")}
        onSubmit={(payload) => createOrg(payload)}
        onSuccess={({ again }) => {
          qc.invalidateQueries({ queryKey: ["orgs"] });
          onCreated();
          toast({ variant: "success", title: t("toast.created") });
          if (!again) onClose();
        }}
        onCancel={onClose}
      />
    </RecordSurface>
  );
}

type OrgTab = "details" | "documentIdentity" | "settings";

function OrgEditSurface({ orgId, onClose, readOnly }: { orgId: string; onClose: () => void; readOnly: boolean }) {
  const t = useTranslations("organizations");
  const qc = useQueryClient();
  const fields = useOrgFields();
  const [tab, setTab] = useState<OrgTab>("details");
  const { data, isError } = useQuery<Record<string, unknown>>({
    queryKey: ["org", orgId],
    queryFn: () => getOrg(orgId),
  });

  const title = (data?.display_name as string) || (data?.legal_name as string) || t("edit_title");
  const etag = data?.etag ? String(data.etag) : undefined;

  return (
    <RecordSurface
      title={title}
      subtitle={data?.code ? `code ${data.code}` : undefined}
      resourceKey="orgs"
      onClose={onClose}
    >
      {isError && <p className="text-sm text-destructive">{t("load_error")}</p>}
      {!data && !isError && <p className="text-sm text-muted-foreground">{t("loading")}</p>}
      {data && (
        <div className="space-y-4">
          {/* document_identity and settings are each their own tab (master-detail
              rule, repo convention): rich, schema-generated config, not a raw-JSON
              field in the main form. */}
          <div className="flex gap-1 border-b">
            {(["details", "documentIdentity", "settings"] as OrgTab[]).map((tk) => (
              <button key={tk} type="button" onClick={() => setTab(tk)}
                className={cn("border-b-2 px-3 py-1.5 text-sm font-medium",
                  tab === tk ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground")}>
                {tk === "details" ? t("tab.details")
                  : tk === "documentIdentity" ? t("documentIdentity.tab")
                  : t("settings.tab")}
              </button>
            ))}
          </div>

          {tab === "details" ? (
            <RecordForm
              // Remount on a fresh load (post-save / post-conflict) to reseed initial + etag.
              key={String(etag ?? orgId)}
              fields={fields}
              mode="edit"
              layout="rich"
              readOnly={readOnly}
              initial={data}
              etag={etag}
              onSubmit={(payload, tag) => updateOrg(orgId, payload, tag)}
              onSuccess={() => {
                qc.invalidateQueries({ queryKey: ["org", orgId] });
                qc.invalidateQueries({ queryKey: ["orgs"] });
              }}
              onConflict={() => qc.invalidateQueries({ queryKey: ["org", orgId] })}
            />
          ) : tab === "documentIdentity" ? (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">{t("documentIdentity.description")}</p>
              <DocumentIdentityForm
                key={String(etag ?? orgId)}
                orgId={orgId}
                documentIdentity={(data.document_identity as Record<string, unknown>) ?? {}}
                etag={etag}
                onSaved={() => {
                  qc.invalidateQueries({ queryKey: ["org", orgId] });
                  qc.invalidateQueries({ queryKey: ["orgs"] });
                }}
              />
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">{t("settings.description")}</p>
              <OrganizationSettingsForm
                key={String(etag ?? orgId)}
                orgId={orgId}
                settings={(data.settings as Record<string, unknown>) ?? {}}
                etag={etag}
                onSaved={() => {
                  qc.invalidateQueries({ queryKey: ["org", orgId] });
                  qc.invalidateQueries({ queryKey: ["orgs"] });
                }}
              />
            </div>
          )}
        </div>
      )}
    </RecordSurface>
  );
}
