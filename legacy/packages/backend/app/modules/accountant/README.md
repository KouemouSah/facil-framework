# Accountant Deadline Tracking API

Comprehensive deadline tracking system for accountants to manage deadlines across all client companies.

## Overview

The Accountant Deadline Tracking API provides accountants with powerful tools to:
- Track upcoming deadlines across all client companies
- Monitor overdue declarations with severity classification
- View calendar aggregations for planning
- Get dashboard analytics and health scores

## Architecture

### 3-Tier FastAPI Architecture

```
accountant/
├── models/              # Pydantic schemas (request/response)
│   └── deadline_models.py
├── repositories/        # Data access layer (SQL queries)
│   └── deadline_repository.py
├── services/           # Business logic layer
│   └── deadline_service.py
└── api/               # HTTP routes (FastAPI)
    └── accountant_routes.py
```

## API Endpoints

### 1. GET /api/v1/accountant/deadlines/upcoming

Get upcoming deadlines across all client companies with advanced filtering and sorting.

**Query Parameters:**
- `start_date` (date, optional): Filter from this date (default: today)
- `end_date` (date, optional): Filter until this date (default: 90 days from now)
- `company_ids` (array[string], optional): Filter by specific company IDs
- `declaration_types` (array[string], optional): Filter by declaration types
- `priority` (enum, optional): Filter by priority (urgent, high, medium, low)
- `status` (enum, optional): Filter by declaration status
- `min_amount` (decimal, optional): Minimum tax amount filter
- `max_amount` (decimal, optional): Maximum tax amount filter
- `sort_by` (string, default: "due_date"): Sort field (due_date, priority, company_name, amount)
- `sort_order` (string, default: "asc"): Sort direction (asc, desc)
- `page` (int, default: 1): Page number (1-indexed)
- `page_size` (int, default: 20): Items per page (max 100)

**Response:**
```json
{
  "deadlines": [
    {
      "id": "uuid",
      "company": {
        "id": "uuid",
        "name": "Company ABC",
        "tax_id": "NIF123456",
        "email": "contact@company.com",
        "phone": "+224..."
      },
      "declaration": {
        "id": "uuid",
        "declaration_type": "iva_real",
        "status": "draft",
        "fiscal_period_start": "2025-01-01",
        "fiscal_period_end": "2025-01-31",
        "tax_year": 2025,
        "calculated_tax": 1500000.00,
        "reference_number": null
      },
      "due_date": "2025-02-15T00:00:00Z",
      "days_until_due": 10,
      "priority": "high",
      "priority_score": 65,
      "created_at": "2025-01-20T10:30:00Z",
      "updated_at": "2025-01-20T10:30:00Z",
      "email_notifications": true,
      "sms_notifications": false,
      "agent_assigned": null,
      "notes": null
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "filters_applied": {
    "start_date": "2025-02-03",
    "end_date": "2025-05-03"
  },
  "summary": {
    "total_urgent": 5,
    "total_high": 15,
    "total_medium": 30,
    "total_low": 100,
    "avg_days_until_due": 25.3,
    "total_tax_amount": 45000000.00,
    "within_7_days": 8,
    "within_30_days": 45
  }
}
```

**Priority Scoring Logic:**
- Base: 0 points
- +50 if overdue (days_until_due <= 0)
- +40 if due within 3 days
- +30 if due within 7 days
- +15 if due within 14 days
- +25 if amount > 5M XAF
- +20 if amount > 1M XAF
- +10 if amount > 500K XAF
- +15 if high-volume type (iva_real, iva_destajo, vat_declaration, income_tax)
- +20 if escalated

**Priority Levels:**
- URGENT: 80-100
- HIGH: 60-79
- MEDIUM: 30-59
- LOW: 0-29

### 2. GET /api/v1/accountant/deadlines/overdue

Get overdue declarations grouped by severity.

**Query Parameters:**
- `company_ids` (array[string], optional): Filter by company IDs
- `declaration_types` (array[string], optional): Filter by types
- `status` (enum, optional): Filter by status
- `min_amount` (decimal, optional): Minimum amount
- `max_amount` (decimal, optional): Maximum amount
- `page` (int, default: 1): Page number
- `page_size` (int, default: 20): Items per page

**Response:**
```json
{
  "deadlines": [
    {
      "id": "uuid",
      "company": { /* same as above */ },
      "declaration": { /* same as above */ },
      "due_date": "2025-01-15T00:00:00Z",
      "days_overdue": 19,
      "severity": "moderate",
      "priority_score": 85,
      "created_at": "2024-12-20T10:30:00Z",
      "updated_at": "2024-12-20T10:30:00Z",
      "escalated": true,
      "escalated_at": "2025-01-25T14:00:00Z",
      "escalation_reason": "Multiple follow-ups with no response",
      "agent_assigned": "uuid",
      "notes": "Client requested extension",
      "last_contact_date": "2025-01-28T16:30:00Z"
    }
  ],
  "grouped_by_severity": {
    "recent": [ /* 1-7 days overdue */ ],
    "moderate": [ /* 7-30 days overdue */ ],
    "critical": [ /* 30+ days overdue */ ]
  },
  "total": 45,
  "page": 1,
  "page_size": 20,
  "summary": {
    "total_recent": 10,
    "total_moderate": 20,
    "total_critical": 15,
    "avg_days_overdue": 23.5,
    "total_tax_amount": 12000000.00,
    "escalated_count": 8,
    "percentage_critical": 33.3
  }
}
```

**Severity Classification:**
- RECENT: 1-7 days overdue
- MODERATE: 7-30 days overdue
- CRITICAL: 30+ days overdue

### 3. GET /api/v1/accountant/calendar

Get calendar view data with deadline aggregations.

**Query Parameters:**
- `start_date` (date, required): Start of date range
- `end_date` (date, required): End of date range
- `view_type` (string, default: "month"): View type (day, week, month)

**Response (Day View):**
```json
{
  "view_type": "day",
  "start_date": "2025-02-01",
  "end_date": "2025-02-28",
  "days": [
    {
      "date": "2025-02-05",
      "count": 8,
      "total_amount": 3500000.00,
      "deadlines": [
        {
          "id": "uuid",
          "company_name": "Company ABC",
          "declaration_type": "iva_real",
          "amount": 1500000.00
        }
      ]
    }
  ],
  "summary": {
    "total_deadlines": 125,
    "total_amount": 42000000.00,
    "busiest_day": "2025-02-15"
  }
}
```

**Response (Week View):**
```json
{
  "view_type": "week",
  "start_date": "2025-02-01",
  "end_date": "2025-02-28",
  "weeks": [
    {
      "week_start": "2025-02-03",
      "week_end": "2025-02-09",
      "week_number": 6,
      "count": 25,
      "total_amount": 8500000.00,
      "high_priority_count": 5
    }
  ],
  "summary": {
    "total_deadlines": 125,
    "total_amount": 42000000.00
  }
}
```

**Response (Month View):**
```json
{
  "view_type": "month",
  "start_date": "2025-01-01",
  "end_date": "2025-06-30",
  "months": [
    {
      "month": "2025-02",
      "month_name": "February 2025",
      "count": 125,
      "total_amount": 42000000.00,
      "high_priority_count": 15
    }
  ],
  "summary": {
    "total_deadlines": 450,
    "total_amount": 150000000.00
  }
}
```

### 4. GET /api/v1/accountant/analytics

Get comprehensive deadline analytics for dashboard.

**Response:**
```json
{
  "analytics": {
    "upcoming_next_30_days": 85,
    "upcoming_urgent": 5,
    "upcoming_high": 20,
    "total_overdue": 45,
    "overdue_recent": 10,
    "overdue_moderate": 20,
    "overdue_critical": 15,
    "total_tax_upcoming": 28000000.00,
    "total_tax_overdue": 12000000.00,
    "health_score": 65,
    "timestamp": "2025-02-03T14:30:00Z"
  },
  "status": "success"
}
```

**Health Score Calculation:**
- Starts at 100
- -2 points per overdue item
- -1 point per urgent upcoming item
- Minimum: 0

## Query Optimization

### Database Indexes

**Required indexes for optimal performance:**

```sql
-- Index on company_members for accountant filtering
CREATE INDEX idx_company_members_user_role
ON company_members(user_id, role)
WHERE role IN ('company_accountant', 'company_owner', 'company_admin');

-- Index on tax_declarations for deadline queries
CREATE INDEX idx_declarations_status_due_date
ON tax_declarations(status, fiscal_period_end)
WHERE status NOT IN ('approved', 'rejected');

-- Composite index for upcoming deadlines
CREATE INDEX idx_declarations_upcoming
ON tax_declarations(fiscal_period_end, calculated_tax DESC)
WHERE fiscal_period_end > CURRENT_DATE
  AND status NOT IN ('approved', 'rejected');

-- Composite index for overdue deadlines
CREATE INDEX idx_declarations_overdue
ON tax_declarations(fiscal_period_end DESC, calculated_tax DESC)
WHERE fiscal_period_end < CURRENT_DATE
  AND status NOT IN ('approved', 'rejected');

-- Index for agent work queue joins
CREATE INDEX idx_agent_work_queue_item
ON agent_work_queue(item_type, item_id)
WHERE item_type = 'declaration';
```

### Query Performance Notes

**1. Upcoming Deadlines Query:**
- Uses CTE (Common Table Expression) for date calculations
- Single query with window function `COUNT(*) OVER()` for total count
- Avoids N+1 problem with JOINs
- Expected execution time: <100ms for 10,000 declarations

**2. Overdue Deadlines Query:**
- Uses CASE WHEN for severity classification in SQL
- Grouping done in application layer (more flexible)
- Filtered by accountant's client companies via company_members JOIN
- Expected execution time: <150ms

**3. Calendar View Queries:**
- Uses `DATE_TRUNC` for efficient grouping
- Aggregations (COUNT, SUM) done in PostgreSQL
- Day view uses `json_agg` for efficient JSON building
- Date range limited to 365 days to prevent excessive queries
- Expected execution time: <200ms

**4. Analytics Query:**
- Runs 2 separate queries (upcoming + overdue)
- Results combined in service layer
- Uses same optimized queries as above
- Expected execution time: <300ms total

### Performance Benchmarks

**Expected performance (with indexes):**
- 10 client companies: <50ms
- 100 client companies: <100ms
- 1,000 client companies: <200ms
- 10,000+ declarations: <300ms

**Without indexes:**
- Can exceed 5,000ms (5 seconds) for large datasets
- Full table scans on tax_declarations
- Nested loop joins become inefficient

## Authentication & Authorization

**Required:**
- JWT Bearer token in Authorization header
- User role: `company_accountant`, `company_owner`, or `company_admin`
- Accountants only see deadlines for their assigned client companies

**Example:**
```bash
curl -X GET "https://api.taxasge.com/api/v1/accountant/deadlines/upcoming" \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "Content-Type: application/json"
```

## Error Handling

**Standard error responses:**

```json
{
  "detail": "Error message",
  "status_code": 400
}
```

**Common errors:**
- `400 Bad Request`: Invalid query parameters
- `401 Unauthorized`: Missing or invalid token
- `403 Forbidden`: Insufficient permissions (not an accountant)
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

## Use Cases

### 1. Dashboard Widget
```javascript
// Fetch dashboard analytics
const response = await fetch('/api/v1/accountant/analytics', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const { analytics } = await response.json();

// Display health score, urgent count, overdue count
console.log(`Health: ${analytics.health_score}/100`);
console.log(`Urgent: ${analytics.upcoming_urgent}`);
console.log(`Overdue: ${analytics.total_overdue}`);
```

### 2. Deadline List with Filters
```javascript
// Get urgent deadlines for specific company
const params = new URLSearchParams({
  company_ids: 'uuid1,uuid2',
  priority: 'urgent',
  sort_by: 'due_date',
  sort_order: 'asc',
  page: 1,
  page_size: 20
});

const response = await fetch(`/api/v1/accountant/deadlines/upcoming?${params}`);
const { deadlines, summary } = await response.json();
```

### 3. Calendar View
```javascript
// Get monthly calendar for February 2025
const response = await fetch('/api/v1/accountant/calendar?' + new URLSearchParams({
  start_date: '2025-02-01',
  end_date: '2025-02-28',
  view_type: 'day'
}));

const { days, summary } = await response.json();

// Render calendar with deadline counts per day
days.forEach(day => {
  console.log(`${day.date}: ${day.count} deadlines`);
});
```

### 4. Overdue Report
```javascript
// Get overdue deadlines grouped by severity
const response = await fetch('/api/v1/accountant/deadlines/overdue');
const { grouped_by_severity, summary } = await response.json();

console.log(`Critical: ${summary.total_critical}`);
console.log(`Moderate: ${summary.total_moderate}`);
console.log(`Recent: ${summary.total_recent}`);
```

## Testing

**Run tests:**
```bash
cd packages/backend
pytest tests/test_accountant_deadlines.py -v
```

**Test coverage:**
- Unit tests for priority scoring logic
- Integration tests for API endpoints
- Performance tests for query optimization

## Future Enhancements

**Planned features:**
- Email/SMS notifications for upcoming deadlines
- Batch operations (bulk updates, exports)
- Custom notification preferences per accountant
- Weekly/monthly digest reports
- Export to Excel/PDF
- Advanced analytics (trends, forecasting)
- Integration with calendar apps (Google Calendar, Outlook)

## Support

For questions or issues, contact:
- API Documentation: `/docs` (development only)
- Technical Support: support@taxasge.com
