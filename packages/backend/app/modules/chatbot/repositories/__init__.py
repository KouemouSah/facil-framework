"""
Chatbot Repositories

Includes:
- Semantic search repository for vector similarity search
- TODO: Conversation history repository
- TODO: User feedback repository
- TODO: AI usage statistics repository
"""

from app.modules.chatbot.repositories.semantic_search_repository import (
    SemanticSearchRepository,
    create_semantic_search_repository
)

__all__ = [
    "SemanticSearchRepository",
    "create_semantic_search_repository",
]
