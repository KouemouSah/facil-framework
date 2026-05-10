'use client';

/**
 * OrphanDetectionPanel
 * Detects inconsistencies between entities.workflow_codes,
 * workflow_menu_mapping patterns, and workflow_display_config codes.
 *
 * Self-contained: fetches ALL mappings, display configs, and entities
 * independently to avoid being limited by parent pagination.
 *
 * @module admin/components
 * @date 2026-02-17
 */

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import { useLocale } from 'next-intl';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { AlertTriangle, CheckCircle2, ChevronDown, Plus } from 'lucide-react';
import apiClient from '@/core/api/client';
import { useEntitiesWithDetails } from '@/modules/cities/hooks';
import { useDisplayConfigs } from '@/modules/admin/hooks';
import type { WorkflowMenuMapping } from '@/modules/agent-dashboard/types/menu-config';
import { sqlLikeToRegex } from '@/core/utils/sql-like';

// =============================================================================
// TYPES
// =============================================================================

interface OrphanItem {
  workflowCode: string;
  entityName?: string;
  entityCode?: string;
}

// =============================================================================
// COMPONENT
// =============================================================================

export function OrphanDetectionPanel() {
  const t = useTranslations('admin.menuConfig.orphanDetection');
  const locale = useLocale();
  const [isOpen, setIsOpen] = useState(false);

  // Self-contained data fetches — always see FULL dataset, not parent pagination
  const { data: mappingsData, isError: mappingsError } = useQuery({
    queryKey: ['workflow-mappings', 'all'],
    queryFn: async () => {
      const response = await apiClient.get<{ items: WorkflowMenuMapping[] }>(
        '/menu-config/workflow-mappings',
        { params: { page: 1, page_size: 100 } }
      );
      return response.data;
    },
  });

  const { data: displayConfigsData, isError: displayError } = useDisplayConfigs({ page: 1, page_size: 100 });

  const { data: entitiesData, isError: entitiesError } = useEntitiesWithDetails({ is_active: true });

  const hasDataError = mappingsError || displayError || entitiesError;

  // Compute orphans
  const analysis = useMemo(() => {
    const mappings = mappingsData?.items ?? [];
    const displayConfigs = displayConfigsData?.items ?? [];
    const entities = entitiesData?.items ?? entitiesData ?? [];
    if (!Array.isArray(entities) || entities.length === 0) {
      return { workflowsNoMapping: [], workflowsNoDisplay: [], mappingsNoWorkflow: [] };
    }

    // Pre-compile regex patterns once (perf: avoid N*M recompilations)
    const activeMappings = mappings.filter(m => m.is_active);
    const compiledPatterns = activeMappings.map(m => ({
      mapping: m,
      regex: sqlLikeToRegex(m.workflow_pattern),
    }));

    // Collect all unique workflow codes from all entities
    const allWorkflowCodes: Record<string, { entityName: string; entityCode: string }> = {};
    for (const entity of entities) {
      const codes = (entity.resolved_workflow_codes?.length ? entity.resolved_workflow_codes : entity.workflow_codes) ?? [];
      for (const wc of codes) {
        if (!allWorkflowCodes[wc]) {
          allWorkflowCodes[wc] = { entityName: entity.name, entityCode: entity.code };
        }
      }
    }

    const allCodes = Object.keys(allWorkflowCodes);

    // 1. Workflows without any matching mapping
    const workflowsNoMapping: OrphanItem[] = [];
    for (const wc of allCodes) {
      const hasMatch = compiledPatterns.some(({ regex }) => regex.test(wc));
      if (!hasMatch) {
        workflowsNoMapping.push({ workflowCode: wc, ...allWorkflowCodes[wc] });
      }
    }

    // 2. Workflows without display config
    const displayCodes = new Set(displayConfigs.filter(d => d.is_active).map(d => d.workflow_code));
    const workflowsNoDisplay: OrphanItem[] = [];
    for (const wc of allCodes) {
      if (!displayCodes.has(wc)) {
        workflowsNoDisplay.push({ workflowCode: wc, ...allWorkflowCodes[wc] });
      }
    }

    // 3. Mappings that don't match any workflow
    const mappingsNoWorkflow: { pattern: string; mappingId: number }[] = [];
    for (const { mapping, regex } of compiledPatterns) {
      const hasMatch = allCodes.some(wc => regex.test(wc));
      if (!hasMatch) {
        mappingsNoWorkflow.push({ pattern: mapping.workflow_pattern, mappingId: mapping.id });
      }
    }

    return { workflowsNoMapping, workflowsNoDisplay, mappingsNoWorkflow };
  }, [mappingsData, displayConfigsData, entitiesData]);

  const totalIssues =
    analysis.workflowsNoMapping.length +
    analysis.workflowsNoDisplay.length +
    analysis.mappingsNoWorkflow.length;

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <Card>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-muted/30 transition-colors">
            <CardTitle className="text-base flex items-center justify-between">
              <div className="flex items-center gap-2">
                {hasDataError ? (
                  <AlertTriangle className="h-4 w-4 text-destructive" />
                ) : totalIssues > 0 ? (
                  <AlertTriangle className="h-4 w-4 text-amber-500" />
                ) : (
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                )}
                {t('title', { defaultValue: 'Detección de inconsistencias' })}
                <Badge variant={hasDataError ? 'outline' : totalIssues > 0 ? 'destructive' : 'secondary'} className="text-xs">
                  {hasDataError ? '?' : totalIssues}
                </Badge>
              </div>
              <ChevronDown
                className={`h-4 w-4 text-muted-foreground transition-transform ${isOpen ? 'rotate-180' : ''}`}
              />
            </CardTitle>
          </CardHeader>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent className="space-y-4 pt-0">
            {hasDataError ? (
              <p className="text-sm text-destructive">
                {t('dataError', { defaultValue: 'Error al cargar datos. Los resultados pueden ser incompletos.' })}
              </p>
            ) : totalIssues === 0 ? (
              <p className="text-sm text-green-600">
                {t('noIssues', { defaultValue: 'Sin inconsistencias. Todos los workflows tienen mapping y display config.' })}
              </p>
            ) : (
              <>
                {/* Workflows without mapping */}
                {analysis.workflowsNoMapping.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium flex items-center gap-2">
                      {t('workflowsWithoutMapping', { defaultValue: 'Workflows sin mapping' })}
                      <Badge variant="outline" className="text-xs">
                        {analysis.workflowsNoMapping.length}
                      </Badge>
                    </h4>
                    <div className="space-y-1">
                      {analysis.workflowsNoMapping.map((item) => (
                        <div
                          key={item.workflowCode}
                          className="flex items-center justify-between py-1.5 px-3 rounded bg-muted/30 text-sm"
                        >
                          <div className="flex items-center gap-2">
                            <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                              {item.workflowCode}
                            </code>
                            {item.entityName && (
                              <span className="text-xs text-muted-foreground">
                                ({item.entityName})
                              </span>
                            )}
                          </div>
                          <Button variant="ghost" size="sm" className="h-7 text-xs" asChild>
                            <Link href={`/${locale}/dashboard/admin/workflow-mappings/new`}>
                              <Plus className="h-3 w-3 mr-1" />
                              {t('createMapping', { defaultValue: 'Crear mapping' })}
                            </Link>
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Workflows without display config */}
                {analysis.workflowsNoDisplay.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium flex items-center gap-2">
                      {t('workflowsWithoutDisplayConfig', { defaultValue: 'Workflows sin display config' })}
                      <Badge variant="outline" className="text-xs">
                        {analysis.workflowsNoDisplay.length}
                      </Badge>
                    </h4>
                    <div className="space-y-1">
                      {analysis.workflowsNoDisplay.map((item) => (
                        <div
                          key={item.workflowCode}
                          className="flex items-center justify-between py-1.5 px-3 rounded bg-muted/30 text-sm"
                        >
                          <div className="flex items-center gap-2">
                            <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                              {item.workflowCode}
                            </code>
                            {item.entityName && (
                              <span className="text-xs text-muted-foreground">
                                ({item.entityName})
                              </span>
                            )}
                          </div>
                          <Button variant="ghost" size="sm" className="h-7 text-xs" asChild>
                            <Link href={`/${locale}/dashboard/admin/menu-config/display/new`}>
                              <Plus className="h-3 w-3 mr-1" />
                              {t('createDisplayConfig', { defaultValue: 'Crear display config' })}
                            </Link>
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Mappings without matching workflows */}
                {analysis.mappingsNoWorkflow.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium flex items-center gap-2">
                      {t('mappingsWithoutWorkflows', { defaultValue: 'Mappings sin workflows' })}
                      <Badge variant="outline" className="text-xs">
                        {analysis.mappingsNoWorkflow.length}
                      </Badge>
                    </h4>
                    <div className="space-y-1">
                      {analysis.mappingsNoWorkflow.map((item) => (
                        <div
                          key={item.pattern}
                          className="flex items-center justify-between py-1.5 px-3 rounded bg-muted/30 text-sm"
                        >
                          <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                            {item.pattern}
                          </code>
                          <Button variant="ghost" size="sm" className="h-7 text-xs" asChild>
                            <Link href={`/${locale}/dashboard/admin/workflow-mappings/${item.mappingId}`}>
                              {t('edit', { defaultValue: 'Editar' })}
                            </Link>
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}

export default OrphanDetectionPanel;
