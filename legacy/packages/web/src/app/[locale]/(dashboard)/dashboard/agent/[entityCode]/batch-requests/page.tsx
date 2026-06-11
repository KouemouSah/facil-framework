'use client'

import { useParams } from 'next/navigation'
import { AgentBatchList } from '@/modules/agent-dashboard/components/batch'
import { slugToEntityCode } from '@/modules/agent-dashboard/utils'

export default function AgentBatchListPage() {
  const params = useParams()
  const entitySlug = (params?.entityCode as string) || ''
  const entityCode = slugToEntityCode(entitySlug)

  return (
    <AgentBatchList
      entityCode={entityCode}
      basePath={`/dashboard/agent/${entitySlug}`}
    />
  )
}
