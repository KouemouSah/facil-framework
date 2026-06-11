'use client'

import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SmsTemplateForm } from '@/modules/communications/components/SmsTemplateForm'
import { useCreateSmsTemplate } from '@/modules/communications/hooks/useSmsTemplates'
import type { SmsTemplateCreate, SmsTemplateUpdate } from '@/modules/communications/types'

export default function NewSmsTemplatePage() {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('communications.smsTemplates')
  const createMutation = useCreateSmsTemplate()

  const handleSubmit = async (data: SmsTemplateCreate | SmsTemplateUpdate) => {
    await createMutation.mutateAsync(data as SmsTemplateCreate)
    router.push(`/${locale}/dashboard/admin/communications/sms-templates`)
  }

  const handleCancel = () => {
    router.back()
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
              {t('newTemplate')}
            </h1>
            <p className="text-muted-foreground">
              {t('newTemplateDescription')}
            </p>
          </div>
        </div>
      </div>

      <SmsTemplateForm
        onSubmit={handleSubmit}
        onCancel={handleCancel}
        isSubmitting={createMutation.isPending}
      />
    </div>
  )
}
