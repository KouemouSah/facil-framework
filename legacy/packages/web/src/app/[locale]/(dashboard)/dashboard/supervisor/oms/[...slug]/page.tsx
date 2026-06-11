'use client'

/**
 * Catch-all redirect: /supervisor/oms/{anything} → /supervisor
 *
 * OMS supervisor sidebar links (stats, escalations, batch-requests)
 * incorrectly point to /supervisor/oms/X. These pages don't exist —
 * the supervisor dashboard at /supervisor handles all functionality.
 */

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale } from 'next-intl'
import { Loader2 } from 'lucide-react'

export default function SupervisorOmsCatchAll() {
  const router = useRouter()
  const locale = useLocale()

  useEffect(() => {
    router.replace(`/${locale}/dashboard/supervisor/entity-dashboard`)
  }, [router, locale])

  return (
    <div className="flex items-center justify-center h-[60vh]">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  )
}
