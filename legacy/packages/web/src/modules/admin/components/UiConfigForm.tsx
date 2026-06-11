'use client';

/**
 * UiConfigForm - Structured form for ui_config
 *
 * Provides controls for known keys (theme, table_density, auto_refresh_interval)
 * plus a collapsible JSON textarea for unknown/extra keys.
 * Roundtrips unknown keys without loss.
 *
 * @module admin/components
 * @date 2026-02-17
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslations } from 'next-intl';
import { z } from 'zod';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Palette, ChevronDown, AlertCircle } from 'lucide-react';

// =============================================================================
// ZOD SCHEMA (exported for reuse)
// =============================================================================

export const uiConfigSchema = z.object({
  theme: z.enum(['default', 'compact']).optional().default('default'),
  table_density: z.enum(['comfortable', 'compact']).optional().default('comfortable'),
  auto_refresh_interval: z.number().int().min(0).max(3600).optional().default(0),
}).passthrough();

// =============================================================================
// TYPES
// =============================================================================

const KNOWN_KEYS = ['theme', 'table_density', 'auto_refresh_interval'] as const;

interface KnownFields {
  theme: 'default' | 'compact';
  table_density: 'comfortable' | 'compact';
  auto_refresh_interval: number;
}

const DEFAULT_KNOWN: KnownFields = {
  theme: 'default',
  table_density: 'comfortable',
  auto_refresh_interval: 0,
};

interface UiConfigFormProps {
  initialConfig: Record<string, unknown> | null;
  onChange: (config: Record<string, unknown>, isDirty: boolean) => void;
  isSaving?: boolean;
  disabled?: boolean;
}

// =============================================================================
// HELPERS
// =============================================================================

function extractKnownFields(raw: Record<string, unknown> | null): {
  known: KnownFields;
  extra: Record<string, unknown>;
} {
  if (!raw) return { known: { ...DEFAULT_KNOWN }, extra: {} };

  const known: KnownFields = {
    theme: raw.theme === 'compact' ? 'compact' : 'default',
    table_density: raw.table_density === 'compact' ? 'compact' : 'comfortable',
    auto_refresh_interval:
      typeof raw.auto_refresh_interval === 'number'
        ? Math.max(0, Math.min(3600, raw.auto_refresh_interval))
        : 0,
  };

  const extra: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(raw)) {
    if (!(KNOWN_KEYS as readonly string[]).includes(k)) {
      extra[k] = v;
    }
  }

  return { known, extra };
}

function serializeConfig(
  known: KnownFields,
  extraJson: string
): Record<string, unknown> {
  let extra: Record<string, unknown> = {};
  try {
    const parsed = JSON.parse(extraJson);
    if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
      extra = parsed;
    }
  } catch {
    // Invalid JSON — ignore extra
  }
  // Known fields override extra on conflict
  return { ...extra, ...known };
}

// =============================================================================
// COMPONENT
// =============================================================================

export function UiConfigForm({
  initialConfig,
  onChange,
  isSaving = false,
  disabled = false,
}: UiConfigFormProps) {
  const t = useTranslations('admin.menuConfig.roleConfig');

  // Parse initial
  const { known: initialKnown, extra: initialExtra } = extractKnownFields(initialConfig);
  const initialExtraJson = Object.keys(initialExtra).length > 0
    ? JSON.stringify(initialExtra, null, 2)
    : '{}';

  // State
  const [known, setKnown] = useState<KnownFields>(initialKnown);
  const [extraJson, setExtraJson] = useState(initialExtraJson);
  const [extraJsonError, setExtraJsonError] = useState<string | null>(null);
  const [extraOpen, setExtraOpen] = useState(Object.keys(initialExtra).length > 0);

  // For dirty check
  const initialRef = useRef(JSON.stringify(serializeConfig(initialKnown, initialExtraJson)));

  // Re-init when initialConfig changes
  useEffect(() => {
    const { known: k, extra: e } = extractKnownFields(initialConfig);
    const ej = Object.keys(e).length > 0 ? JSON.stringify(e, null, 2) : '{}';
    setKnown(k);
    setExtraJson(ej);
    setExtraJsonError(null);
    setExtraOpen(Object.keys(e).length > 0);
    initialRef.current = JSON.stringify(serializeConfig(k, ej));
  }, [initialConfig]);

  // Notify parent on change
  useEffect(() => {
    const config = serializeConfig(known, extraJson);
    const isDirty = JSON.stringify(config) !== initialRef.current;
    onChange(config, isDirty);
  }, [known, extraJson, onChange]);

  const handleKnownChange = useCallback(<K extends keyof KnownFields>(
    key: K,
    value: KnownFields[K]
  ) => {
    setKnown((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleExtraChange = useCallback((value: string) => {
    setExtraJson(value);
    try {
      const parsed = JSON.parse(value);
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        setExtraJsonError(t('uiForm.mustBeObject', { defaultValue: 'Debe ser un objeto JSON' }));
      } else {
        setExtraJsonError(null);
      }
    } catch (e) {
      setExtraJsonError(e instanceof Error ? e.message : t('uiForm.invalidJson', { defaultValue: 'JSON inválido' }));
    }
  }, [t]);

  const isDisabled = disabled || isSaving;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Palette className="h-4 w-4" />
          {t('uiForm.title', { defaultValue: 'Preferencias de Interfaz' })}
        </CardTitle>
        <CardDescription>
          {t('uiForm.description', {
            defaultValue: 'Configura el tema, densidad y opciones de interfaz para este rol.',
          })}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Theme */}
        <div className="flex items-center justify-between rounded-lg border p-3">
          <div className="space-y-0.5">
            <Label className="text-sm font-medium">
              {t('uiForm.theme', { defaultValue: 'Tema' })}
            </Label>
            <p className="text-xs text-muted-foreground">
              {t('uiForm.themeDescription', {
                defaultValue: 'Aspecto visual del dashboard',
              })}
            </p>
          </div>
          <Select
            value={known.theme}
            onValueChange={(v) => handleKnownChange('theme', v as KnownFields['theme'])}
            disabled={isDisabled}
          >
            <SelectTrigger className="h-8 w-[140px] text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="default">
                {t('uiForm.themeDefault', { defaultValue: 'Predeterminado' })}
              </SelectItem>
              <SelectItem value="compact">
                {t('uiForm.themeCompact', { defaultValue: 'Compacto' })}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Table Density */}
        <div className="flex items-center justify-between rounded-lg border p-3">
          <div className="space-y-0.5">
            <Label className="text-sm font-medium">
              {t('uiForm.tableDensity', { defaultValue: 'Densidad de Tabla' })}
            </Label>
            <p className="text-xs text-muted-foreground">
              {t('uiForm.tableDensityDescription', {
                defaultValue: 'Espaciado entre filas en listas y tablas',
              })}
            </p>
          </div>
          <Select
            value={known.table_density}
            onValueChange={(v) =>
              handleKnownChange('table_density', v as KnownFields['table_density'])
            }
            disabled={isDisabled}
          >
            <SelectTrigger className="h-8 w-[140px] text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="comfortable">
                {t('uiForm.tableDensityComfortable', { defaultValue: 'Cómodo' })}
              </SelectItem>
              <SelectItem value="compact">
                {t('uiForm.tableDensityCompact', { defaultValue: 'Compacto' })}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Auto Refresh Interval */}
        <div className="flex items-center justify-between rounded-lg border p-3">
          <div className="space-y-0.5">
            <Label className="text-sm font-medium">
              {t('uiForm.autoRefreshInterval', {
                defaultValue: 'Intervalo de Actualización',
              })}
            </Label>
            <p className="text-xs text-muted-foreground">
              {t('uiForm.autoRefreshDescription', {
                defaultValue: 'Segundos entre actualizaciones automáticas (0 = desactivado)',
              })}
            </p>
          </div>
          <Input
            type="number"
            min={0}
            max={3600}
            value={known.auto_refresh_interval}
            onChange={(e) => {
              const val = Math.max(0, Math.min(3600, parseInt(e.target.value) || 0));
              handleKnownChange('auto_refresh_interval', val);
            }}
            className="h-8 w-[100px] text-sm text-right"
            disabled={isDisabled}
          />
        </div>

        {/* Extra JSON (collapsible) */}
        <Collapsible open={extraOpen} onOpenChange={setExtraOpen}>
          <CollapsibleTrigger className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors w-full py-2">
            <ChevronDown
              className={`h-4 w-4 transition-transform ${extraOpen ? 'rotate-0' : '-rotate-90'}`}
            />
            {t('uiForm.additionalJson', {
              defaultValue: 'Parámetros Adicionales (JSON)',
            })}
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-2 pt-1">
            <p className="text-xs text-muted-foreground">
              {t('uiForm.additionalJsonDescription', {
                defaultValue:
                  'Claves adicionales almacenadas como JSON libre. No se eliminan al guardar.',
              })}
            </p>
            <Textarea
              value={extraJson}
              onChange={(e) => handleExtraChange(e.target.value)}
              className="font-mono text-sm min-h-[100px]"
              disabled={isDisabled}
              placeholder="{}"
            />
            {extraJsonError && (
              <p className="text-sm text-destructive flex items-center gap-1">
                <AlertCircle className="h-3.5 w-3.5" />
                {extraJsonError}
              </p>
            )}
          </CollapsibleContent>
        </Collapsible>
      </CardContent>
    </Card>
  );
}

export default UiConfigForm;
