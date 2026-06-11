'use client'

import { Download } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import type { DetailViewDocumentInfo } from '../types'

interface CitizenDocumentPreviewProps {
  document: DetailViewDocumentInfo | null
  open: boolean
  onClose: () => void
}

/**
 * Read-only document preview for citizens.
 * Shows images inline, PDFs in iframe, other types with download link.
 */
export function CitizenDocumentPreview({ document, open, onClose }: CitizenDocumentPreviewProps) {
  if (!document || !document.file_url) return null

  const isImage = document.mime_type?.startsWith('image/')
  const isPdf = document.mime_type === 'application/pdf'

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-4xl w-[95vw] max-h-[90vh] flex flex-col p-0">
        <DialogHeader className="px-6 pt-4 pb-2 flex-shrink-0">
          <div className="flex items-center justify-between">
            <DialogTitle className="text-sm font-medium truncate pr-4">
              {document.document_name}
            </DialogTitle>
            <Button
              variant="outline"
              size="sm"
              asChild
              className="flex-shrink-0"
            >
              <a href={document.file_url} download={document.file_name} target="_blank" rel="noopener noreferrer">
                <Download className="h-4 w-4 mr-1" />
                {document.file_name}
              </a>
            </Button>
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-auto px-6 pb-6">
          {isImage && (
            <div className="flex items-center justify-center min-h-[300px]">
                <img
                src={document.file_url}
                alt={document.document_name}
                className="max-w-full max-h-[75vh] object-contain rounded"
              />
            </div>
          )}

          {isPdf && (
            <iframe
              src={document.file_url}
              title={document.document_name}
              className="w-full h-[75vh] rounded border"
            />
          )}

          {!isImage && !isPdf && (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <p className="text-sm">
                {document.mime_type || 'Unknown type'}
              </p>
              <Button variant="outline" size="sm" className="mt-4" asChild>
                <a href={document.file_url} download={document.file_name} target="_blank" rel="noopener noreferrer">
                  <Download className="h-4 w-4 mr-1" />
                  Download
                </a>
              </Button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
