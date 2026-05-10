'use client'

import { useParams } from 'next/navigation'
import { MessageCircle, Mail, MessageSquare } from 'lucide-react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { SmsProviderSettings } from '@/modules/communications/components/SmsProviderSettings'
import { EmailProviderSettings } from '@/modules/communications/components/EmailProviderSettings'
import { WhatsAppProviderSettings } from '@/modules/communications/components/WhatsAppProviderSettings'

const translations = {
  es: {
    title: 'Configuracion de Proveedores',
    subtitle: 'Configure los proveedores de comunicacion (SMS, Email, WhatsApp)',
    sms: 'SMS',
    email: 'Email',
    whatsapp: 'WhatsApp',
  },
  fr: {
    title: 'Configuration des Fournisseurs',
    subtitle: 'Configurez les fournisseurs de communication (SMS, Email, WhatsApp)',
    sms: 'SMS',
    email: 'Email',
    whatsapp: 'WhatsApp',
  },
  en: {
    title: 'Provider Settings',
    subtitle: 'Configure communication providers (SMS, Email, WhatsApp)',
    sms: 'SMS',
    email: 'Email',
    whatsapp: 'WhatsApp',
  },
}

export default function ProviderSettingsPage() {
  const params = useParams()
  const locale = (params?.locale as string) || 'es'
  const t = translations[locale as keyof typeof translations] || translations.es

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t.title}</h1>
        <p className="text-muted-foreground mt-2">{t.subtitle}</p>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="sms" className="space-y-6">
        <TabsList className="grid w-full grid-cols-3 lg:w-[500px]">
          <TabsTrigger value="sms" className="flex items-center gap-2">
            <MessageCircle className="h-4 w-4" />
            <span className="hidden sm:inline">{t.sms}</span>
            <span className="sm:hidden">SMS</span>
          </TabsTrigger>
          <TabsTrigger value="email" className="flex items-center gap-2">
            <Mail className="h-4 w-4" />
            <span>{t.email}</span>
          </TabsTrigger>
          <TabsTrigger value="whatsapp" className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4" />
            <span>{t.whatsapp}</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="sms" className="mt-6">
          <SmsProviderSettings locale={locale} />
        </TabsContent>

        <TabsContent value="email" className="mt-6">
          <EmailProviderSettings locale={locale} />
        </TabsContent>

        <TabsContent value="whatsapp" className="mt-6">
          <WhatsAppProviderSettings locale={locale} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
