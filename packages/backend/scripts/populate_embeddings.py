#!/usr/bin/env python3
"""
Populate Embeddings Script - Generate embeddings for fiscal services

This script generates and stores embeddings for all fiscal services
in the database using Gemini text-embedding-004 model.

STANDALONE VERSION: Does not import app modules to avoid circular imports.

Usage:
    python scripts/populate_embeddings.py [OPTIONS]

Options:
    --batch-size N      Batch size for embedding generation (default: 250)
    --force            Regenerate embeddings even if they exist
    --service-id ID    Only process specific service ID
    --limit N          Limit number of services to process (for testing)
    --dry-run          Preview without making changes

Examples:
    # Generate embeddings for all services
    python scripts/populate_embeddings.py

    # Test with first 10 services
    python scripts/populate_embeddings.py --limit 10

    # Force regeneration
    python scripts/populate_embeddings.py --force

    # Dry run to preview
    python scripts/populate_embeddings.py --dry-run --limit 5

Author: Claude Code
Date: 2025-01-22
"""

import asyncio
import argparse
import os
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

import asyncpg
from loguru import logger

# ============================================================================
# STANDALONE EMBEDDING SERVICE (no app module imports)
# ============================================================================

# Try to import Vertex AI
try:
    from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput
    import vertexai
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    logger.warning("⚠️ Vertex AI SDK not installed")


class StandaloneEmbeddingService:
    """
    Standalone embedding service that doesn't depend on app modules.
    Uses environment variables directly.
    """

    def __init__(self):
        """Initialize embedding service with Vertex AI"""
        # Get config from environment
        self.project = os.getenv("GOOGLE_CLOUD_PROJECT", "taxasge-dev")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.model_name = os.getenv("GEMINI_EMBEDDING_MODEL", "text-embedding-004")
        self.batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "250"))

        if not VERTEX_AI_AVAILABLE:
            logger.error("❌ Vertex AI SDK not available - embeddings disabled")
            self.model = None
            self.enabled = False
            return

        try:
            # Initialize Vertex AI with project and location
            vertexai.init(
                project=self.project,
                location=self.location
            )

            # Load embedding model
            self.model = TextEmbeddingModel.from_pretrained(self.model_name)

            self.enabled = True
            logger.info(
                f"✅ Embedding service initialized "
                f"(model: {self.model_name}, project: {self.project})"
            )

        except Exception as e:
            logger.error(f"❌ Failed to initialize embedding service: {e}")
            self.model = None
            self.enabled = False

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            "enabled": self.enabled,
            "model": self.model_name,
            "project": self.project,
            "location": self.location,
            "batch_size": self.batch_size,
        }

    def prepare_service_text(self, service: Dict[str, Any]) -> str:
        """
        Prepare rich text representation of a service for embedding

        Combines service name, description, category, ministry, and keywords
        into a single text optimized for semantic search.
        """
        parts = []

        # Service name (weighted heavily)
        if service.get('name_es'):
            parts.append(f"Servicio: {service['name_es']}")

        # Description
        if service.get('description_es'):
            parts.append(f"Descripción: {service['description_es']}")

        # Category hierarchy
        category_parts = []
        if service.get('ministry_name'):
            category_parts.append(f"Ministerio: {service['ministry_name']}")
        if service.get('sector_name'):
            category_parts.append(f"Sector: {service['sector_name']}")
        if service.get('category_name'):
            category_parts.append(f"Categoría: {service['category_name']}")
        if category_parts:
            parts.append(" | ".join(category_parts))

        # Keywords (for better semantic matching)
        if service.get('keywords'):
            keywords = service['keywords']
            if isinstance(keywords, list):
                keyword_texts = []
                for kw in keywords:
                    if isinstance(kw, dict) and kw.get('keyword'):
                        keyword_texts.append(kw['keyword'])
                if keyword_texts:
                    parts.append(f"Palabras clave: {', '.join(keyword_texts)}")

        return " | ".join(parts)

    async def batch_generate_embeddings(
        self,
        texts: List[str],
        batch_size: int = None,
        task_type: str = "RETRIEVAL_DOCUMENT",
        show_progress: bool = True
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings in batches for efficiency
        """
        if not self.enabled or not self.model:
            logger.warning("Embedding service disabled - returning None list")
            return [None] * len(texts)

        if not texts:
            return []

        # Use configured batch size or default
        if batch_size is None:
            batch_size = self.batch_size

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

                # Prepare inputs
                inputs = [
                    TextEmbeddingInput(text=text, task_type=task_type)
                    for text in batch
                ]

                # Generate embeddings (sync call, run in executor)
                loop = asyncio.get_event_loop()
                embeddings = await loop.run_in_executor(
                    None,
                    lambda: self.model.get_embeddings(inputs)
                )

                # Extract vectors
                batch_embeddings = [emb.values for emb in embeddings]
                all_embeddings.extend(batch_embeddings)

                if show_progress:
                    logger.info(
                        f"  ✅ Batch {batch_num} complete "
                        f"({len(batch_embeddings)} embeddings)"
                    )

            return all_embeddings

        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            # Return None for remaining texts
            remaining = total_texts - len(all_embeddings)
            all_embeddings.extend([None] * remaining)
            return all_embeddings


# ============================================================================
# DATABASE QUERIES
# ============================================================================

async def get_services_needing_embeddings(
    conn: asyncpg.Connection,
    force: bool = False,
    service_id: int = None,
    limit: int = None
) -> List[Dict[str, Any]]:
    """
    Get fiscal services that need embedding generation
    """
    # Build WHERE clause
    where_conditions = ["fs.status = 'active'"]

    if not force:
        where_conditions.append(
            "(fs.embedding IS NULL OR fs.needs_embedding_update = TRUE)"
        )

    if service_id:
        where_conditions.append(f"fs.id = {service_id}")

    where_clause = " AND ".join(where_conditions)

    # Query with full context
    query = f"""
        SELECT
            fs.id,
            fs.service_code,
            fs.name_es,
            fs.description_es,
            c.name_es as category_name,
            s.name_es as sector_name,
            m.name_es as ministry_name,

            -- Aggregate keywords
            ARRAY_AGG(
                DISTINCT jsonb_build_object(
                    'keyword', sk.keyword,
                    'weight', sk.weight,
                    'language_code', sk.language_code
                ) ORDER BY jsonb_build_object(
                    'keyword', sk.keyword,
                    'weight', sk.weight,
                    'language_code', sk.language_code
                )
            ) FILTER (WHERE sk.id IS NOT NULL) as keywords

        FROM fiscal_services fs
        LEFT JOIN categories c ON fs.category_id = c.id
        LEFT JOIN sectors s ON c.sector_id = s.id
        LEFT JOIN ministries m ON c.ministry_id = m.id
        LEFT JOIN service_keywords sk ON fs.id = sk.fiscal_service_id

        WHERE {where_clause}

        GROUP BY
            fs.id, fs.service_code, fs.name_es, fs.description_es,
            c.name_es, s.name_es, m.name_es

        ORDER BY fs.id
        {"LIMIT " + str(limit) if limit else ""}
    """

    results = await conn.fetch(query)
    return [dict(row) for row in results]


async def update_service_embedding(
    conn: asyncpg.Connection,
    service_id: int,
    embedding: List[float],
    model_name: str,
    dry_run: bool = False
) -> bool:
    """
    Update service embedding in database
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would update embedding for service_id={service_id}")
        return True

    # Convert embedding list to pgvector string format
    embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'

    query = """
        UPDATE fiscal_services
        SET
            embedding = $1::vector,
            embedding_generated_at = NOW(),
            embedding_model = $2,
            embedding_version = COALESCE(embedding_version, 0) + 1,
            needs_embedding_update = FALSE
        WHERE id = $3
        RETURNING id
    """

    try:
        result = await conn.fetchrow(
            query,
            embedding_str,
            model_name,
            service_id
        )

        if result:
            logger.debug(f"Updated embedding for service_id={service_id}")
            return True
        else:
            logger.error(f"Failed to update service_id={service_id} (not found)")
            return False

    except Exception as e:
        logger.error(f"Error updating service_id={service_id}: {e}")
        return False


async def get_embedding_stats(conn: asyncpg.Connection) -> Dict[str, Any]:
    """Get current embedding coverage statistics"""
    query = """
        SELECT
            COUNT(*) as total_services,
            COUNT(embedding) as total_with_embeddings,
            COUNT(*) - COUNT(embedding) as total_without_embeddings,
            SUM(CASE WHEN needs_embedding_update = TRUE THEN 1 ELSE 0 END) as total_needs_update,
            ROUND(COUNT(embedding)::numeric / NULLIF(COUNT(*), 0) * 100, 2) as coverage_percentage
        FROM fiscal_services
        WHERE status = 'active'
    """

    try:
        result = await conn.fetchrow(query)
        return dict(result) if result else {}
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {}


# ============================================================================
# MAIN PROCESSING LOGIC
# ============================================================================

async def process_services(
    services: List[Dict[str, Any]],
    conn: asyncpg.Connection,
    embedding_service: StandaloneEmbeddingService,
    batch_size: int = 250,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Process services and generate embeddings
    """
    if not services:
        logger.warning("No services to process")
        return {"processed": 0, "success": 0, "failed": 0}

    total = len(services)
    logger.info(f"Processing {total} services in batches of {batch_size}")

    # Prepare texts for embedding
    texts = []
    service_ids = []

    for service in services:
        text = embedding_service.prepare_service_text(service)
        texts.append(text)
        service_ids.append(service['id'])

        if dry_run:
            logger.info(f"[DRY RUN] Service {service['service_code']}:")
            logger.info(f"  Text: {text[:200]}...")

    if dry_run:
        logger.info(f"[DRY RUN] Would generate {len(texts)} embeddings")
        return {
            "processed": len(texts),
            "success": len(texts),
            "failed": 0,
            "dry_run": True
        }

    # Generate embeddings in batches
    logger.info("Generating embeddings with Gemini...")
    embeddings = await embedding_service.batch_generate_embeddings(
        texts=texts,
        batch_size=batch_size,
        show_progress=True
    )

    # Update database
    logger.info("Updating database...")
    success_count = 0
    failed_count = 0

    for service_id, embedding in zip(service_ids, embeddings):
        if embedding:
            success = await update_service_embedding(
                conn, service_id, embedding, embedding_service.model_name
            )
            if success:
                success_count += 1
            else:
                failed_count += 1
        else:
            logger.warning(f"No embedding generated for service_id={service_id}")
            failed_count += 1

    return {
        "processed": total,
        "success": success_count,
        "failed": failed_count
    }


async def main(args: argparse.Namespace):
    """Main execution function"""

    logger.info("=" * 70)
    logger.info("EMBEDDING POPULATION SCRIPT (Standalone)")
    logger.info("=" * 70)

    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("❌ DATABASE_URL environment variable not set!")
        return 1

    logger.info(f"Database: {database_url[:50]}...")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Force regeneration: {args.force}")
    logger.info(f"Dry run: {args.dry_run}")
    if args.limit:
        logger.info(f"Limit: {args.limit}")
    if args.service_id:
        logger.info(f"Service ID: {args.service_id}")
    logger.info("=" * 70)

    # Initialize embedding service
    embedding_service = StandaloneEmbeddingService()

    if not embedding_service.enabled:
        logger.error("❌ Embedding service is not enabled!")
        logger.error("Please check:")
        logger.error("  1. Vertex AI SDK installed: pip install google-cloud-aiplatform")
        logger.error("  2. Google Cloud credentials configured")
        logger.error("  3. Vertex AI API enabled in GCP project")
        return 1

    logger.info(f"✅ Embedding service ready: {embedding_service.get_stats()}")

    # Connect to database
    logger.info("Connecting to database...")
    try:
        conn = await asyncpg.connect(database_url)
        logger.info("✅ Database connected")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return 1

    try:
        # Get initial stats
        logger.info("\nInitial embedding coverage:")
        stats_before = await get_embedding_stats(conn)
        logger.info(f"  Total services: {stats_before.get('total_services', 0)}")
        logger.info(f"  With embeddings: {stats_before.get('total_with_embeddings', 0)}")
        logger.info(f"  Needs update: {stats_before.get('total_needs_update', 0)}")
        logger.info(f"  Coverage: {stats_before.get('coverage_percentage', 0)}%")

        # Get services needing embeddings
        logger.info("\nFetching services...")
        services = await get_services_needing_embeddings(
            conn,
            force=args.force,
            service_id=args.service_id,
            limit=args.limit
        )

        if not services:
            logger.info("✅ No services need embedding generation!")
            return 0

        logger.info(f"Found {len(services)} services to process")

        # Preview first few
        logger.info("\nPreview of services to process:")
        for service in services[:5]:
            logger.info(f"  - {service['service_code']}: {service['name_es']}")

        if len(services) > 5:
            logger.info(f"  ... and {len(services) - 5} more")

        # Process services
        logger.info("\n" + "=" * 70)
        logger.info("PROCESSING EMBEDDINGS")
        logger.info("=" * 70)

        start_time = datetime.now()

        result = await process_services(
            services,
            conn,
            embedding_service,
            batch_size=args.batch_size,
            dry_run=args.dry_run
        )

        elapsed = (datetime.now() - start_time).total_seconds()

        # Final stats
        logger.info("\n" + "=" * 70)
        logger.info("RESULTS")
        logger.info("=" * 70)
        logger.info(f"Processed: {result['processed']}")
        logger.info(f"Success: {result['success']}")
        logger.info(f"Failed: {result['failed']}")
        logger.info(f"Time: {elapsed:.2f}s")
        logger.info(f"Avg: {elapsed / max(result['processed'], 1):.2f}s per service")

        if not args.dry_run:
            logger.info("\nFinal embedding coverage:")
            stats_after = await get_embedding_stats(conn)
            logger.info(f"  Total services: {stats_after.get('total_services', 0)}")
            logger.info(f"  With embeddings: {stats_after.get('total_with_embeddings', 0)}")
            logger.info(f"  Coverage: {stats_after.get('coverage_percentage', 0)}%")

        logger.info("=" * 70)
        logger.info("✅ COMPLETED")
        logger.info("=" * 70)

        return 0

    finally:
        await conn.close()
        logger.info("Database connection closed")


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate embeddings for fiscal services",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=250,
        help="Batch size for embedding generation (default: 250, max: 250)"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate embeddings even if they exist"
    )

    parser.add_argument(
        "--service-id",
        type=int,
        help="Only process specific service ID"
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of services to process (for testing)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without making changes"
    )

    args = parser.parse_args()

    # Run async main
    exit_code = asyncio.run(main(args))
    sys.exit(exit_code)
