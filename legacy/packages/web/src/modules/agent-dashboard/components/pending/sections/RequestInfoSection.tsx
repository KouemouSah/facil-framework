/**
 * RequestInfoSection - Compact header combining request info + contact
 * Single card: Row 1 (ref + badges + SLA), Row 2 (tramite + contact)
 *
 * @module agent-dashboard/components/pending/sections
 * @date 2026-01-26
 * @updated 2026-03-07 - Merged ContactSection, removed redundant ESTADO column
 */

'use client';

import React from 'react';
import { useLocale, useTranslations } from 'next-intl';
import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Clock, AlertTriangle, AlertCircle, Baby, FileStack, Mail, Phone, Copy } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import type { Priority, SlaStatus } from '../../../services/agent-requests-api';

// =============================================================================
// PROPS
// =============================================================================

interface RequestInfoSectionProps {
  reference: string;
  workflowLabel: string;
  solicitudType: string;
  motivo?: string | null;
  priority: Priority;
  slaStatus: SlaStatus;
  slaRemainingHours?: number | null;
  isMinor: boolean;
  batchReference?: string | null;
  batchId?: string | null;
  // Contact fields (merged from ContactSection)
  contactEmail?: string | null;
  contactPhone?: string | null;
}

// =============================================================================
// HELPERS
// =============================================================================

const PRIORITY_STYLES: Record<Priority, { bg: string; text: string }> = {
  URGENT: { bg: 'bg-red-100', text: 'text-red-700' },
  HIGH: { bg: 'bg-orange-100', text: 'text-orange-700' },
  NORMAL: { bg: 'bg-blue-100', text: 'text-blue-700' },
  LOW: { bg: 'bg-gray-100', text: 'text-gray-600' },
};

const SLA_STYLES: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
  on_track: {
    bg: 'bg-green-100',
    text: 'text-green-700',
    icon: <Clock className="h-3 w-3" />,
  },
  at_risk: {
    bg: 'bg-orange-100',
    text: 'text-orange-700',
    icon: <AlertTriangle className="h-3 w-3" />,
  },
  violated: {
    bg: 'bg-red-100',
    text: 'text-red-700',
    icon: <AlertCircle className="h-3 w-3" />,
  },
};

function formatSlaRemaining(hours: number | null | undefined): string {
  if (hours === null || hours === undefined) return '-';
  if (hours < 0) return `${Math.abs(Math.round(hours))}h atrasado`;
  if (hours < 1) return `${Math.round(hours * 60)}min`;
  if (hours < 24) return `${Math.round(hours)}h`;
  return `${Math.floor(hours / 24)}d ${Math.round(hours % 24)}h`;
}

function buildTramiteLabel(solicitudType: string, motivo: string | null | undefined, workflowLabel: string): string {
  if (solicitudType) {
    const base = solicitudType.charAt(0).toUpperCase() + solicitudType.slice(1);
    return motivo ? `${base} - ${motivo}` : base;
  }
  return workflowLabel;
}

// =============================================================================
// COMPONENT
// =============================================================================

export function RequestInfoSection({
  reference,
  workflowLabel,
  solicitudType,
  motivo,
  priority,
  slaStatus,
  slaRemainingHours,
  isMinor,
  batchReference,
  batchId,
  contactEmail,
  contactPhone,
}: RequestInfoSectionProps) {
  const locale = useLocale();
  const t = useTranslations('agent.pending.preview');
  const priorityStyle = PRIORITY_STYLES[priority] || PRIORITY_STYLES.NORMAL;
  const slaStyle = SLA_STYLES[slaStatus] || SLA_STYLES.on_track;
  const tramiteLabel = buildTramiteLabel(solicitudType, motivo, workflowLabel);

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    toast.success(t('copied', { label }));
  };

  return (
    <Card>
      <CardContent className="p-3">
        {/* Row 1: Reference + Badges + SLA right-aligned */}
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono font-semibold text-sm">{reference}</span>
            <Badge className={cn('text-[10px]', priorityStyle.bg, priorityStyle.text)}>
              {priority}
            </Badge>
            {isMinor && (
              <Badge className="bg-purple-100 text-purple-700 text-[10px]">
                <Baby className="h-3 w-3 mr-0.5" />
                {t('minor', { defaultValue: 'Menor' })}
              </Badge>
            )}
            {batchReference && batchId ? (
              <Link href={`/${locale}/dashboard/batch-requests/${batchId}`}>
                <Badge className="bg-indigo-100 text-indigo-700 hover:bg-indigo-200 cursor-pointer text-[10px]">
                  <FileStack className="h-3 w-3 mr-0.5" />
                  {batchReference}
                </Badge>
              </Link>
            ) : batchReference ? (
              <Badge className="bg-indigo-100 text-indigo-700 text-[10px]">
                <FileStack className="h-3 w-3 mr-0.5" />
                {batchReference}
              </Badge>
            ) : null}
          </div>
          {/* SLA indicator */}
          <div className={cn(
            'flex items-center gap-1 px-1.5 py-0.5 rounded text-xs shrink-0',
            slaStyle.bg, slaStyle.text
          )}>
            {slaStyle.icon}
            <span className="font-medium">{formatSlaRemaining(slaRemainingHours)}</span>
          </div>
        </div>

        {/* Row 2: Tramite + Contact — wraps on narrow screens */}
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <p className="text-sm font-medium leading-tight truncate min-w-0 flex-1">{tramiteLabel}</p>
          <div className="flex items-center gap-3 shrink-0 flex-wrap">
            {contactEmail && (
              <div className="flex items-center gap-1 group">
                <a href={`mailto:${contactEmail}`} className="text-xs text-blue-600 hover:underline truncate max-w-[160px]" title={contactEmail}>
                  <Mail className="h-3 w-3 inline mr-0.5" />
                  {contactEmail}
                </a>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-4 w-4 opacity-0 group-hover:opacity-100"
                  onClick={() => copyToClipboard(contactEmail, 'Email')}
                >
                  <Copy className="h-2 w-2" />
                </Button>
              </div>
            )}
            {contactPhone && (
              <div className="flex items-center gap-1 group">
                <a href={`tel:${contactPhone}`} className="text-xs text-blue-600 hover:underline">
                  <Phone className="h-3 w-3 inline mr-0.5" />
                  {contactPhone}
                </a>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-4 w-4 opacity-0 group-hover:opacity-100"
                  onClick={() => copyToClipboard(contactPhone, 'Tel')}
                >
                  <Copy className="h-2 w-2" />
                </Button>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default RequestInfoSection;
