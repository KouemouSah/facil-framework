import { WebhookList } from '@/modules/communications/components'

interface WebhooksPageProps {
  params: {
    locale: string
  }
}

export default function WebhooksPage({ params }: WebhooksPageProps) {
  return <WebhookList locale={params.locale} />
}

export const metadata = {
  title: 'Webhook Configurations',
  description: 'Manage webhook integrations for external systems',
}
