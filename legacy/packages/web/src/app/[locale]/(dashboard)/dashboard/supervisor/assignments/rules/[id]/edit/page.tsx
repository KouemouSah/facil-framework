'use client';

/**
 * Edit Assignment Rule — Visual Builder
 * Uses shared components from _shared.tsx to eliminate duplication.
 *
 * @route /[locale]/dashboard/supervisor/assignments/rules/[id]/edit
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card, CardContent, CardHeader, CardTitle, CardDescription,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Slider } from '@/components/ui/slider';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Loader2, ArrowLeft, Settings2, AlertCircle } from 'lucide-react';
import apiClient from '@/core/api/client';
import Link from 'next/link';
import { toast } from 'sonner';
import type { AssignmentRule, RuleStatus } from '../../../../types';
import {
  useEntities, useSupervisorEntities, buildConditions, buildActions,
  ConditionsBuilder, ActionsBuilder, PreviewBanner,
  EMPTY_TREASURY_STATE, extractTreasuryState,
  type TreasuryConditionsState,
} from '../../_shared';

// ─── Component ───────────────────────────────────────────────────────────────

export default function EditRulePage() {
  const router = useRouter();
  const params = useParams();
  const locale = useLocale();
  const queryClient = useQueryClient();
  const t = useTranslations('supervisor.rules');
  const tCommon = useTranslations('common');
  const ruleId = params.id as string;

  const { data: entities = [] } = useEntities();
  const { filteredEntities } = useSupervisorEntities(entities);

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [entityCode, setEntityCode] = useState('');
  const [priority, setPriority] = useState(50);
  const [status, setStatus] = useState<RuleStatus>('draft');

  // Conditions
  const [selectedWorkflows, setSelectedWorkflows] = useState<string[]>([]);
  const [minAmount, setMinAmount] = useState('');
  const [maxAmount, setMaxAmount] = useState('');
  const [minPriority, setMinPriority] = useState('');

  // Actions
  const [strategy, setStrategy] = useState<string>('load_balance');
  const [actionSpecializations, setActionSpecializations] = useState<string[]>([]);
  const [maxWorkloadPct, setMaxWorkloadPct] = useState(80);

  // Treasury-specific conditions
  const [treasuryState, setTreasuryState] = useState<TreasuryConditionsState>(EMPTY_TREASURY_STATE);

  // JSON editor — separate errors per field (#11 fix)
  const [useJsonEditor, setUseJsonEditor] = useState(false);
  const [conditionsJson, setConditionsJson] = useState('{}');
  const [actionsJson, setActionsJson] = useState('{}');
  const [conditionsJsonError, setConditionsJsonError] = useState<string | null>(null);
  const [actionsJsonError, setActionsJsonError] = useState<string | null>(null);

  // Fetch existing rule
  const { data: rule, isLoading, isError, error } = useQuery<AssignmentRule>({
    queryKey: ['supervisor', 'rules', ruleId],
    queryFn: async () => {
      const response = await apiClient.get(`/supervisor/rules/${ruleId}`);
      return response.data;
    },
    enabled: !!ruleId,
  });

  // Initialize form when rule loads
  useEffect(() => {
    if (!rule) return;
    setName(rule.name);
    setDescription(rule.description || '');
    setEntityCode(rule.entity_id || '');
    setPriority(rule.priority);
    setStatus(rule.status);

    const c = rule.conditions || {};
    setSelectedWorkflows(c.item_types || []);
    setMinAmount(c.min_amount !== undefined ? String(c.min_amount) : '');
    setMaxAmount(c.max_amount !== undefined ? String(c.max_amount) : '');
    setMinPriority(c.min_priority !== undefined ? String(c.min_priority) : '');
    setTreasuryState(extractTreasuryState(c));

    const a = rule.actions || {};
    setStrategy(a.selection_strategy || 'load_balance');
    setActionSpecializations(a.specializations || []);
    setMaxWorkloadPct(a.max_workload_pct || 80);

    setConditionsJson(JSON.stringify(c, null, 2));
    setActionsJson(JSON.stringify(a, null, 2));
  }, [rule]);

  // Derived
  const selectedEntity = filteredEntities.find((e) => e.code === entityCode);
  const entityType = selectedEntity?.entity_type || rule?.entity_type || '';
  const availableWorkflows = selectedEntity?.workflow_codes || [];

  // Reset workflows + treasury when entity changes (#13 fix — same as create page)
  const [entityInitialized, setEntityInitialized] = useState(false);
  useEffect(() => {
    if (!entityInitialized && rule) {
      setEntityInitialized(true);
      return; // Don't reset on initial load from rule data
    }
    if (entityInitialized) {
      setSelectedWorkflows([]);
      setActionSpecializations([]);
      setTreasuryState(EMPTY_TREASURY_STATE);
    }
  }, [entityCode]); // eslint-disable-line react-hooks/exhaustive-deps

  // Build current values
  const currentConditions = buildConditions(useJsonEditor, conditionsJson, selectedWorkflows, minAmount, maxAmount, minPriority, treasuryState);
  const currentActions = buildActions(useJsonEditor, actionsJson, strategy, actionSpecializations, maxWorkloadPct);

  const handleJsonChange = useCallback((field: 'conditions' | 'actions', value: string) => {
    if (field === 'conditions') {
      setConditionsJson(value);
      try { JSON.parse(value); setConditionsJsonError(null); } catch { setConditionsJsonError(t('jsonInvalid')); }
    } else {
      setActionsJson(value);
      try { JSON.parse(value); setActionsJsonError(null); } catch { setActionsJsonError(t('jsonInvalid')); }
    }
  }, [t]);

  const toggleWorkflow = useCallback((wf: string) => {
    setSelectedWorkflows((prev) => prev.includes(wf) ? prev.filter((w) => w !== wf) : [...prev, wf]);
  }, []);

  const toggleSpecialization = useCallback((wf: string) => {
    setActionSpecializations((prev) => prev.includes(wf) ? prev.filter((w) => w !== wf) : [...prev, wf]);
  }, []);

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: async (data: Record<string, unknown>) => {
      const response = await apiClient.put(`/supervisor/rules/${ruleId}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['supervisor', 'rules'] });
      toast.success(t('updated'));
      router.push(`/${locale}/dashboard/supervisor/assignments/rules`);
    },
    onError: (err: Error) => {
      toast.error(err.message || tCommon('error'));
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { toast.error(t('nameRequired')); return; }
    if (useJsonEditor && (conditionsJsonError || actionsJsonError)) {
      toast.error(t('jsonFixBefore'));
      return;
    }

    // entity_type comes from backend EntityResponse — NOT guessed (#2 fix)
    const ent = filteredEntities.find((e) => e.code === entityCode);
    updateMutation.mutate({
      name: name.trim(),
      description: description.trim() || null,
      entity_type: ent?.entity_type || rule?.entity_type || 'entity',
      entity_id: entityCode || null,
      conditions: currentConditions,
      actions: currentActions,
      priority,
      status,
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
      </div>
    );
  }

  if (isError) {
    return (
      <Card className="border-destructive/50 max-w-3xl mx-auto">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" /> {tCommon('error')}
          </CardTitle>
          <CardDescription>{(error as Error)?.message || t('notFound')}</CardDescription>
        </CardHeader>
        <CardContent>
          <Link href={`/${locale}/dashboard/supervisor/assignments/rules`}>
            <Button variant="outline"><ArrowLeft className="h-4 w-4 mr-2" /> {t('backToList')}</Button>
          </Link>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/${locale}/dashboard/supervisor/assignments/rules`}>
          <Button variant="ghost" size="icon"><ArrowLeft className="h-4 w-4" /></Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Settings2 className="h-6 w-6" /> {t('editRule')}
          </h1>
          <p className="text-muted-foreground text-sm">{rule?.name}</p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        {/* Basic Info */}
        <Card>
          <CardHeader><CardTitle>{t('basicInfo')}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>{t('name')} *</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />
            </div>
            <div className="space-y-2">
              <Label>{t('descriptionLabel')}</Label>
              <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
            </div>
            <div className="space-y-2">
              <Label>{t('entity')}</Label>
              <Select value={entityCode} onValueChange={setEntityCode}>
                <SelectTrigger><SelectValue placeholder={t('selectEntity')} /></SelectTrigger>
                <SelectContent>
                  {filteredEntities.map((ent) => (
                    <SelectItem key={ent.code} value={ent.code}>{ent.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>{t('rulePriority')}</Label>
                <span className="text-sm font-medium">{priority}</span>
              </div>
              <Slider value={[priority]} onValueChange={(v) => setPriority(v[0])} min={1} max={100} step={1} />
            </div>
            <div className="space-y-2">
              <Label>{tCommon('status')}</Label>
              <Select value={status} onValueChange={(v) => setStatus(v as RuleStatus)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">{t('status_active')}</SelectItem>
                  <SelectItem value="inactive">{t('status_inactive')}</SelectItem>
                  <SelectItem value="draft">{t('status_draft')}</SelectItem>
                  <SelectItem value="archived">{t('status_archived')}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Stats (read-only) */}
            {rule && rule.times_applied > 0 && (
              <div className="flex gap-4 p-3 bg-muted rounded-md text-sm">
                <span>{t('applications')}: <strong>{rule.times_applied}</strong></span>
                <span>{t('matches')}: <strong>{rule.times_matched}</strong></span>
                <span>{t('successRate')}: <strong>{(rule.success_rate * 100).toFixed(0)}%</strong></span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Conditions — Shared Component */}
        <ConditionsBuilder
          t={t}
          useJsonEditor={useJsonEditor}
          setUseJsonEditor={setUseJsonEditor}
          conditionsJson={conditionsJson}
          actionsJson={actionsJson}
          onJsonChange={handleJsonChange}
          conditionsJsonError={conditionsJsonError}
          availableWorkflows={availableWorkflows}
          selectedWorkflows={selectedWorkflows}
          toggleWorkflow={toggleWorkflow}
          entityCode={entityCode}
          entityType={entityType}
          minAmount={minAmount}
          setMinAmount={setMinAmount}
          maxAmount={maxAmount}
          setMaxAmount={setMaxAmount}
          minPriority={minPriority}
          setMinPriority={setMinPriority}
          currentConditions={currentConditions}
          currentActions={currentActions}
          treasuryState={treasuryState}
          onTreasuryChange={setTreasuryState}
        />

        {/* Actions — Shared Component */}
        <ActionsBuilder
          t={t}
          useJsonEditor={useJsonEditor}
          actionsJson={actionsJson}
          onJsonChange={handleJsonChange}
          strategy={strategy}
          setStrategy={setStrategy}
          availableWorkflows={availableWorkflows}
          actionSpecializations={actionSpecializations}
          toggleSpecialization={toggleSpecialization}
          maxWorkloadPct={maxWorkloadPct}
          setMaxWorkloadPct={setMaxWorkloadPct}
        />

        {/* Preview — Shared Component */}
        <PreviewBanner t={t} entityCode={entityCode} selectedWorkflows={selectedWorkflows} />

        <div className="flex justify-end gap-3 mt-6">
          <Link href={`/${locale}/dashboard/supervisor/assignments/rules`}>
            <Button type="button" variant="outline">{tCommon('cancel')}</Button>
          </Link>
          <Button type="submit" disabled={updateMutation.isPending}>
            {updateMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            {t('saveChanges')}
          </Button>
        </div>
      </form>
    </div>
  );
}
