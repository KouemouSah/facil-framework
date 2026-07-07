"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { AuthCard } from "@/components/shared";

function Verify() {
  const t = useTranslations("auth");
  const token = useSearchParams().get("token") || "";
  const [state, setState] = useState<"idle" | "ok" | "error">("idle");

  useEffect(() => {
    if (!token) return;
    fetch("/api/bff/api/v1/auth/email-verification/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    })
      .then((r) => setState(r.ok ? "ok" : "error"))
      .catch(() => setState("error"));
  }, [token]);

  return (
    <AuthCard title={t("verify.title")}>
      <div className="space-y-3 text-sm">
        {!token && <p className="text-muted-foreground">{t("verify.open_link")}</p>}
        {state === "ok" && <p className="text-foreground">{t("verify.ok")} ✓</p>}
        {state === "error" && <p className="text-destructive">{t("verify.error")}</p>}
        {state === "idle" && token && <p className="text-muted-foreground">{t("verify.verifying")}</p>}
        <Link href="/login" className="block text-xs text-muted-foreground hover:text-foreground">
          {t("verify.continue")}
        </Link>
      </div>
    </AuthCard>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <Verify />
    </Suspense>
  );
}
