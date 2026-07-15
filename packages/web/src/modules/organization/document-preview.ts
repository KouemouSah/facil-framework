/**
 * Pure model for the document-identity live A4/A5 preview (SP1 debt D1).
 *
 * The preview is composed from THREE inputs — the live form `values` (the
 * fields the current surface lets the user edit: `organization.document_identity`
 * on the org's own page, or the narrower `org_unit.document_identity` /
 * `site.document_identity` OVERRIDE set on a unit/site tab), the RESOLVED
 * issuer identity (`GET .../issuer-identity`, walks site -> org_unit ->
 * organization, first non-empty wins), and the paper FORMAT.
 *
 * A field the current surface does not let the user edit (e.g. `tax_id` on
 * every surface, or `legal_name` on a site tab that hasn't typed an override
 * yet) is simply absent/blank in `values` — it always falls back to the
 * resolved value. This is what makes an EMPTY override read as "inherit",
 * never as "blank on purpose": the preview and the resolved-identity block
 * agree by construction, there is no second code path that could diverge.
 *
 * `format` only ever changes `PreviewModel.format` (and therefore the sheet's
 * CSS aspect-ratio at render time) — never the resolved content. That
 * invariant is the visual proof of the architecture decision behind the whole
 * document engine (CSS flow, not a positional canvas): reformatting reflows
 * the same content, it never repositions hand-placed boxes.
 */

/** The ten keys `resolve_issuer_identity` (backend) always returns. */
export type IssuerKey =
  | "legal_name" | "tax_id" | "registration_number" | "logo_url"
  | "short_code" | "seal_url" | "header_note" | "footer_note"
  | "legal_mentions" | "contact_line";

export type IssuerOrigin = "site" | "org_unit" | "organization" | null;

/** Shape of `GET .../issuer-identity` — `{"key": {"value": ..., "from": ...}}`. */
export type ResolvedIssuerIdentity = Partial<Record<IssuerKey, { value: string | null; from: IssuerOrigin }>>;

export type PaperSize = "a4" | "a5";
export type PaperOrientation = "portrait" | "landscape";
export type PreviewFormat = `${PaperSize}-${PaperOrientation}`;

export const PREVIEW_FORMATS: PreviewFormat[] = [
  "a4-portrait", "a4-landscape", "a5-portrait", "a5-landscape",
];

export interface PreviewModel {
  legalName: string;
  taxId: string;
  registrationNumber: string;
  logoUrl: string;
  shortCode: string;
  sealUrl: string;
  headerNote: string;
  footerNote: string;
  legalMentions: string;
  contactLine: string;
  format: PreviewFormat;
}

type ModelKey = Exclude<keyof PreviewModel, "format">;

const FIELD_MAP: Record<ModelKey, IssuerKey> = {
  legalName: "legal_name",
  taxId: "tax_id",
  registrationNumber: "registration_number",
  logoUrl: "logo_url",
  shortCode: "short_code",
  sealUrl: "seal_url",
  headerNote: "header_note",
  footerNote: "footer_note",
  legalMentions: "legal_mentions",
  contactLine: "contact_line",
};

/** Live form value wins when non-empty (the user is actively editing/overriding
 *  that key); otherwise fall back to the resolved (inherited) value. A field
 *  absent from `values` altogether (not part of this surface's editable set)
 *  behaves exactly like an empty override — same fallback. */
function resolveField(
  key: IssuerKey, values: Record<string, string>, resolved: ResolvedIssuerIdentity | undefined,
): string {
  const live = values[key];
  if (live) return live;
  return resolved?.[key]?.value ?? "";
}

export function buildDocumentPreviewModel(
  values: Record<string, string>,
  resolved: ResolvedIssuerIdentity | undefined,
  format: PreviewFormat,
): PreviewModel {
  const model = { format } as PreviewModel;
  for (const modelKey of Object.keys(FIELD_MAP) as ModelKey[]) {
    model[modelKey] = resolveField(FIELD_MAP[modelKey], values, resolved);
  }
  return model;
}

/** CSS `aspect-ratio` value (width/height, millimetres) for the sheet — the
 *  ISO 216 dimensions, swapped for landscape. Driving the sheet's shape from
 *  this (not a hardcoded per-format class) is what makes the ghost body clip
 *  to more or fewer lines on format change (see `document-preview-sheet.tsx`
 *  for the exact mechanism) instead of the sheet being repositioned by hand. */
export function previewAspectRatio(format: PreviewFormat): string {
  const [size, orientation] = format.split("-") as [PaperSize, PaperOrientation];
  const [w, h] = size === "a4" ? [210, 297] : [148, 210];
  return orientation === "portrait" ? `${w} / ${h}` : `${h} / ${w}`;
}
