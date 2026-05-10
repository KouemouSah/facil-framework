'use client'

/**
 * WebhookTestDialog Component
 * Dialog for testing webhook configurations with custom payload
 */

import { useState } from 'react'
import { TestTube, CheckCircle, XCircle, Clock, Copy, Check } from 'lucide-react'
import { useTestWebhook } from '../hooks/useWebhooks'
import type { WebhookResponse, WebhookTestResponse } from '../types'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface WebhookTestDialogProps {
  webhook: WebhookResponse
  trigger?: React.ReactNode
}

export function WebhookTestDialog({ webhook, trigger }: WebhookTestDialogProps) {
  const [open, setOpen] = useState(false)
  const [testPayload, setTestPayload] = useState(
    JSON.stringify(
      {
        test: true,
        timestamp: new Date().toISOString(),
      },
      null,
      2
    )
  )
  const [testResult, setTestResult] = useState<WebhookTestResponse | null>(null)
  const [copiedField, setCopiedField] = useState<string | null>(null)

  const testMutation = useTestWebhook()

  const handleTest = async () => {
    try {
      let payload: Record<string, unknown> | undefined
      if (testPayload.trim()) {
        payload = JSON.parse(testPayload)
      }

      const result = await testMutation.mutateAsync({
        id: webhook.id,
        data: { testPayload: payload },
      })

      setTestResult(result)
    } catch (error) {
      // Error will be shown via toast in the mutation hook
    }
  }

  const copyToClipboard = async (text: string, field: string) => {
    await navigator.clipboard.writeText(text)
    setCopiedField(field)
    setTimeout(() => setCopiedField(null), 2000)
  }

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }

  const getStatusIcon = (success: boolean) => {
    return success ? (
      <CheckCircle className="h-5 w-5 text-green-600" />
    ) : (
      <XCircle className="h-5 w-5 text-red-600" />
    )
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="outline" size="sm">
            <TestTube className="mr-2 h-4 w-4" />
            Test Webhook
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-4xl max-h-[90vh]">
        <DialogHeader>
          <DialogTitle>Test Webhook: {webhook.name}</DialogTitle>
          <DialogDescription>
            Send a test request to {webhook.endpointUrl}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Test Payload (JSON)</Label>
            <Textarea
              value={testPayload}
              onChange={(e) => setTestPayload(e.target.value)}
              placeholder='{"test": true, "message": "Test webhook"}'
              className="font-mono text-sm"
              rows={6}
            />
            <p className="text-sm text-muted-foreground">
              If webhook has a payload template, variables will be substituted
            </p>
          </div>

          <Button
            onClick={handleTest}
            disabled={testMutation.isPending}
            className="w-full"
          >
            {testMutation.isPending ? (
              <>
                <Clock className="mr-2 h-4 w-4 animate-spin" />
                Testing...
              </>
            ) : (
              <>
                <TestTube className="mr-2 h-4 w-4" />
                Send Test Request
              </>
            )}
          </Button>

          {testResult && (
            <>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {getStatusIcon(testResult.success)}
                    <span className="font-semibold">
                      {testResult.success ? 'Test Successful' : 'Test Failed'}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    {testResult.statusCode && (
                      <Badge
                        variant={testResult.success ? 'default' : 'destructive'}
                      >
                        Status: {testResult.statusCode}
                      </Badge>
                    )}
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatDuration(testResult.durationMs)}
                    </span>
                  </div>
                </div>

                <ScrollArea className="h-[400px] w-full">
                  <div className="space-y-4">
                    <Card>
                      <CardHeader className="pb-3">
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-sm font-medium">
                            Request Details
                          </CardTitle>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <div>
                          <div className="text-sm font-medium text-muted-foreground">
                            URL
                          </div>
                          <div className="mt-1 flex items-center justify-between rounded-md bg-muted p-2">
                            <code className="text-sm">{testResult.requestUrl}</code>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                copyToClipboard(testResult.requestUrl, 'url')
                              }
                            >
                              {copiedField === 'url' ? (
                                <Check className="h-4 w-4" />
                              ) : (
                                <Copy className="h-4 w-4" />
                              )}
                            </Button>
                          </div>
                        </div>

                        <div>
                          <div className="text-sm font-medium text-muted-foreground">
                            Method
                          </div>
                          <div className="mt-1 rounded-md bg-muted p-2">
                            <code className="text-sm">{testResult.requestMethod}</code>
                          </div>
                        </div>

                        <div>
                          <div className="text-sm font-medium text-muted-foreground">
                            Headers
                          </div>
                          <div className="mt-1 rounded-md bg-muted p-2">
                            <pre className="text-xs">
                              {JSON.stringify(testResult.requestHeaders, null, 2)}
                            </pre>
                          </div>
                        </div>

                        <div>
                          <div className="text-sm font-medium text-muted-foreground">
                            Payload
                          </div>
                          <div className="mt-1 rounded-md bg-muted p-2">
                            <pre className="text-xs">
                              {JSON.stringify(testResult.requestPayload, null, 2)}
                            </pre>
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    {testResult.success && testResult.responseBody && (
                      <Card>
                        <CardHeader className="pb-3">
                          <div className="flex items-center justify-between">
                            <CardTitle className="text-sm font-medium">
                              Response
                            </CardTitle>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                copyToClipboard(
                                  testResult.responseBody || '',
                                  'response'
                                )
                              }
                            >
                              {copiedField === 'response' ? (
                                <Check className="h-4 w-4" />
                              ) : (
                                <Copy className="h-4 w-4" />
                              )}
                            </Button>
                          </div>
                        </CardHeader>
                        <CardContent>
                          <div className="rounded-md bg-muted p-2">
                            <pre className="text-xs whitespace-pre-wrap">
                              {testResult.responseBody}
                            </pre>
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {!testResult.success && testResult.errorMessage && (
                      <Card className="border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950">
                        <CardHeader className="pb-3">
                          <CardTitle className="text-sm font-medium text-red-600 dark:text-red-400">
                            Error Details
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="rounded-md bg-red-100 p-3 dark:bg-red-900/50">
                            <p className="text-sm text-red-900 dark:text-red-200">
                              {testResult.errorMessage}
                            </p>
                          </div>
                        </CardContent>
                      </Card>
                    )}
                  </div>
                </ScrollArea>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
