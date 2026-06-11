/**
 * Bank Configurations Page (Read-Only)
 * Supervisor treasury view: connectivity status of payment gateways
 * For full CRUD, use admin /payment-gateways page
 */

'use client';

import { useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
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
import {
  Loader2,
  AlertCircle,
  RefreshCw,
  Building2,
  CheckCircle,
  XCircle,
  Webhook,
  Info,
  Zap,
  Crown,
  ExternalLink,
} from 'lucide-react';
import { useLocale } from 'next-intl';
import Link from 'next/link';
import { useBankConfigurations } from '@/modules/treasury/hooks';
import type { BankConfiguration } from '@/modules/treasury/types';

const PAYMENT_METHOD_LABELS: Record<string, string> = {
  mobile_money: 'Mobile Money',
  card: 'Card',
  bank_transfer: 'Bank Transfer',
};

export default function BankConfigurationsPage() {
  const t = useTranslations('treasury');
  const locale = useLocale();

  const { data: configurations, isLoading, error, refetch } = useBankConfigurations();

  const getGatewayBadge = (config: BankConfiguration) => {
    if (!config.gatewayType) {
      return (
        <Badge variant="secondary" className="text-xs">
          {t('banksPage.gatewayStatus.notIntegrated')}
        </Badge>
      );
    }
    if (config.isPrimary) {
      return (
        <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-100 text-xs">
          <Crown className="h-3 w-3 mr-1" />
          {t('banksPage.gatewayStatus.primary')}
        </Badge>
      );
    }
    return (
      <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 text-xs">
        <Zap className="h-3 w-3 mr-1" />
        {t('banksPage.gatewayStatus.fallback')}
      </Badge>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('banksPage.readOnly.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('banksPage.readOnly.description')}</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isLoading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          {t('banksPage.refresh')}
        </Button>
      </div>

      {/* Admin Contact Notice with link */}
      <Card className="border-amber-200 bg-amber-50">
        <CardContent className="flex items-start justify-between gap-3 py-3">
          <div className="flex items-start gap-3">
            <Info className="h-5 w-5 text-amber-600 mt-0.5 shrink-0" />
            <p className="text-sm text-amber-800">{t('banksPage.readOnly.adminContact')}</p>
          </div>
          <Link href={`/${locale}/dashboard/admin/payment-gateways`}>
            <Button variant="outline" size="sm" className="shrink-0">
              <ExternalLink className="mr-2 h-3.5 w-3.5" />
              {t('banksPage.readOnly.manageGateways')}
            </Button>
          </Link>
        </CardContent>
      </Card>

      {/* Error */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center gap-3 py-3">
            <AlertCircle className="h-5 w-5 text-red-500" />
            <p className="text-red-700">{t('banksPage.loadError')}</p>
          </CardContent>
        </Card>
      )}

      {/* Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Building2 className="h-5 w-5" />
            {t('banksPage.configuredBanks')}
            {configurations && configurations.length > 0 && (
              <Badge variant="secondary" className="ml-2">{configurations.length}</Badge>
            )}
          </CardTitle>
          <CardDescription>{t('banksPage.configuredBanksDescription')}</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : !configurations || configurations.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Building2 className="h-10 w-10 text-muted-foreground mb-3" />
              <h3 className="font-semibold">{t('banksPage.emptyTitle')}</h3>
              <p className="text-sm text-muted-foreground">{t('banksPage.emptyDescription')}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('banksPage.table.code')}</TableHead>
                    <TableHead>{t('banksPage.table.name')}</TableHead>
                    <TableHead>{t('banksPage.table.treasuryAccount')}</TableHead>
                    <TableHead>{t('banksPage.table.gatewayType')}</TableHead>
                    <TableHead>{t('banksPage.table.supportedMethods')}</TableHead>
                    <TableHead>{t('banksPage.table.webhooks')}</TableHead>
                    <TableHead>{t('banksPage.table.status')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {configurations.map((config: BankConfiguration) => (
                    <TableRow key={config.id}>
                      <TableCell className="font-mono font-bold text-sm">{config.bankCode}</TableCell>
                      <TableCell className="text-sm">{config.bankName}</TableCell>
                      <TableCell className="font-mono text-xs">{config.treasuryAccountNumber || '-'}</TableCell>
                      <TableCell>{getGatewayBadge(config)}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {(config.supportedPaymentMethods || []).map((m: string) => (
                            <Badge key={m} variant="outline" className="text-xs">
                              {PAYMENT_METHOD_LABELS[m] || m}
                            </Badge>
                          ))}
                          {(!config.supportedPaymentMethods || config.supportedPaymentMethods.length === 0) && (
                            <span className="text-muted-foreground text-xs">-</span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        {config.supportsWebhooks ? (
                          <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200 text-xs">
                            <Webhook className="h-3 w-3 mr-1" />
                            {t('banksPage.supported')}
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground text-xs">-</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {config.isActive ? (
                          <Badge className="bg-green-100 text-green-700 hover:bg-green-100 text-xs">
                            <CheckCircle className="h-3 w-3 mr-1" />
                            {t('banksPage.active')}
                          </Badge>
                        ) : (
                          <Badge variant="secondary" className="text-xs">
                            <XCircle className="h-3 w-3 mr-1" />
                            {t('banksPage.inactive')}
                          </Badge>
                        )}
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
