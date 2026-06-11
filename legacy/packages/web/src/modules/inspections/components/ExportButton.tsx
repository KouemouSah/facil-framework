'use client'

import { useCallback, useState } from 'react'
import { useTranslations } from 'next-intl'
import { Download, FileSpreadsheet, FileText, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { inspectionApi } from '../services/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ExportButtonProps {
  filters: Record<string, string | boolean | undefined>
  dateRange?: { from?: string; to?: string }
  disabled?: boolean
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10)
}

/** Convert filters to a Record<string,string> for the PDF export API */
function toStringFilters(
  filters: Record<string, string | boolean | undefined>,
): Record<string, string> {
  const out: Record<string, string> = {}
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== null && v !== '') {
      out[k] = String(v)
    }
  }
  return out
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ExportButton({
  filters,
  dateRange,
  disabled,
}: ExportButtonProps) {
  const t = useTranslations('inspection')
  const [exporting, setExporting] = useState<string | null>(null)

  const handleExportCSV = useCallback(async () => {
    try {
      setExporting('csv')
      const blob = await inspectionApi.exportCSV(
        toStringFilters(filters) as Record<string, string | boolean>,
      )
      triggerDownload(blob, `inspections_${todayISO()}.csv`)
    } catch {
      // Error handled silently — toast can be added later
    } finally {
      setExporting(null)
    }
  }, [filters])

  const handleExportAgentsCSV = useCallback(async () => {
    try {
      setExporting('agents')
      const blob = await inspectionApi.exportAgentsCSV({
        date_from: dateRange?.from,
        date_to: dateRange?.to,
      })
      triggerDownload(blob, `agents_performance_${todayISO()}.csv`)
    } catch {
      // Error handled silently
    } finally {
      setExporting(null)
    }
  }, [dateRange])

  const handleExportPDF = useCallback(async () => {
    try {
      setExporting('pdf')
      const blob = await inspectionApi.exportPDF(toStringFilters(filters))
      triggerDownload(blob, `inspections_${todayISO()}.pdf`)
    } catch {
      // Error handled silently
    } finally {
      setExporting(null)
    }
  }, [filters])

  const isExporting = exporting !== null

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="h-8 gap-1.5 text-xs"
          disabled={disabled || isExporting}
        >
          {isExporting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          {t('export.title')}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[200px]">
        <DropdownMenuItem
          onClick={handleExportCSV}
          disabled={isExporting}
          className="gap-2 text-sm"
        >
          <FileSpreadsheet className="h-4 w-4" />
          {t('export.csv')}
          {exporting === 'csv' && (
            <Loader2 className="ml-auto h-3.5 w-3.5 animate-spin" />
          )}
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={handleExportAgentsCSV}
          disabled={isExporting}
          className="gap-2 text-sm"
        >
          <FileSpreadsheet className="h-4 w-4" />
          {t('export.agents_csv')}
          {exporting === 'agents' && (
            <Loader2 className="ml-auto h-3.5 w-3.5 animate-spin" />
          )}
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={handleExportPDF}
          disabled={isExporting}
          className="gap-2 text-sm"
        >
          <FileText className="h-4 w-4" />
          {t('export.pdf')}
          {exporting === 'pdf' && (
            <Loader2 className="ml-auto h-3.5 w-3.5 animate-spin" />
          )}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
