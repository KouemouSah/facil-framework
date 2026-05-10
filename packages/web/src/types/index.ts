/**
 * Shared Types - Used across multiple modules
 *
 * NOTE: Module-specific types should be in their respective module's types/ folder
 * - chatbot types → modules/chatbot/types/
 * Only truly shared types belong here.
 *
 * Due to duplicate definitions across files, prefer importing directly from source:
 * - import { User } from '@/types/auth'
 * - import { UserRole } from '@/types/user'
 */

// Re-export from auth (primary definitions for User, UserRole, UserStatus, UserProfile)
export * from './auth';

// Re-export from declaration
export * from './declaration';

// Re-export from fiscal-service (some exports will be shadowed by auth)
export {
  ServiceTypeEnum,
  CalculationMethodEnum,
  ServiceStatusEnum,
  TranslatableEntityType,
  type Ministry,
  type Sector,
  type Category,
  type RateTier,
  type FiscalServiceBase,
  type FiscalServiceCreate,
  type FiscalServiceUpdate,
  type FiscalServiceResponse,
  type FiscalServiceWithCategory,
  type DocumentTemplate,
  type DocumentTemplateCreate,
  type DocumentTemplateUpdate,
  type ServiceDocumentAssignment,
  type ProcedureTemplate,
  type ProcedureTemplateCreate,
  type ProcedureTemplateUpdate,
  type ProcedureStep,
  type ProcedureStepCreate,
  type ProcedureStepUpdate,
  type ServiceProcedureAssignment,
  type ServiceKeyword,
  type EntityTranslation,
  type CalculationInput,
  type CalculationBreakdown,
  type CalculationResult,
  type FiscalServiceFilter,
  type FiscalServiceStats,
  type FiscalServiceListResponse,
  toCamelCase,
  toSnakeCase,
  isActiveService,
  requiresDocuments,
} from './fiscal-service';
