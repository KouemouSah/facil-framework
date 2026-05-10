'use client'

/**
 * WorkflowWizard Component
 * Multi-step wizard for citizen service request workflow
 */

import { useEffect, useMemo, useCallback, useState } from 'react'
import { useTranslations, useLocale } from 'next-intl'
import { getLocalizedField } from '@/core/utils/i18n-helpers'
import {
  CheckCircle,
  Circle,
  ChevronRight,
  ChevronLeft,
  Loader2,
  AlertCircle,
  Upload,
  FileText,
  CreditCard,
  User,
  List,
  ListChecks,
  Calendar,
  MapPin,
  Settings,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Progress } from '@/components/ui/progress'

import { useServiceRequests } from '../hooks/useServiceRequests'
import type { WorkflowStep, StepType, ServiceRequestCreate } from '../types'

// Step type icons mapping
const stepTypeIcons: Record<StepType, React.ComponentType<{ className?: string }>> = {
  selection: ListChecks,
  identity_verification: User,
  sub_type_selection: List,
  document_upload: Upload,
  form_review: FileText,
  payment: CreditCard,
  confirmation: CheckCircle,
  appointment: Calendar,
  site_selection: MapPin,
  custom: Settings,
}

// ============================================================================
// COMPONENT PROPS
// ============================================================================

interface WorkflowWizardProps {
  workflowCode: string
  subType?: string
  locale?: 'es' | 'fr' | 'en'
  onComplete?: (requestId: string) => void
  onCancel?: () => void
  renderStep?: (step: WorkflowStep, props: StepRenderProps) => React.ReactNode
}

interface StepRenderProps {
  request: ReturnType<typeof useServiceRequests>['currentRequest']
  documents: ReturnType<typeof useServiceRequests>['documents']
  validationResults: ReturnType<typeof useServiceRequests>['validationResults']
  tariff: ReturnType<typeof useServiceRequests>['tariff']
  isLoading: boolean
  isSaving: boolean
  onSubmit: (data: Record<string, unknown>) => Promise<void>
  onUploadDocument: (code: string, file: File, face?: string) => Promise<void>
  onDeleteDocument: (documentId: string) => Promise<void>
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export function WorkflowWizard({
  workflowCode,
  subType,
  locale: localeProp = 'es',
  onComplete,
  onCancel,
  renderStep,
}: WorkflowWizardProps) {
  const t = useTranslations('service_requests')
  const intlLocale = useLocale()
  const locale = intlLocale || localeProp
  const [isInitializing, setIsInitializing] = useState(true)

  const {
    currentRequest,
    workflow,
    currentStep,
    documents,
    validationResults,
    tariff,
    isLoading,
    isSaving,
    error,
    startWorkflow,
    submitStep,
    previousStep,
    uploadDocument,
    deleteDocument,
    clearError,
  } = useServiceRequests()

  // Initialize workflow
  useEffect(() => {
    const init = async () => {
      setIsInitializing(true)
      const data: ServiceRequestCreate = {
        workflowCode,
        subType,
      }
      await startWorkflow(data)
      setIsInitializing(false)
    }

    init()
  }, [workflowCode, subType, startWorkflow])

  // Calculate progress
  const progress = useMemo(() => {
    if (!workflow || !currentRequest) return 0
    const totalSteps = workflow.steps.length
    const currentStepNum = currentRequest.currentStep
    return Math.round((currentStepNum / totalSteps) * 100)
  }, [workflow, currentRequest])

  // Get step title - locale-aware with fallback to Spanish
  const getStepTitle = useCallback((step: WorkflowStep): string => {
    return getLocalizedField(step as unknown as Record<string, unknown>, 'title', locale)
  }, [locale])

  // Get step description - locale-aware with fallback to Spanish
  const getStepDescription = useCallback((step: WorkflowStep): string => {
    return getLocalizedField(step as unknown as Record<string, unknown>, 'description', locale)
  }, [locale])

  // Handle step submission
  const handleSubmit = useCallback(async (data: Record<string, unknown>) => {
    if (!currentStep) return

    const success = await submitStep({
      stepId: currentStep.stepId,
      data,
    })

    // Check if workflow is complete
    if (success && currentRequest) {
      // If we're on the last step and submission was successful
      const isLastStep = workflow && currentRequest.currentStep >= workflow.steps.length
      if (isLastStep && onComplete) {
        onComplete(currentRequest.id)
      }
    }
  }, [currentStep, submitStep, currentRequest, workflow, onComplete])

  // Handle document upload
  const handleUploadDocument = useCallback(async (
    code: string,
    file: File,
    face?: string
  ) => {
    await uploadDocument(code, file, face)
  }, [uploadDocument])

  // Handle document delete
  const handleDeleteDocument = useCallback(async (documentId: string) => {
    await deleteDocument(documentId)
  }, [deleteDocument])

  // Handle previous step
  const handlePrevious = useCallback(async () => {
    await previousStep()
  }, [previousStep])

  // Handle cancel
  const handleCancel = useCallback(() => {
    if (onCancel) {
      onCancel()
    }
  }, [onCancel])

  // Loading state
  if (isInitializing || isLoading) {
    return (
      <Card className="w-full max-w-4xl mx-auto">
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <span className="ml-2">{t('loading')}</span>
        </CardContent>
      </Card>
    )
  }

  // Error state
  if (error && !currentRequest) {
    return (
      <Card className="w-full max-w-4xl mx-auto">
        <CardContent className="py-8">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
          <div className="mt-4 flex justify-center">
            <Button onClick={clearError} variant="outline">
              {t('retry')}
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!workflow || !currentRequest || !currentStep) {
    return null
  }

  const StepIcon = stepTypeIcons[currentStep.stepType as StepType] || Circle

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      {/* Progress Header */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">
                {getLocalizedField(workflow as unknown as Record<string, unknown>, 'serviceName', locale)}
              </CardTitle>
              <CardDescription>
                {t('step_of', {
                  current: currentRequest.currentStep,
                  total: workflow.steps.length,
                })}
              </CardDescription>
            </div>
            <div className="text-sm text-muted-foreground">
              {currentRequest.requestNumber}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Progress value={progress} className="h-2" />

          {/* Step indicators */}
          <div className="flex justify-between mt-4">
            {workflow.steps.map((step, index) => {
              const isComplete = step.stepNumber < currentRequest.currentStep
              const isCurrent = step.stepNumber === currentRequest.currentStep
              const Icon = stepTypeIcons[step.stepType as StepType] || Circle

              return (
                <div
                  key={step.stepId}
                  className={`flex flex-col items-center ${
                    index < workflow.steps.length - 1 ? 'flex-1' : ''
                  }`}
                >
                  <div
                    className={`
                      w-8 h-8 rounded-full flex items-center justify-center
                      ${isComplete ? 'bg-green-500 text-white' : ''}
                      ${isCurrent ? 'bg-primary text-primary-foreground' : ''}
                      ${!isComplete && !isCurrent ? 'bg-muted text-muted-foreground' : ''}
                    `}
                  >
                    {isComplete ? (
                      <CheckCircle className="h-4 w-4" />
                    ) : (
                      <Icon className="h-4 w-4" />
                    )}
                  </div>
                  <span
                    className={`
                      text-xs mt-1 text-center hidden sm:block
                      ${isCurrent ? 'font-medium' : 'text-muted-foreground'}
                    `}
                  >
                    {getStepTitle(step)}
                  </span>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* Current Step Content */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg">
              <StepIcon className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle>{getStepTitle(currentStep)}</CardTitle>
              {getStepDescription(currentStep) && (
                <CardDescription>{getStepDescription(currentStep)}</CardDescription>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* Error Alert */}
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Validation Errors */}
          {validationResults.filter(v => !v.isValid && v.severity === 'error').length > 0 && (
            <Alert variant="destructive" className="mb-4">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                <ul className="list-disc list-inside">
                  {validationResults
                    .filter(v => !v.isValid && v.severity === 'error')
                    .map((v, i) => (
                      <li key={i}>
                        {getLocalizedField(v as unknown as Record<string, unknown>, 'message', locale)}
                      </li>
                    ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}

          {/* Render custom step content or default */}
          {renderStep ? (
            renderStep(currentStep, {
              request: currentRequest,
              documents,
              validationResults,
              tariff,
              isLoading,
              isSaving,
              onSubmit: handleSubmit,
              onUploadDocument: handleUploadDocument,
              onDeleteDocument: handleDeleteDocument,
            })
          ) : (
            <DefaultStepContent
              step={currentStep}
              documents={documents}
              locale={locale as 'es' | 'fr' | 'en'}
              onSubmit={handleSubmit}
              onUploadDocument={handleUploadDocument}
              isSaving={isSaving}
            />
          )}
        </CardContent>
      </Card>

      {/* Navigation Buttons */}
      <div className="flex justify-between">
        <div className="flex gap-2">
          {currentRequest.currentStep > 1 && (
            <Button
              variant="outline"
              onClick={handlePrevious}
              disabled={isSaving}
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              {t('previous')}
            </Button>
          )}
          <Button variant="ghost" onClick={handleCancel} disabled={isSaving}>
            {t('cancel')}
          </Button>
        </div>

        <Button
          onClick={() => handleSubmit({})}
          disabled={isSaving}
        >
          {isSaving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
          {currentRequest.currentStep === workflow.steps.length
            ? t('submit')
            : t('next')}
          {currentRequest.currentStep < workflow.steps.length && (
            <ChevronRight className="h-4 w-4 ml-1" />
          )}
        </Button>
      </div>
    </div>
  )
}

// ============================================================================
// DEFAULT STEP CONTENT
// ============================================================================

interface DefaultStepContentProps {
  step: WorkflowStep
  documents: ReturnType<typeof useServiceRequests>['documents']
  locale: 'es' | 'fr' | 'en'
  onSubmit: (data: Record<string, unknown>) => Promise<void>
  onUploadDocument: (code: string, file: File, face?: string) => Promise<void>
  isSaving: boolean
}

function DefaultStepContent({
  step,
  documents,
  locale: stepLocale,
  onUploadDocument,
  isSaving,
}: DefaultStepContentProps) {
  const t = useTranslations('service_requests')

  // Document upload step
  if (step.stepType === 'document_upload' && step.documents) {
    return (
      <div className="space-y-4">
        {step.documents.map((doc) => {
          const uploaded = documents.find(d => d.documentCode === doc.documentCode)

          return (
            <div
              key={doc.documentCode}
              className={`
                p-4 border rounded-lg
                ${uploaded ? 'border-green-200 bg-green-50' : 'border-dashed'}
              `}
            >
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-medium">
                    {getLocalizedField(doc as unknown as Record<string, unknown>, 'documentName', stepLocale)}
                    {doc.isRequired && (
                      <span className="text-red-500 ml-1">*</span>
                    )}
                  </h4>
                  {getLocalizedField(doc as unknown as Record<string, unknown>, 'instructions', stepLocale) && (
                    <p className="text-sm text-muted-foreground">
                      {getLocalizedField(doc as unknown as Record<string, unknown>, 'instructions', stepLocale)}
                    </p>
                  )}
                </div>

                {uploaded ? (
                  <div className="flex items-center gap-2">
                    <CheckCircle className="h-5 w-5 text-green-500" />
                    <span className="text-sm text-green-700">
                      {uploaded.fileName}
                    </span>
                  </div>
                ) : (
                  <label className="cursor-pointer">
                    <input
                      type="file"
                      className="hidden"
                      accept={doc.acceptedFormats?.map(f => `.${f}`).join(',') || '*'}
                      onChange={(e) => {
                        const file = e.target.files?.[0]
                        if (file) {
                          onUploadDocument(doc.documentCode, file)
                        }
                      }}
                      disabled={isSaving}
                    />
                    <Button variant="outline" size="sm" disabled={isSaving} asChild>
                      <span>
                        <Upload className="h-4 w-4 mr-2" />
                        {t('upload')}
                      </span>
                    </Button>
                  </label>
                )}
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  // Confirmation step
  if (step.stepType === 'confirmation') {
    return (
      <div className="text-center py-8">
        <CheckCircle className="h-16 w-16 text-green-500 mx-auto mb-4" />
        <h3 className="text-xl font-semibold mb-2">
          {t('ready_to_submit')}
        </h3>
        <p className="text-muted-foreground">
          {t('review_and_submit')}
        </p>
      </div>
    )
  }

  // Default: show step info
  return (
    <div className="py-8 text-center text-muted-foreground">
      <p>{t('step_content_placeholder')}</p>
    </div>
  )
}

export default WorkflowWizard
