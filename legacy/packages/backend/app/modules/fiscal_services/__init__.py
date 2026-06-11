"""
Fiscal Services Module - Catalog of 850 tax services (CONFIGURATION)

12 tables DB (structure hiérarchique complète):
- ministries (Ministères)
- sectors (Secteurs par ministère)
- categories (Catégories par secteur)
- fiscal_services (850 services fiscaux - CATALOGUE)
- service_keywords (recherche)
- service_document_assignments (liens services → docs)
- service_procedure_assignments (liens services → procédures)
- steps_count (compteur étapes)
- document_templates (templates documents requis)
- procedure_templates (templates procédures)
- procedure_template_steps (étapes procédures)
- entity_translations (traductions ES/FR/EN)

NOTE: fiscal_service_data → MODULE DECLARATIONS (données utilisateur)

Endpoints: 12 (+ admin templates/procedures)
Priorité: P2 HAUTE (requis par DECLARATIONS)
"""

from app.modules.fiscal_services.api.fiscal_service_routes import router as fiscal_service_router

__all__ = ["fiscal_service_router"]
