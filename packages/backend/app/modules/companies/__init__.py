"""
Companies Module - Company Management for Business Users

Gestion des entreprises et rôles membres.
Requis par DECLARATIONS (business users).

Tables DB (2):
- companies (entreprises)
- user_company_roles (rôles membres)

Endpoints: 10
Priorité: P4 (requis par DECLARATIONS)
"""

from app.modules.companies.api.company_routes import router as company_router

__all__ = ["company_router"]
