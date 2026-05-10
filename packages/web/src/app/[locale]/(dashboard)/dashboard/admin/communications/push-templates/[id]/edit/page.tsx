'use client'

/**
 * Edit Push Template Page
 */

import { useEffect, useState } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { RefreshCw } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import { usePushTemplates } from '@/modules/communications/hooks/usePushTemplates'
import { PushTemplateForm } from '@/modules/communications/components/PushTemplateForm'
import type { PushTemplateResponse, PushTemplateUpdate } from '@/modules/communications/types'

export default function EditPushTemplatePage() {
  const locale = useLocale()
  const router = useRouter()
  const params = useParams()
  const templateId = Number(params.id)
  const t = useTranslations('admin.pushTemplates')
  const { toast } = useToast()
  const { getTemplate, updateTemplate } = usePushTemplates()

  const [template, setTemplate] = useState<PushTemplateResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchTemplate = async () => {
      setIsLoading(true)
      const data = await getTemplate(templateId)
      if (data) {
        setTemplate(data)
      } else {
        toast({
          variant: 'destructive',
          title: t('errorTitle'),
          description: t('errorLoading'),
        })
        router.push(`/${locale}/dashboard/admin/communications/push-templates`)
      }
      setIsLoading(false)
    }

    fetchTemplate()
  }, [templateId, getTemplate, router, locale, t, toast])

  const handleSubmit = async (data: PushTemplateUpdate) => {
    const result = await updateTemplate(templateId, data)
    if (result) {
      toast({
        title: t('successTitle'),
        description: t('templateUpdated'),
      })
      router.push(`/${locale}/dashboard/admin/communications/push-templates`)
    } else {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: t('errorUpdating'),
      })
    }
  }

  const handleCancel = () => {
    router.back()
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">{t('loading')}</span>
      </div>
    )
  }

  if (!template) {
    return null
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t('editTitle')}</h1>
        <p className="text-muted-foreground mt-2">{t('editDescription')}</p>
      </div>

      <PushTemplateForm
        initialData={template}
        onSubmit={handleSubmit}
        onCancel={handleCancel}
      />
    </div>
  )
}
