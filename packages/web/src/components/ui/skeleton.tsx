import * as React from "react";
import { cn } from "@/lib/utils";

/** Loading placeholder. Theme-aware (bg-muted), aria-hidden (decorative).
 *  Compose with h-* / w-* utilities for the shape of the content it replaces. */
export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-testid="skeleton"
      aria-hidden
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  );
}
