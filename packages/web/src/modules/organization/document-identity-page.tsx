"use client";

import { useState } from "react";
import Image from "next/image";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { RecordForm } from "@/components/ui/record-form";
import { useSchemaFields } from "@/lib/schema/use-schema-fields";
import { isSameOriginAsset } from "@/lib/upload";
import { getOrgIssuerIdentity, updateOrg } from "./api";
import { DocumentPreviewSheet } from "./document-preview-sheet";
import type { ResolvedIssuerIdentity } from "./document-preview";

/** The organization's own `document_identity` scalar keys — mirrors
 *  `product_schemas.DOCUMENT_IDENTITY`. Used only to seed the live preview's
 *  initial values (before the user has typed anything) the same way
 *  `RecordForm` seeds its own internal state from `initial`. */
const DOCUMENT_IDENTITY_KEYS = [
  "short_code", "seal_url", "header_note", "footer_note", "legal_mentions", "contact_line",
];

function initialScalarValues(blob: Record<string, unknown> | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  for (const k of DOCUMENT_IDENTITY_KEYS) {
    const v = blob?.[k];
    out[k] = v === undefined || v === null ? "" : String(v);
  }
  return out;
}

/**
 * Full-width document-identity screen (SP1 debt D1 — replaces the old
 * `DocumentIdentityForm` tab, which re-declared `legal_name`/`tax_id`/
 * `registration_number`/`logo_url` and forced double entry against the
 * Organization row). Two things fixed at once:
 *
 * - The four legal-identity fields are now shown READ-ONLY, sourced from
 *   `GET .../issuer-identity` (`InheritedIdentityBlock` below), with a link
 *   back to the Details tab where they are actually edited. One source of
 *   truth, never re-typed here.
 * - A live, non-contractual A4/A5 preview (`DocumentPreviewSheet`) renders
 *   the resolved identity as the paper actually looks, updating on every
 *   keystroke via `RecordForm`'s `onValuesChange`.
 */
export function DocumentIdentityPage({ orgId, documentIdentity, etag, canWrite, onSaved, onGoToDetails }: {
  orgId: string;
  documentIdentity: Record<string, unknown>;
  etag?: string;
  canWrite: boolean;
  onSaved: () => void;
  onGoToDetails: () => void;
}) {
  const t = useTranslations("organizations.documentIdentity");
  const [liveValues, setLiveValues] = useState<Record<string, string>>(
    () => initialScalarValues(documentIdentity));

  const { fields, isLoading: fieldsLoading, isError: fieldsError } =
    useSchemaFields("organization.document_identity", orgId);
  const issuer = useQuery({
    queryKey: ["issuer-identity", "organization", orgId],
    queryFn: () => getOrgIssuerIdentity(orgId),
  });

  if (fieldsError) return <p className="text-sm text-destructive">{t("load_error")}</p>;
  if (fieldsLoading) return <p className="text-sm text-muted-foreground">{t("loading")}</p>;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-start">
      <div className="min-w-0 space-y-6">
        <p className="text-xs text-muted-foreground">{t("description")}</p>
        <RecordForm
          mode="edit"
          layout="rich"
          fields={fields}
          initial={documentIdentity ?? {}}
          etag={etag}
          readOnly={!canWrite}
          onValuesChange={setLiveValues}
          onSubmit={(payload, tag) => updateOrg(orgId, { document_identity: payload }, tag)}
          onSuccess={onSaved}
          onConflict={onSaved}
          submitLabel={t("save")}
        />
        <InheritedIdentityBlock resolved={issuer.data} loading={issuer.isLoading} error={issuer.isError}
          onGoToDetails={onGoToDetails} />
      </div>
      {/* Sticky on desktop only — mobile stacks the preview BELOW the form
          (responsive-by-default, never a horizontal scroll). */}
      <div className="lg:sticky lg:top-0">
        <DocumentPreviewSheet values={liveValues} resolved={issuer.data} />
      </div>
    </div>
  );
}

const INHERITED_ROWS: { key: "legal_name" | "tax_id" | "registration_number" | "logo_url" }[] = [
  { key: "legal_name" }, { key: "tax_id" }, { key: "registration_number" }, { key: "logo_url" },
];

function InheritedIdentityBlock({ resolved, loading, error, onGoToDetails }: {
  resolved: ResolvedIssuerIdentity | undefined;
  loading: boolean;
  error: boolean;
  onGoToDetails: () => void;
}) {
  const t = useTranslations("organizations.documentIdentity.inherited");
  return (
    <section aria-labelledby="doc-identity-inherited-heading" className="space-y-2 rounded-md border bg-muted/30 p-3">
      <div className="flex items-center justify-between gap-2">
        <h3 id="doc-identity-inherited-heading"
          className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {t("title")}
        </h3>
        <button type="button" onClick={onGoToDetails}
          className="text-xs text-primary underline-offset-2 hover:underline">
          {t("edit_in_details")}
        </button>
      </div>
      <p className="text-xs text-muted-foreground">{t("hint")}</p>
      {loading && <p className="text-xs text-muted-foreground">{t("loading")}</p>}
      {error && <p className="text-xs text-destructive">{t("load_error")}</p>}
      {resolved && (
        <dl className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1.5 text-sm">
          {INHERITED_ROWS.map(({ key }) => {
            const value = resolved[key]?.value;
            return (
              <div key={key} className="contents">
                <dt className="text-muted-foreground">{t(key)}</dt>
                <dd className="min-w-0 truncate">
                  {key === "logo_url" && value ? (
                    <Image src={value} alt="" width={24} height={24}
                      unoptimized={!isSameOriginAsset(value)} className="h-6 w-6 object-contain" />
                  ) : (
                    value || <span className="text-muted-foreground/60">{t("empty")}</span>
                  )}
                </dd>
              </div>
            );
          })}
        </dl>
      )}
    </section>
  );
}
