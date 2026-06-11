/**
 * Payment Methods Configuration Page
 * CRUD operations for payment method configurations
 */

'use client';

import React, { useState } from 'react';
import { useTranslations } from 'next-intl';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { useToast } from '@/hooks/use-toast';
import {
  Smartphone,
  CreditCard,
  Building2,
  Banknote,
  FileText,
  Plus,
  Pencil,
  Trash2,
  GripVertical,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import {
  usePaymentMethodConfigs,
  useCreatePaymentMethod,
  useUpdatePaymentMethod,
  useDeletePaymentMethod,
  useTogglePaymentMethodActive,
} from '@/modules/treasury/hooks';
import type {
  PaymentMethodConfig,
  PaymentMethodConfigCreate,
  PaymentMethodConfigUpdate,
} from '@/modules/treasury/types';

// Icon mapping
const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  smartphone: Smartphone,
  'credit-card': CreditCard,
  'building-2': Building2,
  banknote: Banknote,
  'file-text': FileText,
};

// Icon labels are resolved via i18n in the component
const availableIconValues = ['smartphone', 'credit-card', 'building-2', 'banknote', 'file-text'] as const;

// Default protected methods that cannot be deleted
const PROTECTED_METHODS = new Set(['mobile_money', 'card', 'bank_transfer', 'cash', 'check']);

interface PaymentMethodFormData {
  code: string;
  labelEs: string;
  // Note: Translations (FR/EN) are managed via entity_translations table
  processorType: 'gateway_api' | 'bange_api' | 'manual';
  requiresPhone: boolean;
  requiresRedirect: boolean;
  requiresAgentValidation: boolean;
  icon: string;
  minAmount: string;
  maxAmount: string;
  feesPercentage: string;
  feesFixed: string;
}

const defaultFormData: PaymentMethodFormData = {
  code: '',
  labelEs: '',
  processorType: 'manual',
  requiresPhone: false,
  requiresRedirect: false,
  requiresAgentValidation: false,
  icon: 'credit-card',
  minAmount: '',
  maxAmount: '',
  feesPercentage: '0',
  feesFixed: '0',
};

export default function PaymentMethodsPage() {
  const t = useTranslations('treasury');
  const tCommon = useTranslations('common');
  const { toast } = useToast();

  // State
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [editingMethod, setEditingMethod] = useState<PaymentMethodConfig | null>(null);
  const [deletingCode, setDeletingCode] = useState<string | null>(null);
  const [formData, setFormData] = useState<PaymentMethodFormData>(defaultFormData);

  // Queries & Mutations
  const { data: methods, isLoading, error } = usePaymentMethodConfigs();
  const createMutation = useCreatePaymentMethod();
  const updateMutation = useUpdatePaymentMethod();
  const deleteMutation = useDeletePaymentMethod();
  const toggleActiveMutation = useTogglePaymentMethodActive();

  // Handlers
  const handleOpenCreate = () => {
    setFormData(defaultFormData);
    setEditingMethod(null);
    setIsCreateDialogOpen(true);
  };

  const handleOpenEdit = (method: PaymentMethodConfig) => {
    setFormData({
      code: method.code,
      labelEs: method.labelEs,
      processorType: method.processorType,
      requiresPhone: method.requiresPhone,
      requiresRedirect: method.requiresRedirect,
      requiresAgentValidation: method.requiresAgentValidation,
      icon: method.icon,
      minAmount: method.minAmount?.toString() || '',
      maxAmount: method.maxAmount?.toString() || '',
      feesPercentage: method.feesPercentage.toString(),
      feesFixed: method.feesFixed.toString(),
    });
    setEditingMethod(method);
    setIsCreateDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setIsCreateDialogOpen(false);
    setEditingMethod(null);
    setFormData(defaultFormData);
  };

  const handleSubmit = async () => {
    if (!formData.code || !formData.labelEs) {
      toast({
        title: t('paymentMethodsPage.toast.error'),
        description: t('paymentMethodsPage.toast.requiredFields'),
        variant: 'destructive',
      });
      return;
    }

    try {
      if (editingMethod) {
        // Update
        const update: PaymentMethodConfigUpdate = {
          labelEs: formData.labelEs,
          processorType: formData.processorType,
          requiresPhone: formData.requiresPhone,
          requiresRedirect: formData.requiresRedirect,
          requiresAgentValidation: formData.requiresAgentValidation,
          icon: formData.icon,
          minAmount: formData.minAmount ? parseFloat(formData.minAmount) : undefined,
          maxAmount: formData.maxAmount ? parseFloat(formData.maxAmount) : undefined,
          feesPercentage: parseFloat(formData.feesPercentage) || 0,
          feesFixed: parseFloat(formData.feesFixed) || 0,
        };
        await updateMutation.mutateAsync({ code: editingMethod.code, update });
        toast({
          title: t('paymentMethodsPage.toast.updated'),
          description: t('paymentMethodsPage.toast.updatedDescription', { name: formData.labelEs }),
        });
      } else {
        // Create
        const create: PaymentMethodConfigCreate = {
          code: formData.code,
          labelEs: formData.labelEs,
          processorType: formData.processorType,
          requiresPhone: formData.requiresPhone,
          requiresRedirect: formData.requiresRedirect,
          requiresAgentValidation: formData.requiresAgentValidation,
          icon: formData.icon,
          minAmount: formData.minAmount ? parseFloat(formData.minAmount) : undefined,
          maxAmount: formData.maxAmount ? parseFloat(formData.maxAmount) : undefined,
          feesPercentage: parseFloat(formData.feesPercentage) || 0,
          feesFixed: parseFloat(formData.feesFixed) || 0,
        };
        await createMutation.mutateAsync(create);
        toast({
          title: t('paymentMethodsPage.toast.created'),
          description: t('paymentMethodsPage.toast.createdDescription', { name: formData.labelEs }),
        });
      }
      handleCloseDialog();
    } catch (err) {
      toast({
        title: t('paymentMethodsPage.toast.error'),
        description: err instanceof Error ? err.message : t('paymentMethodsPage.toast.saveError'),
        variant: 'destructive',
      });
    }
  };

  const handleDelete = async () => {
    if (!deletingCode) return;

    try {
      await deleteMutation.mutateAsync(deletingCode);
      toast({
        title: t('paymentMethodsPage.toast.deleted'),
        description: t('paymentMethodsPage.toast.deletedDescription'),
      });
      setDeletingCode(null);
    } catch (err) {
      toast({
        title: t('paymentMethodsPage.toast.error'),
        description: err instanceof Error ? err.message : t('paymentMethodsPage.toast.deleteError'),
        variant: 'destructive',
      });
    }
  };

  const handleToggleActive = async (code: string, currentActive: boolean) => {
    try {
      await toggleActiveMutation.mutateAsync({ code, isActive: !currentActive });
      toast({
        title: currentActive ? t('paymentMethodsPage.toast.deactivated') : t('paymentMethodsPage.toast.activated'),
        description: currentActive ? t('paymentMethodsPage.toast.deactivatedDescription') : t('paymentMethodsPage.toast.activatedDescription'),
      });
    } catch (err) {
      toast({
        title: t('paymentMethodsPage.toast.error'),
        description: err instanceof Error ? err.message : t('paymentMethodsPage.toast.toggleError'),
        variant: 'destructive',
      });
    }
  };

  const getIcon = (iconName: string) => {
    const IconComponent = iconMap[iconName] || CreditCard;
    return <IconComponent className="h-5 w-5" />;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-destructive">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span>{t('paymentMethodsPage.loadError')}: {error.message}</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t('paymentMethods.title')}</h1>
          <p className="text-muted-foreground">{t('paymentMethods.description')}</p>
        </div>
        <Button onClick={handleOpenCreate}>
          <Plus className="h-4 w-4 mr-2" />
          {t('paymentMethods.add')}
        </Button>
      </div>

      {/* Table */}
      <Card>
        <CardHeader>
          <CardTitle>{t('paymentMethods.configuredMethods')}</CardTitle>
          <CardDescription>
            {methods?.length || 0} {t('paymentMethods.methodsConfigured')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12"></TableHead>
                <TableHead>{t('paymentMethods.code')}</TableHead>
                <TableHead>{t('paymentMethods.name')}</TableHead>
                <TableHead>{t('paymentMethods.processor')}</TableHead>
                <TableHead>{t('paymentMethods.validation')}</TableHead>
                <TableHead>{t('paymentMethods.fees')}</TableHead>
                <TableHead>{t('paymentMethods.active')}</TableHead>
                <TableHead className="text-right">{tCommon('actions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {methods?.map((method) => (
                <TableRow key={method.code}>
                  <TableCell>
                    <GripVertical className="h-4 w-4 text-muted-foreground cursor-grab" />
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {getIcon(method.icon)}
                      <code className="text-sm bg-muted px-1 rounded">
                        {method.code}
                      </code>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="font-medium">{method.labelEs}</div>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={method.processorType === 'bange_api' ? 'default' : 'secondary'}
                    >
                      {method.processorType === 'bange_api' ? t('paymentMethodsPage.processorBangeApi') : t('paymentMethodsPage.processorManual')}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {method.requiresAgentValidation ? (
                      <Badge variant="outline" className="text-orange-600 border-orange-300">
                        {t('paymentMethodsPage.requiresAgent')}
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-green-600 border-green-300">
                        {t('paymentMethodsPage.automatic')}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="text-sm">
                      {method.feesPercentage > 0 && (
                        <span>{method.feesPercentage}%</span>
                      )}
                      {method.feesPercentage > 0 && method.feesFixed > 0 && ' + '}
                      {method.feesFixed > 0 && (
                        <span>{method.feesFixed.toLocaleString()} XAF</span>
                      )}
                      {method.feesPercentage === 0 && method.feesFixed === 0 && (
                        <span className="text-muted-foreground">{t('paymentMethodsPage.noFees')}</span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Switch
                      checked={method.isActive}
                      onCheckedChange={() =>
                        handleToggleActive(method.code, method.isActive)
                      }
                      disabled={toggleActiveMutation.isPending}
                    />
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleOpenEdit(method)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      {!PROTECTED_METHODS.has(method.code) && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-destructive hover:text-destructive"
                          onClick={() => setDeletingCode(method.code)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {editingMethod
                ? t('paymentMethods.editMethod')
                : t('paymentMethods.addMethod')}
            </DialogTitle>
            <DialogDescription>
              {editingMethod
                ? t('paymentMethods.editDescription')
                : t('paymentMethods.addDescription')}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            {/* Code - only for create */}
            {!editingMethod && (
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="code" className="text-right">
                  {t('paymentMethodsPage.form.code')} *
                </Label>
                <Input
                  id="code"
                  value={formData.code}
                  onChange={(e) =>
                    setFormData({ ...formData, code: e.target.value.toLowerCase().replace(/[^a-z_]/g, '') })
                  }
                  placeholder={t('paymentMethodsPage.form.codePlaceholder')}
                  className="col-span-3"
                />
              </div>
            )}

            {/* Label (Spanish only - translations managed via entity_translations) */}
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="labelEs" className="text-right">
                {t('paymentMethodsPage.form.name')} *
              </Label>
              <Input
                id="labelEs"
                value={formData.labelEs}
                onChange={(e) => setFormData({ ...formData, labelEs: e.target.value })}
                placeholder={t('paymentMethodsPage.form.namePlaceholder')}
                className="col-span-3"
              />
            </div>

            {/* Processor Type & Icon */}
            <div className="grid grid-cols-4 items-center gap-4">
              <Label className="text-right">{t('paymentMethodsPage.form.processor')}</Label>
              <Select
                value={formData.processorType}
                onValueChange={(value: 'gateway_api' | 'bange_api' | 'manual') =>
                  setFormData({ ...formData, processorType: value })
                }
              >
                <SelectTrigger className="col-span-3">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gateway_api">{t('paymentMethodsPage.form.processorGatewayApi')}</SelectItem>
                  <SelectItem value="bange_api">{t('paymentMethodsPage.form.processorBangeApi')}</SelectItem>
                  <SelectItem value="manual">{t('paymentMethodsPage.form.processorManual')}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-4 items-center gap-4">
              <Label className="text-right">{t('paymentMethodsPage.form.icon')}</Label>
              <Select
                value={formData.icon}
                onValueChange={(value) => setFormData({ ...formData, icon: value })}
              >
                <SelectTrigger className="col-span-3">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {availableIconValues.map((iconValue) => (
                    <SelectItem key={iconValue} value={iconValue}>
                      <div className="flex items-center gap-2">
                        {getIcon(iconValue)}
                        <span>{t(`paymentMethodsPage.icons.${iconValue.replace(/-/g, '_')}`)}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Checkboxes */}
            <div className="grid grid-cols-4 items-start gap-4">
              <Label className="text-right pt-2">{t('paymentMethodsPage.form.options')}</Label>
              <div className="col-span-3 space-y-3">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="requiresPhone"
                    checked={formData.requiresPhone}
                    onCheckedChange={(checked) =>
                      setFormData({ ...formData, requiresPhone: !!checked })
                    }
                  />
                  <Label htmlFor="requiresPhone" className="font-normal">
                    {t('paymentMethodsPage.form.requiresPhone')}
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="requiresRedirect"
                    checked={formData.requiresRedirect}
                    onCheckedChange={(checked) =>
                      setFormData({ ...formData, requiresRedirect: !!checked })
                    }
                  />
                  <Label htmlFor="requiresRedirect" className="font-normal">
                    {t('paymentMethodsPage.form.requiresRedirect')}
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="requiresAgentValidation"
                    checked={formData.requiresAgentValidation}
                    onCheckedChange={(checked) =>
                      setFormData({ ...formData, requiresAgentValidation: !!checked })
                    }
                  />
                  <Label htmlFor="requiresAgentValidation" className="font-normal">
                    {t('paymentMethodsPage.form.requiresAgentValidation')}
                  </Label>
                </div>
              </div>
            </div>

            {/* Fees */}
            <div className="grid grid-cols-4 items-center gap-4">
              <Label className="text-right">{t('paymentMethodsPage.form.feesPercentage')}</Label>
              <Input
                type="number"
                step="0.01"
                min="0"
                max="100"
                value={formData.feesPercentage}
                onChange={(e) =>
                  setFormData({ ...formData, feesPercentage: e.target.value })
                }
                className="col-span-3"
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label className="text-right">{t('paymentMethodsPage.form.feesFixed')}</Label>
              <Input
                type="number"
                step="1"
                min="0"
                value={formData.feesFixed}
                onChange={(e) => setFormData({ ...formData, feesFixed: e.target.value })}
                className="col-span-3"
              />
            </div>

            {/* Amount limits */}
            <div className="grid grid-cols-4 items-center gap-4">
              <Label className="text-right">{t('paymentMethodsPage.form.minAmount')}</Label>
              <Input
                type="number"
                step="1"
                min="0"
                value={formData.minAmount}
                onChange={(e) => setFormData({ ...formData, minAmount: e.target.value })}
                placeholder={t('paymentMethodsPage.form.noLimit')}
                className="col-span-3"
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label className="text-right">{t('paymentMethodsPage.form.maxAmount')}</Label>
              <Input
                type="number"
                step="1"
                min="0"
                value={formData.maxAmount}
                onChange={(e) => setFormData({ ...formData, maxAmount: e.target.value })}
                placeholder={t('paymentMethodsPage.form.noLimit')}
                className="col-span-3"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={handleCloseDialog}>
              {tCommon('cancel')}
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {(createMutation.isPending || updateMutation.isPending) && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              {editingMethod ? tCommon('save') : tCommon('create')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deletingCode} onOpenChange={() => setDeletingCode(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('paymentMethods.deleteConfirmTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('paymentMethods.deleteConfirmDescription')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tCommon('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              {tCommon('delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
