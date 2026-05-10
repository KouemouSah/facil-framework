# Accountant Module - Architecture Documentation

**Module:** C:\taxasge\packages\web\src\modules\accountant
**Version:** 1.0.0
**Author:** Claude Code
**Date:** 2025-12-03

---

## Module Structure

```
accountant/
├── components/
│   ├── ClientList.tsx           # Main client list with stats (341 lines)
│   ├── DeadlineCalendar.tsx     # Calendar view for deadlines (401 lines)
│   ├── ClientSwitcher.tsx       # Quick client dropdown (172 lines)
│   ├── TaskQueue.tsx            # Prioritized task list (427 lines)
│   └── index.ts                 # Component exports
│
├── hooks/
│   └── index.ts                 # React Query hooks (243 lines)
│
├── services/
│   └── api.ts                   # API service layer (238 lines)
│
├── types/
│   └── index.ts                 # TypeScript definitions (214 lines)
│
├── examples/
│   └── usage-examples.tsx       # 10 usage examples (500+ lines)
│
├── index.ts                     # Module exports (40 lines)
├── README.md                    # Complete documentation (452 lines)
├── UX_NOTES.md                  # UX considerations (700+ lines)
├── IMPLEMENTATION_SUMMARY.md    # Implementation details (600+ lines)
└── ARCHITECTURE.md              # This file

Demo Page:
app/[locale]/(dashboard)/dashboard/accountant/
└── page.tsx                     # Full dashboard demo (350+ lines)
```

---

## Component Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Accountant Dashboard Page                  │
│  (app/[locale]/(dashboard)/dashboard/accountant/page)   │
└────────────┬────────────────────────────────────────────┘
             │
             ├─ Components Layer ─────────────────────────┐
             │                                             │
             │  ┌──────────────────────────────────────┐  │
             │  │        ClientSwitcher                │  │
             │  │  - Searchable dropdown               │  │
             │  │  - Company selection                 │  │
             │  │  - Pending count badges              │  │
             │  └──────────────────────────────────────┘  │
             │                                             │
             │  ┌──────────────────────────────────────┐  │
             │  │         ClientList                   │  │
             │  │  - Grid of client cards              │  │
             │  │  - Quick stats display               │  │
             │  │  - Search & filter                   │  │
             │  │  - Sort capabilities                 │  │
             │  └──────────────────────────────────────┘  │
             │                                             │
             │  ┌──────────────────────────────────────┐  │
             │  │      DeadlineCalendar                │  │
             │  │  - Month/Week/List views             │  │
             │  │  - Priority color coding             │  │
             │  │  - Overdue alerts                    │  │
             │  │  - Navigation controls               │  │
             │  └──────────────────────────────────────┘  │
             │                                             │
             │  ┌──────────────────────────────────────┐  │
             │  │          TaskQueue                   │  │
             │  │  - Prioritized task cards            │  │
             │  │  - Multi-criteria filtering          │  │
             │  │  - Action indicators                 │  │
             │  │  - Summary statistics                │  │
             │  └──────────────────────────────────────┘  │
             │                                             │
             └─────────────────────────────────────────────┘
                              │
             ├─ Hooks Layer (React Query) ────────────────┐
             │                                             │
             │  ┌──────────────────────────────────────┐  │
             │  │     Client Hooks                     │  │
             │  │  - useAccountantClients()            │  │
             │  │  - useClientStats()                  │  │
             │  │  - useManagedCompanies()             │  │
             │  └──────────────────────────────────────┘  │
             │                                             │
             │  ┌──────────────────────────────────────┐  │
             │  │     Deadline Hooks                   │  │
             │  │  - useUpcomingDeadlines()            │  │
             │  │  - useOverdueDeadlines()             │  │
             │  │  - useClientDeadlines()              │  │
             │  └──────────────────────────────────────┘  │
             │                                             │
             │  ┌──────────────────────────────────────┐  │
             │  │     Task Hooks                       │  │
             │  │  - usePendingTasks()                 │  │
             │  │  - useHighPriorityTasks()            │  │
             │  │  - useTasksRequiringAction()         │  │
             │  └──────────────────────────────────────┘  │
             │                                             │
             │  ┌──────────────────────────────────────┐  │
             │  │     Dashboard Hooks                  │  │
             │  │  - useDashboardSummary()             │  │
             │  └──────────────────────────────────────┘  │
             │                                             │
             │  ┌──────────────────────────────────────┐  │
             │  │     Utility Hooks                    │  │
             │  │  - useInvalidateAccountantQueries()  │  │
             │  │  - usePrefetchClient()               │  │
             │  └──────────────────────────────────────┘  │
             │                                             │
             └─────────────────────────────────────────────┘
                              │
             ├─ Service Layer ────────────────────────────┐
             │                                             │
             │  ┌──────────────────────────────────────┐  │
             │  │    accountantClientsApi              │  │
             │  │  - getAll()                          │  │
             │  │  - getClientStats()                  │  │
             │  │  - getManagedCompanies()             │  │
             │  └──────────────────────────────────────┘  │
             │                                             │
             │  ┌──────────────────────────────────────┐  │
             │  │    accountantDeadlinesApi            │  │
             │  │  - getUpcoming()                     │  │
             │  │  - getOverdue()                      │  │
             │  │  - getByCompany()                    │  │
             │  └──────────────────────────────────────┘  │
             │                                             │
             │  ┌──────────────────────────────────────┐  │
             │  │    accountantTasksApi                │  │
             │  │  - getAll()                          │  │
             │  │  - getHighPriority()                 │  │
             │  │  - getRequiresAction()               │  │
             │  └──────────────────────────────────────┘  │
             │                                             │
             │  ┌──────────────────────────────────────┐  │
             │  │    accountantDashboardApi            │  │
             │  │  - getSummary()                      │  │
             │  └──────────────────────────────────────┘  │
             │                                             │
             └─────────────────────────────────────────────┘
                              │
             ├─ Backend API Layer ────────────────────────┤
             │                                             │
             │  GET /api/v1/accountant/clients            │
             │  GET /api/v1/accountant/clients/:id/stats  │
             │  GET /api/v1/accountant/deadlines          │
             │  GET /api/v1/accountant/deadlines/overdue  │
             │  GET /api/v1/accountant/tasks              │
             │  GET /api/v1/accountant/dashboard/summary  │
             │                                             │
             └─────────────────────────────────────────────┘
                              │
             ├─ Database Layer ───────────────────────────┤
             │                                             │
             │  - companies                                │
             │  - user_company_roles                       │
             │  - tax_declarations                         │
             │  - payments                                 │
             │  - assignments                              │
             │                                             │
             └─────────────────────────────────────────────┘
```

---

## Data Flow

### 1. Client List Flow

```
User Action (Load page)
    │
    ├─> useAccountantClients(filters)
    │       │
    │       ├─> Check React Query cache
    │       │   ├─ Hit: Return cached data
    │       │   └─ Miss: Fetch from API
    │       │
    │       ├─> accountantClientsApi.getAll(filters)
    │       │       │
    │       │       └─> GET /api/v1/accountant/clients?...
    │       │               │
    │       │               └─> Backend aggregates:
    │       │                   - Company info
    │       │                   - Declaration counts
    │       │                   - Financial totals
    │       │                   - Next deadlines
    │       │
    │       └─> Return: PaginatedClientsResponse
    │
    └─> ClientList component renders
            │
            ├─> Display client cards
            ├─> Show quick stats
            └─> Enable interactions
```

### 2. Deadline Calendar Flow

```
User Action (Select month)
    │
    ├─> useUpcomingDeadlines({ startDate, endDate })
    │       │
    │       ├─> Check React Query cache
    │       │
    │       ├─> accountantDeadlinesApi.getUpcoming(params)
    │       │       │
    │       │       └─> GET /api/v1/accountant/deadlines?...
    │       │               │
    │       │               └─> Backend returns:
    │       │                   - Declarations with deadlines
    │       │                   - Priority calculations
    │       │                   - Days until due
    │       │
    │       └─> Return: DeclarationDeadline[]
    │
    ├─> useOverdueDeadlines() (parallel)
    │       │
    │       └─> GET /api/v1/accountant/deadlines/overdue
    │
    └─> DeadlineCalendar component
            │
            ├─> Group deadlines by date
            ├─> Render calendar grid
            ├─> Show overdue alerts
            └─> Enable date navigation
```

### 3. Task Queue Flow

```
User Action (Apply filters)
    │
    ├─> usePendingTasks(filters)
    │       │
    │       ├─> Check React Query cache
    │       │
    │       ├─> accountantTasksApi.getAll(params)
    │       │       │
    │       │       └─> GET /api/v1/accountant/tasks?...
    │       │               │
    │       │               └─> Backend returns:
    │       │                   - Pending declarations
    │       │                   - Action requirements
    │       │                   - Priority calculations
    │       │                   - Deadline info
    │       │
    │       └─> Return: PendingTask[]
    │
    └─> TaskQueue component
            │
            ├─> Display task cards
            ├─> Show action indicators
            ├─> Enable filtering/sorting
            └─> Display summary stats
```

### 4. Client Switcher Flow

```
User Action (Open dropdown)
    │
    ├─> useManagedCompanies()
    │       │
    │       ├─> Check React Query cache (10 min stale)
    │       │
    │       ├─> accountantClientsApi.getManagedCompanies()
    │       │       │
    │       │       └─> GET /api/v1/companies?role=company_accountant
    │       │               │
    │       │               └─> Backend filters by:
    │       │                   - User's company roles
    │       │                   - company_accountant role
    │       │
    │       └─> Return: ClientWithStats[]
    │
    └─> ClientSwitcher component
            │
            ├─> Display company list
            ├─> Enable search
            ├─> Show badges (pending, overdue)
            │
            └─> User selects client
                    │
                    └─> onValueChange(companyId)
                            │
                            ├─> Update selected state
                            ├─> Prefetch client data
                            └─> Filter other components
```

---

## State Management

### React Query Cache Strategy

```
┌─────────────────────────────────────────────────────┐
│           React Query Cache                         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Clients (2 min stale)                              │
│  ├─ accountant.clients.list.{filters}              │
│  ├─ accountant.clients.stats.{companyId}           │
│  └─ accountant.clients.managed                     │
│                                                     │
│  Deadlines (5 min stale)                            │
│  ├─ accountant.deadlines.list.{params}             │
│  ├─ accountant.deadlines.overdue (refetch: 5m)     │
│  └─ accountant.deadlines.by-company.{id}.{params}  │
│                                                     │
│  Tasks (2 min stale)                                │
│  ├─ accountant.tasks.list.{params}                 │
│  ├─ accountant.tasks.high-priority (refetch: 5m)   │
│  └─ accountant.tasks.requires-action (refetch: 5m) │
│                                                     │
│  Dashboard (5 min stale, refetch: 10m)              │
│  └─ accountant.dashboard.summary                    │
│                                                     │
└─────────────────────────────────────────────────────┘

Cache Invalidation:
├─ On declaration submission
├─ On declaration approval
├─ On deadline update
└─ Manual refresh (useInvalidateAccountantQueries)
```

### Component State

```
ClientList
├─ filters (ClientFilters)
├─ searchQuery (string)
└─ prefetch cache (Map)

DeadlineCalendar
├─ currentDate (Date)
├─ view ('month' | 'week' | 'list')
└─ deadlinesByDate (Map<string, Deadline[]>)

ClientSwitcher
├─ open (boolean)
├─ selectedValue (string)
└─ searchQuery (string)

TaskQueue
├─ filters (TaskQueueFilters)
└─ sortState (SortBy, SortOrder)
```

---

## Type System

### Type Hierarchy

```
┌────────────────────────────────────────────────┐
│              Base Types                        │
├────────────────────────────────────────────────┤
│  Company (from @/modules/companies/types)      │
└────────────────────────────────────────────────┘
                    │
    ┌───────────────┴──────────────┐
    │                              │
┌───▼──────────────────┐  ┌────────▼──────────────┐
│  ClientQuickStats    │  │  ClientWithStats      │
│  ├─ companyId        │  │  extends Company      │
│  ├─ companyName      │  │  ├─ ...Company fields │
│  ├─ declarationStats │  │  └─ stats             │
│  ├─ financialStats   │  │                       │
│  ├─ nextDeadline     │  └───────────────────────┘
│  └─ activity         │
└──────────────────────┘

┌────────────────────────────────────────────────┐
│           Declaration Types                    │
├────────────────────────────────────────────────┤
│  DeclarationDeadline                           │
│  ├─ id, companyId, companyName                 │
│  ├─ declarationType, dueDate                   │
│  ├─ status, amount                             │
│  ├─ priority, daysUntilDue                     │
│  └─ assignedAgentName                          │
│                                                │
│  PendingTask                                   │
│  ├─ id, companyId, companyName                 │
│  ├─ declarationType, status                    │
│  ├─ createdAt, updatedAt, dueDate              │
│  ├─ amount, priority                           │
│  ├─ requiresAction, actionType                 │
│  └─ daysUntilDue                               │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│           Filter Types                         │
├────────────────────────────────────────────────┤
│  ClientFilters                                 │
│  ├─ search, status                             │
│  ├─ hasPendingDeclarations                     │
│  ├─ hasOverduePayments                         │
│  └─ sortBy, sortOrder                          │
│                                                │
│  TaskQueueFilters                              │
│  ├─ status, priority                           │
│  ├─ companyId, declarationType                 │
│  └─ sortBy, sortOrder                          │
│                                                │
│  GetDeadlinesParams                            │
│  └─ startDate, endDate, companyId, filters     │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│           Dashboard Types                      │
├────────────────────────────────────────────────┤
│  AccountantDashboardSummary                    │
│  ├─ totalClients, activeClients                │
│  ├─ totalPendingDeclarations                   │
│  ├─ totalAmountDue, totalOverdueAmount         │
│  ├─ upcomingDeadlines, overdueDeadlines        │
│  └─ requiresActionCount, urgentCount           │
└────────────────────────────────────────────────┘
```

---

## Performance Optimizations

### 1. React Query Optimization

```typescript
// Aggressive caching for stable data
useManagedCompanies()
  - staleTime: 10 minutes
  - Data rarely changes
  - Reduces API calls

// Moderate caching for dynamic data
useClientStats()
  - staleTime: 5 minutes
  - Balance freshness vs performance
  - Background refetch on stale

// Short caching for critical data
usePendingTasks()
  - staleTime: 2 minutes
  - Frequent updates expected
  - Auto-refetch on focus
```

### 2. Component Optimization

```typescript
// Memoized calculations
const deadlinesByDate = useMemo(() => {
  // Group deadlines by date
}, [deadlines])

// Debounced search
const handleSearchChange = debounce((value) => {
  setFilters({ ...filters, search: value })
}, 500)

// Hover prefetching
onMouseEnter={() => prefetchClient(companyId)}
```

### 3. Bundle Optimization

```typescript
// Code splitting by route
const AccountantDashboard = lazy(() =>
  import('./accountant/page')
)

// Tree shaking enabled
export { ClientList, DeadlineCalendar } from '@/modules/accountant'
```

---

## Security Considerations

### Authorization

```
┌────────────────────────────────────────────────┐
│           Authorization Flow                   │
├────────────────────────────────────────────────┤
│                                                │
│  1. User Authentication                        │
│     └─> JWT token in request header            │
│                                                │
│  2. Role Verification (Backend)                │
│     ├─> Verify user has company_accountant     │
│     ├─> Check user_company_roles table         │
│     └─> Filter by user's managed companies     │
│                                                │
│  3. Data Filtering (Backend)                   │
│     ├─> Only return user's client data         │
│     ├─> No cross-accountant data access        │
│     └─> Enforce row-level security             │
│                                                │
│  4. Frontend Validation                        │
│     ├─> Display only authorized data           │
│     ├─> Hide unauthorized actions              │
│     └─> Validate permissions before actions    │
│                                                │
└────────────────────────────────────────────────┘
```

### Data Protection

- All API calls use HTTPS
- JWT tokens for authentication
- No sensitive data in localStorage
- XSS protection via React
- CSRF protection on mutations

---

## Error Handling

### Error Boundary Strategy

```
┌────────────────────────────────────────────────┐
│           Error Handling Layers                │
├────────────────────────────────────────────────┤
│                                                │
│  1. Component Level                            │
│     ├─> Try-catch for operations               │
│     ├─> Error state in useState                │
│     └─> Display inline error messages          │
│                                                │
│  2. Hook Level                                 │
│     ├─> React Query error handling             │
│     ├─> onError callbacks                      │
│     └─> Toast notifications                    │
│                                                │
│  3. Service Level                              │
│     ├─> HTTP error handling                    │
│     ├─> Network error handling                 │
│     └─> Parse error responses                  │
│                                                │
│  4. Global Level                               │
│     ├─> Error boundary component               │
│     ├─> Sentry error tracking (future)         │
│     └─> Fallback UI                            │
│                                                │
└────────────────────────────────────────────────┘
```

---

## Testing Strategy

### Test Pyramid

```
         ┌─────────────────┐
         │   E2E Tests     │  ← 10% (Critical paths)
         │   (Playwright)  │
         ├─────────────────┤
         │ Integration     │  ← 30% (Component interaction)
         │ (Testing Lib)   │
         ├─────────────────┤
         │   Unit Tests    │  ← 60% (Functions, hooks)
         │   (Jest/Vitest) │
         └─────────────────┘

Unit Tests:
├─ Hook logic
├─ Utility functions
├─ Type guards
└─ Date calculations

Integration Tests:
├─ Component rendering
├─ User interactions
├─ Filter application
└─ Navigation flows

E2E Tests:
├─ Complete user journeys
├─ Multi-client workflows
└─ Critical business flows
```

---

## Deployment Considerations

### Build Optimization

```bash
# Production build
npm run build

# Check bundle size
npm run analyze

# Lighthouse audit
npm run lighthouse
```

### Environment Variables

```env
NEXT_PUBLIC_API_URL=https://api.taxasge.gq
NEXT_PUBLIC_ENABLE_QUERY_DEVTOOLS=false
```

### Performance Targets

- First Contentful Paint: < 1.5s
- Time to Interactive: < 3.0s
- Lighthouse Score: > 90
- Bundle Size: < 500KB (gzipped)

---

## Monitoring & Analytics

### Metrics to Track

1. **Performance**
   - Page load times
   - API response times
   - Cache hit rates
   - Component render times

2. **Usage**
   - Most used features
   - Filter combinations
   - Navigation patterns
   - Error frequency

3. **Business**
   - Active accountants
   - Clients managed per accountant
   - Tasks completed per day
   - Average response time

---

## Future Scalability

### Planned Enhancements

**Phase 2:** Bulk operations, advanced filters
**Phase 3:** Real-time updates, analytics
**Phase 4:** Automation, mobile app

### Scalability Patterns

```
Current Architecture (< 1000 clients):
└─ Single API calls, client-side filtering

Future Architecture (> 1000 clients):
├─ Server-side pagination
├─ Virtual scrolling
├─ Index-based search
└─ Background sync
```

---

## Support & Resources

- **Documentation:** README.md, UX_NOTES.md
- **Examples:** examples/usage-examples.tsx
- **Demo:** app/[locale]/(dashboard)/dashboard/accountant/page.tsx
- **Types:** types/index.ts
- **API Contracts:** services/api.ts

---

**Architecture Version:** 1.0.0
**Last Updated:** 2025-12-03
**Maintained By:** TaxasGE Frontend Team
