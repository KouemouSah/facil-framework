/** Client for GET /api/v1/schema/{target} (Task 6). Goes through the same BFF
 *  helper as every other admin call (see packages/web/src/lib/api.ts and
 *  modules/providers/api.ts) — no bespoke fetch wrapper. */

import { apiFetch } from "@/lib/api";
import type { FieldSpec } from "./types";

export interface SchemaResponse {
  target: string;
  fields: FieldSpec[];
  etag: string;
}

export function getSchema(target: string, organizationId?: string): Promise<SchemaResponse> {
  const qs = organizationId ? `?organization_id=${encodeURIComponent(organizationId)}` : "";
  return apiFetch<SchemaResponse>(`/api/v1/schema/${encodeURIComponent(target)}${qs}`);
}
