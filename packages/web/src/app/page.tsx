import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/app-shell";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";

// D5.0 demo dashboard: a no-scroll overview grid (KPI cards) inside the fixed
// shell. Real data wires in once auth (D5.1) + admin (D5.2) land.
export default async function DashboardPage() {
  const t = await getTranslations("nav");
  const kpis = [
    { label: t("organizations"), value: "—", hint: "tenants" },
    { label: t("locations"), value: "—", hint: "sites & branches" },
    { label: t("agents"), value: "—", hint: "active accounts" },
    { label: t("roles"), value: "—", hint: "scoped assignments" },
  ];
  return (
    <AppShell>
      <div className="mx-auto max-w-6xl space-y-6">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{t("dashboard")}</h1>
          <p className="text-sm text-muted-foreground">
            Facil Framework — web console (D5.0 scaffold).
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
    </AppShell>
  );
}
