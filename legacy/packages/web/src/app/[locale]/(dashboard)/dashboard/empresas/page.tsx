'use client'

/**
 * Mis Empresas — Citizen company management
 *
 * List all companies owned by the citizen with license status,
 * obligation progress, and quick actions (pay, view detail).
 *
 * @route /[locale]/dashboard/empresas
 */

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  Building2, Plus, MapPin, RefreshCw, ArrowRight,
  AlertTriangle, CheckCircle2, Clock, DollarSign, Shield,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useTranslations } from 'next-intl'
import { useLocale } from 'next-intl'
import { exportToExcel } from '@/core/utils/export'
import { useQuery } from '@tanstack/react-query'
import { bundleWorkflowApi } from '@/modules/bundle-workflow/services/bundle-workflow-api'

const STATUS_CONFIG: Record<string, { color: string; icon: typeof Clock }> = {
  open:     { color: 'bg-blue-100 text-blue-800', icon: Clock },
  partial:  { color: 'bg-yellow-100 text-yellow-800', icon: DollarSign },
  complete: { color: 'bg-green-100 text-green-800', icon: CheckCircle2 },
  overdue:  { color: 'bg-red-100 text-red-800', icon: AlertTriangle },
  closed:   { color: 'bg-gray-100 text-gray-800', icon: Shield },
}

export default function MisEmpresasPage() {
  const t = useTranslations('empresas')
  const locale = useLocale()
  const router = useRouter()
  const [year] = useState(new Date().getFullYear())

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['my-companies', year],
    queryFn: () => bundleWorkflowApi.getMyCompanies(year),
    staleTime: 60_000,
  })

  const companies = data?.companies ?? []

  return (
    <div className="space-y-6 p-4 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Building2 className="h-6 w-6" />
            {t('title')}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">{t('subtitle')}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => {
            if (!companies.length) return
            exportToExcel(companies.map(item => ({
              Empresa: item.company.legalName,
              Registro: item.company.registrationNumber || item.company.nif || '',
              Zona: item.company.zoneCode || '',
              Ciudad: item.company.cityName || '',
              Comercio: item.company.commerceType || '',
              'Estado Licencia': item.licenseStatus || 'Sin licencia',
              'Obl. Pendientes': item.pendingObligations || 0,
              'Año Fiscal': item.fiscalYear,
            })), { fileName: `mis_empresas_${new Date().toISOString().slice(0,10)}`, sheetName: 'Empresas' })
          }} disabled={!companies.length}>
            <Building2 className="h-4 w-4 mr-1" /> Excel
          </Button>
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 mr-1 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
          <Link href={`/${locale}/dashboard/bundle-payment?mode=new`}>
            <Button size="sm" className="gap-2">
              <Plus className="h-4 w-4" />
              {t('newCompany')}
            </Button>
          </Link>
        </div>
      </div>

      {/* Company cards */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2].map(i => <Skeleton key={i} className="h-48 w-full" />)}
        </div>
      ) : companies.length === 0 ? (
        <Card className="py-16">
          <CardContent className="text-center space-y-4">
            <Building2 className="h-12 w-12 mx-auto text-muted-foreground opacity-30" />
            <div>
              <p className="text-lg font-medium">{t('noCompanies')}</p>
              <p className="text-sm text-muted-foreground mt-1">{t('noCompaniesDesc')}</p>
            </div>
            <Link href={`/${locale}/dashboard/bundle-payment?mode=new`}>
              <Button className="gap-2 mt-2">
                <Plus className="h-4 w-4" />
                {t('startBundle')}
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {companies.map((item) => {
            const c = item.company
            const status = item.licenseStatus || 'open'
            const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.open
            const StatusIcon = cfg.icon
            const pending = item.pendingObligations || 0

            return (
              <Card
                key={c.id}
                className="hover:border-primary/50 transition-colors cursor-pointer group"
                onClick={() => router.push(`/${locale}/dashboard/empresas/${c.id}`)}
              >
                <CardContent className="p-4 space-y-3">
                  {/* Company header */}
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      <Building2 className="h-5 w-5 text-muted-foreground shrink-0" />
                      <div className="min-w-0">
                        <p className="font-semibold truncate">{c.legalName}</p>
                        <p className="text-xs text-muted-foreground font-mono">
                          {c.registrationNumber || c.nif || '—'}
                        </p>
                      </div>
                    </div>
                    <Badge className={`text-[10px] gap-1 shrink-0 ${cfg.color}`}>
                      <StatusIcon className="h-3 w-3" />
                      {t(status)}
                    </Badge>
                  </div>

                  {/* Location + type */}
                  <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                    {c.zoneCode && (
                      <span className="flex items-center gap-1">
                        <MapPin className="h-3 w-3" /> {c.zoneCode}
                      </span>
                    )}
                    {c.cityName && <span>{c.cityName}</span>}
                    {c.commerceType && (
                      <Badge variant="secondary" className="text-[10px] h-4">{c.commerceType}</Badge>
                    )}
                  </div>

                  {/* License status */}
                  {item.licenseId ? (
                    <div className="space-y-1.5">
                      <div className="flex justify-between text-xs">
                        <span className="text-muted-foreground">{t('fiscalYear')} {item.fiscalYear}</span>
                        <span className="text-muted-foreground">{t('expiryDate')}: 31/12/{item.fiscalYear}</span>
                      </div>
                      {pending > 0 && (
                        <div className="flex items-center gap-2 text-xs">
                          <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                          <span className="text-amber-700 font-medium">
                            {pending} {t('filterPending').toLowerCase()}
                          </span>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground italic">{t('noLicense')}</p>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2 pt-1 border-t">
                    <Button
                      variant="outline" size="sm" className="flex-1 h-8 text-xs gap-1"
                      onClick={(e) => { e.stopPropagation(); router.push(`/${locale}/dashboard/empresas/${c.id}`) }}
                    >
                      {t('viewDetail')} <ArrowRight className="h-3 w-3" />
                    </Button>
                    {item.isEligible && (
                      <Button
                        size="sm" className="flex-1 h-8 text-xs gap-1"
                        onClick={(e) => { e.stopPropagation(); router.push(`/${locale}/dashboard/bundle-payment?companyId=${c.id}`) }}
                      >
                        <DollarSign className="h-3 w-3" /> {t('payTaxes')}
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
