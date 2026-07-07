"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { confirmTextMatches } from "@/lib/confirm";

/**
 * Confirmation gate for destructive/irreversible actions (audit 3): delete, and
 * "suspend → revokes sessions". Replaces the raw click / `window.confirm`. For
 * high-impact targets pass `requireText` (e.g. the record code) — the confirm
 * button stays disabled until it is typed exactly. Initial focus lands on Cancel
 * (safe default), and the action button is styled `destructive` when `danger`.
 * Controlled: the parent owns `open` and typically flips `busy` while awaiting.
 */
export interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: React.ReactNode;
  body?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Destructive styling on the confirm button. */
  danger?: boolean;
  /** If set, the operator must type this exact value to enable confirm. */
  requireText?: string;
  /** Disables both buttons and shows a working state (in-flight action). */
  busy?: boolean;
  onConfirm: () => void | Promise<void>;
  onCancel?: () => void;
}

export function ConfirmDialog({
  open, onOpenChange, title, body, confirmLabel, cancelLabel,
  danger, requireText, busy, onConfirm, onCancel,
}: ConfirmDialogProps) {
  const t = useTranslations("confirm");
  const [typed, setTyped] = useState("");
  const cancelRef = useRef<HTMLButtonElement>(null);

  // Fresh gate each time the dialog opens (never carry a stale typed value).
  useEffect(() => { if (open) setTyped(""); }, [open]);

  const canConfirm = confirmTextMatches(requireText, typed) && !busy;

  function cancel() {
    onCancel?.();
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o && !busy) cancel(); }}>
      <DialogContent
        onOpenAutoFocus={(e) => { e.preventDefault(); cancelRef.current?.focus(); }}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {body && <DialogDescription>{body}</DialogDescription>}
        </DialogHeader>

        {requireText && (
          <div className="space-y-1.5">
            <Label htmlFor="confirm-text">{t("type_to_confirm", { value: requireText })}</Label>
            <Input id="confirm-text" value={typed} autoComplete="off"
              spellCheck={false} disabled={busy}
              onChange={(e) => setTyped(e.target.value)} />
          </div>
        )}

        <DialogFooter>
          <Button ref={cancelRef} type="button" variant="ghost" size="sm"
            onClick={cancel} disabled={busy}>
            {cancelLabel ?? t("cancel")}
          </Button>
          <Button type="button" size="sm" variant={danger ? "destructive" : "default"}
            disabled={!canConfirm} onClick={() => void onConfirm()}>
            {busy ? t("working") : (confirmLabel ?? t("confirm"))}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
