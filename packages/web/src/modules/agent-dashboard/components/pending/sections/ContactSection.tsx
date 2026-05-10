/**
 * ContactSection - Compact contact info card
 *
 * @module agent-dashboard/components/pending/sections
 * @date 2026-01-26
 * @updated 2026-03-06 - Compact layout for side-by-side display
 */

'use client';

import React from 'react';
import { useTranslations } from 'next-intl';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Mail, Phone, Copy, User } from 'lucide-react';
import { toast } from 'sonner';

interface ContactSectionProps {
  name: string;
  email?: string | null;
  phone?: string | null;
}

export function ContactSection({ name: _name, email, phone }: ContactSectionProps) {
  const t = useTranslations('agent.pending.preview');

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copiado`);
  };

  return (
    <Card>
      <CardContent className="p-3">
        <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5 flex items-center gap-1">
          <User className="h-3 w-3" />
          {t('contact')}
        </p>
        <div className="space-y-1">
          {email && (
            <div className="flex items-center gap-1.5 group">
              <Mail className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <a href={`mailto:${email}`} className="text-sm text-blue-600 hover:underline truncate">
                {email}
              </a>
              <Button
                variant="ghost"
                size="icon"
                className="h-5 w-5 opacity-0 group-hover:opacity-100 shrink-0"
                onClick={() => copyToClipboard(email, 'Email')}
              >
                <Copy className="h-2.5 w-2.5" />
              </Button>
            </div>
          )}
          {phone && (
            <div className="flex items-center gap-1.5 group">
              <Phone className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <a href={`tel:${phone}`} className="text-sm text-blue-600 hover:underline">
                {phone}
              </a>
              <Button
                variant="ghost"
                size="icon"
                className="h-5 w-5 opacity-0 group-hover:opacity-100 shrink-0"
                onClick={() => copyToClipboard(phone, 'Tel')}
              >
                <Copy className="h-2.5 w-2.5" />
              </Button>
            </div>
          )}
          {!email && !phone && (
            <p className="text-xs text-muted-foreground">{t('noContactInfo')}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default ContactSection;
