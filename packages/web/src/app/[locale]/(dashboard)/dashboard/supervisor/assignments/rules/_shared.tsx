'use client';

/**
 * Shared hooks and components for Assignment Rules pages.
 * Single source — eliminates duplication between new/edit pages.
 *
 * Fixes applied:
 * - Entity type read from backend (not guessed from workflow_codes)
 * - Preview uses server-side count (no client-side amount/priority filter)
 * - Consistent use of apiClient (not fetchClient)
 * - Entity scoping via useAgentProfile
 * - Proper i18n via useTranslations
 * - Treasury-specific conditions (payment_methods, payment_types, has_penalties, entity_location)
 */

import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Code, Info, X, Eye, Banknote } from 'lucide-react';
import apiClient from '@/core/api/client';
import type { RuleConditions, RuleActions } from '../../types';
import { useAgentProfile } from '@/modules/agent-dashboard/hooks/useAgentDashboard';

// ─── Types ───────────────────────────────────────────────────────────────────

export interface Entity {
  code: string;
  name: string;
  entity_type: string; // from backend EntityResponse — NOT guessed
  workflow_codes: string[];
}

export interface EntityLocation {
  id: string;
  location_name: string;
  city: string;
  is_active: boolean;
}

// Treasury constants
const PAYMENT_METHODS = [
  { value: 'cash', labelKey: 'paymentMethodCash' },
  { value: 'bank_transfer', labelKey: 'paymentMethodTransfer' },
  { value: 'mobile_money', labelKey: 'paymentMethodMobile' },
  { value: 'card', labelKey: 'paymentMethodCard' },
  { value: 'bange_wallet', labelKey: 'paymentMethodBange' },
  { value: 'check', labelKey: 'paymentMethodCheck' },
] as const;

const PAYMENT_TYPES = [
  { value: 'full', labelKey: 'paymentTypeFull' },
  { value: 'partial', labelKey: 'paymentTypePartial' },
  { value: 'installment', labelKey: 'paymentTypeInstallment' },
  { value: 'complementary', labelKey: 'paymentTypeComplementary' },
] as const;

// ─── Hooks ───────────────────────────────────────────────────────────────────

/** Fetch all entities via apiClient (consistent with other calls). */
export function useEntities() {
  return useQuery<Entity[]>({
    queryKey: ['entities-with-workflows'],
    queryFn: async () => {
      try {
        const res = await apiClient.get<{ items?: Entity[] } | Entity[]>('/entities/');
        const data = res.data;
        if (Array.isArray(data)) return data;
        return (data as { items?: Entity[] }).items || [];
      } catch { return []; }
    },
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Filter entities to supervisor's scope using agent profile.
 * Returns filteredEntities + supervisorEntityCode for auto-fill.
 */
export function useSupervisorEntities(entities: Entity[]) {
  const { data: agentProfile } = useAgentProfile();
  const supervisorEntityCode = (agentProfile?.entity_code as string) || undefined;

  const filteredEntities = useMemo(() => {
    if (!supervisorEntityCode) return entities;
    const childCodes = (agentProfile?.child_entity_codes as string[]) || [];
    const allowedCodes = [supervisorEntityCode, ...childCodes];
    const filtered = entities.filter((e) => allowedCodes.includes(e.code));
    // Fallback to all entities if none match (safety net)
    return filtered.length > 0 ? filtered : entities;
  }, [entities, supervisorEntityCode, agentProfile?.child_entity_codes]);

  return { filteredEntities, supervisorEntityCode };
}

/** Fetch entity locations for a given entity code. */
export function useEntityLocations(entityCode: string) {
  return useQuery<EntityLocation[]>({
    queryKey: ['entity-locations', entityCode],
    queryFn: async () => {
      try {
        const res = await apiClient.get(`/entity-locations/by-entity/${entityCode}`);
        const data = res.data;
        const items = Array.isArray(data) ? data : (data?.items || data?.locations || []);
        return items.filter((loc: EntityLocation) => loc.is_active);
      } catch { return []; }
    },
    enabled: !!entityCode,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Preview count: uses the backend's server-side count from assignable-items.
 * Only filters by entity_code + workflow_code (the fields actually returned).
 * Amount/priority filtering happens in the rules_engine at runtime, not here.
 */
export function usePreviewCount(entityCode: string, workflowCodes: string[]) {
  return useQuery<number>({
    queryKey: ['rule-preview', entityCode, workflowCodes],
    queryFn: async () => {
      const params = new URLSearchParams({ tab: 'unassigned', page_size: '1' });
      if (entityCode) params.set('entity_code', entityCode);
      const res = await apiClient.get(`/assignments/assignable-items?${params.toString()}`);
      const total: number = res.data?.total ?? 0;
      // If specific workflows are selected, we need to count only those
      if (workflowCodes.length > 0) {
        // Fetch a larger batch to count matching workflows client-side
        const resFull = await apiClient.get(`/assignments/assignable-items?${new URLSearchParams({ tab: 'unassigned', page_size: '200' }).toString()}&entity_code=${entityCode}`);
        const items: Array<{ workflow_code?: string }> = resFull.data?.items || [];
        return items.filter((item) => workflowCodes.includes(item.workflow_code || '')).length;
      }
      return total;
    },
    enabled: !!entityCode,
    staleTime: 30_000,
  });
}

// ─── Build helpers ───────────────────────────────────────────────────────────

export function buildConditions(
  useJsonEditor: boolean,
  conditionsJson: string,
  selectedWorkflows: string[],
  minAmount: string,
  maxAmount: string,
  minPriority: string,
  // Treasury-specific
  treasuryState?: TreasuryConditionsState,
): RuleConditions {
  if (useJsonEditor) {
    try { return JSON.parse(conditionsJson); } catch { return {}; }
  }
  const c: RuleConditions = {};
  if (selectedWorkflows.length > 0) c.item_types = selectedWorkflows;
  if (minAmount) c.min_amount = parseFloat(minAmount);
  if (maxAmount) c.max_amount = parseFloat(maxAmount);
  if (minPriority) c.min_priority = parseInt(minPriority, 10);
  // Treasury-specific conditions
  if (treasuryState) {
    if (treasuryState.paymentMethods.length > 0) c.payment_methods = treasuryState.paymentMethods;
    if (treasuryState.paymentTypes.length > 0) c.payment_types = treasuryState.paymentTypes;
    if (treasuryState.hasPenalties) c.has_penalties = true;
    if (treasuryState.entityLocationId) c.entity_location_id = treasuryState.entityLocationId;
  }
  return c;
}

export function buildActions(
  useJsonEditor: boolean,
  actionsJson: string,
  strategy: string,
  actionSpecializations: string[],
  maxWorkloadPct: number,
): RuleActions {
  if (useJsonEditor) {
    try { return JSON.parse(actionsJson); } catch { return {}; }
  }
  const a: RuleActions = { selection_strategy: strategy as RuleActions['selection_strategy'] };
  if (actionSpecializations.length > 0) a.specializations = actionSpecializations;
  if (maxWorkloadPct < 100) a.max_workload_pct = maxWorkloadPct;
  return a;
}

// ─── Treasury conditions state ──────────────────────────────────────────────

export interface TreasuryConditionsState {
  paymentMethods: string[];
  paymentTypes: string[];
  hasPenalties: boolean;
  entityLocationId: string;
}

export const EMPTY_TREASURY_STATE: TreasuryConditionsState = {
  paymentMethods: [],
  paymentTypes: [],
  hasPenalties: false,
  entityLocationId: '',
};

/** Extract treasury state from RuleConditions (for edit page initialization). */
export function extractTreasuryState(conditions: RuleConditions): TreasuryConditionsState {
  return {
    paymentMethods: conditions.payment_methods || [],
    paymentTypes: conditions.payment_types || [],
    hasPenalties: conditions.has_penalties || false,
    entityLocationId: conditions.entity_location_id || '',
  };
}

// ─── Shared Form Components ─────────────────────────────────────────────────

interface ConditionsBuilderProps {
  t: (key: string) => string;
  useJsonEditor: boolean;
  setUseJsonEditor: (v: boolean) => void;
  conditionsJson: string;
  actionsJson: string;
  onJsonChange: (field: 'conditions' | 'actions', value: string) => void;
  conditionsJsonError: string | null;
  availableWorkflows: string[];
  selectedWorkflows: string[];
  toggleWorkflow: (wf: string) => void;
  entityCode: string;
  entityType: string;
  minAmount: string;
  setMinAmount: (v: string) => void;
  maxAmount: string;
  setMaxAmount: (v: string) => void;
  minPriority: string;
  setMinPriority: (v: string) => void;
  // For syncing JSON when toggling
  currentConditions: RuleConditions;
  currentActions: RuleActions;
  // Treasury-specific
  treasuryState: TreasuryConditionsState;
  onTreasuryChange: (state: TreasuryConditionsState) => void;
}

export function ConditionsBuilder({
  t, useJsonEditor, setUseJsonEditor,
  conditionsJson, onJsonChange, conditionsJsonError,
  availableWorkflows, selectedWorkflows, toggleWorkflow, entityCode, entityType,
  minAmount, setMinAmount, maxAmount, setMaxAmount, minPriority, setMinPriority,
  currentConditions, currentActions,
  treasuryState, onTreasuryChange,
}: ConditionsBuilderProps) {
  const isTreasury = entityType === 'treasury';
  const { data: locations = [] } = useEntityLocations(isTreasury ? entityCode : '');

  return (
    <Card className="mt-4">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>{t('conditionsTitle')}</CardTitle>
            <CardDescription>{t('conditionsDescription')}</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Label className="text-xs">JSON</Label>
            <Switch
              checked={useJsonEditor}
              onCheckedChange={(checked) => {
                setUseJsonEditor(checked);
                if (checked) {
                  onJsonChange('conditions', JSON.stringify(currentConditions, null, 2));
                  onJsonChange('actions', JSON.stringify(currentActions, null, 2));
                }
              }}
            />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {useJsonEditor ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Code className="h-3 w-3" /> {t('jsonEditor')} — {t('conditionsTitle')}
            </div>
            <Textarea
              value={conditionsJson}
              onChange={(e) => onJsonChange('conditions', e.target.value)}
              className="font-mono text-sm" rows={6}
            />
            {conditionsJsonError && <p className="text-xs text-destructive">{conditionsJsonError}</p>}
          </div>
        ) : (
          <div className="space-y-4">
            {/* Workflow types — only for non-treasury entities */}
            {!isTreasury && (
              <>
                {availableWorkflows.length > 0 ? (
                  <div className="space-y-2">
                    <Label>{t('workflowTypes')}</Label>
                    <div className="flex flex-wrap gap-2">
                      {availableWorkflows.map((wf) => (
                        <Badge
                          key={wf}
                          variant={selectedWorkflows.includes(wf) ? 'default' : 'outline'}
                          className="cursor-pointer"
                          onClick={() => toggleWorkflow(wf)}
                        >
                          {wf.replace(/_/g, ' ')}
                          {selectedWorkflows.includes(wf) && <X className="h-3 w-3 ml-1" />}
                        </Badge>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {selectedWorkflows.length === 0
                        ? t('noWorkflowSelected')
                        : `${selectedWorkflows.length} ${t('selected')}`}
                    </p>
                  </div>
                ) : entityCode ? (
                  <div className="flex items-start gap-2 p-3 bg-muted rounded-md">
                    <Info className="h-4 w-4 mt-0.5 text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">{t('entityNoWorkflows')}</p>
                  </div>
                ) : null}
              </>
            )}

            {/* Treasury-specific conditions */}
            {isTreasury && entityCode && (
              <TreasuryConditionsSection
                t={t}
                state={treasuryState}
                onChange={onTreasuryChange}
                locations={locations}
              />
            )}

            {/* Common conditions: amount + priority */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label>{t('minAmount')}</Label>
                <Input
                  type="number" min={0}
                  value={minAmount}
                  onChange={(e) => setMinAmount(e.target.value)}
                  placeholder={t('optional')}
                />
              </div>
              <div className="space-y-1">
                <Label>{t('maxAmount')}</Label>
                <Input
                  type="number" min={0}
                  value={maxAmount}
                  onChange={(e) => setMaxAmount(e.target.value)}
                  placeholder={t('optional')}
                />
              </div>
            </div>

            <div className="space-y-1">
              <Label>{t('minRequestPriority')}</Label>
              <Input
                type="number" min={1} max={10}
                value={minPriority}
                onChange={(e) => setMinPriority(e.target.value)}
                placeholder={`${t('optional')} — ${t('minRequestPriorityHelp')}`}
              />
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Treasury Conditions Section ────────────────────────────────────────────

interface TreasuryConditionsSectionProps {
  t: (key: string) => string;
  state: TreasuryConditionsState;
  onChange: (state: TreasuryConditionsState) => void;
  locations: EntityLocation[];
}

function TreasuryConditionsSection({ t, state, onChange, locations }: TreasuryConditionsSectionProps) {
  const togglePaymentMethod = (method: string) => {
    const next = state.paymentMethods.includes(method)
      ? state.paymentMethods.filter((m) => m !== method)
      : [...state.paymentMethods, method];
    onChange({ ...state, paymentMethods: next });
  };

  const togglePaymentType = (type: string) => {
    const next = state.paymentTypes.includes(type)
      ? state.paymentTypes.filter((t) => t !== type)
      : [...state.paymentTypes, type];
    onChange({ ...state, paymentTypes: next });
  };

  return (
    <div className="space-y-4 rounded-lg border border-amber-200 bg-amber-50/50 dark:border-amber-900 dark:bg-amber-950/20 p-4">
      <div className="flex items-center gap-2">
        <Banknote className="h-4 w-4 text-amber-600" />
        <Label className="font-semibold text-amber-800 dark:text-amber-400">{t('treasuryConditions')}</Label>
      </div>
      <p className="text-xs text-muted-foreground">{t('treasuryConditionsHelp')}</p>

      {/* Payment Methods */}
      <div className="space-y-2">
        <Label className="text-sm">{t('paymentMethod')}</Label>
        <div className="flex flex-wrap gap-2">
          {PAYMENT_METHODS.map(({ value, labelKey }) => (
            <Badge
              key={value}
              variant={state.paymentMethods.includes(value) ? 'default' : 'outline'}
              className="cursor-pointer"
              onClick={() => togglePaymentMethod(value)}
            >
              {t(labelKey)}
              {state.paymentMethods.includes(value) && <X className="h-3 w-3 ml-1" />}
            </Badge>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          {state.paymentMethods.length === 0
            ? t('noPaymentMethodSelected')
            : `${state.paymentMethods.length} ${t('selected')}`}
        </p>
      </div>

      {/* Payment Types */}
      <div className="space-y-2">
        <Label className="text-sm">{t('paymentType')}</Label>
        <div className="flex flex-wrap gap-2">
          {PAYMENT_TYPES.map(({ value, labelKey }) => (
            <Badge
              key={value}
              variant={state.paymentTypes.includes(value) ? 'default' : 'outline'}
              className="cursor-pointer"
              onClick={() => togglePaymentType(value)}
            >
              {t(labelKey)}
              {state.paymentTypes.includes(value) && <X className="h-3 w-3 ml-1" />}
            </Badge>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          {state.paymentTypes.length === 0
            ? t('noPaymentTypeSelected')
            : `${state.paymentTypes.length} ${t('selected')}`}
        </p>
      </div>

      {/* Has Penalties */}
      <div className="flex items-center gap-3">
        <Checkbox
          id="has-penalties"
          checked={state.hasPenalties}
          onCheckedChange={(checked) => onChange({ ...state, hasPenalties: !!checked })}
        />
        <div>
          <Label htmlFor="has-penalties" className="text-sm cursor-pointer">{t('hasPenalties')}</Label>
          <p className="text-xs text-muted-foreground">{t('hasPenaltiesHelp')}</p>
        </div>
      </div>

      {/* Entity Location */}
      {locations.length > 0 && (
        <div className="space-y-2">
          <Label className="text-sm">{t('entityLocation')}</Label>
          <Select
            value={state.entityLocationId}
            onValueChange={(v) => onChange({ ...state, entityLocationId: v === '_all' ? '' : v })}
          >
            <SelectTrigger>
              <SelectValue placeholder={t('allLocations')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="_all">{t('allLocations')}</SelectItem>
              {locations.map((loc) => (
                <SelectItem key={loc.id} value={loc.id}>
                  {loc.location_name} — {loc.city}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">{t('entityLocationHelp')}</p>
        </div>
      )}
    </div>
  );
}

// ─── Actions Builder ────────────────────────────────────────────────────────

interface ActionsBuilderProps {
  t: (key: string) => string;
  useJsonEditor: boolean;
  actionsJson: string;
  onJsonChange: (field: 'conditions' | 'actions', value: string) => void;
  strategy: string;
  setStrategy: (v: string) => void;
  availableWorkflows: string[];
  actionSpecializations: string[];
  toggleSpecialization: (wf: string) => void;
  maxWorkloadPct: number;
  setMaxWorkloadPct: (v: number) => void;
}

export function ActionsBuilder({
  t, useJsonEditor, actionsJson, onJsonChange,
  strategy, setStrategy,
  availableWorkflows, actionSpecializations, toggleSpecialization,
  maxWorkloadPct, setMaxWorkloadPct,
}: ActionsBuilderProps) {
  return (
    <Card className="mt-4">
      <CardHeader>
        <CardTitle>{t('actionsTitle')}</CardTitle>
        <CardDescription>{t('actionsDescription')}</CardDescription>
      </CardHeader>
      <CardContent>
        {useJsonEditor ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Code className="h-3 w-3" /> {t('jsonEditor')} — {t('actionsTitle')}
            </div>
            <Textarea
              value={actionsJson}
              onChange={(e) => onJsonChange('actions', e.target.value)}
              className="font-mono text-sm" rows={6}
            />
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{t('assignmentStrategy')}</Label>
              <Select value={strategy} onValueChange={setStrategy}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="load_balance">{t('strategyLoadBalance')}</SelectItem>
                  <SelectItem value="round_robin">{t('strategyRoundRobin')}</SelectItem>
                  <SelectItem value="specialization">{t('strategySpecialization')}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {availableWorkflows.length > 0 && (
              <div className="space-y-2">
                <Label>{t('requiredSpecializations')}</Label>
                <div className="flex flex-wrap gap-2">
                  {availableWorkflows.map((wf) => (
                    <Badge
                      key={wf}
                      variant={actionSpecializations.includes(wf) ? 'default' : 'outline'}
                      className="cursor-pointer"
                      onClick={() => toggleSpecialization(wf)}
                    >
                      {wf.replace(/_/g, ' ')}
                      {actionSpecializations.includes(wf) && <X className="h-3 w-3 ml-1" />}
                    </Badge>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">{t('requiredSpecializationsHelp')}</p>
              </div>
            )}

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>{t('maxAgentWorkload')}</Label>
                <span className="text-sm font-medium">{maxWorkloadPct}%</span>
              </div>
              <Slider
                value={[maxWorkloadPct]}
                onValueChange={(v) => setMaxWorkloadPct(v[0])}
                min={10} max={100} step={5}
              />
              <p className="text-xs text-muted-foreground">{t('maxAgentWorkloadHelp')}</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface PreviewBannerProps {
  t: (key: string, values?: Record<string, string | number>) => string;
  entityCode: string;
  selectedWorkflows: string[];
}

export function PreviewBanner({ t, entityCode, selectedWorkflows }: PreviewBannerProps) {
  const { data: previewCount, isFetching } = usePreviewCount(entityCode, selectedWorkflows);

  if (!entityCode) return null;

  return (
    <Card className="mt-4 border-primary/20 bg-primary/5">
      <CardContent className="py-3">
        <div className="flex items-center gap-2 text-sm">
          <Eye className="h-4 w-4 text-primary" />
          {isFetching ? (
            <span className="text-muted-foreground">{t('previewCalculating')}</span>
          ) : (
            <span>
              {t('previewResult', { count: previewCount ?? 0 })}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
