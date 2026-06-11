'use client'

/**
 * Fiscal Service Edit Form - Complete with All Fields and Tabs
 * Edit existing fiscal service with all database fields
 *
 * @module dashboard/admin/fiscal-services/[id]/edit
 * @author Claude Code
 * @date 2025-12-08
 */

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  ArrowLeft,
  Save,
  Loader2,
  RefreshCw,
  FileText,
  Building2,
  Calculator,
  Clock,
  BookOpen,
  Settings,
  Link2,
  Trash2,
  Check,
  X,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/hooks/use-toast'
import fiscalServicesAPI from '@/modules/fiscal-services/services/api'
import { SearchableTemplateTable } from '@/modules/fiscal-services/components'
import type {
  FiscalServiceResponse,
  FiscalServiceUpdate,
  Category,
  Ministry,
  Sector,
  ServiceTypeEnum,
  ServiceStatusEnum,
  CalculationMethodEnum,
  ServiceDocumentAssignment,
  ServiceProcedureAssignment,
  DocumentTemplate,
  ProcedureTemplate,
} from '@/types/fiscal-service'

export default function EditFiscalServicePage() {
  const params = useParams()
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('admin.fiscalServices')
  const { toast } = useToast()

  const serviceId = params.id as string

  const [service, setService] = useState<FiscalServiceResponse | null>(null)
  const [ministries, setMinistries] = useState<Ministry[]>([])
  const [sectors, setSectors] = useState<Sector[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [filteredSectors, setFilteredSectors] = useState<Sector[]>([])
  const [filteredCategories, setFilteredCategories] = useState<Category[]>([])
  const [selectedMinistry, setSelectedMinistry] = useState<number | null>(null)
  const [selectedSector, setSelectedSector] = useState<number | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const [formData, setFormData] = useState<FiscalServiceUpdate>({})

  // Assignments state
  const [documentAssignments, setDocumentAssignments] = useState<ServiceDocumentAssignment[]>([])
  const [procedureAssignments, setProcedureAssignments] = useState<ServiceProcedureAssignment[]>([])
  const [documentTemplates, setDocumentTemplates] = useState<DocumentTemplate[]>([])
  const [procedureTemplates, setProcedureTemplates] = useState<ProcedureTemplate[]>([])
  const [isLoadingAssignments, setIsLoadingAssignments] = useState(false)
  const [isAssigning, setIsAssigning] = useState(false)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [serviceData, ministriesData, sectorsData, categoriesData] = await Promise.all([
          fiscalServicesAPI.services.get(serviceId),
          fiscalServicesAPI.hierarchy.ministries.list(locale),
          fiscalServicesAPI.hierarchy.sectors.list(undefined, locale),
          fiscalServicesAPI.hierarchy.categories.list(undefined, locale),
        ])
        setService(serviceData)
        setMinistries(ministriesData)
        setSectors(sectorsData)
        setCategories(categoriesData)

        // Initialize form with service data
        setFormData({
          categoryId: serviceData.categoryId,
          nameEs: serviceData.nameEs,
          descriptionEs: serviceData.descriptionEs,
          descriptionVisible: serviceData.descriptionVisible ?? true,
          serviceType: serviceData.serviceType,
          calculationMethod: serviceData.calculationMethod,
          tasaExpedicion: serviceData.tasaExpedicion,
          tasaRenovacion: serviceData.tasaRenovacion,
          expeditionFormula: serviceData.expeditionFormula,
          expeditionUnitMeasure: serviceData.expeditionUnitMeasure,
          renewalFormula: serviceData.renewalFormula,
          renewalUnitMeasure: serviceData.renewalUnitMeasure,
          basePercentage: serviceData.basePercentage,
          percentageOf: serviceData.percentageOf,
          unitRate: serviceData.unitRate,
          unitType: serviceData.unitType,
          validityPeriodMonths: serviceData.validityPeriodMonths,
          renewalFrequencyMonths: serviceData.renewalFrequencyMonths,
          gracePeriodDays: serviceData.gracePeriodDays,
          latePenaltyPercentage: serviceData.latePenaltyPercentage,
          latePenaltyFixed: serviceData.latePenaltyFixed,
          legalReference: serviceData.legalReference,
          regulatoryArticles: serviceData.regulatoryArticles,
          tariffEffectiveFrom: serviceData.tariffEffectiveFrom,
          tariffEffectiveTo: serviceData.tariffEffectiveTo,
          status: serviceData.status,
          priority: serviceData.priority,
          complexityLevel: serviceData.complexityLevel,
          processingTimeDays: serviceData.processingTimeDays,
          parentServiceId: serviceData.parentServiceId,
          tierGroupName: serviceData.tierGroupName,
          isTierComponent: serviceData.isTierComponent,
        })

        // Find and set ministry/sector based on category
        const category = categoriesData.find(c => c.id === serviceData.categoryId)
        if (category) {
          const sectorId = category.sectorId ?? category.sector_id
          if (sectorId) {
            const sector = sectorsData.find(s => s.id === sectorId)
            if (sector) {
              const ministryId = sector.ministryId ?? sector.ministry_id
              setSelectedMinistry(ministryId ?? null)
              setSelectedSector(sectorId)
            }
          }
        }
      } catch (err) {
        toast({
          variant: 'destructive',
          title: t('errorTitle'),
          description: t('errorLoadingServices'),
        })
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serviceId])

  // Filter sectors when ministry changes
  useEffect(() => {
    if (selectedMinistry) {
      const filtered = sectors.filter(s => (s.ministryId ?? s.ministry_id) === selectedMinistry)
      setFilteredSectors(filtered)
    } else {
      setFilteredSectors([])
    }
  }, [selectedMinistry, sectors])

  // Filter categories when sector changes
  useEffect(() => {
    if (selectedSector) {
      const filtered = categories.filter(c => (c.sectorId ?? c.sector_id) === selectedSector)
      setFilteredCategories(filtered)
    } else {
      setFilteredCategories([])
    }
  }, [selectedSector, categories])

  // Fetch assignments and templates
  const fetchAssignments = async () => {
    if (!serviceId) return
    setIsLoadingAssignments(true)
    try {
      const [docs, procs, docTemplates, procTemplates] = await Promise.all([
        fiscalServicesAPI.documents.list(serviceId),
        fiscalServicesAPI.procedures.list(serviceId),
        fiscalServicesAPI.documents.templates.list(locale),
        fiscalServicesAPI.procedures.templates.list(locale),
      ])
      setDocumentAssignments(docs)
      setProcedureAssignments(procs)
      setDocumentTemplates(docTemplates)
      setProcedureTemplates(procTemplates)
    } catch (err) {
      console.error('Error fetching assignments:', err)
    } finally {
      setIsLoadingAssignments(false)
    }
  }

  useEffect(() => {
    if (serviceId) {
      fetchAssignments()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serviceId])

  // Handle unassign document
  const handleUnassignDocument = async (assignmentId: number) => {
    if (!confirm(t('confirmUnassign'))) return
    try {
      await fiscalServicesAPI.documents.unassign(serviceId, assignmentId)
      toast({
        title: t('successTitle'),
        description: t('assignmentRemoved'),
      })
      fetchAssignments()
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: err instanceof Error ? err.message : t('errorRemoving'),
      })
    }
  }

  // Handle unassign procedure
  const handleUnassignProcedure = async (assignmentId: number) => {
    if (!confirm(t('confirmUnassign'))) return
    try {
      await fiscalServicesAPI.procedures.unassign(serviceId, assignmentId)
      toast({
        title: t('successTitle'),
        description: t('assignmentRemoved'),
      })
      fetchAssignments()
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: err instanceof Error ? err.message : t('errorRemoving'),
      })
    }
  }

  // Handle multi-document assignment from SearchableTemplateTable
  const handleAssignDocuments = async (selectedIds: number[], options?: Record<string, boolean | string>) => {
    if (selectedIds.length === 0) return
    setIsAssigning(true)
    const isRequiredExpedition = options?.isRequiredExpedition === true
    const isRequiredRenewal = options?.isRequiredRenewal === true

    try {
      for (const docId of selectedIds) {
        await fiscalServicesAPI.documents.assign(serviceId, {
          documentTemplateId: docId,
          isRequiredExpedition,
          isRequiredRenewal,
        })
      }
      toast({
        title: t('successTitle'),
        description: `${selectedIds.length} ${t('documentAssigned')}`,
      })
      fetchAssignments()
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: err instanceof Error ? err.message : t('errorAssigning'),
      })
    } finally {
      setIsAssigning(false)
    }
  }

  // Handle multi-procedure assignment from SearchableTemplateTable
  const handleAssignProcedures = async (selectedIds: number[], options?: Record<string, boolean | string>) => {
    if (selectedIds.length === 0) return
    setIsAssigning(true)
    const appliesTo = (options?.appliesTo as string) || 'both'

    try {
      for (const procId of selectedIds) {
        await fiscalServicesAPI.procedures.assign(serviceId, {
          templateId: procId,
          appliesTo,
        })
      }
      toast({
        title: t('successTitle'),
        description: `${selectedIds.length} ${t('procedureAssigned')}`,
      })
      fetchAssignments()
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: err instanceof Error ? err.message : t('errorAssigning'),
      })
    } finally {
      setIsAssigning(false)
    }
  }

  // Get IDs of already assigned templates
  const assignedDocIds = documentAssignments.map(da => da.documentTemplateId)
  const assignedProcIds = procedureAssignments.map(pa => pa.templateId)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)

    try {
      // Build update data - only include changed fields
      const updateData: FiscalServiceUpdate = {}

      // Basic fields
      if (formData.categoryId !== undefined) updateData.categoryId = formData.categoryId
      if (formData.nameEs !== undefined) updateData.nameEs = formData.nameEs
      if (formData.descriptionEs !== undefined) updateData.descriptionEs = formData.descriptionEs
      if (formData.descriptionVisible !== undefined) updateData.descriptionVisible = formData.descriptionVisible
      if (formData.serviceType !== undefined) updateData.serviceType = formData.serviceType
      if (formData.status !== undefined) updateData.status = formData.status

      // Calculation fields
      if (formData.calculationMethod !== undefined) updateData.calculationMethod = formData.calculationMethod
      if (formData.tasaExpedicion !== undefined) updateData.tasaExpedicion = formData.tasaExpedicion
      if (formData.tasaRenovacion !== undefined) updateData.tasaRenovacion = formData.tasaRenovacion
      if (formData.expeditionFormula !== undefined) updateData.expeditionFormula = formData.expeditionFormula
      if (formData.expeditionUnitMeasure !== undefined) updateData.expeditionUnitMeasure = formData.expeditionUnitMeasure
      if (formData.renewalFormula !== undefined) updateData.renewalFormula = formData.renewalFormula
      if (formData.renewalUnitMeasure !== undefined) updateData.renewalUnitMeasure = formData.renewalUnitMeasure
      if (formData.basePercentage !== undefined) updateData.basePercentage = formData.basePercentage
      if (formData.percentageOf !== undefined) updateData.percentageOf = formData.percentageOf
      if (formData.unitRate !== undefined) updateData.unitRate = formData.unitRate
      if (formData.unitType !== undefined) updateData.unitType = formData.unitType

      // Validity fields
      if (formData.validityPeriodMonths !== undefined) updateData.validityPeriodMonths = formData.validityPeriodMonths
      if (formData.renewalFrequencyMonths !== undefined) updateData.renewalFrequencyMonths = formData.renewalFrequencyMonths
      if (formData.gracePeriodDays !== undefined) updateData.gracePeriodDays = formData.gracePeriodDays
      if (formData.latePenaltyPercentage !== undefined) updateData.latePenaltyPercentage = formData.latePenaltyPercentage
      if (formData.latePenaltyFixed !== undefined) updateData.latePenaltyFixed = formData.latePenaltyFixed
      if (formData.processingTimeDays !== undefined) updateData.processingTimeDays = formData.processingTimeDays

      // Legal fields
      if (formData.legalReference !== undefined) updateData.legalReference = formData.legalReference
      if (formData.regulatoryArticles !== undefined) updateData.regulatoryArticles = formData.regulatoryArticles
      if (formData.tariffEffectiveFrom !== undefined) updateData.tariffEffectiveFrom = formData.tariffEffectiveFrom
      if (formData.tariffEffectiveTo !== undefined) updateData.tariffEffectiveTo = formData.tariffEffectiveTo

      // Advanced fields
      if (formData.priority !== undefined) updateData.priority = formData.priority
      if (formData.complexityLevel !== undefined) updateData.complexityLevel = formData.complexityLevel
      if (formData.parentServiceId !== undefined) updateData.parentServiceId = formData.parentServiceId
      if (formData.tierGroupName !== undefined) updateData.tierGroupName = formData.tierGroupName
      if (formData.isTierComponent !== undefined) updateData.isTierComponent = formData.isTierComponent

      await fiscalServicesAPI.admin.update(serviceId, updateData)

      toast({
        title: t('successTitle'),
        description: t('serviceUpdated'),
      })

      router.push(`/${locale}/dashboard/admin/fiscal-services/${serviceId}`)
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: err instanceof Error ? err.message : t('errorUpdating'),
      })
      setIsSubmitting(false)
    }
  }

  if (isLoading || !service) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-3 text-muted-foreground">{t('loading')}</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          {t('back')}
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('editTitle')}</h1>
          <p className="text-muted-foreground mt-1">
            {t('editSubtitle')}: <span className="font-mono">{service.serviceCode}</span>
          </p>
        </div>
      </div>

      {/* Form with Tabs */}
      <form onSubmit={handleSubmit}>
        <Tabs defaultValue="basic" className="space-y-6">
          <TabsList className="grid w-full grid-cols-7">
            <TabsTrigger value="basic" className="flex items-center gap-2">
              <FileText className="h-4 w-4" />
              <span className="hidden md:inline">{t('basicInformation')}</span>
            </TabsTrigger>
            <TabsTrigger value="hierarchy" className="flex items-center gap-2">
              <Building2 className="h-4 w-4" />
              <span className="hidden md:inline">{t('hierarchyTab')}</span>
            </TabsTrigger>
            <TabsTrigger value="calculation" className="flex items-center gap-2">
              <Calculator className="h-4 w-4" />
              <span className="hidden md:inline">{t('calculation')}</span>
            </TabsTrigger>
            <TabsTrigger value="validity" className="flex items-center gap-2">
              <Clock className="h-4 w-4" />
              <span className="hidden md:inline">Validez</span>
            </TabsTrigger>
            <TabsTrigger value="legal" className="flex items-center gap-2">
              <BookOpen className="h-4 w-4" />
              <span className="hidden md:inline">Legal</span>
            </TabsTrigger>
            <TabsTrigger value="assignments" className="flex items-center gap-2">
              <Link2 className="h-4 w-4" />
              <span className="hidden md:inline">{t('tabs.assignments')}</span>
            </TabsTrigger>
            <TabsTrigger value="advanced" className="flex items-center gap-2">
              <Settings className="h-4 w-4" />
              <span className="hidden md:inline">Avanzado</span>
            </TabsTrigger>
          </TabsList>

          {/* Basic Information Tab */}
          <TabsContent value="basic" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>{t('basicInformation')}</CardTitle>
                <CardDescription>{t('basicInformationDesc')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>{t('serviceCode')}</Label>
                    <Input value={service.serviceCode} disabled className="bg-muted" />
                    <p className="text-xs text-muted-foreground">El codigo no se puede modificar</p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="status">{t('tableStatus')} *</Label>
                    <Select
                      value={formData.status}
                      onValueChange={(v) => setFormData({ ...formData, status: v as ServiceStatusEnum })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="draft">{t('statusDraft')}</SelectItem>
                        <SelectItem value="active">{t('statusActive')}</SelectItem>
                        <SelectItem value="inactive">{t('statusInactive')}</SelectItem>
                        <SelectItem value="deprecated">{t('statusDeprecated')}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="nameEs">{t('serviceName')} *</Label>
                  <Input
                    id="nameEs"
                    value={formData.nameEs || ''}
                    onChange={(e) => setFormData({ ...formData, nameEs: e.target.value })}
                    required
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="descriptionEs">{t('description')}</Label>
                    <div className="flex items-center gap-2">
                      <Label htmlFor="descriptionVisible" className="text-xs text-muted-foreground">
                        {t('descriptionVisibleLabel')}
                      </Label>
                      <Switch
                        id="descriptionVisible"
                        checked={formData.descriptionVisible ?? true}
                        onCheckedChange={(checked) => setFormData({ ...formData, descriptionVisible: checked })}
                      />
                    </div>
                  </div>
                  <Textarea
                    id="descriptionEs"
                    value={formData.descriptionEs || ''}
                    onChange={(e) => setFormData({ ...formData, descriptionEs: e.target.value })}
                    rows={3}
                  />
                  {service?.descriptionSource && (
                    <p className="text-xs text-muted-foreground">
                      {t('descriptionSource')}: {
                        service.descriptionSource === 'ai_generated' || service.descriptionSource === 'ai_draft'
                          ? t('descriptionSourceAI')
                          : t('descriptionSourceManual')
                      }
                    </p>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="serviceType">{t('serviceType')} *</Label>
                    <Select
                      value={formData.serviceType}
                      onValueChange={(v) => setFormData({ ...formData, serviceType: v as ServiceTypeEnum })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="document_processing">{t('typeDocumentProcessing')}</SelectItem>
                        <SelectItem value="license_permit">{t('typeLicensePermit')}</SelectItem>
                        <SelectItem value="residence_permit">{t('typeResidencePermit')}</SelectItem>
                        <SelectItem value="registration_fee">{t('typeRegistrationFee')}</SelectItem>
                        <SelectItem value="inspection_fee">{t('typeInspectionFee')}</SelectItem>
                        <SelectItem value="administrative_tax">{t('typeAdministrativeTax')}</SelectItem>
                        <SelectItem value="customs_duty">{t('typeCustomsDuty')}</SelectItem>
                        <SelectItem value="declaration_tax">{t('typeDeclarationTax')}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="processingTimeDays">Tiempo de procesamiento (dias)</Label>
                    <Input
                      id="processingTimeDays"
                      type="number"
                      min="0"
                      value={formData.processingTimeDays || ''}
                      onChange={(e) => setFormData({ ...formData, processingTimeDays: Number(e.target.value) || undefined })}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Hierarchy Tab */}
          <TabsContent value="hierarchy" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>{t('hierarchyTab')}</CardTitle>
                <CardDescription>{t('hierarchyTabDesc')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>{t('selectMinistry')}</Label>
                  <Select
                    value={String(selectedMinistry || '')}
                    onValueChange={(v) => {
                      setSelectedMinistry(Number(v))
                      setSelectedSector(null)
                      setFormData({ ...formData, categoryId: undefined })
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t('selectMinistry')} />
                    </SelectTrigger>
                    <SelectContent>
                      {ministries.map((m) => (
                        <SelectItem key={m.id} value={String(m.id)}>{m.nameEs || m.name_es}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>{t('selectSector')}</Label>
                  <Select
                    value={String(selectedSector || '')}
                    onValueChange={(v) => {
                      setSelectedSector(Number(v))
                      setFormData({ ...formData, categoryId: undefined })
                    }}
                    disabled={!selectedMinistry}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t('selectSector')} />
                    </SelectTrigger>
                    <SelectContent>
                      {filteredSectors.map((s) => (
                        <SelectItem key={s.id} value={String(s.id)}>{s.nameEs || s.name_es}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>{t('category')} *</Label>
                  <Select
                    value={String(formData.categoryId || '')}
                    onValueChange={(v) => setFormData({ ...formData, categoryId: Number(v) })}
                    disabled={!selectedSector}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t('selectCategory')} />
                    </SelectTrigger>
                    <SelectContent>
                      {filteredCategories.map((c) => (
                        <SelectItem key={c.id} value={String(c.id)}>{c.nameEs || c.name_es}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Calculation Tab */}
          <TabsContent value="calculation" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>{t('calculation')}</CardTitle>
                <CardDescription>{t('calculationDesc')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="calculationMethod">{t('calculationMethod')} *</Label>
                  <Select
                    value={formData.calculationMethod}
                    onValueChange={(v) => setFormData({ ...formData, calculationMethod: v as CalculationMethodEnum })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="fixed_expedition">{t('methodFixedExpedition')}</SelectItem>
                      <SelectItem value="fixed_renewal">{t('methodFixedRenewal')}</SelectItem>
                      <SelectItem value="fixed_both">{t('methodFixedBoth')}</SelectItem>
                      <SelectItem value="percentage_based">{t('methodPercentageBased')}</SelectItem>
                      <SelectItem value="unit_based">{t('methodUnitBased')}</SelectItem>
                      <SelectItem value="tiered_rates">{t('methodTieredRates')}</SelectItem>
                      <SelectItem value="formula_based">{t('methodFormulaBased')}</SelectItem>
                      <SelectItem value="fixed_plus_unit">{t('methodFixedPlusUnit')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Fixed Expedition: tasaExpedicion only */}
                {formData.calculationMethod === 'fixed_expedition' && (
                  <div className="space-y-2">
                    <Label htmlFor="tasaExpedicion">{t('expeditionFee')} (XAF) *</Label>
                    <Input
                      id="tasaExpedicion"
                      type="number"
                      min="0"
                      step="1"
                      value={formData.tasaExpedicion || ''}
                      onChange={(e) => setFormData({ ...formData, tasaExpedicion: Number(e.target.value) || undefined })}
                      placeholder="0"
                    />
                  </div>
                )}

                {/* Fixed Renewal: tasaRenovacion only */}
                {formData.calculationMethod === 'fixed_renewal' && (
                  <div className="space-y-2">
                    <Label htmlFor="tasaRenovacion">{t('renewalFee')} (XAF) *</Label>
                    <Input
                      id="tasaRenovacion"
                      type="number"
                      min="0"
                      step="1"
                      value={formData.tasaRenovacion || ''}
                      onChange={(e) => setFormData({ ...formData, tasaRenovacion: Number(e.target.value) || undefined })}
                      placeholder="0"
                    />
                  </div>
                )}

                {/* Fixed Both: tasaExpedicion + tasaRenovacion */}
                {formData.calculationMethod === 'fixed_both' && (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="tasaExpedicion">{t('expeditionFee')} (XAF) *</Label>
                      <Input
                        id="tasaExpedicion"
                        type="number"
                        min="0"
                        step="1"
                        value={formData.tasaExpedicion || ''}
                        onChange={(e) => setFormData({ ...formData, tasaExpedicion: Number(e.target.value) || undefined })}
                        placeholder="0"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="tasaRenovacion">{t('renewalFee')} (XAF) *</Label>
                      <Input
                        id="tasaRenovacion"
                        type="number"
                        min="0"
                        step="1"
                        value={formData.tasaRenovacion || ''}
                        onChange={(e) => setFormData({ ...formData, tasaRenovacion: Number(e.target.value) || undefined })}
                        placeholder="0"
                      />
                    </div>
                  </div>
                )}

                {/* Percentage Based: basePercentage + percentageOf */}
                {formData.calculationMethod === 'percentage_based' && (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="basePercentage">Porcentaje Base (%) *</Label>
                      <Input
                        id="basePercentage"
                        type="number"
                        min="0"
                        max="100"
                        step="0.01"
                        value={formData.basePercentage || ''}
                        onChange={(e) => setFormData({ ...formData, basePercentage: Number(e.target.value) || undefined })}
                        placeholder="0.00"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="percentageOf">Porcentaje de *</Label>
                      <Input
                        id="percentageOf"
                        value={formData.percentageOf || ''}
                        onChange={(e) => setFormData({ ...formData, percentageOf: e.target.value })}
                        placeholder="ej. valor_declarado, capital_social"
                      />
                    </div>
                  </div>
                )}

                {/* Unit Based: unitRate + unitType */}
                {formData.calculationMethod === 'unit_based' && (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="unitRate">Tarifa por Unidad (XAF) *</Label>
                      <Input
                        id="unitRate"
                        type="number"
                        min="0"
                        step="1"
                        value={formData.unitRate || ''}
                        onChange={(e) => setFormData({ ...formData, unitRate: Number(e.target.value) || undefined })}
                        placeholder="0"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="unitType">Tipo de Unidad *</Label>
                      <Input
                        id="unitType"
                        value={formData.unitType || ''}
                        onChange={(e) => setFormData({ ...formData, unitType: e.target.value })}
                        placeholder="ej. kg, unidad, m²"
                      />
                    </div>
                  </div>
                )}

                {/* Tiered Rates: message about configuration */}
                {formData.calculationMethod === 'tiered_rates' && (
                  <div className="p-4 bg-muted/50 rounded-lg border border-dashed">
                    <p className="text-sm text-muted-foreground">
                      {t('tieredRatesNotice') || 'Las tarifas escalonadas se configuran en una seccion separada.'}
                    </p>
                  </div>
                )}

                {/* Formula Based: formulas + unit measures */}
                {formData.calculationMethod === 'formula_based' && (
                  <>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="expeditionFormula">Formula de Expedicion *</Label>
                        <Input
                          id="expeditionFormula"
                          value={formData.expeditionFormula || ''}
                          onChange={(e) => setFormData({ ...formData, expeditionFormula: e.target.value })}
                          placeholder="ej. base * 0.05"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="expeditionUnitMeasure">Unidad de Expedicion</Label>
                        <Input
                          id="expeditionUnitMeasure"
                          value={formData.expeditionUnitMeasure || ''}
                          onChange={(e) => setFormData({ ...formData, expeditionUnitMeasure: e.target.value })}
                          placeholder="ej. documento, pagina"
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="renewalFormula">Formula de Renovacion</Label>
                        <Input
                          id="renewalFormula"
                          value={formData.renewalFormula || ''}
                          onChange={(e) => setFormData({ ...formData, renewalFormula: e.target.value })}
                          placeholder="ej. base * 0.03"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="renewalUnitMeasure">Unidad de Renovacion</Label>
                        <Input
                          id="renewalUnitMeasure"
                          value={formData.renewalUnitMeasure || ''}
                          onChange={(e) => setFormData({ ...formData, renewalUnitMeasure: e.target.value })}
                          placeholder="ej. documento, pagina"
                        />
                      </div>
                    </div>
                  </>
                )}

                {/* Fixed Plus Unit: fixed fees + unit fields */}
                {formData.calculationMethod === 'fixed_plus_unit' && (
                  <>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="tasaExpedicion">{t('expeditionFee')} (XAF)</Label>
                        <Input
                          id="tasaExpedicion"
                          type="number"
                          min="0"
                          step="1"
                          value={formData.tasaExpedicion || ''}
                          onChange={(e) => setFormData({ ...formData, tasaExpedicion: Number(e.target.value) || undefined })}
                          placeholder="0"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="tasaRenovacion">{t('renewalFee')} (XAF)</Label>
                        <Input
                          id="tasaRenovacion"
                          type="number"
                          min="0"
                          step="1"
                          value={formData.tasaRenovacion || ''}
                          onChange={(e) => setFormData({ ...formData, tasaRenovacion: Number(e.target.value) || undefined })}
                          placeholder="0"
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="unitRate">Tarifa por Unidad (XAF) *</Label>
                        <Input
                          id="unitRate"
                          type="number"
                          min="0"
                          step="1"
                          value={formData.unitRate || ''}
                          onChange={(e) => setFormData({ ...formData, unitRate: Number(e.target.value) || undefined })}
                          placeholder="0"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="unitType">Tipo de Unidad *</Label>
                        <Input
                          id="unitType"
                          value={formData.unitType || ''}
                          onChange={(e) => setFormData({ ...formData, unitType: e.target.value })}
                          placeholder="ej. kg, unidad, m²"
                        />
                      </div>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Validity & Penalties Tab */}
          <TabsContent value="validity" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Validez y Renovacion</CardTitle>
                <CardDescription>Periodos de validez, renovacion y penalidades</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="validityPeriodMonths">Periodo de Validez (meses)</Label>
                    <Input
                      id="validityPeriodMonths"
                      type="number"
                      min="0"
                      value={formData.validityPeriodMonths || ''}
                      onChange={(e) => setFormData({ ...formData, validityPeriodMonths: Number(e.target.value) || undefined })}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="renewalFrequencyMonths">Frecuencia de Renovacion (meses)</Label>
                    <Input
                      id="renewalFrequencyMonths"
                      type="number"
                      min="0"
                      value={formData.renewalFrequencyMonths || ''}
                      onChange={(e) => setFormData({ ...formData, renewalFrequencyMonths: Number(e.target.value) || undefined })}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="gracePeriodDays">Periodo de Gracia (dias)</Label>
                    <Input
                      id="gracePeriodDays"
                      type="number"
                      min="0"
                      value={formData.gracePeriodDays || ''}
                      onChange={(e) => setFormData({ ...formData, gracePeriodDays: Number(e.target.value) || undefined })}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="latePenaltyPercentage">Penalidad por Atraso (%)</Label>
                    <Input
                      id="latePenaltyPercentage"
                      type="number"
                      min="0"
                      max="100"
                      step="0.01"
                      value={formData.latePenaltyPercentage || ''}
                      onChange={(e) => setFormData({ ...formData, latePenaltyPercentage: Number(e.target.value) || undefined })}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="latePenaltyFixed">Penalidad Fija (XAF)</Label>
                    <Input
                      id="latePenaltyFixed"
                      type="number"
                      min="0"
                      step="1"
                      value={formData.latePenaltyFixed || ''}
                      onChange={(e) => setFormData({ ...formData, latePenaltyFixed: Number(e.target.value) || undefined })}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Legal Tab */}
          <TabsContent value="legal" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Informacion Legal</CardTitle>
                <CardDescription>Referencias legales y fechas de vigencia</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="legalReference">Referencia Legal</Label>
                  <Textarea
                    id="legalReference"
                    value={formData.legalReference || ''}
                    onChange={(e) => setFormData({ ...formData, legalReference: e.target.value })}
                    placeholder="Ley, decreto o reglamento aplicable..."
                    rows={3}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="regulatoryArticles">Articulos Regulatorios (uno por linea)</Label>
                  <Textarea
                    id="regulatoryArticles"
                    value={(formData.regulatoryArticles || []).join('\n')}
                    onChange={(e) => setFormData({ ...formData, regulatoryArticles: e.target.value.split('\n').filter(s => s.trim()) })}
                    placeholder="Art. 1&#10;Art. 2&#10;Art. 3"
                    rows={3}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="tariffEffectiveFrom">{t('effectiveFrom')} *</Label>
                    <Input
                      id="tariffEffectiveFrom"
                      type="date"
                      value={formData.tariffEffectiveFrom?.split('T')[0] || ''}
                      onChange={(e) => setFormData({ ...formData, tariffEffectiveFrom: e.target.value })}
                      required
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="tariffEffectiveTo">Vigente hasta</Label>
                    <Input
                      id="tariffEffectiveTo"
                      type="date"
                      value={formData.tariffEffectiveTo?.split('T')[0] || ''}
                      onChange={(e) => setFormData({ ...formData, tariffEffectiveTo: e.target.value || undefined })}
                    />
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
                  <CardContent className="space-y-4">
                    {/* Existing assignments */}
                    {documentAssignments.length === 0 ? (
                      <div className="text-center py-6 text-muted-foreground">
                        <FileText className="h-10 w-10 mx-auto mb-2 opacity-30" />
                        <p>{t('noAssignedDocuments')}</p>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {documentAssignments.map((doc) => (
                          <div
                            key={doc.id}
                            className="flex items-center justify-between p-3 border rounded-lg bg-muted/30"
                          >
                            <div className="flex-1">
                              <p className="font-medium">{doc.documentName || `Document #${doc.documentTemplateId}`}</p>
                            </div>
                            <div className="flex items-center gap-4">
                              <div className="flex items-center gap-1 text-xs">
                                <span className="text-muted-foreground">{t('expedition')}:</span>
                                {doc.isRequiredExpedition ? <Check className="h-4 w-4 text-green-600" /> : <X className="h-4 w-4 text-red-500" />}
                              </div>
                              <div className="flex items-center gap-1 text-xs">
                                <span className="text-muted-foreground">{t('renewal')}:</span>
                                {doc.isRequiredRenewal ? <Check className="h-4 w-4 text-green-600" /> : <X className="h-4 w-4 text-red-500" />}
                              </div>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => handleUnassignDocument(doc.id)}
                              >
                                <Trash2 className="h-4 w-4 text-red-500" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Searchable template table for documents */}
                    <SearchableTemplateTable
                      type="document"
                      templates={documentTemplates}
                      excludeIds={assignedDocIds}
                      onAssign={handleAssignDocuments}
                      locale={locale}
                      isAssigning={isAssigning}
                    />
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
                  <CardContent className="space-y-4">
                    {/* Existing assignments */}
                    {procedureAssignments.length === 0 ? (
                      <div className="text-center py-6 text-muted-foreground">
                        <BookOpen className="h-10 w-10 mx-auto mb-2 opacity-30" />
                        <p>{t('noAssignedProcedures')}</p>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {procedureAssignments.map((proc) => (
                          <div
                            key={proc.id}
                            className="flex items-center justify-between p-3 border rounded-lg bg-muted/30"
                          >
                            <div className="flex-1">
                              <p className="font-medium">{proc.procedureName || `Procedure #${proc.templateId}`}</p>
                            </div>
                            <div className="flex items-center gap-3">
                              <Badge variant="outline">
                                {proc.appliesTo === 'expedition' ? t('expedition') :
                                 proc.appliesTo === 'renewal' ? t('renewal') :
                                 proc.appliesTo === 'both' ? t('both') :
                                 proc.appliesTo || '-'}
                              </Badge>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => handleUnassignProcedure(proc.id)}
                              >
                                <Trash2 className="h-4 w-4 text-red-500" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Searchable template table for procedures */}
                    <SearchableTemplateTable
                      type="procedure"
                      templates={procedureTemplates}
                      excludeIds={assignedProcIds}
                      onAssign={handleAssignProcedures}
                      locale={locale}
                      isAssigning={isAssigning}
                    />
                  </CardContent>
                </Card>
              </>
            )}
          </TabsContent>

          {/* Advanced Tab */}
          <TabsContent value="advanced" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Configuracion Avanzada</CardTitle>
                <CardDescription>Prioridad, complejidad y agrupaciones</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="priority">Prioridad</Label>
                    <Input
                      id="priority"
                      type="number"
                      min="0"
                      value={formData.priority || ''}
                      onChange={(e) => setFormData({ ...formData, priority: Number(e.target.value) || undefined })}
                    />
                    <p className="text-xs text-muted-foreground">Mayor numero = mayor prioridad</p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="complexityLevel">Nivel de Complejidad (1-5)</Label>
                    <Select
                      value={String(formData.complexityLevel || '')}
                      onValueChange={(v) => setFormData({ ...formData, complexityLevel: Number(v) || undefined })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Seleccionar nivel" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="1">1 - Muy Simple</SelectItem>
                        <SelectItem value="2">2 - Simple</SelectItem>
                        <SelectItem value="3">3 - Moderado</SelectItem>
                        <SelectItem value="4">4 - Complejo</SelectItem>
                        <SelectItem value="5">5 - Muy Complejo</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="parentServiceId">Servicio Padre (ID)</Label>
                    <Input
                      id="parentServiceId"
                      type="number"
                      min="0"
                      value={formData.parentServiceId || ''}
                      onChange={(e) => setFormData({ ...formData, parentServiceId: Number(e.target.value) || undefined })}
                    />
                    <p className="text-xs text-muted-foreground">Para sub-servicios</p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="tierGroupName">Nombre de Grupo de Tarifa</Label>
                    <Input
                      id="tierGroupName"
                      value={formData.tierGroupName || ''}
                      onChange={(e) => setFormData({ ...formData, tierGroupName: e.target.value })}
                      placeholder="ej. tarifas_vehiculos"
                    />
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <Switch
                    id="isTierComponent"
                    checked={formData.isTierComponent || false}
                    onCheckedChange={(checked) => setFormData({ ...formData, isTierComponent: checked })}
                  />
                  <Label htmlFor="isTierComponent">Es componente de tarifa escalonada</Label>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Actions */}
        <div className="flex items-center justify-end gap-4 mt-6">
          <Button type="button" variant="outline" onClick={() => router.back()}>
            {t('cancel')}
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                {t('updating')}
              </>
            ) : (
              <>
                <Save className="h-4 w-4 mr-2" />
                {t('updateServiceButton')}
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  )
}
