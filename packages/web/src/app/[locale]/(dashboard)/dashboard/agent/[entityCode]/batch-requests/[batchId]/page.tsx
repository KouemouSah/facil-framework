'use client'

import { useParams } from 'next/navigation'
import { AgentBatchDetail } from '@/modules/agent-dashboard/components/batch'
import { slugToEntityCode } from '@/modules/agent-dashboard/utils'

export default function AgentBatchDetailPage() {
  const params = useParams()
  const entitySlug = (params?.entityCode as string) || ''
  const batchId = (params?.batchId as string) || ''
  const entityCode = slugToEntityCode(entitySlug)

  return (
    <AgentBatchDetail
      entityCode={entityCode}
      batchId={batchId}
      basePath={`/dashboard/agent/${entitySlug}`}
    />
  )
}
