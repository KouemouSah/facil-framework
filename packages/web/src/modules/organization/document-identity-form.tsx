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
 * `document_identity` used to be a raw JSON textarea (fields.ts:34, removed by
 * Task 8). It is now a generated form driven by the `organization.document_identity`
 * product schema (Task 8, backend `app/core/schema/product_schemas.py`) — the
 * letterhead/footer/seal identity the Document Designer (SP2) prints on every
 * report for this entity.
 *
 * Field LABELS come from the server (`fieldSpecToFieldDef`) — never duplicated
 * here. Only the surrounding chrome (tab title, description, loading, save) is
 * localized client-side, under the `organizations` i18n namespace.
 *
 * The backend enforces merge-preserve semantics (`merge_blob`, Task 8): only the
 * 10 declared keys can be written by this form; any pre-existing undeclared key
 * (historic data nobody ever validated) survives untouched in the stored blob.
 */
export function DocumentIdentityForm({ orgId, documentIdentity, etag, onSaved }: {
  orgId: string;
  documentIdentity: Record<string, unknown>;
  etag?: string;
  onSaved: () => void;
}) {
  const locale = useLocale() as Locale;
  const t = useTranslations("organizations");
  const { can } = usePermissions();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["schema", "organization.document_identity"],
    queryFn: () => getSchema("organization.document_identity"),
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
      initial={documentIdentity ?? {}}
      etag={etag}
      readOnly={!can("organization.update")}
      onSubmit={(payload, tag) => updateOrg(orgId, { document_identity: payload }, tag)}
      onSuccess={onSaved}
      onConflict={onSaved}
      submitLabel={t("save")}
    />
  );
}
