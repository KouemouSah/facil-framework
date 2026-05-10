/**
 * Role Menu Config Page
 * Admin page for managing role-specific menu, dashboard, and UI configurations
 *
 * Phase 3: Visual builders for dashboard_config (DnD widget builder) and ui_config (structured form)
 *
 * @page /dashboard/admin/roles/[id]/menu-config
 * @date 2026-01-25
 * @updated 2026-02-17 - Phase 3: Visual builders for Dashboard and UI tabs
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import Link from 'next/link';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  ArrowLeft,
  Loader2,
  Save,
  RotateCcw,
  Menu,
  LayoutDashboard,
  Palette,
  Code,
  AlertCircle,
  Copy,
  WrapText,
  Download,
  Upload,
} from 'lucide-react';
import { toast } from 'sonner';

import { useRoleWithPermissions } from '@/modules/roles-admin';
import {
  useRoleMenuConfig,
  useUpdateRoleMenuConfig,
  type RoleMenuConfigUpdateRequest,
} from '@/modules/admin/hooks/useRoleMenuConfig';
import { MenuBuilder, type MenuItem, menuConfigToJson, validateMenuItemArray } from '@/modules/admin/components/menu-builder';
import { DashboardConfigBuilder } from '@/modules/admin/components/DashboardConfigBuilder';
import { UiConfigForm } from '@/modules/admin/components/UiConfigForm';
import type { DashboardConfig } from '@/modules/agent-dashboard/types/menu-config';

// =============================================================================
// TYPES
// =============================================================================

interface MenuBuilderState {
  menus: MenuItem[];
  isAutoMode: boolean;
  isDirty: boolean;
}

interface ConfigBuilderState<T> {
  config: T;
  isDirty: boolean;
  showRaw: boolean;
  rawJson: string;
  rawJsonErrors: string[];
}

// =============================================================================
// RAW JSON VALIDATION (kept for raw JSON toggle)
// =============================================================================

function validateRawJson(json: string): string[] {
  try {
    const parsed = JSON.parse(json);
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      return ['Must be a JSON object'];
    }
    return [];
  } catch (e) {
    return [`Invalid JSON: ${e instanceof Error ? e.message : 'Parse error'}`];
  }
}

// =============================================================================
// COMPONENT
// =============================================================================

export default function RoleMenuConfigPage() {
  const params = useParams();
  const locale = useLocale();
  const t = useTranslations('admin.menuConfig');
  const tCommon = useTranslations('common');

  const roleId = params.id as string;

  // Fetch role basic info
  const {
    data: role,
    isLoading: roleLoading,
    error: roleError,
  } = useRoleWithPermissions(roleId);

  // Fetch role menu config
  const {
    data: config,
    isLoading: configLoading,
    error: configError,
  } = useRoleMenuConfig(roleId);

  // Update mutation
  const updateMutation = useUpdateRoleMenuConfig();

  // Menu builder state (visual editor)
  const [menuBuilderState, setMenuBuilderState] = useState<MenuBuilderState>({
    menus: [],
    isAutoMode: true,
    isDirty: false,
  });

  // Dashboard config state (visual builder + raw JSON toggle)
  const [dashboardState, setDashboardState] = useState<ConfigBuilderState<DashboardConfig>>({
    config: { version: '1.0', layout: 'grid', widgets: [] },
    isDirty: false,
    showRaw: false,
    rawJson: '{}',
    rawJsonErrors: [],
  });

  // UI config state (structured form + raw JSON toggle)
  const [uiState, setUiState] = useState<ConfigBuilderState<Record<string, unknown>>>({
    config: {},
    isDirty: false,
    showRaw: false,
    rawJson: '{}',
    rawJsonErrors: [],
  });

  // Reset confirmation dialog
  const [isResetDialogOpen, setIsResetDialogOpen] = useState(false);
  const [resetTarget, setResetTarget] = useState<'menu' | 'dashboard' | 'ui' | 'all'>('all');
  // Key counter to force child component re-mount on reset
  const [resetKey, setResetKey] = useState(0);

  // Shared state reset helper — used by both init and reset
  const applyConfigToState = useCallback((source: typeof config, targets: 'all' | 'menu' | 'dashboard' | 'ui' = 'all') => {
    if (!source) return;
    if (targets === 'all' || targets === 'menu') {
      setMenuBuilderState({
        menus: [],
        isAutoMode: source.menu_config === null,
        isDirty: false,
      });
    }
    if (targets === 'all' || targets === 'dashboard') {
      const rawDash = source.dashboard_config
        ? JSON.stringify(source.dashboard_config, null, 2) : '{}';
      setDashboardState({
        config: { version: '1.0', layout: 'grid', widgets: [] },
        isDirty: false,
        showRaw: false,
        rawJson: rawDash,
        rawJsonErrors: [],
      });
    }
    if (targets === 'all' || targets === 'ui') {
      const rawUi = source.ui_config
        ? JSON.stringify(source.ui_config, null, 2) : '{}';
      setUiState({
        config: source.ui_config ?? {},
        isDirty: false,
        showRaw: false,
        rawJson: rawUi,
        rawJsonErrors: [],
      });
    }
  }, []);

  // Initialize states from fetched data
  useEffect(() => {
    applyConfigToState(config);
  }, [config, applyConfigToState]);

  // MenuBuilder onChange callback
  const handleMenuBuilderChange = useCallback((menus: MenuItem[], isAutoMode: boolean) => {
    setMenuBuilderState((prev) => ({
      menus,
      isAutoMode,
      isDirty: prev.isDirty || menus.length > 0 || prev.isAutoMode !== isAutoMode,
    }));
  }, []);

  // Dashboard builder onChange
  const handleDashboardChange = useCallback((newConfig: DashboardConfig, isDirty: boolean) => {
    setDashboardState((prev) => ({
      ...prev,
      config: newConfig,
      isDirty,
      rawJson: JSON.stringify(newConfig, null, 2),
      rawJsonErrors: [],
    }));
  }, []);

  // UI form onChange
  const handleUiChange = useCallback((newConfig: Record<string, unknown>, isDirty: boolean) => {
    setUiState((prev) => ({
      ...prev,
      config: newConfig,
      isDirty,
      rawJson: JSON.stringify(newConfig, null, 2),
      rawJsonErrors: [],
    }));
  }, []);

  // Raw JSON change handlers (for raw toggle mode)
  const handleRawDashboardChange = useCallback((value: string) => {
    setDashboardState((prev) => ({
      ...prev,
      rawJson: value,
      rawJsonErrors: validateRawJson(value),
      isDirty: true,
    }));
  }, []);

  const handleRawUiChange = useCallback((value: string) => {
    setUiState((prev) => ({
      ...prev,
      rawJson: value,
      rawJsonErrors: validateRawJson(value),
      isDirty: true,
    }));
  }, []);

  // Toggle between visual and raw JSON
  const toggleDashboardRaw = useCallback(() => {
    setDashboardState((prev) => {
      if (prev.showRaw) {
        // Switching to visual: if raw JSON is valid, sync config from it
        if (prev.rawJsonErrors.length === 0) {
          try {
            const parsed = JSON.parse(prev.rawJson);
            return { ...prev, showRaw: false, config: parsed as DashboardConfig };
          } catch {
            return prev; // Can't switch with invalid JSON
          }
        }
        return prev; // Can't switch with errors
      }
      // Switching to raw: sync raw from current config
      return { ...prev, showRaw: true, rawJson: JSON.stringify(prev.config, null, 2) };
    });
  }, []);

  const toggleUiRaw = useCallback(() => {
    setUiState((prev) => {
      if (prev.showRaw) {
        if (prev.rawJsonErrors.length === 0) {
          try {
            const parsed = JSON.parse(prev.rawJson);
            return { ...prev, showRaw: false, config: parsed as Record<string, unknown> };
          } catch {
            return prev;
          }
        }
        return prev;
      }
      return { ...prev, showRaw: true, rawJson: JSON.stringify(prev.config, null, 2) };
    });
  }, []);

  // Copy JSON to clipboard
  const handleCopyJson = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success(t('roleConfig.copiedToClipboard', { defaultValue: 'Copiado al portapapeles' }));
    } catch {
      toast.error('Failed to copy');
    }
  };

  // Format raw JSON
  const handleFormatRawJson = useCallback((
    setter: React.Dispatch<React.SetStateAction<ConfigBuilderState<DashboardConfig>>> |
            React.Dispatch<React.SetStateAction<ConfigBuilderState<Record<string, unknown>>>>
  ) => {
    (setter as React.Dispatch<React.SetStateAction<ConfigBuilderState<unknown>>>)((prev: ConfigBuilderState<unknown>) => {
      try {
        const formatted = JSON.stringify(JSON.parse(prev.rawJson), null, 2);
        return { ...prev, rawJson: formatted, rawJsonErrors: [] };
      } catch {
        return prev;
      }
    });
  }, []);

  // Get serialized config for save (respects showRaw mode)
  const getDashboardForSave = (): Record<string, unknown> | null => {
    if (!dashboardState.isDirty) return null;
    if (dashboardState.showRaw) {
      try { return JSON.parse(dashboardState.rawJson); }
      catch { return null; }
    }
    return dashboardState.config as unknown as Record<string, unknown>;
  };

  const getUiForSave = (): Record<string, unknown> | null => {
    if (!uiState.isDirty) return null;
    if (uiState.showRaw) {
      try { return JSON.parse(uiState.rawJson); }
      catch { return null; }
    }
    return uiState.config;
  };

  // Save all configurations
  const handleSaveAll = async () => {
    if (hasErrors) {
      toast.error(t('roleConfig.fixJsonErrors'));
      return;
    }

    try {
      const data: RoleMenuConfigUpdateRequest = {};

      if (menuBuilderState.isDirty) {
        if (menuBuilderState.isAutoMode) {
          data.menu_config = null;
        } else {
          const menuConfigJson = menuConfigToJson(menuBuilderState.menus);
          data.menu_config = JSON.parse(menuConfigJson);
        }
      }

      const dashSave = getDashboardForSave();
      if (dashSave) data.dashboard_config = dashSave;

      const uiSave = getUiForSave();
      if (uiSave) data.ui_config = uiSave;

      if (Object.keys(data).length === 0) {
        toast.info(t('roleConfig.noChanges'));
        return;
      }

      await updateMutation.mutateAsync({ roleId, data });

      setMenuBuilderState((prev) => ({ ...prev, isDirty: false }));
      setDashboardState((prev) => ({ ...prev, isDirty: false }));
      setUiState((prev) => ({ ...prev, isDirty: false }));
    } catch {
      // Error handled by mutation
    }
  };

  // Save individual configuration
  const handleSaveConfig = async (type: 'menu' | 'dashboard' | 'ui') => {
    if (type === 'menu') {
      if (!menuBuilderState.isDirty) {
        toast.info(t('roleConfig.noChanges'));
        return;
      }
      try {
        const data: RoleMenuConfigUpdateRequest = {
          menu_config: menuBuilderState.isAutoMode
            ? null
            : JSON.parse(menuConfigToJson(menuBuilderState.menus)),
        };
        await updateMutation.mutateAsync({ roleId, data });
        setMenuBuilderState((prev) => ({ ...prev, isDirty: false }));
      } catch {
        // Error handled by mutation
      }
      return;
    }

    if (type === 'dashboard') {
      if (dashboardState.rawJsonErrors.length > 0) {
        toast.error(t('roleConfig.fixJsonErrors'));
        return;
      }
      if (!dashboardState.isDirty) {
        toast.info(t('roleConfig.noChanges'));
        return;
      }
      try {
        const dashSave = getDashboardForSave();
        if (!dashSave) return;
        await updateMutation.mutateAsync({ roleId, data: { dashboard_config: dashSave } });
        setDashboardState((prev) => ({ ...prev, isDirty: false }));
      } catch {
        // Error handled by mutation
      }
      return;
    }

    // UI
    if (uiState.rawJsonErrors.length > 0) {
      toast.error(t('roleConfig.fixJsonErrors'));
      return;
    }
    if (!uiState.isDirty) {
      toast.info(t('roleConfig.noChanges'));
      return;
    }
    try {
      const uiSave = getUiForSave();
      if (!uiSave) return;
      await updateMutation.mutateAsync({ roleId, data: { ui_config: uiSave } });
      setUiState((prev) => ({ ...prev, isDirty: false }));
    } catch {
      // Error handled by mutation
    }
  };

  // Reset configurations
  const handleReset = () => {
    if (!config) return;
    applyConfigToState(config, resetTarget);
    setResetKey((k) => k + 1);
    setIsResetDialogOpen(false);
    toast.success(t('roleConfig.configReset'));
  };

  // Import/Export handlers
  const handleExport = useCallback(() => {
    const exportData = {
      menu_config: menuBuilderState.isDirty
        ? (menuBuilderState.isAutoMode ? null : menuBuilderState.menus)
        : (config?.menu_config ?? null),
      dashboard_config: dashboardState.isDirty ? dashboardState.config : (config?.dashboard_config ?? {}),
      ui_config: uiState.isDirty ? uiState.config : (config?.ui_config ?? {}),
      exported_at: new Date().toISOString(),
      role_id: roleId,
      role_code: role?.code ?? 'unknown',
    };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const date = new Date().toISOString().slice(0, 10);
    a.download = `role-config-${role?.code ?? 'unknown'}-${date}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success(t('roleConfig.exportSuccess', { defaultValue: 'Configuración exportada' }));
  }, [menuBuilderState, dashboardState, uiState, config, roleId, role?.code, t]);

  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const [isImportDialogOpen, setIsImportDialogOpen] = useState(false);
  const [pendingImportData, setPendingImportData] = useState<Record<string, unknown> | null>(null);

  const handleImportFile = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const data = JSON.parse(evt.target?.result as string);
        if (typeof data !== 'object' || data === null || Array.isArray(data)) {
          toast.error(t('roleConfig.importInvalidJson', { defaultValue: 'El archivo debe contener un objeto JSON' }));
          return;
        }
        setPendingImportData(data);
        setIsImportDialogOpen(true);
      } catch {
        toast.error(t('roleConfig.importError', { defaultValue: 'Error al leer el archivo JSON' }));
      }
    };
    reader.readAsText(file);
    // Reset input value to allow re-importing the same file
    e.target.value = '';
  }, [t]);

  const handleConfirmImport = useCallback(() => {
    if (!pendingImportData) return;
    // Apply menu_config (with structural validation)
    if ('menu_config' in pendingImportData) {
      if (pendingImportData.menu_config === null) {
        setMenuBuilderState({ menus: [], isAutoMode: true, isDirty: true });
      } else if (validateMenuItemArray(pendingImportData.menu_config)) {
        setMenuBuilderState({ menus: pendingImportData.menu_config, isAutoMode: false, isDirty: true });
      } else {
        toast.error(t('roleConfig.importInvalidJson', { defaultValue: 'menu_config debe ser null o un array de MenuItem válidos' }));
        return;
      }
    }
    // Apply dashboard_config
    if (pendingImportData.dashboard_config && typeof pendingImportData.dashboard_config === 'object') {
      const dc = pendingImportData.dashboard_config as DashboardConfig;
      setDashboardState({
        config: dc,
        isDirty: true,
        showRaw: false,
        rawJson: JSON.stringify(dc, null, 2),
        rawJsonErrors: [],
      });
    }
    // Apply ui_config
    if (pendingImportData.ui_config && typeof pendingImportData.ui_config === 'object') {
      const uc = pendingImportData.ui_config as Record<string, unknown>;
      setUiState({
        config: uc,
        isDirty: true,
        showRaw: false,
        rawJson: JSON.stringify(uc, null, 2),
        rawJsonErrors: [],
      });
    }
    // Force re-mount of visual builders
    setResetKey((k) => k + 1);
    setIsImportDialogOpen(false);
    setPendingImportData(null);
    toast.success(t('roleConfig.importSuccess', { defaultValue: 'Configuración importada. No olvide guardar.' }));
  }, [pendingImportData, t]);

  // Derived states
  const hasUnsavedChanges = menuBuilderState.isDirty || dashboardState.isDirty || uiState.isDirty;
  const hasErrors = dashboardState.rawJsonErrors.length > 0 || uiState.rawJsonErrors.length > 0;

  // Loading state
  if (roleLoading || configLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center space-y-4">
          <Loader2 className="h-10 w-10 animate-spin text-primary mx-auto" />
          <p className="text-muted-foreground">{tCommon('loading')}</p>
        </div>
      </div>
    );
  }

  // Error state
  if (roleError || configError || !role) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link href={`/${locale}/dashboard/admin/roles/${roleId}`}>
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <h1 className="text-2xl font-bold">{t('roleConfig.notFound')}</h1>
        </div>
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              <span>
                {roleError instanceof Error
                  ? roleError.message
                  : configError instanceof Error
                  ? configError.message
                  : t('roleConfig.loadError')}
              </span>
            </div>
            <Link href={`/${locale}/dashboard/admin/roles/${roleId}`}>
              <Button variant="outline" className="mt-4">
                {t('roleConfig.returnToRole')}
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href={`/${locale}/dashboard/admin/roles/${roleId}`}>
            <Button variant="ghost" size="icon" title={t('roleConfig.backToRole')}>
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
              <Menu className="h-6 w-6" />
              {t('roleConfig.title')}
            </h1>
            <p className="text-muted-foreground">
              {t('roleConfig.description', { roleName: role.name })}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {hasUnsavedChanges && (
            <Badge variant="outline" className="gap-1 text-amber-600 border-amber-300">
              <AlertCircle className="h-3 w-3" />
              {t('menuBuilder.unsavedChanges')}
            </Badge>
          )}

          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="h-4 w-4 mr-2" />
            {t('roleConfig.export', { defaultValue: 'Exportar' })}
          </Button>

          <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
            <Upload className="h-4 w-4 mr-2" />
            {t('roleConfig.import', { defaultValue: 'Importar' })}
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            className="hidden"
            onChange={handleImportFile}
          />

          <Button
            variant="outline"
            onClick={() => {
              setResetTarget('all');
              setIsResetDialogOpen(true);
            }}
            disabled={!hasUnsavedChanges}
          >
            <RotateCcw className="h-4 w-4 mr-2" />
            {t('roleConfig.reset')}
          </Button>

          <Button
            onClick={handleSaveAll}
            disabled={!hasUnsavedChanges || hasErrors || updateMutation.isPending}
          >
            {updateMutation.isPending ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            {t('roleConfig.saveAll')}
          </Button>
        </div>
      </div>

      {/* Role Info Summary */}
      <Card className="bg-muted/50">
        <CardContent className="pt-4 pb-4">
          <div className="flex items-center gap-4">
            <div>
              <p className="text-sm text-muted-foreground">{tCommon('role')}</p>
              <p className="font-medium">{role.name}</p>
            </div>
            <div className="h-8 w-px bg-border" />
            <div>
              <p className="text-sm text-muted-foreground">{tCommon('code')}</p>
              <code className="text-sm bg-muted px-2 py-0.5 rounded">{role.code}</code>
            </div>
            {role.entity_type && (
              <>
                <div className="h-8 w-px bg-border" />
                <div>
                  <p className="text-sm text-muted-foreground">{tCommon('entityType')}</p>
                  <Badge variant="secondary">{role.entity_type}</Badge>
                </div>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Configuration Tabs */}
      <Tabs defaultValue="menu" className="space-y-4">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="menu" className="gap-2">
            <Menu className="h-4 w-4" />
            {t('roleConfig.tabs.menu')}
            {menuBuilderState.isDirty && <Badge variant="secondary" className="h-5 px-1.5">*</Badge>}
          </TabsTrigger>
          <TabsTrigger value="dashboard" className="gap-2">
            <LayoutDashboard className="h-4 w-4" />
            {t('roleConfig.tabs.dashboard')}
            {dashboardState.isDirty && <Badge variant="secondary" className="h-5 px-1.5">*</Badge>}
          </TabsTrigger>
          <TabsTrigger value="ui" className="gap-2">
            <Palette className="h-4 w-4" />
            {t('roleConfig.tabs.ui')}
            {uiState.isDirty && <Badge variant="secondary" className="h-5 px-1.5">*</Badge>}
          </TabsTrigger>
        </TabsList>

        {/* Menu Config Tab - Visual MenuBuilder */}
        <TabsContent value="menu">
          <div className="space-y-4">
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Menu className="h-5 w-5" />
                      {t('roleConfig.menuConfig.title')}
                    </CardTitle>
                    <CardDescription>
                      {t('roleConfig.menuConfig.description')}
                    </CardDescription>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleSaveConfig('menu')}
                    disabled={!menuBuilderState.isDirty || updateMutation.isPending}
                  >
                    {updateMutation.isPending ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Save className="h-4 w-4 mr-2" />
                    )}
                    {t('roleConfig.saveMenuConfig')}
                  </Button>
                </div>
              </CardHeader>
            </Card>

            <MenuBuilder
              initialConfig={config?.menu_config ?? null}
              onChange={handleMenuBuilderChange}
              isSaving={updateMutation.isPending}
              roleCode={role?.code}
              entityCode={role?.entity_type || undefined}
              disabled={false}
            />
          </div>
        </TabsContent>

        {/* Dashboard Config Tab — Visual Builder + Raw JSON toggle */}
        <TabsContent value="dashboard">
          <div className="space-y-4">
            {/* Tab header */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <LayoutDashboard className="h-5 w-5" />
                      {t('roleConfig.dashboardConfig.title')}
                    </CardTitle>
                    <CardDescription>
                      {t('roleConfig.dashboardConfig.description')}
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={toggleDashboardRaw}
                      disabled={dashboardState.showRaw && dashboardState.rawJsonErrors.length > 0}
                    >
                      <Code className="h-4 w-4 mr-1" />
                      {dashboardState.showRaw ? 'Visual' : 'JSON'}
                    </Button>
                    {dashboardState.showRaw && (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleFormatRawJson(setDashboardState as React.Dispatch<React.SetStateAction<ConfigBuilderState<DashboardConfig>>>)}
                          title="Format JSON"
                        >
                          <WrapText className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleCopyJson(dashboardState.rawJson)}
                          title="Copy"
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                      </>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleSaveConfig('dashboard')}
                      disabled={!dashboardState.isDirty || dashboardState.rawJsonErrors.length > 0 || updateMutation.isPending}
                    >
                      {updateMutation.isPending ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <Save className="h-4 w-4 mr-2" />
                      )}
                      {t('roleConfig.save')}
                    </Button>
                  </div>
                </div>
              </CardHeader>
            </Card>

            {/* Visual builder or raw JSON */}
            {dashboardState.showRaw ? (
              <Card>
                <CardContent className="pt-4">
                  <div className="space-y-2">
                    <Textarea
                      value={dashboardState.rawJson}
                      onChange={(e) => handleRawDashboardChange(e.target.value)}
                      className="font-mono text-sm min-h-[300px]"
                      placeholder='{"version": "1.0", "layout": "grid", "widgets": []}'
                    />
                    {dashboardState.rawJsonErrors.length > 0 && (
                      <ul className="text-sm text-destructive space-y-1">
                        {dashboardState.rawJsonErrors.map((err, i) => (
                          <li key={i} className="flex items-start gap-1">
                            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                            {err}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </CardContent>
              </Card>
            ) : (
              <DashboardConfigBuilder
                key={`dash-${resetKey}`}
                initialConfig={config?.dashboard_config ?? null}
                onChange={handleDashboardChange}
                isSaving={updateMutation.isPending}
              />
            )}
          </div>
        </TabsContent>

        {/* UI Config Tab — Structured Form + Raw JSON toggle */}
        <TabsContent value="ui">
          <div className="space-y-4">
            {/* Tab header */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Palette className="h-5 w-5" />
                      {t('roleConfig.uiConfig.title')}
                    </CardTitle>
                    <CardDescription>
                      {t('roleConfig.uiConfig.description')}
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={toggleUiRaw}
                      disabled={uiState.showRaw && uiState.rawJsonErrors.length > 0}
                    >
                      <Code className="h-4 w-4 mr-1" />
                      {uiState.showRaw ? 'Visual' : 'JSON'}
                    </Button>
                    {uiState.showRaw && (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleFormatRawJson(setUiState as React.Dispatch<React.SetStateAction<ConfigBuilderState<Record<string, unknown>>>>)}
                          title="Format JSON"
                        >
                          <WrapText className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleCopyJson(uiState.rawJson)}
                          title="Copy"
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                      </>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleSaveConfig('ui')}
                      disabled={!uiState.isDirty || uiState.rawJsonErrors.length > 0 || updateMutation.isPending}
                    >
                      {updateMutation.isPending ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <Save className="h-4 w-4 mr-2" />
                      )}
                      {t('roleConfig.save')}
                    </Button>
                  </div>
                </div>
              </CardHeader>
            </Card>

            {/* Structured form or raw JSON */}
            {uiState.showRaw ? (
              <Card>
                <CardContent className="pt-4">
                  <div className="space-y-2">
                    <Textarea
                      value={uiState.rawJson}
                      onChange={(e) => handleRawUiChange(e.target.value)}
                      className="font-mono text-sm min-h-[300px]"
                      placeholder='{"theme": "default"}'
                    />
                    {uiState.rawJsonErrors.length > 0 && (
                      <ul className="text-sm text-destructive space-y-1">
                        {uiState.rawJsonErrors.map((err, i) => (
                          <li key={i} className="flex items-start gap-1">
                            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                            {err}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </CardContent>
              </Card>
            ) : (
              <UiConfigForm
                key={`ui-${resetKey}`}
                initialConfig={config?.ui_config ?? null}
                onChange={handleUiChange}
                isSaving={updateMutation.isPending}
              />
            )}
          </div>
        </TabsContent>
      </Tabs>

      {/* Reset Confirmation Dialog */}
      <AlertDialog open={isResetDialogOpen} onOpenChange={setIsResetDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('roleConfig.resetDialog.title')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('roleConfig.resetDialog.description')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('roleConfig.resetDialog.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleReset}>
              {t('roleConfig.resetDialog.confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Import Confirmation Dialog */}
      <AlertDialog open={isImportDialogOpen} onOpenChange={(open) => {
        setIsImportDialogOpen(open);
        if (!open) setPendingImportData(null);
      }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t('roleConfig.importConfirm', { defaultValue: '¿Importar la configuración?' })}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t('roleConfig.importConfirmDescription', {
                defaultValue: 'Esto reemplazará la configuración actual de las pestañas Dashboard y UI. Los cambios no se guardarán hasta que pulse Guardar.',
              })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setPendingImportData(null)}>
              {t('roleConfig.resetDialog.cancel', { defaultValue: 'Cancelar' })}
            </AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmImport}>
              {t('roleConfig.importApply', { defaultValue: 'Aplicar' })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
