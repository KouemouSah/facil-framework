'use client'

/**
 * Dashboard Layout
 * Main layout wrapper for all dashboard pages with sidebar navigation
 * Renders appropriate sidebar based on user role:
 * - AdminSidebar for admin users
 * - GenericAgentSidebar for unified 'agent' role (entity-based)
 * - DashboardSidebar for citizens/businesses/accountants/funcionarios
 */

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import { DashboardSidebar } from './DashboardSidebar'
import { DashboardErrorBoundary } from './DashboardErrorBoundary'
import { SessionTimeoutDialog } from './SessionTimeoutDialog'
import { AdminSidebar, MobileAdminSidebar } from '@/modules/admin/components'
import { AdminCommandPalette } from '@/modules/admin/components/AdminCommandPalette'
import { GenericAgentSidebar, MobileAgentSidebar } from '@/modules/agent-dashboard'
import { getAuthData } from '@/core/auth/storage'
import { APP_CONSTANTS } from '@/core/config/constants'
import type { User } from '@/types/auth'
import { useLocale, useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet'
import { Menu } from 'lucide-react'

interface DashboardLayoutProps {
  children: React.ReactNode
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('dashboard')
  const _tCommon = useTranslations('common')
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Note: Body overflow-hidden removed — the flex h-screen overflow-hidden
  // container already prevents body scroll. The body class was breaking
  // iOS Safari scroll behavior and causing mobile UX issues.

  useEffect(() => {
    const authData = getAuthData()

    if (!authData) {
      router.push(`/${locale}/auth`)
      return
    }

    // Map backend status to is_active boolean for UI compatibility
    const userData = {
      ...authData.user,
      is_active: authData.user.status === 'active',
      email_verified: authData.user.email_verified ?? false,
    }

    // Bug 4 follow-up (2026-05-06): when an agent/admin lands on the bare
    // `/dashboard` URL (citizen route), redirect them to their proper home
    // BEFORE rendering the layout sidebar with citizen affordances. This
    // keeps `isLoading=true` so the loader stays visible during the
    // redirect (no flicker of the citizen Quick Actions, no
    // ipsa-inconsistent role-based routing). Page-level `dashboard/page.tsx`
    // also redirects (defense in depth).
    if (typeof window !== 'undefined') {
      const path = window.location.pathname
      // Strip locale prefix to get the canonical path (`/es/dashboard` → `/dashboard`)
      const canonical = path.replace(/^\/[a-z]{2}/, '')
      const role = (userData.role || '').toLowerCase()
      if (canonical === '/dashboard' || canonical === '/dashboard/') {
        if (role === 'admin') {
          router.replace(`/${locale}/dashboard/admin`)
          return
        }
        if (role === 'agent' || role.startsWith('supervisor_')) {
          router.replace(`/${locale}/dashboard/supervisor`)
          return
        }
      }
    }

    setUser(userData as User)
    setIsLoading(false)
  }, [router, locale])

  if (isLoading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full mx-auto"></div>
          <p className="text-muted-foreground">{t('loading')}</p>
        </div>
      </div>
    )
  }

  // Determine which sidebar to show based on user role
  // Simplified role structure from migration 048:
  // - admin: AdminSidebar
  // - agent: GenericAgentSidebar (unified, entity-based)
  // - citizen/business/accountant/funcionario: DashboardSidebar
  const isAdmin = user?.role === APP_CONSTANTS.USER_ROLES.ADMIN
  const isAgent = user?.role === 'agent'

  // Determine sidebar and title
  const getSidebar = () => {
    if (isAdmin) return <AdminSidebar />
    if (isAgent) return <GenericAgentSidebar />
    return <DashboardSidebar />
  }

  // Role-aware mobile sidebar
  const getMobileSidebar = () => {
    if (isAdmin) return <MobileAdminSidebar />
    if (isAgent) return <MobileAgentSidebar />
    // Default citizen mobile sidebar
    return (
      <Sheet>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon" className="md:hidden">
            <Menu className="h-6 w-6" />
            <span className="sr-only">Toggle menu</span>
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-72 p-0">
          <DashboardSidebar />
        </SheetContent>
      </Sheet>
    )
  }

  const getTitle = () => {
    if (isAdmin) return 'Facil Admin'
    if (isAgent) return 'Facil Agent'
    return 'Facil'
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <SessionTimeoutDialog />
      {isAdmin && <AdminCommandPalette />}

      {/* Desktop Sidebar - Role-based */}
      <div className="hidden md:flex md:w-64 md:flex-col">
        {getSidebar()}
      </div>

      {/* Main Content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile Header - Role-aware sidebar */}
        <header className="flex h-16 items-center gap-4 border-b bg-card px-4 md:hidden">
          {getMobileSidebar()}
          <Image src="/logo.png" alt="Facil" width={76} height={32} className="h-8 w-auto" />
          <h1 className="text-lg font-semibold">{getTitle()}</h1>
        </header>

        {/* Content Area */}
        <main className="flex-1 overflow-y-auto bg-muted/10 p-4 md:p-6 lg:p-8">
          <DashboardErrorBoundary>
            {children}
          </DashboardErrorBoundary>
        </main>

        {/* Footer */}
        <footer className="border-t bg-card px-4 py-3 text-center">
          <p className="text-xs text-muted-foreground">
            {t('copyright', { year: new Date().getFullYear() })}
          </p>
        </footer>
      </div>
    </div>
  )
}
