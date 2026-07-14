"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import type { FieldDef } from "@/components/ui/record-form";
import { getSchema } from "./api";
import { fieldSpecToFieldDef } from "./to-field-def";
import type { Locale } from "./types";

/**
 * Shared "fetch schema by (target, scopeId) -> `FieldDef[]`" pipeline used by
 * every schema-blob form (`organization.settings`, `organization.
 * document_identity`, and the `org_unit`/`site` document-identity override
 * tabs) — the ONE thing all three genuinely have in common (SP1 D1 review
 * finding: `SchemaBlobForm` grew `placeholders`/`onSubmit` props "for" the
 * override screens, but they hand-rolled their own fetch+map instead of
 * calling it, leaving three near-duplicate copies and two dead props). Each
 * caller still owns its OWN `RecordForm` — layout, live-preview wiring
 * (`onValuesChange`), sticky two-column panels, etc. are real per-surface
 * differences (the org's own document-identity page needs a live A4/A5
 * preview and a read-only inherited-identity block; plain settings needs
 * neither), so they stay with the caller rather than being forced through a
 * one-size-fits-all component.
 *
 * `inheritedFrom` (org_unit/site override tabs only) overlays a per-field
 * "value if left blank" hint: a raw `FieldDef.inheritedValue` for `file`
 * fields (FileUpload's own preview channel) or a localized "Hérité : X"
 * `placeholder` for every other control, so a blank override reads as
 * "inherit", never as "empty on purpose". Omit it for surfaces with no
 * inheritance concept (settings) or that show the resolved value some other
 * way (the org's own page, which renders it in a separate read-only block).
 */
export function useSchemaFields(
  schemaTarget: string,
  scopeId: string,
  options?: { inheritedFrom?: Record<string, string | undefined> },
): { fields: FieldDef[]; isLoading: boolean; isError: boolean } {
  const locale = useLocale() as Locale;
  const t = useTranslations("organizations");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["schema", schemaTarget, scopeId],
    queryFn: () => getSchema(schemaTarget, scopeId),
  });

  const inheritedFrom = options?.inheritedFrom;
  const fields: FieldDef[] = (data?.fields ?? []).map((s) => {
    const fd = fieldSpecToFieldDef(s, locale);
    const inherited = inheritedFrom?.[s.key];
    if (!inherited) return fd;
    return s.type === "file"
      ? { ...fd, inheritedValue: inherited }
      : { ...fd, placeholder: t("inherited_placeholder", { value: inherited }) };
  });

  return { fields, isLoading, isError };
}
