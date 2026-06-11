/**
 * DocumentDetailSheet - Side panel showing full document details
 *
 * Opens when a user clicks a document card. Displays:
 * 1. Header with document name, category badge, verification badge
 * 2. Preview area (image thumbnail or PDF/file placeholder)
 * 3. Metadata grid (type, category, status, size, format, dates, etc.)
 * 4. Extracted data section (collapsible key-value table)
 * 5. Workflow tag chips
 * 6. Version history timeline
 * 7. Actions bar (download, reclassify, archive, delete)
 *
 * @module user-documents/components
 */

'use client';

import { useState, useCallback, useEffect } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { useQueryClient } from '@tanstack/react-query';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Download,
  RefreshCw,
  Archive,
  Trash2,
  Shield,
  FileText,
  Calendar,
  User,
  Hash,
  Building2,
  Eye,
  ChevronDown,
  ChevronRight,
  Loader2,
} from 'lucide-react';

import { DocumentPreview } from './DocumentPreview';
import { ExpiryBadge } from './ExpiryBadge';
import { WorkflowTagChips } from './WorkflowTagChips';
import { useUserDocument, useDocumentMutations, useDocumentVersions, userDocumentKeys } from '../hooks';
import { userDocumentsApi } from '../services/api';
import type { DocumentCategory, UserDocumentListItem } from '../types';
import { CATEGORY_LABELS } from '../types';

// ---------------------------------------------------------------------------
// Category color mapping (reused from DocumentCard)
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
// Status color mapping
// ---------------------------------------------------------------------------

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
  archived: 'bg-slate-100 text-slate-800 dark:bg-slate-900/30 dark:text-slate-300',
  expired: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
  deleted: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400',
};

// ---------------------------------------------------------------------------
// Size formatter
// ---------------------------------------------------------------------------

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ---------------------------------------------------------------------------
// Date formatter
// ---------------------------------------------------------------------------

function formatDate(dateStr: string, locale: string): string {
  try {
    return new Date(dateStr).toLocaleDateString(locale, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DocumentDetailSheetProps {
  documentId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DocumentDetailSheet({
  documentId,
  open,
  onOpenChange,
}: DocumentDetailSheetProps) {
  const locale = useLocale() as 'es' | 'fr' | 'en';
  const t = useTranslations('userDocuments');
  const queryClient = useQueryClient();

  // Fetch document detail
  const { document: doc, isLoading } = useUserDocument(documentId ?? '');

  // Fetch version history
  const { data: versions, isLoading: versionsLoading } = useDocumentVersions(
    documentId ?? ''
  );

  // Mutations
  const {
    archiveDocument,
    deleteDocument,
    reclassifyDocument,
    isArchiving,
    isDeleting,
    isReclassifying,
  } = useDocumentMutations();

  // Local state
  const [isDownloading, setIsDownloading] = useState(false);
  const [isPermanentDeleting, setIsPermanentDeleting] = useState(false);
  const [thumbnailUrl, setThumbnailUrl] = useState<string | undefined>(undefined);
  const [extractionOpen, setExtractionOpen] = useState(false);

  // Fetch thumbnail or download URL for inline preview
  const isImageDoc = doc?.mime_type?.startsWith('image/');
  useEffect(() => {
    setThumbnailUrl(undefined);
    if (!documentId) return;

    let cancelled = false;

    if (doc?.thumbnail_path) {
      // Use pre-generated thumbnail
      userDocumentsApi
        .getThumbnailUrl(documentId)
        .then((result) => { if (!cancelled) setThumbnailUrl(result.url); })
        .catch(() => {});
    } else if (isImageDoc) {
      // No thumbnail — use signed download URL directly for images
      userDocumentsApi
        .getDownloadUrl(documentId)
        .then((result) => { if (!cancelled) setThumbnailUrl(result.url); })
        .catch(() => {});
    }

    return () => { cancelled = true; };
  }, [documentId, doc?.thumbnail_path, isImageDoc]);

  // Handlers
  const handleDownload = useCallback(async () => {
    if (!documentId) return;
    setIsDownloading(true);
    try {
      const { url } = await userDocumentsApi.getDownloadUrl(documentId);
      window.open(url, '_blank');
    } catch {
      // Silent fail
    } finally {
      setIsDownloading(false);
    }
  }, [documentId]);

  const handleReclassify = useCallback(() => {
    if (!documentId) return;
    reclassifyDocument.mutate({ documentId });
  }, [documentId, reclassifyDocument]);

  const handleArchive = useCallback(() => {
    if (!documentId) return;
    archiveDocument.mutate({ documentId });
    onOpenChange(false);
  }, [documentId, archiveDocument, onOpenChange]);

  const handleDelete = useCallback(() => {
    if (!documentId) return;
    deleteDocument.mutate({ documentId });
    onOpenChange(false);
  }, [documentId, deleteDocument, onOpenChange]);

  const handlePermanentDelete = useCallback(async () => {
    if (!documentId) return;
    setIsPermanentDeleting(true);
    try {
      await userDocumentsApi.permanentDelete(documentId);
      queryClient.invalidateQueries({ queryKey: userDocumentKeys.all });
      onOpenChange(false);
    } catch {
      // Silent fail
    } finally {
      setIsPermanentDeleting(false);
    }
  }, [documentId, queryClient, onOpenChange]);

  // Derived values
  const displayName = doc?.display_name || doc?.file_name || '';
  const categoryLabel =
    doc ? (CATEGORY_LABELS[doc.category]?.[locale] ?? doc.category) : '';
  const categoryColor = doc
    ? (CATEGORY_COLORS[doc.category] ?? CATEGORY_COLORS.other)
    : '';
  const statusColor = doc
    ? (STATUS_COLORS[doc.status] ?? STATUS_COLORS.active)
    : '';

  const extractionEntries = doc?.extracted_data
    ? Object.entries(doc.extracted_data).filter(
        ([, value]) => value !== null && value !== undefined && value !== ''
      )
    : [];

  // Backend sends workflow_tags as flat string[] of workflow codes
  const workflowTagStrings = (doc?.workflow_tags ?? []).filter(Boolean);
  const versionsList = (versions as UserDocumentListItem[] | undefined) ?? [];

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-lg p-0 flex flex-col"
      >
        {/* Loading state */}
        {isLoading && (
          <div className="flex-1 p-6 space-y-4">
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-48 w-full rounded-lg" />
            <div className="space-y-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="flex justify-between">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-32" />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Content when loaded */}
        {!isLoading && doc && (
          <>
            {/* Header */}
            <SheetHeader className="px-6 pt-6 pb-4">
              <SheetTitle className="text-base font-semibold leading-tight pr-8">
                {displayName}
              </SheetTitle>
              <div className="flex items-center gap-2 mt-2 flex-wrap">
                <Badge
                  variant="outline"
                  className={`text-xs px-2 py-0.5 border-none ${categoryColor}`}
                >
                  {categoryLabel}
                </Badge>
                {doc.is_verified && (
                  <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 border-none gap-1 text-xs px-2 py-0.5">
                    <Shield className="h-3 w-3" strokeWidth={1.5} />
                    {t('card.verified')}
                  </Badge>
                )}
                <Badge
                  variant="outline"
                  className={`text-xs px-2 py-0.5 border-none ${statusColor}`}
                >
                  {doc.status}
                </Badge>
              </div>
            </SheetHeader>

            <Separator />

            {/* Scrollable body */}
            <ScrollArea className="flex-1">
              <div className="p-6 space-y-6">
                {/* Preview area */}
                <DocumentPreview
                  mimeType={doc.mime_type}
                  thumbnailUrl={thumbnailUrl}
                  fileName={doc.file_name}
                  onDownload={handleDownload}
                />

                {/* Metadata section */}
                <div>
                  <h3 className="text-sm font-medium mb-3">{t('detail.metadata')}</h3>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-sm">
                    {/* Type */}
                    <div className="flex items-center gap-1.5 text-muted-foreground">
                      <FileText className="h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
                      {t('detail.type')}
                    </div>
                    <div className="text-right font-medium truncate" title={doc.document_type}>
                      {doc.document_type.replace(/_/g, ' ')}
                    </div>

                    {/* Category */}
                    <div className="flex items-center gap-1.5 text-muted-foreground">
                      <Eye className="h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
                      {t('detail.category')}
                    </div>
                    <div className="text-right">{categoryLabel}</div>

                    {/* Status */}
                    <div className="flex items-center gap-1.5 text-muted-foreground">
                      <Shield className="h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
                      {t('detail.status')}
                    </div>
                    <div className="text-right capitalize">{doc.status}</div>

                    {/* File size */}
                    <div className="text-muted-foreground">{t('detail.fileSize')}</div>
                    <div className="text-right">{formatFileSize(doc.file_size_bytes)}</div>

                    {/* MIME type */}
                    <div className="text-muted-foreground">{t('detail.mimeType')}</div>
                    <div className="text-right font-mono text-xs">{doc.mime_type}</div>

                    {/* Uploaded date */}
                    <div className="flex items-center gap-1.5 text-muted-foreground">
                      <Calendar className="h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
                      {t('detail.uploadedAt')}
                    </div>
                    <div className="text-right">{formatDate(doc.created_at, locale)}</div>

                    {/* Document number */}
                    {doc.document_number && (
                      <>
                        <div className="flex items-center gap-1.5 text-muted-foreground">
                          <Hash className="h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
                          {t('detail.documentNumber')}
                        </div>
                        <div className="text-right font-mono">{doc.document_number}</div>
                      </>
                    )}

                    {/* Holder name */}
                    {doc.holder_name && (
                      <>
                        <div className="flex items-center gap-1.5 text-muted-foreground">
                          <User className="h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
                          {t('detail.holderName')}
                        </div>
                        <div className="text-right">{doc.holder_name}</div>
                      </>
                    )}

                    {/* Issue date */}
                    {doc.issue_date && (
                      <>
                        <div className="text-muted-foreground">{t('detail.issueDate')}</div>
                        <div className="text-right">{formatDate(doc.issue_date, locale)}</div>
                      </>
                    )}

                    {/* Expiry date */}
                    {doc.expiry_date && (
                      <>
                        <div className="text-muted-foreground">{t('detail.expiryDate')}</div>
                        <div className="text-right">
                          <ExpiryBadge
                            expiryDate={doc.expiry_date}
                            expiryStatus={doc.expiry_status}
                            daysUntilExpiry={doc.days_until_expiry}
                          />
                        </div>
                      </>
                    )}

                    {/* Issuing authority */}
                    {doc.issuing_authority && (
                      <>
                        <div className="flex items-center gap-1.5 text-muted-foreground">
                          <Building2 className="h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
                          {t('detail.issuingAuthority')}
                        </div>
                        <div className="text-right">{doc.issuing_authority}</div>
                      </>
                    )}

                    {/* AI confidence */}
                    {doc.extraction_confidence != null && doc.extraction_confidence > 0 && (
                      <>
                        <div className="text-muted-foreground col-span-2 mt-1">
                          {t('detail.confidence')}
                        </div>
                        <div className="col-span-2 flex items-center gap-3">
                          <Progress
                            value={Math.round(doc.extraction_confidence * 100)}
                            className="h-2 flex-1"
                          />
                          <span className="text-xs font-medium text-muted-foreground w-10 text-right">
                            {Math.round(doc.extraction_confidence * 100)}%
                          </span>
                        </div>
                      </>
                    )}
                  </div>
                </div>

                <Separator />

                {/* Extracted data section (collapsible) */}
                {extractionEntries.length > 0 && (
                  <Collapsible open={extractionOpen} onOpenChange={setExtractionOpen}>
                    <CollapsibleTrigger className="flex items-center gap-2 w-full text-sm font-medium hover:text-primary transition-colors">
                      {extractionOpen ? (
                        <ChevronDown className="h-4 w-4" strokeWidth={1.5} />
                      ) : (
                        <ChevronRight className="h-4 w-4" strokeWidth={1.5} />
                      )}
                      {t('detail.extraction')}
                      <Badge variant="outline" className="text-[10px] ml-auto">
                        {extractionEntries.length}
                      </Badge>
                    </CollapsibleTrigger>
                    <CollapsibleContent className="mt-3">
                      <div className="rounded-lg border bg-muted/30 p-3 space-y-1.5">
                        {extractionEntries.map(([key, value]) => (
                          <div
                            key={key}
                            className="flex justify-between gap-2 text-xs py-1 border-b border-border/50 last:border-0"
                          >
                            <span className="text-muted-foreground font-mono truncate">
                              {key}
                            </span>
                            <span className="text-right font-medium max-w-[60%] truncate">
                              {typeof value === 'object'
                                ? JSON.stringify(value)
                                : String(value)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </CollapsibleContent>
                  </Collapsible>
                )}

                {extractionEntries.length === 0 && (
                  <div>
                    <h3 className="text-sm font-medium mb-1">{t('detail.extraction')}</h3>
                    <p className="text-xs text-muted-foreground">
                      {t('detail.noExtractedData')}
                    </p>
                  </div>
                )}

                {/* Workflow tags section */}
                {workflowTagStrings.length > 0 && (
                  <>
                    <Separator />
                    <div>
                      <h3 className="text-sm font-medium mb-3">{t('detail.workflows')}</h3>
                      <WorkflowTagChips tags={workflowTagStrings} maxVisible={6} />
                    </div>
                  </>
                )}

                {/* Version history section */}
                <Separator />
                <div>
                  <h3 className="text-sm font-medium mb-3">{t('detail.versions')}</h3>
                  {versionsLoading && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      {t('detail.loading')}
                    </div>
                  )}
                  {!versionsLoading && versionsList.length === 0 && (
                    <p className="text-xs text-muted-foreground">
                      {t('detail.noVersions')}
                    </p>
                  )}
                  {!versionsLoading && versionsList.length > 0 && (
                    <div className="space-y-2">
                      {versionsList.map((version) => (
                        <div
                          key={version.id}
                          className="flex items-center gap-3 rounded-md border p-2.5 text-xs"
                        >
                          <div className="h-2 w-2 rounded-full bg-primary shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="font-medium truncate">
                              {version.display_name || version.file_name}
                            </p>
                            <p className="text-muted-foreground">
                              {formatDate(version.created_at, locale)}
                            </p>
                          </div>
                          <Badge
                            variant="outline"
                            className="text-[10px] shrink-0"
                          >
                            {version.status}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </ScrollArea>

            <Separator />

            {/* Actions bar */}
            <div className="px-6 py-4 flex items-center gap-2 shrink-0 flex-wrap">
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownload}
                disabled={isDownloading}
                className="gap-1.5"
              >
                {isDownloading ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.5} />
                ) : (
                  <Download className="h-3.5 w-3.5" strokeWidth={1.5} />
                )}
                {t('card.download')}
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={handleReclassify}
                disabled={isReclassifying}
                className="gap-1.5"
              >
                {isReclassifying ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.5} />
                ) : (
                  <RefreshCw className="h-3.5 w-3.5" strokeWidth={1.5} />
                )}
                {t('card.reclassify')}
              </Button>

              <div className="flex-1" />

              <Button
                variant="outline"
                size="sm"
                onClick={handleArchive}
                disabled={isArchiving}
                className="gap-1.5"
              >
                {isArchiving ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.5} />
                ) : (
                  <Archive className="h-3.5 w-3.5" strokeWidth={1.5} />
                )}
                {t('card.archive')}
              </Button>

              <Button
                variant="destructive"
                size="sm"
                onClick={handleDelete}
                disabled={isDeleting}
                className="gap-1.5"
              >
                {isDeleting ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.5} />
                ) : (
                  <Trash2 className="h-3.5 w-3.5" strokeWidth={1.5} />
                )}
                {t('card.delete')}
              </Button>

              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="destructive"
                    size="sm"
                    className="gap-1.5 text-xs"
                    disabled={isPermanentDeleting}
                  >
                    {isPermanentDeleting ? (
                      <Loader2 className="h-3 w-3 animate-spin" strokeWidth={1.5} />
                    ) : (
                      <Trash2 className="h-3 w-3" strokeWidth={1.5} />
                    )}
                    {t('actions.permanentDelete')}
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>
                      {t('actions.confirmPermanentDelete')}
                    </AlertDialogTitle>
                    <AlertDialogDescription>
                      {t('actions.permanentDeleteWarning')}
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>{t('upload.cancel')}</AlertDialogCancel>
                    <AlertDialogAction
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      onClick={handlePermanentDelete}
                    >
                      {t('actions.permanentDelete')}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
