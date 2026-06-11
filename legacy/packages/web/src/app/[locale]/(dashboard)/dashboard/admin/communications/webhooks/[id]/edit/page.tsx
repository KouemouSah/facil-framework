'use client'

import { useWebhook } from '@/modules/communications/hooks/useWebhooks'
import { WebhookForm } from '@/modules/communications/components'
import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent } from '@/components/ui/card'

interface EditWebhookPageProps {
  params: {
    locale: string
    id: string
  }
}

export default function EditWebhookPage({ params }: EditWebhookPageProps) {
  const webhookId = parseInt(params.id, 10)
  const { data: webhook, isLoading, error } = useWebhook(webhookId)

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <Skeleton className="h-9 w-[200px]" />
          <Skeleton className="mt-2 h-5 w-[300px]" />
        </div>
        <Card>
          <CardContent className="pt-6 space-y-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error || !webhook) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center text-red-600">
            {error ? `Error loading webhook: ${error.message}` : 'Webhook not found'}
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Edit Webhook</h1>
        <p className="text-muted-foreground">
          Update webhook configuration: {webhook.name}
        </p>
      </div>

      <WebhookForm webhook={webhook} locale={params.locale} />
    </div>
  )
}
