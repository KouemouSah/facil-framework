'use client'

/**
 * Admin — Create Company with Auto-License
 *
 * Full-page form (not dialog) with navigation between companies.
 * Creates company + auto-generates licence + obligations in one call.
 *
 * @route /[locale]/dashboard/admin/companies/new
 */

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useToast } from '@/hooks/use-toast'
import {
  ArrowLeft, Building2, CheckCircle, Loader2,
  FileText, Plus,
} from 'lucide-react'
import { companiesAdminApi } from '@/modules/companies/services/api'

const COMMERCE_TYPES = [
  { value: 'abaceria', label: 'Abacerias, Factorias y Comercio en General' },
  { value: 'bar_restaurante', label: 'Bares y Restaurantes' },
  { value: 'cafeteria_pasteleria', label: 'Cafeterias-Pastelerias, Panaderias y Snack Bar' },
  { value: 'carpinteria', label: 'Carpinterias en General' },
  { value: 'clinica_farmacia', label: 'Clinicas, Farmacias y Similares' },
  { value: 'discoteca', label: 'Discotecas y Similares' },
  { value: 'ferreteria', label: 'Ferreterias' },
  { value: 'taller_artesanal', label: 'Talleres y Tiendas Artesanales' },
  { value: 'taller_bloqueria', label: 'Talleres y Bloquerias en General' },
  { value: 'video_club', label: 'Video Clubs y Similares' },
] as const

const ZONE_CODES = [
  'A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'C1', 'C2', 'C3', 'D1', 'D2', 'D3',
] as const

const FORMA_JURIDICA_OPTIONS = [
  'SOCIEDAD LIMITADA', 'SOCIEDAD ANONIMA', 'COOPERATIVA',
  'AUTONOMO', 'EMPRESA INDIVIDUAL', 'ASOCIACION', 'FUNDACION',
] as const

interface CreationResult {
  company_id: string
  company_name: string
  license_id: string
  license_status: string
  obligations_count: number
  total_amount: number
  zone_code: string
  fiscal_year: number
  source: string
}

export default function AdminCreateCompanyPage() {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('admin.companies.createPage')
  const { toast } = useToast()

  // Form state
  const [legalName, setLegalName] = useState('')
  const [commerceType, setCommerceType] = useState('')
  const [zoneCode, setZoneCode] = useState('')
  const [representanteLegal, setRepresentanteLegal] = useState('')
  const [nif, setNif] = useState('')
  const [registrationNumber, setRegistrationNumber] = useState('')
  const [formaJuridica, setFormaJuridica] = useState('')
  const [address, setAddress] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [objetoSocial, setObjetoSocial] = useState('')
  const [employeeCount, setEmployeeCount] = useState('')

  // UI state
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<CreationResult | null>(null)
  const [error, setError] = useState('')

  // Recently created companies for navigation
  const [recentIds, setRecentIds] = useState<string[]>([])

  const canSubmit = legalName.trim().length >= 2 && commerceType && zoneCode
    && representanteLegal.trim().length >= 2 && (nif || registrationNumber)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setSubmitting(true)
    setError('')
    setResult(null)

    try {
      const res = await companiesAdminApi.createWithLicense({
        legalName: legalName.trim(),
        commerceType,
        zoneCode,
        representanteLegal: representanteLegal.trim(),
        nif: nif || undefined,
        registrationNumber: registrationNumber || undefined,
        formaJuridica: formaJuridica || undefined,
        address: address || undefined,
        phone: phone || undefined,
        email: email || undefined,
        objetoSocial: objetoSocial || undefined,
        employeeCount: employeeCount ? parseInt(employeeCount) : undefined,
      })
      setResult(res)
      setRecentIds(prev => [res.company_id, ...prev])
      toast({
        title: t('successToast'),
        description: `${res.company_name} — ${res.obligations_count} obligaciones, ${res.total_amount.toLocaleString()} XAF`,
      })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || 'Error al crear la empresa'
      setError(msg)
      toast({ title: 'Error', description: msg, variant: 'destructive' })
    } finally {
      setSubmitting(false)
    }
  }

  const handleReset = () => {
    setLegalName('')
    setCommerceType('')
    setZoneCode('')
    setRepresentanteLegal('')
    setNif('')
    setRegistrationNumber('')
    setFormaJuridica('')
    setAddress('')
    setPhone('')
    setEmail('')
    setObjetoSocial('')
    setEmployeeCount('')
    setResult(null)
    setError('')
  }

  const navigateToCompany = (id: string) => {
    router.push(`/${locale}/dashboard/admin/companies/${id}`)
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-12">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost" size="icon"
            onClick={() => router.push(`/${locale}/dashboard/admin/companies`)}
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Plus className="h-6 w-6" />
              {t('title')}
            </h1>
            <p className="text-sm text-muted-foreground">
              {t('subtitle')}
            </p>
          </div>
        </div>
        {recentIds.length > 0 && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>{recentIds.length} {t('recentCount')}</span>
            <Button
              variant="outline" size="sm"
              onClick={() => navigateToCompany(recentIds[0])}
            >
              {t('viewLast')}
            </Button>
          </div>
        )}
      </div>

      {/* Success result */}
      {result && (
        <Card className="border-green-200 bg-green-50">
          <CardContent className="pt-6">
            <div className="flex items-start gap-4">
              <CheckCircle className="h-8 w-8 text-green-600 shrink-0" />
              <div className="flex-1 space-y-2">
                <h3 className="font-semibold text-green-900">{t('successTitle')}</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Empresa</span>
                    <p className="font-medium">{result.company_name}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Zona</span>
                    <p className="font-medium">{result.zone_code}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Obligaciones</span>
                    <p className="font-medium">{result.obligations_count}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Total</span>
                    <p className="font-medium">{result.total_amount.toLocaleString()} XAF</p>
                  </div>
                </div>
                <div className="flex gap-2 pt-2">
                  <Badge variant="secondary">{result.fiscal_year}</Badge>
                  <Badge variant="outline" className="text-green-700 border-green-300">
                    {t('manualBadge')}
                  </Badge>
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <Button size="sm" onClick={() => navigateToCompany(result.company_id)}>
                  {t('viewCompany')}
                </Button>
                <Button size="sm" variant="outline" onClick={handleReset}>
                  {t('createAnother')}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit}>
        <div className="grid gap-6">
          {/* Required fields */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Building2 className="h-4 w-4" />
                {t('requiredFields')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="legalName">{t('legalName')} *</Label>
                  <Input
                    id="legalName"
                    value={legalName}
                    onChange={e => setLegalName(e.target.value)}
                    placeholder="TIENDA EJEMPLO S.L."
                    required
                    minLength={2}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="representante">{t('representanteLegal')} *</Label>
                  <Input
                    id="representante"
                    value={representanteLegal}
                    onChange={e => setRepresentanteLegal(e.target.value)}
                    placeholder="Juan Carlos Ndong Obiang"
                    required
                    minLength={2}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>{t('commerceType')} *</Label>
                  <Select value={commerceType} onValueChange={setCommerceType}>
                    <SelectTrigger>
                      <SelectValue placeholder="Seleccionar tipo" />
                    </SelectTrigger>
                    <SelectContent>
                      {COMMERCE_TYPES.map(ct => (
                        <SelectItem key={ct.value} value={ct.value}>
                          {ct.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label>{t('zone')} *</Label>
                  <Select value={zoneCode} onValueChange={setZoneCode}>
                    <SelectTrigger>
                      <SelectValue placeholder="Zona" />
                    </SelectTrigger>
                    <SelectContent>
                      {ZONE_CODES.map(z => (
                        <SelectItem key={z} value={z}>{z}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="nif">NIF</Label>
                  <Input
                    id="nif"
                    value={nif}
                    onChange={e => setNif(e.target.value)}
                    placeholder="123456789"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="regNumber">N de registro (PE-XXXX)</Label>
                  <Input
                    id="regNumber"
                    value={registrationNumber}
                    onChange={e => setRegistrationNumber(e.target.value)}
                    placeholder="PE-1234"
                  />
                </div>
              </div>

              {!nif && !registrationNumber && (
                <p className="text-sm text-amber-600">
                  * {t('identifierRequired')}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Optional fields */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <FileText className="h-4 w-4" />
                {t('optionalFields')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>{t('formaJuridica')}</Label>
                  <Select value={formaJuridica} onValueChange={setFormaJuridica}>
                    <SelectTrigger>
                      <SelectValue placeholder="Seleccionar" />
                    </SelectTrigger>
                    <SelectContent>
                      {FORMA_JURIDICA_OPTIONS.map(fj => (
                        <SelectItem key={fj} value={fj}>{fj}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="employees">{t('employees')}</Label>
                  <Input
                    id="employees" type="number" min={0}
                    value={employeeCount}
                    onChange={e => setEmployeeCount(e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="objetoSocial">{t('objetoSocial')}</Label>
                <Textarea
                  id="objetoSocial"
                  value={objetoSocial}
                  onChange={e => setObjetoSocial(e.target.value)}
                  placeholder="Descripcion de la actividad comercial"
                  rows={2}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="address">{t('address')}</Label>
                  <Input
                    id="address" value={address}
                    onChange={e => setAddress(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="phone">{t('phone')}</Label>
                  <Input
                    id="phone" value={phone}
                    onChange={e => setPhone(e.target.value)}
                    placeholder="+240..."
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="email">{t('email')}</Label>
                  <Input
                    id="email" type="email" value={email}
                    onChange={e => setEmail(e.target.value)}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Error */}
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-3">
            <Button
              type="button" variant="outline"
              onClick={() => router.push(`/${locale}/dashboard/admin/companies`)}
            >
              {t('cancel')}
            </Button>
            <Button type="submit" disabled={!canSubmit || submitting}>
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t('submitting')}
                </>
              ) : (
                <>
                  <Plus className="h-4 w-4 mr-2" />
                  {t('submit')}
                </>
              )}
            </Button>
          </div>
        </div>
      </form>

      {/* Recent companies navigation */}
      {recentIds.length > 1 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t('recentSession')} ({recentIds.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {recentIds.map((id, i) => (
                <Button
                  key={id} variant="outline" size="sm"
                  onClick={() => navigateToCompany(id)}
                >
                  <Building2 className="h-3 w-3 mr-1" />
                  Empresa {recentIds.length - i}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
