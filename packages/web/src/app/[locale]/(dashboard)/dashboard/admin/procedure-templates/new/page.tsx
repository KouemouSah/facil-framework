'use client'

/**
 * Procedure Template Creation Page
 *
 * @module dashboard/admin/procedure-templates/new
 */

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { ArrowLeft, Save, ListOrdered, Plus } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import templatesAPI from '@/modules/templates/services/api'
import type { ProcedureTemplateCreate } from '@/types/fiscal-service'

export default function NewProcedureTemplatePage() {
  const locale = useLocale()
  const router = useRouter()
  const tAdmin = useTranslations('admin')
  const tCommon = useTranslations('common')
  const { toast } = useToast()

  const t = (key: string) => tAdmin(`templates.${key}`)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formData, setFormData] = useState<ProcedureTemplateCreate>({
    templateCode: '',
    nameEs: '',
    descriptionEs: '',
    category: '',
    isActive: true,
  })

  const handleSubmit = async (e: React.FormEvent, redirectToAddSteps: boolean = false) => {
    e.preventDefault()
    setIsSubmitting(true)

    try {
      const createdTemplate = await templatesAPI.procedures.create(formData)
      toast({
        title: t('successTitle'),
        description: t('procedureCreated'),
      })

      if (redirectToAddSteps) {
        // Redirect to add steps page
        router.push(`/${locale}/dashboard/admin/procedure-templates/${createdTemplate.id}/steps/new`)
      } else {
        // Redirect to edit page where user can manage steps
        router.push(`/${locale}/dashboard/admin/procedure-templates/${createdTemplate.id}/edit`)
      }
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: err instanceof Error ? err.message : 'Error creating template',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleSaveAndAddSteps = async () => {
    // Validate required fields
    if (!formData.templateCode || !formData.nameEs) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: t('requiredFieldsMissing'),
      })
      return
    }

    // Create a fake event to pass to handleSubmit
    const fakeEvent = { preventDefault: () => {} } as React.FormEvent
    await handleSubmit(fakeEvent, true)
  }

  const handleInputChange = (field: keyof ProcedureTemplateCreate, value: string | boolean) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => router.push(`/${locale}/dashboard/admin/procedure-templates`)}
        >
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold">{t('createProcedureTemplate')}</h1>
          <p className="text-muted-foreground">{t('createProcedureSubtitle')}</p>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ListOrdered className="h-5 w-5" />
              {t('procedureInfo')}
            </CardTitle>
            <CardDescription>{t('procedureInfoDescription')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Template Code */}
            <div className="space-y-2">
              <Label htmlFor="templateCode">{t('templateCode')} *</Label>
              <Input
                id="templateCode"
                value={formData.templateCode}
                onChange={(e) => handleInputChange('templateCode', e.target.value)}
                placeholder="PROC_001"
                required
              />
            </div>

            {/* Procedure Name */}
            <div className="space-y-2">
              <Label htmlFor="nameEs">{t('procedureName')} *</Label>
              <Input
                id="nameEs"
                value={formData.nameEs}
                onChange={(e) => handleInputChange('nameEs', e.target.value)}
                placeholder={t('procedureNamePlaceholder')}
                required
              />
            </div>

            {/* Description */}
            <div className="space-y-2">
              <Label htmlFor="descriptionEs">{t('description')}</Label>
              <Textarea
                id="descriptionEs"
                value={formData.descriptionEs || ''}
                onChange={(e) => handleInputChange('descriptionEs', e.target.value)}
                placeholder={t('descriptionPlaceholder')}
                rows={3}
              />
            </div>

            {/* Category */}
            <div className="space-y-2">
              <Label htmlFor="category">{t('category')}</Label>
              <Input
                id="category"
                value={formData.category || ''}
                onChange={(e) => handleInputChange('category', e.target.value)}
                placeholder={t('categoryPlaceholder')}
              />
            </div>

            {/* Is Active */}
            <div className="flex items-center justify-between rounded-lg border p-4">
              <div className="space-y-0.5">
                <Label>{t('activeStatus')}</Label>
                <p className="text-sm text-muted-foreground">{t('activeStatusDescription')}</p>
              </div>
              <Switch
                checked={formData.isActive}
                onCheckedChange={(checked) => handleInputChange('isActive', checked)}
              />
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-4 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.push(`/${locale}/dashboard/admin/procedure-templates`)}
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

      {/* Procedure Steps Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <ListOrdered className="h-5 w-5" />
                {t('procedureSteps')}
              </CardTitle>
              <CardDescription>
                0 {t('steps')}
              </CardDescription>
            </div>
            <Button size="sm" onClick={handleSaveAndAddSteps} disabled={isSubmitting}>
              <Plus className="h-4 w-4 mr-2" />
              {t('addStep')}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center gap-4 py-12 text-center">
            <ListOrdered className="h-12 w-12 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">{t('noSteps')}</p>
            <Button size="sm" onClick={handleSaveAndAddSteps} disabled={isSubmitting}>
              <Plus className="h-4 w-4 mr-2" />
              {t('addStep')}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
