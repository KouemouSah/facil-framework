/**
 * TemplateCard Component
 * Displays a single template as a card
 *
 * @module templates/components
 */

'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { FileText, ListOrdered, Edit, Trash2 } from 'lucide-react'
import { useTranslations } from 'next-intl'
import type { TemplateCardProps } from '../types'

export function TemplateCard({
  id: _id,
  name,
  description,
  category,
  isActive,
  type,
  onClick,
  onEdit,
  onDelete,
}: TemplateCardProps) {
  const t = useTranslations('templates')

  const Icon = type === 'document' ? FileText : ListOrdered

  return (
    <Card
      className={`cursor-pointer hover:shadow-md transition-shadow ${
        !isActive ? 'opacity-60' : ''
      }`}
      onClick={onClick}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <Icon className="h-5 w-5 text-primary" />
            <CardTitle className="text-base line-clamp-1">{name}</CardTitle>
          </div>
          <Badge variant={isActive ? 'default' : 'secondary'}>
            {isActive ? t('active') : t('inactive')}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {description && (
          <p className="text-sm text-muted-foreground line-clamp-2 mb-3">
            {description}
          </p>
        )}
        {category && (
          <Badge variant="outline" className="mb-3">
            {category}
          </Badge>
        )}
        <div className="flex justify-end gap-2">
          {onEdit && (
            <Button
              variant="ghost"
              size="sm"
              onClick={(e) => {
                e.stopPropagation()
                onEdit()
              }}
            >
              <Edit className="h-4 w-4" />
            </Button>
          )}
          {onDelete && (
            <Button
              variant="ghost"
              size="sm"
              onClick={(e) => {
                e.stopPropagation()
                onDelete()
              }}
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
