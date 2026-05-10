/**
 * PersonalDocumentsGrid - Grid/list of personal (uploaded + wizard-imported) documents
 *
 * Features:
 * - Infinite scroll with cursor-based pagination
 * - Category filter chips
 * - Search input
 * - Responsive grid layout (1/2/3 cols)
 * - Empty state
 * - Loading skeleton
 *
 * @module user-documents/components
 */

'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
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
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  Search,
  Filter,
  FileX,
  Loader2,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  Trash2,
  Archive as ArchiveIcon,
  FileText,
  Image as ImageIcon,
} from 'lucide-react';
import { useUserDocuments, userDocumentKeys } from '../hooks';
import { DocumentCard } from './DocumentCard';
import { DocumentDetailSheet } from './DocumentDetailSheet';
import { userDocumentsApi } from '../services/api';
import type { DocumentCategory, DocumentFilters, UserDocumentListItem } from '../types';
import { CATEGORY_LABELS } from '../types';

// ---------------------------------------------------------------------------
// Category filter options
// ---------------------------------------------------------------------------

const CATEGORY_OPTIONS: DocumentCategory[] = [
  'identity',
  'vehicle',
  'legal',
  'financial',
  'administrative',
  'medical',
  'education',
  'photo',
  'business',
  'employment',
  'other',
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PersonalDocumentsGrid() {
  const t = useTranslations('userDocuments');
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<DocumentCategory | undefined>(undefined);
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce search input
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [search]);

  // Build filters: personal tab shows BOTH 'personal' uploads AND 'wizard_import'
  // documents (imported from service request submissions). NOT generated docs.
  // Omit source filter — backend returns all sources. Generated docs are in their own tab.
  const filters: DocumentFilters = {
    category,
    search: debouncedSearch || undefined,
    limit: 20,
  };

  const {
    documents: allDocuments,
    totalCount,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useUserDocuments(filters);

  // Exclude platform-generated docs (they belong in the Generados tab)
  const documents = allDocuments.filter(
    (doc) => doc.source !== 'platform_generated'
  );

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

  // Category toggle
  const toggleCategory = useCallback(
    (cat: DocumentCategory) => {
      setCategory((prev) => (prev === cat ? undefined : cat));
    },
    []
  );

  // Handle document view - open detail sheet
  const handleView = useCallback((doc: UserDocumentListItem) => {
    setSelectedDocId(doc.id);
  }, []);

  // -------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Search + Filter bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('personal.searchPlaceholder')}
            className="pl-9"
          />
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          <Filter className="h-4 w-4 text-muted-foreground shrink-0" />
          {CATEGORY_OPTIONS.map((cat) => (
            <Badge
              key={cat}
              variant={category === cat ? 'default' : 'outline'}
              className="cursor-pointer text-xs"
              onClick={() => toggleCategory(cat)}
            >
              {CATEGORY_LABELS[cat]?.es ?? cat}
            </Badge>
          ))}
        </div>
      </div>

      {/* Results count */}
      {!isLoading && (
        <p className="text-xs text-muted-foreground">
          {t('personal.resultCount', { count: totalCount })}
        </p>
      )}

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
          <h3 className="text-lg font-medium">{t('personal.emptyTitle')}</h3>
          <p className="text-sm text-muted-foreground mt-1 max-w-sm">
            {debouncedSearch || category
              ? t('personal.emptyFiltered')
              : t('personal.emptyDescription')}
          </p>
        </div>
      )}

      {/* Document grid */}
      {!isLoading && documents.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 overflow-y-auto flex-1 min-h-0 pb-2">
          {documents.map((doc) => (
            <DocumentCard key={doc.id} document={doc} onView={handleView} />
          ))}

          {/* Infinite scroll sentinel */}
          <div ref={loadMoreRef} className="col-span-full h-1" />

          {/* Loading more indicator */}
          {isFetchingNextPage && (
            <div className="col-span-full flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
              <span className="ml-2 text-sm text-muted-foreground">
                {t('personal.loadingMore')}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Load more button fallback */}
      {!isLoading && hasNextPage && !isFetchingNextPage && (
        <div className="flex justify-center">
          <Button variant="outline" size="sm" onClick={() => fetchNextPage()}>
            {t('personal.loadMore')}
          </Button>
        </div>
      )}

      {/* Archived documents section */}
      <ArchivedDocumentsSection />

      {/* Document detail sheet */}
      <DocumentDetailSheet
        documentId={selectedDocId}
        open={!!selectedDocId}
        onOpenChange={(open) => {
          if (!open) setSelectedDocId(null);
        }}
      />
    </div>
  );
}


// ---------------------------------------------------------------------------
// Archived Documents Section (collapsible)
// ---------------------------------------------------------------------------

function ArchivedDocumentsSection() {
  const t = useTranslations('userDocuments');
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [archivePage, setArchivePage] = useState(1);
  const [archiveSearch, setArchiveSearch] = useState('');
  const ARCHIVE_PAGE_SIZE = 20;

  const { data, isLoading, refetch } = useQuery({
    queryKey: [...userDocumentKeys.lists(), 'archived', archivePage],
    queryFn: () =>
      userDocumentsApi.list({ status: 'archived', limit: ARCHIVE_PAGE_SIZE, offset: (archivePage - 1) * ARCHIVE_PAGE_SIZE }),
    enabled: open,
    staleTime: 30_000,
  });

  const allItems = data?.items ?? [];
  const count = data?.total_count ?? 0;
  const totalPages = Math.ceil(count / ARCHIVE_PAGE_SIZE);

  // Client-side search within loaded page
  const items = archiveSearch
    ? allItems.filter(d => {
        const q = archiveSearch.toLowerCase();
        return (d.display_name || d.file_name || '').toLowerCase().includes(q)
          || (d.document_type || '').toLowerCase().includes(q);
      })
    : allItems;

  const handlePermanentDelete = useCallback(
    async (docId: string) => {
      setDeletingId(docId);
      try {
        await userDocumentsApi.permanentDelete(docId);
        refetch();
        queryClient.invalidateQueries({ queryKey: userDocumentKeys.stats() });
      } catch {
        // Silent fail
      } finally {
        setDeletingId(null);
      }
    },
    [refetch, queryClient]
  );

  const getFileIcon = (doc: UserDocumentListItem) => {
    const mime = doc.mime_type || '';
    if (mime.startsWith('image/')) return ImageIcon;
    return FileText;
  };

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="mt-2">
      <CollapsibleTrigger className="flex items-center gap-2 w-full text-sm font-medium text-muted-foreground hover:text-foreground transition-colors py-2">
        {open ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
        <ArchiveIcon className="h-4 w-4" />
        {t('archived.title')}
        {count > 0 && (
          <Badge variant="secondary" className="text-xs ml-1">
            {count}
          </Badge>
        )}
      </CollapsibleTrigger>
      <CollapsibleContent>
        {isLoading && (
          <div className="flex items-center gap-2 py-4 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            {t('detail.loading')}
          </div>
        )}

        {!isLoading && count === 0 && (
          <p className="text-xs text-muted-foreground py-3">
            {t('archived.empty')}
          </p>
        )}

        {!isLoading && count > 0 && (
          <div className="py-2 space-y-3">
            {/* Search + count */}
            <div className="flex items-center gap-2">
              <div className="relative flex-1 max-w-xs">
                <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                <input
                  type="text"
                  placeholder={t('archived.search') || 'Buscar archivo...'}
                  value={archiveSearch}
                  onChange={(e) => setArchiveSearch(e.target.value)}
                  className="w-full pl-7 pr-2 py-1.5 text-xs border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-primary/30"
                />
              </div>
              <span className="text-xs text-muted-foreground">
                {t('archived.count', { count })}
              </span>
            </div>

            {/* Grid compacte 4 colonnes */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
              {items.map((doc) => {
                const Icon = getFileIcon(doc);
                return (
                  <div
                    key={doc.id}
                    className="group relative flex flex-col items-center gap-1 rounded-lg border p-2.5 hover:bg-accent/50 transition-colors text-center"
                  >
                    <Icon className="h-8 w-8 text-muted-foreground/60 shrink-0" strokeWidth={1} />
                    <p className="text-[11px] font-medium truncate w-full leading-tight">
                      {doc.display_name || doc.file_name}
                    </p>
                    <p className="text-[10px] text-muted-foreground truncate w-full">
                      {doc.document_type.replace(/_/g, ' ')}
                    </p>
                    <p className="text-[9px] text-muted-foreground">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </p>
                    {/* Delete button (hover) */}
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="absolute top-1 right-1 h-6 w-6 opacity-0 group-hover:opacity-100 text-destructive hover:text-destructive transition-opacity"
                          disabled={deletingId === doc.id}
                        >
                          {deletingId === doc.id ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Trash2 className="h-3 w-3" />
                          )}
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>{t('actions.confirmPermanentDelete')}</AlertDialogTitle>
                          <AlertDialogDescription>{t('actions.permanentDeleteWarning')}</AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>{t('upload.cancel')}</AlertDialogCancel>
                          <AlertDialogAction
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                            onClick={() => handlePermanentDelete(doc.id)}
                          >
                            {t('actions.permanentDelete')}
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                );
              })}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between text-xs text-muted-foreground pt-1">
                <span>{archivePage}/{totalPages}</span>
                <div className="flex gap-1">
                  <Button variant="outline" size="icon" className="h-7 w-7"
                    disabled={archivePage <= 1} onClick={() => setArchivePage(p => p - 1)}>
                    <ChevronLeft className="h-3.5 w-3.5" />
                  </Button>
                  <Button variant="outline" size="icon" className="h-7 w-7"
                    disabled={archivePage >= totalPages} onClick={() => setArchivePage(p => p + 1)}>
                    <ChevronRight className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </CollapsibleContent>
    </Collapsible>
  );
}
