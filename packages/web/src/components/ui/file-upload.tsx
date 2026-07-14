"use client";

import { useId, useRef, useState } from "react";
import Image from "next/image";
import { useTranslations } from "next-intl";
import { ImagePlus, Loader2, X } from "lucide-react";
import { uploadAsset, validateImageFile, isSameOriginAsset, UploadValidationError, IMAGE_ACCEPT } from "@/lib/upload";

/**
 * Secure image upload control (audit 1/2). Replaces the raw "paste a logo URL"
 * text field: pick or drag-drop → client pre-validation (allowlist + cap) → POST
 * to the authenticated `/api/assets/upload` route → the backend re-sniffs magic
 * bytes and returns a same-origin url stored in `value`. SVG is refused. The
 * preview renders through `next/image` (same-origin, optimizable). All strings
 * are i18n keys (namespace `upload`); errors are announced via `aria-live`.
 */
export interface FileUploadProps {
  /** Current asset URL (same-origin, e.g. `/api/v1/assets/<id>`), or empty. */
  value?: string;
  onUploaded: (url: string) => void;
  onRemove: () => void;
  maxSizeMB?: number;
  disabled?: boolean;
  /** SP1 D1 (org_unit/site document-identity overrides): the value this field
   *  would resolve to if left blank (e.g. the organization's own logo). When
   *  `value` is empty and this is set, the dropzone shows that image with an
   *  "inherited" caption instead of a bare empty state — a blank override
   *  must read as "inherit", never as "no logo at all". Purely additive:
   *  every existing caller that doesn't pass it keeps today's behaviour. */
  inheritedPreviewUrl?: string;
}

export function FileUpload({ value, onUploaded, onRemove, maxSizeMB, disabled, inheritedPreviewUrl }: FileUploadProps) {
  const t = useTranslations("upload");
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);

  const maxBytes = maxSizeMB ? maxSizeMB * 1024 * 1024 : undefined;

  async function handleFile(file: File) {
    setError("");
    const bad = validateImageFile(file, { maxBytes });
    if (bad) { setError(t(`errors.${bad}`)); return; }
    setBusy(true);
    try {
      const asset = await uploadAsset(file, { maxBytes });
      onUploaded(asset.url);
    } catch (e) {
      setError(e instanceof UploadValidationError ? t(`errors.${e.reason}`) : t("errors.failed"));
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = ""; // allow re-picking same file
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (disabled || busy) return;
    const file = e.dataTransfer.files?.[0];
    if (file) void handleFile(file);
  }

  return (
    <div className="space-y-1.5">
      {value ? (
        <div className="flex items-center gap-3 rounded-md border border-input bg-background p-2">
          <Image src={value} alt={t("preview_alt")} width={48} height={48}
            unoptimized={!isSameOriginAsset(value)}
            className="h-12 w-12 rounded object-contain" />
          <div className="ml-auto flex items-center gap-2">
            <button type="button" disabled={disabled || busy}
              onClick={() => inputRef.current?.click()}
              className="text-xs text-primary underline-offset-2 hover:underline disabled:opacity-50">
              {t("replace")}
            </button>
            <button type="button" disabled={disabled || busy} aria-label={t("remove")}
              onClick={onRemove}
              className="rounded p-1 text-muted-foreground hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50">
              <X className="size-4" />
            </button>
          </div>
        </div>
      ) : (
        <label htmlFor={inputId}
          onDragOver={(e) => { e.preventDefault(); if (!disabled && !busy) setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`flex min-h-[92px] cursor-pointer flex-col items-center justify-center gap-1 rounded-md border border-dashed px-3 py-4 text-center text-sm transition-colors ${
            dragging ? "border-primary bg-primary/5" : "border-input bg-background"
          } ${disabled || busy ? "cursor-not-allowed opacity-60" : "hover:bg-muted/50"}`}>
          {busy ? (
            <><Loader2 className="size-5 animate-spin text-muted-foreground" />
              <span className="text-muted-foreground">{t("uploading")}</span></>
          ) : inheritedPreviewUrl ? (
            <>
              <Image src={inheritedPreviewUrl} alt="" width={32} height={32}
                unoptimized={!isSameOriginAsset(inheritedPreviewUrl)}
                className="h-8 w-8 rounded object-contain opacity-70" />
              <span className="text-muted-foreground">{t("inherited")}</span>
              <span><span className="text-primary">{t("browse")}</span> {t("drop")}</span>
            </>
          ) : (
            <><ImagePlus className="size-5 text-muted-foreground" />
              <span><span className="text-primary">{t("browse")}</span> {t("drop")}</span>
              <span className="text-xs text-muted-foreground">{t("hint")}</span></>
          )}
        </label>
      )}

      <input ref={inputRef} id={inputId} type="file" className="sr-only"
        accept={IMAGE_ACCEPT.join(",")} disabled={disabled || busy}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) void handleFile(f); }} />

      {error && <p className="text-xs text-destructive" role="alert" aria-live="polite">{error}</p>}
    </div>
  );
}
