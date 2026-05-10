/**
 * Declarations API Service
 * Handles tax declarations API operations
 *
 * @module declarations/services
 * @author Claude Code
 * @date 2025-12-21
 *
 * BACKEND ALIGNMENT:
 * Routes: /api/v1/declarations (from app/modules/declarations/api/declaration_routes.py)
 * - GET    /api/v1/declarations                    → list_declarations
 * - GET    /api/v1/declarations/{id}               → get_declaration
 * - POST   /api/v1/declarations                    → create_declaration
 * - PUT    /api/v1/declarations/{id}               → update_declaration
 * - DELETE /api/v1/declarations/{id}               → delete_declaration
 * - POST   /api/v1/declarations/{id}/submit        → submit_declaration
 */

import { fetchClient } from '@/core/api';
import type {
  DeclarationResponse,
  DeclarationListResponse,
  DeclarationStatus,
} from '@/types/declaration';

// =============================================================================
// CONFIGURATION
// =============================================================================

const DECLARATIONS_BASE = '/declarations';

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Convert snake_case keys to camelCase
 */
function toCamelCase<T>(obj: Record<string, unknown>): T {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      result[camelKey] = toCamelCase(value as Record<string, unknown>);
    } else if (Array.isArray(value)) {
      result[camelKey] = value.map((item) =>
        typeof item === 'object' && item !== null
          ? toCamelCase(item as Record<string, unknown>)
          : item
      );
    } else {
      result[camelKey] = value;
    }
  }
  return result as T;
}

/**
 * Transform API response to frontend format
 */
function transformDeclaration(data: Record<string, unknown>): DeclarationResponse {
  return toCamelCase<DeclarationResponse>(data);
}

function transformListResponse(data: Record<string, unknown>): DeclarationListResponse {
  const declarations = (data.declarations as Record<string, unknown>[]) || [];
  return {
    declarations: declarations.map(transformDeclaration),
    total: (data.total as number) || 0,
    page: (data.page as number) || 1,
    pageSize: (data.page_size as number) || 20,
    totalPages: (data.total_pages as number) || 0,
  };
}

// =============================================================================
// DECLARATIONS API
// =============================================================================

export interface ListDeclarationsParams {
  status?: DeclarationStatus;
  page?: number;
  pageSize?: number;
}

export const declarationsApi = {
  /**
   * List user's declarations
   * BACKEND: GET /api/v1/declarations
   * ROUTE: list_declarations() in declaration_routes.py
   */
  listDeclarations: async (params: ListDeclarationsParams = {}): Promise<DeclarationListResponse> => {
    const queryParams: Record<string, string | number | boolean | undefined> = {
      page: params.page || 1,
      page_size: params.pageSize || 20,
    };

    if (params.status) {
      queryParams.status_filter = params.status;
    }

    const response = await fetchClient.get<Record<string, unknown>>(
      DECLARATIONS_BASE,
      queryParams
    );

    return transformListResponse(response);
  },

  /**
   * Get declaration by ID
   * BACKEND: GET /api/v1/declarations/{id}
   * ROUTE: get_declaration() in declaration_routes.py
   */
  getDeclaration: async (id: string): Promise<DeclarationResponse> => {
    const response = await fetchClient.get<Record<string, unknown>>(
      `${DECLARATIONS_BASE}/${id}`
    );
    return transformDeclaration(response);
  },

  /**
   * Delete declaration (soft delete)
   * BACKEND: DELETE /api/v1/declarations/{id}
   * ROUTE: delete_declaration() in declaration_routes.py
   */
  deleteDeclaration: async (id: string): Promise<{ message: string }> => {
    return fetchClient.delete<{ message: string }>(`${DECLARATIONS_BASE}/${id}`);
  },

  /**
   * Submit declaration for processing
   * BACKEND: POST /api/v1/declarations/{id}/submit
   * ROUTE: submit_declaration() in declaration_routes.py
   */
  submitDeclaration: async (id: string): Promise<DeclarationResponse> => {
    const response = await fetchClient.post<Record<string, unknown>>(
      `${DECLARATIONS_BASE}/${id}/submit`
    );
    return transformDeclaration(response);
  },

  /**
   * Create new declaration
   * BACKEND: POST /api/v1/declarations
   * ROUTE: create_declaration() in declaration_routes.py
   */
  createDeclaration: async (data: Record<string, unknown>): Promise<DeclarationResponse> => {
    const response = await fetchClient.post<Record<string, unknown>>(
      DECLARATIONS_BASE,
      data
    );
    return transformDeclaration(response);
  },

  /**
   * Update declaration
   * BACKEND: PUT /api/v1/declarations/{id}
   * ROUTE: update_declaration() in declaration_routes.py
   */
  updateDeclaration: async (id: string, data: Record<string, unknown>): Promise<DeclarationResponse> => {
    const response = await fetchClient.put<Record<string, unknown>>(
      `${DECLARATIONS_BASE}/${id}`,
      data
    );
    return transformDeclaration(response);
  },

  /**
   * Get declaration workflow status
   * BACKEND: GET /api/v1/declarations/{id}/workflow
   * ROUTE: get_declaration_workflow_status() in declaration_routes.py
   */
  getDeclarationWorkflow: async (id: string): Promise<Record<string, unknown>> => {
    return fetchClient.get<Record<string, unknown>>(
      `${DECLARATIONS_BASE}/${id}/workflow`
    );
  },
};

// =============================================================================
// EXPORTS
// =============================================================================

export default declarationsApi;
