"""
Accountant Module - Deadline Tracking for Accountants

This module provides comprehensive deadline tracking across all client companies
for accountants. It includes:
- Upcoming deadlines with priority scoring
- Overdue deadlines grouped by severity
- Calendar view with aggregations
- Dashboard analytics

API Endpoints:
- GET /api/v1/accountant/deadlines/upcoming
- GET /api/v1/accountant/deadlines/overdue
- GET /api/v1/accountant/calendar
- GET /api/v1/accountant/analytics
"""

from app.modules.accountant.api import accountant_router

__all__ = [
    "accountant_router",
]
