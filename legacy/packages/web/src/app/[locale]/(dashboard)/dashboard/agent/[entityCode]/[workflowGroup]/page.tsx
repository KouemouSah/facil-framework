/**
 * Generic Workflow Group Landing Page
 * Redirects to the pending view for the workflow group
 *
 * Replaces: cnedoge-pasaporte/[workflowGroup]/page.tsx, cnedoge-residencia/[workflowGroup]/page.tsx
 *
 * @route /[locale]/dashboard/agent/[entityCode]/[workflowGroup]
 * @date 2026-02-21
 */

'use client';

import { useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useLocale } from 'next-intl';
import { Loader2 } from 'lucide-react';

export default function WorkflowGroupPage() {
  const router = useRouter();
  const locale = useLocale();
  const params = useParams();
  const entityCode = params.entityCode as string;
  const workflowGroup = params.workflowGroup as string;

  useEffect(() => {
    router.replace(`/${locale}/dashboard/agent/${entityCode}/${workflowGroup}/pending`);
  }, [router, locale, entityCode, workflowGroup]);

  return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
    </div>
  );
}
