'use client'

import { useState, useEffect, useMemo } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { AlertTriangle, ArrowRight, Check, ChevronsUpDown, Minus, Plus, Search, Shield, User, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useRoles, useSimulateRolePermission, useSimulateUserRoleChange, useOverprivilegedUsers } from '../hooks/useRoles'
import usersApi from '@/modules/users-admin/services/api'
import type { User as UserType } from '@/modules/users-admin/types'
import type { SimulateRolePermissionResponse, SimulateUserRoleChangeResponse, OverprivilegedUser } from '../types'

export function PermissionSimulatorTab() {
  return (
    <div className="space-y-6">
      <Tabs defaultValue="role-sim">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="role-sim" className="flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Simular Rol
          </TabsTrigger>
          <TabsTrigger value="user-sim" className="flex items-center gap-2">
            <User className="h-4 w-4" />
            Cambio de Rol
          </TabsTrigger>
          <TabsTrigger value="anomalies" className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            Anomalias
          </TabsTrigger>
        </TabsList>

        <TabsContent value="role-sim" className="mt-4">
          <RolePermissionSimulator />
        </TabsContent>
        <TabsContent value="user-sim" className="mt-4">
          <UserRoleChangeSimulator />
        </TabsContent>
        <TabsContent value="anomalies" className="mt-4">
          <OverprivilegedUsersPanel />
        </TabsContent>
      </Tabs>
    </div>
  )
}

// =============================================================================
// ROLE PERMISSION SIMULATOR
// =============================================================================

function RolePermissionSimulator() {
  const { data: rolesData } = useRoles({ page_size: 100 })
  const simulateMutation = useSimulateRolePermission()
  const [selectedRoleId, setSelectedRoleId] = useState('')
  const [permissionInput, setPermissionInput] = useState('')
  const [action, setAction] = useState<'grant' | 'revoke'>('grant')
  const [result, setResult] = useState<SimulateRolePermissionResponse | null>(null)

  const roles = rolesData?.roles || []

  const handleSimulate = async () => {
    if (!selectedRoleId || !permissionInput.trim()) return
    const names = permissionInput.split(',').map(s => s.trim()).filter(Boolean)
    try {
      const res = await simulateMutation.mutateAsync({
        role_id: selectedRoleId,
        permission_names: names,
        action,
      })
      setResult(res)
    } catch {
      // handled by react-query
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Zap className="h-5 w-5" />
          Simulador de Permisos de Rol
        </CardTitle>
        <CardDescription>
          Simula el impacto de otorgar/revocar permisos a un rol SIN aplicar cambios.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-2">
            <Label>Rol</Label>
            <Select value={selectedRoleId} onValueChange={setSelectedRoleId}>
              <SelectTrigger>
                <SelectValue placeholder="Seleccionar rol..." />
              </SelectTrigger>
              <SelectContent>
                {roles.map(r => (
                  <SelectItem key={r.id} value={r.id}>
                    {r.name} ({r.code})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Permisos (separados por coma)</Label>
            <Input
              value={permissionInput}
              onChange={e => setPermissionInput(e.target.value)}
              placeholder="service_requests.approve, payments.view"
            />
          </div>

          <div className="space-y-2">
            <Label>Accion</Label>
            <div className="flex gap-2">
              <Select value={action} onValueChange={(v: 'grant' | 'revoke') => setAction(v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="grant">Otorgar</SelectItem>
                  <SelectItem value="revoke">Revocar</SelectItem>
                </SelectContent>
              </Select>
              <Button
                onClick={handleSimulate}
                disabled={simulateMutation.isPending || !selectedRoleId || !permissionInput.trim()}
              >
                <Search className="h-4 w-4 mr-2" />
                Simular
              </Button>
            </div>
          </div>
        </div>

        {/* Results */}
        {result && (
          <div className="mt-6 space-y-4">
            <div className="flex items-center gap-4">
              <Badge variant={result.affected_users_count > 0 ? 'destructive' : 'secondary'}>
                {result.affected_users_count} usuarios afectados
              </Badge>
              <Badge variant="outline">
                {result.action === 'grant' ? 'Otorgar' : 'Revocar'}: {result.permission_names.join(', ')}
              </Badge>
            </div>

            {result.affected_users.length > 0 && (
              <div className="border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-muted">
                    <tr>
                      <th className="text-left p-3">Usuario</th>
                      <th className="text-left p-3">Rol</th>
                      <th className="text-left p-3">Cambios</th>
                      <th className="text-right p-3">Permisos</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.affected_users.map(u => (
                      <tr key={u.user_id} className="border-t">
                        <td className="p-3">
                          <div className="font-medium">{u.full_name}</div>
                          <div className="text-muted-foreground text-xs">{u.email}</div>
                        </td>
                        <td className="p-3">
                          <Badge variant="outline">{u.role_code}</Badge>
                        </td>
                        <td className="p-3">
                          {u.added.map(p => (
                            <span key={p} className="inline-flex items-center gap-1 text-green-600 mr-2">
                              <Plus className="h-3 w-3" />{p}
                            </span>
                          ))}
                          {u.removed.map(p => (
                            <span key={p} className="inline-flex items-center gap-1 text-red-600 mr-2">
                              <Minus className="h-3 w-3" />{p}
                            </span>
                          ))}
                        </td>
                        <td className="p-3 text-right">
                          {u.total_before} <ArrowRight className="inline h-3 w-3" /> {u.total_after}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {result.affected_users_count === 0 && (
              <p className="text-muted-foreground text-center py-4">
                Ningun usuario seria afectado por este cambio.
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// =============================================================================
// USER ROLE CHANGE SIMULATOR
// =============================================================================

function UserRoleChangeSimulator() {
  const { data: rolesData } = useRoles({ page_size: 100 })
  const simulateMutation = useSimulateUserRoleChange()
  const [userId, setUserId] = useState('')
  const [newRoleId, setNewRoleId] = useState('')
  const [result, setResult] = useState<SimulateUserRoleChangeResponse | null>(null)
  const [allUsers, setAllUsers] = useState<UserType[]>([])
  const [userSearchOpen, setUserSearchOpen] = useState(false)
  const [userSearchQuery, setUserSearchQuery] = useState('')

  const roles = rolesData?.roles || []

  // Load users list on mount
  useEffect(() => {
    usersApi.getAll({ size: 100 }).then(res => setAllUsers(res.items)).catch(() => {})
  }, [])

  // Filter users based on search
  const filteredUsers = useMemo(() => {
    if (!userSearchQuery) return allUsers.slice(0, 50)
    const q = userSearchQuery.toLowerCase()
    return allUsers
      .filter(u =>
        u.email.toLowerCase().includes(q) ||
        u.first_name.toLowerCase().includes(q) ||
        u.last_name.toLowerCase().includes(q)
      )
      .slice(0, 50)
  }, [allUsers, userSearchQuery])

  const selectedUser = allUsers.find(u => u.id === userId)

  const handleSimulate = async () => {
    if (!userId.trim() || !newRoleId) return
    try {
      const res = await simulateMutation.mutateAsync({
        user_id: userId.trim(),
        new_role_id: newRoleId,
      })
      setResult(res)
    } catch {
      // handled by react-query
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <User className="h-5 w-5" />
          Simulador de Cambio de Rol
        </CardTitle>
        <CardDescription>
          Simula el impacto de cambiar el rol de un usuario SIN aplicar el cambio.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-2">
            <Label>Usuario</Label>
            <Popover open={userSearchOpen} onOpenChange={setUserSearchOpen}>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  role="combobox"
                  aria-expanded={userSearchOpen}
                  className="w-full justify-between font-normal"
                >
                  {selectedUser
                    ? `${selectedUser.first_name} ${selectedUser.last_name}`
                    : 'Buscar usuario...'}
                  <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[350px] p-0" align="start">
                <Command shouldFilter={false}>
                  <CommandInput
                    placeholder="Buscar por nombre o email..."
                    value={userSearchQuery}
                    onValueChange={setUserSearchQuery}
                  />
                  <CommandList>
                    <CommandEmpty>No se encontraron usuarios.</CommandEmpty>
                    <CommandGroup>
                      {filteredUsers.map(u => (
                        <CommandItem
                          key={u.id}
                          value={u.id}
                          onSelect={(val) => {
                            setUserId(val === userId ? '' : val)
                            setUserSearchOpen(false)
                          }}
                        >
                          <Check className={cn('mr-2 h-4 w-4', userId === u.id ? 'opacity-100' : 'opacity-0')} />
                          <div className="flex flex-col">
                            <span className="font-medium">{u.first_name} {u.last_name}</span>
                            <span className="text-xs text-muted-foreground">{u.email} · {u.role}</span>
                          </div>
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
          </div>

          <div className="space-y-2">
            <Label>Nuevo Rol</Label>
            <Select value={newRoleId} onValueChange={setNewRoleId}>
              <SelectTrigger>
                <SelectValue placeholder="Seleccionar rol..." />
              </SelectTrigger>
              <SelectContent>
                {roles.map(r => (
                  <SelectItem key={r.id} value={r.id}>
                    {r.name} ({r.code})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-end">
            <Button
              onClick={handleSimulate}
              disabled={simulateMutation.isPending || !userId.trim() || !newRoleId}
              className="w-full"
            >
              <Search className="h-4 w-4 mr-2" />
              Simular Cambio
            </Button>
          </div>
        </div>

        {/* Results */}
        {result && (
          <div className="mt-6 space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              {result.full_name && (
                <span className="font-medium">{result.full_name}</span>
              )}
              {result.new_role?.code && (
                <Badge variant="outline">
                  Nuevo rol: {result.new_role.name || result.new_role.code}
                </Badge>
              )}
              <Badge variant="secondary">
                {result.total_before} <ArrowRight className="inline h-3 w-3 mx-1" /> {result.total_after} permisos
              </Badge>
              <Badge variant="secondary">
                {result.unchanged} sin cambio
              </Badge>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Added permissions */}
              <div className="border rounded-lg p-4">
                <h4 className="font-medium text-green-600 mb-2 flex items-center gap-2">
                  <Plus className="h-4 w-4" />
                  Permisos ganados ({result.added.length})
                </h4>
                {result.added.length > 0 ? (
                  <div className="flex flex-wrap gap-1">
                    {result.added.map(p => (
                      <Badge key={p} variant="outline" className="text-green-600 border-green-200">
                        {p}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-muted-foreground text-sm">Ninguno</p>
                )}
              </div>

              {/* Removed permissions */}
              <div className="border rounded-lg p-4">
                <h4 className="font-medium text-red-600 mb-2 flex items-center gap-2">
                  <Minus className="h-4 w-4" />
                  Permisos perdidos ({result.removed.length})
                </h4>
                {result.removed.length > 0 ? (
                  <div className="flex flex-wrap gap-1">
                    {result.removed.map(p => (
                      <Badge key={p} variant="outline" className="text-red-600 border-red-200">
                        {p}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-muted-foreground text-sm">Ninguno</p>
                )}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// =============================================================================
// OVERPRIVILEGED USERS PANEL
// =============================================================================

function OverprivilegedUsersPanel() {
  const [minScore, setMinScore] = useState(20)
  const { data, isLoading, refetch } = useOverprivilegedUsers({ min_risk_score: minScore })

  const riskColors: Record<string, string> = {
    CRITICAL: 'bg-red-100 text-red-800 border-red-200',
    HIGH: 'bg-orange-100 text-orange-800 border-orange-200',
    MEDIUM: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    LOW: 'bg-green-100 text-green-800 border-green-200',
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5" />
          Deteccion de Usuarios Sobreprivilegiados
        </CardTitle>
        <CardDescription>
          Analisis de anomalias de permisos basado en scoring de riesgo.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-4">
          <div className="space-y-1">
            <Label>Puntuacion minima de riesgo</Label>
            <Input
              type="number"
              min={0}
              max={100}
              value={minScore}
              onChange={e => setMinScore(Number(e.target.value))}
              className="w-24"
            />
          </div>
          <Button
            onClick={() => refetch()}
            disabled={isLoading}
            variant="outline"
            className="mt-6"
          >
            <Search className="h-4 w-4 mr-2" />
            Analizar
          </Button>
          {data && (
            <Badge variant="secondary" className="mt-6">
              {data.count} usuarios detectados
            </Badge>
          )}
        </div>

        {data && data.overprivileged_users.length > 0 && (
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted">
                <tr>
                  <th className="text-left p-3">Usuario</th>
                  <th className="text-left p-3">Rol</th>
                  <th className="text-center p-3">Riesgo</th>
                  <th className="text-right p-3">Puntuacion</th>
                </tr>
              </thead>
              <tbody>
                {data.overprivileged_users.map((u: OverprivilegedUser) => (
                  <tr key={u.user_id} className="border-t">
                    <td className="p-3">
                      <div className="font-medium">{u.full_name}</div>
                      <div className="text-muted-foreground text-xs">{u.email}</div>
                    </td>
                    <td className="p-3">
                      <Badge variant="outline">{u.role_code}</Badge>
                    </td>
                    <td className="p-3 text-center">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${riskColors[u.risk_level] || ''}`}>
                        {u.risk_level}
                      </span>
                    </td>
                    <td className="p-3 text-right font-mono">
                      {u.risk_score}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {data && data.overprivileged_users.length === 0 && (
          <p className="text-muted-foreground text-center py-8">
            No se detectaron usuarios sobreprivilegiados con la puntuacion minima de {minScore}.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
