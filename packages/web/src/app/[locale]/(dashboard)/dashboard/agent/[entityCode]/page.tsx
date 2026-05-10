/**
 * Generic Entity Agent Dashboard Landing Page
 * Resolves entityCode from URL and renders GenericEntityDashboard
 *
 * @route /[locale]/dashboard/agent/[entityCode]
 * @date 2026-02-21
 */

'use client';

import { useParams } from 'next/navigation';
import { GenericEntityDashboard } from '@/modules/agent-dashboard';
import { slugToEntityCode } from '@/modules/agent-dashboard/utils';

export default function EntityAgentDashboardPage() {
  const params = useParams();
  const entitySlug = (params?.entityCode as string) || '';
  const entityCode = slugToEntityCode(entitySlug);

  return <GenericEntityDashboard entityCode={entityCode} />;
}
