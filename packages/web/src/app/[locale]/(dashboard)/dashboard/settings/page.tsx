'use client'

/**
 * Settings Page
 * Redirects to Security settings by default
 */

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'

export default function SettingsPage() {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('settings')

  useEffect(() => {
    router.push(`/${locale}/dashboard/settings/security`)
  }, [router, locale])

  return (
    <div className="min-h-screen flex items-center justify-center">
      <p>{t('redirecting')}</p>
    </div>
  )
}
