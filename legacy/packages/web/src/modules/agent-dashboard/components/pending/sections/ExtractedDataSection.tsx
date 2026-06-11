/**
 * ExtractedDataSection - Display structured data sections with optional photo thumbnail
 *
 * Driven by display_config.list_columns + OCR extraction_data.
 * Photo carnet displayed as thumbnail in header when available.
 *
 * @module agent-dashboard/components/pending/sections
 * @date 2026-01-26
 * @updated 2026-03-07 - Photo thumbnail, single source display_config
 */

'use client';

import React, { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { Card, CardContent } from '@/components/ui/card';
import { ClipboardList, Loader2, User } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import type { PreviewDataSection, RequestPreviewDocument } from '../../../services/agent-requests-api';
import { getDocumentDownloadUrlCached } from '../../../services/agent-requests-api';

interface ExtractedDataSectionProps {
  dataSections?: PreviewDataSection[];
  /** Documents list to find photo_carnet for thumbnail */
  documents?: RequestPreviewDocument[];
  /** Request ID needed for signed URL fetch */
  requestId?: string;
}

function isIsoDate(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}/.test(value);
}

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString('es-ES', {
      day: '2-digit', month: '2-digit', year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

function formatValue(value: string): string {
  if (isIsoDate(value)) return formatDate(value);
  return value;
}

function PhotoThumbnail({ requestId, photoDoc, photoLabel }: { requestId: string; photoDoc: RequestPreviewDocument; photoLabel: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showFull, setShowFull] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getDocumentDownloadUrlCached(requestId, photoDoc.code)
      .then((signedUrl) => {
        if (!cancelled) setUrl(signedUrl);
      })
      .catch(() => {/* silently fail - photo is non-critical */})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [requestId, photoDoc.code]);

  if (loading) {
    return (
      <div className="h-20 w-20 rounded-lg bg-muted flex items-center justify-center shrink-0">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!url) {
    return (
      <div className="h-20 w-20 rounded-lg bg-muted flex items-center justify-center shrink-0">
        <User className="h-6 w-6 text-muted-foreground" />
      </div>
    );
  }

  return (
    <>
      <button
        onClick={() => setShowFull(true)}
        className="h-20 w-20 rounded-lg overflow-hidden border hover:ring-2 hover:ring-primary/50 transition-all shrink-0 cursor-pointer"
      >
        <img src={url} alt={photoLabel} className="h-full w-full object-cover" />
      </button>
      <Dialog open={showFull} onOpenChange={setShowFull}>
        <DialogContent className="max-w-md p-0">
          <DialogHeader className="px-4 pt-4 pb-2">
            <DialogTitle className="text-sm">{photoLabel}</DialogTitle>
          </DialogHeader>
          <div className="flex items-center justify-center p-4 bg-muted/30">
            <img src={url} alt={photoLabel} className="max-w-full max-h-[60vh] object-contain rounded shadow-sm" />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

export function ExtractedDataSection({ dataSections, documents, requestId }: ExtractedDataSectionProps) {
  const t = useTranslations('agent.pending.preview');
  const photoDoc = documents?.find(d => d.code === 'photo_carnet');

  if (!dataSections || dataSections.length === 0) {
    return (
      <Card>
        <CardContent className="p-3">
          <p className="text-[11px] text-muted-foreground uppercase tracking-wider mb-1.5 flex items-center gap-1">
            <ClipboardList className="h-3 w-3" />
            {t('extractedData')}
          </p>
          <p className="text-xs text-muted-foreground">
            {t('pendingOcr')}
          </p>
        </CardContent>
      </Card>
    );
  }

  const totalFields = dataSections.reduce((sum, s) => sum + s.fields.length, 0);

  return (
    <Card>
      <CardContent className="p-3">
        {/* Header with photo thumbnail */}
        <div className="flex items-start gap-3 mb-2">
          {/* Photo thumbnail (left) */}
          {photoDoc && requestId && (
            <PhotoThumbnail requestId={requestId} photoDoc={photoDoc} photoLabel={t('photoCarnet')} />
          )}
          <div className="flex-1 min-w-0">
            <p className="text-[11px] text-muted-foreground uppercase tracking-wider mb-1 flex items-center gap-1">
              <ClipboardList className="h-3 w-3" />
              {t('extractedData')}
              <span className="ml-1 text-muted-foreground/60">({totalFields})</span>
            </p>
            {/* First section inline next to photo */}
            {dataSections[0] && (
              <div>
                <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-0.5">
                  {dataSections[0].title}
                </p>
                <div className="flex flex-wrap gap-x-4 gap-y-0.5">
                  {dataSections[0].fields.map((field, fIdx) => (
                    <div key={fIdx} className="min-w-[120px]">
                      <p className="text-[11px] text-muted-foreground leading-tight">{field.label}</p>
                      <p className="text-xs font-medium leading-tight">{formatValue(field.value)}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
        {/* Remaining sections */}
        {dataSections.length > 1 && (
          <div className="space-y-2">
            {dataSections.slice(1).map((section, idx) => (
              <div key={idx + 1}>
                <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-0.5">
                  {section.title}
                </p>
                <div className="flex flex-wrap gap-x-4 gap-y-0.5">
                  {section.fields.map((field, fIdx) => (
                    <div key={fIdx} className="min-w-[120px]">
                      <p className="text-[11px] text-muted-foreground leading-tight">{field.label}</p>
                      <p className="text-xs font-medium leading-tight">{formatValue(field.value)}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default ExtractedDataSection;
