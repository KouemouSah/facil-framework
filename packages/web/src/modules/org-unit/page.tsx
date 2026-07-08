"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Plus, Trash2, CornerDownRight } from "lucide-react";
import { toast } from "@/lib/toast";
import { ApiError } from "@/lib/api";
import { codeField, requiredText } from "@/lib/form-schemas";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { OrgCombobox } from "@/components/ui/org-combobox";
import { ExportMenu, RecordForm, RecordSurface, type FieldDef } from "@/components/shared";
import { usePermissions } from "@/lib/use-permissions";
import { useFirstOrg } from "@/lib/use-organizations";
import { orderForTree, validParents } from "./tree";
import {
  createUnit, deleteUnit, getUnit, listUnits, unitsExportPath, updateUnit, type OrgUnit,
} from "./api";

function useUnitFields(parents: OrgUnit[]): FieldDef[] {
  const t = useTranslations("org_units");
  return [
    { name: "code", label: t("f.code"), required: true, immutable: true, zod: codeField, hint: t("f.code_hint") },
    { name: "name", label: t("f.name"), required: true, zod: requiredText("Name") },
    { name: "unit_type", label: t("f.unit_type"), placeholder: "department" },
    { name: "parent_id", label: t("f.parent"), type: "select",
      selectOptions: parents.map((p) => ({ value: p.id, label: p.name })) },
    { name: "description", label: t("f.description"), type: "textarea", colSpan: 2 },
    { name: "external_ref", label: t("f.external_ref") },
    { name: "is_active", label: t("f.is_active"), type: "checkbox" },
    { name: "metadata", label: t("f.metadata"), type: "json" },
  ];
}

export default function OrgUnitsPage() {
  const t = useTranslations("org_units");
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const isNew = params.get("new") === "1";
  const newParent = params.get("parent") ?? "";
  const sel = params.get("sel") ?? "";
  const [orgId, setOrgId] = useState("");
  const [pendingDelete, setPendingDelete] = useState<OrgUnit | null>(null);

  const { can } = usePermissions();
  const canCreate = can("organization.create");
  const canUpdate = can("organization.update");
  const canDelete = can("organization.delete");

  const firstOrg = useFirstOrg();
  useEffect(() => { if (!orgId && firstOrg.id) setOrgId(firstOrg.id); }, [firstOrg.id, orgId]);

  const units = useQuery({
    queryKey: ["org-units", orgId], queryFn: () => listUnits(orgId), enabled: !!orgId,
  });
  const all = units.data ?? [];
  // A parent can't be deleted while it has children (backend 409, no cascade).
  const parentIds = new Set(all.map((u) => u.parent_id).filter((p): p is string => !!p));
  const tree = orderForTree(all);

  const openCreate = (parent?: string) =>
    router.replace(`${pathname}?new=1${parent ? `&parent=${parent}` : ""}`, { scroll: false });
  const openEdit = (id: string) => router.replace(`${pathname}?sel=${id}`, { scroll: false });
  const closeSurface = () => router.replace(pathname, { scroll: false });

  const del = useMutation({
    mutationFn: (u: OrgUnit) => deleteUnit(u.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["org-units", orgId] }); toast({ variant: "success", title: t("toast.deleted") }); },
    onError: (e: unknown) => toast({ variant: "error", title: t("toast.delete_failed"),
      description: e instanceof ApiError ? e.message : undefined }),
  });

  const surfaceOpen = (isNew && canCreate && !!orgId) || !!sel;

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-64">
            <OrgCombobox value={orgId} allowNone={false} placeholder={t("org_placeholder")}
              onChange={(id) => setOrgId(id)} />
          </div>
          <ExportMenu filename="org-units" disabled={!orgId} path={unitsExportPath(orgId)} />
          {canCreate && (
            <Button size="sm" disabled={!orgId} onClick={() => openCreate()}>
              <Plus className="size-4" /> {t("new")}
            </Button>
          )}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 gap-4">
        <div className="min-w-0 flex-1 space-y-1 overflow-auto">
          {!orgId && <p className="text-sm text-muted-foreground">{t("empty_no_org")}</p>}
          {orgId && units.isLoading && <p className="text-sm text-muted-foreground">{t("loading")}</p>}
          {orgId && units.isError && <p className="text-sm text-destructive">{t("load_error")}</p>}
          {orgId && units.data && tree.length === 0 && <p className="text-sm text-muted-foreground">{t("empty")}</p>}
          {tree.map(({ unit, level }) => (
            <UnitRow key={unit.id} unit={unit} level={level} selected={sel === unit.id}
              canCreate={canCreate} canDelete={canDelete} hasChildren={parentIds.has(unit.id)}
              onEdit={() => openEdit(unit.id)}
              onAddChild={() => openCreate(unit.id)}
              onDelete={() => setPendingDelete(unit)}
              busy={del.isPending} />
          ))}
          {/* The list is server-capped at 200 (no keyset on the tree view); never
              hide the truncation silently (no-silent-cap mandate). */}
          {orgId && all.length >= 200 && (
            <p className="mt-2 text-xs text-amber-600 dark:text-amber-500" role="status">
              {t("capped", { n: all.length })}
            </p>
          )}
        </div>

        {surfaceOpen && (
          isNew
            ? (canCreate && <UnitCreateSurface orgId={orgId} units={all} presetParent={newParent}
                onClose={closeSurface} onSaved={() => units.refetch()} />)
            : <UnitEditSurface key={sel} unitId={sel} orgId={orgId} units={all}
                readOnly={!canUpdate} onClose={closeSurface} />
        )}
      </div>

      <ConfirmDialog
        open={!!pendingDelete}
        onOpenChange={(o) => { if (!o) setPendingDelete(null); }}
        danger
        title={t("delete.title")}
        body={t("delete.body", { name: pendingDelete ? `${pendingDelete.code} · ${pendingDelete.name}` : "" })}
        confirmLabel={t("delete.confirm")}
        busy={del.isPending}
        onConfirm={() => { if (pendingDelete) del.mutate(pendingDelete); setPendingDelete(null); }}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}

function UnitRow({ unit, level, selected, canCreate, canDelete, hasChildren, onEdit, onAddChild, onDelete, busy }: {
  unit: OrgUnit; level: number; selected: boolean; canCreate: boolean; canDelete: boolean;
  hasChildren: boolean; onEdit: () => void; onAddChild: () => void; onDelete: () => void; busy: boolean;
}) {
  const t = useTranslations("org_units");
  return (
    <div className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm ${selected ? "bg-primary/10" : ""}`}
      style={{ marginLeft: `${level * 1.25}rem` }}>
      {level > 0 && <CornerDownRight className="size-3.5 shrink-0 text-muted-foreground" />}
      <button type="button" className="min-w-0 text-left" onClick={onEdit}>
        <span className="font-mono text-xs hover:underline">{unit.code}</span>
        <span className="ml-2">{unit.name}</span>
      </button>
      <div className="ml-auto flex shrink-0 items-center gap-1">
        <Badge variant="secondary">{unit.unit_type}</Badge>
        {!unit.is_active && <Badge variant="warning">{t("inactive")}</Badge>}
        {canCreate && (
          <Button variant="ghost" size="icon" onClick={onAddChild} title={t("add_child")}>
            <Plus className="size-3.5" />
          </Button>
        )}
        {canDelete && (
          <Button variant="ghost" size="icon" disabled={busy || hasChildren} onClick={onDelete}
            title={hasChildren ? t("delete_parent_hint") : t("delete.confirm")}>
            <Trash2 className="size-3.5" />
          </Button>
        )}
      </div>
    </div>
  );
}

function UnitCreateSurface({ orgId, units, presetParent, onClose, onSaved }: {
  orgId: string; units: OrgUnit[]; presetParent: string; onClose: () => void; onSaved: () => void;
}) {
  const t = useTranslations("org_units");
  const qc = useQueryClient();
  const fields = useUnitFields(validParents(units));
  return (
    <RecordSurface title={t("new_title")} resourceKey="org-units" onClose={onClose}>
      <RecordForm
        fields={fields}
        mode="create"
        layout="rich"
        enableSaveNew
        submitLabel={t("new")}
        initial={{ unit_type: "department", parent_id: presetParent, is_active: true }}
        onSubmit={(payload) => createUnit(orgId, payload)}
        onSuccess={({ again }) => {
          qc.invalidateQueries({ queryKey: ["org-units", orgId] });
          onSaved();
          toast({ variant: "success", title: t("toast.created") });
          if (!again) onClose();
        }}
        onCancel={onClose}
      />
    </RecordSurface>
  );
}

function UnitEditSurface({ unitId, orgId, units, readOnly, onClose }: {
  unitId: string; orgId: string; units: OrgUnit[]; readOnly: boolean; onClose: () => void;
}) {
  const t = useTranslations("org_units");
  const qc = useQueryClient();
  const { data, isError } = useQuery({ queryKey: ["org-unit", unitId], queryFn: () => getUnit(unitId) });
  const fields = useUnitFields(validParents(units, unitId));

  return (
    <RecordSurface title={data ? `${data.code} · ${data.name}` : t("edit_title")} resourceKey="org-units" onClose={onClose}>
      {isError && <p className="text-sm text-destructive">{t("load_error")}</p>}
      {!data && !isError && <p className="text-sm text-muted-foreground">{t("loading")}</p>}
      {data && (
        <RecordForm
          key={data.etag ?? unitId}
          fields={fields}
          mode="edit"
          layout="rich"
          readOnly={readOnly}
          initial={data as unknown as Record<string, unknown>}
          etag={data.etag}
          onSubmit={(payload, etag) => updateUnit(unitId, payload, etag)}
          onSuccess={() => {
            qc.invalidateQueries({ queryKey: ["org-unit", unitId] });
            qc.invalidateQueries({ queryKey: ["org-units", orgId] });
            toast({ variant: "success", title: t("toast.saved") });
          }}
          onConflict={() => qc.invalidateQueries({ queryKey: ["org-unit", unitId] })}
        />
      )}
    </RecordSurface>
  );
}
