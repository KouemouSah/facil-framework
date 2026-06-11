/**
 * Payment Status Badge Component
 * Displays colored badge for payment status
 */

'use client';

import { useTranslations } from 'next-intl';
import { Badge } from '@/components/ui/badge';
import type { PaymentStatus, PaymentWorkflowStatus } from '../types';

interface PaymentStatusBadgeProps {
  status: PaymentStatus | string | undefined;
  className?: string;
}

const statusVariantConfig: Record<
  PaymentStatus,
  { variant: 'default' | 'secondary' | 'destructive' | 'outline' }
> = {
  pending: { variant: 'secondary' },
  processing: { variant: 'default' },
  completed: { variant: 'default' },
  failed: { variant: 'destructive' },
  refunded: { variant: 'outline' },
  cancelled: { variant: 'outline' },
};

export function PaymentStatusBadge({ status, className }: PaymentStatusBadgeProps) {
  const t = useTranslations('treasury');
  if (!status) {
    return <Badge variant="secondary" className={className}>-</Badge>;
  }
  const config = statusVariantConfig[status as PaymentStatus] || { variant: 'secondary' as const };
  const label = (status as PaymentStatus) in statusVariantConfig
    ? t(`statusLabels.${status}`)
    : status;

  return (
    <Badge variant={config.variant} className={className}>
      {label}
    </Badge>
  );
}

// Workflow status badge
interface WorkflowStatusBadgeProps {
  status: PaymentWorkflowStatus | string;
  className?: string;
}

const workflowStatusColorConfig: Record<
  PaymentWorkflowStatus,
  { color: string }
> = {
  submitted: { color: 'bg-gray-500' },
  auto_processing: { color: 'bg-blue-500' },
  auto_approved: { color: 'bg-green-500' },
  pending_agent_review: { color: 'bg-yellow-500' },
  agent_reviewing: { color: 'bg-blue-500' },
  requires_documents: { color: 'bg-yellow-600' },
  docs_resubmitted: { color: 'bg-blue-400' },
  approved_by_agent: { color: 'bg-green-500' },
  rejected_by_agent: { color: 'bg-red-500' },
  escalated_supervisor: { color: 'bg-purple-500' },
  supervisor_reviewing: { color: 'bg-purple-400' },
  completed: { color: 'bg-green-600' },
  cancelled_by_user: { color: 'bg-gray-500' },
  cancelled_by_agent: { color: 'bg-gray-600' },
  expired: { color: 'bg-red-400' },
};

export function WorkflowStatusBadge({ status, className }: WorkflowStatusBadgeProps) {
  const t = useTranslations('treasury');
  const config = workflowStatusColorConfig[status as PaymentWorkflowStatus] || { color: 'bg-gray-500' };
  const label = (status as PaymentWorkflowStatus) in workflowStatusColorConfig
    ? t(`workflowStatusLabels.${status}`)
    : status;

  return (
    <span
      className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium text-white ${config.color} ${className || ''}`}
    >
      {label}
    </span>
  );
}

// Payment Method badge
interface PaymentMethodBadgeProps {
  method: string;
  className?: string;
}

const methodColorConfig: Record<string, { color: string }> = {
  cash: { color: 'bg-green-100 text-green-800 border-green-200' },
  check: { color: 'bg-blue-100 text-blue-800 border-blue-200' },
  mobile_money: { color: 'bg-purple-100 text-purple-800 border-purple-200' },
  bank_transfer: { color: 'bg-indigo-100 text-indigo-800 border-indigo-200' },
  card: { color: 'bg-orange-100 text-orange-800 border-orange-200' },
};

export function PaymentMethodBadge({ method, className }: PaymentMethodBadgeProps) {
  const t = useTranslations('treasury');
  const config = methodColorConfig[method] || { color: 'bg-gray-100 text-gray-800 border-gray-200' };
  const label = method in methodColorConfig
    ? t(`methodLabels.${method}`)
    : method;

  return (
    <span
      className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium border ${config.color} ${className || ''}`}
    >
      {label}
    </span>
  );
}

export default PaymentStatusBadge;
