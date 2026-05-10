'use client';

import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CreditCard, Calendar, DollarSign } from 'lucide-react';
import { formatDate, formatCurrency } from '@/core/utils';

interface Payment {
  id: string;
  amount: number;
  status: string;
  payment_method: string;
  created_at: string;
  declaration_id?: string;
}

interface PaymentCardProps {
  payment: Payment;
}

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    pending: 'bg-yellow-500',
    processing: 'bg-blue-500',
    completed: 'bg-green-500',
    failed: 'bg-red-500',
    refunded: 'bg-purple-500',
    cancelled: 'bg-gray-500',
  };
  return colors[status] || 'bg-gray-500';
};

export const PaymentCard = ({ payment }: PaymentCardProps) => {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg">
            <CreditCard className="h-5 w-5 text-primary" />
          </div>
          <div>
            <p className="font-semibold text-lg">{formatCurrency(payment.amount)}</p>
            <p className="text-sm text-muted-foreground">ID: {payment.id}</p>
          </div>
        </div>
        <Badge className={getStatusColor(payment.status)}>{payment.status}</Badge>
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex items-center gap-2 text-muted-foreground">
          <DollarSign className="h-4 w-4" />
          <span>{payment.payment_method}</span>
        </div>
        <div className="flex items-center gap-2 text-muted-foreground">
          <Calendar className="h-4 w-4" />
          <span>{formatDate(payment.created_at)}</span>
        </div>
      </div>
    </Card>
  );
};

export default PaymentCard;
