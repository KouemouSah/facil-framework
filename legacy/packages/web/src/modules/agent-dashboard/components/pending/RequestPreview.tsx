/**
 * RequestPreview - Right column preview of selected request
 *
 * @module agent-dashboard/components/pending
 * @date 2026-01-26
 */

'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import {
  ChevronLeft,
  ChevronRight,
  Check,
  X,
  FileQuestion,
  ExternalLink,
  Loader2,
  ShieldAlert,
} from 'lucide-react';
import { toast } from 'sonner';
import { RequestInfoSection } from './sections/RequestInfoSection';
import { ExtractedDataSection } from './sections/ExtractedDataSection';
import { DocumentsSection } from './sections/DocumentsSection';
import { AppointmentSection } from './sections/AppointmentSection';
import { PaymentDetailsSection } from './sections/PaymentDetailsSection';
import { useDisplayConfigForWorkflow } from '@/modules/admin/hooks/useDisplayConfigs';
import type { ServiceRequestPreview, ActionType } from '../../services/agent-requests-api';
import type { EntityCode } from '../../types';

// =============================================================================
// DEFAULT PREVIEW SECTIONS
// =============================================================================

const DEFAULT_PREVIEW_SECTIONS = ['info', 'extractedData', 'documents', 'contact', 'appointment', 'paymentDetails'];


// =============================================================================
// PREDEFINED REJECTION REASONS
// =============================================================================

const REJECTION_REASONS = [
  { code: 'DIP_EXPIRE', labelKey: 'dipExpired' },
  { code: 'DOC_ILLEGIBLE', labelKey: 'docIllegible' },
  { code: 'PHOTO_NON_CONFORME', labelKey: 'photoNonCompliant' },
  { code: 'FRAUDE_SUSPECTEE', labelKey: 'fraudSuspected' },
  { code: 'DOC_FAUX', labelKey: 'docFalse' },
  { code: 'AUTRE', labelKey: 'other' },
] as const;

const ESCALATION_REASONS = [
  { code: 'DOCUMENT_SUSPECT', labelKey: 'documentSuspect' },
  { code: 'NEEDS_SUPERVISOR_DECISION', labelKey: 'needsSupervisor' },
  { code: 'SPECIAL_CASE', labelKey: 'specialCase' },
  { code: 'COMPLEX_VALIDATION', labelKey: 'complexValidation' },
  { code: 'OTHER', labelKey: 'other' },
] as const;

// =============================================================================
// PROPS
// =============================================================================

interface RequestPreviewProps {
  data: ServiceRequestPreview;
  entityCode: EntityCode;
  action?: ActionType;
  /** Workflow code for fetching display config (sections to show) */
  workflowCode?: string;
  onApprove: () => Promise<void>;
  onReject: (reason: string) => Promise<void>;
  onRequestDocuments: (requestedDocuments: string[], comments: string) => Promise<void>;
  onEscalate?: (reason: string, priorityBoost: number) => Promise<void>;
  onResolveEscalation?: () => Promise<void>;
  onNavigate: (direction: 'prev' | 'next') => void;
  canNavigatePrev: boolean;
  canNavigateNext: boolean;
  // External control of dialogs (for keyboard shortcuts)
  showRejectDialog?: boolean;
  onRejectDialogChange?: (open: boolean) => void;
  showRequestDocsDialog?: boolean;
  onRequestDocsDialogChange?: (open: boolean) => void;
  // Callback when appointment is created
  onAppointmentCreated?: () => void;
  // Escalation context (passed from list item for banner display)
  escalationReason?: string | null;
  escalatedAt?: string | null;
}

// =============================================================================
// COMPONENT
// =============================================================================

export function RequestPreview({
  data,
  entityCode,
  action = 'pending',
  workflowCode,
  onApprove,
  onReject,
  onRequestDocuments,
  onEscalate,
  onResolveEscalation,
  onNavigate,
  canNavigatePrev,
  canNavigateNext,
  showRejectDialog: externalShowRejectDialog,
  onRejectDialogChange,
  showRequestDocsDialog: externalShowRequestDocsDialog,
  onRequestDocsDialogChange,
  onAppointmentCreated,
  escalationReason,
  escalatedAt,
}: RequestPreviewProps) {
  // History action is read-only (no approve/reject buttons)
  // Escalated requests are also read-only (supervisor must decide)
  // DOCUMENTS_REQUIRED: agent already requested docs — waiting for citizen
  const isEscalationView = action === 'escalations';
  const isWaitingDocuments = data.status === 'DOCUMENTS_REQUIRED';
  const isReadOnly = action === 'history' || isEscalationView || !!escalatedAt || isWaitingDocuments;
  const locale = useLocale();
  const t = useTranslations('agent.pending.preview');

  // Fetch display config for this specific workflow (Option D: workflow-specific preview)
  const { data: displayConfig } = useDisplayConfigForWorkflow(
    workflowCode ?? '',
    !!workflowCode
  );

  // Determine which sections to show (from config or defaults)
  const previewSections = displayConfig?.preview_sections ?? DEFAULT_PREVIEW_SECTIONS;
  const shouldShowSection = (sectionId: string) => previewSections.includes(sectionId);


  const [isApproving, setIsApproving] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);
  const [isRequestingDocs, setIsRequestingDocs] = useState(false);
  const [isEscalating, setIsEscalating] = useState(false);
  const [isResolving, setIsResolving] = useState(false);
  const [internalShowRejectDialog, setInternalShowRejectDialog] = useState(false);
  const [internalShowRequestDocsDialog, setInternalShowRequestDocsDialog] = useState(false);
  const [showEscalateDialog, setShowEscalateDialog] = useState(false);
  const [selectedReasonCode, setSelectedReasonCode] = useState<string>('');
  const [customReason, setCustomReason] = useState('');
  const [selectedDocCodes, setSelectedDocCodes] = useState<string[]>([]);
  const [docsComment, setDocsComment] = useState('');
  const [escalationReasonCode, setEscalationReasonCode] = useState<string>('');
  const [escalationCustomReason, setEscalationCustomReason] = useState('');
  const [escalationPriorityBoost, setEscalationPriorityBoost] = useState(10);

  // Use external control if provided, otherwise use internal state
  const showRejectDialog = externalShowRejectDialog ?? internalShowRejectDialog;
  const setShowRejectDialog = onRejectDialogChange ?? setInternalShowRejectDialog;
  const showRequestDocsDialog = externalShowRequestDocsDialog ?? internalShowRequestDocsDialog;
  const setShowRequestDocsDialog = onRequestDocsDialogChange ?? setInternalShowRequestDocsDialog;

  const entityPath = entityCode.toLowerCase().replace('_', '-');
  const detailUrl = `/${locale}/dashboard/agent/${entityPath}/request/${data.id}`;

  // Handle approve
  const handleApprove = async () => {
    setIsApproving(true);
    try {
      await onApprove();
      toast.success(t('approveSuccess'));
    } catch (error) {
      console.error('Approve error:', error);
      toast.error(t('approveError'));
    } finally {
      setIsApproving(false);
    }
  };

  // Handle reject
  const handleReject = async () => {
    if (!selectedReasonCode) {
      toast.error(t('rejectReasonRequired'));
      return;
    }
    // For "AUTRE", require custom reason
    if (selectedReasonCode === 'AUTRE' && !customReason.trim()) {
      toast.error(t('customReasonRequired'));
      return;
    }

    // Build final reason: predefined label + custom text if applicable
    const selectedReason = REJECTION_REASONS.find(r => r.code === selectedReasonCode);
    const predefinedLabel = selectedReason ? t(`rejectReasons.${selectedReason.labelKey}`) : '';
    const finalReason = selectedReasonCode === 'AUTRE'
      ? customReason.trim()
      : `${predefinedLabel}${customReason.trim() ? ` - ${customReason.trim()}` : ''}`;

    setIsRejecting(true);
    try {
      await onReject(finalReason);
      toast.success(t('rejectSuccess'));
      setShowRejectDialog(false);
      setSelectedReasonCode('');
      setCustomReason('');
    } catch (error) {
      console.error('Reject error:', error);
      toast.error(t('rejectError'));
    } finally {
      setIsRejecting(false);
    }
  };

  // Handle request documents
  const handleRequestDocuments = async () => {
    const hasDocs = selectedDocCodes.length > 0;
    const hasComment = docsComment.trim().length > 0;

    if (!hasDocs && !hasComment) {
      toast.error(t('requestDocsAtLeastOne'));
      return;
    }

    // Auto-generate comment from selected document names if no custom comment
    let finalComment = docsComment.trim();
    if (hasDocs && !hasComment) {
      const docNames = selectedDocCodes
        .map((code) => data.documents.find((d) => d.code === code)?.name ?? code)
        .join(', ');
      finalComment = `${t('requestDocsAutoComment')}: ${docNames}`;
    }

    setIsRequestingDocs(true);
    try {
      await onRequestDocuments(hasDocs ? selectedDocCodes : [], finalComment);
      toast.success(t('requestDocsSuccess'));
      setShowRequestDocsDialog(false);
      setSelectedDocCodes([]);
      setDocsComment('');
    } catch (error) {
      console.error('Request documents error:', error);
      toast.error(t('requestDocsError'));
    } finally {
      setIsRequestingDocs(false);
    }
  };

  // Handle escalation
  const handleEscalate = async () => {
    if (!escalationReasonCode) {
      toast.error(t('escalateReasonRequired'));
      return;
    }
    if (escalationReasonCode === 'OTHER' && !escalationCustomReason.trim()) {
      toast.error(t('escalateCustomReasonRequired'));
      return;
    }

    const selectedReason = ESCALATION_REASONS.find(r => r.code === escalationReasonCode);
    const predefinedLabel = selectedReason ? t(`escalateReasons.${selectedReason.labelKey}`) : '';
    const finalReason = escalationReasonCode === 'OTHER'
      ? escalationCustomReason.trim()
      : `${predefinedLabel}${escalationCustomReason.trim() ? ` - ${escalationCustomReason.trim()}` : ''}`;

    if (finalReason.length < 10) {
      toast.error(t('escalateReasonTooShort'));
      return;
    }

    setIsEscalating(true);
    try {
      await onEscalate?.(finalReason, escalationPriorityBoost);
      toast.success(t('escalateSuccess'));
      setShowEscalateDialog(false);
      setEscalationReasonCode('');
      setEscalationCustomReason('');
      setEscalationPriorityBoost(10);
    } catch (error) {
      console.error('Escalate error:', error);
      toast.error(t('escalateError'));
    } finally {
      setIsEscalating(false);
    }
  };

  const toggleDocCode = (code: string) => {
    setSelectedDocCodes((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  };

  return (
    <div className="flex flex-col h-full">
      {/* Navigation Header */}
      <div className="flex items-center justify-between p-3 border-b bg-muted/30">
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onNavigate('prev')}
            disabled={!canNavigatePrev}
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            {t('prev')}
          </Button>
          <span className="text-sm text-muted-foreground">
            {(data.listIndex ?? 0) + 1} / {data.listTotal ?? 1}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onNavigate('next')}
            disabled={!canNavigateNext}
          >
            {t('next')}
            <ChevronRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
        <Link href={detailUrl}>
          <Button variant="outline" size="sm">
            {t('viewDetail')}
            <ExternalLink className="h-4 w-4 ml-2" />
          </Button>
        </Link>
      </div>

      {/* Escalation Banner (only in escalation view) */}
      {isEscalationView && escalationReason && (
        <div className="mx-3 mt-3 p-3 bg-orange-50 border border-orange-200 rounded-lg">
          <div className="flex items-start gap-2">
            <ShieldAlert className="h-4 w-4 text-orange-500 mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-orange-800">{t('escalationBanner.title')}</p>
              <p className="text-sm text-orange-700 mt-0.5">{escalationReason}</p>
              {escalatedAt && (
                <p className="text-xs text-orange-500 mt-1">
                  {t('escalationBanner.since', { date: new Date(escalatedAt).toLocaleString() })}
                </p>
              )}
            </div>
            {onResolveEscalation && (
              <Button
                size="sm"
                variant="outline"
                className="border-orange-300 text-orange-700 hover:bg-orange-100 flex-shrink-0"
                onClick={async () => {
                  setIsResolving(true);
                  try {
                    await onResolveEscalation();
                    toast.success(t('escalationBanner.resolved'));
                  } catch {
                    toast.error(t('escalationBanner.resolveError'));
                  } finally {
                    setIsResolving(false);
                  }
                }}
                disabled={isResolving}
              >
                {isResolving ? (
                  <Loader2 className="h-3 w-3 animate-spin mr-1" />
                ) : (
                  <Check className="h-3 w-3 mr-1" />
                )}
                {t('escalationBanner.resolve')}
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Content - Sections rendered based on display config */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {/* Section: Request Info + Contact (merged compact header) */}
        {shouldShowSection('info') && (
          <RequestInfoSection
            reference={data.reference}
            workflowLabel={data.workflowLabel}
            solicitudType={data.solicitudType}
            motivo={data.motivo}
            priority={data.priority}
            slaStatus={data.slaStatus}
            slaRemainingHours={data.slaRemainingHours}
            isMinor={data.isMinor}
            batchReference={data.batchReference}
            batchId={data.batchId}
            contactEmail={data.contactEmail}
            contactPhone={data.contactPhone}
          />
        )}

        {/* Section: Extracted Data - structured sections from workflow config */}
        {shouldShowSection('extractedData') && (
          <ExtractedDataSection
            dataSections={data.dataSections}
            documents={data.documents}
            requestId={data.id}
          />
        )}

        {/* Section: Documents */}
        {shouldShowSection('documents') && (
          <DocumentsSection
            documents={data.documents}
            documentsCount={data.documentsCount}
            requestId={data.id}
          />
        )}

        {/* Compact row: Appointment + Payment side by side */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {/* Section: Appointment */}
          {shouldShowSection('appointment') && (
            <AppointmentSection
              appointment={data.appointment}
              requestId={data.id}
              entityCode={entityCode}
              onAppointmentCreated={onAppointmentCreated}
            />
          )}

          {/* Section: Payment Details */}
          {shouldShowSection('paymentDetails') && (
            <PaymentDetailsSection
              status={data.paymentStatus}
              amount={data.paymentAmount}
              currency={data.paymentCurrency}
              method={data.paymentMethod}
              paidAt={data.paymentPaidAt}
              reference={data.paymentReference}
              receiptNumber={data.paymentReceiptNumber}
            />
          )}
        </div>
      </div>

      {/* Waiting for documents banner */}
      {isWaitingDocuments && (
        <div className="px-3 py-3 border-t bg-amber-50">
          <div className="flex items-center gap-2 text-amber-700">
            <FileQuestion className="h-4 w-4 flex-shrink-0" />
            <span className="text-sm font-medium">{t('waitingDocuments')}</span>
          </div>
        </div>
      )}

      {/* Actions Footer - Hidden for read-only (history/escalation/waiting docs) mode */}
      {!isReadOnly && (
        <div className="px-3 py-2 border-t bg-muted/30">
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={handleApprove}
              disabled={isApproving || isRejecting || isRequestingDocs}
              className="flex-1 h-8 bg-green-600 hover:bg-green-700"
            >
              {isApproving ? (
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
              ) : (
                <Check className="h-3.5 w-3.5 mr-1.5" />
              )}
              {isApproving ? t('approving') : t('approve')}
              <kbd className="ml-1.5 px-1 py-0.5 text-[10px] font-mono bg-green-700/50 rounded">A</kbd>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowRequestDocsDialog(true)}
              disabled={isApproving || isRejecting || isRequestingDocs}
              className="flex-1 h-8 border-amber-500 text-amber-600 hover:bg-amber-50"
            >
              <FileQuestion className="h-3.5 w-3.5 mr-1.5" />
              {t('requestDocs')}
              <kbd className="ml-1.5 px-1 py-0.5 text-[10px] font-mono bg-amber-100 rounded">D</kbd>
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setShowRejectDialog(true)}
              disabled={isApproving || isRejecting || isRequestingDocs || isEscalating}
              className="flex-1 h-8"
            >
              <X className="h-3.5 w-3.5 mr-1.5" />
              {t('reject')}
              <kbd className="ml-1.5 px-1 py-0.5 text-[10px] font-mono bg-red-700/50 rounded">R</kbd>
            </Button>
            {onEscalate && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowEscalateDialog(true)}
                disabled={isApproving || isRejecting || isRequestingDocs || isEscalating}
                className="h-8 border-orange-400 text-orange-600 hover:bg-orange-50"
              >
                <ShieldAlert className="h-3.5 w-3.5 mr-1.5" />
                {t('escalate')}
                <kbd className="ml-1.5 px-1 py-0.5 text-[10px] font-mono bg-orange-100 rounded">E</kbd>
              </Button>
            )}
          </div>
          <p className="text-[10px] text-muted-foreground text-center mt-1">
            {t('keyboardHint')}
          </p>
        </div>
      )}

      {/* Reject Dialog */}
      <Dialog open={showRejectDialog} onOpenChange={(open) => {
        setShowRejectDialog(open);
        if (!open) {
          setSelectedReasonCode('');
          setCustomReason('');
        }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('rejectTitle')}</DialogTitle>
            <DialogDescription>
              {t('rejectDescription', { reference: data.reference })}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {/* Predefined reasons select */}
            <div className="space-y-2">
              <Label>{t('selectReason')}</Label>
              <Select
                value={selectedReasonCode}
                onValueChange={setSelectedReasonCode}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t('selectReasonPlaceholder')} />
                </SelectTrigger>
                <SelectContent>
                  {REJECTION_REASONS.map((reason) => (
                    <SelectItem key={reason.code} value={reason.code}>
                      {t(`rejectReasons.${reason.labelKey}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Custom reason textarea - always visible for additional details */}
            <div className="space-y-2">
              <Label>
                {selectedReasonCode === 'AUTRE'
                  ? t('customReasonRequired')
                  : t('additionalDetails')}
              </Label>
              <Textarea
                placeholder={selectedReasonCode === 'AUTRE'
                  ? t('customReasonPlaceholder')
                  : t('additionalDetailsPlaceholder')}
                value={customReason}
                onChange={(e) => setCustomReason(e.target.value)}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowRejectDialog(false)}
              disabled={isRejecting}
            >
              {t('cancelReject')}
            </Button>
            <Button
              variant="destructive"
              onClick={handleReject}
              disabled={isRejecting || !selectedReasonCode || (selectedReasonCode === 'AUTRE' && !customReason.trim())}
            >
              {isRejecting ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : null}
              {isRejecting ? t('rejecting') : t('confirmReject')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {/* Request Documents Dialog */}
      <Dialog open={showRequestDocsDialog} onOpenChange={(open) => {
        setShowRequestDocsDialog(open);
        if (!open) {
          setSelectedDocCodes([]);
          setDocsComment('');
        }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('requestDocsTitle')}</DialogTitle>
            <DialogDescription>
              {t('requestDocsDescription', { reference: data.reference })}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {/* Document checkboxes (optional) */}
            <div className="space-y-2">
              <Label>{t('requestDocsSelectLabel')} <span className="text-muted-foreground font-normal">({t('requestDocsOptional')})</span></Label>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {data.documents.map((doc) => (
                  <label
                    key={doc.code}
                    className="flex items-center gap-2 p-2 rounded hover:bg-muted cursor-pointer"
                  >
                    <Checkbox
                      checked={selectedDocCodes.includes(doc.code)}
                      onCheckedChange={() => toggleDocCode(doc.code)}
                    />
                    <span className="text-sm">{doc.name}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Comments textarea */}
            <div className="space-y-2">
              <Label>{t('requestDocsCommentLabel')}</Label>
              <Textarea
                placeholder={t('requestDocsCommentPlaceholder')}
                value={docsComment}
                onChange={(e) => setDocsComment(e.target.value)}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowRequestDocsDialog(false)}
              disabled={isRequestingDocs}
            >
              {t('cancelReject')}
            </Button>
            <Button
              onClick={handleRequestDocuments}
              disabled={isRequestingDocs || (selectedDocCodes.length === 0 && !docsComment.trim())}
              className="bg-amber-600 hover:bg-amber-700"
            >
              {isRequestingDocs ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : null}
              {isRequestingDocs ? t('requestDocsSubmitting') : t('requestDocsSubmit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Escalation Dialog */}
      <Dialog open={showEscalateDialog} onOpenChange={(open) => {
        setShowEscalateDialog(open);
        if (!open) {
          setEscalationReasonCode('');
          setEscalationCustomReason('');
          setEscalationPriorityBoost(10);
        }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-orange-500" />
              {t('escalateTitle')}
            </DialogTitle>
            <DialogDescription>
              {t('escalateDescription', { reference: data.reference })}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {/* Predefined escalation reasons */}
            <div className="space-y-2">
              <Label>{t('escalateSelectReason')}</Label>
              <Select value={escalationReasonCode} onValueChange={setEscalationReasonCode}>
                <SelectTrigger>
                  <SelectValue placeholder={t('escalateSelectReasonPlaceholder')} />
                </SelectTrigger>
                <SelectContent>
                  {ESCALATION_REASONS.map((reason) => (
                    <SelectItem key={reason.code} value={reason.code}>
                      {t(`escalateReasons.${reason.labelKey}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Custom reason / additional details */}
            <div className="space-y-2">
              <Label>
                {escalationReasonCode === 'OTHER'
                  ? t('escalateCustomReasonRequired')
                  : t('escalateAdditionalDetails')}
              </Label>
              <Textarea
                placeholder={t('escalateReasonPlaceholder')}
                value={escalationCustomReason}
                onChange={(e) => setEscalationCustomReason(e.target.value)}
                rows={3}
                maxLength={500}
              />
              <p className="text-xs text-muted-foreground">
                {escalationCustomReason.length}/500
              </p>
            </div>

            {/* Priority boost */}
            <div className="space-y-2">
              <Label>{t('escalatePriority')}</Label>
              <Select
                value={String(escalationPriorityBoost)}
                onValueChange={(v) => setEscalationPriorityBoost(Number(v))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">{t('escalatePriorityNormal')}</SelectItem>
                  <SelectItem value="25">{t('escalatePriorityHigh')}</SelectItem>
                  <SelectItem value="50">{t('escalatePriorityCritical')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowEscalateDialog(false)}
              disabled={isEscalating}
            >
              {t('cancelReject')}
            </Button>
            <Button
              onClick={handleEscalate}
              disabled={isEscalating || !escalationReasonCode || (escalationReasonCode === 'OTHER' && !escalationCustomReason.trim())}
              className="bg-orange-600 hover:bg-orange-700"
            >
              {isEscalating ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <ShieldAlert className="h-4 w-4 mr-2" />
              )}
              {isEscalating ? t('escalating') : t('confirmEscalate')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default RequestPreview;
