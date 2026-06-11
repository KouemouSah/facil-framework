/**
 * DocumentPreview - Inline preview component for document detail sheet
 *
 * Renders an appropriate preview based on MIME type:
 * - Images (jpeg/png/webp): thumbnail via <img> with objectFit cover
 * - PDF: styled placeholder with FileText icon + download prompt
 * - Other: generic file icon
 *
 * @module user-documents/components
 */

'use client';

import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { FileText, Image as ImageIcon, File, Download } from 'lucide-react';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DocumentPreviewProps {
  mimeType: string | undefined | null;
  thumbnailUrl?: string;
  fileName: string;
  onDownload: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DocumentPreview({
  mimeType,
  thumbnailUrl,
  fileName,
  onDownload,
}: DocumentPreviewProps) {
  const t = useTranslations('userDocuments.detail');

  // ---- Image preview ----
  if (mimeType && mimeType.startsWith('image/')) {
    if (thumbnailUrl) {
      return (
        <div className="relative w-full rounded-lg overflow-hidden bg-muted border">
          <img
            src={thumbnailUrl}
            alt={fileName}
            className="w-full max-h-64 object-cover"
          />
          <button
            type="button"
            onClick={onDownload}
            className="absolute bottom-2 right-2 rounded-md bg-background/80 backdrop-blur-sm p-1.5 hover:bg-background transition-colors"
            title={t('downloadToView')}
          >
            <Download className="h-4 w-4" strokeWidth={1.5} />
          </button>
        </div>
      );
    }

    // No thumbnail URL available
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed bg-muted/50 py-8">
        <ImageIcon className="h-10 w-10 text-muted-foreground/60" strokeWidth={1.5} />
        <p className="text-sm text-muted-foreground">{fileName}</p>
        <Button variant="outline" size="sm" onClick={onDownload} className="gap-2">
          <Download className="h-3.5 w-3.5" strokeWidth={1.5} />
          {t('downloadToView')}
        </Button>
      </div>
    );
  }

  // ---- PDF preview ----
  if (mimeType === 'application/pdf') {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed bg-muted/50 py-8">
        <FileText className="h-10 w-10 text-red-500/70" strokeWidth={1.5} />
        <p className="text-sm text-muted-foreground">{fileName}</p>
        <Button variant="outline" size="sm" onClick={onDownload} className="gap-2">
          <Download className="h-3.5 w-3.5" strokeWidth={1.5} />
          {t('downloadToView')}
        </Button>
      </div>
    );
  }

  // ---- Other file types ----
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed bg-muted/50 py-8">
      <File className="h-10 w-10 text-muted-foreground/60" strokeWidth={1.5} />
      <p className="text-sm text-muted-foreground">{fileName}</p>
      <Button variant="outline" size="sm" onClick={onDownload} className="gap-2">
        <Download className="h-3.5 w-3.5" strokeWidth={1.5} />
        {t('downloadToView')}
      </Button>
    </div>
  );
}
