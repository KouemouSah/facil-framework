"use client";

import { useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, ShieldCheck, Check, Search, ChevronDown } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { codeField, requiredText, optionalText } from "@/lib/form-schemas";
import { ExportMenu } from "@/components/export-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DataGrid, type DataGridColumn } from "@/components/ui/data-grid";
import { DetailPanel } from "@/components/ui/detail-panel";
import { useServerTable, type ServerPage } from "@/lib/use-server-table";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose } from "@/components/ui/dialog";

interface Role {
  id: string;
  code: string;
  name: string;
  description?: string | null;
  organization_id?: string | null;
  is_system: boolean;
}
interface Permission { id: string; code: string; module: string; description?: string | null }

const DEFAULT_PAGE = 20;

export default function RolesPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const sel = searchParams.get("sel") ?? "";
  const [open, setOpen] = useState(false);

  const select = (id: string) => router.replace(`${pathname}?sel=${id}`, { scroll: false });
  const clearSel = () => router.replace(pathname, { scroll: false });

  const table = useServerTable<Role>({
    resource: "roles",
    defaultSort: "code",
    defaultPageSize: DEFAULT_PAGE,
    fetchPage: ({ cursor, limit, sort, q }) =>
      apiFetch<ServerPage<Role>>(
        `/api/v1/rbac/roles?q=${encodeURIComponent(q)}&sort=${sort}` +
        `&limit=${limit}` + (cursor ? `&cursor=${encodeURIComponent(cursor)}` : "")),
  });
  const roles = table.rows;
  const selRole = roles.find((r) => r.id === sel) ?? null;

  const del = useMutation({
    mutationFn: (id: string) => apiFetch(`/api/v1/rbac/roles/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["roles"] }),
  });

  const columns: DataGridColumn<Role>[] = [
    { key: "code", header: "Code", sortable: true, className: "font-mono text-xs" },
    {
      key: "name", header: "Name", sortable: true,
      cell: (r) => (
        <>
          {r.name}
          {r.is_system && (
            <span className="ml-2 inline-flex items-center gap-1 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
              <ShieldCheck className="size-3" /> system
            </span>
          )}
        </>
      ),
    },
    {
      key: "scope", header: "Scope", className: "text-muted-foreground",
      cell: (r) => (r.organization_id ? "Organization" : "Global"),
    },
    {
      key: "actions", header: "Actions", align: "right", headClassName: "w-16", stopClick: true,
      cell: (r) => (
        <Button variant="ghost" size="icon" title={r.is_system ? "System role (protected)" : "Delete"}
          disabled={r.is_system || del.isPending} onClick={() => del.mutate(r.id)}>
          <Trash2 className="size-4" />
        </Button>
      ),
    },
  ];

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Toolbar — fixed */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Roles &amp; access</h1>
          <p className="text-sm text-muted-foreground">Roles bundle permissions; assign them to accounts (scoped).</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="h-9 w-56 pl-8" placeholder="Search code / name"
              value={table.q} onChange={(e) => table.setQ(e.target.value)} />
          </div>
          <ExportMenu filename="roles"
            path={`/api/v1/rbac/roles/export?q=${encodeURIComponent(table.q)}&sort=${table.sort}`} />
          <NewRoleDialog open={open} setOpen={setOpen} />
        </div>
      </div>

      {/* Master-detail: list left, permission editor right (deep-linkable ?sel=) */}
      <div className={`grid min-h-0 flex-1 gap-4 ${selRole ? "lg:grid-cols-[1fr_minmax(360px,460px)]" : ""}`}>
        <DataGrid<Role>
          mode="cursor"
          columns={columns}
          rows={roles}
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
          onRowClick={(r) => select(r.id)}
          selectedId={sel}
          emptyLabel="No roles. Reseed a profile or create one."
        />
        {selRole && <RoleDetail role={selRole} onClose={clearSel} />}
      </div>
    </div>
  );
}

const roleForm = z.object({
  code: codeField,
  name: requiredText("Name"),
  description: optionalText(),
});
type RoleForm = z.infer<typeof roleForm>;

function NewRoleDialog({ open, setOpen }: { open: boolean; setOpen: (b: boolean) => void }) {
  const qc = useQueryClient();
  const [error, setError] = useState("");
  const { register, handleSubmit, reset, formState: { errors } } = useForm<RoleForm>({
    resolver: zodResolver(roleForm),
    defaultValues: { code: "", name: "", description: "" },
  });

  const create = useMutation({
    mutationFn: (values: RoleForm) =>
      apiFetch("/api/v1/rbac/roles", {
        method: "POST",
        body: JSON.stringify({
          code: values.code, name: values.name,
          description: values.description || null,
        }),
      }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["roles"] }); setOpen(false); reset(); setError(""); },
    onError: (e: Error) => setError(e.message || "Create failed"),
  });

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) { reset(); setError(""); } }}>
      <DialogTrigger asChild>
        <Button size="sm"><Plus className="size-4" /> New role</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>New role</DialogTitle></DialogHeader>
        <form className="space-y-3" onSubmit={handleSubmit((v) => create.mutate(v))}>
          <div className="space-y-1.5">
            <Label htmlFor="code">Code</Label>
            <Input id="code" {...register("code")} placeholder="auditor" />
            {errors.code && <p className="text-xs text-destructive">{errors.code.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="name">Name</Label>
            <Input id="name" {...register("name")} placeholder="Auditor" />
            {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="desc">Description</Label>
            <Input id="desc" {...register("description")} placeholder="Read-only access to records" />
            {errors.description && <p className="text-xs text-destructive">{errors.description.message}</p>}
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

function RoleDetail({ role, onClose }: { role: Role; onClose: () => void }) {
  const qc = useQueryClient();
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [selected, setSelected] = useState<Set<string> | null>(null);
  // Collapsible module groups (default collapsed → click a module to reveal + edit
  // its permissions), so the editor stays scannable instead of a long flat list.
  const [openModules, setOpenModules] = useState<Set<string>>(new Set());
  const toggleModule = (m: string) =>
    setOpenModules((prev) => {
      const next = new Set(prev);
      if (next.has(m)) next.delete(m); else next.add(m);
      return next;
    });

  const { data: catalog = [] } = useQuery<Permission[]>({
    queryKey: ["permissions"],
    queryFn: () => apiFetch<Permission[]>(`/api/v1/rbac/permissions`),
  });

  const { data: current, isLoading, isError } = useQuery<{ role_id: string; codes: string[]; etag?: string }>({
    queryKey: ["role-perms", role.id],
    queryFn: () => apiFetch(`/api/v1/rbac/roles/${role.id}/permissions`),
  });

  // Initialise the working set once the role's current grants arrive.
  const working = selected ?? (current ? new Set(current.codes) : null);

  const grouped = useMemo(() => {
    const m = new Map<string, Permission[]>();
    for (const p of catalog) {
      const list = m.get(p.module) ?? [];
      list.push(p);
      m.set(p.module, list);
    }
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [catalog]);

  function toggle(code: string) {
    const next = new Set(working ?? []);
    if (next.has(code)) next.delete(code); else next.add(code);
    setSelected(next);
    setSaved(false);
  }

  const save = useMutation({
    mutationFn: () =>
      apiFetch(`/api/v1/rbac/roles/${role.id}/permissions`, {
        method: "PUT",
        headers: current?.etag ? { "If-Match": current.etag } : undefined,
        body: JSON.stringify({ codes: [...(working ?? [])] }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["role-perms", role.id] });
      setSaved(true);
    },
    onError: (e: { status?: number; message?: string }) => {
      if (e.status === 409) {
        setError("Permissions were changed elsewhere — reloading the latest.");
        setSelected(null);  // drop local edits; refetched grants repopulate
        qc.invalidateQueries({ queryKey: ["role-perms", role.id] });
      } else {
        setError(e.message || "Save failed");
      }
    },
  });

  return (
    <DetailPanel
      title={`Permissions — ${role.name}`}
      subtitle={role.organization_id ? "Organization role" : "Global role"}
      onClose={onClose}
      loading={isLoading}
      footer={
        <div className="flex items-center gap-2">
          {saved && <span className="flex items-center gap-1 text-sm text-emerald-600"><Check className="size-4" /> Saved</span>}
          {error && <span className="text-sm text-destructive">{error}</span>}
          <Button type="button" size="sm" className="ml-auto"
            disabled={role.is_system || save.isPending || working === null}
            onClick={() => save.mutate()}>
            {save.isPending ? "Saving…" : "Save"}
          </Button>
        </div>
      }
    >
      {role.is_system && (
        <p className="mb-3 rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
          System role — permissions are protected and cannot be changed.
        </p>
      )}
      {isError && (
        <p className="mb-3 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          Failed to load this role&apos;s permissions. Please close and reopen to retry.
        </p>
      )}
      <div className="space-y-2">
        {working !== null && grouped.map(([module, perms]) => {
          const open = openModules.has(module);
          const granted = perms.filter((p) => working.has(p.code)).length;
          return (
            <div key={module} className="overflow-hidden rounded-md border">
              <button
                type="button"
                onClick={() => toggleModule(module)}
                aria-expanded={open}
                className="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-accent"
              >
                <ChevronDown className={cn("size-4 shrink-0 text-muted-foreground transition-transform", !open && "-rotate-90")} />
                <span className="text-xs font-semibold uppercase tracking-wide">{module}</span>
                <span className={cn("ml-auto rounded-full px-2 py-0.5 text-xs tabular-nums",
                  granted > 0 ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground")}>
                  {granted}/{perms.length}
                </span>
              </button>
              {open && (
                <div className="grid grid-cols-1 gap-0.5 border-t p-2">
                  {perms.map((p) => (
                    <label key={p.code} className="flex items-center gap-2 rounded-md px-2 py-1 text-sm hover:bg-accent">
                      <input
                        type="checkbox"
                        className="size-4 shrink-0 accent-[hsl(var(--primary))]"
                        checked={working.has(p.code)}
                        disabled={role.is_system}
                        onChange={() => toggle(p.code)}
                      />
                      <span className="font-mono text-xs">{p.code}</span>
                      {p.description && <span className="truncate text-xs text-muted-foreground">— {p.description}</span>}
                    </label>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </DetailPanel>
  );
}
