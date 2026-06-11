/**
 * NotificationTemplateForm Component
 * Form for creating and editing notification templates
 */

'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2, Save, X, Plus, Trash2, Eye } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import {
  useCreateNotificationTemplate,
  useUpdateNotificationTemplate,
  usePreviewNotification,
} from '../hooks/useNotificationTemplates'
import type {
  NotificationTemplateCreate,
  NotificationTemplateUpdate,
  NotificationTemplateResponse,
} from '../types/notification-template'
import { NotificationPreview } from './NotificationPreview'

// Form schema
const notificationTemplateSchema = z.object({
  templateCode: z
    .string()
    .min(1, 'Template code is required')
    .max(100)
    .regex(/^[a-z0-9_-]+$/, 'Only lowercase letters, numbers, hyphens, and underscores allowed'),
  nameEs: z.string().min(1, 'Spanish name is required').max(255),
  nameFr: z.string().max(255).optional(),
  nameEn: z.string().max(255).optional(),
  titleEs: z.string().min(1, 'Spanish title is required').max(255),
  titleFr: z.string().max(255).optional(),
  titleEn: z.string().max(255).optional(),
  bodyEs: z.string().min(1, 'Spanish body is required'),
  bodyFr: z.string().optional(),
  bodyEn: z.string().optional(),
  icon: z.string().max(100).optional(),
  actionUrl: z.string().max(500).optional(),
  variables: z.array(z.string()),
  notificationType: z.enum(['info', 'success', 'warning', 'error']),
  priority: z.enum(['low', 'normal', 'high', 'urgent']),
  isActive: z.boolean(),
})

type FormData = z.infer<typeof notificationTemplateSchema>

interface NotificationTemplateFormProps {
  template?: NotificationTemplateResponse
  locale: string
  mode: 'create' | 'edit'
}

export function NotificationTemplateForm({ template, locale, mode }: NotificationTemplateFormProps) {
  const router = useRouter()
  const [newVariable, setNewVariable] = useState('')
  const [showPreview, setShowPreview] = useState(false)
  const [previewLanguage] = useState<'es' | 'fr' | 'en'>('es')
  const [previewVars, setPreviewVars] = useState<Record<string, string>>({})

  const createMutation = useCreateNotificationTemplate()
  const updateMutation = useUpdateNotificationTemplate()
  const previewMutation = usePreviewNotification()

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(notificationTemplateSchema),
    defaultValues: template
      ? {
          templateCode: template.templateCode,
          nameEs: template.nameEs,
          nameFr: template.nameFr || '',
          nameEn: template.nameEn || '',
          titleEs: template.titleEs,
          titleFr: template.titleFr || '',
          titleEn: template.titleEn || '',
          bodyEs: template.bodyEs,
          bodyFr: template.bodyFr || '',
          bodyEn: template.bodyEn || '',
          icon: template.icon || '',
          actionUrl: template.actionUrl || '',
          variables: template.variables,
          notificationType: template.notificationType,
          priority: template.priority,
          isActive: template.isActive,
        }
      : {
          templateCode: '',
          nameEs: '',
          nameFr: '',
          nameEn: '',
          titleEs: '',
          titleFr: '',
          titleEn: '',
          bodyEs: '',
          bodyFr: '',
          bodyEn: '',
          icon: '',
          actionUrl: '',
          variables: [],
          notificationType: 'info',
          priority: 'normal',
          isActive: true,
        },
  })

  const variables = watch('variables')
  const notificationType = watch('notificationType')
  const priority = watch('priority')

  // Initialize preview variables when template variables change
  useEffect(() => {
    if (variables) {
      const newPreviewVars: Record<string, string> = {}
      variables.forEach((v) => {
        if (!previewVars[v]) {
          newPreviewVars[v] = `{${v}}`
        } else {
          newPreviewVars[v] = previewVars[v]
        }
      })
      setPreviewVars(newPreviewVars)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- previewVars is used inside but shouldn't trigger re-run
  }, [variables])

  const onSubmit = async (data: FormData) => {
    try {
      if (mode === 'create') {
        await createMutation.mutateAsync(data as NotificationTemplateCreate)
        router.push(`/${locale}/dashboard/admin/communications/notification-templates`)
      } else if (template) {
        const updateData: NotificationTemplateUpdate = { ...data }
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        delete (updateData as Record<string, unknown>).templateCode // Cannot update template code
        await updateMutation.mutateAsync({ id: template.id, data: updateData })
        router.push(`/${locale}/dashboard/admin/communications/notification-templates`)
      }
    } catch (error) {
      console.error('Failed to save template:', error)
    }
  }

  const addVariable = () => {
    if (newVariable && !variables.includes(newVariable)) {
      setValue('variables', [...variables, newVariable])
      setNewVariable('')
    }
  }

  const removeVariable = (variable: string) => {
    setValue(
      'variables',
      variables.filter((v) => v !== variable)
    )
  }

  const handlePreview = async () => {
    if (template) {
      try {
        await previewMutation.mutateAsync({
          templateId: template.id,
          language: previewLanguage,
          variables: previewVars,
        })
        setShowPreview(true)
      } catch (error) {
        console.error('Failed to preview:', error)
      }
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            {mode === 'create' ? 'Create' : 'Edit'} Notification Template
          </h1>
          <p className="text-muted-foreground">
            {mode === 'create'
              ? 'Create a new notification template'
              : 'Edit notification template details'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {mode === 'edit' && template && (
            <Button type="button" variant="outline" onClick={handlePreview}>
              <Eye className="mr-2 h-4 w-4" />
              Preview
            </Button>
          )}
          <Button
            type="button"
            variant="outline"
            onClick={() =>
              router.push(`/${locale}/dashboard/admin/communications/notification-templates`)
            }
          >
            <X className="mr-2 h-4 w-4" />
            Cancel
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="mr-2 h-4 w-4" />
                Save
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Basic Information */}
      <Card>
        <CardHeader>
          <CardTitle>Basic Information</CardTitle>
          <CardDescription>Template code and configuration</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="templateCode">
                Template Code <span className="text-destructive">*</span>
              </Label>
              <Input
                id="templateCode"
                {...register('templateCode')}
                placeholder="payment_confirmation"
                disabled={mode === 'edit'}
              />
              {errors.templateCode && (
                <p className="text-sm text-destructive">{errors.templateCode.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="notificationType">
                Notification Type <span className="text-destructive">*</span>
              </Label>
              <Select
                value={notificationType}
                onValueChange={(value) =>
                  setValue('notificationType', value as 'info' | 'success' | 'warning' | 'error')
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="info">Info</SelectItem>
                  <SelectItem value="success">Success</SelectItem>
                  <SelectItem value="warning">Warning</SelectItem>
                  <SelectItem value="error">Error</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="priority">
                Priority <span className="text-destructive">*</span>
              </Label>
              <Select
                value={priority}
                onValueChange={(value) =>
                  setValue('priority', value as 'low' | 'normal' | 'high' | 'urgent')
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="normal">Normal</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="urgent">Urgent</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="icon">Icon (Lucide icon name)</Label>
              <Input id="icon" {...register('icon')} placeholder="CheckCircle" />
              {errors.icon && <p className="text-sm text-destructive">{errors.icon.message}</p>}
            </div>

            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="actionUrl">Action URL</Label>
              <Input
                id="actionUrl"
                {...register('actionUrl')}
                placeholder="/dashboard/payments/{{payment_id}}"
              />
              {errors.actionUrl && (
                <p className="text-sm text-destructive">{errors.actionUrl.message}</p>
              )}
            </div>

            <div className="flex items-center space-x-2">
              <Switch
                id="isActive"
                checked={watch('isActive')}
                onCheckedChange={(checked) => setValue('isActive', checked)}
              />
              <Label htmlFor="isActive">Active</Label>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Multilingual Content */}
      <Card>
        <CardHeader>
          <CardTitle>Multilingual Content</CardTitle>
          <CardDescription>Template name, title, and body in multiple languages</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="es" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="es">Spanish</TabsTrigger>
              <TabsTrigger value="fr">French</TabsTrigger>
              <TabsTrigger value="en">English</TabsTrigger>
            </TabsList>

            <TabsContent value="es" className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="nameEs">
                  Template Name <span className="text-destructive">*</span>
                </Label>
                <Input id="nameEs" {...register('nameEs')} placeholder="Payment Confirmation" />
                {errors.nameEs && (
                  <p className="text-sm text-destructive">{errors.nameEs.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="titleEs">
                  Notification Title <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="titleEs"
                  {...register('titleEs')}
                  placeholder="Pago recibido correctamente"
                />
                {errors.titleEs && (
                  <p className="text-sm text-destructive">{errors.titleEs.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="bodyEs">
                  Notification Body <span className="text-destructive">*</span>
                </Label>
                <Textarea
                  id="bodyEs"
                  {...register('bodyEs')}
                  placeholder="Hemos recibido su pago de {{amount}} para {{service_name}}"
                  rows={4}
                />
                {errors.bodyEs && (
                  <p className="text-sm text-destructive">{errors.bodyEs.message}</p>
                )}
                <p className="text-sm text-muted-foreground">
                  Use {'{{variable_name}}'} for dynamic content
                </p>
              </div>
            </TabsContent>

            <TabsContent value="fr" className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="nameFr">Template Name</Label>
                <Input id="nameFr" {...register('nameFr')} placeholder="Confirmation de Paiement" />
              </div>

              <div className="space-y-2">
                <Label htmlFor="titleFr">Notification Title</Label>
                <Input
                  id="titleFr"
                  {...register('titleFr')}
                  placeholder="Paiement reçu avec succès"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="bodyFr">Notification Body</Label>
                <Textarea
                  id="bodyFr"
                  {...register('bodyFr')}
                  placeholder="Nous avons reçu votre paiement de {{amount}} pour {{service_name}}"
                  rows={4}
                />
              </div>
            </TabsContent>

            <TabsContent value="en" className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="nameEn">Template Name</Label>
                <Input id="nameEn" {...register('nameEn')} placeholder="Payment Confirmation" />
              </div>

              <div className="space-y-2">
                <Label htmlFor="titleEn">Notification Title</Label>
                <Input
                  id="titleEn"
                  {...register('titleEn')}
                  placeholder="Payment received successfully"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="bodyEn">Notification Body</Label>
                <Textarea
                  id="bodyEn"
                  {...register('bodyEn')}
                  placeholder="We have received your payment of {{amount}} for {{service_name}}"
                  rows={4}
                />
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Variables */}
      <Card>
        <CardHeader>
          <CardTitle>Template Variables</CardTitle>
          <CardDescription>
            Variables that can be used in the notification body and action URL
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="variable_name"
              value={newVariable}
              onChange={(e) => setNewVariable(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addVariable())}
            />
            <Button type="button" onClick={addVariable}>
              <Plus className="mr-2 h-4 w-4" />
              Add
            </Button>
          </div>

          {variables && variables.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {variables.map((variable) => (
                <Badge key={variable} variant="secondary" className="pl-3 pr-2">
                  {variable}
                  <button
                    type="button"
                    onClick={() => removeVariable(variable)}
                    className="ml-2 hover:text-destructive"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Preview Dialog */}
      {showPreview && previewMutation.data && (
        <NotificationPreview
          preview={previewMutation.data}
          onClose={() => setShowPreview(false)}
        />
      )}
    </form>
  )
}
