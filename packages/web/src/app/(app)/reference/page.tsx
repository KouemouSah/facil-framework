"use client";

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Upload } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { parseCsv } from "@/lib/parse-csv";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DataGrid, type DataGridColumn } from "@/components/ui/data-grid";
import { DetailPanel } from "@/components/ui/detail-panel";
import { RefSelect } from "@/components/ui/ref-select";
import { useServerTable, type ServerPage } from "@/lib/use-server-table";

/**
 * Reference master data admin (ERP-grade F.2) — Currencies / Countries / Regions.
 *
 * Expert ergonomics choice (vs "create as full pages"): these are simple records
 * (3–6 fields), so management is a keyset grid + a slide-over quick-create/edit
 * (Save & New), the Salesforce/Odoo pattern for master data. Full record pages are
 * reserved for rich entities (org/site/agent). Lives under Configuration, not the
 * primary workspace.
 */
const REF = "/api/v1/modules/reference";
type Row = Record<string, unknown> & { id: string; code: string; name: string };
type Tab = "currencies" | "countries" | "regions";

const TABS: { key: Tab; defaultSort: string }[] = [
  { key: "currencies", defaultSort: "code" },
  { key: "countries", defaultSort: "name" },
  { key: "regions", defaultSort: "name" },
];

export default function ReferencePage() {
  const t = useTranslations("reference");
  const [tab, setTab] = useState<Tab>("currencies");
  return (
    <div className="flex h-full flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>
      <div className="flex gap-1 border-b">
        {TABS.map((tb) => (
          <button key={tb.key} type="button"
            onClick={() => setTab(tb.key)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
              tab === tb.key ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"}`}>
            {t(`tab.${tb.key}`)}
          </button>
        ))}
      </div>
      {/* Remount per tab so each gets its own table state */}
      {tab === "currencies" && <RefTab key="cur" tab="currencies" />}
      {tab === "countries" && <RefTab key="cou" tab="countries" />}
      {tab === "regions" && <RefTab key="reg" tab="regions" />}
    </div>
  );
}

function RefTab({ tab }: { tab: Tab }) {
  const t = useTranslations("reference");
  const conf = TABS.find((x) => x.key === tab)!;
  const [editing, setEditing] = useState<Row | "new" | null>(null);
  // Regions are scoped to a country (dependent filter).
  const [countryId, setCountryId] = useState("");

  const filters: Record<string, string> = tab === "regions" && countryId
    ? { country_id: countryId } : {};

  const table = useServerTable<Row>({
    resource: `ref-${tab}`,
    defaultSort: conf.defaultSort,
    defaultPageSize: 50,
    enabled: tab !== "regions" || !!countryId,
    fetchPage: ({ cursor, limit, sort, q }) => {
      const p = new URLSearchParams({ q, sort, limit: String(limit) });
      if (cursor) p.set("cursor", cursor);
      if (tab === "regions" && countryId) p.set("country_id", countryId);
      return apiFetch<ServerPage<Row>>(`${REF}/${tab}?${p.toString()}`);
    },
  });

  const del = useMutation({
    mutationFn: (id: string) => apiFetch(`${REF}/${tab}/${id}`, { method: "DELETE" }),
    onSuccess: () => table.refetch(),
  });

  // Bulk import: parse the CSV client-side, POST rows; the backend reports per-row
  // errors (no silent drop). Region rows need a country_id column in the CSV.
  const fileRef = useRef<HTMLInputElement>(null);
  const [imported, setImported] =
    useState<{ created: number; total: number; errors: { row: number; detail: string }[] } | null>(null);
  const doImport = useMutation({
    mutationFn: async (file: File) => {
      const rows = parseCsv(await file.text());
      return apiFetch<{ created: number; total: number; errors: { row: number; detail: string }[] }>(
        `${REF}/${tab}/import`, { method: "POST", body: JSON.stringify({ rows }) });
    },
    onSuccess: (r) => { setImported(r); table.refetch(); },
  });

  const columns: DataGridColumn<Row>[] = [
    { key: "code", header: t("col.code"), sortable: true, className: "font-mono text-xs" },
    { key: "name", header: t("col.name"), sortable: true },
    ...(tab === "currencies"
      ? [{ key: "symbol", header: t("col.symbol"), cell: (r: Row) => String(r.symbol ?? "—") }]
      : []),
    {
      key: "actions", header: "", align: "right" as const, headClassName: "w-16", stopClick: true,
      cell: (r: Row) => (
        <Button variant="ghost" size="icon" title={t("delete")}
          disabled={del.isPending} onClick={() => del.mutate(r.id)}>
          <Trash2 className="size-4" />
        </Button>
      ),
    },
  ];

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex items-center gap-2">
        {tab === "regions" && (
          <div className="w-72">
            <RefSelect resource="countries" value={countryId} onChange={setCountryId}
              allowNone={false} placeholder={t("pick_country_placeholder")} />
          </div>
        )}
        <Input className="h-9 w-56" placeholder={t("search_placeholder")}
          value={table.q} onChange={(e) => table.setQ(e.target.value)} />
        <input ref={fileRef} type="file" accept=".csv,text/csv" hidden
          onChange={(e) => { const f = e.target.files?.[0]; if (f) doImport.mutate(f); e.target.value = ""; }} />
        <Button size="sm" variant="outline" className="ml-auto" disabled={doImport.isPending}
          onClick={() => fileRef.current?.click()}>
          <Upload className="size-4" /> {doImport.isPending ? t("importing") : t("import")}
        </Button>
        <Button size="sm"
          disabled={tab === "regions" && !countryId}
          onClick={() => setEditing("new")}>
          <Plus className="size-4" /> {t("new")}
        </Button>
      </div>

      {imported && (
        <div className="rounded-md border bg-accent/30 px-3 py-2 text-sm">
          <span className="font-medium">{t("imported", { created: imported.created, total: imported.total })}</span>
          {imported.errors.length > 0 && (
            <span className="ml-2 text-destructive">
              {t("import_errors", {
                count: imported.errors.length,
                rows: imported.errors.slice(0, 3).map((e) => e.row).join(", ")
                  + (imported.errors.length > 3 ? "…" : ""),
              })}
            </span>
          )}
          <button type="button" className="ml-2 text-xs text-muted-foreground underline"
            onClick={() => setImported(null)}>{t("dismiss")}</button>
        </div>
      )}

      <div className={`grid min-h-0 flex-1 gap-4 ${editing ? "lg:grid-cols-[1fr_minmax(340px,420px)]" : ""}`}>
        <DataGrid<Row>
          mode="cursor"
          columns={columns}
          rows={table.rows}
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
          onRowClick={(r) => setEditing(r)}
          selectedId={editing && editing !== "new" ? editing.id : undefined}
          emptyLabel={tab === "regions" && !countryId ? t("empty_pick_country") : t("empty")}
        />
        {editing && (
          <RefForm tab={tab} record={editing === "new" ? null : editing}
            countryId={countryId}
            onClose={() => setEditing(null)}
            onSaved={(again) => { table.refetch(); setEditing(again ? "new" : null); }} />
        )}
      </div>
    </div>
  );
}

function RefForm({ tab, record, countryId, onClose, onSaved }: {
  tab: Tab; record: Row | null; countryId: string;
  onClose: () => void; onSaved: (again: boolean) => void;
}) {
  const t = useTranslations("reference");
  const qc = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>(() => ({
    code: String(record?.code ?? ""),
    name: String(record?.name ?? ""),
    symbol: String(record?.symbol ?? ""),
    decimal_places: String(record?.decimal_places ?? "2"),
    region_type: String(record?.region_type ?? ""),
    default_currency_id: String(record?.default_currency_id ?? ""),
  }));
  const [error, setError] = useState("");
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  function payload(): Record<string, unknown> {
    if (tab === "currencies") return {
      code: form.code, name: form.name, symbol: form.symbol || null,
      decimal_places: Number(form.decimal_places || 2),
    };
    if (tab === "countries") return {
      code: form.code, name: form.name,
      default_currency_id: form.default_currency_id || null,
    };
    return { country_id: countryId, code: form.code, name: form.name,
             region_type: form.region_type || null };
  }

  const save = useMutation({
    mutationFn: () => record
      ? apiFetch(`${REF}/${tab}/${record.id}`, { method: "PUT", body: JSON.stringify(payload()) })
      : apiFetch(`${REF}/${tab}`, { method: "POST", body: JSON.stringify(payload()) }),
    onError: (e: Error) => setError(e.message || t("save_failed")),
  });

  async function submit(again: boolean) {
    setError("");
    await save.mutateAsync();
    qc.invalidateQueries({ queryKey: ["ref-one"] });
    onSaved(again);
  }

  return (
    <DetailPanel title={record ? t("edit_title", { code: record.code })
                                : t("new_title", { entity: t(`singular.${tab}`) })} onClose={onClose}
      footer={
        <div className="flex items-center gap-2">
          {error && <span className="text-sm text-destructive">{error}</span>}
          {!record && (
            <Button type="button" size="sm" variant="outline" disabled={save.isPending}
              onClick={() => submit(true)}>{t("save_new")}</Button>
          )}
          <Button type="button" size="sm" className="ml-auto" disabled={save.isPending}
            onClick={() => submit(false)}>{save.isPending ? t("saving") : t("save")}</Button>
        </div>
      }>
      <div className="space-y-3">
        <Field label={t("f.code")}><Input value={form.code} disabled={!!record}
          onChange={(e) => set("code", e.target.value)} placeholder={tab === "countries" ? "GQ" : "XAF"} /></Field>
        <Field label={t("f.name")}><Input value={form.name} onChange={(e) => set("name", e.target.value)} /></Field>
        {tab === "currencies" && (<>
          <Field label={t("f.symbol")}><Input value={form.symbol} onChange={(e) => set("symbol", e.target.value)} /></Field>
          <Field label={t("f.decimal_places")}><Input type="number" min={0} max={4} value={form.decimal_places}
            onChange={(e) => set("decimal_places", e.target.value)} /></Field>
        </>)}
        {tab === "countries" && (
          <Field label={t("f.default_currency")}>
            <RefSelect resource="currencies" value={form.default_currency_id}
              onChange={(v) => set("default_currency_id", v)} />
          </Field>
        )}
        {tab === "regions" && (
          <Field label={t("f.type")}><Input value={form.region_type}
            onChange={(e) => set("region_type", e.target.value)} placeholder={t("type_placeholder")} /></Field>
        )}
      </div>
    </DetailPanel>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}
