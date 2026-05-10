'use client'

/**
 * SmsTemplateForm Component
 * Form for creating and editing SMS templates
 */

import React, { useState } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { RefreshCw, Plus, X } from 'lucide-react'
import { SmsCharCounter } from './SmsCharCounter'
import type { SmsTemplateCreate, SmsTemplateUpdate, SmsTemplateResponse, SmsTemplateCategory } from '../types'

interface SmsTemplateFormProps {
  initialData?: SmsTemplateResponse
  onSubmit: (data: SmsTemplateCreate | SmsTemplateUpdate) => Promise<void>
  onCancel: () => void
  isSubmitting?: boolean
}

const CATEGORIES: { value: SmsTemplateCategory; label: string }[] = [
  { value: 'auth', label: 'Authentication' },
  { value: 'notifications', label: 'Notifications' },
  { value: 'payments', label: 'Payments' },
  { value: 'declarations', label: 'Declarations' },
  { value: 'reminders', label: 'Reminders' },
  { value: 'alerts', label: 'Alerts' },
]

export function SmsTemplateForm({
  initialData,
  onSubmit,
  onCancel,
  isSubmitting = false,
}: SmsTemplateFormProps) {
  const _locale = useLocale()
  const t = useTranslations('admin.smsTemplates.form')
  const tCommon = useTranslations('common')

  const [formData, setFormData] = useState<SmsTemplateCreate>({
    templateCode: initialData?.templateCode || '',
    nameEs: initialData?.nameEs || '',
    nameFr: initialData?.nameFr || '',
    nameEn: initialData?.nameEn || '',
    contentEs: initialData?.contentEs || '',
    contentFr: initialData?.contentFr || '',
    contentEn: initialData?.contentEn || '',
    variables: initialData?.variables || [],
    category: initialData?.category || 'notifications',
    maxSegments: initialData?.maxSegments || 2,
    isActive: initialData?.isActive ?? true,
  })

  const [newVariable, setNewVariable] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await onSubmit(formData)
  }

  const addVariable = () => {
    if (newVariable && !formData.variables?.includes(newVariable)) {
      setFormData({
        ...formData,
        variables: [...(formData.variables || []), newVariable],
      })
      setNewVariable('')
    }
  }

  const removeVariable = (variable: string) => {
    setFormData({
      ...formData,
      variables: formData.variables?.filter(v => v !== variable) || [],
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Basic Information */}
      <Card>
        <CardHeader>
          <CardTitle>{t('basicInfo')}</CardTitle>
          <CardDescription>{t('basicInfoDescription')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="templateCode">{t('fieldTemplateCode')} *</Label>
              <Input
                id="templateCode"
                value={formData.templateCode}
                onChange={(e) => setFormData({ ...formData, templateCode: e.target.value.toUpperCase() })}
                placeholder="PAYMENT_RECEIVED"
                maxLength={100}
                disabled={!!initialData}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="category">{t('fieldCategory')} *</Label>
              <Select
                value={formData.category}
                onValueChange={(v) => setFormData({ ...formData, category: v as SmsTemplateCategory })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((category) => (
                    <SelectItem key={category.value} value={category.value}>
                      {category.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="nameEs">{t('fieldNameEs')} *</Label>
              <Input
                id="nameEs"
                value={formData.nameEs}
                onChange={(e) => setFormData({ ...formData, nameEs: e.target.value })}
                placeholder="Pago Recibido"
                maxLength={255}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="nameFr">{t('fieldNameFr')}</Label>
              <Input
                id="nameFr"
                value={formData.nameFr}
                onChange={(e) => setFormData({ ...formData, nameFr: e.target.value })}
                placeholder="Paiement Reçu"
                maxLength={255}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="nameEn">{t('fieldNameEn')}</Label>
              <Input
                id="nameEn"
                value={formData.nameEn}
                onChange={(e) => setFormData({ ...formData, nameEn: e.target.value })}
                placeholder="Payment Received"
                maxLength={255}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* SMS Content - Spanish */}
      <Card>
        <CardHeader>
          <CardTitle>{t('contentEs')}</CardTitle>
          <CardDescription>{t('contentEsDescription')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="contentEs">{t('fieldContentEs')} *</Label>
            <Textarea
              id="contentEs"
              value={formData.contentEs}
              onChange={(e) => setFormData({ ...formData, contentEs: e.target.value })}
              placeholder="Tu pago de {amount} XAF ha sido recibido. Ref: {reference}"
              rows={3}
              required
            />
          </div>
          <SmsCharCounter
            content={formData.contentEs}
            maxSegments={formData.maxSegments}
          />
        </CardContent>
      </Card>

      {/* SMS Content - French */}
      <Card>
        <CardHeader>
          <CardTitle>{t('contentFr')}</CardTitle>
          <CardDescription>{t('contentFrDescription')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="contentFr">{t('fieldContentFr')}</Label>
            <Textarea
              id="contentFr"
              value={formData.contentFr}
              onChange={(e) => setFormData({ ...formData, contentFr: e.target.value })}
              placeholder="Votre paiement de {amount} XAF a été reçu. Réf: {reference}"
              rows={3}
            />
          </div>
          {formData.contentFr && (
            <SmsCharCounter
              content={formData.contentFr}
              maxSegments={formData.maxSegments}
            />
          )}
        </CardContent>
      </Card>

      {/* SMS Content - English */}
      <Card>
        <CardHeader>
          <CardTitle>{t('contentEn')}</CardTitle>
          <CardDescription>{t('contentEnDescription')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="contentEn">{t('fieldContentEn')}</Label>
            <Textarea
              id="contentEn"
              value={formData.contentEn}
              onChange={(e) => setFormData({ ...formData, contentEn: e.target.value })}
              placeholder="Your payment of {amount} XAF has been received. Ref: {reference}"
              rows={3}
            />
          </div>
          {formData.contentEn && (
            <SmsCharCounter
              content={formData.contentEn}
              maxSegments={formData.maxSegments}
            />
          )}
        </CardContent>
      </Card>

      {/* Variables */}
      <Card>
        <CardHeader>
          <CardTitle>{t('variablesTitle')}</CardTitle>
          <CardDescription>{t('variablesDescription')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              value={newVariable}
              onChange={(e) => setNewVariable(e.target.value)}
              placeholder="amount, reference, user_name..."
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  addVariable()
                }
              }}
            />
            <Button type="button" onClick={addVariable}>
              <Plus className="h-4 w-4 mr-1" />
              {t('addVariable')}
            </Button>
          </div>

          {formData.variables && formData.variables.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {formData.variables.map((variable) => (
                <Badge key={variable} variant="secondary" className="text-sm">
                  {'{'}
                  {variable}
                  {'}'}
                  <button
                    type="button"
                    onClick={() => removeVariable(variable)}
                    className="ml-1 hover:text-red-600"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Settings */}
      <Card>
        <CardHeader>
          <CardTitle>{t('settingsTitle')}</CardTitle>
          <CardDescription>{t('settingsDescription')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="maxSegments">{t('fieldMaxSegments')}</Label>
            <div className="flex items-center gap-4">
              <Input
                id="maxSegments"
                type="number"
                value={formData.maxSegments}
                onChange={(e) => setFormData({ ...formData, maxSegments: Number(e.target.value) })}
                min={1}
                max={4}
                className="w-32"
              />
              <span className="text-sm text-muted-foreground">
                {formData.maxSegments} {formData.maxSegments === 1 ? 'segment' : 'segments'} max
              </span>
            </div>
            <p className="text-xs text-muted-foreground">{t('maxSegmentsHint')}</p>
          </div>

          <div className="flex items-center space-x-2">
            <Switch
              id="isActive"
              checked={formData.isActive}
              onCheckedChange={(checked) => setFormData({ ...formData, isActive: checked })}
            />
            <Label htmlFor="isActive">{t('fieldActive')}</Label>
          </div>
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex items-center justify-end gap-4">
        <Button type="button" variant="outline" onClick={onCancel} disabled={isSubmitting}>
          {tCommon('cancel')}
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting && <RefreshCw className="h-4 w-4 mr-2 animate-spin" />}
          {initialData ? t('update') : t('create')}
        </Button>
      </div>
    </form>
  )
}
