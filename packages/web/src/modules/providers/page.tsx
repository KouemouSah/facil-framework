"use client";

import { useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { Activity, CheckCircle2, XCircle, Loader2, Plug, Plus, Star, Trash2 } from "lucide-react";
import { toast } from "@/lib/toast";
import { ApiError } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { RecordForm, RecordSurface } from "@/components/shared";
import { usePermissions } from "@/lib/use-permissions";
import type { Locale } from "@/lib/schema/types";
import { buildProviderFields, createInitial, flattenProvider, splitPayload } from "./fields";
import {
  LLM_KINDS, ROUTING_ROLES, providersToMap, routingToProviders, validateRouting, type NamedProvider,
} from "./routing";
import {
  CAPABILITIES, checkProvider, checkRouting, deleteProvider, getProvider, getRouting,
  getSettingOrNull, listProviders, listRegistered, putProvider, putSetting, setDefaultProvider,
  type ConfigField, type HealthResult, type Provider, type RegisteredType, type RoutingCheck, type RoutingView,
} from "./api";

const schemaFor = (registered: RegisteredType[] | undefined, cap: string, code: string): ConfigField[] =>
  registered?.find((r) => r.capability === cap && r.provider_code === code)?.config_schema ?? [];

export default function ProvidersPage() {
  const t = useTranslations("providers");
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const newCap = params.get("new") ?? "";                 // ?new=<capability>
  const sel = params.get("sel") ?? "";                    // ?sel=<capability>/<code>
  const [pendingDelete, setPendingDelete] = useState<Provider | null>(null);

  const { can } = usePermissions();
  const canManage = can("provider.manage");

  const providers = useQuery({ queryKey: ["providers"], queryFn: () => listProviders() });
  const registered = useQuery({ queryKey: ["providers-registered"], queryFn: listRegistered });

  const openCreate = (cap: string) => router.replace(`${pathname}?new=${cap}`, { scroll: false });
  const openEdit = (cap: string, code: string) => router.replace(`${pathname}?sel=${cap}/${code}`, { scroll: false });
  const closeSurface = () => router.replace(pathname, { scroll: false });

  const byCapability = (cap: string) => (providers.data ?? []).filter((p) => p.capability === cap);
  const configuredCodes = (cap: string) => new Set(byCapability(cap).map((p) => p.provider_code));
  const availableTypes = (cap: string) =>
    (registered.data ?? []).filter((r) => r.capability === cap && !configuredCodes(cap).has(r.provider_code));

  const del = useMutation({
    mutationFn: (p: Provider) => deleteProvider(p.capability, p.provider_code),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["providers"] }); toast({ variant: "success", title: t("toast.deleted") }); },
    onError: (e: unknown) => toast({ variant: "error", title: t("toast.delete_failed"),
      description: e instanceof ApiError ? e.message : undefined }),
  });

  const setDefault = useMutation({
    mutationFn: (p: Provider) => setDefaultProvider(p.capability, p.provider_code),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["providers"] }); toast({ variant: "success", title: t("toast.default_set") }); },
    onError: (e: unknown) => toast({ variant: "error", title: t("toast.default_failed"),
      description: e instanceof ApiError ? e.message : undefined }),
  });

  const [selCap, selCode] = sel ? sel.split("/") : ["", ""];
  const surfaceOpen = (!!newCap && canManage) || !!sel;

  return (
    <div className="flex h-full flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      {registered.isError && (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {t("registry_error")}
        </p>
      )}

      <div className="flex min-h-0 flex-1 gap-4">
        <div className="flex min-w-0 flex-1 flex-col gap-4 overflow-auto">
          <RoutingCard />
          <div className="grid gap-4 lg:grid-cols-2">
            {CAPABILITIES.map((cap) => (
              <Card key={cap}>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Plug className="size-4 text-muted-foreground" />
                    <CardTitle className="text-base">{t(`cap.${cap}`)}</CardTitle>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {t("types_available", { count: (registered.data ?? []).filter((r) => r.capability === cap).length })}
                    </span>
                    {canManage && availableTypes(cap).length > 0 && (
                      <Button variant="ghost" size="sm" onClick={() => openCreate(cap)}>
                        <Plus className="size-3.5" /> {t("add")}
                      </Button>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="space-y-2">
                  {providers.isLoading && <p className="text-sm text-muted-foreground">{t("loading")}</p>}
                  {providers.isError && <p className="text-sm text-destructive">{t("load_error")}</p>}
                  {providers.data && byCapability(cap).length === 0 && (
                    <p className="text-sm text-muted-foreground">{t("empty")}</p>
                  )}
                  {byCapability(cap).map((p) => (
                    <ProviderRow key={`${p.capability}/${p.provider_code}`} provider={p} canManage={canManage}
                      selected={sel === `${p.capability}/${p.provider_code}`}
                      onEdit={() => openEdit(p.capability, p.provider_code)}
                      onSetDefault={() => setDefault.mutate(p)}
                      onDelete={() => setPendingDelete(p)}
                      busy={setDefault.isPending || del.isPending} />
                  ))}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {surfaceOpen && (
          newCap
            ? (canManage && <CreateSurface capability={newCap}
                onClose={closeSurface} onSaved={() => providers.refetch()} />)
            : <EditSurface key={sel} capability={selCap} code={selCode}
                readOnly={!canManage} onClose={closeSurface} />
        )}
      </div>

      <ConfirmDialog
        open={!!pendingDelete}
        onOpenChange={(o) => { if (!o) setPendingDelete(null); }}
        danger
        title={t("delete.title")}
        body={t("delete.body", { name: pendingDelete ? `${pendingDelete.capability}/${pendingDelete.provider_code}` : "" })}
        confirmLabel={t("delete.confirm")}
        busy={del.isPending}
        onConfirm={() => { if (pendingDelete) del.mutate(pendingDelete); setPendingDelete(null); }}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}

function ProviderRow({ provider, canManage, selected, onEdit, onSetDefault, onDelete, busy }: {
  provider: Provider; canManage: boolean; selected: boolean;
  onEdit: () => void; onSetDefault: () => void; onDelete: () => void; busy: boolean;
}) {
  const t = useTranslations("providers");
  const check = useMutation<HealthResult, Error>({
    mutationFn: () => checkProvider(provider.capability, provider.provider_code),
    // A diagnostic that fails silently is worse than useless: surface transport
    // errors (the healthcheck's own request failing, not an unhealthy 200 result).
    onError: (e) => toast({ variant: "error", title: t("toast.check_failed"),
      description: e instanceof ApiError ? e.message : undefined }),
  });
  const health = check.data;

  return (
    <div className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm ${selected ? "bg-primary/10" : ""}`}>
      <button type="button" className="font-mono text-xs hover:underline disabled:cursor-default disabled:no-underline"
        onClick={onEdit} disabled={!canManage}>{provider.provider_code}</button>
      {provider.is_default && <Badge variant="success">{t("badge.default")}</Badge>}
      {!provider.is_active && <Badge variant="warning">{t("badge.inactive")}</Badge>}
      {health && (
        <span className={`inline-flex items-center gap-1 text-xs ${health.ok ? "text-emerald-600" : "text-destructive"}`}>
          {health.ok ? <CheckCircle2 className="size-3.5" /> : <XCircle className="size-3.5" />}
          <span className="max-w-[12rem] truncate" title={health.detail}>{health.detail}</span>
        </span>
      )}
      <div className="ml-auto flex items-center gap-1">
        {/* Health-check triggers an outbound probe → provider.manage (SEC-F6b). */}
        {canManage && (
          <Button variant="ghost" size="sm" disabled={check.isPending} onClick={() => check.mutate()} title={t("check")}>
            {check.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Activity className="size-3.5" />}
          </Button>
        )}
        {canManage && !provider.is_default && (
          <Button variant="ghost" size="icon" disabled={busy} onClick={onSetDefault} title={t("set_default")}>
            <Star className="size-3.5" />
          </Button>
        )}
        {canManage && (
          <Button variant="ghost" size="icon" disabled={busy} onClick={onDelete} title={t("delete.confirm")}>
            <Trash2 className="size-3.5" />
          </Button>
        )}
      </div>
    </div>
  );
}

function SecretNote() {
  const t = useTranslations("providers");
  return (
    <p className="mb-3 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
      {t("secret_note")}
    </p>
  );
}

function CreateSurface({ capability, onClose, onSaved }: {
  capability: string; onClose: () => void; onSaved: () => void;
}) {
  const t = useTranslations("providers");
  const locale = useLocale() as Locale;
  const qc = useQueryClient();
  const [code, setCode] = useState("");
  // Own the registered query (shared cache) so the type list is always current.
  const registered = useQuery({ queryKey: ["providers-registered"], queryFn: listRegistered });
  const configured = new Set(
    (qc.getQueryData<Provider[]>(["providers"]) ?? [])
      .filter((p) => p.capability === capability).map((p) => p.provider_code));
  const types = (registered.data ?? []).filter((r) => r.capability === capability && !configured.has(r.provider_code));
  const schema = schemaFor(registered.data, capability, code);
  const schemaKeys = schema.map((f) => f.key);

  return (
    <RecordSurface title={t("new_title", { capability: t(`cap.${capability}`) })} resourceKey="providers" onClose={onClose}>
      <SecretNote />
      <div className="mb-4 space-y-1.5">
        <Label htmlFor="ptype">{t("pick_type")}</Label>
        <Select id="ptype" value={code} onChange={(e) => setCode(e.target.value)}
          disabled={!registered.data}>
          <option value="">{t("pick_type_placeholder")}</option>
          {types.map((r) => <option key={r.provider_code} value={r.provider_code}>{r.provider_code}</option>)}
        </Select>
        {registered.isError && <p className="text-xs text-destructive">{t("load_error")}</p>}
        {registered.isLoading && <p className="text-xs text-muted-foreground">{t("loading")}</p>}
        {registered.data && types.length === 0 && (
          <p className="text-xs text-muted-foreground">{t("all_configured")}</p>
        )}
      </div>
      {code && (
        <RecordForm
          key={code}
          fields={buildProviderFields(schema, locale)}
          mode="create"
          layout="rich"
          submitLabel={t("create")}
          initial={createInitial(schema)}
          onSubmit={(payload) => putProvider(capability, code, splitPayload(payload, schemaKeys))}
          onSuccess={() => {
            qc.invalidateQueries({ queryKey: ["providers"] });
            onSaved();
            toast({ variant: "success", title: t("toast.saved") });
            onClose();
          }}
          onCancel={onClose}
        />
      )}
    </RecordSurface>
  );
}

function EditSurface({ capability, code, readOnly, onClose }: {
  capability: string; code: string; readOnly: boolean; onClose: () => void;
}) {
  const t = useTranslations("providers");
  const locale = useLocale() as Locale;
  const qc = useQueryClient();
  const provider = useQuery({
    queryKey: ["provider", capability, code],
    queryFn: () => getProvider(capability, code),
  });
  // Own the registered query too: the config_schema MUST be loaded before the
  // form renders, else an empty schema would PUT `config: {}` and wipe the stored
  // config (deep-link race). Gate the form on BOTH being ready.
  const registered = useQuery({ queryKey: ["providers-registered"], queryFn: listRegistered });
  const isRegistered = registered.data?.some(
    (r) => r.capability === capability && r.provider_code === code);
  const schema = schemaFor(registered.data, capability, code);
  const schemaKeys = schema.map((f) => f.key);
  const data = provider.data;
  const isError = provider.isError || registered.isError;
  const ready = !!data && !!registered.data;

  return (
    <RecordSurface title={`${t(`cap.${capability}`)} · ${code}`} resourceKey="providers" onClose={onClose}>
      {!readOnly && <SecretNote />}
      {isError && <p className="text-sm text-destructive">{t("load_error")}</p>}
      {!ready && !isError && <p className="text-sm text-muted-foreground">{t("loading")}</p>}
      {ready && !isRegistered && (
        <p className="text-sm text-destructive">{t("unregistered_type")}</p>
      )}
      {ready && isRegistered && (
        <RecordForm
          // Remount (reseed) if the schema arrives/changes so config fields never
          // render blank against a live row.
          key={`${data!.etag ?? code}:${schemaKeys.length}`}
          fields={buildProviderFields(schema, locale)}
          mode="edit"
          layout="rich"
          readOnly={readOnly}
          submitLabel={t("save")}
          initial={flattenProvider(data!)}
          etag={data!.etag}
          onSubmit={(payload, etag) => putProvider(capability, code, splitPayload(payload, schemaKeys), etag)}
          onSuccess={() => {
            qc.invalidateQueries({ queryKey: ["provider", capability, code] });
            qc.invalidateQueries({ queryKey: ["providers"] });
            toast({ variant: "success", title: t("toast.saved") });
          }}
          onConflict={() => qc.invalidateQueries({ queryKey: ["provider", capability, code] })}
        />
      )}
    </RecordSurface>
  );
}

function RoutingCard() {
  const t = useTranslations("providers");
  const { can } = usePermissions();
  const canEdit = can("settings.manage");
  const canProbe = can("provider.manage");  // /llm/routing/check is manage-gated (SEC-F6b)
  const [editing, setEditing] = useState(false);
  const routing = useQuery({ queryKey: ["llm-routing"], queryFn: getRouting });
  const probe = useMutation<RoutingCheck, Error>({
    mutationFn: checkRouting,
    onError: (e) => toast({ variant: "error", title: t("toast.check_failed"),
      description: e instanceof ApiError ? e.message : undefined }),
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle className="text-base">{t("routing.title")}</CardTitle>
          <div className="ml-auto flex items-center gap-2">
            {canEdit && !editing && (
              <Button data-testid="routing-edit" variant="outline" size="sm" onClick={() => setEditing(true)}>{t("routing.edit")}</Button>
            )}
            {!editing && canProbe && (
              <Button variant="outline" size="sm" disabled={probe.isPending} onClick={() => probe.mutate()}>
                {probe.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Activity className="size-3.5" />}
                {t("routing.check")}
              </Button>
            )}
          </div>
        </div>
        <CardDescription>{t("routing.subtitle")}</CardDescription>
      </CardHeader>
      <CardContent>
        {routing.isLoading && <p className="text-sm text-muted-foreground">{t("loading")}</p>}
        {routing.isError && <p className="text-sm text-destructive">{t("load_error")}</p>}
        {routing.data && editing && (
          <RoutingEditor view={routing.data} onDone={() => setEditing(false)} onCancel={() => setEditing(false)} />
        )}
        {routing.data && !editing && (
          <dl className="grid gap-2 sm:grid-cols-3">
            {ROUTING_ROLES.map((role) => {
              const name = routing.data.routing[role];
              const status = probe.data?.[role];
              return (
                <div key={role} className="rounded-md border px-3 py-2">
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">{t(`routing.role.${role}`)}</dt>
                  <dd className="mt-0.5 font-medium">{name || <span className="text-muted-foreground">{t("routing.none")}</span>}</dd>
                  {status && (
                    <p className={`mt-1 inline-flex items-center gap-1 text-xs ${status.ok ? "text-emerald-600" : "text-destructive"}`}>
                      {status.ok ? <CheckCircle2 className="size-3.5" /> : <XCircle className="size-3.5" />}
                      <span className="max-w-[12rem] truncate" title={status.detail}>{status.detail}</span>
                    </p>
                  )}
                </div>
              );
            })}
          </dl>
        )}
      </CardContent>
    </Card>
  );
}

function RoutingEditor({ view, onDone, onCancel }: {
  view: RoutingView; onDone: () => void; onCancel: () => void;
}) {
  const t = useTranslations("providers");
  const qc = useQueryClient();
  const [list, setList] = useState<NamedProvider[]>(() => routingToProviders(view));
  const [routing, setRouting] = useState<Record<string, string>>(() => ({ ...view.routing }));
  const [error, setError] = useState("");

  // Raw settings carry the etags for optimistic concurrency (unset → null → create).
  const routingSetting = useQuery({ queryKey: ["setting", "ai.routing"], queryFn: () => getSettingOrNull("ai.routing") });
  const providersSetting = useQuery({ queryKey: ["setting", "ai.providers"], queryFn: () => getSettingOrNull("ai.providers") });
  // Don't allow a save until BOTH etag lookups have settled — a blind PUT (no
  // If-Match) would silently defeat the concurrency guard. isSuccess covers the
  // unset (404→null) case too.
  const etagsReady = routingSetting.isSuccess && providersSetting.isSuccess;
  const etagsError = routingSetting.isError || providersSetting.isError;

  const setProvider = (i: number, patch: Partial<NamedProvider>) =>
    setList((l) => l.map((p, idx) => (idx === i ? { ...p, ...patch } : p)));
  const addProvider = () =>
    setList((l) => [...l, { name: "", kind: "ollama", endpoint: "", model: "", api_key_secret: "" }]);
  const removeProvider = (i: number) => setList((l) => l.filter((_, idx) => idx !== i));

  const save = useMutation({
    mutationFn: async () => {
      const problem = validateRouting(list, routing);
      if (problem) throw new Error(problem);
      // Providers first (so routing references resolve), then the routing map.
      await putSetting("ai.providers", providersToMap(list), providersSetting.data?.etag);
      await putSetting("ai.routing", routing, routingSetting.data?.etag);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["llm-routing"] });
      qc.invalidateQueries({ queryKey: ["setting"] });
      toast({ variant: "success", title: t("routing.saved") });
      onDone();
    },
    onError: (e: unknown) => {
      if (e instanceof Error && (e.message === "duplicate_name" || e.message === "unknown_ref")) {
        setError(t(`routing.err_${e.message}`)); // pre-PUT validation → nothing written
      } else if (e instanceof ApiError && e.status === 409) {
        // Lost update: reload the current routing and DISCARD local edits (never
        // silently overwrite the concurrent change). The operator re-opens to redo.
        qc.invalidateQueries({ queryKey: ["llm-routing"] });
        qc.invalidateQueries({ queryKey: ["setting"] });
        toast({ variant: "error", title: t("routing.conflict") });
        onCancel();
      } else {
        // Non-atomic: providers may already be saved. Refresh etags + reload so the
        // read view reflects the half-applied state; keep the editor open to retry.
        qc.invalidateQueries({ queryKey: ["llm-routing"] });
        qc.invalidateQueries({ queryKey: ["setting"] });
        setError(e instanceof ApiError ? e.message : t("routing.save_failed"));
      }
    },
  });

  const names = list.map((p) => p.name.trim()).filter(Boolean);

  return (
    <div className="space-y-4">
      <p className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
        {t("routing.secret_note")}
      </p>

      {/* Named providers */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{t("routing.providers")}</span>
          <Button variant="ghost" size="sm" className="ml-auto" onClick={addProvider}>
            <Plus className="size-3.5" /> {t("add")}
          </Button>
        </div>
        {list.length === 0 && <p className="text-xs text-muted-foreground">{t("routing.no_providers")}</p>}
        {list.map((p, i) => (
          <div key={i} className="grid gap-2 rounded-md border p-2 sm:grid-cols-[1fr_auto]">
            <div className="grid gap-2 sm:grid-cols-2">
              <Input placeholder={t("routing.name")} value={p.name} onChange={(e) => setProvider(i, { name: e.target.value })} />
              <Select value={p.kind} onChange={(e) => setProvider(i, { kind: e.target.value })}>
                {LLM_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
              </Select>
              <Input placeholder={t("routing.endpoint")} value={p.endpoint} onChange={(e) => setProvider(i, { endpoint: e.target.value })} />
              <Input placeholder={t("routing.model")} value={p.model} onChange={(e) => setProvider(i, { model: e.target.value })} />
              <Input className="sm:col-span-2" placeholder={t("routing.api_key_secret")} value={p.api_key_secret}
                onChange={(e) => setProvider(i, { api_key_secret: e.target.value })} />
            </div>
            <Button variant="ghost" size="icon" onClick={() => removeProvider(i)} title={t("routing.remove")}>
              <Trash2 className="size-3.5" />
            </Button>
          </div>
        ))}
      </div>

      {/* Role assignment */}
      <div className="space-y-2">
        <span className="text-sm font-medium">{t("routing.assignment")}</span>
        <div className="grid gap-2 sm:grid-cols-3">
          {ROUTING_ROLES.map((role) => (
            <div key={role} className="space-y-1">
              <Label htmlFor={`rt-${role}`}>{t(`routing.role.${role}`)}</Label>
              <Select id={`rt-${role}`} value={routing[role] ?? ""}
                onChange={(e) => setRouting((r) => ({ ...r, [role]: e.target.value }))}>
                <option value="">{t("routing.none")}</option>
                {names.map((n) => <option key={n} value={n}>{n}</option>)}
              </Select>
            </div>
          ))}
        </div>
      </div>

      {etagsError && <p className="text-sm text-destructive">{t("routing.etags_error")}</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex items-center justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={onCancel}>{t("routing.cancel")}</Button>
        <Button size="sm" disabled={save.isPending || !etagsReady}
          onClick={() => { setError(""); save.mutate(); }}>
          {save.isPending ? t("routing.saving") : t("routing.save")}
        </Button>
      </div>
    </div>
  );
}
