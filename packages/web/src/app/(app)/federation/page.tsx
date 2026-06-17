"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, ShieldCheck, ShieldOff } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

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

export default function FederationPage() {
  const [q, setQ] = useState("");

  const { data: status } = useQuery<Status>({
    queryKey: ["fed-status"],
    queryFn: () => apiFetch<Status>(`/api/v1/admin/federation/status`),
  });

  const { data: rows = [], isLoading, error } = useQuery<Identity[]>({
    queryKey: ["fed-identities", q],
    queryFn: () =>
      apiFetch<Identity[]>(`/api/v1/admin/federation/identities?q=${encodeURIComponent(q)}&limit=100`),
  });

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

      {/* Data region — the ONLY scrollable part */}
      <div className="min-h-0 flex-1 overflow-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Provider</TableHead>
              <TableHead>External subject</TableHead>
              <TableHead>Local account</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={4} className="py-8 text-center text-muted-foreground">Loading…</TableCell></TableRow>
            )}
            {error && (
              <TableRow><TableCell colSpan={4} className="py-8 text-center text-destructive">Failed to load.</TableCell></TableRow>
            )}
            {!isLoading && !error && rows.length === 0 && (
              <TableRow><TableCell colSpan={4} className="py-8 text-center text-muted-foreground">No federated identities.</TableCell></TableRow>
            )}
            {rows.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="font-medium">{r.provider}</TableCell>
                <TableCell className="font-mono text-xs">{r.subject}</TableCell>
                <TableCell>{r.display_name || r.email || r.id.slice(0, 8)}</TableCell>
                <TableCell className="text-muted-foreground">{r.status}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
