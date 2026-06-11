import type { InspectionStatus, SealReason } from '../types'

// D4 fix: Status config uses icon+color only — labels come from i18n
// Usage: const t = useTranslations('inspection'); label = t(`status.${status}`)
export const INSPECTION_STATUS_CONFIG: Record<
  InspectionStatus,
  { color: string; bgColor: string }
> = {
  in_progress: { color: 'text-blue-700', bgColor: 'bg-blue-100' },
  completed: { color: 'text-green-700', bgColor: 'bg-green-100' },
  mise_en_demeure: { color: 'text-orange-700', bgColor: 'bg-orange-100' },
  seal_proposed: { color: 'text-red-700', bgColor: 'bg-red-100' },
  seal_approved: { color: 'text-red-900', bgColor: 'bg-red-200' },
  seal_rejected: { color: 'text-gray-700', bgColor: 'bg-gray-100' },
  cancelled: { color: 'text-gray-500', bgColor: 'bg-gray-50' },
}

// D4 fix: Seal reason labels come from i18n
// Usage: const t = useTranslations('inspection'); label = t(`seal.reasons.${reason}`)
export const SEAL_REASONS: SealReason[] = [
  'non_paiement_apres_med',
  'activite_non_autorisee',
  'fraude_fiscale',
  'faux_documents',
  'refus_controle',
  'non_conformite_grave',
  'decision_judiciaire',
  'ordre_ministeriel',
]

export function fmtXAF(amount: number | undefined | null, locale = 'es'): string {
  if (amount == null) return '0 XAF'
  return new Intl.NumberFormat(locale === 'en' ? 'en-GQ' : locale === 'fr' ? 'fr-GQ' : 'es-GQ', {
    style: 'decimal',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount) + ' XAF'
}
