'use client'

/**
 * Document Template View Page
 *
 * @module dashboard/admin/document-templates/[id]
 */

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, Edit, Trash2, FileText, Calendar, CheckCircle2, XCircle, RefreshCw, AlertTriangle } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import templatesAPI from '@/modules/templates/services/api'
import type { DocumentTemplate } from '@/types/fiscal-service'

export default function ViewDocumentTemplatePage() {
  const locale = useLocale()
  const router = useRouter()
  const params = useParams()
  const templateId = params.id as string
  const tAdmin = useTranslations('admin')
  const tCommon = useTranslations('common')
  const { toast } = useToast()

  const t = (key: string, params?: Record<string, string | number>) =>
    tAdmin(`templates.${key}`, params)

  const [template, setTemplate] = useState<DocumentTemplate | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchTemplate = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const data = await templatesAPI.documents.get(templateId)
        setTemplate(data)
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

  const handleDelete = async () => {
    if (!template) return
    if (!confirm(t('confirmDeleteDocument', { name: template.documentNameEs }))) return

    try {
      await templatesAPI.documents.delete(template.id)
      toast({
        title: t('successTitle'),
        description: t('documentDeleted'),
      })
      router.push(`/${locale}/dashboard/admin/document-templates`)
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: err instanceof Error ? err.message : 'Error deleting template',
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
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push(`/${locale}/dashboard/admin/document-templates`)}
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold">{template.documentNameEs}</h1>
            <p className="text-muted-foreground font-mono">{template.templateCode}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => router.push(`/${locale}/dashboard/admin/document-templates/${templateId}/edit`)}
          >
            <Edit className="h-4 w-4 mr-2" />
            {tCommon('edit')}
          </Button>
          <Button variant="destructive" onClick={handleDelete}>
            <Trash2 className="h-4 w-4 mr-2" />
            {tCommon('delete')}
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Basic Info */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              {t('documentInfo')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm font-medium text-muted-foreground">{t('templateCode')}</p>
              <p className="font-mono">{template.templateCode}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">{t('documentName')}</p>
              <p>{template.documentNameEs}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">{t('description')}</p>
              <p>{template.descriptionEs || '—'}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">{t('category')}</p>
              {template.category ? (
                <Badge variant="outline">{template.category}</Badge>
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">{t('tableStatus')}</p>
              {template.isActive ? (
                <Badge className="bg-green-500">
                  <CheckCircle2 className="mr-1 h-3 w-3" />
                  {t('active')}
                </Badge>
              ) : (
                <Badge variant="secondary">
                  <XCircle className="mr-1 h-3 w-3" />
                  {t('inactive')}
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Validity & Stats */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5" />
              {t('validityAndStats')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm font-medium text-muted-foreground">{t('validityDuration')}</p>
              <p>{template.validityDurationMonths ? `${template.validityDurationMonths} ${t('months')}` : '—'}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">{t('validityNotes')}</p>
              <p>{template.validityNotes || '—'}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">{t('tableUsageCount')}</p>
              <p className="text-2xl font-bold">{template.usageCount}</p>
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
    </div>
  )
}
