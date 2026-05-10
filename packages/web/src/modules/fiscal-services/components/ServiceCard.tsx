'use client';

import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Building, Clock, ArrowRight } from 'lucide-react';
import { formatCurrency } from '@/core/utils';
import type { ServiceResult } from '@/core/api/services';

interface ServiceCardProps {
  service: ServiceResult;
  onClick?: () => void;
}

export const ServiceCard = ({ service, onClick }: ServiceCardProps) => {
  return (
    <Card className="group hover:shadow-lg transition-all duration-300 cursor-pointer" onClick={onClick}>
      <div className="p-6 space-y-4">
        {/* Header */}
        <div>
          <div className="flex items-start justify-between mb-2">
            <h3 className="font-semibold text-lg group-hover:text-primary transition-colors line-clamp-2">
              {service.name}
            </h3>
            <Badge variant="secondary">{service.service_type}</Badge>
          </div>
          {service.description && (
            <p className="text-sm text-muted-foreground line-clamp-2">{service.description}</p>
          )}
        </div>

        {/* Category & Ministry */}
        <div className="space-y-1 text-sm">
          <div className="flex items-center text-muted-foreground">
            <Building className="mr-2 h-4 w-4" />
            <span className="truncate">{service.category_name}</span>
          </div>
          {service.ministry_name && (
            <div className="flex items-center text-muted-foreground">
              <Building className="mr-2 h-4 w-4" />
              <span className="truncate">{service.ministry_name}</span>
            </div>
          )}
        </div>

        {/* Pricing */}
        <div className="flex items-center justify-between pt-4 border-t">
          <div className="space-y-1">
            <div className="text-sm text-muted-foreground">Prix d&apos;expédition</div>
            <div className="text-lg font-bold text-primary">
              {formatCurrency(service.expedition_price)}
            </div>
          </div>
          {service.processing_time_days > 0 && (
            <div className="flex items-center text-sm text-muted-foreground">
              <Clock className="mr-1 h-4 w-4" />
              <span>{service.processing_time_days}j</span>
            </div>
          )}
        </div>

        {/* Action Button */}
        <Button className="w-full group-hover:bg-primary/90 transition-colors">
          Voir les détails
          <ArrowRight className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform" />
        </Button>
      </div>
    </Card>
  );
};

export default ServiceCard;
