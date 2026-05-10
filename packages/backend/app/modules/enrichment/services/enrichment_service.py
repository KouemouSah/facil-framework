"""
Enrichment Service — Production-grade Gemini-powered enrichment agent.

Architecture:
- process_batch(conn, limit=20): Sequential processing for cron backward compat
- process_all_pending(): Concurrent processing (Semaphore=10) with progress tracking
  - Auto-triggered after seed (Option B — one-click flow)
  - Also available via manual "Procesar Ahora" (Option A)

Pattern: BatchDocumentClassifier semaphore + asyncio.gather (10 concurrent Gemini calls).
Scale: 1000+ tasks in ~5 minutes (vs 4+ hours sequential).
"""

import asyncio
import json
import re
import time
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from loguru import logger

from app.config import get_settings
from app.core.ai_telemetry import traced_generate_sync
from app.modules.enrichment.repositories.enrichment_repository import (
    EnrichmentRepository,
)

from app.modules.shared.services.vertex_ai_manager import (
    VERTEX_AI_AVAILABLE,
    VertexAIManager,
)

if VERTEX_AI_AVAILABLE:
    from vertexai.generative_models import GenerationConfig


# ---------------------------------------------------------------------------
# Concurrency tuning (production-grade)
# ---------------------------------------------------------------------------
ENRICHMENT_CONCURRENCY = 10     # Max parallel Gemini calls (Flash handles 1000+ RPM)
BATCH_CLAIM_SIZE = 50           # Tasks claimed per DB round-trip
MAX_CONSECUTIVE_FAILURES = 5    # Circuit breaker threshold
MAX_CIRCUIT_BREAKER_TRIPS = 3   # Stop after N circuit breaker resets
CIRCUIT_BREAKER_PAUSE_S = 30    # Pause duration on circuit break

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

DESCRIPTION_PROMPT = """Eres un experto en servicios fiscales del Gobierno de Guinea Ecuatorial.
Genera una descripción estructurada en español para este servicio.

DATOS DEL SERVICIO:
- Nombre: {name_es}
- Código: {service_code}
- Categoría: {category}
- Sector: {sector}
- Ministerio: {ministry}
- Tipo: {service_type}
- Procedimientos asociados: {procedure_count}
- Documentos requeridos: {document_count}
{bundle_info}
{similar_examples}

FORMATO OBLIGATORIO (3 párrafos separados por línea en blanco, máximo 600 caracteres total):

QUÉ ES: [Definición del servicio en 1-2 frases. Naturaleza jurídica/administrativa.]

PARA QUIÉN: [Público objetivo y casos de uso en 1-2 frases. Sectores, perfiles de usuarios.]

RESULTADO: [Qué obtiene el usuario en 1-2 frases. Documento/autorización, validez, efecto jurídico.]

REGLAS CRÍTICAS:
1. SOLO información derivable de los datos — NO inventar
2. NO incluir precios, montos, ni tarifas (ya se muestran en la interfaz)
3. NO listar documentos requeridos (ya se muestran en la interfaz)
4. NO detallar procedimientos ni pasos (ya se muestran en la interfaz)
5. Tono profesional e institucional, tercera persona, frases completas con puntuación
6. Máximo 600 caracteres en TOTAL (aprox. 200 por sección)
7. Cada sección en un párrafo separado (línea en blanco entre secciones)
8. Respetar EXACTAMENTE el formato de 3 secciones con sus etiquetas

Responde SOLO con las 3 secciones, sin comillas ni prefijos."""

SELF_EVALUATION_PROMPT = """Evalúa la siguiente descripción de servicio fiscal.

SERVICIO: {name_es}
DESCRIPCIÓN GENERADA:
{description}

Criterios de evaluación (0-10 cada uno):
1. FORMATO: ¿Tiene exactamente 3 secciones (QUÉ ES / PARA QUIÉN / RESULTADO)?
2. PRECISION: ¿La información es derivable del nombre/categoría del servicio?
3. PROFESIONALISMO: ¿Tono institucional sin informalidades?
4. RESTRICCIONES: ¿NO contiene precios, documentos ni procedimientos?

Responde SOLO con JSON: {{"format": N, "precision": N, "professionalism": N, "restrictions": N, "average": N.N}}"""

TRANSLATION_PROMPT = """Traduce los siguientes textos del español al {target_language}.
Contexto: servicio fiscal del gobierno de Guinea Ecuatorial.
Conserva los términos técnicos (XAF, nombres de ministerios).
Tono formal administrativo.

Nombre: {name_es}
Descripción: {description_es}

Responde SOLO con JSON válido: {{"name": "traducción del nombre", "description": "traducción de la descripción"}}"""

MINISTRY_DESCRIPTION_PROMPT = """Eres un experto en la administración pública de Guinea Ecuatorial.
Genera una descripción concisa (2-3 frases, máximo 250 caracteres) para el siguiente ministerio.
La descripción debe explicar: la misión del ministerio y sus competencias principales.

DATOS DEL MINISTERIO:
- Nombre: {name_es}
- Código: {ministry_code}
- Sectores: {sectors}
- Número de servicios fiscales gestionados: {service_count}

REGLAS CRÍTICAS:
1. SOLO información derivable de los datos y del nombre del ministerio — NO inventar
2. Tono formal institucional
3. En español
4. Máximo 250 caracteres

Responde SOLO con el texto de la descripción, sin comillas ni prefijos."""

KEYWORDS_PROMPT = """Genera entre 5 y 8 palabras clave de búsqueda para el siguiente servicio fiscal.
Las palabras clave deben ayudar a los ciudadanos a encontrar este servicio.

Nombre: {name_es}
Descripción: {description_es}
Categoría: {category}

Genera palabras clave en los 3 idiomas:
- ES (español): 5-8 palabras
- FR (français): 5-8 mots
- EN (English): 5-8 words

Responde SOLO con JSON válido:
{{"es": ["palabra1", "palabra2", ...], "fr": ["mot1", "mot2", ...], "en": ["word1", "word2", ...]}}"""

# Max lengths — defense against unusually long LLM output
_MAX_DESCRIPTION_LEN = 700  # 600 target + margin for section labels
_MAX_NAME_LEN = 200
_MAX_KEYWORD_LEN = 50

_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Human-readable labels for service_type enum
_SERVICE_TYPE_LABELS = {
    "document_processing": "Procesamiento de documentos",
    "license_permit": "Licencia o permiso",
    "residence_permit": "Permiso de residencia",
    "registration_fee": "Tasa de registro",
    "inspection_fee": "Tasa de inspección",
    "administrative_tax": "Tasa administrativa",
    "customs_duty": "Derecho de aduana",
    "declaration_tax": "Tasa de declaración",
}


def _sanitize_llm_text(text: str, max_len: int = 500) -> str:
    """Strip HTML tags and truncate LLM output. Defense-in-depth against XSS."""
    cleaned = _HTML_TAG_RE.sub("", text).strip()
    return cleaned[:max_len]


class EnrichmentService:
    """Production-grade Gemini-powered enrichment agent for fiscal services."""

    def __init__(self):
        self._model: Optional[GenerativeModel] = None
        self._initialized = False
        self._processing_lock = asyncio.Lock()

    def _ensure_initialized(self):
        """Lazy initialization of Gemini model via VertexAIManager singleton."""
        if self._initialized:
            return

        manager = VertexAIManager()
        if not manager.is_available:
            self._initialized = True
            return

        try:
            settings = get_settings()
            model_name = getattr(settings, "GEMINI_CHAT_MODEL", "gemini-2.0-flash")
            self._model = manager.create_model(model_name)
            self._initialized = True
            logger.info(f"EnrichmentService initialized via VertexAIManager ({model_name})")
        except Exception as e:
            logger.error(f"Failed to initialize EnrichmentService: {e}")
            self._initialized = True

    # ------------------------------------------------------------------
    # Public static: auto-enqueue hook for fiscal service CRUD
    # ------------------------------------------------------------------

    @staticmethod
    async def auto_enqueue(
        conn,
        service_id: int,
        current_description: Optional[str],
        description_source: Optional[str] = None,
    ) -> int:
        """
        Auto-enqueue enrichment tasks after service create/update.
        Non-blocking: caller wraps in try/except.

        Returns number of tasks enqueued.
        """
        enqueued = 0
        has_description = bool(
            current_description and current_description.strip()
        )

        if not has_description:
            if description_source != "manual":
                result = await EnrichmentRepository.enqueue(
                    conn, service_id, "generate_description", priority=1
                )
                if result:
                    enqueued += 1
        else:
            for lang in ("translate_fr", "translate_en"):
                result = await EnrichmentRepository.enqueue(
                    conn, service_id, lang, priority=0
                )
                if result:
                    enqueued += 1

        if enqueued:
            logger.info(
                f"Enrichment: enqueued {enqueued} tasks for service {service_id}"
            )
        return enqueued

    # ------------------------------------------------------------------
    # Cron: process a batch of pending tasks (sequential, backward compat)
    # ------------------------------------------------------------------

    async def process_batch(
        self, conn, limit: int = 20
    ) -> Dict[str, Any]:
        """
        Process a batch of pending enrichment tasks — SEQUENTIAL.
        Called by cron endpoint every 5 minutes as a safety net.

        Uses atomic claim pattern:
        1. Transaction: SELECT FOR UPDATE SKIP LOCKED + UPDATE status='processing'
        2. Commit (releases locks, but tasks are now 'processing')
        3. Process tasks one by one (Gemini calls, outside transaction)
        """
        self._ensure_initialized()

        if not self._model:
            logger.warning("Gemini model not available — skipping enrichment batch")
            return {"processed": 0, "failed": 0, "skipped": 0, "tokens_total": 0}

        # Phase 1: Atomically claim a batch
        async with conn.transaction():
            tasks = await EnrichmentRepository.fetch_pending_batch(conn, limit)
            if not tasks:
                return {"processed": 0, "failed": 0, "skipped": 0, "tokens_total": 0}
            task_ids = [t["id"] for t in tasks]
            await EnrichmentRepository.mark_processing_batch(conn, task_ids)

        # Phase 2: Process tasks one by one (sequential — cron safety net)
        processed = 0
        failed = 0
        skipped = 0
        tokens_total = 0

        for task in tasks:
            status, tokens = await self._process_single_task(conn, task)
            if status == "processed":
                processed += 1
                tokens_total += tokens
            elif status == "skipped":
                skipped += 1
            else:
                failed += 1

        return {
            "processed": processed,
            "failed": failed,
            "skipped": skipped,
            "tokens_total": tokens_total,
        }

    # ------------------------------------------------------------------
    # Production agent: concurrent processing of ALL pending tasks
    # ------------------------------------------------------------------

    async def process_all_pending(self) -> Dict[str, Any]:
        """
        Process ALL pending enrichment tasks with concurrent Gemini calls.

        Architecture (BatchDocumentClassifier pattern):
        - asyncio.Semaphore(10) limits parallel Gemini calls
        - asyncio.gather runs batch concurrently
        - Circuit breaker stops after consecutive failures
        - Redis progress tracking for admin UI polling

        Scale: 1000 tasks × 10 concurrent × ~2s/call = ~3-5 minutes.
        """
        if self._processing_lock.locked():
            logger.warning("Enrichment: process_all_pending already running — skipping")
            return {"processed": 0, "failed": 0, "skipped": 0, "status": "already_running"}

        async with self._processing_lock:
            return await self._do_process_all()

    async def _do_process_all(self) -> Dict[str, Any]:
        """Core concurrent processing loop. Must be called under _processing_lock."""
        from app.database.connection import db_manager
        from app.core.cache import get_cache, invalidate_services_cache

        self._ensure_initialized()
        if not self._model:
            logger.warning("Gemini model not available — skipping enrichment agent")
            return {"processed": 0, "failed": 0, "skipped": 0, "status": "no_model"}

        cache = get_cache()
        job_id = str(uuid4())
        semaphore = asyncio.Semaphore(ENRICHMENT_CONCURRENCY)

        # Count total pending for progress tracking
        async with db_manager.get_connection() as conn:
            total = await EnrichmentRepository.count_pending(conn)

        if total == 0:
            logger.info("Enrichment agent: 0 pending tasks — nothing to do")
            await cache.set("enrichment:progress", {
                "job_id": job_id, "total": 0, "processed": 0,
                "failed": 0, "skipped": 0, "tokens_total": 0,
                "status": "completed",
            }, ttl=300)
            return {"processed": 0, "failed": 0, "skipped": 0, "total": 0, "status": "completed"}

        logger.info(f"Enrichment agent starting: {total} pending tasks, concurrency={ENRICHMENT_CONCURRENCY}")

        # Initial progress
        progress = {
            "job_id": job_id, "total": total,
            "processed": 0, "failed": 0, "skipped": 0,
            "tokens_total": 0, "status": "running",
        }
        await cache.set("enrichment:progress", progress, ttl=3600)

        processed = 0
        failed = 0
        skipped = 0
        tokens_total = 0
        consecutive_failures = 0
        circuit_breaker_trips = 0

        try:
            while True:
                # ---- Claim batch atomically ----
                async with db_manager.get_connection() as conn:
                    async with conn.transaction():
                        tasks = await EnrichmentRepository.fetch_pending_batch(
                            conn, limit=BATCH_CLAIM_SIZE
                        )
                        if not tasks:
                            break
                        task_ids = [t["id"] for t in tasks]
                        await EnrichmentRepository.mark_processing_batch(conn, task_ids)

                # ---- Circuit breaker check ----
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    circuit_breaker_trips += 1
                    if circuit_breaker_trips >= MAX_CIRCUIT_BREAKER_TRIPS:
                        logger.error(
                            f"Enrichment circuit breaker: {MAX_CIRCUIT_BREAKER_TRIPS} trips — "
                            f"stopping agent. {failed} failures total."
                        )
                        break
                    logger.warning(
                        f"Enrichment circuit breaker trip #{circuit_breaker_trips}: "
                        f"{consecutive_failures} consecutive failures — "
                        f"pausing {CIRCUIT_BREAKER_PAUSE_S}s"
                    )
                    await cache.set("enrichment:progress", {
                        "job_id": job_id, "total": total,
                        "processed": processed, "failed": failed,
                        "skipped": skipped, "tokens_total": tokens_total,
                        "status": "circuit_breaker_pause",
                    }, ttl=3600)
                    await asyncio.sleep(CIRCUIT_BREAKER_PAUSE_S)
                    consecutive_failures = 0

                # ---- Process batch concurrently (semaphore pattern) ----
                async def _process_one(task_data: Dict[str, Any]) -> tuple:
                    async with semaphore:
                        async with db_manager.get_connection() as task_conn:
                            return await self._process_single_task(task_conn, task_data)

                coroutines = [_process_one(t) for t in tasks]
                results = await asyncio.gather(*coroutines, return_exceptions=True)

                # ---- Aggregate results ----
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        failed += 1
                        consecutive_failures += 1
                        logger.error(
                            f"Enrichment gather exception: task={tasks[i]['id']} "
                            f"error={result}"
                        )
                        try:
                            async with db_manager.get_connection() as exc_conn:
                                await EnrichmentRepository.mark_failed(
                                    exc_conn, tasks[i]["id"], str(result)[:500]
                                )
                        except Exception:
                            pass
                    else:
                        status, tokens = result
                        if status == "processed":
                            processed += 1
                            tokens_total += tokens
                            consecutive_failures = 0
                        elif status == "skipped":
                            skipped += 1
                        elif status == "failed":
                            failed += 1
                            consecutive_failures += 1

                # ---- Update progress in Redis ----
                await cache.set("enrichment:progress", {
                    "job_id": job_id, "total": total,
                    "processed": processed, "failed": failed,
                    "skipped": skipped, "tokens_total": tokens_total,
                    "status": "running",
                }, ttl=3600)

                logger.info(
                    f"Enrichment agent batch done: {processed}/{total} processed, "
                    f"{failed} failed (batch of {len(tasks)})"
                )

        except Exception as e:
            logger.error(f"Enrichment agent error: {e}")

        # ---- Final progress ----
        final_status = "completed"
        await cache.set("enrichment:progress", {
            "job_id": job_id, "total": total,
            "processed": processed, "failed": failed,
            "skipped": skipped, "tokens_total": tokens_total,
            "status": final_status,
        }, ttl=3600)

        # ---- Refresh materialized view once at the end ----
        if processed > 0:
            try:
                async with db_manager.get_connection() as conn:
                    async with conn.transaction():
                        await conn.execute("SET LOCAL statement_timeout = '120000'")
                        await conn.execute(
                            "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_services_translated"
                        )
                logger.info("mv_services_translated refreshed after enrichment agent")
            except Exception as e:
                logger.warning(f"MV refresh CONCURRENTLY failed: {e}")
                try:
                    async with db_manager.get_connection() as conn:
                        await conn.execute(
                            "REFRESH MATERIALIZED VIEW mv_services_translated"
                        )
                    logger.info("mv_services_translated refreshed (non-concurrent fallback)")
                except Exception as e2:
                    logger.error(f"MV refresh fallback also failed: {e2}")

            await invalidate_services_cache()

        logger.info(
            f"Enrichment agent completed: {processed}/{total} processed, "
            f"{failed} failed, {skipped} skipped, {tokens_total} tokens"
        )

        return {
            "processed": processed,
            "failed": failed,
            "skipped": skipped,
            "tokens_total": tokens_total,
            "total": total,
            "status": final_status,
        }

    # ------------------------------------------------------------------
    # Single task processor (extracted from process_batch for loop)
    # ------------------------------------------------------------------

    async def _process_single_task(
        self, conn, task: Dict[str, Any]
    ) -> tuple:
        """
        Process a single enrichment task.

        Returns: (status, tokens) where status is 'processed', 'failed', or 'skipped'.
        """
        task_id = task["id"]
        service_id = task["fiscal_service_id"]
        task_type = task["task_type"]

        try:
            # Ministry tasks use a different context path
            if task_type == "generate_ministry_description":
                context = None
            else:
                context = await EnrichmentRepository.get_service_context(
                    conn, service_id
                )
                if not context:
                    await EnrichmentRepository.mark_failed(
                        conn, task_id, f"Service {service_id} not found"
                    )
                    return ("failed", 0)

                # Defer translations if no description yet
                if task_type in ("translate_fr", "translate_en"):
                    if not context.get("description_es"):
                        await EnrichmentRepository.mark_deferred(
                            conn, task_id,
                            "No description_es to translate — deferred until description is generated"
                        )
                        return ("skipped", 0)

            # Dispatch to handler
            start = time.monotonic()
            tokens = 0

            if task_type == "generate_description":
                tokens = await self._generate_description(conn, task_id, context)
            elif task_type == "generate_keywords":
                tokens = await self._generate_keywords(conn, task_id, context)
            elif task_type in ("translate_fr", "translate_en"):
                target = task_type.replace("translate_", "")
                tokens = await self._translate(conn, task_id, context, target)
            elif task_type == "generate_ministry_description":
                tokens = await self._generate_ministry_description(conn, task_id, service_id)
            else:
                await EnrichmentRepository.mark_failed(
                    conn, task_id, f"Unknown task_type: {task_type}"
                )
                return ("failed", 0)

            elapsed = round(time.monotonic() - start, 2)

            # tokens == 0 means handler called mark_failed internally
            if tokens == 0:
                return ("failed", 0)

            logger.info(
                f"Enrichment OK: service={service_id} type={task_type} "
                f"tokens={tokens} elapsed={elapsed}s"
            )
            return ("processed", tokens)

        except Exception as e:
            logger.error(
                f"Enrichment FAIL: service={service_id} type={task_type} error={e}"
            )
            try:
                await EnrichmentRepository.mark_failed(conn, task_id, str(e)[:500])
            except Exception:
                pass
            return ("failed", 0)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _generate_description(
        self, conn, task_id: UUID, context: Dict[str, Any]
    ) -> int:
        """
        Generate structured Spanish description via Gemini Flash (v2).

        Flow: enriched context + few-shot → generate → self-evaluate → retry if low quality.
        """
        service_id = context["id"]

        # 1. Fetch enriched context (category hierarchy, sector, bundle, counts)
        enriched = await EnrichmentRepository.get_enriched_service_context(conn, service_id)
        if not enriched:
            await EnrichmentRepository.mark_failed(conn, task_id, f"Enriched context not found for {service_id}")
            return 0

        # 2. Fetch few-shot examples from similar services with descriptions
        similar = await EnrichmentRepository.get_similar_services_fewshot(conn, service_id, limit=3)
        similar_text = ""
        if similar:
            examples = []
            for s in similar:
                examples.append(f"  - {s['name_es']} ({s.get('category_name', '')}): {s['description_es']}")
            similar_text = "- Ejemplos de descripciones similares:\n" + "\n".join(examples)
            logger.info(f"Enrichment: {len(similar)} similar services found as few-shot examples for service {service_id}")

        # 3. Build bundle info
        bundle_info = ""
        if enriched.get("bundle_name"):
            bundle_info = f"- Paquete fiscal asociado: {enriched['bundle_name']}"

        # 4. Format prompt
        raw_type = enriched.get("service_type", "")
        prompt = DESCRIPTION_PROMPT.format(
            name_es=enriched.get("name_es", ""),
            service_code=enriched.get("service_code", ""),
            category=enriched.get("category_name", "Sin categoría"),
            sector=enriched.get("sector_name", "Sin sector"),
            ministry=enriched.get("ministry_name", "Sin ministerio"),
            service_type=_SERVICE_TYPE_LABELS.get(raw_type, raw_type),
            procedure_count=enriched.get("procedure_count", 0),
            document_count=enriched.get("document_count", 0),
            bundle_info=bundle_info,
            similar_examples=similar_text,
        )

        # 5. Generate description
        description, quality_score = await self._generate_and_evaluate(
            conn, task_id, prompt, enriched.get("name_es", "")
        )
        if not description:
            return 0  # mark_failed already called inside

        # 6. Determine description_source based on quality
        desc_source = "ai_draft"
        if quality_score is not None and quality_score < 6.0:
            desc_source = "ai_draft_low_quality"
            logger.warning(
                f"Enrichment: low quality score ({quality_score}) for service {service_id} — "
                f"marked as ai_draft_low_quality"
            )

        # 7. Save to DB
        await conn.execute(
            """
            UPDATE fiscal_services
            SET description_es = $1, description_source = $2,
                description_visible = false, updated_at = NOW()
            WHERE id = $3
              AND (description_source IS NULL
                   OR description_source NOT IN ('manual', 'ai_approved'))
            """,
            description,
            desc_source,
            service_id,
        )

        tokens = len(prompt.split()) + len(description.split())
        await EnrichmentRepository.mark_completed(
            conn, task_id,
            output_data={
                "description": description,
                "quality_score": quality_score,
                "similar_count": len(similar),
                "has_bundle": bool(enriched.get("bundle_name")),
            },
            tokens_used=tokens,
        )

        # Auto-enqueue translations now that we have a description
        for lang_task in ("translate_fr", "translate_en"):
            await EnrichmentRepository.enqueue(
                conn, service_id, lang_task, priority=0
            )

        return tokens

    async def _generate_and_evaluate(
        self, conn, task_id: UUID, prompt: str, service_name: str
    ) -> tuple:
        """
        Generate description + self-evaluate. Retry once if quality < 6.0.
        Returns (description, quality_score) or (None, None) on failure.
        """
        for attempt in range(2):
            text = await self._call_gemini(prompt, max_tokens=500)
            if not text:
                if attempt == 0:
                    continue  # retry once on empty
                await EnrichmentRepository.mark_failed(conn, task_id, "Empty Gemini response after retry")
                return None, None

            description = _sanitize_llm_text(text.strip('"').strip("'"), _MAX_DESCRIPTION_LEN)
            if len(description) < 20:
                if attempt == 0:
                    continue
                await EnrichmentRepository.mark_failed(
                    conn, task_id, f"Description too short after retry: {description}"
                )
                return None, None

            # Self-evaluate
            quality_score = await self._self_evaluate(description, service_name)

            if quality_score is not None and quality_score >= 6.0:
                return description, quality_score
            elif attempt == 0 and quality_score is not None and quality_score < 6.0:
                logger.info(
                    f"Enrichment: quality {quality_score} < 6.0 for '{service_name}' — retrying"
                )
                continue  # retry with same prompt
            else:
                # Second attempt or eval failed — return what we have
                return description, quality_score

        # Should not reach here, but safety
        return None, None

    async def _self_evaluate(
        self, description: str, service_name: str
    ) -> Optional[float]:
        """
        Self-evaluate a generated description using Gemini.
        Returns average score (0-10) or None on failure.
        """
        eval_prompt = SELF_EVALUATION_PROMPT.format(
            name_es=service_name,
            description=description,
        )
        text = await self._call_gemini(eval_prompt, max_tokens=150, json_mode=True, temperature=0.1)
        if not text:
            logger.warning("Self-evaluation: empty response — skipping evaluation")
            return None

        try:
            data = json.loads(text)
            avg = data.get("average")
            if avg is not None:
                return float(avg)
            # Compute average from individual scores
            scores = [
                data.get("format", 0), data.get("precision", 0),
                data.get("professionalism", 0), data.get("restrictions", 0),
            ]
            valid = [s for s in scores if isinstance(s, (int, float)) and s > 0]
            return round(sum(valid) / len(valid), 1) if valid else None
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f"Self-evaluation parse error: {e} — raw: {text[:200]}")
            return None

    async def _translate(
        self, conn, task_id: UUID, context: Dict[str, Any], target_lang: str
    ) -> int:
        """Translate name + description to target language via Gemini Flash."""
        lang_names = {"fr": "francés", "en": "inglés"}
        prompt = TRANSLATION_PROMPT.format(
            target_language=lang_names.get(target_lang, target_lang),
            name_es=context.get("name_es", ""),
            description_es=context.get("description_es", ""),
        )

        text = await self._call_gemini(
            prompt, max_tokens=400, json_mode=True
        )
        if not text:
            await EnrichmentRepository.mark_failed(conn, task_id, "Empty Gemini response")
            return 0

        try:
            data = json.loads(text)
            translated_name = _sanitize_llm_text(data.get("name", ""), _MAX_NAME_LEN)
            translated_desc = _sanitize_llm_text(data.get("description", ""), _MAX_DESCRIPTION_LEN)
        except (json.JSONDecodeError, TypeError) as e:
            await EnrichmentRepository.mark_failed(
                conn, task_id, f"JSON parse error: {e} — raw: {text[:200]}"
            )
            return 0

        if not translated_name:
            await EnrichmentRepository.mark_failed(
                conn, task_id, "Empty translated name"
            )
            return 0

        service_code = context["service_code"]
        for field_name, translation_text in [
            ("name", translated_name),
            ("description", translated_desc),
        ]:
            if not translation_text:
                continue
            await conn.execute(
                """
                INSERT INTO entity_translations (
                    entity_type, entity_code, language_code, field_name,
                    translation_text, translation_source, translation_quality,
                    created_at, updated_at
                )
                VALUES ('service'::translatable_entity_type, $1, $2, $3, $4, 'ai_generated', 0.8, NOW(), NOW())
                ON CONFLICT (entity_type, entity_code, language_code, field_name)
                DO UPDATE SET
                    translation_text = EXCLUDED.translation_text,
                    translation_source = EXCLUDED.translation_source,
                    translation_quality = EXCLUDED.translation_quality,
                    updated_at = NOW()
                WHERE entity_translations.translation_source != 'manual'
                """,
                service_code,
                target_lang,
                field_name,
                translation_text,
            )

        tokens = len(prompt.split()) + len(text.split())
        await EnrichmentRepository.mark_completed(
            conn, task_id,
            output_data={"name": translated_name, "description": translated_desc},
            tokens_used=tokens,
        )
        return tokens

    async def _generate_keywords(
        self, conn, task_id: UUID, context: Dict[str, Any]
    ) -> int:
        """Generate multilingual keywords via Gemini Flash."""
        prompt = KEYWORDS_PROMPT.format(
            name_es=context.get("name_es", ""),
            description_es=context.get("description_es", ""),
            category=context.get("category_name", ""),
        )

        text = await self._call_gemini(prompt, max_tokens=400, json_mode=True)
        if not text:
            await EnrichmentRepository.mark_failed(conn, task_id, "Empty Gemini response")
            return 0

        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError) as e:
            await EnrichmentRepository.mark_failed(
                conn, task_id, f"JSON parse error: {e} — raw: {text[:200]}"
            )
            return 0

        service_id = context["id"]
        inserted = 0

        for lang_code, keywords in data.items():
            if lang_code not in ("es", "fr", "en") or not isinstance(keywords, list):
                continue
            for kw in keywords[:8]:
                if not isinstance(kw, str) or len(kw) < 2:
                    continue
                clean_kw = _sanitize_llm_text(kw, _MAX_KEYWORD_LEN).lower().strip()
                if len(clean_kw) < 2:
                    continue
                await conn.execute(
                    """
                    INSERT INTO service_keywords (
                        fiscal_service_id, keyword, language_code,
                        weight, is_auto_generated, created_at
                    )
                    VALUES ($1, $2, $3, 3, true, NOW())
                    ON CONFLICT (fiscal_service_id, keyword, language_code) DO NOTHING
                    """,
                    service_id,
                    clean_kw,
                    lang_code,
                )
                inserted += 1

        tokens = len(prompt.split()) + len(text.split())
        await EnrichmentRepository.mark_completed(
            conn, task_id,
            output_data={"keywords": data, "inserted": inserted},
            tokens_used=tokens,
        )
        return tokens

    # ------------------------------------------------------------------
    # Ministry description generation
    # ------------------------------------------------------------------

    async def _generate_ministry_description(
        self, conn, task_id: UUID, ministry_id: int
    ) -> int:
        """Generate draft description for a ministry via Gemini Flash."""
        context = await EnrichmentRepository.get_ministry_context(conn, ministry_id)
        if not context:
            await EnrichmentRepository.mark_failed(
                conn, task_id, f"Ministry {ministry_id} not found"
            )
            return 0

        prompt = MINISTRY_DESCRIPTION_PROMPT.format(
            name_es=context.get("name_es", ""),
            ministry_code=context.get("ministry_code", ""),
            sectors=context.get("sector_names", "Sin sectores"),
            service_count=context.get("service_count", 0),
        )

        text = await self._call_gemini(prompt, max_tokens=300)
        if not text:
            await EnrichmentRepository.mark_failed(conn, task_id, "Empty Gemini response")
            return 0

        description = _sanitize_llm_text(text.strip('"').strip("'"), _MAX_DESCRIPTION_LEN)
        if len(description) < 10:
            await EnrichmentRepository.mark_failed(
                conn, task_id, f"Description too short: {description}"
            )
            return 0

        await conn.execute(
            """
            UPDATE ministries
            SET description_es = $1, description_source = 'ai_draft', updated_at = NOW()
            WHERE id = $2
              AND (description_source IS NULL OR description_source = 'ai_draft')
            """,
            description,
            ministry_id,
        )

        tokens = len(prompt.split()) + len(description.split())
        await EnrichmentRepository.mark_completed(
            conn, task_id,
            output_data={"description": description, "entity": "ministry"},
            tokens_used=tokens,
        )
        return tokens

    # ------------------------------------------------------------------
    # Gemini call wrapper
    # ------------------------------------------------------------------

    async def _call_gemini(
        self,
        prompt: str,
        max_tokens: int = 300,
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> Optional[str]:
        """
        Call Gemini Flash with timeout and error handling.
        Uses run_in_executor (Vertex AI SDK is synchronous).
        """
        if not self._model:
            return None

        gen_config_kwargs: Dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if json_mode:
            gen_config_kwargs["response_mime_type"] = "application/json"

        config = GenerationConfig(**gen_config_kwargs)

        try:
            response = await asyncio.wait_for(
                traced_generate_sync(
                    self._model, [prompt],
                    feature="enrichment",
                    generation_config=config,
                ),
                timeout=15.0,
            )

            # Track token usage via centralized manager
            VertexAIManager().track_usage(response, "EnrichmentService")
            VertexAIManager().track_success()

            if not response.candidates:
                feedback = getattr(response, "prompt_feedback", None)
                logger.warning(
                    f"Enrichment Gemini: empty candidates — "
                    f"prompt_feedback={feedback}"
                )
                return None

            text = response.text
            if not text:
                logger.warning("Enrichment Gemini: empty response text")
                return None

            return text.strip()

        except asyncio.TimeoutError:
            VertexAIManager().track_failure()
            logger.error("Enrichment Gemini: timeout (15s)")
            return None
        except Exception as e:
            VertexAIManager().track_failure()
            logger.error(f"Enrichment Gemini error: {e}")
            return None


# Singleton instance
_enrichment_service: Optional[EnrichmentService] = None


def get_enrichment_service() -> EnrichmentService:
    """Get or create the singleton EnrichmentService."""
    global _enrichment_service
    if _enrichment_service is None:
        _enrichment_service = EnrichmentService()
    return _enrichment_service
