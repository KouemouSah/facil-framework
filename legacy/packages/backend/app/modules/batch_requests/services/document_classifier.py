"""
Batch Document Classifier — Gemini Flash classification + beneficiary matching.

Three sub-phases:
1. CLASSIFY: Lightweight Gemini call per document (type + identity, ~700 tokens/doc)
2. MATCH: Assign classified documents to beneficiaries (exact ID + fuzzy name)
3. EXTRACT: Full extraction via existing GeminiDocumentProcessor (reuses 39 schemas)

Key design:
- Firebase Early Upload: docs already on Firebase, we download content for Gemini
- Semaphore(10) for classification, Semaphore(5) for extraction (heavier)
- All results stored in Redis session (metadata only, no base64)
- Reuses the Gemini model from gemini_document_processor (no duplicate init)
"""
import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from uuid import UUID

from loguru import logger

# Vertex AI imports — guarded like the existing gemini_document_processor
try:
    from vertexai.generative_models import (
        GenerationConfig,
        HarmCategory,
        HarmBlockThreshold,
        Part,
    )
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    logger.warning("[BatchClassifier] Vertex AI SDK not installed - classification disabled")

from app.modules.service_requests.services.gemini_document_processor import (
    normalize_name,
    levenshtein_distance,
    LEVENSHTEIN_THRESHOLD,
)
from app.modules.service_requests.services.schema_loader import schema_loader
from app.modules.service_requests.services.workflow_engine import workflow_engine
from app.core.ai_telemetry import traced_generate_sync
from app.modules.service_requests.models.enums import SolicitudType

from .batch_session_service import batch_session_service, BatchSessionError


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ClassificationResult:
    """Result of lightweight Gemini classification for a single document."""
    file_path: str
    file_name: str
    mime_type: str
    document_type: Optional[str] = None
    confidence: float = 0.0
    person_name: Optional[str] = None
    identifier: Optional[str] = None
    identifier_type: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "mime_type": self.mime_type,
            "document_type": self.document_type,
            "confidence": self.confidence,
            "person_name": self.person_name,
            "identifier": self.identifier,
            "identifier_type": self.identifier_type,
            "error": self.error,
        }


@dataclass
class MatchResult:
    """Result of matching a classified document to a beneficiary."""
    file_path: str
    document_type: Optional[str] = None
    beneficiary_id: Optional[str] = None
    beneficiary_name: Optional[str] = None
    match_method: Optional[str] = None  # "id_exact", "name_fuzzy", "unassigned"
    match_score: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "document_type": self.document_type,
            "beneficiary_id": self.beneficiary_id,
            "beneficiary_name": self.beneficiary_name,
            "match_method": self.match_method,
            "match_score": self.match_score,
            "confidence": self.confidence,
        }


@dataclass
class ExtractionResult:
    """Result of full extraction for a single document."""
    file_path: str
    beneficiary_id: str
    document_code: str
    extraction_data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    status: str = "success"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "beneficiary_id": self.beneficiary_id,
            "document_code": self.document_code,
            "extraction_data": self.extraction_data,
            "confidence": self.confidence,
            "status": self.status,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

# Concurrency limits
CLASSIFY_CONCURRENCY = 10   # Lightweight classification (~700 tokens)
EXTRACT_CONCURRENCY = 5     # Full extraction (~7s/doc)


class BatchDocumentClassifier:
    """
    Classifies and matches documents in a batch session.

    IMPORTANT: Does NOT create its own Gemini model.
    Reuses gemini_document_processor.model (lazy-accessed) to avoid
    duplicate vertexai.init() and duplicate GenerativeModel instances.
    Only the GenerationConfig differs (lighter: 1024 tokens vs 8192).
    """

    def __init__(self):
        self.enabled = False
        self._classify_config = None
        self._safety_settings = None

        if not VERTEX_AI_AVAILABLE:
            logger.warning("[BatchClassifier] Vertex AI SDK not available - disabled")
            return

        try:
            # Lighter config for classification (~700 tokens output)
            self._classify_config = GenerationConfig(
                temperature=0.1,
                top_p=0.8,
                top_k=20,
                max_output_tokens=1024,
            )
            self._safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            }
            self.enabled = True
            logger.info("[BatchClassifier] Ready (will reuse gemini_document_processor model)")
        except Exception as e:
            logger.warning(f"[BatchClassifier] Failed to init: {e}")

    def _get_model(self):
        """Get the Gemini model from the existing processor singleton (lazy)."""
        from app.modules.service_requests.services.gemini_document_processor import (
            gemini_document_processor,
        )
        if not gemini_document_processor.enabled or not gemini_document_processor.model:
            raise BatchSessionError(
                "Servicio Gemini no disponible para clasificación.",
                "GEMINI_UNAVAILABLE",
            )
        return gemini_document_processor.model

    # =========================================================================
    # SUB-PHASE 1: LIGHTWEIGHT CLASSIFICATION
    # =========================================================================

    def _get_known_document_types(self, workflow_code: str) -> List[str]:
        """
        Get the list of known document types for a workflow.
        Uses the workflow's get_document_requirements() for all solicitud types.
        """
        workflow = workflow_engine.get_workflow_by_string(workflow_code)
        if not workflow:
            # Fallback: return all schema keys
            return schema_loader.get_schema_keys()

        doc_codes = set()
        for sol_type in SolicitudType:
            try:
                reqs = workflow.get_document_requirements(sol_type)
                for req in reqs:
                    doc_codes.add(req.document_code)
            except Exception:
                pass

        return sorted(doc_codes) if doc_codes else schema_loader.get_schema_keys()

    def _build_classify_prompt(self, known_types: List[str]) -> str:
        """Build a lightweight classification prompt."""
        types_str = ", ".join(known_types)
        return f"""TASK: Identify the document type and the person it belongs to from this scanned document.

KNOWN DOCUMENT TYPES: [{types_str}]

INSTRUCTIONS:
- Identify which document type this is from the KNOWN TYPES list.
- If it doesn't match any known type, use "unknown".
- Extract the person's full name as written on the document.
- Extract the main identifying number (passport number, DIP number, etc.).
- Identify the type of identifier (passport, dip, nie, nif, etc.).

RESPOND ONLY IN THIS JSON FORMAT (no markdown, no explanation):
{{
  "document_type": "string",
  "confidence": 0.0,
  "person_name": "FULL NAME as on document or null",
  "identifier": "main ID number or null",
  "identifier_type": "passport|dip|nie|nif|other or null"
}}"""

    async def _classify_single(
        self,
        content: bytes,
        mime_type: str,
        file_path: str,
        file_name: str,
        known_types: List[str],
        semaphore: asyncio.Semaphore,
    ) -> ClassificationResult:
        """Classify a single document via Gemini Flash."""
        async with semaphore:
            try:
                prompt = self._build_classify_prompt(known_types)
                document_part = Part.from_data(data=content, mime_type=mime_type)
                contents = [document_part, Part.from_text(prompt)]

                model = self._get_model()
                response = await traced_generate_sync(
                    model, contents,
                    feature="classification_batch",
                    generation_config=self._classify_config,
                    safety_settings=self._safety_settings,
                )

                # Parse JSON response
                text = response.text.strip()
                json_match = re.search(r"\{[\s\S]*\}", text)
                if not json_match:
                    return ClassificationResult(
                        file_path=file_path,
                        file_name=file_name,
                        mime_type=mime_type,
                        error="No se pudo parsear la respuesta de clasificación",
                    )

                data = json.loads(json_match.group())
                doc_type = data.get("document_type")
                confidence = float(data.get("confidence", 0))

                # Validate document_type against known types
                if doc_type and doc_type not in known_types:
                    logger.warning(
                        f"[BatchClassifier] Unknown type '{doc_type}' for {file_name} "
                        f"(known: {len(known_types)}). Capping confidence."
                    )
                    # Don't reject — keep the type but cap confidence to flag it
                    confidence = min(confidence, 0.5)

                return ClassificationResult(
                    file_path=file_path,
                    file_name=file_name,
                    mime_type=mime_type,
                    document_type=doc_type,
                    confidence=confidence,
                    person_name=data.get("person_name"),
                    identifier=data.get("identifier"),
                    identifier_type=data.get("identifier_type"),
                )

            except Exception as e:
                logger.error(f"[BatchClassifier] Error classifying {file_name}: {e}")
                return ClassificationResult(
                    file_path=file_path,
                    file_name=file_name,
                    mime_type=mime_type,
                    error=str(e),
                )

    async def classify_documents(
        self,
        documents: List[Dict[str, Any]],
        workflow_code: str,
    ) -> List[ClassificationResult]:
        """
        Classify multiple documents in parallel.

        Args:
            documents: List of {"content": bytes, "mime_type": str, "file_path": str, "file_name": str}
            workflow_code: Workflow code to determine known document types

        Returns:
            List of ClassificationResult
        """
        if not self.enabled:
            raise BatchSessionError(
                "Servicio de clasificación no disponible.",
                "CLASSIFIER_UNAVAILABLE",
            )

        known_types = self._get_known_document_types(workflow_code)
        semaphore = asyncio.Semaphore(CLASSIFY_CONCURRENCY)

        tasks = [
            self._classify_single(
                content=doc["content"],
                mime_type=doc["mime_type"],
                file_path=doc["file_path"],
                file_name=doc["file_name"],
                known_types=known_types,
                semaphore=semaphore,
            )
            for doc in documents
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        final: List[ClassificationResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final.append(ClassificationResult(
                    file_path=documents[i]["file_path"],
                    file_name=documents[i]["file_name"],
                    mime_type=documents[i]["mime_type"],
                    error=str(result),
                ))
            else:
                final.append(result)

        logger.info(
            f"[BatchClassifier] Classified {len(final)} documents "
            f"(errors: {sum(1 for r in final if r.error)})"
        )
        return final

    # =========================================================================
    # SUB-PHASE 2: BENEFICIARY MATCHING
    # =========================================================================

    def _name_similarity(self, name1: Optional[str], name2: Optional[str]) -> float:
        """Calculate name similarity score between 0 and 1."""
        if not name1 or not name2:
            return 0.0

        n1 = normalize_name(name1)
        n2 = normalize_name(name2)

        if not n1 or not n2:
            return 0.0

        # Exact match
        if n1 == n2:
            return 1.0

        # Containment (Gemini may add extra data)
        if n1 in n2 or n2 in n1:
            shorter = min(len(n1), len(n2))
            longer = max(len(n1), len(n2))
            return shorter / longer if longer > 0 else 0.0

        # Word subset
        words1 = set(n1.split())
        words2 = set(n2.split())
        shorter_words = words1 if len(words1) <= len(words2) else words2
        longer_words = words2 if len(words1) <= len(words2) else words1
        if shorter_words and shorter_words.issubset(longer_words):
            return len(shorter_words) / len(longer_words)

        # Levenshtein
        dist = levenshtein_distance(n1, n2)
        max_len = max(len(n1), len(n2))
        return 1.0 - (dist / max_len) if max_len > 0 else 0.0

    def match_to_beneficiaries(
        self,
        classifications: List[ClassificationResult],
        beneficiaries: List[Dict[str, Any]],
    ) -> List[MatchResult]:
        """
        Match classified documents to beneficiaries.

        Strategy:
        1. Exact identifier match (score=1.0)
        2. Fuzzy name match (Levenshtein >= 0.85)
        3. Unassigned (manual review)
        """
        # Build index by identifier (upper-cased)
        id_index: Dict[str, Dict[str, Any]] = {}
        for ben in beneficiaries:
            identifier = ben.get("identifier")
            if identifier:
                id_index[identifier.strip().upper()] = ben

        results: List[MatchResult] = []

        for cls in classifications:
            if cls.error:
                results.append(MatchResult(
                    file_path=cls.file_path,
                    document_type=cls.document_type,
                    match_method="error",
                    confidence=cls.confidence,
                ))
                continue

            # Strategy 1: Exact identifier match
            if cls.identifier:
                norm_id = cls.identifier.strip().upper()
                if norm_id in id_index:
                    ben = id_index[norm_id]
                    results.append(MatchResult(
                        file_path=cls.file_path,
                        document_type=cls.document_type,
                        beneficiary_id=ben["id"],
                        beneficiary_name=ben.get("name"),
                        match_method="id_exact",
                        match_score=1.0,
                        confidence=cls.confidence,
                    ))
                    continue

            # Strategy 2: Fuzzy name match
            if cls.person_name:
                best_ben = None
                best_score = 0.0
                for ben in beneficiaries:
                    score = self._name_similarity(cls.person_name, ben.get("name"))
                    if score > best_score:
                        best_score = score
                        best_ben = ben

                if best_ben and best_score >= LEVENSHTEIN_THRESHOLD:
                    results.append(MatchResult(
                        file_path=cls.file_path,
                        document_type=cls.document_type,
                        beneficiary_id=best_ben["id"],
                        beneficiary_name=best_ben.get("name"),
                        match_method="name_fuzzy",
                        match_score=round(best_score, 3),
                        confidence=cls.confidence,
                    ))
                    continue

            # Strategy 3: Unassigned
            results.append(MatchResult(
                file_path=cls.file_path,
                document_type=cls.document_type,
                match_method="unassigned",
                match_score=0.0,
                confidence=cls.confidence,
            ))

        # Log stats
        assigned = sum(1 for r in results if r.beneficiary_id)
        unassigned = sum(1 for r in results if r.match_method == "unassigned")
        errors = sum(1 for r in results if r.match_method == "error")
        logger.info(
            f"[BatchClassifier] Matching: {assigned} assigned, "
            f"{unassigned} unassigned, {errors} errors"
        )
        return results

    # =========================================================================
    # SUB-PHASE 3: FULL EXTRACTION
    # =========================================================================

    async def extract_documents(
        self,
        session_id: str,
        user_id: UUID,
    ) -> Dict[str, Any]:
        """
        Run full extraction on all assigned documents in the session.
        Uses existing GeminiDocumentProcessor.process() for each document.

        Returns:
            {"extracted": int, "errors": int, "results": [...]}
        """
        # Lazy import to avoid circular dependency
        from app.modules.service_requests.services.gemini_document_processor import (
            gemini_document_processor,
        )
        from app.modules.documents.services.storage_service import (
            firebase_storage_service,
        )

        session = await batch_session_service.get_session(session_id, user_id)
        item_documents = session.get("item_documents", {})

        if not item_documents:
            return {"extracted": 0, "errors": 0, "results": []}

        semaphore = asyncio.Semaphore(EXTRACT_CONCURRENCY)
        all_results: List[ExtractionResult] = []

        async def _extract_one(
            beneficiary_id: str,
            doc: Dict[str, Any],
        ) -> ExtractionResult:
            async with semaphore:
                try:
                    # Download from Firebase
                    download = await firebase_storage_service.download_file(
                        file_path=doc["file_path"],
                        user_id=str(user_id),
                    )

                    document_code = doc["document_code"]

                    # Full extraction via existing processor
                    result = await gemini_document_processor.process(
                        content=download.content,
                        mime_type=download.mime_type,
                        document_code=document_code,
                        request_id=f"batch_{session_id}",
                        user_id=str(user_id),
                        workflow_code=session.get("workflow_code"),
                    )

                    return ExtractionResult(
                        file_path=doc["file_path"],
                        beneficiary_id=beneficiary_id,
                        document_code=document_code,
                        extraction_data=result.get("extraction", {}),
                        confidence=result.get("confidence", 0),
                        status=result.get("status", "success"),
                        error=result.get("error_message"),
                    )

                except Exception as e:
                    logger.error(
                        f"[BatchClassifier] Extraction error "
                        f"(ben={beneficiary_id}, doc={doc.get('document_code')}): {e}"
                    )
                    return ExtractionResult(
                        file_path=doc["file_path"],
                        beneficiary_id=beneficiary_id,
                        document_code=doc.get("document_code", "unknown"),
                        error=str(e),
                        status="error",
                    )

        # Build extraction tasks
        tasks = []
        for ben_id, docs in item_documents.items():
            for doc in docs:
                tasks.append(_extract_one(ben_id, doc))

        if not tasks:
            return {"extracted": 0, "errors": 0, "results": []}

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                all_results.append(ExtractionResult(
                    file_path="unknown",
                    beneficiary_id="unknown",
                    document_code="unknown",
                    error=str(result),
                    status="error",
                ))
            else:
                all_results.append(result)

        # Update session with extraction data
        for ext_result in all_results:
            if ext_result.status != "error" and ext_result.beneficiary_id != "unknown":
                try:
                    await batch_session_service.add_item_document(
                        session_id=session_id,
                        user_id=user_id,
                        beneficiary_id=ext_result.beneficiary_id,
                        document_code=ext_result.document_code,
                        file_path=ext_result.file_path,
                        file_name=ext_result.file_path.split("/")[-1],
                        extraction_data=ext_result.extraction_data,
                        confidence=ext_result.confidence,
                    )
                except Exception as e:
                    logger.error(
                        f"[BatchClassifier] Failed to update session doc: {e}"
                    )

        extracted = sum(1 for r in all_results if r.status != "error")
        errors = sum(1 for r in all_results if r.status == "error")

        logger.info(
            f"[BatchClassifier] Extraction complete for session {session_id}: "
            f"{extracted} extracted, {errors} errors"
        )

        return {
            "extracted": extracted,
            "errors": errors,
            "results": [r.to_dict() for r in all_results],
        }

    # =========================================================================
    # ORCHESTRATION: Classify + Match pipeline
    # =========================================================================

    async def classify_and_match(
        self,
        session_id: str,
        user_id: UUID,
        uploaded_docs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Full classify + match pipeline.

        Args:
            session_id: Batch session ID
            user_id: User ID
            uploaded_docs: List of {"content": bytes, "mime_type": str, "file_path": str, "file_name": str}

        Returns:
            {
                "classifications": [...],
                "assignments": [...],
                "stats": {"total": N, "assigned": N, "unassigned": N, "errors": N}
            }
        """
        session = await batch_session_service.get_session(session_id, user_id)
        workflow_code = session["workflow_code"]
        beneficiaries = session.get("beneficiaries", [])

        if not beneficiaries:
            raise BatchSessionError(
                "Agregue beneficiarios antes de clasificar documentos.",
                "NO_BENEFICIARIES",
            )

        # Sub-phase 1: Classify
        classifications = await self.classify_documents(uploaded_docs, workflow_code)

        # Sub-phase 2: Match
        assignments = self.match_to_beneficiaries(classifications, beneficiaries)

        # Store assignments in session for user review
        await batch_session_service.update_session_fields(
            session_id, user_id, {
                "classifications": [c.to_dict() for c in classifications],
                "assignments": [a.to_dict() for a in assignments],
                "status": "CLASSIFYING",
            }
        )

        # Stats
        assigned = sum(1 for a in assignments if a.beneficiary_id)
        unassigned = sum(1 for a in assignments if a.match_method == "unassigned")
        errors = sum(1 for a in assignments if a.match_method == "error")

        return {
            "classifications": [c.to_dict() for c in classifications],
            "assignments": [a.to_dict() for a in assignments],
            "stats": {
                "total": len(classifications),
                "assigned": assigned,
                "unassigned": unassigned,
                "errors": errors,
            },
        }

    async def confirm_assignments(
        self,
        session_id: str,
        user_id: UUID,
        assignments: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Confirm (or modify) document-to-beneficiary assignments.
        User can reassign unmatched documents or correct wrong assignments.

        Args:
            assignments: List of {"file_path": str, "document_type": str, "beneficiary_id": str}

        Returns:
            Updated session item_documents summary
        """
        session = await batch_session_service.get_session(session_id, user_id)

        # Validate beneficiary IDs exist
        ben_ids = {b["id"] for b in session.get("beneficiaries", [])}

        # Clear previous assignments
        session["item_documents"] = {}

        assigned_count = 0
        skipped_count = 0

        for assignment in assignments:
            ben_id = assignment.get("beneficiary_id")
            doc_type = assignment.get("document_type")
            file_path = assignment.get("file_path")

            if not ben_id or ben_id not in ben_ids:
                skipped_count += 1
                continue

            if ben_id not in session["item_documents"]:
                session["item_documents"][ben_id] = []

            session["item_documents"][ben_id].append({
                "document_code": doc_type,
                "file_path": file_path,
                "file_name": file_path.split("/")[-1] if file_path else "document",
                "extraction_data": {},
                "confidence": None,
                "match_method": "user_confirmed",
                "match_score": 1.0,
            })
            assigned_count += 1

        await batch_session_service.update_session_fields(
            session_id, user_id, {
                "item_documents": session["item_documents"],
                "status": "REVIEW",
            }
        )

        logger.info(
            f"[BatchClassifier] Assignments confirmed for {session_id}: "
            f"{assigned_count} assigned, {skipped_count} skipped"
        )

        return {
            "assigned": assigned_count,
            "skipped": skipped_count,
            "beneficiaries_with_docs": len(session["item_documents"]),
        }


# Singleton
batch_document_classifier = BatchDocumentClassifier()
