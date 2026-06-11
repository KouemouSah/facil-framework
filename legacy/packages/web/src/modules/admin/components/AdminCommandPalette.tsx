'use client';

/**
 * AdminCommandPalette — Cmd+K global command palette for admin users
 *
 * Phase 2.6 RBAC Engine Core
 *
 * Features:
 * - Keyboard shortcut: Cmd+K (Mac) / Ctrl+K (Windows)
 * - Navigation: quick jump to any admin page
 * - Actions: create role, export, search users/agents
 */

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useLocale } from 'next-intl';
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from '@/components/ui/command';
import {
  Shield,
  Users,
  Key,
  Settings,
  FileText,
  BarChart3,
  MessageSquare,
  Building2,
  CreditCard,
  Plus,
  Download,
  UserCog,
  Headphones,
  LayoutDashboard,
  ShieldCheck,
  Globe,
  Bell,
} from 'lucide-react';

interface CommandAction {
  id: string;
  label: string;
  icon: React.ReactNode;
  action: () => void;
  shortcut?: string;
}

export function AdminCommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const locale = useLocale();

  const navigate = useCallback(
    (path: string) => {
      router.push(`/${locale}/dashboard/${path}`);
      setOpen(false);
    },
    [router, locale]
  );

  // Cmd+K / Ctrl+K listener
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, []);

  const navigationItems: CommandAction[] = [
    { id: 'dashboard', label: 'Dashboard Admin', icon: <LayoutDashboard className="h-4 w-4" />, action: () => navigate('admin') },
    { id: 'roles', label: 'Roles y Permisos', icon: <Shield className="h-4 w-4" />, action: () => navigate('admin/roles'), shortcut: 'R' },
    { id: 'permissions', label: 'Catalogo de Permisos', icon: <Key className="h-4 w-4" />, action: () => navigate('admin/roles?tab=permissions') },
    { id: 'user-permissions', label: 'Permisos de Usuario', icon: <ShieldCheck className="h-4 w-4" />, action: () => navigate('admin/roles?tab=user-permissions') },
    { id: 'agents', label: 'Gestion de Agentes', icon: <UserCog className="h-4 w-4" />, action: () => navigate('admin/agents'), shortcut: 'A' },
    { id: 'users', label: 'Gestion de Usuarios', icon: <Users className="h-4 w-4" />, action: () => navigate('admin/users'), shortcut: 'U' },
    { id: 'entities', label: 'Entidades', icon: <Building2 className="h-4 w-4" />, action: () => navigate('admin/entities') },
    { id: 'services', label: 'Servicios Fiscales', icon: <FileText className="h-4 w-4" />, action: () => navigate('admin/services') },
    { id: 'payments', label: 'Pagos', icon: <CreditCard className="h-4 w-4" />, action: () => navigate('admin/payments') },
    { id: 'communications', label: 'Comunicaciones', icon: <MessageSquare className="h-4 w-4" />, action: () => navigate('admin/communications') },
    { id: 'support', label: 'Soporte', icon: <Headphones className="h-4 w-4" />, action: () => navigate('admin/support') },
    { id: 'stats', label: 'Estadisticas', icon: <BarChart3 className="h-4 w-4" />, action: () => navigate('admin/stats') },
    { id: 'translations', label: 'Traducciones', icon: <Globe className="h-4 w-4" />, action: () => navigate('admin/translations') },
    { id: 'notifications', label: 'Notificaciones', icon: <Bell className="h-4 w-4" />, action: () => navigate('admin/notifications') },
    { id: 'settings', label: 'Configuracion', icon: <Settings className="h-4 w-4" />, action: () => navigate('admin/settings') },
  ];

  const quickActions: CommandAction[] = [
    { id: 'create-role', label: 'Crear nuevo rol', icon: <Plus className="h-4 w-4" />, action: () => navigate('admin/roles/new') },
    { id: 'export-roles', label: 'Exportar roles (CSV)', icon: <Download className="h-4 w-4" />, action: async () => {
      const { rolesApi } = await import('@/modules/roles-admin');
      await rolesApi.exportCsv();
      setOpen(false);
    }},
    { id: 'permission-matrix', label: 'Ver matriz de permisos', icon: <Shield className="h-4 w-4" />, action: () => navigate('admin/roles?tab=roles&view=matrix') },
  ];

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Buscar paginas, acciones..." />
      <CommandList>
        <CommandEmpty>Sin resultados.</CommandEmpty>

        <CommandGroup heading="Acciones rapidas">
          {quickActions.map((item) => (
            <CommandItem key={item.id} onSelect={item.action} className="gap-2">
              {item.icon}
              <span>{item.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Navegacion">
          {navigationItems.map((item) => (
            <CommandItem key={item.id} onSelect={item.action} className="gap-2">
              {item.icon}
              <span>{item.label}</span>
              {item.shortcut && <CommandShortcut>{item.shortcut}</CommandShortcut>}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
