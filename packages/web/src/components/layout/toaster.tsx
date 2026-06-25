"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from "@/components/ui/toast";
import {
  dismissToast,
  subscribeToasts,
  type ToastItem,
  type ToastState,
  type ToastVariant,
} from "@/lib/toast";

// Bridges the framework-agnostic toast store to Radix Toast. Mounted once in the
// root layout. Errors stay until dismissed; others auto-close.
const DURATION: Record<ToastVariant, number> = {
  default: 4000,
  success: 4000,
  warning: 6000,
  error: Infinity, // require explicit dismiss for failures
};

export function Toaster() {
  const tc = useTranslations("common");
  const [state, setState] = useState<ToastState>({ toasts: [] });

  useEffect(() => subscribeToasts(setState), []);

  return (
    <ToastProvider swipeDirection="right">
      {state.toasts.map((t: ToastItem) => (
        <Toast
          key={t.id}
          variant={t.variant}
          duration={DURATION[t.variant]}
          onOpenChange={(open) => {
            if (!open) dismissToast(t.id);
          }}
        >
          <div className="min-w-0 flex-1">
            <ToastTitle>{t.title}</ToastTitle>
            {t.description && <ToastDescription>{t.description}</ToastDescription>}
          </div>
          <ToastClose aria-label={tc("close")} />
        </Toast>
      ))}
      <ToastViewport />
    </ToastProvider>
  );
}
