'use client'

/**
 * VerificationFuncionarioTab Component
 * Tab content for civil servant verification in the Profile page
 *
 * Session-based workflow (v2):
 * 1. User enters matricula and starts session (30-min TTL)
 * 2. User uploads DIP document (OCR extraction)
 * 3. User uploads proof document (nombramiento/carnet/contrato)
 * 4. User reviews extracted data and cross-validation results
 * 5. User submits - atomic transaction (Firebase upload + DB insert)
 * 6. Success view with complete recap
 */

import { useState, useCallback, useEffect } from 'react'
import { useTranslations, useLocale } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useToast } from '@/hooks/use-toast'
import {
  CheckCircle2,
  Clock,
  XCircle,
  Upload,
  FileText,
  AlertCircle,
  Loader2,
  ChevronRight,
  ChevronLeft,
  BadgeCheck,
  Send,
  AlertTriangle,
  Copy,
  Home,
  RefreshCw,
  Timer,
  Shield,
  User,
  FileCheck,
  Sparkles,
} from 'lucide-react'

import { useVerificacionStatus } from '../hooks/useVerificacionStatus'
import { verificacionApi } from '../services/verificacionApi'
import type {
  SessionWizardState,
  DocumentoTipoPrueba,
  ValidacionCruzada,
  SessionSubmitResponse,
} from '../types'
import { DOCUMENTO_TIPO_LABELS } from '../types'

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

// Status badge component
function StatusBadge({ status }: { status: string | null }) {
  const t = useTranslations('funcionario')

  if (!status) return null

  switch (status) {
    case 'pendiente':
      return (
        <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">
          <Clock className="mr-1 h-3 w-3" />
          {t('statusPending')}
        </Badge>
      )
    case 'aprobado':
      return (
        <Badge className="bg-green-500">
          <CheckCircle2 className="mr-1 h-3 w-3" />
          {t('statusApproved')}
        </Badge>
      )
    case 'rechazado':
      return (
        <Badge variant="destructive">
          <XCircle className="mr-1 h-3 w-3" />
          {t('statusRejected')}
        </Badge>
      )
    default:
      return null
  }
}

// Session timer component
function SessionTimer({ expiresAt }: { expiresAt: string | null }) {
  const [timeLeft, setTimeLeft] = useState<number>(0)
  const t = useTranslations('funcionario')

  useEffect(() => {
    if (!expiresAt) return

    const updateTimer = () => {
      const exp = new Date(expiresAt).getTime()
      const now = Date.now()
      const diff = Math.max(0, Math.floor((exp - now) / 1000))
      setTimeLeft(diff)
    }

    updateTimer()
    const interval = setInterval(updateTimer, 1000)
    return () => clearInterval(interval)
  }, [expiresAt])

  if (!expiresAt || timeLeft <= 0) return null

  const minutes = Math.floor(timeLeft / 60)
  const seconds = timeLeft % 60
  const isLow = timeLeft < 300 // Less than 5 minutes

  return (
    <div className={`flex items-center gap-2 text-sm ${isLow ? 'text-red-600' : 'text-muted-foreground'}`}>
      <Timer className="h-4 w-4" />
      <span>
        {t('sessionExpires')}: {minutes}:{seconds.toString().padStart(2, '0')}
      </span>
      {isLow && <AlertTriangle className="h-4 w-4" />}
    </div>
  )
}

// Document upload component
function DocumentUpload({
  label,
  description,
  onFileSelect,
  isLoading,
  isUploaded,
  fileName,
  confidence,
}: {
  label: string
  description: string
  onFileSelect: (file: File) => void
  isLoading: boolean
  isUploaded?: boolean
  fileName?: string
  confidence?: number
}) {
  const t = useTranslations('funcionario')

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      onFileSelect(file)
    }
  }

  return (
    <div className="space-y-3">
      <div>
        <Label className="text-base font-medium">{label}</Label>
        <p className="text-sm text-muted-foreground mt-1">{description}</p>
      </div>

      {isUploaded ? (
        <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
          <CheckCircle2 className="h-6 w-6 text-green-600 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="font-medium text-green-700 truncate">{fileName}</p>
            <div className="flex items-center gap-2 mt-1">
              <Progress value={(confidence || 0) * 100} className="h-2 flex-1" />
              <span className="text-sm text-green-600 flex-shrink-0">
                {Math.round((confidence || 0) * 100)}%
              </span>
            </div>
          </div>
        </div>
      ) : (
        <div className="relative">
          <input
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
            onChange={handleFileChange}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
            disabled={isLoading}
          />
          <div className="flex items-center justify-center p-8 border-2 border-dashed rounded-lg hover:border-primary hover:bg-primary/5 transition-colors">
            {isLoading ? (
              <div className="flex flex-col items-center gap-3">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <span className="text-sm font-medium">{t('processing')}</span>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <Upload className="h-10 w-10 text-muted-foreground" />
                <div className="text-center">
                  <p className="text-sm font-medium">{t('uploadPlaceholder')}</p>
                  <p className="text-xs text-muted-foreground mt-1">PDF, JPG, PNG (max 10MB)</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// Cross-validation display
function CrossValidationDisplay({ validation }: { validation: ValidacionCruzada | null }) {
  const t = useTranslations('funcionario')

  if (!validation) return null

  const isAutoValidable = validation.validacion_automatica_posible

  return (
    <Card className={isAutoValidable ? 'border-green-200 bg-green-50/50' : 'border-yellow-200 bg-yellow-50/50'}>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          {isAutoValidable ? (
            <>
              <Sparkles className="h-5 w-5 text-green-600" />
              <span className="text-green-700">{t('crossValidationSuccess')}</span>
            </>
          ) : (
            <>
              <AlertTriangle className="h-5 w-5 text-yellow-600" />
              <span className="text-yellow-700">{t('crossValidationWarning')}</span>
            </>
          )}
        </CardTitle>
        <CardDescription>
          {isAutoValidable ? t('autoValidableDesc') : t('manualReviewDesc')}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-3">
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wide">{t('nameDip')}</p>
              <p className="font-medium mt-1">{validation.nombre_dip || '-'}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wide">{t('nameDocument')}</p>
              <p className="font-medium mt-1">{validation.nombre_documento || '-'}</p>
            </div>
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted-foreground uppercase tracking-wide">{t('nameMatch')}</p>
              {validation.nombres_coinciden ? (
                <Badge className="bg-green-100 text-green-700">
                  <CheckCircle2 className="mr-1 h-3 w-3" />
                  {Math.round(validation.similitud_nombre * 100)}%
                </Badge>
              ) : (
                <Badge variant="outline" className="border-yellow-300 text-yellow-700">
                  <AlertTriangle className="mr-1 h-3 w-3" />
                  {Math.round(validation.similitud_nombre * 100)}%
                </Badge>
              )}
            </div>
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted-foreground uppercase tracking-wide">{t('matriculaMatch')}</p>
              {validation.matriculas_coinciden ? (
                <Badge className="bg-green-100 text-green-700">
                  <CheckCircle2 className="mr-1 h-3 w-3" />
                  {t('yes')}
                </Badge>
              ) : (
                <Badge variant="outline" className="border-red-300 text-red-700">
                  <XCircle className="mr-1 h-3 w-3" />
                  {t('no')}
                </Badge>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// Success view - Complete recap of submitted request
function SubmissionSuccessView({
  submitResult,
  wizardState,
  onBackToStatus,
}: {
  submitResult: SessionSubmitResponse
  wizardState: SessionWizardState
  onBackToStatus: () => void
}) {
  const t = useTranslations('funcionario')
  const locale = useLocale() as 'es' | 'fr' | 'en'
  const { toast } = useToast()

  const copyReference = () => {
    if (submitResult.reference) {
      navigator.clipboard.writeText(submitResult.reference)
      toast({
        title: t('copied'),
        description: t('referenceCopied'),
      })
    }
  }

  const validacion = submitResult.validacion_cruzada || wizardState.validacion_cruzada

  return (
    <div className="space-y-6">
      {/* Success Header */}
      <Card className="border-green-200 bg-gradient-to-br from-green-50 to-emerald-50">
        <CardHeader className="text-center pb-2">
          <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
            <CheckCircle2 className="h-10 w-10 text-green-600" />
          </div>
          <CardTitle className="text-2xl text-green-700">{t('submittedTitle')}</CardTitle>
          <CardDescription className="text-green-600 text-base">
            {t('submittedDescription')}
          </CardDescription>
        </CardHeader>
        <CardContent className="text-center space-y-4">
          {/* Reference */}
          {submitResult.reference && (
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-white rounded-lg shadow-sm border">
              <span className="text-sm text-muted-foreground">{t('referenceLabel')}:</span>
              <span className="font-mono font-bold text-lg">{submitResult.reference}</span>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={copyReference}>
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          )}

          {/* Auto-validable badge */}
          {submitResult.auto_validable && (
            <div className="flex justify-center">
              <Badge className="bg-emerald-100 text-emerald-700 px-4 py-1">
                <Sparkles className="mr-1 h-3 w-3" />
                {t('autoValidable')}
              </Badge>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recap Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileCheck className="h-5 w-5" />
            {t('recapTitle')}
          </CardTitle>
          <CardDescription>{t('recapDescription')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Personal Info */}
          <div>
            <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-2">
              <User className="h-4 w-4" />
              {t('personalInfo')}
            </h4>
            <div className="grid grid-cols-2 gap-4 bg-muted/30 rounded-lg p-4">
              <div>
                <p className="text-xs text-muted-foreground">{t('matricula')}</p>
                <p className="font-medium">{wizardState.matricula}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">{t('status')}</p>
                <StatusBadge status={submitResult.status || 'pendiente'} />
              </div>
            </div>
          </div>

          <Separator />

          {/* Documents */}
          <div>
            <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-2">
              <FileText className="h-4 w-4" />
              {t('uploadedDocuments')}
            </h4>
            <div className="space-y-2">
              {wizardState.documents.dip && (
                <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-lg">
                  <FileCheck className="h-5 w-5 text-green-600" />
                  <div className="flex-1">
                    <p className="font-medium">{t('dipLabel')}</p>
                    <p className="text-sm text-muted-foreground">{wizardState.documents.dip.file_name}</p>
                  </div>
                  <Badge variant="outline" className="text-green-600">
                    {Math.round((wizardState.documents.dip.confidence || 0) * 100)}%
                  </Badge>
                </div>
              )}
              {wizardState.documents.proof && (
                <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-lg">
                  <FileCheck className="h-5 w-5 text-green-600" />
                  <div className="flex-1">
                    <p className="font-medium">
                      {DOCUMENTO_TIPO_LABELS[wizardState.documents.proof.tipo][locale]}
                    </p>
                    <p className="text-sm text-muted-foreground">{wizardState.documents.proof.file_name}</p>
                  </div>
                  <Badge variant="outline" className="text-green-600">
                    {Math.round((wizardState.documents.proof.confidence || 0) * 100)}%
                  </Badge>
                </div>
              )}
            </div>
          </div>

          <Separator />

          {/* Cross-validation */}
          {validacion && (
            <div>
              <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-2">
                <Shield className="h-4 w-4" />
                {t('validationResults')}
              </h4>
              <CrossValidationDisplay validation={validacion} />
            </div>
          )}

          {/* Warnings */}
          {submitResult.warnings && submitResult.warnings.length > 0 && (
            <>
              <Separator />
              <div>
                <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" />
                  {t('warnings')}
                </h4>
                <div className="space-y-2">
                  {submitResult.warnings.map((warning, index) => (
                    <Alert key={index} variant="default" className="border-yellow-200 bg-yellow-50">
                      <AlertTriangle className="h-4 w-4 text-yellow-600" />
                      <AlertDescription className="text-yellow-700">
                        {warning.message}
                      </AlertDescription>
                    </Alert>
                  ))}
                </div>
              </div>
            </>
          )}
        </CardContent>
        <CardFooter className="flex-col gap-4 bg-muted/30">
          {/* Next steps */}
          <div className="w-full">
            <h4 className="text-sm font-semibold mb-2">{t('nextSteps')}</h4>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li className="flex items-start gap-2">
                <span className="text-primary">1.</span>
                {t('nextStep1')}
              </li>
              <li className="flex items-start gap-2">
                <span className="text-primary">2.</span>
                {t('nextStep2')}
              </li>
              <li className="flex items-start gap-2">
                <span className="text-primary">3.</span>
                {t('nextStep3')}
              </li>
            </ul>
          </div>

          <Button onClick={onBackToStatus} className="w-full">
            <Home className="mr-2 h-4 w-4" />
            {t('backToStatus')}
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function VerificationFuncionarioTab() {
  const t = useTranslations('funcionario')
  const locale = useLocale() as 'es' | 'fr' | 'en'
  const { toast } = useToast()
  const { status, isLoading: statusLoading, error: statusError, refetch } = useVerificacionStatus()

  // Session-based wizard state (v2)
  const [wizardState, setWizardState] = useState<SessionWizardState>({
    session_id: null,
    matricula: '',
    step: 'matricula',
    expires_at: null,
    documents: {},
    validacion_cruzada: null,
    form_review_data: null,
    submit_result: null,
  })

  const [isProcessing, setIsProcessing] = useState(false)
  const [selectedProofType, setSelectedProofType] = useState<DocumentoTipoPrueba>('nombramiento')

  // Handle starting session
  const handleStartSession = async () => {
    if (!wizardState.matricula.trim()) {
      toast({
        variant: 'destructive',
        title: t('error'),
        description: t('matriculaRequired'),
      })
      return
    }

    setIsProcessing(true)
    try {
      const result = await verificacionApi.startSession(wizardState.matricula)
      setWizardState((prev) => ({
        ...prev,
        session_id: result.session_id,
        expires_at: result.expires_at,
        step: 'dip',
      }))
      toast({
        title: t('sessionStarted'),
        description: t('uploadDipNext'),
      })
    } catch (err: unknown) {
      const error = err as { message?: string; code?: string }
      toast({
        variant: 'destructive',
        title: t('error'),
        description: error.message || t('createError'),
      })
    } finally {
      setIsProcessing(false)
    }
  }

  // Handle DIP upload
  const handleDipUpload = useCallback(
    async (file: File) => {
      if (!wizardState.session_id) return

      setIsProcessing(true)
      try {
        const result = await verificacionApi.sessionPreviewDocument(
          wizardState.session_id,
          file,
          'dip'
        )

        setWizardState((prev) => ({
          ...prev,
          expires_at: result.expires_at,
          documents: {
            ...prev.documents,
            dip: {
              file_name: result.file_name,
              confidence: result.confidence,
              extraction: result.extraction,
              uploaded: true,
            },
          },
          validacion_cruzada: result.validacion_cruzada,
          step: 'proof',
        }))

        toast({
          title: t('dipUploaded'),
          description: t('uploadProofNext'),
        })
      } catch (err: unknown) {
        const error = err as { message?: string; code?: string }
        if (error.code === 'SESSION_EXPIRED') {
          resetWizard()
          toast({
            variant: 'destructive',
            title: t('sessionExpired'),
            description: t('sessionExpiredDesc'),
          })
        } else {
          toast({
            variant: 'destructive',
            title: t('error'),
            description: error.message || t('uploadError'),
          })
        }
      } finally {
        setIsProcessing(false)
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- resetWizard is intentionally omitted to avoid re-creating callback
    [wizardState.session_id, toast, t]
  )

  // Handle proof document upload
  const handleProofUpload = useCallback(
    async (file: File) => {
      if (!wizardState.session_id) return

      setIsProcessing(true)
      try {
        const result = await verificacionApi.sessionPreviewDocument(
          wizardState.session_id,
          file,
          selectedProofType
        )

        setWizardState((prev) => ({
          ...prev,
          expires_at: result.expires_at,
          documents: {
            ...prev.documents,
            proof: {
              file_name: result.file_name,
              confidence: result.confidence,
              extraction: result.extraction,
              uploaded: true,
              tipo: selectedProofType,
            },
          },
          validacion_cruzada: result.validacion_cruzada,
          step: 'form_review',
        }))

        toast({
          title: t('proofUploaded'),
          description: t('reviewAndSubmit'),
        })
      } catch (err: unknown) {
        const error = err as { message?: string; code?: string }
        if (error.code === 'SESSION_EXPIRED') {
          resetWizard()
          toast({
            variant: 'destructive',
            title: t('sessionExpired'),
            description: t('sessionExpiredDesc'),
          })
        } else {
          toast({
            variant: 'destructive',
            title: t('error'),
            description: error.message || t('uploadError'),
          })
        }
      } finally {
        setIsProcessing(false)
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- resetWizard is intentionally omitted to avoid re-creating callback
    [wizardState.session_id, selectedProofType, toast, t]
  )

  // Handle submit
  const handleSubmit = async (forceSubmit = false) => {
    if (!wizardState.session_id) return

    setIsProcessing(true)
    try {
      const result = await verificacionApi.sessionValidateAndSubmit(
        wizardState.session_id,
        { force_submit: forceSubmit }
      )

      if (result.requires_confirmation && !forceSubmit) {
        // Show warnings and ask for confirmation
        toast({
          variant: 'default',
          title: t('confirmRequired'),
          description: result.message,
        })
        setWizardState((prev) => ({
          ...prev,
          submit_result: result,
        }))
        return
      }

      if (result.submitted) {
        setWizardState((prev) => ({
          ...prev,
          step: 'submitted',
          submit_result: result,
        }))

        toast({
          title: t('verificationSubmitted'),
          description: result.message,
        })

        // Refresh status
        refetch()
      }
    } catch (err: unknown) {
      const error = err as { message?: string; code?: string }
      if (error.code === 'SESSION_EXPIRED') {
        resetWizard()
        toast({
          variant: 'destructive',
          title: t('sessionExpired'),
          description: t('sessionExpiredDesc'),
        })
      } else {
        toast({
          variant: 'destructive',
          title: t('error'),
          description: error.message || t('submitError'),
        })
      }
    } finally {
      setIsProcessing(false)
    }
  }

  // Reset wizard
  const resetWizard = () => {
    setWizardState({
      session_id: null,
      matricula: '',
      step: 'matricula',
      expires_at: null,
      documents: {},
      validacion_cruzada: null,
      form_review_data: null,
      submit_result: null,
    })
    refetch()
  }

  // Loading state
  if (statusLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center min-h-[200px]">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    )
  }

  // Error state
  if (statusError) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>{t('error')}</AlertTitle>
        <AlertDescription>{statusError}</AlertDescription>
      </Alert>
    )
  }

  // Already verified
  if (status?.is_verified_funcionario) {
    return (
      <Card className="border-green-200 bg-green-50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-green-700">
            <BadgeCheck className="h-6 w-6" />
            {t('verifiedTitle')}
          </CardTitle>
          <CardDescription className="text-green-600">
            {t('verifiedDescription')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">{t('matricula')}</p>
              <p className="font-medium">{status.matricula}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('verifiedAt')}</p>
              <p className="font-medium">
                {status.funcionario_verified_at
                  ? new Date(status.funcionario_verified_at).toLocaleDateString(locale)
                  : '-'}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Has pending verification
  if (status?.has_verification && status.status === 'pendiente') {
    return (
      <Card className="border-yellow-200">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-yellow-600" />
            {t('pendingTitle')}
          </CardTitle>
          <CardDescription>{t('pendingDescription')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <StatusBadge status={status.status} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">{t('matricula')}</p>
              <p className="font-medium">{status.matricula}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('submittedAt')}</p>
              <p className="font-medium">
                {status.submitted_at
                  ? new Date(status.submitted_at).toLocaleDateString(locale)
                  : '-'}
              </p>
            </div>
          </div>
          <Alert>
            <Clock className="h-4 w-4" />
            <AlertDescription>{status.message || t('pendingMessage')}</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    )
  }

  // Rejected - can submit again
  if (status?.has_verification && status.status === 'rechazado') {
    return (
      <Card className="border-red-200">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <XCircle className="h-5 w-5 text-red-600" />
            {t('rejectedTitle')}
          </CardTitle>
          <CardDescription>{t('rejectedDescription')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <StatusBadge status={status.status} />
          </div>
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>{t('rejectionReason')}</AlertTitle>
            <AlertDescription>{status.rejection_reason || t('noReasonProvided')}</AlertDescription>
          </Alert>
          <Button onClick={resetWizard} className="w-full">
            <RefreshCw className="mr-2 h-4 w-4" />
            {t('submitNewRequest')}
          </Button>
        </CardContent>
      </Card>
    )
  }

  // Wizard: Submitted - Success View
  if (wizardState.step === 'submitted' && wizardState.submit_result) {
    return (
      <SubmissionSuccessView
        submitResult={wizardState.submit_result}
        wizardState={wizardState}
        onBackToStatus={resetWizard}
      />
    )
  }

  // Wizard: Step 1 - Matricula
  if (wizardState.step === 'matricula') {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BadgeCheck className="h-5 w-5" />
            {t('verifyTitle')}
          </CardTitle>
          <CardDescription>{t('verifyDescription')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{t('verifyInstructions')}</AlertDescription>
          </Alert>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="matricula">{t('matriculaLabel')}</Label>
              <Input
                id="matricula"
                value={wizardState.matricula}
                onChange={(e) =>
                  setWizardState((prev) => ({ ...prev, matricula: e.target.value }))
                }
                placeholder={t('matriculaPlaceholder')}
              />
              <p className="text-sm text-muted-foreground">{t('matriculaHelp')}</p>
            </div>

            <Alert variant="default" className="bg-blue-50 border-blue-200">
              <Timer className="h-4 w-4 text-blue-600" />
              <AlertDescription className="text-blue-700">
                {t('sessionTimeoutWarning')}
              </AlertDescription>
            </Alert>

            <Button
              onClick={handleStartSession}
              disabled={!wizardState.matricula.trim() || isProcessing}
              className="w-full"
              size="lg"
            >
              {isProcessing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <ChevronRight className="mr-2 h-4 w-4" />
              )}
              {t('continueButton')}
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Wizard: Step 2 - DIP Upload
  if (wizardState.step === 'dip') {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t('uploadDipTitle')}</CardTitle>
              <CardDescription>{t('uploadDipDescription')}</CardDescription>
            </div>
            <SessionTimer expiresAt={wizardState.expires_at} />
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Badge variant="outline">{t('step')} 1/3</Badge>
            <span>{t('matricula')}: {wizardState.matricula}</span>
          </div>

          <DocumentUpload
            label={t('dipLabel')}
            description={t('dipDescription')}
            onFileSelect={handleDipUpload}
            isLoading={isProcessing}
            isUploaded={wizardState.documents.dip?.uploaded}
            fileName={wizardState.documents.dip?.file_name}
            confidence={wizardState.documents.dip?.confidence}
          />

          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={resetWizard}
              disabled={isProcessing}
            >
              <ChevronLeft className="mr-2 h-4 w-4" />
              {t('cancelButton')}
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Wizard: Step 3 - Proof Document Upload
  if (wizardState.step === 'proof') {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t('uploadProofTitle')}</CardTitle>
              <CardDescription>{t('uploadProofDescription')}</CardDescription>
            </div>
            <SessionTimer expiresAt={wizardState.expires_at} />
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Badge variant="outline">{t('step')} 2/3</Badge>
            <span>{t('matricula')}: {wizardState.matricula}</span>
          </div>

          <div className="space-y-3">
            <Label>{t('selectProofType')}</Label>
            <Select
              value={selectedProofType}
              onValueChange={(v) => setSelectedProofType(v as DocumentoTipoPrueba)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(DOCUMENTO_TIPO_LABELS).map(([key, labels]) => (
                  <SelectItem key={key} value={key}>
                    {labels[locale]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <DocumentUpload
            label={DOCUMENTO_TIPO_LABELS[selectedProofType][locale]}
            description={t('proofDescription')}
            onFileSelect={handleProofUpload}
            isLoading={isProcessing}
            isUploaded={wizardState.documents.proof?.uploaded}
            fileName={wizardState.documents.proof?.file_name}
            confidence={wizardState.documents.proof?.confidence}
          />

          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => setWizardState((prev) => ({ ...prev, step: 'dip' }))}
              disabled={isProcessing}
            >
              <ChevronLeft className="mr-2 h-4 w-4" />
              {t('backButton')}
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Wizard: Step 4 - Form Review
  if (wizardState.step === 'form_review') {
    const needsConfirmation = wizardState.submit_result?.requires_confirmation

    return (
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t('reviewTitle')}</CardTitle>
              <CardDescription>{t('reviewDescription')}</CardDescription>
            </div>
            <SessionTimer expiresAt={wizardState.expires_at} />
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Badge variant="outline">{t('step')} 3/3</Badge>
            <span>{t('matricula')}: {wizardState.matricula}</span>
          </div>

          {/* Documents summary */}
          <div className="space-y-3">
            <h4 className="font-medium">{t('uploadedDocuments')}</h4>
            <div className="space-y-2">
              {wizardState.documents.dip && (
                <div className="flex items-center gap-3 p-3 bg-green-50 border border-green-200 rounded-lg">
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                  <div className="flex-1">
                    <p className="font-medium">{t('dipLabel')}</p>
                    <p className="text-sm text-muted-foreground">
                      {wizardState.documents.dip.file_name}
                    </p>
                  </div>
                  <Badge variant="outline" className="text-green-600">
                    {Math.round((wizardState.documents.dip.confidence || 0) * 100)}%
                  </Badge>
                </div>
              )}
              {wizardState.documents.proof && (
                <div className="flex items-center gap-3 p-3 bg-green-50 border border-green-200 rounded-lg">
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                  <div className="flex-1">
                    <p className="font-medium">
                      {DOCUMENTO_TIPO_LABELS[wizardState.documents.proof.tipo][locale]}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {wizardState.documents.proof.file_name}
                    </p>
                  </div>
                  <Badge variant="outline" className="text-green-600">
                    {Math.round((wizardState.documents.proof.confidence || 0) * 100)}%
                  </Badge>
                </div>
              )}
            </div>
          </div>

          {/* Cross-validation results */}
          <CrossValidationDisplay validation={wizardState.validacion_cruzada} />

          {/* Warnings requiring confirmation */}
          {needsConfirmation && wizardState.submit_result?.warnings && (
            <Alert variant="default" className="border-yellow-300 bg-yellow-50">
              <AlertTriangle className="h-4 w-4 text-yellow-600" />
              <AlertTitle className="text-yellow-700">{t('confirmRequired')}</AlertTitle>
              <AlertDescription className="text-yellow-600">
                <ul className="mt-2 space-y-1">
                  {wizardState.submit_result.warnings.map((warning, index) => (
                    <li key={index}>• {warning.message}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}

          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => setWizardState((prev) => ({ ...prev, step: 'proof', submit_result: null }))}
              disabled={isProcessing}
            >
              <ChevronLeft className="mr-2 h-4 w-4" />
              {t('backButton')}
            </Button>
            <Button
              onClick={() => handleSubmit(needsConfirmation)}
              disabled={isProcessing}
              className="flex-1"
              variant={needsConfirmation ? 'destructive' : 'default'}
            >
              {isProcessing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Send className="mr-2 h-4 w-4" />
              )}
              {needsConfirmation ? t('confirmAndSubmit') : t('submitButton')}
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Default: Start new verification
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BadgeCheck className="h-5 w-5" />
          {t('verifyTitle')}
        </CardTitle>
        <CardDescription>{t('verifyDescription')}</CardDescription>
      </CardHeader>
      <CardContent>
        <Button onClick={() => setWizardState((prev) => ({ ...prev, step: 'matricula' }))}>
          {t('startVerification')}
        </Button>
      </CardContent>
    </Card>
  )
}
