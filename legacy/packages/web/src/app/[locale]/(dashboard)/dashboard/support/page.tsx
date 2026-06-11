'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import Link from 'next/link'
import { Plus, HelpCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { TicketList, useSupport } from '@/modules/support'

export default function UserSupportPage() {
  const t = useTranslations('support')
  const locale = useLocale()
  const router = useRouter()

  const {
    tickets,
    isLoading,
    pagination,
    loadMyTickets,
  } = useSupport()

  useEffect(() => {
    loadMyTickets(1, 10)
  }, [loadMyTickets])

  const handlePageChange = (page: number) => {
    loadMyTickets(page, 10)
  }

  const handleCreateClick = () => {
    router.push(`/${locale}/dashboard/support/new`)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('pageTitle')}</h1>
          <p className="text-muted-foreground mt-2">
            {t('pageSubtitle')}
          </p>
        </div>
        <Link href={`/${locale}/dashboard/support/new`}>
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            {t('newTicket')}
          </Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('myRequestsTitle')}</CardTitle>
          <CardDescription>{t('myRequestsDesc')}</CardDescription>
        </CardHeader>
        <CardContent>
          <TicketList
            tickets={tickets}
            isLoading={isLoading}
            basePath={`/${locale}/dashboard/support`}
            locale={locale}
            pagination={pagination}
            onPageChange={handlePageChange}
            showCreateButton={false}
            onCreateClick={handleCreateClick}
          />
        </CardContent>
      </Card>

      {/* FAQ / Aide Rapide */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HelpCircle className="h-5 w-5" />
            {t('faqTitle')}
          </CardTitle>
          <CardDescription>
            {t('faqDesc')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <h4 className="font-medium">{t('faqQuestion1')}</h4>
            <p className="text-sm text-muted-foreground">
              {t('faqAnswer1')}
            </p>
          </div>
          <div className="space-y-2">
            <h4 className="font-medium">{t('faqQuestion2')}</h4>
            <p className="text-sm text-muted-foreground">
              {t('faqAnswer2')}
            </p>
          </div>
          <div className="space-y-2">
            <h4 className="font-medium">{t('faqQuestion3')}</h4>
            <p className="text-sm text-muted-foreground">
              {t('faqAnswer3')}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
