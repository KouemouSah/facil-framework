/**
 * AgentOnboarding - First-visit dialog for the Documents vault
 *
 * Shows a brief welcome with 4 feature highlights on the first time
 * a user navigates to the "Mes Documents" page. Once dismissed, a
 * localStorage flag (`vault_onboarding_seen`) prevents re-display.
 *
 * Uses shadcn/ui Dialog + Lucide icons. Fully i18n-aware via
 * the `userDocuments.onboarding` translation namespace.
 *
 * @module user-documents/components
 */

'use client';

import { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { FolderOpen, Brain, Bell, Shield } from 'lucide-react';

const STORAGE_KEY = 'vault_onboarding_seen';

interface FeatureItemProps {
  icon: React.ReactNode;
  text: string;
}

function FeatureItem({ icon, text }: FeatureItemProps) {
  return (
    <li className="flex items-start gap-3">
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
        {icon}
      </span>
      <span className="text-sm text-muted-foreground leading-relaxed">{text}</span>
    </li>
  );
}

export function AgentOnboarding() {
  const t = useTranslations('userDocuments.onboarding');
  const [open, setOpen] = useState(false);

  // Check localStorage on mount (client-only)
  useEffect(() => {
    try {
      const seen = localStorage.getItem(STORAGE_KEY);
      if (!seen) {
        setOpen(true);
      }
    } catch {
      // localStorage unavailable (SSR, incognito with storage blocked, etc.)
    }
  }, []);

  function handleClose() {
    setOpen(false);
    try {
      localStorage.setItem(STORAGE_KEY, '1');
    } catch {
      // Silently ignore storage errors
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleClose(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-lg">{t('title')}</DialogTitle>
          <DialogDescription className="text-sm">
            {t('description')}
          </DialogDescription>
        </DialogHeader>

        <ul className="my-4 space-y-4">
          <FeatureItem
            icon={<FolderOpen className="h-4 w-4" strokeWidth={1.5} />}
            text={t('feature1')}
          />
          <FeatureItem
            icon={<Brain className="h-4 w-4" strokeWidth={1.5} />}
            text={t('feature2')}
          />
          <FeatureItem
            icon={<Bell className="h-4 w-4" strokeWidth={1.5} />}
            text={t('feature3')}
          />
          <FeatureItem
            icon={<Shield className="h-4 w-4" strokeWidth={1.5} />}
            text={t('feature4')}
          />
        </ul>

        <Button onClick={handleClose} className="w-full">
          {t('start')}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
