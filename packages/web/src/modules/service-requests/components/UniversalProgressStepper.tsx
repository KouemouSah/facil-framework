'use client'

import { CheckCircle, ListChecks, FileUp, FileText, Calendar, CreditCard, ShieldCheck } from 'lucide-react'

export interface StepperPhase {
  id: string
  title_es: string
  step_type: string
  number: number
  is_optional?: boolean
}

interface UniversalProgressStepperProps {
  phases: StepperPhase[]
  currentIndex: number
  status: string
  locale?: string
}

const STEP_TYPE_ICONS: Record<string, React.ElementType> = {
  selection: ListChecks,
  upload: FileUp,
  form_review: FileText,
  appointment: Calendar,
  payment: CreditCard,
  confirmation: ShieldCheck,
}

/**
 * Collapse consecutive form_review steps into groups for visual compactness.
 * E.g. form_review_1, form_review_2, form_review_3 → single "Formulario" dot.
 * Non-form_review steps are kept as-is.
 */
function collapsePhases(phases: StepperPhase[], formLabel: string): { label: string; type: string; startIndex: number; endIndex: number }[] {
  const groups: { label: string; type: string; startIndex: number; endIndex: number }[] = []
  let i = 0
  while (i < phases.length) {
    const phase = phases[i]
    if (phase.step_type === 'form_review') {
      // Collapse consecutive form_review steps
      const start = i
      while (i < phases.length && phases[i].step_type === 'form_review') {
        i++
      }
      groups.push({
        label: formLabel,
        type: 'form_review',
        startIndex: start,
        endIndex: i - 1,
      })
    } else {
      groups.push({
        label: phase.title_es,
        type: phase.step_type,
        startIndex: i,
        endIndex: i,
      })
      i++
    }
  }
  return groups
}

const FORM_REVIEW_LABELS: Record<string, string> = {
  es: 'Formulario',
  fr: 'Formulaire',
  en: 'Form',
}

export function UniversalProgressStepper({ phases, currentIndex, status, locale = 'es' }: UniversalProgressStepperProps) {
  if (!phases.length) return null

  const isTerminal = ['COMPLETED', 'REJECTED', 'CANCELLED', 'EXPIRED'].includes(status)
  const formLabel = FORM_REVIEW_LABELS[locale] || FORM_REVIEW_LABELS.es
  const groups = collapsePhases(phases, formLabel)

  return (
    <div className="overflow-x-auto">
      <div className="flex items-center justify-between min-w-[500px]">
        {groups.map((group, gi) => {
          const isDone = isTerminal || currentIndex > group.endIndex
          const isCurrent = !isTerminal && currentIndex >= group.startIndex && currentIndex <= group.endIndex
          const Icon = STEP_TYPE_ICONS[group.type] || FileText

          return (
            <div key={group.startIndex} className="flex items-center flex-1">
              <div className="flex flex-col items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center transition-all ${
                    isDone
                      ? 'bg-green-500 text-white'
                      : isCurrent
                        ? 'bg-blue-500 text-white ring-2 ring-blue-200 animate-pulse'
                        : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {isDone ? <CheckCircle className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                </div>
                <span
                  className={`text-[10px] mt-1 text-center max-w-[70px] leading-tight ${
                    isDone
                      ? 'text-green-700 font-medium'
                      : isCurrent
                        ? 'text-blue-700 font-medium'
                        : 'text-muted-foreground'
                  }`}
                >
                  {group.label}
                </span>
              </div>
              {gi < groups.length - 1 && (
                <div className={`flex-1 h-0.5 mx-1 ${isDone ? 'bg-green-500' : 'bg-muted'}`} />
              )}
            </div>
          )
        })}
      </div>
      {/* Progress percentage based on collapsed groups */}
      <div className="mt-3 text-center">
        <span className="text-xs text-muted-foreground">
          {isTerminal
            ? '100%'
            : `${Math.round((Math.max(0, groups.findIndex(g => currentIndex >= g.startIndex && currentIndex <= g.endIndex)) / Math.max(groups.length - 1, 1)) * 100)}%`}
        </span>
      </div>
    </div>
  )
}
