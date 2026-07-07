import { describe, it, expect } from "vitest";
import { providersToMap, routingToProviders, validateRouting, type NamedProvider } from "./routing";
import type { RoutingView } from "./api";

const VIEW: RoutingView = {
  routing: { public_chat: "ollama_public", agent_backend: "cloud_x", embedding: "ollama_embed" },
  providers: {
    ollama_public: { kind: "ollama", endpoint: "http://ollama:11434", model: "gemma4:e4b" },
    cloud_x: { kind: "openai_compat", endpoint: "https://api.x/v1", model: "gpt-4o", api_key_secret: "X_KEY" },
  },
};

describe("routingToProviders", () => {
  it("expands the ai.providers map into an editable list with all fields", () => {
    const list = routingToProviders(VIEW);
    expect(list).toHaveLength(2);
    expect(list[0]).toEqual({ name: "ollama_public", kind: "ollama", endpoint: "http://ollama:11434", model: "gemma4:e4b", api_key_secret: "" });
    expect(list[1].api_key_secret).toBe("X_KEY");
  });
  it("handles an undefined view", () => {
    expect(routingToProviders(undefined)).toEqual([]);
  });
});

describe("providersToMap", () => {
  it("rebuilds the map, trimming names and dropping empty rows", () => {
    const list: NamedProvider[] = [
      { name: " a ", kind: "ollama", endpoint: "e", model: "m", api_key_secret: "" },
      { name: "", kind: "ollama", endpoint: "", model: "", api_key_secret: "" },
    ];
    const map = providersToMap(list);
    expect(Object.keys(map)).toEqual(["a"]);
    expect(map.a).toEqual({ kind: "ollama", endpoint: "e", model: "m", api_key_secret: "" });
  });
});

describe("validateRouting", () => {
  const p = (name: string): NamedProvider => ({ name, kind: "ollama", endpoint: "", model: "", api_key_secret: "" });
  it("passes when names are unique and every routed role is known or blank", () => {
    expect(validateRouting([p("a"), p("b")], { public_chat: "a", embedding: "" })).toBeNull();
  });
  it("rejects duplicate names", () => {
    expect(validateRouting([p("a"), p("a")], {})).toBe("duplicate_name");
  });
  it("rejects a role pointing at an unknown provider", () => {
    expect(validateRouting([p("a")], { public_chat: "ghost" })).toBe("unknown_ref");
  });
});
