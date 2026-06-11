# Accountant Multi-Client Dashboard Module

**Status:** ✅ Complete - Frontend Implementation
**Author:** Claude Code
**Date:** 2025-12-03

## Overview

The Accountant module provides a comprehensive multi-client dashboard for accountants managing multiple companies. It enables accountants to view, monitor, and manage declarations, deadlines, and tasks across all their client companies from a centralized interface.

## Features

### 1. Client List with Quick Stats
- View all managed companies with real-time statistics
- Quick stats: pending declarations, drafts, in-review, approved count
- Financial overview: total amount due, overdue amounts
- Next deadline preview for each client
- Search and filter capabilities
- Sortable by name, last activity, pending count, total due

### 2. Deadline Calendar
- Visual calendar view of upcoming deadlines across all clients
- Multiple views: Month, Week, List
- Color-coded priorities: Urgent, High, Medium, Low
- Overdue deadline alerts
- Click-through to declaration details
- Company-specific deadline filtering

### 3. Client Switcher
- Quick dropdown for switching between managed companies
- Search functionality for fast client location
- Shows pending declaration count badges
- Displays overdue payment indicators
- Optimized for keyboard navigation

### 4. Task Queue
- Prioritized list of pending declarations requiring action
- Filter by: status, priority, company, declaration type
- Sort by: due date, priority, created date, amount
- Action indicators: review, approve, fix errors, add documents
- Visual priority badges and status indicators
- Days until due / overdue calculations

## Architecture

### Directory Structure

```
src/modules/accountant/
├── components/
│   ├── ClientList.tsx           # Main client list with stats
│   ├── DeadlineCalendar.tsx     # Calendar view for deadlines
│   ├── ClientSwitcher.tsx       # Quick client switching dropdown
│   ├── TaskQueue.tsx            # Prioritized task list
│   └── index.ts                 # Component exports
├── hooks/
│   └── index.ts                 # React Query hooks
├── services/
│   └── api.ts                   # API service layer
├── types/
│   └── index.ts                 # TypeScript type definitions
├── index.ts                     # Module exports
└── README.md                    # This file
```

## Usage

### Basic Usage

```tsx
import {
  ClientList,
  DeadlineCalendar,
  ClientSwitcher,
  TaskQueue,
} from '@/modules/accountant'

function AccountantDashboard() {
  const [selectedClient, setSelectedClient] = useState<string>()

  return (
    <div className="space-y-6">
      {/* Client switcher in header */}
      <ClientSwitcher
        value={selectedClient}
        onValueChange={setSelectedClient}
      />

      {/* Client list */}
      <ClientList onClientSelect={setSelectedClient} />

      {/* Deadline calendar */}
      <DeadlineCalendar
        companyId={selectedClient}
        onDeadlineClick={(id) => router.push(`/declarations/${id}`)}
      />

      {/* Task queue */}
      <TaskQueue
        onTaskClick={(id) => router.push(`/declarations/${id}`)}
      />
    </div>
  )
}
```

### Using React Query Hooks

```tsx
import {
  useAccountantClients,
  usePendingTasks,
  useUpcomingDeadlines,
  useDashboardSummary,
} from '@/modules/accountant'

function DashboardStats() {
  const { data: summary, isLoading } = useDashboardSummary()
  const { data: clients } = useAccountantClients({ status: 'active' })
  const { data: tasks } = usePendingTasks({ priority: 'urgent' })
  const { data: deadlines } = useUpcomingDeadlines()

  return (
    <div>
      <h2>Total Clients: {summary?.totalClients}</h2>
      <h2>Pending Tasks: {summary?.totalPendingDeclarations}</h2>
      <h2>Upcoming Deadlines: {summary?.upcomingDeadlines}</h2>
    </div>
  )
}
```

### Advanced Filtering

```tsx
import { ClientList, TaskQueue } from '@/modules/accountant'

function FilteredViews() {
  return (
    <>
      {/* Clients with pending declarations */}
      <ClientList
        initialFilters={{
          hasPendingDeclarations: true,
          sortBy: 'pendingCount',
          sortOrder: 'desc',
        }}
      />

      {/* High priority tasks only */}
      <TaskQueue
        initialFilters={{
          priority: 'high',
          status: 'in_review',
          sortBy: 'dueDate',
        }}
      />
    </>
  )
}
```

## Components

### ClientList

**Props:**
- `onClientSelect?: (companyId: string) => void` - Callback when client is clicked
- `initialFilters?: ClientFilters` - Initial filter state
- `showSearch?: boolean` - Show search bar (default: true)
- `showFilters?: boolean` - Show filter controls (default: true)
- `className?: string` - Additional CSS classes

**Features:**
- Real-time stats for each client
- Search by company name or tax ID
- Filter by status (active/inactive/suspended)
- Sort by multiple criteria
- Hover prefetching for optimized navigation
- Responsive grid layout

### DeadlineCalendar

**Props:**
- `onDeadlineClick?: (declarationId: string) => void` - Callback when deadline is clicked
- `companyId?: string` - Filter deadlines for specific company
- `className?: string` - Additional CSS classes

**Features:**
- Month view with visual calendar grid
- List view for detailed deadline information
- Overdue deadline alerts
- Priority color coding
- Navigation controls (previous/next month, today)
- Responsive layout

### ClientSwitcher

**Props:**
- `value?: string` - Currently selected company ID
- `onValueChange?: (companyId: string) => void` - Callback when selection changes
- `className?: string` - Additional CSS classes
- `placeholder?: string` - Placeholder text

**Features:**
- Searchable dropdown
- Shows pending declaration badges
- Overdue payment indicators
- Keyboard navigation support
- Command palette UI pattern

### TaskQueue

**Props:**
- `onTaskClick?: (declarationId: string) => void` - Callback when task is clicked
- `initialFilters?: TaskQueueFilters` - Initial filter state
- `className?: string` - Additional CSS classes
- `showFilters?: boolean` - Show filter controls (default: true)

**Features:**
- Multi-criteria filtering
- Priority-based sorting
- Action requirement indicators
- Days until due calculations
- Visual status and priority badges
- Summary statistics

## React Query Hooks

### Client Hooks
- `useAccountantClients(filters?)` - Fetch all managed clients with stats
- `useClientStats(companyId)` - Fetch stats for specific client
- `useManagedCompanies()` - Fetch list of managed companies (for switcher)

### Deadline Hooks
- `useUpcomingDeadlines(params?)` - Fetch upcoming deadlines
- `useOverdueDeadlines()` - Fetch overdue deadlines
- `useClientDeadlines(companyId, params?)` - Fetch deadlines for specific client

### Task Hooks
- `usePendingTasks(params?)` - Fetch pending tasks/declarations
- `useHighPriorityTasks()` - Fetch high priority tasks only
- `useTasksRequiringAction()` - Fetch tasks requiring immediate action

### Dashboard Hooks
- `useDashboardSummary()` - Fetch aggregated dashboard stats

### Utility Hooks
- `useInvalidateAccountantQueries()` - Invalidate all accountant queries
- `usePrefetchClient()` - Prefetch client data for optimistic navigation

## Type Definitions

### Main Types
- `ClientQuickStats` - Quick stats for client card
- `ClientWithStats` - Client data with aggregated stats
- `DeclarationDeadline` - Deadline information across clients
- `PendingTask` - Task/declaration requiring action
- `AccountantDashboardSummary` - Overall dashboard statistics

### Filter Types
- `ClientFilters` - Client list filtering options
- `TaskQueueFilters` - Task queue filtering options
- `GetDeadlinesParams` - Deadline query parameters

## Backend Requirements

The following backend endpoints need to be implemented:

### Required Endpoints

```
GET /api/v1/accountant/clients
  - Returns paginated list of clients with stats
  - Filters: search, status, hasPending, hasOverdue, city
  - Includes: pending count, draft count, financial totals

GET /api/v1/accountant/clients/{companyId}/stats
  - Returns detailed stats for specific client

GET /api/v1/accountant/deadlines
  - Returns upcoming deadlines across all clients
  - Filters: startDate, endDate, companyId, status, priority

GET /api/v1/accountant/deadlines/overdue
  - Returns overdue deadlines

GET /api/v1/accountant/tasks
  - Returns pending tasks/declarations
  - Filters: status, priority, companyId, declarationType
  - Sorting: dueDate, priority, createdAt, amount

GET /api/v1/accountant/tasks/high-priority
  - Returns high priority tasks only

GET /api/v1/accountant/tasks/requires-action
  - Returns tasks requiring immediate action

GET /api/v1/accountant/dashboard/summary
  - Returns aggregated dashboard statistics
```

### Data Requirements

Backend should aggregate data from:
- `companies` table (for client list)
- `user_company_roles` table (filter by company_accountant role)
- `tax_declarations` table (for declaration counts and deadlines)
- `payments` table (for financial totals)
- `assignments` table (for agent assignment info)

### Authorization

All endpoints should:
- Verify user has `company_accountant` role for requested companies
- Only return data for companies user manages
- Implement proper RBAC checks

## UX Considerations

### Performance
- React Query caching reduces API calls
- Stale times configured for optimal balance
- Prefetching on hover for instant navigation
- Optimistic updates where applicable

### Accessibility
- Keyboard navigation support
- ARIA labels and roles
- Screen reader friendly
- Focus management

### Responsive Design
- Mobile-first approach
- Grid layouts adapt to screen size
- Touch-friendly interactions
- Collapsible sections on small screens

### User Experience
- Real-time updates with auto-refetch
- Loading states with skeletons
- Error handling with user-friendly messages
- Empty states with clear messaging
- Visual priority indicators (colors, badges)
- Search debouncing for better performance
- Filter persistence across sessions (optional)

### Visual Design
- Consistent with existing TaxasGE design system
- Uses shadcn/ui components
- Color-coded priorities and statuses
- Clear visual hierarchy
- Appropriate use of white space

## Dependencies

### Required Packages
- `@tanstack/react-query` - Data fetching and caching
- `date-fns` - Date manipulation and formatting
- `lucide-react` - Icons
- `sonner` - Toast notifications
- `@radix-ui/*` - UI primitives (via shadcn/ui)

### Internal Dependencies
- `@/components/ui/*` - Shared UI components
- `@/core/api` - API client
- `@/core/utils` - Utility functions
- `@/lib/utils` - Class name utilities
- `@/modules/companies/types` - Company type definitions

## Testing Recommendations

### Unit Tests
- Test hooks with React Query mock
- Test component rendering with various props
- Test filter and sort logic
- Test date calculations

### Integration Tests
- Test complete user flows
- Test client selection and navigation
- Test filtering and searching
- Test deadline calendar interactions

### E2E Tests
- Test accountant dashboard workflows
- Test multi-client switching
- Test task completion flows
- Test deadline notifications

## Future Enhancements

### Planned Features
1. **Bulk Actions**
   - Approve multiple declarations at once
   - Send reminders to multiple clients
   - Export reports for multiple clients

2. **Advanced Analytics**
   - Client performance trends
   - Revenue forecasting
   - Workload distribution charts
   - Compliance rate tracking

3. **Notifications**
   - Real-time deadline alerts
   - Client activity notifications
   - Task assignment notifications
   - Email/SMS reminders

4. **Collaboration**
   - Notes and comments on clients
   - Task assignment to team members
   - Shared client views
   - Activity timeline

5. **Reporting**
   - Custom report builder
   - Scheduled report generation
   - PDF/Excel export
   - Client-specific reports

6. **Automation**
   - Auto-assign declarations
   - Smart priority calculation
   - Deadline reminder automation
   - Status update triggers

## Support

For issues or questions:
- Check the main project README
- Review TypeScript types for API contracts
- Check console for React Query DevTools
- Review backend API documentation

## Contributing

When adding new features:
1. Follow existing patterns and conventions
2. Update types in `types/index.ts`
3. Add React Query hooks in `hooks/index.ts`
4. Create reusable components
5. Update this README with new features
6. Add proper TypeScript types
7. Include loading and error states
8. Test with various data scenarios

## License

Part of the TaxasGE project. See project root for license information.
