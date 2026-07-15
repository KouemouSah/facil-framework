"use client";

import { usePermissions } from "@/lib/use-permissions";
import { SchemaBlobForm } from "./schema-blob-form";

/**
 * `settings` used to be a raw JSON field on the main organization form
 * (fields.ts, `type: "json"`, removed by Task 9). It is now a generated form
 * driven by the `organization.settings` product schema (Task 9, backend
 * `app/core/schema/product_schemas.py`) — the small set of per-organization
 * settings the product actually consumes today: default document locale,
 * document numbering prefix (reserved for SP2), fiscal year start month.
 * `SchemaBlobForm` carries the actual rendering (shared with
 * `organization.document_identity`, Task 8) — this is a thin, named wrapper.
 */
export function OrganizationSettingsForm({ orgId, settings, etag, onSaved }: {
  orgId: string;
  settings: Record<string, unknown>;
  etag?: string;
  onSaved: () => void;
}) {
  const { can } = usePermissions();
  return (
    <SchemaBlobForm
      orgId={orgId}
      schemaTarget="organization.settings"
      payloadKey="settings"
      blob={settings}
      etag={etag}
      onSaved={onSaved}
      canWrite={can("organization.update")}
    />
  );
}
