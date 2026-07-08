"use client";

import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { OrgCombobox } from "@/components/ui/org-combobox";

/**
 * Cascading RBAC scope picker — Organization → Org Unit → Site — matching the
 * AccountRole scope tuple the backend already enforces (AssignIn / BulkAssignIn).
 * NULL-widening semantics are surfaced in the option labels:
 *   no org  = Global (all orgs)
 *   org, no unit = whole organization
 *   unit, no site = whole unit (subtree)
 *   site = that site only
 * Picking a wider level clears the narrower ones (org change clears unit+site;
 * unit change clears site) so an inconsistent tuple can't be submitted.
 */
export interface Scope {
  organization_id: string;
  org_unit_id: string;
  site_id: string;
}

export const EMPTY_SCOPE: Scope = { organization_id: "", org_unit_id: "", site_id: "" };

interface NamedRow { id: string; name: string; code: string }

export function ScopePicker({ value, onChange }: {
  value: Scope;
  onChange: (s: Scope) => void;
}) {
  const t = useTranslations("scope");
  const { organization_id, org_unit_id, site_id } = value;

  // Units of the chosen org (offset list, capped at 200 — units per org are
  // bounded; the API enforces the cap, not a silent client truncation).
  const { data: units = [] } = useQuery<NamedRow[]>({
    queryKey: ["scope-units", organization_id],
    enabled: !!organization_id,
    queryFn: () => apiFetch(`/api/v1/modules/organization/${organization_id}/units?limit=200`),
  });

  // Sites of the chosen org, narrowed by unit when one is picked (keyset list;
  // `capped` is surfaced so a >200 result is never silently truncated).
  const { data: sitesResp } = useQuery<{ items: NamedRow[]; capped: boolean }>({
    queryKey: ["scope-sites", organization_id, org_unit_id],
    enabled: !!organization_id,
    queryFn: () => apiFetch(
      `/api/v1/modules/location/sites?organization_id=${organization_id}` +
      (org_unit_id ? `&org_unit_id=${org_unit_id}` : "") + `&limit=200`),
  });
  const sites = sitesResp?.items ?? [];

  return (
    <div className="space-y-2">
      <div className="space-y-1">
        <Label className="text-xs">{t("organization")}</Label>
        <OrgCombobox value={organization_id} noneLabel={t("global")}
          onChange={(id) => onChange({ organization_id: id, org_unit_id: "", site_id: "" })} />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <Label htmlFor="scope-unit" className="text-xs">{t("unit")}</Label>
          <Select id="scope-unit" value={org_unit_id} disabled={!organization_id}
            onChange={(e) => onChange({ ...value, org_unit_id: e.target.value, site_id: "" })}>
            <option value="">{t("whole_org")}</option>
            {units.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="scope-site" className="text-xs">{t("site")}</Label>
          <Select id="scope-site" value={site_id} disabled={!organization_id}
            onChange={(e) => onChange({ ...value, site_id: e.target.value })}>
            <option value="">{org_unit_id ? t("whole_unit") : t("all_sites")}</option>
            {sites.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
        </div>
      </div>
      {sitesResp?.capped && (
        <p className="text-xs text-muted-foreground">{t("capped")}</p>
      )}
    </div>
  );
}
