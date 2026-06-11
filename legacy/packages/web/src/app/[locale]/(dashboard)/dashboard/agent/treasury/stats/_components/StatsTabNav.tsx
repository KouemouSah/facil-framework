'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { cn } from '@/lib/utils';
import { BarChart3, Users, Clock } from 'lucide-react';

const TABS = [
  { id: 'kpis', icon: BarChart3, path: '' },
  { id: 'agents', icon: Users, path: '/agents' },
  { id: 'sla', icon: Clock, path: '/sla' },
] as const;

export function StatsTabNav() {
  const locale = useLocale();
  const pathname = usePathname();
  const t = useTranslations('treasury.statsNav');
  const basePath = `/${locale}/dashboard/agent/treasury/stats`;

  return (
    <div className="flex gap-1 border-b mb-4">
      {TABS.map((tab) => {
        const href = `${basePath}${tab.path}`;
        const isActive = tab.path === ''
          ? pathname === basePath || pathname === `${basePath}/`
          : pathname.startsWith(href);
        const Icon = tab.icon;

        return (
          <Link
            key={tab.id}
            href={href}
            className={cn(
              'flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
              isActive
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground/30'
            )}
          >
            <Icon className="h-4 w-4" />
            {t(tab.id)}
          </Link>
        );
      })}
    </div>
  );
}
