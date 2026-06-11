/**
 * Service Bundles — Types for commerce zone-based pricing.
 */

export type FeeType = 'tesoro' | 'municipal' | 'chamber';

export const FEE_TYPE_LABELS: Record<FeeType, { es: string; fr: string; en: string }> = {
  tesoro: { es: 'TESORO PÚBLICO', fr: 'TRÉSOR PUBLIC', en: 'PUBLIC TREASURY' },
  municipal: { es: 'AYUNTAMIENTO', fr: 'MUNICIPALITÉ', en: 'MUNICIPALITY' },
  chamber: { es: 'CÁMARA DE COMERCIO', fr: 'CHAMBRE DE COMMERCE', en: 'CHAMBER OF COMMERCE' },
};

export interface FeeTypeTotals {
  tesoro: number | string;
  municipal: number | string;
  chamber: number | string;
  grandTotal: number | string;
}

export interface CommerceZone {
  id: string;
  zoneCode: string;
  zoneTier: string;
  zoneRank: number;
  nameEs: string;
  descriptionEs?: string;
  displayOrder: number;
}

export type ProcessingMode = 'per_line' | 'consolidated';

export interface ServiceBundle {
  id: string;
  bundleCode: string;
  commerceType: string;
  nameEs: string;
  descriptionEs?: string;
  legalReference?: string;
  isActive: boolean;
  installmentEligible: boolean;
  maxInstallments: number;
  installmentFrequency: string;
  publicInstallmentVisible: boolean;
  // OMS fields
  processingMode: ProcessingMode;
  deadlineMonth: number;
  deadlineDay: number;
  createdBy?: string;
  updatedBy?: string;
  createdAt: string;
  updatedAt: string;
  itemCount: number;
  zoneCount: number;
}

export interface BundleItem {
  id: string;
  bundleId: string;
  fiscalServiceId: number;
  zoneId: string;
  ministryId?: number;
  amount: number;
  feeType: FeeType;
  isFixedAcrossZones: boolean;
  displayOrder: number;
  notes?: string;
  isActive: boolean;
  // OMS fields
  effectivePenalty?: Record<string, unknown> | null;
  effectiveDeadline?: Record<string, unknown> | null;
  configResolvedAt?: string | null;
  requiresDocument: boolean;
  documentTemplateId?: number | null;
  // Enriched
  serviceCode?: string;
  serviceName?: string;
  ministryName?: string;
}

export interface BundleWithItems {
  bundle: ServiceBundle;
  items: BundleItem[];
  totalAmount: number | string;
  feeTypeTotals?: FeeTypeTotals;
  currency: string;
  installmentEligible: boolean;
  maxInstallments: number;
}

export interface ZoneTotal {
  zone: CommerceZone;
  totalAmount: number | string;
  itemCount: number;
  tesoroTotal: number | string;
  municipalTotal: number | string;
  chamberTotal: number | string;
}

export interface PricingMatrix {
  bundle: ServiceBundle;
  zones: CommerceZone[];
  items: BundleItem[];
  zoneTotals: ZoneTotal[];
  currency: string;
}

export interface BundleDocument {
  documentTemplateId: number;
  documentNameEs: string;
  templateCode?: string;
  isRequired: boolean;
}

export interface InstallmentPreviewItem {
  installmentNumber: number;
  amountDue: number | string;
  dueDate: string;
  cumulativePaid: number | string;
}

export interface InstallmentPreview {
  bundleCode: string;
  totalAmount: number | string;
  numInstallments: number;
  frequency: string;
  gracePeriodDays: number;
  lateFeeRate: string;
  installments: InstallmentPreviewItem[];
  currency: string;
}

// Simulator (public single-call endpoint)

export interface FeeGroupItems {
  feeType: FeeType;
  labelEs: string;
  items: BundleItem[];
  subtotal: number | string;
}

export interface CommerceTypeOption {
  commerceType: string;
  nameEs: string;
  bundleCode: string;
  id: string;
  descriptionEs?: string;
  installmentEligible: boolean;
}

export interface ServiceBundlePublic {
  bundleCode: string;
  commerceType: string;
  nameEs: string;
  descriptionEs?: string;
  legalReference?: string;
  installmentEligible: boolean;
}

export interface SimulatorResponse {
  bundle: ServiceBundlePublic;
  zone: CommerceZone;
  feeGroups: FeeGroupItems[];
  grandTotal: number | string;
  documents: BundleDocument[];
  installmentPreview?: InstallmentPreview | null;
  currency: string;
}

export interface ServiceBundleBadge {
  id: string;
  bundleCode: string;
  nameEs: string;
  commerceType: string;
}

export interface BundleListResponse {
  items: ServiceBundle[];
  total: number;
  page: number;
  pageSize: number;
}

export interface BundleItemCreateInput {
  fiscalServiceId: number;
  zoneId: string;
  ministryId?: number;
  amount: number;
  feeType?: FeeType;
  isFixedAcrossZones?: boolean;
  displayOrder?: number;
  notes?: string;
  isActive?: boolean;
}

export interface BundleCreateInput {
  bundleCode: string;
  commerceType: string;
  nameEs: string;
  descriptionEs?: string;
  legalReference?: string;
  isActive?: boolean;
  installmentEligible?: boolean;
  maxInstallments?: number;
  installmentFrequency?: string;
  publicInstallmentVisible?: boolean;
  processingMode?: ProcessingMode;
  deadlineMonth?: number;
  deadlineDay?: number;
}

export interface BundleUpdateInput {
  bundleCode?: string;
  commerceType?: string;
  nameEs?: string;
  descriptionEs?: string;
  legalReference?: string;
  isActive?: boolean;
  installmentEligible?: boolean;
  maxInstallments?: number;
  installmentFrequency?: string;
  publicInstallmentVisible?: boolean;
  processingMode?: ProcessingMode;
  deadlineMonth?: number;
  deadlineDay?: number;
}

export interface CopyZonePricesInput {
  sourceZoneId: string;
  targetZoneId: string;
  multiplier?: number;
}

export interface FiscalServiceOption {
  id: number;
  serviceCode: string;
  nameEs: string;
  ministryId: number | null;
  ministryName: string | null;
}

export interface BundleStats {
  bundles: number;
  zones: number;
  items: number;
}

export interface BulkImportItem {
  serviceCode: string;
  zoneCode: string;
  amount: number;
  feeType?: FeeType;
  ministryId?: number;
  isFixedAcrossZones?: boolean;
}

export interface BulkImportResult {
  imported: number;
  skipped: { serviceCode: string; zoneCode: string; reason: string }[];
  total: number;
}

export interface ParsedPdfItem {
  serviceCode: string;
  zoneCode: string;
  amount: number;
  isFixedAcrossZones: boolean;
  knownService: boolean;
}

export interface ParsePdfResult {
  extractedItems: ParsedPdfItem[];
  totalExtracted: number;
  tablesFound: number;
  method: string;
  note: string;
}
