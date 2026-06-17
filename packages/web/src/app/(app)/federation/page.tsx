"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, ShieldCheck, ShieldOff } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { DataGrid, type DataGridColumn } from "@/components/ui/data-grid";

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
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("-created_at");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE);

  const { data: status } = useQuery<Status>({
    queryKey: ["fed-status"],
    queryFn: () => apiFetch<Status>(`/api/v1/admin/federation/status`),
  });

  const { data, isLoading, error } = useQuery<{ items: Identity[]; total: number }>({
    queryKey: ["fed-identities", q, sort, page, pageSize],
    queryFn: () =>
      apiFetch<{ items: Identity[]; total: number }>(
        `/api/v1/admin/federation/identities?q=${encodeURIComponent(q)}&sort=${sort}` +
        `&limit=${pageSize}&offset=${page * pageSize}`),
  });
  const rows = data?.items ?? [];
  const total = data?.total ?? 0;

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
            value={q} onChange={(e) => setQ(e.target.value)} />
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
        columns={columns}
        rows={rows}
        rowKey={(r) => r.id}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageSizeChange={(n) => { setPageSize(n); setPage(0); }}
        onPageChange={setPage}
        sort={sort}
        onSortChange={(s) => { setSort(s); setPage(0); }}
        filters={{}}
        onFilterChange={() => undefined}
        isLoading={isLoading}
        error={!!error}
        emptyLabel="No federated identities."
      />
    </div>
  );
}
