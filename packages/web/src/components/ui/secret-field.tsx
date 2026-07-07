"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Eye, EyeOff, Copy, Check, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * Display a sensitive value (federation client secret, API key) — audit 4. Masked
 * by default (never shown in cleartext until the operator reveals it), with a
 * copy-to-clipboard action and an optional "Regenerate". Read-only: a generated
 * secret is shown, not edited. The value still lives in the DOM (masked), so this
 * is for authorized admin surfaces only — the backend never returns it to the
 * browser except right after generation (one-shot), which the caller controls.
 */
export interface SecretFieldProps {
  value: string;
  label?: string;
  onRegenerate?: () => void;
  disabled?: boolean;
}

export function SecretField({ value, label, onRegenerate, disabled }: SecretFieldProps) {
  const t = useTranslations("secret");
  const [revealed, setRevealed] = useState(false);
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard blocked (insecure context / permission) — reveal so the
      // operator can select-copy manually rather than failing silently.
      setRevealed(true);
    }
  }

  return (
    <div className="space-y-1.5">
      {label && <Label>{label}</Label>}
      <div className="flex items-center gap-2">
        <Input readOnly value={value} type={revealed ? "text" : "password"}
          className="font-mono" onFocus={(e) => e.currentTarget.select()} />
        <Button type="button" variant="ghost" size="sm" disabled={disabled}
          aria-label={revealed ? t("hide") : t("reveal")}
          aria-pressed={revealed} onClick={() => setRevealed((r) => !r)}>
          {revealed ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </Button>
        <Button type="button" variant="ghost" size="sm" disabled={disabled}
          aria-label={copied ? t("copied") : t("copy")} onClick={copy}>
          {copied ? <Check className="size-4 text-emerald-600" /> : <Copy className="size-4" />}
        </Button>
        {onRegenerate && (
          <Button type="button" variant="outline" size="sm" disabled={disabled}
            onClick={onRegenerate}>
            <RefreshCw className="size-4" /> {t("regenerate")}
          </Button>
        )}
      </div>
    </div>
  );
}
