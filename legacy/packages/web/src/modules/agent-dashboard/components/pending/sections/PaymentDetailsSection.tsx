/**
 * PaymentDetailsSection - Compact payment card with full details
 *
 * @module agent-dashboard/components/pending/sections
 * @date 2026-03-06
 * @updated 2026-03-07 - Added paid date and payment reference display
 */

'use client';

import React from 'react';
import { useTranslations } from 'next-intl';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CreditCard } from 'lucide-react';

interface PaymentDetailsSectionProps {
  status?: string | null;
  amount?: number | null;
  currency?: string | null;
  method?: string | null;
  paidAt?: string | null;
  reference?: string | null;
  receiptNumber?: string | null;
}

const STATUS_VARIANTS: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  completed: 'default',
  approved: 'default',
  pending_agent_review: 'secondary',
  submitted: 'secondary',
  rejected: 'destructive',
  failed: 'destructive',
  cancelled: 'outline',
  expired: 'outline',
};

const METHOD_KEYS: Record<string, string> = {
  cash: 'paymentMethodCash',
  mobile_money: 'paymentMethodMobileMoney',
  bank_transfer: 'paymentMethodBankTransfer',
  card: 'paymentMethodCard',
  bange_wallet: 'paymentMethodBange',
};

function formatAmount(amount: number, currency: string): string {
  return new Intl.NumberFormat('es-GQ', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatDate(dateString: string): string {
  try {
    return new Date(dateString).toLocaleDateString('es-ES', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateString;
  }
}

export function PaymentDetailsSection({
  status,
  amount,
  currency = 'XAF',
  method,
  paidAt,
  reference,
  receiptNumber,
}: PaymentDetailsSectionProps) {
  const t = useTranslations('agent.pending.preview');

  if (!status && amount == null) return null;

  const statusVariant = STATUS_VARIANTS[status || ''] || 'secondary';

  return (
    <Card className="h-full">
      <CardContent className="p-3">
        <p className="text-[11px] text-muted-foreground uppercase tracking-wider mb-1 flex items-center gap-1">
          <CreditCard className="h-3 w-3" />
          {t('paymentDetails')}
        </p>
        {/* Line 1: Amount + Reference */}
        <div className="flex items-baseline gap-2 flex-wrap">
          {amount != null && (
            <span className="text-base font-bold leading-tight">{formatAmount(amount, currency || 'XAF')}</span>
          )}
          {(reference || receiptNumber) && (
            <span className="text-[11px] font-mono text-muted-foreground break-all">
              {receiptNumber || reference}
            </span>
          )}
        </div>
        {/* Line 2: Status + Method + Date */}
        <div className="flex items-center gap-2 flex-wrap mt-0.5">
          {status && (
            <Badge variant={statusVariant} className="text-[10px]">
              {status.replace(/_/g, ' ')}
            </Badge>
          )}
          {method && (
            <span className="text-xs text-muted-foreground">
              {METHOD_KEYS[method] ? t(METHOD_KEYS[method]) : method}
            </span>
          )}
          {paidAt && (
            <span className="text-xs text-muted-foreground">
              {formatDate(paidAt)}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default PaymentDetailsSection;
