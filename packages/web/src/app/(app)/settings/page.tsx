"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

interface Branding {
  app_name: string;
  tagline: string;
  logo_url: string;
  logo_dark_url: string;
  favicon_url: string;
  login_background_url: string;
  primary_color: string;
  secondary_color: string;
  theme_mode: string;
  default_locale: string;
  support_email: string;
  support_url: string;
  supported_locales: string[];
}

export default function SettingsPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const [form, setForm] = useState<Branding | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const { data } = useQuery<Branding>({
    queryKey: ["admin-branding"],
    queryFn: () => apiFetch<Branding>(`/api/v1/admin/branding`),
  });

  useEffect(() => { if (data && !form) setForm(data); }, [data, form]);

  function set<K extends keyof Branding>(k: K, v: Branding[K]) {
    setForm((f) => (f ? { ...f, [k]: v } : f));
    setSaved(false);
  }

  const save = useMutation({
    mutationFn: () => {
      const { supported_locales: _omit, ...payload } = form as Branding;
      return apiFetch("/api/v1/admin/branding", { method: "PUT", body: JSON.stringify(payload) });
    },
    onSuccess: async () => {
      qc.invalidateQueries({ queryKey: ["admin-branding"] });
      qc.invalidateQueries({ queryKey: ["branding"] }); // app-shell name/logo
      setSaved(true);
      setError("");
      // Bust the cached server-side branding, then re-run the layout to re-theme.
      await fetch("/api/branding/revalidate", { method: "POST" }).catch(() => undefined);
      router.refresh();
    },
    onError: (e: Error) => setError(e.message || "Save failed"),
  });

  if (!form) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  const locales = form.supported_locales?.length ? form.supported_locales : ["en", "fr", "es"];

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Toolbar — fixed */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Branding</h1>
          <p className="text-sm text-muted-foreground">White-label the platform — applies live on save.</p>
        </div>
        <div className="flex items-center gap-2">
          {saved && <span className="flex items-center gap-1 text-sm text-emerald-600"><Check className="size-4" /> Saved</span>}
          <Button size="sm" disabled={save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </div>

      {/* Form region — the scrollable part */}
      <div className="min-h-0 flex-1 overflow-auto">
        <div className="grid max-w-3xl gap-6 pb-4">
          <Section title="Identity">
            <Field label="Application name">
              <Input value={form.app_name} onChange={(e) => set("app_name", e.target.value)} placeholder="Facil" />
            </Field>
            <Field label="Tagline">
              <Input value={form.tagline} onChange={(e) => set("tagline", e.target.value)} placeholder="Digital services platform" />
            </Field>
          </Section>

          <Section title="Colours">
            <ColorField label="Primary" value={form.primary_color} onChange={(v) => set("primary_color", v)} />
            <ColorField label="Secondary" value={form.secondary_color} onChange={(v) => set("secondary_color", v)} />
          </Section>

          <Section title="Assets (URLs)">
            <Field label="Logo"><Input value={form.logo_url} onChange={(e) => set("logo_url", e.target.value)} placeholder="https://…/logo.svg" /></Field>
            <Field label="Logo (dark)"><Input value={form.logo_dark_url} onChange={(e) => set("logo_dark_url", e.target.value)} placeholder="https://…/logo-dark.svg" /></Field>
            <Field label="Favicon"><Input value={form.favicon_url} onChange={(e) => set("favicon_url", e.target.value)} placeholder="https://…/favicon.ico" /></Field>
            <Field label="Login background"><Input value={form.login_background_url} onChange={(e) => set("login_background_url", e.target.value)} placeholder="https://…/bg.jpg" /></Field>
          </Section>

          <Section title="Locale & theme">
            <Field label="Default locale">
              <Select value={form.default_locale} onChange={(e) => set("default_locale", e.target.value)}>
                {locales.map((l) => <option key={l} value={l}>{l}</option>)}
              </Select>
            </Field>
            <Field label="Theme mode">
              <Select value={form.theme_mode} onChange={(e) => set("theme_mode", e.target.value)}>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
                <option value="auto">Auto</option>
              </Select>
            </Field>
          </Section>

          <Section title="Support">
            <Field label="Support email"><Input type="email" value={form.support_email} onChange={(e) => set("support_email", e.target.value)} placeholder="support@org.com" /></Field>
            <Field label="Support URL"><Input value={form.support_url} onChange={(e) => set("support_url", e.target.value)} placeholder="https://help.org.com" /></Field>
          </Section>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border p-4">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</p>
      <div className="grid gap-3 sm:grid-cols-2">{children}</div>
    </div>
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

function ColorField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  const valid = /^#[0-9a-fA-F]{6}$/.test(value);
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <div className="flex items-center gap-2">
        <input
          type="color"
          aria-label={`${label} colour`}
          className="h-9 w-12 cursor-pointer rounded-md border border-input bg-background p-1"
          value={valid ? value : "#000000"}
          onChange={(e) => onChange(e.target.value)}
        />
        <Input className="font-mono" value={value} onChange={(e) => onChange(e.target.value)} placeholder="#2563eb" />
      </div>
    </div>
  );
}
