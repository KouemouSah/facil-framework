'use client'

/**
 * PushTemplateForm Component
 * Form for creating and editing push notification templates
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
import type { PushTemplateCreate, PushTemplateUpdate, PushTemplateResponse, PlatformEnum } from '../types'

interface PushTemplateFormProps {
  initialData?: PushTemplateResponse
  onSubmit: (data: PushTemplateCreate | PushTemplateUpdate) => Promise<void>
  onCancel: () => void
  isSubmitting?: boolean
}

const PLATFORMS: { value: PlatformEnum; label: string }[] = [
  { value: 'all', label: 'All Platforms' },
  { value: 'ios', label: 'iOS' },
  { value: 'android', label: 'Android' },
  { value: 'web', label: 'Web' },
]

export function PushTemplateForm({
  initialData,
  onSubmit,
  onCancel,
  isSubmitting = false,
}: PushTemplateFormProps) {
  const _locale = useLocale()
  const t = useTranslations('admin.pushTemplates.form')
  const tCommon = useTranslations('common')

  const [formData, setFormData] = useState<PushTemplateCreate>({
    templateCode: initialData?.templateCode || '',
    nameEs: initialData?.nameEs || '',
    nameFr: initialData?.nameFr || '',
    nameEn: initialData?.nameEn || '',
    titleEs: initialData?.titleEs || '',
    titleFr: initialData?.titleFr || '',
    titleEn: initialData?.titleEn || '',
    bodyEs: initialData?.bodyEs || '',
    bodyFr: initialData?.bodyFr || '',
    bodyEn: initialData?.bodyEn || '',
    imageUrl: initialData?.imageUrl || '',
    iconUrl: initialData?.iconUrl || '',
    clickAction: initialData?.clickAction || '',
    dataPayload: initialData?.dataPayload || {},
    variables: initialData?.variables || [],
    platform: initialData?.platform || 'all',
    ttlSeconds: initialData?.ttlSeconds || 86400,
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

  const getTtlLabel = (seconds: number) => {
    if (seconds < 3600) return `${Math.floor(seconds / 60)} minutes`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} hours`
    return `${Math.floor(seconds / 86400)} days`
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
              <Label htmlFor="platform">{t('fieldPlatform')} *</Label>
              <Select
                value={formData.platform}
                onValueChange={(v) => setFormData({ ...formData, platform: v as PlatformEnum })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PLATFORMS.map((platform) => (
                    <SelectItem key={platform.value} value={platform.value}>
                      {platform.label}
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

      {/* Notification Content */}
      <Card>
        <CardHeader>
          <CardTitle>{t('contentTitle')}</CardTitle>
          <CardDescription>{t('contentDescription')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Title (max 65 chars recommended) */}
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="titleEs">
                {t('fieldTitleEs')} * <span className="text-xs text-muted-foreground">(max 65 chars)</span>
              </Label>
              <Input
                id="titleEs"
                value={formData.titleEs}
                onChange={(e) => setFormData({ ...formData, titleEs: e.target.value })}
                placeholder="Pago Confirmado"
                maxLength={100}
                required
              />
              <p className="text-xs text-muted-foreground">{formData.titleEs.length}/65</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="titleFr">
                {t('fieldTitleFr')} <span className="text-xs text-muted-foreground">(max 65 chars)</span>
              </Label>
              <Input
                id="titleFr"
                value={formData.titleFr}
                onChange={(e) => setFormData({ ...formData, titleFr: e.target.value })}
                placeholder="Paiement Confirmé"
                maxLength={100}
              />
              <p className="text-xs text-muted-foreground">{formData.titleFr?.length || 0}/65</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="titleEn">
                {t('fieldTitleEn')} <span className="text-xs text-muted-foreground">(max 65 chars)</span>
              </Label>
              <Input
                id="titleEn"
                value={formData.titleEn}
                onChange={(e) => setFormData({ ...formData, titleEn: e.target.value })}
                placeholder="Payment Confirmed"
                maxLength={100}
              />
              <p className="text-xs text-muted-foreground">{formData.titleEn?.length || 0}/65</p>
            </div>
          </div>

          {/* Body (max 240 chars) */}
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="bodyEs">
                {t('fieldBodyEs')} * <span className="text-xs text-muted-foreground">(max 240 chars)</span>
              </Label>
              <Textarea
                id="bodyEs"
                value={formData.bodyEs}
                onChange={(e) => setFormData({ ...formData, bodyEs: e.target.value })}
                placeholder="Tu pago de {amount} XAF ha sido recibido."
                maxLength={240}
                rows={3}
                required
              />
              <p className="text-xs text-muted-foreground">{formData.bodyEs.length}/240</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="bodyFr">
                {t('fieldBodyFr')} <span className="text-xs text-muted-foreground">(max 240 chars)</span>
              </Label>
              <Textarea
                id="bodyFr"
                value={formData.bodyFr}
                onChange={(e) => setFormData({ ...formData, bodyFr: e.target.value })}
                placeholder="Votre paiement de {amount} XAF a été reçu."
                maxLength={240}
                rows={3}
              />
              <p className="text-xs text-muted-foreground">{formData.bodyFr?.length || 0}/240</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="bodyEn">
                {t('fieldBodyEn')} <span className="text-xs text-muted-foreground">(max 240 chars)</span>
              </Label>
              <Textarea
                id="bodyEn"
                value={formData.bodyEn}
                onChange={(e) => setFormData({ ...formData, bodyEn: e.target.value })}
                placeholder="Your payment of {amount} XAF has been received."
                maxLength={240}
                rows={3}
              />
              <p className="text-xs text-muted-foreground">{formData.bodyEn?.length || 0}/240</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Media & Actions */}
      <Card>
        <CardHeader>
          <CardTitle>{t('mediaTitle')}</CardTitle>
          <CardDescription>{t('mediaDescription')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="imageUrl">{t('fieldImageUrl')}</Label>
              <Input
                id="imageUrl"
                type="url"
                value={formData.imageUrl}
                onChange={(e) => setFormData({ ...formData, imageUrl: e.target.value })}
                placeholder="https://example.com/image.png"
                maxLength={500}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="iconUrl">{t('fieldIconUrl')}</Label>
              <Input
                id="iconUrl"
                type="url"
                value={formData.iconUrl}
                onChange={(e) => setFormData({ ...formData, iconUrl: e.target.value })}
                placeholder="https://example.com/icon.png"
                maxLength={500}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="clickAction">{t('fieldClickAction')}</Label>
            <Input
              id="clickAction"
              value={formData.clickAction}
              onChange={(e) => setFormData({ ...formData, clickAction: e.target.value })}
              placeholder="/dashboard/payments"
              maxLength={500}
            />
            <p className="text-xs text-muted-foreground">{t('clickActionHint')}</p>
          </div>
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
              placeholder="amount, user_name, payment_id..."
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
            <Label htmlFor="ttlSeconds">{t('fieldTtl')}</Label>
            <div className="flex items-center gap-4">
              <Input
                id="ttlSeconds"
                type="number"
                value={formData.ttlSeconds}
                onChange={(e) => setFormData({ ...formData, ttlSeconds: Number(e.target.value) })}
                min={60}
                max={2419200}
                className="w-32"
              />
              <span className="text-sm text-muted-foreground">
                {getTtlLabel(formData.ttlSeconds)}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">{t('ttlHint')}</p>
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
