'use client'

import { useParams } from 'next/navigation'
import { BatchDetail } from '@/modules/batch-requests/components/BatchDetail'

export default function BatchDetailPage() {
  const params = useParams()
  const batchId = params?.batchId as string

  return <BatchDetail batchId={batchId} />
}
