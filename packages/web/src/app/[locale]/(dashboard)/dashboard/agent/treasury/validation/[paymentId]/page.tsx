/**
 * Payment Detail Page
 * Complete view for Treasury agents to review and act on payments
 * Includes navigation between payments and integrated actions
 */

'use client';

import { useState, useMemo } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  ArrowLeft,
  ArrowRight,
  ChevronLeft,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Loader2,
  User,
  CreditCard,
  Receipt,
  Building2,
  Package,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { treasuryApi } from '@/modules/treasury/services/api';
import { usePendingPayments, usePaymentActions } from '@/modules/treasury/hooks';
import {
  PaymentMethodBadge,
  WorkflowStatusBadge,
  SLABadge,
  ReceiptSuccessDialog,
} from '@/modules/treasury/components';

function formatCurrency(amount: number | undefined): string {
  if (amount === undefined || amount === null) return 'N/A';
  return new Intl.NumberFormat('es-GQ', {
    style: 'currency',
    currency: 'XAF',
    minimumFractionDigits: 0,
  }).format(amount);
}

function formatDate(dateString: string | undefined): string {
  if (!dateString) return 'N/A';
  return new Date(dateString).toLocaleDateString('es-GQ', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function PaymentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const locale = useLocale();
  const t = useTranslations('treasury');
  const paymentId = params.paymentId as string;

  // Workflow name helper using i18n
  const getWorkflowName = (code: string | undefined): string => {
    if (!code) return t('validationPage.unspecified');
    const normalizedKey = code.toUpperCase().replace(/[^A-Z_]/g, '');
    if (t.has(`workflowNames.${normalizedKey}`)) {
      return t(`workflowNames.${normalizedKey}`);
    }
    return code.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  // Format hours with i18n
  const formatHours = (hours: number | undefined): string => {
    if (!hours) return 'N/A';
    if (hours < 1) return t('detail.formatHours.minutes', { value: Math.round(hours * 60) });
    if (hours < 24) return t('detail.formatHours.hours', { value: hours.toFixed(1) });
    return t('detail.formatHours.days', { value: Math.round(hours / 24) });
  };

  // Get filter params from URL to maintain context
  const statusFilter = searchParams.get('status') || 'pending_agent_review';
  const methodFilter = searchParams.get('method') || undefined;

  // State for actions
  const [comment, setComment] = useState('');
  const [rejectReason, setRejectReason] = useState('');
  const [showValidateConfirm, setShowValidateConfirm] = useState(false);
  const [showRejectConfirm, setShowRejectConfirm] = useState(false);
  const [showEscalateConfirm, setShowEscalateConfirm] = useState(false);
  const [escalateReason, setEscalateReason] = useState('');
  const [escalateLevel, setEscalateLevel] = useState('medium');

  // Receipt dialog state
  const [receiptData, setReceiptData] = useState<{ receiptNumber: string; paymentId: string } | null>(null);

  // Fetch current payment details
  const { data: payment, isLoading: isLoadingPayment, error: paymentError } = useQuery({
    queryKey: ['treasury-payment-detail', paymentId],
    queryFn: () => treasuryApi.getPaymentDetails(paymentId),
    enabled: !!paymentId,
  });

  // Fetch list of payments for navigation (same filters as list page)
  const { data: paymentsData } = usePendingPayments({
    status: statusFilter !== 'all' ? statusFilter : undefined,
    method: methodFilter !== 'all' ? methodFilter : undefined,
  });

  // Payment actions
  const {
    validatePayment,
    rejectPayment,
    escalatePayment,
    isValidating,
    isRejecting,
    isEscalating,
  } = usePaymentActions();

  // Calculate navigation (prev/next)
  const navigation = useMemo(() => {
    const payments = paymentsData?.payments || [];
    const currentIndex = payments.findIndex(p => p.id === paymentId);

    return {
      currentIndex: currentIndex + 1,
      total: payments.length,
      prevId: currentIndex > 0 ? payments[currentIndex - 1]?.id : null,
      nextId: currentIndex < payments.length - 1 ? payments[currentIndex + 1]?.id : null,
      hasPrev: currentIndex > 0,
      hasNext: currentIndex < payments.length - 1 && currentIndex !== -1,
    };
  }, [paymentsData?.payments, paymentId]);

  // Navigation handlers
  const navigateToPayment = (id: string) => {
    const navParams = new URLSearchParams();
    if (statusFilter) navParams.set('status', statusFilter);
    if (methodFilter) navParams.set('method', methodFilter);
    router.push(`/${locale}/dashboard/agent/treasury/validation/${id}?${navParams.toString()}`);
  };

  const goBack = () => {
    const navParams = new URLSearchParams();
    if (statusFilter) navParams.set('status', statusFilter);
    if (methodFilter) navParams.set('method', methodFilter);
    router.push(`/${locale}/dashboard/agent/treasury/validation?${navParams.toString()}`);
  };

  // Navigate after validation (used by receipt dialog dismiss and direct navigation)
  const navigateAfterValidation = () => {
    if (navigation.nextId) {
      navigateToPayment(navigation.nextId);
    } else {
      goBack();
    }
  };

  // Action handlers
  const handleValidate = async () => {
    try {
      const result = await validatePayment.mutateAsync({
        paymentId,
        request: comment ? { comment } : undefined,
      });
      setShowValidateConfirm(false);
      setComment('');
      // Show receipt dialog if receipt was generated
      if (result.receiptNumber) {
        setReceiptData({ receiptNumber: result.receiptNumber, paymentId });
        return;
      }
      navigateAfterValidation();
    } catch (error) {
      // Error is handled by the hook
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) return;
    try {
      await rejectPayment.mutateAsync({
        paymentId,
        request: { reason: rejectReason },
      });
      setShowRejectConfirm(false);
      setRejectReason('');
      // Navigate to next payment or back to list
      if (navigation.nextId) {
        navigateToPayment(navigation.nextId);
      } else {
        goBack();
      }
    } catch (error) {
      // Error is handled by the hook
    }
  };

  const handleEscalate = async () => {
    if (!escalateReason.trim()) return;
    try {
      await escalatePayment.mutateAsync({
        paymentId,
        reason: escalateReason,
        level: escalateLevel,
      });
      setShowEscalateConfirm(false);
      setEscalateReason('');
      goBack();
    } catch {
      // Error is handled by the hook
    }
  };

  const isActionable = payment?.workflowStatus === 'pending_agent_review';
  const isAnyLoading = isValidating || isRejecting || isEscalating;

  // Loading state
  if (isLoadingPayment) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Error state
  if (paymentError || !payment) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={goBack}>
          <ChevronLeft className="mr-2 h-4 w-4" />
          {t('detail.backToListFull')}
        </Button>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center gap-3 py-6">
            <AlertTriangle className="h-6 w-6 text-red-500" />
            <div>
              <p className="font-medium text-red-700">{t('detail.paymentNotFound')}</p>
              <p className="text-sm text-red-600">
                {t('detail.paymentNotFoundDescription')}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Compact header with navigation */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={goBack}>
            <ChevronLeft className="mr-1 h-4 w-4" />
            {t('detail.backToList')}
          </Button>
          <div>
            <h1 className="text-xl font-bold tracking-tight">{t('detail.title')}</h1>
            <p className="text-sm text-muted-foreground font-mono">{payment.paymentReference}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {navigation.total > 0 && (
            <span className="text-sm text-muted-foreground mr-2">
              {navigation.currentIndex > 0 ? navigation.currentIndex : '?'} / {navigation.total}
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigation.prevId && navigateToPayment(navigation.prevId)}
            disabled={!navigation.hasPrev}
          >
            <ArrowLeft className="mr-1 h-4 w-4" />
            {t('detail.previous')}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigation.nextId && navigateToPayment(navigation.nextId)}
            disabled={!navigation.hasNext}
          >
            {t('detail.next')}
            <ArrowRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Main content - single dense card */}
        <div className="lg:col-span-2">
          <Card>
            <CardContent className="pt-5 space-y-4">
              {/* Row 1: Service + Status + SLA */}
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-muted-foreground">{t('detail.procedureType')}</p>
                  <p className="text-lg font-semibold truncate">{getWorkflowName(payment.workflowCode)}</p>
                  {payment.entityName && (
                    <Badge variant="outline" className="mt-1 text-xs font-normal">
                      {payment.entityName}
                    </Badge>
                  )}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <WorkflowStatusBadge status={payment.workflowStatus} />
                  <SLABadge
                    slaTargetDate={payment.slaTargetDate}
                    workflowStatus={payment.workflowStatus}
                  />
                </div>
              </div>

              {/* Row 2: References + Key Dates */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {payment.requestReference && (
                  <div>
                    <p className="text-xs text-muted-foreground">{t('detail.requestReference')}</p>
                    <p className="font-mono text-xs">{payment.requestReference}</p>
                  </div>
                )}
                <div>
                  <p className="text-xs text-muted-foreground">{t('detail.submitted')}</p>
                  <p className="text-xs">{formatDate(payment.submittedAt || payment.createdAt)}</p>
                </div>
                {payment.slaTargetDate && (
                  <div>
                    <p className="text-xs text-muted-foreground">{t('detail.slaLimit')}</p>
                    <p className="text-xs">{formatDate(payment.slaTargetDate)}</p>
                  </div>
                )}
                <div>
                  <p className="text-xs text-muted-foreground">{t('detail.waiting')}</p>
                  <p className="text-xs font-medium">{formatHours(payment.hoursWaiting)}</p>
                </div>
              </div>

              {/* Bundle Info — conditional */}
              {payment.workflowCode === 'BUNDLE_PAYMENT' && (
                <div className="space-y-1.5 px-3 py-2 bg-muted/50 rounded-lg text-sm">
                  <div className="flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-muted-foreground shrink-0" />
                    <span className="font-medium truncate">{payment.companyName || 'N/A'}</span>
                    {payment.registrationNumber && (
                      <span className="text-xs text-muted-foreground shrink-0">RC: {payment.registrationNumber}</span>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground pl-6">
                    {payment.commerceType && (
                      <span>{payment.commerceType.replace(/_/g, ' ')}</span>
                    )}
                    {payment.sectorActividad && (
                      <span>{payment.sectorActividad}</span>
                    )}
                    {payment.zoneTier && payment.zoneCode && (
                      <span>{t('detail.zone', { defaultValue: 'Zona' })} {payment.zoneCode} ({payment.zoneTier})</span>
                    )}
                    {payment.cityName && (
                      <span>{payment.cityName}</span>
                    )}
                    {payment.obligationCount != null && payment.obligationCount > 0 && (
                      <span className="flex items-center gap-1">
                        <Package className="h-3 w-3" />
                        {payment.obligationCount} {t('detail.obligations', { defaultValue: 'obligaciones' })}
                      </span>
                    )}
                  </div>
                </div>
              )}

              <Separator />

              {/* Row 3: Payment Breakdown (left) + Beneficiary (right) */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Payment breakdown */}
                <div className="space-y-2">
                  <div className="flex items-center gap-2 mb-2">
                    <CreditCard className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">{t('detail.paymentDetails')}</span>
                  </div>

                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{t('detail.paymentMethod')}</span>
                    <PaymentMethodBadge method={payment.paymentMethod} />
                  </div>

                  {payment.baseAmount != null && (
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">{t('detail.baseAmount')}</span>
                      <span>{formatCurrency(payment.baseAmount)}</span>
                    </div>
                  )}

                  {payment.calculationDetails?.supplements && payment.calculationDetails.supplements.length > 0 && (
                    <div className="border-l-2 border-muted pl-3 space-y-1">
                      {payment.calculationDetails.supplements.map((supp, idx) => (
                        <div key={idx} className="flex justify-between text-xs">
                          <span className="text-muted-foreground">{supp.nameEs} x{supp.quantity}</span>
                          <span>{formatCurrency(supp.subtotal)}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {payment.penalties != null && payment.penalties > 0 && (
                    <div className="flex justify-between text-sm text-orange-600">
                      <span>{t('detail.penalties')}</span>
                      <span>+{formatCurrency(payment.penalties)}</span>
                    </div>
                  )}

                  {payment.discounts != null && payment.discounts > 0 && (
                    <div className="flex justify-between text-sm text-green-600">
                      <span>{t('detail.discounts')}</span>
                      <span>-{formatCurrency(payment.discounts)}</span>
                    </div>
                  )}

                  <Separator />

                  <div className="flex justify-between text-lg font-bold">
                    <span>{t('detail.total')}</span>
                    <span>{formatCurrency(payment.totalAmount)}</span>
                  </div>
                </div>

                {/* Beneficiary + Account */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2 mb-2">
                    <User className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">{t('detail.beneficiary')}</span>
                  </div>

                  <div>
                    <p className="text-xs text-muted-foreground">{t('detail.fullName')}</p>
                    <p className="font-medium">{payment.beneficiaryName || payment.userName || 'N/A'}</p>
                  </div>

                  <div>
                    <p className="text-xs text-muted-foreground">{t('detail.accountEmail')}</p>
                    <p className="text-sm">{payment.userEmail || 'N/A'}</p>
                  </div>

                  {payment.beneficiaryName && payment.userName && payment.beneficiaryName !== payment.userName && (
                    <div>
                      <p className="text-xs text-muted-foreground">{t('detail.accountHolder')}</p>
                      <p className="text-sm text-muted-foreground">{payment.userName}</p>
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar - Actions only */}
        <div className="space-y-4">
          {/* Actions Card */}
          {isActionable && (
            <Card className="border-primary">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Receipt className="h-4 w-4" />
                  {t('detail.actions')}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-1">
                  <Label htmlFor="comment" className="text-xs">{t('detail.commentOptional')}</Label>
                  <Textarea
                    id="comment"
                    placeholder={t('detail.commentPlaceholder')}
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    rows={2}
                    disabled={isAnyLoading}
                  />
                </div>

                <div className="flex flex-col gap-2">
                  <Button
                    className="w-full bg-green-600 hover:bg-green-700"
                    onClick={() => setShowValidateConfirm(true)}
                    disabled={isAnyLoading}
                  >
                    {isValidating ? (
                      <><Loader2 className="mr-2 h-4 w-4 animate-spin" />{t('detail.validating')}</>
                    ) : (
                      <><CheckCircle className="mr-2 h-4 w-4" />{t('detail.validatePayment')}</>
                    )}
                  </Button>

                  <Button
                    variant="destructive"
                    className="w-full"
                    onClick={() => setShowRejectConfirm(true)}
                    disabled={isAnyLoading}
                  >
                    {isRejecting ? (
                      <><Loader2 className="mr-2 h-4 w-4 animate-spin" />{t('detail.rejecting')}</>
                    ) : (
                      <><XCircle className="mr-2 h-4 w-4" />{t('detail.rejectPayment')}</>
                    )}
                  </Button>

                  <Button
                    variant="outline"
                    className="w-full border-amber-300 text-amber-700 hover:bg-amber-50"
                    onClick={() => setShowEscalateConfirm(true)}
                    disabled={isAnyLoading}
                  >
                    {isEscalating ? (
                      <><Loader2 className="mr-2 h-4 w-4 animate-spin" />{t('escalation.escalating')}</>
                    ) : (
                      <><AlertTriangle className="mr-2 h-4 w-4" />{t('escalation.escalate')}</>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Already processed - compact inline */}
          {!isActionable && (
            <Card className="border-muted">
              <CardContent className="py-4">
                {payment.workflowStatus === 'completed' && (
                  <div className="flex items-center gap-3">
                    <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0" />
                    <div>
                      <p className="font-medium text-green-700 text-sm">{t('detail.paymentValidated')}</p>
                      <p className="text-xs text-muted-foreground">{t('detail.paymentAlreadyProcessed')}</p>
                    </div>
                  </div>
                )}
                {payment.workflowStatus === 'rejected_by_agent' && (
                  <div className="flex items-center gap-3">
                    <XCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
                    <div>
                      <p className="font-medium text-red-700 text-sm">{t('detail.paymentRejected')}</p>
                      <p className="text-xs text-muted-foreground">{t('detail.paymentWasRejected')}</p>
                    </div>
                  </div>
                )}
                {!['completed', 'rejected_by_agent', 'pending_agent_review'].includes(payment.workflowStatus) && (
                  <div className="flex items-center gap-3">
                    <AlertTriangle className="h-5 w-5 text-yellow-500 flex-shrink-0" />
                    <div>
                      <p className="font-medium text-sm">{t('detail.statusLabel', { status: payment.workflowStatus })}</p>
                      <p className="text-xs text-muted-foreground">{t('detail.noActionsAvailable')}</p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Validation Confirmation Dialog */}
      <AlertDialog open={showValidateConfirm} onOpenChange={setShowValidateConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-500" />
              {t('detail.confirmValidation')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t('detail.confirmValidationDescription', { reference: payment.paymentReference, amount: formatCurrency(payment.totalAmount) })}
              <br /><br />
              {t('detail.confirmValidationInfo')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isValidating}>{t('validationPage.buttons.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleValidate}
              disabled={isValidating}
              className="bg-green-600 hover:bg-green-700"
            >
              {isValidating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t('detail.validating')}
                </>
              ) : (
                t('detail.confirmValidationButton')
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Rejection Confirmation Dialog */}
      <AlertDialog open={showRejectConfirm} onOpenChange={setShowRejectConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <XCircle className="h-5 w-5 text-red-500" />
              {t('detail.confirmRejection')}
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-4">
                <p>
                  {t('detail.confirmRejectionDescription', { reference: payment.paymentReference })}
                </p>
                <div className="space-y-2">
                  <Label htmlFor="rejectReason">{t('detail.rejectionReason')}</Label>
                  <Textarea
                    id="rejectReason"
                    placeholder={t('detail.rejectionReasonPlaceholder')}
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    rows={3}
                    className="bg-background"
                  />
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isRejecting}>{t('validationPage.buttons.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleReject}
              disabled={isRejecting || !rejectReason.trim()}
              className="bg-red-600 hover:bg-red-700"
            >
              {isRejecting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t('detail.rejecting')}
                </>
              ) : (
                t('detail.confirmRejectionButton')
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Escalation Confirmation Dialog */}
      <AlertDialog open={showEscalateConfirm} onOpenChange={setShowEscalateConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              {t('escalation.dialogTitle')}
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-4">
                <p>{t('escalation.dialogDescription')}</p>
                <div className="space-y-2">
                  <Label htmlFor="escalateLevel">{t('escalation.level')}</Label>
                  <Select value={escalateLevel} onValueChange={setEscalateLevel}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">{t('escalation.levels.low')}</SelectItem>
                      <SelectItem value="medium">{t('escalation.levels.medium')}</SelectItem>
                      <SelectItem value="high">{t('escalation.levels.high')}</SelectItem>
                      <SelectItem value="critical">{t('escalation.levels.critical')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="escalateReason">{t('escalation.reason')}</Label>
                  <Textarea
                    id="escalateReason"
                    placeholder={t('escalation.reasonPlaceholder')}
                    value={escalateReason}
                    onChange={(e) => setEscalateReason(e.target.value)}
                    rows={3}
                    className="bg-background"
                  />
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isEscalating}>{t('validationPage.buttons.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleEscalate}
              disabled={isEscalating || escalateReason.trim().length < 10}
              className="bg-amber-600 hover:bg-amber-700"
            >
              {isEscalating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t('escalation.escalating')}
                </>
              ) : (
                t('escalation.confirm')
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Receipt Success Dialog */}
      {receiptData && (
        <ReceiptSuccessDialog
          open={!!receiptData}
          onClose={() => {
            setReceiptData(null);
            navigateAfterValidation();
          }}
          receiptNumber={receiptData.receiptNumber}
          paymentId={receiptData.paymentId}
        />
      )}
    </div>
  );
}
