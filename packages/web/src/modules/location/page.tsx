"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "@/lib/toast";
import { ApiError } from "@/lib/api";
import { DataGrid, ExportMenu, RecordForm, RecordSurface } from "@/components/shared";
import { type DataGridColumn } from "@/components/ui/data-grid";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { OrgCombobox } from "@/components/ui/org-combobox";
import { useFirstOrg } from "@/lib/use-organizations";
import { useServerTable, type ServerPage } from "@/lib/use-server-table";
import { usePermissions } from "@/lib/use-permissions";
import { useSiteFields } from "./fields";
import {
  SITE_BASE, createSite, deleteSite, getSite, listSites, updateSite, type Site,
} from "./api";

const DEFAULT_PAGE = 20;

export default function LocationsPage() {
  const t = useTranslations("sites");
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const sel = searchParams.get("sel") ?? "";
  const isNew = searchParams.get("new") === "1";
  const [orgId, setOrgId] = useState("");
  const [pendingDelete, setPendingDelete] = useState<Site | null>(null);
  const { can } = usePermissions();
  const canCreate = can("location.create");
  const canUpdate = can("location.update");
  const canDelete = can("location.delete");

  const openCreate = () => router.replace(`${pathname}?new=1`, { scroll: false });
  const select = (id: string) => router.replace(`${pathname}?sel=${id}`, { scroll: false });
  const closeSurface = () => router.replace(pathname, { scroll: false });

  // Sites are org-scoped at the API, so a chosen org gates listing/creating.
  const firstOrg = useFirstOrg();
  useEffect(() => {
    if (!orgId && firstOrg.id) setOrgId(firstOrg.id);
  }, [firstOrg.id, orgId]);

  const table = useServerTable<Site>({
    resource: "sites",
    defaultSort: "code",
    defaultPageSize: DEFAULT_PAGE,
    enabled: !!orgId,
    fetchPage: ({ cursor, limit, sort, filters }) =>
      listSites({ orgId: filters.organization_id ?? "", sort, limit, cursor }),
  });
  const setTableFilter = table.onFilterChange;
  useEffect(() => { setTableFilter("organization_id", orgId); }, [orgId, setTableFilter]);

  // Optimistic delete + rollback (E5).
  const del = useMutation({
    mutationFn: (id: string) => deleteSite(id),
    onMutate: async (id: string) => {
      await qc.cancelQueries({ queryKey: ["sites"] });
      const prev = qc.getQueriesData<ServerPage<Site>>({ queryKey: ["sites"] });
      qc.setQueriesData<ServerPage<Site>>({ queryKey: ["sites"] }, (old) =>
        old
          ? { ...old, items: old.items.filter((r) => r.id !== id), count: Math.max(0, old.count - 1) }
          : old);
      return { prev };
    },
    onError: (e, _id, ctx) => {
      ctx?.prev?.forEach(([key, data]) => qc.setQueryData(key, data));
      // Surface the (sanitized) backend reason instead of a dead-end generic message.
      toast({ variant: "error", title: t("toast.delete_failed"),
        description: e instanceof ApiError ? e.message : undefined });
    },
    onSuccess: () => toast({ variant: "success", title: t("toast.deleted") }),
    onSettled: () => qc.invalidateQueries({ queryKey: ["sites"] }),
  });

  const columns: DataGridColumn<Site>[] = [
    { key: "code", header: t("col.code"), sortable: true, className: "font-mono text-xs" },
    {
      key: "name", header: t("col.name"), sortable: true,
      cell: (s) => (
        <>{s.name}{s.is_primary && <span className="ml-2 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">{t("primary")}</span>}</>
      ),
    },
    { key: "site_type", header: t("col.type"), sortable: true, className: "text-muted-foreground" },
    {
      key: "city", header: t("col.city"), sortable: true, className: "text-muted-foreground",
      cell: (s) => [s.city, s.country_code].filter(Boolean).join(", "),
    },
    ...(canDelete ? [{
      key: "actions", header: t("col.actions"), align: "right" as const, headClassName: "w-16", stopClick: true,
      cell: (s: Site) => (
        <Button variant="ghost" size="icon" title={t("delete.confirm")}
          onClick={() => setPendingDelete(s)} disabled={del.isPending}>
          <Trash2 className="size-4" />
        </Button>
      ),
    }] : []),
  ];

  const surfaceOpen = (isNew && !!orgId) || !!sel;

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Toolbar — fixed (does not scroll with the data) */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-64">
            <OrgCombobox value={orgId} allowNone={false}
              placeholder={t("org_placeholder")}
              onChange={(id) => setOrgId(id)} />
          </div>
          <ExportMenu filename="sites" disabled={!orgId}
            path={`${SITE_BASE}/export?organization_id=${orgId}&sort=${table.sort}`} />
          {canCreate && (
            <Button size="sm" disabled={!orgId} onClick={openCreate}>
              <Plus className="size-4" /> {t("new")}
            </Button>
          )}
        </div>
      </div>

      {/* Master-detail: list + docked RecordSurface (edit) or full-width create page
          (P2.0 consistency — a rich site create takes the whole area; edit keeps
          the split-view). */}
      <div className="flex min-h-0 flex-1 gap-4">
        {!(surfaceOpen && isNew) && (
        <div className="min-w-0 flex-1">
          <DataGrid<Site>
            mode="cursor"
            columns={columns}
            rows={table.rows}
            rowKey={(s) => s.id}
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
            isLoading={!!orgId && table.isLoading}
            error={table.error}
            onRowClick={(s) => select(s.id)}
            selectedId={sel}
            emptyLabel={orgId ? t("empty") : firstOrg.isError ? t("org_load_error") : t("empty_no_org")}
          />
        </div>
        )}
        {surfaceOpen && (
          isNew
            ? (canCreate && <SiteCreateSurface orgId={orgId} onClose={closeSurface} onCreated={() => { table.refetch(); }} />)
            : <SiteEditSurface key={sel} siteId={sel} onClose={closeSurface} readOnly={!canUpdate} />
        )}
      </div>

      <ConfirmDialog
        open={!!pendingDelete}
        onOpenChange={(o) => { if (!o) setPendingDelete(null); }}
        danger
        title={t("delete.title")}
        body={t("delete.body", { name: pendingDelete?.name || "" })}
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

function SiteCreateSurface({ orgId, onClose, onCreated }: {
  orgId: string; onClose: () => void; onCreated: () => void;
}) {
  const t = useTranslations("sites");
  const qc = useQueryClient();
  const fields = useSiteFields();
  return (
    <RecordSurface title={t("new_title")} resourceKey="sites" mode="page" onClose={onClose}>
      <RecordForm
        fields={fields}
        mode="create"
        layout="rich"
        enableSaveNew
        submitLabel={t("new")}
        initial={{ site_type: "branch" }}
        onSubmit={(payload) => createSite(orgId, payload)}
        onSuccess={({ again }) => {
          qc.invalidateQueries({ queryKey: ["sites"] });
          onCreated();
          toast({ variant: "success", title: t("toast.created") });
          if (!again) onClose();
        }}
        onCancel={onClose}
      />
    </RecordSurface>
  );
}

function SiteEditSurface({ siteId, onClose, readOnly }: { siteId: string; onClose: () => void; readOnly: boolean }) {
  const t = useTranslations("sites");
  const qc = useQueryClient();
  const fields = useSiteFields();
  const { data, isError } = useQuery<Record<string, unknown>>({
    queryKey: ["site", siteId],
    queryFn: () => getSite(siteId),
  });

  return (
    <RecordSurface
      title={(data?.name as string) || t("edit_title")}
      subtitle={data?.code ? `code ${data.code}` : undefined}
      resourceKey="sites"
      onClose={onClose}
    >
      {isError && <p className="text-sm text-destructive">{t("load_error")}</p>}
      {!data && !isError && <p className="text-sm text-muted-foreground">{t("loading")}</p>}
      {data && (
        <RecordForm
          key={String(data.etag ?? siteId)}
          fields={fields}
          mode="edit"
          layout="rich"
          readOnly={readOnly}
          initial={data}
          etag={data.etag ? String(data.etag) : undefined}
          onSubmit={(payload, etag) => updateSite(siteId, payload, etag)}
          onSuccess={() => {
            qc.invalidateQueries({ queryKey: ["site", siteId] });
            qc.invalidateQueries({ queryKey: ["sites"] });
          }}
          onConflict={() => qc.invalidateQueries({ queryKey: ["site", siteId] })}
        />
      )}
    </RecordSurface>
  );
}
