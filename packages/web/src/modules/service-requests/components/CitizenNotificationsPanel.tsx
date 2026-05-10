'use client'

import { useState } from 'react'
import {
  Bell,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  Calendar,
  CreditCard,
  MessageSquare,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

export interface CitizenNotification {
  id: string
  action: string
  title: string
  message?: string | null
  performed_at: string
  performer_role?: string | null
  is_new: boolean
  new_status?: string | null
}

interface CitizenNotificationsPanelProps {
  notifications: CitizenNotification[]
  unreadCount: number
  locale?: string
}

const ACTION_ICONS: Record<string, React.ElementType> = {
  status_change: CheckCircle,
  agent_action_taken: AlertCircle,
  comment_added: MessageSquare,
  cita_scheduled: Calendar,
  cita_rescheduled: Calendar,
  cita_cancelled: XCircle,
  payment_received: CreditCard,
  payment_failed: XCircle,
  validation_failed: AlertCircle,
}

const ACTION_COLORS: Record<string, string> = {
  status_change: 'text-blue-500',
  agent_action_taken: 'text-amber-500',
  comment_added: 'text-purple-500',
  cita_scheduled: 'text-cyan-500',
  cita_rescheduled: 'text-cyan-500',
  cita_cancelled: 'text-red-500',
  payment_received: 'text-green-500',
  payment_failed: 'text-red-500',
  validation_failed: 'text-orange-500',
}

function formatRelativeTime(dateString: string, locale: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMin < 1) return locale === 'es' ? 'Ahora' : locale === 'fr' ? 'Maintenant' : 'Now'
  if (diffMin < 60) return locale === 'es' ? `hace ${diffMin} min` : locale === 'fr' ? `il y a ${diffMin} min` : `${diffMin} min ago`
  if (diffHours < 24) return locale === 'es' ? `hace ${diffHours}h` : locale === 'fr' ? `il y a ${diffHours}h` : `${diffHours}h ago`
  if (diffDays < 7) return locale === 'es' ? `hace ${diffDays}d` : locale === 'fr' ? `il y a ${diffDays}j` : `${diffDays}d ago`

  return date.toLocaleDateString(locale === 'es' ? 'es-GQ' : locale === 'fr' ? 'fr-FR' : 'en-US', {
    day: '2-digit',
    month: 'short',
  })
}

const ACTION_TITLES: Record<string, Record<string, string>> = {
  status_change: { es: 'Cambio de estado', fr: 'Changement de statut', en: 'Status change' },
  agent_action_taken: { es: 'Accion del agente', fr: "Action de l'agent", en: 'Agent action' },
  comment_added: { es: 'Comentario', fr: 'Commentaire', en: 'Comment' },
  cita_scheduled: { es: 'Cita programada', fr: 'Rendez-vous programmé', en: 'Appointment scheduled' },
  cita_rescheduled: { es: 'Cita reprogramada', fr: 'Rendez-vous reprogrammé', en: 'Appointment rescheduled' },
  cita_cancelled: { es: 'Cita cancelada', fr: 'Rendez-vous annulé', en: 'Appointment cancelled' },
  payment_received: { es: 'Pago recibido', fr: 'Paiement reçu', en: 'Payment received' },
  payment_failed: { es: 'Pago fallido', fr: 'Paiement échoué', en: 'Payment failed' },
  validation_failed: { es: 'Validacion fallida', fr: 'Validation échouée', en: 'Validation failed' },
}

export function CitizenNotificationsPanel({ notifications, unreadCount, locale = 'es' }: CitizenNotificationsPanelProps) {
  const [expanded, setExpanded] = useState(unreadCount > 0)

  if (notifications.length === 0) return null

  const labels = {
    es: { title: 'Notificaciones', showHistory: 'Ver historial', hideHistory: 'Ocultar historial' },
    fr: { title: 'Notifications', showHistory: 'Voir historique', hideHistory: 'Masquer historique' },
    en: { title: 'Notifications', showHistory: 'View history', hideHistory: 'Hide history' },
  }
  const l = labels[locale as keyof typeof labels] || labels.es

  return (
    <Card className="h-fit">
      <CardHeader className="py-3 px-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Bell className="h-4 w-4" />
            {l.title}
            {unreadCount > 0 && (
              <Badge variant="destructive" className="h-5 min-w-5 px-1.5 text-[10px]">
                {unreadCount}
              </Badge>
            )}
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
        </div>
      </CardHeader>

      {expanded && (
        <CardContent className="px-4 pb-4 pt-0">
          <div className="space-y-3 max-h-[400px] overflow-y-auto">
            {notifications.map((notif) => {
              const Icon = ACTION_ICONS[notif.action] || Clock
              const color = ACTION_COLORS[notif.action] || 'text-gray-500'

              return (
                <div
                  key={notif.id}
                  className={`flex gap-3 p-2 rounded-lg transition-colors ${
                    notif.is_new ? 'bg-blue-50 dark:bg-blue-950/20' : ''
                  }`}
                >
                  <div className={`flex-shrink-0 mt-0.5 ${color}`}>
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium truncate">{ACTION_TITLES[notif.action]?.[locale] || notif.title}</p>
                      {notif.is_new && (
                        <span className="flex-shrink-0 w-2 h-2 rounded-full bg-blue-500" />
                      )}
                    </div>
                    {notif.message && (
                      <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                        {notif.message}
                      </p>
                    )}
                    <p className="text-[10px] text-muted-foreground mt-1">
                      {formatRelativeTime(notif.performed_at, locale)}
                    </p>
                  </div>
                </div>
              )
            })}
          </div>
        </CardContent>
      )}

      {!expanded && unreadCount === 0 && (
        <CardContent className="px-4 pb-3 pt-0">
          <Button
            variant="ghost"
            size="sm"
            className="w-full text-xs text-muted-foreground"
            onClick={() => setExpanded(true)}
          >
            {l.showHistory}
          </Button>
        </CardContent>
      )}
    </Card>
  )
}
