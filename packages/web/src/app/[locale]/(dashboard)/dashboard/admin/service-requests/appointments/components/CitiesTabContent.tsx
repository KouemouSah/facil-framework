'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import {
  MapPin,
  Plus,
  Loader2,
  AlertCircle,
  Pencil,
  Trash2,
  Building,
  Star,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  useCities,
  useCreateCity,
  useUpdateCity,
  useDeleteCity,
  useEntities,
  useCreateEntity,
  useUpdateEntity,
  useDeleteEntity,
} from '@/modules/cities/hooks'
import type { City, CityCreate, CityUpdate, Entity, EntityCreate, EntityUpdate, Region } from '@/modules/cities/types'

type ManageType = 'cities' | 'entities'

export default function CitiesTabContent() {
  const t = useTranslations('admin.serviceRequests.appointments.citiesManagement')
  const tCommon = useTranslations('common')

  const [manageType, setManageType] = useState<ManageType>('cities')

  // Cities state
  const { data: citiesData, isLoading: citiesLoading, error: citiesError } = useCities()
  const createCityMutation = useCreateCity()
  const updateCityMutation = useUpdateCity()
  const deleteCityMutation = useDeleteCity()

  // Entities state
  const { data: entitiesData, isLoading: entitiesLoading, error: entitiesError } = useEntities()
  const createEntityMutation = useCreateEntity()
  const updateEntityMutation = useUpdateEntity()
  const deleteEntityMutation = useDeleteEntity()

  // Dialog state
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [editingCity, setEditingCity] = useState<City | null>(null)
  const [editingEntity, setEditingEntity] = useState<Entity | null>(null)
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)

  // Form state for city
  const [cityForm, setCityForm] = useState<CityCreate>({
    name: '',
    region: 'Insular',
    description: '',
    is_capital: false,
    is_active: true,
  })

  // Form state for entity
  const [entityForm, setEntityForm] = useState<EntityCreate>({
    code: '',
    name: '',
    description: '',
    is_active: true,
  })

  const cities = citiesData?.items || []
  const entities = entitiesData?.items || []
  const isLoading = manageType === 'cities' ? citiesLoading : entitiesLoading
  const error = manageType === 'cities' ? citiesError : entitiesError

  // City handlers
  const handleOpenCityDialog = (city?: City) => {
    if (city) {
      setEditingCity(city)
      setCityForm({
        name: city.name,
        region: city.region,
        description: city.description || '',
        is_capital: city.is_capital,
        is_active: city.is_active,
      })
    } else {
      setEditingCity(null)
      setCityForm({
        name: '',
        region: 'Insular',
        description: '',
        is_capital: false,
        is_active: true,
      })
    }
    setIsDialogOpen(true)
  }

  const handleSaveCity = async () => {
    try {
      if (editingCity) {
        await updateCityMutation.mutateAsync({
          cityId: editingCity.id,
          data: cityForm as CityUpdate,
        })
        toast.success(t('cityUpdated'))
      } else {
        await createCityMutation.mutateAsync(cityForm)
        toast.success(t('cityCreated'))
      }
      setIsDialogOpen(false)
    } catch {
      toast.error(editingCity ? t('cityUpdateError') : t('cityCreateError'))
    }
  }

  const handleDeleteCity = async (cityId: string) => {
    try {
      await deleteCityMutation.mutateAsync(cityId)
      toast.success(t('cityDeleted'))
      setDeleteConfirmId(null)
    } catch {
      toast.error(t('cityDeleteError'))
    }
  }

  // Entity handlers
  const handleOpenEntityDialog = (entity?: Entity) => {
    if (entity) {
      setEditingEntity(entity)
      setEntityForm({
        code: entity.code,
        name: entity.name,
        description: entity.description || '',
        is_active: entity.is_active,
      })
    } else {
      setEditingEntity(null)
      setEntityForm({
        code: '',
        name: '',
        description: '',
        is_active: true,
      })
    }
    setIsDialogOpen(true)
  }

  const handleSaveEntity = async () => {
    try {
      if (editingEntity) {
        await updateEntityMutation.mutateAsync({
          entityId: editingEntity.id,
          data: entityForm as EntityUpdate,
        })
        toast.success(t('entityUpdated'))
      } else {
        await createEntityMutation.mutateAsync(entityForm)
        toast.success(t('entityCreated'))
      }
      setIsDialogOpen(false)
    } catch {
      toast.error(editingEntity ? t('entityUpdateError') : t('entityCreateError'))
    }
  }

  const handleDeleteEntity = async (entityId: string) => {
    try {
      await deleteEntityMutation.mutateAsync(entityId)
      toast.success(t('entityDeleted'))
      setDeleteConfirmId(null)
    } catch {
      toast.error(t('entityDeleteError'))
    }
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <Card className="border-destructive">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span>{error instanceof Error ? error.message : 'Error loading data'}</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  const isSaving = createCityMutation.isPending || updateCityMutation.isPending ||
    createEntityMutation.isPending || updateEntityMutation.isPending

  return (
    <div className="space-y-6">
      {/* Type Selector */}
      <div className="flex items-center gap-4">
        <Button
          variant={manageType === 'cities' ? 'default' : 'outline'}
          onClick={() => setManageType('cities')}
          className="gap-2"
        >
          <MapPin className="h-4 w-4" />
          {t('cities')} ({cities.length})
        </Button>
        <Button
          variant={manageType === 'entities' ? 'default' : 'outline'}
          onClick={() => setManageType('entities')}
          className="gap-2"
        >
          <Building className="h-4 w-4" />
          {t('entities')} ({entities.length})
        </Button>
      </div>

      {/* Cities Table */}
      {manageType === 'cities' && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <MapPin className="h-5 w-5" />
                  {t('citiesTitle')}
                </CardTitle>
                <CardDescription>{t('citiesDescription')}</CardDescription>
              </div>
              <Button onClick={() => handleOpenCityDialog()}>
                <Plus className="mr-2 h-4 w-4" />
                {t('addCity')}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {cities.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <MapPin className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p className="text-lg font-medium mb-2">{t('noCities')}</p>
                <Button onClick={() => handleOpenCityDialog()}>
                  <Plus className="mr-2 h-4 w-4" />
                  {t('addFirstCity')}
                </Button>
              </div>
            ) : (
              <div className="border rounded-md">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('cityName')}</TableHead>
                      <TableHead>{t('region')}</TableHead>
                      <TableHead>{t('description')}</TableHead>
                      <TableHead className="text-center">{t('status')}</TableHead>
                      <TableHead className="text-right">{tCommon('actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {cities.map((city) => (
                      <TableRow key={city.id}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{city.name}</span>
                            {city.is_capital && (
                              <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={city.region === 'Insular' ? 'default' : 'secondary'}>
                            {city.region}
                          </Badge>
                        </TableCell>
                        <TableCell className="max-w-[200px] truncate">
                          {city.description || '-'}
                        </TableCell>
                        <TableCell className="text-center">
                          <Badge variant={city.is_active ? 'default' : 'outline'}>
                            {city.is_active ? tCommon('active') : tCommon('inactive')}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleOpenCityDialog(city)}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="text-destructive hover:text-destructive"
                              onClick={() => setDeleteConfirmId(city.id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Entities Table */}
      {manageType === 'entities' && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Building className="h-5 w-5" />
                  {t('entitiesTitle')}
                </CardTitle>
                <CardDescription>{t('entitiesDescription')}</CardDescription>
              </div>
              <Button onClick={() => handleOpenEntityDialog()}>
                <Plus className="mr-2 h-4 w-4" />
                {t('addEntity')}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {entities.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <Building className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p className="text-lg font-medium mb-2">{t('noEntities')}</p>
                <Button onClick={() => handleOpenEntityDialog()}>
                  <Plus className="mr-2 h-4 w-4" />
                  {t('addFirstEntity')}
                </Button>
              </div>
            ) : (
              <div className="border rounded-md">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('entityCode')}</TableHead>
                      <TableHead>{t('entityName')}</TableHead>
                      <TableHead>{t('description')}</TableHead>
                      <TableHead className="text-center">{t('status')}</TableHead>
                      <TableHead className="text-right">{tCommon('actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {entities.map((entity) => (
                      <TableRow key={entity.id}>
                        <TableCell>
                          <Badge variant="outline" className="font-mono">
                            {entity.code}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-medium">{entity.name}</TableCell>
                        <TableCell className="max-w-[200px] truncate">
                          {entity.description || '-'}
                        </TableCell>
                        <TableCell className="text-center">
                          <Badge variant={entity.is_active ? 'default' : 'outline'}>
                            {entity.is_active ? tCommon('active') : tCommon('inactive')}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleOpenEntityDialog(entity)}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="text-destructive hover:text-destructive"
                              onClick={() => setDeleteConfirmId(entity.id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* City Dialog */}
      {manageType === 'cities' && (
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editingCity ? t('editCity') : t('addCity')}
              </DialogTitle>
              <DialogDescription>
                {editingCity ? t('editCityDescription') : t('addCityDescription')}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="city-name">{t('cityName')}</Label>
                <Input
                  id="city-name"
                  value={cityForm.name}
                  onChange={(e) => setCityForm({ ...cityForm, name: e.target.value })}
                  placeholder={t('cityNamePlaceholder')}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="city-region">{t('region')}</Label>
                <Select
                  value={cityForm.region}
                  onValueChange={(v) => setCityForm({ ...cityForm, region: v as Region })}
                >
                  <SelectTrigger id="city-region">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Insular">Insular</SelectItem>
                    <SelectItem value="Continental">Continental</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="city-description">{t('description')}</Label>
                <Textarea
                  id="city-description"
                  value={cityForm.description || ''}
                  onChange={(e) => setCityForm({ ...cityForm, description: e.target.value })}
                  placeholder={t('descriptionPlaceholder')}
                />
              </div>
              <div className="flex items-center justify-between">
                <Label htmlFor="city-capital">{t('isCapital')}</Label>
                <Switch
                  id="city-capital"
                  checked={cityForm.is_capital}
                  onCheckedChange={(v) => setCityForm({ ...cityForm, is_capital: v })}
                />
              </div>
              <div className="flex items-center justify-between">
                <Label htmlFor="city-active">{t('isActive')}</Label>
                <Switch
                  id="city-active"
                  checked={cityForm.is_active}
                  onCheckedChange={(v) => setCityForm({ ...cityForm, is_active: v })}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
                {tCommon('cancel')}
              </Button>
              <Button onClick={handleSaveCity} disabled={isSaving || !cityForm.name}>
                {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {tCommon('save')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {/* Entity Dialog */}
      {manageType === 'entities' && (
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editingEntity ? t('editEntity') : t('addEntity')}
              </DialogTitle>
              <DialogDescription>
                {editingEntity ? t('editEntityDescription') : t('addEntityDescription')}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="entity-code">{t('entityCode')}</Label>
                <Input
                  id="entity-code"
                  value={entityForm.code}
                  onChange={(e) => setEntityForm({ ...entityForm, code: e.target.value.toUpperCase() })}
                  placeholder={t('entityCodePlaceholder')}
                  className="font-mono"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="entity-name">{t('entityName')}</Label>
                <Input
                  id="entity-name"
                  value={entityForm.name}
                  onChange={(e) => setEntityForm({ ...entityForm, name: e.target.value })}
                  placeholder={t('entityNamePlaceholder')}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="entity-description">{t('description')}</Label>
                <Textarea
                  id="entity-description"
                  value={entityForm.description || ''}
                  onChange={(e) => setEntityForm({ ...entityForm, description: e.target.value })}
                  placeholder={t('descriptionPlaceholder')}
                />
              </div>
              <div className="flex items-center justify-between">
                <Label htmlFor="entity-active">{t('isActive')}</Label>
                <Switch
                  id="entity-active"
                  checked={entityForm.is_active}
                  onCheckedChange={(v) => setEntityForm({ ...entityForm, is_active: v })}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
                {tCommon('cancel')}
              </Button>
              <Button onClick={handleSaveEntity} disabled={isSaving || !entityForm.code || !entityForm.name}>
                {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {tCommon('save')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteConfirmId} onOpenChange={() => setDeleteConfirmId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('confirmDelete')}</DialogTitle>
            <DialogDescription>{t('confirmDeleteDescription')}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirmId(null)}>
              {tCommon('cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (deleteConfirmId) {
                  if (manageType === 'cities') {
                    handleDeleteCity(deleteConfirmId)
                  } else {
                    handleDeleteEntity(deleteConfirmId)
                  }
                }
              }}
              disabled={deleteCityMutation.isPending || deleteEntityMutation.isPending}
            >
              {(deleteCityMutation.isPending || deleteEntityMutation.isPending) && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {tCommon('delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
