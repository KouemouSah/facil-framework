/**
 * `components/shared` — composite, reusable building blocks (not primitives).
 *
 * Foundation convention (incremental migration): new module pages import composites
 * from `@/components/shared`. The implementations still physically live where they
 * were built; this barrel is the stable public surface so later moves don't churn
 * every call site. Import direction: app → modules → components/shared → components/ui → core.
 */

export { DataGrid } from "@/components/ui/data-grid";
export { DetailPanel } from "@/components/ui/detail-panel";
export { RecordSurface } from "@/components/shared/record-surface";
export { RecordForm } from "@/components/ui/record-form";
export type { FieldDef, FieldType } from "@/components/ui/record-form";
export { JsonField } from "@/components/ui/json-field";
export { RefSelect } from "@/components/ui/ref-select";
export { OrgCombobox } from "@/components/ui/org-combobox";
export { PartyCombobox } from "@/components/ui/party-combobox";
export { AddressField } from "@/components/ui/address-field";
export { ScopePicker } from "@/components/ui/scope-picker";
export { ExportMenu } from "@/components/export-menu";
export { SavedViews } from "@/components/saved-views";
export { AuthCard } from "@/components/shared/auth-card";
