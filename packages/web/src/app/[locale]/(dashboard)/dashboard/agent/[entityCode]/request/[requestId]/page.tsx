/**
 * Generic Agent Request Detail Page
 *
 * Dynamic detail view for service requests with:
 * - Tab RESUMEN: Form data + document key data + checklist + agent actions
 * - Tab DOCUMENTOS: Document preview with validate/reject per document
 * - Tab HISTORIAL: Compact timeline of all actions on this request
 *
 * @module agent/[entityCode]/request/[requestId]
 */

'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import Image from 'next/image';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

// UI Components
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

// Icons
import {
  ArrowLeft,
  Loader2,
  FileText,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Eye,
  Calendar,
  Clock,
  MapPin,
  ClipboardCheck,
  FileImage,
  ThumbsUp,
  ThumbsDown,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  CreditCard,
  User,
  Tag,
  ShieldCheck,
  Mail,
  Phone,
  X,
  ArrowUpRight,
  MessageSquarePlus,
  History,
  UserPlus,
  Users,
  Scan,
  MessageSquare,
  RotateCcw,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

// API
import {
  agentRequestsApi,
  getDocumentDownloadUrlCached,
  validateDocument,
  rejectDocument,
  type ServiceRequestDetail,
  type FormDisplaySchema,
  type AgentChecklistItem,
} from '@/modules/agent-dashboard/services/agent-requests-api';
import { serviceRequestsApi } from '@/modules/service-requests/services/api';
import {
  HistoryActionType,
  getHistoryActionLabel,
  getHistoryActionColor,
  getStatusLabel,
} from '@/modules/service-requests/types';
import { useImageZoom } from '@/modules/agent-dashboard/hooks/useImageZoom';
// DocumentPreviewDialog used in splitview; DocumentosTab has inline split-view

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Get value from nested object using dot notation
 */
function getNestedValue(obj: Record<string, unknown>, path: string): unknown {
  return path.split('.').reduce((acc, part) => {
    if (acc && typeof acc === 'object') {
      return (acc as Record<string, unknown>)[part];
    }
    return undefined;
  }, obj as unknown);
}

/**
 * Format value based on field type
 */
function formatFieldValue(
  value: unknown,
  type: string,
  defaultValue?: string
): string {
  if (value === undefined || value === null || value === '') {
    return defaultValue || '-';
  }

  switch (type) {
    case 'date':
      try {
        return new Date(String(value)).toLocaleDateString('es-ES');
      } catch {
        return String(value);
      }
    case 'datetime':
      try {
        return new Date(String(value)).toLocaleString('es-ES');
      } catch {
        return String(value);
      }
    case 'status':
      return String(value).toUpperCase();
    default:
      return String(value);
  }
}

/**
 * Get status badge variant
 */
function getStatusBadgeVariant(
  status: string
): 'default' | 'secondary' | 'destructive' | 'outline' {
  const statusUpper = status.toUpperCase();
  if (
    statusUpper.includes('COMPLETED') ||
    statusUpper.includes('APPROVED') ||
    statusUpper.includes('VERIFIED')
  ) {
    return 'default';
  }
  if (statusUpper.includes('REJECTED') || statusUpper.includes('FAILED')) {
    return 'destructive';
  }
  if (statusUpper.includes('PENDING') || statusUpper.includes('DRAFT')) {
    return 'secondary';
  }
  return 'outline';
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function AgentRequestDetailPage() {
  const params = useParams();
  const router = useRouter();
  const t = useTranslations('agent.requestDetail');
  const queryClient = useQueryClient();

  const requestId = params.requestId as string;
  const entitySlug = (params.entityCode as string) || '';
  const locale = useLocale();

  // State
  const [activeTab, setActiveTab] = useState('resumen');
  const [checklist, setChecklist] = useState<Record<string, boolean>>({});
  const [checklistNotes, setChecklistNotes] = useState('');
  // hasChecklistChanges removed — actions use inline callbacks
  // Document preview is now inline in DocumentosTab (split-view layout)

  // Navigation state - loaded from sessionStorage
  const [requestIds, setRequestIds] = useState<string[]>([]);

  // Load request IDs from sessionStorage on mount
  useEffect(() => {
    const storedIds = sessionStorage.getItem('agent-request-ids');
    if (storedIds) {
      try {
        setRequestIds(JSON.parse(storedIds));
      } catch {
        // Ignore parse errors
      }
    }
  }, []);

  // Navigation helpers
  const currentIndex = requestIds.indexOf(requestId);
  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex >= 0 && currentIndex < requestIds.length - 1;

  const navigateTo = useCallback((targetId: string) => {
    const basePath = `/${locale}/dashboard/agent/${entitySlug}/request/${targetId}`;
    router.push(basePath);
  }, [router, locale, entitySlug]);

  const goToPrev = useCallback(() => {
    if (hasPrev) {
      navigateTo(requestIds[currentIndex - 1]);
    }
  }, [hasPrev, requestIds, currentIndex, navigateTo]);

  const goToNext = useCallback(() => {
    if (hasNext) {
      navigateTo(requestIds[currentIndex + 1]);
    }
  }, [hasNext, requestIds, currentIndex, navigateTo]);

  // Fetch request detail
  const {
    data: request,
    isLoading: isLoadingRequest,
    error: requestError,
  } = useQuery({
    queryKey: ['agent-request-detail', requestId],
    queryFn: () => agentRequestsApi.getRequestDetail(requestId),
    enabled: !!requestId,
  });

  // Fetch workflow schema
  const { data: workflowSchema, isLoading: isLoadingSchema } = useQuery({
    queryKey: ['workflow-schema', request?.workflowCode],
    queryFn: () => agentRequestsApi.getWorkflowSchema(request!.workflowCode),
    enabled: !!request?.workflowCode,
  });

  // Initialize checklist from request data
  useEffect(() => {
    if (request?.verificationDetails?.checklist) {
      setChecklist(request.verificationDetails.checklist);
    } else if (workflowSchema?.agentChecklist) {
      // Initialize with all items unchecked
      const initial: Record<string, boolean> = {};
      workflowSchema.agentChecklist.forEach((item) => {
        initial[item.id] = false;
      });
      setChecklist(initial);
    }
    if (request?.verificationDetails?.notes) {
      setChecklistNotes(request.verificationDetails.notes);
    }
  }, [request, workflowSchema]);

  // Update verification mutation
  const updateVerificationMutation = useMutation({
    mutationFn: (data: { checklist: Record<string, boolean>; notes?: string }) =>
      agentRequestsApi.updateVerification(requestId, {
        checklist: data.checklist,
        notes: data.notes,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-request-detail', requestId] });
    },
  });

  // Decision mutation (approve, reject, request_documents)
  const decisionMutation = useMutation({
    mutationFn: (data: {
      decision: 'approve' | 'reject' | 'request_documents';
      comments?: string;
      rejectionReason?: string;
      requestedDocuments?: string[];
    }) =>
      agentRequestsApi.makeDecision(requestId, data.decision, {
        comments: data.comments,
        rejectionReason: data.rejectionReason,
        requestedDocuments: data.requestedDocuments,
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['agent-request-detail', requestId] });
      const messages: Record<string, string> = {
        approve: 'Solicitud aprobada exitosamente',
        reject: 'Solicitud rechazada',
        request_documents: 'Documentos adicionales solicitados',
      };
      toast.success(messages[variables.decision] || 'Decisión registrada');
      router.back();
    },
    onError: (error: Error & { response?: { data?: { detail?: string } } }) => {
      toast.error(error.response?.data?.detail || error.message || 'Error al procesar la decisión');
    },
  });

  // Escalation mutation
  const escalationMutation = useMutation({
    mutationFn: (data: { reason: string; priorityBoost?: number }) =>
      agentRequestsApi.escalate(requestId, data.reason, data.priorityBoost),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-request-detail', requestId] });
      toast.success('Solicitud escalada al supervisor');
      router.back();
    },
  });

  // Handle checklist change
  const handleChecklistChange = useCallback((itemId: string, checked: boolean) => {
    setChecklist((prev) => ({ ...prev, [itemId]: checked }));
  }, []);

  // Save checklist (used by action bar's onSaveNotes)
  // handleApprove, handleReject, handleEscalate are now inline in Tabs section

  // Loading state
  if (isLoadingRequest || isLoadingSchema) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Error state
  if (requestError) {
    return (
      <Card className="border-red-200 bg-red-50">
        <CardContent className="flex items-center gap-3 py-6">
          <AlertCircle className="h-6 w-6 text-red-500" />
          <div>
            <p className="font-medium text-red-700">
              {t('loadError') || 'Error al cargar la solicitud'}
            </p>
            <p className="text-sm text-red-600">
              {requestError instanceof Error ? requestError.message : 'Error desconocido'}
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!request) {
    return null;
  }

  const formDisplaySchema = workflowSchema?.formDisplaySchema;
  const agentChecklistItems = workflowSchema?.agentChecklist || [];

  // Get photo URL if defined in schema
  const photoUrl = formDisplaySchema?.photoField
    ? (getNestedValue(request.formData, formDisplaySchema.photoField) as string)
    : null;

  return (
    <div className="space-y-6">
      {/* Header with Navigation */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.back()}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{request.reference}</h1>
          <p className="text-muted-foreground">
            {workflowSchema?.name || request.workflowCode}
          </p>
        </div>
        <Badge variant={getStatusBadgeVariant(request.status)}>{request.status}</Badge>

        {/* Navigation Prev/Next */}
        {requestIds.length > 0 && (
          <div className="flex items-center gap-1 ml-4 border-l pl-4">
            <Button
              variant="outline"
              size="icon"
              onClick={goToPrev}
              disabled={!hasPrev}
              title={t('previousRequest') || 'Solicitud anterior'}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm text-muted-foreground px-2">
              {currentIndex + 1} / {requestIds.length}
            </span>
            <Button
              variant="outline"
              size="icon"
              onClick={goToNext}
              disabled={!hasNext}
              title={t('nextRequest') || 'Solicitud siguiente'}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="resumen" className="gap-2">
            <FileText className="h-4 w-4" />
            {t('tabs.resumen') || 'Resumen'}
          </TabsTrigger>
          <TabsTrigger value="documentos" className="gap-2">
            <FileImage className="h-4 w-4" />
            {t('tabs.documentos') || 'Documentos'}
          </TabsTrigger>
          <TabsTrigger value="historial" className="gap-2">
            <History className="h-4 w-4" />
            Historial
          </TabsTrigger>
        </TabsList>

        {/* Tab RESUMEN — includes checklist + action bar */}
        <TabsContent value="resumen" className="mt-6">
          <ResumenTab
            request={request}
            formDisplaySchema={formDisplaySchema}
            photoUrl={photoUrl}
            checklistItems={agentChecklistItems}
            checklist={checklist}
            onChecklistChange={handleChecklistChange}
            canMakeDecision={request.status === 'SUBMITTED' || request.status === 'UNDER_REVIEW'}
            isDeciding={decisionMutation.isPending || escalationMutation.isPending}
            onApprove={() => {
              if (workflowSchema?.agentChecklist) {
                const allRequiredChecked = workflowSchema.agentChecklist
                  .filter((item) => item.required)
                  .every((item) => checklist[item.id]);
                if (!allRequiredChecked) {
                  toast.error('Complete todos los items requeridos de la verificación.');
                  return;
                }
              }
              decisionMutation.mutate({ decision: 'approve', comments: checklistNotes });
            }}
            onReject={(reason, comments) => {
              decisionMutation.mutate({ decision: 'reject', rejectionReason: reason, comments });
            }}
            onEscalate={(reason) => {
              escalationMutation.mutate({ reason });
            }}
            onRequestDocuments={(docCodes, comments) => {
              decisionMutation.mutate({ decision: 'request_documents', requestedDocuments: docCodes, comments });
            }}
            onBatchValidateDocs={async () => {
              const pendingDocs = (request.providedDocuments || []).filter(
                (d) => d.validationStatus !== 'validated' && d.validationStatus !== 'rejected'
              );
              if (pendingDocs.length === 0) return;
              try {
                await Promise.all(pendingDocs.map((d) => validateDocument(d.id)));
                toast.success(`${pendingDocs.length} documentos validados`);
                queryClient.invalidateQueries({ queryKey: ['agent-request-detail', requestId] });
              } catch (err) {
                toast.error('Error al validar documentos: ' + (err instanceof Error ? err.message : 'Error'));
              }
            }}
            onSaveNotes={(notes) => {
              setChecklistNotes(notes);
              updateVerificationMutation.mutate({ checklist, notes });
            }}
          />
        </TabsContent>

        {/* Tab DOCUMENTOS */}
        <TabsContent value="documentos" className="mt-6">
          <DocumentosTab
            requestId={requestId}
            documents={request.providedDocuments || []}
            onDocumentStatusChanged={() => {
              queryClient.invalidateQueries({ queryKey: ['agent-request-detail', requestId] });
            }}
          />
        </TabsContent>

        {/* Tab HISTORIAL — timeline of actions on this request */}
        <TabsContent value="historial" className="mt-6">
          <HistorialTab requestId={requestId} />
        </TabsContent>
      </Tabs>

      {/* Document preview is now inline in DocumentosTab (split-view) */}

    </div>
  );
}

// ============================================================================
// SUB-COMPONENTS
// ============================================================================

// ============================================================================
// DYNAMIC FORM DATA HELPERS
// ============================================================================

/** Duplicate fields to avoid showing the same value multiple times */
const DEDUP_FIELDS = new Set([
  'solicitud_type', 'tipo_solicitud', 'solicitud_sub_type',
]);

/** Photo-related fields — displayed as image, not text */
const PHOTO_FIELDS = new Set([
  'photo_url', 'foto_url', 'photo', 'photo_carnet',
]);

/** Fields that identify the applicant — shown in the identity card */
const IDENTITY_FIELDS = new Set([
  'nombres', 'apellidos', 'numero_dip', 'numero_identificacion',
  'tipo_identificacion', 'sexo', 'fecha_nacimiento', 'nacionalidad',
  'numero_nie',
]);

/** Request metadata fields — shown in a compact header card */
const REQUEST_META_FIELDS = new Set([
  'sub_type', 'motivo', 'is_minor', 'applicant_type', 'persona_type',
  'select_classes', 'clases_solicitadas', 'tipo_contrato',
]);

// ============================================================================
// DECISION FIELDS — Business-critical OCR fields per document type
// Only these fields are shown in the "Datos Clave de Documentos" card.
// Agent can see ALL fields in the Documentos tab.
// ============================================================================

type FieldDef = {
  key: string;
  altKeys?: string[];
  label: string;
  type: 'text' | 'date' | 'result' | 'boolean' | 'id';
  resultMap?: Record<string, 'ok' | 'warning' | 'error'>;
};

const DECISION_FIELDS: Record<string, FieldDef[]> = {
  // --- Identity documents ---
  pasaporte: [
    { key: 'apellidos', label: 'Apellidos', type: 'text' },
    { key: 'nombres', label: 'Nombres', type: 'text' },
    { key: 'nacionalidad', label: 'Nacionalidad', type: 'text' },
    { key: 'fecha_nacimiento', label: 'Fecha Nac.', type: 'date' },
    { key: 'fecha_expiracion', label: 'Vigencia', type: 'date' },
    { key: 'numero_pasaporte', label: 'N\u00b0 Pasaporte', type: 'id' },
  ],
  pasaporte_antiguo: [
    { key: 'apellidos', label: 'Apellidos', type: 'text' },
    { key: 'nombres', label: 'Nombres', type: 'text' },
    { key: 'fecha_expiracion', label: 'Vigencia', type: 'date' },
    { key: 'numero_pasaporte', label: 'N\u00b0 Pasaporte', type: 'id' },
  ],
  dip: [
    { key: 'apellidos', label: 'Apellidos', type: 'text' },
    { key: 'nombres', label: 'Nombres', type: 'text' },
    { key: 'fecha_nacimiento', label: 'Fecha Nac.', type: 'date' },
    { key: 'fecha_expiracion', label: 'Vigencia', type: 'date' },
    { key: 'numero_dip', label: 'N\u00b0 DIP', type: 'id' },
    { key: 'natural_de', label: 'Natural de', type: 'text' },
  ],
  // --- Residencia documents ---
  sello_entrada: [
    { key: 'fecha', altKeys: ['fecha_entrada'], label: 'Fecha entrada', type: 'date' },
    { key: 'puesto_fronterizo', label: 'Puesto', type: 'text' },
  ],
  visado_entrada: [
    { key: 'tipo_visado', label: 'Tipo visado', type: 'text' },
    { key: 'fecha_expedicion', label: 'Expedido', type: 'date' },
    { key: 'fecha_expiracion', label: 'Vigencia', type: 'date' },
    { key: 'sobre_pasaporte', altKeys: ['numero_pasaporte'], label: 'N\u00b0 Pasaporte', type: 'id' },
  ],
  antecedentes_penales: [
    { key: 'resultado', label: 'Resultado', type: 'result',
      resultMap: { NEGATIVO: 'ok', POSITIVO: 'error', HAS_CONVICTIONS: 'error' } },
    { key: 'numero_timbre_fiscal', label: 'N\u00b0 Timbre', type: 'id' },
    { key: 'fecha_expedicion', label: 'Fecha exp.', type: 'date' },
  ],
  extrait_casier_judiciaire: [
    { key: 'resultado', label: 'Resultado', type: 'result',
      resultMap: { CLEAN: 'ok', HAS_CONVICTIONS: 'error' } },
    { key: 'numero_reference', label: 'N\u00b0 Ref.', type: 'id' },
    { key: 'fecha_expedicion', label: 'Fecha exp.', type: 'date' },
    { key: 'pays_emission', label: 'Pa\u00eds', type: 'text' },
  ],
  solvencia_tributaria: [
    { key: 'resultado', label: 'Resultado', type: 'result',
      resultMap: { SOLVENTE: 'ok', NO_SOLVENTE: 'warning' } },
    { key: 'nif', altKeys: ['empresa_nif'], label: 'NIF empresa', type: 'id' },
    { key: 'fecha_expedicion', label: 'Fecha exp.', type: 'date' },
    { key: 'numero_certificado', label: 'N\u00b0 Cert.', type: 'id' },
  ],
  certificado_buena_conducta: [
    { key: 'resultado', label: 'Resultado', type: 'result',
      resultMap: { FAVORABLE: 'ok', DESFAVORABLE: 'error' } },
    { key: 'fecha_expedicion', label: 'Fecha exp.', type: 'date' },
    { key: 'numero_certificado', label: 'N\u00b0 Cert.', type: 'id' },
    { key: 'municipio', label: 'Municipio', type: 'text' },
  ],
  certificado_medico: [
    { key: 'resultado', label: 'Resultado', type: 'result',
      resultMap: { APTO: 'ok', SANO: 'ok', 'NO APTO': 'error', ENFERMO: 'error' } },
    { key: 'fecha_certificado', altKeys: ['fecha_expedicion'], label: 'Fecha cert.', type: 'date' },
    { key: 'nombre_centro', label: 'Centro', type: 'text' },
    { key: 'nombre_medico', label: 'M\u00e9dico', type: 'text' },
  ],
  atestacion_bancaria: [
    { key: 'nombre_completo', label: 'Titular cuenta', type: 'text' },
    { key: 'nombre_banco', label: 'Banco', type: 'text' },
  ],
  permiso_residencia: [
    { key: 'apellidos', label: 'Apellidos', type: 'text' },
    { key: 'nombres', label: 'Nombres', type: 'text' },
    { key: 'fecha_expiracion', label: 'Vigencia', type: 'date' },
    { key: 'numero_registro', label: 'N\u00b0 Registro', type: 'id' },
    { key: 'nacionalidad', label: 'Nacionalidad', type: 'text' },
  ],
  // --- Contrato documents ---
  contrato_onrc: [
    { key: 'numero_contrato', label: 'N\u00b0 Contrato', type: 'id' },
    { key: 'descripcion', altKeys: ['objeto_contrato'], label: 'Objeto', type: 'text' },
    { key: 'fecha_firma', label: 'Fecha firma', type: 'date' },
    { key: 'monto_total', label: 'Monto', type: 'text' },
    { key: 'moneda', label: 'Moneda', type: 'text' },
    { key: 'duracion_meses', altKeys: ['duracion_texto'], label: 'Duraci\u00f3n', type: 'text' },
    { key: 'nif_contratista', label: 'NIF contratista', type: 'id' },
  ],
  escritura_constitucion: [
    { key: 'denominacion_social', label: 'Empresa', type: 'text' },
  ],
  certificado_nif: [
    { key: 'nif', altKeys: ['empresa_nif'], label: 'NIF', type: 'id' },
    { key: 'denominacion_social', label: 'Empresa', type: 'text' },
  ],
  // --- Vehicle documents ---
  permiso_circulacion: [
    { key: 'matricula', label: 'Matr\u00edcula', type: 'id' },
    { key: 'numero_bastidor', label: 'VIN/Bastidor', type: 'id' },
    { key: 'propietario', altKeys: ['nombre_completo'], label: 'Propietario', type: 'text' },
  ],
  cuve: [
    { key: 'matricula', label: 'Matr\u00edcula', type: 'id' },
    { key: 'numero_bastidor', label: 'VIN/Bastidor', type: 'id' },
    { key: 'numero_referencia', label: 'N\u00b0 Ref.', type: 'id' },
    { key: 'fecha_impresion', label: 'Fecha imp.', type: 'date' },
  ],
  contrato_compraventa: [
    { key: 'nombre_completo', label: 'Vendedor', type: 'text' },
    { key: 'dni_nie', label: 'DNI/NIE vendedor', type: 'id' },
    { key: 'fecha', label: 'Fecha contrato', type: 'date' },
    { key: 'matricula', label: 'Matr\u00edcula', type: 'id' },
    { key: 'numero_bastidor', label: 'VIN/Bastidor', type: 'id' },
  ],
  certificado_reconocimiento: [
    { key: 'cumple_condiciones_minimas', label: 'Condiciones', type: 'boolean' },
    { key: 'tiene_firma', label: 'Firma ingeniero', type: 'boolean' },
    { key: 'tiene_sello', label: 'Sello ITV', type: 'boolean' },
  ],
  // --- Conducir documents ---
  certificado_actual: [
    { key: 'clases_permiso', label: 'Clases actuales', type: 'text' },
    { key: 'reg_numero', label: 'N\u00b0 Registro', type: 'id' },
    { key: 'lugar_expedicion', label: 'Lugar exp.', type: 'text' },
    { key: 'valido_hasta', label: 'V\u00e1lido hasta', type: 'date' },
  ],
  // --- Funcion publica documents ---
  nombramiento: [
    { key: 'fecha_nombramiento', label: 'Fecha nombr.', type: 'date' },
  ],
  certificado_perdida: [
    { key: 'fecha_emision', label: 'Fecha emisi\u00f3n', type: 'date' },
  ],
  carnet_funcionario: [
    { key: 'categoria', label: 'Categor\u00eda actual', type: 'text' },
  ],
};

/** Get a decision field value from extraction data, trying altKeys */
function getDecisionValue(data: Record<string, unknown>, field: FieldDef): unknown {
  const val = data[field.key];
  if (val !== null && val !== undefined && val !== '') return val;
  if (field.altKeys) {
    for (const alt of field.altKeys) {
      const altVal = data[alt];
      if (altVal !== null && altVal !== undefined && altVal !== '') return altVal;
    }
  }
  return undefined;
}

/** Convert snake_case to Title Case (fallback when no i18n key exists) */
function snakeToTitle(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** ISO date pattern: YYYY-MM-DD or YYYY-MM-DDTHH:mm:ss */
const ISO_DATE_REGEX = /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?/;

/** Format a field value for display */
function formatDisplayValue(_key: string, value: unknown, locale = 'es'): string {
  if (value === null || value === undefined || value === '') return '-';

  // Arrays → comma-separated
  if (Array.isArray(value)) {
    return value.join(', ') || '-';
  }

  // Objects → skip (shouldn't happen with flat data)
  if (typeof value === 'object') return '-';

  const str = String(value);

  // Date detection by VALUE format (not by key name — avoids false positives like lugar_nacimiento)
  if (ISO_DATE_REGEX.test(str)) {
    try {
      const d = new Date(str);
      if (!isNaN(d.getTime())) {
        const localeMap: Record<string, string> = { es: 'es-ES', fr: 'fr-FR', en: 'en-GB' };
        return d.toLocaleDateString(localeMap[locale] || 'es-ES', {
          day: '2-digit', month: '2-digit', year: 'numeric',
        });
      }
    } catch { /* fall through */ }
  }

  return str;
}

/**
 * Tab RESUMEN - Display form data according to schema or dynamically
 */
// Action bar props shared between ResumenTab and DynamicFormDisplay
interface ActionBarProps {
  checklistItems: AgentChecklistItem[];
  checklist: Record<string, boolean>;
  onChecklistChange: (itemId: string, checked: boolean) => void;
  canMakeDecision: boolean;
  isDeciding: boolean;
  onApprove: () => void;
  onReject: (reason: string, comments?: string) => void;
  onEscalate: (reason: string) => void;
  onRequestDocuments: (docCodes: string[], comments?: string) => void;
  onBatchValidateDocs: () => Promise<void>;
  onSaveNotes: (notes: string) => void;
}

function ResumenTab({
  request,
  formDisplaySchema,
  photoUrl,
  ...actionProps
}: {
  request: ServiceRequestDetail;
  formDisplaySchema: FormDisplaySchema | null | undefined;
  photoUrl: string | null;
} & ActionBarProps) {
  const tDocs = useTranslations('agent.requestDetail.documentNames');
  const locale = useLocale();
  const qc = useQueryClient();

  if (!formDisplaySchema) {
    return <DynamicFormDisplay request={request} {...actionProps} />;
  }

  // Group sections by column
  const leftSections = formDisplaySchema.sections.filter((s) => s.column === 'left');
  const rightSections = formDisplaySchema.sections.filter((s) => s.column === 'right');

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">{formDisplaySchema.title}</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="space-y-4">
          {photoUrl && (
            <Card>
              <CardContent className="pt-6">
                <div className="flex justify-center">
                  <div className="w-32 h-40 relative border rounded overflow-hidden">
                    <Image src={photoUrl} alt="Photo" fill className="object-cover" unoptimized />
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
          {leftSections.map((section) => (
            <SectionCard key={section.id} section={section} request={request} />
          ))}
        </div>
        <div className="space-y-4">
          {rightSections.map((section) => (
            <SectionCard key={section.id} section={section} request={request} />
          ))}
        </div>
      </div>

      <AppointmentCard request={request} />

      {/* Document key data (also available in schema path) */}
      {request.providedDocuments && request.providedDocuments.length > 0 && (
        <DocumentKeyDataCard
          documents={request.providedDocuments}
          locale={locale}
          getDocLabel={(code, fallback) => getDocName(tDocs, code, fallback)}
          onValidateDoc={async (docId) => {
            await validateDocument(docId);
            toast.success('Documento validado');
            qc.invalidateQueries({ queryKey: ['agent-request-detail', request.id] });
          }}
          onRejectDoc={async (docId, reason) => {
            await rejectDocument(docId, reason);
            toast.success('Documento rechazado');
            qc.invalidateQueries({ queryKey: ['agent-request-detail', request.id] });
          }}
        />
      )}

      {/* Checklist + Action bar */}
      <ResumenActionBar
        documents={request.providedDocuments || []}
        paymentStatus={request.paymentWorkflowStatus}
        {...actionProps}
      />
    </div>
  );
}

/**
 * Dynamic form data display - used when formDisplaySchema is not configured
 */
function DynamicFormDisplay({ request, ...actionProps }: { request: ServiceRequestDetail } & ActionBarProps) {
  const t = useTranslations('agent.requestDetail');
  const tFields = useTranslations('agent.requestDetail.fieldLabels');
  const tDocs = useTranslations('agent.requestDetail.documentNames');
  const locale = useLocale();
  const queryClient = useQueryClient();
  const formData = request.formData || {};

  // Document preview state (split-view on desktop, dialog on mobile)
  const [previewDocCode, setPreviewDocCode] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewDocName, setPreviewDocName] = useState('');
  const [previewMime, setPreviewMime] = useState('');
  const [showMobilePreview, setShowMobilePreview] = useState(false);
  const { zoomLevel: inlineZoom, setZoomLevel: setInlineZoom, containerRef: inlineZoomRef, zoomIn: inlineZoomIn, zoomOut: inlineZoomOut, zoomReset: inlineZoomReset } = useImageZoom({ enabled: !!previewDocCode });

  const handleDocPreview = useCallback(async (docCode: string, docName: string, mimeType: string) => {
    if (previewDocCode === docCode) {
      // Toggle off if same doc
      setPreviewDocCode(null);
      setPreviewUrl(null);
      return;
    }
    setPreviewDocCode(docCode);
    setPreviewDocName(docName);
    setPreviewMime(mimeType);
    setPreviewUrl(null);
    setPreviewLoading(true);
    setInlineZoom(1);
    // Detect mobile via window width (lg breakpoint = 1024px)
    const isMobile = typeof window !== 'undefined' && window.innerWidth < 1024;
    if (isMobile) setShowMobilePreview(true);
    try {
      const url = await getDocumentDownloadUrlCached(request.id, docCode);
      setPreviewUrl(url);
    } catch (err) {
      console.error('Failed to load document preview:', err);
    } finally {
      setPreviewLoading(false);
    }
  }, [previewDocCode, request.id, setInlineZoom]);

  const closePreview = useCallback(() => {
    setPreviewDocCode(null);
    setPreviewUrl(null);
    setShowMobilePreview(false);
  }, []);

  // Resolve label: i18n key if exists, else snake_case → Title Case fallback
  const getLabel = (key: string): string => {
    try {
      // next-intl throws on missing key in strict mode
      return tFields(key as never);
    } catch {
      return snakeToTitle(key);
    }
  };

  // Show all filled fields, hide empty ones — handles workflow differences naturally
  // Only deduplicate fields that are stored redundantly (sub_type/solicitud_type/tipo_solicitud)
  const allEntries = Object.entries(formData).filter(
    ([key, value]) => !DEDUP_FIELDS.has(key) && value !== null && value !== undefined && value !== ''
  );

  const identityEntries = allEntries.filter(([key]) => IDENTITY_FIELDS.has(key));
  const metaEntries = allEntries.filter(([key]) => REQUEST_META_FIELDS.has(key));
  const otherEntries = allEntries.filter(([key]) =>
    !IDENTITY_FIELDS.has(key) && !REQUEST_META_FIELDS.has(key) && !PHOTO_FIELDS.has(key)
  );

  // Check for photo URL in form_data (flat keys + nested paths)
  const photoUrl = (() => {
    // 1. Flat keys
    const flatKey = Object.keys(formData).find((k) =>
      k === 'photo_url' || k === 'foto_url' || k === 'photo'
    );
    if (flatKey && formData[flatKey]) return String(formData[flatKey]);
    // 2. Nested: photo_carnet.url (common in passport/carnet workflows)
    const nested = getNestedValue(formData as Record<string, unknown>, 'photo_carnet.url');
    if (nested && typeof nested === 'string') return nested;
    // 3. Any key containing 'photo' with a URL-like value (strict: https:// or blob:)
    const photoLikeKey = Object.keys(formData).find((k) => {
      if (!k.toLowerCase().includes('photo') && !k.toLowerCase().includes('foto')) return false;
      const v = formData[k];
      return typeof v === 'string' && (v.startsWith('https://') || v.startsWith('blob:'));
    });
    if (photoLikeKey) return String(formData[photoLikeKey]);
    // 4. Nested object with url property
    const photoObj = formData['photo_carnet'];
    if (photoObj && typeof photoObj === 'object' && (photoObj as Record<string, unknown>).url) {
      return String((photoObj as Record<string, unknown>).url);
    }
    return null;
  })();

  const isPdf = (mime?: string) => mime === 'application/pdf' || mime?.endsWith('.pdf');
  const isImg = (mime?: string) => mime?.startsWith('image/');

  if (allEntries.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          {t('noData')}
        </CardContent>
      </Card>
    );
  }

  // ── Top cards: always full-width (meta, identity, pago+cita, complementary) ──
  const topCards = (
    <div className="space-y-4">
      {/* Request metadata — compact inline badges */}
      {metaEntries.length > 0 && (
        <Card className="bg-muted/30">
          <CardContent className="py-3">
            <div className="flex items-center gap-2 flex-wrap">
              <Tag className="h-4 w-4 text-muted-foreground" />
              {metaEntries.map(([key, value]) => (
                <Badge key={key} variant="outline" className="text-xs font-normal">
                  {getLabel(key)}: <span className="font-medium ml-1">{formatDisplayValue(key, value, locale)}</span>
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Identity Card — applicant core info + contact (merged) */}
      {(identityEntries.length > 0 || request.userName) && (
        <Card className="border-primary/20 bg-primary/[0.02]">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <User className="h-4 w-4 text-primary" />
              {t('applicantData')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-6">
              {photoUrl && (
                <div className="w-28 h-36 relative border rounded overflow-hidden flex-shrink-0">
                  <Image src={photoUrl} alt="Photo" fill className="object-cover" unoptimized />
                </div>
              )}
              <div className="flex-1 grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-1.5">
                {identityEntries.map(([key, value]) => (
                  <div key={key}>
                    <p className="text-xs text-muted-foreground">{getLabel(key)}</p>
                    <p className="text-sm font-medium" title={String(value)}>
                      {formatDisplayValue(key, value, locale)}
                    </p>
                  </div>
                ))}
                {request.userEmail && (
                  <div>
                    <p className="text-xs text-muted-foreground flex items-center gap-1"><Mail className="h-3 w-3" />{t('email')}</p>
                    <p className="text-sm font-medium truncate" title={request.userEmail}>{request.userEmail}</p>
                  </div>
                )}
                {request.userPhone && (
                  <div>
                    <p className="text-xs text-muted-foreground flex items-center gap-1"><Phone className="h-3 w-3" />{t('phone')}</p>
                    <p className="text-sm font-medium">{request.userPhone}</p>
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Payment + Appointment — flex-wrap inline full-width */}
      {(request.paymentAmount || request.citaDate || request.citaLocation) && (
        <Card>
          <CardContent className="py-3 space-y-1.5">
              {/* Line 1: Payment — monto, referencia, recibo, método, estado, fecha */}
              {request.paymentAmount && (
                <div className="flex items-center gap-4 flex-wrap">
                  <div className="flex items-center gap-1.5">
                    <CreditCard className="h-4 w-4 text-green-600 shrink-0" />
                    <span className="text-sm font-bold text-green-700">
                      {new Intl.NumberFormat(locale === 'fr' ? 'fr-FR' : 'es-ES').format(request.paymentAmount)} {request.paymentCurrency || 'XAF'}
                    </span>
                  </div>
                  {request.paymentReference && (
                    <span className="text-sm font-mono text-muted-foreground">{request.paymentReference}</span>
                  )}
                  {request.paymentReceiptNumber && (
                    <span className="text-sm font-mono text-muted-foreground">Recibo: {request.paymentReceiptNumber}</span>
                  )}
                  {request.paymentMethod && (
                    <span className="text-sm text-muted-foreground">{request.paymentMethod}</span>
                  )}
                  {request.paymentWorkflowStatus && (
                    <Badge variant={request.paymentWorkflowStatus === 'completed' ? 'default' : 'destructive'} className="text-xs">
                      {request.paymentWorkflowStatus}
                    </Badge>
                  )}
                  {request.paymentPaidAt && (
                    <span className="text-sm text-muted-foreground">{formatDisplayValue('', request.paymentPaidAt, locale)}</span>
                  )}
                </div>
              )}
              {/* Line 2: Appointment info */}
              {(request.citaDate || request.citaLocation) && (
                <div className="flex items-center gap-4 flex-wrap">
                  {request.citaDate && (
                    <div className="flex items-center gap-1.5">
                      <Calendar className="h-4 w-4 text-primary shrink-0" />
                      <span className="text-sm">{request.citaDate}</span>
                    </div>
                  )}
                  {request.citaTime && (
                    <div className="flex items-center gap-1.5">
                      <Clock className="h-4 w-4 text-muted-foreground shrink-0" />
                      <span className="text-sm">{request.citaTime}</span>
                    </div>
                  )}
                  {request.citaLocation && (
                    <div className="flex items-center gap-1.5">
                      <MapPin className="h-4 w-4 text-muted-foreground shrink-0" />
                      <span className="text-sm">{request.citaLocation}</span>
                    </div>
                  )}
                </div>
              )}
          </CardContent>
        </Card>
      )}

      {/* Complementary fields — personal details, address, etc */}
      {otherEntries.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <ClipboardCheck className="h-4 w-4 text-primary" />
              {t('complementaryInfo')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-6 gap-y-1.5">
              {otherEntries.map(([key, value]) => (
                <div key={key}>
                  <p className="text-xs text-muted-foreground">{getLabel(key)}</p>
                  <p className="text-sm font-medium" title={String(value)}>
                    {formatDisplayValue(key, value, locale)}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );

  // ── Document key data card (goes into split-view 30% on preview) ──
  const hasDocKeyData = request.providedDocuments && request.providedDocuments.length > 0;

  // Preview panel content (shared between desktop split-view and mobile dialog)
  const previewPanel = (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-3 py-2 border-b flex items-center justify-between shrink-0 bg-muted/30">
        <div className="flex items-center gap-2 min-w-0">
          <FileImage className="h-4 w-4 text-blue-500 shrink-0" />
          <span className="text-sm font-medium truncate">{previewDocName}</span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {previewUrl && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => window.open(previewUrl, '_blank')}
              title="Abrir en nueva pestaña"
            >
              <Eye className="h-3.5 w-3.5" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={closePreview}
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
      {/* Body */}
      <div className="flex-1 min-h-0 overflow-hidden bg-muted/10">
        {previewLoading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : previewUrl && isPdf(previewMime) ? (
          <iframe
            src={previewUrl}
            className="w-full h-full"
            title={previewDocName}
          />
        ) : previewUrl && isImg(previewMime) ? (
          <div className="relative h-full">
            {/* Zoom controls */}
            <div className="absolute top-2 right-2 z-10 flex items-center gap-1 bg-background/90 backdrop-blur-sm rounded-md border shadow-sm p-0.5">
              <Button variant="ghost" size="icon" className="h-6 w-6" onClick={inlineZoomOut}>
                <ZoomOut className="h-3 w-3" />
              </Button>
              <span className="text-[10px] font-mono w-8 text-center">{Math.round(inlineZoom * 100)}%</span>
              <Button variant="ghost" size="icon" className="h-6 w-6" onClick={inlineZoomIn}>
                <ZoomIn className="h-3 w-3" />
              </Button>
              <Button variant="ghost" size="icon" className="h-6 w-6" onClick={inlineZoomReset}>
                <RotateCcw className="h-2.5 w-2.5" />
              </Button>
            </div>
            <div
              ref={inlineZoomRef}
              className="flex items-center justify-center h-full p-4 overflow-auto"
            >
              <img
                src={previewUrl}
                alt={previewDocName}
                className="object-contain rounded shadow-sm transition-transform duration-150"
                style={{
                  transform: `scale(${inlineZoom})`,
                  transformOrigin: 'center center',
                  maxWidth: inlineZoom <= 1 ? '100%' : 'none',
                  maxHeight: inlineZoom <= 1 ? '100%' : 'none',
                }}
                draggable={false}
              />
            </div>
          </div>
        ) : previewUrl ? (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <FileText className="h-12 w-12 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Vista previa no disponible</p>
            <Button variant="outline" size="sm" onClick={() => window.open(previewUrl, '_blank')}>
              Descargar archivo
            </Button>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-muted-foreground">Error al cargar el documento</p>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Top cards — ALWAYS full-width, never affected by split-view */}
      {topCards}

      {/* Document key data section — split-view on desktop when preview active */}
      {hasDocKeyData && (
        <div className="mt-4">
          {/* Desktop split-view: 30% doc blocks + 70% preview */}
          {previewDocCode ? (
            <div className="hidden lg:flex gap-4 h-[calc(100vh-280px)] min-h-[400px]">
              {/* Left 30%: doc key data blocks (scrollable, 1 col) */}
              <div className="w-[30%] shrink-0 overflow-y-auto pr-1">
                <DocumentKeyDataCard
                  documents={request.providedDocuments!}
                  locale={locale}
                  getDocLabel={(code, fallback) => getDocName(tDocs, code, fallback)}
                  onDocPreview={handleDocPreview}
                  onValidateDoc={async (docId) => {
                    await validateDocument(docId);
                    toast.success('Documento validado');
                    queryClient.invalidateQueries({ queryKey: ['agent-request-detail', request.id] });
                  }}
                  onRejectDoc={async (docId, reason) => {
                    await rejectDocument(docId, reason);
                    toast.success('Documento rechazado');
                    queryClient.invalidateQueries({ queryKey: ['agent-request-detail', request.id] });
                  }}
                  activeDocCode={previewDocCode}
                  compact
                />
              </div>
              {/* Right 70%: document preview */}
              <Card className="flex-1 flex flex-col overflow-hidden">
                {previewPanel}
              </Card>
            </div>
          ) : null}

          {/* Normal full-width layout (no preview, or mobile) */}
          <div className={cn(previewDocCode && 'lg:hidden')}>
            <DocumentKeyDataCard
              documents={request.providedDocuments!}
              locale={locale}
              getDocLabel={(code, fallback) => getDocName(tDocs, code, fallback)}
              onDocPreview={handleDocPreview}
              onValidateDoc={async (docId) => {
                await validateDocument(docId);
                toast.success('Documento validado');
                queryClient.invalidateQueries({ queryKey: ['agent-request-detail', request.id] });
              }}
              onRejectDoc={async (docId, reason) => {
                await rejectDocument(docId, reason);
                toast.success('Documento rechazado');
                queryClient.invalidateQueries({ queryKey: ['agent-request-detail', request.id] });
              }}
              activeDocCode={previewDocCode}
            />
          </div>
        </div>
      )}

      {/* Mobile document preview dialog */}
      <Dialog open={showMobilePreview} onOpenChange={(open) => { if (!open) closePreview(); }}>
        <DialogContent className="max-w-[95vw] h-[85vh] p-0 flex flex-col">
          <DialogHeader className="sr-only">
            <DialogTitle>{previewDocName}</DialogTitle>
          </DialogHeader>
          {previewPanel}
        </DialogContent>
      </Dialog>

      {/* Checklist + Action bar */}
      <div className="mt-4">
        <ResumenActionBar
          documents={request.providedDocuments || []}
          paymentStatus={request.paymentWorkflowStatus}
          {...actionProps}
        />
      </div>
    </>
  );
}

// ============================================================================
// RESUMEN ACTION BAR — Checklist + Agent decision buttons
// ============================================================================

function ResumenActionBar({
  checklistItems,
  checklist,
  onChecklistChange,
  canMakeDecision,
  isDeciding,
  onApprove,
  onReject,
  onEscalate,
  onRequestDocuments,
  onBatchValidateDocs,
  onSaveNotes,
  documents,
  paymentStatus,
}: ActionBarProps & {
  documents: NonNullable<ServiceRequestDetail['providedDocuments']>;
  paymentStatus?: string | null;
}) {
  const [actionDialog, setActionDialog] = useState<'reject' | 'escalate' | 'request_docs' | 'note' | null>(null);
  const [dialogText, setDialogText] = useState('');
  const [isBatchValidating, setIsBatchValidating] = useState(false);

  // Auto-check logic
  const allDocsValidated = documents.length > 0 && documents.every(
    (d) => d.validationStatus === 'validated' || d.validationStatus === 'rejected'
  );
  const pendingDocsCount = documents.filter(
    (d) => d.validationStatus !== 'validated' && d.validationStatus !== 'rejected'
  ).length;
  const paymentCompleted = paymentStatus === 'completed';

  // Checklist with auto-check for known items
  const effectiveChecklist = { ...checklist };
  if (allDocsValidated && 'documents_verified' in effectiveChecklist) {
    effectiveChecklist['documents_verified'] = true;
  }
  if (paymentCompleted && 'payment_verified' in effectiveChecklist) {
    effectiveChecklist['payment_verified'] = true;
  }

  const requiredItems = checklistItems.filter((item) => item.required);
  const allRequiredChecked = requiredItems.every((item) => effectiveChecklist[item.id]);

  // Handle documents_verified checkbox → batch validate
  const handleChecklistItemChange = async (itemId: string, checked: boolean) => {
    if (itemId === 'documents_verified' && checked && pendingDocsCount > 0) {
      setIsBatchValidating(true);
      try {
        await onBatchValidateDocs();
      } finally {
        setIsBatchValidating(false);
      }
    }
    onChecklistChange(itemId, checked);
  };

  const handleDialogConfirm = () => {
    if (!dialogText.trim()) return;
    switch (actionDialog) {
      case 'reject':
        onReject(dialogText);
        break;
      case 'escalate':
        onEscalate(dialogText);
        break;
      case 'request_docs':
        onRequestDocuments([], dialogText);
        break;
      case 'note':
        onSaveNotes(dialogText);
        break;
    }
    setActionDialog(null);
    setDialogText('');
  };

  const dialogConfig: Record<string, { title: string; placeholder: string; minLength: number }> = {
    reject: { title: 'Motivo del rechazo', placeholder: 'Indique el motivo del rechazo...', minLength: 5 },
    escalate: { title: 'Motivo de la escalación', placeholder: 'Describa por qué escala esta solicitud...', minLength: 10 },
    request_docs: { title: 'Solicitar documentos', placeholder: 'Indique qué documentos necesita y por qué...', minLength: 5 },
    note: { title: 'Añadir nota', placeholder: 'Escriba una nota sobre esta solicitud...', minLength: 1 },
  };

  const currentConfig = actionDialog ? dialogConfig[actionDialog] : null;

  return (
    <>
      <Card className="border-t-2 border-t-primary/20">
        <CardContent className="py-3 space-y-3">
          {/* Checklist (if configured for this workflow) */}
          {checklistItems.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Verificación</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-1.5">
                {checklistItems.map((item) => {
                  const isAutoChecked =
                    (item.id === 'documents_verified' && allDocsValidated) ||
                    (item.id === 'payment_verified' && paymentCompleted);
                  const isChecked = effectiveChecklist[item.id] || false;

                  return (
                    <div key={item.id} className="flex items-center gap-2">
                      <Checkbox
                        id={`chk-${item.id}`}
                        checked={isChecked}
                        disabled={isAutoChecked || isBatchValidating}
                        onCheckedChange={(checked) => handleChecklistItemChange(item.id, checked as boolean)}
                      />
                      <Label
                        htmlFor={`chk-${item.id}`}
                        className={cn(
                          'text-xs cursor-pointer leading-tight',
                          isAutoChecked && 'text-green-700'
                        )}
                      >
                        {item.label}
                        {item.required && <span className="text-red-500 ml-0.5">*</span>}
                        {isAutoChecked && <span className="text-[10px] text-green-600 ml-1">(auto)</span>}
                        {item.id === 'documents_verified' && pendingDocsCount > 0 && !isAutoChecked && (
                          <span className="text-[10px] text-amber-600 ml-1">({pendingDocsCount} pendientes — se validarán al marcar)</span>
                        )}
                      </Label>
                      {isBatchValidating && item.id === 'documents_verified' && (
                        <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Action buttons */}
          {canMakeDecision && (
            <div className="flex items-center gap-2 flex-wrap pt-1">
              <Button
                size="sm"
                onClick={onApprove}
                disabled={isDeciding || (checklistItems.length > 0 && !allRequiredChecked)}
                className="bg-green-600 hover:bg-green-700"
              >
                {isDeciding ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <ThumbsUp className="h-4 w-4 mr-1" />}
                Aprobar
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => { setActionDialog('reject'); setDialogText(''); }}
                disabled={isDeciding}
              >
                <ThumbsDown className="h-4 w-4 mr-1" />
                Rechazar
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => { setActionDialog('escalate'); setDialogText(''); }}
                disabled={isDeciding}
              >
                <ArrowUpRight className="h-4 w-4 mr-1" />
                Escalar
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => { setActionDialog('request_docs'); setDialogText(''); }}
                disabled={isDeciding}
              >
                <FileText className="h-4 w-4 mr-1" />
                Solicitar Doc.
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => { setActionDialog('note'); setDialogText(''); }}
              >
                <MessageSquarePlus className="h-4 w-4 mr-1" />
                Nota
              </Button>

              {checklistItems.length > 0 && !allRequiredChecked && (
                <p className="text-[11px] text-amber-600 flex items-center gap-1 ml-auto">
                  <AlertTriangle className="h-3 w-3" />
                  Complete la verificación para aprobar
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Action dialog (reject/escalate/request_docs/note) */}
      <Dialog open={!!actionDialog} onOpenChange={(open) => { if (!open) { setActionDialog(null); setDialogText(''); } }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{currentConfig?.title}</DialogTitle>
          </DialogHeader>
          <Textarea
            value={dialogText}
            onChange={(e) => setDialogText(e.target.value)}
            placeholder={currentConfig?.placeholder}
            rows={4}
            autoFocus
          />
          <div className="flex justify-end gap-2 mt-2">
            <Button variant="outline" size="sm" onClick={() => { setActionDialog(null); setDialogText(''); }}>
              Cancelar
            </Button>
            <Button
              size="sm"
              variant={actionDialog === 'reject' ? 'destructive' : 'default'}
              onClick={handleDialogConfirm}
              disabled={dialogText.trim().length < (currentConfig?.minLength || 1) || isDeciding}
            >
              {isDeciding && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
              Confirmar
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

/**
 * Appointment info card (compact)
 */
function AppointmentCard({ request }: { request: ServiceRequestDetail }) {
  const t = useTranslations('agent.requestDetail');
  if (!request.citaDate && !request.citaLocation) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Calendar className="h-4 w-4 text-primary" />
          {t('appointment')}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-6 flex-wrap">
          {request.citaDate && (
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm">{request.citaDate}</span>
            </div>
          )}
          {request.citaTime && (
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm">{request.citaTime}</span>
            </div>
          )}
          {request.citaLocation && (
            <div className="flex items-center gap-2">
              <MapPin className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm">{request.citaLocation}</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/* ContactCard removed — contact info merged into Identity card */

/** Get document display name via i18n with fallback */
function getDocName(tDocs: (key: string) => string, code: string, fallbackName?: string): string {
  try {
    return tDocs(code as never);
  } catch {
    return fallbackName || snakeToTitle(code);
  }
}

/* DocumentExtractionSections removed — replaced by DocumentKeyDataCard */

// ============================================================================
// DOCUMENT KEY DATA CARD — Business-critical fields in a responsive grid
// ============================================================================

const RESULT_STYLES = {
  ok: 'bg-green-100 text-green-800',
  warning: 'bg-orange-100 text-orange-800',
  error: 'bg-red-100 text-red-800',
} as const;

function DocumentKeyDataCard({
  documents,
  locale,
  getDocLabel,
  onDocPreview,
  onValidateDoc,
  onRejectDoc,
  activeDocCode,
  compact = false,
}: {
  documents: NonNullable<ServiceRequestDetail['providedDocuments']>;
  locale: string;
  getDocLabel: (code: string, fallback?: string) => string;
  onDocPreview?: (docCode: string, docName: string, mimeType: string) => void;
  onValidateDoc?: (docId: string) => Promise<void>;
  onRejectDoc?: (docId: string, reason: string) => Promise<void>;
  activeDocCode?: string | null;
  compact?: boolean;
}) {
  // Local state for inline reject input per doc
  const [rejectingDocId, setRejectingDocId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [validatingDocId, setValidatingDocId] = useState<string | null>(null);
  const [rejectingLoading, setRejectingLoading] = useState(false);
  // Local status overrides after validate/reject
  const [statusOverrides, setStatusOverrides] = useState<Record<string, string>>({});

  // Filter documents that have extraction data AND decision fields configured
  const docsWithDecisionFields = documents.filter((doc) => {
    if (!doc.extractionData || Object.keys(doc.extractionData).length === 0) return false;
    if (doc.documentCode === 'photo_carnet') return false;
    const fields = DECISION_FIELDS[doc.documentCode];
    if (!fields) return false;
    // At least one field must have a value
    return fields.some((f) => getDecisionValue(doc.extractionData!, f) !== undefined);
  });

  const handleValidate = async (docId: string) => {
    if (!onValidateDoc) return;
    setValidatingDocId(docId);
    try {
      await onValidateDoc(docId);
      setStatusOverrides((prev) => ({ ...prev, [docId]: 'validated' }));
    } finally {
      setValidatingDocId(null);
    }
  };

  const handleRejectConfirm = async (docId: string) => {
    if (!onRejectDoc || rejectReason.length < 5) return;
    setRejectingLoading(true);
    try {
      await onRejectDoc(docId, rejectReason);
      setStatusOverrides((prev) => ({ ...prev, [docId]: 'rejected' }));
      setRejectingDocId(null);
      setRejectReason('');
    } finally {
      setRejectingLoading(false);
    }
  };

  if (docsWithDecisionFields.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-blue-600" />
          Datos Clave de Documentos
          <span className="text-xs font-normal text-muted-foreground ml-1">(extra\u00eddos)</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className={cn(
          'grid gap-3',
          compact
            ? 'grid-cols-1'
            : docsWithDecisionFields.length === 1
              ? 'grid-cols-1'
              : docsWithDecisionFields.length === 2
                ? 'grid-cols-1 sm:grid-cols-2'
                : docsWithDecisionFields.length <= 4
                  ? 'grid-cols-1 sm:grid-cols-2'
                  : 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3'
        )}>
          {docsWithDecisionFields.map((doc) => {
            const fields = DECISION_FIELDS[doc.documentCode]!;
            const docLabel = getDocLabel(doc.documentCode, doc.documentName);
            const isActive = activeDocCode === doc.documentCode;
            const effectiveStatus = statusOverrides[doc.id] || doc.validationStatus || 'pending';
            const isPending = effectiveStatus !== 'validated' && effectiveStatus !== 'rejected';

            return (
              <div
                key={doc.id}
                className={cn(
                  'border rounded-md p-2.5 bg-muted/30 space-y-1.5 transition-colors',
                  isActive && 'ring-2 ring-blue-400 bg-blue-50/50'
                )}
              >
                {/* Document name header + validation badge */}
                <div className="flex items-center justify-between gap-1">
                  <div className="flex items-center gap-1.5 min-w-0">
                    {effectiveStatus === 'validated' ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-green-600 shrink-0" />
                    ) : effectiveStatus === 'rejected' ? (
                      <XCircle className="h-3.5 w-3.5 text-red-500 shrink-0" />
                    ) : (
                      <AlertCircle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                    )}
                    <p className="text-xs font-semibold text-foreground truncate" title={docLabel}>
                      {docLabel}
                    </p>
                  </div>
                  <div className="flex items-center gap-0.5 shrink-0">
                    {doc.extractionConfidence != null && doc.extractionConfidence < 0.8 && (
                      <Badge variant="secondary" className="text-[9px] px-1">
                        {Math.round(doc.extractionConfidence * 100)}%
                      </Badge>
                    )}
                    {onDocPreview && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className={cn(
                          'h-5 w-5 rounded-sm',
                          isActive ? 'text-blue-600 bg-blue-100' : 'text-muted-foreground hover:text-blue-600'
                        )}
                        onClick={() => onDocPreview(doc.documentCode, docLabel, doc.mimeType || 'application/pdf')}
                        title="Ver documento"
                      >
                        <Eye className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                </div>
                {/* Decision fields */}
                {fields.map((field) => {
                  const value = getDecisionValue(doc.extractionData!, field);
                  if (value === undefined) return null;

                  return (
                    <div key={field.key} className="flex items-baseline gap-2">
                      <span className="text-[11px] text-muted-foreground shrink-0 whitespace-nowrap">{field.label}</span>
                      {field.type === 'result' && field.resultMap ? (
                        <Badge className={cn(
                          'text-[10px] px-1.5 py-0',
                          RESULT_STYLES[field.resultMap[String(value).toUpperCase()] || 'warning']
                        )}>
                          {String(value)}
                        </Badge>
                      ) : field.type === 'boolean' ? (
                        <span className="text-xs">
                          {value === true || value === 'true' ? (
                            <CheckCircle2 className="h-3.5 w-3.5 text-green-600 inline" />
                          ) : (
                            <XCircle className="h-3.5 w-3.5 text-red-500 inline" />
                          )}
                        </span>
                      ) : field.type === 'id' ? (
                        <span className="text-xs font-mono font-medium break-all" title={String(value)}>
                          {String(value)}
                        </span>
                      ) : (
                        <span className="text-xs font-medium break-words" title={String(value)}>
                          {formatDisplayValue(field.key, value, locale)}
                        </span>
                      )}
                    </div>
                  );
                })}
                {/* Inline validate/reject actions for pending docs */}
                {isPending && onValidateDoc && onRejectDoc && (
                  <div className="pt-1 border-t border-dashed">
                    {rejectingDocId === doc.id ? (
                      <div className="flex items-center gap-1">
                        <input
                          type="text"
                          value={rejectReason}
                          onChange={(e) => setRejectReason(e.target.value)}
                          placeholder="Motivo del rechazo..."
                          className="flex-1 h-6 px-1.5 text-[10px] border rounded focus:outline-none focus:ring-1 focus:ring-ring"
                          autoFocus
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && rejectReason.length >= 5) handleRejectConfirm(doc.id);
                            if (e.key === 'Escape') { setRejectingDocId(null); setRejectReason(''); }
                          }}
                        />
                        <Button
                          variant="destructive"
                          size="icon"
                          className="h-5 w-5 shrink-0"
                          onClick={() => handleRejectConfirm(doc.id)}
                          disabled={rejectingLoading || rejectReason.length < 5}
                        >
                          {rejectingLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <XCircle className="h-3 w-3" />}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-5 w-5 shrink-0"
                          onClick={() => { setRejectingDocId(null); setRejectReason(''); }}
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-5 px-1.5 text-[10px] text-green-700 hover:bg-green-50 hover:text-green-800"
                          onClick={() => handleValidate(doc.id)}
                          disabled={validatingDocId === doc.id}
                        >
                          {validatingDocId === doc.id ? (
                            <Loader2 className="h-3 w-3 animate-spin mr-0.5" />
                          ) : (
                            <CheckCircle2 className="h-3 w-3 mr-0.5" />
                          )}
                          Validar
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-5 px-1.5 text-[10px] text-red-600 hover:bg-red-50 hover:text-red-700"
                          onClick={() => { setRejectingDocId(doc.id); setRejectReason(''); }}
                        >
                          <XCircle className="h-3 w-3 mr-0.5" />
                          Rechazar
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Section Card Component
 */
function SectionCard({
  section,
  request,
}: {
  section: { id: string; title: string; fields: Array<{
    key: string;
    label: string;
    type: string;
    source?: string;
    default?: string;
  }> };
  request: ServiceRequestDetail;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{section.title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {section.fields.map((field) => {
            let value: unknown;

            // Get value based on source
            if (field.source === 'request') {
              value = getNestedValue(request as unknown as Record<string, unknown>, field.key);
            } else if (field.source === 'appointment') {
              // Map appointment fields
              if (field.key === 'cita_location') {
                value = request.citaLocation;
              } else if (field.key === 'cita_date') {
                value = request.citaDate;
              }
            } else {
              // Default: get from form_data
              value = getNestedValue(request.formData, field.key);
            }

            const displayValue = formatFieldValue(value, field.type, field.default);

            return (
              <div key={field.key} className="flex justify-between items-start py-1">
                <span className="text-sm text-muted-foreground">{field.label}</span>
                <span className="text-sm font-medium text-right max-w-[60%]">
                  {field.type === 'status' ? (
                    <Badge variant={getStatusBadgeVariant(displayValue)}>
                      {displayValue}
                    </Badge>
                  ) : (
                    displayValue
                  )}
                </span>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Tab DOCUMENTOS - List of uploaded documents with preview
 */
function DocumentosTab({
  requestId,
  documents,
  onDocumentStatusChanged,
}: {
  requestId: string;
  documents: Array<{
    id: string;
    documentCode: string;
    documentName: string;
    filePath: string;
    fileName: string;
    mimeType: string;
    validationStatus?: string;
  }>;
  onDocumentStatusChanged?: () => void;
}) {
  const t = useTranslations('agent.requestDetail');
  const tp = useTranslations('agent.pending.preview');
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loadingDoc, setLoadingDoc] = useState<string | null>(null);
  const [statusOverrides, setStatusOverrides] = useState<Record<string, string>>({});

  // Reject form state
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [isValidating, setIsValidating] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);

  const selectedDoc = documents.find(d => d.id === selectedDocId) || null;
  const effectiveStatus = selectedDoc
    ? (statusOverrides[selectedDoc.id] || selectedDoc.validationStatus || 'pending')
    : 'pending';
  const isAlreadyDecided = effectiveStatus === 'validated' || effectiveStatus === 'rejected';

  const handleSelect = useCallback(async (doc: typeof documents[0]) => {
    setSelectedDocId(doc.id);
    setPreviewUrl(null);
    setShowRejectForm(false);
    setRejectReason('');
    setLoadingDoc(doc.id);
    try {
      const url = await getDocumentDownloadUrlCached(requestId, doc.documentCode);
      setPreviewUrl(url);
    } catch (error) {
      console.error('Failed to get document URL:', error);
    } finally {
      setLoadingDoc(null);
    }
  }, [requestId]);

  const handleValidate = async () => {
    if (!selectedDoc) return;
    setIsValidating(true);
    try {
      const { validateDocument } = await import('@/modules/agent-dashboard/services/agent-requests-api');
      await validateDocument(selectedDoc.id);
      toast.success(tp('docValidateSuccess'));
      setStatusOverrides(prev => ({ ...prev, [selectedDoc.id]: 'validated' }));
      onDocumentStatusChanged?.();
    } catch {
      toast.error(tp('docValidateError'));
    } finally {
      setIsValidating(false);
    }
  };

  const handleRejectConfirm = async () => {
    if (!selectedDoc || rejectReason.length < 5) return;
    setIsRejecting(true);
    try {
      const { rejectDocument } = await import('@/modules/agent-dashboard/services/agent-requests-api');
      await rejectDocument(selectedDoc.id, rejectReason);
      toast.success(tp('docRejectSuccess'));
      setStatusOverrides(prev => ({ ...prev, [selectedDoc.id]: 'rejected' }));
      setShowRejectForm(false);
      setRejectReason('');
      onDocumentStatusChanged?.();
    } catch {
      toast.error(tp('docRejectError'));
    } finally {
      setIsRejecting(false);
    }
  };

  const isPdf = (mime?: string, name?: string) =>
    mime === 'application/pdf' || name?.toLowerCase().endsWith('.pdf');
  const isImg = (mime?: string) => mime?.startsWith('image/');

  if (documents.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 text-center">
          <FileImage className="h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="font-semibold">{t('noDocuments') || 'Sin documentos'}</h3>
          <p className="text-muted-foreground text-sm">
            {t('noDocumentsDescription') || 'No hay documentos cargados para esta solicitud'}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex gap-4 h-[calc(100vh-320px)] min-h-[500px]">
      {/* Left: Document list (40%) */}
      <Card className="w-[40%] shrink-0 flex flex-col overflow-hidden">
        <CardHeader className="py-3 px-4 shrink-0">
          <CardTitle className="flex items-center gap-2 text-base">
            <FileImage className="h-4 w-4" />
            {t('documents') || 'Documentos'} ({documents.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0 flex-1 overflow-y-auto">
          {documents.map((doc) => {
            const docStatus = statusOverrides[doc.id] || doc.validationStatus || 'pending';
            const isSelected = selectedDocId === doc.id;
            return (
              <button
                key={doc.id}
                onClick={() => handleSelect(doc)}
                className={cn(
                  'flex items-center gap-3 w-full px-4 py-3 text-left transition-colors border-b',
                  'hover:bg-blue-50/60',
                  isSelected && 'bg-blue-50 border-l-2 border-l-blue-500'
                )}
              >
                <FileText className={cn(
                  'h-6 w-6 shrink-0',
                  docStatus === 'validated' ? 'text-green-500' :
                  docStatus === 'rejected' ? 'text-red-500' : 'text-blue-500'
                )} />
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-sm truncate">{doc.documentName}</p>
                  <p className="text-xs text-muted-foreground truncate">{doc.fileName}</p>
                </div>
                {docStatus !== 'pending' && (
                  <Badge
                    variant={docStatus === 'validated' ? 'default' : 'destructive'}
                    className="text-[10px] shrink-0"
                  >
                    {docStatus === 'validated' && <CheckCircle2 className="h-3 w-3 mr-0.5" />}
                    {docStatus === 'rejected' && <XCircle className="h-3 w-3 mr-0.5" />}
                    {docStatus === 'validated' ? tp('docAlreadyValidated') : tp('docAlreadyRejected')}
                  </Badge>
                )}
                {loadingDoc === doc.id && (
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground shrink-0" />
                )}
              </button>
            );
          })}
        </CardContent>
      </Card>

      {/* Right: Preview + Actions (60%) */}
      <Card className="flex-1 flex flex-col overflow-hidden">
        {!selectedDoc ? (
          /* Empty state */
          <CardContent className="flex flex-col items-center justify-center flex-1 text-center">
            <Eye className="h-10 w-10 text-muted-foreground/40 mb-3" />
            <p className="text-sm text-muted-foreground">
              {t('selectDocumentToPreview') || 'Seleccione un documento para previsualizar'}
            </p>
          </CardContent>
        ) : (
          <>
            {/* Preview header */}
            <div className="px-4 py-2 border-b flex items-center justify-between shrink-0 bg-muted/30">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-sm font-medium truncate">{selectedDoc.documentName}</span>
                {effectiveStatus === 'validated' && (
                  <Badge className="bg-green-100 text-green-700 text-[10px]">
                    <CheckCircle2 className="h-3 w-3 mr-0.5" />
                    {tp('docAlreadyValidated')}
                  </Badge>
                )}
                {effectiveStatus === 'rejected' && (
                  <Badge className="bg-red-100 text-red-700 text-[10px]">
                    <XCircle className="h-3 w-3 mr-0.5" />
                    {tp('docAlreadyRejected')}
                  </Badge>
                )}
              </div>
              {previewUrl && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => window.open(previewUrl, '_blank')}
                  className="shrink-0 h-7 text-xs"
                >
                  <Eye className="h-3 w-3 mr-1" />
                  {tp('newTab')}
                </Button>
              )}
            </div>

            {/* Preview body */}
            <div className="flex-1 min-h-0 overflow-hidden bg-muted/10">
              {loadingDoc === selectedDoc.id ? (
                <div className="flex items-center justify-center h-full">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : previewUrl && isPdf(selectedDoc.mimeType, selectedDoc.fileName) ? (
                <iframe
                  src={previewUrl}
                  className="w-full h-full"
                  title={selectedDoc.fileName}
                />
              ) : previewUrl && isImg(selectedDoc.mimeType) ? (
                <div className="flex items-center justify-center h-full p-4">
                  <img
                    src={previewUrl}
                    alt={selectedDoc.fileName}
                    className="max-w-full max-h-full object-contain rounded shadow-sm"
                  />
                </div>
              ) : previewUrl ? (
                <div className="flex flex-col items-center justify-center h-full gap-3">
                  <FileText className="h-12 w-12 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">
                    {tp('previewNotAvailable')}
                  </p>
                </div>
              ) : (
                <div className="flex items-center justify-center h-full">
                  <p className="text-sm text-muted-foreground">
                    {t('documentUrlError') || 'Error al cargar el documento'}
                  </p>
                </div>
              )}
            </div>

            {/* Actions footer */}
            <div className="px-4 py-3 border-t bg-muted/30 shrink-0">
              {isAlreadyDecided ? (
                <div className="flex items-center gap-2 text-sm">
                  {effectiveStatus === 'validated' ? (
                    <span className="text-green-700 font-medium flex items-center gap-1">
                      <CheckCircle2 className="h-4 w-4" />
                      {tp('docAlreadyValidated')}
                    </span>
                  ) : (
                    <span className="text-red-700 font-medium flex items-center gap-1">
                      <XCircle className="h-4 w-4" />
                      {tp('docAlreadyRejected')}
                    </span>
                  )}
                </div>
              ) : showRejectForm ? (
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    placeholder={tp('docRejectReasonPlaceholder')}
                    className="flex-1 h-9 px-3 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-ring"
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && rejectReason.length >= 5) handleRejectConfirm();
                      if (e.key === 'Escape') setShowRejectForm(false);
                    }}
                  />
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={handleRejectConfirm}
                    disabled={isRejecting || rejectReason.length < 5}
                  >
                    {isRejecting ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <XCircle className="h-4 w-4 mr-1" />}
                    {isRejecting ? tp('docRejecting') : tp('docRejectConfirm')}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => { setShowRejectForm(false); setRejectReason(''); }}>
                    {tp('docRejectCancel')}
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    onClick={handleValidate}
                    disabled={isValidating}
                    className="bg-green-600 hover:bg-green-700"
                  >
                    {isValidating ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <CheckCircle2 className="h-4 w-4 mr-1" />}
                    {isValidating ? tp('docValidating') : tp('docValidate')}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setShowRejectForm(true)}
                    className="border-red-300 text-red-700 hover:bg-red-50"
                  >
                    <XCircle className="h-4 w-4 mr-1" />
                    {tp('docReject')}
                  </Button>
                </div>
              )}
            </div>
          </>
        )}
      </Card>
    </div>
  );
}

// ============================================================================
// HISTORIAL TAB — Compact timeline of all actions on this request
// ============================================================================

/** Icon for a history action type */
function HistorialIcon({ action, className = 'h-3.5 w-3.5' }: { action: string; className?: string }) {
  switch (action) {
    case HistoryActionType.STATUS_CHANGE:
    case HistoryActionType.STATUS_CORRECTION:
      return <ArrowUpRight className={className} />;
    case HistoryActionType.DOCUMENT_ADDED:
    case HistoryActionType.DOCUMENT_VALIDATED:
      return <FileText className={className} />;
    case HistoryActionType.DOCUMENT_REMOVED:
      return <XCircle className={className} />;
    case HistoryActionType.OCR_COMPLETED:
      return <Scan className={className} />;
    case HistoryActionType.OCR_FAILED:
      return <AlertTriangle className={className} />;
    case HistoryActionType.ASSIGNED:
      return <UserPlus className={className} />;
    case HistoryActionType.REASSIGNED:
      return <Users className={className} />;
    case HistoryActionType.CITA_SCHEDULED:
    case HistoryActionType.CITA_RESCHEDULED:
    case HistoryActionType.CITA_CANCELLED:
      return <Calendar className={className} />;
    case HistoryActionType.VERIFICATION_UPDATED:
      return <ShieldCheck className={className} />;
    case HistoryActionType.AGENT_ACTION:
      return <ClipboardCheck className={className} />;
    case HistoryActionType.PAYMENT_INITIATED:
    case HistoryActionType.PAYMENT_RECEIVED:
    case HistoryActionType.PAYMENT_FAILED:
      return <CreditCard className={className} />;
    case HistoryActionType.COMMENT_ADDED:
    case HistoryActionType.NOTE_ADDED:
      return <MessageSquare className={className} />;
    case HistoryActionType.ESCALATED:
      return <AlertTriangle className={className} />;
    case HistoryActionType.REOPENED:
      return <RotateCcw className={className} />;
    default:
      return <Clock className={className} />;
  }
}

function HistorialTab({ requestId }: { requestId: string }) {
  const locale = useLocale() as 'es' | 'fr' | 'en';

  const { data, isLoading, error } = useQuery({
    queryKey: ['request-history', requestId],
    queryFn: () => serviceRequestsApi.getRequestHistory(requestId),
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-10 flex justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <CardContent className="py-10 text-center">
          <AlertCircle className="h-8 w-8 text-destructive mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">
            Error al cargar el historial
          </p>
        </CardContent>
      </Card>
    );
  }

  const entries = data.entries;

  if (entries.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center">
          <History className="h-8 w-8 text-muted-foreground/40 mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">
            Sin acciones registradas
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="py-3 px-4">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <History className="h-4 w-4" />
          Historial ({entries.length}{data.total > entries.length ? ` / ${data.total}` : ''})
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-4 pt-0">
        <div className="space-y-0">
          {entries.map((entry, idx) => {
            const colorClass = getHistoryActionColor(entry.action);
            const date = new Date(entry.performedAt);
            const details = entry.details || {};
            const isLast = idx === entries.length - 1;

            return (
              <div key={entry.id} className="flex gap-3">
                {/* Timeline dot + line */}
                <div className="flex flex-col items-center pt-0.5">
                  <div className={cn('p-1.5 rounded-full shrink-0', colorClass)}>
                    <HistorialIcon action={entry.action} />
                  </div>
                  {!isLast && <div className="w-px flex-1 bg-border my-1" />}
                </div>

                {/* Content */}
                <div className={cn('flex-1 min-w-0', !isLast && 'pb-3')}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium truncate">
                      {getHistoryActionLabel(entry.action, locale)}
                    </p>
                    <time className="text-[11px] text-muted-foreground shrink-0 tabular-nums">
                      {date.toLocaleDateString(locale, { day: '2-digit', month: 'short' })}{' '}
                      {date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })}
                    </time>
                  </div>

                  {/* Status transition */}
                  {entry.action === HistoryActionType.STATUS_CHANGE && entry.newStatus && (
                    <div className="flex items-center gap-1.5 mt-0.5">
                      {entry.previousStatus && (
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                          {getStatusLabel(entry.previousStatus, locale)}
                        </Badge>
                      )}
                      <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />
                      <Badge className="text-[10px] px-1.5 py-0">
                        {getStatusLabel(entry.newStatus, locale)}
                      </Badge>
                    </div>
                  )}

                  {/* OCR details (compact) */}
                  {(entry.action === HistoryActionType.OCR_COMPLETED || entry.action === HistoryActionType.OCR_FAILED) && (
                    <p className="text-xs text-muted-foreground mt-0.5 truncate">
                      {String(details.document_name || details.document_code || '')}
                      {details.extraction_confidence !== undefined && (
                        <span className="ml-2 font-medium">
                          {Math.round(Number(details.extraction_confidence) * 100)}%
                        </span>
                      )}
                      {!!details.has_error && !!details.error_message && (
                        <span className="ml-2 text-destructive">{String(details.error_message)}</span>
                      )}
                    </p>
                  )}

                  {/* Assignment details (compact) */}
                  {(entry.action === HistoryActionType.ASSIGNED || entry.action === HistoryActionType.REASSIGNED) && (
                    <p className="text-xs text-muted-foreground mt-0.5 truncate">
                      {!!details.agent_name && <span>{String(details.agent_name)}</span>}
                      {!!details.reassigned_to_name && (
                        <span> → {String(details.reassigned_to_name)}</span>
                      )}
                    </p>
                  )}

                  {/* Comment */}
                  {entry.comment && (
                    <p className="text-xs text-muted-foreground mt-0.5 italic truncate">
                      &ldquo;{entry.comment}&rdquo;
                    </p>
                  )}

                  {/* Performer */}
                  {entry.performedBy && !entry.performedBy.isSystem && (
                    <p className="text-[11px] text-muted-foreground/70 mt-0.5">
                      {entry.performedBy.fullName}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
