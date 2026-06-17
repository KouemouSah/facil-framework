"use client";

import { useQuery } from "@tanstack/react-query";
import { Search, ShieldCheck, ShieldOff } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { DataGrid, type DataGridColumn } from "@/components/ui/data-grid";
import { useServerTable, type ServerPage } from "@/lib/use-server-table";

interface Status {
  scim: { enabled: boolean; provider: string };
  federation: { linked_identities: number; providers: string[] };
}
interface Identity {
  id: string;
  provider: string;
  subject: string;
  email?: string | null;
  display_name?: string | null;
  status: string;
  linked_at?: string | null;
}

const DEFAULT_PAGE = 20;

export default function FederationPage() {
  const { data: status } = useQuery<Status>({
    queryKey: ["fed-status"],
    queryFn: () => apiFetch<Status>(`/api/v1/admin/federation/status`),
  });

  const table = useServerTable<Identity>({
    resource: "fed-identities",
    defaultSort: "-created_at",
    defaultPageSize: DEFAULT_PAGE,
    fetchPage: ({ cursor, limit, sort, q }) =>
      apiFetch<ServerPage<Identity>>(
        `/api/v1/admin/federation/identities?q=${encodeURIComponent(q)}&sort=${sort}` +
        `&limit=${limit}` + (cursor ? `&cursor=${encodeURIComponent(cursor)}` : "")),
  });
  const rows = table.rows;

  const columns: DataGridColumn<Identity>[] = [
    { key: "provider", header: "Provider", sortable: true, className: "font-medium" },
    { key: "subject", header: "External subject", sortable: true, className: "font-mono text-xs" },
    { key: "account", header: "Local account", cell: (r) => r.display_name || r.email || r.id.slice(0, 8) },
    { key: "status", header: "Status", className: "text-muted-foreground" },
  ];

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Toolbar — fixed */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Federation &amp; SCIM</h1>
          <p className="text-sm text-muted-foreground">External identity providers and provisioned accounts (read-only).</p>
        </div>
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="h-9 w-56 pl-8" placeholder="Search subject / provider / email"
            value={table.q} onChange={(e) => table.setQ(e.target.value)} />
        </div>
      </div>

      {/* Status cards — overview, no scroll */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-lg border p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            {status?.scim.enabled ? <ShieldCheck className="size-4 text-emerald-600" /> : <ShieldOff className="size-4" />}
            SCIM provisioning
          </div>
          <p className="mt-1 text-lg font-semibold">{status ? (status.scim.enabled ? "Enabled" : "Disabled") : "—"}</p>
        </div>
        <div className="rounded-lg border p-4">
          <div className="text-sm text-muted-foreground">Federation provider</div>
          <p className="mt-1 text-lg font-semibold">{status?.scim.provider ?? "—"}</p>
        </div>
        <div className="rounded-lg border p-4">
          <div className="text-sm text-muted-foreground">Linked identities</div>
          <p className="mt-1 text-lg font-semibold">{status?.federation.linked_identities ?? "—"}</p>
        </div>
      </div>

      <DataGrid<Identity>
        mode="cursor"
        columns={columns}
        rows={rows}
        rowKey={(r) => r.id}
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
        emptyLabel="No federated identities."
      />
    </div>
  );
}
