"use client";

import { usePermissions } from "@/lib/use-permissions";
import { SchemaBlobForm } from "./schema-blob-form";

/**
 * `document_identity` used to be a raw JSON textarea (fields.ts:34, removed by
 * Task 8). It is now a generated form driven by the `organization.document_identity`
 * product schema (Task 8, backend `app/core/schema/product_schemas.py`) — the
 * letterhead/footer/seal identity the Document Designer (SP2) prints on every
 * report for this entity. `SchemaBlobForm` carries the actual rendering (shared
 * with `organization.settings`, Task 9) — this is a thin, named wrapper.
 */
export function DocumentIdentityForm({ orgId, documentIdentity, etag, onSaved }: {
  orgId: string;
  documentIdentity: Record<string, unknown>;
  etag?: string;
  onSaved: () => void;
}) {
  const { can } = usePermissions();
  return (
    <SchemaBlobForm
      orgId={orgId}
      schemaTarget="organization.document_identity"
      payloadKey="document_identity"
      blob={documentIdentity}
      etag={etag}
      onSaved={onSaved}
      canWrite={can("organization.update")}
    />
  );
}
