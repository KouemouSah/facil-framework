"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { AuthCard } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { passwordField } from "@/lib/form-schemas";

function ResetForm() {
  const t = useTranslations("auth");
  const router = useRouter();
  const token = useSearchParams().get("token") || "";
  const [pw, setPw] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    // Mirror the server policy (check_strength / SEC-009: ≥12 + classes) so the
    // user gets an instant, specific message; the backend still enforces (422).
    const parsed = passwordField.safeParse(pw);
    if (!parsed.success) { setError(parsed.error.issues[0]?.message ?? ""); return; }
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/bff/api/v1/auth/password-reset/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: pw }),
      });
      if (res.ok) { router.replace("/login"); return; }
      if (res.status === 422) setError(t("reset.weak"));
      else if (res.status >= 500) setError(t("service_unavailable"));
      else setError(t("reset.invalid"));
    } catch {
      // Network/offline: never leave the button stuck in "Saving…" with no message.
      setError(t("network_error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard title={t("reset.title")} description={t("reset.subtitle")}>
      <form onSubmit={submit} className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="pw">{t("reset.new_password")}</Label>
          <Input id="pw" type="password" autoComplete="new-password" required
            value={pw} onChange={(e) => setPw(e.target.value)} />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" className="w-full" disabled={busy || !token}>
          {busy ? t("reset.saving") : t("reset.submit")}
        </Button>
      </form>
    </AuthCard>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetForm />
    </Suspense>
  );
}
