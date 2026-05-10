/**
 * PaymentDetailPanel
 * Compact detail view for a payment, used in the split-view validation page.
 * Shows service info, payment breakdown, citizen info, timeline, and actions.
 */

'use client';

import { useState } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import { getLocalizedField } from '@/core/utils/i18n-helpers';
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
  CheckCircle,
  XCircle,
  AlertTriangle,
  Loader2,
  User,
  CreditCard,
  ArrowLeft,
  ArrowRight,
  ExternalLink,
  UserCog,
  Building2,
  Package,
  Mail,
  Phone,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import {
  PaymentMethodBadge,
  WorkflowStatusBadge,
  SLABadge,
} from './index';
import type { PendingPayment } from '../types';

// =============================================================================
// TYPES
// =============================================================================

interface PaymentDetailPanelProps {
  payment: PendingPayment;
  /** Navigation: current index in the list (1-based) */
  currentIndex?: number;
  /** Navigation: total items in list */
  totalItems?: number;
  onNavigate?: (direction: 'prev' | 'next') => void;
  hasPrev?: boolean;
  hasNext?: boolean;
  /** Open the full detail page */
  onOpenFullDetail?: (paymentId: string) => void;
  /** Action callbacks */
  onValidate?: (paymentId: string, comment?: string) => Promise<void>;
  onReject?: (paymentId: string, reason: string) => Promise<void>;
  onEscalate?: (paymentId: string, reason: string, level: string) => Promise<void>;
  onReassign?: (paymentId: string) => void;
  isSupervisor?: boolean;
  isValidating?: boolean;
  isRejecting?: boolean;
  isEscalating?: boolean;
}

// =============================================================================
// HELPERS
// =============================================================================

function formatCurrency(amount: number | undefined): string {
  if (amount === undefined || amount === null) return 'N/A';
  return new Intl.NumberFormat('es-GQ', {
    style: 'currency',
    currency: 'XAF',
    minimumFractionDigits: 0,
  }).format(amount);
}

// =============================================================================
// COMPONENT
// =============================================================================

export function PaymentDetailPanel({
  payment,
  currentIndex,
  totalItems,
  onNavigate,
  hasPrev = false,
  hasNext = false,
  onOpenFullDetail,
  onValidate,
  onReject,
  onEscalate,
  onReassign,
  isSupervisor = false,
  isValidating = false,
  isRejecting = false,
  isEscalating = false,
}: PaymentDetailPanelProps) {
  const t = useTranslations('treasury');
  const locale = useLocale();

  // Dialog states
  const [comment, setComment] = useState('');
  const [showRejectDialog, setShowRejectDialog] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [showEscalateDialog, setShowEscalateDialog] = useState(false);
  const [escalateReason, setEscalateReason] = useState('');
  const [escalateLevel, setEscalateLevel] = useState('medium');

  const isActionable = payment.workflowStatus === 'pending_agent_review';
  const isAnyLoading = isValidating || isRejecting || isEscalating;

  // Workflow name helper
  const getWorkflowName = (code: string | undefined): string => {
    if (!code) return t('validationPage.unspecified');
    const normalizedKey = code.toUpperCase().replace(/[^A-Z_]/g, '');
    if (t.has(`workflowNames.${normalizedKey}`)) {
      return t(`workflowNames.${normalizedKey}`);
    }
    return code.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());
  };

  // Action handlers
  const handleValidate = async () => {
    if (onValidate) {
      await onValidate(payment.id, comment || undefined);
      setComment('');
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim() || !onReject) return;
    await onReject(payment.id, rejectReason);
    setShowRejectDialog(false);
    setRejectReason('');
  };

  const handleEscalate = async () => {
    if (!escalateReason.trim() || !onEscalate) return;
    await onEscalate(payment.id, escalateReason, escalateLevel);
    setShowEscalateDialog(false);
    setEscalateReason('');
  };

  return (
    <div className="flex flex-col h-full">
      {/* Navigation Header */}
      <div className="flex items-center justify-between p-3 border-b bg-muted/30 shrink-0">
        <div className="flex items-center gap-2">
          {onNavigate && (
            <>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                onClick={() => onNavigate('prev')}
                disabled={!hasPrev}
              >
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                onClick={() => onNavigate('next')}
                disabled={!hasNext}
              >
                <ArrowRight className="h-4 w-4" />
              </Button>
            </>
          )}
          {currentIndex !== undefined && totalItems !== undefined && (
            <span className="text-xs text-muted-foreground">
              {currentIndex} / {totalItems}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm font-mono font-medium">{payment.paymentReference}</span>
          {onOpenFullDetail && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => onOpenFullDetail(payment.id)}
              title={t('detail.openFullDetail')}
            >
              <ExternalLink className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      {/* Content — optimized for zero-scroll decision-making */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {/* Service + Status Row */}
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="font-semibold truncate">{getWorkflowName(payment.workflowCode)}</p>
            <div className="flex items-center gap-2 mt-0.5">
              {isSupervisor && payment.entityName && (
                <Badge variant="outline" className="text-xs font-normal">
                  {payment.entityName}
                </Badge>
              )}
              {payment.requestReference && (
                <span className="text-xs font-mono text-muted-foreground">{payment.requestReference}</span>
              )}
            </div>
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0">
            <WorkflowStatusBadge status={payment.workflowStatus} />
            <SLABadge
              slaTargetDate={payment.slaTargetDate}
              workflowStatus={payment.workflowStatus}
            />
          </div>
        </div>

        {/* Bundle Info — conditional for BUNDLE_PAYMENT */}
        {payment.workflowCode === 'BUNDLE_PAYMENT' && (
          <div className="space-y-1.5 px-2 py-2 bg-muted/50 rounded text-sm">
            <div className="flex items-center gap-2">
              <Building2 className="h-4 w-4 text-muted-foreground shrink-0" />
              <span className="font-medium truncate">{payment.companyName || 'N/A'}</span>
              {payment.registrationNumber && (
                <span className="text-xs text-muted-foreground shrink-0">RC: {payment.registrationNumber}</span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground pl-6">
              {payment.commerceType && (
                <span>{payment.commerceType.replace(/_/g, ' ')}</span>
              )}
              {payment.sectorActividad && (
                <span>{payment.sectorActividad}</span>
              )}
              {payment.zoneTier && payment.zoneCode && (
                <Badge variant="secondary" className="text-[10px] h-4 px-1">
                  {t('detail.zone', { defaultValue: 'Zona' })} {payment.zoneCode} ({payment.zoneTier})
                </Badge>
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

        {/* Applicant — compact inline header */}
        <div className="flex items-center gap-3 text-xs text-muted-foreground px-1 flex-wrap">
          <div className="flex items-center gap-1.5 min-w-0">
            <User className="h-3.5 w-3.5 shrink-0" />
            <span className="font-medium text-foreground truncate">{payment.beneficiaryName || payment.userName || 'N/A'}</span>
          </div>
          <span className="text-border">|</span>
          <div className="flex items-center gap-1 min-w-0">
            <Mail className="h-3 w-3 shrink-0" />
            <span className="truncate">{payment.userEmail || 'N/A'}</span>
          </div>
          {payment.userPhone && (
            <>
              <span className="text-border">|</span>
              <div className="flex items-center gap-1">
                <Phone className="h-3 w-3 shrink-0" />
                <span>{payment.userPhone}</span>
              </div>
            </>
          )}
        </div>

        <Separator />

        {/* Payment breakdown + Obligations (bundle) or Beneficiary (non-bundle) */}
        <div className="grid grid-cols-2 gap-4">
          {/* Left: Payment breakdown */}
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2 mb-1">
              <CreditCard className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-xs font-medium text-muted-foreground">{t('detail.paymentDetails')}</span>
            </div>

            <div className="flex justify-between">
              <span className="text-muted-foreground">{t('detail.paymentMethod')}</span>
              <PaymentMethodBadge method={payment.paymentMethod} />
            </div>

            {payment.baseAmount != null && (
              <div className="flex justify-between">
                <span className="text-xs text-muted-foreground">{t('detail.baseAmount')}</span>
                <span className="text-xs">{formatCurrency(payment.baseAmount)}</span>
              </div>
            )}

            {payment.calculationDetails?.supplements && payment.calculationDetails.supplements.length > 0 && (
              <div className="border-l-2 border-muted pl-2 space-y-0.5">
                {payment.calculationDetails.supplements.map((supp, idx) => (
                  <div key={idx} className="flex justify-between text-xs">
                    <span className="text-muted-foreground truncate mr-2">
                      {getLocalizedField(supp as unknown as Record<string, unknown>, 'name', locale)} x{supp.quantity}
                    </span>
                    <span className="shrink-0">{formatCurrency(supp.subtotal)}</span>
                  </div>
                ))}
              </div>
            )}

            {payment.penalties != null && payment.penalties > 0 && (
              <div className="flex justify-between text-xs text-orange-600">
                <span>{t('detail.penalties')}</span>
                <span>+{formatCurrency(payment.penalties)}</span>
              </div>
            )}

            {payment.discounts != null && payment.discounts > 0 && (
              <div className="flex justify-between text-xs text-green-600">
                <span>{t('detail.discounts')}</span>
                <span>-{formatCurrency(payment.discounts)}</span>
              </div>
            )}

            <Separator />

            <div className="flex justify-between font-bold">
              <span>{t('detail.total')}</span>
              <span>{formatCurrency(payment.totalAmount)}</span>
            </div>
          </div>

          {/* Right: Obligations list (bundle) or Beneficiary details (non-bundle) */}
          <div className="space-y-2 text-sm">
            {payment.workflowCode === 'BUNDLE_PAYMENT' && payment.obligations && payment.obligations.length > 0 ? (
              <>
                <div className="flex items-center gap-2 mb-1">
                  <Package className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-xs font-medium text-muted-foreground">
                    {t('detail.obligations', { defaultValue: 'obligaciones' })} ({payment.obligations.length})
                  </span>
                </div>
                <div className="space-y-1">
                  {payment.obligations.map((obl, idx) => (
                    <div key={idx} className="flex justify-between text-xs">
                      <span className="text-muted-foreground truncate mr-2">{obl.name}</span>
                      <span className="shrink-0 font-medium">{formatCurrency(obl.amount)}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <>
                <div className="flex items-center gap-2 mb-1">
                  <User className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-xs font-medium text-muted-foreground">{t('detail.applicant')}</span>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">{t('detail.beneficiary')}</p>
                  <p className="font-medium text-sm">{payment.beneficiaryName || payment.userName || 'N/A'}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">{t('detail.accountEmail')}</p>
                  <p className="text-xs truncate">{payment.userEmail || 'N/A'}</p>
                </div>
                {payment.beneficiaryName && payment.userName && payment.beneficiaryName !== payment.userName && (
                  <div>
                    <p className="text-xs text-muted-foreground">{t('detail.accountHolder')}</p>
                    <p className="text-xs text-muted-foreground">{payment.userName}</p>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Assigned agent (supervisor view) */}
        {isSupervisor && (
          <>
            <Separator />
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm">
                <UserCog className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">{t('detail.assignedAgent')}:</span>
                <span className="text-xs font-medium">
                  {payment.assignedAgentName || t('validationPage.unassigned')}
                </span>
              </div>
              {onReassign && (
                <Button
                  variant="outline"
                  size="sm"
                  className="h-6 text-xs"
                  onClick={() => onReassign(payment.id)}
                >
                  <UserCog className="h-3 w-3 mr-1" />
                  {t('validationPage.reassign.button')}
                </Button>
              )}
            </div>
          </>
        )}

        {/* Escalation info — conditional */}
        {payment.escalationLevel && (
          <>
            <Separator />
            <div className="p-2 bg-amber-50 border border-amber-200 rounded text-xs">
              <p className="font-medium text-amber-800">{t('escalation.escalated')}</p>
              <p className="text-amber-700 mt-0.5">{payment.escalationReason}</p>
            </div>
          </>
        )}

        {/* Already processed banner */}
        {!isActionable && (
          <div className="text-center py-3">
            {payment.workflowStatus === 'completed' || payment.workflowStatus === 'approved_by_agent' ? (
              <div className="flex items-center justify-center gap-2">
                <CheckCircle className="h-5 w-5 text-green-500" />
                <p className="font-medium text-green-700">{t('detail.paymentValidated')}</p>
              </div>
            ) : payment.workflowStatus === 'rejected_by_agent' ? (
              <div className="flex items-center justify-center gap-2">
                <XCircle className="h-5 w-5 text-red-500" />
                <p className="font-medium text-red-700">{t('detail.paymentRejected')}</p>
              </div>
            ) : (
              <div className="flex items-center justify-center gap-2">
                <AlertTriangle className="h-5 w-5 text-yellow-500" />
                <p className="font-medium">{payment.workflowStatus}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Actions Footer — fixed at bottom */}
      {isActionable && (
        <div className="p-3 border-t bg-muted/30 space-y-2 shrink-0">
          {/* Comment input — compact, expands on focus */}
          <Textarea
            placeholder={t('detail.commentPlaceholder')}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={1}
            disabled={isAnyLoading}
            className="text-sm resize-none focus:rows-3 min-h-[2rem]"
          />

          {/* Action buttons */}
          <div className="flex gap-2">
            <Button
              size="sm"
              className="flex-1 bg-green-600 hover:bg-green-700"
              onClick={handleValidate}
              disabled={isAnyLoading}
            >
              {isValidating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  <CheckCircle className="h-4 w-4 mr-1" />
                  {t('detail.validatePayment')}
                </>
              )}
            </Button>
            <Button
              size="sm"
              variant="destructive"
              className="flex-1"
              onClick={() => setShowRejectDialog(true)}
              disabled={isAnyLoading}
            >
              {isRejecting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  <XCircle className="h-4 w-4 mr-1" />
                  {t('detail.rejectPayment')}
                </>
              )}
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="border-amber-300 text-amber-700 hover:bg-amber-50"
              onClick={() => setShowEscalateDialog(true)}
              disabled={isAnyLoading}
            >
              <AlertTriangle className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Reject Dialog */}
      <AlertDialog open={showRejectDialog} onOpenChange={setShowRejectDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <XCircle className="h-5 w-5 text-red-500" />
              {t('detail.confirmRejection')}
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-4">
                <p>{t('detail.confirmRejectionDescription', { reference: payment.paymentReference })}</p>
                <div className="space-y-2">
                  <Label htmlFor="panelRejectReason">{t('detail.rejectionReason')}</Label>
                  <Textarea
                    id="panelRejectReason"
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
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              {t('detail.confirmRejectionButton')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Escalate Dialog */}
      <AlertDialog open={showEscalateDialog} onOpenChange={setShowEscalateDialog}>
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
                  <Label htmlFor="panelEscalateLevel">{t('escalation.level')}</Label>
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
                  <Label htmlFor="panelEscalateReason">{t('escalation.reason')}</Label>
                  <Textarea
                    id="panelEscalateReason"
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
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              {t('escalation.confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
