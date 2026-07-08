"use client";

import { useState, useTransition } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Check, Languages } from "lucide-react";
import { cn } from "@/lib/utils";
import { LOCALE_COOKIE } from "@/i18n/request";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

// Language names are shown in their OWN language (convention — never translated).
const NATIVE: Record<string, string> = { en: "English", fr: "Français", es: "Español" };

/**
 * Language switcher (P2.3). Writes the `NEXT_LOCALE` cookie (read by
 * `i18n/request.ts`) and refreshes so the server components re-render in the new
 * locale. Only the deployment's `supported_locales` are offered; hidden when
 * there's nothing to switch to. Built on the shared Popover primitive.
 */
export function LocaleSwitcher({ supported }: { supported: string[] }) {
  const t = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [, startTransition] = useTransition();

  const options = supported.filter((l) => l in NATIVE);
  if (options.length < 2) return null;

  function choose(next: string) {
    // 1-year cookie; SameSite=Lax so it rides top-level navigations.
    document.cookie = `${LOCALE_COOKIE}=${next};path=/;max-age=31536000;samesite=lax`;
    setOpen(false);
    startTransition(() => router.refresh());
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={t("language")}
          title={t("language")}
          className="inline-flex h-9 items-center gap-1.5 rounded-md px-2 text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Languages className="size-4" />
          <span className="uppercase">{locale}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-44">
        {options.map((l) => (
          <button
            key={l}
            type="button"
            onClick={() => choose(l)}
            className={cn(
              "flex w-full items-center justify-between rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent",
              l === locale && "font-medium",
            )}
          >
            {NATIVE[l]}
            {l === locale && <Check className="size-3.5 text-primary" />}
          </button>
        ))}
      </PopoverContent>
    </Popover>
  );
}
