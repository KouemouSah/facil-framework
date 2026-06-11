'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { APP_CONSTANTS } from '@/core/config/constants';

interface DeclarationFormProps {
  onSubmit: (data: DeclarationFormData) => Promise<void>;
  initialData?: Partial<DeclarationFormData>;
}

export interface DeclarationFormData {
  type: string;
  period: string;
  amount: number;
  description?: string;
}

export const DeclarationForm = ({ onSubmit, initialData }: DeclarationFormProps) => {
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState<DeclarationFormData>({
    type: initialData?.type || '',
    period: initialData?.period || '',
    amount: initialData?.amount || 0,
    description: initialData?.description || '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await onSubmit(formData);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="p-6">
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Type */}
        <div className="space-y-2">
          <Label htmlFor="type">Type de déclaration</Label>
          <Select
            value={formData.type}
            onValueChange={(value) => setFormData({ ...formData, type: value })}
          >
            <SelectTrigger id="type">
              <SelectValue placeholder="Sélectionner un type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={APP_CONSTANTS.DECLARATION_TYPES.IVA_DESTAJO}>
                IVA Destajo
              </SelectItem>
              <SelectItem value={APP_CONSTANTS.DECLARATION_TYPES.IVA_REAL}>
                IVA Real
              </SelectItem>
              <SelectItem value={APP_CONSTANTS.DECLARATION_TYPES.INCOME_TAX}>
                Impôt sur le revenu
              </SelectItem>
              <SelectItem value={APP_CONSTANTS.DECLARATION_TYPES.CORPORATE_TAX}>
                Impôt sur les sociétés
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Period */}
        <div className="space-y-2">
          <Label htmlFor="period">Période</Label>
          <Input
            id="period"
            type="month"
            value={formData.period}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, period: e.target.value })}
            required
          />
        </div>

        {/* Amount */}
        <div className="space-y-2">
          <Label htmlFor="amount">Montant (XAF)</Label>
          <Input
            id="amount"
            type="number"
            min="0"
            step="0.01"
            value={formData.amount}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, amount: parseFloat(e.target.value) })}
            required
          />
        </div>

        {/* Description */}
        <div className="space-y-2">
          <Label htmlFor="description">Description (optionnel)</Label>
          <Textarea
            id="description"
            rows={4}
            value={formData.description}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setFormData({ ...formData, description: e.target.value })}
            placeholder="Informations complémentaires..."
          />
        </div>

        {/* Actions */}
        <div className="flex gap-4">
          <Button type="submit" disabled={loading} className="flex-1">
            {loading ? 'Enregistrement...' : 'Enregistrer'}
          </Button>
          <Button type="button" variant="outline" disabled={loading} className="flex-1">
            Annuler
          </Button>
        </div>
      </form>
    </Card>
  );
};

export default DeclarationForm;
