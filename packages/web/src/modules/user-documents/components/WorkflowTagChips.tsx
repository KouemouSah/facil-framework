/**
 * WorkflowTagChips - Horizontal chips showing workflow compatibility
 *
 * Displays workflow codes as small, color-coded chips to indicate
 * which procedures a document can be used for.
 *
 * @module user-documents/components
 */

'use client';

import { useTranslations } from 'next-intl';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Link2 } from 'lucide-react';

// ---------------------------------------------------------------------------
// Color palette for chips (cycling through for variety)
// ---------------------------------------------------------------------------

const CHIP_COLORS = [
  'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
  'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
  'bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-300',
  'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300',
  'bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-300',
];

interface WorkflowTagChipsProps {
  /** Array of workflow code strings */
  tags?: string[];
  /** Maximum number of chips to show before "+N more" */
  maxVisible?: number;
}

export function WorkflowTagChips({ tags, maxVisible = 3 }: WorkflowTagChipsProps) {
  const t = useTranslations('userDocuments');

  if (!tags || tags.length === 0) return null;

  const visible = tags.slice(0, maxVisible);
  const overflow = tags.length - maxVisible;

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex flex-wrap items-center gap-1">
        <Link2 className="h-3 w-3 text-muted-foreground shrink-0" />
        {visible.map((code, index) => {
          const label = t(`workflows.short.${code.toLowerCase()}`, { defaultValue: code.replace(/_/g, ' ') });
          const colorClass = CHIP_COLORS[index % CHIP_COLORS.length];

          return (
            <Tooltip key={code}>
              <TooltipTrigger asChild>
                <Badge
                  variant="outline"
                  className={`text-[10px] px-1.5 py-0 h-5 font-medium border-none ${colorClass}`}
                >
                  {label}
                </Badge>
              </TooltipTrigger>
              <TooltipContent side="top" className="text-xs">
                {t('workflowTag.usableFor', { workflow: code })}
              </TooltipContent>
            </Tooltip>
          );
        })}

        {overflow > 0 && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge
                variant="outline"
                className="text-[10px] px-1.5 py-0 h-5 text-muted-foreground"
              >
                +{overflow}
              </Badge>
            </TooltipTrigger>
            <TooltipContent side="top" className="text-xs">
              {tags.slice(maxVisible).map((c) => (
                <div key={c}>
                  {t(`workflows.short.${c.toLowerCase()}`, { defaultValue: c.replace(/_/g, ' ') })}
                </div>
              ))}
            </TooltipContent>
          </Tooltip>
        )}
      </div>
    </TooltipProvider>
  );
}
