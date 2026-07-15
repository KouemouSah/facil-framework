"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Plus, Search, Trash2, KeyRound } from "lucide-react";
import { toast } from "@/lib/toast";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { JsonField } from "@/components/ui/json-field";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { RecordSurface } from "@/components/shared";
import { usePermissions } from "@/lib/use-permissions";
import {
  VALUE_TYPES, deleteSetting, getSetting, listSettings, putSetting,
  type Setting, type SettingIn,
} from "./api";
import {
  filterSettings, formatValuePreview, fromSettingValue, groupByScope, scopesOf, toSettingValue,
} from "./value";

// Keys with a dedicated, friendlier editor elsewhere — editing them raw here works
// (parity) but we hint the operator toward the curated surface.
import { curatedHref, isCurated } from "./curated";

export default function ConfigPage() {
  const t = useTranslations("configuration");
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const isNew = params.get("new") === "1";
  const sel = params.get("sel") ?? "";
  const [q, setQ] = useState("");
  const [scope, setScope] = useState("");
  const [pendingDelete, setPendingDelete] = useState<Setting | null>(null);

  const { can } = usePermissions();
  const canManage = can("settings.manage");
  const qc = useQueryClient();

  const settings = useQuery({ queryKey: ["settings"], queryFn: () => listSettings() });

  const openCreate = () => router.replace(`${pathname}?new=1`, { scroll: false });
  const openEdit = (key: string) => router.replace(`${pathname}?sel=${encodeURIComponent(key)}`, { scroll: false });
  const closeSurface = () => router.replace(pathname, { scroll: false });

  const del = useMutation({
    mutationFn: (s: Setting) => deleteSetting(s.key),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["settings"] }); toast({ variant: "success", title: t("toast.deleted") }); },
    onError: (e: unknown) => toast({ variant: "error", title: t("toast.delete_failed"),
      description: e instanceof ApiError ? e.message : undefined }),
  });

  const all = settings.data ?? [];
  const existingKeys = new Set(all.map((s) => s.key));
  const filtered = filterSettings(all, q, scope);
  const groups = groupByScope(filtered);
  const surfaceOpen = (isNew && canManage) || !!sel;

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="h-9 w-56 pl-8" placeholder={t("search_placeholder")}
              value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <Select className="h-9 w-40" value={scope} onChange={(e) => setScope(e.target.value)}>
            <option value="">{t("all_scopes")}</option>
            {scopesOf(all).map((s) => <option key={s} value={s}>{s}</option>)}
          </Select>
          {canManage && (
            <Button size="sm" onClick={openCreate}><Plus className="size-4" /> {t("new")}</Button>
          )}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 gap-4">
        <div className="min-w-0 flex-1 space-y-4 overflow-auto">
          {settings.isLoading && <p className="text-sm text-muted-foreground">{t("loading")}</p>}
          {settings.isError && <p className="text-sm text-destructive">{t("load_error")}</p>}
          {settings.data && groups.length === 0 && <p className="text-sm text-muted-foreground">{t("empty")}</p>}
          {groups.map(([scopeName, rows]) => (
            <div key={scopeName}>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{scopeName}</p>
              <div className="space-y-1.5">
                {rows.map((s) => (
                  <SettingRow key={s.key} setting={s} canManage={canManage}
                    selected={sel === s.key}
                    onEdit={() => openEdit(s.key)}
                    onDelete={() => setPendingDelete(s)}
                    busy={del.isPending} />
                ))}
              </div>
            </div>
          ))}
        </div>

        {surfaceOpen && (
          isNew
            ? (canManage && <SettingSurface existingKeys={existingKeys} onClose={closeSurface} onSaved={() => settings.refetch()} />)
            : <SettingEditSurface key={sel} settingKey={sel} readOnly={!canManage} onClose={closeSurface} />
        )}
      </div>

      <ConfirmDialog
        open={!!pendingDelete}
        onOpenChange={(o) => { if (!o) setPendingDelete(null); }}
        danger
        requireText={pendingDelete?.key}
        title={t("delete.title")}
        body={t("delete.body", { key: pendingDelete?.key ?? "" })}
        confirmLabel={t("delete.confirm")}
        busy={del.isPending}
        onConfirm={() => { if (pendingDelete) del.mutate(pendingDelete); setPendingDelete(null); }}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}

function SettingRow({ setting, canManage, selected, onEdit, onDelete, busy }: {
  setting: Setting; canManage: boolean; selected: boolean;
  onEdit: () => void; onDelete: () => void; busy: boolean;
}) {
  const t = useTranslations("configuration");
  return (
    <div className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm ${selected ? "bg-primary/10" : ""}`}>
      <button type="button" className="min-w-0 text-left" onClick={onEdit}>
        <span className="font-mono text-xs hover:underline">{setting.key}</span>
        <span className="ml-2 text-muted-foreground">{formatValuePreview(setting.value, setting.value_type)}</span>
      </button>
      <div className="ml-auto flex shrink-0 items-center gap-1">
        <Badge variant="secondary">{setting.value_type}</Badge>
        {setting.secret_ref && <Badge variant="warning" title={setting.secret_ref}><KeyRound className="size-3" /> ref</Badge>}
        {!setting.is_active && <Badge variant="outline">{t("inactive")}</Badge>}
        {canManage && (
          <Button variant="ghost" size="icon" disabled={busy} onClick={onDelete} title={t("delete.confirm")}>
            <Trash2 className="size-3.5" />
          </Button>
        )}
      </div>
    </div>
  );
}

function SettingEditSurface({ settingKey, readOnly, onClose }: {
  settingKey: string; readOnly: boolean; onClose: () => void;
}) {
  const t = useTranslations("configuration");
  const { data, isError } = useQuery({
    queryKey: ["setting", settingKey],
    queryFn: () => getSetting(settingKey),
  });
  return (
    <RecordSurface title={settingKey} resourceKey="config" onClose={onClose}>
      {isError && <p className="text-sm text-destructive">{t("load_error")}</p>}
      {!data && !isError && <p className="text-sm text-muted-foreground">{t("loading")}</p>}
      {/* Remount (reseed) when the row reloads — after save OR after a 409 refetch —
          so local edits never re-save over a concurrent change (A3 lesson). */}
      {data && <SettingForm key={data.etag ?? settingKey} mode="edit" initial={data}
        existingKeys={new Set()} readOnly={readOnly} onClose={onClose} onSaved={() => undefined} />}
    </RecordSurface>
  );
}

function SettingSurface({ existingKeys, onClose, onSaved }: {
  existingKeys: Set<string>; onClose: () => void; onSaved: () => void;
}) {
  const t = useTranslations("configuration");
  return (
    <RecordSurface title={t("new_title")} resourceKey="config" onClose={onClose}>
      <SettingForm mode="create" initial={null} existingKeys={existingKeys}
        readOnly={false} onClose={onClose} onSaved={onSaved} />
    </RecordSurface>
  );
}

function SettingForm({ mode, initial, existingKeys, readOnly, onClose, onSaved }: {
  mode: "create" | "edit"; initial: Setting | null; existingKeys: Set<string>;
  readOnly: boolean; onClose: () => void; onSaved: () => void;
}) {
  const t = useTranslations("configuration");
  const qc = useQueryClient();
  const seed = initial ? fromSettingValue(initial) : { text: "", bool: false, json: {} };
  const [key, setKey] = useState(initial?.key ?? "");
  const [scope, setScope] = useState(initial?.scope ?? "global");
  const [valueType, setValueType] = useState(initial?.value_type ?? "string");
  const [text, setText] = useState(seed.text);
  const [bool, setBool] = useState(seed.bool);
  const [json, setJson] = useState<unknown>(seed.json);
  const [jsonOk, setJsonOk] = useState(true);
  const [nameEn, setNameEn] = useState(initial?.name.en ?? "");
  const [nameFr, setNameFr] = useState(initial?.name.fr ?? "");
  const [nameEs, setNameEs] = useState(initial?.name.es ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [secretRef, setSecretRef] = useState(initial?.secret_ref ?? "");
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [errors, setErrors] = useState<{ key?: string; value?: string; form?: string }>({});

  const save = useMutation({
    mutationFn: () => {
      const next: typeof errors = {};
      if (mode === "create" && !key.trim()) next.key = t("err.key_required");
      // Create is a PUT upsert — refuse an existing key (a typo would silently
      // overwrite a live setting); the operator must edit it instead.
      else if (mode === "create" && existingKeys.has(key.trim())) next.key = t("err.key_exists");
      const v = toSettingValue(valueType, { text, bool, json });
      if (valueType === "json" && !jsonOk) next.value = t("err.json_invalid");
      else if (!v.ok) next.value = t(`err.${v.error}_invalid`);
      if (Object.keys(next).length) { setErrors(next); throw new Error("validation"); }
      setErrors({});
      const value = v.ok ? v.value : null;
      const body: SettingIn = {
        value, value_type: valueType, scope: scope.trim() || "global", secret_ref: secretRef,
        name_es: nameEs || null, name_fr: nameFr || null, name_en: nameEn || null,
        description: description || null, is_active: isActive,
      };
      return putSetting(key.trim(), body, initial?.etag);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      qc.invalidateQueries({ queryKey: ["setting", key.trim()] });
      toast({ variant: "success", title: t("toast.saved") });
      onSaved();
      if (mode === "create") onClose();
    },
    onError: (e: unknown) => {
      if (e instanceof Error && e.message === "validation") return; // already shown
      if (e instanceof ApiError && e.status === 409) {
        // Lost update: reload the row (→ SettingForm remounts on the new etag and
        // discards stale local edits). Toast, don't leave a stale inline form.
        toast({ variant: "error", title: t("conflict") });
        qc.invalidateQueries({ queryKey: ["setting", key.trim()] });
        qc.invalidateQueries({ queryKey: ["settings"] });
      } else if (e instanceof ApiError && e.status === 422) {
        setErrors({ value: e.message });
      } else {
        setErrors({ form: e instanceof ApiError ? e.message : t("toast.save_failed") });
      }
    },
  });

  const label = useTranslations("configuration.labels");
  return (
    <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (!readOnly) save.mutate(); }}>
      {isCurated(key) && (
        <p className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
          {t("curated_note")}{" "}
          {curatedHref(key) && (
            <Link href={curatedHref(key)!} className="font-medium underline underline-offset-2 hover:text-amber-800 dark:hover:text-amber-300">
              {t("curated_link")}
            </Link>
          )}
        </p>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="cfg-key">{label("key")}</Label>
        <Input id="cfg-key" value={key} disabled={mode === "edit" || readOnly}
          placeholder="e.g. email.provider" onChange={(e) => setKey(e.target.value)} />
        {errors.key && <p className="text-xs text-destructive">{errors.key}</p>}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="cfg-scope">{label("scope")}</Label>
          <Input id="cfg-scope" value={scope} disabled={readOnly} onChange={(e) => setScope(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="cfg-type">{label("value_type")}</Label>
          <Select id="cfg-type" value={valueType} disabled={readOnly} onChange={(e) => setValueType(e.target.value)}>
            {VALUE_TYPES.map((vt) => <option key={vt} value={vt}>{vt}</option>)}
          </Select>
        </div>
      </div>

      {/* Value control adapts to value_type */}
      <div className="space-y-1.5">
        {valueType === "json" ? (
          <JsonField id="cfg-value" label={label("value")} value={json}
            onChange={(v, ok) => { setJson(v); setJsonOk(ok); }} />
        ) : valueType === "boolean" ? (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4 accent-[hsl(var(--primary))]"
              checked={bool} disabled={readOnly} onChange={(e) => setBool(e.target.checked)} />
            {label("value")}
          </label>
        ) : (
          <>
            <Label htmlFor="cfg-value">{label("value")}</Label>
            <Input id="cfg-value" type={valueType === "number" ? "number" : "text"}
              value={text} disabled={readOnly} onChange={(e) => setText(e.target.value)} />
          </>
        )}
        {errors.value && <p className="text-xs text-destructive">{errors.value}</p>}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="cfg-secret">{label("secret_ref")}</Label>
        <Input id="cfg-secret" value={secretRef} disabled={readOnly}
          placeholder={t("secret_ref_hint")} onChange={(e) => setSecretRef(e.target.value)} />
      </div>
      <div className="grid grid-cols-3 gap-2">
        <div className="space-y-1.5"><Label htmlFor="cfg-en">{label("name_en")}</Label>
          <Input id="cfg-en" value={nameEn} disabled={readOnly} onChange={(e) => setNameEn(e.target.value)} /></div>
        <div className="space-y-1.5"><Label htmlFor="cfg-fr">{label("name_fr")}</Label>
          <Input id="cfg-fr" value={nameFr} disabled={readOnly} onChange={(e) => setNameFr(e.target.value)} /></div>
        <div className="space-y-1.5"><Label htmlFor="cfg-es">{label("name_es")}</Label>
          <Input id="cfg-es" value={nameEs} disabled={readOnly} onChange={(e) => setNameEs(e.target.value)} /></div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="cfg-desc">{label("description")}</Label>
        <textarea id="cfg-desc" rows={2} value={description} disabled={readOnly}
          onChange={(e) => setDescription(e.target.value)}
          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50" />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" className="size-4 accent-[hsl(var(--primary))]"
          checked={isActive} disabled={readOnly} onChange={(e) => setIsActive(e.target.checked)} />
        {label("is_active")}
      </label>

      {errors.form && <p className="text-sm text-destructive">{errors.form}</p>}
      {!readOnly && (
        <div className="flex items-center justify-end gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>{t("cancel")}</Button>
          <Button type="submit" size="sm" disabled={save.isPending}>
            {save.isPending ? t("saving") : t("save")}
          </Button>
        </div>
      )}
    </form>
  );
}
