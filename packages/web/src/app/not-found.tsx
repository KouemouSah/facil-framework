import Link from "next/link";
import { useTranslations } from "next-intl";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// 404 boundary (App Router). Rendered INSIDE the root layout, so the i18n provider
// is available (useTranslations works in this Server Component). No client JS needed.
export default function NotFound() {
  const t = useTranslations("not_found");
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-6 text-center">
      <p className="text-5xl font-semibold tracking-tight text-muted-foreground">404</p>
      <div className="space-y-1">
        <h1 className="text-lg font-semibold">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("body")}</p>
      </div>
      <Link href="/" className={cn(buttonVariants({ variant: "default" }))}>
        {t("back")}
      </Link>
    </div>
  );
}
