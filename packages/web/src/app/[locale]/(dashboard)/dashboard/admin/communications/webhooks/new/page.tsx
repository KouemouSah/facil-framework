import { WebhookForm } from '@/modules/communications/components'

interface NewWebhookPageProps {
  params: {
    locale: string
  }
}

export default function NewWebhookPage({ params }: NewWebhookPageProps) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Create Webhook</h1>
        <p className="text-muted-foreground">
          Configure a new webhook integration for external systems
        </p>
      </div>

      <WebhookForm locale={params.locale} />
    </div>
  )
}

export const metadata = {
  title: 'Create Webhook',
  description: 'Create a new webhook configuration',
}
