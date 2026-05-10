'use client'

import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { FEE_TYPE_LABELS } from '@/types/service-bundle'
import { OBLIGATION_STATUS_LABELS } from '@/types/commercial-license'
import type { ObligationItem } from '../types'

interface ObligationRowProps {
  obligation: ObligationItem
  isSelected: boolean
  onToggle: (id: string) => void
  showCheckbox: boolean
  locale: string
}

const feeTypeColors: Record<string, string> = {
  tesoro: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  municipal: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200',
  chamber: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
}

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  overdue: 'bg-red-100 text-red-800',
  paid: 'bg-green-100 text-green-800',
  processing: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  payment_pending: 'bg-orange-100 text-orange-800',
}

function formatXAF(amount: number): string {
  return new Intl.NumberFormat('es-GQ', {
    style: 'decimal',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}

export function ObligationRow({
  obligation,
  isSelected,
  onToggle,
  showCheckbox,
  locale,
}: ObligationRowProps) {
  const lang = (locale === 'fr' ? 'fr' : locale === 'en' ? 'en' : 'es') as 'es' | 'fr' | 'en'
  const isPaid = !obligation.isPayable

  return (
    <>
      {/* Desktop row */}
      <tr className={`hidden md:table-row border-b last:border-b-0 ${
        isPaid ? 'opacity-50 bg-muted/30' : ''
      }`}>
        {showCheckbox && (
          <td className="p-3 w-10">
            {obligation.isPayable ? (
              <Checkbox
                checked={isSelected}
                onCheckedChange={() => onToggle(obligation.id)}
              />
            ) : (
              <Checkbox checked disabled className="opacity-30" />
            )}
          </td>
        )}
        <td className="p-3">
          <span className="text-sm font-medium">{obligation.fiscalServiceName}</span>
          {obligation.ministryName && (
            <p className="text-xs text-muted-foreground mt-0.5">{obligation.ministryName}</p>
          )}
        </td>
        <td className="p-3">
          <Badge variant="outline" className={`text-xs ${feeTypeColors[obligation.feeType] || ''}`}>
            {(FEE_TYPE_LABELS as Record<string, Record<string, string>>)[obligation.feeType]?.[lang] || obligation.feeType}
          </Badge>
        </td>
        <td className="p-3 text-right tabular-nums text-sm">
          {formatXAF(obligation.amount)} XAF
          {obligation.penaltyAmount > 0 && (
            <p className="text-xs text-red-600">+{formatXAF(obligation.penaltyAmount)}</p>
          )}
        </td>
        <td className="p-3">
          <Badge variant="outline" className={`text-xs ${statusColors[obligation.status] || ''}`}>
            {(OBLIGATION_STATUS_LABELS as Record<string, Record<string, string>>)[obligation.status]?.[lang] || obligation.status}
          </Badge>
        </td>
      </tr>

      {/* Mobile card */}
      <div
        className={`md:hidden rounded-lg border p-3 ${
          isPaid ? 'opacity-50 bg-muted/30' : ''
        } ${isSelected && obligation.isPayable ? 'border-primary bg-primary/5' : ''}`}
        onClick={() => obligation.isPayable && showCheckbox && onToggle(obligation.id)}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-2 min-w-0 flex-1">
            {showCheckbox && (
              <div className="pt-0.5">
                {obligation.isPayable ? (
                  <Checkbox
                    checked={isSelected}
                    onCheckedChange={() => onToggle(obligation.id)}
                  />
                ) : (
                  <Checkbox checked disabled className="opacity-30" />
                )}
              </div>
            )}
            <div className="min-w-0">
              <p className="text-sm font-medium truncate">{obligation.fiscalServiceName}</p>
              {obligation.ministryName && (
                <p className="text-xs text-muted-foreground truncate">{obligation.ministryName}</p>
              )}
              <div className="flex items-center gap-1.5 mt-1">
                <Badge variant="outline" className={`text-xs ${feeTypeColors[obligation.feeType] || ''}`}>
                  {(FEE_TYPE_LABELS as Record<string, Record<string, string>>)[obligation.feeType]?.[lang] || obligation.feeType}
                </Badge>
                <Badge variant="outline" className={`text-xs ${statusColors[obligation.status] || ''}`}>
                  {(OBLIGATION_STATUS_LABELS as Record<string, Record<string, string>>)[obligation.status]?.[lang] || obligation.status}
                </Badge>
              </div>
            </div>
          </div>
          <div className="text-right shrink-0">
            <span className="text-sm font-semibold tabular-nums">{formatXAF(obligation.amount)}</span>
            <span className="text-xs text-muted-foreground ml-1">XAF</span>
            {obligation.penaltyAmount > 0 && (
              <p className="text-xs text-red-600">+{formatXAF(obligation.penaltyAmount)}</p>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
