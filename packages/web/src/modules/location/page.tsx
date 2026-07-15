"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "@/lib/toast";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { DataGrid, ExportMenu, RecordForm, RecordSurface } from "@/components/shared";
import { type DataGridColumn } from "@/components/ui/data-grid";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { OrgCombobox } from "@/components/ui/org-combobox";
import { useFirstOrg } from "@/lib/use-organizations";
import { useServerTable, type ServerPage } from "@/lib/use-server-table";
import { usePermissions } from "@/lib/use-permissions";
import { flattenCustomInitial, splitCustomPayload } from "@/modules/fields/fields";
import { DocumentIdentityOverrideTab } from "@/modules/organization/document-identity-override-tab";
import { SITE_BASE_KEYS, useSiteFields, useSiteFieldsSchemaError } from "./fields";
import {
  SITE_BASE, createSite, deleteSite, getSite, getSiteIssuerIdentity, listSites, updateSite, type Site,
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
  // Lifted (not local to SiteEditSurface): the document-identity tab needs
  // the full content width for the edit-column + live-preview split, so the
  // list-hiding decision below has to know which tab is active.
  const [tab, setTab] = useState<SiteTab>("details");
  useEffect(() => { setTab("details"); }, [sel]);
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

      {/* Master-detail: list + docked RecordSurface (edit) or full-width create/
          document-identity page (P2.0 consistency + SP1 D1 — a rich site
          create OR the document-identity screen takes the whole area; the
          details tab keeps the split-view). */}
      <div className="flex min-h-0 flex-1 gap-4">
        {!(surfaceOpen && (isNew || tab === "documentIdentity")) && (
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
            : <SiteEditSurface key={sel} siteId={sel} orgId={orgId} tab={tab} onTabChange={setTab}
                onClose={closeSurface} readOnly={!canUpdate} />
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
  const fields = useSiteFields(orgId);
  const customFieldsError = useSiteFieldsSchemaError(orgId);
  return (
    <RecordSurface title={t("new_title")} resourceKey="sites" mode="page" onClose={onClose}>
      {customFieldsError && <p className="text-sm text-destructive">{t("load_error")}</p>}
      <RecordForm
        fields={fields}
        mode="create"
        layout="rich"
        enableSaveNew
        submitLabel={t("new")}
        initial={{ site_type: "branch" }}
        onSubmit={(payload) => {
          // Custom-field values are NOT flat top-level columns — they live
          // nested under `custom_fields` (SiteCreate.custom_fields: dict).
          // Pydantic silently drops an undeclared top-level key, so this
          // split is required, not cosmetic (see fields.ts:splitCustomPayload).
          const { base, customFields } = splitCustomPayload(payload, SITE_BASE_KEYS);
          const body = Object.keys(customFields).length ? { ...base, custom_fields: customFields } : base;
          return createSite(orgId, body);
        }}
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

type SiteTab = "details" | "documentIdentity";

function SiteEditSurface({ siteId, orgId, tab, onTabChange, onClose, readOnly }: {
  siteId: string; orgId: string; tab: SiteTab; onTabChange: (t: SiteTab) => void;
  onClose: () => void; readOnly: boolean;
}) {
  const t = useTranslations("sites");
  const qc = useQueryClient();
  const fields = useSiteFields(orgId);
  const customFieldsError = useSiteFieldsSchemaError(orgId);
  const { data, isError: rowError } = useQuery<Record<string, unknown>>({
    queryKey: ["site", siteId],
    queryFn: () => getSite(siteId),
  });
  // IMPORTANT-4 fix: surface a failed custom-fields schema load too, not just
  // a failed row load.
  const isError = rowError || customFieldsError;

  return (
    <RecordSurface
      title={(data?.name as string) || t("edit_title")}
      subtitle={data?.code ? `code ${data.code}` : undefined}
      resourceKey="sites"
      mode={tab === "documentIdentity" ? "page" : "panel"}
      onClose={onClose}
    >
      {isError && <p className="text-sm text-destructive">{t("load_error")}</p>}
      {!data && !isError && <p className="text-sm text-muted-foreground">{t("loading")}</p>}
      {data && (
        <div className="space-y-4">
          <div className="flex gap-1 border-b">
            {(["details", "documentIdentity"] as SiteTab[]).map((tk) => (
              <button key={tk} type="button" onClick={() => onTabChange(tk)}
                className={cn("border-b-2 px-3 py-1.5 text-sm font-medium",
                  tab === tk ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground")}>
                {tk === "details" ? t("tab.details") : t("documentIdentity.tab")}
              </button>
            ))}
          </div>

          {tab === "details" ? (
            <RecordForm
              // `fields.length` in the key (not just the row's etag) — Task 16
              // e2e caught a real bug here: `SiteEditSurface` can mount before
              // `orgId` (async `useFirstOrg()`, resolved by the PARENT page, not
              // this component) is known — `LocationsPage`'s `surfaceOpen` opens
              // this surface off `!!sel` alone, so a hard reload/deep-link lands
              // here with `orgId=""` on the first render. `useSiteFields("")`
              // then returns ONLY the base columns (its schema query is `enabled:
              // Boolean(organizationId)`); RecordForm's `values` state is seeded
              // ONCE, from whatever `fields` it was first mounted with (a lazy
              // `useState` initializer, not an effect) — so once `orgId` resolves
              // a moment later and a custom field's `FieldDef` appears, RecordForm
              // does NOT remount (same key) and never seeds that field's stored
              // value from `initial`, showing it permanently blank. Worse: saving
              // the form afterward would submit that blank and silently ERASE the
              // real value. Including `fields.length` forces a remount (fresh
              // `values` seed from `initial`, using the now-complete `fields`)
              // the moment the custom-fields schema finishes loading; once
              // `fields` is stable (the common case — orgId already resolved
              // before this surface ever mounted) the key never changes again, so
              // no extra remounts are introduced for the already-working path.
              key={`${String(data.etag ?? siteId)}-${fields.length}`}
              fields={fields}
              mode="edit"
              layout="rich"
              readOnly={readOnly}
              initial={flattenCustomInitial(data)}
              etag={data.etag ? String(data.etag) : undefined}
              onSubmit={(payload, etag) => {
                const { base, customFields } = splitCustomPayload(payload, SITE_BASE_KEYS);
                const body = Object.keys(customFields).length ? { ...base, custom_fields: customFields } : base;
                return updateSite(siteId, body, etag);
              }}
              onSuccess={() => {
                qc.invalidateQueries({ queryKey: ["site", siteId] });
                qc.invalidateQueries({ queryKey: ["sites"] });
              }}
              onConflict={() => qc.invalidateQueries({ queryKey: ["site", siteId] })}
            />
          ) : (
            <DocumentIdentityOverrideTab
              key={String(data.etag ?? siteId)}
              schemaTarget="site.document_identity"
              organizationId={orgId}
              blob={(data.document_identity as Record<string, unknown>) ?? {}}
              etag={data.etag ? String(data.etag) : undefined}
              canWrite={!readOnly}
              issuerIdentityQueryKey={["issuer-identity", "site", siteId]}
              fetchIssuerIdentity={() => getSiteIssuerIdentity(siteId)}
              onSubmit={(payload, etag) => updateSite(siteId, { document_identity: payload }, etag)}
              onSaved={() => {
                qc.invalidateQueries({ queryKey: ["site", siteId] });
                qc.invalidateQueries({ queryKey: ["sites"] });
              }}
            />
          )}
        </div>
      )}
    </RecordSurface>
  );
}
