'use client';

/**
 * Create New Assignment Rule — Visual Builder
 * Uses shared components from _shared.tsx to eliminate duplication.
 *
 * @route /[locale]/dashboard/supervisor/assignments/rules/new
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { useMutation } from '@tanstack/react-query';
import {
  Card, CardContent, CardHeader, CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Loader2, ArrowLeft, Settings2 } from 'lucide-react';
import apiClient from '@/core/api/client';
import Link from 'next/link';
import { toast } from 'sonner';
import {
  useEntities, useSupervisorEntities, buildConditions, buildActions,
  ConditionsBuilder, ActionsBuilder, PreviewBanner,
  EMPTY_TREASURY_STATE,
  type TreasuryConditionsState,
} from '../_shared';

// ─── Component ───────────────────────────────────────────────────────────────

export default function NewRulePage() {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations('supervisor.rules');
  const tCommon = useTranslations('common');
  const { data: entities = [] } = useEntities();
  const { filteredEntities, supervisorEntityCode } = useSupervisorEntities(entities);

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [entityCode, setEntityCode] = useState('');
  const [priority, setPriority] = useState(50);
  const [activateImmediately, setActivateImmediately] = useState(false);

  // Auto-fill entity from supervisor profile (once)
  const [entityAutoFilled, setEntityAutoFilled] = useState(false);
  useEffect(() => {
    if (!entityAutoFilled && !entityCode && filteredEntities.length > 0) {
      if (supervisorEntityCode) {
        const match = filteredEntities.find((e) => e.code === supervisorEntityCode);
        if (match) {
          setEntityCode(match.code);
          setEntityAutoFilled(true);
        }
      }
      // If only one entity available, auto-select it
      if (!entityAutoFilled && filteredEntities.length === 1) {
        setEntityCode(filteredEntities[0].code);
        setEntityAutoFilled(true);
      }
    }
  }, [supervisorEntityCode, entityAutoFilled, entityCode, filteredEntities]);

  // Conditions state
  const [selectedWorkflows, setSelectedWorkflows] = useState<string[]>([]);
  const [minAmount, setMinAmount] = useState('');
  const [maxAmount, setMaxAmount] = useState('');
  const [minPriority, setMinPriority] = useState('');

  // Actions state
  const [strategy, setStrategy] = useState<string>('load_balance');
  const [actionSpecializations, setActionSpecializations] = useState<string[]>([]);
  const [maxWorkloadPct, setMaxWorkloadPct] = useState(80);

  // Treasury-specific conditions
  const [treasuryState, setTreasuryState] = useState<TreasuryConditionsState>(EMPTY_TREASURY_STATE);

  // JSON editor
  const [useJsonEditor, setUseJsonEditor] = useState(false);
  const [conditionsJson, setConditionsJson] = useState('{}');
  const [actionsJson, setActionsJson] = useState('{}');
  const [conditionsJsonError, setConditionsJsonError] = useState<string | null>(null);
  const [actionsJsonError, setActionsJsonError] = useState<string | null>(null);

  // Derived
  const selectedEntity = filteredEntities.find((e) => e.code === entityCode);
  const entityType = selectedEntity?.entity_type || '';
  const availableWorkflows = selectedEntity?.workflow_codes || [];

  // Reset workflows + treasury state when entity changes
  useEffect(() => {
    setSelectedWorkflows([]);
    setActionSpecializations([]);
    setTreasuryState(EMPTY_TREASURY_STATE);
  }, [entityCode]);

  // Build current values
  const currentConditions = buildConditions(useJsonEditor, conditionsJson, selectedWorkflows, minAmount, maxAmount, minPriority, treasuryState);
  const currentActions = buildActions(useJsonEditor, actionsJson, strategy, actionSpecializations, maxWorkloadPct);

  // JSON change handler — separate error state per field (#11 fix)
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

  // Create mutation
  const createMutation = useMutation({
    mutationFn: async (data: Record<string, unknown>) => {
      const response = await apiClient.post('/supervisor/rules', data);
      return response.data;
    },
    onSuccess: () => {
      toast.success(t('created'));
      router.push(`/${locale}/dashboard/supervisor/assignments/rules`);
    },
    onError: (err: Error) => {
      toast.error(err.message || tCommon('error'));
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { toast.error(t('nameRequired')); return; }
    if (!entityCode) { toast.error(t('entityRequired')); return; }
    if (useJsonEditor && (conditionsJsonError || actionsJsonError)) {
      toast.error(t('jsonFixBefore'));
      return;
    }

    // entity_type comes from backend EntityResponse — NOT guessed (#2 fix)
    const ent = filteredEntities.find((e) => e.code === entityCode);
    createMutation.mutate({
      name: name.trim(),
      description: description.trim() || undefined,
      entity_type: ent?.entity_type || 'entity',
      entity_id: entityCode,
      conditions: currentConditions,
      actions: currentActions,
      priority,
      status: activateImmediately ? 'active' : 'draft',
    });
  };

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/${locale}/dashboard/supervisor/assignments/rules`}>
          <Button variant="ghost" size="icon"><ArrowLeft className="h-4 w-4" /></Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Settings2 className="h-6 w-6" /> {t('newRule')}
          </h1>
          <p className="text-muted-foreground text-sm">{t('createDescription')}</p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        {/* Basic Info */}
        <Card>
          <CardHeader><CardTitle>{t('basicInfo')}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">{t('name')} *</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t('namePlaceholder')}
                maxLength={200}
              />
              <p className="text-xs text-muted-foreground">{name.length}/200</p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="desc">{t('descriptionLabel')}</Label>
              <Textarea
                id="desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t('descriptionPlaceholder')}
                rows={2}
              />
            </div>

            <div className="space-y-2">
              <Label>{t('entity')} *</Label>
              <Select value={entityCode} onValueChange={setEntityCode}>
                <SelectTrigger>
                  <SelectValue placeholder={t('selectEntity')} />
                </SelectTrigger>
                <SelectContent>
                  {filteredEntities.map((ent) => (
                    <SelectItem key={ent.code} value={ent.code}>
                      {ent.name}
                      {ent.workflow_codes?.length > 0 && (
                        <span className="text-muted-foreground ml-1">
                          ({ent.workflow_codes.length} {t('tramites')})
                        </span>
                      )}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>{t('rulePriority')}</Label>
                <span className="text-sm font-medium">{priority}</span>
              </div>
              <Slider
                value={[priority]}
                onValueChange={(v) => setPriority(v[0])}
                min={1} max={100} step={1}
              />
              <p className="text-xs text-muted-foreground">{t('priorityHelpNew')}</p>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <Label>{t('activateImmediately')}</Label>
                <p className="text-xs text-muted-foreground">{t('activateImmediatelyHelp')}</p>
              </div>
              <Switch checked={activateImmediately} onCheckedChange={setActivateImmediately} />
            </div>
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

        {/* Submit */}
        <div className="flex justify-end gap-3 mt-6">
          <Link href={`/${locale}/dashboard/supervisor/assignments/rules`}>
            <Button type="button" variant="outline">{tCommon('cancel')}</Button>
          </Link>
          <Button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            {activateImmediately ? t('createAndActivate') : t('createAsDraft')}
          </Button>
        </div>
      </form>
    </div>
  );
}
