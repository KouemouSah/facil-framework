"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { RecordForm } from "@/components/ui/record-form";
import { getSchema } from "@/lib/schema/api";
import { fieldSpecToFieldDef } from "@/lib/schema/to-field-def";
import type { Locale } from "@/lib/schema/types";
import { updateOrg } from "./api";

/**
 * Generic schema-generated form for an org-scoped JSON blob column
 * (`document_identity`, `settings`, …) — factored out of what was originally
 * `DocumentIdentityForm` (Task 8) once `settings` (Task 9) needed the exact
 * same shape: one `RecordForm` driven by `GET /api/v1/schema/{schemaTarget}`,
 * submitting `{ [payloadKey]: payload }` through `PUT organization/{id}`.
 *
 * The backend enforces merge-preserve semantics (`merge_blob`): only the
 * declared keys are ever written by this form; a pre-existing undeclared key
 * (historic data nobody ever validated) survives untouched in the stored blob.
 *
 * Field LABELS come from the server (`fieldSpecToFieldDef`) — never
 * duplicated here. Only the surrounding chrome (loading/error/save labels)
 * is localized client-side, under the `organizations` i18n namespace shared
 * by every blob-form tab.
 */
export function SchemaBlobForm({ orgId, schemaTarget, payloadKey, blob, etag, onSaved, canWrite,
  placeholders, onSubmit }: {
  orgId: string;
  schemaTarget: string;
  payloadKey: string;
  blob: Record<string, unknown>;
  etag?: string;
  onSaved: () => void;
  canWrite: boolean;
  /** Per-field "inherited value" hints (SP1 D1, org_unit/site override tabs),
   *  keyed by the schema's field key — rendered as the native input
   *  placeholder ("Hérité : Facil SA") so a blank override reads as
   *  "inherit", never as "empty on purpose". Absent = today's plain behaviour. */
  placeholders?: Record<string, string>;
  /** Override the default `PUT organization/{orgId}` submit — an org_unit or
   *  site override tab PUTs its OWN row, not the organization's. Every
   *  pre-existing caller (organization.document_identity / .settings) omits
   *  this and keeps writing through `updateOrg` unchanged. */
  onSubmit?: (payload: Record<string, unknown>, etag?: string) => Promise<unknown>;
}) {
  const locale = useLocale() as Locale;
  const t = useTranslations("organizations");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["schema", schemaTarget, orgId],
    queryFn: () => getSchema(schemaTarget, orgId),
  });

  if (isError) {
    return <p className="text-sm text-destructive">{t("load_error")}</p>;
  }
  if (isLoading || !data) {
    return <p className="text-sm text-muted-foreground">{t("loading")}</p>;
  }

  const submit = onSubmit ?? ((payload: Record<string, unknown>, tag?: string) =>
    updateOrg(orgId, { [payloadKey]: payload }, tag));

  return (
    <RecordForm
      mode="edit"
      layout="rich"
      fields={data.fields.map((s) => {
        const fd = fieldSpecToFieldDef(s, locale);
        const inherited = placeholders?.[s.key];
        if (!inherited) return fd;
        // `FileUpload` (type "file") reads its "inherited" channel as a raw
        // preview URL, not display text — every other control shows the
        // formatted "Hérité : X" string via the native `placeholder`
        // attribute. Same `f.placeholder` field, two renderings.
        return { ...fd, placeholder: s.type === "file" ? inherited : t("inherited_placeholder", { value: inherited }) };
      })}
      initial={blob ?? {}}
      etag={etag}
      readOnly={!canWrite}
      onSubmit={submit}
      onSuccess={onSaved}
      onConflict={onSaved}
      submitLabel={t("save")}
    />
  );
}
