/**
 * View Notification Template Page
 * Display notification template details
 */

'use client'

import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Loader2, Edit, Trash2, ArrowLeft, CheckCircle, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import {
  useNotificationTemplate,
  useDeleteNotificationTemplate,
} from '@/modules/communications/hooks/useNotificationTemplates'
import {
  NOTIFICATION_TYPE_LABELS,
  NOTIFICATION_PRIORITY_LABELS,
} from '@/modules/communications/types/notification-template'

export default function ViewNotificationTemplatePage() {
  const params = useParams()
  const router = useRouter()
  const templateId = parseInt(params.id as string)
  const locale = params.locale as string

  const { data: template, isLoading, error } = useNotificationTemplate(templateId)
  const deleteMutation = useDeleteNotificationTemplate()

  const handleDelete = async () => {
    await deleteMutation.mutateAsync(templateId)
    router.push(`/${locale}/dashboard/admin/communications/notification-templates`)
  }

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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href={`/${locale}/dashboard/admin/communications/notification-templates`}>
            <Button variant="outline" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{template.nameEs}</h1>
            <p className="text-muted-foreground">
              Template Code: <code className="text-sm">{template.templateCode}</code>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Link href={`/${locale}/dashboard/admin/communications/notification-templates/${template.id}/edit`}>
            <Button variant="outline">
              <Edit className="mr-2 h-4 w-4" />
              Edit
            </Button>
          </Link>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive">
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete Notification Template</AlertDialogTitle>
                <AlertDialogDescription>
                  Are you sure you want to delete this notification template? This action cannot be
                  undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={handleDelete} className="bg-destructive">
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {/* Basic Information */}
      <Card>
        <CardHeader>
          <CardTitle>Basic Information</CardTitle>
          <CardDescription>Template configuration and settings</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Template Code</p>
              <p className="text-base font-mono">{template.templateCode}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Status</p>
              <div className="mt-1">
                {template.isActive ? (
                  <Badge variant="outline" className="bg-green-100 text-green-800 border-green-200">
                    <CheckCircle className="mr-1 h-3 w-3" />
                    Active
                  </Badge>
                ) : (
                  <Badge variant="outline" className="bg-gray-100 text-gray-800 border-gray-200">
                    <XCircle className="mr-1 h-3 w-3" />
                    Inactive
                  </Badge>
                )}
              </div>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Notification Type</p>
              <p className="text-base">{NOTIFICATION_TYPE_LABELS[template.notificationType]}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Priority</p>
              <p className="text-base">{NOTIFICATION_PRIORITY_LABELS[template.priority]}</p>
            </div>
            {template.icon && (
              <div>
                <p className="text-sm font-medium text-muted-foreground">Icon</p>
                <p className="text-base font-mono">{template.icon}</p>
              </div>
            )}
            {template.actionUrl && (
              <div className="md:col-span-2">
                <p className="text-sm font-medium text-muted-foreground">Action URL</p>
                <p className="text-base font-mono">{template.actionUrl}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Content */}
      <Card>
        <CardHeader>
          <CardTitle>Notification Content</CardTitle>
          <CardDescription>Title and body in multiple languages</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="es">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="es">Spanish</TabsTrigger>
              <TabsTrigger value="fr">French</TabsTrigger>
              <TabsTrigger value="en">English</TabsTrigger>
            </TabsList>

            <TabsContent value="es" className="space-y-4">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Template Name</p>
                <p className="text-base">{template.nameEs}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Notification Title</p>
                <p className="text-base">{template.titleEs}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Notification Body</p>
                <p className="text-base whitespace-pre-wrap">{template.bodyEs}</p>
              </div>
            </TabsContent>

            <TabsContent value="fr" className="space-y-4">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Template Name</p>
                <p className="text-base">{template.nameFr || <em className="text-muted-foreground">Not set</em>}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Notification Title</p>
                <p className="text-base">{template.titleFr || <em className="text-muted-foreground">Not set</em>}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Notification Body</p>
                <p className="text-base whitespace-pre-wrap">{template.bodyFr || <em className="text-muted-foreground">Not set</em>}</p>
              </div>
            </TabsContent>

            <TabsContent value="en" className="space-y-4">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Template Name</p>
                <p className="text-base">{template.nameEn || <em className="text-muted-foreground">Not set</em>}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Notification Title</p>
                <p className="text-base">{template.titleEn || <em className="text-muted-foreground">Not set</em>}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Notification Body</p>
                <p className="text-base whitespace-pre-wrap">{template.bodyEn || <em className="text-muted-foreground">Not set</em>}</p>
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Variables */}
      <Card>
        <CardHeader>
          <CardTitle>Template Variables</CardTitle>
          <CardDescription>Variables used in this template</CardDescription>
        </CardHeader>
        <CardContent>
          {template.variables && template.variables.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {template.variables.map((variable) => (
                <Badge key={variable} variant="secondary">
                  {variable}
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground">No variables defined</p>
          )}
        </CardContent>
      </Card>

      {/* Metadata */}
      <Card>
        <CardHeader>
          <CardTitle>Metadata</CardTitle>
          <CardDescription>Template creation and update information</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex justify-between">
            <span className="text-sm text-muted-foreground">Created At:</span>
            <span className="text-sm">{new Date(template.createdAt).toLocaleString()}</span>
          </div>
          {template.updatedAt && (
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">Updated At:</span>
              <span className="text-sm">{new Date(template.updatedAt).toLocaleString()}</span>
            </div>
          )}
          {template.createdBy && (
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">Created By:</span>
              <span className="text-sm">User ID: {template.createdBy}</span>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
