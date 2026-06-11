'use client';

/**
 * Display Configuration Create Page
 * Uses shared DisplayConfigForm component
 *
 * @module dashboard/admin/menu-config/display/new
 * @date 2026-02-01
 */

import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useLocale } from 'next-intl';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Breadcrumb } from '@/components/ui/breadcrumb';
import { ArrowLeft, Plus } from 'lucide-react';
import { useCreateDisplayConfig } from '@/modules/admin/hooks';
import { DisplayConfigForm } from '@/modules/admin/components/DisplayConfigForm';
import type { DisplayConfigFormData } from '@/modules/admin/components/DisplayConfigForm';

export default function DisplayConfigCreatePage() {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations('admin.menuConfig.displayConfig');

  const createMutation = useCreateDisplayConfig();

  const handleSubmit = async (data: DisplayConfigFormData) => {
    try {
      await createMutation.mutateAsync({
        workflow_code: data.workflow_code,
        list_columns: data.list_columns,
        preview_sections: data.preview_sections,
        labels: data.labels,
      });
      router.push(`/${locale}/dashboard/admin/menu-config/display`);
    } catch {
      // Error already handled by mutation hook toast
    }
  };

  return (
    <div className="space-y-6">
      <Breadcrumb items={[
        { label: 'Admin', href: `/${locale}/dashboard/admin` },
        { label: 'Menu Config', href: `/${locale}/dashboard/admin/menu-config` },
        { label: 'Display Config', href: `/${locale}/dashboard/admin/menu-config/display` },
        { label: t('createTitle') },
      ]} />

      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href={`/${locale}/dashboard/admin/menu-config/display`}>
            <ArrowLeft className="h-5 w-5" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
            <Plus className="h-7 w-7" />
            {t('createTitle')}
          </h1>
          <p className="text-muted-foreground mt-1">{t('createDescription')}</p>
        </div>
      </div>

      {/* Form */}
      <DisplayConfigForm
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending}
        mode="create"
      />
    </div>
  );
}
