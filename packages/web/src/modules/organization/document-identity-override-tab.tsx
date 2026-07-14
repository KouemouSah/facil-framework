"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { RecordForm } from "@/components/ui/record-form";
import { useSchemaFields } from "@/lib/schema/use-schema-fields";
import { DocumentPreviewSheet } from "./document-preview-sheet";
import type { ResolvedIssuerIdentity } from "./document-preview";

/** `ResolvedIssuerIdentity` (`{key: {value, from}}`) flattened to the plain
 *  `{key: value}` map `useSchemaFields`'s `inheritedFrom` expects — the hook
 *  doesn't need to know about `IssuerKey`/`IssuerOrigin`, only that a value
 *  may be present per field key. */
function flattenIssuerValues(resolved: ResolvedIssuerIdentity | undefined): Record<string, string | undefined> {
  const out: Record<string, string | undefined> = {};
  for (const [k, v] of Object.entries(resolved ?? {})) out[k] = v?.value ?? undefined;
  return out;
}

/** `product_schemas.DOCUMENT_IDENTITY_OVERRIDE` keys — mirrors the seed used
 *  to prime the live preview before the user has typed anything (see
 *  `document-identity-page.tsx`'s twin `initialScalarValues`, same reasoning). */
const OVERRIDE_KEYS = ["legal_name", "short_code", "logo_url", "contact_line", "footer_note"];

function initialScalarValues(blob: Record<string, unknown> | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  for (const k of OVERRIDE_KEYS) {
    const v = blob?.[k];
    out[k] = v === undefined || v === null ? "" : String(v);
  }
  return out;
}

/**
 * Shared "Identité documentaire" override tab for `Site` and `OrgUnit`
 * (SP1 debt D1) — the narrow, OPTIONAL `org_unit.document_identity` /
 * `site.document_identity` schema (`DOCUMENT_IDENTITY_OVERRIDE`). Every
 * field's placeholder is the value it would resolve to if left blank
 * (`GET .../issuer-identity`), so a blank override reads as "inherit", never
 * as "not set" — the exact ambiguity the SP1 spec calls out as the classic
 * bug of this kind of system. Drives the same live A4/A5 preview as the
 * organization's own document-identity page (`DocumentIdentityPage`).
 */
export function DocumentIdentityOverrideTab({
  schemaTarget, organizationId, blob, etag, canWrite, onSubmit, onSaved,
  issuerIdentityQueryKey, fetchIssuerIdentity,
}: {
  schemaTarget: "org_unit.document_identity" | "site.document_identity";
  /** The OWNING organization — scopes the schema lookup (product schema, so
   *  scope is a no-op today, but kept consistent with every other schema call). */
  organizationId: string;
  blob: Record<string, unknown>;
  etag?: string;
  canWrite: boolean;
  onSubmit: (payload: Record<string, unknown>, etag?: string) => Promise<unknown>;
  onSaved: () => void;
  issuerIdentityQueryKey: unknown[];
  fetchIssuerIdentity: () => Promise<ResolvedIssuerIdentity>;
}) {
  const t = useTranslations("organizations.documentIdentity");
  const [liveValues, setLiveValues] = useState<Record<string, string>>(() => initialScalarValues(blob));

  const issuer = useQuery({ queryKey: issuerIdentityQueryKey, queryFn: fetchIssuerIdentity });
  // Deferred until `issuer` resolves (see `inheritedFrom` below): while the
  // issuer query is in flight, `useSchemaFields` gets `undefined` and returns
  // plain fields with no placeholder, which is exactly why we don't render
  // the form yet either (`fieldsLoading || issuer.isLoading` below) — a blank
  // field must never momentarily read as "empty on purpose" before we
  // actually know what it inherits.
  const inheritedFrom = issuer.data ? flattenIssuerValues(issuer.data) : undefined;
  const { fields, isLoading: fieldsLoading, isError: fieldsError } =
    useSchemaFields(schemaTarget, organizationId, { inheritedFrom });

  if (fieldsError || issuer.isError) return <p className="text-sm text-destructive">{t("load_error")}</p>;
  if (fieldsLoading || issuer.isLoading) return <p className="text-sm text-muted-foreground">{t("loading")}</p>;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-start">
      <div className="min-w-0 space-y-2">
        <p className="text-xs text-muted-foreground">{t("override_description")}</p>
        <RecordForm
          mode="edit"
          layout="rich"
          fields={fields}
          initial={blob ?? {}}
          etag={etag}
          readOnly={!canWrite}
          onValuesChange={setLiveValues}
          onSubmit={onSubmit}
          onSuccess={onSaved}
          onConflict={onSaved}
          submitLabel={t("save")}
        />
      </div>
      {/* Sticky on desktop only — mobile stacks the preview BELOW the form. */}
      <div className="lg:sticky lg:top-0">
        <DocumentPreviewSheet values={liveValues} resolved={issuer.data} />
      </div>
    </div>
  );
}
