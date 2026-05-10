/**
 * Calculator React Query hooks.
 */

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import { DEFAULT_CALCULABLE_SERVICES } from '../constants/calculator.constants';
import type {
  ApiServiceConfig,
  CalculableService,
  FormulaService,
  FormulaVariable,
  PercentageService,
} from '../types/calculator.types';
import { getCalculatorConfig, type CalculatorLanguage } from './calculator-api';

export const CALCULATOR_QUERY_KEYS = {
  config: (language: CalculatorLanguage) => ['calculator', 'config', language] as const,
} as const;

/**
 * Fetch calculator service overrides.
 *
 * `retry:false` + `staleTime:1h` mirror the backend's 1-hour cache.
 * On any error the consumer falls back to `DEFAULT_CALCULABLE_SERVICES`
 * via `useMergedCalculableServices`. We never surface an error UI for this
 * — graceful degradation matches the web behaviour.
 */
export function useCalculatorConfig(language: CalculatorLanguage) {
  return useQuery({
    queryKey: CALCULATOR_QUERY_KEYS.config(language),
    queryFn: () => getCalculatorConfig(language),
    staleTime: 60 * 60_000,
    gcTime: 60 * 60_000,
    retry: false,
    refetchOnWindowFocus: false,
  });
}

/**
 * Combine the API response with the default services, preserving the local
 * "user-friendly" formula (with `/100` for percentage inputs).
 *
 * Mirror of web `mergeServiceConfig` (calculateur/page.tsx:304-347).
 */
function mergeServiceConfig(
  defaultService: CalculableService,
  apiConfig: ApiServiceConfig | undefined
): CalculableService {
  if (!apiConfig) return defaultService;

  if (defaultService.type === 'percentage' && apiConfig.base_percentage !== null) {
    const merged: PercentageService = {
      ...defaultService,
      percentage: apiConfig.base_percentage,
    };
    return merged;
  }

  if (defaultService.type === 'formula') {
    const config = apiConfig.calculation_config;
    if (config?.variables) {
      const updatedVariables: FormulaVariable[] = Object.entries(config.variables).map(
        ([key, v]) => ({
          key,
          type: v.type,
          label_es: v.label_es || key,
          label_fr: v.label_fr || key,
          label_en: v.label_en || key,
          description_es: v.description_es,
          description_fr: v.description_fr,
          description_en: v.description_en,
          defaultValue: v.default_value,
        })
      );
      const merged: FormulaService = {
        ...defaultService,
        variables: updatedVariables,
      };
      return merged;
    }
  }

  return defaultService;
}

/**
 * Returns the list of calculable services merged with the API config.
 * Falls back silently to defaults if the query is loading or has errored.
 */
export function useMergedCalculableServices(language: CalculatorLanguage): CalculableService[] {
  const { data } = useCalculatorConfig(language);

  return useMemo(() => {
    if (!data?.services?.length) return DEFAULT_CALCULABLE_SERVICES;
    return DEFAULT_CALCULABLE_SERVICES.map((defaultService) => {
      const apiConfig = data.services.find((s) => s.id === defaultService.id);
      return mergeServiceConfig(defaultService, apiConfig);
    });
  }, [data]);
}
