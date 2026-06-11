/**
 * RelatedServices Component
 * Display semantically related services with similarity scores
 */

'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import { FileText } from 'lucide-react'
import type { ServiceReference } from '../types'

export interface RelatedServicesProps {
  services: ServiceReference[]
  onSelect?: (service: ServiceReference) => void
  maxVisible?: number
  className?: string
}

export const RelatedServices: React.FC<RelatedServicesProps> = ({
  services,
  onSelect,
  maxVisible = 3,
  className = '',
}) => {
  const t = useTranslations('chatbot')

  if (services.length === 0) return null

  return (
    <div className={`px-4 py-2 border-t bg-muted/30 ${className}`}>
      <div className="text-xs font-medium mb-2 text-muted-foreground flex items-center gap-1">
        <FileText className="h-3 w-3" />
        {t('relatedServices') || 'Related Services'}
      </div>
      <div className="space-y-1">
        {services.slice(0, maxVisible).map((service, i) => (
          <div
            key={i}
            className="text-xs p-2 rounded bg-white border hover:border-primary/50 cursor-pointer transition-colors"
            onClick={() => onSelect?.(service)}
          >
            <div className="flex items-center justify-between">
              <div className="font-medium flex-1">{service.name}</div>
              {service.similarity && (
                <div className="text-muted-foreground text-[10px] ml-2">
                  {Math.round(service.similarity * 100)}% {t('match') || 'match'}
                </div>
              )}
            </div>
            {service.serviceCode && (
              <div className="text-[10px] text-muted-foreground mt-0.5 font-mono">
                {service.serviceCode}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default RelatedServices
