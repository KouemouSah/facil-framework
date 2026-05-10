'use client'

import { useState, useEffect, useMemo } from 'react'
import { useTranslations } from 'next-intl'
import {
  ArrowRightLeft,
  FileText,
  User,
  Check,
  Loader2,
  AlertCircle,
  Sparkles,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { UseBatchSessionReturn } from '../../hooks/useBatchSession'

interface AssignmentReviewProps {
  hook: UseBatchSessionReturn
}

export function AssignmentReview({ hook }: AssignmentReviewProps) {
  const {
    session,
    isLoading,
    isSaving,
    confirmAssignments,
    extractDocuments,
  } = hook
  const t = useTranslations('batch')

  const beneficiaries = session?.beneficiaries || []
  const classifications = useMemo(
    () => session?.classificationResults || [],
    [session?.classificationResults]
  )

  // Local state for editable assignments
  const [assignments, setAssignments] = useState<
    Array<{
      filePath: string
      fileName: string
      documentType: string
      beneficiaryId: string | null
      confidence: number
    }>
  >([])
  const [isExtracting, setIsExtracting] = useState(false)
  const [extractResult, setExtractResult] = useState<{ extracted: number; failed: number } | null>(null)

  // Initialize assignments from classifications
  useEffect(() => {
    if (classifications.length > 0) {
      setAssignments(
        classifications.map((c) => ({
          filePath: c.filePath,
          fileName: c.fileName,
          documentType: c.documentType,
          beneficiaryId: c.matchedBeneficiaryId,
          confidence: c.confidence,
        }))
      )
    }
  }, [classifications])

  // Unassigned count
  const unassignedCount = useMemo(
    () => assignments.filter((a) => !a.beneficiaryId).length,
    [assignments]
  )

  const handleBeneficiaryChange = (index: number, beneficiaryId: string) => {
    setAssignments((prev) => {
      const updated = [...prev]
      updated[index] = {
        ...updated[index],
        beneficiaryId: beneficiaryId === '__none__' ? null : beneficiaryId,
      }
      return updated
    })
  }

  const handleConfirmAndExtract = async () => {
    // 1. Confirm assignments
    const confirmed = await confirmAssignments(
      assignments.map((a) => ({
        file_path: a.filePath,
        document_type: a.documentType,
        beneficiary_id: a.beneficiaryId,
      }))
    )
    if (!confirmed) return

    // 2. Run extraction
    setIsExtracting(true)
    const result = await extractDocuments()
    if (result) {
      setExtractResult({ extracted: result.extracted, failed: result.failed })
    }
    setIsExtracting(false)
  }

  if (assignments.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400">
        <ArrowRightLeft className="h-10 w-10 mx-auto mb-3 opacity-30" />
        <p>{t('assignment.noAssignments')}</p>
        <p className="text-sm mt-1">
          {t('assignment.goBackHint')}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ArrowRightLeft className="h-5 w-5 text-blue-600" />
          <h2 className="text-lg font-semibold">{t('assignment.title')}</h2>
        </div>
        {unassignedCount > 0 && (
          <Badge className="bg-amber-100 text-amber-700">
            {unassignedCount} {t('assignment.unassigned')}
          </Badge>
        )}
      </div>

      {unassignedCount > 0 && (
        <Alert className="border-amber-200 bg-amber-50">
          <AlertCircle className="h-4 w-4 text-amber-600" />
          <AlertDescription className="text-amber-700">
            {t('assignment.assignHint')}
          </AlertDescription>
        </Alert>
      )}

      {/* Assignments table */}
      <div className="border rounded-lg divide-y max-h-[500px] overflow-y-auto">
        {assignments.map((assignment, idx) => (
          <div
            key={idx}
            className="flex items-center gap-3 px-4 py-3"
          >
            {/* File info */}
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <FileText className="h-4 w-4 text-gray-400 flex-shrink-0" />
              <div className="min-w-0">
                <p className="text-sm truncate">{assignment.fileName}</p>
                <div className="flex items-center gap-1">
                  <Badge variant="outline" className="text-[10px]">
                    {assignment.documentType}
                  </Badge>
                  <span className="text-[10px] text-gray-400">
                    {Math.round(assignment.confidence * 100)}%
                  </span>
                </div>
              </div>
            </div>

            {/* Arrow */}
            <ArrowRightLeft className="h-4 w-4 text-gray-300 flex-shrink-0" />

            {/* Beneficiary selector */}
            <div className="flex-1 max-w-[250px]">
              <Select
                value={assignment.beneficiaryId || '__none__'}
                onValueChange={(val) => handleBeneficiaryChange(idx, val)}
              >
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">
                    <span className="text-gray-400">{t('assignment.unassigned')}</span>
                  </SelectItem>
                  {beneficiaries.map((b) => (
                    <SelectItem key={b.id} value={b.id}>
                      <span className="flex items-center gap-1">
                        <User className="h-3 w-3" />
                        {b.name}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Confidence indicator */}
            {assignment.confidence >= 0.85 && (
              <Sparkles className="h-4 w-4 text-green-500 flex-shrink-0" />
            )}
          </div>
        ))}
      </div>

      {/* Extract result */}
      {extractResult && (
        <Alert className={extractResult.failed > 0 ? 'border-amber-200 bg-amber-50' : 'border-green-200 bg-green-50'}>
          <Check className={`h-4 w-4 ${extractResult.failed > 0 ? 'text-amber-600' : 'text-green-600'}`} />
          <AlertDescription>
            {t('assignment.extractionDone')}: {extractResult.extracted} {t('assignment.docProcessed')}
            {extractResult.failed > 0 && `, ${extractResult.failed} ${t('assignment.failed')}`}.
          </AlertDescription>
        </Alert>
      )}

      {/* Confirm + Extract button */}
      <div className="flex justify-end">
        <Button
          onClick={handleConfirmAndExtract}
          disabled={isLoading || isSaving || isExtracting}
          size="lg"
        >
          {isExtracting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              {t('assignment.extracting')}
            </>
          ) : (
            <>
              <Check className="h-4 w-4 mr-2" />
              {t('assignment.confirmAndExtract')}
            </>
          )}
        </Button>
      </div>
    </div>
  )
}
