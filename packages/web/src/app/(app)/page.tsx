"use client";

import { useTranslations } from "next-intl";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { useSession } from "@/lib/use-session";

// D5.1 dashboard: a no-scroll overview grid inside the fixed shell. Greets the
// signed-in principal (from /api/auth/session); real KPI data lands in D5.2.
export default function DashboardPage() {
  const t = useTranslations("nav");
  const { data: session } = useSession();
  const who =
    session?.account?.display_name || session?.account?.email ||
    (session?.break_glass ? "Bootstrap Admin" : "");

  const kpis = [
    { label: t("organizations"), value: "—", hint: "tenants" },
    { label: t("locations"), value: "—", hint: "sites & branches" },
    { label: t("agents"), value: "—", hint: "active accounts" },
    { label: t("roles"), value: "—", hint: "scoped assignments" },
  ];
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{t("dashboard")}</h1>
        <p className="text-sm text-muted-foreground">
          {who ? `Welcome, ${who}.` : "Facil Framework — web console."}
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {kpis.map((k) => (
          <Card key={k.label}>
            <CardHeader>
              <CardDescription>{k.label}</CardDescription>
              <CardTitle className="text-2xl">{k.value}</CardTitle>
            </CardHeader>
            <CardContent>
              <span className="text-xs text-muted-foreground">{k.hint}</span>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
