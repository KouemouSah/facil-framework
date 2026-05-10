'use client'

/**
 * Fiscal Service Detail Page
 * View complete service information with 6 tabs
 *
 * PHASE 8.3: Service Detail View - Enhanced with all fields
 * CRITICAL: 100% backend-aligned with fiscal_service_routes.py
 *
 * @module dashboard/admin/fiscal-services/[id]
 * @author Claude Code
 * @date 2025-12-08
 */

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  ArrowLeft,
  Edit,
  Trash2,
  RefreshCw,
  AlertTriangle,
  FileText,
  CheckCircle2,
  DollarSign,
  Info,
  BookOpen,
  Building,
  Settings,
  Clock,
  Link2,
  Check,
  X,
  Eye,
  EyeOff,
} from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import fiscalServicesAPI from '@/modules/fiscal-services/services/api'
import type {
  FiscalServiceResponse,
  ServiceStatusEnum,
  Ministry,
  Sector,
  Category,
  ServiceDocumentAssignment,
  ServiceProcedureAssignment,
} from '@/types/fiscal-service'
import { BackendUnavailableAlert } from '@/modules/admin/components'

export default function FiscalServiceDetailPage() {
  const params = useParams()
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('admin.fiscalServices')
  const { toast } = useToast()

  const serviceId = params.id as string

  const [service, setService] = useState<FiscalServiceResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isBackendUnavailable, setIsBackendUnavailable] = useState(false)

  // Hierarchy data
  const [ministries, setMinistries] = useState<Ministry[]>([])
  const [sectors, setSectors] = useState<Sector[]>([])
  const [categories, setCategories] = useState<Category[]>([])

  // Assignments data
  const [documentAssignments, setDocumentAssignments] = useState<ServiceDocumentAssignment[]>([])
  const [procedureAssignments, setProcedureAssignments] = useState<ServiceProcedureAssignment[]>([])
  const [isLoadingAssignments, setIsLoadingAssignments] = useState(false)

  const fetchAssignments = async () => {
    if (!serviceId) return
    setIsLoadingAssignments(true)
    try {
      const [docs, procs] = await Promise.all([
        fiscalServicesAPI.documents.list(serviceId),
        fiscalServicesAPI.procedures.list(serviceId),
      ])
      setDocumentAssignments(docs)
      setProcedureAssignments(procs)
    } catch (err) {
      console.error('Error fetching assignments:', err)
    } finally {
      setIsLoadingAssignments(false)
    }
  }

  const fetchHierarchy = async () => {
    try {
      const [ministriesData, sectorsData, categoriesData] = await Promise.all([
        fiscalServicesAPI.hierarchy.ministries.list(locale),
        fiscalServicesAPI.hierarchy.sectors.list(undefined, locale),
        fiscalServicesAPI.hierarchy.categories.list(undefined, locale),
      ])
      setMinistries(ministriesData)
      setSectors(sectorsData)
      setCategories(categoriesData)
    } catch (err) {
      console.error('Error fetching hierarchy:', err)
    }
  }

  const fetchService = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const data = await fiscalServicesAPI.services.get(serviceId)
      setService(data)
      setIsBackendUnavailable(false)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('errorLoading')
      setError(errorMessage)

      if (errorMessage.includes('fetch') || errorMessage.includes('Network') || errorMessage.includes('Failed')) {
        setIsBackendUnavailable(true)
      }

      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: t('errorLoadingServices'),
      })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchService()
    fetchHierarchy()
    fetchAssignments()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serviceId])

  // Get hierarchy names
  const getCategoryInfo = () => {
    const category = categories.find(c => c.id === service?.categoryId)
    if (!category) return { category: null, sector: null, ministry: null }

    const sectorId = category.sector_id || category.sectorId
    const sector = sectors.find(s => s.id === sectorId)

    const ministryId = sector?.ministry_id || sector?.ministryId
    const ministry = ministries.find(m => m.id === ministryId)

    return { category, sector, ministry }
  }

  const handleDelete = async () => {
    if (!service) return
    if (!confirm(t('confirmDelete', { name: service.nameEs }))) return

    try {
      await fiscalServicesAPI.admin.delete(service.id)
      toast({
        title: t('successTitle'),
        description: t('serviceDeleted'),
      })
      router.push(`/${locale}/dashboard/admin/fiscal-services`)
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: t('errorDeleting'),
      })
    }
  }

  const getStatusBadge = (status: ServiceStatusEnum) => {
    const statusConfig: Record<ServiceStatusEnum, { className: string; icon: typeof CheckCircle2 }> = {
      active: { className: 'bg-green-100 text-green-700', icon: CheckCircle2 },
      inactive: { className: 'bg-gray-100 text-gray-700', icon: AlertTriangle },
      draft: { className: 'bg-blue-100 text-blue-700', icon: FileText },
      deprecated: { className: 'bg-red-100 text-red-700', icon: AlertTriangle },
    }

    const config = statusConfig[status]
    const Icon = config.icon

    return (
      <Badge variant="outline" className={`${config.className} flex items-center gap-1`}>
        <Icon className="h-3 w-3" />
        {t(`status${status.charAt(0).toUpperCase() + status.slice(1)}` as Parameters<typeof t>[0])}
      </Badge>
    )
  }

  const formatCurrency = (amount: number | undefined | null) => {
    if (amount === undefined || amount === null) return '-'
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: 'XAF',
      minimumFractionDigits: 0,
    }).format(amount)
  }

  const formatDate = (dateString: string | undefined | null) => {
    if (!dateString) return '-'
    return new Date(dateString).toLocaleDateString(locale, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  }

  const formatPercent = (value: number | undefined | null) => {
    if (value === undefined || value === null) return '-'
    return `${value}%`
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-3 text-muted-foreground">{t('loading')}</span>
      </div>
    )
  }

  if (error || !service) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          {t('back')}
        </Button>
        {isBackendUnavailable && <BackendUnavailableAlert />}
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertTriangle className="h-12 w-12 text-red-500 mb-4" />
            <p className="text-lg font-medium">{t('errorLoading')}</p>
            <p className="text-muted-foreground">{error}</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  const { category, sector, ministry } = getCategoryInfo()

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            {t('back')}
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold tracking-tight">{service.nameEs}</h1>
              {getStatusBadge(service.status)}
            </div>
            <p className="text-muted-foreground mt-1">
              Code: <span className="font-mono">{service.serviceCode}</span>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={fetchService}>
            <RefreshCw className="h-4 w-4 mr-2" />
            {t('refresh')}
          </Button>
          <Button variant="outline" onClick={() => router.push(`/${locale}/dashboard/admin/fiscal-services/${service.id}/edit`)}>
            <Edit className="h-4 w-4 mr-2" />
            {t('edit')}
          </Button>
          <Button variant="destructive" onClick={handleDelete}>
            <Trash2 className="h-4 w-4 mr-2" />
            {t('delete')}
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="basic" className="w-full">
        <TabsList className="grid w-full grid-cols-7">
          <TabsTrigger value="basic">
            <Info className="h-4 w-4 mr-2" />
            {t('tabs.basic')}
          </TabsTrigger>
          <TabsTrigger value="hierarchy">
            <Building className="h-4 w-4 mr-2" />
            {t('tabs.hierarchy')}
          </TabsTrigger>
          <TabsTrigger value="calculation">
            <DollarSign className="h-4 w-4 mr-2" />
            {t('tabs.calculation')}
          </TabsTrigger>
          <TabsTrigger value="validity">
            <Clock className="h-4 w-4 mr-2" />
            {t('tabs.validity')}
          </TabsTrigger>
          <TabsTrigger value="legal">
            <BookOpen className="h-4 w-4 mr-2" />
            {t('tabs.legal')}
          </TabsTrigger>
          <TabsTrigger value="assignments">
            <Link2 className="h-4 w-4 mr-2" />
            {t('tabs.assignments')}
          </TabsTrigger>
          <TabsTrigger value="advanced">
            <Settings className="h-4 w-4 mr-2" />
            {t('tabs.advanced')}
          </TabsTrigger>
        </TabsList>

        {/* Basic Information Tab */}
        <TabsContent value="basic" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t('basicInfo')}</CardTitle>
              <CardDescription>{t('basicInfoDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">{t('serviceCode')}</label>
                  <p className="mt-1 font-mono text-lg">{service.serviceCode}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">{t('status')}</label>
                  <div className="mt-1">{getStatusBadge(service.status)}</div>
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-muted-foreground">{t('nameEs')}</label>
                <p className="mt-1 text-lg font-medium">{service.nameEs}</p>
              </div>

              {service.descriptionEs && (
                <div>
                  <div className="flex items-center gap-2">
                    <label className="text-sm font-medium text-muted-foreground">{t('descriptionEs')}</label>
                    {service.descriptionVisible === false ? (
                      <Badge variant="outline" className="text-xs bg-yellow-50 text-yellow-700">
                        <EyeOff className="h-3 w-3 mr-1" />{t('descriptionHidden')}
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-xs bg-green-50 text-green-700">
                        <Eye className="h-3 w-3 mr-1" />{t('descriptionPublic')}
                      </Badge>
                    )}
                    {service.descriptionSource && (
                      <Badge variant="outline" className="text-xs">
                        {service.descriptionSource === 'ai_generated' || service.descriptionSource === 'ai_draft'
                          ? t('descriptionSourceAI')
                          : t('descriptionSourceManual')}
                      </Badge>
                    )}
                  </div>
                  <p className="mt-1 text-sm whitespace-pre-wrap">{service.descriptionEs}</p>
                </div>
              )}

              <div className="grid grid-cols-2 gap-6 pt-4 border-t">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">{t('serviceType')}</label>
                  <p className="mt-1">{t(`type${service.serviceType.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join('')}` as Parameters<typeof t>[0])}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">{t('processingTimeDays')}</label>
                  <p className="mt-1">{service.processingTimeDays ? `${service.processingTimeDays} ${t('days')}` : '-'}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Hierarchy Tab */}
        <TabsContent value="hierarchy" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t('hierarchy')}</CardTitle>
              <CardDescription>{t('hierarchyDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 gap-6">
                <div className="p-4 border rounded-lg bg-muted/30">
                  <label className="text-sm font-medium text-muted-foreground">{t('ministry')}</label>
                  <p className="mt-1 text-lg font-medium">
                    {ministry ? (ministry.name_es || ministry.nameEs) : '-'}
                  </p>
                  {ministry && (ministry.ministry_code || ministry.ministryCode) && (
                    <p className="text-xs text-muted-foreground font-mono mt-1">
                      {ministry.ministry_code || ministry.ministryCode}
                    </p>
                  )}
                </div>

                <div className="p-4 border rounded-lg bg-muted/30">
                  <label className="text-sm font-medium text-muted-foreground">{t('sector')}</label>
                  <p className="mt-1 text-lg font-medium">
                    {sector ? (sector.name_es || sector.nameEs) : '-'}
                  </p>
                  {sector && (sector.sector_code || sector.sectorCode) && (
                    <p className="text-xs text-muted-foreground font-mono mt-1">
                      {sector.sector_code || sector.sectorCode}
                    </p>
                  )}
                </div>

                <div className="p-4 border rounded-lg bg-muted/30">
                  <label className="text-sm font-medium text-muted-foreground">{t('category')}</label>
                  <p className="mt-1 text-lg font-medium">
                    {service.categoryName || (category ? (category.name_es || category.nameEs) : `ID: ${service.categoryId}`)}
                  </p>
                  {category && (category.category_code || category.categoryCode) && (
                    <p className="text-xs text-muted-foreground font-mono mt-1">
                      {category.category_code || category.categoryCode}
                    </p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Calculation Tab */}
        <TabsContent value="calculation" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t('calculationDetails')}</CardTitle>
              <CardDescription>{t('calculationDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <label className="text-sm font-medium text-muted-foreground">{t('calculationMethod')}</label>
                <p className="mt-1 text-lg font-medium">
                  {t(`method${service.calculationMethod.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join('')}` as Parameters<typeof t>[0])}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-6 pt-4 border-t">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-muted-foreground">{t('tasaExpedicion')}</label>
                  <p className="text-2xl font-bold text-green-600">{formatCurrency(service.tasaExpedicion)}</p>
                  {service.expeditionFormula && (
                    <p className="text-xs text-muted-foreground">{t('formula')}: {service.expeditionFormula}</p>
                  )}
                  {service.expeditionUnitMeasure && (
                    <p className="text-xs text-muted-foreground">{t('unitMeasure')}: {service.expeditionUnitMeasure}</p>
                  )}
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-muted-foreground">{t('tasaRenovacion')}</label>
                  <p className="text-2xl font-bold text-blue-600">{formatCurrency(service.tasaRenovacion)}</p>
                  {service.renewalFormula && (
                    <p className="text-xs text-muted-foreground">{t('formula')}: {service.renewalFormula}</p>
                  )}
                  {service.renewalUnitMeasure && (
                    <p className="text-xs text-muted-foreground">{t('unitMeasure')}: {service.renewalUnitMeasure}</p>
                  )}
                </div>
              </div>

              {(service.basePercentage || service.unitRate) && (
                <div className="grid grid-cols-2 gap-6 pt-4 border-t">
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">{t('basePercentage')}</label>
                    <p className="mt-1 text-lg">{formatPercent(service.basePercentage)}</p>
                    {service.percentageOf && (
                      <p className="text-xs text-muted-foreground">{t('percentageOf')}: {service.percentageOf}</p>
                    )}
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">{t('unitRate')}</label>
                    <p className="mt-1 text-lg">{formatCurrency(service.unitRate)}</p>
                    {service.unitType && (
                      <p className="text-xs text-muted-foreground">{t('unitType')}: {service.unitType}</p>
                    )}
                  </div>
                </div>
              )}

              {service.rateTiers && service.rateTiers.length > 0 && (
                <div className="pt-4 border-t">
                  <label className="text-sm font-medium text-muted-foreground">{t('rateTiers')}</label>
                  <div className="mt-2 space-y-2">
                    {service.rateTiers.map((tier, index) => (
                      <div key={index} className="flex justify-between items-center p-2 bg-muted/50 rounded">
                        <span>
                          {formatCurrency(tier.minValue)} - {tier.maxValue ? formatCurrency(tier.maxValue) : '∞'}
                        </span>
                        <span className="font-medium">
                          {tier.fixedAmount ? formatCurrency(tier.fixedAmount) : `${tier.rate}%`}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Validity Tab */}
        <TabsContent value="validity" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t('validity')}</CardTitle>
              <CardDescription>{t('validityDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">{t('validityPeriodMonths')}</label>
                  <p className="mt-1 text-lg">
                    {service.validityPeriodMonths ? `${service.validityPeriodMonths} ${t('months')}` : '-'}
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">{t('renewalFrequencyMonths')}</label>
                  <p className="mt-1 text-lg">
                    {service.renewalFrequencyMonths ? `${service.renewalFrequencyMonths} ${t('months')}` : '-'}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-6 pt-4 border-t">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">{t('gracePeriodDays')}</label>
                  <p className="mt-1 text-lg">
                    {service.gracePeriodDays ? `${service.gracePeriodDays} ${t('days')}` : '-'}
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">{t('latePenaltyPercentage')}</label>
                  <p className="mt-1 text-lg">{formatPercent(service.latePenaltyPercentage)}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">{t('latePenaltyFixed')}</label>
                  <p className="mt-1 text-lg">{formatCurrency(service.latePenaltyFixed)}</p>
                </div>
              </div>

              {service.penaltyCalculationRules && Object.keys(service.penaltyCalculationRules).length > 0 && (
                <div className="pt-4 border-t">
                  <label className="text-sm font-medium text-muted-foreground">{t('penaltyCalculationRules')}</label>
                  <pre className="mt-2 p-3 bg-muted rounded text-xs overflow-auto">
                    {JSON.stringify(service.penaltyCalculationRules, null, 2)}
                  </pre>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Legal Tab */}
        <TabsContent value="legal" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t('legalInfo')}</CardTitle>
              <CardDescription>{t('legalDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <label className="text-sm font-medium text-muted-foreground">{t('legalReference')}</label>
                <p className="mt-1">{service.legalReference || '-'}</p>
              </div>

              {service.regulatoryArticles && service.regulatoryArticles.length > 0 && (
                <div className="pt-4 border-t">
                  <label className="text-sm font-medium text-muted-foreground">{t('regulatoryArticles')}</label>
                  <ul className="mt-2 list-disc list-inside space-y-1">
                    {service.regulatoryArticles.map((article, index) => (
                      <li key={index} className="text-sm">{article}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="grid grid-cols-2 gap-6 pt-4 border-t">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">{t('tariffEffectiveFrom')}</label>
                  <p className="mt-1">{formatDate(service.tariffEffectiveFrom)}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">{t('tariffEffectiveTo')}</label>
                  <p className="mt-1">{formatDate(service.tariffEffectiveTo)}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Assignments Tab */}
        <TabsContent value="assignments" className="space-y-6">
          {isLoadingAssignments ? (
            <div className="flex items-center justify-center h-32">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
              <span className="ml-2 text-muted-foreground">{t('loading')}</span>
            </div>
          ) : (
            <>
              {/* Document Assignments */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5" />
                    {t('assignedDocuments')}
                    <Badge variant="secondary" className="ml-2">{documentAssignments.length}</Badge>
                  </CardTitle>
                  <CardDescription>{t('assignedDocumentsDescription')}</CardDescription>
                </CardHeader>
                <CardContent>
                  {documentAssignments.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      <FileText className="h-12 w-12 mx-auto mb-3 opacity-30" />
                      <p>{t('noAssignedDocuments')}</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {documentAssignments.map((doc) => (
                        <div
                          key={doc.id}
                          className="flex items-center justify-between p-4 border rounded-lg bg-muted/30"
                        >
                          <div className="flex-1">
                            <p className="font-medium">{doc.documentName || `Document #${doc.documentTemplateId}`}</p>
                            {doc.customNotes && (
                              <p className="text-sm text-muted-foreground mt-1">{doc.customNotes}</p>
                            )}
                          </div>
                          <div className="flex items-center gap-4">
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground">{t('requiredForExpedition')}:</span>
                              {doc.isRequiredExpedition ? (
                                <Check className="h-4 w-4 text-green-600" />
                              ) : (
                                <X className="h-4 w-4 text-red-500" />
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground">{t('requiredForRenewal')}:</span>
                              {doc.isRequiredRenewal ? (
                                <Check className="h-4 w-4 text-green-600" />
                              ) : (
                                <X className="h-4 w-4 text-red-500" />
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Procedure Assignments */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BookOpen className="h-5 w-5" />
                    {t('assignedProcedures')}
                    <Badge variant="secondary" className="ml-2">{procedureAssignments.length}</Badge>
                  </CardTitle>
                  <CardDescription>{t('assignedProceduresDescription')}</CardDescription>
                </CardHeader>
                <CardContent>
                  {procedureAssignments.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      <BookOpen className="h-12 w-12 mx-auto mb-3 opacity-30" />
                      <p>{t('noAssignedProcedures')}</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {procedureAssignments.map((proc) => (
                        <div
                          key={proc.id}
                          className="flex items-center justify-between p-4 border rounded-lg bg-muted/30"
                        >
                          <div className="flex-1">
                            <p className="font-medium">{proc.procedureName || `Procedure #${proc.templateId}`}</p>
                            {proc.customNotes && (
                              <p className="text-sm text-muted-foreground mt-1">{proc.customNotes}</p>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-muted-foreground">{t('appliesTo')}:</span>
                            <Badge variant="outline">
                              {proc.appliesTo === 'expedition' ? t('expedition') :
                               proc.appliesTo === 'renewal' ? t('renewal') :
                               proc.appliesTo === 'both' ? t('both') :
                               proc.appliesTo || '-'}
                            </Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        {/* Advanced Tab */}
        <TabsContent value="advanced" className="space-y-6">
          {/* Statistics */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">{t('viewCount')}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{service.viewCount}</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">{t('calculationCount')}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{service.calculationCount}</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">{t('paymentCount')}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{service.paymentCount}</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">{t('favoriteCount')}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{service.favoriteCount}</div>
              </CardContent>
            </Card>
          </div>

          {/* Advanced Settings */}
          <Card>
            <CardHeader>
              <CardTitle>{t('advancedSettings')}</CardTitle>
              <CardDescription>{t('advancedDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-3 gap-6">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">{t('priority')}</label>
                  <p className="mt-1">{service.priority ?? '-'}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">{t('complexityLevel')}</label>
                  <p className="mt-1">{service.complexityLevel ?? '-'}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">{t('parentServiceId')}</label>
                  <p className="mt-1">{service.parentServiceId ?? '-'}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-6 pt-4 border-t">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">{t('tierGroupName')}</label>
                  <p className="mt-1">{service.tierGroupName || '-'}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">{t('isTierComponent')}</label>
                  <p className="mt-1">
                    {service.isTierComponent === true ? t('yes') : service.isTierComponent === false ? t('no') : '-'}
                  </p>
                </div>
              </div>

              {service.calculationConfig && Object.keys(service.calculationConfig).length > 0 && (
                <div className="pt-4 border-t">
                  <label className="text-sm font-medium text-muted-foreground">{t('calculationConfig')}</label>
                  <pre className="mt-2 p-3 bg-muted rounded text-xs overflow-auto">
                    {JSON.stringify(service.calculationConfig, null, 2)}
                  </pre>
                </div>
              )}

              {service.eligibilityCriteria && Object.keys(service.eligibilityCriteria).length > 0 && (
                <div className="pt-4 border-t">
                  <label className="text-sm font-medium text-muted-foreground">{t('eligibilityCriteria')}</label>
                  <pre className="mt-2 p-3 bg-muted rounded text-xs overflow-auto">
                    {JSON.stringify(service.eligibilityCriteria, null, 2)}
                  </pre>
                </div>
              )}

              {service.exemptionConditions && service.exemptionConditions.length > 0 && (
                <div className="pt-4 border-t">
                  <label className="text-sm font-medium text-muted-foreground">{t('exemptionConditions')}</label>
                  <ul className="mt-2 list-disc list-inside space-y-1">
                    {service.exemptionConditions.map((condition, index) => (
                      <li key={index} className="text-sm">
                        {typeof condition === 'string' ? condition : JSON.stringify(condition)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Metadata */}
          <Card>
            <CardHeader>
              <CardTitle>{t('metadata')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">{t('createdAt')}</label>
                  <p className="mt-1">{formatDate(service.createdAt)}</p>
                  {service.createdBy && (
                    <p className="text-xs text-muted-foreground">{t('by')}: {service.createdBy}</p>
                  )}
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">{t('updatedAt')}</label>
                  <p className="mt-1">{formatDate(service.updatedAt)}</p>
                  {service.updatedBy && (
                    <p className="text-xs text-muted-foreground">{t('by')}: {service.updatedBy}</p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
