'use client'

/**
 * WebhookForm Component
 * Form for creating and editing webhook configurations
 */

import { useState } from 'react'
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Plus, Trash2, HelpCircle } from 'lucide-react'
import {
  WebhookType,
  HttpMethod,
  AuthType,
  type WebhookResponse,
} from '../types'
import { useCreateWebhook, useUpdateWebhook } from '../hooks/useWebhooks'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

// =============================================================================
// VALIDATION SCHEMA
// =============================================================================

const webhookSchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  webhookType: z.nativeEnum(WebhookType),
  endpointUrl: z.string().url('Must be a valid URL'),
  httpMethod: z.nativeEnum(HttpMethod),
  headers: z.array(
    z.object({
      key: z.string().min(1, 'Header name is required'),
      value: z.string().min(1, 'Header value is required'),
    })
  ),
  authType: z.nativeEnum(AuthType),
  authConfig: z.object({
    apiKey: z.string().optional(),
    apiKeyHeader: z.string().optional(),
    bearerToken: z.string().optional(),
    basicUsername: z.string().optional(),
    basicPassword: z.string().optional(),
  }),
  payloadTemplateJson: z.string().optional(),
  retryConfig: z.object({
    maxRetries: z.coerce.number().min(0).max(10),
    retryDelaySeconds: z.coerce.number().min(1).max(3600),
  }),
  timeoutSeconds: z.coerce.number().min(1).max(300),
  events: z.array(z.string()),
  isActive: z.boolean(),
})

type WebhookFormData = z.infer<typeof webhookSchema>

// =============================================================================
// COMPONENT
// =============================================================================

interface WebhookFormProps {
  webhook?: WebhookResponse
  locale: string
}

export function WebhookForm({ webhook, locale }: WebhookFormProps) {
  const router = useRouter()
  const t = useTranslations('admin.webhooks.form')
  const isEditing = !!webhook
  const [eventInput, setEventInput] = useState('')

  const createMutation = useCreateWebhook()
  const updateMutation = useUpdateWebhook()

  const form = useForm<WebhookFormData>({
    resolver: zodResolver(webhookSchema),
    defaultValues: {
      name: webhook?.name || '',
      webhookType: webhook?.webhookType || WebhookType.CUSTOM,
      endpointUrl: webhook?.endpointUrl || '',
      httpMethod: webhook?.httpMethod || HttpMethod.POST,
      headers: webhook?.headers
        ? Object.entries(webhook.headers).map(([key, value]) => ({ key, value }))
        : [{ key: 'Content-Type', value: 'application/json' }],
      authType: webhook?.authType || AuthType.NONE,
      authConfig: webhook?.authConfig || {},
      payloadTemplateJson: webhook?.payloadTemplate
        ? JSON.stringify(webhook.payloadTemplate, null, 2)
        : '',
      retryConfig: webhook?.retryConfig || {
        maxRetries: 3,
        retryDelaySeconds: 60,
      },
      timeoutSeconds: webhook?.timeoutSeconds || 30,
      events: webhook?.events || [],
      isActive: webhook?.isActive ?? true,
    },
  })

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: 'headers',
  })

  const watchAuthType = form.watch('authType')
  const watchEvents = form.watch('events')

  const onSubmit = async (data: WebhookFormData) => {
    try {
      // Convert headers array to object
      const headers: Record<string, string> = {}
      data.headers.forEach((h) => {
        headers[h.key] = h.value
      })

      // Parse payload template JSON if provided
      let payloadTemplate: Record<string, unknown> | undefined
      if (data.payloadTemplateJson) {
        try {
          payloadTemplate = JSON.parse(data.payloadTemplateJson)
        } catch (e) {
          form.setError('payloadTemplateJson', {
            message: 'Invalid JSON format',
          })
          return
        }
      }

      const payload = {
        ...data,
        headers,
        payloadTemplate,
        payloadTemplateJson: undefined,
      }

      if (isEditing && webhook) {
        await updateMutation.mutateAsync({
          id: webhook.id,
          data: payload,
        })
      } else {
        await createMutation.mutateAsync(payload)
      }

      router.push(`/${locale}/dashboard/admin/communications/webhooks`)
    } catch (error) {
      // Error handling is done in mutation hooks
    }
  }

  const addEvent = () => {
    if (eventInput && !watchEvents.includes(eventInput)) {
      form.setValue('events', [...watchEvents, eventInput])
      setEventInput('')
    }
  }

  const removeEvent = (event: string) => {
    form.setValue(
      'events',
      watchEvents.filter((e) => e !== event)
    )
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addEvent()
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>{t('basicInfo')}</CardTitle>
            <CardDescription>
              {t('basicInfoDesc')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('nameLabel')}</FormLabel>
                  <FormControl>
                    <Input placeholder={t('namePlaceholder')} {...field} />
                  </FormControl>
                  <FormDescription>
                    {t('nameDesc')}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid gap-4 md:grid-cols-2">
              <FormField
                control={form.control}
                name="webhookType"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('typeLabel')}</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder={t('typePlaceholder')} />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value={WebhookType.WHATSAPP}>
                          WhatsApp
                        </SelectItem>
                        <SelectItem value={WebhookType.CUSTOM}>
                          Custom
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="httpMethod"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('httpMethodLabel')}</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder={t('httpMethodPlaceholder')} />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {Object.values(HttpMethod).map((method) => (
                          <SelectItem key={method} value={method}>
                            {method}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="endpointUrl"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('endpointLabel')}</FormLabel>
                  <FormControl>
                    <Input
                      type="url"
                      placeholder={t('endpointPlaceholder')}
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>
                    {t('endpointDesc')}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid gap-4 md:grid-cols-2">
              <FormField
                control={form.control}
                name="timeoutSeconds"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('timeoutLabel')}</FormLabel>
                    <FormControl>
                      <Input type="number" min={1} max={300} {...field} />
                    </FormControl>
                    <FormDescription>
                      {t('timeoutDesc')}
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="isActive"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                    <div className="space-y-0.5">
                      <FormLabel className="text-base">{t('activeLabel')}</FormLabel>
                      <FormDescription>
                        {t('activeDesc')}
                      </FormDescription>
                    </div>
                    <FormControl>
                      <Switch
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                  </FormItem>
                )}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('authentication')}</CardTitle>
            <CardDescription>
              {t('authenticationDesc')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <FormField
              control={form.control}
              name="authType"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('authTypeLabel')}</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    defaultValue={field.value}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder={t('authTypePlaceholder')} />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value={AuthType.NONE}>{t('authTypeNone')}</SelectItem>
                      <SelectItem value={AuthType.API_KEY}>{t('authTypeApiKey')}</SelectItem>
                      <SelectItem value={AuthType.BEARER}>{t('authTypeBearer')}</SelectItem>
                      <SelectItem value={AuthType.BASIC}>{t('authTypeBasic')}</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {watchAuthType === AuthType.API_KEY && (
              <>
                <FormField
                  control={form.control}
                  name="authConfig.apiKeyHeader"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('apiKeyHeader')}</FormLabel>
                      <FormControl>
                        <Input placeholder={t('apiKeyHeaderPlaceholder')} {...field} />
                      </FormControl>
                      <FormDescription>
                        {t('apiKeyHeaderDesc')}
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="authConfig.apiKey"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('apiKeyLabel')}</FormLabel>
                      <FormControl>
                        <Input type="password" placeholder={t('apiKeyPlaceholder')} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </>
            )}

            {watchAuthType === AuthType.BEARER && (
              <FormField
                control={form.control}
                name="authConfig.bearerToken"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('bearerTokenLabel')}</FormLabel>
                    <FormControl>
                      <Input type="password" placeholder={t('bearerTokenPlaceholder')} {...field} />
                    </FormControl>
                    <FormDescription>
                      {t('bearerTokenDesc')}
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            {watchAuthType === AuthType.BASIC && (
              <>
                <FormField
                  control={form.control}
                  name="authConfig.basicUsername"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('usernameLabel')}</FormLabel>
                      <FormControl>
                        <Input placeholder={t('usernamePlaceholder')} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="authConfig.basicPassword"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('passwordLabel')}</FormLabel>
                      <FormControl>
                        <Input type="password" placeholder={t('passwordPlaceholder')} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>{t('customHeaders')}</CardTitle>
                <CardDescription>
                  {t('customHeadersDesc')}
                </CardDescription>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => append({ key: '', value: '' })}
              >
                <Plus className="mr-2 h-4 w-4" />
                {t('addHeader')}
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {fields.map((field, index) => (
              <div key={field.id} className="flex gap-2">
                <FormField
                  control={form.control}
                  name={`headers.${index}.key`}
                  render={({ field }) => (
                    <FormItem className="flex-1">
                      {index === 0 && <FormLabel>{t('headerName')}</FormLabel>}
                      <FormControl>
                        <Input placeholder="Content-Type" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name={`headers.${index}.value`}
                  render={({ field }) => (
                    <FormItem className="flex-1">
                      {index === 0 && <FormLabel>{t('headerValue')}</FormLabel>}
                      <FormControl>
                        <Input placeholder="application/json" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => remove(index)}
                  className={index === 0 ? 'mt-8' : ''}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <CardTitle>{t('payloadTemplate')}</CardTitle>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <HelpCircle className="h-4 w-4 text-muted-foreground" />
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="max-w-xs">
                      {t('payloadHint')}
                    </p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
            <CardDescription>
              {t('payloadTemplateDesc')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <FormField
              control={form.control}
              name="payloadTemplateJson"
              render={({ field }) => (
                <FormItem>
                  <FormControl>
                    <Textarea
                      placeholder={'{\n  "message": "{{message}}",\n  "user": "{{user_id}}"\n}'}
                      className="font-mono text-sm"
                      rows={10}
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>
                    {t('payloadValid')}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('events')}</CardTitle>
            <CardDescription>
              {t('eventsDesc')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                placeholder={t('eventPlaceholder')}
                value={eventInput}
                onChange={(e) => setEventInput(e.target.value)}
                onKeyDown={handleKeyDown}
              />
              <Button type="button" onClick={addEvent} variant="outline">
                {t('addEvent')}
              </Button>
            </div>

            {watchEvents.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {watchEvents.map((event) => (
                  <div
                    key={event}
                    className="flex items-center gap-1 rounded-md border bg-secondary px-3 py-1 text-sm"
                  >
                    <span>{event}</span>
                    <button
                      type="button"
                      onClick={() => removeEvent(event)}
                      className="ml-1 hover:text-destructive"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('retryConfig')}</CardTitle>
            <CardDescription>
              {t('retryConfigDesc')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <FormField
                control={form.control}
                name="retryConfig.maxRetries"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('maxRetriesLabel')}</FormLabel>
                    <FormControl>
                      <Input type="number" min={0} max={10} {...field} />
                    </FormControl>
                    <FormDescription>
                      {t('maxRetriesDesc')}
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="retryConfig.retryDelaySeconds"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('retryDelayLabel')}</FormLabel>
                    <FormControl>
                      <Input type="number" min={1} max={3600} {...field} />
                    </FormControl>
                    <FormDescription>
                      {t('retryDelayDesc')}
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
          </CardContent>
        </Card>

        <div className="flex items-center justify-end gap-4">
          <Button
            type="button"
            variant="outline"
            onClick={() => router.back()}
          >
            {t('cancel')}
          </Button>
          <Button
            type="submit"
            disabled={createMutation.isPending || updateMutation.isPending}
          >
            {createMutation.isPending || updateMutation.isPending
              ? t('saving')
              : isEditing
              ? t('updateWebhook')
              : t('createWebhook')}
          </Button>
        </div>
      </form>
    </Form>
  )
}
