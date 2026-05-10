/**
 * DocumentPreviewDialog - Shared document preview with agent validation actions
 *
 * Used in:
 * - DocumentsSection (splitview compact list)
 * - DocumentosTab (detail page)
 *
 * Agent actions: Validate (approve) / Reject (with reason)
 * Shows confidence score badge when available.
 *
 * @module agent-dashboard/components/shared
 * @date 2026-03-07
 */

'use client';

import React, { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  FileText,
  ExternalLink,
  CheckCircle2,
  XCircle,
  Loader2,
  ShieldCheck,
  ShieldX,
  ZoomIn,
  ZoomOut,
  RotateCcw,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { validateDocument, rejectDocument } from '../../services/agent-requests-api';
import { useImageZoom } from '../../hooks/useImageZoom';

// =============================================================================
// TYPES
// =============================================================================

export interface PreviewDocumentInfo {
  id: string;
  code: string;
  name: string;
  mimeType?: string | null;
  validationStatus: string;
  confidence?: number | null;
}

interface DocumentPreviewDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The document being previewed */
  document: PreviewDocumentInfo | null;
  /** Signed URL for the document */
  previewUrl: string | null;
  /** Enable agent validation actions (validate/reject) */
  agentActions?: boolean;
  /** Callback after validate/reject to refresh parent state */
  onDocumentStatusChanged?: (documentId: string, newStatus: 'validated' | 'rejected') => void;
}

// =============================================================================
// HELPERS
// =============================================================================

function isPdf(mimeType?: string | null, fileName?: string | null): boolean {
  if (mimeType === 'application/pdf') return true;
  if (fileName?.toLowerCase().endsWith('.pdf')) return true;
  return false;
}

function isImage(mimeType?: string | null, fileName?: string | null): boolean {
  if (mimeType?.startsWith('image/')) return true;
  const ext = fileName?.split('.').pop()?.toLowerCase();
  return ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'].includes(ext || '');
}

function confidenceColor(confidence: number): string {
  if (confidence >= 0.85) return 'bg-green-100 text-green-700';
  if (confidence >= 0.6) return 'bg-orange-100 text-orange-700';
  return 'bg-red-100 text-red-700';
}

// =============================================================================
// COMPONENT
// =============================================================================

export function DocumentPreviewDialog({
  open,
  onOpenChange,
  document: doc,
  previewUrl,
  agentActions = false,
  onDocumentStatusChanged,
}: DocumentPreviewDialogProps) {
  const t = useTranslations('agent.pending.preview');

  // Reject form state
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [isValidating, setIsValidating] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);
  // Track local status override after action (so UI updates without refetch)
  const [localStatus, setLocalStatus] = useState<string | null>(null);

  // Zoom state for images (shared hook handles passive wheel listener)
  const { zoomLevel, containerRef: imgContainerRef, zoomIn: handleZoomIn, zoomOut: handleZoomOut, zoomReset: handleZoomReset, setZoomLevel } = useImageZoom({ enabled: open });

  // Reset state when dialog closes
  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      setShowRejectForm(false);
      setRejectReason('');
      setLocalStatus(null);
      setZoomLevel(1);
    }
    onOpenChange(nextOpen);
  };

  const handleOpenInNewTab = () => {
    if (previewUrl) window.open(previewUrl, '_blank');
  };

  const effectiveStatus = localStatus || doc?.validationStatus || 'pending';
  const isAlreadyDecided = effectiveStatus === 'validated' || effectiveStatus === 'rejected';

  // ---- Agent actions ----

  const handleValidate = async () => {
    if (!doc) return;
    setIsValidating(true);
    try {
      await validateDocument(doc.id);
      toast.success(t('docValidateSuccess'));
      setLocalStatus('validated');
      onDocumentStatusChanged?.(doc.id, 'validated');
    } catch (err) {
      toast.error(t('docValidateError'));
      console.error('Validate error:', err);
    } finally {
      setIsValidating(false);
    }
  };

  const handleRejectConfirm = async () => {
    if (!doc || rejectReason.length < 5) return;
    setIsRejecting(true);
    try {
      await rejectDocument(doc.id, rejectReason);
      toast.success(t('docRejectSuccess'));
      setLocalStatus('rejected');
      setShowRejectForm(false);
      setRejectReason('');
      onDocumentStatusChanged?.(doc.id, 'rejected');
    } catch (err) {
      toast.error(t('docRejectError'));
      console.error('Reject error:', err);
    } finally {
      setIsRejecting(false);
    }
  };

  if (!doc) return null;

  const docIsPdf = isPdf(doc.mimeType, doc.name);
  const docIsImage = isImage(doc.mimeType, doc.name);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-4xl w-[95vw] max-h-[90vh] flex flex-col p-0">
        {/* Header */}
        <DialogHeader className="px-4 pt-4 pb-2 border-b shrink-0">
          <DialogTitle className="flex items-center justify-between text-sm gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <span className="truncate">{doc.name}</span>
              {/* Status badge */}
              {effectiveStatus === 'validated' && (
                <Badge className="bg-green-100 text-green-700 text-[10px] shrink-0">
                  <CheckCircle2 className="h-3 w-3 mr-0.5" />
                  {t('docAlreadyValidated')}
                </Badge>
              )}
              {effectiveStatus === 'rejected' && (
                <Badge className="bg-red-100 text-red-700 text-[10px] shrink-0">
                  <XCircle className="h-3 w-3 mr-0.5" />
                  {t('docAlreadyRejected')}
                </Badge>
              )}
              {/* Confidence badge */}
              {doc.confidence != null && doc.confidence > 0 && (
                <Badge className={cn('text-[10px] shrink-0', confidenceColor(doc.confidence))}>
                  {t('docConfidence')}: {Math.round(doc.confidence * 100)}%
                </Badge>
              )}
            </div>
            <Button variant="outline" size="sm" onClick={handleOpenInNewTab} className="shrink-0">
              <ExternalLink className="h-3.5 w-3.5 mr-1" />
              {t('newTab')}
            </Button>
          </DialogTitle>
        </DialogHeader>

        {/* Body: document preview */}
        <div className="flex-1 min-h-0 overflow-hidden">
          {previewUrl && docIsPdf && (
            <iframe
              src={previewUrl}
              className="w-full h-full min-h-[60vh]"
              title={doc.name}
            />
          )}
          {previewUrl && docIsImage && (
            <div className="relative h-full bg-muted/30">
              {/* Zoom controls */}
              <div className="absolute top-2 right-2 z-10 flex items-center gap-1 bg-background/90 backdrop-blur-sm rounded-md border shadow-sm p-0.5">
                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleZoomOut} title="Zoom out">
                  <ZoomOut className="h-3.5 w-3.5" />
                </Button>
                <span className="text-xs font-mono w-10 text-center">{Math.round(zoomLevel * 100)}%</span>
                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleZoomIn} title="Zoom in">
                  <ZoomIn className="h-3.5 w-3.5" />
                </Button>
                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleZoomReset} title="Reset zoom">
                  <RotateCcw className="h-3 w-3" />
                </Button>
              </div>
              {/* Zoomable image */}
              <div
                ref={imgContainerRef}
                className="flex items-center justify-center p-4 h-full overflow-auto"
              >
                <img
                  src={previewUrl}
                  alt={doc.name}
                  className="object-contain rounded shadow-sm transition-transform duration-150"
                  style={{
                    transform: `scale(${zoomLevel})`,
                    transformOrigin: 'center center',
                    maxWidth: zoomLevel <= 1 ? '100%' : 'none',
                    maxHeight: zoomLevel <= 1 ? '60vh' : 'none',
                  }}
                  draggable={false}
                />
              </div>
            </div>
          )}
          {previewUrl && !docIsPdf && !docIsImage && (
            <div className="flex flex-col items-center justify-center p-8 gap-4">
              <FileText className="h-12 w-12 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                {t('previewNotAvailable')}
              </p>
              <Button onClick={handleOpenInNewTab}>
                <ExternalLink className="h-4 w-4 mr-2" />
                {t('openDocument')}
              </Button>
            </div>
          )}
        </div>

        {/* Footer: Agent actions */}
        {agentActions && (
          <div className="px-4 py-3 border-t bg-muted/30 shrink-0">
            {isAlreadyDecided ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                {effectiveStatus === 'validated' ? (
                  <>
                    <ShieldCheck className="h-4 w-4 text-green-600" />
                    <span className="text-green-700 font-medium">{t('docAlreadyValidated')}</span>
                  </>
                ) : (
                  <>
                    <ShieldX className="h-4 w-4 text-red-600" />
                    <span className="text-red-700 font-medium">{t('docAlreadyRejected')}</span>
                  </>
                )}
              </div>
            ) : showRejectForm ? (
              /* Inline reject form */
              <div className="flex items-center gap-2">
                <Input
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder={t('docRejectReasonPlaceholder')}
                  className="flex-1 h-8 text-sm"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && rejectReason.length >= 5) handleRejectConfirm();
                    if (e.key === 'Escape') setShowRejectForm(false);
                  }}
                />
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={handleRejectConfirm}
                  disabled={isRejecting || rejectReason.length < 5}
                  className="h-8"
                >
                  {isRejecting ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5 mr-1" />
                  )}
                  {isRejecting ? t('docRejecting') : t('docRejectConfirm')}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => { setShowRejectForm(false); setRejectReason(''); }}
                  className="h-8"
                >
                  {t('docRejectCancel')}
                </Button>
              </div>
            ) : (
              /* Action buttons */
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  onClick={handleValidate}
                  disabled={isValidating}
                  className="bg-green-600 hover:bg-green-700 h-8"
                >
                  {isValidating ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
                  ) : (
                    <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                  )}
                  {isValidating ? t('docValidating') : t('docValidate')}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowRejectForm(true)}
                  className="border-red-300 text-red-700 hover:bg-red-50 h-8"
                >
                  <XCircle className="h-3.5 w-3.5 mr-1" />
                  {t('docReject')}
                </Button>
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default DocumentPreviewDialog;
