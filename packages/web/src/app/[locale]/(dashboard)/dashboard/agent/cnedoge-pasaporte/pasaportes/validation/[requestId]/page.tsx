'use client';

/**
 * Verification Detail Page for CNEDOGE Passport Agents
 * Split-view: Documents on left, Identifiers on right
 * Navigation between pending requests without returning to list
 */

import { useState, useCallback } from 'react';
import { useRouter, useParams, useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import {
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  FileText,
  Eye,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import {
  useVerificationDetails,
  useVerificationActions,
  VerificationStatusBadge,
  IdentifierCard,
  VerificationDialog,
} from '@/modules/verified-identifiers';
import type { ExtractedIdentifier, DocumentInfo } from '@/modules/verified-identifiers';

const ENTITY_CODE = 'CNEDOGE_PASAPORTE';

export default function VerificationDetailPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const t = useTranslations();

  const requestId = params.requestId as string;
  const entityCode = searchParams.get('entity') || ENTITY_CODE;

  // State for dialogs
  const [selectedIdentifier, setSelectedIdentifier] =
    useState<ExtractedIdentifier | null>(null);
  const [dialogMode, setDialogMode] = useState<
    'verify' | 'reject' | 'verify-batch' | null
  >(null);
  const [documentPreview, setDocumentPreview] = useState<DocumentInfo | null>(
    null
  );

  // Fetch verification details
  const { data, isLoading, isError, refetch, isFetching } =
    useVerificationDetails(requestId, entityCode);

  // Verification actions
  const {
    verify,
    verifyBatch,
    reject,
    isLoading: isActionLoading,
  } = useVerificationActions(requestId, {
    onVerifySuccess: (response) => {
      toast.success(
        response.allVerified
          ? 'Todos los identificadores verificados'
          : 'Identificador verificado correctamente'
      );
      refetch();
      setDialogMode(null);
      setSelectedIdentifier(null);
    },
    onVerifyBatchSuccess: (response) => {
      toast.success(
        `${response.verifiedCount} identificadores verificados correctamente`
      );
      refetch();
      setDialogMode(null);
    },
    onRejectSuccess: (response) => {
      toast.success(
        response.status === 'fraud'
          ? 'Identificador marcado como fraude'
          : 'Identificador rechazado'
      );
      refetch();
      setDialogMode(null);
      setSelectedIdentifier(null);
    },
    onError: (error) => {
      toast.error(`Error: ${error.message}`);
    },
  });

  // Navigation handlers
  const handleBack = () => {
    router.push('/dashboard/agent/cnedoge-pasaporte/pasaportes/validation');
  };

  const handlePrevious = useCallback(() => {
    if (data?.previousId) {
      router.push(
        `/dashboard/agent/cnedoge-pasaporte/pasaportes/validation/${data.previousId}?entity=${entityCode}`
      );
    }
  }, [data?.previousId, entityCode, router]);

  const handleNext = useCallback(() => {
    if (data?.nextId) {
      router.push(
        `/dashboard/agent/cnedoge-pasaporte/pasaportes/validation/${data.nextId}?entity=${entityCode}`
      );
    }
  }, [data?.nextId, entityCode, router]);

  // Action handlers
  const handleVerifyClick = (identifier: ExtractedIdentifier) => {
    setSelectedIdentifier(identifier);
    setDialogMode('verify');
  };

  const handleRejectClick = (identifier: ExtractedIdentifier) => {
    setSelectedIdentifier(identifier);
    setDialogMode('reject');
  };

  const handleVerifyAllClick = () => {
    setDialogMode('verify-batch');
  };

  const handleDialogConfirm = (dialogData: {
    notes?: string;
    isFraud?: boolean;
    reason?: string;
  }) => {
    if (dialogMode === 'verify' && selectedIdentifier) {
      verify({
        identifierType: selectedIdentifier.identifierType,
        identifierValue: selectedIdentifier.value,
        expiresAt: selectedIdentifier.expiresAt,
        notes: dialogData.notes,
      });
    } else if (dialogMode === 'verify-batch') {
      const pendingIdentifiers =
        data?.identifiers.filter((i) => i.status === 'pending') || [];
      verifyBatch({
        identifiers: pendingIdentifiers.map((i) => ({
          identifierType: i.identifierType,
          identifierValue: i.value,
          expiresAt: i.expiresAt,
        })),
        notes: dialogData.notes,
      });
    } else if (dialogMode === 'reject' && selectedIdentifier) {
      reject({
        identifierType: selectedIdentifier.identifierType,
        identifierValue: selectedIdentifier.value,
        reason: dialogData.reason || '',
        isFraud: dialogData.isFraud || false,
      });
    }
  };

  // Computed values
  const pendingIdentifiers =
    data?.identifiers.filter((i) => i.status === 'pending') || [];
  const verifiedIdentifiers =
    data?.identifiers.filter(
      (i) => i.status === 'verified' || i.status === 'verified_manually'
    ) || [];
  const rejectedIdentifiers =
    data?.identifiers.filter(
      (i) => i.status === 'rejected' || i.status === 'fraud'
    ) || [];

  if (isLoading) {
    return (
      <div className="container mx-auto py-6 space-y-6">
        <Skeleton className="h-12 w-full" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-96 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="container mx-auto py-6">
        <Card>
          <CardContent className="py-12 text-center">
            <AlertCircle className="h-12 w-12 mx-auto text-red-500 mb-4" />
            <p className="text-lg font-medium">Error al cargar la solicitud</p>
            <Button variant="outline" className="mt-4" onClick={handleBack}>
              Volver a la lista
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Header with navigation */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={handleBack}>
            <ChevronLeft className="h-5 w-5" />
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">{data.reference}</h1>
              <VerificationStatusBadge status={data.verificationStatus} />
            </div>
            <p className="text-muted-foreground">
              {data.citizenName} - {data.workflowCode}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            disabled={!data.previousId || isFetching}
            onClick={handlePrevious}
            title={t('verification.previousRequest', {
              defaultValue: 'Solicitud anterior',
            })}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            disabled={!data.nextId || isFetching}
            onClick={handleNext}
            title={t('verification.nextRequest', {
              defaultValue: 'Siguiente solicitud',
            })}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw
              className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`}
            />
          </Button>
        </div>
      </div>

      {/* Request info summary */}
      <Card>
        <CardContent className="py-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Tipo de solicitud</p>
              <p className="font-medium">{data.solicitudType || '-'}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Estado</p>
              <p className="font-medium">{data.status}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Fecha de envío</p>
              <p className="font-medium">
                {data.submittedAt
                  ? new Date(data.submittedAt).toLocaleDateString('es-ES')
                  : '-'}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground">Email</p>
              <p className="font-medium">{data.citizenEmail || '-'}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Split view: Documents | Identifiers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Documents */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Documentos ({data.documents.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.documents.length === 0 ? (
              <p className="text-muted-foreground text-center py-8">
                No hay documentos
              </p>
            ) : (
              data.documents.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{doc.documentName}</p>
                    <p className="text-sm text-muted-foreground truncate">
                      {doc.fileName}
                    </p>
                    {doc.extractionConfidence !== null && (
                      <Badge variant="outline" className="mt-1 text-xs">
                        {Math.round(doc.extractionConfidence * 100)}% confianza
                      </Badge>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setDocumentPreview(doc)}
                  >
                    <Eye className="h-4 w-4 mr-1" />
                    Ver
                  </Button>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Right: Identifiers */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5" />
              Identificadores ({data.identifiers.length})
            </CardTitle>
            {pendingIdentifiers.length > 0 && (
              <Button
                size="sm"
                className="bg-green-600 hover:bg-green-700"
                onClick={handleVerifyAllClick}
                disabled={isActionLoading}
              >
                Validar todos ({pendingIdentifiers.length})
              </Button>
            )}
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Pending identifiers */}
            {pendingIdentifiers.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-medium text-yellow-600 flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-yellow-500" />
                  Pendientes ({pendingIdentifiers.length})
                </h3>
                {pendingIdentifiers.map((identifier, idx) => (
                  <IdentifierCard
                    key={`pending-${idx}`}
                    identifier={identifier}
                    onVerify={() => handleVerifyClick(identifier)}
                    onReject={() => handleRejectClick(identifier)}
                    isLoading={isActionLoading}
                  />
                ))}
              </div>
            )}

            {/* Verified identifiers */}
            {verifiedIdentifiers.length > 0 && (
              <>
                {pendingIdentifiers.length > 0 && <Separator />}
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-green-600 flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-green-500" />
                    Verificados ({verifiedIdentifiers.length})
                  </h3>
                  {verifiedIdentifiers.map((identifier, idx) => (
                    <IdentifierCard
                      key={`verified-${idx}`}
                      identifier={identifier}
                    />
                  ))}
                </div>
              </>
            )}

            {/* Rejected identifiers */}
            {rejectedIdentifiers.length > 0 && (
              <>
                <Separator />
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-red-600 flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-red-500" />
                    Rechazados ({rejectedIdentifiers.length})
                  </h3>
                  {rejectedIdentifiers.map((identifier, idx) => (
                    <IdentifierCard
                      key={`rejected-${idx}`}
                      identifier={identifier}
                    />
                  ))}
                </div>
              </>
            )}

            {/* Empty state */}
            {data.identifiers.length === 0 && (
              <p className="text-muted-foreground text-center py-8">
                No se encontraron identificadores en los documentos
              </p>
            )}

            {/* All verified message */}
            {pendingIdentifiers.length === 0 &&
              verifiedIdentifiers.length > 0 && (
                <div className="text-center py-4 bg-green-50 rounded-lg border border-green-200">
                  <CheckCircle className="h-8 w-8 mx-auto text-green-600 mb-2" />
                  <p className="font-medium text-green-800">
                    {t('verification.allVerified', {
                      defaultValue: 'Todos los identificadores están verificados',
                    })}
                  </p>
                </div>
              )}
          </CardContent>
        </Card>
      </div>

      {/* Verification Dialog */}
      <VerificationDialog
        open={dialogMode !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDialogMode(null);
            setSelectedIdentifier(null);
          }
        }}
        mode={dialogMode || 'verify'}
        identifier={selectedIdentifier || undefined}
        identifiers={
          dialogMode === 'verify-batch' ? pendingIdentifiers : undefined
        }
        onConfirm={handleDialogConfirm}
        isLoading={isActionLoading}
      />

      {/* Document Preview Dialog */}
      <Dialog
        open={documentPreview !== null}
        onOpenChange={(open) => !open && setDocumentPreview(null)}
      >
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{documentPreview?.documentName}</DialogTitle>
          </DialogHeader>
          {documentPreview && (
            <div className="space-y-4">
              {/* Document preview (iframe or image) */}
              <div className="border rounded-lg overflow-hidden bg-muted min-h-[400px] flex items-center justify-center">
                {!documentPreview.fileUrl ? (
                  <div className="text-center py-12">
                    <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                    <p className="text-muted-foreground">URL del documento no disponible</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {documentPreview.filePath}
                    </p>
                  </div>
                ) : documentPreview.mimeType?.startsWith('image/') ? (
                  <img
                    src={documentPreview.fileUrl}
                    alt={documentPreview.documentName}
                    className="max-w-full max-h-[500px] object-contain"
                  />
                ) : documentPreview.mimeType === 'application/pdf' ? (
                  <div className="text-center py-12">
                    <FileText className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
                    <p className="text-lg font-medium mb-2">Documento PDF</p>
                    <p className="text-muted-foreground mb-4">
                      Los PDFs se abren en una nueva pestaña para mejor visualización
                    </p>
                    <Button
                      onClick={() => window.open(documentPreview.fileUrl!, '_blank')}
                      className="gap-2"
                    >
                      <Eye className="h-4 w-4" />
                      Abrir PDF en nueva pestaña
                    </Button>
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                    <p>Vista previa no disponible</p>
                    <a
                      href={documentPreview.fileUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      Abrir documento
                    </a>
                  </div>
                )}
              </div>

              {/* Extraction data */}
              {documentPreview.extractionData &&
                Object.keys(documentPreview.extractionData).length > 0 && (
                  <div className="border rounded-lg p-4">
                    <h4 className="font-medium mb-3">Datos extraídos (OCR)</h4>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      {Object.entries(documentPreview.extractionData)
                        .filter(
                          ([, value]) =>
                            value !== null &&
                            value !== undefined &&
                            typeof value !== 'object'
                        )
                        .map(([key, value]) => (
                          <div key={key}>
                            <span className="text-muted-foreground">
                              {key.replace(/_/g, ' ')}:
                            </span>{' '}
                            <span className="font-medium">
                              {String(value)}
                            </span>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
