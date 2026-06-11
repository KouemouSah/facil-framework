'use client'

import { Building2, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import type { MyCompanyWithStatus } from '../types'

interface MyCompanyCardProps {
  data: MyCompanyWithStatus
  locale: string
  onSelect: (company: MyCompanyWithStatus['company']) => void
}

const labels = {
  pending: { es: 'obligaciones pendientes', fr: 'obligations en attente', en: 'pending obligations' },
  upToDate: { es: 'Al dia', fr: 'A jour', en: 'Up to date' },
  notEligible: { es: 'No elegible', fr: 'Non eligible', en: 'Not eligible' },
  pay: { es: 'Pagar', fr: 'Payer', en: 'Pay' },
} as const

export function MyCompanyCard({ data, locale, onSelect }: MyCompanyCardProps) {
  const lang = (locale === 'fr' ? 'fr' : locale === 'en' ? 'en' : 'es') as 'es' | 'fr' | 'en'
  const { company, pendingObligations, isEligible } = data

  return (
    <Card
      className={`p-4 transition-shadow ${
        isEligible
          ? 'cursor-pointer hover:shadow-md border-border'
          : 'opacity-60 cursor-not-allowed border-muted'
      }`}
      onClick={() => isEligible && onSelect(company)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0 flex-1">
          <Building2 className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" />
          <div className="min-w-0">
            <p className="font-medium text-sm truncate">{company.legalName}</p>
            <p className="text-xs text-muted-foreground truncate">
              {company.registrationNumber || company.taxId}
              {company.cityName && ` · ${company.cityName}`}
              {company.zoneCode && ` (${company.zoneCode})`}
            </p>
            {isEligible ? (
              pendingObligations > 0 ? (
                <div className="flex items-center gap-1 mt-1">
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                  <span className="text-xs text-amber-600 font-medium">
                    {pendingObligations} {labels.pending[lang]}
                  </span>
                </div>
              ) : (
                <div className="flex items-center gap-1 mt-1">
                  <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                  <span className="text-xs text-green-600">{labels.upToDate[lang]}</span>
                </div>
              )
            ) : (
              <div className="flex items-center gap-1 mt-1">
                <XCircle className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">{labels.notEligible[lang]}</span>
              </div>
            )}
          </div>
        </div>
        {isEligible && (
          <Button
            size="sm"
            variant="outline"
            className="shrink-0"
            onClick={(e) => { e.stopPropagation(); onSelect(company) }}
          >
            {labels.pay[lang]} →
          </Button>
        )}
      </div>
    </Card>
  )
}
