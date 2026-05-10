/**
 * Treasury Escalations Page
 * Read-only view of payments the current TESORO agent has escalated to their supervisor.
 * No action buttons - supervisor handles escalated payments.
 * @version 1.0.0
 */

'use client';

import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ArrowLeft, Loader2, AlertTriangle, ExternalLink } from 'lucide-react';
import {
  PaymentMethodBadge,
  WorkflowStatusBadge,
} from '@/modules/treasury/components';
import { treasuryApi } from '@/modules/treasury/services/api';
import type { PendingPayment } from '@/modules/treasury/types';
import { useMenuConfig } from '@/modules/agent-dashboard/hooks/useMenuConfig';

function getEscalationLevelVariant(
  level: string | undefined
): 'secondary' | 'destructive' | 'outline' | 'default' {
  switch (level) {
    case 'critical':
      return 'destructive';
    case 'high':
    case 'medium':
    case 'low':
    default:
      return 'secondary';
  }
}

function getEscalationLevelClassName(level: string | undefined): string {
  switch (level) {
    case 'critical':
      return 'bg-red-100 text-red-800 border-red-200';
    case 'high':
      return 'bg-orange-100 text-orange-800 border-orange-200';
    case 'medium':
      return 'bg-amber-100 text-amber-800 border-amber-200';
    case 'low':
      return 'bg-gray-100 text-gray-700 border-gray-200';
    default:
      return 'bg-gray-100 text-gray-700 border-gray-200';
  }
}

export default function TreasuryEscalationsPage() {
  const t = useTranslations('treasury');
  const locale = useLocale();
  const router = useRouter();
  const { menuItems } = useMenuConfig();

  // Fetch escalated payments
  const {
    data: escalationsData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['treasury', 'my-escalations'],
    queryFn: () => treasuryApi.getMyEscalations(),
  });

  const payments = escalationsData?.payments || [];

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('es-GQ', {
      style: 'currency',
      currency: 'XAF',
      minimumFractionDigits: 0,
    }).format(amount);
  };

  const formatDate = (dateString: string | undefined) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString('es-GQ', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const truncateText = (text: string | undefined, maxLength: number) => {
    if (!text) return '-';
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength) + '...';
  };

  // Workflow name helper using i18n
  const getWorkflowName = (code: string | undefined): string => {
    if (!code) return '-';
    const normalizedKey = code.toUpperCase().replace(/[^A-Z_]/g, '');
    if (t.has(`workflowNames.${normalizedKey}`)) {
      return t(`workflowNames.${normalizedKey}`);
    }
    return code.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
  };

  const getEscalationLevelLabel = (level: string | undefined): string => {
    switch (level) {
      case 'low':
        return t('escalation.levels.low');
      case 'medium':
        return t('escalation.levels.medium');
      case 'high':
        return t('escalation.levels.high');
      case 'critical':
        return t('escalation.levels.critical');
      default:
        return level || '-';
    }
  };

  // Navigate to payment detail
  const openPaymentDetail = (paymentId: string) => {
    router.push(
      `/${locale}/dashboard/agent/treasury/validation/${paymentId}`
    );
  };

  // Navigate back to dashboard — resolve href from menu_config (source of truth
  // seeded by migration 153). Hardcoding `/dashboard/agent/treasury` was a
  // supervisor-only page that 403-ed for agents (regressed in commit 3fdce698).
  const goToDashboard = () => {
    const dashboardHref = menuItems.find((m) => m.id === 'dashboard')?.href;
    router.push(dashboardHref ?? `/${locale}/dashboard/agent/treasury/validation`);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={goToDashboard}>
          <ArrowLeft className="mr-1 h-4 w-4" />
          {t('nav.dashboard')}
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            {t('escalation.pageTitle')}
          </h1>
          <p className="text-muted-foreground mt-1">
            {t('escalation.pageDescription')}
          </p>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            <p className="text-red-700">
              {t('validationPage.error.loadingPayments')}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Escalations Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            {t('escalation.pageTitle')}
            {escalationsData?.total !== undefined && (
              <Badge variant="secondary" className="ml-2">
                {escalationsData.total}
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : payments.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <AlertTriangle className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold">
                {t('escalation.noEscalations')}
              </h3>
              <p className="text-muted-foreground">
                {t('escalation.noEscalationsDescription')}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>
                      {t('validationPage.table.reference')}
                    </TableHead>
                    <TableHead>
                      {t('validationPage.table.service')}
                    </TableHead>
                    <TableHead>
                      {t('validationPage.table.amount')}
                    </TableHead>
                    <TableHead>
                      {t('validationPage.table.method')}
                    </TableHead>
                    <TableHead>
                      {t('escalation.escalationLevel')}
                    </TableHead>
                    <TableHead>{t('escalation.reason')}</TableHead>
                    <TableHead>{t('escalation.escalatedAt')}</TableHead>
                    <TableHead>{t('escalation.status')}</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {payments.map((payment: PendingPayment) => (
                    <TableRow
                      key={payment.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => openPaymentDetail(payment.id)}
                    >
                      <TableCell className="font-mono text-sm">
                        {payment.paymentReference}
                      </TableCell>
                      <TableCell>
                        <div>
                          <p className="font-medium text-sm">
                            {getWorkflowName(payment.workflowCode)}
                          </p>
                          {payment.requestReference && (
                            <p className="text-xs text-muted-foreground font-mono">
                              {payment.requestReference}
                            </p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="font-bold">
                        {formatCurrency(payment.totalAmount)}
                      </TableCell>
                      <TableCell>
                        <PaymentMethodBadge method={payment.paymentMethod} />
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={getEscalationLevelVariant(
                            payment.escalationLevel
                          )}
                          className={getEscalationLevelClassName(
                            payment.escalationLevel
                          )}
                        >
                          {getEscalationLevelLabel(payment.escalationLevel)}
                        </Badge>
                      </TableCell>
                      <TableCell
                        className="max-w-[200px] text-sm text-muted-foreground"
                        title={payment.escalationReason}
                      >
                        {truncateText(payment.escalationReason, 40)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDate(payment.escalatedAt)}
                      </TableCell>
                      <TableCell>
                        <WorkflowStatusBadge
                          status={payment.workflowStatus}
                        />
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            openPaymentDetail(payment.id);
                          }}
                        >
                          <ExternalLink className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
