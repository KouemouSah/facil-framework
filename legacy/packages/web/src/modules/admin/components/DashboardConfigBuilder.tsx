'use client';

/**
 * DashboardConfigBuilder - Visual widget builder for dashboard_config
 *
 * Replaces raw JSON textarea with a DnD sortable list of widgets.
 * Each widget has: grip handle, label, size selector, visibility toggle.
 *
 * @module admin/components
 * @date 2026-02-17
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useTranslations } from 'next-intl';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { z } from 'zod';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  GripVertical,
  ChevronUp,
  ChevronDown,
  LayoutDashboard,
  Eye,
  EyeOff,
} from 'lucide-react';
import { WIDGET_REGISTRY, DEFAULT_ENTITY_WIDGETS } from '@/modules/agent-dashboard/components/widgets/WidgetRegistry';
import type { DashboardConfig, DashboardLayout, WidgetConfig, WidgetSize } from '@/modules/agent-dashboard/types/menu-config';

// =============================================================================
// ZOD SCHEMA (exported for reuse in page.tsx)
// Derived from canonical WidgetSize type to prevent divergence
// =============================================================================

const WIDGET_SIZES: readonly [WidgetSize, ...WidgetSize[]] = ['small', 'medium', 'large', 'full'];

export const dashboardConfigSchema = z.object({
  version: z.string().default('1.0'),
  layout: z.enum(['grid', 'list', 'custom']).default('grid'),
  widgets: z.array(z.object({
    id: z.string().min(1),
    visible: z.boolean(),
    position: z.number().int().nonnegative(),
    size: z.enum(WIDGET_SIZES),
  })),
});

// =============================================================================
// WIDGET LABELS (fallback keys — i18n labels built in component via useMemo)
// =============================================================================

const WIDGET_LABEL_KEYS: Record<string, string> = {
  urgent_requests: 'Solicitudes Urgentes',
  today_appointments: 'Citas de Hoy',
  workflow_distribution: 'Distribución Workflows',
  alerts: 'Alertas',
  system_alerts: 'Alertas del Sistema',
  personal_stats: 'Estadísticas Personales',
  team_workload: 'Carga del Equipo',
  escalations: 'Escalaciones',
  pending_payments: 'Pagos Pendientes',
  anomaly_summary: 'Resumen de Anomalías',
  calendar_week: 'Calendario Semanal',
  calendar_slots: 'Slots del Calendario',
};

const SIZE_OPTIONS: { value: WidgetSize; label: string }[] = [
  { value: 'small', label: 'S' },
  { value: 'medium', label: 'M' },
  { value: 'large', label: 'L' },
  { value: 'full', label: 'Full' },
];

// =============================================================================
// TYPES
// =============================================================================

interface WidgetRow {
  id: string;
  visible: boolean;
  size: WidgetSize;
}

interface DashboardConfigBuilderProps {
  initialConfig: Record<string, unknown> | null;
  onChange: (config: DashboardConfig, isDirty: boolean) => void;
  isSaving?: boolean;
  disabled?: boolean;
}

// =============================================================================
// HELPERS
// =============================================================================

const REGISTRY_IDS = Object.keys(WIDGET_REGISTRY);

function mergeWidgetsWithRegistry(configWidgets?: WidgetConfig[]): WidgetRow[] {
  // Start with ordered config widgets that exist in registry
  const ordered: WidgetRow[] = (configWidgets ?? [])
    .filter((w) => REGISTRY_IDS.includes(w.id))
    .map((w) => ({ id: w.id, visible: w.visible, size: w.size }));

  // Append registry widgets not in config (hidden by default)
  const inConfig = new Set(ordered.map((r) => r.id));
  for (const id of REGISTRY_IDS) {
    if (!inConfig.has(id)) {
      ordered.push({ id, visible: false, size: 'medium' });
    }
  }
  return ordered;
}

function parseDashboardConfig(raw: Record<string, unknown> | null): {
  layout: DashboardLayout;
  widgets: WidgetRow[];
} {
  if (!raw) {
    return {
      layout: 'grid',
      widgets: mergeWidgetsWithRegistry(DEFAULT_ENTITY_WIDGETS),
    };
  }
  const result = dashboardConfigSchema.safeParse(raw);
  if (result.success) {
    return {
      layout: result.data.layout,
      widgets: mergeWidgetsWithRegistry(result.data.widgets as WidgetConfig[]),
    };
  }
  // Fallback: try to extract what we can
  const layout = (['grid', 'list', 'custom'] as const).includes(raw.layout as DashboardLayout)
    ? (raw.layout as DashboardLayout)
    : 'grid';
  const widgets = Array.isArray(raw.widgets)
    ? mergeWidgetsWithRegistry(raw.widgets as WidgetConfig[])
    : mergeWidgetsWithRegistry(DEFAULT_ENTITY_WIDGETS);
  return { layout, widgets };
}

function serialize(layout: DashboardLayout, rows: WidgetRow[]): DashboardConfig {
  return {
    version: '1.0',
    layout,
    widgets: rows.map((r, i) => ({
      id: r.id,
      visible: r.visible,
      position: i + 1,
      size: r.size,
    })),
  };
}

// =============================================================================
// SORTABLE WIDGET ROW
// =============================================================================

interface SortableWidgetRowProps {
  row: WidgetRow;
  index: number;
  totalCount: number;
  label: string;
  onToggleVisible: () => void;
  onChangeSize: (size: WidgetSize) => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  disabled?: boolean;
}

function SortableWidgetRow({
  row,
  index,
  totalCount,
  label,
  onToggleVisible,
  onChangeSize,
  onMoveUp,
  onMoveDown,
  disabled,
}: SortableWidgetRowProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: row.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 1000 : ('auto' as const),
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-3 p-2.5 rounded-md border bg-card ${
        isDragging ? 'shadow-lg ring-2 ring-primary' : ''
      } ${!row.visible ? 'opacity-60' : ''}`}
    >
      {/* Drag Handle */}
      <button
        type="button"
        className="cursor-grab active:cursor-grabbing touch-none shrink-0"
        disabled={disabled}
        {...attributes}
        {...listeners}
      >
        <GripVertical className="h-4 w-4 text-muted-foreground" />
      </button>

      {/* Position number */}
      <span className="text-xs text-muted-foreground w-5 text-center shrink-0">
        {index + 1}
      </span>

      {/* Widget label */}
      <span className="flex-1 text-sm truncate">
        {label}
      </span>

      {/* Size selector */}
      <Select
        value={row.size}
        onValueChange={(v) => onChangeSize(v as WidgetSize)}
        disabled={disabled}
      >
        <SelectTrigger className="h-7 w-[70px] text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {SIZE_OPTIONS.map((opt) => (
            <SelectItem key={opt.value} value={opt.value} className="text-xs">
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Visible toggle */}
      <Switch
        checked={row.visible}
        onCheckedChange={onToggleVisible}
        disabled={disabled}
        className="shrink-0"
      />

      {/* Arrow controls */}
      <div className="flex items-center gap-0.5 shrink-0">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={onMoveUp}
          disabled={disabled || index === 0}
        >
          <ChevronUp className="h-3 w-3" />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={onMoveDown}
          disabled={disabled || index === totalCount - 1}
        >
          <ChevronDown className="h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function DashboardConfigBuilder({
  initialConfig,
  onChange,
  isSaving = false,
  disabled = false,
}: DashboardConfigBuilderProps) {
  const t = useTranslations('admin.menuConfig.roleConfig');

  // Build i18n-aware labels (with Spanish fallbacks from WIDGET_LABEL_KEYS)
  const widgetLabels = useMemo(() => {
    const labels: Record<string, string> = {};
    for (const [id, fallback] of Object.entries(WIDGET_LABEL_KEYS)) {
      labels[id] = t(`dashboardBuilder.widgets.${id}`, { defaultValue: fallback });
    }
    return labels;
  }, [t]);

  const layoutOptions = useMemo(() => [
    { value: 'grid' as DashboardLayout, label: t('dashboardBuilder.layoutGrid', { defaultValue: 'Cuadrícula' }) },
    { value: 'list' as DashboardLayout, label: t('dashboardBuilder.layoutList', { defaultValue: 'Lista' }) },
    { value: 'custom' as DashboardLayout, label: t('dashboardBuilder.layoutCustom', { defaultValue: 'Personalizado' }) },
  ], [t]);

  // Parse initial config
  const parsed = useMemo(() => parseDashboardConfig(initialConfig), [initialConfig]);

  // State
  const [layout, setLayout] = useState<DashboardLayout>(parsed.layout);
  const [widgetRows, setWidgetRows] = useState<WidgetRow[]>(parsed.widgets);

  // Track initial serialized form for dirty check
  const initialRef = useRef<string>(JSON.stringify(serialize(parsed.layout, parsed.widgets)));

  // Re-init when initialConfig changes (e.g. after save)
  useEffect(() => {
    const p = parseDashboardConfig(initialConfig);
    setLayout(p.layout);
    setWidgetRows(p.widgets);
    initialRef.current = JSON.stringify(serialize(p.layout, p.widgets));
  }, [initialConfig]);

  // Notify parent on change
  useEffect(() => {
    const config = serialize(layout, widgetRows);
    const isDirty = JSON.stringify(config) !== initialRef.current;
    onChange(config, isDirty);
  }, [layout, widgetRows, onChange]);

  // DnD sensors
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      setWidgetRows((rows) => {
        const oldIndex = rows.findIndex((r) => r.id === active.id);
        const newIndex = rows.findIndex((r) => r.id === over.id);
        return arrayMove(rows, oldIndex, newIndex);
      });
    }
  }, []);

  const handleToggleVisible = useCallback((id: string) => {
    setWidgetRows((rows) =>
      rows.map((r) => (r.id === id ? { ...r, visible: !r.visible } : r))
    );
  }, []);

  const handleChangeSize = useCallback((id: string, size: WidgetSize) => {
    setWidgetRows((rows) =>
      rows.map((r) => (r.id === id ? { ...r, size } : r))
    );
  }, []);

  const handleMoveUp = useCallback((index: number) => {
    if (index <= 0) return;
    setWidgetRows((rows) => arrayMove(rows, index, index - 1));
  }, []);

  const handleMoveDown = useCallback((index: number) => {
    setWidgetRows((rows) => {
      if (index >= rows.length - 1) return rows;
      return arrayMove(rows, index, index + 1);
    });
  }, []);

  const visibleCount = widgetRows.filter((r) => r.visible).length;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <LayoutDashboard className="h-4 w-4" />
              {t('dashboardBuilder.widgetList', { defaultValue: 'Widgets del Dashboard' })}
              <Badge variant="secondary">
                {visibleCount}/{widgetRows.length}
              </Badge>
            </CardTitle>
            <CardDescription className="mt-1">
              {t('dashboardBuilder.widgetListDescription', {
                defaultValue: 'Arrastra para reordenar. El orden define la posición en el dashboard.',
              })}
            </CardDescription>
          </div>

          {/* Layout selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {t('dashboardBuilder.layout', { defaultValue: 'Diseño' })}:
            </span>
            <Select
              value={layout}
              onValueChange={(v) => setLayout(v as DashboardLayout)}
              disabled={disabled || isSaving}
            >
              <SelectTrigger className="h-8 w-[130px] text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {layoutOptions.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value} className="text-xs">
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Column headers */}
        <div className="flex items-center gap-3 px-2.5 pb-2 text-xs text-muted-foreground border-b mb-2">
          <span className="w-4" /> {/* grip */}
          <span className="w-5 text-center">#</span>
          <span className="flex-1">Widget</span>
          <span className="w-[70px] text-center">
            {t('dashboardBuilder.size', { defaultValue: 'Tamaño' })}
          </span>
          <span className="w-9 text-center">
            <Eye className="h-3 w-3 inline" />
          </span>
          <span className="w-[52px]" /> {/* arrows */}
        </div>

        {/* Sortable widget list */}
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={widgetRows.map((r) => r.id)}
            strategy={verticalListSortingStrategy}
          >
            <div className="space-y-1.5">
              {widgetRows.map((row, index) => (
                <SortableWidgetRow
                  key={row.id}
                  row={row}
                  index={index}
                  totalCount={widgetRows.length}
                  label={widgetLabels[row.id] ?? row.id}
                  onToggleVisible={() => handleToggleVisible(row.id)}
                  onChangeSize={(size) => handleChangeSize(row.id, size)}
                  onMoveUp={() => handleMoveUp(index)}
                  onMoveDown={() => handleMoveDown(index)}
                  disabled={disabled || isSaving}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>

        {/* Quick actions */}
        <div className="flex items-center gap-2 mt-3 pt-3 border-t">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setWidgetRows((rows) => rows.map((r) => ({ ...r, visible: true })))}
            disabled={disabled || isSaving || visibleCount === widgetRows.length}
          >
            <Eye className="h-3 w-3 mr-1" />
            {t('dashboardBuilder.showAll', { defaultValue: 'Mostrar Todos' })}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setWidgetRows((rows) => rows.map((r) => ({ ...r, visible: false })))}
            disabled={disabled || isSaving || visibleCount === 0}
          >
            <EyeOff className="h-3 w-3 mr-1" />
            {t('dashboardBuilder.hideAll', { defaultValue: 'Ocultar Todos' })}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              const p = parseDashboardConfig(null);
              setLayout(p.layout);
              setWidgetRows(p.widgets);
            }}
            disabled={disabled || isSaving}
          >
            {t('dashboardBuilder.resetDefaults', { defaultValue: 'Restablecer' })}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default DashboardConfigBuilder;
