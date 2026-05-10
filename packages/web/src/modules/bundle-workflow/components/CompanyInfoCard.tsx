'use client'

import { Building2, MapPin, ShieldCheck, X } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { CompanySummary } from '../types'

interface CompanyInfoCardProps {
  company: CompanySummary
  locale: string
  onClear?: () => void
  compact?: boolean
}

const labels = {
  zone: { es: 'Zona', fr: 'Zone', en: 'Zone' },
  verified: { es: 'Verificada', fr: 'Verifiee', en: 'Verified' },
  change: { es: 'Cambiar', fr: 'Changer', en: 'Change' },
} as const

export function CompanyInfoCard({ company, locale, onClear, compact }: CompanyInfoCardProps) {
  const lang = (locale === 'fr' ? 'fr' : locale === 'en' ? 'en' : 'es') as 'es' | 'fr' | 'en'

  if (compact) {
    return (
      <div className="flex items-center gap-2 text-sm bg-muted/50 rounded-lg px-3 py-2">
        <Building2 className="h-4 w-4 text-muted-foreground shrink-0" />
        <span className="font-medium truncate">{company.legalName}</span>
        <span className="text-muted-foreground">·</span>
        <span className="text-muted-foreground truncate">
          {company.registrationNumber || company.taxId}
        </span>
        {company.zoneCode && (
          <Badge variant="outline" className="shrink-0 text-xs">
            {company.zoneCode}
          </Badge>
        )}
        {onClear && (
          <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0 ml-auto" onClick={onClear}>
            <X className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>
    )
  }

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
            <Building2 className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h3 className="font-semibold text-base">{company.legalName}</h3>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-sm text-muted-foreground">
              <span>{company.registrationNumber || company.nif || company.taxId}</span>
              {company.commerceType && (
                <span className="capitalize">{company.commerceType.replace(/_/g, ' ')}</span>
              )}
            </div>
            {(company.cityName || company.zoneCode) && (
              <div className="flex items-center gap-1 mt-1 text-sm text-muted-foreground">
                <MapPin className="h-3.5 w-3.5" />
                <span>
                  {company.cityName}
                  {company.zoneCode && ` (${labels.zone[lang]} ${company.zoneCode})`}
                </span>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {company.isVerified && (
            <Badge variant="default" className="gap-1">
              <ShieldCheck className="h-3 w-3" />
              {labels.verified[lang]}
            </Badge>
          )}
          {onClear && (
            <Button variant="outline" size="sm" onClick={onClear}>
              {labels.change[lang]}
            </Button>
          )}
        </div>
      </div>
    </Card>
  )
}
