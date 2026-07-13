/** FieldSpec (server) → FieldDef (RecordForm). Generalises
 *  `configFieldToFieldDef` (providers/fields.ts:14-22), which proved this exact
 *  path end-to-end for providers. */

import type { FieldDef } from "@/components/ui/record-form";
import { rulesToZod } from "./to-zod";
import { tr, type FieldSpec, type Locale } from "./types";

export function fieldSpecToFieldDef(spec: FieldSpec, locale: Locale): FieldDef {
  return {
    name: spec.key,
    label: tr(spec.label, locale),
    type: spec.type,
    widget: spec.widget,
    required: spec.required,
    hint: tr(spec.hint, locale) || undefined,
    colSpan: (spec.col_span === 2 ? 2 : 1) as 1 | 2,
    rules: spec.rules,
    zod: rulesToZod(spec),
    relationResource: spec.relation_resource || undefined,
    refFilter: Object.keys(spec.relation_filter || {}).length ? spec.relation_filter : undefined,
    selectOptions: spec.options?.length
      ? spec.options.map((o) => ({ value: o.value, label: tr(o.label, locale) }))
      : undefined,
  };
}
