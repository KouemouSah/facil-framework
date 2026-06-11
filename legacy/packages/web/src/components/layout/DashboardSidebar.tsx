'use client'

/**
 * Dashboard Sidebar Navigation
 * Main navigation menu for authenticated users
 */

import { useState, useMemo } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { usePathname, useRouter } from 'next/navigation'
import { cn } from '@/core/utils'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet'
import {
  LayoutDashboard,
  FileText,
  ClipboardList,
  HelpCircle,
  User,
  Settings,
  LogOut,
  Menu,
  ChevronRight,
  MessageCircle,
  BadgeCheck,
  Lock,
  FileStack,
  Calculator,
  FolderOpen,
  Building2,
} from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import { authApi } from '@/core/api/auth'
import { getAuthData, clearAuthData } from '@/core/auth/storage'
import { FEATURE_DECLARATIONS } from '@/core/config/features'
import { useDocumentAlerts } from '@/modules/user-documents/hooks'
import { useLocale, useTranslations } from 'next-intl'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

interface NavItem {
  titleKey: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  badge?: string
  disabled?: boolean
  disabledTooltip?: string
  visible?: boolean
}

interface DashboardSidebarProps {
  className?: string
}

export function DashboardSidebar({ className }: DashboardSidebarProps) {
  const pathname = usePathname()
  const router = useRouter()
  const { toast } = useToast()
  const locale = useLocale()
  const t = useTranslations('dashboard')

  // Get user info to determine funcionario status
  const authData = getAuthData()
  const user = authData?.user

  // Vault alerts count for badge (unread, non-dismissed)
  const { unreadCount: vaultUnread } = useDocumentAlerts()
  const alertsCount = useMemo(() => {
    return vaultUnread > 0 ? String(vaultUnread) : undefined
  }, [vaultUnread])

  // Check if user is a verified funcionario with active status
  const isVerifiedFuncionario = useMemo(() => {
    if (!user) return false

    // User must have matricula_funcionario and funcionario_verified_at
    const hasVerification = !!(user.matricula_funcionario && user.funcionario_verified_at)
    if (!hasVerification) return false

    // Check funcionario_status from verified_identifiers (real-time check)
    // If funcionario_status exists, check is_active
    // If it doesn't exist yet (backward compatibility), allow access
    const status = user.funcionario_status
    if (status) {
      return status.is_active === true
    }

    // Backward compatibility: if no status, allow based on verification only
    return true
  }, [user])

  const navItems: NavItem[] = useMemo(() => [
    {
      titleKey: 'overview',
      href: `/${locale}/dashboard`,
      icon: LayoutDashboard,
    },
    {
      titleKey: 'declarations',
      href: `/${locale}/dashboard/declarations`,
      icon: FileText,
      visible: FEATURE_DECLARATIONS,
    },
    {
      titleKey: 'serviceRequests',
      href: `/${locale}/dashboard/service-requests`,
      icon: ClipboardList,
    },
    {
      titleKey: 'myCompanies',
      href: `/${locale}/dashboard/empresas`,
      icon: Building2,
    },
    {
      titleKey: 'batchRequests',
      href: `/${locale}/dashboard/batch-requests`,
      icon: FileStack,
    },
    {
      titleKey: 'myDocuments',
      href: `/${locale}/dashboard/documents`,
      icon: FolderOpen,
      badge: alertsCount,
    },
    // Accountant menu - only visible for accountant role
    {
      titleKey: 'accountant',
      href: `/${locale}/dashboard/accountant`,
      icon: Calculator,
      visible: user?.role === 'accountant',
    },
    // Funcionario menu - only visible for verified civil servants
    {
      titleKey: 'funcionario',
      href: `/${locale}/dashboard/funcionario`,
      icon: BadgeCheck,
      visible: isVerifiedFuncionario,
    },
    {
      titleKey: 'chatAssistant',
      href: `/${locale}/dashboard/chat`,
      icon: MessageCircle,
    },
    {
      titleKey: 'support',
      href: `/${locale}/dashboard/support`,
      icon: HelpCircle,
    },
    {
      titleKey: 'profile',
      href: `/${locale}/dashboard/profile`,
      icon: User,
    },
    {
      titleKey: 'settings',
      href: `/${locale}/dashboard/settings`,
      icon: Settings,
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [locale, isVerifiedFuncionario, user?.role, alertsCount, t])

  const handleLogout = async () => {
    const authData = getAuthData()

    if (!authData) {
      router.push(`/${locale}/auth`)
      return
    }

    try {
      await authApi.logout({
        access_token: authData.access_token,
        refresh_token: authData.refresh_token,
      })

      clearAuthData()

      toast({
        title: t('logoutSuccess'),
        description: t('logoutMessage'),
      })

      router.push(`/${locale}`)
    } catch (error: unknown) {
      // Even if logout fails on backend, clear local storage
      clearAuthData()
      router.push(`/${locale}`)
    }
  }

  const isActive = (href: string) => {
    return pathname === href || pathname?.startsWith(href + '/')
  }

  return (
    <aside className={cn('h-full border-r bg-card', className)}>
      <div className="flex h-full flex-col">
        {/* Logo */}
        <div className="flex h-16 items-center border-b px-6">
          <Link href={`/${locale}/dashboard`} className="flex items-center gap-2">
            <Image src="/logo.png" alt="Facil" width={76} height={32} className="h-8 w-auto" />
          </Link>
        </div>

        {/* Navigation */}
        <ScrollArea className="flex-1 px-3 py-4">
          <TooltipProvider>
            <nav className="space-y-1">
              {navItems
                .filter((item) => item.visible !== false)
                .map((item) => {
                  const Icon = item.icon
                  const active = isActive(item.href)

                  // Disabled item with tooltip
                  if (item.disabled) {
                    return (
                      <Tooltip key={item.href}>
                        <TooltipTrigger asChild>
                          <div
                            className={cn(
                              'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium',
                              'cursor-not-allowed opacity-50 text-muted-foreground'
                            )}
                          >
                            <Icon className="h-5 w-5" />
                            <span>{t(item.titleKey)}</span>
                            <Lock className="ml-auto h-4 w-4" />
                          </div>
                        </TooltipTrigger>
                        <TooltipContent side="right">
                          <p>{item.disabledTooltip || t('comingSoon')}</p>
                        </TooltipContent>
                      </Tooltip>
                    )
                  }

                  // Normal item
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all hover:bg-accent',
                        active
                          ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                          : 'text-muted-foreground hover:text-foreground'
                      )}
                    >
                      <Icon className="h-5 w-5" />
                      <span>{t(item.titleKey)}</span>
                      {item.badge && (
                        <span className="ml-auto flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground">
                          {item.badge}
                        </span>
                      )}
                      {active && <ChevronRight className="ml-auto h-4 w-4" />}
                    </Link>
                  )
                })}
            </nav>
          </TooltipProvider>
        </ScrollArea>

        {/* Logout Button */}
        <div className="border-t p-4">
          <Button
            variant="ghost"
            className="w-full justify-start text-destructive hover:bg-destructive hover:text-destructive-foreground"
            onClick={handleLogout}
          >
            <LogOut className="mr-3 h-5 w-5" />
            {t('logout')}
          </Button>
        </div>
      </div>
    </aside>
  )
}

// Mobile Sidebar
export function MobileSidebar() {
  const [open, setOpen] = useState(false)

  return (
    <Sheet open={open} onOpenChange={setOpen}>
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
