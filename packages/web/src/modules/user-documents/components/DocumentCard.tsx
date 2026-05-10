/**
 * DocumentCard - Single document card with thumbnail, title, category badge,
 * expiry badge, and quick actions.
 *
 * Used in both PersonalDocumentsGrid and as a standalone component.
 *
 * @module user-documents/components
 */

'use client';

import { useState, useCallback, useEffect } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  FileText,
  Image as ImageIcon,
  File,
  Download,
  Archive,
  Trash2,
  MoreVertical,
  Eye,
  RefreshCw,
  ShieldCheck,
  ShieldAlert,
} from 'lucide-react';
import { ExpiryBadge } from './ExpiryBadge';
import { WorkflowTagChips } from './WorkflowTagChips';
import { useDocumentMutations } from '../hooks';
import { userDocumentsApi } from '../services/api';
import type { UserDocumentListItem, DocumentCategory } from '../types';
import { CATEGORY_LABELS } from '../types';

// ---------------------------------------------------------------------------
// Category color mapping
// ---------------------------------------------------------------------------

const CATEGORY_COLORS: Record<DocumentCategory, string> = {
  identity: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
  vehicle: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300',
  legal: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
  financial: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
  administrative: 'bg-slate-100 text-slate-800 dark:bg-slate-900/30 dark:text-slate-300',
  medical: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
  education: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300',
  photo: 'bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-300',
  business: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300',
  employment: 'bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-300',
  other: 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300',
};

// ---------------------------------------------------------------------------
// File icon selector
// ---------------------------------------------------------------------------

function getFileIcon(mimeType: string | undefined | null) {
  if (!mimeType) return File;
  if (mimeType.startsWith('image/')) return ImageIcon;
  if (mimeType === 'application/pdf') return FileText;
  return File;
}

// ---------------------------------------------------------------------------
// Size formatter
// ---------------------------------------------------------------------------

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DocumentCardProps {
  document: UserDocumentListItem;
  onView?: (doc: UserDocumentListItem) => void;
  selectable?: boolean;
  selected?: boolean;
  onSelect?: (id: string, selected: boolean) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DocumentCard({
  document: doc,
  onView,
  selectable = false,
  selected = false,
  onSelect,
}: DocumentCardProps) {
  const locale = useLocale() as 'es' | 'fr' | 'en';
  const t = useTranslations('userDocuments');
  const { archiveDocument, deleteDocument, reclassifyDocument } =
    useDocumentMutations();
  const [isDownloading, setIsDownloading] = useState(false);

  const FileIcon = getFileIcon(doc.mime_type);
  const categoryLabel = CATEGORY_LABELS[doc.category]?.[locale] ?? doc.category;
  const categoryColor = CATEGORY_COLORS[doc.category] ?? CATEGORY_COLORS.other;
  const displayName = doc.display_name || doc.file_name;

  // Lazy-load thumbnail: use thumbnail_path if available, else download URL for images
  const isImage = doc.mime_type?.startsWith('image/');
  const [thumbUrl, setThumbUrl] = useState<string | null>(null);
  useEffect(() => {
    if (doc.thumbnail_path) {
      userDocumentsApi
        .getThumbnailUrl(doc.id)
        .then((res) => setThumbUrl(res.url))
        .catch(() => {});
    } else if (isImage) {
      // No thumbnail generated — use signed download URL as inline preview
      userDocumentsApi
        .getDownloadUrl(doc.id)
        .then((res) => setThumbUrl(res.url))
        .catch(() => {});
    }
  }, [doc.id, doc.thumbnail_path, isImage]);

  // Handle download
  const handleDownload = useCallback(async () => {
    setIsDownloading(true);
    try {
      const { url } = await userDocumentsApi.getDownloadUrl(doc.id);
      window.open(url, '_blank');
    } catch {
      // Silent fail -- toast would be added in a real implementation
    } finally {
      setIsDownloading(false);
    }
  }, [doc.id]);

  // Handle archive
  const handleArchive = useCallback(() => {
    archiveDocument.mutate({ documentId: doc.id });
  }, [archiveDocument, doc.id]);

  // Handle delete
  const handleDelete = useCallback(() => {
    deleteDocument.mutate({ documentId: doc.id });
  }, [deleteDocument, doc.id]);

  // Handle reclassify
  const handleReclassify = useCallback(() => {
    reclassifyDocument.mutate({ documentId: doc.id });
  }, [reclassifyDocument, doc.id]);

  return (
    <Card
      className={`group relative transition-all hover:shadow-md ${
        selected ? 'ring-2 ring-primary' : ''
      }`}
    >
      <CardContent className="p-4">
        {/* Selection checkbox area */}
        {selectable && (
          <div className="absolute top-2 left-2 z-10">
            <input
              type="checkbox"
              checked={selected}
              onChange={(e) => onSelect?.(doc.id, e.target.checked)}
              className="h-4 w-4 rounded border-muted-foreground/50"
            />
          </div>
        )}

        {/* Top row: icon + title + actions */}
        <div className="flex items-start gap-3">
          {/* File type icon / thumbnail */}
          {thumbUrl ? (
            <div className="shrink-0 w-10 h-10 rounded-lg overflow-hidden bg-muted">
              <img
                src={thumbUrl}
                alt={displayName}
                className="w-full h-full object-cover"
                loading="lazy"
                onError={() => setThumbUrl(null)}
              />
            </div>
          ) : doc.mime_type === 'application/pdf' ? (
            <div className="shrink-0 w-10 h-10 rounded-lg bg-red-50 dark:bg-red-950/20 flex items-center justify-center">
              <FileText className="h-5 w-5 text-red-500" />
            </div>
          ) : (
            <div className="shrink-0 w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
              <FileIcon className="h-5 w-5 text-muted-foreground" />
            </div>
          )}

          {/* Title + meta */}
          <div className="flex-1 min-w-0">
            <button
              onClick={() => onView?.(doc)}
              className="text-sm font-medium truncate block w-full text-left hover:text-primary transition-colors"
              title={displayName}
            >
              {displayName}
            </button>

            <div className="flex items-center gap-1.5 mt-1 flex-wrap">
              {/* Category badge */}
              <Badge
                variant="outline"
                className={`text-[10px] px-1.5 py-0 h-5 border-none ${categoryColor}`}
              >
                {categoryLabel}
              </Badge>

              {/* Verification status */}
              <TooltipProvider delayDuration={200}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    {doc.is_verified ? (
                      <ShieldCheck className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />
                    ) : (
                      <ShieldAlert className="h-3.5 w-3.5 text-muted-foreground/50" />
                    )}
                  </TooltipTrigger>
                  <TooltipContent side="top" className="text-xs">
                    {doc.is_verified ? t('card.verified') : t('card.unverified')}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>

              {/* Document number — shown only in detail view (not in list items) */}
            </div>
          </div>

          {/* Actions dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
              >
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem onClick={() => onView?.(doc)}>
                <Eye className="mr-2 h-4 w-4" />
                {t('actions.view')}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleDownload} disabled={isDownloading}>
                <Download className="mr-2 h-4 w-4" />
                {t('actions.download')}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleReclassify}>
                <RefreshCw className="mr-2 h-4 w-4" />
                {t('actions.reclassify')}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleArchive}>
                <Archive className="mr-2 h-4 w-4" />
                {t('actions.archive')}
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={handleDelete}
                className="text-destructive focus:text-destructive"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                {t('actions.delete')}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Bottom row: expiry + size + workflow tags */}
        <div className="mt-3 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <ExpiryBadge
              expiryDate={doc.expiry_date}
              expiryStatus={doc.expiry_status}
              daysUntilExpiry={doc.days_until_expiry}
              compact
            />
            <span className="text-[10px] text-muted-foreground shrink-0">
              {formatFileSize(doc.file_size_bytes)}
            </span>
          </div>

          <WorkflowTagChips tags={doc.workflow_tags} maxVisible={2} />
        </div>
      </CardContent>
    </Card>
  );
}
