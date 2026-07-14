"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { RecordForm } from "@/components/ui/record-form";
import { getSchema } from "@/lib/schema/api";
import { fieldSpecToFieldDef } from "@/lib/schema/to-field-def";
import type { Locale } from "@/lib/schema/types";
import { usePermissions } from "@/lib/use-permissions";
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
export function SchemaBlobForm({ orgId, schemaTarget, payloadKey, blob, etag, onSaved, canWrite }: {
  orgId: string;
  schemaTarget: string;
  payloadKey: string;
  blob: Record<string, unknown>;
  etag?: string;
  onSaved: () => void;
  canWrite: boolean;
}) {
  const locale = useLocale() as Locale;
  const t = useTranslations("organizations");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["schema", schemaTarget],
    queryFn: () => getSchema(schemaTarget),
  });

  if (isError) {
    return <p className="text-sm text-destructive">{t("load_error")}</p>;
  }
  if (isLoading || !data) {
    return <p className="text-sm text-muted-foreground">{t("loading")}</p>;
  }

  return (
    <RecordForm
      mode="edit"
      layout="rich"
      fields={data.fields.map((s) => fieldSpecToFieldDef(s, locale))}
      initial={blob ?? {}}
      etag={etag}
      readOnly={!canWrite}
      onSubmit={(payload, tag) => updateOrg(orgId, { [payloadKey]: payload }, tag)}
      onSuccess={onSaved}
      onConflict={onSaved}
      submitLabel={t("save")}
    />
  );
}
