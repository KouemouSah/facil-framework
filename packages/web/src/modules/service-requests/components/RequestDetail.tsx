'use client'

/**
 * RequestDetail Component
 * Detailed view of a service request for agents with actions
 */

import { useEffect, useState, useCallback } from 'react'
import { useTranslations } from 'next-intl'
import {
  ArrowLeft,
  CheckCircle,
  XCircle,
  MessageSquare,
  Calendar,
  User,
  FileText,
  AlertCircle,
  Eye,
  Loader2,
  Send,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

import { useServiceRequests } from '../hooks/useServiceRequests'
import { ExtractionPreview } from './ExtractionPreview'
import type { ServiceRequest, ServiceRequestDocument, ValidationResult } from '../types'
import { getStatusColor, getStatusLabel, ServiceRequestStatus } from '../types'

// ============================================================================
// TYPES
// ============================================================================

interface RequestDetailProps {
  requestId: string
  locale?: 'es' | 'fr' | 'en'
  onBack?: () => void
  onApproved?: (request: ServiceRequest) => void
  onRejected?: (request: ServiceRequest) => void
}

// ============================================================================
// DOCUMENT CARD
// ============================================================================

interface DocumentCardProps {
  document: ServiceRequestDocument
  locale: 'es' | 'fr' | 'en'
  onView: () => void
}

function DocumentCard({ document, locale: _locale, onView }: DocumentCardProps) {
  const isImage = document.mimeType.startsWith('image/')

  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow"
      onClick={onView}
    >
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0">
            {isImage && document.fileUrl ? (
              <img
                src={document.fileUrl}
                alt={document.fileName}
                className="w-16 h-20 object-cover rounded border"
              />
            ) : (
              <div className="w-16 h-20 bg-muted rounded border flex items-center justify-center">
                <FileText className="h-8 w-8 text-muted-foreground" />
              </div>
            )}
          </div>

          <div className="flex-1 min-w-0">
            <h4 className="font-medium text-sm truncate">{document.documentNameEs}</h4>
            <p className="text-xs text-muted-foreground truncate">{document.fileName}</p>

            <div className="flex items-center gap-2 mt-2">
              <Badge
                variant="outline"
                className={
                  document.extractionStatus === 'completed'
                    ? 'border-green-500 text-green-700'
                    : document.extractionStatus === 'failed'
                    ? 'border-red-500 text-red-700'
                    : 'border-yellow-500 text-yellow-700'
                }
              >
                {document.extractionStatus}
              </Badge>

              {document.extractionConfidence && (
                <span className="text-xs text-muted-foreground">
                  {Math.round(document.extractionConfidence * 100)}%
                </span>
              )}
            </div>
          </div>

          <Button variant="ghost" size="sm">
            <Eye className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

// ============================================================================
// VALIDATION RESULT ITEM
// ============================================================================

interface ValidationItemProps {
  result: ValidationResult
  locale: 'es' | 'fr' | 'en'
}

function ValidationItem({ result, locale: _locale }: ValidationItemProps) {
  const Icon = result.isValid
    ? CheckCircle
    : result.severity === 'error'
    ? AlertCircle
    : AlertCircle

  const colorClass = result.isValid
    ? 'text-green-600 bg-green-50'
    : result.severity === 'error'
    ? 'text-red-600 bg-red-50'
    : 'text-yellow-600 bg-yellow-50'

  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg ${colorClass}`}>
      <Icon className="h-5 w-5 flex-shrink-0 mt-0.5" />
      <div>
        <p className="text-sm font-medium">
          {result.messageEs}
        </p>
        {result.field && (
          <p className="text-xs opacity-75 mt-1">Campo: {result.field}</p>
        )}
      </div>
    </div>
  )
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export function RequestDetail({
  requestId,
  locale = 'es',
  onBack,
  onApproved,
  onRejected,
}: RequestDetailProps) {
  const t = useTranslations('service_requests')

  // State
  const [selectedDocument, setSelectedDocument] = useState<ServiceRequestDocument | null>(null)
  const [showApproveDialog, setShowApproveDialog] = useState(false)
  const [showRejectDialog, setShowRejectDialog] = useState(false)
  const [showInfoDialog, setShowInfoDialog] = useState(false)
  const [showAppointmentDialog, setShowAppointmentDialog] = useState(false)
  const [actionNotes, setActionNotes] = useState('')
  const [rejectReason, setRejectReason] = useState('')
  const [infoMessage, setInfoMessage] = useState('')
  const [appointmentDate, setAppointmentDate] = useState('')
  const [appointmentTime, setAppointmentTime] = useState('')
  const [appointmentLocation, setAppointmentLocation] = useState('')

  const {
    currentRequest,
    workflow,
    documents,
    validationResults,
    isLoading,
    isSaving,
    error,
    loadRequest,
    validateDocuments,
    approveRequest,
    rejectRequest,
    requestAdditionalInfo,
    scheduleAppointment,
  } = useServiceRequests()

  // Load request on mount
  useEffect(() => {
    loadRequest(requestId)
  }, [requestId, loadRequest])

  // Run validation on documents load
  useEffect(() => {
    if (documents.length > 0) {
      validateDocuments()
    }
  }, [documents, validateDocuments])

  // Handle approve
  const handleApprove = useCallback(async () => {
    const success = await approveRequest(actionNotes || undefined)
    if (success && currentRequest) {
      setShowApproveDialog(false)
      setActionNotes('')
      onApproved?.(currentRequest)
    }
  }, [approveRequest, actionNotes, currentRequest, onApproved])

  // Handle reject
  const handleReject = useCallback(async () => {
    if (!rejectReason) return
    const success = await rejectRequest(rejectReason, actionNotes || undefined)
    if (success && currentRequest) {
      setShowRejectDialog(false)
      setRejectReason('')
      setActionNotes('')
      onRejected?.(currentRequest)
    }
  }, [rejectRequest, rejectReason, actionNotes, currentRequest, onRejected])

  // Handle request info
  const handleRequestInfo = useCallback(async () => {
    if (!infoMessage) return
    const success = await requestAdditionalInfo(infoMessage)
    if (success) {
      setShowInfoDialog(false)
      setInfoMessage('')
    }
  }, [requestAdditionalInfo, infoMessage])

  // Handle schedule appointment
  const handleScheduleAppointment = useCallback(async () => {
    if (!appointmentDate || !appointmentTime || !appointmentLocation) return
    const success = await scheduleAppointment(appointmentDate, appointmentTime, appointmentLocation)
    if (success) {
      setShowAppointmentDialog(false)
      setAppointmentDate('')
      setAppointmentTime('')
      setAppointmentLocation('')
    }
  }, [scheduleAppointment, appointmentDate, appointmentTime, appointmentLocation])

  // Loading state
  if (isLoading && !currentRequest) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  // Error state
  if (error && !currentRequest) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  if (!currentRequest) {
    return null
  }

  const canApprove = [ServiceRequestStatus.UNDER_REVIEW, ServiceRequestStatus.SUBMITTED].includes(currentRequest.status as ServiceRequestStatus)
  const canReject = [ServiceRequestStatus.UNDER_REVIEW, ServiceRequestStatus.SUBMITTED].includes(currentRequest.status as ServiceRequestStatus)
  const canRequestInfo = [ServiceRequestStatus.UNDER_REVIEW, ServiceRequestStatus.SUBMITTED].includes(currentRequest.status as ServiceRequestStatus)
  const canSchedule = currentRequest.status === ServiceRequestStatus.DOSSIER_VALIDE

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {onBack && (
            <Button variant="ghost" size="sm" onClick={onBack}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              {t('back')}
            </Button>
          )}

          <div>
            <h1 className="text-2xl font-bold">{currentRequest.requestNumber}</h1>
            <p className="text-muted-foreground">
              {workflow?.serviceNameEs || currentRequest.workflowCode}
            </p>
          </div>
        </div>

        <Badge className={`text-lg px-4 py-1 ${getStatusColor(currentRequest.status)}`}>
          {getStatusLabel(currentRequest.status as ServiceRequestStatus, locale)}
        </Badge>
      </div>

      {/* Action Buttons */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-2">
            {canApprove && (
              <Button onClick={() => setShowApproveDialog(true)} className="bg-green-600 hover:bg-green-700">
                <CheckCircle className="h-4 w-4 mr-2" />
                {t('approve')}
              </Button>
            )}

            {canReject && (
              <Button onClick={() => setShowRejectDialog(true)} variant="destructive">
                <XCircle className="h-4 w-4 mr-2" />
                {t('reject')}
              </Button>
            )}

            {canRequestInfo && (
              <Button onClick={() => setShowInfoDialog(true)} variant="outline">
                <MessageSquare className="h-4 w-4 mr-2" />
                {t('request_info')}
              </Button>
            )}

            {canSchedule && (
              <Button onClick={() => setShowAppointmentDialog(true)} variant="outline">
                <Calendar className="h-4 w-4 mr-2" />
                {t('schedule_appointment')}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Content Tabs */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">{t('overview')}</TabsTrigger>
          <TabsTrigger value="documents">
            {t('documents')} ({documents.length})
          </TabsTrigger>
          <TabsTrigger value="validation">{t('validation')}</TabsTrigger>
          <TabsTrigger value="history">{t('history')}</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid md:grid-cols-2 gap-4">
            {/* Applicant Info */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <User className="h-5 w-5" />
                  {t('applicant')}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('name')}</span>
                  <span className="font-medium">{currentRequest.userName || 'N/A'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('email')}</span>
                  <span className="font-medium">{currentRequest.userEmail || 'N/A'}</span>
                </div>
              </CardContent>
            </Card>

            {/* Request Info */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  {t('request_info')}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('workflow')}</span>
                  <span className="font-medium">{currentRequest.workflowCode}</span>
                </div>
                {currentRequest.subType && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">{t('sub_type')}</span>
                    <span className="font-medium">{currentRequest.subType}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('created')}</span>
                  <span className="font-medium">
                    {new Date(currentRequest.createdAt).toLocaleString(locale)}
                  </span>
                </div>
                {currentRequest.tariffAmount && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">{t('tariff')}</span>
                    <span className="font-medium">
                      {currentRequest.tariffAmount.toLocaleString()} XAF
                    </span>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Form Data Preview */}
          {currentRequest.formData && Object.keys(currentRequest.formData).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">{t('form_data')}</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="text-sm bg-muted p-4 rounded overflow-auto max-h-60">
                  {JSON.stringify(currentRequest.formData, null, 2)}
                </pre>
              </CardContent>
            </Card>
          )}

          {/* Agent Notes */}
          {currentRequest.agentNotes && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">{t('agent_notes')}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm">{currentRequest.agentNotes}</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Documents Tab */}
        <TabsContent value="documents" className="space-y-4">
          {documents.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                {t('no_documents')}
              </CardContent>
            </Card>
          ) : (
            <div className="grid md:grid-cols-2 gap-4">
              {documents.map((doc) => (
                <DocumentCard
                  key={doc.id}
                  document={doc}
                  locale={locale}
                  onView={() => setSelectedDocument(doc)}
                />
              ))}
            </div>
          )}

          {/* Document Detail Dialog */}
          <Dialog open={!!selectedDocument} onOpenChange={() => setSelectedDocument(null)}>
            <DialogContent className="max-w-4xl max-h-[90vh] overflow-auto">
              {selectedDocument && (
                <>
                  <DialogHeader>
                    <DialogTitle>{selectedDocument.documentNameEs}</DialogTitle>
                    <DialogDescription>{selectedDocument.fileName}</DialogDescription>
                  </DialogHeader>

                  <div className="space-y-4">
                    {/* Document Preview */}
                    {selectedDocument.mimeType.startsWith('image/') && selectedDocument.fileUrl && (
                      <img
                        src={selectedDocument.fileUrl}
                        alt={selectedDocument.fileName}
                        className="w-full h-auto rounded border"
                      />
                    )}

                    {/* Extracted Data */}
                    <ExtractionPreview
                      document={selectedDocument}
                      locale={locale}
                      showRawData
                    />
                  </div>
                </>
              )}
            </DialogContent>
          </Dialog>
        </TabsContent>

        {/* Validation Tab */}
        <TabsContent value="validation" className="space-y-4">
          {validationResults.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                {t('no_validation_results')}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-4 space-y-2">
                {validationResults.map((result, index) => (
                  <ValidationItem key={index} result={result} locale={locale} />
                ))}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history">
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              {t('history_coming_soon')}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Approve Dialog */}
      <Dialog open={showApproveDialog} onOpenChange={setShowApproveDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('approve_request')}</DialogTitle>
            <DialogDescription>{t('approve_confirm_message')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label>{t('notes_optional')}</Label>
              <Textarea
                value={actionNotes}
                onChange={(e) => setActionNotes(e.target.value)}
                placeholder={t('notes_placeholder')}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowApproveDialog(false)}>
              {t('cancel')}
            </Button>
            <Button onClick={handleApprove} disabled={isSaving} className="bg-green-600 hover:bg-green-700">
              {isSaving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {t('confirm_approve')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reject Dialog */}
      <Dialog open={showRejectDialog} onOpenChange={setShowRejectDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('reject_request')}</DialogTitle>
            <DialogDescription>{t('reject_confirm_message')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label>{t('rejection_reason')}</Label>
              <Select value={rejectReason} onValueChange={setRejectReason}>
                <SelectTrigger>
                  <SelectValue placeholder={t('select_reason')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="invalid_documents">{t('reason.invalid_documents')}</SelectItem>
                  <SelectItem value="incomplete_data">{t('reason.incomplete_data')}</SelectItem>
                  <SelectItem value="identity_mismatch">{t('reason.identity_mismatch')}</SelectItem>
                  <SelectItem value="expired_documents">{t('reason.expired_documents')}</SelectItem>
                  <SelectItem value="other">{t('reason.other')}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label>{t('notes_optional')}</Label>
              <Textarea
                value={actionNotes}
                onChange={(e) => setActionNotes(e.target.value)}
                placeholder={t('notes_placeholder')}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRejectDialog(false)}>
              {t('cancel')}
            </Button>
            <Button onClick={handleReject} disabled={isSaving || !rejectReason} variant="destructive">
              {isSaving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {t('confirm_reject')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Request Info Dialog */}
      <Dialog open={showInfoDialog} onOpenChange={setShowInfoDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('request_additional_info')}</DialogTitle>
            <DialogDescription>{t('info_request_message')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label>{t('message_to_applicant')}</Label>
              <Textarea
                value={infoMessage}
                onChange={(e) => setInfoMessage(e.target.value)}
                placeholder={t('info_message_placeholder')}
                rows={4}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowInfoDialog(false)}>
              {t('cancel')}
            </Button>
            <Button onClick={handleRequestInfo} disabled={isSaving || !infoMessage}>
              {isSaving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              <Send className="h-4 w-4 mr-2" />
              {t('send_request')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Schedule Appointment Dialog */}
      <Dialog open={showAppointmentDialog} onOpenChange={setShowAppointmentDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('schedule_appointment')}</DialogTitle>
            <DialogDescription>{t('appointment_message')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label>{t('date')}</Label>
              <Input
                type="date"
                value={appointmentDate}
                onChange={(e) => setAppointmentDate(e.target.value)}
              />
            </div>

            <div>
              <Label>{t('time')}</Label>
              <Input
                type="time"
                value={appointmentTime}
                onChange={(e) => setAppointmentTime(e.target.value)}
              />
            </div>

            <div>
              <Label>{t('location')}</Label>
              <Input
                value={appointmentLocation}
                onChange={(e) => setAppointmentLocation(e.target.value)}
                placeholder={t('location_placeholder')}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAppointmentDialog(false)}>
              {t('cancel')}
            </Button>
            <Button
              onClick={handleScheduleAppointment}
              disabled={isSaving || !appointmentDate || !appointmentTime || !appointmentLocation}
            >
              {isSaving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              <Calendar className="h-4 w-4 mr-2" />
              {t('schedule')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default RequestDetail
