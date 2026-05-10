'use client';

/**
 * Users Admin Page - Public Accounts Management
 * Display and manage citizen/business/accountant/funcionario users
 *
 * BUSINESS RULES:
 * - Shows ONLY: citizen, business, accountant, funcionario
 * - admin/agent are managed in /admin/agents
 * - NO creation (users self-register)
 * - NO modification (users manage their profiles)
 * - ONLY Activate/Deactivate functionality
 * - View details in read-only mode
 *
 * REFACTORED: Using DataTable component with row selection and pagination
 *
 * @module dashboard/admin/users
 * @date 2025-01-17
 */

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
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
  Users,
  RefreshCw,
  Search,
  Shield,
  Eye,
  MoreHorizontal,
  Power,
  PowerOff,
  Building2,
  Briefcase,
  User as UserIcon,
  UserCheck,
  Download,
  FileSpreadsheet,
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import usersApi from '@/modules/users-admin/services/api';
import type { User } from '@/modules/users-admin/types';
import { UserRole } from '@/types/user';
import { useUserLabels } from '@/hooks/use-user-labels';
import { BackendUnavailableAlert } from '@/modules/admin/components';
import { exportToCsv, exportToExcel } from '@/core/utils/export';
import { DataTable, type DataTableColumn, type BulkAction } from '@/components/ui/data-table';

// Roles managed in this page (NOT admin/agent - those are in /admin/agents)
const PUBLIC_ROLES = [
  UserRole.CITIZEN,
  UserRole.BUSINESS,
  UserRole.ACCOUNTANT,
  UserRole.FUNCIONARIO,
] as const;

type PublicRole = typeof PUBLIC_ROLES[number];

export default function UsersPage() {
  const locale = useLocale();
  const t = useTranslations('admin.users');
  const tCommon = useTranslations('common');
  const { toast } = useToast();
  const router = useRouter();
  const { getRoleLabel } = useUserLabels();

  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [_error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'all' | PublicRole>('all');
  const [isBackendUnavailable, setIsBackendUnavailable] = useState(false);
  const PAGE_SIZE = 20;

  // Dialog states
  const [activateDialogOpen, setActivateDialogOpen] = useState(false);
  const [deactivateDialogOpen, setDeactivateDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [deactivateReason, setDeactivateReason] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  // Fetch users with server-side pagination
  const fetchUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const roleFilter = activeTab === 'all' ? PUBLIC_ROLES.join(',') : activeTab;
      const data = await usersApi.getAll({
        roles: roleFilter,
        search: searchQuery || undefined,
        page,
        size: PAGE_SIZE,
      });
      setUsers(data.items);
      setTotal(data.total);
      setTotalPages(data.pages || Math.ceil(data.total / PAGE_SIZE) || 1);
      setIsBackendUnavailable(false);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('errorLoading');
      setError(errorMessage);

      if (errorMessage.includes('fetch') || errorMessage.includes('Network') || errorMessage.includes('Failed')) {
        setIsBackendUnavailable(true);
      }

      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: t('errorLoadingUsers'),
      });
    } finally {
      setIsLoading(false);
    }
  }, [t, toast, page, activeTab, searchQuery]);

  // Debounce search (400ms) — avoid API call per keystroke
  const debounceRef = useRef<NodeJS.Timeout>();
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchUsers(), 400);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) };
  }, [searchQuery, fetchUsers]);

  // Immediate fetch on page/tab change
  useEffect(() => {
    fetchUsers();
  }, [page, activeTab, fetchUsers]);

  // Server-side filtering — users is already filtered by page/tab/search
  const filteredUsers = users;

  // Statistics (from current page — approximate; total is server-side)
  const stats = useMemo(() => {
    const byRole = {
      citizen: users.filter((u) => u.role === UserRole.CITIZEN).length,
      business: users.filter((u) => u.role === UserRole.BUSINESS).length,
      accountant: users.filter((u) => u.role === UserRole.ACCOUNTANT).length,
      funcionario: users.filter((u) => u.role === UserRole.FUNCIONARIO).length,
    };

    return {
      total,
      active: users.filter((u) => u.is_active).length,
      inactive: users.filter((u) => !u.is_active).length,
      byRole,
    };
  }, [users, total]);

  const handleActivate = async () => {
    if (!selectedUser) return;

    setIsProcessing(true);
    try {
      await usersApi.setActive(selectedUser.id, true);
      toast({
        title: t('successTitle'),
        description: t('userActivated'),
      });
      fetchUsers();
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: t('errorActivating'),
      });
    } finally {
      setIsProcessing(false);
      setActivateDialogOpen(false);
      setSelectedUser(null);
    }
  };

  const handleDeactivate = async () => {
    if (!selectedUser) return;

    setIsProcessing(true);
    try {
      await usersApi.setActive(selectedUser.id, false);
      toast({
        title: t('successTitle'),
        description: t('userDeactivated'),
      });
      fetchUsers();
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: t('errorDeactivating'),
      });
    } finally {
      setIsProcessing(false);
      setDeactivateDialogOpen(false);
      setDeactivateReason('');
      setSelectedUser(null);
    }
  };

  // DataTable columns
  const columns: DataTableColumn<User>[] = useMemo(() => {
    const getRoleBadge = (role: UserRole) => {
      const roleConfig: Record<string, { className: string; icon: React.ReactNode }> = {
        citizen: { className: 'bg-gray-100 text-gray-700', icon: <UserIcon className="h-3 w-3 mr-1" /> },
        business: { className: 'bg-green-100 text-green-700', icon: <Building2 className="h-3 w-3 mr-1" /> },
        accountant: { className: 'bg-blue-100 text-blue-700', icon: <Briefcase className="h-3 w-3 mr-1" /> },
        funcionario: { className: 'bg-amber-100 text-amber-700', icon: <UserCheck className="h-3 w-3 mr-1" /> },
      };

      const config = roleConfig[role];
      return (
        <Badge variant="outline" className={`flex items-center ${config?.className || 'bg-gray-100 text-gray-700'}`}>
          {config?.icon}
          {getRoleLabel(role)}
        </Badge>
      );
    };

    const handleViewDetails = (user: User) => {
      router.push(`/${locale}/dashboard/admin/users/${user.id}`);
    };

    const openActivateDialog = (user: User) => {
      setSelectedUser(user);
      setActivateDialogOpen(true);
    };

    const openDeactivateDialog = (user: User) => {
      setSelectedUser(user);
      setDeactivateDialogOpen(true);
    };

    return [
    {
      id: 'fullName',
      header: t('tableFullName'),
      cell: (user) => (
        <span className="font-medium">
          {user.first_name} {user.last_name}
        </span>
      ),
    },
    {
      id: 'email',
      header: t('tableEmail'),
      cell: (user) => user.email,
    },
    {
      id: 'role',
      header: t('tableRole'),
      cell: (user) => getRoleBadge(user.role),
    },
    {
      id: 'status',
      header: t('tableStatus'),
      cell: (user) => (
        user.is_active ? (
          <Badge variant="outline" className="bg-green-50 text-green-700">
            {t('statusActive')}
          </Badge>
        ) : (
          <Badge variant="outline" className="bg-red-50 text-red-700">
            {t('statusInactive')}
          </Badge>
        )
      ),
    },
    {
      id: '2fa',
      header: t('table2FA'),
      cell: (user) => (
        user.two_factor_enabled ? (
          <Shield className="h-4 w-4 text-green-500" />
        ) : (
          <Shield className="h-4 w-4 text-gray-300" />
        )
      ),
    },
    {
      id: 'lastLogin',
      header: t('tableLastLogin'),
      cell: (user) => (
        user.last_login ? (
          new Date(user.last_login).toLocaleDateString(locale, {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          })
        ) : (
          <span className="text-muted-foreground">{t('never')}</span>
        )
      ),
    },
    {
      id: 'actions',
      header: t('tableActions'),
      className: 'text-right',
      cell: (user) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => handleViewDetails(user)}>
              <Eye className="h-4 w-4 mr-2" />
              {t('viewDetails')}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            {user.is_active ? (
              <DropdownMenuItem
                className="text-red-600"
                onClick={() => openDeactivateDialog(user)}
              >
                <PowerOff className="h-4 w-4 mr-2" />
                {t('deactivate')}
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem
                className="text-green-600"
                onClick={() => openActivateDialog(user)}
              >
                <Power className="h-4 w-4 mr-2" />
                {t('activate')}
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ]; }, [t, locale, getRoleLabel, router]);

  // Bulk actions
  const bulkActions: BulkAction<User>[] = useMemo(() => [
    {
      id: 'activate',
      label: t('activateSelected'),
      icon: <Power className="h-4 w-4" />,
      variant: 'outline',
      requiresConfirmation: true,
      confirmTitle: t('confirmActivateTitle'),
      confirmDescription: t('confirmActivateDescription'),
      confirmButtonLabel: t('activate'),
      onExecute: async (selectedUsers) => {
        for (const user of selectedUsers) {
          if (!user.is_active) {
            await usersApi.setActive(user.id, true);
          }
        }
        toast({
          title: t('successTitle'),
          description: t('usersActivated', { count: selectedUsers.length }),
        });
      },
    },
    {
      id: 'deactivate',
      label: t('deactivateSelected'),
      icon: <PowerOff className="h-4 w-4" />,
      variant: 'destructive',
      requiresConfirmation: true,
      confirmTitle: t('confirmDeactivateTitle'),
      confirmDescription: t('confirmDeactivateDescription'),
      confirmButtonLabel: t('deactivate'),
      onExecute: async (selectedUsers) => {
        for (const user of selectedUsers) {
          if (user.is_active) {
            await usersApi.setActive(user.id, false);
          }
        }
        toast({
          title: t('successTitle'),
          description: t('usersDeactivated', { count: selectedUsers.length }),
        });
      },
    },
  ], [t, toast]);

  // Export helpers
  const getUserExportData = () =>
    filteredUsers.map((u) => ({
      [t('tableFullName')]: `${u.first_name} ${u.last_name}`,
      Email: u.email,
      [t('tableRole')]: getRoleLabel(u.role),
      [t('tableStatus')]: u.is_active ? t('statusActive') : t('statusInactive'),
      '2FA': u.two_factor_enabled ? 'Si' : 'No',
      [t('tableLastLogin')]: u.last_login ? new Date(u.last_login).toLocaleString() : '-',
      [t('tableCity')]: u.city || '-',
      [t('tablePhone')]: u.phone_number || '-',
    }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
          <Users className="h-8 w-8" />
          {t('title')}
        </h1>
        <p className="text-muted-foreground mt-2">
          {t('subtitle')}
        </p>
      </div>

      {/* Backend Unavailable Alert */}
      {isBackendUnavailable && <BackendUnavailableAlert />}

      {/* Statistics */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('statsTotal')}</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
            <p className="text-xs text-muted-foreground">{t('publicAccounts')}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('statsActive')}</CardTitle>
            <Power className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{stats.active}</div>
            <p className="text-xs text-muted-foreground">{t('activeUsers')}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('statsInactive')}</CardTitle>
            <PowerOff className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{stats.inactive}</div>
            <p className="text-xs text-muted-foreground">{t('inactiveUsers')}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('businessAccounts')}</CardTitle>
            <Building2 className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.byRole.business}</div>
            <p className="text-xs text-muted-foreground">{t('companies')}</p>
          </CardContent>
        </Card>
      </div>

      {/* Users Table with Tabs */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t('listTitle')}</CardTitle>
              <CardDescription>
                {t('usersFound', { count: total })}
              </CardDescription>
            </div>
            <div className="flex items-center gap-4">
              <div className="relative w-64">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder={t('searchPlaceholder')}
                  value={searchQuery}
                  onChange={(e) => { setSearchQuery(e.target.value); setPage(1) }}
                  className="pl-9"
                />
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm">
                    <Download className="h-4 w-4 mr-2" />
                    {tCommon('export') || 'Export'}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => exportToCsv(getUserExportData(), { fileName: `usuarios_${new Date().toISOString().slice(0, 10)}` })}>
                    <Download className="h-4 w-4 mr-2" />
                    CSV
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => exportToExcel(getUserExportData(), { fileName: `usuarios_${new Date().toISOString().slice(0, 10)}`, sheetName: 'Usuarios' })}>
                    <FileSpreadsheet className="h-4 w-4 mr-2" />
                    Excel
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              <Button variant="outline" size="sm" onClick={fetchUsers}>
                <RefreshCw className="h-4 w-4 mr-2" />
                {tCommon('refresh')}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* Tabs for filtering by role */}
          <Tabs value={activeTab} onValueChange={(v) => { setActiveTab(v as typeof activeTab); setPage(1) }} className="mb-4">
            <TabsList>
              <TabsTrigger value="all">
                {t('tabAll')} ({stats.total})
              </TabsTrigger>
              <TabsTrigger value={UserRole.CITIZEN}>
                <UserIcon className="h-4 w-4 mr-1" />
                {t('tabCitizens')} ({stats.byRole.citizen})
              </TabsTrigger>
              <TabsTrigger value={UserRole.BUSINESS}>
                <Building2 className="h-4 w-4 mr-1" />
                {t('tabBusinesses')} ({stats.byRole.business})
              </TabsTrigger>
              <TabsTrigger value={UserRole.ACCOUNTANT}>
                <Briefcase className="h-4 w-4 mr-1" />
                {t('tabAccountants')} ({stats.byRole.accountant})
              </TabsTrigger>
              <TabsTrigger value={UserRole.FUNCIONARIO}>
                <UserCheck className="h-4 w-4 mr-1" />
                {t('tabFuncionarios')} ({stats.byRole.funcionario})
              </TabsTrigger>
            </TabsList>
          </Tabs>

          {/* DataTable — server-side pagination */}
          <DataTable
            data={filteredUsers}
            columns={columns}
            getRowId={(user) => user.id}
            bulkActions={bulkActions}
            selectable={true}
            isLoading={isLoading}
            emptyMessage={t('noUsersFound')}
            emptyIcon={<Users className="h-12 w-12" />}
            defaultPageSize={PAGE_SIZE}
            pageSizeOptions={[PAGE_SIZE]}
            onRefresh={fetchUsers}
          />

          {/* Server-side pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4 px-2">
              <span className="text-sm text-muted-foreground">
                {t('usersFound', { count: total })} — {tCommon('page')} {page}/{totalPages}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline" size="sm"
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page <= 1 || isLoading}
                >
                  {tCommon('previous')}
                </Button>
                <Button
                  variant="outline" size="sm"
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages || isLoading}
                >
                  {tCommon('next')}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Activate Dialog */}
      <AlertDialog open={activateDialogOpen} onOpenChange={setActivateDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('activateUserTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {selectedUser && (
                <>
                  {t('activateUserDescription', {
                    name: `${selectedUser.first_name} ${selectedUser.last_name}`,
                    email: selectedUser.email,
                  })}
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isProcessing}>{tCommon('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleActivate}
              disabled={isProcessing}
              className="bg-green-600 hover:bg-green-700"
            >
              {isProcessing ? (
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Power className="h-4 w-4 mr-2" />
              )}
              {t('activate')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Deactivate Dialog */}
      <AlertDialog open={deactivateDialogOpen} onOpenChange={setDeactivateDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('deactivateUserTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {selectedUser && (
                <>
                  {t('deactivateUserDescription', {
                    name: `${selectedUser.first_name} ${selectedUser.last_name}`,
                    email: selectedUser.email,
                  })}
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="py-4">
            <Input
              placeholder={t('deactivateReasonPlaceholder')}
              value={deactivateReason}
              onChange={(e) => setDeactivateReason(e.target.value)}
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isProcessing}>{tCommon('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeactivate}
              disabled={isProcessing}
              className="bg-red-600 hover:bg-red-700"
            >
              {isProcessing ? (
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <PowerOff className="h-4 w-4 mr-2" />
              )}
              {t('deactivate')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
