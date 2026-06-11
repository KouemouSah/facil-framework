/**
 * Workflow Mapping Edit Page
 * Admin page for editing existing workflow-to-menu mappings
 *
 * @page /dashboard/admin/workflow-mappings/[id]
 * @date 2026-01-25
 */

'use client';

import React from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import Link from 'next/link';
import { ArrowLeft, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Breadcrumb } from '@/components/ui/breadcrumb';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { WorkflowMappingForm } from '@/modules/admin/components/WorkflowMappingForm';
import {
  useWorkflowMapping,
  useUpdateWorkflowMapping,
  useWorkflowMappingIds,
} from '@/modules/admin/hooks/useWorkflowMappings';
import { ItemNavigation } from '@/modules/admin/components/ItemNavigation';
import type { WorkflowMappingUpdateRequest } from '@/modules/admin/services/menuConfigService';

export default function WorkflowMappingEditPage() {
  const router = useRouter();
  const params = useParams();
  const locale = useLocale();
  const t = useTranslations('admin.menuConfig');

  // Parse mapping ID from URL params
  const mappingId = params.id ? parseInt(params.id as string, 10) : 0;

  // Fetch mapping data
  const {
    data: mapping,
    isLoading,
    isError,
    error,
  } = useWorkflowMapping(mappingId, mappingId > 0);

  // Fetch all IDs for navigation
  const { data: allIds = [] } = useWorkflowMappingIds();

  // Update mutation
  const updateMutation = useUpdateWorkflowMapping();

  const handleSubmit = async (data: WorkflowMappingUpdateRequest) => {
    try {
      await updateMutation.mutateAsync({ id: mappingId, data });
      router.push(`/${locale}/dashboard/admin/menu-config?tab=workflow-mappings`);
    } catch {
      // Error is handled by the mutation's onError callback
    }
  };

  const handleCancel = () => {
    router.push(`/${locale}/dashboard/admin/menu-config?tab=workflow-mappings`);
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Error state
  if (isError || !mapping) {
    return (
      <div className="space-y-4">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>{t('errors.loadError')}</AlertTitle>
          <AlertDescription>
            {error?.message || t('errors.mappingNotFound')}
          </AlertDescription>
        </Alert>
        <Button asChild variant="outline">
          <Link href={`/${locale}/dashboard/admin/menu-config?tab=workflow-mappings`}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t('actions.backToList')}
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb items={[
        { label: 'Admin', href: `/${locale}/dashboard/admin` },
        { label: 'Menu Config', href: `/${locale}/dashboard/admin/menu-config` },
        { label: mapping.workflow_pattern },
      ]} />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button asChild variant="ghost" size="icon">
            <Link href={`/${locale}/dashboard/admin/menu-config`}>
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              {t('workflowMappings.editTitle')}
            </h1>
            <p className="text-muted-foreground">
              {t('workflowMappings.editDescription', {
                pattern: mapping.workflow_pattern,
              })}
            </p>
          </div>
        </div>
        {/* Prev/Next Navigation */}
        <ItemNavigation
          currentId={mappingId}
          allIds={allIds}
          basePath="/dashboard/admin/workflow-mappings"
        />
      </div>

      {/* Form */}
      <WorkflowMappingForm
        mapping={mapping}
        onSubmit={handleSubmit}
        onCancel={handleCancel}
        isLoading={updateMutation.isPending}
        mode="edit"
      />
    </div>
  );
}
