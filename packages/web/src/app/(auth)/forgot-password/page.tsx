"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { AuthCard } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function ForgotPasswordPage() {
  const t = useTranslations("auth");
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    // Always succeeds from the user's POV (anti-enumeration, same as the backend).
    await fetch("/api/bff/api/v1/auth/password-reset/request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    }).catch(() => undefined);
    setSent(true);
    setBusy(false);
  }

  return (
    <AuthCard title={t("forgot_page.title")} description={t("forgot_page.subtitle")}>
      {sent ? (
        <p className="text-sm text-muted-foreground">{t("forgot_page.sent", { email })}</p>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="email">{t("forgot_page.email")}</Label>
            <Input id="email" type="email" required value={email}
              onChange={(e) => setEmail(e.target.value)} />
          </div>
          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? t("forgot_page.sending") : t("forgot_page.submit")}
          </Button>
        </form>
      )}
      <Link href="/login" className="mt-4 block text-center text-xs text-muted-foreground hover:text-foreground">
        {t("forgot_page.back")}
      </Link>
    </AuthCard>
  );
}
