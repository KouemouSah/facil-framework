'use client'

import { useEffect, useMemo } from 'react'
import { useTranslations } from 'next-intl'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Loader2, ChevronLeft, ChevronRight, X } from 'lucide-react'

import {
  DEFAULT_CITIES,
  DEFAULT_CITY_REGION_MAP,
  DEFAULT_ENTITY_CODES,
  DEFAULT_ENTITY_INFO,
  REGIONS,
  getCityRegion,
  type EntityLocation,
  type EntityLocationCreate,
  type Region,
} from '../types'

import { useCitiesSimple, useEntitiesSimple } from '@/modules/cities'

const entityLocationSchema = z.object({
  entity_code: z.string().min(2, 'Entity code is required').max(50),
  city: z.string().min(2, 'City is required').max(100),
  region: z.enum(REGIONS, {
    required_error: 'Region is required',
  }),
  location_name: z
    .string()
    .min(3, 'Location name must be at least 3 characters')
    .max(255, 'Location name must be at most 255 characters'),
  location_address: z.string().nullable().optional(),
  phone: z
    .string()
    .regex(/^\+?[0-9\s-]*$/, 'Invalid phone number format')
    .nullable()
    .optional()
    .or(z.literal('')),
  email: z.string().email('Invalid email').nullable().optional().or(z.literal('')),
  is_main_office: z.boolean().default(false),
  is_active: z.boolean().default(true),
  notes: z.string().nullable().optional(),
})

type FormData = z.infer<typeof entityLocationSchema>

interface EntityLocationFormProps {
  location?: EntityLocation
  onSubmit: (data: EntityLocationCreate) => void
  onCancel: () => void
  isLoading?: boolean
  onPrevious?: () => void
  onNext?: () => void
  hasPrevious?: boolean
  hasNext?: boolean
}

export function EntityLocationForm({
  location,
  onSubmit,
  onCancel,
  isLoading = false,
  onPrevious,
  onNext,
  hasPrevious = false,
  hasNext = false,
}: EntityLocationFormProps) {
  const t = useTranslations('admin.serviceRequests.appointments.locations.form')
  const tCommon = useTranslations('common')

  // Fetch cities and entities from API
  const { data: apiCities, isLoading: citiesLoading } = useCitiesSimple(true)
  const { data: apiEntities, isLoading: entitiesLoading } = useEntitiesSimple(true)

  const form = useForm<FormData>({
    resolver: zodResolver(entityLocationSchema),
    defaultValues: {
      entity_code: location?.entity_code || '',
      city: location?.city || '',
      region: location?.region || 'Continental',
      location_name: location?.location_name || '',
      location_address: location?.location_address || '',
      phone: location?.phone || '',
      email: location?.email || '',
      is_main_office: location?.is_main_office || false,
      is_active: location?.is_active ?? true,
      notes: location?.notes || '',
    },
  })

  const watchedCity = form.watch('city')

  // Build city list from API or fallback to defaults
  const cities = useMemo(() => {
    if (apiCities && apiCities.length > 0) {
      return apiCities
    }
    // Fallback to defaults if API not available
    return DEFAULT_CITIES.map((name) => ({
      id: name,
      name,
      region: DEFAULT_CITY_REGION_MAP[name] || ('Continental' as Region),
      is_capital: name === 'Malabo',
    }))
  }, [apiCities])

  // Build entity list from API or fallback to defaults
  const entities = useMemo(() => {
    if (apiEntities && apiEntities.length > 0) {
      return apiEntities
    }
    // Fallback to defaults if API not available
    return DEFAULT_ENTITY_CODES.map((code) => ({
      id: code,
      code,
      name: DEFAULT_ENTITY_INFO[code]?.description || code,
    }))
  }, [apiEntities])

  // Build city region map from API data
  const cityRegionMap = useMemo(() => {
    const map: Record<string, Region> = { ...DEFAULT_CITY_REGION_MAP }
    if (apiCities) {
      apiCities.forEach((city) => {
        map[city.name] = city.region
      })
    }
    return map
  }, [apiCities])

  // Auto-fill region when city changes
  useEffect(() => {
    if (watchedCity) {
      const suggestedRegion = cityRegionMap[watchedCity] || getCityRegion(watchedCity)
      form.setValue('region', suggestedRegion)
    }
  }, [watchedCity, form, cityRegionMap])

  // Reset form when location changes
  useEffect(() => {
    if (location) {
      form.reset({
        entity_code: location.entity_code,
        city: location.city,
        region: location.region,
        location_name: location.location_name,
        location_address: location.location_address || '',
        phone: location.phone || '',
        email: location.email || '',
        is_main_office: location.is_main_office,
        is_active: location.is_active,
        notes: location.notes || '',
      })
    }
  }, [location, form])

  const handleSubmit = (data: FormData) => {
    const submitData: EntityLocationCreate = {
      entity_code: data.entity_code.toUpperCase(),
      city: data.city,
      region: data.region,
      location_name: data.location_name,
      location_address: data.location_address || null,
      phone: data.phone || null,
      email: data.email || null,
      is_main_office: data.is_main_office,
      is_active: data.is_active,
      notes: data.notes || null,
    }
    onSubmit(submitData)
  }


  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
        {/* Navigation Header */}
        <div className="flex items-center justify-between border-b pb-4">
          <div className="flex items-center gap-2">
            {hasPrevious && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={onPrevious}
                disabled={isLoading}
              >
                <ChevronLeft className="h-4 w-4 mr-1" />
                {t('previous')}
              </Button>
            )}
          </div>
          <h2 className="text-lg font-semibold">
            {location ? t('editTitle') : t('createTitle')}
          </h2>
          <div className="flex items-center gap-2">
            {hasNext && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={onNext}
                disabled={isLoading}
              >
                {t('next')}
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            )}
            <Button type="button" variant="ghost" size="icon" onClick={onCancel}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* City, Region, and Entity */}
        <div className="grid gap-4 md:grid-cols-3">
          {/* City Select */}
          <FormField
            control={form.control}
            name="city"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('city')} *</FormLabel>
                <Select
                  onValueChange={field.onChange}
                  value={field.value}
                  disabled={!!location || citiesLoading}
                >
                  <FormControl>
                    <SelectTrigger>
                      {citiesLoading ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <SelectValue placeholder={t('selectCity')} />
                      )}
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {cities.map((city) => (
                      <SelectItem key={city.id} value={city.name}>
                        <div className="flex items-center gap-2">
                          <span>{city.name}</span>
                          <Badge variant="outline" className="text-xs">
                            {city.region}
                          </Badge>
                          {city.is_capital && (
                            <Badge variant="secondary" className="text-xs">
                              Capital
                            </Badge>
                          )}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormDescription className="text-xs">
                  {t('cityDescription')}
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Region Select */}
          <FormField
            control={form.control}
            name="region"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('region')} *</FormLabel>
                <Select
                  onValueChange={field.onChange}
                  value={field.value}
                >
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder={t('selectRegion')} />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {REGIONS.map((region) => (
                      <SelectItem key={region} value={region}>
                        {region}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormDescription className="text-xs">
                  {t('regionDescription')}
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Entity Select */}
          <FormField
            control={form.control}
            name="entity_code"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('entityCode')} *</FormLabel>
                <Select
                  onValueChange={field.onChange}
                  value={field.value}
                  disabled={!!location || entitiesLoading}
                >
                  <FormControl>
                    <SelectTrigger>
                      {entitiesLoading ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <SelectValue placeholder={t('selectEntity')} />
                      )}
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {entities.map((entity) => (
                      <SelectItem key={entity.id} value={entity.code}>
                        <div className="flex flex-col">
                          <span className="font-medium">{entity.code}</span>
                          <span className="text-xs text-muted-foreground">
                            {entity.name}
                          </span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormDescription className="text-xs">
                  {t('entityDescription')}
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {/* Location Name and Address */}
        <FormField
          control={form.control}
          name="location_name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('locationName')} *</FormLabel>
              <FormControl>
                <Input placeholder={t('locationNamePlaceholder')} {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="location_address"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('address')}</FormLabel>
              <FormControl>
                <Input
                  placeholder={t('addressPlaceholder')}
                  {...field}
                  value={field.value || ''}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Contact Info */}
        <div className="grid gap-4 md:grid-cols-2">
          <FormField
            control={form.control}
            name="phone"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('phone')}</FormLabel>
                <FormControl>
                  <Input
                    placeholder="+240 222 XXX XXX"
                    {...field}
                    value={field.value || ''}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('email')}</FormLabel>
                <FormControl>
                  <Input
                    type="email"
                    placeholder="contact@example.com"
                    {...field}
                    value={field.value || ''}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {/* Checkboxes */}
        <div className="flex flex-wrap gap-6">
          <FormField
            control={form.control}
            name="is_main_office"
            render={({ field }) => (
              <FormItem className="flex flex-row items-start space-x-3 space-y-0">
                <FormControl>
                  <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                </FormControl>
                <div className="space-y-1 leading-none">
                  <FormLabel>{t('mainOffice')}</FormLabel>
                  <FormDescription>{t('mainOfficeDescription')}</FormDescription>
                </div>
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="is_active"
            render={({ field }) => (
              <FormItem className="flex flex-row items-start space-x-3 space-y-0">
                <FormControl>
                  <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                </FormControl>
                <div className="space-y-1 leading-none">
                  <FormLabel>{t('active')}</FormLabel>
                  <FormDescription>{t('activeDescription')}</FormDescription>
                </div>
              </FormItem>
            )}
          />
        </div>

        {/* Notes */}
        <FormField
          control={form.control}
          name="notes"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('notes')}</FormLabel>
              <FormControl>
                <Textarea
                  placeholder={t('notesPlaceholder')}
                  className="min-h-[80px]"
                  {...field}
                  value={field.value || ''}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Actions */}
        <div className="flex justify-end gap-4 pt-4 border-t">
          <Button type="button" variant="outline" onClick={onCancel} disabled={isLoading}>
            {tCommon('cancel')}
          </Button>
          <Button type="submit" disabled={isLoading}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {location ? tCommon('save') : tCommon('create')}
          </Button>
        </div>
      </form>
    </Form>
  )
}

export default EntityLocationForm
