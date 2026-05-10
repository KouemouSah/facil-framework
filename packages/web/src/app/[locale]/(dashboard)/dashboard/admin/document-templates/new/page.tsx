'use client'

/**
 * Document Template Creation Page
 *
 * @module dashboard/admin/document-templates/new
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ArrowLeft, Save, FileText } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import templatesAPI from '@/modules/templates/services/api'
import type { DocumentTemplateCreate } from '@/types/fiscal-service'

// Valid document template categories (must match database check constraint)
const DOCUMENT_CATEGORIES = [
  'academic',
  'aircraft',
  'authorization',
  'certificate',
  'general',
  'identity',
  'payment_proof',
  'photo',
  'property',
] as const

export default function NewDocumentTemplatePage() {
  const locale = useLocale()
  const router = useRouter()
  const tAdmin = useTranslations('admin')
  const tCommon = useTranslations('common')
  const { toast } = useToast()

  const t = (key: string) => tAdmin(`templates.${key}`)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formData, setFormData] = useState<DocumentTemplateCreate>({
    templateCode: '',
    documentNameEs: '',
    descriptionEs: '',
    category: '',
    validityDurationMonths: undefined,
    validityNotes: '',
    isActive: true,
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)

    try {
      await templatesAPI.documents.create(formData)
      toast({
        title: t('successTitle'),
        description: t('documentCreated'),
      })
      router.push(`/${locale}/dashboard/admin/document-templates`)
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

  const handleInputChange = (field: keyof DocumentTemplateCreate, value: string | number | boolean | undefined) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => router.push(`/${locale}/dashboard/admin/document-templates`)}
        >
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold">{t('createDocumentTemplate')}</h1>
          <p className="text-muted-foreground">{t('createDocumentSubtitle')}</p>
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
            <CardDescription>{t('documentInfoDescription')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Template Code */}
            <div className="space-y-2">
              <Label htmlFor="templateCode">{t('templateCode')} *</Label>
              <Input
                id="templateCode"
                value={formData.templateCode}
                onChange={(e) => handleInputChange('templateCode', e.target.value)}
                placeholder="DOC_001"
                required
              />
            </div>

            {/* Document Name */}
            <div className="space-y-2">
              <Label htmlFor="documentNameEs">{t('documentName')} *</Label>
              <Input
                id="documentNameEs"
                value={formData.documentNameEs}
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
              <Select
                value={formData.category || ''}
                onValueChange={(value) => handleInputChange('category', value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t('categoryPlaceholder')} />
                </SelectTrigger>
                <SelectContent>
                  {DOCUMENT_CATEGORIES.map((category) => (
                    <SelectItem key={category} value={category}>
                      {t(`categories.${category}`) || category}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
                onClick={() => router.push(`/${locale}/dashboard/admin/document-templates`)}
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
