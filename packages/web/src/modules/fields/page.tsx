"use client";

import { useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { AlertTriangle, Loader2, Plus } from "lucide-react";
import { toast } from "@/lib/toast";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { DataGrid, RecordForm, RecordSurface } from "@/components/shared";
import { type DataGridColumn } from "@/components/ui/data-grid";
import { OrgCombobox } from "@/components/ui/org-combobox";
import { useFirstOrg } from "@/lib/use-organizations";
import { usePermissions } from "@/lib/use-permissions";
import { fieldSpecToFieldDef } from "@/lib/schema/to-field-def";
import { tr, type FieldSpecType, type Locale } from "@/lib/schema/types";
import {
  TARGETS, archiveDefinition, buildIndex, createDefinition, getDefinition, listDefinitions,
  purgeDefinition, unarchiveDefinition, updateDefinition, type Definition, type Target,
} from "./api";
import {
  buildDefinitionPayload, canRenderCreateSurface, filterDefinitions, flattenDefinition,
  isSortable, sortDefinitions, targetLabelKey, useFieldDefFields,
} from "./fields";

/**
 * Screen A — the Studio. Master-detail: org + entity picker + a DataGrid of
 * this organisation's OWN definitions on the left, create/edit on the right
 * (a `RecordForm` — the socle authoring its own extension mechanism). The
 * definitions list is capped at 50/target by the backend (`MAX_FIELDS_PER_TARGET`)
 * and the admin API has no `sort`/`q` params, so sort/search here are local —
 * see `sortDefinitions`/`filterDefinitions`'s docstrings.
 */
export default function FieldsStudioPage() {
  const t = useTranslations("fields");
  const locale = useLocale() as Locale;
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const sel = params.get("sel") ?? "";
  const isNew = params.get("new") === "1";

  const { can } = usePermissions();
  const canManage = can("fields.manage");

  const firstOrg = useFirstOrg();
  const [orgId, setOrgId] = useState("");
  const effectiveOrgId = orgId || firstOrg.id;
  const [target, setTarget] = useState<Target>(TARGETS[0]);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("key");

  const openCreate = () => router.replace(`${pathname}?new=1`, { scroll: false });
  const select = (id: string) => router.replace(`${pathname}?sel=${id}`, { scroll: false });
  const closeSurface = () => router.replace(pathname, { scroll: false });

  const list = useQuery({
    queryKey: ["field-definitions", effectiveOrgId, target, includeArchived],
    queryFn: () => listDefinitions(effectiveOrgId, target, includeArchived),
    enabled: Boolean(effectiveOrgId),
  });
  const rows = filterDefinitions(sortDefinitions(list.data?.items ?? [], sort), q, locale);

  const columns: DataGridColumn<Definition>[] = [
    { key: "key", header: t("col.key"), sortable: true, className: "font-mono text-xs" },
    { key: "type", header: t("col.type"), sortable: true, cell: (r) => t(`type.${r.type}`) },
    { key: "widget", header: t("col.widget"), className: "text-muted-foreground font-mono text-xs" },
    { key: "label", header: t("col.label"), cell: (r) => tr(r.label, locale) },
    { key: "group", header: t("col.group"), sortable: true, className: "text-muted-foreground" },
    { key: "required", header: t("col.required"), sortable: true, cell: (r) => (r.required ? t("yes") : t("no")) },
    {
      key: "indexed", header: t("col.indexed"), sortable: true,
      cell: (r) => (
        <div className="flex items-center gap-1.5">
          <Badge variant={r.index_state === "ready" ? "success" : r.index_state === "failed" ? "destructive" : r.index_state === "pending" ? "warning" : "outline"}>
            {t(`index_state.${r.index_state}`)}
          </Badge>
          {r.indexed && !isSortable(r) && (
            // Decorative (the badge text already states the non-ready state) —
            // `title` gives a mouse-hover explanation without a redundant/
            // conflicting screen-reader announcement.
            <span title={t("not_sortable")}>
              <AlertTriangle className="size-3.5 shrink-0 text-amber-500" aria-hidden="true" />
            </span>
          )}
        </div>
      ),
    },
    {
      key: "status", header: t("col.status"),
      cell: (r) => (r.archived ? <Badge variant="outline">{t("archived_badge")}</Badge> : null),
    },
  ];

  const surfaceOpen = (isNew && canManage && !!effectiveOrgId) || !!sel;

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-64">
            <OrgCombobox value={effectiveOrgId} allowNone={false} placeholder={t("org_placeholder")}
              onChange={setOrgId} />
          </div>
          {canManage && (
            <Button size="sm" disabled={!effectiveOrgId} onClick={openCreate}>
              <Plus className="size-4" /> {t("new")}
            </Button>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1 border-b">
        {TARGETS.map((tk) => (
          <button key={tk} type="button" onClick={() => setTarget(tk)}
            className={cn("border-b-2 px-3 py-1.5 text-sm font-medium",
              target === tk ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground")}>
            {t(`target.${targetLabelKey(tk)}`)}
          </button>
        ))}
      </div>

      {!(surfaceOpen && isNew) && (
        <div className="flex items-center gap-2">
          <Input className="h-9 w-64" placeholder={t("search_placeholder")} value={q}
            onChange={(e) => setQ(e.target.value)} />
          <label className="ml-auto flex items-center gap-1.5 text-sm text-muted-foreground">
            <input type="checkbox" className="size-4 accent-[hsl(var(--primary))]"
              checked={includeArchived} onChange={(e) => setIncludeArchived(e.target.checked)} />
            {t("include_archived")}
          </label>
        </div>
      )}

      <div className="flex min-h-0 flex-1 gap-4">
        {!(surfaceOpen && isNew) && (
          <div className="min-w-0 flex-1">
            <DataGrid<Definition>
              mode="offset"
              columns={columns}
              rows={rows}
              rowKey={(r) => r.id}
              pageSize={Math.max(rows.length, 1)}
              total={rows.length}
              page={0}
              sort={sort}
              onSortChange={setSort}
              filters={{}}
              onFilterChange={() => undefined}
              isLoading={Boolean(effectiveOrgId) && list.isLoading}
              error={list.isError}
              onRowClick={(r) => select(r.id)}
              selectedId={sel}
              emptyLabel={effectiveOrgId ? t("empty") : firstOrg.isError ? t("org_load_error") : t("empty_no_org")}
            />
          </div>
        )}
        {surfaceOpen && (
          isNew
            ? (canRenderCreateSurface(isNew, canManage) && <CreateSurface orgId={effectiveOrgId} target={target} onClose={closeSurface}
                onCreated={() => list.refetch()} />)
            : <EditSurface key={sel} definitionId={sel} target={target} readOnly={!canManage}
                onClose={closeSurface} onChanged={() => list.refetch()} />
        )}
      </div>
    </div>
  );
}

/** Read-only `RecordForm` rendering the ACTUAL control the definition
 *  describes — not a mock-up. Reflects the last SAVED version of the
 *  definition (create: after the first Save; edit: the currently loaded
 *  row, refreshed whenever the row is refetched) — RecordForm keeps its
 *  in-progress values internal and does not expose them to a parent, so a
 *  true per-keystroke live preview is not achievable without extending that
 *  shared, heavily-used component (see the task report). */
function Preview({ row }: { row: Definition | null }) {
  const t = useTranslations("fields.preview");
  const locale = useLocale() as Locale;
  return (
    <div className="space-y-2 rounded-lg border p-3">
      <div>
        <h3 className="text-sm font-semibold">{t("title")}</h3>
        <p className="text-xs text-muted-foreground">{t("subtitle")}</p>
      </div>
      {row ? (
        <RecordForm
          key={row.etag}
          fields={[fieldSpecToFieldDef(row, locale)]}
          mode="create"
          readOnly
          initial={{}}
          onSubmit={async () => undefined}
        />
      ) : (
        <p className="text-sm text-muted-foreground">{t("empty")}</p>
      )}
    </div>
  );
}

function CreateSurface({ orgId, target, onClose, onCreated }: {
  orgId: string; target: Target; onClose: () => void; onCreated: () => void;
}) {
  const t = useTranslations("fields");
  const qc = useQueryClient();
  // Fix wave 1 (Task 15, Important #4): narrow the `widget` choices to the
  // LIVE `type` selection, not just the full cross-type union. `RecordForm`
  // exposes its in-progress scalar values via the additive `onValuesChange`
  // callback (see its docstring) — `liveType` mirrors the `type` field as the
  // user picks it, seeding `useFieldDefFields` exactly like `EditSurface`
  // already does with the row's SAVED `type`.
  const [liveType, setLiveType] = useState<FieldSpecType | undefined>(undefined);
  const fields = useFieldDefFields(liveType);
  const [savedRow, setSavedRow] = useState<Definition | null>(null);

  return (
    <RecordSurface title={t("new_title")} resourceKey="field-definitions" mode="page" onClose={onClose}>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <RecordForm
          fields={fields}
          mode="create"
          layout="rich"
          enableSaveNew
          submitLabel={t("new")}
          initial={{ col_span: "1" }}
          onValuesChange={(v) => setLiveType((v.type || undefined) as FieldSpecType | undefined)}
          onSubmit={async (payload) => {
            const body = buildDefinitionPayload(payload, target);
            const created = await createDefinition(orgId, body);
            setSavedRow(created);
            return created;
          }}
          onSuccess={({ again }) => {
            qc.invalidateQueries({ queryKey: ["field-definitions"] });
            onCreated();
            toast({ variant: "success", title: t("toast.created") });
            // "Save & New" resets RecordForm's own fields (including `type`)
            // back to blank — mirror that here so the widget list resets to
            // the full union for the next entry too.
            if (again) setLiveType(undefined);
            else onClose();
          }}
          onCancel={onClose}
        />
        <Preview row={savedRow} />
      </div>
    </RecordSurface>
  );
}

function EditSurface({ definitionId, target, readOnly, onClose, onChanged }: {
  definitionId: string; target: Target; readOnly: boolean; onClose: () => void; onChanged: () => void;
}) {
  const t = useTranslations("fields");
  const qc = useQueryClient();
  const [pendingPurge, setPendingPurge] = useState(false);
  const { data, isError } = useQuery({
    queryKey: ["field-definition", definitionId],
    queryFn: () => getDefinition(definitionId),
  });
  const fields = useFieldDefFields(data?.type);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["field-definition", definitionId] });
    qc.invalidateQueries({ queryKey: ["field-definitions"] });
    onChanged();
  };
  const onActionError = (e: unknown) => {
    toast({ variant: "error", title: t("toast.action_failed"), description: e instanceof ApiError ? e.message : undefined });
    // 409 (stale `If-Match`, someone else changed it) — reload the row rather
    // than leaving the surface showing data the next retry would reject again.
    if (e instanceof ApiError && e.status === 409) {
      qc.invalidateQueries({ queryKey: ["field-definition", definitionId] });
    }
  };

  const archive = useMutation({
    mutationFn: () => (data!.archived ? unarchiveDefinition(definitionId, data!.etag) : archiveDefinition(definitionId, data!.etag)),
    onSuccess: () => { invalidate(); toast({ variant: "success", title: t(data!.archived ? "toast.unarchived" : "toast.archived") }); },
    onError: onActionError,
  });
  const index = useMutation({
    mutationFn: () => buildIndex(definitionId, data!.etag),
    onSuccess: () => { invalidate(); toast({ variant: "success", title: t("toast.index_requested") }); },
    onError: onActionError,
  });
  const purge = useMutation({
    mutationFn: () => purgeDefinition(definitionId, data!.etag),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["field-definitions"] });
      onChanged();
      toast({ variant: "success", title: t("toast.purged") });
      onClose();
    },
    onError: onActionError,
  });

  return (
    <RecordSurface title={data ? data.key : t("edit_title")} subtitle={data ? t(`target.${targetLabelKey(data.target)}`) : undefined}
      resourceKey="field-definitions" onClose={onClose}>
      {isError && <p className="text-sm text-destructive">{t("load_error")}</p>}
      {!data && !isError && <p className="text-sm text-muted-foreground">{t("loading")}</p>}
      {data && (
        <div className="space-y-4">
          {/* Index state — explicit, never a silent "it'll just be slow". */}
          <div className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
            <Badge variant={data.index_state === "ready" ? "success" : data.index_state === "failed" ? "destructive" : data.index_state === "pending" ? "warning" : "outline"}>
              {t(`index_state.${data.index_state}`)}
            </Badge>
            {data.indexed && !isSortable(data) && (
              <span className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-500">
                <AlertTriangle className="size-3.5" aria-hidden="true" /> {t("not_sortable")}
              </span>
            )}
            {!readOnly && (
              <div className="ml-auto flex items-center gap-2">
                {/* Mirrors the backend's OWN guard exactly (`build_index`): indexed,
                    not archived, no build already in flight. Deliberately NOT
                    restricted to a non-"ready" state — the backend allows an
                    explicit rebuild of an already-ready index (e.g. after a
                    manual data fix), and hiding that here would be an
                    orphaned capability. */}
                {data.indexed && !data.archived && data.index_state !== "pending" && (
                  <Button variant="outline" size="sm" disabled={index.isPending} onClick={() => index.mutate()}>
                    {index.isPending ? <Loader2 className="size-3.5 animate-spin" /> : null} {t("action.index")}
                  </Button>
                )}
                <Button variant="outline" size="sm" disabled={archive.isPending} onClick={() => archive.mutate()}>
                  {t(data.archived ? "action.unarchive" : "action.archive")}
                </Button>
                {/* The only destructive action — behind a confirmation. */}
                <Button variant="outline" size="sm" className="text-destructive" onClick={() => setPendingPurge(true)}>
                  {t("action.purge")}
                </Button>
              </div>
            )}
          </div>

          <RecordForm
            key={data.etag}
            fields={fields}
            mode="edit"
            layout="rich"
            readOnly={readOnly}
            initial={flattenDefinition(data)}
            etag={data.etag}
            onSubmit={(payload, etag) => updateDefinition(definitionId, buildDefinitionPayload(payload, target), etag)}
            onSuccess={() => { invalidate(); toast({ variant: "success", title: t("toast.saved") }); }}
            onConflict={() => qc.invalidateQueries({ queryKey: ["field-definition", definitionId] })}
          />

          <Preview row={data} />
        </div>
      )}

      <ConfirmDialog
        open={pendingPurge}
        onOpenChange={setPendingPurge}
        danger
        requireText={data?.key}
        title={t("purge_confirm.title")}
        body={t("purge_confirm.body", { key: data?.key ?? "" })}
        confirmLabel={t("purge_confirm.confirm")}
        busy={purge.isPending}
        onConfirm={() => { purge.mutate(); setPendingPurge(false); }}
        onCancel={() => setPendingPurge(false)}
      />
    </RecordSurface>
  );
}
