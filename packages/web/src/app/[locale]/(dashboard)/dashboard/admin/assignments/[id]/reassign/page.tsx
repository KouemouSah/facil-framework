'use client'

/**
 * Assignment Reassign Page
 * Dedicated page for reassigning an assignment to another agent
 *
 * @route /[locale]/dashboard/admin/assignments/[id]/reassign
 * @date 2026-01-20
 *
 * FEATURES:
 * - Automatic agent list (no manual UUID entry)
 * - Agent workload display
 * - Reassignment reason selection (DB enum aligned)
 * - Navigation to next assignment after success
 */

import { useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Loader2,
  AlertCircle,
  ArrowLeft,
  ArrowRightLeft,
  User,
  Briefcase,
  Target,
  Clock,
  CheckCircle2,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  useAssignment,
  useReassignAssignment,
} from '@/modules/assignments-admin'
import type { ReassignmentReason } from '@/modules/assignments-admin'
import { agentsApi } from '@/modules/assignments-admin/services/agents'

// Reassignment reasons - aligned with reassignment_reason_enum DB
const REASSIGNMENT_REASONS: ReassignmentReason[] = [
  'workload_imbalance',
  'agent_unavailable',
  'specialization_mismatch',
  'quality_issue',
  'deadline_missed',
  'agent_request',
  'supervisor_decision',
  'complexity_change',
]

// Workload status colors
const workloadColors: Record<string, string> = {
  available: 'bg-green-100 text-green-800',
  normal: 'bg-blue-100 text-blue-800',
  busy: 'bg-yellow-100 text-yellow-800',
  overloaded: 'bg-red-100 text-red-800',
  unavailable: 'bg-gray-100 text-gray-800',
}

export default function ReassignPage() {
  const params = useParams()
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('admin.assignments')
  const tCommon = useTranslations('common')

  const assignmentId = params.id as string

  // Form state
  const [selectedAgentId, setSelectedAgentId] = useState<string>('')
  const [reason, setReason] = useState<ReassignmentReason>('supervisor_decision')
  const [notes, setNotes] = useState('')

  // Fetch current assignment
  const { data: assignment, isLoading: assignmentLoading, error: assignmentError } = useAssignment(assignmentId)

  // Fetch available agents - will be filtered by ministry/entity of the assignment
  const { data: agentsResponse, isLoading: agentsLoading } = useQuery({
    queryKey: ['agents', 'available'],
    queryFn: async () => {
      // Get all active agents for now
      // In a real scenario, you'd filter by the assignment's context (ministry, entity, etc.)
      const response = await agentsApi.getAll({
        is_active: true,
        page_size: 100,
      })
      return response.items
    },
  })

  const availableAgents = agentsResponse ?? []

  // Filter out current agent from available agents
  const filteredAgents = availableAgents.filter(
    (agent) => agent.id !== assignment?.agent_profile_id
  )

  // Mutation
  const reassignMutation = useReassignAssignment()

  // Handle submit
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!selectedAgentId) {
      toast.error(t('selectAgentRequired'))
      return
    }

    try {
      await reassignMutation.mutateAsync({
        id: assignmentId,
        data: {
          new_agent_profile_id: selectedAgentId,
          reason: reason,
          notes: notes || undefined,
        },
      })
      toast.success(t('reassignSuccess'))
      router.push(`/${locale}/dashboard/admin/assignments/${assignmentId}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Error')
    }
  }

  // Get selected agent details
  const selectedAgent = filteredAgents.find((a) => a.id === selectedAgentId)

  // Loading
  if (assignmentLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Error
  if (assignmentError || !assignment) {
    return (
      <div className="space-y-6 max-w-2xl mx-auto">
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              <span>{t('notFound') || 'Assignment not found'}</span>
            </div>
            <Button variant="outline" className="mt-4" onClick={() => router.back()}>
              {tCommon('back')}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Check if assignment can be reassigned
  if (['completed', 'cancelled', 'rejected'].includes(assignment.status)) {
    return (
      <div className="space-y-6 max-w-2xl mx-auto">
        <div className="flex items-center gap-4">
          <Link href={`/${locale}/dashboard/admin/assignments/${assignmentId}`}>
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <h1 className="text-2xl font-bold">{t('reassignTitle')}</h1>
        </div>
        <Card className="border-yellow-500">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-yellow-600">
              <AlertCircle className="h-5 w-5" />
              <span>{t('cannotReassign') || 'This assignment cannot be reassigned.'}</span>
            </div>
            <p className="text-sm text-muted-foreground mt-2">
              {t('cannotReassignReason') || `Assignments with status "${assignment.status}" cannot be reassigned.`}
            </p>
            <Link href={`/${locale}/dashboard/admin/assignments/${assignmentId}`}>
              <Button variant="outline" className="mt-4">
                {tCommon('back')}
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/${locale}/dashboard/admin/assignments/${assignmentId}`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <ArrowRightLeft className="h-6 w-6" />
            {t('reassignTitle')}
          </h1>
          <p className="text-muted-foreground">{t('reassignDescription')}</p>
        </div>
      </div>

      {/* Current Assignment Info */}
      <Card>
        <CardHeader>
          <CardTitle>{t('currentAssignment') || 'Current Assignment'}</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium text-muted-foreground">{t('item')}</label>
            <p className="font-mono text-sm">{assignment.item_id.slice(0, 8)}...</p>
            <Badge variant="secondary" className="mt-1">{assignment.item_type}</Badge>
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground">{t('currentAgent') || 'Current Agent'}</label>
            <p className="font-medium">{assignment.agent_name || '-'}</p>
            <p className="font-mono text-xs text-muted-foreground">{assignment.agent_profile_id.slice(0, 8)}...</p>
          </div>
        </CardContent>
      </Card>

      {/* Reassignment Form */}
      <form onSubmit={handleSubmit}>
        {/* Select New Agent */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-5 w-5" />
              {t('selectNewAgent') || 'Select New Agent'}
            </CardTitle>
            <CardDescription>
              {t('selectNewAgentDescription') || 'Choose an available agent to reassign this item to.'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {agentsLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : filteredAgents.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <User className="h-12 w-12 mx-auto mb-2 opacity-50" />
                <p>{t('noAgentsAvailable') || 'No other agents available'}</p>
              </div>
            ) : (
              <div className="space-y-4">
                <Select value={selectedAgentId} onValueChange={setSelectedAgentId}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder={t('selectAgent') || 'Select an agent...'} />
                  </SelectTrigger>
                  <SelectContent>
                    {filteredAgents.map((agent) => (
                      <SelectItem key={agent.id} value={agent.id}>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{agent.full_name || agent.email || 'Agent'}</span>
                          {agent.workload_status && (
                            <Badge className={workloadColors[agent.workload_status] || 'bg-gray-100'} variant="secondary">
                              {agent.workload_status}
                            </Badge>
                          )}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {/* Selected Agent Details */}
                {selectedAgent && (
                  <Card className="bg-muted/50">
                    <CardContent className="pt-4">
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div className="flex items-center gap-2">
                          <User className="h-4 w-4 text-muted-foreground" />
                          <div>
                            <p className="font-medium">{selectedAgent.full_name || '-'}</p>
                            <p className="text-xs text-muted-foreground">{selectedAgent.email}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Briefcase className="h-4 w-4 text-muted-foreground" />
                          <div>
                            <p className="font-medium">{selectedAgent.agent_type}</p>
                            <p className="text-xs text-muted-foreground">
                              {selectedAgent.is_supervisor ? 'Supervisor' : 'Agent'}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Target className="h-4 w-4 text-muted-foreground" />
                          <div>
                            <p className="font-medium">
                              {selectedAgent.current_workload ?? 0}/{selectedAgent.max_capacity ?? 20}
                            </p>
                            <p className="text-xs text-muted-foreground">{t('workload') || 'Workload'}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Clock className="h-4 w-4 text-muted-foreground" />
                          <div>
                            <Badge className={workloadColors[selectedAgent.workload_status || 'available']}>
                              {selectedAgent.workload_status || 'available'}
                            </Badge>
                          </div>
                        </div>
                      </div>
                      {selectedAgent.entity_name && (
                        <p className="text-xs text-muted-foreground mt-2">
                          {selectedAgent.ministry_name} / {selectedAgent.entity_name}
                        </p>
                      )}
                    </CardContent>
                  </Card>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Reason Selection */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>{t('reason')}</CardTitle>
            <CardDescription>
              {t('reasonDescription') || 'Select the reason for this reassignment.'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <RadioGroup value={reason} onValueChange={(v) => setReason(v as ReassignmentReason)}>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {REASSIGNMENT_REASONS.map((r) => (
                  <div key={r} className="flex items-center space-x-2">
                    <RadioGroupItem value={r} id={r} />
                    <Label htmlFor={r} className="cursor-pointer">
                      {t(`reasons.${r}`) || r.replace(/_/g, ' ')}
                    </Label>
                  </div>
                ))}
              </div>
            </RadioGroup>
          </CardContent>
        </Card>

        {/* Notes */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>{t('notes')}</CardTitle>
            <CardDescription>
              {t('notesDescription') || 'Add optional notes for this reassignment.'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t('notesPlaceholder')}
              rows={3}
            />
          </CardContent>
        </Card>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Link href={`/${locale}/dashboard/admin/assignments/${assignmentId}`}>
            <Button type="button" variant="outline">
              {tCommon('cancel')}
            </Button>
          </Link>
          <Button
            type="submit"
            disabled={reassignMutation.isPending || !selectedAgentId}
          >
            {reassignMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="mr-2 h-4 w-4" />
            )}
            {t('confirmReassign') || 'Confirm Reassignment'}
          </Button>
        </div>
      </form>
    </div>
  )
}
