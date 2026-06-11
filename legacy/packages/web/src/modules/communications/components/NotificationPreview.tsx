/**
 * NotificationPreview Component
 * Live preview of how a notification will appear
 */

'use client'

import { X, Info, CheckCircle, AlertTriangle, XCircle, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import type { NotificationPreviewResponse } from '../types/notification-template'
import { NOTIFICATION_PRIORITY_LABELS } from '../types/notification-template'

interface NotificationPreviewProps {
  preview: NotificationPreviewResponse
  onClose: () => void
  isDialog?: boolean
}

export function NotificationPreview({ preview, onClose, isDialog = true }: NotificationPreviewProps) {
  const getIcon = () => {
    const iconClasses = 'h-5 w-5'
    switch (preview.notificationType) {
      case 'info':
        return <Info className={iconClasses} />
      case 'success':
        return <CheckCircle className={iconClasses} />
      case 'warning':
        return <AlertTriangle className={iconClasses} />
      case 'error':
        return <XCircle className={iconClasses} />
      default:
        return <Info className={iconClasses} />
    }
  }

  const getColorClasses = () => {
    switch (preview.notificationType) {
      case 'info':
        return 'border-l-blue-500 bg-blue-50 text-blue-900'
      case 'success':
        return 'border-l-green-500 bg-green-50 text-green-900'
      case 'warning':
        return 'border-l-yellow-500 bg-yellow-50 text-yellow-900'
      case 'error':
        return 'border-l-red-500 bg-red-50 text-red-900'
      default:
        return 'border-l-gray-500 bg-gray-50 text-gray-900'
    }
  }

  const getPriorityBadge = () => {
    const colors = {
      low: 'bg-gray-100 text-gray-800 border-gray-200',
      normal: 'bg-blue-100 text-blue-800 border-blue-200',
      high: 'bg-orange-100 text-orange-800 border-orange-200',
      urgent: 'bg-red-100 text-red-800 border-red-200',
    }

    return (
      <Badge variant="outline" className={colors[preview.priority]}>
        {NOTIFICATION_PRIORITY_LABELS[preview.priority]}
      </Badge>
    )
  }

  const NotificationCard = () => (
    <div className="space-y-4">
      {/* Priority Badge */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">Priority Level:</span>
        {getPriorityBadge()}
      </div>

      {/* Notification Preview */}
      <Card className={`border-l-4 ${getColorClasses()}`}>
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 mt-0.5">{getIcon()}</div>
            <div className="flex-1 space-y-2">
              <h3 className="font-semibold text-base">{preview.title}</h3>
              <p className="text-sm whitespace-pre-wrap">{preview.body}</p>
              {preview.actionUrl && (
                <Button variant="link" size="sm" className="h-auto p-0 text-current">
                  View Details
                  <ExternalLink className="ml-1 h-3 w-3" />
                </Button>
              )}
            </div>
            <button className="flex-shrink-0 text-current hover:opacity-70">
              <X className="h-4 w-4" />
            </button>
          </div>
        </CardContent>
      </Card>

      {/* Metadata */}
      <div className="rounded-lg border bg-muted/50 p-4 space-y-2 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Type:</span>
          <Badge variant="secondary">{preview.notificationType}</Badge>
        </div>
        {preview.icon && (
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Icon:</span>
            <code className="text-xs bg-background px-2 py-1 rounded">{preview.icon}</code>
          </div>
        )}
        {preview.actionUrl && (
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Action URL:</span>
            <code className="text-xs bg-background px-2 py-1 rounded truncate max-w-[200px]">
              {preview.actionUrl}
            </code>
          </div>
        )}
      </div>

      {/* Instructions */}
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
        <p className="font-medium mb-1">Preview Information</p>
        <p className="text-blue-700">
          This is how the notification will appear to users in the application. The actual
          notification may vary slightly based on the user&apos;s device and browser.
        </p>
      </div>
    </div>
  )

  if (isDialog) {
    return (
      <Dialog open onOpenChange={onClose}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Notification Preview</DialogTitle>
          </DialogHeader>
          <NotificationCard />
        </DialogContent>
      </Dialog>
    )
  }

  return <NotificationCard />
}
