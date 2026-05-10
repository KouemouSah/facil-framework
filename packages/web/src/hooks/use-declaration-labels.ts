/**
 * useDeclarationLabels Hook
 *
 * Centralized hook for translating declaration types and statuses
 * Aligned with backend Pydantic enums
 */

import { useTranslations } from 'next-intl'
import { DeclarationStatus, DeclarationType } from '@/types/declaration'

export function useDeclarationLabels() {
  const t = useTranslations('declarations')

  /**
   * Get translated label for declaration status
   */
  const getStatusLabel = (status: DeclarationStatus | string): string => {
    const statusMap: Record<DeclarationStatus, string> = {
      [DeclarationStatus.DRAFT]: t('statusDraft'),
      [DeclarationStatus.SUBMITTED]: t('statusSubmitted'),
      [DeclarationStatus.PROCESSING]: t('statusProcessing'),
      [DeclarationStatus.ACCEPTED]: t('statusAccepted'),
      [DeclarationStatus.REJECTED]: t('statusRejected'),
      [DeclarationStatus.AMENDED]: t('statusAmended'),
    }

    return statusMap[status as DeclarationStatus] || status
  }

  /**
   * Get translated label for declaration type
   */
  const getTypeLabel = (type: DeclarationType | string): string => {
    const typeMap: Record<DeclarationType, string> = {
      // IVA (90% volume)
      [DeclarationType.IVA_DESTAJO]: t('typeIvaDestajo'),
      [DeclarationType.IVA_REAL]: t('typeIvaReal'),

      // IRPF (5% volume)
      [DeclarationType.INCOME_TAX]: t('typeIncomeTax'),
      [DeclarationType.CORPORATE_TAX]: t('typeCorporateTax'),

      // Pétroliers (4% volume, gros montants)
      [DeclarationType.RETENCION_3PCT_PETROLERO]: t('typeRetencion3PctPetrolero'),
      [DeclarationType.RETENCION_5PCT_PETROLERO]: t('typeRetencion5PctPetrolero'),
      [DeclarationType.RETENCION_10PCT_PETROLERO]: t('typeRetencion10PctPetrolero'),
      [DeclarationType.PETROLEO_GAS]: t('typePetroleoGas'),
      [DeclarationType.PETROLEO_DIESEL]: t('typePetroleoDiesel'),
      [DeclarationType.PETROLEO_ESSENCE]: t('typePetroleoEssence'),

      // Retenciones (1% volume)
      [DeclarationType.RETENCION_3PCT]: t('typeRetencion3Pct'),
      [DeclarationType.RETENCION_5PCT]: t('typeRetencion5Pct'),
      [DeclarationType.RETENCION_10PCT]: t('typeRetencion10Pct'),

      // Autres types (<1% volume)
      [DeclarationType.VAT_DECLARATION]: t('typeVatDeclaration'),
      [DeclarationType.SALES_TAX]: t('typeSalesTax'),
      [DeclarationType.PROPERTY_TAX]: t('typePropertyTax'),
      [DeclarationType.PAYROLL_TAX]: t('typePayrollTax'),
      [DeclarationType.EXCISE_TAX]: t('typeExciseTax'),
      [DeclarationType.CUSTOMS_DECLARATION]: t('typeCustomsDeclaration'),
      [DeclarationType.SPECIAL_TAX]: t('typeSpecialTax'),

      // Types additionnels
      [DeclarationType.QUARTERLY_RETURN]: t('typeQuarterlyReturn'),
      [DeclarationType.ANNUAL_RETURN]: t('typeAnnualReturn'),
      [DeclarationType.AMENDED_RETURN]: t('typeAmendedReturn'),
      [DeclarationType.ESTIMATED_TAX]: t('typeEstimatedTax'),
      [DeclarationType.WITHHOLDING_TAX]: t('typeWithholdingTax'),
      [DeclarationType.CAPITAL_GAINS]: t('typeCapitalGains'),
      [DeclarationType.INHERITANCE_TAX]: t('typeInheritanceTax'),
    }

    return typeMap[type as DeclarationType] || type
  }

  /**
   * Get all status options for filters/selects
   */
  const getStatusOptions = () => {
    return [
      { value: 'all', label: t('filterAll') },
      { value: DeclarationStatus.DRAFT, label: getStatusLabel(DeclarationStatus.DRAFT) },
      { value: DeclarationStatus.SUBMITTED, label: getStatusLabel(DeclarationStatus.SUBMITTED) },
      { value: DeclarationStatus.PROCESSING, label: getStatusLabel(DeclarationStatus.PROCESSING) },
      { value: DeclarationStatus.ACCEPTED, label: getStatusLabel(DeclarationStatus.ACCEPTED) },
      { value: DeclarationStatus.REJECTED, label: getStatusLabel(DeclarationStatus.REJECTED) },
      { value: DeclarationStatus.AMENDED, label: getStatusLabel(DeclarationStatus.AMENDED) },
    ]
  }

  /**
   * Get all type options for filters/selects (grouped by category)
   */
  const getTypeOptions = () => {
    return {
      iva: [
        { value: DeclarationType.IVA_DESTAJO, label: getTypeLabel(DeclarationType.IVA_DESTAJO) },
        { value: DeclarationType.IVA_REAL, label: getTypeLabel(DeclarationType.IVA_REAL) },
      ],
      irpf: [
        { value: DeclarationType.INCOME_TAX, label: getTypeLabel(DeclarationType.INCOME_TAX) },
        { value: DeclarationType.CORPORATE_TAX, label: getTypeLabel(DeclarationType.CORPORATE_TAX) },
      ],
      petroleros: [
        { value: DeclarationType.RETENCION_3PCT_PETROLERO, label: getTypeLabel(DeclarationType.RETENCION_3PCT_PETROLERO) },
        { value: DeclarationType.RETENCION_5PCT_PETROLERO, label: getTypeLabel(DeclarationType.RETENCION_5PCT_PETROLERO) },
        { value: DeclarationType.RETENCION_10PCT_PETROLERO, label: getTypeLabel(DeclarationType.RETENCION_10PCT_PETROLERO) },
        { value: DeclarationType.PETROLEO_GAS, label: getTypeLabel(DeclarationType.PETROLEO_GAS) },
        { value: DeclarationType.PETROLEO_DIESEL, label: getTypeLabel(DeclarationType.PETROLEO_DIESEL) },
        { value: DeclarationType.PETROLEO_ESSENCE, label: getTypeLabel(DeclarationType.PETROLEO_ESSENCE) },
      ],
      retenciones: [
        { value: DeclarationType.RETENCION_3PCT, label: getTypeLabel(DeclarationType.RETENCION_3PCT) },
        { value: DeclarationType.RETENCION_5PCT, label: getTypeLabel(DeclarationType.RETENCION_5PCT) },
        { value: DeclarationType.RETENCION_10PCT, label: getTypeLabel(DeclarationType.RETENCION_10PCT) },
      ],
      otros: [
        { value: DeclarationType.VAT_DECLARATION, label: getTypeLabel(DeclarationType.VAT_DECLARATION) },
        { value: DeclarationType.SALES_TAX, label: getTypeLabel(DeclarationType.SALES_TAX) },
        { value: DeclarationType.PROPERTY_TAX, label: getTypeLabel(DeclarationType.PROPERTY_TAX) },
        { value: DeclarationType.PAYROLL_TAX, label: getTypeLabel(DeclarationType.PAYROLL_TAX) },
        { value: DeclarationType.EXCISE_TAX, label: getTypeLabel(DeclarationType.EXCISE_TAX) },
        { value: DeclarationType.CUSTOMS_DECLARATION, label: getTypeLabel(DeclarationType.CUSTOMS_DECLARATION) },
        { value: DeclarationType.SPECIAL_TAX, label: getTypeLabel(DeclarationType.SPECIAL_TAX) },
        { value: DeclarationType.QUARTERLY_RETURN, label: getTypeLabel(DeclarationType.QUARTERLY_RETURN) },
        { value: DeclarationType.ANNUAL_RETURN, label: getTypeLabel(DeclarationType.ANNUAL_RETURN) },
        { value: DeclarationType.AMENDED_RETURN, label: getTypeLabel(DeclarationType.AMENDED_RETURN) },
        { value: DeclarationType.ESTIMATED_TAX, label: getTypeLabel(DeclarationType.ESTIMATED_TAX) },
        { value: DeclarationType.WITHHOLDING_TAX, label: getTypeLabel(DeclarationType.WITHHOLDING_TAX) },
        { value: DeclarationType.CAPITAL_GAINS, label: getTypeLabel(DeclarationType.CAPITAL_GAINS) },
        { value: DeclarationType.INHERITANCE_TAX, label: getTypeLabel(DeclarationType.INHERITANCE_TAX) },
      ],
    }
  }

  return {
    getStatusLabel,
    getTypeLabel,
    getStatusOptions,
    getTypeOptions,
  }
}
