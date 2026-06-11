# Communications Module

React components, hooks, and services for the TaxasGE communications system.

## Structure

```
communications/
├── components/           # React components
│   ├── NotificationTemplateList.tsx
│   ├── NotificationTemplateForm.tsx
│   ├── NotificationPreview.tsx
│   ├── PushPreview.tsx
│   ├── PushTemplateForm.tsx
│   ├── WebhookList.tsx
│   ├── WebhookForm.tsx
│   └── WebhookTestDialog.tsx
├── hooks/               # React Query hooks
│   └── useNotificationTemplates.ts
├── services/            # API service layer
│   └── notification-template-api.ts
└── types/              # TypeScript interfaces
    ├── index.ts
    └── notification-template.ts
```

## Components

### NotificationTemplateList
Displays a table of notification templates with filtering, pagination, and actions.

**Usage:**
```tsx
import { NotificationTemplateList } from '@/modules/communications/components'

<NotificationTemplateList locale="es" />
```

### NotificationTemplateForm
Form for creating and editing notification templates with multilingual support.

**Usage:**
```tsx
import { NotificationTemplateForm } from '@/modules/communications/components'

// Create mode
<NotificationTemplateForm locale="es" mode="create" />

// Edit mode
<NotificationTemplateForm locale="es" mode="edit" template={template} />
```

### NotificationPreview
Live preview of how a notification will appear to users.

**Usage:**
```tsx
import { NotificationPreview } from '@/modules/communications/components'

<NotificationPreview
  preview={previewData}
  onClose={() => setShowPreview(false)}
  isDialog={true}
/>
```

## Hooks

### useNotificationTemplates
List notification templates with filters and pagination.

```tsx
import { useNotificationTemplates } from '@/modules/communications/hooks/useNotificationTemplates'

const { data, isLoading, error } = useNotificationTemplates({
  page: 1,
  pageSize: 20,
  isActive: true,
  notificationType: 'success',
  search: 'payment',
})
```

### useNotificationTemplate
Get a single notification template by ID.

```tsx
const { data: template } = useNotificationTemplate(templateId)
```

### useCreateNotificationTemplate
Create a new notification template.

```tsx
const createMutation = useCreateNotificationTemplate()

await createMutation.mutateAsync({
  templateCode: 'payment_confirmation',
  nameEs: 'Confirmación de Pago',
  titleEs: 'Pago recibido',
  bodyEs: 'Su pago de {{amount}} ha sido procesado',
  variables: ['amount'],
  notificationType: 'success',
  priority: 'normal',
  isActive: true,
})
```

### useUpdateNotificationTemplate
Update an existing notification template.

```tsx
const updateMutation = useUpdateNotificationTemplate()

await updateMutation.mutateAsync({
  id: templateId,
  data: { isActive: false },
})
```

### useDeleteNotificationTemplate
Delete a notification template.

```tsx
const deleteMutation = useDeleteNotificationTemplate()

await deleteMutation.mutateAsync(templateId)
```

### usePreviewNotification
Preview a notification with variable substitution.

```tsx
const previewMutation = usePreviewNotification()

const preview = await previewMutation.mutateAsync({
  templateId: 1,
  language: 'es',
  variables: { amount: '5000 XAF' },
})
```

## API Service

### notificationTemplateApi

```typescript
import { notificationTemplateApi } from '@/modules/communications/services/notification-template-api'

// Create
const template = await notificationTemplateApi.create(data)

// Get by ID
const template = await notificationTemplateApi.getById(1)

// Get by code
const template = await notificationTemplateApi.getByCode('payment_confirmation')

// List with filters
const result = await notificationTemplateApi.list({
  page: 1,
  pageSize: 20,
  isActive: true,
})

// Update
const updated = await notificationTemplateApi.update(1, data)

// Delete
await notificationTemplateApi.delete(1)

// Preview
const preview = await notificationTemplateApi.preview({
  templateId: 1,
  language: 'es',
  variables: { amount: '5000' },
})

// Get active templates
const activeTemplates = await notificationTemplateApi.getActive()
```

## Types

### NotificationType
```typescript
type NotificationType = 'info' | 'success' | 'warning' | 'error'
```

### NotificationPriority
```typescript
type NotificationPriority = 'low' | 'normal' | 'high' | 'urgent'
```

### NotificationTemplateResponse
```typescript
interface NotificationTemplateResponse {
  id: number
  templateCode: string
  nameEs: string
  nameFr?: string
  nameEn?: string
  titleEs: string
  titleFr?: string
  titleEn?: string
  bodyEs: string
  bodyFr?: string
  bodyEn?: string
  icon?: string
  actionUrl?: string
  variables: string[]
  notificationType: NotificationType
  priority: NotificationPriority
  isActive: boolean
  createdAt: string
  updatedAt?: string
  createdBy?: number
}
```

## Color Coding

Notification types are color-coded:
- **info** - Blue (#3B82F6)
- **success** - Green (#10B981)
- **warning** - Yellow (#F59E0B)
- **error** - Red (#EF4444)

## Variable System

Templates support dynamic variables using `{{variable_name}}` syntax:

```
Title: Payment Received
Body: We have received your payment of {{amount}} for {{service_name}}
URL: /dashboard/payments/{{payment_id}}

Variables: ['amount', 'service_name', 'payment_id']
```

## Admin Routes

- List: `/[locale]/dashboard/admin/communications/notification-templates`
- Create: `/[locale]/dashboard/admin/communications/notification-templates/new`
- View: `/[locale]/dashboard/admin/communications/notification-templates/[id]`
- Edit: `/[locale]/dashboard/admin/communications/notification-templates/[id]/edit`

## Permissions

All notification template operations require admin permissions. Ensure the user has the appropriate role or permissions.
