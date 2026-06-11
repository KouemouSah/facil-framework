'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useToast } from '@/hooks/use-toast'
import { TicketForm, useSupport } from '@/modules/support'
import type { SupportTicketCreate } from '@/modules/support'

export default function NewTicketPage() {
  const t = useTranslations('support')
  const locale = useLocale()
  const router = useRouter()
  const { toast } = useToast()

  const {
    categories,
    isLoading,
    loadCategories,
    createTicket,
  } = useSupport()

  useEffect(() => {
    loadCategories(true, 'user')
  }, [loadCategories])

  const handleSubmit = async (data: SupportTicketCreate) => {
    try {
      await createTicket(data)
      toast({
        title: t('ticketCreated'),
        description: t('ticketCreatedMessage'),
      })
      router.push(`/${locale}/dashboard/support`)
    } catch (error) {
      toast({
        title: t('errorRequired'),
        description: t('errorRequiredMessage'),
        variant: 'destructive',
      })
    }
  }

  const handleCancel = () => {
    router.push(`/${locale}/dashboard/support`)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href={`/${locale}/dashboard/support`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('newRequestTitle')}</h1>
          <p className="text-muted-foreground mt-2">
            {t('newRequestDesc')}
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('createTicket')}</CardTitle>
          <CardDescription>{t('newRequestDesc')}</CardDescription>
        </CardHeader>
        <CardContent>
          <TicketForm
            categories={categories}
            isLoading={isLoading}
            onSubmit={handleSubmit}
            onCancel={handleCancel}
            locale={locale}
          />
        </CardContent>
      </Card>
    </div>
  )
}
