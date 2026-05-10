'use client'

/**
 * Procedure Template Edit Page
 * Same layout as view page with editable form and steps section
 *
 * @module dashboard/admin/procedure-templates/[id]/edit
 */

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ArrowLeft, Save, ListOrdered, Calendar, RefreshCw, AlertTriangle, Plus, Edit, Trash2 } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import templatesAPI from '@/modules/templates/services/api'
import type { ProcedureTemplate, ProcedureTemplateUpdate, ProcedureStep } from '@/types/fiscal-service'

export default function EditProcedureTemplatePage() {
  const locale = useLocale()
  const router = useRouter()
  const params = useParams()
  const templateId = params.id as string
  const tAdmin = useTranslations('admin')
  const tCommon = useTranslations('common')
  const { toast } = useToast()

  const t = (key: string, params?: Record<string, string | number>) =>
    tAdmin(`templates.${key}`, params)

  const [template, setTemplate] = useState<ProcedureTemplate | null>(null)
  const [steps, setSteps] = useState<ProcedureStep[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [formData, setFormData] = useState<ProcedureTemplateUpdate>({
    nameEs: '',
    descriptionEs: '',
    category: '',
    isActive: true,
  })

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const [templateData, stepsData] = await Promise.all([
          templatesAPI.procedures.get(templateId),
          templatesAPI.steps.list(templateId),
        ])
        setTemplate(templateData)
        setSteps(stepsData)
        setFormData({
          nameEs: templateData.nameEs,
          descriptionEs: templateData.descriptionEs || '',
          category: templateData.category || '',
          isActive: templateData.isActive,
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

    fetchData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [templateId, toast])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)

    try {
      await templatesAPI.procedures.update(templateId, formData)
      toast({
        title: t('successTitle'),
        description: t('procedureUpdated'),
      })
      router.push(`/${locale}/dashboard/admin/procedure-templates/${templateId}`)
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

  const handleInputChange = (field: keyof ProcedureTemplateUpdate, value: string | boolean) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  const handleDeleteStep = async (stepId: number) => {
    if (!confirm(t('confirmDeleteStep'))) return

    try {
      await templatesAPI.steps.delete(templateId, stepId)
      toast({
        title: t('successTitle'),
        description: t('stepDeleted'),
      })
      // Refresh steps
      const stepsData = await templatesAPI.steps.list(templateId)
      setSteps(stepsData)
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: err instanceof Error ? err.message : 'Error deleting step',
      })
    }
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
        <Button onClick={() => router.push(`/${locale}/dashboard/admin/procedure-templates`)} variant="outline">
          <ArrowLeft className="h-4 w-4 mr-2" />
          {tCommon('back')}
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push(`/${locale}/dashboard/admin/procedure-templates`)}
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold">{t('editProcedureTemplate')}</h1>
            <p className="text-muted-foreground font-mono">{template.templateCode}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => router.push(`/${locale}/dashboard/admin/procedure-templates/${templateId}`)}
          >
            {tCommon('cancel')}
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            <Save className="h-4 w-4 mr-2" />
            {isSubmitting ? tCommon('saving') : tCommon('save')}
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Edit Form */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ListOrdered className="h-5 w-5" />
              {t('procedureInfo')}
            </CardTitle>
            <CardDescription>{t('editProcedureDescription')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
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

            {/* Procedure Name */}
            <div className="space-y-2">
              <Label htmlFor="nameEs">{t('procedureName')} *</Label>
              <Input
                id="nameEs"
                value={formData.nameEs || ''}
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
          </CardContent>
        </Card>

        {/* Stats */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5" />
              {t('statistics')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm font-medium text-muted-foreground">{t('tableUsageCount')}</p>
              <p className="text-2xl font-bold">{template.usageCount}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">{t('stepsCount')}</p>
              <p className="text-2xl font-bold">{steps.length}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">{t('createdAt')}</p>
              <p>{new Date(template.createdAt).toLocaleDateString(locale)}</p>
            </div>
            {template.updatedAt && (
              <div>
                <p className="text-sm font-medium text-muted-foreground">{t('updatedAt')}</p>
                <p>{new Date(template.updatedAt).toLocaleDateString(locale)}</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Steps */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <ListOrdered className="h-5 w-5" />
                {t('procedureSteps')}
              </CardTitle>
              <CardDescription>
                {steps.length} {steps.length === 1 ? t('step') : t('steps')}
              </CardDescription>
            </div>
            <Button size="sm" onClick={() => router.push(`/${locale}/dashboard/admin/procedure-templates/${templateId}/steps/new`)}>
              <Plus className="h-4 w-4 mr-2" />
              {t('addStep')}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {steps.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-4 py-12 text-center">
              <ListOrdered className="h-12 w-12 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">{t('noSteps')}</p>
              <Button size="sm" onClick={() => router.push(`/${locale}/dashboard/admin/procedure-templates/${templateId}/steps/new`)}>
                <Plus className="h-4 w-4 mr-2" />
                {t('addStep')}
              </Button>
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[80px]">{t('stepNumber')}</TableHead>
                    <TableHead>{t('stepDescription')}</TableHead>
                    <TableHead>{t('estimatedDuration')}</TableHead>
                    <TableHead>{t('optional')}</TableHead>
                    <TableHead className="text-right">{t('tableActions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {steps.sort((a, b) => a.stepNumber - b.stepNumber).map((step) => (
                    <TableRow key={step.id}>
                      <TableCell className="font-bold">{step.stepNumber}</TableCell>
                      <TableCell>{step.descriptionEs}</TableCell>
                      <TableCell>
                        {step.estimatedDurationMinutes ? `${step.estimatedDurationMinutes} min` : '—'}
                      </TableCell>
                      <TableCell>
                        {step.isOptional ? (
                          <Badge variant="secondary">{t('yes')}</Badge>
                        ) : (
                          <Badge variant="outline">{t('no')}</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => router.push(`/${locale}/dashboard/admin/procedure-templates/${templateId}/steps/${step.id}/edit`)}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteStep(step.id)}
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
