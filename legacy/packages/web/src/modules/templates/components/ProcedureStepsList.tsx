/**
 * ProcedureStepsList Component
 * Displays and manages procedure steps
 *
 * @module templates/components
 */

'use client'

import { useTranslations } from 'next-intl'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Loader2, GripVertical, Plus, Trash2 } from 'lucide-react'
import { useProcedureSteps } from '../hooks/useProcedureTemplates'
import type { ProcedureStep } from '../types'

interface ProcedureStepsListProps {
  templateId: string | number
  onAddStep?: () => void
  onEditStep?: (step: ProcedureStep) => void
  onDeleteStep?: (stepId: number) => void
  editable?: boolean
}

export function ProcedureStepsList({
  templateId,
  onAddStep,
  onEditStep,
  onDeleteStep,
  editable = false,
}: ProcedureStepsListProps) {
  const t = useTranslations('templates')
  const { data: steps, isLoading, error } = useProcedureSteps(templateId)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-8 text-destructive">
        {t('errorLoadingSteps')}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">{t('steps.title')}</h3>
        {editable && onAddStep && (
          <Button size="sm" onClick={onAddStep}>
            <Plus className="h-4 w-4 mr-1" />
            {t('steps.add')}
          </Button>
        )}
      </div>

      {!steps || steps.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          {t('steps.empty')}
        </div>
      ) : (
        <div className="space-y-2">
          {steps.map((step: ProcedureStep, index: number) => (
            <Card
              key={step.id}
              className="cursor-pointer hover:bg-muted/50 transition-colors"
              onClick={() => onEditStep?.(step)}
            >
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  {editable && (
                    <GripVertical className="h-5 w-5 text-muted-foreground mt-0.5 cursor-grab" />
                  )}
                  <Badge variant="outline" className="shrink-0">
                    {index + 1}
                  </Badge>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium">{step.descriptionEs}</p>
                    {step.instructionsEs && (
                      <p className="text-sm text-muted-foreground line-clamp-2 mt-1">
                        {step.instructionsEs}
                      </p>
                    )}
                    {step.estimatedDurationMinutes && (
                      <p className="text-xs text-muted-foreground mt-1">
                        {t('steps.estimatedTime')}: {step.estimatedDurationMinutes} min
                      </p>
                    )}
                  </div>
                  {editable && onDeleteStep && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        onDeleteStep(step.id)
                      }}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
