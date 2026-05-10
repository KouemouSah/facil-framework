'use client'

import { useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { Loader2, AlertTriangle, Clock } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { useBatchSession } from '../hooks/useBatchSession'
import { BatchWizardStep, BATCH_WIZARD_STEP_KEYS } from '../types'
import { WorkflowSelection } from './steps/WorkflowSelection'
import { BeneficiaryRoster } from './steps/BeneficiaryRoster'
import { SharedDocuments } from './steps/SharedDocuments'
import { BulkDocumentUpload } from './steps/BulkDocumentUpload'
import { AssignmentReview } from './steps/AssignmentReview'
import { BatchDataGrid } from './steps/BatchDataGrid'
import { BatchPayment } from './steps/BatchPayment'

// ============================================================================
// STEPPER
// ============================================================================

const STEPS = [
  BatchWizardStep.WORKFLOW_SELECTION,
  BatchWizardStep.BENEFICIARY_ROSTER,
  BatchWizardStep.SHARED_DOCUMENTS,
  BatchWizardStep.BULK_UPLOAD,
  BatchWizardStep.ASSIGNMENT_REVIEW,
  BatchWizardStep.DATA_GRID,
  BatchWizardStep.PAYMENT,
]

function BatchStepper({ currentStep }: { currentStep: BatchWizardStep }) {
  const t = useTranslations('batch')
  return (
    <nav className="mb-6">
      <ol className="flex items-center gap-1 overflow-x-auto pb-2">
        {STEPS.map((step, index) => {
          const isActive = step === currentStep
          const isDone = step < currentStep
          return (
            <li key={step} className="flex items-center">
              {index > 0 && (
                <div
                  className={`h-0.5 w-6 mx-1 ${
                    isDone ? 'bg-green-500' : 'bg-gray-200'
                  }`}
                />
              )}
              <div
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                  isActive
                    ? 'bg-blue-100 text-blue-700 ring-2 ring-blue-300'
                    : isDone
                      ? 'bg-green-100 text-green-700'
                      : 'bg-gray-100 text-gray-500'
                }`}
              >
                <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-current/10 text-[10px]">
                  {isDone ? '✓' : index + 1}
                </span>
                <span className="hidden sm:inline">
                  {t(BATCH_WIZARD_STEP_KEYS[step])}
                </span>
              </div>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

// ============================================================================
// TTL BANNER
// ============================================================================

function TTLBanner({
  timeRemaining,
  isExpiring,
  isExpired,
}: {
  timeRemaining: number | null
  isExpiring: boolean
  isExpired: boolean
}) {
  const t = useTranslations('batch')

  if (!isExpiring && !isExpired) return null

  const remaining = timeRemaining ?? 0
  const minutes = Math.floor(remaining / 60)
  const seconds = remaining % 60

  if (isExpired) {
    return (
      <Alert variant="destructive" className="mb-4">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>
          {t('wizard.sessionExpired')}
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <Alert className="mb-4 border-amber-200 bg-amber-50">
      <Clock className="h-4 w-4 text-amber-600" />
      <AlertDescription className="text-amber-700">
        {t('wizard.timeRemaining')}: {minutes}:{seconds.toString().padStart(2, '0')} —{' '}
        {t('wizard.saveWarning')}
      </AlertDescription>
    </Alert>
  )
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export function BatchWizard() {
  const router = useRouter()
  const params = useParams()
  const locale = useLocale()
  const t = useTranslations('batch')
  const sessionId = params?.sessionId as string | undefined

  const hook = useBatchSession()
  const {
    session,
    isLoading,
    error,
    currentStep,
    timeRemaining,
    isExpiring,
    isExpired,
    canGoNext,
    loadSession,
    goNext,
    goBack,
    clearError,
  } = hook

  // Load session on mount if sessionId is in URL
  useEffect(() => {
    if (sessionId && !session) {
      loadSession(sessionId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  // Redirect after successful submit
  const handleSubmitSuccess = (batchId: string, redirectUrl?: string) => {
    if (redirectUrl) {
      window.location.href = redirectUrl
    } else {
      router.push(`/${locale}/dashboard/batch-requests/${batchId}`)
    }
  }

  // After session creation, push sessionId into URL
  const handleSessionCreated = (newSessionId: string) => {
    router.replace(`/${locale}/dashboard/batch-requests/wizard/${newSessionId}`)
  }

  if (isLoading && !session) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
        <span className="ml-2 text-gray-500">{t('wizard.loadingSession')}</span>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">{t('wizard.title')}</h1>

      <TTLBanner
        timeRemaining={timeRemaining}
        isExpiring={isExpiring}
        isExpired={isExpired}
      />

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription className="flex items-center justify-between">
            <span>{error}</span>
            <Button variant="ghost" size="sm" onClick={clearError}>
              ✕
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {session && <BatchStepper currentStep={currentStep} />}

      <div className="bg-white rounded-lg border p-6">
        {currentStep === BatchWizardStep.WORKFLOW_SELECTION && (
          <WorkflowSelection
            hook={hook}
            onSessionCreated={handleSessionCreated}
          />
        )}
        {currentStep === BatchWizardStep.BENEFICIARY_ROSTER && (
          <BeneficiaryRoster hook={hook} />
        )}
        {currentStep === BatchWizardStep.SHARED_DOCUMENTS && (
          <SharedDocuments hook={hook} />
        )}
        {currentStep === BatchWizardStep.BULK_UPLOAD && (
          <BulkDocumentUpload hook={hook} />
        )}
        {currentStep === BatchWizardStep.ASSIGNMENT_REVIEW && (
          <AssignmentReview hook={hook} />
        )}
        {currentStep === BatchWizardStep.DATA_GRID && (
          <BatchDataGrid hook={hook} />
        )}
        {currentStep === BatchWizardStep.PAYMENT && (
          <BatchPayment
            hook={hook}
            onSuccess={handleSubmitSuccess}
          />
        )}
      </div>

      {session && currentStep > BatchWizardStep.WORKFLOW_SELECTION && currentStep < BatchWizardStep.PAYMENT && (
        <div className="flex justify-between mt-6">
          <Button variant="outline" onClick={goBack}>
            {t('wizard.previous')}
          </Button>
          <Button onClick={goNext} disabled={!canGoNext()}>
            {t('wizard.next')}
          </Button>
        </div>
      )}
    </div>
  )
}
