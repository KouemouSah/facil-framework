'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
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
import { Checkbox } from '@/components/ui/checkbox';
import { ScrollArea } from '@/components/ui/scroll-area';
import { AlertCircle, Loader2 } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface Company {
  id: string;
  name: string;
  tax_id?: string;
}

interface ClientData {
  company_id: string;
  taxable_base?: number;
  calculated_tax?: number;
  deductions?: number;
  credits?: number;
  taxpayer_notes?: string;
}

interface BatchCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  companies: Company[];
  onSubmit: (data: BatchCreateRequest) => Promise<void>;
}

interface BatchCreateRequest {
  template: {
    declaration_type: string;
    fiscal_year: number;
    fiscal_period?: string;
    declaration_deadline: string;
    default_taxable_base?: number;
    default_calculated_tax?: number;
    default_deductions?: number;
    default_credits?: number;
    taxpayer_notes?: string;
    declared_data?: Record<string, any>;
    supporting_documents?: string[];
  };
  clients: ClientData[];
  batch_name?: string;
  send_notifications: boolean;
  auto_submit: boolean;
}

const DECLARATION_TYPES = [
  { value: 'iva_destajo', label: 'IVA Destajo' },
  { value: 'iva_real', label: 'IVA Real' },
  { value: 'income_tax', label: 'Impôt sur le revenu' },
  { value: 'corporate_tax', label: 'Impôt sur les sociétés' },
  { value: 'payroll_tax', label: 'Taxe sur les salaires' },
];

export function BatchCreateDialog({
  open,
  onOpenChange,
  companies,
  onSubmit,
}: BatchCreateDialogProps) {
  const [loading, setLoading] = useState(false);
  const [selectedCompanies, setSelectedCompanies] = useState<Set<string>>(new Set());
  const [batchName, setBatchName] = useState('');
  const [template, setTemplate] = useState({
    declaration_type: '',
    fiscal_year: new Date().getFullYear(),
    fiscal_period: '',
    declaration_deadline: '',
    default_taxable_base: undefined as number | undefined,
    default_calculated_tax: undefined as number | undefined,
    default_deductions: undefined as number | undefined,
    default_credits: undefined as number | undefined,
    taxpayer_notes: '',
  });
  const [sendNotifications, setSendNotifications] = useState(true);
  const [autoSubmit, setAutoSubmit] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleCompanyToggle = (companyId: string) => {
    const newSelected = new Set(selectedCompanies);
    if (newSelected.has(companyId)) {
      newSelected.delete(companyId);
    } else {
      newSelected.add(companyId);
    }
    setSelectedCompanies(newSelected);
  };

  const handleSelectAll = () => {
    if (selectedCompanies.size === companies.length) {
      setSelectedCompanies(new Set());
    } else {
      setSelectedCompanies(new Set(companies.map((c) => c.id)));
    }
  };

  const handleSubmit = async () => {
    if (!template.declaration_type || !template.declaration_deadline || selectedCompanies.size === 0) {
      return;
    }

    setLoading(true);
    try {
      const request: BatchCreateRequest = {
        template: {
          ...template,
          fiscal_period: template.fiscal_period || undefined,
        },
        clients: Array.from(selectedCompanies).map((company_id) => ({
          company_id,
        })),
        batch_name: batchName || undefined,
        send_notifications: sendNotifications,
        auto_submit: autoSubmit,
      };

      await onSubmit(request);
      onOpenChange(false);

      // Reset form
      setSelectedCompanies(new Set());
      setBatchName('');
      setTemplate({
        declaration_type: '',
        fiscal_year: new Date().getFullYear(),
        fiscal_period: '',
        declaration_deadline: '',
        default_taxable_base: undefined,
        default_calculated_tax: undefined,
        default_deductions: undefined,
        default_credits: undefined,
        taxpayer_notes: '',
      });
    } catch (error) {
      console.error('Error creating batch:', error);
    } finally {
      setLoading(false);
    }
  };

  const isValid = template.declaration_type && template.declaration_deadline && selectedCompanies.size > 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Créer des déclarations en lot</DialogTitle>
          <DialogDescription>
            Créer des déclarations similaires pour plusieurs clients à la fois
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="flex-1 pr-4">
          <div className="space-y-6 py-4">
            {/* Batch Name */}
            <div className="space-y-2">
              <Label htmlFor="batch-name">Nom du lot (optionnel)</Label>
              <Input
                id="batch-name"
                placeholder="Ex: IVA Novembre 2025"
                value={batchName}
                onChange={(e) => setBatchName(e.target.value)}
              />
            </div>

            {/* Template Section */}
            <div className="space-y-4 border rounded-lg p-4">
              <h3 className="font-semibold text-sm">Modèle de déclaration</h3>

              {/* Declaration Type */}
              <div className="space-y-2">
                <Label htmlFor="declaration-type">
                  Type de déclaration <span className="text-red-500">*</span>
                </Label>
                <Select
                  value={template.declaration_type}
                  onValueChange={(value) =>
                    setTemplate({ ...template, declaration_type: value })
                  }
                >
                  <SelectTrigger id="declaration-type">
                    <SelectValue placeholder="Sélectionner un type" />
                  </SelectTrigger>
                  <SelectContent>
                    {DECLARATION_TYPES.map((type) => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                {/* Fiscal Year */}
                <div className="space-y-2">
                  <Label htmlFor="fiscal-year">Année fiscale</Label>
                  <Input
                    id="fiscal-year"
                    type="number"
                    min="2000"
                    max="2100"
                    value={template.fiscal_year}
                    onChange={(e) =>
                      setTemplate({ ...template, fiscal_year: parseInt(e.target.value) })
                    }
                  />
                </div>

                {/* Fiscal Period */}
                <div className="space-y-2">
                  <Label htmlFor="fiscal-period">Période fiscale (optionnel)</Label>
                  <Input
                    id="fiscal-period"
                    placeholder="Ex: Novembre, Q4"
                    value={template.fiscal_period}
                    onChange={(e) =>
                      setTemplate({ ...template, fiscal_period: e.target.value })
                    }
                  />
                </div>
              </div>

              {/* Declaration Deadline */}
              <div className="space-y-2">
                <Label htmlFor="deadline">
                  Date limite <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="deadline"
                  type="date"
                  value={template.declaration_deadline}
                  onChange={(e) =>
                    setTemplate({ ...template, declaration_deadline: e.target.value })
                  }
                />
              </div>

              {/* Advanced Options */}
              <div className="space-y-4">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="text-sm"
                >
                  {showAdvanced ? 'Masquer' : 'Afficher'} les options avancées
                </Button>

                {showAdvanced && (
                  <div className="space-y-4 border-t pt-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="default-taxable-base">Base imposable par défaut</Label>
                        <Input
                          id="default-taxable-base"
                          type="number"
                          min="0"
                          step="0.01"
                          placeholder="0.00"
                          value={template.default_taxable_base || ''}
                          onChange={(e) =>
                            setTemplate({
                              ...template,
                              default_taxable_base: e.target.value
                                ? parseFloat(e.target.value)
                                : undefined,
                            })
                          }
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="default-calculated-tax">Impôt calculé par défaut</Label>
                        <Input
                          id="default-calculated-tax"
                          type="number"
                          min="0"
                          step="0.01"
                          placeholder="0.00"
                          value={template.default_calculated_tax || ''}
                          onChange={(e) =>
                            setTemplate({
                              ...template,
                              default_calculated_tax: e.target.value
                                ? parseFloat(e.target.value)
                                : undefined,
                            })
                          }
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="taxpayer-notes">Notes du contribuable</Label>
                      <Textarea
                        id="taxpayer-notes"
                        placeholder="Notes communes pour toutes les déclarations..."
                        value={template.taxpayer_notes}
                        onChange={(e) =>
                          setTemplate({ ...template, taxpayer_notes: e.target.value })
                        }
                        rows={3}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Client Selection */}
            <div className="space-y-4 border rounded-lg p-4">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-sm">
                  Sélectionner les clients ({selectedCompanies.size})
                </h3>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleSelectAll}
                >
                  {selectedCompanies.size === companies.length
                    ? 'Tout désélectionner'
                    : 'Tout sélectionner'}
                </Button>
              </div>

              {companies.length === 0 ? (
                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    Aucune entreprise disponible. Ajoutez des clients d&apos;abord.
                  </AlertDescription>
                </Alert>
              ) : (
                <ScrollArea className="h-[200px] border rounded-md p-2">
                  <div className="space-y-2">
                    {companies.map((company) => (
                      <div
                        key={company.id}
                        className="flex items-center space-x-3 p-2 hover:bg-accent rounded-md cursor-pointer"
                        onClick={() => handleCompanyToggle(company.id)}
                      >
                        <Checkbox
                          checked={selectedCompanies.has(company.id)}
                          onCheckedChange={() => handleCompanyToggle(company.id)}
                        />
                        <div className="flex-1">
                          <p className="text-sm font-medium">{company.name}</p>
                          {company.tax_id && (
                            <p className="text-xs text-muted-foreground">{company.tax_id}</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </div>

            {/* Options */}
            <div className="space-y-4 border rounded-lg p-4">
              <h3 className="font-semibold text-sm">Options</h3>

              <div className="flex items-center space-x-3">
                <Checkbox
                  id="send-notifications"
                  checked={sendNotifications}
                  onCheckedChange={(checked) => setSendNotifications(checked as boolean)}
                />
                <Label htmlFor="send-notifications" className="text-sm font-normal cursor-pointer">
                  Envoyer des notifications aux clients
                </Label>
              </div>

              <div className="flex items-center space-x-3">
                <Checkbox
                  id="auto-submit"
                  checked={autoSubmit}
                  onCheckedChange={(checked) => setAutoSubmit(checked as boolean)}
                />
                <Label htmlFor="auto-submit" className="text-sm font-normal cursor-pointer">
                  Soumettre automatiquement après création
                </Label>
              </div>
            </div>
          </div>
        </ScrollArea>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
            Annuler
          </Button>
          <Button onClick={handleSubmit} disabled={!isValid || loading}>
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Créer {selectedCompanies.size} déclaration{selectedCompanies.size > 1 ? 's' : ''}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
