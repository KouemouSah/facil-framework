"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Eye, EyeOff } from "lucide-react";
import { AuthCard } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const OIDC_ENABLED = process.env.NEXT_PUBLIC_OIDC_ENABLED === "1";

export function LoginForm({ selfRegistration }: { selfRegistration: boolean }) {
  const t = useTranslations("auth");
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/";
  const expired = params.has("next"); // arrived here from a 401 redirect

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [totp, setTotp] = useState("");
  const [needTotp, setNeedTotp] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Send first-run operators to the installer instead of a dead login.
  useEffect(() => {
    fetch("/api/bff/api/v1/system/install-status")
      .then((r) => r.json())
      .then((s) => { if (!s.installed) router.replace("/install"); })
      .catch(() => undefined);
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, password, totp_code: totp || undefined }),
      });
      const data = await res.json().catch(() => ({}));
      if (data.totp_required) {
        setNeedTotp(true);
        setError("");
      } else if (res.ok) {
        router.replace(next);
      } else if (res.status === 423) {
        setError(t("locked"));
      } else if (res.status >= 500) {
        // A backend outage isn't "wrong password" — don't mislead the user.
        setError(t("service_unavailable"));
      } else {
        setError(t("invalid_credentials"));
      }
    } catch {
      // fetch rejected (offline / connection reset): surface it, never fail silent.
      setError(t("network_error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard title={t("sign_in_title")} description={t("sign_in_subtitle")}>
      {expired && (
        <p className="mb-4 rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
          {t("session_expired")}
        </p>
      )}
      <form onSubmit={submit} className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="identifier">{t("identifier")}</Label>
          <Input id="identifier" autoComplete="username" required
            value={identifier} onChange={(e) => setIdentifier(e.target.value)}
            disabled={needTotp} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">{t("password")}</Label>
          <div className="relative">
            <Input id="password" type={showPw ? "text" : "password"} autoComplete="current-password"
              required className="pr-9"
              value={password} onChange={(e) => setPassword(e.target.value)}
              disabled={needTotp} />
            <button type="button" tabIndex={-1}
              onClick={() => setShowPw((v) => !v)}
              aria-label={showPw ? t("hide_password") : t("show_password")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground disabled:opacity-50"
              disabled={needTotp}>
              {showPw ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
        </div>
        {needTotp && (
          <div className="space-y-1.5">
            <Label htmlFor="totp">{t("totp")}</Label>
            {/* Not restricted to 6 digits: the field also accepts backup codes. */}
            <Input id="totp" inputMode="numeric" autoComplete="one-time-code" autoFocus
              placeholder={t("totp_placeholder")}
              value={totp} onChange={(e) => setTotp(e.target.value)} />
          </div>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? t("signing_in") : t("login")}
        </Button>
      </form>

      {OIDC_ENABLED && (
        <Button asChild variant="outline" className="mt-3 w-full">
          <a href="/api/auth/oidc/start">{t("sso")}</a>
        </Button>
      )}

      <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
        <Link href="/forgot-password" className="hover:text-foreground">{t("forgot")}</Link>
        {selfRegistration && (
          <Link href="/register" className="hover:text-foreground">{t("create_account")}</Link>
        )}
      </div>
    </AuthCard>
  );
}
