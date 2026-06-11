/**
 * Create Notification Template Page
 * Form to create a new notification template
 */

import { NotificationTemplateForm } from '@/modules/communications/components/NotificationTemplateForm'

interface PageProps {
  params: {
    locale: string
  }
}

export default function NewNotificationTemplatePage({ params }: PageProps) {
  return <NotificationTemplateForm locale={params.locale} mode="create" />
}

export const metadata = {
  title: 'Create Notification Template | Facil Admin',
  description: 'Create a new notification template',
}
