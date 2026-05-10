'use client'

/**
 * Create Push Template Page
 */

import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { useToast } from '@/hooks/use-toast'
import { usePushTemplates } from '@/modules/communications/hooks/usePushTemplates'
import { PushTemplateForm } from '@/modules/communications/components/PushTemplateForm'
import type { PushTemplateCreate, PushTemplateUpdate } from '@/modules/communications/types'

export default function NewPushTemplatePage() {
  const locale = useLocale()
  const router = useRouter()
  const t = useTranslations('admin.pushTemplates')
  const { toast } = useToast()
  const { createTemplate } = usePushTemplates()

  const handleSubmit = async (data: PushTemplateCreate | PushTemplateUpdate) => {
    const result = await createTemplate(data as PushTemplateCreate)
    if (result) {
      toast({
        title: t('successTitle'),
        description: t('templateCreated'),
      })
      router.push(`/${locale}/dashboard/admin/communications/push-templates`)
    } else {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: t('errorCreating'),
      })
    }
  }

  const handleCancel = () => {
    router.back()
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t('createTitle')}</h1>
        <p className="text-muted-foreground mt-2">{t('createDescription')}</p>
      </div>

      <PushTemplateForm onSubmit={handleSubmit} onCancel={handleCancel} />
    </div>
  )
}
