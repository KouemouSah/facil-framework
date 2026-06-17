"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Search, Check } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { codeField, requiredText } from "@/lib/form-schemas";
import { ExportMenu } from "@/components/export-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DataGrid, type DataGridColumn } from "@/components/ui/data-grid";
import { DetailPanel } from "@/components/ui/detail-panel";
import { JsonField } from "@/components/ui/json-field";
import { useServerTable, type ServerPage } from "@/lib/use-server-table";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose } from "@/components/ui/dialog";

interface Org { id: string; code: string; legal_name: string; display_name?: string }
const DEFAULT_PAGE = 20;

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
        `/api/v1/modules/organization/?q=${encodeURIComponent(q)}&sort=${sort}` +
        `&limit=${limit}` + (cursor ? `&cursor=${encodeURIComponent(cursor)}` : "")),
  });
  const rows = table.rows;

  const del = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/v1/modules/organization/${id}`, { method: "DELETE" }),
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
            path={`/api/v1/modules/organization/export?q=${encodeURIComponent(table.q)}&sort=${table.sort}`} />
          <NewOrgDialog open={open} setOpen={setOpen} />
        </div>
      </div>

      {/* Master-detail: list left, edit form right (deep-linkable ?sel=) */}
      <div className={`grid min-h-0 flex-1 gap-4 ${sel ? "lg:grid-cols-[1fr_minmax(380px,520px)]" : ""}`}>
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

// Editable scalar fields of OrganizationUpdate (code is immutable; the JSON
// document_identity/settings are edited via the JsonField editors below).
const ORG_FIELDS: { key: string; label: string }[] = [
  { key: "legal_name", label: "Legal name" },
  { key: "display_name", label: "Display name" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "website", label: "Website" },
  { key: "logo_url", label: "Logo URL" },
  { key: "address_line1", label: "Address line 1" },
  { key: "address_line2", label: "Address line 2" },
  { key: "city", label: "City" },
  { key: "region", label: "Region" },
  { key: "country_code", label: "Country (ISO-2)" },
  { key: "postal_code", label: "Postal code" },
  { key: "tax_id", label: "Tax ID" },
  { key: "registration_number", label: "Registration #" },
  { key: "default_locale", label: "Default locale" },
  { key: "timezone", label: "Timezone" },
  { key: "currency", label: "Currency (ISO-3)" },
];

function OrgDetail({ orgId, onClose }: { orgId: string; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState<Record<string, string> | null>(null);
  const [docIdentity, setDocIdentity] = useState<unknown>({});
  const [settings, setSettings] = useState<unknown>({});
  const [jsonOk, setJsonOk] = useState({ document_identity: true, settings: true });
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const { data } = useQuery<Record<string, unknown>>({
    queryKey: ["org", orgId],
    queryFn: () => apiFetch(`/api/v1/modules/organization/${orgId}`),
  });

  useEffect(() => {
    if (data && !form) {
      const f: Record<string, string> = {};
      for (const { key } of ORG_FIELDS) f[key] = (data[key] as string) ?? "";
      setForm(f);
      setDocIdentity(data.document_identity ?? {});
      setSettings(data.settings ?? {});
      setJsonOk({ document_identity: true, settings: true });
    }
  }, [data, form]);

  const save = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = {};
      for (const { key } of ORG_FIELDS) payload[key] = (form?.[key] ?? "") || null;
      payload.document_identity = docIdentity;
      payload.settings = settings;
      return apiFetch(`/api/v1/modules/organization/${orgId}`, {
        method: "PUT",
        headers: data?.etag ? { "If-Match": String(data.etag) } : undefined,
        body: JSON.stringify(payload),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["org", orgId] });
      qc.invalidateQueries({ queryKey: ["orgs"] });
      setSaved(true);
    },
    onError: (e: { status?: number; message?: string }) => {
      if (e.status === 409) {
        setError("Changed elsewhere — reloading the latest.");
        setForm(null);
        qc.invalidateQueries({ queryKey: ["org", orgId] });
      } else { setError(e.message || "Save failed"); }
    },
  });

  function set(k: string, v: string) {
    setForm((f) => (f ? { ...f, [k]: v } : f));
    setSaved(false);
  }

  return (
    <DetailPanel
      title={(data?.display_name as string) || (data?.legal_name as string) || "Organization"}
      subtitle={data?.code ? `code ${data.code}` : undefined}
      onClose={onClose}
      footer={
        <div className="flex items-center gap-2">
          {saved && <span className="flex items-center gap-1 text-sm text-emerald-600"><Check className="size-4" /> Saved</span>}
          {error && <span className="text-sm text-destructive">{error}</span>}
          <Button type="button" size="sm" className="ml-auto"
            disabled={save.isPending || form === null || !jsonOk.document_identity || !jsonOk.settings}
            onClick={() => save.mutate()}>
            {save.isPending ? "Saving…" : "Save"}
          </Button>
        </div>
      }
    >
      {form === null && <p className="text-sm text-muted-foreground">Loading…</p>}
      {form !== null && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {ORG_FIELDS.map(({ key, label }) => (
              <div key={key} className="space-y-1.5">
                <Label htmlFor={`org-${key}`}>{label}</Label>
                <Input id={`org-${key}`} value={form[key]} onChange={(e) => set(key, e.target.value)} />
              </div>
            ))}
          </div>
          <JsonField id="org-document_identity" label="Document identity (JSON)"
            value={data?.document_identity}
            hint="Identifiers shown on generated documents (registry, VAT…)."
            onChange={(v, ok) => { setJsonOk((s) => ({ ...s, document_identity: ok })); if (ok) setDocIdentity(v); setSaved(false); }} />
          <JsonField id="org-settings" label="Settings (JSON)"
            value={data?.settings}
            hint="Free-form organization settings."
            onChange={(v, ok) => { setJsonOk((s) => ({ ...s, settings: ok })); if (ok) setSettings(v); setSaved(false); }} />
        </div>
      )}
    </DetailPanel>
  );
}

const orgForm = z.object({ code: codeField, legal_name: requiredText("Legal name") });
type OrgForm = z.infer<typeof orgForm>;

function NewOrgDialog({ open, setOpen }: { open: boolean; setOpen: (b: boolean) => void }) {
  const qc = useQueryClient();
  const [error, setError] = useState("");
  const { register, handleSubmit, reset, formState: { errors } } = useForm<OrgForm>({
    resolver: zodResolver(orgForm),
    defaultValues: { code: "", legal_name: "" },
  });

  const create = useMutation({
    mutationFn: (values: OrgForm) =>
      apiFetch("/api/v1/modules/organization/", {
        method: "POST",
        body: JSON.stringify(values),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orgs"] });
      setOpen(false);
      reset(); setError("");
    },
    onError: (e: Error) => setError(e.message || "Create failed"),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm"><Plus className="size-4" /> New</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>New organization</DialogTitle></DialogHeader>
        <form className="space-y-3" onSubmit={handleSubmit((v) => create.mutate(v))}>
          <div className="space-y-1.5">
            <Label htmlFor="code">Code</Label>
            <Input id="code" {...register("code")} placeholder="acme" />
            {errors.code && <p className="text-xs text-destructive">{errors.code.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="legal">Legal name</Label>
            <Input id="legal" {...register("legal_name")} placeholder="Acme Corp" />
            {errors.legal_name && <p className="text-xs text-destructive">{errors.legal_name.message}</p>}
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <DialogClose asChild><Button type="button" variant="ghost">Cancel</Button></DialogClose>
            <Button type="submit" disabled={create.isPending}>{create.isPending ? "Creating…" : "Create"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
