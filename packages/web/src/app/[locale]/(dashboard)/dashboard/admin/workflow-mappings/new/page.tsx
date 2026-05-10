/**
 * Workflow Mapping Create Page
 * Admin page for creating new workflow-to-menu mappings
 *
 * @page /dashboard/admin/workflow-mappings/new
 * @date 2026-01-25
 */

'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Breadcrumb } from '@/components/ui/breadcrumb';
import { WorkflowMappingForm } from '@/modules/admin/components/WorkflowMappingForm';
import { useCreateWorkflowMapping } from '@/modules/admin/hooks/useWorkflowMappings';
import type {
  WorkflowMappingCreateRequest,
  WorkflowMappingUpdateRequest,
} from '@/modules/admin/services/menuConfigService';

export default function WorkflowMappingCreatePage() {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations('admin.menuConfig');

  // Create mutation
  const createMutation = useCreateWorkflowMapping();

  const handleSubmit = async (
    data: WorkflowMappingCreateRequest | WorkflowMappingUpdateRequest
  ) => {
    try {
      await createMutation.mutateAsync(data as WorkflowMappingCreateRequest);
      router.push(`/${locale}/dashboard/admin/menu-config?tab=workflow-mappings`);
    } catch {
      // Error is handled by the mutation's onError callback
    }
  };

  const handleCancel = () => {
    router.push(`/${locale}/dashboard/admin/menu-config?tab=workflow-mappings`);
  };

  return (
    <div className="space-y-6">
      <Breadcrumb items={[
        { label: 'Admin', href: `/${locale}/dashboard/admin` },
        { label: 'Menu Config', href: `/${locale}/dashboard/admin/menu-config` },
        { label: t('workflowMappings.createTitle') },
      ]} />

      {/* Header */}
      <div className="flex items-center gap-4">
        <Button asChild variant="ghost" size="icon">
          <Link href={`/${locale}/dashboard/admin/menu-config?tab=workflow-mappings`}>
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {t('workflowMappings.createTitle')}
          </h1>
          <p className="text-muted-foreground">
            {t('workflowMappings.createDescription')}
          </p>
        </div>
      </div>

      {/* Form */}
      <WorkflowMappingForm
        onSubmit={handleSubmit}
        onCancel={handleCancel}
        isLoading={createMutation.isPending}
        mode="create"
      />
    </div>
  );
}
