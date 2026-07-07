"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { MailWarning, X } from "lucide-react";
import { useSession } from "@/lib/use-session";
import { needsEmailVerification } from "@/lib/session-schema";
import { Button } from "@/components/ui/button";

/**
 * In-app nudge (P7, audit 15) replacing the dead login "Verify email" link: a
 * signed-in account whose email is unverified gets a dismissible strip with a
 * one-click resend (`POST /auth/email-verification/request`, authed via the BFF).
 * Renders nothing for verified accounts, break-glass, NIU-only, or unknown state
 * (see `needsEmailVerification`).
 */
export function EmailVerifyBanner() {
  const t = useTranslations("auth.banner");
  const { data: session } = useSession();
  const [dismissed, setDismissed] = useState(false);
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");

  if (dismissed || !session || !needsEmailVerification(session)) return null;

  async function resend() {
    setState("sending");
    // Distinguish failure (network, 429 rate-limit, 401/5xx) from success so a
    // rate-limited or offline resend doesn't look like it silently worked.
    const res = await fetch("/api/bff/api/v1/auth/email-verification/request", {
      method: "POST",
    }).catch(() => null);
    setState(res && res.ok ? "sent" : "error");
  }

  return (
    <div className="flex items-center gap-3 border-b bg-amber-500/10 px-5 py-2 text-sm text-amber-700 dark:text-amber-400">
      <MailWarning className="size-4 shrink-0" />
      <span>{t("message")}</span>
      <div className="ml-auto flex items-center gap-2">
        {state === "sent" ? (
          <span className="text-xs">{t("sent")}</span>
        ) : (
          <>
            {state === "error" && <span className="text-xs">{t("error")}</span>}
            <Button size="sm" variant="outline" className="h-7"
              disabled={state === "sending"} onClick={resend}>
              {state === "sending" ? t("sending") : t("resend")}
            </Button>
          </>
        )}
        <button type="button" onClick={() => setDismissed(true)} aria-label={t("dismiss")}
          className="text-amber-700/70 hover:text-amber-700 dark:text-amber-400/70 dark:hover:text-amber-400">
          <X className="size-4" />
        </button>
      </div>
    </div>
  );
}
