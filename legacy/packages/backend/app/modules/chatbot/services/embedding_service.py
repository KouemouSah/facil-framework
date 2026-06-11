"""
Embedding Service - Generate semantic embeddings using Gemini

Uses Google Cloud Vertex AI text-embedding-004 model to generate
768-dimensional embeddings for semantic search.

Author: Claude Code
Date: 2025-01-22
"""

import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger

# Vertex AI imports
try:
    from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput
    import vertexai
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    logger.warning("⚠️ Vertex AI SDK not installed. Install with: pip install google-cloud-aiplatform")

from app.config import settings
from app.core.ai_telemetry import traced_embed_sync


class EmbeddingService:
    """
    Generate embeddings using Gemini text-embedding-004

    Model specifications:
    - Dimensions: 768
    - Max input tokens: 2048
    - Cost: ~$0.000025 per 1K characters (2024 pricing)
    - Supports batch processing (up to 250 texts)

    Usage:
        embedding_service = EmbeddingService()
        embedding = await embedding_service.generate_embedding("Hello world")
    """

    def __init__(self):
        """Initialize embedding service with Vertex AI"""
        if not VERTEX_AI_AVAILABLE:
            logger.error("❌ Vertex AI SDK not available - embeddings disabled")
            self.model = None
            self.enabled = False
            return

        try:
            # Initialize Vertex AI with project and location
            vertexai.init(
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.GOOGLE_CLOUD_LOCATION
            )

            # Load embedding model
            self.model = TextEmbeddingModel.from_pretrained(
                settings.GEMINI_EMBEDDING_MODEL
            )

            self.enabled = True
            logger.info(
                f"✅ Embedding service initialized "
                f"(model: {settings.GEMINI_EMBEDDING_MODEL}, "
                f"project: {settings.GOOGLE_CLOUD_PROJECT})"
            )

        except Exception as e:
            logger.error(f"❌ Failed to initialize embedding service: {e}")
            self.model = None
            self.enabled = False

    async def generate_embedding(
        self,
        text: str,
        task_type: str = "RETRIEVAL_DOCUMENT",
        title: Optional[str] = None
    ) -> Optional[List[float]]:
        """
        Generate embedding for single text

        Args:
            text: Text to embed (max 2048 tokens)
            task_type: Task type for optimized embeddings:
                - RETRIEVAL_QUERY: For search queries
                - RETRIEVAL_DOCUMENT: For documents (default)
                - SEMANTIC_SIMILARITY: For similarity comparison
                - CLASSIFICATION: For text classification
            title: Optional title for document (helps with relevance)

        Returns:
            768-dimensional embedding vector or None if failed

        Cost: ~$0.000025 per 1K characters
        """
        if not self.enabled or not self.model:
            logger.warning("Embedding service disabled - returning None")
            return None

        if not text or len(text.strip()) == 0:
            logger.warning("Empty text provided for embedding")
            return None

        try:
            # Prepare input
            embedding_input = TextEmbeddingInput(
                text=text,
                task_type=task_type,
                title=title
            )

            # Generate embedding via wrapper (telemetry + executor)
            embeddings = await traced_embed_sync(
                self.model, [embedding_input],
                feature="embeddings_rag",
            )

            if not embeddings or len(embeddings) == 0:
                logger.error("No embeddings returned from model")
                return None

            # Extract vector values
            embedding_vector = embeddings[0].values

            logger.debug(
                f"Generated embedding for text (length: {len(text)}, "
                f"dimensions: {len(embedding_vector)})"
            )

            return embedding_vector

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    async def batch_generate_embeddings(
        self,
        texts: List[str],
        batch_size: int = None,
        task_type: str = "RETRIEVAL_DOCUMENT",
        show_progress: bool = True
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings in batches for efficiency

        Args:
            texts: List of texts to embed
            batch_size: Batch size (default: from settings, max 250)
            task_type: Task type for all embeddings
            show_progress: Log progress updates

        Returns:
            List of embedding vectors (same order as input)

        Used for:
        - Initial population of fiscal_services embeddings
        - Bulk updates after data changes

        Cost: ~$0.000025 per 1K characters * total characters
        """
        if not self.enabled or not self.model:
            logger.warning("Embedding service disabled - returning None list")
            return [None] * len(texts)

        if not texts:
            return []

        # Use configured batch size or default
        if batch_size is None:
            batch_size = settings.EMBEDDING_BATCH_SIZE

        # Gemini has a limit of 250 texts per batch
        batch_size = min(batch_size, 250)

        all_embeddings = []
        total_texts = len(texts)

        try:
            for i in range(0, total_texts, batch_size):
                batch = texts[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (total_texts + batch_size - 1) // batch_size

                if show_progress:
                    logger.info(
                        f"Processing batch {batch_num}/{total_batches} "
                        f"({len(batch)} texts)"
                    )

                # Prepare batch inputs
                batch_inputs = [
                    TextEmbeddingInput(text=text, task_type=task_type)
                    for text in batch
                    if text and len(text.strip()) > 0
                ]

                # Generate embeddings (sync call in executor)
                loop = asyncio.get_event_loop()
                batch_embeddings = await loop.run_in_executor(
                    None,
                    lambda: self.model.get_embeddings(batch_inputs)
                )

                # Extract vectors
                batch_vectors = [emb.values for emb in batch_embeddings]
                all_embeddings.extend(batch_vectors)

                if show_progress:
                    logger.info(
                        f"Completed {len(all_embeddings)}/{total_texts} embeddings"
                    )

            logger.info(
                f"✅ Generated {len(all_embeddings)} embeddings in "
                f"{(total_texts + batch_size - 1) // batch_size} batches"
            )

            return all_embeddings

        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            # Return partial results + None for remaining
            remaining = total_texts - len(all_embeddings)
            return all_embeddings + [None] * remaining

    def prepare_service_text(self, service: Dict[str, Any]) -> str:
        """
        Prepare comprehensive text from fiscal service for embedding

        Combines all relevant fields to create rich semantic representation:
        - Service name and code
        - Description
        - Category hierarchy (category → sector → ministry)
        - Keywords (weighted by importance)

        Args:
            service: Fiscal service dict with fields:
                - name_es, service_code, description_es
                - category_name, sector_name, ministry_name (optional)
                - keywords: List[{keyword, weight, language}] (optional)

        Returns:
            Formatted text optimized for embedding generation

        Example output:
            "Servicio: Patente de Comercio | Código: PAT-001 |
             Descripción: Licencia comercial para actividades... |
             Categoría: Comercio e Industria | Sector: Economía |
             Ministerio: Economía y Planificación |
             Palabras clave: patente, comercio, licencia, negocio"
        """
        parts = []

        # Core fields (always present)
        parts.append(f"Servicio: {service.get('name_es', '')}")
        parts.append(f"Código: {service.get('service_code', '')}")

        # Description (if available)
        if service.get('description_es'):
            desc = service['description_es']
            # Truncate long descriptions to avoid token limits
            if len(desc) > 500:
                desc = desc[:500] + "..."
            parts.append(f"Descripción: {desc}")

        # Category hierarchy (enriches context)
        if service.get('category_name'):
            parts.append(f"Categoría: {service['category_name']}")

        if service.get('sector_name'):
            parts.append(f"Sector: {service['sector_name']}")

        if service.get('ministry_name'):
            parts.append(f"Ministerio: {service['ministry_name']}")

        # Keywords (prioritize by weight)
        if service.get('keywords'):
            # Filter Spanish keywords with weight > 0
            keywords_list = [
                kw['keyword']
                for kw in service['keywords']
                if kw.get('language_code') == 'es' and kw.get('weight', 0) > 0
            ]

            if keywords_list:
                # Sort by weight if available
                if all('weight' in kw for kw in service['keywords']):
                    keywords_list = [
                        kw['keyword']
                        for kw in sorted(
                            service['keywords'],
                            key=lambda x: x.get('weight', 0),
                            reverse=True
                        )
                        if kw.get('language_code') == 'es'
                    ]

                parts.append(f"Palabras clave: {', '.join(keywords_list)}")

        # Join all parts with separator
        return " | ".join(parts)

    async def generate_query_embedding(self, query: str) -> Optional[List[float]]:
        """
        Generate embedding optimized for search queries

        Uses RETRIEVAL_QUERY task type for better query-document matching

        Args:
            query: User search query

        Returns:
            768-dimensional embedding optimized for search
        """
        return await self.generate_embedding(
            text=query,
            task_type="RETRIEVAL_QUERY"
        )

    async def generate_document_embedding(
        self,
        text: str,
        title: Optional[str] = None
    ) -> Optional[List[float]]:
        """
        Generate embedding optimized for documents

        Uses RETRIEVAL_DOCUMENT task type for better indexing

        Args:
            text: Document text
            title: Optional document title (improves relevance)

        Returns:
            768-dimensional embedding optimized for document storage
        """
        return await self.generate_embedding(
            text=text,
            task_type="RETRIEVAL_DOCUMENT",
            title=title
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get embedding service statistics

        Returns:
            Dict with service status and configuration
        """
        return {
            "enabled": self.enabled,
            "model": settings.GEMINI_EMBEDDING_MODEL if self.enabled else None,
            "dimensions": settings.EMBEDDING_DIMENSIONS,
            "batch_size": settings.EMBEDDING_BATCH_SIZE,
            "project": settings.GOOGLE_CLOUD_PROJECT if self.enabled else None,
            "location": settings.GOOGLE_CLOUD_LOCATION if self.enabled else None,
            "vertex_ai_available": VERTEX_AI_AVAILABLE
        }


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

# Create singleton instance for use across application
embedding_service = EmbeddingService()
