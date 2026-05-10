'use client';

/**
 * VaultDocumentPicker - Dialog for selecting a document from the user's vault.
 *
 * Used in the wizard DocumentUploader to allow re-using a previously uploaded
 * vault document instead of uploading a new file.
 *
 * @module user-documents/components
 */

import { useState } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import { useQuery } from '@tanstack/react-query';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  FileText,
  FolderOpen,
  Check,
  Image as ImageIcon,
  File,
  AlertTriangle,
} from 'lucide-react';
import { userDocumentsApi } from '../services/api';
import { ExpiryBadge } from './ExpiryBadge';
import type { UserDocumentListItem, DocumentCategory } from '../types';
import { CATEGORY_LABELS } from '../types';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface VaultDocumentPickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workflowCode?: string;
  onSelect: (documentId: string, documentName: string) => void;
}

// ---------------------------------------------------------------------------
// Category color mapping (same as DocumentCard)
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
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function VaultDocumentPicker({
  open,
  onOpenChange,
  workflowCode,
  onSelect,
}: VaultDocumentPickerProps) {
  const t = useTranslations('userDocuments');
  const locale = useLocale() as 'es' | 'fr' | 'en';
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Fetch vault documents -- filtered by workflow if provided, else personal
  const { data: documents, isLoading, error } = useQuery<UserDocumentListItem[], Error>({
    queryKey: ['vault-picker', workflowCode ?? 'personal'],
    queryFn: () => {
      if (workflowCode) {
        return userDocumentsApi.getForWorkflow(workflowCode);
      }
      return userDocumentsApi.list({ source: 'personal', limit: 20 }).then((r) => r.items);
    },
    enabled: open,
    staleTime: 30_000,
  });

  const handleConfirm = () => {
    if (!selectedId || !documents) return;
    const doc = documents.find((d) => d.id === selectedId);
    if (doc) {
      onSelect(doc.id, doc.display_name || doc.file_name);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FolderOpen className="h-5 w-5" strokeWidth={1.5} />
            {t('vaultPicker.title')}
          </DialogTitle>
        </DialogHeader>

        {/* Loading state */}
        {isLoading && (
          <div className="space-y-3 py-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex items-center gap-3 p-3">
                <Skeleton className="h-10 w-10 rounded" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="flex items-center gap-2 py-6 justify-center text-sm text-destructive">
            <AlertTriangle className="h-4 w-4" />
            {t('vaultPicker.error')}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && documents && documents.length === 0 && (
          <div className="text-center py-8 text-sm text-muted-foreground">
            <FolderOpen className="h-10 w-10 mx-auto mb-2 opacity-40" strokeWidth={1.5} />
            <p>{t('vaultPicker.empty')}</p>
          </div>
        )}

        {/* Document list */}
        {!isLoading && !error && documents && documents.length > 0 && (
          <>
            <ScrollArea className="max-h-[320px] -mx-1">
              <div className="space-y-1 px-1">
                {documents.map((doc) => {
                  const Icon = getFileIcon(doc.mime_type);
                  const isSelected = selectedId === doc.id;
                  const categoryLabel = CATEGORY_LABELS[doc.category]?.[locale] ?? doc.category;

                  return (
                    <button
                      key={doc.id}
                      type="button"
                      onClick={() => setSelectedId(doc.id)}
                      className={`w-full flex items-center gap-3 p-3 rounded-md text-left transition-colors ${
                        isSelected
                          ? 'bg-primary/10 border border-primary/30'
                          : 'hover:bg-muted border border-transparent'
                      }`}
                    >
                      {/* Icon */}
                      <div className="flex-shrink-0 h-10 w-10 rounded bg-muted flex items-center justify-center">
                        {isSelected ? (
                          <Check className="h-5 w-5 text-primary" strokeWidth={2} />
                        ) : (
                          <Icon className="h-5 w-5 text-muted-foreground" strokeWidth={1.5} />
                        )}
                      </div>

                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">
                          {doc.display_name || doc.file_name}
                        </p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <Badge
                            variant="secondary"
                            className={`text-[10px] px-1.5 py-0 ${
                              CATEGORY_COLORS[doc.category] ?? CATEGORY_COLORS.other
                            }`}
                          >
                            {categoryLabel}
                          </Badge>
                          <span className="text-[10px] text-muted-foreground">
                            {formatFileSize(doc.file_size_bytes)}
                          </span>
                        </div>
                      </div>

                      {/* Expiry badge */}
                      <div className="flex-shrink-0">
                        <ExpiryBadge
                          expiryDate={doc.expiry_date}
                          expiryStatus={doc.expiry_status}
                          daysUntilExpiry={doc.days_until_expiry}
                          compact
                        />
                      </div>
                    </button>
                  );
                })}
              </div>
            </ScrollArea>

            {/* Confirm button */}
            <div className="flex justify-end pt-2 border-t">
              <Button
                size="sm"
                disabled={!selectedId}
                onClick={handleConfirm}
              >
                <Check className="mr-2 h-4 w-4" strokeWidth={1.5} />
                {t('vaultPicker.select')}
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
