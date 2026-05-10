'use client';

/**
 * Agent AI Assistant Page
 * Route: /[locale]/dashboard/agent/[entityCode]/assistant
 *
 * Works for both supervisors and field agents.
 * Resolves entityCode from URL and renders SupervisorAssistantTab
 * with entity context and isSupervisor flag for appropriate quick actions.
 */

import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { fetchClient } from '@/core/api';
import { SupervisorAssistantTab } from '@/modules/agent-dashboard/components/SupervisorAssistantTab';
import { slugToEntityCode } from '@/modules/agent-dashboard/utils';

interface MenuConfigResponse {
  entity_code: string | null;
  entity_name: string | null;
  is_supervisor?: boolean;
}

export default function AgentAssistantPage() {
  const params = useParams();
  const entitySlug = (params?.entityCode as string) || '';
  const entityCode = slugToEntityCode(entitySlug);

  // Fetch entity context from menu-config (already cached by sidebar)
  const { data, isLoading } = useQuery({
    queryKey: ['menu-config', 'me'],
    queryFn: () => fetchClient.get<MenuConfigResponse>('/menu-config/me'),
    staleTime: 5 * 60 * 1000,
  });

  const entityName = data?.entity_name || entityCode;
  const isSupervisor = data?.is_supervisor ?? false;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <SupervisorAssistantTab
      entityCode={entityCode}
      entityName={entityName}
      isSupervisor={isSupervisor}
    />
  );
}
