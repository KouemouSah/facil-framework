import { getTranslations } from "next-intl/server";
import { Skeleton } from "@/components/ui/skeleton";

// Route-level loading fallback for the (app) segment — preserves the shell layout
// (toolbar + table) instead of a blank flash, per the "fixed shell" doctrine. A
// visually-hidden status text gives screen readers something to announce (the
// skeletons themselves are aria-hidden).
export default async function Loading() {
  const t = await getTranslations("common");
  return (
    <div className="flex h-full flex-col gap-4" aria-busy="true">
      <span className="sr-only" role="status">{t("loading")}</span>
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-72" />
        </div>
        <Skeleton className="h-9 w-28" />
      </div>
      <div className="min-h-0 flex-1 space-y-2">
        <Skeleton className="h-10 w-full" />
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    </div>
  );
}
