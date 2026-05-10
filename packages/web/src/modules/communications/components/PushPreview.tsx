/**
 * PushPreview Component
 * Mobile push notification preview showing how notification will appear on devices
 */

import React from 'react'
import { Bell, X, ChevronDown } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { PushNotificationPreview } from '../types'

interface PushPreviewProps {
  preview: PushNotificationPreview
  appName?: string
  appIcon?: string
  className?: string
}

export function PushPreview({
  preview,
  appName = 'Facil',
  appIcon,
  className = '',
}: PushPreviewProps) {
  const currentTime = new Date().toLocaleTimeString('es-ES', {
    hour: '2-digit',
    minute: '2-digit',
  })

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Platform Badge */}
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-muted-foreground">Preview:</span>
        <Badge variant="outline" className="capitalize">
          {preview.platform === 'all' ? 'All Platforms' : preview.platform}
        </Badge>
      </div>

      {/* Mobile Device Frame */}
      <div className="mx-auto max-w-sm">
        {/* iOS Style Notification */}
        {(preview.platform === 'ios' || preview.platform === 'all') && (
          <div className="mb-4">
            <p className="text-xs font-medium text-muted-foreground mb-2">iOS</p>
            <Card className="overflow-hidden shadow-lg border-gray-200">
              <div className="bg-gray-50 p-3">
                {/* Status Bar */}
                <div className="flex items-center justify-between text-xs mb-2">
                  <span className="font-semibold">{currentTime}</span>
                  <div className="flex items-center gap-1">
                    <div className="w-4 h-3 bg-gray-400 rounded-sm" />
                    <div className="w-1 h-1 rounded-full bg-gray-400" />
                  </div>
                </div>

                {/* Notification Card */}
                <Card className="bg-white shadow-md">
                  <CardContent className="p-3">
                    <div className="flex gap-3">
                      {/* App Icon */}
                      <div className="flex-shrink-0">
                        {preview.iconUrl || appIcon ? (
                          <img
                            src={preview.iconUrl || appIcon}
                            alt={appName}
                            className="w-8 h-8 rounded-lg"
                          />
                        ) : (
                          <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center">
                            <Bell className="w-4 h-4 text-white" />
                          </div>
                        )}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between mb-1">
                          <p className="text-xs font-semibold text-gray-600">{appName}</p>
                          <span className="text-xs text-gray-400">now</span>
                        </div>
                        <p className="text-sm font-semibold text-gray-900 mb-1 line-clamp-2">
                          {preview.title}
                        </p>
                        <p className="text-sm text-gray-700 line-clamp-3">
                          {preview.body}
                        </p>

                        {/* Image (if provided) */}
                        {preview.imageUrl && (
                          <div className="mt-2 rounded-lg overflow-hidden">
                            <img
                              src={preview.imageUrl}
                              alt="Notification"
                              className="w-full h-32 object-cover"
                            />
                          </div>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </Card>
          </div>
        )}

        {/* Android Style Notification */}
        {(preview.platform === 'android' || preview.platform === 'all') && (
          <div className="mb-4">
            <p className="text-xs font-medium text-muted-foreground mb-2">Android</p>
            <Card className="overflow-hidden shadow-lg border-gray-200">
              <div className="bg-gray-900 p-3">
                {/* Status Bar */}
                <div className="flex items-center justify-between text-xs mb-2 text-white">
                  <span>{currentTime}</span>
                  <div className="flex items-center gap-1">
                    <div className="w-4 h-3 bg-white opacity-70 rounded-sm" />
                  </div>
                </div>

                {/* Notification Card */}
                <Card className="bg-white">
                  <CardContent className="p-3">
                    <div className="flex gap-3">
                      {/* App Icon */}
                      <div className="flex-shrink-0">
                        {preview.iconUrl || appIcon ? (
                          <img
                            src={preview.iconUrl || appIcon}
                            alt={appName}
                            className="w-6 h-6 rounded-full"
                          />
                        ) : (
                          <div className="w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center">
                            <Bell className="w-3 h-3 text-white" />
                          </div>
                        )}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between mb-1">
                          <p className="text-xs font-medium text-gray-600">{appName}</p>
                          <div className="flex items-center gap-1">
                            <span className="text-xs text-gray-400">now</span>
                            <ChevronDown className="w-3 h-3 text-gray-400" />
                          </div>
                        </div>
                        <p className="text-sm font-medium text-gray-900 mb-1 line-clamp-2">
                          {preview.title}
                        </p>
                        <p className="text-sm text-gray-700 line-clamp-4">
                          {preview.body}
                        </p>

                        {/* Image (if provided) */}
                        {preview.imageUrl && (
                          <div className="mt-2 rounded overflow-hidden">
                            <img
                              src={preview.imageUrl}
                              alt="Notification"
                              className="w-full h-40 object-cover"
                            />
                          </div>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </Card>
          </div>
        )}

        {/* Web/Desktop Style Notification */}
        {(preview.platform === 'web' || preview.platform === 'all') && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-2">Web (Desktop)</p>
            <Card className="shadow-xl border-gray-300">
              <CardContent className="p-4">
                <div className="flex gap-3">
                  {/* App Icon */}
                  <div className="flex-shrink-0">
                    {preview.iconUrl || appIcon ? (
                      <img
                        src={preview.iconUrl || appIcon}
                        alt={appName}
                        className="w-10 h-10 rounded"
                      />
                    ) : (
                      <div className="w-10 h-10 rounded bg-blue-500 flex items-center justify-center">
                        <Bell className="w-5 h-5 text-white" />
                      </div>
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <p className="text-sm font-semibold text-gray-900">{appName}</p>
                        <p className="text-xs text-gray-500">{preview.title}</p>
                      </div>
                      <button className="text-gray-400 hover:text-gray-600">
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                    <p className="text-sm text-gray-700 line-clamp-3">
                      {preview.body}
                    </p>

                    {/* Image (if provided) */}
                    {preview.imageUrl && (
                      <div className="mt-3 rounded overflow-hidden">
                        <img
                          src={preview.imageUrl}
                          alt="Notification"
                          className="w-full h-48 object-cover"
                        />
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>

      {/* Variables Used */}
      {Object.keys(preview.variablesUsed).length > 0 && (
        <div className="text-xs text-muted-foreground">
          <p className="font-medium mb-1">Variables used:</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(preview.variablesUsed).map(([key, value]) => (
              <Badge key={key} variant="secondary" className="text-xs">
                {key}: {value}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
