"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Activity, CheckCircle2, XCircle, Loader2, Plug } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { usePermissions } from "@/lib/use-permissions";
import {
  CAPABILITIES, checkProvider, checkRouting, getRouting, listProviders, listRegistered,
  type HealthResult, type Provider, type RoutingCheck,
} from "./api";

export default function ProvidersPage() {
  const t = useTranslations("providers");
  const { can } = usePermissions();
  const canManage = can("provider.manage");

  const providers = useQuery({ queryKey: ["providers"], queryFn: () => listProviders() });
  const registered = useQuery({ queryKey: ["providers-registered"], queryFn: listRegistered });

  const byCapability = (cap: string) => (providers.data ?? []).filter((p) => p.capability === cap);
  const registeredCount = (cap: string) =>
    (registered.data ?? []).filter((r) => r.capability === cap).length;

  return (
    <div className="flex h-full flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-auto">
        <RoutingCard />

        <div className="grid gap-4 lg:grid-cols-2">
          {CAPABILITIES.map((cap) => (
            <Card key={cap}>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Plug className="size-4 text-muted-foreground" />
                  <CardTitle className="text-base">{t(`cap.${cap}`)}</CardTitle>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {t("types_available", { count: registeredCount(cap) })}
                  </span>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {providers.isLoading && <p className="text-sm text-muted-foreground">{t("loading")}</p>}
                {providers.isError && <p className="text-sm text-destructive">{t("load_error")}</p>}
                {providers.data && byCapability(cap).length === 0 && (
                  <p className="text-sm text-muted-foreground">{t("empty")}</p>
                )}
                {byCapability(cap).map((p) => (
                  <ProviderRow key={`${p.capability}/${p.provider_code}`} provider={p} canManage={canManage} />
                ))}
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

function ProviderRow({ provider }: { provider: Provider; canManage: boolean }) {
  const t = useTranslations("providers");
  const check = useMutation<HealthResult, Error>({
    mutationFn: () => checkProvider(provider.capability, provider.provider_code),
  });
  const health = check.data;

  return (
    <div className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
      <span className="font-mono text-xs">{provider.provider_code}</span>
      {provider.is_default && <Badge variant="success">{t("badge.default")}</Badge>}
      {!provider.is_active && <Badge variant="warning">{t("badge.inactive")}</Badge>}
      {health && (
        <span className={`inline-flex items-center gap-1 text-xs ${health.ok ? "text-emerald-600" : "text-destructive"}`}>
          {health.ok ? <CheckCircle2 className="size-3.5" /> : <XCircle className="size-3.5" />}
          <span className="max-w-[16rem] truncate" title={health.detail}>{health.detail}</span>
        </span>
      )}
      <Button variant="ghost" size="sm" className="ml-auto" disabled={check.isPending}
        onClick={() => check.mutate()}>
        {check.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Activity className="size-3.5" />}
        {t("check")}
      </Button>
    </div>
  );
}

const ROUTING_ROLES = ["public_chat", "agent_backend", "embedding"] as const;

function RoutingCard() {
  const t = useTranslations("providers");
  const routing = useQuery({ queryKey: ["llm-routing"], queryFn: getRouting });
  const probe = useMutation<RoutingCheck, Error>({ mutationFn: checkRouting });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle className="text-base">{t("routing.title")}</CardTitle>
          <Button variant="outline" size="sm" className="ml-auto" disabled={probe.isPending}
            onClick={() => probe.mutate()}>
            {probe.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Activity className="size-3.5" />}
            {t("routing.check")}
          </Button>
        </div>
        <CardDescription>{t("routing.subtitle")}</CardDescription>
      </CardHeader>
      <CardContent>
        {routing.isLoading && <p className="text-sm text-muted-foreground">{t("loading")}</p>}
        {routing.isError && <p className="text-sm text-destructive">{t("load_error")}</p>}
        {routing.data && (
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
