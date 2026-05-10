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
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { AlertCircle, AlertTriangle, Loader2, FileText } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface Declaration {
  id: string;
  declaration_number: string;
  declaration_type: string;
  company_name?: string;
  status: string;
  fiscal_period?: string;
  calculated_tax?: number;
}

interface BatchSubmitDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  declarations: Declaration[];
  onSubmit: (data: BatchSubmitRequest) => Promise<void>;
}

interface BatchSubmitRequest {
  declaration_ids: string[];
  validate_before_submit: boolean;
  skip_invalid: boolean;
  send_notifications: boolean;
  processor_notes?: string;
}

export function BatchSubmitDialog({
  open,
  onOpenChange,
  declarations,
  onSubmit,
}: BatchSubmitDialogProps) {
  const [loading, setLoading] = useState(false);
  const [validateBeforeSubmit, setValidateBeforeSubmit] = useState(true);
  const [skipInvalid, setSkipInvalid] = useState(false);
  const [sendNotifications, setSendNotifications] = useState(true);
  const [processorNotes, setProcessorNotes] = useState('');

  // Filter only DRAFT declarations
  const draftDeclarations = declarations.filter((d) => d.status === 'draft');
  const nonDraftCount = declarations.length - draftDeclarations.length;

  const totalTax = draftDeclarations.reduce(
    (sum, d) => sum + (d.calculated_tax || 0),
    0
  );

  const handleSubmit = async () => {
    if (draftDeclarations.length === 0) {
      return;
    }

    setLoading(true);
    try {
      const request: BatchSubmitRequest = {
        declaration_ids: draftDeclarations.map((d) => d.id),
        validate_before_submit: validateBeforeSubmit,
        skip_invalid: skipInvalid,
        send_notifications: sendNotifications,
        processor_notes: processorNotes || undefined,
      };

      await onSubmit(request);
      onOpenChange(false);

      // Reset form
      setProcessorNotes('');
    } catch (error) {
      console.error('Error submitting batch:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Soumettre des déclarations en lot</DialogTitle>
          <DialogDescription>
            Soumettre plusieurs déclarations à la fois pour traitement
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="flex-1 pr-4">
          <div className="space-y-6 py-4">
            {/* Warnings */}
            {nonDraftCount > 0 && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Attention</AlertTitle>
                <AlertDescription>
                  {nonDraftCount} déclaration{nonDraftCount > 1 ? 's' : ''} ne{' '}
                  {nonDraftCount > 1 ? 'sont' : 'peut'} pas être soumise
                  {nonDraftCount > 1 ? 's' : ''} car {nonDraftCount > 1 ? 'elles ne sont' : 'elle n\'est'} pas
                  en état BROUILLON. {nonDraftCount > 1 ? 'Elles' : 'Elle'} sera{nonDraftCount > 1 ? 'ont' : ''} ignorée
                  {nonDraftCount > 1 ? 's' : ''}.
                </AlertDescription>
              </Alert>
            )}

            {draftDeclarations.length === 0 && (
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  Aucune déclaration en état BROUILLON sélectionnée.
                </AlertDescription>
              </Alert>
            )}

            {/* Summary */}
            {draftDeclarations.length > 0 && (
              <div className="space-y-4 border rounded-lg p-4 bg-muted/50">
                <h3 className="font-semibold text-sm">Résumé</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Déclarations à soumettre</p>
                    <p className="text-2xl font-bold">{draftDeclarations.length}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Total des impôts</p>
                    <p className="text-2xl font-bold">
                      {totalTax.toLocaleString('fr-FR', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}{' '}
                      XAF
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Declarations List */}
            {draftDeclarations.length > 0 && (
              <div className="space-y-4 border rounded-lg p-4">
                <h3 className="font-semibold text-sm">
                  Déclarations ({draftDeclarations.length})
                </h3>

                <ScrollArea className="h-[250px] border rounded-md">
                  <div className="p-4 space-y-3">
                    {draftDeclarations.map((declaration) => (
                      <div
                        key={declaration.id}
                        className="flex items-start space-x-3 p-3 bg-card border rounded-md"
                      >
                        <FileText className="h-5 w-5 text-muted-foreground mt-0.5" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <p className="text-sm font-medium truncate">
                              {declaration.declaration_number}
                            </p>
                            <Badge variant="outline" className="ml-2">
                              {declaration.declaration_type}
                            </Badge>
                          </div>
                          {declaration.company_name && (
                            <p className="text-xs text-muted-foreground mt-1">
                              {declaration.company_name}
                            </p>
                          )}
                          <div className="flex items-center justify-between mt-2">
                            <p className="text-xs text-muted-foreground">
                              {declaration.fiscal_period}
                            </p>
                            {declaration.calculated_tax && (
                              <p className="text-sm font-semibold">
                                {declaration.calculated_tax.toLocaleString('fr-FR', {
                                  minimumFractionDigits: 2,
                                })} XAF
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            )}

            {/* Options */}
            {draftDeclarations.length > 0 && (
              <div className="space-y-4 border rounded-lg p-4">
                <h3 className="font-semibold text-sm">Options de soumission</h3>

                <div className="space-y-4">
                  <div className="flex items-start space-x-3">
                    <Checkbox
                      id="validate-before-submit"
                      checked={validateBeforeSubmit}
                      onCheckedChange={(checked) => setValidateBeforeSubmit(checked as boolean)}
                      className="mt-0.5"
                    />
                    <div className="flex-1">
                      <Label
                        htmlFor="validate-before-submit"
                        className="text-sm font-normal cursor-pointer"
                      >
                        Valider avant soumission
                      </Label>
                      <p className="text-xs text-muted-foreground mt-1">
                        Vérifier que toutes les déclarations sont complètes avant de les soumettre
                      </p>
                    </div>
                  </div>

                  {validateBeforeSubmit && (
                    <div className="flex items-start space-x-3 ml-6">
                      <Checkbox
                        id="skip-invalid"
                        checked={skipInvalid}
                        onCheckedChange={(checked) => setSkipInvalid(checked as boolean)}
                        className="mt-0.5"
                      />
                      <div className="flex-1">
                        <Label
                          htmlFor="skip-invalid"
                          className="text-sm font-normal cursor-pointer"
                        >
                          Ignorer les déclarations invalides
                        </Label>
                        <p className="text-xs text-muted-foreground mt-1">
                          Continuer même si certaines déclarations ne sont pas valides
                        </p>
                      </div>
                    </div>
                  )}

                  <div className="flex items-start space-x-3">
                    <Checkbox
                      id="send-notifications"
                      checked={sendNotifications}
                      onCheckedChange={(checked) => setSendNotifications(checked as boolean)}
                      className="mt-0.5"
                    />
                    <div className="flex-1">
                      <Label
                        htmlFor="send-notifications"
                        className="text-sm font-normal cursor-pointer"
                      >
                        Envoyer des notifications
                      </Label>
                      <p className="text-xs text-muted-foreground mt-1">
                        Notifier les clients que leurs déclarations ont été soumises
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Processor Notes */}
            {draftDeclarations.length > 0 && (
              <div className="space-y-2">
                <Label htmlFor="processor-notes">Notes du processeur (optionnel)</Label>
                <Textarea
                  id="processor-notes"
                  placeholder="Ajouter des notes pour toutes les soumissions..."
                  value={processorNotes}
                  onChange={(e) => setProcessorNotes(e.target.value)}
                  rows={3}
                />
              </div>
            )}
          </div>
        </ScrollArea>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
            Annuler
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={draftDeclarations.length === 0 || loading}
          >
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Soumettre {draftDeclarations.length} déclaration
            {draftDeclarations.length > 1 ? 's' : ''}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
