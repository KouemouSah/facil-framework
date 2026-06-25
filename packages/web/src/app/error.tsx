"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";

// Segment error boundary (App Router). Catches render/runtime errors BELOW the
// root layout — the i18n provider (mounted in the root layout) is still available,
// so copy is translated. `digest` is the only server-error detail exposed (no stack
// leak). The root-level fallback when the layout itself throws is `global-error.tsx`.
export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const t = useTranslations("errors");

  useEffect(() => {
    // Hook point for client telemetry (Sentry, optional). Avoid logging PII.
    if (process.env.NODE_ENV !== "production") console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[50vh] items-center justify-center p-6">
      <div className="w-full max-w-md space-y-4">
        <Banner variant="error" title={t("title")}>
          {t("body")}
          {error.digest && <span className="mt-1 block font-mono text-xs">ref: {error.digest}</span>}
        </Banner>
        <div className="flex gap-2">
          <Button onClick={reset}>{t("retry")}</Button>
          <Button variant="outline" onClick={() => window.location.reload()}>{t("reload")}</Button>
        </div>
      </div>
    </div>
  );
}
