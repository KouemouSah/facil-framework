"use client";

import { useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Search } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { codeField, requiredText } from "@/lib/form-schemas";
import { ExportMenu } from "@/components/export-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DataGrid, type DataGridColumn } from "@/components/ui/data-grid";
import { DetailPanel } from "@/components/ui/detail-panel";
import { RecordForm, type FieldDef } from "@/components/ui/record-form";
import { useServerTable, type ServerPage } from "@/lib/use-server-table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

interface Org { id: string; code: string; legal_name: string; display_name?: string }
const DEFAULT_PAGE = 20;
const ORG_BASE = "/api/v1/modules/organization";

// Canonical Company fields (ERP-grade F.3): the legal identity (tax id /
// registration / postal address) now lives on the linked Party + Address — the
// org keeps its code/branding/scope plus FK links to that master data. The old
// flat free-text geo/tax/currency inputs are intentionally gone.
const ORG_FIELDS: FieldDef[] = [
  { name: "code", label: "Code", required: true, immutable: true, zod: codeField,
    hint: "Immutable identifier." },
  { name: "legal_name", label: "Legal name", required: true, zod: requiredText("Legal name") },
  { name: "display_name", label: "Display name" },
  { name: "party_id", label: "Legal identity (directory)", type: "party",
    hint: "Party holding tax id / registration / contacts." },
  { name: "parent_id", label: "Consolidation parent", type: "org",
    hint: "Owning company for multi-company groups." },
  { name: "currency_id", label: "Currency", type: "ref", refResource: "currencies" },
  { name: "email", label: "Email" },
  { name: "phone", label: "Phone" },
  { name: "website", label: "Website" },
  { name: "logo_url", label: "Logo URL", colSpan: 2 },
  { name: "default_locale", label: "Default locale", placeholder: "en" },
  { name: "timezone", label: "Timezone", placeholder: "UTC" },
  { name: "hq_address_id", label: "Head office address", type: "address" },
  { name: "document_identity", label: "Document identity (JSON)", type: "json",
    hint: "Identifiers shown on generated documents (registry, VAT…)." },
  { name: "settings", label: "Settings (JSON)", type: "json",
    hint: "Free-form organization settings." },
];

export default function OrganizationsPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const sel = searchParams.get("sel") ?? "";
  const [open, setOpen] = useState(false);

  const select = (id: string) => router.replace(`${pathname}?sel=${id}`, { scroll: false });
  const clearSel = () => router.replace(pathname, { scroll: false });

  const table = useServerTable<Org>({
    resource: "orgs",
    defaultSort: "code",
    defaultPageSize: DEFAULT_PAGE,
    fetchPage: ({ cursor, limit, sort, q }) =>
      apiFetch<ServerPage<Org>>(
        `${ORG_BASE}/?q=${encodeURIComponent(q)}&sort=${sort}` +
        `&limit=${limit}` + (cursor ? `&cursor=${encodeURIComponent(cursor)}` : "")),
  });
  const rows = table.rows;

  const del = useMutation({
    mutationFn: (id: string) => apiFetch(`${ORG_BASE}/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orgs"] }),
  });

  const columns: DataGridColumn<Org>[] = [
    { key: "code", header: "Code", sortable: true, className: "font-mono text-xs" },
    {
      key: "legal_name", header: "Legal name", sortable: true,
      cell: (o) => o.display_name || o.legal_name,
    },
    {
      key: "actions", header: "Actions", align: "right", headClassName: "w-16", stopClick: true,
      cell: (o) => (
        <Button variant="ghost" size="icon" title="Delete"
          onClick={() => del.mutate(o.id)} disabled={del.isPending}>
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
          <h1 className="text-xl font-semibold tracking-tight">Organizations</h1>
          <p className="text-sm text-muted-foreground">Tenants you can access.</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="h-9 w-56 pl-8" placeholder="Search code / name"
              value={table.q} onChange={(e) => table.setQ(e.target.value)} />
          </div>
          <ExportMenu filename="organizations"
            path={`${ORG_BASE}/export?q=${encodeURIComponent(table.q)}&sort=${table.sort}`} />
          <NewOrgDialog open={open} setOpen={setOpen} />
        </div>
      </div>

      {/* Master-detail: list left, edit form right (deep-linkable ?sel=) */}
      <div className={`grid min-h-0 flex-1 gap-4 ${sel ? "lg:grid-cols-[1fr_minmax(420px,560px)]" : ""}`}>
        <DataGrid<Org>
          mode="cursor"
          columns={columns}
          rows={rows}
          rowKey={(o) => o.id}
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
          isLoading={table.isLoading}
          error={table.error}
          onRowClick={(o) => select(o.id)}
          selectedId={sel}
          emptyLabel="No organizations."
        />
        {sel && <OrgDetail orgId={sel} onClose={clearSel} />}
      </div>
    </div>
  );
}

function OrgDetail({ orgId, onClose }: { orgId: string; onClose: () => void }) {
  const qc = useQueryClient();
  const { data } = useQuery<Record<string, unknown>>({
    queryKey: ["org", orgId],
    queryFn: () => apiFetch(`${ORG_BASE}/${orgId}`),
  });

  return (
    <DetailPanel
      title={(data?.display_name as string) || (data?.legal_name as string) || "Organization"}
      subtitle={data?.code ? `code ${data.code}` : undefined}
      onClose={onClose}
    >
      {!data && <p className="text-sm text-muted-foreground">Loading…</p>}
      {data && (
        <RecordForm
          // Remount on a fresh load (post-save / post-conflict) to reseed initial + etag.
          key={String(data.etag ?? orgId)}
          fields={ORG_FIELDS}
          mode="edit"
          layout="rich"
          initial={data}
          etag={data.etag ? String(data.etag) : undefined}
          onSubmit={(payload, etag) =>
            apiFetch(`${ORG_BASE}/${orgId}`, {
              method: "PUT",
              headers: etag ? { "If-Match": etag } : undefined,
              body: JSON.stringify(payload),
            })}
          onSuccess={() => {
            qc.invalidateQueries({ queryKey: ["org", orgId] });
            qc.invalidateQueries({ queryKey: ["orgs"] });
          }}
          onConflict={() => qc.invalidateQueries({ queryKey: ["org", orgId] })}
        />
      )}
    </DetailPanel>
  );
}

function NewOrgDialog({ open, setOpen }: { open: boolean; setOpen: (b: boolean) => void }) {
  const qc = useQueryClient();
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm"><Plus className="size-4" /> New</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>New organization</DialogTitle></DialogHeader>
        <div className="max-h-[70vh] overflow-auto pr-1">
          <RecordForm
            fields={ORG_FIELDS}
            mode="create"
            layout="rich"
            enableSaveNew
            submitLabel="Create"
            onSubmit={(payload) =>
              apiFetch(`${ORG_BASE}/`, { method: "POST", body: JSON.stringify(payload) })}
            onSuccess={({ again }) => {
              qc.invalidateQueries({ queryKey: ["orgs"] });
              if (!again) setOpen(false);
            }}
            onCancel={() => setOpen(false)}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
