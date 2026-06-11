/**
 * Funcionario Verification Types
 * Types for civil servant verification workflow (Session-based v2)
 */

export type VerificacionStatus = 'pendiente' | 'aprobado' | 'rechazado'

export type DocumentoTipoPrueba = 'nombramiento' | 'carnet_funcionario' | 'contrato_funcionario'

export interface ValidacionCruzada {
  nombre_dip: string | null
  nombre_documento: string | null
  nombres_coinciden: boolean
  similitud_nombre: number
  matricula_documento: string | null
  matricula_ingresada: string | null
  matriculas_coinciden: boolean
  validacion_automatica_posible: boolean
}

export interface MyVerificationStatus {
  has_verification: boolean
  status: VerificacionStatus | null
  matricula: string | null
  submitted_at: string | null
  processed_at: string | null
  rejection_reason: string | null
  is_verified_funcionario: boolean
  funcionario_verified_at: string | null
  can_submit_new: boolean
  message: string | null
}

// =============================================================================
// SESSION-BASED FLOW (v2) - Types
// =============================================================================

export interface SessionStartResponse {
  session_id: string
  matricula: string
  created_at: string
  expires_at: string
  ttl_seconds: number
  required_documents: Array<{
    code: string
    name: string
    required: boolean
  }>
}

export interface SessionPreviewResponse {
  session_id: string
  document_code: string
  file_name: string
  file_size: number
  extraction: Record<string, unknown>
  confidence: number
  status: string
  risk_analysis?: Record<string, unknown>
  validacion_cruzada: ValidacionCruzada | null
  expires_at: string
}

export interface SessionStatusResponse {
  session_id: string
  matricula: string
  created_at: string
  expires_at: string
  documents: Record<string, {
    uploaded: boolean
    file_name: string
    confidence: number
    status: string
    previewed_at: string
  }>
  validacion_cruzada: ValidacionCruzada | null
  ready_for_submit: boolean
  proof_document_type: DocumentoTipoPrueba | null
}

export interface SessionFormReviewResponse {
  session_id: string
  expires_at: string
  documents_uploaded: string[]
  proof_document_type: DocumentoTipoPrueba | null
  ready_for_submit: boolean
  step_id: string
  title_es: string
  description_es: string
  cross_validation_passed: boolean
  auto_validable: boolean
  warnings: Array<{
    code: string
    message: string
    severity: string
  }>
  sections: Array<{
    id: string
    title_es: string
    source_document?: string
    readonly?: boolean
    fields: Array<{
      key: string
      label_es: string
      value: unknown
      type?: string
      required?: boolean
      editable?: boolean
      critical?: boolean
      confidence?: number
    }>
  }>
}

export interface SessionSubmitResponse {
  success: boolean
  submitted: boolean
  verificacion_id?: string
  reference?: string
  status?: VerificacionStatus
  auto_validable?: boolean
  warnings: Array<{
    code: string
    message: string
    severity: string
  }>
  warnings_acknowledged?: boolean
  message: string
  validacion_cruzada?: ValidacionCruzada
  // For requires_confirmation response
  requires_confirmation?: boolean
  session_id?: string
}

export interface SessionSubmitRequest {
  form_data?: Record<string, unknown>
  force_submit?: boolean
}

// =============================================================================
// LEGACY TYPES (v1) - Deprecated
// =============================================================================

export interface DocumentPreviewResponse {
  preview_id: string
  document_code: string
  document_name: string
  file_name: string
  file_size: number
  mime_type: string
  extraction: Record<string, unknown>
  confidence: number
  processor: string
  extraction_status: string
  expires_at: string | null
}

export interface DocumentValidateResponse {
  document_id: string
  document_code: string
  document_name: string
  file_path: string
  extraction_data: Record<string, unknown>
  extraction_confidence: number
  is_validated: boolean
  validated_at: string
  validacion_cruzada: ValidacionCruzada | null
}

export interface CreateVerificacionResponse {
  id: string
  matricula: string
  status: VerificacionStatus
  message: string
}

export interface SubmitVerificacionResponse {
  success: boolean
  verificacion_id: string
  status: VerificacionStatus
  message: string
  validacion_cruzada: ValidacionCruzada | null
  auto_validable: boolean
}

// =============================================================================
// WIZARD STATE
// =============================================================================

// Session-based wizard state (v2)
export interface SessionWizardState {
  session_id: string | null
  matricula: string
  step: 'matricula' | 'dip' | 'proof' | 'form_review' | 'submitted'
  expires_at: string | null
  documents: {
    dip?: {
      file_name: string
      confidence: number
      extraction: Record<string, unknown>
      uploaded: boolean
    }
    proof?: {
      file_name: string
      confidence: number
      extraction: Record<string, unknown>
      uploaded: boolean
      tipo: DocumentoTipoPrueba
    }
  }
  validacion_cruzada: ValidacionCruzada | null
  form_review_data: Record<string, unknown> | null
  // Submit result (for success view)
  submit_result: SessionSubmitResponse | null
}

// Legacy wizard state (v1 - deprecated)
export interface VerificacionWizardState {
  verificacion_id: string | null
  matricula: string
  step: 'matricula' | 'dip' | 'proof' | 'review' | 'submitted'
  documents: {
    dip?: DocumentPreviewResponse & { validated?: boolean; extraction_data?: Record<string, unknown> }
    proof?: DocumentPreviewResponse & {
      validated?: boolean
      extraction_data?: Record<string, unknown>
      tipo: DocumentoTipoPrueba
    }
  }
  validacion_cruzada: ValidacionCruzada | null
}

// Document type labels
export const DOCUMENTO_TIPO_LABELS: Record<DocumentoTipoPrueba, { es: string; fr: string; en: string }> = {
  nombramiento: {
    es: 'Nombramiento',
    fr: 'Nomination',
    en: 'Appointment',
  },
  carnet_funcionario: {
    es: 'Carnet de Funcionario',
    fr: 'Carte de Fonctionnaire',
    en: 'Civil Servant ID Card',
  },
  contrato_funcionario: {
    es: 'Contrato de Funcionario',
    fr: 'Contrat de Fonctionnaire',
    en: 'Civil Servant Contract',
  },
}
