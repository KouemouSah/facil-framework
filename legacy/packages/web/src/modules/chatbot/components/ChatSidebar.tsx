/**
 * ChatSidebar — Collapsible sidebar with monographic vector icons.
 *
 * Desktop: toggles between collapsed (w-14) and expanded (w-56).
 * Mobile: always expanded in Sheet.
 *
 * Icons: Lucide monographic outline (strokeWidth 1.5).
 * Transitions: smooth width + opacity for labels.
 * Palette: warm stone consistent with ChatPage.
 */

'use client';

import React, { useMemo } from 'react';
import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import { usePathname } from 'next/navigation';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  Globe,
  ScrollText,
  Landmark,
  Building2,
  Layers,
  LogIn,
  PanelLeftClose,
  PanelLeftOpen,
  SquarePen,
  User,
  Plus,
} from 'lucide-react';
import { getAuthData } from '@/core/auth/storage';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChatSidebarProps {
  onNavigate?: () => void;
  className?: string;
  expanded?: boolean;
  collapsed?: boolean;
  onToggle?: () => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const NAV_ITEMS = [
  { key: 'home', href: '/', icon: Globe },
  { key: 'licenses', href: '/licencias-comerciales', icon: ScrollText },
  { key: 'companies', href: '/annuaire', icon: Building2 },
  { key: 'ministries', href: '/ministere', icon: Landmark },
  { key: 'guide', href: '/guide', icon: Layers },
];

const ICON_PROPS = { className: 'w-[18px] h-[18px] shrink-0', strokeWidth: 1.5 } as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const ChatSidebar: React.FC<ChatSidebarProps> = ({
  onNavigate,
  className = '',
  expanded = false,
  collapsed = false,
  onToggle,
}) => {
  const t = useTranslations('chatbot');
  const locale = useLocale();
  const pathname = usePathname();

  const authData = getAuthData();
  const isAuthenticated = !!authData?.user;
  const userRole = authData?.user?.role ?? '';

  // Map user role to their role-specific dashboard path
  const dashboardPath = useMemo(() => {
    const r = userRole.toLowerCase();
    if (r === 'admin') return '/dashboard/admin';
    if (r === 'supervisor' || r.startsWith('supervisor_')) return '/dashboard/supervisor';
    if (r === 'agent' || r.startsWith('agent_') || r === 'dgi_agent' || r === 'ministry_agent') return '/dashboard/agent';
    return '/dashboard';
  }, [userRole]);

  const isActive = (href: string) => {
    const localizedHref = `/${locale}${href}`;
    return pathname === localizedHref;
  };

  const showLabels = expanded || !collapsed;
  const sidebarWidth = expanded ? 'w-56' : collapsed ? 'w-14' : 'w-56';

  const navLinkClass = (active: boolean) =>
    `flex items-center ${showLabels ? 'gap-3 px-3' : 'justify-center'} rounded-lg py-2.5 text-sm transition-all duration-200 ${
      active
        ? 'bg-stone-200/70 dark:bg-stone-700/50 text-stone-900 dark:text-stone-100'
        : 'text-stone-500 dark:text-stone-400 hover:bg-stone-100 dark:hover:bg-stone-800 hover:text-stone-800 dark:hover:text-stone-200'
    }`;

  const renderNavItem = (item: typeof NAV_ITEMS[0]) => {
    const Icon = item.icon;
    const active = isActive(item.href);
    const label = t(`chatPage.nav_${item.key}`);

    const link = (
      <Link
        href={`/${locale}${item.href}`}
        onClick={onNavigate}
        className={navLinkClass(active)}
      >
        <Icon {...ICON_PROPS} />
        {showLabels && (
          <span className="truncate transition-opacity duration-200">{label}</span>
        )}
      </Link>
    );

    if (collapsed && !expanded) {
      return (
        <Tooltip key={item.key}>
          <TooltipTrigger asChild>{link}</TooltipTrigger>
          <TooltipContent side="right" sideOffset={8}>
            <p className="text-xs">{label}</p>
          </TooltipContent>
        </Tooltip>
      );
    }
    return <React.Fragment key={item.key}>{link}</React.Fragment>;
  };

  return (
    <TooltipProvider delayDuration={150}>
      <aside
        className={`flex flex-col h-full bg-stone-50/80 dark:bg-stone-900/80 border-r border-stone-200 dark:border-stone-800 transition-all duration-300 ease-in-out ${sidebarWidth} ${className}`}
      >
        {/* Top: toggle + new chat */}
        <div className={`flex items-center ${showLabels ? 'justify-between px-3' : 'justify-center'} h-12 shrink-0`}>
          {!expanded && onToggle && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="w-9 h-9 text-stone-400 hover:text-stone-700 dark:hover:text-stone-200 transition-colors"
                  onClick={onToggle}
                  aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                >
                  {collapsed
                    ? <PanelLeftOpen {...ICON_PROPS} />
                    : <PanelLeftClose {...ICON_PROPS} />
                  }
                </Button>
              </TooltipTrigger>
              {collapsed && (
                <TooltipContent side="right" sideOffset={8}>
                  <p className="text-xs">Expandir</p>
                </TooltipContent>
              )}
            </Tooltip>
          )}

          <Tooltip>
            <TooltipTrigger asChild>
              <Link href={`/${locale}/chat`} onClick={onNavigate}>
                <Button
                  variant="ghost"
                  size="icon"
                  className="w-9 h-9 text-stone-400 hover:text-stone-700 dark:hover:text-stone-200 transition-colors"
                  aria-label={t('newConversation')}
                >
                  <SquarePen {...ICON_PROPS} />
                </Button>
              </Link>
            </TooltipTrigger>
            {collapsed && (
              <TooltipContent side="right" sideOffset={8}>
                <p className="text-xs">{t('newConversation')}</p>
              </TooltipContent>
            )}
          </Tooltip>
        </div>

        <Separator className="bg-stone-200 dark:bg-stone-800" />

        {/* Navigation */}
        <nav className={`flex-1 flex flex-col ${showLabels ? 'px-2' : 'items-center px-1'} py-3 gap-0.5 overflow-y-auto`}>
          {NAV_ITEMS.map(renderNavItem)}
        </nav>

        {/* Bottom: auth */}
        <Separator className="bg-stone-200 dark:bg-stone-800" />
        <div className={`${showLabels ? 'px-2' : 'flex flex-col items-center'} py-3 shrink-0 space-y-1`}>
          {isAuthenticated ? (
            showLabels ? (
              <>
                <Link href={`/${locale}/dashboard/services`} onClick={onNavigate}>
                  <Button variant="default" size="sm" className="w-full justify-start gap-2 text-xs h-9">
                    <Plus {...ICON_PROPS} />
                    {t('chatPage.new_request')}
                  </Button>
                </Link>
                <Link href={`/${locale}${dashboardPath}`} onClick={onNavigate}>
                  <Button variant="ghost" size="sm" className="w-full justify-start gap-2 text-xs text-stone-500 hover:text-stone-800 dark:hover:text-stone-200 h-9 transition-colors">
                    <User {...ICON_PROPS} />
                    Dashboard
                  </Button>
                </Link>
              </>
            ) : (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Link href={`/${locale}${dashboardPath}`}>
                    <Button variant="ghost" size="icon" className="w-9 h-9 text-stone-400 hover:text-stone-700 dark:hover:text-stone-200 transition-colors">
                      <User {...ICON_PROPS} />
                    </Button>
                  </Link>
                </TooltipTrigger>
                <TooltipContent side="right" sideOffset={8}>
                  <p className="text-xs">Dashboard</p>
                </TooltipContent>
              </Tooltip>
            )
          ) : (
            showLabels ? (
              <Link href={`/${locale}/auth`} onClick={onNavigate}>
                <Button variant="outline" size="sm" className="w-full justify-start gap-2 text-xs border-stone-200 dark:border-stone-700 text-stone-600 dark:text-stone-300 h-9 transition-colors">
                  <LogIn {...ICON_PROPS} />
                  {t('chatPage.login_cta')}
                </Button>
              </Link>
            ) : (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Link href={`/${locale}/auth`}>
                    <Button variant="ghost" size="icon" className="w-9 h-9 text-stone-400 hover:text-stone-700 dark:hover:text-stone-200 transition-colors">
                      <LogIn {...ICON_PROPS} />
                    </Button>
                  </Link>
                </TooltipTrigger>
                <TooltipContent side="right" sideOffset={8}>
                  <p className="text-xs">{t('chatPage.login_cta')}</p>
                </TooltipContent>
              </Tooltip>
            )
          )}
        </div>
      </aside>
    </TooltipProvider>
  );
};
