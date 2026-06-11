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
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  FileText,
  FileSpreadsheet,
  Download,
  Loader2,
  Calendar,
  Building2,
  Filter,
} from 'lucide-react';
import { Card } from '@/components/ui/card';

interface Company {
  id: string;
  name: string;
}

interface ReportGeneratorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  companies: Company[];
  onGenerate: (data: ReportGenerateRequest) => Promise<void>;
}

interface ReportGenerateRequest {
  report_type: 'summary' | 'detailed' | 'client_breakdown' | 'tax_breakdown' | 'timeline';
  format: 'pdf' | 'excel' | 'csv' | 'json';
  period: {
    start_date: string;
    end_date: string;
  };
  filters?: {
    company_ids?: string[];
    declaration_types?: string[];
    declaration_statuses?: string[];
    fiscal_years?: number[];
    min_tax_amount?: number;
    max_tax_amount?: number;
  };
  include_charts: boolean;
  include_raw_data: boolean;
  group_by_client: boolean;
  group_by_type: boolean;
  report_title?: string;
  report_notes?: string;
}

const REPORT_TYPES = [
  {
    value: 'summary',
    label: 'Résumé',
    description: 'Vue d\'ensemble avec totaux et statistiques',
    icon: FileText,
  },
  {
    value: 'detailed',
    label: 'Détaillé',
    description: 'Détails complets de toutes les déclarations',
    icon: FileSpreadsheet,
  },
  {
    value: 'client_breakdown',
    label: 'Par client',
    description: 'Regroupé par client',
    icon: Building2,
  },
  {
    value: 'tax_breakdown',
    label: 'Par type d\'impôt',
    description: 'Regroupé par type de déclaration',
    icon: Filter,
  },
  {
    value: 'timeline',
    label: 'Chronologique',
    description: 'Vue chronologique',
    icon: Calendar,
  },
];

const EXPORT_FORMATS = [
  { value: 'pdf', label: 'PDF', icon: '📄', description: 'Rapport professionnel avec graphiques' },
  {
    value: 'excel',
    label: 'Excel',
    icon: '📊',
    description: 'Feuille de calcul avec plusieurs onglets',
  },
  { value: 'csv', label: 'CSV', icon: '📋', description: 'Export simple CSV' },
  { value: 'json', label: 'JSON', icon: '{ }', description: 'Données brutes JSON' },
];

const DECLARATION_TYPES = [
  { value: 'iva_destajo', label: 'IVA Destajo' },
  { value: 'iva_real', label: 'IVA Real' },
  { value: 'income_tax', label: 'Impôt sur le revenu' },
  { value: 'corporate_tax', label: 'Impôt sur les sociétés' },
];

const DECLARATION_STATUSES = [
  { value: 'draft', label: 'Brouillon' },
  { value: 'submitted', label: 'Soumise' },
  { value: 'processing', label: 'En traitement' },
  { value: 'accepted', label: 'Acceptée' },
  { value: 'rejected', label: 'Rejetée' },
];

export function ReportGenerator({
  open,
  onOpenChange,
  companies,
  onGenerate,
}: ReportGeneratorProps) {
  const [loading, setLoading] = useState(false);
  const [reportType, setReportType] = useState<string>('summary');
  const [format, setFormat] = useState<string>('pdf');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [selectedCompanies, setSelectedCompanies] = useState<Set<string>>(new Set());
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());
  const [selectedStatuses, setSelectedStatuses] = useState<Set<string>>(new Set());
  const [includeCharts, setIncludeCharts] = useState(true);
  const [includeRawData, setIncludeRawData] = useState(false);
  const [groupByClient, setGroupByClient] = useState(true);
  const [groupByType, setGroupByType] = useState(false);
  const [reportTitle, setReportTitle] = useState('');
  const [reportNotes, setReportNotes] = useState('');
  const [_showAdvanced, _setShowAdvanced] = useState(false);

  const handleCompanyToggle = (companyId: string) => {
    const newSelected = new Set(selectedCompanies);
    if (newSelected.has(companyId)) {
      newSelected.delete(companyId);
    } else {
      newSelected.add(companyId);
    }
    setSelectedCompanies(newSelected);
  };

  const handleTypeToggle = (type: string) => {
    const newSelected = new Set(selectedTypes);
    if (newSelected.has(type)) {
      newSelected.delete(type);
    } else {
      newSelected.add(type);
    }
    setSelectedTypes(newSelected);
  };

  const handleStatusToggle = (status: string) => {
    const newSelected = new Set(selectedStatuses);
    if (newSelected.has(status)) {
      newSelected.delete(status);
    } else {
      newSelected.add(status);
    }
    setSelectedStatuses(newSelected);
  };

  const handleGenerate = async () => {
    if (!reportType || !format || !startDate || !endDate) {
      return;
    }

    setLoading(true);
    try {
      const request: ReportGenerateRequest = {
        report_type: reportType as any,
        format: format as any,
        period: {
          start_date: startDate,
          end_date: endDate,
        },
        filters: {
          company_ids:
            selectedCompanies.size > 0 ? Array.from(selectedCompanies) : undefined,
          declaration_types:
            selectedTypes.size > 0 ? Array.from(selectedTypes) : undefined,
          declaration_statuses:
            selectedStatuses.size > 0 ? Array.from(selectedStatuses) : undefined,
        },
        include_charts: includeCharts,
        include_raw_data: includeRawData,
        group_by_client: groupByClient,
        group_by_type: groupByType,
        report_title: reportTitle || undefined,
        report_notes: reportNotes || undefined,
      };

      await onGenerate(request);
      onOpenChange(false);
    } catch (error) {
      console.error('Error generating report:', error);
    } finally {
      setLoading(false);
    }
  };

  const isValid = reportType && format && startDate && endDate;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Générer un rapport consolidé</DialogTitle>
          <DialogDescription>
            Créer un rapport détaillé de vos déclarations sur une période donnée
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="flex-1 pr-4">
          <div className="space-y-6 py-4">
            {/* Report Title */}
            <div className="space-y-2">
              <Label htmlFor="report-title">Titre du rapport (optionnel)</Label>
              <Input
                id="report-title"
                placeholder="Ex: Rapport trimestriel Q4 2025"
                value={reportTitle}
                onChange={(e) => setReportTitle(e.target.value)}
              />
            </div>

            {/* Report Type */}
            <div className="space-y-3">
              <Label>Type de rapport <span className="text-red-500">*</span></Label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {REPORT_TYPES.map((type) => (
                  <Card
                    key={type.value}
                    className={`p-4 cursor-pointer transition-all ${
                      reportType === type.value
                        ? 'border-primary bg-primary/5'
                        : 'hover:border-primary/50'
                    }`}
                    onClick={() => setReportType(type.value)}
                  >
                    <div className="flex items-start space-x-3">
                      <type.icon className="h-5 w-5 mt-0.5 text-muted-foreground" />
                      <div className="flex-1">
                        <h4 className="text-sm font-medium">{type.label}</h4>
                        <p className="text-xs text-muted-foreground mt-1">
                          {type.description}
                        </p>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>

            {/* Export Format */}
            <div className="space-y-3">
              <Label>Format d&apos;export <span className="text-red-500">*</span></Label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {EXPORT_FORMATS.map((fmt) => (
                  <Card
                    key={fmt.value}
                    className={`p-3 cursor-pointer transition-all ${
                      format === fmt.value
                        ? 'border-primary bg-primary/5'
                        : 'hover:border-primary/50'
                    }`}
                    onClick={() => setFormat(fmt.value)}
                  >
                    <div className="text-center">
                      <div className="text-2xl mb-1">{fmt.icon}</div>
                      <p className="text-sm font-medium">{fmt.label}</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {fmt.description}
                      </p>
                    </div>
                  </Card>
                ))}
              </div>
            </div>

            {/* Period */}
            <div className="space-y-4 border rounded-lg p-4">
              <h3 className="font-semibold text-sm">
                Période <span className="text-red-500">*</span>
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="start-date">Date de début</Label>
                  <Input
                    id="start-date"
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="end-date">Date de fin</Label>
                  <Input
                    id="end-date"
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                  />
                </div>
              </div>
            </div>

            {/* Filters */}
            <div className="space-y-4 border rounded-lg p-4">
              <h3 className="font-semibold text-sm">Filtres (optionnel)</h3>

              {/* Company Filter */}
              <div className="space-y-2">
                <Label>Clients ({selectedCompanies.size || 'tous'})</Label>
                <ScrollArea className="h-[120px] border rounded-md p-2">
                  <div className="space-y-2">
                    {companies.map((company) => (
                      <div
                        key={company.id}
                        className="flex items-center space-x-2 p-1 hover:bg-accent rounded cursor-pointer"
                        onClick={() => handleCompanyToggle(company.id)}
                      >
                        <Checkbox checked={selectedCompanies.has(company.id)} />
                        <span className="text-sm">{company.name}</span>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </div>

              {/* Type Filter */}
              <div className="space-y-2">
                <Label>Types de déclaration ({selectedTypes.size || 'tous'})</Label>
                <div className="flex flex-wrap gap-2">
                  {DECLARATION_TYPES.map((type) => (
                    <Badge
                      key={type.value}
                      variant={selectedTypes.has(type.value) ? 'default' : 'outline'}
                      className="cursor-pointer"
                      onClick={() => handleTypeToggle(type.value)}
                    >
                      {type.label}
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Status Filter */}
              <div className="space-y-2">
                <Label>Statuts ({selectedStatuses.size || 'tous'})</Label>
                <div className="flex flex-wrap gap-2">
                  {DECLARATION_STATUSES.map((status) => (
                    <Badge
                      key={status.value}
                      variant={selectedStatuses.has(status.value) ? 'default' : 'outline'}
                      className="cursor-pointer"
                      onClick={() => handleStatusToggle(status.value)}
                    >
                      {status.label}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>

            {/* Options */}
            <div className="space-y-4 border rounded-lg p-4">
              <h3 className="font-semibold text-sm">Options du rapport</h3>

              <div className="space-y-3">
                {format === 'pdf' && (
                  <div className="flex items-center space-x-3">
                    <Checkbox
                      id="include-charts"
                      checked={includeCharts}
                      onCheckedChange={(checked) => setIncludeCharts(checked as boolean)}
                    />
                    <Label htmlFor="include-charts" className="text-sm font-normal cursor-pointer">
                      Inclure des graphiques (PDF uniquement)
                    </Label>
                  </div>
                )}

                {format === 'excel' && (
                  <div className="flex items-center space-x-3">
                    <Checkbox
                      id="include-raw-data"
                      checked={includeRawData}
                      onCheckedChange={(checked) => setIncludeRawData(checked as boolean)}
                    />
                    <Label
                      htmlFor="include-raw-data"
                      className="text-sm font-normal cursor-pointer"
                    >
                      Inclure les données brutes (Excel uniquement)
                    </Label>
                  </div>
                )}

                <div className="flex items-center space-x-3">
                  <Checkbox
                    id="group-by-client"
                    checked={groupByClient}
                    onCheckedChange={(checked) => setGroupByClient(checked as boolean)}
                  />
                  <Label htmlFor="group-by-client" className="text-sm font-normal cursor-pointer">
                    Regrouper par client
                  </Label>
                </div>

                <div className="flex items-center space-x-3">
                  <Checkbox
                    id="group-by-type"
                    checked={groupByType}
                    onCheckedChange={(checked) => setGroupByType(checked as boolean)}
                  />
                  <Label htmlFor="group-by-type" className="text-sm font-normal cursor-pointer">
                    Regrouper par type de déclaration
                  </Label>
                </div>
              </div>
            </div>

            {/* Notes */}
            <div className="space-y-2">
              <Label htmlFor="report-notes">Notes du rapport (optionnel)</Label>
              <Textarea
                id="report-notes"
                placeholder="Ajouter des notes ou commentaires pour ce rapport..."
                value={reportNotes}
                onChange={(e) => setReportNotes(e.target.value)}
                rows={3}
              />
            </div>
          </div>
        </ScrollArea>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
            Annuler
          </Button>
          <Button onClick={handleGenerate} disabled={!isValid || loading}>
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            <Download className="mr-2 h-4 w-4" />
            Générer le rapport
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
