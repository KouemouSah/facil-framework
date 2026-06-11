"""Dashboards module — exposes business dashboard data via Looker Studio community connector.

Phase B.1 skeleton: USER_PASS auth (email + JWT-as-token), recaudacion only, no RLS.
Phase B.2: OAUTH2 + per-ministry RLS via agent_profiles.ministry_id.
"""

from app.modules.dashboards.api import dashboards_router

__all__ = ["dashboards_router"]
