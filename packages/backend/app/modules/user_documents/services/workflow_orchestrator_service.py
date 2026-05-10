"""
Workflow Orchestrator Service — Auto-prepare wizard sessions from vault.

Creates a wizard session, loads documents from the user's vault,
pre-fills form data with extracted information, and returns a ready-to-finalize
session that skips the first 5 steps of the wizard.

This is the LEVEL 2 agent capability: preparation with user confirmation.
"""

import asyncio
import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import asyncpg
from loguru import logger


class WorkflowOrchestratorService:
    """Orchestrates wizard session creation from vault documents."""

    # ── Workflow name → code resolution ──────────────────────────────
    WORKFLOW_NAME_MAP = {
        # Pasaporte
        "pasaporte": "PASAPORTE_NUEVO",
        "passport": "PASAPORTE_NUEVO",
        "passeport": "PASAPORTE_NUEVO",
        "pasaporte nuevo": "PASAPORTE_NUEVO",
        "pasaporte renovacion": "PASAPORTE_RENOVACION",
        "renovar pasaporte": "PASAPORTE_RENOVACION",
        "renouveler passeport": "PASAPORTE_RENOVACION",
        "renew passport": "PASAPORTE_RENOVACION",
        "pasaporte perdida": "PASAPORTE_PERDIDA",
        "pasaporte robo": "PASAPORTE_ROBO",
        "pasaporte deterioro": "PASAPORTE_DETERIORO",
        # Residencia
        "residencia": "RESIDENCIA_PRIMERA_VEZ",
        "residence": "RESIDENCIA_PRIMERA_VEZ",
        "résidence": "RESIDENCIA_PRIMERA_VEZ",
        "residencia renovacion": "RESIDENCIA_RENOVACION",
        "renovar residencia": "RESIDENCIA_RENOVACION",
        # Conducir
        "licencia": "CONDUCIR_NUEVO",
        "licencia conducir": "CONDUCIR_NUEVO",
        "permis de conduire": "CONDUCIR_NUEVO",
        "driver license": "CONDUCIR_NUEVO",
        "renovar licencia": "CONDUCIR_RENOVACION",
        "conducir renovacion": "CONDUCIR_RENOVACION",
        # Carnet funcionario
        "carnet funcionario": "FP_CARNET_FUNCIONARIO",
        "carné funcionario": "FP_CARNET_FUNCIONARIO",
        "carnet": "FP_CARNET_FUNCIONARIO",
        # Contrato
        "contrato": "CONTRATO_SERVICIO",
        "contract": "CONTRATO_SERVICIO",
        "contrat": "CONTRATO_SERVICIO",
        # Verificacion
        "verificacion": "FP_VERIFICACION_FUNCIONARIO",
        "verificación": "FP_VERIFICACION_FUNCIONARIO",
        # Vehiculo
        "vehiculo": "VEHICULO_PRIMERA_MATRICULACION",
        "matriculacion": "VEHICULO_PRIMERA_MATRICULACION",
        "transferencia": "VEHICULO_TRANSFERENCIA",
        "itv": "VEHICULO_RENOVACION_ITV",
        # Visado
        "visado": "VISADO_ALTERNATIVO",
        "visa": "VISADO_ALTERNATIVO",
        "prorroga visado": "PRORROGA_VISADO",
        # Bundle
        "pagar obligaciones": "BUNDLE_PAYMENT",
        "pago obligaciones": "BUNDLE_PAYMENT",
        "bundle": "BUNDLE_PAYMENT",
    }

    # ── Workflow code → solicitud_type mapping ───────────────────────
    SOLICITUD_TYPE_MAP = {
        "PASAPORTE_NUEVO": "expedicion",
        "PASAPORTE_RENOVACION": "renovacion",
        "PASAPORTE_PERDIDA": "renovacion",
        "PASAPORTE_ROBO": "renovacion",
        "PASAPORTE_DETERIORO": "renovacion",
        "RESIDENCIA_PRIMERA_VEZ": "expedicion",
        "RESIDENCIA_RENOVACION": "renovacion",
        "CONDUCIR_NUEVO": "expedicion",
        "CONDUCIR_RENOVACION": "renovacion",
        "CONDUCIR_CANJE": "canje",
        "CONDUCIR_DUPLICADO": "duplicado",
        "CONDUCIR_EXTENSION": "extension",
        "FP_CARNET_FUNCIONARIO": "expedicion",
        "FP_VERIFICACION_FUNCIONARIO": "expedicion",
        "FP_CERTIFICADO_ADMINISTRATIVO": "expedicion",
        "FP_PERMISO_EXTRAORDINARIO": "expedicion",
        "FP_PROMOCION_ADMINISTRATIVA": "expedicion",
    }

    # ── Workflow code → motivo mapping ───────────────────────────────
    MOTIVO_MAP = {
        "PASAPORTE_RENOVACION": "VENCIMIENTO",
        "PASAPORTE_PERDIDA": "PERDIDA",
        "PASAPORTE_ROBO": "ROBO",
        "PASAPORTE_DETERIORO": "DETERIORO",
    }

    async def prepare_wizard_from_vault(
        self,
        db: asyncpg.Connection,
        user_id: str,
        workflow_name: str,
        solicitud_type: Optional[str] = None,
        motivo: Optional[str] = None,
        skip_missing_docs: bool = False,
    ) -> Dict[str, Any]:
        """
        Main orchestration method. Creates a wizard session and pre-fills it
        with documents from the user's vault.

        Returns a dict with session info, loaded documents, and a wizard URL.
        """
        try:
            # 1. Resolve workflow code from natural language
            workflow_code, resolved_type, resolved_motivo = await self._resolve_workflow(
                db, workflow_name, solicitud_type, motivo
            )

            if not workflow_code:
                return {
                    "status": "error",
                    "error": "workflow_not_found",
                    "message": f"No se encontró un trámite para: '{workflow_name}'. "
                               "Intente con nombres como: pasaporte, residencia, licencia conducir, contrato.",
                }

            # 2. Check readiness — what docs are in the vault?
            readiness = await self._check_vault_readiness(db, user_id, workflow_code)

            if not skip_missing_docs and readiness["missing_count"] > 0:
                return {
                    "status": "missing_documents",
                    "workflow_code": workflow_code,
                    "workflow_name": readiness.get("workflow_name", workflow_code),
                    "readiness_score": readiness["readiness_score"],
                    "total_required": readiness["total_required"],
                    "available": readiness["available_count"],
                    "missing_count": readiness["missing_count"],
                    "missing_documents": readiness["missing"],
                    "available_documents": readiness["ready"],
                    "message": (
                        f"Para {readiness.get('workflow_name', workflow_code)}, "
                        f"tiene {readiness['available_count']}/{readiness['total_required']} documentos. "
                        f"Faltan: {', '.join(m['name'] for m in readiness['missing'][:5])}. "
                        "¿Desea continuar con los documentos disponibles o primero agregar los faltantes?"
                    ),
                    "requires_user_choice": True,
                }

            # 3. Create wizard session
            session_result = await self._create_wizard_session(
                db, user_id, workflow_code, resolved_type, resolved_motivo
            )

            if not session_result.get("session_id"):
                return {
                    "status": "error",
                    "error": "session_creation_failed",
                    "message": "No se pudo crear la sesión del wizard. Intente nuevamente.",
                }

            session_id = session_result["session_id"]

            # 4. Load documents from vault into the wizard session
            loaded_docs, failed_docs = await self._load_vault_documents_into_session(
                db, user_id, session_id, workflow_code
            )

            # 5. Pre-fill form data from extracted data
            form_completion = await self._pre_fill_form_data(
                db, user_id, session_id, loaded_docs
            )

            # 6. Build result
            return {
                "status": "prepared",
                "session_id": session_id,
                "workflow_code": workflow_code,
                "workflow_name": readiness.get("workflow_name", workflow_code),
                "solicitud_type": resolved_type,
                "motivo": resolved_motivo,
                "documents_loaded": len(loaded_docs),
                "documents_total": readiness["total_required"],
                "documents_failed": len(failed_docs),
                "documents_missing": readiness["missing_count"],
                "form_completion_pct": form_completion,
                "wizard_url": f"/dashboard/service-requests/wizard/session/{session_id}",
                "requires_user_action": True,
                "action": {
                    "type": "open_wizard",
                    "url": f"/dashboard/service-requests/wizard/session/{session_id}",
                    "label": "Finalizar mi solicitud",
                },
                "message": (
                    f"He preparado su solicitud de {readiness.get('workflow_name', workflow_code)}:\n"
                    f"- {len(loaded_docs)}/{readiness['total_required']} documentos cargados desde su cofre digital\n"
                    f"- Formulario pre-rellenado al {form_completion}%\n"
                    + (f"- {len(failed_docs)} documento(s) requieren carga manual\n" if failed_docs else "")
                    + "\nHaga clic en el botón para verificar la información y finalizar."
                ),
            }

        except Exception as e:
            logger.error(f"Workflow orchestrator error: {e}")
            return {
                "status": "error",
                "error": "orchestration_failed",
                "message": f"Error al preparar la solicitud: {str(e)}",
            }

    async def _resolve_workflow(
        self,
        db: asyncpg.Connection,
        workflow_name: str,
        solicitud_type: Optional[str],
        motivo: Optional[str],
    ) -> Tuple[Optional[str], str, Optional[str]]:
        """Resolve natural language → workflow_code + params."""
        name_lower = workflow_name.strip().lower()

        # 1. Try direct mapping
        code = self.WORKFLOW_NAME_MAP.get(name_lower)

        # 2. Try partial match in map keys
        if not code:
            for key, val in self.WORKFLOW_NAME_MAP.items():
                if key in name_lower or name_lower in key:
                    code = val
                    break

        # 3. Try DB lookup (workflows table)
        if not code:
            row = await db.fetchrow("""
                SELECT code FROM workflows
                WHERE is_active = TRUE
                  AND (code ILIKE '%' || $1 || '%' OR name_es ILIKE '%' || $1 || '%')
                ORDER BY CASE WHEN code ILIKE $1 THEN 0 ELSE 1 END
                LIMIT 1
            """, name_lower)
            if row:
                code = row["code"]

        if not code:
            return None, "expedicion", None

        # Resolve solicitud_type and motivo
        resolved_type = solicitud_type or self.SOLICITUD_TYPE_MAP.get(code, "expedicion")
        resolved_motivo = motivo or self.MOTIVO_MAP.get(code)

        return code, resolved_type, resolved_motivo

    async def _check_vault_readiness(
        self,
        db: asyncpg.Connection,
        user_id: str,
        workflow_code: str,
    ) -> Dict[str, Any]:
        """Check which required documents are available in the vault."""
        # Get required documents for this workflow
        required = await db.fetch("""
            SELECT wdr.document_code, wdr.document_name_es, wdr.is_required
            FROM workflow_document_requirements wdr
            WHERE wdr.workflow_code = $1 AND wdr.is_active = TRUE
            ORDER BY wdr.display_order
        """, workflow_code)

        # Get workflow name
        wf_row = await db.fetchrow(
            "SELECT name_es FROM workflows WHERE code = $1", workflow_code
        )
        workflow_name = wf_row["name_es"] if wf_row else workflow_code

        # Get user's vault documents tagged for this workflow
        available = await db.fetch("""
            SELECT ud.id, ud.document_type, ud.file_path, ud.expiry_date,
                   ud.extraction_data, ud.extraction_confidence,
                   ud.file_name, ud.mime_type, ud.file_size_bytes,
                   udwt.document_code
            FROM user_documents ud
            JOIN user_document_workflow_tags udwt ON udwt.user_document_id = ud.id
            WHERE ud.user_id = $1::uuid AND udwt.workflow_code = $2
              AND ud.status = 'active' AND ud.deleted_at IS NULL
        """, user_id, workflow_code)

        available_codes = {r["document_code"]: r for r in available}
        ready = []
        missing = []

        for req in required:
            code = req["document_code"]
            name = req["document_name_es"]
            if code in available_codes:
                doc = available_codes[code]
                # Check expiry
                if doc.get("expiry_date") and doc["expiry_date"] < date.today():
                    missing.append({"code": code, "name": name, "reason": "expired"})
                else:
                    ready.append({
                        "code": code,
                        "name": name,
                        "vault_doc_id": str(doc["id"]),
                        "file_path": doc["file_path"],
                        "confidence": float(doc["extraction_confidence"] or 0),
                    })
            elif req["is_required"]:
                missing.append({"code": code, "name": name, "reason": "not_in_vault"})

        total = len(required)
        score = round((len(ready) / total * 100) if total > 0 else 0)

        return {
            "workflow_name": workflow_name,
            "readiness_score": score,
            "total_required": total,
            "available_count": len(ready),
            "missing_count": len(missing),
            "ready": ready,
            "missing": missing,
        }

    async def _create_wizard_session(
        self,
        db: asyncpg.Connection,
        user_id: str,
        workflow_code: str,
        solicitud_type: str,
        motivo: Optional[str],
    ) -> Dict[str, Any]:
        """Create a wizard session via the existing service."""
        try:
            from app.modules.service_requests.services.wizard_session_service import (
                wizard_session_service,
            )

            result = await wizard_session_service.start_session(
                user_id=UUID(user_id),
                workflow_code=workflow_code,
                solicitud_type=solicitud_type,
                motivo=motivo,
                is_minor=False,
            )

            return {
                "session_id": result.session_id if hasattr(result, 'session_id') else result.get("session_id"),
                "status": "active",
            }
        except Exception as e:
            logger.error(f"Failed to create wizard session: {e}")
            return {"session_id": None, "error": str(e)}

    async def _load_vault_documents_into_session(
        self,
        db: asyncpg.Connection,
        user_id: str,
        session_id: str,
        workflow_code: str,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Load vault documents into the wizard session.
        Downloads from Firebase and uploads into the session cache.
        """
        loaded = []
        failed = []

        # Get available vault docs for this workflow
        vault_docs = await db.fetch("""
            SELECT ud.id, ud.document_type, ud.file_path, ud.file_name,
                   ud.mime_type, ud.file_size_bytes,
                   ud.extraction_data, ud.extraction_confidence,
                   udwt.document_code
            FROM user_documents ud
            JOIN user_document_workflow_tags udwt ON udwt.user_document_id = ud.id
            WHERE ud.user_id = $1::uuid AND udwt.workflow_code = $2
              AND ud.status = 'active' AND ud.deleted_at IS NULL
              AND (ud.expiry_date IS NULL OR ud.expiry_date >= CURRENT_DATE)
        """, user_id, workflow_code)

        from app.modules.service_requests.services.wizard_session_service import (
            wizard_session_service,
        )

        for doc in vault_docs:
            try:
                # Use vault document directly — zero Firebase download/upload overhead
                vault_confidence = float(doc["extraction_confidence"] or 0)

                await wizard_session_service.use_vault_document(
                    session_id=session_id,
                    user_id=UUID(user_id),
                    document_code=doc["document_code"],
                    vault_document_id=str(doc["id"]),
                    db=db,
                )

                loaded.append({
                    "code": doc["document_code"],
                    "file_name": doc["file_name"],
                    "confidence": vault_confidence,
                    "auto_confirmed": vault_confidence >= 0.85,
                })

                logger.info(
                    f"Vault doc {doc['document_code']} linked to session {session_id} "
                    f"via use_vault_document (confidence: {vault_confidence:.0%})"
                )

            except Exception as e:
                logger.warning(f"Failed to link vault doc {doc['document_code']}: {e}")
                failed.append({
                    "code": doc["document_code"],
                    "reason": str(e),
                })

        return loaded, failed

    async def _pre_fill_form_data(
        self,
        db: asyncpg.Connection,
        user_id: str,
        session_id: str,
        loaded_docs: List[Dict],
    ) -> int:
        """
        Pre-fill form data from extracted document data.
        Returns completion percentage (0-100).
        """
        if not loaded_docs:
            return 0

        try:
            from app.modules.service_requests.services.wizard_session_service import (
                wizard_session_service,
            )

            # The wizard session already has extracted_data from the preview step.
            # Calling save_form_data with an empty dict triggers the merge of
            # extracted_data → form_data (extractions are already in the session).
            await wizard_session_service.save_form_data(
                session_id=session_id,
                user_id=UUID(user_id),
                form_data={},  # Merge existing extractions
            )

            # Estimate completion based on confirmed docs
            confirmed = sum(1 for d in loaded_docs if d.get("auto_confirmed"))
            total = len(loaded_docs)
            return round((confirmed / total * 100) if total > 0 else 0)

        except Exception as e:
            logger.warning(f"Form pre-fill failed: {e}")
            return 0

    async def _download_from_firebase(self, file_path: str) -> Optional[bytes]:
        """Download file content from Firebase Storage."""
        try:
            from app.modules.documents.services.storage_service import (
                firebase_storage_service,
            )

            if not firebase_storage_service._initialized:
                await firebase_storage_service.initialize()

            blob = firebase_storage_service.bucket.blob(file_path)
            if not blob.exists():
                logger.warning(f"Firebase blob not found: {file_path}")
                return None

            return blob.download_as_bytes(timeout=30)

        except Exception as e:
            logger.error(f"Firebase download failed for {file_path}: {e}")
            return None


# Singleton
workflow_orchestrator_service = WorkflowOrchestratorService()
