'use client'

/**
 * Assignment Edit Page
 * Page for editing assignment properties (priority, deadline, notes)
 *
 * @route /[locale]/dashboard/admin/assignments/[id]/edit
 * @date 2026-01-20
 *
 * FEATURES:
 * - Priority level adjustment (1-10 scale)
 * - Deadline extension
 * - Notes update
 * - Navigation to detail view after save
 */

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
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
import { Slider } from '@/components/ui/slider'
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
  Edit3,
  Save,
  Calendar,
  AlertTriangle,
  Info,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  useAssignment,
  useUpdateAssignmentPriority,
  useExtendAssignmentDeadline,
  useUpdateAssignmentNotes,
} from '@/modules/assignments-admin'

// Priority level keys map to i18n + color
const PRIORITY_COLORS = [
  'bg-gray-100 text-gray-800',   // 1
  'bg-gray-100 text-gray-800',   // 2
  'bg-blue-100 text-blue-800',   // 3
  'bg-green-100 text-green-800', // 4
  'bg-green-100 text-green-800', // 5
  'bg-yellow-100 text-yellow-800', // 6
  'bg-orange-100 text-orange-800', // 7
  'bg-orange-100 text-orange-800', // 8
  'bg-red-100 text-red-800',     // 9
  'bg-red-200 text-red-900',     // 10
]

const PRIORITY_LABEL_KEYS = [
  'priorityVeryLow', 'priorityVeryLow', 'priorityLow', 'priorityNormal', 'priorityNormal',
  'priorityMedium', 'priorityHigh', 'priorityHigh', 'priorityUrgent', 'priorityCritical',
]

function getPriorityInfo(level: number, t: (key: string) => string) {
  const idx = Math.min(Math.max(level - 1, 0), 9)
  return { value: level, label: t(PRIORITY_LABEL_KEYS[idx]), color: PRIORITY_COLORS[idx] }
}

export default function EditAssignmentPage() {
  const params = useParams()
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('admin.assignments')
  const tCommon = useTranslations('common')

  const assignmentId = params.id as string

  // Form state
  const [priorityLevel, setPriorityLevel] = useState<number>(5)
  const [additionalDays, setAdditionalDays] = useState<number>(0)
  const [deadlineReason, setDeadlineReason] = useState<string>('')
  const [notes, setNotes] = useState<string>('')
  const [hasChanges, setHasChanges] = useState(false)

  // Fetch current assignment
  const {
    data: assignment,
    isLoading,
    error,
  } = useAssignment(assignmentId)

  // Mutations
  const priorityMutation = useUpdateAssignmentPriority()
  const deadlineMutation = useExtendAssignmentDeadline()
  const notesMutation = useUpdateAssignmentNotes()

  // Initialize form with current values
  useEffect(() => {
    if (assignment) {
      setPriorityLevel(assignment.priority_level ?? 5)
      setNotes(assignment.notes ?? '')
    }
  }, [assignment])

  // Track changes
  useEffect(() => {
    if (assignment) {
      const priorityChanged = priorityLevel !== (assignment.priority_level ?? 5)
      const deadlineChanged = additionalDays > 0
      const notesChanged = notes !== (assignment.notes ?? '')
      setHasChanges(priorityChanged || deadlineChanged || notesChanged)
    }
  }, [assignment, priorityLevel, additionalDays, notes])

  // Handle save
  const handleSave = async () => {
    const promises: Promise<unknown>[] = []

    // Update priority if changed
    if (assignment && priorityLevel !== (assignment.priority_level ?? 5)) {
      promises.push(
        priorityMutation.mutateAsync({
          id: assignmentId,
          data: { priority_level: priorityLevel },
        })
      )
    }

    // Extend deadline if requested
    if (additionalDays > 0) {
      promises.push(
        deadlineMutation.mutateAsync({
          id: assignmentId,
          data: {
            additional_days: additionalDays,
            reason: deadlineReason || undefined,
          },
        })
      )
    }

    // Update notes if changed
    if (assignment && notes !== (assignment.notes ?? '')) {
      promises.push(
        notesMutation.mutateAsync({
          id: assignmentId,
          data: { notes },
        })
      )
    }

    if (promises.length === 0) {
      toast.info(t('noChanges') || 'No changes to save')
      return
    }

    try {
      await Promise.all(promises)
      toast.success(t('updateSuccess') || 'Assignment updated successfully')
      router.push(`/${locale}/dashboard/admin/assignments/${assignmentId}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Error updating assignment')
    }
  }

  const isSaving = priorityMutation.isPending || deadlineMutation.isPending || notesMutation.isPending

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Error state
  if (error || !assignment) {
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

  // Check if assignment can be edited
  if (['completed', 'cancelled', 'rejected'].includes(assignment.status)) {
    return (
      <div className="space-y-6 max-w-2xl mx-auto">
        <div className="flex items-center gap-4">
          <Link href={`/${locale}/dashboard/admin/assignments/${assignmentId}`}>
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <h1 className="text-2xl font-bold">{t('editTitle') || 'Edit Assignment'}</h1>
        </div>
        <Card className="border-yellow-500">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-yellow-600">
              <AlertTriangle className="h-5 w-5" />
              <span>{t('cannotEdit') || 'This assignment cannot be edited.'}</span>
            </div>
            <p className="text-sm text-muted-foreground mt-2">
              {t('cannotEditReason') ||
                `Assignments with status "${assignment.status}" cannot be modified.`}
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

  const priorityInfo = getPriorityInfo(priorityLevel, t)
  const currentDeadline = assignment.deadline ? new Date(assignment.deadline) : null
  const newDeadline =
    currentDeadline && additionalDays > 0
      ? new Date(currentDeadline.getTime() + additionalDays * 24 * 60 * 60 * 1000)
      : currentDeadline

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/${locale}/dashboard/admin/assignments/${assignmentId}`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Edit3 className="h-6 w-6" />
            {t('editTitle') || 'Edit Assignment'}
          </h1>
          <p className="text-muted-foreground">{t('editDescription') || 'Modify assignment properties'}</p>
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
            <Badge variant="secondary" className="mt-1">
              {assignment.item_type}
            </Badge>
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground">{t('agent')}</label>
            <p className="font-medium">{assignment.agent_name || '-'}</p>
            <Badge variant="outline" className="mt-1">
              {assignment.status}
            </Badge>
          </div>
        </CardContent>
      </Card>

      {/* Priority Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            {t('priority') || 'Priority'}
          </CardTitle>
          <CardDescription>
            {t('priorityDescription') || 'Adjust the priority level (1-10) for this assignment.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>{t('priorityLevel') || 'Priority Level'}</Label>
              <Badge className={priorityInfo.color}>
                {priorityLevel} - {priorityInfo.label}
              </Badge>
            </div>
            <Slider
              value={[priorityLevel]}
              onValueChange={(values: number[]) => setPriorityLevel(values[0])}
              min={1}
              max={10}
              step={1}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>1 - {t('low') || 'Low'}</span>
              <span>5 - {t('normal') || 'Normal'}</span>
              <span>10 - {t('critical') || 'Critical'}</span>
            </div>
          </div>

          {assignment.priority_level !== priorityLevel && (
            <div className="flex items-center gap-2 text-sm text-blue-600 bg-blue-50 p-2 rounded">
              <Info className="h-4 w-4" />
              <span>
                {t('priorityChangePreview') ||
                  `Priority will change from ${assignment.priority_level ?? 5} to ${priorityLevel}`}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Deadline Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            {t('deadline') || 'Deadline'}
          </CardTitle>
          <CardDescription>
            {t('deadlineDescription') || 'Extend the deadline if more time is needed.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {currentDeadline ? (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-muted-foreground">{t('currentDeadline') || 'Current Deadline'}</Label>
                  <p className="font-medium">
                    {currentDeadline.toLocaleDateString(locale, {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                    })}
                  </p>
                </div>
                {newDeadline && additionalDays > 0 && (
                  <div>
                    <Label className="text-muted-foreground">{t('newDeadline') || 'New Deadline'}</Label>
                    <p className="font-medium text-blue-600">
                      {newDeadline.toLocaleDateString(locale, {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                      })}
                    </p>
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="additionalDays">{t('extendBy') || 'Extend by (days)'}</Label>
                <Select
                  value={String(additionalDays)}
                  onValueChange={(v) => setAdditionalDays(Number(v))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('selectDays') || 'Select days'} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="0">{t('noExtension') || 'No extension'}</SelectItem>
                    <SelectItem value="1">1 {t('day') || 'day'}</SelectItem>
                    <SelectItem value="2">2 {t('days') || 'days'}</SelectItem>
                    <SelectItem value="3">3 {t('days') || 'days'}</SelectItem>
                    <SelectItem value="5">5 {t('days') || 'days'}</SelectItem>
                    <SelectItem value="7">7 {t('days') || 'days'}</SelectItem>
                    <SelectItem value="14">14 {t('days') || 'days'}</SelectItem>
                    <SelectItem value="30">30 {t('days') || 'days'}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {additionalDays > 0 && (
                <div className="space-y-2">
                  <Label htmlFor="deadlineReason">{t('extensionReason') || 'Reason for extension'}</Label>
                  <Textarea
                    id="deadlineReason"
                    value={deadlineReason}
                    onChange={(e) => setDeadlineReason(e.target.value)}
                    placeholder={t('extensionReasonPlaceholder') || 'Optional: explain why the deadline needs to be extended'}
                    rows={2}
                  />
                </div>
              )}
            </>
          ) : (
            <div className="text-center py-4 text-muted-foreground">
              <Calendar className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>{t('noDeadlineSet') || 'No deadline set for this assignment'}</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Notes Section */}
      <Card>
        <CardHeader>
          <CardTitle>{t('notes') || 'Notes'}</CardTitle>
          <CardDescription>
            {t('notesDescription') || 'Add or update notes for this assignment.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            id="notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder={t('notesPlaceholder') || 'Enter notes about this assignment...'}
            rows={4}
            maxLength={5000}
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>{notes.length} / 5000</span>
            {notes !== (assignment.notes ?? '') && (
              <span className="text-blue-600">
                {t('notesChanged') || 'Notes modified'}
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex justify-between gap-3">
        <Link href={`/${locale}/dashboard/admin/assignments/${assignmentId}`}>
          <Button type="button" variant="outline">
            {tCommon('cancel')}
          </Button>
        </Link>
        <Button onClick={handleSave} disabled={isSaving || !hasChanges}>
          {isSaving ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Save className="mr-2 h-4 w-4" />
          )}
          {t('saveChanges') || 'Save Changes'}
        </Button>
      </div>
    </div>
  )
}
