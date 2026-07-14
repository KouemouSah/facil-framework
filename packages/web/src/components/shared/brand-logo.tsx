import Image from "next/image";
import { cn } from "@/lib/utils";
import { isSameOriginAsset } from "@/lib/upload";

/**
 * White-label logo with automatic light/dark swap (Config-UI-first, Phase A2).
 * Renders the light logo hidden in dark mode and the dark logo (when a distinct
 * `dark` URL is provided) shown only in dark mode — pure CSS via Tailwind `dark:`
 * variants, reactive to the `.dark` class with no JS or theme hook. Falls back to
 * the light logo when no dark variant is set, and to a bundled default asset when
 * branding provides neither. Presentational (no hooks) → usable in BOTH the server
 * tree (auth layout) and the client tree (app-shell). The hidden variant is
 * `display:none`, so screen readers only ever announce the visible one.
 */
export function BrandLogo({
  light, dark, fallback, alt, width, height, className, priority,
}: {
  light?: string;
  dark?: string;
  fallback: string;
  alt: string;
  width: number;
  height: number;
  className?: string;
  priority?: boolean;
}) {
  const lightSrc = light || fallback;
  const hasDistinctDark = Boolean(dark) && dark !== light;
  return (
    <>
      <Image
        src={lightSrc}
        alt={alt}
        width={width}
        height={height}
        priority={priority}
        unoptimized={!isSameOriginAsset(lightSrc)}
        className={cn(className, hasDistinctDark && "dark:hidden")}
      />
      {hasDistinctDark && (
        // No `priority` on the dark variant: it is `display:none` in the default
        // (light) theme, so preloading it would waste an LCP-priority fetch on a
        // hidden image. The light variant carries the preload.
        <Image
          src={dark as string}
          alt={alt}
          width={width}
          height={height}
          unoptimized={!isSameOriginAsset(dark as string)}
          className={cn(className, "hidden dark:block")}
        />
      )}
    </>
  );
}
