"""
Chatbot Module - AI-powered assistance for TaxasGE

Provides intelligent chatbot, search, recommendations, translations,
and guidance features.

Status: Placeholder mode - AI provider integration pending

Architecture: 3-tier
- models/: Pydantic models for requests/responses
- services/: Business logic (placeholder until AI integration)
- api/: FastAPI routes
- repositories/: Database access (TODO when tables added)

Migrated from: app/api/v1/ai_services.py

TODO:
1. Integrate AI provider (OpenAI, Claude, Gemini, etc.)
2. Add database tables for conversation history and feedback
3. Implement vector search for semantic search
4. Add document AI integration
5. Implement translation API integration
"""

from app.modules.chatbot.api import chatbot_router

__all__ = ["chatbot_router"]
