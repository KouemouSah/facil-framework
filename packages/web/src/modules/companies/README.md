# Company Member Management Components

Frontend UI components for managing company members in TaxasGE.

## Overview

This module provides a complete set of React components for managing company members, including:
- Displaying member lists with roles and status
- Adding new members to companies
- Changing member roles
- Removing members from companies
- Role-based access control

## Components

### 1. CompanyMembersManager (All-in-One)

The easiest way to implement member management. This component includes everything needed.

```tsx
import { CompanyMembersManager } from '@/modules/companies'

function CompanyPage({ companyId }: { companyId: string }) {
  return (
    <div className="container mx-auto p-6">
      <CompanyMembersManager
        companyId={companyId}
        currentUserId={currentUser.id}
        canManageMembers={hasPermission('companies.manage_members')}
      />
    </div>
  )
}
```

**Props:**
- `companyId` (required): The company UUID
- `currentUserId` (optional): Current user's ID (to highlight in the list)
- `canManageMembers` (optional): Whether user can add/remove members

### 2. MemberList

Display company members in a table with actions.

```tsx
import { MemberList } from '@/modules/companies'

<MemberList
  companyId="company-uuid"
  currentUserId="user-uuid"
  onChangeRole={(member) => handleRoleChange(member)}
  canManageMembers={true}
/>
```

**Props:**
- `companyId` (required): The company UUID
- `currentUserId` (optional): Highlights the current user with a "You" badge
- `onChangeRole` (optional): Callback when user clicks "Change Role"
- `canManageMembers` (optional): Shows/hides action buttons

**Features:**
- Displays member name, email, role, status, and join date
- Action dropdown for each member (if `canManageMembers` is true)
- Prevents removing owner or current user
- Confirmation dialog before removing members
- Optimistic updates for instant UI feedback

### 3. InviteMemberDialog

Dialog for adding members to a company.

```tsx
import { InviteMemberDialog } from '@/modules/companies'

const [open, setOpen] = useState(false)

<InviteMemberDialog
  companyId="company-uuid"
  open={open}
  onOpenChange={setOpen}
/>
```

**Props:**
- `companyId` (required): The company UUID
- `open` (required): Dialog open state
- `onOpenChange` (required): Callback to change open state

**Features:**
- Form validation with Zod
- User ID input (email-based invitations coming in future)
- Role selector (excludes owner role)
- Optimistic updates
- Success/error toast notifications

### 4. MemberRoleSelector

Dropdown for selecting company member roles.

```tsx
import { MemberRoleSelector } from '@/modules/companies'

<MemberRoleSelector
  value={selectedRole}
  onChange={(role) => setRole(role)}
  label="Select Role"
  excludeRoles={['company_owner']}
  disabled={false}
/>
```

**Props:**
- `value` (required): Current role value
- `onChange` (required): Callback when role changes
- `label` (optional): Label text for the selector
- `excludeRoles` (optional): Array of roles to exclude from the list
- `disabled` (optional): Disable the selector

**Available Roles:**
- `company_owner` - Full control, can delete company and transfer ownership
- `company_admin` - Manage members, declarations, and payments
- `company_accountant` - Manage declarations and payments
- `company_member` - View company and create own declarations

### Utility Functions

```tsx
import { getRoleLabel, getRoleDescription } from '@/modules/companies'

// Get human-readable label
getRoleLabel('company_admin') // Returns: "Admin"

// Get role description
getRoleDescription('company_admin')
// Returns: "Manage members, declarations, and payments"
```

## React Query Hooks

### useCompanyMembers

Fetch all members for a company.

```tsx
import { useCompanyMembers } from '@/modules/companies'

const { data: members, isLoading, error } = useCompanyMembers(companyId)
```

### useAddCompanyMember

Add a member to a company (with optimistic updates).

```tsx
import { useAddCompanyMember } from '@/modules/companies'

const addMember = useAddCompanyMember(companyId)

await addMember.mutateAsync({
  memberUserId: 'user-uuid',
  role: 'company_member',
})
```

### useRemoveCompanyMember

Remove a member from a company (with optimistic updates).

```tsx
import { useRemoveCompanyMember } from '@/modules/companies'

const removeMember = useRemoveCompanyMember(companyId)

await removeMember.mutateAsync(userId)
```

### useUpdateMemberRole

Update a member's role (with optimistic updates).

```tsx
import { useUpdateMemberRole } from '@/modules/companies'

const updateRole = useUpdateMemberRole(companyId)

await updateRole.mutateAsync({
  userId: 'user-uuid',
  role: 'company_admin',
})
```

**Note:** Backend endpoint not yet implemented. Will throw error if used.

## Types

```tsx
import type {
  CompanyMember,
  CompanyMemberRole,
  AddMemberRequest,
  UpdateMemberRoleRequest,
} from '@/modules/companies'

// CompanyMemberRole
type CompanyMemberRole =
  | 'company_owner'
  | 'company_admin'
  | 'company_accountant'
  | 'company_member'

// CompanyMember
interface CompanyMember {
  user_id: string
  company_id: string
  role: CompanyMemberRole
  is_active?: boolean
  assigned_at?: string
  user_email?: string | null
  user_name?: string | null
}
```

## Validation Schemas

```tsx
import { addMemberSchema, type AddMemberInput } from '@/modules/companies'

// Zod schema for form validation
const form = useForm<AddMemberInput>({
  resolver: zodResolver(addMemberSchema),
})
```

## Backend Alignment

All components are aligned with the backend API:

**Base URL:** `/api/v1/companies`

**Endpoints:**
- `GET /companies/{company_id}/members` - Get all members
- `POST /companies/{company_id}/members` - Add member (requires owner/admin)
- `DELETE /companies/{company_id}/members/{user_id}` - Remove member (requires owner/admin)

**Permissions:**
- Company owner/admin can add/remove members
- System admins with `companies.manage_members` permission can override
- Owner cannot remove themselves
- Members can view but not modify

## Features

### Optimistic Updates
All mutations include optimistic updates for instant UI feedback. If the backend request fails, changes are automatically rolled back.

### Error Handling
- Toast notifications for success/error states
- Form validation with Zod
- Detailed error messages from backend

### Confirmation Dialogs
- AlertDialog before removing members
- Prevents accidental deletions

### Role-Based Access
- Actions only shown when user has permissions
- Owner and current user cannot be removed
- Role selector excludes inappropriate roles

## Future Enhancements

1. **Email-based Invitations**
   - Send invitation emails to non-registered users
   - Invitation token system
   - Expiration dates

2. **Role Update Endpoint**
   - Backend API for updating roles without remove+add
   - More efficient role changes

3. **Bulk Operations**
   - Add multiple members at once
   - Bulk role changes

4. **Activity Tracking**
   - Member activity logs
   - Last login tracking

## Dependencies

- `@tanstack/react-query` - Data fetching and caching
- `react-hook-form` - Form handling
- `zod` - Schema validation
- `@hookform/resolvers` - Zod + React Hook Form integration
- `sonner` - Toast notifications
- `date-fns` - Date formatting
- `lucide-react` - Icons
- `@radix-ui/*` - UI primitives (via shadcn/ui)

## File Structure

```
packages/web/src/modules/companies/
├── components/
│   ├── CompanyCard.tsx
│   ├── MemberList.tsx
│   ├── InviteMemberDialog.tsx
│   ├── MemberRoleSelector.tsx
│   ├── CompanyMembersManager.tsx
│   └── index.ts
├── hooks/
│   └── useCompanyMembers.ts
├── services/
│   └── api.ts
├── types/
│   └── index.ts
├── validations/
│   └── members.ts
├── index.ts
└── README.md
```
