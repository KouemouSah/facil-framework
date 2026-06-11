'use client'

/**
 * /supervisor/oms → redirect to /supervisor/oms/team
 *
 * The OMS supervisor team page shows per-agent performance
 * scoped by the supervisor's entity (CAMARA, AYUNTAMIENTO, etc.).
 * It uses OMS endpoints that are already entity-scoped,
 * NOT the treasury admin endpoints.
 */

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale } from 'next-intl'
import { Loader2 } from 'lucide-react'

export default function SupervisorOmsRedirect() {
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
