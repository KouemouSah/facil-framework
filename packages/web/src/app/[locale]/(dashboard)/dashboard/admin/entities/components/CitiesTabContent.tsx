'use client'

/**
 * Cities Tab Content
 * CRUD management for cities
 */

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  MapPin,
  RefreshCw,
  Plus,
  Edit,
  Trash2,
  Search,
  AlertTriangle,
  Star,
} from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import {
  useCities,
  useCreateCity,
  useUpdateCity,
  useDeleteCity,
} from '@/modules/cities'
import type { City, CityCreate, CityUpdate, Region } from '@/modules/cities'

interface CityFormData {
  name: string
  region: Region
  description: string
  is_capital: boolean
  is_active: boolean
}

const defaultFormData: CityFormData = {
  name: '',
  region: 'Insular',
  description: '',
  is_capital: false,
  is_active: true,
}

export default function CitiesTabContent() {
  const t = useTranslations('admin.entities.cities')
  const tCommon = useTranslations('common')
  const { toast } = useToast()

  // Filter states
  const [searchQuery, setSearchQuery] = useState('')
  const [regionFilter, setRegionFilter] = useState<'all' | Region>('all')

  // Modal states
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [selectedCity, setSelectedCity] = useState<City | null>(null)
  const [formData, setFormData] = useState<CityFormData>(defaultFormData)

  // Queries
  const { data: citiesData, isLoading, error, refetch } = useCities()

  // Mutations
  const createMutation = useCreateCity()
  const updateMutation = useUpdateCity()
  const deleteMutation = useDeleteCity()

  const cities = citiesData?.items || []

  // Filter cities
  const filteredCities = cities.filter((c) => {
    if (regionFilter !== 'all' && c.region !== regionFilter) return false
    if (!searchQuery) return true
    const search = searchQuery.toLowerCase()
    return c.name.toLowerCase().includes(search) || c.description?.toLowerCase().includes(search)
  })

  // Open create dialog
  const handleCreate = () => {
    setSelectedCity(null)
    setFormData(defaultFormData)
    setIsDialogOpen(true)
  }

  // Open edit dialog
  const handleEdit = (city: City) => {
    setSelectedCity(city)
    setFormData({
      name: city.name,
      region: city.region,
      description: city.description || '',
      is_capital: city.is_capital,
      is_active: city.is_active,
    })
    setIsDialogOpen(true)
  }

  // Open delete confirmation
  const handleDeleteClick = (city: City) => {
    setSelectedCity(city)
    setIsDeleteDialogOpen(true)
  }

  // Submit form
  const handleSubmit = async () => {
    if (!formData.name) {
      toast({
        variant: 'destructive',
        title: tCommon('error'),
        description: t('messages.nameRequired'),
      })
      return
    }

    try {
      if (selectedCity) {
        await updateMutation.mutateAsync({
          cityId: selectedCity.id,
          data: formData as CityUpdate,
        })
        toast({ title: tCommon('success'), description: t('messages.updateSuccess') })
      } else {
        await createMutation.mutateAsync(formData as CityCreate)
        toast({ title: tCommon('success'), description: t('messages.createSuccess') })
      }
      setIsDialogOpen(false)
      refetch()
    } catch (err) {
      toast({
        variant: 'destructive',
        title: tCommon('error'),
        description: err instanceof Error ? err.message : t('messages.saveError'),
      })
    }
  }

  // Delete city
  const handleDelete = async () => {
    if (!selectedCity) return

    try {
      await deleteMutation.mutateAsync(selectedCity.id)
      toast({ title: tCommon('success'), description: t('messages.deleteSuccess') })
      setIsDeleteDialogOpen(false)
      refetch()
    } catch (err) {
      toast({
        variant: 'destructive',
        title: tCommon('error'),
        description: err instanceof Error ? err.message : t('messages.deleteError'),
      })
    }
  }

  // Stats
  const insularCount = cities.filter((c) => c.region === 'Insular').length
  const continentalCount = cities.filter((c) => c.region === 'Continental').length

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('stats.totalCities')}</CardTitle>
            <MapPin className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{cities.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('stats.insular')}</CardTitle>
            <MapPin className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{insularCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('stats.continental')}</CardTitle>
            <MapPin className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{continentalCount}</div>
          </CardContent>
        </Card>
      </div>

      {/* Cities Table */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>{t('list.title')}</CardTitle>
                <CardDescription>
                  {t('list.found', { count: filteredCities.length })}
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="outline" onClick={() => refetch()}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  {tCommon('refresh')}
                </Button>
                <Button size="sm" onClick={handleCreate}>
                  <Plus className="h-4 w-4 mr-2" />
                  {t('list.addCity')}
                </Button>
              </div>
            </div>

            {/* Filters */}
            <div className="flex gap-4 flex-wrap">
              <div className="relative max-w-sm">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder={t('list.searchPlaceholder')}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Select
                value={regionFilter}
                onValueChange={(v) => setRegionFilter(v as 'all' | Region)}
              >
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder={t('table.region')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('list.allRegions')}</SelectItem>
                  <SelectItem value="Insular">{t('stats.insular')}</SelectItem>
                  <SelectItem value="Continental">{t('stats.continental')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
              <span className="ml-2 text-muted-foreground">{t('loading')}</span>
            </div>
          )}

          {error && (
            <div className="flex items-center justify-center py-8 text-red-500">
              <AlertTriangle className="h-5 w-5 mr-2" />
              {error.message}
            </div>
          )}

          {!isLoading && !error && filteredCities.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <MapPin className="h-12 w-12 mb-4 opacity-50" />
              <p>{t('list.noCitiesFound')}</p>
              <Button className="mt-4" onClick={handleCreate}>
                <Plus className="h-4 w-4 mr-2" />
                {t('list.addFirstCity')}
              </Button>
            </div>
          )}

          {!isLoading && !error && filteredCities.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('table.name')}</TableHead>
                  <TableHead>{t('table.region')}</TableHead>
                  <TableHead>{t('table.description')}</TableHead>
                  <TableHead>{t('table.status')}</TableHead>
                  <TableHead className="text-right">{t('table.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredCities.map((city) => (
                  <TableRow key={city.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        {city.name}
                        {city.is_capital && (
                          <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={city.region === 'Insular' ? 'default' : 'secondary'}>
                        {city.region === 'Insular' ? t('stats.insular') : t('stats.continental')}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-[200px] truncate text-muted-foreground">
                      {city.description || '-'}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={
                          city.is_active
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-700'
                        }
                      >
                        {city.is_active ? t('status.active') : t('status.inactive')}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button variant="ghost" size="sm" onClick={() => handleEdit(city)}>
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleDeleteClick(city)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {selectedCity ? t('form.editTitle') : t('form.addTitle')}
            </DialogTitle>
            <DialogDescription>
              {selectedCity ? t('form.editDescription') : t('form.addDescription')}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">{t('form.nameRequired')}</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder={t('form.namePlaceholder')}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="region">{t('form.regionRequired')}</Label>
              <Select
                value={formData.region}
                onValueChange={(v) => setFormData({ ...formData, region: v as Region })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Insular">{t('stats.insular')}</SelectItem>
                  <SelectItem value="Continental">{t('stats.continental')}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">{t('form.description')}</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder={t('form.descriptionPlaceholder')}
                rows={2}
              />
            </div>

            <div className="flex items-center space-x-2">
              <Switch
                id="is_capital"
                checked={formData.is_capital}
                onCheckedChange={(checked) => setFormData({ ...formData, is_capital: checked })}
              />
              <Label htmlFor="is_capital">{t('form.capitalCity')}</Label>
            </div>

            <div className="flex items-center space-x-2">
              <Switch
                id="is_active"
                checked={formData.is_active}
                onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
              />
              <Label htmlFor="is_active">{t('form.active')}</Label>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
              {tCommon('cancel')}
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {(createMutation.isPending || updateMutation.isPending) && (
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              )}
              {selectedCity ? t('form.saveChanges') : t('form.create')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('delete.title')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('delete.description', { name: selectedCity?.name || '' })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tCommon('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-red-600 hover:bg-red-700"
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending && <RefreshCw className="h-4 w-4 mr-2 animate-spin" />}
              {t('delete.button')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
