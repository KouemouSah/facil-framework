"use client";

import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { apiFetch } from "@/lib/api";
import { toast } from "@/lib/toast";
import { requiredText } from "@/lib/form-schemas";
import { usePermissions } from "@/lib/use-permissions";
import { RecordForm } from "@/components/shared";
import type { FieldDef } from "@/components/ui/record-form";

interface Branding {
  app_name: string;
  tagline: string;
  logo_url: string;
  logo_dark_url: string;
  favicon_url: string;
  login_background_url: string;
  primary_color: string;
  secondary_color: string;
  theme_mode: string;
  default_locale: string;
  support_email: string;
  support_url: string;
  supported_locales: string[];
  etag?: string;
}

/**
 * Branding (white-label) settings. Modernized to the §11bis `RecordForm` (was a
 * hand-rolled useState form with paste-a-URL asset inputs and English-only
 * strings): localized labels, assets via `FileUpload` (type "image", never a raw
 * URL), colours via the new `color` field, and optimistic concurrency (`If-Match`
 * → 409 reload) handled by RecordForm. Applies live on save (revalidate + refresh).
 */
function useBrandingFields(locales: string[]): FieldDef[] {
  const t = useTranslations("branding.f");
  const th = useTranslations("branding.theme");
  return [
    { name: "app_name", label: t("app_name"), required: true, zod: requiredText(t("app_name")), placeholder: "Facil" },
    { name: "tagline", label: t("tagline") },
    { name: "primary_color", label: t("primary_color"), type: "color", placeholder: "#2563eb" },
    { name: "secondary_color", label: t("secondary_color"), type: "color", placeholder: "#7c3aed" },
    { name: "logo_url", label: t("logo_url"), type: "image" },
    { name: "logo_dark_url", label: t("logo_dark_url"), type: "image" },
    { name: "favicon_url", label: t("favicon_url"), type: "image" },
    { name: "login_background_url", label: t("login_background_url"), type: "image", colSpan: 2 },
    { name: "default_locale", label: t("default_locale"), type: "select", required: true,
      selectOptions: locales.map((l) => ({ value: l, label: l })) },
    { name: "theme_mode", label: t("theme_mode"), type: "select", required: true,
      selectOptions: [
        { value: "light", label: th("light") },
        { value: "dark", label: th("dark") },
        { value: "auto", label: th("auto") },
      ] },
    { name: "support_email", label: t("support_email"), type: "email" },
    { name: "support_url", label: t("support_url") },
  ];
}

export default function SettingsPage() {
  const t = useTranslations("branding");
  const qc = useQueryClient();
  const router = useRouter();
  const { can } = usePermissions();
  const readOnly = !can("branding.manage");

  const { data, isError } = useQuery<Branding>({
    queryKey: ["admin-branding"],
    queryFn: () => apiFetch<Branding>(`/api/v1/admin/branding`),
  });

  const locales = data?.supported_locales?.length ? data.supported_locales : ["en", "fr", "es"];
  const fields = useBrandingFields(locales);

  return (
    <div className="flex h-full flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      <div className="min-h-0 flex-1 overflow-auto">
        <div>
          {isError && <p className="text-sm text-destructive">{t("load_error")}</p>}
          {!data && !isError && <p className="text-sm text-muted-foreground">{t("loading")}</p>}
          {data && (
            <RecordForm
              // Remount on a fresh load (post-save / post-conflict) to reseed initial + etag.
              key={String(data.etag)}
              fields={fields}
              mode="edit"
              layout="rich"
              readOnly={readOnly}
              initial={data as unknown as Record<string, unknown>}
              etag={data.etag}
              submitLabel={t("save")}
              onSubmit={(payload, etag) =>
                apiFetch("/api/v1/admin/branding", {
                  method: "PUT",
                  headers: etag ? { "If-Match": etag } : undefined,
                  body: JSON.stringify(payload),
                })
              }
              onSuccess={async () => {
                qc.invalidateQueries({ queryKey: ["admin-branding"] });
                qc.invalidateQueries({ queryKey: ["branding"] }); // app-shell name/logo/locales
                toast({ variant: "success", title: t("toast.saved") });
                // Bust the cached server-side branding, then re-run the layout to re-theme.
                await fetch("/api/branding/revalidate", { method: "POST" }).catch(() => undefined);
                router.refresh();
              }}
              onConflict={() => qc.invalidateQueries({ queryKey: ["admin-branding"] })}
            />
          )}
        </div>
      </div>
    </div>
  );
}
