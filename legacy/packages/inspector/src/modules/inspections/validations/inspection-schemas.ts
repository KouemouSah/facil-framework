/**
 * Inspection Zod Validation Schemas - Facil Inspeccion
 *
 * Aligned with backend Pydantic models:
 * - packages/backend/app/modules/inspections/models/inspection.py
 *
 * IMPORTANT: Constraints MUST match backend exactly to prevent
 * client-side validation passing but server-side rejecting.
 *
 * Backend model → Zod schema mapping:
 *   InspectionCreate       → createInspectionSchema
 *   InspectionUpdate       → updateInspectionSchema
 *   InspectionCompleteReq  → completeInspectionSchema
 *   MiseEnDemeureRequest   → miseEnDemeureSchema
 *   SealProposeRequest     → sealProposeSchema
 *   SealApproveRequest     → sealApproveSchema
 *   FieldCollectRequest    → fieldCollectSchema
 */

import { z } from 'zod';

// ---------------------------------------------------------------------------
// Shared Validators
// ---------------------------------------------------------------------------

/** UUID v4 format validation */
const uuidSchema = z
  .string()
  .uuid('validation.invalidUuid');

/** Notes field with configurable max length */
const notesSchema = (maxLength = 2000) =>
  z
    .string()
    .max(maxLength, 'validation.notesTooLong')
    .optional();

// ---------------------------------------------------------------------------
// SealReason enum — mirrors backend SealReason(str, Enum)
// ---------------------------------------------------------------------------

export const SEAL_REASONS = [
  'non_paiement_apres_med',
  'activite_non_autorisee',
  'fraude_fiscale',
  'faux_documents',
  'refus_controle',
  'non_conformite_grave',
  'decision_judiciaire',
  'ordre_ministeriel',
] as const;

export type SealReasonValue = (typeof SEAL_REASONS)[number];

// ---------------------------------------------------------------------------
// Inspection Schemas
// ---------------------------------------------------------------------------

/**
 * POST /inspections/ — InspectionCreate
 *
 * Backend: license_id: UUID, company_id: UUID, notes: Optional[str] max_length=2000
 */
export const createInspectionSchema = z.object({
  license_id: uuidSchema,
  company_id: uuidSchema,
  notes: notesSchema(2000),
});

/**
 * PUT /inspections/{id} — InspectionUpdate
 *
 * Backend: activity_conforme: Optional[bool], activity_declared: Optional[str] max_length=200,
 *          activity_observed: Optional[str] max_length=200, notes: Optional[str] max_length=2000
 * Note: photos, gps_*, agent_signature handled separately (not form fields)
 */
export const updateInspectionSchema = z.object({
  activity_conforme: z.boolean().optional(),
  activity_declared: z
    .string()
    .max(200, 'validation.activityTooLong')
    .optional(),
  activity_observed: z
    .string()
    .max(200, 'validation.activityTooLong')
    .optional(),
  notes: notesSchema(2000),
});

/**
 * POST /inspections/{id}/complete — InspectionCompleteRequest
 *
 * Backend: notes: Optional[str] max_length=2000
 */
export const completeInspectionSchema = z.object({
  notes: notesSchema(2000),
});

/**
 * POST /inspections/{id}/mise-en-demeure — MiseEnDemeureRequest
 *
 * Backend: obligation_ids: List[UUID] min_length=1,
 *          deadline_hours: int ge=24 le=720 default=72,
 *          notes: Optional[str] max_length=2000
 */
export const miseEnDemeureSchema = z.object({
  obligation_ids: z
    .array(uuidSchema)
    .min(1, 'med.selectObligations'),
  deadline_hours: z
    .number()
    .int('validation.mustBeInteger')
    .min(24, 'med.deadlineTooShort')
    .max(720, 'med.deadlineTooLong')
    .default(72),
  notes: notesSchema(2000),
});

/**
 * POST /inspections/{id}/seal — SealProposeRequest
 *
 * Backend: reason: SealReason (enum), notes: Optional[str] max_length=2000,
 *          photo: Optional[str]
 */
export const sealProposeSchema = z.object({
  reason: z.enum(SEAL_REASONS, {
    required_error: 'seal.selectReason',
    invalid_type_error: 'seal.selectReason',
  }),
  notes: notesSchema(2000),
  photo: z.string().optional(),
});

/**
 * POST /inspections/{id}/seal/approve — SealApproveRequest
 *
 * Backend: approved: bool, notes: Optional[str] max_length=2000
 * Business rule: rejection (approved=false) requires justification notes
 */
export const sealApproveSchema = z
  .object({
    approved: z.boolean(),
    notes: z.string().max(2000, 'validation.notesTooLong').optional(),
  })
  .refine(
    (data) => data.approved || (data.notes && data.notes.trim().length > 0),
    {
      message: 'seal.rejectionNotesRequired',
      path: ['notes'],
    },
  );

/**
 * POST /inspections/{id}/collect — FieldCollectRequest
 *
 * Backend: obligation_ids: List[UUID] min_length=1,
 *          method: str pattern=^(cash|mobile_money)$,
 *          amount: Decimal gt=0,
 *          phone_number: Optional[str] max_length=20 (required if mobile_money),
 *          notes: Optional[str] max_length=500
 *
 * Frontend additional constraint: amount <= 50_000_000 (appConfig.business.maxFieldCollectionAmount)
 * Frontend phone regex: /^\+240[0-9]{9}$/ (appConfig.business.phoneRegex)
 */
export const fieldCollectSchema = z
  .object({
    obligation_ids: z
      .array(uuidSchema)
      .min(1, 'payment.selectObligations'),
    method: z.enum(['cash', 'mobile_money'], {
      required_error: 'payment.selectMethod',
      invalid_type_error: 'payment.selectMethod',
    }),
    amount: z
      .number()
      .positive('payment.invalidAmount')
      .max(50_000_000, 'payment.maxAmountExceeded'),
    phone_number: z
      .string()
      .regex(/^\+240[0-9]{9}$/, 'payment.invalidPhone')
      .optional(),
    notes: notesSchema(500),
  })
  .refine(
    (data) =>
      data.method !== 'mobile_money' ||
      (data.phone_number !== undefined && data.phone_number !== ''),
    {
      message: 'payment.phoneRequired',
      path: ['phone_number'],
    },
  );

// ---------------------------------------------------------------------------
// Inferred Types
// ---------------------------------------------------------------------------

export type CreateInspectionInput = z.infer<typeof createInspectionSchema>;
export type UpdateInspectionInput = z.infer<typeof updateInspectionSchema>;
export type CompleteInspectionInput = z.infer<typeof completeInspectionSchema>;
export type MiseEnDemeureInput = z.infer<typeof miseEnDemeureSchema>;
export type SealProposeInput = z.infer<typeof sealProposeSchema>;
export type SealApproveInput = z.infer<typeof sealApproveSchema>;
export type FieldCollectInput = z.infer<typeof fieldCollectSchema>;
