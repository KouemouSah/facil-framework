/**
 * Edit Notification Template Page
 * Form to edit an existing notification template
 */

'use client'

import { useParams } from 'next/navigation'
import { Loader2 } from 'lucide-react'
import { NotificationTemplateForm } from '@/modules/communications/components/NotificationTemplateForm'
import { useNotificationTemplate } from '@/modules/communications/hooks/useNotificationTemplates'

export default function EditNotificationTemplatePage() {
  const params = useParams()
  const templateId = parseInt(params.id as string)
  const locale = params.locale as string

  const { data: template, isLoading, error } = useNotificationTemplate(templateId)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">Loading template...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <p className="text-destructive mb-2">Failed to load template</p>
          <p className="text-sm text-muted-foreground">{error.message}</p>
        </div>
      </div>
    )
  }

  if (!template) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <p className="text-muted-foreground">Template not found</p>
        </div>
      </div>
    )
  }

  return <NotificationTemplateForm template={template} locale={locale} mode="edit" />
}
