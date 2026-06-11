'use client'

import { useEffect } from 'react'
import { Loader2, CheckCircle2, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { FEE_TYPE_LABELS } from '@/types/service-bundle'
import { CompanyInfoCard } from './CompanyInfoCard'
import { PaymentModeSwitcher } from './PaymentModeSwitcher'
import { ObligationRow } from './ObligationRow'
import { BundleErrorAlert } from './BundleErrorAlert'
import type { UseBundleWizardReturn } from '../hooks/useBundleWizard'
import type { ObligationItem } from '../types'

interface ObligationsReviewStepProps {
  wizard: UseBundleWizardReturn
  locale: string
}

const labels = {
  title: {
    es: 'Obligaciones Fiscales',
    fr: 'Obligations Fiscales',
    en: 'Fiscal Obligations',
  },
  loading: {
    es: 'Verificando obligaciones fiscales...',
    fr: 'Verification des obligations fiscales...',
    en: 'Verifying fiscal obligations...',
  },
  alreadyComplete: {
    es: 'Todas las obligaciones ya estan pagadas para este ano fiscal.',
    fr: 'Toutes les obligations sont deja payees pour cette annee fiscale.',
    en: 'All obligations are already paid for this fiscal year.',
  },
  paymentMode: {
    es: 'Modo de pago',
    fr: 'Mode de paiement',
    en: 'Payment mode',
  },
  obligations: {
    es: 'Obligaciones',
    fr: 'Obligations',
    en: 'Obligations',
  },
  selectAll: {
    es: 'Seleccionar todo',
    fr: 'Tout selectionner',
    en: 'Select all',
  },
  deselectAll: {
    es: 'Deseleccionar todo',
    fr: 'Tout deselectionner',
    en: 'Deselect all',
  },
  totalSelected: {
    es: 'Total seleccionado',
    fr: 'Total selectionne',
    en: 'Total selected',
  },
  alreadyPaid: {
    es: 'Ya pagado',
    fr: 'Deja paye',
    en: 'Already paid',
  },
  year: {
    es: 'Ano fiscal',
    fr: 'Annee fiscale',
    en: 'Fiscal year',
  },
  backToDashboard: {
    es: 'Volver al dashboard',
    fr: 'Retour au tableau de bord',
    en: 'Back to dashboard',
  },
  pendingWarning: {
    es: 'Las obligaciones no seleccionadas quedaran pendientes. Podra pagarlas en otro momento.',
    fr: 'Les obligations non selectionnees resteront en attente. Vous pourrez les payer plus tard.',
    en: 'Unselected obligations will remain pending. You can pay them later.',
  },
} as const

function formatXAF(amount: number): string {
  return new Intl.NumberFormat('es-GQ', {
    style: 'decimal',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}

export function ObligationsReviewStep({ wizard, locale }: ObligationsReviewStepProps) {
  const lang = (locale === 'fr' ? 'fr' : locale === 'en' ? 'en' : 'es') as 'es' | 'fr' | 'en'

  // Load obligations on mount
  useEffect(() => {
    if (!wizard.licenseData && wizard.selectedCompany) {
      wizard.loadObligations()
    }
  }, [wizard.selectedCompany]) // eslint-disable-line react-hooks/exhaustive-deps

  // Loading state
  if (wizard.isInitiating) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
        <p className="text-sm text-muted-foreground">{labels.loading[lang]}</p>
      </div>
    )
  }

  if (!wizard.licenseData) {
    // Classification preview needs manual zone/category selection
    const preview = wizard.classificationPreview
    if (preview) {
      const classLabels = {
        title: { es: 'Clasificación de la Empresa', fr: "Classification de l'Entreprise", en: 'Company Classification' },
        extracted: { es: 'Datos extraídos del documento', fr: 'Données extraites du document', en: 'Data extracted from document' },
        selectZone: { es: 'Zona fiscal', fr: 'Zone fiscale', en: 'Fiscal zone' },
        detectedZone: { es: 'Zona detectada (puede modificar)', fr: 'Zone détectée (modifiable)', en: 'Detected zone (editable)' },
        selectCategory: { es: 'Categoría de actividad', fr: "Catégorie d'activité", en: 'Activity category' },
        confirm: { es: 'Confirmar y continuar', fr: 'Confirmer et continuer', en: 'Confirm and continue' },
      }
      // Zone: user selection > auto-detected
      const effectiveZoneId = wizard.selectedZoneId || preview.zone?.id || ''

      // Show tier-filtered zones if OCR detected a city, otherwise ALL zones
      // tierZones = zones matching detected tier (e.g., A1/A2/A3 for Malabo)
      const primaryZones = preview.tierZones?.length > 0
        ? preview.tierZones
        : preview.availableZones

      // Categories: zone-specific if available, otherwise global commerce_types
      const categoryOptions = preview.availableCategories.length > 0
        ? preview.availableCategories
        : (preview.availableCommerceTypes || [])

      // Effective commerce_type: user selection > auto-classification
      const effectiveCommerceType = wizard.selectedCommerceType || preview.classification?.commerceType || ''

      // Need confirmation
      const zoneConfirmed = !!effectiveZoneId
      const categoryConfirmed = !!effectiveCommerceType

      const f = wizard.editedFields
      const required = (val: string | null) => !val ? 'border-red-300 bg-red-50' : 'bg-background'
      const fieldLabels = {
        legalName: { es: 'Nombre comercial *', fr: 'Nom commercial *', en: 'Trade name *' },
        registrationNumber: { es: 'N° Registro (PE-XXXX) *', fr: 'N° Registre (PE-XXXX) *', en: 'Registration No. (PE-XXXX) *' },
        nif: { es: 'NIF (si aplica)', fr: 'NIF (si applicable)', en: 'NIF (if applicable)' },
        formaJuridica: { es: 'Forma jurídica', fr: 'Forme juridique', en: 'Legal form' },
        localidad: { es: 'Localidad *', fr: 'Localité *', en: 'City *' },
        provincia: { es: 'Provincia', fr: 'Province', en: 'Province' },
        sector: { es: 'Sector', fr: 'Secteur', en: 'Sector' },
        objetoSocial: { es: 'Objeto social', fr: 'Objet social', en: 'Business activity' },
        missingRequired: { es: 'Campo obligatorio', fr: 'Champ obligatoire', en: 'Required field' },
      }

      return (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">{classLabels.title[lang]}</h3>
          <p className="text-xs text-muted-foreground">{classLabels.extracted[lang]}</p>

          {/* ── Company data form (all fields editable) ── */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* Legal name — REQUIRED */}
            <div className="md:col-span-2">
              <label className="text-xs font-medium text-muted-foreground">{fieldLabels.legalName[lang]}</label>
              <input type="text" className={`w-full rounded-md border px-3 py-2 text-sm ${required(f.legalName)}`}
                value={f.legalName || ''} onChange={e => wizard.setEditedField('legalName', e.target.value || null)}
              />
              {!f.legalName && <p className="text-[10px] text-red-600 mt-0.5">{fieldLabels.missingRequired[lang]}</p>}
            </div>

            {/* Registration number — REQUIRED for AUTONOMO (PE-XXXX) */}
            <div className="md:col-span-2">
              <label className="text-xs font-medium text-muted-foreground">{fieldLabels.registrationNumber[lang]}</label>
              <input type="text" className={`w-full rounded-md border px-3 py-2 text-sm font-mono ${required(f.registrationNumber)}`}
                value={f.registrationNumber || ''} onChange={e => wizard.setEditedField('registrationNumber', e.target.value || null)}
                placeholder="PE-000000"
              />
              {!f.registrationNumber && <p className="text-[10px] text-red-600 mt-0.5">{fieldLabels.missingRequired[lang]}</p>}
            </div>

            {/* Forma juridica */}
            <div>
              <label className="text-xs font-medium text-muted-foreground">{fieldLabels.formaJuridica[lang]}</label>
              <input type="text" className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                value={f.formaJuridica || ''} onChange={e => wizard.setEditedField('formaJuridica', e.target.value || null)}
              />
            </div>

            {/* Localidad */}
            <div>
              <label className="text-xs font-medium text-muted-foreground">{fieldLabels.localidad[lang]}</label>
              <input type="text" className={`w-full rounded-md border px-3 py-2 text-sm ${required(f.localidad)}`}
                value={f.localidad || ''} onChange={e => wizard.setEditedField('localidad', e.target.value || null)}
              />
              {!f.localidad && <p className="text-[10px] text-red-600 mt-0.5">{fieldLabels.missingRequired[lang]}</p>}
            </div>

            {/* Provincia */}
            <div>
              <label className="text-xs font-medium text-muted-foreground">{fieldLabels.provincia[lang]}</label>
              <input type="text" className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                value={f.provincia || ''} onChange={e => wizard.setEditedField('provincia', e.target.value || null)}
              />
            </div>

            {/* Sector */}
            <div>
              <label className="text-xs font-medium text-muted-foreground">{fieldLabels.sector[lang]}</label>
              <input type="text" className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                value={f.sector || ''} onChange={e => wizard.setEditedField('sector', e.target.value || null)}
              />
            </div>

            {/* Objeto social */}
            <div className="md:col-span-2">
              <label className="text-xs font-medium text-muted-foreground">{fieldLabels.objetoSocial[lang]}</label>
              <input type="text" className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                value={f.objetoSocial || ''} onChange={e => wizard.setEditedField('objetoSocial', e.target.value || null)}
              />
            </div>
          </div>

          {/* ── Zone detected info ── */}
          {preview.detectedCity && preview.detectedTier && (
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm">
              <p className="font-medium text-blue-800">
                {preview.detectedCity} — Tier {preview.detectedTier}
              </p>
              <p className="text-xs text-blue-600 mt-0.5">
                {{es: 'Seleccione la zona según la ubicación de su comercio', fr: 'Sélectionnez la zone selon l\'emplacement de votre commerce', en: 'Select the zone based on your commerce location'}[lang]}
              </p>
            </div>
          )}

          {/* ── Zone selector ── */}
          {primaryZones.length > 0 && (
            <div className="space-y-2">
              <label className="text-sm font-medium">{classLabels.selectZone[lang]} *</label>
              <select className={`w-full rounded-md border px-3 py-2 text-sm ${!effectiveZoneId ? 'border-red-300 bg-red-50' : 'bg-background'}`}
                value={effectiveZoneId}
                onChange={(e) => { wizard.setSelectedZoneId(e.target.value || null); wizard.setSelectedCommerceType(null) }}
              >
                <option value="">--</option>
                {primaryZones.map((z) => (
                  <option key={z.id} value={z.id}>{z.code} — {z.name}{z.description ? ` (${z.description})` : ''}</option>
                ))}
              </select>
              {preview.tierZones?.length > 0 && preview.availableZones.length > preview.tierZones.length && (
                <details className="text-xs text-muted-foreground">
                  <summary className="cursor-pointer hover:text-foreground">
                    {{es: 'Mostrar todas las zonas', fr: 'Afficher toutes les zones', en: 'Show all zones'}[lang]}
                  </summary>
                  <select className="w-full mt-1 rounded-md border bg-background px-3 py-2 text-sm"
                    value={effectiveZoneId}
                    onChange={(e) => { wizard.setSelectedZoneId(e.target.value || null); wizard.setSelectedCommerceType(null) }}
                  >
                    <option value="">--</option>
                    {preview.availableZones.map((z) => (
                      <option key={z.id} value={z.id}>{z.code} — {z.name}{z.description ? ` (${z.description})` : ''}</option>
                    ))}
                  </select>
                </details>
              )}
            </div>
          )}

          {/* ── Category (commerce_type) selector ── */}
          {categoryOptions.length > 0 && (
            <div className="space-y-2">
              <label className="text-sm font-medium">{classLabels.selectCategory[lang]} *</label>
              <select className={`w-full rounded-md border px-3 py-2 text-sm ${!effectiveCommerceType ? 'border-red-300 bg-red-50' : 'bg-background'}`}
                value={effectiveCommerceType}
                onChange={(e) => wizard.setSelectedCommerceType(e.target.value || null)}
              >
                <option value="">--</option>
                {categoryOptions.map((c) => (
                  <option key={c.commerceType} value={c.commerceType}>
                    {c.bundleName} ({c.commerceType})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Confirm — goNext handles loadObligations when moving to OBLIGATIONS step */}
          <Button
            className="w-full"
            disabled={!zoneConfirmed || !categoryConfirmed || wizard.isInitiating}
            onClick={() => {
              wizard.clearError()
              wizard.goNext()
            }}
          >
            {wizard.isInitiating
              ? <><Loader2 className="h-4 w-4 animate-spin mr-2" />{classLabels.confirm[lang]}</>
              : classLabels.confirm[lang]}
          </Button>
        </div>
      )
    }

    // Classification not yet loaded
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
        <p className="text-sm text-muted-foreground">{labels.loading[lang]}</p>
      </div>
    )
  }

  // Show error if obligations failed to load — retry invokes loadObligations
  if (wizard.apiError) {
    return (
      <div className="space-y-4">
        <BundleErrorAlert
          error={wizard.apiError}
          locale={locale}
          onRetry={() => {
            wizard.clearError()
            wizard.loadObligations()
          }}
          onBack={wizard.goBack}
          onClear={wizard.clearError}
        />
      </div>
    )
  }

  const { licenseData } = wizard

  // Already complete
  if (licenseData.alreadyComplete) {
    return (
      <div className="space-y-4">
        {wizard.selectedCompany && (
          <CompanyInfoCard company={wizard.selectedCompany} locale={locale} compact />
        )}
        <Alert className="border-green-200 bg-green-50 dark:bg-green-950">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800 dark:text-green-200">
            {labels.alreadyComplete[lang]}
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  // Group obligations by fee_type
  const groups = groupByFeeType(licenseData.obligations)
  const showCheckbox = wizard.selectedMode === 'per_line'

  // Calculate selected total
  const selectedTotal = licenseData.obligations
    .filter(o => wizard.selectedObligationIds.has(o.id))
    .reduce((sum, o) => sum + o.total, 0)

  const paidTotal = licenseData.obligations
    .filter(o => !o.isPayable)
    .reduce((sum, o) => sum + o.total, 0)

  const hasUnselected = showCheckbox &&
    wizard.selectedObligationIds.size < licenseData.obligations.filter(o => o.isPayable).length

  return (
    <div className="space-y-6">
      {/* Company summary */}
      {wizard.selectedCompany && (
        <CompanyInfoCard company={wizard.selectedCompany} locale={locale} compact />
      )}

      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          {labels.title[lang]} — {licenseData.fiscalYear}
        </h2>
      </div>

      {/* Payment mode switcher */}
      <div>
        <h3 className="text-sm font-medium mb-3">{labels.paymentMode[lang]}</h3>
        <PaymentModeSwitcher
          value={wizard.selectedMode}
          onChange={wizard.setSelectedMode}
          locale={locale}
        />
      </div>

      <Separator />

      {/* Obligations table */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium">{labels.obligations[lang]}</h3>
          {showCheckbox && (
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={wizard.selectAllObligations}>
                {labels.selectAll[lang]}
              </Button>
              <Button variant="ghost" size="sm" onClick={wizard.deselectAllObligations}>
                {labels.deselectAll[lang]}
              </Button>
            </div>
          )}
        </div>

        {groups.map(({ feeType, obligations: groupObls }) => (
          <div key={feeType} className="mb-4">
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
              {(FEE_TYPE_LABELS as Record<string, Record<string, string>>)[feeType]?.[lang] || feeType}
            </h4>

            {/* Desktop table */}
            <table className="hidden md:table w-full">
              <tbody>
                {groupObls.map((obl) => (
                  <ObligationRow
                    key={obl.id}
                    obligation={obl}
                    isSelected={wizard.selectedObligationIds.has(obl.id)}
                    onToggle={wizard.toggleObligation}
                    showCheckbox={showCheckbox}
                    locale={locale}
                  />
                ))}
              </tbody>
            </table>

            {/* Mobile cards */}
            <div className="md:hidden space-y-2">
              {groupObls.map((obl) => (
                <ObligationRow
                  key={obl.id}
                  obligation={obl}
                  isSelected={wizard.selectedObligationIds.has(obl.id)}
                  onToggle={wizard.toggleObligation}
                  showCheckbox={showCheckbox}
                  locale={locale}
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      <Separator />

      {/* Totals */}
      <div className="space-y-2">
        {paidTotal > 0 && (
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>{labels.alreadyPaid[lang]}</span>
            <span className="tabular-nums">{formatXAF(paidTotal)} XAF</span>
          </div>
        )}
        <div className="flex justify-between text-base font-semibold">
          <span>
            {labels.totalSelected[lang]}
            <span className="text-sm font-normal text-muted-foreground ml-2">
              ({wizard.selectedObligationIds.size} obl.)
            </span>
          </span>
          <span className="tabular-nums">{formatXAF(selectedTotal)} XAF</span>
        </div>
      </div>

      {/* Warning for partial selection */}
      {hasUnselected && (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription className="text-sm">
            {labels.pendingWarning[lang]}
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}

// ── Helper: Group obligations by fee_type ─────────────────────

function groupByFeeType(
  obligations: ObligationItem[],
): Array<{ feeType: string; obligations: ObligationItem[] }> {
  const order = ['tesoro', 'municipal', 'chamber']
  const map = new Map<string, ObligationItem[]>()

  for (const obl of obligations) {
    const group = map.get(obl.feeType) || []
    group.push(obl)
    map.set(obl.feeType, group)
  }

  return order
    .filter(ft => map.has(ft))
    .map(ft => ({ feeType: ft, obligations: map.get(ft)! }))
}
