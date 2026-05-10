/**
 * Calculator API client.
 *
 * Single endpoint: `GET /api/v1/homepage/calculator/config?language={lng}`.
 * Public (no auth required). Returns service overrides that the frontend
 * merges with `DEFAULT_CALCULABLE_SERVICES`.
 */

import { apiGet } from '@core/api/client';
import type { CalculatorConfigResponse } from '../types/calculator.types';

export type CalculatorLanguage = 'es' | 'fr' | 'en';

export async function getCalculatorConfig(
  language: CalculatorLanguage
): Promise<CalculatorConfigResponse> {
  return apiGet<CalculatorConfigResponse>('/homepage/calculator/config', { language });
}
