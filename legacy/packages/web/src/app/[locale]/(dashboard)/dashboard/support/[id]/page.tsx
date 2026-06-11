'use client'

import { useEffect, useCallback, useState } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useToast } from '@/hooks/use-toast'
import { TicketDetail, MessageThread, useSupport } from '@/modules/support'
import type { SupportMessageCreate } from '@/modules/support'

export default function UserTicketDetailPage() {
  const t = useTranslations('support')
  const locale = useLocale()
  const router = useRouter()
  const params = useParams()
  const { toast } = useToast()

  const ticketId = Number(params.id)

  // Get current user ID from localStorage
  const [currentUserId, setCurrentUserId] = useState<string>('')

  useEffect(() => {
    // Try to get user ID from stored token payload
    const accessToken = localStorage.getItem('access_token')
    if (accessToken) {
      try {
        const payload = JSON.parse(atob(accessToken.split('.')[1]))
        setCurrentUserId(payload.sub || '')
      } catch {
        setCurrentUserId('')
      }
    }
  }, [])

  const {
    currentTicket,
    messages,
    isLoading,
    loadTicket,
    loadMessages,
    addMessage,
    closeTicket,
  } = useSupport()

  useEffect(() => {
    if (ticketId) {
      loadTicket(ticketId)
      loadMessages(ticketId)
    }
  }, [ticketId, loadTicket, loadMessages])

  const handleBack = () => {
    router.push(`/${locale}/dashboard/support`)
  }

  const handleClose = async () => {
    try {
      await closeTicket(ticketId)
      toast({
        title: t('ticketClosed'),
        description: t('ticketClosedMessage'),
      })
      loadTicket(ticketId)
    } catch (error) {
      toast({
        title: t('errorRequired'),
        description: String(error),
        variant: 'destructive',
      })
    }
  }

  const handleSendMessage = useCallback(async (data: SupportMessageCreate) => {
    await addMessage(ticketId, data)
  }, [ticketId, addMessage])

  return (
    <div className="space-y-6">
      <TicketDetail
        ticket={currentTicket}
        isLoading={isLoading}
        isAdmin={false}
        onBack={handleBack}
        onClose={handleClose}
        locale={locale}
      />

      <Card>
        <CardHeader>
          <CardTitle>{t('viewConversation')}</CardTitle>
        </CardHeader>
        <CardContent>
          <MessageThread
            messages={messages}
            isLoading={isLoading}
            isAdmin={false}
            currentUserId={currentUserId}
            onSendMessage={handleSendMessage}
            ticketClosed={currentTicket?.status === 'closed'}
            locale={locale}
          />
        </CardContent>
      </Card>
    </div>
  )
}
