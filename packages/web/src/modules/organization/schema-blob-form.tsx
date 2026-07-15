"use client";

import { useTranslations } from "next-intl";
import { RecordForm } from "@/components/ui/record-form";
import { useSchemaFields } from "@/lib/schema/use-schema-fields";
import { updateOrg } from "./api";

/**
 * Generic schema-generated form for an org-scoped JSON blob column
 * (`document_identity`, `settings`, …) — factored out of what was originally
 * `DocumentIdentityForm` (Task 8) once `settings` (Task 9) needed the exact
 * same shape: one `RecordForm` driven by `GET /api/v1/schema/{schemaTarget}`
 * (via `useSchemaFields`, shared with `DocumentIdentityPage` and
 * `DocumentIdentityOverrideTab`), submitting `{ [payloadKey]: payload }`
 * through `PUT organization/{id}`.
 *
 * The backend enforces merge-preserve semantics (`merge_blob`): only the
 * declared keys are ever written by this form; a pre-existing undeclared key
 * (historic data nobody ever validated) survives untouched in the stored blob.
 *
 * Field LABELS come from the server (`fieldSpecToFieldDef`) — never
 * duplicated here. Only the surrounding chrome (loading/error/save labels)
 * is localized client-side, under the `organizations` i18n namespace shared
 * by every blob-form tab.
 *
 * Today's only caller (`organization.settings`) has no live preview and no
 * inherited-value concept, so this stays a plain, single-column `RecordForm`
 * always submitting through `updateOrg`. `DocumentIdentityPage` and
 * `DocumentIdentityOverrideTab` need a live A4/A5 preview, a sticky
 * two-column layout, and (for the override tab) inherited-placeholder
 * fields — real per-surface differences a generic blob form has no business
 * knowing about — so they own their `RecordForm` directly instead of routing
 * through here. (SP1 D1 review: this component used to carry `placeholders`/
 * `onSubmit` props built "for" those two screens, which never actually
 * called it; removed as dead code rather than left unused. The part that
 * WAS genuinely common — the schema fetch + `FieldDef` mapping + placeholder-
 * as-inherited overlay — now lives once in `useSchemaFields`.)
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
  const t = useTranslations("organizations");
  const { fields, isLoading, isError } = useSchemaFields(schemaTarget, orgId);

  if (isError) {
    return <p className="text-sm text-destructive">{t("load_error")}</p>;
  }
  if (isLoading) {
    return <p className="text-sm text-muted-foreground">{t("loading")}</p>;
  }

  return (
    <RecordForm
      mode="edit"
      layout="rich"
      fields={fields}
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
