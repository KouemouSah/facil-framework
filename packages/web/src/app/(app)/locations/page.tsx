"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { codeField, requiredText } from "@/lib/form-schemas";
import { ExportMenu } from "@/components/export-menu";
import { Button } from "@/components/ui/button";
import { DataGrid, type DataGridColumn } from "@/components/ui/data-grid";
import { DetailPanel } from "@/components/ui/detail-panel";
import { RecordForm, type FieldDef } from "@/components/ui/record-form";
import { OrgCombobox } from "@/components/ui/org-combobox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useFirstOrg } from "@/lib/use-organizations";
import { useServerTable, type ServerPage } from "@/lib/use-server-table";

interface Site {
  id: string;
  code: string;
  name: string;
  site_type: string;
  city?: string | null;
  country_code?: string | null;
  is_primary: boolean;
  is_active: boolean;
}
const DEFAULT_PAGE = 20;
const SITE_BASE = "/api/v1/modules/location/sites";

const SITE_TYPES = [
  { value: "branch", label: "Branch" },
  { value: "headquarters", label: "Headquarters" },
  { value: "warehouse", label: "Warehouse" },
  { value: "office", label: "Office" },
  { value: "point_of_sale", label: "Point of sale" },
];

// Canonical site fields (ERP-grade F.3c): geo moves to a reusable Address
// (address_id via AddressField); the old flat address/city/country inputs are
// gone. org_unit_id / parent_site_id stay API-only until their pickers land.
const SITE_FIELDS: FieldDef[] = [
  { name: "code", label: "Code", required: true, immutable: true, zod: codeField,
    hint: "Immutable identifier." },
  { name: "name", label: "Name", required: true, zod: requiredText("Name") },
  { name: "site_type", label: "Type", type: "select", required: true, selectOptions: SITE_TYPES },
  { name: "is_primary", label: "Primary site", type: "checkbox" },
  { name: "phone", label: "Phone" },
  { name: "email", label: "Email" },
  { name: "timezone", label: "Timezone", placeholder: "UTC" },
  { name: "address_id", label: "Address", type: "address" },
  { name: "notes", label: "Notes", type: "textarea", colSpan: 2 },
  { name: "operating_hours", label: "Operating hours (JSON)", type: "json",
    hint: 'e.g. {"mon": ["09:00-17:00"], "sat": []}' },
  { name: "metadata", label: "Metadata (JSON)", type: "json", hint: "Free-form site metadata." },
];

export default function LocationsPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const sel = searchParams.get("sel") ?? "";
  const [orgId, setOrgId] = useState("");
  const [open, setOpen] = useState(false);

  const select = (id: string) => router.replace(`${pathname}?sel=${id}`, { scroll: false });
  const clearSel = () => router.replace(pathname, { scroll: false });

  // Sites are org-scoped at the API, so a chosen org gates listing/creating.
  const firstOrgId = useFirstOrg();
  useEffect(() => {
    if (!orgId && firstOrgId) setOrgId(firstOrgId);
  }, [firstOrgId, orgId]);

  const table = useServerTable<Site>({
    resource: "sites",
    defaultSort: "code",
    defaultPageSize: DEFAULT_PAGE,
    enabled: !!orgId,
    fetchPage: ({ cursor, limit, sort, filters }) =>
      apiFetch<ServerPage<Site>>(
        `${SITE_BASE}?organization_id=${filters.organization_id ?? ""}` +
        `&sort=${sort}&limit=${limit}` + (cursor ? `&cursor=${encodeURIComponent(cursor)}` : "")),
  });
  const setTableFilter = table.onFilterChange;
  useEffect(() => { setTableFilter("organization_id", orgId); }, [orgId, setTableFilter]);
  const rows = table.rows;

  const del = useMutation({
    mutationFn: (id: string) => apiFetch(`${SITE_BASE}/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sites"] }),
  });

  const columns: DataGridColumn<Site>[] = [
    { key: "code", header: "Code", sortable: true, className: "font-mono text-xs" },
    {
      key: "name", header: "Name", sortable: true,
      cell: (s) => (
        <>{s.name}{s.is_primary && <span className="ml-2 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">primary</span>}</>
      ),
    },
    { key: "site_type", header: "Type", sortable: true, className: "text-muted-foreground" },
    {
      key: "city", header: "City", sortable: true, className: "text-muted-foreground",
      cell: (s) => [s.city, s.country_code].filter(Boolean).join(", "),
    },
    {
      key: "actions", header: "Actions", align: "right", headClassName: "w-16", stopClick: true,
      cell: (s) => (
        <Button variant="ghost" size="icon" title="Delete"
          onClick={() => del.mutate(s.id)} disabled={del.isPending}>
          <Trash2 className="size-4" />
        </Button>
      ),
    },
  ];

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Toolbar — fixed (does not scroll with the data) */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Sites</h1>
          <p className="text-sm text-muted-foreground">Physical sites and branches per organization.</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-64">
            <OrgCombobox value={orgId} allowNone={false}
              placeholder="Search organization…"
              onChange={(id) => setOrgId(id)} />
          </div>
          <ExportMenu filename="sites" disabled={!orgId}
            path={`${SITE_BASE}/export?organization_id=${orgId}&sort=${table.sort}`} />
          <NewSiteDialog open={open} setOpen={setOpen} orgId={orgId} />
        </div>
      </div>

      {/* Master-detail: list left, edit form right (deep-linkable ?sel=) */}
      <div className={`grid min-h-0 flex-1 gap-4 ${sel ? "lg:grid-cols-[1fr_minmax(420px,560px)]" : ""}`}>
        <DataGrid<Site>
          mode="cursor"
          columns={columns}
          rows={rows}
          rowKey={(s) => s.id}
          pageSize={table.pageSize}
          onPageSizeChange={table.onPageSizeChange}
          sort={table.sort}
          onSortChange={table.onSortChange}
          filters={table.filters}
          onFilterChange={table.onFilterChange}
          hasPrev={table.hasPrev}
          hasNext={table.hasNext}
          onPrev={table.onPrev}
          onNext={table.onNext}
          count={table.count}
          capped={table.capped}
          isLoading={!!orgId && table.isLoading}
          error={table.error}
          onRowClick={(s) => select(s.id)}
          selectedId={sel}
          emptyLabel={orgId ? "No sites." : "Select an organization."}
        />
        {sel && <SiteDetail siteId={sel} onClose={clearSel} />}
      </div>
    </div>
  );
}

function SiteDetail({ siteId, onClose }: { siteId: string; onClose: () => void }) {
  const qc = useQueryClient();
  const { data } = useQuery<Record<string, unknown>>({
    queryKey: ["site", siteId],
    queryFn: () => apiFetch(`${SITE_BASE}/${siteId}`),
  });

  return (
    <DetailPanel
      title={(data?.name as string) || "Site"}
      subtitle={data?.code ? `code ${data.code}` : undefined}
      onClose={onClose}
    >
      {!data && <p className="text-sm text-muted-foreground">Loading…</p>}
      {data && (
        <RecordForm
          key={String(data.etag ?? siteId)}
          fields={SITE_FIELDS}
          mode="edit"
          layout="rich"
          initial={data}
          etag={data.etag ? String(data.etag) : undefined}
          onSubmit={(payload, etag) =>
            apiFetch(`${SITE_BASE}/${siteId}`, {
              method: "PUT",
              headers: etag ? { "If-Match": etag } : undefined,
              body: JSON.stringify(payload),
            })}
          onSuccess={() => {
            qc.invalidateQueries({ queryKey: ["site", siteId] });
            qc.invalidateQueries({ queryKey: ["sites"] });
          }}
          onConflict={() => qc.invalidateQueries({ queryKey: ["site", siteId] })}
        />
      )}
    </DetailPanel>
  );
}

function NewSiteDialog({ open, setOpen, orgId }: { open: boolean; setOpen: (b: boolean) => void; orgId: string }) {
  const qc = useQueryClient();
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" disabled={!orgId}><Plus className="size-4" /> New</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>New site</DialogTitle></DialogHeader>
        <div className="max-h-[70vh] overflow-auto pr-1">
          <RecordForm
            fields={SITE_FIELDS}
            mode="create"
            layout="rich"
            enableSaveNew
            submitLabel="Create"
            initial={{ site_type: "branch" }}
            onSubmit={(payload) =>
              apiFetch(SITE_BASE, {
                method: "POST",
                body: JSON.stringify({ ...payload, organization_id: orgId }),
              })}
            onSuccess={({ again }) => {
              qc.invalidateQueries({ queryKey: ["sites"] });
              if (!again) setOpen(false);
            }}
            onCancel={() => setOpen(false)}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
