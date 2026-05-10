/**
 * TemplateForm Component
 * Form for creating/editing templates
 *
 * @module templates/components
 */

'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Loader2 } from 'lucide-react'
import type { TemplateFormProps } from '../types'

export function TemplateForm({
  type,
  initialData,
  onSubmit,
  onCancel,
  isLoading = false,
}: TemplateFormProps) {
  const t = useTranslations('templates')

  const [formData, setFormData] = useState({
    name: initialData?.name || '',
    description: initialData?.description || '',
    category: initialData?.category || '',
    is_active: initialData?.is_active ?? true,
    file_type: initialData?.file_type || '',
    estimated_duration: initialData?.estimated_duration || '',
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await onSubmit(formData)
  }

  const handleChange = (field: string, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="name">{t('form.name')}</Label>
        <Input
          id="name"
          value={formData.name}
          onChange={(e) => handleChange('name', e.target.value)}
          placeholder={t('form.namePlaceholder')}
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="description">{t('form.description')}</Label>
        <Input
          id="description"
          value={formData.description}
          onChange={(e) => handleChange('description', e.target.value)}
          placeholder={t('form.descriptionPlaceholder')}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="category">{t('form.category')}</Label>
        <Input
          id="category"
          value={formData.category}
          onChange={(e) => handleChange('category', e.target.value)}
          placeholder={t('form.categoryPlaceholder')}
        />
      </div>

      {type === 'document' && (
        <div className="space-y-2">
          <Label htmlFor="file_type">{t('form.fileType')}</Label>
          <Input
            id="file_type"
            value={formData.file_type}
            onChange={(e) => handleChange('file_type', e.target.value)}
            placeholder="PDF, DOCX, etc."
          />
        </div>
      )}

      {type === 'procedure' && (
        <div className="space-y-2">
          <Label htmlFor="estimated_duration">
            {t('form.estimatedDuration')}
          </Label>
          <Input
            id="estimated_duration"
            value={formData.estimated_duration}
            onChange={(e) => handleChange('estimated_duration', e.target.value)}
            placeholder={t('form.durationPlaceholder')}
          />
        </div>
      )}

      <div className="flex items-center space-x-2">
        <Switch
          id="is_active"
          checked={formData.is_active}
          onCheckedChange={(checked) => handleChange('is_active', checked)}
        />
        <Label htmlFor="is_active">{t('form.isActive')}</Label>
      </div>

      <div className="flex justify-end gap-2 pt-4">
        <Button type="button" variant="outline" onClick={onCancel}>
          {t('form.cancel')}
        </Button>
        <Button type="submit" disabled={isLoading}>
          {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {initialData ? t('form.update') : t('form.create')}
        </Button>
      </div>
    </form>
  )
}
