'use client';

import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { FileText, Calendar, CreditCard } from 'lucide-react';
import { formatDate, formatCurrency } from '@/core/utils';

interface Declaration {
  id: string;
  type: string;
  status: string;
  amount?: number;
  created_at: string;
  due_date?: string;
}

interface DeclarationCardProps {
  declaration: Declaration;
  onClick?: () => void;
}

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    draft: 'bg-gray-500',
    pending: 'bg-yellow-500',
    in_review: 'bg-blue-500',
    approved: 'bg-green-500',
    rejected: 'bg-red-500',
    paid: 'bg-green-600',
  };
  return colors[status] || 'bg-gray-500';
};

const getStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    draft: 'Brouillon',
    pending: 'En attente',
    in_review: 'En révision',
    approved: 'Approuvé',
    rejected: 'Rejeté',
    paid: 'Payé',
  };
  return labels[status] || status;
};

export const DeclarationCard = ({ declaration, onClick }: DeclarationCardProps) => {
  return (
    <Card className="hover:shadow-lg transition-all duration-300 cursor-pointer" onClick={onClick}>
      <div className="p-6 space-y-4">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg">
              <FileText className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 className="font-semibold">{declaration.type}</h3>
              <p className="text-sm text-muted-foreground">ID: {declaration.id}</p>
            </div>
          </div>
          <Badge className={getStatusColor(declaration.status)}>
            {getStatusLabel(declaration.status)}
          </Badge>
        </div>

        {/* Details */}
        <div className="space-y-2">
          <div className="flex items-center text-sm text-muted-foreground">
            <Calendar className="mr-2 h-4 w-4" />
            <span>Créé le {formatDate(declaration.created_at)}</span>
          </div>
          {declaration.due_date && (
            <div className="flex items-center text-sm text-muted-foreground">
              <Calendar className="mr-2 h-4 w-4" />
              <span>Échéance: {formatDate(declaration.due_date)}</span>
            </div>
          )}
          {declaration.amount && (
            <div className="flex items-center text-sm">
              <CreditCard className="mr-2 h-4 w-4" />
              <span className="font-semibold">{formatCurrency(declaration.amount)}</span>
            </div>
          )}
        </div>

        {/* Action */}
        <Button variant="outline" className="w-full">
          Voir les détails
        </Button>
      </div>
    </Card>
  );
};

export default DeclarationCard;
