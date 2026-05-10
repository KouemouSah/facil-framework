'use client'

/**
 * Procedure Step Creation Page
 *
 * @module dashboard/admin/procedure-templates/[id]/steps/new
 */

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { ArrowLeft, Save, ListOrdered, RefreshCw } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import templatesAPI from '@/modules/templates/services/api'
import type { ProcedureStepCreate, ProcedureStep } from '@/types/fiscal-service'

export default function NewProcedureStepPage() {
  const locale = useLocale()
  const router = useRouter()
  const params = useParams()
  const templateId = params.id as string
  const tAdmin = useTranslations('admin')
  const tCommon = useTranslations('common')
  const { toast } = useToast()

  const t = (key: string, params?: Record<string, string | number>) =>
    tAdmin(`templates.${key}`, params)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isLoadingSteps, setIsLoadingSteps] = useState(true)
  const [nextStepNumber, setNextStepNumber] = useState(1)
  const [formData, setFormData] = useState<Omit<ProcedureStepCreate, 'templateId'>>({
    stepNumber: 1,
    descriptionEs: '',
    instructionsEs: '',
    estimatedDurationMinutes: undefined,
    locationAddress: '',
    officeHours: '',
    requiresAppointment: false,
    isOptional: false,
  })

  useEffect(() => {
    const fetchSteps = async () => {
      try {
        const steps = await templatesAPI.steps.list(templateId)
        const maxStep = steps.length > 0 ? Math.max(...steps.map((s: ProcedureStep) => s.stepNumber)) : 0
        setNextStepNumber(maxStep + 1)
        setFormData(prev => ({ ...prev, stepNumber: maxStep + 1 }))
      } catch (err) {
        console.error('Error fetching steps:', err)
      } finally {
        setIsLoadingSteps(false)
      }
    }

    fetchSteps()
  }, [templateId])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)

    try {
      await templatesAPI.steps.create(templateId, {
        ...formData,
        templateId: parseInt(templateId),
      })
      toast({
        title: t('successTitle'),
        description: t('stepCreated'),
      })
      router.push(`/${locale}/dashboard/admin/procedure-templates/${templateId}`)
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: err instanceof Error ? err.message : 'Error creating step',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleInputChange = (field: keyof Omit<ProcedureStepCreate, 'templateId'>, value: string | number | boolean | undefined) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  if (isLoadingSteps) {
    return (
      <div className="flex items-center justify-center py-24">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => router.push(`/${locale}/dashboard/admin/procedure-templates/${templateId}`)}
        >
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold">{t('addStep')}</h1>
          <p className="text-muted-foreground">{t('addStepSubtitle')}</p>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ListOrdered className="h-5 w-5" />
              {t('stepInfo')}
            </CardTitle>
            <CardDescription>{t('stepInfoDescription')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Step Number */}
            <div className="space-y-2">
              <Label htmlFor="stepNumber">{t('stepNumber')} *</Label>
              <Input
                id="stepNumber"
                type="number"
                min={1}
                value={formData.stepNumber}
                onChange={(e) => handleInputChange('stepNumber', parseInt(e.target.value) || 1)}
                required
              />
              <p className="text-xs text-muted-foreground">{t('stepNumberHint', { next: nextStepNumber })}</p>
            </div>

            {/* Description */}
            <div className="space-y-2">
              <Label htmlFor="descriptionEs">{t('stepDescription')} *</Label>
              <Textarea
                id="descriptionEs"
                value={formData.descriptionEs}
                onChange={(e) => handleInputChange('descriptionEs', e.target.value)}
                placeholder={t('stepDescriptionPlaceholder')}
                rows={2}
                required
              />
            </div>

            {/* Instructions */}
            <div className="space-y-2">
              <Label htmlFor="instructionsEs">{t('stepInstructions')}</Label>
              <Textarea
                id="instructionsEs"
                value={formData.instructionsEs || ''}
                onChange={(e) => handleInputChange('instructionsEs', e.target.value)}
                placeholder={t('stepInstructionsPlaceholder')}
                rows={3}
              />
            </div>

            {/* Estimated Duration */}
            <div className="space-y-2">
              <Label htmlFor="estimatedDurationMinutes">{t('estimatedDuration')}</Label>
              <Input
                id="estimatedDurationMinutes"
                type="number"
                min={0}
                value={formData.estimatedDurationMinutes || ''}
                onChange={(e) => handleInputChange('estimatedDurationMinutes', e.target.value ? parseInt(e.target.value) : undefined)}
                placeholder="30"
              />
              <p className="text-xs text-muted-foreground">{t('durationInMinutes')}</p>
            </div>

            {/* Location Address */}
            <div className="space-y-2">
              <Label htmlFor="locationAddress">{t('locationAddress')}</Label>
              <Input
                id="locationAddress"
                value={formData.locationAddress || ''}
                onChange={(e) => handleInputChange('locationAddress', e.target.value)}
                placeholder={t('locationAddressPlaceholder')}
              />
            </div>

            {/* Office Hours */}
            <div className="space-y-2">
              <Label htmlFor="officeHours">{t('officeHours')}</Label>
              <Input
                id="officeHours"
                value={formData.officeHours || ''}
                onChange={(e) => handleInputChange('officeHours', e.target.value)}
                placeholder="08:00 - 16:00"
              />
            </div>

            {/* Requires Appointment */}
            <div className="flex items-center justify-between rounded-lg border p-4">
              <div className="space-y-0.5">
                <Label>{t('requiresAppointment')}</Label>
                <p className="text-sm text-muted-foreground">{t('requiresAppointmentDescription')}</p>
              </div>
              <Switch
                checked={formData.requiresAppointment}
                onCheckedChange={(checked) => handleInputChange('requiresAppointment', checked)}
              />
            </div>

            {/* Is Optional */}
            <div className="flex items-center justify-between rounded-lg border p-4">
              <div className="space-y-0.5">
                <Label>{t('optionalStep')}</Label>
                <p className="text-sm text-muted-foreground">{t('optionalStepDescription')}</p>
              </div>
              <Switch
                checked={formData.isOptional}
                onCheckedChange={(checked) => handleInputChange('isOptional', checked)}
              />
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-4 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.push(`/${locale}/dashboard/admin/procedure-templates/${templateId}`)}
              >
                {tCommon('cancel')}
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                <Save className="h-4 w-4 mr-2" />
                {isSubmitting ? tCommon('saving') : tCommon('save')}
              </Button>
            </div>
          </CardContent>
        </Card>
      </form>
    </div>
  )
}
