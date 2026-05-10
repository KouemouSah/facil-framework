/**
 * Core API Module Exports
 * Central export point for all API clients
 */

export { default as apiClient } from './client';
export { default as fetchClient, FetchClient } from './fetchClient';
export * from './auth';
export * from './homepage';
export * from './services';
// Explicitly export non-conflicting items from serviceDetails
// formatPrice and getServiceTypeLabel are exported from services.ts
export {
  getServiceDetails,
  formatDuration,
  getCalculationMethodLabel,
  type DocumentDetailItem,
  type ProcedureStepDetailItem,
  type ProcedureDetailItem,
  type CategoryDetailItem,
  type SectorDetailItem,
  type MinistryDetailItem,
  type PricingInfo,
  type RelatedServiceItem,
  type KeywordItem,
  type ServiceDetailsResponse,
} from './serviceDetails';
