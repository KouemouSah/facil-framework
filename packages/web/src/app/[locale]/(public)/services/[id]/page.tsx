'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Separator } from "@/components/ui/separator"
import {
  AlertCircle, Loader2, ArrowLeft, Calculator, ExternalLink,
  FileText, ListChecks, Building2, Clock, DollarSign, Info, MapPin, Package
} from "lucide-react"
import Link from "next/link"
import Breadcrumb from "@/components/ui/breadcrumb"
import {
  getServiceDetails,
  formatPrice,
  getServiceTypeLabel,
  getCalculationMethodLabel,
  type ServiceDetailsResponse,
} from "@/core/api/serviceDetails"
import { bundleApi } from "@/modules/fiscal-services/services/bundle-api"
import type { ServiceBundleBadge } from "@/types/service-bundle"
import { getLocalizedName } from '@/core/utils/i18n-helpers'

/**
 * Service Details Page
 * Layout with 2 distinct blocks:
 * - Block 1 (Left): Description, Pricing, Duration, Ministry
 * - Block 2 (Right): Documents + Procedures (numbered lists with icons)
 */
export default function ServiceDetailsPage() {
  const params = useParams()
  const router = useRouter()
  const serviceId = parseInt(params?.id as string)
  const locale = (params?.locale as string) || 'es'

  const t = useTranslations('serviceDetails')

  // State
  const [service, setService] = useState<ServiceDetailsResponse | null>(null)
  const [bundles, setBundles] = useState<ServiceBundleBadge[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  // Fetch service details + bundles in parallel
  useEffect(() => {
    async function fetchDetails() {
      if (!serviceId || isNaN(serviceId)) {
        setError('Invalid service ID')
        setLoading(false)
        return
      }

      try {
        setLoading(true)
        setError(null)
        const [data, bundleData] = await Promise.all([
          getServiceDetails(serviceId, locale),
          bundleApi.getBundlesForService(serviceId).catch(() => []),
        ])
        setService(data)
        setBundles(bundleData)
      } catch (err) {
        console.error('Failed to fetch service details:', err)
        setError(err instanceof Error ? err.message : 'Failed to load service details')
      } finally {
        setLoading(false)
      }
    }

    fetchDetails()
  }, [serviceId, locale, retryCount])

  // Loading state
  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex justify-center items-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <span className="ml-3 text-muted-foreground">{t('loading')}</span>
        </div>
      </div>
    )
  }

  // Error state
  if (error || !service) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Alert variant="destructive" className="max-w-2xl mx-auto">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {error || t('errorLoading')}
          </AlertDescription>
        </Alert>
        <div className="flex justify-center gap-3 mt-6">
          <Button onClick={() => router.back()} variant="outline">
            <ArrowLeft className="h-4 w-4 mr-2" />
            {t('backToServices')}
          </Button>
          <Button onClick={() => setRetryCount(c => c + 1)} variant="default">
            {t('retry') || 'Reintentar'}
          </Button>
        </div>
      </div>
    )
  }

  // Calculate total estimated minutes from procedures
  const getTotalEstimatedMinutes = () => {
    if (!service.procedures || service.procedures.length === 0) return null
    const total = service.procedures.reduce((sum, proc) => {
      return sum + (proc.total_estimated_minutes || 0)
    }, 0)
    return total > 0 ? total : null
  }

  // Get location and office hours from first procedure step
  const getLocationInfo = () => {
    if (!service.procedures || service.procedures.length === 0) return null
    for (const proc of service.procedures) {
      if (proc.steps && proc.steps.length > 0) {
        for (const step of proc.steps) {
          if (step.location_address || step.office_hours) {
            return {
              location_address: step.location_address,
              office_hours: step.office_hours
            }
          }
        }
      }
    }
    return null
  }

  /**
   * Render pricing based on 4 cases
   */
  const renderPricing = () => {
    const expeditionPrice = service.pricing.expedition_price
    const renewalPrice = service.pricing.renewal_price
    const calculationMethod = service.pricing.calculation_method

    const isFormulaBased = calculationMethod === 'formula_based' ||
                           calculationMethod === 'percentage_based' ||
                           calculationMethod === 'unit_based' ||
                           calculationMethod === 'tiered_rates' ||
                           calculationMethod === 'fixed_plus_unit'

    // Case 1: Free service
    if (expeditionPrice === 0 && renewalPrice === 0 && !isFormulaBased) {
      return (
        <Badge variant="secondary" className="bg-green-100 text-green-800 text-lg px-4 py-2">
          {t('free')}
        </Badge>
      )
    }

    // Case 2: Formula-based pricing
    if (isFormulaBased) {
      return (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">{t('calculationMethod')}</p>
          <p className="font-medium">
            {getCalculationMethodLabel(calculationMethod, locale)}
          </p>
          <Button
            onClick={() => router.push(`/${locale}/calculateur?service_id=${service.id}`)}
            className="w-full"
          >
            <Calculator className="h-4 w-4 mr-2" />
            {t('calculate')}
          </Button>
        </div>
      )
    }

    // Case 3: Same price for expedition and renewal
    if (expeditionPrice === renewalPrice && expeditionPrice > 0) {
      return (
        <p className="text-2xl font-bold text-primary">
          {formatPrice(expeditionPrice, service.pricing.currency, locale)}
        </p>
      )
    }

    // Case 4: Different prices - side by side with separator and distinct colors
    return (
      <div className="flex flex-wrap items-center gap-4">
        <div>
          <p className="text-sm text-muted-foreground">{t('firstExpedition')}</p>
          <p className="text-xl font-bold text-emerald-600">
            {formatPrice(expeditionPrice, service.pricing.currency, locale)}
          </p>
        </div>
        {renewalPrice > 0 && (
          <>
            <span className="text-2xl text-muted-foreground font-light">|</span>
            <div>
              <p className="text-sm text-muted-foreground">{t('renewalPrice')}</p>
              <p className="text-xl font-bold text-blue-600">
                {formatPrice(renewalPrice, service.pricing.currency, locale)}
              </p>
            </div>
          </>
        )}
      </div>
    )
  }

  const totalMinutes = getTotalEstimatedMinutes()
  const locationInfo = getLocationInfo()

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Breadcrumbs */}
      <Breadcrumb
        items={[
          { label: t('services'), href: `/${locale}/services` },
          { label: service.category?.name || t('category') },
          { label: service.name }
        ]}
        className="mb-6"
      />

      {/* Back button */}
      <Button
        variant="ghost"
        onClick={() => router.back()}
        className="mb-6"
      >
        <ArrowLeft className="h-4 w-4 mr-2" />
        {t('backToServices')}
      </Button>

      {/* Header Section */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">{service.name}</h1>
        <div className="flex flex-wrap items-center gap-2 mt-2">
          <Badge variant="secondary">
            {getServiceTypeLabel(service.service_type, locale)}
          </Badge>
          {bundles.map((b) => (
            <Link key={b.id} href={`/${locale}/licencias-comerciales`}>
              <Badge variant="outline" className="cursor-pointer hover:bg-primary/10 transition-colors gap-1">
                <Package className="h-3 w-3" />
                {t('includedInBundle', { bundle: getLocalizedName(b as unknown as Record<string, unknown>, locale) })}
              </Badge>
            </Link>
          ))}
        </div>
      </div>

      {/* Main Content: 2 Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

        {/* BLOCK 1 (LEFT): Description, Pricing, Duration, Ministry */}
        <Card>
          <CardContent className="p-6 space-y-4">
            {/* Description */}
            {service.description && (
              <div className="flex gap-3">
                <Info className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-lg font-semibold flex items-center gap-2 mb-2">{t('description')}</h3>
                  <p className="text-muted-foreground">{service.description}</p>
                </div>
              </div>
            )}

            {/* Pricing Section */}
            <div className="flex gap-3">
              <DollarSign className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <h3 className="text-lg font-semibold flex items-center gap-2 mb-3">{t('pricing')}</h3>
                {renderPricing()}
              </div>
            </div>

            <Separator />

            {/* Processing Time / Duration - Always show */}
            <div className="flex gap-3">
              <Clock className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-lg font-semibold flex items-center gap-2 mb-1">{t('estimatedDuration')}</h3>
                <p className="text-muted-foreground">
                  {totalMinutes
                    ? `${totalMinutes} ${t('minutes')}`
                    : service.processing_time_days
                      ? `${service.processing_time_days} ${t('days')}`
                      : t('notSpecified')
                  }
                </p>
              </div>
            </div>

            <Separator />

            {/* Ministry - Always show */}
            <div className="flex gap-3">
              <Building2 className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <h3 className="text-lg font-semibold mb-1">{t('ministry')}</h3>
                <p className="text-sm text-muted-foreground">{service.ministry?.name || t('notSpecified')}</p>

                <div className="mt-3 space-y-1 text-sm text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <MapPin className="h-4 w-4" />
                    <span className="font-medium">{t('location')}:</span>
                    <span>{locationInfo?.location_address || t('comingSoon')}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4" />
                    <span className="font-medium">{t('openingHours')}:</span>
                    <span>{locationInfo?.office_hours || t('comingSoon')}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Legal Reference */}
            {service.legal_reference && (
              <>
                <Separator />
                <div className="pt-2">
                  <h3 className="text-lg font-semibold mb-2">{t('legalReference')}</h3>
                  <p className="text-sm text-muted-foreground">{service.legal_reference}</p>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* BLOCK 2 (RIGHT): Documents + Procedures */}
        <div className="space-y-6">
          {/* Documents Section */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg font-semibold flex items-center gap-2">
                <FileText className="h-5 w-5 text-primary" />
                {t('requiredDocuments')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {service.documents.length > 0 ? (
                <div className="space-y-2">
                  {/* Split document names by comma and display as numbered list */}
                  {service.documents.flatMap((doc) =>
                    doc.name.split(',').map((item) => item.trim()).filter((item) => item.length > 0)
                  ).map((docName, index) => (
                    <div key={`doc-${index}`} className="flex gap-3 text-sm">
                      <span className="font-semibold text-primary min-w-[24px]">{index + 1}.</span>
                      <span>{docName}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground text-sm">{t('noDocuments')}</p>
              )}
            </CardContent>
          </Card>

          {/* Procedures Section */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg font-semibold flex items-center gap-2">
                <ListChecks className="h-5 w-5 text-primary" />
                {t('procedures')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {service.procedures.length > 0 ? (
                <div className="space-y-2">
                  {/* Split procedure step descriptions by comma and display as numbered list */}
                  {(() => {
                    // Collect all step descriptions, split by comma
                    const allSteps = service.procedures.flatMap((procedure) =>
                      procedure.steps && procedure.steps.length > 0
                        ? procedure.steps.flatMap((step) =>
                            step.description.split(',').map((item) => item.trim()).filter((item) => item.length > 0)
                          )
                        : procedure.name.split(',').map((item) => item.trim()).filter((item) => item.length > 0)
                    )
                    return allSteps.map((stepDesc, index) => (
                      <div key={`step-${index}`} className="flex gap-3 text-sm">
                        <span className="font-semibold text-primary min-w-[24px]">{index + 1}.</span>
                        <span>{stepDesc}</span>
                      </div>
                    ))
                  })()}
                </div>
              ) : (
                <p className="text-muted-foreground text-sm">{t('noProcedures')}</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* CTA: Start Request */}
        <div className="mt-8 text-center">
          <Button
            size="lg"
            className="gap-2 px-8"
            onClick={() => router.push(`/${locale}/auth`)}
          >
            <ExternalLink className="h-4 w-4" />
            {t('startRequest')}
          </Button>
          <p className="text-xs text-muted-foreground mt-2">{t('loginRequired')}</p>
        </div>
      </div>
    </div>
  )
}
