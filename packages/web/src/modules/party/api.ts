import { apiFetch } from "@/lib/api";
import type { ServerPage } from "@/lib/use-server-table";

export const PARTY_BASE = "/api/v1/modules/party";
export const PARTY_TYPES = ["organization", "person"] as const;

export interface Party {
  id: string;
  party_type: string;
  name: string;
  tax_id: string | null;
  registration_number: string | null;
  email: string | null;
  phone: string | null;
  website: string | null;
  custom_fields: Record<string, unknown>;
  is_active: boolean;
  etag?: string;
}
export interface PartyRole { id: string; party_id: string; role: string; is_active: boolean }
export interface PartyAddressLink {
  id: string; party_id: string; address_id: string;
  address_type: string; is_primary: boolean; is_active: boolean;
}
export interface Address {
  id: string;
  label: string | null;
  line1: string | null;
  line2: string | null;
  city: string | null;
  postal_code: string | null;
  country_id: string | null;
  country_region_id: string | null;
  latitude: number | null;
  longitude: number | null;
  is_active: boolean;
  etag?: string;
}

// --- Parties ---
export const listParties = (p: { q: string; sort: string; limit: number; cursor: string | null; filters: Record<string, string> }) =>
  apiFetch<ServerPage<Party>>(
    `${PARTY_BASE}/parties?q=${encodeURIComponent(p.q)}&sort=${p.sort}&limit=${p.limit}` +
    (p.filters.party_type ? `&party_type=${p.filters.party_type}` : "") +
    (p.filters.active ? `&active=${p.filters.active}` : "") +
    (p.cursor ? `&cursor=${encodeURIComponent(p.cursor)}` : ""));

export const getParty = (id: string) => apiFetch<Party>(`${PARTY_BASE}/parties/${id}`);
export const createParty = (body: Record<string, unknown>) =>
  apiFetch<Party>(`${PARTY_BASE}/parties`, { method: "POST", body: JSON.stringify(body) });
export const updateParty = (id: string, body: Record<string, unknown>, etag?: string) =>
  apiFetch<Party>(`${PARTY_BASE}/parties/${id}`, {
    method: "PUT", headers: etag ? { "If-Match": etag } : undefined, body: JSON.stringify(body),
  });
export const deleteParty = (id: string) => apiFetch(`${PARTY_BASE}/parties/${id}`, { method: "DELETE" });

// --- Party roles (nested) ---
export const listPartyRoles = (pid: string) => apiFetch<PartyRole[]>(`${PARTY_BASE}/parties/${pid}/roles`);
export const addPartyRole = (pid: string, role: string) =>
  apiFetch<PartyRole>(`${PARTY_BASE}/parties/${pid}/roles`, { method: "POST", body: JSON.stringify({ role }) });
export const deletePartyRole = (pid: string, roleId: string) =>
  apiFetch(`${PARTY_BASE}/parties/${pid}/roles/${roleId}`, { method: "DELETE" });

// --- Party addresses (link nested) ---
export const listPartyAddresses = (pid: string) => apiFetch<PartyAddressLink[]>(`${PARTY_BASE}/parties/${pid}/addresses`);
export const linkPartyAddress = (pid: string, body: { address_id: string; address_type: string; is_primary: boolean }) =>
  apiFetch<PartyAddressLink>(`${PARTY_BASE}/parties/${pid}/addresses`, { method: "POST", body: JSON.stringify(body) });
export const unlinkPartyAddress = (pid: string, linkId: string) =>
  apiFetch(`${PARTY_BASE}/parties/${pid}/addresses/${linkId}`, { method: "DELETE" });

// --- Addresses (directory) ---
export const listAddresses = (p: { q: string; sort: string; limit: number; cursor: string | null; filters: Record<string, string> }) =>
  apiFetch<ServerPage<Address>>(
    `${PARTY_BASE}/addresses?q=${encodeURIComponent(p.q)}&sort=${p.sort}&limit=${p.limit}` +
    (p.filters.country_id ? `&country_id=${p.filters.country_id}` : "") +
    (p.filters.active ? `&active=${p.filters.active}` : "") +
    (p.cursor ? `&cursor=${encodeURIComponent(p.cursor)}` : ""));

export const getAddress = (id: string) => apiFetch<Address>(`${PARTY_BASE}/addresses/${id}`);
export const createAddress = (body: Record<string, unknown>) =>
  apiFetch<Address>(`${PARTY_BASE}/addresses`, { method: "POST", body: JSON.stringify(body) });
export const updateAddress = (id: string, body: Record<string, unknown>, etag?: string) =>
  apiFetch<Address>(`${PARTY_BASE}/addresses/${id}`, {
    method: "PUT", headers: etag ? { "If-Match": etag } : undefined, body: JSON.stringify(body),
  });
export const deleteAddress = (id: string) => apiFetch(`${PARTY_BASE}/addresses/${id}`, { method: "DELETE" });
