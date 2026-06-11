"""
Batch Session Service — Redis metadata session for batch requests.

Key differences from individual WizardSessionService:
- TTL = 2 hours (batch takes longer than individual requests)
- NO base64 documents in Redis (Firebase early upload instead)
- Stores only metadata: beneficiary list, doc references, form_data_grid
- Supports CSV import for beneficiaries
"""
import csv
import hashlib
import io
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from uuid import UUID, uuid4

from loguru import logger

from app.modules.service_requests.services.preview_cache import preview_cache
from app.modules.batch_requests.repositories.batch_repository import MAX_BENEFICIARIES_PER_BATCH

BATCH_SESSION_TTL = 7200  # 2 hours
BATCH_SESSION_PREFIX = "batch_session_"


class BatchSessionError(Exception):
    """Base error for batch session operations."""
    def __init__(self, message: str, code: str = "BATCH_SESSION_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class BatchSessionNotFoundError(BatchSessionError):
    """Session not in cache."""
    def __init__(self):
        super().__init__(
            "Sesión de lote no encontrada o expirada. Por favor, inicie una nueva.",
            "SESSION_NOT_FOUND"
        )


class BatchSessionService:
    """
    Manages batch sessions in Redis cache.

    Session lifecycle:
    1. start_session() → create session with workflow info
    2. add/import beneficiaries → update beneficiaries list
    3. upload shared docs → Firebase early upload, store refs in session
    4. classify individual docs → Phase 3 (document_classifier)
    5. review form data → update form_data_grid
    6. submit → atomic persist (Phase 4)
    """

    def __init__(self):
        self.session_ttl = BATCH_SESSION_TTL
        self.cache = preview_cache

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    def _generate_session_id(self, user_id: UUID, workflow_code: str) -> str:
        """Generate unique session ID."""
        unique = f"{user_id}_batch_{workflow_code}_{uuid4().hex[:8]}_{datetime.now(timezone.utc).timestamp()}"
        return f"{BATCH_SESSION_PREFIX}{hashlib.sha256(unique.encode()).hexdigest()[:16]}"

    def _get_cache_key(self, session_id: str) -> str:
        """Get cache key for session."""
        if session_id.startswith(BATCH_SESSION_PREFIX):
            return session_id
        return f"{BATCH_SESSION_PREFIX}{session_id}"

    async def _get_session(self, session_id: str, user_id: UUID) -> Dict[str, Any]:
        """Get session from cache with ownership validation."""
        cache_key = self._get_cache_key(session_id)

        try:
            data = await self.cache.get(cache_key)
        except Exception as e:
            logger.error(f"[BatchSession] Cache error getting {session_id}: {e}")
            raise BatchSessionError("Error al acceder a la sesión de lote.")

        if not data:
            raise BatchSessionNotFoundError()

        if data.get("user_id") != str(user_id):
            raise BatchSessionError("No autorizado para esta sesión.", "UNAUTHORIZED")

        # Check expiration (belt and suspenders)
        expires_at = data.get("expires_at")
        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > exp_dt:
                    await self.cache.delete(cache_key)
                    raise BatchSessionNotFoundError()
            except (ValueError, TypeError):
                pass

        return data

    async def _save_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Save session to cache with TTL renewal."""
        cache_key = self._get_cache_key(session_id)
        now = datetime.now(timezone.utc)
        data["updated_at"] = now.isoformat()
        data["expires_at"] = (now + timedelta(seconds=self.session_ttl)).isoformat()

        try:
            success = await self.cache.set(cache_key, data, self.session_ttl)
            if not success:
                logger.error(f"[BatchSession] Failed to save session {session_id}")
            return success
        except Exception as e:
            logger.error(f"[BatchSession] Cache error saving {session_id}: {e}")
            return False

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    async def start_session(
        self,
        user_id: UUID,
        workflow_code: str,
        solicitud_type: str = "expedicion",
        company_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Create a new batch session in Redis."""
        session_id = self._generate_session_id(user_id, workflow_code)
        now = datetime.now(timezone.utc)

        session_data = {
            "session_id": session_id,
            "user_id": str(user_id),
            "workflow_code": workflow_code,
            "solicitud_type": solicitud_type,
            "company_id": str(company_id) if company_id else None,
            "status": "DRAFT",
            "beneficiaries": [],
            "shared_documents": [],
            "item_documents": {},
            "form_data_grid": {},
            "tariff": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=self.session_ttl)).isoformat(),
        }

        saved = await self._save_session(session_id, session_data)
        if not saved:
            raise BatchSessionError("No se pudo crear la sesión de lote.")

        logger.info(
            f"[BatchSession] Session created: {session_id} "
            f"(user={user_id}, workflow={workflow_code})"
        )
        return session_data

    async def get_session(self, session_id: str, user_id: UUID) -> Dict[str, Any]:
        """Get current session state."""
        return await self._get_session(session_id, user_id)

    async def delete_session(self, session_id: str, user_id: UUID) -> bool:
        """Delete/cancel a session."""
        await self._get_session(session_id, user_id)  # validate ownership
        cache_key = self._get_cache_key(session_id)
        deleted = await self.cache.delete(cache_key)
        if deleted:
            logger.info(f"[BatchSession] Session deleted: {session_id}")
        return deleted

    # =========================================================================
    # BENEFICIARIES
    # =========================================================================

    async def add_beneficiary(
        self,
        session_id: str,
        user_id: UUID,
        name: str,
        identifier: Optional[str] = None,
        identifier_type: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        conditions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add a single beneficiary to the session."""
        session = await self._get_session(session_id, user_id)

        if len(session["beneficiaries"]) >= MAX_BENEFICIARIES_PER_BATCH:
            raise BatchSessionError(
                f"Límite de {MAX_BENEFICIARIES_PER_BATCH} beneficiarios por lote alcanzado.",
                "MAX_BENEFICIARIES_EXCEEDED"
            )

        beneficiary_id = uuid4().hex[:12]
        beneficiary = {
            "id": beneficiary_id,
            "name": name,
            "identifier": identifier,
            "identifier_type": identifier_type,
            "email": email,
            "phone": phone,
            "conditions": conditions or {},
            "status": "PENDING",
        }

        session["beneficiaries"].append(beneficiary)
        await self._save_session(session_id, session)
        return beneficiary

    async def update_beneficiary(
        self,
        session_id: str,
        user_id: UUID,
        beneficiary_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update a beneficiary in the session."""
        session = await self._get_session(session_id, user_id)

        allowed_fields = {"name", "identifier", "identifier_type", "email", "phone", "conditions"}
        found = False
        updated_ben = None
        for ben in session["beneficiaries"]:
            if ben["id"] == beneficiary_id:
                for key, val in updates.items():
                    if key in allowed_fields:
                        ben[key] = val
                found = True
                updated_ben = ben
                break

        if not found:
            raise BatchSessionError("Beneficiario no encontrado en la sesión.", "BENEFICIARY_NOT_FOUND")

        await self._save_session(session_id, session)
        return updated_ben

    async def remove_beneficiary(
        self,
        session_id: str,
        user_id: UUID,
        beneficiary_id: str,
    ) -> bool:
        """Remove a beneficiary from the session."""
        session = await self._get_session(session_id, user_id)

        original_len = len(session["beneficiaries"])
        session["beneficiaries"] = [
            b for b in session["beneficiaries"] if b["id"] != beneficiary_id
        ]

        if len(session["beneficiaries"]) == original_len:
            raise BatchSessionError("Beneficiario no encontrado.", "BENEFICIARY_NOT_FOUND")

        # Also clean up associated documents
        if beneficiary_id in session.get("item_documents", {}):
            del session["item_documents"][beneficiary_id]
        if beneficiary_id in session.get("form_data_grid", {}):
            del session["form_data_grid"][beneficiary_id]

        await self._save_session(session_id, session)
        return True

    async def reorder_beneficiary(
        self,
        session_id: str,
        user_id: UUID,
        beneficiary_id: str,
        direction: str,
    ) -> List[Dict[str, Any]]:
        """Move a beneficiary up or down in the list (F-022)."""
        session = await self._get_session(session_id, user_id)
        bens = session["beneficiaries"]

        idx = next((i for i, b in enumerate(bens) if b["id"] == beneficiary_id), -1)
        if idx == -1:
            raise BatchSessionError("Beneficiario no encontrado.", "BENEFICIARY_NOT_FOUND")

        if direction == "up" and idx > 0:
            bens[idx], bens[idx - 1] = bens[idx - 1], bens[idx]
        elif direction == "down" and idx < len(bens) - 1:
            bens[idx], bens[idx + 1] = bens[idx + 1], bens[idx]

        session["beneficiaries"] = bens
        await self._save_session(session_id, session)
        return bens

    async def import_beneficiaries_csv(
        self,
        session_id: str,
        user_id: UUID,
        csv_content: bytes,
    ) -> Dict[str, Any]:
        """
        Import beneficiaries from CSV file.

        Expected columns (flexible names):
        - name/nombre/beneficiary_name (required)
        - identifier/numero/passport/dip (optional)
        - identifier_type/tipo (optional)
        - email/correo (optional)
        - phone/telefono (optional)

        Returns: {added: int, skipped: int, errors: []}
        """
        session = await self._get_session(session_id, user_id)

        # Parse CSV with encoding detection
        text = None
        for encoding in ["utf-8", "utf-8-sig", "latin-1"]:
            try:
                text = csv_content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if text is None:
            raise BatchSessionError(
                "No se pudo leer el archivo CSV. Verifique la codificación.",
                "CSV_ENCODING_ERROR"
            )

        reader = csv.DictReader(io.StringIO(text))

        # Check current beneficiaries count
        current_count = len(session["beneficiaries"])
        remaining_capacity = MAX_BENEFICIARIES_PER_BATCH - current_count

        # Flexible column name mapping
        name_cols = ["name", "nombre", "beneficiary_name", "nombres", "full_name", "nom"]
        id_cols = ["identifier", "numero", "passport", "dip", "nie", "numero_documento", "id_number"]
        id_type_cols = ["identifier_type", "tipo", "tipo_documento", "document_type"]
        email_cols = ["email", "correo", "e-mail", "mail"]
        phone_cols = ["phone", "telefono", "tel", "mobile", "movil"]

        def _find_value(row: Dict, candidates: List[str]) -> Optional[str]:
            for col in candidates:
                # Check exact match and case-insensitive
                for key in row:
                    if key.strip().lower() == col.lower() and row[key] and row[key].strip():
                        return row[key].strip()
            return None

        added = 0
        skipped = 0
        errors = []
        max_reported_errors = 50  # Cap error list to prevent bloated responses

        for row_idx, row in enumerate(reader, start=2):  # start=2 because row 1 is header
            if added >= remaining_capacity:
                if len(errors) < max_reported_errors:
                    errors.append({
                        "row": row_idx,
                        "error": f"Límite de {MAX_BENEFICIARIES_PER_BATCH} beneficiarios alcanzado, filas restantes ignoradas"
                    })
                skipped += 1
                continue

            name = _find_value(row, name_cols)
            if not name:
                if len(errors) < max_reported_errors:
                    errors.append({"row": row_idx, "error": "Nombre requerido"})
                skipped += 1
                continue

            beneficiary = {
                "id": uuid4().hex[:12],
                "name": name,
                "identifier": _find_value(row, id_cols),
                "identifier_type": _find_value(row, id_type_cols),
                "email": _find_value(row, email_cols),
                "phone": _find_value(row, phone_cols),
                "conditions": {},
                "status": "PENDING",
            }
            session["beneficiaries"].append(beneficiary)
            added += 1

        # Add truncation notice if errors were capped
        if skipped > len(errors):
            errors.append({
                "row": 0,
                "error": f"... y {skipped - len(errors)} errores más (mostrando los primeros {max_reported_errors})"
            })

        await self._save_session(session_id, session)
        result = {"added": added, "skipped": skipped, "errors": errors, "total": len(session["beneficiaries"])}
        logger.info(f"[BatchSession] CSV import for {session_id}: added={added}, skipped={skipped}")
        return result

    # =========================================================================
    # SHARED DOCUMENTS
    # =========================================================================

    async def add_shared_document(
        self,
        session_id: str,
        user_id: UUID,
        document_code: str,
        file_path: str,
        file_name: str,
        file_size: int,
        mime_type: str,
        extraction_data: Optional[Dict[str, Any]] = None,
        confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Register a shared document (already uploaded to Firebase).
        Only stores metadata reference in Redis — NO base64.
        """
        session = await self._get_session(session_id, user_id)

        # Replace if same document_code exists
        session["shared_documents"] = [
            d for d in session["shared_documents"] if d["document_code"] != document_code
        ]

        doc_ref = {
            "document_code": document_code,
            "file_path": file_path,
            "file_name": file_name,
            "file_size": file_size,
            "mime_type": mime_type,
            "extraction_data": extraction_data or {},
            "confidence": confidence,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        session["shared_documents"].append(doc_ref)

        if session["status"] == "DRAFT":
            session["status"] = "UPLOADING"

        await self._save_session(session_id, session)
        return doc_ref

    async def remove_shared_document(
        self,
        session_id: str,
        user_id: UUID,
        document_code: str,
    ) -> bool:
        """Remove a shared document reference from the session."""
        session = await self._get_session(session_id, user_id)

        original_len = len(session["shared_documents"])
        session["shared_documents"] = [
            d for d in session["shared_documents"] if d["document_code"] != document_code
        ]

        if len(session["shared_documents"]) == original_len:
            raise BatchSessionError("Documento compartido no encontrado.", "SHARED_DOC_NOT_FOUND")

        await self._save_session(session_id, session)
        return True

    # =========================================================================
    # ITEM DOCUMENTS (individual per beneficiary)
    # =========================================================================

    async def add_item_document(
        self,
        session_id: str,
        user_id: UUID,
        beneficiary_id: str,
        document_code: str,
        file_path: str,
        file_name: str,
        extraction_data: Optional[Dict[str, Any]] = None,
        confidence: Optional[float] = None,
        match_method: Optional[str] = None,
        match_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Register an individual document assigned to a beneficiary."""
        session = await self._get_session(session_id, user_id)

        if "item_documents" not in session:
            session["item_documents"] = {}

        if beneficiary_id not in session["item_documents"]:
            session["item_documents"][beneficiary_id] = []

        # Replace if same document_code for this beneficiary
        session["item_documents"][beneficiary_id] = [
            d for d in session["item_documents"][beneficiary_id]
            if d["document_code"] != document_code
        ]

        doc_ref = {
            "document_code": document_code,
            "file_path": file_path,
            "file_name": file_name,
            "extraction_data": extraction_data or {},
            "confidence": confidence,
            "match_method": match_method,
            "match_score": match_score,
        }
        session["item_documents"][beneficiary_id].append(doc_ref)
        await self._save_session(session_id, session)
        return doc_ref

    # =========================================================================
    # FORM DATA GRID
    # =========================================================================

    async def update_form_data(
        self,
        session_id: str,
        user_id: UUID,
        form_data_grid: Dict[str, Dict[str, Any]],
    ) -> bool:
        """
        Save form data for all beneficiaries at once.
        form_data_grid = {"beneficiary_id": {"field": "value", ...}, ...}
        """
        session = await self._get_session(session_id, user_id)
        session["form_data_grid"] = form_data_grid
        return await self._save_session(session_id, session)

    async def update_session_fields(
        self,
        session_id: str,
        user_id: UUID,
        updates: Dict[str, Any],
    ) -> bool:
        """
        Update arbitrary top-level fields on a session.
        Used by document_classifier to store classifications/assignments/status.

        Args:
            updates: Dict of field_name → value to merge into session.
        """
        session = await self._get_session(session_id, user_id)
        for key, value in updates.items():
            session[key] = value
        return await self._save_session(session_id, session)


# Singleton
batch_session_service = BatchSessionService()
