'use client'

import { useWebhook } from '@/modules/communications/hooks/useWebhooks'
import { WebhookTestDialog } from '@/modules/communications/components'
import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ExternalLink } from 'lucide-react'

interface TestWebhookPageProps {
  params: {
    locale: string
    id: string
  }
}

export default function TestWebhookPage({ params }: TestWebhookPageProps) {
  const webhookId = parseInt(params.id, 10)
  const { data: webhook, isLoading, error } = useWebhook(webhookId)

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-9 w-[200px]" />
        <Card>
          <CardContent className="pt-6">
            <Skeleton className="h-20 w-full" />
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
        <h1 className="text-3xl font-bold tracking-tight">Test Webhook</h1>
        <p className="text-muted-foreground">
          Test and verify webhook configuration
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{webhook.name}</CardTitle>
          <CardDescription>
            Send test requests to verify your webhook configuration
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <div className="text-sm font-medium text-muted-foreground">Type</div>
              <Badge className="mt-1">{webhook.webhookType}</Badge>
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">Status</div>
              <Badge
                className="mt-1"
                variant={webhook.isActive ? 'default' : 'secondary'}
              >
                {webhook.isActive ? 'Active' : 'Inactive'}
              </Badge>
            </div>
          </div>

          <div>
            <div className="text-sm font-medium text-muted-foreground">Endpoint URL</div>
            <div className="mt-1 flex items-center gap-2 rounded-md bg-muted p-3">
              <code className="text-sm flex-1">{webhook.endpointUrl}</code>
              <a
                href={webhook.endpointUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground hover:text-foreground"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            </div>
          </div>

          <div>
            <div className="text-sm font-medium text-muted-foreground">HTTP Method</div>
            <div className="mt-1 rounded-md bg-muted p-3">
              <code className="text-sm">{webhook.httpMethod}</code>
            </div>
          </div>

          {webhook.events.length > 0 && (
            <div>
              <div className="text-sm font-medium text-muted-foreground">Events</div>
              <div className="mt-1 flex flex-wrap gap-2">
                {webhook.events.map((event) => (
                  <Badge key={event} variant="outline">
                    {event}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          <div className="pt-4">
            <WebhookTestDialog webhook={webhook} />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
