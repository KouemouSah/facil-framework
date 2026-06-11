'use client'

import Link from 'next/link'
import { useLocale } from 'next-intl'
import { Mail, MessageCircle, Webhook, Phone, Bell, Send, Settings } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

interface CommunicationCard {
  title: string
  description: string
  icon: React.ComponentType<{ className?: string }>
  href: string
  stats?: string
}

export default function CommunicationsPage() {
  const locale = useLocale()

  const communicationCards: CommunicationCard[] = [
    {
      title: 'Email Templates',
      description: 'Manage email templates for automated communications',
      icon: Mail,
      href: `/${locale}/dashboard/admin/communications/email-templates`,
      stats: 'Manage templates'
    },
    {
      title: 'SMS Templates',
      description: 'Configure SMS templates for notifications',
      icon: MessageCircle,
      href: `/${locale}/dashboard/admin/communications/sms-templates`,
      stats: 'Manage templates'
    },
    {
      title: 'Notification Templates',
      description: 'Manage in-app notification templates',
      icon: Bell,
      href: `/${locale}/dashboard/admin/communications/notification-templates`,
      stats: 'Manage templates'
    },
    {
      title: 'Push Notification Templates',
      description: 'Configure push notification templates for mobile devices',
      icon: Send,
      href: `/${locale}/dashboard/admin/communications/push-templates`,
      stats: 'Manage templates'
    },
    {
      title: 'Providers',
      description: 'Configure SMS (Infobip), Email (SendGrid), and WhatsApp (Meta) providers',
      icon: Settings,
      href: `/${locale}/dashboard/admin/communications/provider-settings`,
      stats: 'Configure providers'
    },
    {
      title: 'USSD Configuration',
      description: 'Configure USSD menu structures and responses',
      icon: Phone,
      href: `/${locale}/dashboard/admin/communications/ussd`,
      stats: 'Configure USSD'
    },
    {
      title: 'Webhooks',
      description: 'Configure webhook endpoints and manage integrations',
      icon: Webhook,
      href: `/${locale}/dashboard/admin/communications/webhooks`,
      stats: 'Manage webhooks'
    }
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Communications Management</h1>
        <p className="text-muted-foreground mt-2">
          Manage all communication templates and configurations
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {communicationCards.map((card) => {
          const Icon = card.icon
          return (
            <Link key={card.href} href={card.href}>
              <Card className="hover:bg-accent transition-colors cursor-pointer h-full">
                <CardHeader>
                  <div className="flex items-center gap-4">
                    <div className="p-2 bg-primary/10 rounded-lg">
                      <Icon className="h-6 w-6 text-primary" />
                    </div>
                    <div className="flex-1">
                      <CardTitle className="text-lg">{card.title}</CardTitle>
                    </div>
                  </div>
                  <CardDescription className="mt-3">
                    {card.description}
                  </CardDescription>
                </CardHeader>
                {card.stats && (
                  <CardContent>
                    <p className="text-sm text-muted-foreground">{card.stats}</p>
                  </CardContent>
                )}
              </Card>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
