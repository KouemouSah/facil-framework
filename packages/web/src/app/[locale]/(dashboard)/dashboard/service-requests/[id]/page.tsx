'use client'

/**
 * Service Request Detail Page - Citizen View (Mi Solicitud)
 *
 * 100% dynamic — works for ALL workflows (no passport-specific code).
 * Data comes from a single endpoint: GET /service-requests/{id}/detail-view
 *
 * Features:
 * - Universal progress stepper (adapts to any workflow's steps)
 * - Dynamic data sections (same as PDF, from workflow form configs)
 * - Citizen notifications panel (agent actions, status changes)
 * - Payment & appointment cards
 * - Document list with upload capability
 *
 * BEHAVIOR:
 * - DRAFT status → Auto-redirect to wizard
 * - Other statuses → Read-only consultation with notifications
 */

import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  ArrowLeft,
  ArrowRight,
  FileText,
  CheckCircle,
  AlertCircle,
  XCircle,
  CreditCard,
  Upload,
  Eye,
  Loader2,
  CalendarCheck,
  RefreshCw,
  Download,
  Clock,
  Building2,
} from 'lucide-react'
import { useDetailView } from '@/modules/service-requests/hooks/useWorkflowQueries'
import { useWorkflowTranslations, workflowNameKey } from '@/hooks/use-workflow-translations'
import { UniversalProgressStepper } from '@/modules/service-requests/components/UniversalProgressStepper'
import { DynamicDataSections } from '@/modules/service-requests/components/DynamicDataSections'
// CitizenNotificationsPanel removed — notifications moved to dedicated /notifications page
import { CitizenDocumentPreview } from '@/modules/service-requests/components/CitizenDocumentPreview'
import { serviceRequestsApi } from '@/modules/service-requests/services/api'
import type { DetailViewDocumentInfo } from '@/modules/service-requests/types'

// Status configuration for visual styling (messages use translation keys)
const STATUS_CONFIG: Record<string, { color: string; icon: React.ElementType; messageKey: string }> = {
  DRAFT: { color: 'bg-slate-500', icon: FileText, messageKey: 'status_messages.draft' },
  TIMBRES_PENDING: { color: 'bg-amber-500', icon: CreditCard, messageKey: 'status_messages.timbres_pending' },
  TIMBRES_PAID: { color: 'bg-amber-600', icon: CheckCircle, messageKey: 'status_messages.timbres_paid' },
  SUBMITTED: { color: 'bg-blue-500', icon: Clock, messageKey: 'status_messages.submitted' },
  DOCUMENTS_REQUIRED: { color: 'bg-orange-500', icon: AlertCircle, messageKey: 'status_messages.documents_required' },
  UNDER_REVIEW: { color: 'bg-indigo-500', icon: Eye, messageKey: 'status_messages.under_review' },
  DOSSIER_VALIDE: { color: 'bg-teal-500', icon: CheckCircle, messageKey: 'status_messages.dossier_valide' },
  REJECTED: { color: 'bg-red-500', icon: XCircle, messageKey: 'status_messages.rejected' },
  PAYMENT_PENDING: { color: 'bg-yellow-500', icon: CreditCard, messageKey: 'status_messages.payment_pending' },
  PAYMENT_PROCESSING: { color: 'bg-yellow-600', icon: Loader2, messageKey: 'status_messages.payment_processing' },
  PAID: { color: 'bg-green-500', icon: CheckCircle, messageKey: 'status_messages.paid' },
  CITA_SCHEDULED: { color: 'bg-cyan-500', icon: CalendarCheck, messageKey: 'status_messages.cita_scheduled' },
  IN_PROGRESS: { color: 'bg-blue-600', icon: Clock, messageKey: 'status_messages.in_progress' },
  COMPLETED: { color: 'bg-green-600', icon: CheckCircle, messageKey: 'status_messages.completed' },
  CANCELLED: { color: 'bg-gray-500', icon: XCircle, messageKey: 'status_messages.cancelled' },
  EXPIRED: { color: 'bg-gray-600', icon: Clock, messageKey: 'status_messages.expired' },
}

export default function ServiceRequestDetailPage() {
  const params = useParams()
  const router = useRouter()
  const locale = params.locale as string
  const requestId = params.id as string
  const t = useTranslations('service_requests')

  // Detail view data (single API call)
  const { data: detailView, isLoading, error: queryError, refetch } = useDetailView(requestId)
  const { tw } = useWorkflowTranslations()

  // State
  const [activeTab, setActiveTab] = useState('overview')
  const [downloadingPdf, setDownloadingPdf] = useState(false)
  const [previewDoc, setPreviewDoc] = useState<DetailViewDocumentInfo | null>(null)

  // Handle PDF download
  const handleDownloadPdf = useCallback(async () => {
    setDownloadingPdf(true)
    try {
      const blob = await serviceRequestsApi.downloadSummaryPDF(requestId, locale)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `solicitud_${detailView?.request.requestNumber || requestId}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch {
      // Silent fail — PDF download is non-critical
    } finally {
      setDownloadingPdf(false)
    }
  }, [requestId, locale, detailView])

  // Auto-redirect DRAFT status to wizard
  useEffect(() => {
    if (detailView?.request && detailView.request.status === 'DRAFT') {
      router.replace(`/${locale}/dashboard/service-requests/${requestId}/wizard`)
    }
  }, [detailView, locale, requestId, router])

  // Get status config
  const getStatusConfig = (status: string) => {
    return STATUS_CONFIG[status] || STATUS_CONFIG.DRAFT
  }

  // Format date as DD/MM/YY - HHhMM
  const formatDate = (dateString?: string): string => {
    if (!dateString) return '-'
    const date = new Date(dateString)
    const day = date.getDate().toString().padStart(2, '0')
    const month = (date.getMonth() + 1).toString().padStart(2, '0')
    const year = date.getFullYear().toString().slice(-2)
    const hours = date.getHours().toString().padStart(2, '0')
    const minutes = date.getMinutes().toString().padStart(2, '0')
    return `${day}/${month}/${year} - ${hours}H${minutes}`
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">{t('loading')}</p>
        </div>
      </div>
    )
  }

  // Error state
  if (queryError) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => router.back()}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          {t('back')}
        </Button>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>
            {queryError instanceof Error ? queryError.message : 'Error loading request'}
          </AlertDescription>
        </Alert>
        <Button onClick={() => refetch()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          {t('retry')}
        </Button>
      </div>
    )
  }

  // No data
  if (!detailView) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => router.back()}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          {t('back')}
        </Button>
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>{t('no_requests_found')}</AlertTitle>
          <AlertDescription>
            {t('request_not_found_id', { id: requestId })}
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  const { request, stepper_phases, current_phase_index, data_sections, citizen_notifications, unread_notification_count, photo_url, appointment, payment_status, payment_reference, receipt_number, documents: requestDocuments } = detailView
  const statusConfig = getStatusConfig(request.status)
  const StatusIcon = statusConfig.icon
  // citizen_notifications available in detailView but displayed in /notifications page
  void citizen_notifications
  void unread_notification_count

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t('back')}
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              {request.requestNumber || `#${request.id.slice(0, 8)}`}
            </h1>
            <p className="text-muted-foreground">
              {tw(workflowNameKey(request.workflowCode), detailView.workflow_name_es)}
            </p>
          </div>
        </div>
        <Badge className={`${statusConfig.color} text-white flex items-center gap-1 px-3 py-1`}>
          <StatusIcon className="h-4 w-4" />
          {t(`status.${request.status.toLowerCase()}`) || request.status}
        </Badge>
      </div>

      {/* Status Alert */}
      <Alert
        className={
          request.status === 'REJECTED'
            ? 'border-red-500 bg-red-50'
            : request.status === 'COMPLETED'
              ? 'border-green-500 bg-green-50'
              : request.status === 'DOCUMENTS_REQUIRED'
                ? 'border-orange-500 bg-orange-50'
                : ''
        }
      >
        <StatusIcon className="h-4 w-4" />
        <AlertTitle>
          {t(`status.${request.status.toLowerCase()}`) || 'Estado de tu solicitud'}
        </AlertTitle>
        <AlertDescription>{t(statusConfig.messageKey)}</AlertDescription>
      </Alert>

      {/* Rejection reason / Notes */}
      {request.rejectionReason && (
        <Alert className="border-red-500 bg-red-50">
          <XCircle className="h-4 w-4 text-red-500" />
          <AlertTitle>{locale === 'es' ? 'Motivo del rechazo' : locale === 'fr' ? 'Motif du rejet' : 'Rejection reason'}</AlertTitle>
          <AlertDescription>{request.rejectionReason}</AlertDescription>
        </Alert>
      )}
      {request.notes && !request.rejectionReason && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>{locale === 'es' ? 'Nota del agente' : locale === 'fr' ? 'Note de l\'agent' : 'Agent note'}</AlertTitle>
          <AlertDescription>{request.notes}</AlertDescription>
        </Alert>
      )}

      {/* Universal Progress Stepper */}
      {stepper_phases.length > 0 && (
        <Card className="p-4">
          <UniversalProgressStepper
            phases={stepper_phases}
            currentIndex={current_phase_index}
            status={request.status}
            locale={locale}
          />
        </Card>
      )}

      {/* Continue Wizard Button for DOCUMENTS_REQUIRED */}
      {request.status === 'DOCUMENTS_REQUIRED' && (
        <Alert className="border-primary/50 bg-primary/5">
          <FileText className="h-4 w-4 text-primary" />
          <AlertTitle className="text-primary">
            {locale === 'es' ? 'Documentos Requeridos' : locale === 'fr' ? 'Documents Requis' : 'Documents Required'}
          </AlertTitle>
          <AlertDescription className="flex items-center justify-between">
            <span>
              {locale === 'es'
                ? 'Se requieren documentos adicionales para continuar.'
                : locale === 'fr'
                  ? 'Des documents supplémentaires sont requis pour continuer.'
                  : 'Additional documents are required to continue.'}
            </span>
            <Button size="sm" asChild>
              <Link href={`/${locale}/dashboard/service-requests/${requestId}/wizard`}>
                {locale === 'es' ? 'Continuar' : locale === 'fr' ? 'Continuer' : 'Continue'}
              </Link>
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* Main Content: Split layout when notifications exist (desktop) */}
      <div className="grid gap-6">
        {/* Left Column: Tabs */}
        <div>
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
            <TabsList>
              <TabsTrigger value="overview">{t('overview')}</TabsTrigger>
              <TabsTrigger value="documents">{t('documents_tab')}</TabsTrigger>
            </TabsList>

            {/* Overview Tab */}
            <TabsContent value="overview" className="space-y-4">
              {/* Request Info Card */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5" />
                    {t('overview') || 'Información General'}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <p className="text-sm text-muted-foreground">{t('request_number') || 'Referencia'}</p>
                      <p className="font-mono font-medium">
                        {request.requestNumber || request.id.slice(0, 8)}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">{t('sub_type') || 'Tipo'}</p>
                      <p className="font-medium">{detailView.solicitud_type_display || '-'}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">{t('created') || 'Creado'}</p>
                      <p className="font-medium">{formatDate(request.createdAt)}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">{t('table.updated') || 'Actualizado'}</p>
                      <p className="font-medium">{formatDate(request.updatedAt)}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Bundle Details — conditional for BUNDLE_PAYMENT */}
              {detailView.bundle_details && (() => {
                const bd = detailView.bundle_details
                const fmtXAF = (n: number) => new Intl.NumberFormat(locale === 'fr' ? 'fr-FR' : locale === 'en' ? 'en-US' : 'es-GQ', { maximumFractionDigits: 0 }).format(n) + ' XAF'
                const paidObls = bd.obligations?.filter(o => ['completed', 'paid', 'processing'].includes(o.status)) || []
                const pendingObls = bd.obligations?.filter(o => !['completed', 'paid', 'processing'].includes(o.status)) || []
                const paidTotal = paidObls.reduce((s, o) => s + o.amount, 0)
                const remainingTotal = (bd.total_amount || 0) - paidTotal
                const FEE_COLORS: Record<string, string> = { tesoro: 'bg-blue-100 text-blue-800', municipal: 'bg-amber-100 text-amber-800', chamber: 'bg-indigo-100 text-indigo-800' }

                return (
                  <Card>
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <CardTitle className="flex items-center gap-2 text-base">
                          <Building2 className="h-5 w-5" />
                          {bd.company_name || 'Paquete Fiscal'}
                          {bd.registration_number && (
                            <span className="text-sm font-normal text-muted-foreground">RC: {bd.registration_number}</span>
                          )}
                        </CardTitle>
                        {bd.certificate_url && (
                          <Button variant="outline" size="sm" className="h-7 text-xs gap-1" asChild>
                            <a href={bd.certificate_url} target="_blank" rel="noopener noreferrer">
                              <Download className="h-3 w-3" />
                              {locale === 'fr' ? 'Telecharger Licence' : locale === 'en' ? 'Download License' : 'Descargar Licencia'}
                            </a>
                          </Button>
                        )}
                      </div>
                      {bd.certificate_number && (
                        <CardDescription className="font-mono text-xs">{bd.certificate_number}</CardDescription>
                      )}
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {/* KPI: Total / Paid / Remaining */}
                      <div className="grid grid-cols-3 gap-3">
                        <div className="text-center p-2 rounded-lg bg-muted/50">
                          <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Total</p>
                          <p className="font-bold text-sm">{fmtXAF(bd.total_amount || 0)}</p>
                        </div>
                        <div className="text-center p-2 rounded-lg bg-green-50">
                          <p className="text-[10px] text-green-700 uppercase tracking-wider">
                            {locale === 'fr' ? 'Paye' : locale === 'en' ? 'Paid' : 'Pagado'}
                          </p>
                          <p className="font-bold text-sm text-green-700">{fmtXAF(paidTotal)}</p>
                        </div>
                        <div className="text-center p-2 rounded-lg bg-red-50">
                          <p className="text-[10px] text-red-700 uppercase tracking-wider">
                            {locale === 'fr' ? 'Restant' : locale === 'en' ? 'Remaining' : 'Restante'}
                          </p>
                          <p className="font-bold text-sm text-red-700">{fmtXAF(remainingTotal)}</p>
                        </div>
                      </div>

                      {/* Payment splits by entity */}
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        {bd.splits?.map((split: any, idx: number) => (
                          <div key={idx} className="p-3 rounded-lg border">
                            <p className="text-xs text-muted-foreground">{split.entity_name || split.entity_code}</p>
                            <p className="text-lg font-bold">{fmtXAF(split.amount)}</p>
                            <Badge className={split.status === 'completed' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}>
                              {split.status === 'completed' ? (
                                <><CheckCircle className="h-3 w-3 mr-1" />{t('status.paid') || 'Validado'}</>
                              ) : (
                                <><Clock className="h-3 w-3 mr-1" />{t('status.payment_processing') || 'En proceso'}</>
                              )}
                            </Badge>
                            {split.receipt_number && (
                              <p className="text-[10px] text-muted-foreground mt-1">{split.receipt_number}</p>
                            )}
                          </div>
                        ))}
                      </div>

                      {/* Obligations — paid */}
                      {paidObls.length > 0 && (
                        <div>
                          <p className="text-sm font-medium flex items-center gap-1 mb-2 text-green-700">
                            <CheckCircle className="h-4 w-4" />
                            {paidObls.length} {locale === 'fr' ? 'obligations payees' : locale === 'en' ? 'paid obligations' : 'obligaciones pagadas'}
                          </p>
                          <div className="space-y-1">
                            {paidObls.map((obl: any, idx: number) => (
                              <div key={idx} className="flex items-center justify-between text-sm py-1.5 px-2 rounded bg-green-50/50">
                                <div className="flex items-center gap-2 min-w-0">
                                  <CheckCircle className="h-3 w-3 text-green-500 shrink-0" />
                                  <span className="truncate">{obl.service_name}</span>
                                  <Badge className={`text-[9px] h-4 ${FEE_COLORS[obl.fee_type] || 'bg-gray-100 text-gray-700'}`}>{obl.fee_type?.toUpperCase()}</Badge>
                                </div>
                                <span className="font-mono text-xs shrink-0 ml-2">{fmtXAF(obl.amount)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Obligations — pending */}
                      {pendingObls.length > 0 && (
                        <div>
                          <p className="text-sm font-medium flex items-center gap-1 mb-2 text-amber-700">
                            <Clock className="h-4 w-4" />
                            {pendingObls.length} {locale === 'fr' ? 'obligations en attente' : locale === 'en' ? 'pending obligations' : 'obligaciones pendientes'}
                          </p>
                          <div className="space-y-1">
                            {pendingObls.map((obl: any, idx: number) => (
                              <div key={idx} className="flex items-center justify-between text-sm py-1.5 px-2 rounded bg-amber-50/50">
                                <div className="flex items-center gap-2 min-w-0">
                                  <CreditCard className="h-3 w-3 text-amber-500 shrink-0" />
                                  <span className="truncate text-muted-foreground">{obl.service_name}</span>
                                  <Badge className={`text-[9px] h-4 ${FEE_COLORS[obl.fee_type] || 'bg-gray-100 text-gray-700'}`}>{obl.fee_type?.toUpperCase()}</Badge>
                                </div>
                                <span className="font-mono text-xs shrink-0 ml-2">{fmtXAF(obl.amount)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )
              })()}

              {/* Dynamic Data Sections with highlight blocks (Pago/Cita/Anterior) */}
              {data_sections.length > 0 && (
                <DynamicDataSections
                  sections={data_sections}
                  photoUrl={photo_url}
                  highlight={{
                    paymentStatus: payment_status,
                    paymentReference: payment_reference,
                    receiptNumber: receipt_number,
                    tariff: detailView.tariff,
                    appointment: appointment,
                  }}
                  locale={locale}
                />
              )}
            </TabsContent>

            {/* Documents Tab */}
            <TabsContent value="documents" className="space-y-4">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle>{t('documents_tab')}</CardTitle>
                    <CardDescription>
                      {requestDocuments.length} {t('documents_uploaded')}
                    </CardDescription>
                  </div>
                  {['DRAFT', 'DOCUMENTS_REQUIRED'].includes(request.status) && (
                    <Button onClick={() => router.push(`/${locale}/dashboard/service-requests/${requestId}/wizard`)}>
                      <Upload className="mr-2 h-4 w-4" />
                      {t('upload')}
                    </Button>
                  )}
                </CardHeader>
                <CardContent>
                  {requestDocuments.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                      <p>{t('documents.no_documents')}</p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {requestDocuments.map((doc) => (
                        <div
                          key={doc.id}
                          className="flex items-center gap-3 p-3 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors"
                          onClick={() => doc.file_url && setPreviewDoc(doc)}
                        >
                          <div className="p-2 bg-muted rounded flex-shrink-0">
                            <FileText className="h-4 w-4" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm truncate">{doc.document_name}</p>
                            <p className="text-xs text-muted-foreground truncate">{doc.file_name}</p>
                          </div>
                          {doc.file_url && (
                            <div className="flex items-center gap-1 flex-shrink-0">
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setPreviewDoc(doc)
                                }}
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  const link = document.createElement('a')
                                  link.href = doc.file_url!
                                  link.download = doc.file_name || 'document'
                                  link.target = '_blank'
                                  document.body.appendChild(link)
                                  link.click()
                                  document.body.removeChild(link)
                                }}
                              >
                                <Download className="h-4 w-4" />
                              </Button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

      </div>

      {/* Bottom Actions */}
      <div className="flex justify-between">
        <Button variant="outline" asChild>
          <Link href={`/${locale}/dashboard/service-requests`}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t('back') || 'Volver a mis solicitudes'}
          </Link>
        </Button>
        <div className="flex gap-2">
          {/* Download PDF */}
          {!['DRAFT'].includes(request.status) && (
            <Button variant="outline" onClick={handleDownloadPdf} disabled={downloadingPdf}>
              {downloadingPdf ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Download className="mr-2 h-4 w-4" />
              )}
              PDF
            </Button>
          )}
          {/* Continue wizard */}
          {['DRAFT', 'DOCUMENTS_REQUIRED'].includes(request.status) && (
            <Button
              onClick={() => router.push(`/${locale}/dashboard/service-requests/${requestId}/wizard`)}
            >
              <ArrowRight className="mr-2 h-4 w-4" />
              {locale === 'es' ? 'Continuar Solicitud' : locale === 'fr' ? 'Continuer la Demande' : 'Continue Request'}
            </Button>
          )}
        </div>
      </div>

      {/* Document Preview Dialog */}
      <CitizenDocumentPreview
        document={previewDoc}
        open={!!previewDoc}
        onClose={() => setPreviewDoc(null)}
      />
    </div>
  )
}
