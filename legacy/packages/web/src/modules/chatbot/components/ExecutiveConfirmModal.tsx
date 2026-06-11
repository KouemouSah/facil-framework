/**
 * ExecutiveConfirmModal — per-action consent for Level 3 agent tools.
 *
 * When the backend emits a `confirm_executive` action, MessageItem
 * dispatches it to this modal via the `onConfirmExecutive` callback.
 * The modal shows the human-readable summary of what the agent is
 * about to do, and on confirmation POSTs the confirmation_code to
 * `/chatbot/execute-confirmed`. The server validates the code in Redis
 * (single-use, 5min TTL) and runs the tool directly, bypassing Gemini.
 *
 * Design rationale (OWASP A04): a persistent "always allow" toggle for
 * executive actions (submit requests, book appointments) would be
 * dangerous — one grant would authorize every future legal action.
 * Per-action consent keeps the user in the loop for every irreversible
 * operation.
 */

'use client';

import { useState, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { AlertTriangle, Loader2 } from 'lucide-react';

interface ExecutiveConfirmModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  summary?: string;
  confirmationCode?: string;
  toolName?: string;
  /** Async handler that POSTs to /chatbot/execute-confirmed with the code. */
  onConfirm: (confirmationCode: string, toolName: string) => Promise<void>;
}

export function ExecutiveConfirmModal({
  open,
  onOpenChange,
  summary,
  confirmationCode,
  toolName,
  onConfirm,
}: ExecutiveConfirmModalProps) {
  const t = useTranslations('chatbot.executive');
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConfirm = useCallback(async () => {
    if (!confirmationCode || !toolName) return;
    setIsExecuting(true);
    setError(null);
    try {
      await onConfirm(confirmationCode, toolName);
      onOpenChange(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
    } finally {
      setIsExecuting(false);
    }
  }, [confirmationCode, toolName, onConfirm, onOpenChange]);

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" strokeWidth={1.5} />
            {t('confirmTitle')}
          </AlertDialogTitle>
          <AlertDialogDescription className="whitespace-pre-wrap text-left leading-relaxed">
            {summary || t('defaultSummary')}
          </AlertDialogDescription>
        </AlertDialogHeader>

        {error && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {error}
          </div>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel disabled={isExecuting}>
            {t('cancel')}
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={(e) => {
              e.preventDefault();
              void handleConfirm();
            }}
            disabled={isExecuting || !confirmationCode}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {isExecuting && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
            {t('confirmButton')}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
