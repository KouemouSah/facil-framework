/**
 * Edit USSD Configuration Page
 */

'use client'

import { useParams, useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { ArrowLeft, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { useUssdConfig, useUpdateUssdConfig, useUssdOperators } from '@/modules/communications/hooks/useUssdConfigs'
import { UssdMenuEditor } from '@/modules/communications/components'
import type { MenuNode } from '@/modules/communications/types'
import { useEffect, useState } from 'react'

const formSchema = z.object({
  operatorName: z.enum(['getesa', 'muni', 'other_api_sms']).optional(),
  operatorCode: z.string().min(1).optional(),
  shortCode: z.string().regex(/^\*\d+#$/).optional(),
  apiEndpoint: z.string().url().optional().or(z.literal('')),
  sessionTimeoutSeconds: z.number().min(30).max(600).optional(),
  maxInputLength: z.number().min(1).max(500).optional(),
  isActive: z.boolean().optional(),
})

export default function EditUssdConfigPage() {
  const params = useParams()
  const router = useRouter()
  const configId = parseInt(params.id as string)

  const { data: config, isLoading } = useUssdConfig(configId)
  const { data: operators } = useUssdOperators()
  const updateMutation = useUpdateUssdConfig()

  // State for menu structure (managed separately from form)
  const [menuStructure, setMenuStructure] = useState<MenuNode[]>([])
  const [menuChanged, setMenuChanged] = useState(false)

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      operatorName: undefined,
      operatorCode: '',
      shortCode: '',
      apiEndpoint: '',
      sessionTimeoutSeconds: 180,
      maxInputLength: 160,
      isActive: true,
    },
  })

  useEffect(() => {
    if (config) {
      form.reset({
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        operatorName: config.operatorName as 'getesa' | 'muni' | 'other_api_sms',
        operatorCode: config.operatorCode,
        shortCode: config.shortCode,
        apiEndpoint: config.apiEndpoint || '',
        sessionTimeoutSeconds: config.sessionTimeoutSeconds,
        maxInputLength: config.maxInputLength,
        isActive: config.isActive,
      })
      // Initialize menu structure from config
      setMenuStructure(config.menuStructure || [])
    }
  }, [config, form])

  const handleMenuChange = (menus: MenuNode[]) => {
    setMenuStructure(menus)
    setMenuChanged(true)
  }

  const onSubmit = async (values: z.infer<typeof formSchema>) => {
    try {
      // Include menu structure if it was changed
      const updateData = {
        ...values,
        ...(menuChanged && { menuStructure }),
      }
      await updateMutation.mutateAsync({
        configId,
        data: updateData as Parameters<typeof updateMutation.mutateAsync>[0]['data'],
      })
      router.push('/dashboard/admin/communications/ussd')
    } catch (error) {
      console.error('Failed to update config:', error)
    }
  }

  if (isLoading) {
    return (
      <div className="container mx-auto py-6">
        <div className="text-center">Loading...</div>
      </div>
    )
  }

  if (!config) {
    return (
      <div className="container mx-auto py-6">
        <div className="text-center text-destructive">Configuration not found</div>
      </div>
    )
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold">Edit USSD Configuration</h1>
          <p className="text-muted-foreground">Update configuration for {config.shortCode}</p>
        </div>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Basic Information</CardTitle>
              <CardDescription>Update operator details and settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <FormField
                control={form.control}
                name="operatorName"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Mobile Operator</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value ?? config?.operatorName ?? ''}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select a mobile operator" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {operators?.map((op) => (
                          <SelectItem key={op.value} value={op.value}>
                            {op.name} - {op.description}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="operatorCode"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Operator Code</FormLabel>
                    <FormControl>
                      <Input placeholder="GETESA_EG" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="shortCode"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>USSD Short Code</FormLabel>
                    <FormControl>
                      <Input placeholder="*123#" {...field} />
                    </FormControl>
                    <FormDescription>Format: *XXX#</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="apiEndpoint"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>API Endpoint (Optional)</FormLabel>
                    <FormControl>
                      <Input placeholder="https://api.operator.gq/ussd" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="sessionTimeoutSeconds"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Session Timeout (seconds)</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          {...field}
                          onChange={(e) => field.onChange(parseInt(e.target.value))}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="maxInputLength"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Max Input Length</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          {...field}
                          onChange={(e) => field.onChange(parseInt(e.target.value))}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="isActive"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                    <div className="space-y-0.5">
                      <FormLabel className="text-base">Active</FormLabel>
                      <FormDescription>Enable or disable this configuration</FormDescription>
                    </div>
                    <FormControl>
                      <Switch checked={field.value} onCheckedChange={field.onChange} />
                    </FormControl>
                  </FormItem>
                )}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Menu Structure</CardTitle>
              <CardDescription>
                Configure USSD menu tree with options and navigation
                {menuChanged && (
                  <span className="ml-2 text-orange-600 font-medium">(Modified)</span>
                )}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <UssdMenuEditor
                menuStructure={menuStructure}
                onChange={handleMenuChange}
              />
            </CardContent>
          </Card>

          <div className="flex justify-end gap-4">
            <Button type="button" variant="outline" onClick={() => router.back()}>
              Cancel
            </Button>
            <Button type="submit" disabled={updateMutation.isPending}>
              <Save className="mr-2 h-4 w-4" />
              {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </form>
      </Form>
    </div>
  )
}
