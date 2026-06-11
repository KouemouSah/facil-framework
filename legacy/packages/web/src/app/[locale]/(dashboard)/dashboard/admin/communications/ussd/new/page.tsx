/**
 * Create New USSD Configuration Page
 */

'use client'

import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { ArrowLeft, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { useCreateUssdConfig, useUssdOperators } from '@/modules/communications/hooks/useUssdConfigs'
import type { MenuNode } from '@/modules/communications/types'

// Simple inline menu builder for now
function MenuBuilder({ value, onChange }: { value: MenuNode[]; onChange: (v: MenuNode[]) => void }) {
  const addMenu = () => {
    const newMenu: MenuNode = {
      id: `menu_${Date.now()}`,
      titleEs: 'New Menu',
      options: [],
      isRoot: value.length === 0,
    }
    onChange([...value, newMenu])
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-sm text-muted-foreground">{value.length} menu(s) configured</p>
        <Button type="button" variant="outline" size="sm" onClick={addMenu}>
          Add Menu
        </Button>
      </div>
      {value.length === 0 && (
        <div className="text-center py-8 border-2 border-dashed rounded-lg">
          <p className="text-sm text-muted-foreground">No menus configured yet</p>
          <p className="text-xs text-muted-foreground">Click Add Menu to create your first menu</p>
        </div>
      )}
      {value.map((menu) => (
        <Card key={menu.id}>
          <CardHeader>
            <CardTitle className="text-sm">{menu.titleEs}</CardTitle>
            {menu.isRoot && <Badge>Root Menu</Badge>}
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">{menu.options.length} options</p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

const menuActionTypes = ['balance', 'payment', 'tax_info', 'service_search', 'declaration_status', 'support', 'custom'] as const

const menuNodeSchema: z.ZodType<MenuNode> = z.object({
  id: z.string(),
  titleEs: z.string(),
  titleFr: z.string().optional(),
  titleEn: z.string().optional(),
  options: z.array(z.object({
    key: z.string(),
    labelEs: z.string(),
    labelFr: z.string().optional(),
    labelEn: z.string().optional(),
    nextMenu: z.string().optional(),
    action: z.enum(menuActionTypes).optional(),
    actionParams: z.record(z.unknown()).optional(),
  })),
  isRoot: z.boolean().optional(),
  parentMenu: z.string().optional(),
})

const formSchema = z.object({
  operatorName: z.enum(['getesa', 'muni', 'other_api_sms']),
  operatorCode: z.string().min(1, 'Operator code is required'),
  shortCode: z.string().regex(/^\*\d+#$/, 'Must be format *XXX#'),
  apiEndpoint: z.string().url().optional().or(z.literal('')),
  sessionTimeoutSeconds: z.number().min(30).max(600),
  maxInputLength: z.number().min(1).max(500),
  isActive: z.boolean(),
  menuStructure: z.array(menuNodeSchema).min(1, 'At least one menu is required'),
})

export default function NewUssdConfigPage() {
  const router = useRouter()
  const { data: operators } = useUssdOperators()
  const createMutation = useCreateUssdConfig()

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      operatorName: 'getesa',
      operatorCode: '',
      shortCode: '*',
      sessionTimeoutSeconds: 180,
      maxInputLength: 160,
      isActive: true,
      menuStructure: [
        {
          id: 'main',
          titleEs: 'Bienvenido a Facil',
          titleFr: 'Bienvenue à Facil',
          titleEn: 'Welcome to Facil',
          isRoot: true,
          options: [
            { key: '1', labelEs: 'Consultar Saldo', action: 'balance' },
            { key: '2', labelEs: 'Información', action: 'tax_info' },
          ],
        },
      ],
    },
  })

  const onSubmit = async (values: z.infer<typeof formSchema>) => {
    try {
      await createMutation.mutateAsync({
        ...values,
        menuStructure: values.menuStructure as MenuNode[],
      })
      router.push('/dashboard/admin/communications/ussd')
    } catch (error) {
      console.error('Failed to create config:', error)
    }
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold">New USSD Configuration</h1>
          <p className="text-muted-foreground">Create a new USSD configuration for a mobile operator</p>
        </div>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Basic Information</CardTitle>
              <CardDescription>Configure operator details and short code</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <FormField
                control={form.control}
                name="operatorName"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Mobile Operator</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
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
                    <FormDescription>Unique identifier for this operator</FormDescription>
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
                      <FormDescription>Enable this configuration immediately</FormDescription>
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
              <CardDescription>Define the USSD menu tree</CardDescription>
            </CardHeader>
            <CardContent>
              <FormField
                control={form.control}
                name="menuStructure"
                render={({ field }) => (
                  <FormItem>
                    <FormControl>
                      <MenuBuilder value={field.value} onChange={field.onChange} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </CardContent>
          </Card>

          <div className="flex justify-end gap-4">
            <Button type="button" variant="outline" onClick={() => router.back()}>
              Cancel
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              <Save className="mr-2 h-4 w-4" />
              {createMutation.isPending ? 'Creating...' : 'Create Configuration'}
            </Button>
          </div>
        </form>
      </Form>
    </div>
  )
}
