/**
 * Notification Templates Admin Page
 * Lists all notification templates with filters and actions
 */

import { NotificationTemplateList } from '@/modules/communications/components/NotificationTemplateList'

interface PageProps {
  params: {
    locale: string
  }
}

export default function NotificationTemplatesPage({ params }: PageProps) {
  return <NotificationTemplateList locale={params.locale} />
}

export const metadata = {
  title: 'Notification Templates | Facil Admin',
  description: 'Manage notification templates for in-app notifications',
}
