"use client";

import { useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Plus, Trash2, Search } from "lucide-react";
import { toast } from "@/lib/toast";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { DataGrid, RecordForm, RecordSurface } from "@/components/shared";
import { type DataGridColumn } from "@/components/ui/data-grid";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useServerTable } from "@/lib/use-server-table";
import { usePermissions } from "@/lib/use-permissions";
import { usePartyFields } from "./fields";
import {
  PARTY_TYPES, createParty, deleteParty, getParty, listParties, updateParty, type Party,
} from "./api";
import { AddressesTab } from "./addresses";
import { PartyRolesSection, PartyAddressesSection } from "./nested";

type Tab = "parties" | "addresses";

export default function DirectoryPage() {
  const t = useTranslations("directory");
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const tab = (params.get("tab") === "addresses" ? "addresses" : "parties") as Tab;
  const sel = params.get("sel") ?? "";
  const isNew = params.get("new") === "1";

  const setTab = (nt: Tab) => router.replace(`${pathname}?tab=${nt}`, { scroll: false });
  const openCreate = () => router.replace(`${pathname}?tab=${tab}&new=1`, { scroll: false });
  const openEdit = (id: string) => router.replace(`${pathname}?tab=${tab}&sel=${id}`, { scroll: false });
  const closeSurface = () => router.replace(`${pathname}?tab=${tab}`, { scroll: false });

  const surface = { sel, isNew, openCreate, openEdit, closeSurface };

  return (
    <div className="flex h-full flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      <div className="flex gap-1 border-b">
        {(["parties", "addresses"] as Tab[]).map((tk) => (
          <button key={tk} type="button" onClick={() => setTab(tk)}
            className={cn("border-b-2 px-3 py-1.5 text-sm font-medium",
              tab === tk ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground")}>
            {t(`tab.${tk}`)}
          </button>
        ))}
      </div>

      {tab === "parties" ? <PartiesTab {...surface} /> : <AddressesTab {...surface} />}
    </div>
  );
}

export interface TabProps {
  sel: string; isNew: boolean;
  openCreate: () => void; openEdit: (id: string) => void; closeSurface: () => void;
}

function PartiesTab({ sel, isNew, openCreate, openEdit, closeSurface }: TabProps) {
  const t = useTranslations("directory");
  const qc = useQueryClient();
  const { can } = usePermissions();
  const canCreate = can("party.create");
  const canUpdate = can("party.update");
  const canDelete = can("party.delete");
  const [pendingDelete, setPendingDelete] = useState<Party | null>(null);

  const table = useServerTable<Party>({
    resource: "parties", defaultSort: "name", defaultPageSize: 20,
    fetchPage: ({ cursor, limit, sort, filters, q }) => listParties({ q, sort, limit, cursor, filters }),
  });

  const del = useMutation({
    mutationFn: (p: Party) => deleteParty(p.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["parties"] }); toast({ variant: "success", title: t("toast.deleted") }); },
    onError: (e: unknown) => toast({ variant: "error", title: t("toast.delete_failed"), description: e instanceof ApiError ? e.message : undefined }),
  });

  const columns: DataGridColumn<Party>[] = [
    { key: "name", header: t("p.name"), sortable: true, cell: (p) => p.name },
    {
      key: "party_type", header: t("p.type"), stopClick: true,
      filter: { type: "select", options: PARTY_TYPES.map((x) => ({ value: x, label: x })) },
      cell: (p) => <span className="text-muted-foreground">{p.party_type}</span>,
    },
    { key: "email", header: t("p.email"), className: "text-muted-foreground", cell: (p) => p.email || "—" },
    {
      key: "status", header: t("status"), stopClick: true,
      filter: { type: "select", options: [{ value: "1", label: t("active") }, { value: "0", label: t("inactive") }] },
      cell: (p) => <Badge variant={p.is_active ? "secondary" : "outline"}>{p.is_active ? t("active") : t("inactive")}</Badge>,
    },
    ...(canDelete ? [{
      key: "actions", header: "", align: "right" as const, headClassName: "w-12", stopClick: true,
      cell: (p: Party) => (
        <Button variant="ghost" size="icon" title={t("delete.confirm")} disabled={del.isPending}
          onClick={() => setPendingDelete(p)}><Trash2 className="size-4" /></Button>
      ),
    }] : []),
  ];

  const surfaceOpen = (isNew && canCreate) || !!sel;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex items-center gap-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="h-9 w-56 pl-8" placeholder={t("p.search")} value={table.q} onChange={(e) => table.setQ(e.target.value)} />
        </div>
        {canCreate && <Button size="sm" className="ml-auto" onClick={openCreate}><Plus className="size-4" /> {t("p.new")}</Button>}
      </div>
      <div className="flex min-h-0 flex-1 gap-4">
        <div className="min-w-0 flex-1">
          <DataGrid<Party> mode="cursor" columns={columns} rows={table.rows} rowKey={(p) => p.id}
            pageSize={table.pageSize} onPageSizeChange={table.onPageSizeChange} sort={table.sort} onSortChange={table.onSortChange}
            filters={table.filters} onFilterChange={table.onFilterChange} hasPrev={table.hasPrev} hasNext={table.hasNext}
            onPrev={table.onPrev} onNext={table.onNext} count={table.count} capped={table.capped}
            isLoading={table.isLoading} error={table.error} onRowClick={(p) => openEdit(p.id)} selectedId={sel} emptyLabel={t("p.empty")} />
        </div>
        {surfaceOpen && (
          isNew
            ? (canCreate && <PartyCreateSurface onClose={closeSurface} onSaved={() => table.refetch()} />)
            : <PartyEditSurface key={sel} partyId={sel} readOnly={!canUpdate} onClose={closeSurface} />
        )}
      </div>
      <ConfirmDialog open={!!pendingDelete} onOpenChange={(o) => { if (!o) setPendingDelete(null); }} danger
        title={t("delete.title")} body={t("delete.body", { name: pendingDelete?.name ?? "" })} confirmLabel={t("delete.confirm")}
        busy={del.isPending}
        onConfirm={() => { if (pendingDelete) del.mutate(pendingDelete); setPendingDelete(null); }}
        onCancel={() => setPendingDelete(null)} />
    </div>
  );
}

function PartyCreateSurface({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const t = useTranslations("directory");
  const partyFields = usePartyFields();
  const qc = useQueryClient();
  return (
    <RecordSurface title={t("p.new_title")} resourceKey="parties" onClose={onClose}>
      {/* No custom-fields split: `party.custom_fields` is not an extensible
          target (Fix wave 1) — every `PARTY_FIELD_SPECS` name is already a
          real `PartyIn` column, so the flat RecordForm payload is the body. */}
      <RecordForm fields={partyFields} mode="create" layout="rich" enableSaveNew submitLabel={t("p.new")}
        initial={{ party_type: "organization", is_active: true }}
        onSubmit={(payload) => createParty(payload)}
        onSuccess={({ again }) => { qc.invalidateQueries({ queryKey: ["parties"] }); onSaved(); toast({ variant: "success", title: t("toast.created") }); if (!again) onClose(); }}
        onCancel={onClose} />
    </RecordSurface>
  );
}

function PartyEditSurface({ partyId, readOnly, onClose }: { partyId: string; readOnly: boolean; onClose: () => void }) {
  const t = useTranslations("directory");
  const partyFields = usePartyFields();
  const qc = useQueryClient();
  const { can } = usePermissions();
  const { data, isError } = useQuery({ queryKey: ["party", partyId], queryFn: () => getParty(partyId) });
  return (
    <RecordSurface title={data?.name || t("p.edit_title")} resourceKey="parties" onClose={onClose}>
      {isError && <p className="text-sm text-destructive">{t("load_error")}</p>}
      {!data && !isError && <p className="text-sm text-muted-foreground">{t("loading")}</p>}
      {data && (
        <div className="space-y-4">
          <RecordForm key={data.etag ?? partyId} fields={partyFields} mode="edit" layout="rich" readOnly={readOnly}
            initial={data as unknown as Record<string, unknown>} etag={data.etag}
            onSubmit={(payload, etag) => updateParty(partyId, payload, etag)}
            onSuccess={() => { qc.invalidateQueries({ queryKey: ["party", partyId] }); qc.invalidateQueries({ queryKey: ["parties"] }); toast({ variant: "success", title: t("toast.saved") }); }}
            onConflict={() => qc.invalidateQueries({ queryKey: ["party", partyId] })} />
          <PartyRolesSection pid={partyId} canCreate={can("party.create")} canDelete={can("party.delete")} />
          <PartyAddressesSection pid={partyId} canCreate={can("party.create")} canDelete={can("party.delete")} />
        </div>
      )}
    </RecordSurface>
  );
}
