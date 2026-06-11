'use client'

/**
 * Fiscal Service Create Form - Complete with All Fields and Tabs
 * Create new fiscal service with all database fields (49 columns)
 *
 * PHASE 8.2: Service Creation Form
 * CRITICAL: 100% backend-aligned with FiscalServiceCreate
 *
 * @module dashboard/admin/fiscal-services/new
 * @author Claude Code
 * @date 2025-12-08
 */

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
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
  Building2,
  FileText,
  Link2,
  Calculator,
  Clock,
  BookOpen,
  Settings,
  Trash2,
  Check,
  X,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/hooks/use-toast'
import fiscalServicesAPI from '@/modules/fiscal-services/services/api'
import { SearchableTemplateTable } from '@/modules/fiscal-services/components'
import type {
  FiscalServiceCreate,
  Category,
  Ministry,
  Sector,
  ServiceTypeEnum,
  ServiceStatusEnum,
  CalculationMethodEnum,
  DocumentTemplate,
  ProcedureTemplate,
} from '@/types/fiscal-service'

// Type for selected document with assignment options
interface SelectedDocument {
  id: number
  isRequiredExpedition: boolean
  isRequiredRenewal: boolean
  name?: string
}

// Type for selected procedure with assignment options
interface SelectedProcedure {
  id: number
  appliesTo: string
  name?: string
}

export default function CreateFiscalServicePage() {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('admin.fiscalServices')
  const { toast } = useToast()

  // Hierarchy data
  const [ministries, setMinistries] = useState<Ministry[]>([])
  const [sectors, setSectors] = useState<Sector[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [filteredSectors, setFilteredSectors] = useState<Sector[]>([])
  const [filteredCategories, setFilteredCategories] = useState<Category[]>([])

  // Templates data
  const [documentTemplates, setDocumentTemplates] = useState<DocumentTemplate[]>([])
  const [procedureTemplates, setProcedureTemplates] = useState<ProcedureTemplate[]>([])

  // Assignments with options
  const [selectedDocuments, setSelectedDocuments] = useState<SelectedDocument[]>([])
  const [selectedProcedures, setSelectedProcedures] = useState<SelectedProcedure[]>([])
  const [isAssigning, setIsAssigning] = useState(false)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isLoadingData, setIsLoadingData] = useState(true)
  const [selectedMinistry, setSelectedMinistry] = useState<number | null>(null)
  const [selectedSector, setSelectedSector] = useState<number | null>(null)

  // Form state - ALL fields from fiscal_services table
  const [formData, setFormData] = useState<Partial<FiscalServiceCreate>>({
    // Basic
    serviceCode: '',
    categoryId: 0,
    nameEs: '',
    descriptionEs: '',
    serviceType: 'registration_fee' as ServiceTypeEnum,
    status: 'draft' as ServiceStatusEnum,
    processingTimeDays: 1,

    // Calculation
    calculationMethod: 'fixed_both' as CalculationMethodEnum,
    tasaExpedicion: undefined,
    tasaRenovacion: undefined,
    expeditionFormula: '',
    expeditionUnitMeasure: '',
    renewalFormula: '',
    renewalUnitMeasure: '',
    basePercentage: undefined,
    percentageOf: '',
    unitRate: undefined,
    unitType: '',

    // Validity & Penalties
    validityPeriodMonths: undefined,
    renewalFrequencyMonths: undefined,
    gracePeriodDays: 0,
    latePenaltyPercentage: undefined,
    latePenaltyFixed: undefined,

    // Legal
    legalReference: '',
    regulatoryArticles: [],
    tariffEffectiveFrom: new Date().toISOString().split('T')[0],
    tariffEffectiveTo: undefined,

    // Advanced
    priority: 0,
    complexityLevel: 1,
    parentServiceId: undefined,
    tierGroupName: '',
    isTierComponent: false,
  })

  useEffect(() => {
    const fetchData = async () => {
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
        console.error('Error fetching hierarchy data:', err)
      }
    }

    const fetchTemplates = async () => {
      try {
        const [docs, procs] = await Promise.all([
          fiscalServicesAPI.documents.templates.list(locale),
          fiscalServicesAPI.procedures.templates.list(locale),
        ])
        setDocumentTemplates(docs)
        setProcedureTemplates(procs)
      } catch (err) {
        console.error('Error fetching templates:', err)
      } finally {
        setIsLoadingData(false)
      }
    }

    fetchData()
    fetchTemplates()
  }, [locale])

  // Filter sectors when ministry changes
  useEffect(() => {
    if (selectedMinistry) {
      const filtered = sectors.filter(s => (s.ministryId ?? s.ministry_id) === selectedMinistry)
      setFilteredSectors(filtered)
      setSelectedSector(null)
      setFilteredCategories([])
      setFormData(prev => ({ ...prev, categoryId: 0 }))
    } else {
      setFilteredSectors([])
    }
  }, [selectedMinistry, sectors])

  // Filter categories when sector changes
  useEffect(() => {
    if (selectedSector) {
      const filtered = categories.filter(c => (c.sectorId ?? c.sector_id) === selectedSector)
      setFilteredCategories(filtered)
      setFormData(prev => ({ ...prev, categoryId: 0 }))
    } else {
      setFilteredCategories([])
    }
  }, [selectedSector, categories])

  // Handle document assignment from SearchableTemplateTable
  const handleAssignDocuments = useCallback((selectedIds: number[], options?: Record<string, boolean | string>) => {
    setIsAssigning(true)
    const isRequiredExpedition = options?.isRequiredExpedition === true
    const isRequiredRenewal = options?.isRequiredRenewal === true

    const newDocs: SelectedDocument[] = selectedIds.map(id => {
      const template = documentTemplates.find(dt => dt.id === id)
      return {
        id,
        isRequiredExpedition,
        isRequiredRenewal,
        name: template?.documentNameEs || template?.templateCode || `Doc #${id}`,
      }
    })

    setSelectedDocuments(prev => [...prev, ...newDocs])
    setIsAssigning(false)

    toast({
      title: t('successTitle'),
      description: `${selectedIds.length} ${t('documentAssigned')}`,
    })
  }, [documentTemplates, toast, t])

  // Handle procedure assignment from SearchableTemplateTable
  const handleAssignProcedures = useCallback((selectedIds: number[], options?: Record<string, boolean | string>) => {
    setIsAssigning(true)
    const appliesTo = (options?.appliesTo as string) || 'both'

    const newProcs: SelectedProcedure[] = selectedIds.map(id => {
      const template = procedureTemplates.find(pt => pt.id === id)
      return {
        id,
        appliesTo,
        name: template?.nameEs || template?.templateCode || `Proc #${id}`,
      }
    })

    setSelectedProcedures(prev => [...prev, ...newProcs])
    setIsAssigning(false)

    toast({
      title: t('successTitle'),
      description: `${selectedIds.length} ${t('procedureAssigned')}`,
    })
  }, [procedureTemplates, toast, t])

  // Remove document assignment
  const removeDocumentAssignment = (docId: number) => {
    setSelectedDocuments(prev => prev.filter(d => d.id !== docId))
  }

  // Remove procedure assignment
  const removeProcedureAssignment = (procId: number) => {
    setSelectedProcedures(prev => prev.filter(p => p.id !== procId))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)

    try {
      // Basic validation
      if (!formData.serviceCode || !formData.categoryId || !formData.nameEs) {
        toast({
          variant: 'destructive',
          title: t('errorTitle'),
          description: t('requiredFields'),
        })
        setIsSubmitting(false)
        return
      }

      // Create service with ALL fields
      const createData: FiscalServiceCreate = {
        // Required fields
        serviceCode: formData.serviceCode!,
        categoryId: formData.categoryId!,
        nameEs: formData.nameEs!,
        tariffEffectiveFrom: formData.tariffEffectiveFrom!,

        // Basic
        descriptionEs: formData.descriptionEs || undefined,
        serviceType: formData.serviceType as ServiceTypeEnum,
        status: formData.status as ServiceStatusEnum,
        processingTimeDays: formData.processingTimeDays || 1,

        // Calculation
        calculationMethod: formData.calculationMethod as CalculationMethodEnum,
        tasaExpedicion: formData.tasaExpedicion || undefined,
        tasaRenovacion: formData.tasaRenovacion || undefined,
        expeditionFormula: formData.expeditionFormula || undefined,
        expeditionUnitMeasure: formData.expeditionUnitMeasure || undefined,
        renewalFormula: formData.renewalFormula || undefined,
        renewalUnitMeasure: formData.renewalUnitMeasure || undefined,
        basePercentage: formData.basePercentage || undefined,
        percentageOf: formData.percentageOf || undefined,
        unitRate: formData.unitRate || undefined,
        unitType: formData.unitType || undefined,

        // Validity & Penalties
        validityPeriodMonths: formData.validityPeriodMonths || undefined,
        renewalFrequencyMonths: formData.renewalFrequencyMonths || undefined,
        gracePeriodDays: formData.gracePeriodDays || 0,
        latePenaltyPercentage: formData.latePenaltyPercentage || undefined,
        latePenaltyFixed: formData.latePenaltyFixed || undefined,

        // Legal
        legalReference: formData.legalReference || undefined,
        regulatoryArticles: formData.regulatoryArticles?.length ? formData.regulatoryArticles : undefined,
        tariffEffectiveTo: formData.tariffEffectiveTo || undefined,

        // Advanced
        priority: formData.priority || 0,
        complexityLevel: formData.complexityLevel || 1,
        parentServiceId: formData.parentServiceId || undefined,
        tierGroupName: formData.tierGroupName || undefined,
        isTierComponent: formData.isTierComponent || false,
      }

      const newService = await fiscalServicesAPI.admin.create(createData)

      // Assign documents with their options
      if (selectedDocuments.length > 0) {
        for (const doc of selectedDocuments) {
          await fiscalServicesAPI.documents.assign(newService.id, {
            documentTemplateId: doc.id,
            isRequiredExpedition: doc.isRequiredExpedition,
            isRequiredRenewal: doc.isRequiredRenewal,
          })
        }
      }

      // Assign procedures with their options
      if (selectedProcedures.length > 0) {
        for (const proc of selectedProcedures) {
          await fiscalServicesAPI.procedures.assign(newService.id, {
            templateId: proc.id,
            appliesTo: proc.appliesTo,
          })
        }
      }

      toast({
        title: t('successTitle'),
        description: t('serviceCreated'),
      })

      router.push(`/${locale}/dashboard/admin/fiscal-services/${newService.id}`)
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: err instanceof Error ? err.message : t('errorCreating'),
      })
      setIsSubmitting(false)
    }
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
          <h1 className="text-3xl font-bold tracking-tight">{t('createTitle')}</h1>
          <p className="text-muted-foreground mt-1">{t('createSubtitle')}</p>
        </div>
      </div>

      {/* Form */}
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
              <span className="hidden md:inline">{t('validityTab') || 'Validez'}</span>
            </TabsTrigger>
            <TabsTrigger value="legal" className="flex items-center gap-2">
              <BookOpen className="h-4 w-4" />
              <span className="hidden md:inline">{t('legalTab') || 'Legal'}</span>
            </TabsTrigger>
            <TabsTrigger value="assignments" className="flex items-center gap-2">
              <Link2 className="h-4 w-4" />
              <span className="hidden md:inline">{t('assignmentsTab')}</span>
            </TabsTrigger>
            <TabsTrigger value="advanced" className="flex items-center gap-2">
              <Settings className="h-4 w-4" />
              <span className="hidden md:inline">{t('advancedTab') || 'Avanzado'}</span>
            </TabsTrigger>
          </TabsList>

          {/* Tab 1: Basic Information */}
          <TabsContent value="basic" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>{t('basicInformation')}</CardTitle>
                <CardDescription>{t('basicInformationDesc')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="serviceCode">{t('serviceCode')} *</Label>
                    <Input
                      id="serviceCode"
                      value={formData.serviceCode}
                      onChange={(e) => setFormData({ ...formData, serviceCode: e.target.value })}
                      placeholder={t('serviceCodePlaceholder')}
                      required
                    />
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
                    value={formData.nameEs}
                    onChange={(e) => setFormData({ ...formData, nameEs: e.target.value })}
                    placeholder={t('serviceNamePlaceholder')}
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="descriptionEs">{t('description')}</Label>
                  <Textarea
                    id="descriptionEs"
                    value={formData.descriptionEs || ''}
                    onChange={(e) => setFormData({ ...formData, descriptionEs: e.target.value })}
                    placeholder={t('descriptionPlaceholder')}
                    rows={3}
                  />
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
                    <Label htmlFor="processingTimeDays">{t('processingTime') || 'Tiempo de procesamiento (días)'}</Label>
                    <Input
                      id="processingTimeDays"
                      type="number"
                      min="0"
                      value={formData.processingTimeDays || ''}
                      onChange={(e) => setFormData({ ...formData, processingTimeDays: Number(e.target.value) || 1 })}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tab 2: Hierarchy */}
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
                    onValueChange={(v) => setSelectedMinistry(Number(v))}
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
                    onValueChange={(v) => setSelectedSector(Number(v))}
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

          {/* Tab 3: Calculation */}
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
                      <Label htmlFor="basePercentage">{t('basePercentage') || 'Porcentaje Base'} (%) *</Label>
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
                      <Label htmlFor="percentageOf">{t('percentageOf') || 'Porcentaje de'} *</Label>
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
                      <Label htmlFor="unitRate">{t('unitRate') || 'Tarifa por Unidad'} (XAF) *</Label>
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
                      <Label htmlFor="unitType">{t('unitType') || 'Tipo de Unidad'} *</Label>
                      <Input
                        id="unitType"
                        value={formData.unitType || ''}
                        onChange={(e) => setFormData({ ...formData, unitType: e.target.value })}
                        placeholder="ej. kg, unidad, m²"
                      />
                    </div>
                  </div>
                )}

                {/* Tiered Rates: message about configuration after creation */}
                {formData.calculationMethod === 'tiered_rates' && (
                  <div className="p-4 bg-muted/50 rounded-lg border border-dashed">
                    <p className="text-sm text-muted-foreground">
                      {t('tieredRatesNotice') || 'Las tarifas escalonadas se configuran después de crear el servicio.'}
                    </p>
                  </div>
                )}

                {/* Formula Based: formulas + unit measures */}
                {formData.calculationMethod === 'formula_based' && (
                  <>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="expeditionFormula">{t('expeditionFormula') || 'Fórmula de Expedición'} *</Label>
                        <Input
                          id="expeditionFormula"
                          value={formData.expeditionFormula || ''}
                          onChange={(e) => setFormData({ ...formData, expeditionFormula: e.target.value })}
                          placeholder="ej. base * 0.05"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="expeditionUnitMeasure">{t('expeditionUnitMeasure') || 'Unidad de Expedición'}</Label>
                        <Input
                          id="expeditionUnitMeasure"
                          value={formData.expeditionUnitMeasure || ''}
                          onChange={(e) => setFormData({ ...formData, expeditionUnitMeasure: e.target.value })}
                          placeholder="ej. documento, página"
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="renewalFormula">{t('renewalFormula') || 'Fórmula de Renovación'}</Label>
                        <Input
                          id="renewalFormula"
                          value={formData.renewalFormula || ''}
                          onChange={(e) => setFormData({ ...formData, renewalFormula: e.target.value })}
                          placeholder="ej. base * 0.03"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="renewalUnitMeasure">{t('renewalUnitMeasure') || 'Unidad de Renovación'}</Label>
                        <Input
                          id="renewalUnitMeasure"
                          value={formData.renewalUnitMeasure || ''}
                          onChange={(e) => setFormData({ ...formData, renewalUnitMeasure: e.target.value })}
                          placeholder="ej. documento, página"
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
                        <Label htmlFor="unitRate">{t('unitRate') || 'Tarifa por Unidad'} (XAF) *</Label>
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
                        <Label htmlFor="unitType">{t('unitType') || 'Tipo de Unidad'} *</Label>
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

          {/* Tab 4: Validity & Penalties */}
          <TabsContent value="validity" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>{t('validityTitle') || 'Validez y Renovación'}</CardTitle>
                <CardDescription>{t('validityDescription') || 'Períodos de validez, renovación y penalidades'}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="validityPeriodMonths">{t('validityPeriod') || 'Período de Validez (meses)'}</Label>
                    <Input
                      id="validityPeriodMonths"
                      type="number"
                      min="0"
                      value={formData.validityPeriodMonths || ''}
                      onChange={(e) => setFormData({ ...formData, validityPeriodMonths: Number(e.target.value) || undefined })}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="renewalFrequencyMonths">{t('renewalFrequency') || 'Frecuencia de Renovación (meses)'}</Label>
                    <Input
                      id="renewalFrequencyMonths"
                      type="number"
                      min="0"
                      value={formData.renewalFrequencyMonths || ''}
                      onChange={(e) => setFormData({ ...formData, renewalFrequencyMonths: Number(e.target.value) || undefined })}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="gracePeriodDays">{t('gracePeriod') || 'Período de Gracia (días)'}</Label>
                    <Input
                      id="gracePeriodDays"
                      type="number"
                      min="0"
                      value={formData.gracePeriodDays || ''}
                      onChange={(e) => setFormData({ ...formData, gracePeriodDays: Number(e.target.value) || 0 })}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="latePenaltyPercentage">{t('latePenaltyPercentage') || 'Penalidad por Atraso (%)'}</Label>
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
                    <Label htmlFor="latePenaltyFixed">{t('latePenaltyFixed') || 'Penalidad Fija (XAF)'}</Label>
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

          {/* Tab 5: Legal */}
          <TabsContent value="legal" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>{t('legalTitle') || 'Información Legal'}</CardTitle>
                <CardDescription>{t('legalDescription') || 'Referencias legales y fechas de vigencia'}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="legalReference">{t('legalReference') || 'Referencia Legal'}</Label>
                  <Textarea
                    id="legalReference"
                    value={formData.legalReference || ''}
                    onChange={(e) => setFormData({ ...formData, legalReference: e.target.value })}
                    placeholder="Ley, decreto o reglamento aplicable..."
                    rows={3}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="regulatoryArticles">{t('regulatoryArticles') || 'Artículos Regulatorios (uno por línea)'}</Label>
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
                      value={formData.tariffEffectiveFrom}
                      onChange={(e) => setFormData({ ...formData, tariffEffectiveFrom: e.target.value })}
                      required
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="tariffEffectiveTo">{t('effectiveTo') || 'Vigente hasta'}</Label>
                    <Input
                      id="tariffEffectiveTo"
                      type="date"
                      value={formData.tariffEffectiveTo || ''}
                      onChange={(e) => setFormData({ ...formData, tariffEffectiveTo: e.target.value || undefined })}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tab 6: Assignments */}
          <TabsContent value="assignments" className="space-y-6">
            {/* Document Assignments */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  {t('documentsTitle')}
                  <Badge variant="secondary" className="ml-2">{selectedDocuments.length}</Badge>
                </CardTitle>
                <CardDescription>{t('documentsSubtitle')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Existing assignments */}
                {selectedDocuments.length > 0 && (
                  <div className="space-y-2 mb-4">
                    <Label className="text-sm font-medium">{t('assignedDocuments') || 'Documentos asignados'}</Label>
                    {selectedDocuments.map((doc) => (
                      <div
                        key={doc.id}
                        className="flex items-center justify-between p-3 border rounded-lg bg-muted/30"
                      >
                        <div className="flex-1">
                          <p className="font-medium">{doc.name}</p>
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
                            onClick={() => removeDocumentAssignment(doc.id)}
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Searchable template table for documents */}
                {!isLoadingData && (
                  <SearchableTemplateTable
                    type="document"
                    templates={documentTemplates}
                    excludeIds={selectedDocuments.map(d => d.id)}
                    onAssign={handleAssignDocuments}
                    locale={locale}
                    isAssigning={isAssigning}
                  />
                )}
              </CardContent>
            </Card>

            {/* Procedure Assignments */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Link2 className="h-5 w-5" />
                  {t('proceduresTitle')}
                  <Badge variant="secondary" className="ml-2">{selectedProcedures.length}</Badge>
                </CardTitle>
                <CardDescription>{t('proceduresSubtitle')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Existing assignments */}
                {selectedProcedures.length > 0 && (
                  <div className="space-y-2 mb-4">
                    <Label className="text-sm font-medium">{t('assignedProcedures') || 'Procedimientos asignados'}</Label>
                    {selectedProcedures.map((proc) => (
                      <div
                        key={proc.id}
                        className="flex items-center justify-between p-3 border rounded-lg bg-muted/30"
                      >
                        <div className="flex-1">
                          <p className="font-medium">{proc.name}</p>
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
                            onClick={() => removeProcedureAssignment(proc.id)}
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Searchable template table for procedures */}
                {!isLoadingData && (
                  <SearchableTemplateTable
                    type="procedure"
                    templates={procedureTemplates}
                    excludeIds={selectedProcedures.map(p => p.id)}
                    onAssign={handleAssignProcedures}
                    locale={locale}
                    isAssigning={isAssigning}
                  />
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tab 7: Advanced */}
          <TabsContent value="advanced" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>{t('advancedTitle') || 'Configuración Avanzada'}</CardTitle>
                <CardDescription>{t('advancedDescription') || 'Prioridad, complejidad y agrupaciones'}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="priority">{t('priority') || 'Prioridad'}</Label>
                    <Input
                      id="priority"
                      type="number"
                      min="0"
                      value={formData.priority || ''}
                      onChange={(e) => setFormData({ ...formData, priority: Number(e.target.value) || 0 })}
                    />
                    <p className="text-xs text-muted-foreground">Mayor número = mayor prioridad</p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="complexityLevel">{t('complexityLevel') || 'Nivel de Complejidad (1-5)'}</Label>
                    <Select
                      value={String(formData.complexityLevel || '')}
                      onValueChange={(v) => setFormData({ ...formData, complexityLevel: Number(v) || 1 })}
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
                    <Label htmlFor="parentServiceId">{t('parentService') || 'Servicio Padre (ID)'}</Label>
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
                    <Label htmlFor="tierGroupName">{t('tierGroup') || 'Nombre de Grupo de Tarifa'}</Label>
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
                  <Label htmlFor="isTierComponent">{t('isTierComponent') || 'Es componente de tarifa escalonada'}</Label>
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
                {t('creating')}
              </>
            ) : (
              <>
                <Save className="h-4 w-4 mr-2" />
                {t('createServiceButton')}
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  )
}
