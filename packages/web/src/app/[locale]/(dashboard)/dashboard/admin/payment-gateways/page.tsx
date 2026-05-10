/**
 * Admin Payment Gateways Page
 * Full CRUD management of bank gateway configurations (admin only)
 * Includes multi-gateway fields: gateway_type, supported_payment_methods, is_primary
 */

'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Loader2,
  AlertCircle,
  RefreshCw,
  Building2,
  Plus,
  Edit,
  CheckCircle,
  XCircle,
  Shield,
  Webhook,
  Zap,
  Crown,
} from 'lucide-react';
import {
  useBankConfigurations,
  useCreateBankConfiguration,
  useUpdateBankConfiguration,
} from '@/modules/treasury/hooks';
import type { BankConfiguration } from '@/modules/treasury/types';

const PAYMENT_METHODS = ['mobile_money', 'card', 'bank_transfer'] as const;

const PAYMENT_METHOD_LABELS: Record<string, string> = {
  mobile_money: 'Mobile Money',
  card: 'Card',
  bank_transfer: 'Bank Transfer',
};

interface GatewayFormData {
  bankCode: string;
  bankName: string;
  apiEndpoint: string;
  apiKeyEncrypted: string;
  webhookSecret: string;
  treasuryAccountNumber: string;
  isActive: boolean;
  supportsWebhooks: boolean;
  supportsDirectIntegration: boolean;
  gatewayType: string;
  supportedPaymentMethods: string[];
  isPrimary: boolean;
}

const defaultFormData: GatewayFormData = {
  bankCode: '',
  bankName: '',
  apiEndpoint: '',
  apiKeyEncrypted: '',
  webhookSecret: '',
  treasuryAccountNumber: '',
  isActive: true,
  supportsWebhooks: false,
  supportsDirectIntegration: false,
  gatewayType: '',
  supportedPaymentMethods: [],
  isPrimary: false,
};

export default function PaymentGatewaysPage() {
  const t = useTranslations('treasury');

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingConfig, setEditingConfig] = useState<BankConfiguration | null>(null);
  const [formData, setFormData] = useState<GatewayFormData>(defaultFormData);

  const { data: configurations, isLoading, error, refetch } = useBankConfigurations(false);
  const createMutation = useCreateBankConfiguration();
  const updateMutation = useUpdateBankConfiguration();

  const isSaving = createMutation.isPending || updateMutation.isPending;

  const openCreateDialog = () => {
    setEditingConfig(null);
    setFormData(defaultFormData);
    setIsDialogOpen(true);
  };

  const openEditDialog = (config: BankConfiguration) => {
    setEditingConfig(config);
    setFormData({
      bankCode: String(config.bankCode),
      bankName: config.bankName,
      apiEndpoint: config.apiEndpoint || '',
      apiKeyEncrypted: '',
      webhookSecret: '',
      treasuryAccountNumber: config.treasuryAccountNumber || '',
      isActive: config.isActive,
      supportsWebhooks: config.supportsWebhooks,
      supportsDirectIntegration: config.supportsDirectIntegration,
      gatewayType: config.gatewayType || '',
      supportedPaymentMethods: config.supportedPaymentMethods || [],
      isPrimary: config.isPrimary || false,
    });
    setIsDialogOpen(true);
  };

  const handleSubmit = async () => {
    const payload = {
      bankName: formData.bankName,
      apiEndpoint: formData.apiEndpoint || undefined,
      treasuryAccountNumber: formData.treasuryAccountNumber,
      isActive: formData.isActive,
      supportsWebhooks: formData.supportsWebhooks,
      supportsDirectIntegration: formData.supportsDirectIntegration,
      gatewayType: formData.gatewayType || undefined,
      supportedPaymentMethods: formData.supportedPaymentMethods,
      isPrimary: formData.isPrimary,
      ...(formData.apiKeyEncrypted ? { apiKeyEncrypted: formData.apiKeyEncrypted } : {}),
      ...(formData.webhookSecret ? { webhookSecret: formData.webhookSecret } : {}),
    };

    if (editingConfig) {
      await updateMutation.mutateAsync({
        configId: editingConfig.id,
        update: payload,
      });
    } else {
      await createMutation.mutateAsync({
        bankCode: formData.bankCode as 'BANGE' | 'BGFI' | 'CCEIBANK' | 'SGBGE' | 'ECOBANK',
        ...payload,
      } as Parameters<typeof createMutation.mutateAsync>[0]);
    }
    setIsDialogOpen(false);
  };

  const toggleMethod = (method: string) => {
    setFormData(prev => ({
      ...prev,
      supportedPaymentMethods: prev.supportedPaymentMethods.includes(method)
        ? prev.supportedPaymentMethods.filter(m => m !== method)
        : [...prev.supportedPaymentMethods, method],
    }));
  };

  const isFormValid = formData.bankCode.trim() && formData.bankName.trim() && formData.treasuryAccountNumber.trim();

  const getGatewayBadge = (config: BankConfiguration) => {
    if (!config.gatewayType) {
      return (
        <Badge variant="secondary" className="text-xs">
          {t('banksPage.gatewayStatus.notIntegrated')}
        </Badge>
      );
    }
    const isMpgs = config.gatewayType === 'ecobank_mpgs';
    if (config.isPrimary) {
      return (
        <div className="flex flex-wrap gap-1">
          <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-100 text-xs">
            <Crown className="h-3 w-3 mr-1" />
            {t('banksPage.gatewayStatus.primary')}
          </Badge>
          {isMpgs && (
            <Badge variant="outline" className="bg-indigo-50 text-indigo-700 border-indigo-200 text-xs">
              MPGS
            </Badge>
          )}
        </div>
      );
    }
    return (
      <div className="flex flex-wrap gap-1">
        <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 text-xs">
          <Zap className="h-3 w-3 mr-1" />
          {t('banksPage.gatewayStatus.fallback')}
        </Badge>
        {isMpgs && (
          <Badge variant="outline" className="bg-indigo-50 text-indigo-700 border-indigo-200 text-xs">
            MPGS
          </Badge>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('banksPage.infoTitle')}</h1>
          <p className="text-muted-foreground mt-1">
            {t('banksPage.infoDescription')}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            {t('banksPage.refresh')}
          </Button>
          <Button size="sm" onClick={openCreateDialog}>
            <Plus className="mr-2 h-4 w-4" />
            {t('banksPage.addBank')}
          </Button>
        </div>
      </div>

      {/* Security Info */}
      <Card className="border-blue-200 bg-blue-50">
        <CardContent className="flex items-start gap-3 py-3">
          <Shield className="h-5 w-5 text-blue-500 mt-0.5 shrink-0" />
          <p className="text-sm text-blue-700">
            {t('banksPage.infoDescription')}
          </p>
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
              <p className="text-sm text-muted-foreground mb-3">{t('banksPage.emptyDescription')}</p>
              <Button size="sm" onClick={openCreateDialog}>
                <Plus className="mr-2 h-4 w-4" />
                {t('banksPage.addBank')}
              </Button>
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
                    <TableHead className="text-right">{t('banksPage.table.actions')}</TableHead>
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
                      <TableCell className="text-right">
                        <Button variant="ghost" size="icon" onClick={() => openEditDialog(config)}>
                          <Edit className="h-4 w-4" />
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

      {/* Create/Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-[550px] max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5" />
              {editingConfig ? t('banksPage.dialog.editTitle') : t('banksPage.dialog.createTitle')}
            </DialogTitle>
            <DialogDescription>
              {editingConfig ? t('banksPage.dialog.editDescription') : t('banksPage.dialog.createDescription')}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Bank Code */}
            <div className="space-y-1.5">
              <Label htmlFor="bankCode">{t('banksPage.form.bankCode')} *</Label>
              <Input
                id="bankCode"
                placeholder={t('banksPage.form.bankCodePlaceholder')}
                value={formData.bankCode}
                onChange={(e) => setFormData({ ...formData, bankCode: e.target.value.toUpperCase() })}
                disabled={!!editingConfig}
                className="font-mono"
              />
            </div>

            {/* Bank Name */}
            <div className="space-y-1.5">
              <Label htmlFor="bankName">{t('banksPage.form.bankName')} *</Label>
              <Input
                id="bankName"
                placeholder={t('banksPage.form.bankNamePlaceholder')}
                value={formData.bankName}
                onChange={(e) => setFormData({ ...formData, bankName: e.target.value })}
              />
            </div>

            {/* Treasury Account */}
            <div className="space-y-1.5">
              <Label htmlFor="treasuryAccountNumber">{t('banksPage.form.treasuryAccount')} *</Label>
              <Input
                id="treasuryAccountNumber"
                placeholder={t('banksPage.form.treasuryAccountPlaceholder')}
                value={formData.treasuryAccountNumber}
                onChange={(e) => setFormData({ ...formData, treasuryAccountNumber: e.target.value })}
                className="font-mono"
              />
            </div>

            {/* Gateway Type */}
            <div className="space-y-1.5">
              <Label>{t('banksPage.form.gatewayType')}</Label>
              <Select
                value={formData.gatewayType || '_none'}
                onValueChange={(value) => setFormData({ ...formData, gatewayType: value === '_none' ? '' : value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t('banksPage.form.gatewayTypePlaceholder')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_none">{t('banksPage.form.gatewayTypeNone')}</SelectItem>
                  <SelectItem value="bange">{t('banksPage.form.gatewayTypeBange')}</SelectItem>
                  <SelectItem value="ecobank">{t('banksPage.form.gatewayTypeEcobank')}</SelectItem>
                  <SelectItem value="ecobank_mpgs">{t('banksPage.form.gatewayTypeMpgs')}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Supported Payment Methods */}
            {formData.gatewayType && (
              <div className="space-y-2">
                <Label>{t('banksPage.form.supportedMethods')}</Label>
                <p className="text-xs text-muted-foreground">{t('banksPage.form.supportedMethodsDescription')}</p>
                <div className="flex flex-wrap gap-3">
                  {PAYMENT_METHODS.map((method) => (
                    <div key={method} className="flex items-center gap-2">
                      <Checkbox
                        id={`method-${method}`}
                        checked={formData.supportedPaymentMethods.includes(method)}
                        onCheckedChange={() => toggleMethod(method)}
                      />
                      <Label htmlFor={`method-${method}`} className="text-sm font-normal cursor-pointer">
                        {PAYMENT_METHOD_LABELS[method]}
                      </Label>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* API Endpoint */}
            <div className="space-y-1.5">
              <Label htmlFor="apiEndpoint">{t('banksPage.form.apiEndpoint')}</Label>
              <Input
                id="apiEndpoint"
                placeholder="https://api.bank.com/v1"
                value={formData.apiEndpoint}
                onChange={(e) => setFormData({ ...formData, apiEndpoint: e.target.value })}
              />
            </div>

            {/* API Key (masked) */}
            <div className="space-y-1.5">
              <Label htmlFor="apiKeyEncrypted">{t('banksPage.form.apiKeyEncrypted')}</Label>
              <Input
                id="apiKeyEncrypted"
                type="password"
                placeholder={t('banksPage.form.apiKeyPlaceholder')}
                value={formData.apiKeyEncrypted}
                onChange={(e) => setFormData({ ...formData, apiKeyEncrypted: e.target.value })}
                autoComplete="off"
              />
            </div>

            {/* Webhook Secret (masked) */}
            <div className="space-y-1.5">
              <Label htmlFor="webhookSecret">{t('banksPage.form.webhookSecret')}</Label>
              <Input
                id="webhookSecret"
                type="password"
                placeholder={t('banksPage.form.webhookSecretPlaceholder')}
                value={formData.webhookSecret}
                onChange={(e) => setFormData({ ...formData, webhookSecret: e.target.value })}
                autoComplete="off"
              />
            </div>

            {/* Switches */}
            <div className="space-y-3 pt-1 border-t">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-sm">{t('banksPage.form.bankActive')}</Label>
                  <p className="text-xs text-muted-foreground">{t('banksPage.form.bankActiveDescription')}</p>
                </div>
                <Switch checked={formData.isActive} onCheckedChange={(v) => setFormData({ ...formData, isActive: v })} />
              </div>

              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-sm">{t('banksPage.form.supportsWebhooks')}</Label>
                  <p className="text-xs text-muted-foreground">{t('banksPage.form.supportsWebhooksDescription')}</p>
                </div>
                <Switch checked={formData.supportsWebhooks} onCheckedChange={(v) => setFormData({ ...formData, supportsWebhooks: v })} />
              </div>

              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-sm">{t('banksPage.form.directIntegration')}</Label>
                  <p className="text-xs text-muted-foreground">{t('banksPage.form.directIntegrationDescription')}</p>
                </div>
                <Switch checked={formData.supportsDirectIntegration} onCheckedChange={(v) => setFormData({ ...formData, supportsDirectIntegration: v })} />
              </div>

              {formData.gatewayType && (
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="text-sm">{t('banksPage.form.isPrimary')}</Label>
                    <p className="text-xs text-muted-foreground">{t('banksPage.form.isPrimaryDescription')}</p>
                  </div>
                  <Switch checked={formData.isPrimary} onCheckedChange={(v) => setFormData({ ...formData, isPrimary: v })} />
                </div>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)} disabled={isSaving}>
              {t('banksPage.cancel')}
            </Button>
            <Button onClick={handleSubmit} disabled={isSaving || !isFormValid}>
              {isSaving ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" />{t('banksPage.saving')}</>
              ) : (
                <><CheckCircle className="mr-2 h-4 w-4" />{editingConfig ? t('banksPage.saveChanges') : t('banksPage.createBank')}</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
