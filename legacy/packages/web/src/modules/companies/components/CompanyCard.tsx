'use client';

import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Building, MapPin, Phone } from 'lucide-react';
import type { Company } from '../types';

interface CompanyCardProps {
  company: Company;
  onClick?: () => void;
}

export const CompanyCard = ({ company, onClick }: CompanyCardProps) => {
  return (
    <Card className="p-4 cursor-pointer hover:shadow-lg transition-all" onClick={onClick}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <Building className="h-8 w-8 text-primary" />
          <div>
            <h3 className="font-semibold">{company.legal_name}</h3>
            <p className="text-sm text-muted-foreground">NIF: {company.nif || company.tax_id}</p>
          </div>
        </div>
        <Badge variant={company.is_active ? 'default' : 'secondary'}>
          {company.is_active ? 'Activa' : 'Inactiva'}
        </Badge>
      </div>
      {(company.address || company.phone) && (
        <div className="space-y-1 text-sm text-muted-foreground">
          {company.address && (
            <div className="flex items-center gap-2">
              <MapPin className="h-4 w-4" />
              <span>{company.address}{company.city_name && `, ${company.city_name}`}</span>
            </div>
          )}
          {company.phone && (
            <div className="flex items-center gap-2">
              <Phone className="h-4 w-4" />
              <span>{company.phone}</span>
            </div>
          )}
        </div>
      )}
    </Card>
  );
};
