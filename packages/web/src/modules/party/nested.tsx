"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Plus, X, Star } from "lucide-react";
import { toast } from "@/lib/toast";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { AddressCombobox } from "@/components/ui/address-combobox";
import { AddressField } from "@/components/ui/address-field";
import {
  addPartyRole, deletePartyRole, getAddress, linkPartyAddress, listPartyAddresses,
  listPartyRoles, unlinkPartyAddress,
} from "./api";

const ROLE_SUGGESTIONS = ["customer", "vendor", "employee", "contact"];
const TYPE_SUGGESTIONS = ["main", "billing", "shipping"];

export function PartyRolesSection({ pid, canCreate, canDelete }: {
  pid: string; canCreate: boolean; canDelete: boolean;
}) {
  const t = useTranslations("directory");
  const qc = useQueryClient();
  const [role, setRole] = useState("");
  const roles = useQuery({ queryKey: ["party-roles", pid], queryFn: () => listPartyRoles(pid) });

  const add = useMutation({
    mutationFn: () => addPartyRole(pid, role.trim()),
    onSuccess: () => { setRole(""); qc.invalidateQueries({ queryKey: ["party-roles", pid] }); },
    onError: (e: unknown) => toast({ variant: "error", title: t("r.add_failed"), description: e instanceof ApiError ? e.message : undefined }),
  });
  const remove = useMutation({
    mutationFn: (roleId: string) => deletePartyRole(pid, roleId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["party-roles", pid] }),
    onError: (e: unknown) => toast({ variant: "error", title: t("r.remove_failed"), description: e instanceof ApiError ? e.message : undefined }),
  });

  return (
    <section className="space-y-2 border-t pt-4">
      <h3 className="text-sm font-semibold">{t("r.title")}</h3>
      <div className="flex flex-wrap gap-1.5">
        {roles.isLoading && <span className="text-xs text-muted-foreground">{t("loading")}</span>}
        {roles.isError && <span className="text-xs text-destructive">{t("load_error")}</span>}
        {(roles.data ?? []).map((r) => (
          <Badge key={r.id} variant="secondary" className="gap-1">
            {r.role}
            {canDelete && (
              <button type="button" title={t("r.remove")} onClick={() => remove.mutate(r.id)}
                className="text-muted-foreground hover:text-destructive"><X className="size-3" /></button>
            )}
          </Badge>
        ))}
        {roles.data && roles.data.length === 0 && <span className="text-xs text-muted-foreground">{t("r.empty")}</span>}
      </div>
      {canCreate && (
        <form className="flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); if (role.trim()) add.mutate(); }}>
          <Input className="h-8 w-48" list="role-suggestions" value={role} placeholder={t("r.placeholder")}
            onChange={(e) => setRole(e.target.value)} maxLength={40} />
          <datalist id="role-suggestions">{ROLE_SUGGESTIONS.map((s) => <option key={s} value={s} />)}</datalist>
          <Button type="submit" size="sm" variant="secondary" disabled={!role.trim() || add.isPending}>
            <Plus className="size-3.5" /> {t("r.add")}
          </Button>
        </form>
      )}
    </section>
  );
}

export function PartyAddressesSection({ pid, canCreate, canDelete }: {
  pid: string; canCreate: boolean; canDelete: boolean;
}) {
  const t = useTranslations("directory");
  const qc = useQueryClient();
  const [target, setTarget] = useState("");        // the address id to attach (picked OR created)
  const [addressType, setAddressType] = useState("main");
  const [isPrimary, setIsPrimary] = useState(false);
  const [newMode, setNewMode] = useState(false);   // pick-existing vs create-new

  const links = useQuery({ queryKey: ["party-addresses", pid], queryFn: () => listPartyAddresses(pid) });

  const attach = useMutation({
    mutationFn: () => linkPartyAddress(pid, { address_id: target, address_type: addressType.trim() || "main", is_primary: isPrimary }),
    onSuccess: () => {
      setTarget(""); setIsPrimary(false); setAddressType("main"); setNewMode(false);
      qc.invalidateQueries({ queryKey: ["party-addresses", pid] });
      toast({ variant: "success", title: t("l.attached") });
    },
    onError: (e: unknown) => toast({ variant: "error", title: t("l.attach_failed"), description: e instanceof ApiError ? e.message : undefined }),
  });
  const unlink = useMutation({
    mutationFn: (linkId: string) => unlinkPartyAddress(pid, linkId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["party-addresses", pid] }); toast({ variant: "success", title: t("l.unlinked") }); },
    onError: (e: unknown) => toast({ variant: "error", title: t("l.unlink_failed"), description: e instanceof ApiError ? e.message : undefined }),
  });

  return (
    <section className="space-y-3 border-t pt-4">
      <h3 className="text-sm font-semibold">{t("l.title")}</h3>
      <div className="space-y-1.5">
        {links.isLoading && <p className="text-xs text-muted-foreground">{t("loading")}</p>}
        {links.isError && <p className="text-xs text-destructive">{t("load_error")}</p>}
        {(links.data ?? []).map((lk) => (
          <div key={lk.id} className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm">
            <AddressLinkLabel addressId={lk.address_id} />
            <div className="ml-auto flex shrink-0 items-center gap-1.5">
              <Badge variant="outline">{lk.address_type}</Badge>
              {lk.is_primary && <Badge variant="secondary" className="gap-1"><Star className="size-3" /> {t("l.primary")}</Badge>}
              {canDelete && (
                <Button variant="ghost" size="icon" title={t("l.unlink")} disabled={unlink.isPending}
                  onClick={() => unlink.mutate(lk.id)}><X className="size-3.5" /></Button>
              )}
            </div>
          </div>
        ))}
        {links.data && links.data.length === 0 && <p className="text-xs text-muted-foreground">{t("l.empty")}</p>}
      </div>

      {canCreate && (
        <div className="space-y-2 rounded-md border border-dashed p-3">
          <div className="flex items-center gap-2 text-xs">
            <button type="button" onClick={() => { setNewMode(false); setTarget(""); }}
              className={newMode ? "text-muted-foreground hover:text-foreground" : "font-medium text-foreground underline"}>{t("l.mode_existing")}</button>
            <span className="text-muted-foreground">·</span>
            <button type="button" onClick={() => { setNewMode(true); setTarget(""); }}
              className={newMode ? "font-medium text-foreground underline" : "text-muted-foreground hover:text-foreground"}>{t("l.mode_new")}</button>
          </div>

          {newMode
            ? <AddressField value={target} onChange={setTarget} label={t("l.new_address")} />
            : <AddressCombobox value={target} onChange={setTarget} />}

          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1">
              <Label htmlFor="link-type" className="text-xs">{t("l.type")}</Label>
              <Input id="link-type" list="addr-type-suggestions" className="h-8 w-36" value={addressType}
                onChange={(e) => setAddressType(e.target.value)} maxLength={30} />
              <datalist id="addr-type-suggestions">{TYPE_SUGGESTIONS.map((s) => <option key={s} value={s} />)}</datalist>
            </div>
            <label className="flex h-8 items-center gap-2 text-sm">
              <input type="checkbox" className="size-4 accent-[hsl(var(--primary))]" checked={isPrimary}
                onChange={(e) => setIsPrimary(e.target.checked)} />
              {t("l.primary")}
            </label>
            <Button type="button" size="sm" className="ml-auto" disabled={!target || attach.isPending}
              onClick={() => attach.mutate()}>{t("l.attach")}</Button>
          </div>
        </div>
      )}
    </section>
  );
}

/** Resolve a linked address's label (the link only carries `address_id`). On a
 *  resolve failure (e.g. a dangling link to a deleted address) show it as such —
 *  not a perpetual "…" — so the operator knows to unlink it. */
function AddressLinkLabel({ addressId }: { addressId: string }) {
  const t = useTranslations("directory");
  const { data, isError } = useQuery({ queryKey: ["address", addressId], queryFn: () => getAddress(addressId) });
  if (isError) return <span className="min-w-0 truncate text-destructive">{t("l.unavailable", { id: addressId.slice(0, 8) })}</span>;
  const label = data ? (data.label || data.line1 || data.city || `#${addressId.slice(0, 8)}`) : "…";
  return <span className="min-w-0 truncate">{label}{data?.city ? <span className="text-muted-foreground"> · {data.city}</span> : null}</span>;
}
