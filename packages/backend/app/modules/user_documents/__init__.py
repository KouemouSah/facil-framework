"""
User Documents Module — Coffre-fort documentaire

Personal document vault for citizens:
- Upload, classify (Gemini AI), and store identity/legal/financial documents
- Automatic expiry tracking with alerts
- Workflow readiness checks (do I have all docs for passport renewal?)
- Import from wizard sessions, export generated receipts/certificates
- AI-powered deduplication and extraction
"""

from app.modules.user_documents.api.user_documents_routes import router as user_documents_router

__all__ = ["user_documents_router"]

MODULE_TABLES = [
    "user_documents",
    "user_document_workflow_tags",
    "user_document_access_log",
    "user_document_alerts",
    "user_agent_memory",
    "user_agent_permissions",
]
