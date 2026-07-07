"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Eye, EyeOff } from "lucide-react";
import { AuthCard } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { emailField, passwordField } from "@/lib/form-schemas";

export function RegisterForm() {
  const t = useTranslations("auth");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string; form?: string }>({});
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    // Mirror the backend (email regex + check_strength ≥12/classes) for instant
    // field-level feedback; the server still enforces and wins (422/409).
    const next: typeof errors = {};
    const em = emailField.safeParse(email);
    if (!em.success) next.email = em.error.issues[0]?.message;
    const pm = passwordField.safeParse(password);
    if (!pm.success) next.password = pm.error.issues[0]?.message;
    if (Object.keys(next).length) { setErrors(next); return; }

    setErrors({});
    setBusy(true);
    const res = await fetch("/api/bff/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, display_name: displayName || null }),
    }).catch(() => null);
    setBusy(false);

    if (res && res.ok) { setDone(true); return; }
    if (res && res.status === 409) setErrors({ email: t("register.email_taken") });
    else if (res && res.status === 422) setErrors({ password: t("reset.weak") });
    else setErrors({ form: t("register.failed") });
  }

  if (done) {
    return (
      <AuthCard title={t("register.title")}>
        <p className="text-sm text-muted-foreground">{t("register.success")}</p>
        <Link href="/login" className="mt-4 block text-center text-xs text-muted-foreground hover:text-foreground">
          {t("register.sign_in")}
        </Link>
      </AuthCard>
    );
  }

  return (
    <AuthCard title={t("register.title")} description={t("register.subtitle")}>
      <form onSubmit={submit} className="space-y-3" noValidate>
        <div className="space-y-1.5">
          <Label htmlFor="email">{t("register.email")}</Label>
          <Input id="email" type="email" autoComplete="email" required
            value={email} onChange={(e) => setEmail(e.target.value)} />
          {errors.email && <p className="text-xs text-destructive">{errors.email}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="dn">{t("register.display_name")}</Label>
          <Input id="dn" autoComplete="name"
            value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="pw">{t("register.password")}</Label>
          <div className="relative">
            <Input id="pw" type={showPw ? "text" : "password"} autoComplete="new-password" required
              className="pr-9" value={password} onChange={(e) => setPassword(e.target.value)} />
            <button type="button" tabIndex={-1}
              onClick={() => setShowPw((v) => !v)}
              aria-label={showPw ? t("hide_password") : t("show_password")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
              {showPw ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
          {errors.password && <p className="text-xs text-destructive">{errors.password}</p>}
        </div>
        {errors.form && <p className="text-sm text-destructive">{errors.form}</p>}
        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? t("register.creating") : t("register.submit")}
        </Button>
      </form>
      <p className="mt-4 text-center text-xs text-muted-foreground">
        {t("register.have_account")}{" "}
        <Link href="/login" className="hover:text-foreground">{t("register.sign_in")}</Link>
      </p>
    </AuthCard>
  );
}
