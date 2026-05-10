/**
 * DocumentUploadDialog - Dialog with drag-drop upload support
 *
 * Features:
 * - Drag & drop zone
 * - File picker fallback
 * - Per-file progress indicator
 * - Duplicate detection feedback
 * - Optional document type hint
 *
 * @module user-documents/components
 */

'use client';

import { useState, useCallback, useRef, type DragEvent } from 'react';
import { useTranslations } from 'next-intl';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import {
  Upload,
  FileText,
  Image as ImageIcon,
  File,
  CheckCircle,
  XCircle,
  AlertTriangle,
  X,
  Loader2,
} from 'lucide-react';
import { useDocumentUpload, type UploadFileState } from '../hooks';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DocumentUploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// ---------------------------------------------------------------------------
// File icon helper
// ---------------------------------------------------------------------------

function getFileIcon(mimeType: string | undefined | null) {
  if (!mimeType) return File;
  if (mimeType.startsWith('image/')) return ImageIcon;
  if (mimeType === 'application/pdf') return FileText;
  return File;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ---------------------------------------------------------------------------
// Status icon helper
// ---------------------------------------------------------------------------

function StatusIcon({ status }: { status: UploadFileState['status'] }) {
  switch (status) {
    case 'success':
      return <CheckCircle className="h-4 w-4 text-green-600" />;
    case 'error':
      return <XCircle className="h-4 w-4 text-destructive" />;
    case 'duplicate':
      return <AlertTriangle className="h-4 w-4 text-orange-500" />;
    case 'uploading':
      return <Loader2 className="h-4 w-4 text-primary animate-spin" />;
    default:
      return <File className="h-4 w-4 text-muted-foreground" />;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DocumentUploadDialog({
  open,
  onOpenChange,
}: DocumentUploadDialogProps) {
  const t = useTranslations('userDocuments');
  const {
    uploadMultiple,
    isUploading,
    fileStates,
    error: uploadError,
    reset,
  } = useDocumentUpload();

  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [notes, setNotes] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // -------------------------------------------------------------------
  // Drag & Drop handlers
  // -------------------------------------------------------------------

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    if (droppedFiles.length > 0) {
      setSelectedFiles((prev) => [...prev, ...droppedFiles].slice(0, 5));
    }
  }, []);

  // -------------------------------------------------------------------
  // File picker handler
  // -------------------------------------------------------------------

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        setSelectedFiles((prev) => [...prev, ...Array.from(files)].slice(0, 5));
      }
      // Reset input so re-selecting the same file works
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    },
    []
  );

  // -------------------------------------------------------------------
  // Remove a file from the selection
  // -------------------------------------------------------------------

  const removeFile = useCallback((index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  // -------------------------------------------------------------------
  // Upload handler
  // -------------------------------------------------------------------

  const handleUpload = useCallback(async () => {
    if (selectedFiles.length === 0) return;

    await uploadMultiple(selectedFiles, {
      notes: notes.trim() || undefined,
    });

    // If all succeeded, close the dialog after a brief delay
    // (user can see the green checkmarks)
    setTimeout(() => {
      setSelectedFiles([]);
      setNotes('');
      reset();
      onOpenChange(false);
    }, 1500);
  }, [selectedFiles, notes, uploadMultiple, reset, onOpenChange]);

  // -------------------------------------------------------------------
  // Close handler
  // -------------------------------------------------------------------

  const handleClose = useCallback(
    (isOpen: boolean) => {
      if (!isOpen && !isUploading) {
        setSelectedFiles([]);
        setNotes('');
        reset();
      }
      if (!isUploading) {
        onOpenChange(isOpen);
      }
    },
    [isUploading, reset, onOpenChange]
  );

  // -------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------

  const fileStatesArr = Array.from(fileStates.values());

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5 text-primary" />
            {t('upload.title')}
          </DialogTitle>
          <DialogDescription>{t('upload.description')}</DialogDescription>
        </DialogHeader>

        {/* Drop zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`
            border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
            ${isDragOver
              ? 'border-primary bg-primary/5'
              : 'border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50'}
          `}
        >
          <Upload className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
          <p className="text-sm font-medium">{t('upload.dropzone')}</p>
          <p className="text-xs text-muted-foreground mt-1">
            {t('upload.formats')}
          </p>
          <p className="text-xs text-muted-foreground">
            {t('upload.maxSize')}
          </p>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.jpg,.jpeg,.png,.tiff,.webp,.doc,.docx"
            onChange={handleFileSelect}
            className="hidden"
          />
        </div>

        {/* Selected files list */}
        {selectedFiles.length > 0 && !isUploading && (
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {selectedFiles.map((file, index) => {
              const Icon = getFileIcon(file.type);
              return (
                <div
                  key={`${file.name}-${file.size}-${index}`}
                  className="flex items-center gap-2 p-2 rounded-md bg-muted/50"
                >
                  <Icon className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span className="text-sm truncate flex-1">{file.name}</span>
                  <span className="text-xs text-muted-foreground shrink-0">
                    {formatBytes(file.size)}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 shrink-0"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFile(index);
                    }}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </div>
              );
            })}
          </div>
        )}

        {/* Upload progress */}
        {fileStatesArr.length > 0 && isUploading && (
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {fileStatesArr.map((fs) => (
              <div
                key={`${fs.file.name}-${fs.file.size}`}
                className="space-y-1"
              >
                <div className="flex items-center gap-2">
                  <StatusIcon status={fs.status} />
                  <span className="text-sm truncate flex-1">
                    {fs.file.name}
                  </span>
                  {fs.status === 'duplicate' && (
                    <Badge variant="outline" className="text-orange-600 text-[10px]">
                      {t('upload.duplicate')}
                    </Badge>
                  )}
                  {fs.status === 'error' && (
                    <span className="text-xs text-destructive truncate max-w-[150px]">
                      {fs.error}
                    </span>
                  )}
                </div>
                {(fs.status === 'uploading' || fs.status === 'pending') && (
                  <Progress value={fs.progress} className="h-1.5" />
                )}
              </div>
            ))}
          </div>
        )}

        {/* Notes */}
        {selectedFiles.length > 0 && !isUploading && (
          <div>
            <label className="text-sm font-medium" htmlFor="upload-notes">
              {t('upload.notes')}
            </label>
            <Input
              id="upload-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t('upload.notesPlaceholder')}
              className="mt-1"
            />
          </div>
        )}

        {/* Global error */}
        {uploadError && (
          <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm text-destructive">
            {uploadError}
          </div>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleClose(false)}
            disabled={isUploading}
          >
            {t('upload.cancel')}
          </Button>
          <Button
            onClick={handleUpload}
            disabled={selectedFiles.length === 0 || isUploading}
          >
            {isUploading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t('upload.uploading')}
              </>
            ) : (
              <>
                <Upload className="mr-2 h-4 w-4" />
                {t('upload.submit', { count: selectedFiles.length })}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
