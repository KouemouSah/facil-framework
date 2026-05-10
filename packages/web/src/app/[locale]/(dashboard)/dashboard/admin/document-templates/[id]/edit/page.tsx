'use client'

/**
 * Document Template Edit Page
 *
 * @module dashboard/admin/document-templates/[id]/edit
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
import { ArrowLeft, Save, FileText, RefreshCw, AlertTriangle } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import templatesAPI from '@/modules/templates/services/api'
import type { DocumentTemplate, DocumentTemplateUpdate } from '@/types/fiscal-service'

export default function EditDocumentTemplatePage() {
  const locale = useLocale()
  const router = useRouter()
  const params = useParams()
  const templateId = params.id as string
  const tAdmin = useTranslations('admin')
  const tCommon = useTranslations('common')
  const { toast } = useToast()

  const t = (key: string) => tAdmin(`templates.${key}`)

  const [template, setTemplate] = useState<DocumentTemplate | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [formData, setFormData] = useState<DocumentTemplateUpdate>({
    documentNameEs: '',
    descriptionEs: '',
    category: '',
    validityDurationMonths: undefined,
    validityNotes: '',
    isActive: true,
  })

  useEffect(() => {
    const fetchTemplate = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const data = await templatesAPI.documents.get(templateId)
        setTemplate(data)
        setFormData({
          documentNameEs: data.documentNameEs,
          descriptionEs: data.descriptionEs || '',
          category: data.category || '',
          validityDurationMonths: data.validityDurationMonths,
          validityNotes: data.validityNotes || '',
          isActive: data.isActive,
        })
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Error loading template'
        setError(errorMessage)
        toast({
          variant: 'destructive',
          title: t('errorTitle'),
          description: errorMessage,
        })
      } finally {
        setIsLoading(false)
      }
    }

    fetchTemplate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [templateId, toast])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)

    try {
      await templatesAPI.documents.update(templateId, formData)
      toast({
        title: t('successTitle'),
        description: t('documentUpdated'),
      })
      router.push(`/${locale}/dashboard/admin/document-templates/${templateId}`)
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: err instanceof Error ? err.message : 'Error updating template',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleInputChange = (field: keyof DocumentTemplateUpdate, value: string | number | boolean | undefined) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">{t('loading')}</span>
      </div>
    )
  }

  if (error || !template) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
        <AlertTriangle className="h-12 w-12 text-destructive" />
        <p className="text-sm text-muted-foreground">{error || 'Template not found'}</p>
        <Button onClick={() => router.push(`/${locale}/dashboard/admin/document-templates`)} variant="outline">
          <ArrowLeft className="h-4 w-4 mr-2" />
          {tCommon('back')}
        </Button>
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
          onClick={() => router.push(`/${locale}/dashboard/admin/document-templates/${templateId}`)}
        >
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold">{t('editDocumentTemplate')}</h1>
          <p className="text-muted-foreground font-mono">{template.templateCode}</p>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              {t('documentInfo')}
            </CardTitle>
            <CardDescription>{t('editDocumentDescription')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Template Code (read-only) */}
            <div className="space-y-2">
              <Label htmlFor="templateCode">{t('templateCode')}</Label>
              <Input
                id="templateCode"
                value={template.templateCode}
                disabled
                className="bg-muted"
              />
              <p className="text-xs text-muted-foreground">{t('templateCodeReadOnly')}</p>
            </div>

            {/* Document Name */}
            <div className="space-y-2">
              <Label htmlFor="documentNameEs">{t('documentName')} *</Label>
              <Input
                id="documentNameEs"
                value={formData.documentNameEs || ''}
                onChange={(e) => handleInputChange('documentNameEs', e.target.value)}
                placeholder={t('documentNamePlaceholder')}
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

            {/* Validity Duration */}
            <div className="space-y-2">
              <Label htmlFor="validityDurationMonths">{t('validityDuration')}</Label>
              <Input
                id="validityDurationMonths"
                type="number"
                min={0}
                value={formData.validityDurationMonths || ''}
                onChange={(e) => handleInputChange('validityDurationMonths', e.target.value ? parseInt(e.target.value) : undefined)}
                placeholder="12"
              />
            </div>

            {/* Validity Notes */}
            <div className="space-y-2">
              <Label htmlFor="validityNotes">{t('validityNotes')}</Label>
              <Textarea
                id="validityNotes"
                value={formData.validityNotes || ''}
                onChange={(e) => handleInputChange('validityNotes', e.target.value)}
                placeholder={t('validityNotesPlaceholder')}
                rows={2}
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
                onClick={() => router.push(`/${locale}/dashboard/admin/document-templates/${templateId}`)}
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
