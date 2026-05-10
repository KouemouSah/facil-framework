/**
 * Declarations Hooks Exports
 *
 * Includes:
 * - Legacy hook: useUserDeclarations (stateful)
 * - React Query hooks with caching (recommended)
 *
 * @module declarations/hooks
 * @date 2026-01-25
 */

// Legacy hook (for backwards compatibility)
export { useUserDeclarations, default } from './useUserDeclarations';

// React Query hooks with caching (recommended)
export {
  useDeclarations,
  useAllDeclarations,
  useDeclaration,
  useDeclarationWorkflow,
  useCreateDeclaration,
  useUpdateDeclaration,
  useSubmitDeclaration,
  useDeleteDeclaration,
  usePrefetchDeclaration,
  useInvalidateDeclarationsCache,
  declarationQueryKeys,
} from './useDeclarationsQueries';
