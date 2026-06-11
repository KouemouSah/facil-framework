'use client';

/**
 * Display Configuration Edit Page
 * Uses shared DisplayConfigForm component
 *
 * @module dashboard/admin/menu-config/display/[id]
 * @date 2026-02-01
 */

import { useState, useCallback, useRef, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useLocale } from 'next-intl';
import Link from 'next/link';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Breadcrumb } from '@/components/ui/breadcrumb';
import { ArrowLeft, LayoutGrid, Save, Loader2, AlertCircle } from 'lucide-react';
import { useDisplayConfig, useUpdateDisplayConfig } from '@/modules/admin/hooks';
import { DisplayConfigForm } from '@/modules/admin/components/DisplayConfigForm';
import type { DisplayConfigFormData } from '@/modules/admin/components/DisplayConfigForm';

export default function DisplayConfigEditPage() {
  const params = useParams();
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations('admin.menuConfig.displayConfig');
  const configId = Number(params.id);

  // Fetch existing config
  const { data: config, isLoading, isError, error } = useDisplayConfig(configId);

  // Update mutation
  const updateMutation = useUpdateDisplayConfig();

  // Track dirty state from form
  const [isDirty, setIsDirty] = useState(false);

  // Ref to form's submit function
  const formSubmitRef = useRef<(() => Promise<void>) | null>(null);

  const handleDirtyChange = useCallback((dirty: boolean) => {
    setIsDirty(dirty);
  }, []);

  const handleSubmit = async (data: DisplayConfigFormData) => {
    await updateMutation.mutateAsync({
      id: configId,
      data: {
        list_columns: data.list_columns,
        preview_sections: data.preview_sections,
        labels: data.labels,
      },
    });
    setIsDirty(false);
  };

  const handleCancel = () => {
    router.push(`/${locale}/dashboard/admin/menu-config/display`);
  };

  // Memoize initialData to prevent useEffect reset loop in the form:
  // Without this, every parent re-render creates a new object reference,
  // which triggers the form's useEffect([initialData]) and resets all selections.
  const formInitialData = useMemo(() => config ? {
    workflow_code: config.workflow_code,
    list_columns: config.list_columns,
    preview_sections: config.preview_sections,
    labels: config.labels ?? {},
  } : undefined, [config]);

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Error state
  if (isError || !config) {
    return (
      <Card className="border-destructive">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span>{error instanceof Error ? error.message : t('messages.loadError')}</span>
          </div>
          <Button variant="outline" className="mt-4" asChild>
            <Link href={`/${locale}/dashboard/admin/menu-config/display`}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              {t('actions.backToList')}
            </Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb items={[
        { label: 'Admin', href: `/${locale}/dashboard/admin` },
        { label: 'Menu Config', href: `/${locale}/dashboard/admin/menu-config` },
        { label: 'Display Config', href: `/${locale}/dashboard/admin/menu-config/display` },
        { label: config.workflow_code },
      ]} />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href={`/${locale}/dashboard/admin/menu-config/display`}>
              <ArrowLeft className="h-5 w-5" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
              <LayoutGrid className="h-7 w-7" />
              {t('editTitle')}
            </h1>
            <div className="flex items-center gap-2 mt-1">
              <code className="text-sm bg-muted px-2 py-1 rounded">{config.workflow_code}</code>
              {isDirty && (
                <Badge variant="secondary" className="bg-amber-100 text-amber-800">
                  {t('unsavedChanges')}
                </Badge>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={handleCancel}>
            {t('actions.cancel')}
          </Button>
          <Button
            onClick={() => formSubmitRef.current?.()}
            disabled={!isDirty || updateMutation.isPending}
          >
            {updateMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            <Save className="h-4 w-4 mr-2" />
            {t('actions.save')}
          </Button>
        </div>
      </div>

      {/* Form - initialData must be memoized to avoid resetting form state on parent re-render */}
      <DisplayConfigForm
        initialData={formInitialData}
        onSubmit={handleSubmit}
        onDirtyChange={handleDirtyChange}
        onSubmitRef={(fn) => { formSubmitRef.current = fn; }}
        isSubmitting={updateMutation.isPending}
        mode="edit"
      />
    </div>
  );
}
