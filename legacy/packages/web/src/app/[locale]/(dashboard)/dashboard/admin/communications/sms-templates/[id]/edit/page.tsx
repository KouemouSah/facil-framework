'use client'

import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SmsTemplateForm } from '@/modules/communications/components/SmsTemplateForm'
import {
  useSmsTemplate,
  useUpdateSmsTemplate
} from '@/modules/communications/hooks/useSmsTemplates'
import type { SmsTemplateCreate, SmsTemplateUpdate } from '@/modules/communications/types'
import { Skeleton } from '@/components/ui/skeleton'

interface PageProps {
  params: {
    locale: string
    id: string
  }
}

export default function EditSmsTemplatePage({ params }: PageProps) {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('communications.smsTemplates')

  const templateId = parseInt(params.id, 10)
  const { data: template, isLoading } = useSmsTemplate(templateId)
  const updateMutation = useUpdateSmsTemplate()

  const handleSubmit = async (data: SmsTemplateCreate | SmsTemplateUpdate) => {
    await updateMutation.mutateAsync({
      id: templateId,
      data: data as SmsTemplateUpdate
    })
    router.push(`/${locale}/dashboard/admin/communications/sms-templates`)
  }

  const handleCancel = () => {
    router.back()
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Skeleton className="h-10 w-10" />
            <div className="space-y-2">
              <Skeleton className="h-8 w-64" />
              <Skeleton className="h-4 w-96" />
            </div>
          </div>
        </div>
        <div className="space-y-4">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      </div>
    )
  }

  if (!template) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={handleCancel}
              aria-label={t('backToList')}
            >
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div>
              <h1 className="text-3xl font-bold tracking-tight">
                {t('templateNotFound')}
              </h1>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={handleCancel}
            aria-label={t('backToList')}
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              {t('editTemplate')}
            </h1>
            <p className="text-muted-foreground">
              {t('editTemplateDescription')}
            </p>
          </div>
        </div>
      </div>

      <SmsTemplateForm
        initialData={template}
        onSubmit={handleSubmit}
        onCancel={handleCancel}
        isSubmitting={updateMutation.isPending}
      />
    </div>
  )
}
