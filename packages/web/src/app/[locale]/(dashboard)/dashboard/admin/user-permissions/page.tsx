'use client'

/**
 * User Permissions Page - DEPRECATED
 *
 * @deprecated As of 2025-01-14, this page redirects to /admin/roles?tab=user-permissions
 * User permission overrides are now part of the unified Roles & Permissions page.
 *
 * This redirect ensures backward compatibility for any bookmarked links.
 */

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale } from 'next-intl'
import { Loader2 } from 'lucide-react'

export default function UserPermissionsRedirectPage() {
  const router = useRouter()
  const locale = useLocale()

  useEffect(() => {
    // Redirect to the unified roles page with user-permissions tab
    router.replace(`/${locale}/dashboard/admin/roles?tab=user-permissions`)
  }, [router, locale])

  return (
    <div className="flex h-[50vh] items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          Redirection vers Rôles & Permissions...
        </p>
      </div>
    </div>
  )
}
