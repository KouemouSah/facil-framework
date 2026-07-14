"use client";

import { useState } from "react";
import Image from "next/image";
import { useTranslations } from "next-intl";
import { isSameOriginAsset } from "@/lib/upload";
import { buildDocumentPreviewModel, previewAspectRatio,
  type PreviewFormat, type ResolvedIssuerIdentity } from "./document-preview";

/** Ghost-body line widths (%) — a fixed, deterministic pattern (not random,
 *  so the preview doesn't jitter on every re-render) simulating printed body
 *  text without pretending to render a real document. */
const GHOST_LINES = [95, 88, 92, 60, 0, 90, 84, 96, 70, 0, 82, 91];

/**
 * Live, non-contractual A4/A5 preview of the resolved issuer identity
 * (SP1 debt D1) — pure HTML/CSS, no PDF/canvas. The sheet is a flex column
 * (header / ghost body / footer); its `aspect-ratio` is driven entirely by
 * `previewAspectRatio(format)`, so switching format RESIZES the sheet.
 *
 * That resize is the whole mechanism — it is NOT a text reflow: every
 * header/footer `<p>` uses `truncate` (single line, ellipsis, never wraps
 * to a second line) and the footer is always a vertical stack
 * (`space-y-0.5`), in every format. What visibly changes between formats is
 * the ghost body — its container is `overflow-hidden`, so as the sheet's
 * computed height shrinks or grows with the aspect ratio, fewer or more of
 * the fixed-width `GHOST_LINES` are visible, clipped by the browser's box
 * model rather than repositioned by hand. That is the visual proof of the
 * document engine's architecture (CSS flow, not a positional canvas).
 */
export function DocumentPreviewSheet({ values, resolved }: {
  values: Record<string, string>;
  resolved: ResolvedIssuerIdentity | undefined;
}) {
  const t = useTranslations("organizations.documentIdentity.preview");
  const [format, setFormat] = useState<PreviewFormat>("a4-portrait");
  const model = buildDocumentPreviewModel(values, resolved, format);
  const [size, orientation] = format.split("-") as ["a4" | "a5", "portrait" | "landscape"];

  return (
    <div className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{t("title")}</h3>
        <div className="flex items-center gap-1.5">
          <label htmlFor="doc-preview-size" className="sr-only">{t("size_label")}</label>
          <select id="doc-preview-size" value={size}
            onChange={(e) => setFormat(`${e.target.value as "a4" | "a5"}-${orientation}`)}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <option value="a4">A4</option>
            <option value="a5">A5</option>
          </select>
          <label htmlFor="doc-preview-orientation" className="sr-only">{t("orientation_label")}</label>
          <select id="doc-preview-orientation" value={orientation}
            onChange={(e) => setFormat(`${size}-${e.target.value as "portrait" | "landscape"}`)}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <option value="portrait">{t("portrait")}</option>
            <option value="landscape">{t("landscape")}</option>
          </select>
        </div>
      </div>

      {/* `role="img"` + accessible name: informative but not interactive — a
          screen reader announces it once and moves on, never trapping focus. */}
      <div
        role="img"
        aria-label={t("aria_label")}
        style={{ aspectRatio: previewAspectRatio(format) }}
        className="mx-auto flex w-full max-w-md flex-col overflow-hidden rounded-sm border bg-white text-neutral-900 shadow-sm transition-[aspect-ratio] motion-reduce:transition-none">
        <header className="flex shrink-0 flex-wrap items-start justify-between gap-2 border-b border-neutral-200 p-3">
          {model.logoUrl ? (
            <Image src={model.logoUrl} alt="" width={40} height={40} unoptimized={!isSameOriginAsset(model.logoUrl)}
              className="h-10 w-10 shrink-0 object-contain" />
          ) : (
            <div className="h-10 w-10 shrink-0 rounded bg-neutral-100" aria-hidden />
          )}
          <div className="min-w-0 flex-1 text-right">
            <p className="truncate text-sm font-semibold">{model.legalName || t("placeholder.legal_name")}</p>
            <p className="truncate text-[10px] text-neutral-500">
              {[model.taxId, model.registrationNumber].filter(Boolean).join(" · ")}
            </p>
            {model.shortCode && <p className="truncate text-[10px] text-neutral-400">{model.shortCode}</p>}
          </div>
        </header>

        {model.headerNote && (
          <p className="shrink-0 border-b border-neutral-100 px-3 py-1.5 text-[10px] text-neutral-500">
            {model.headerNote}
          </p>
        )}

        {/* Ghost body — ERP convention for "this is a layout preview, not real
            content": ratio lines only, never lorem ipsum. */}
        <div className="min-h-0 flex-1 space-y-2 overflow-hidden p-3">
          {GHOST_LINES.map((w, i) => (
            w === 0
              ? <div key={i} className="h-2" aria-hidden />
              : <div key={i} className="h-2 rounded-full bg-neutral-100" style={{ width: `${w}%` }} aria-hidden />
          ))}
        </div>

        <footer className="flex shrink-0 flex-wrap items-end justify-between gap-2 border-t border-neutral-200 p-3">
          <div className="min-w-0 flex-1 space-y-0.5 text-[9px] text-neutral-500">
            {model.footerNote && <p className="truncate">{model.footerNote}</p>}
            {model.contactLine && <p className="truncate">{model.contactLine}</p>}
            {model.legalMentions && <p className="line-clamp-2">{model.legalMentions.replace(/<[^>]+>/g, " ")}</p>}
          </div>
          {model.sealUrl && (
            <Image src={model.sealUrl} alt="" width={28} height={28} unoptimized={!isSameOriginAsset(model.sealUrl)}
              className="h-7 w-7 shrink-0 object-contain" />
          )}
        </footer>
      </div>
      <p className="text-center text-xs text-muted-foreground">{t("caption")}</p>
    </div>
  );
}
