/**
 * DocumentsSection - Compact numbered list with status indicators
 *
 * Uses shared DocumentPreviewDialog for preview + agent validate/reject actions.
 * Signed URLs are cached to avoid redundant fetches on rapid navigation.
 *
 * @module agent-dashboard/components/pending/sections
 * @date 2026-03-07
 */

'use client';

import React, { useState, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { FileText, Image as ImageIcon, AlertCircle, Loader2, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { RequestPreviewDocument } from '../../../services/agent-requests-api';
import { getDocumentDownloadUrlCached } from '../../../services/agent-requests-api';
import { DocumentPreviewDialog } from '../../shared/DocumentPreviewDialog';
import type { PreviewDocumentInfo } from '../../shared/DocumentPreviewDialog';

interface DocumentsSectionProps {
  documents: RequestPreviewDocument[];
  documentsCount: number;
  requestId: string;
}

const STATUS_DOT_COLORS: Record<string, string> = {
  valid: 'bg-green-500',
  validated: 'bg-green-500',
  pending: 'bg-orange-400',
  invalid: 'bg-red-500',
  rejected: 'bg-red-500',
};

const STATUS_DOT_KEYS: Record<string, string> = {
  valid: 'docStatusValid',
  validated: 'docStatusValid',
  pending: 'docStatusPending',
  invalid: 'docStatusRejected',
  rejected: 'docStatusRejected',
};

function isImage(mimeType?: string | null, fileName?: string | null): boolean {
  if (mimeType?.startsWith('image/')) return true;
  const ext = fileName?.split('.').pop()?.toLowerCase();
  return ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'].includes(ext || '');
}

export function DocumentsSection({
  documents,
  documentsCount,
  requestId,
}: DocumentsSectionProps) {
  const t = useTranslations('agent.pending.preview');
  const [previewDoc, setPreviewDoc] = useState<PreviewDocumentInfo | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loadingDocId, setLoadingDocId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Track local status overrides from validate/reject actions
  const [statusOverrides, setStatusOverrides] = useState<Record<string, string>>({});

  const handleDocumentClick = useCallback(async (doc: RequestPreviewDocument) => {
    setLoadingDocId(doc.id);
    setError(null);
    try {
      const signedUrl = await getDocumentDownloadUrlCached(requestId, doc.code);
      setPreviewDoc({
        id: doc.id,
        code: doc.code,
        name: doc.name,
        mimeType: doc.mimeType,
        validationStatus: statusOverrides[doc.id] || doc.validationStatus,
      });
      setPreviewUrl(signedUrl);
    } catch (err) {
      setError(t('docLoadError', { name: doc.name, error: err instanceof Error ? err.message : 'unknown' }));
    } finally {
      setLoadingDocId(null);
    }
  }, [requestId, statusOverrides, t]);

  const handleClose = useCallback(() => {
    setPreviewDoc(null);
    setPreviewUrl(null);
  }, []);

  const handleDocumentStatusChanged = useCallback((documentId: string, newStatus: 'validated' | 'rejected') => {
    setStatusOverrides(prev => ({ ...prev, [documentId]: newStatus }));
  }, []);

  return (
    <>
      <Card>
        <CardContent className="p-3">
          <p className="text-[11px] text-muted-foreground uppercase tracking-wider mb-1.5 flex items-center gap-1">
            <FileText className="h-3 w-3" />
            {t('documents')}
            <Badge variant="secondary" className="ml-1 text-[10px] h-4 px-1">{documentsCount}</Badge>
          </p>
          {error && (
            <div className="mb-2 p-1.5 bg-destructive/10 text-destructive text-xs rounded flex items-center gap-2">
              <AlertCircle className="h-3 w-3 shrink-0" />
              <span className="truncate">{error}</span>
              <button onClick={() => setError(null)} className="ml-auto"><X className="h-3 w-3" /></button>
            </div>
          )}
          {documents.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('noDocuments')}</p>
          ) : (
            <div className="flex flex-wrap gap-1">
              {documents.map((doc) => {
                const effectiveStatus = statusOverrides[doc.id] || doc.validationStatus;
                const dotColor = STATUS_DOT_COLORS[effectiveStatus] || STATUS_DOT_COLORS.pending;
                const dotKey = STATUS_DOT_KEYS[effectiveStatus] || 'docStatusPending';
                const label = doc.code.replace(/_/g, ' ');
                const isLoading = loadingDocId === doc.id;
                const docIsImg = isImage(doc.mimeType, doc.name);

                return (
                  <button
                    key={doc.id}
                    onClick={() => handleDocumentClick(doc)}
                    disabled={isLoading}
                    className={cn(
                      'inline-flex items-center gap-1.5 px-2 py-1 rounded-md border text-left',
                      'hover:bg-muted/50 transition-colors cursor-pointer',
                      isLoading && 'opacity-60'
                    )}
                  >
                    <span className={cn('h-2 w-2 rounded-full shrink-0', dotColor)} title={t(dotKey)} />
                    {isLoading ? (
                      <Loader2 className="h-3 w-3 animate-spin text-muted-foreground shrink-0" />
                    ) : docIsImg ? (
                      <ImageIcon className="h-3 w-3 text-muted-foreground shrink-0" />
                    ) : (
                      <FileText className="h-3 w-3 text-muted-foreground shrink-0" />
                    )}
                    <span className="text-sm font-medium whitespace-nowrap">{label}</span>
                  </button>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Shared preview dialog with agent actions */}
      <DocumentPreviewDialog
        open={previewDoc !== null}
        onOpenChange={(open) => { if (!open) handleClose(); }}
        document={previewDoc}
        previewUrl={previewUrl}
        agentActions
        onDocumentStatusChanged={handleDocumentStatusChanged}
      />
    </>
  );
}

export default DocumentsSection;
