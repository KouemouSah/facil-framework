import type { RoutingView } from "./api";

export const ROUTING_ROLES = ["public_chat", "agent_backend", "embedding"] as const;
export type RoutingRole = (typeof ROUTING_ROLES)[number];

// LLM provider kinds (the registered llm provider_codes).
export const LLM_KINDS = ["ollama", "openai_compat"] as const;

/** An editable named provider (ai.providers[name]). `api_key_secret` is a secret
 *  REFERENCE (a name in the secret store), never the key itself. */
export interface NamedProvider {
  name: string;
  kind: string;
  endpoint: string;
  model: string;
  api_key_secret: string;
}

/** Resolved routing view (GET /llm/routing) → editable named-provider list. */
export function routingToProviders(view: RoutingView | undefined): NamedProvider[] {
  return Object.entries(view?.providers ?? {}).map(([name, d]) => ({
    name,
    kind: d.kind ?? "",
    endpoint: d.endpoint ?? "",
    model: d.model ?? "",
    api_key_secret: d.api_key_secret ?? "",
  }));
}

/** Editable list → the `ai.providers` map (empty-named rows dropped, names trimmed). */
export function providersToMap(list: NamedProvider[]): Record<string, Record<string, string>> {
  const out: Record<string, Record<string, string>> = {};
  for (const p of list) {
    const name = p.name.trim();
    if (!name) continue;
    out[name] = {
      kind: p.kind,
      endpoint: p.endpoint,
      model: p.model,
      api_key_secret: p.api_key_secret,
    };
  }
  return out;
}

/** Validate before save: unique non-empty names, and every routed role points at a
 *  known provider (or is left blank). Returns an error code or null. */
export function validateRouting(
  list: NamedProvider[], routing: Record<string, string>,
): "duplicate_name" | "unknown_ref" | null {
  const names = list.map((p) => p.name.trim()).filter(Boolean);
  if (new Set(names).size !== names.length) return "duplicate_name";
  for (const role of Object.keys(routing)) {
    const ref = routing[role];
    if (ref && !names.includes(ref)) return "unknown_ref";
  }
  return null;
}
