/**
 * GeneratedDocumentsGrid - Grid of platform-generated documents
 *
 * Lists certificates, receipts, summary PDFs, and other generated documents
 * with infinite scroll, type filter, and download actions.
 *
 * @module user-documents/components
 */

'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  FileText,
  Receipt,
  Award,
  Download,
  ExternalLink,
  FileX,
  Loader2,
  ShieldCheck,
} from 'lucide-react';
import { useGeneratedDocuments } from '../hooks';
import { userDocumentsApi } from '../services/api';
import type { GeneratedDocument } from '../types';

// ---------------------------------------------------------------------------
// Generation type metadata
// ---------------------------------------------------------------------------

const TYPE_STYLE: Record<string, { icon: typeof FileText; color: string }> = {
  certificate: {
    icon: Award,
    color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
  },
  receipt: {
    icon: Receipt,
    color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
  },
  payment_receipt: {
    icon: Receipt,
    color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
  },
  summary: {
    icon: FileText,
    color: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
  },
  request_summary: {
    icon: FileText,
    color: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
  },
  attestation: {
    icon: FileText,
    color: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300',
  },
  confirmation: {
    icon: FileText,
    color: 'bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-300',
  },
  LICENSE_CERTIFICATE: {
    icon: Award,
    color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
  },
  CITIZEN_SUMMARY: {
    icon: FileText,
    color: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
  },
  MISE_EN_DEMEURE: {
    icon: FileText,
    color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
  },
  SEAL_ORDER: {
    icon: FileText,
    color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
  },
  PAYMENT_RECEIPT: {
    icon: Receipt,
    color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
  },
};

function getTypeStyle(generationType: string) {
  return (
    TYPE_STYLE[generationType] ?? {
      icon: FileText,
      color: 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300',
    }
  );
}

function formatDate(dateStr: string, locale: string): string {
  try {
    return new Intl.DateTimeFormat(locale, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }).format(new Date(dateStr));
  } catch {
    return dateStr;
  }
}

function formatFileSize(bytes?: number): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ---------------------------------------------------------------------------
// Type filter options
// ---------------------------------------------------------------------------

// Filter values must match backend GenerationType + actual DB values
const TYPE_FILTER_VALUES = [undefined, 'certificate', 'payment_receipt', 'request_summary', 'attestation'] as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function GeneratedDocumentsGrid() {
  const locale = useLocale() as 'es' | 'fr' | 'en';
  const t = useTranslations('userDocuments');
  const [generationType, setGenerationType] = useState<string | undefined>(undefined);

  const {
    documents,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useGeneratedDocuments(generationType);

  // Infinite scroll observer
  const loadMoreRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = loadMoreRef.current;
    if (!el || !hasNextPage) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { rootMargin: '200px' }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // Download handler
  const handleDownload = useCallback(async (docId: string) => {
    try {
      const { url } = await userDocumentsApi.getGeneratedDownloadUrl(docId);
      window.open(url, '_blank');
    } catch {
      // Silent fail
    }
  }, []);

  // Get localized title
  const getTitle = useCallback(
    (doc: GeneratedDocument): string => {
      // Use i18n translation keys — no need for backend multilingual fields
      const typeKey = doc.generation_type || 'other';
      const translated = t(`generated.types.${typeKey}`);
      // If key exists in translations, use it; otherwise fallback to backend fields
      if (translated && !translated.startsWith('userDocuments.')) {
        return translated;
      }
      return doc.title_es || doc.title || doc.file_name;
    },
    [t]
  );

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Type filter chips */}
      <div className="flex items-center gap-2 flex-wrap">
        {TYPE_FILTER_VALUES.map((value) => (
          <Badge
            key={value ?? 'all'}
            variant={generationType === value ? 'default' : 'outline'}
            className="cursor-pointer text-xs"
            onClick={() => setGenerationType(value)}
          >
            {t(`generatedTypes.${value ?? 'all'}`)}
          </Badge>
        ))}
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-lg border p-4 space-y-3">
              <div className="flex items-start gap-3">
                <Skeleton className="h-10 w-10 rounded-lg" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              </div>
              <Skeleton className="h-3 w-full" />
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && documents.length === 0 && (
        <div className="flex-1 flex flex-col items-center justify-center text-center py-12">
          <FileX className="h-12 w-12 text-muted-foreground/50 mb-4" />
          <h3 className="text-lg font-medium">{t('generated.emptyTitle')}</h3>
          <p className="text-sm text-muted-foreground mt-1 max-w-sm">
            {t('generated.emptyDescription')}
          </p>
        </div>
      )}

      {/* Document grid */}
      {!isLoading && documents.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 overflow-y-auto flex-1 min-h-0 pb-2">
          {documents.filter(Boolean).map((doc) => {
            if (!doc) return null;
            const genType = doc.generation_type || 'other';
            const style = getTypeStyle(genType);
            const Icon = style.icon;
            const typeLabel = t(`generatedLabels.${genType}`, { defaultValue: genType });
            const title = getTitle(doc);

            return (
              <Card key={doc.id} className="group hover:shadow-md transition-shadow">
                <CardContent className="p-4">
                  {/* Top row: icon + title + download */}
                  <div className="flex items-start gap-3">
                    <div
                      className={`shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${style.color}`}
                    >
                      <Icon className="h-5 w-5" />
                    </div>

                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate" title={title}>
                        {title}
                      </p>
                      <div className="flex items-center gap-1.5 mt-1">
                        <Badge
                          variant="outline"
                          className={`text-[10px] px-1.5 py-0 h-5 border-none ${style.color}`}
                        >
                          {typeLabel}
                        </Badge>
                        {doc.verification_code && (
                          <ShieldCheck className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />
                        )}
                      </div>
                    </div>

                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                      onClick={() => handleDownload(doc.id)}
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                  </div>

                  {/* Bottom row: meta info */}
                  <div className="mt-3 flex items-center justify-between text-[10px] text-muted-foreground">
                    <div className="flex items-center gap-2">
                      <span>{formatDate(doc.created_at, locale)}</span>
                      {doc.file_size_bytes && (
                        <>
                          <span>-</span>
                          <span>{formatFileSize(doc.file_size_bytes)}</span>
                        </>
                      )}
                    </div>

                    {doc.reference_number && (
                      <span className="font-mono text-[10px]" title={t('generated.reference')}>
                        #{doc.reference_number}
                      </span>
                    )}
                  </div>

                  {/* Verification code */}
                  {doc.verification_code && (
                    <div className="mt-2 flex items-center gap-1 text-[10px] text-muted-foreground">
                      <ExternalLink className="h-3 w-3" />
                      <span className="font-mono">{doc.verification_code}</span>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}

          {/* Infinite scroll sentinel */}
          <div ref={loadMoreRef} className="col-span-full h-1" />

          {isFetchingNextPage && (
            <div className="col-span-full flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
              <span className="ml-2 text-sm text-muted-foreground">
                {t('generated.loadingMore')}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
