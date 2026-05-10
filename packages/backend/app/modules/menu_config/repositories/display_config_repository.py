"""
Workflow Display Config Repository - Database operations for workflow display configurations (asyncpg version)

Manages the workflow_display_config table which controls how PendingPage
displays columns and sections per workflow pattern.

Author: Claude Code Expert
Date: 2026-02-01
"""
from typing import List, Optional, Dict, Any
import json
import asyncpg
from loguru import logger

from app.modules.menu_config.models.menu_config import (
    WorkflowDisplayConfigCreate,
    WorkflowDisplayConfigUpdate,
)
from app.core.cache import get_cache, CacheKeys

DISPLAY_CONFIG_CACHE_TTL = 300  # 5 minutes


_BILINGUAL_EN_PREFIXES = frozenset({
    "type", "code", "passport no.", "date of issue", "date of expiry",
    "authority", "surname", "given names", "sex", "nationality",
    "date of birth", "place of birth", "profession", "personal no.",
    "residence",
})


def _extract_es_label(field_label: str) -> str:
    """Extract the Spanish part from bilingual field labels.

    Only pasaporte_gq.json uses bilingual "English/Español" format
    (e.g. "Type/Tipo", "Passport No./No. Pasaporte").
    Other schemas use "/" in Spanish labels (e.g. "DON/DOÑA", "DIP/NIE")
    which must NOT be split.

    Detects bilingual format by checking if the part before "/" is a
    known English prefix.
    """
    if "/" not in field_label:
        return field_label
    left, right = field_label.rsplit("/", 1)
    if left.strip().lower() in _BILINGUAL_EN_PREFIXES:
        return right.strip()
    return field_label


def _row_to_dict(record: asyncpg.Record) -> Optional[Dict[str, Any]]:
    """Convert asyncpg Record to dict, handling JSONB fields."""
    if record is None:
        return None
    result = dict(record)
    # Parse JSONB fields if they're strings
    for key in ['list_columns', 'preview_sections', 'labels']:
        if key in result and isinstance(result[key], str):
            result[key] = json.loads(result[key])
    return result


class DisplayConfigRepository:
    """Repository for workflow display config CRUD operations using asyncpg"""

    def __init__(self, db_connection: asyncpg.Connection):
        """
        Initialize repository with database connection

        Args:
            db_connection: asyncpg connection object
        """
        self.db = db_connection

    async def get_by_id(self, config_id: int) -> Optional[Dict[str, Any]]:
        """
        Get display config by ID

        Args:
            config_id: Config ID

        Returns:
            Config dict or None if not found
        """
        result = await self.db.fetchrow("""
            SELECT id, workflow_code, list_columns, preview_sections, labels,
                   is_active, created_at, updated_at
            FROM workflow_display_config
            WHERE id = $1
        """, config_id)

        return _row_to_dict(result)

    async def get_by_code(self, workflow_code: str) -> Optional[Dict[str, Any]]:
        """
        Get display config by exact workflow code

        Args:
            workflow_code: Exact workflow code (e.g., 'PASAPORTE_EXPEDICION_ADULTO')

        Returns:
            Config dict or None if not found
        """
        result = await self.db.fetchrow("""
            SELECT id, workflow_code, list_columns, preview_sections, labels,
                   is_active, created_at, updated_at
            FROM workflow_display_config
            WHERE workflow_code = $1
            AND is_active = true
            AND deleted_at IS NULL
        """, workflow_code)

        return _row_to_dict(result)


    async def get_all(
        self,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get all display configs with optional filters

        Args:
            is_active: Filter by active status
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of config dicts
        """
        if is_active is not None:
            query = """
                SELECT id, workflow_code, list_columns, preview_sections, labels,
                       is_active, created_at, updated_at
                FROM workflow_display_config
                WHERE is_active = $1
                AND deleted_at IS NULL
                ORDER BY workflow_code
                LIMIT $2 OFFSET $3
            """
            results = await self.db.fetch(query, is_active, limit, offset)
        else:
            query = """
                SELECT id, workflow_code, list_columns, preview_sections, labels,
                       is_active, created_at, updated_at
                FROM workflow_display_config
                WHERE deleted_at IS NULL
                ORDER BY workflow_code
                LIMIT $1 OFFSET $2
            """
            results = await self.db.fetch(query, limit, offset)

        return [_row_to_dict(row) for row in results]

    async def get_active_configs(self) -> List[Dict[str, Any]]:
        """
        Get all active display configs

        Returns:
            List of active config dicts
        """
        results = await self.db.fetch("""
            SELECT id, workflow_code, list_columns, preview_sections, labels,
                   is_active, created_at, updated_at
            FROM workflow_display_config
            WHERE is_active = true
            AND deleted_at IS NULL
            ORDER BY workflow_code
        """)

        return [_row_to_dict(row) for row in results]

    async def count(self, is_active: Optional[bool] = None) -> int:
        """
        Count display configs

        Args:
            is_active: Filter by active status

        Returns:
            Count of configs
        """
        if is_active is not None:
            result = await self.db.fetchval(
                "SELECT COUNT(*) FROM workflow_display_config WHERE is_active = $1 AND deleted_at IS NULL",
                is_active
            )
        else:
            result = await self.db.fetchval(
                "SELECT COUNT(*) FROM workflow_display_config WHERE deleted_at IS NULL"
            )

        return result or 0

    async def create(self, config: WorkflowDisplayConfigCreate) -> Dict[str, Any]:
        """
        Create a new display config

        Args:
            config: Config data

        Returns:
            Created config dict
        """
        result = await self.db.fetchrow("""
            INSERT INTO workflow_display_config (
                workflow_code, list_columns, preview_sections, labels
            )
            VALUES ($1, $2::jsonb, $3::jsonb, $4::jsonb)
            RETURNING id, workflow_code, list_columns, preview_sections, labels,
                      is_active, created_at, updated_at
        """,
            config.workflow_code,
            json.dumps(config.list_columns),
            json.dumps(config.preview_sections),
            json.dumps(config.labels or {})
        )

        return _row_to_dict(result)

    async def update(
        self,
        config_id: int,
        config: WorkflowDisplayConfigUpdate
    ) -> Optional[Dict[str, Any]]:
        """
        Update an existing display config

        Args:
            config_id: Config ID
            config: Updated config data

        Returns:
            Updated config dict or None if not found
        """
        # Build dynamic update query
        update_fields = []
        params = []
        param_count = 0

        if config.list_columns is not None:
            param_count += 1
            update_fields.append(f"list_columns = ${param_count}::jsonb")
            params.append(json.dumps(config.list_columns))

        if config.preview_sections is not None:
            param_count += 1
            update_fields.append(f"preview_sections = ${param_count}::jsonb")
            params.append(json.dumps(config.preview_sections))

        if config.labels is not None:
            param_count += 1
            update_fields.append(f"labels = ${param_count}::jsonb")
            params.append(json.dumps(config.labels))

        if config.is_active is not None:
            param_count += 1
            update_fields.append(f"is_active = ${param_count}")
            params.append(config.is_active)

        if not update_fields:
            return await self.get_by_id(config_id)

        param_count += 1
        params.append(config_id)

        query = f"""
            UPDATE workflow_display_config
            SET {', '.join(update_fields)}, updated_at = NOW()
            WHERE id = ${param_count}
            AND deleted_at IS NULL
            RETURNING id, workflow_code, list_columns, preview_sections, labels,
                      is_active, created_at, updated_at
        """

        result = await self.db.fetchrow(query, *params)
        updated = _row_to_dict(result)

        # Invalidate cache for this workflow_code
        if updated and updated.get('workflow_code'):
            await self.invalidate_cache(updated['workflow_code'])

        return updated

    async def delete(self, config_id: int) -> bool:
        """
        Delete a display config

        Args:
            config_id: Config ID

        Returns:
            True if deleted, False if not found
        """
        # Atomic DELETE + fetch workflow_code for cache invalidation
        workflow_code = await self.db.fetchval("""
            DELETE FROM workflow_display_config
            WHERE id = $1
            RETURNING workflow_code
        """, config_id)

        if workflow_code:
            await self.invalidate_cache(workflow_code)
            return True

        return False

    async def find_config_for_workflow(
        self,
        workflow_code: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find the display config for an exact workflow code.
        Uses Redis cache (5 min TTL) to avoid repeated DB queries
        when agents navigate multiple requests of the same workflow.

        Args:
            workflow_code: Exact workflow code (e.g., 'PASAPORTE_EXPEDICION_ADULTO')

        Returns:
            Matching config dict or None
        """
        cache = get_cache()
        cache_key = CacheKeys.display_config(workflow_code)

        # Try cache first
        try:
            cached = await cache.get(cache_key)
            if cached is not None:
                # "__none__" marker means we cached a "not found" result
                if isinstance(cached, dict) and cached.get("__none__"):
                    return None
                return cached
        except Exception:
            pass  # Cache miss or error, fall through to DB

        # DB lookup
        result = await self.db.fetchrow("""
            SELECT id, workflow_code, list_columns, preview_sections, labels,
                   is_active, created_at, updated_at
            FROM workflow_display_config
            WHERE is_active = true
              AND workflow_code = $1
              AND deleted_at IS NULL
        """, workflow_code)

        config = _row_to_dict(result)

        # Cache result (even None as empty dict marker)
        try:
            await cache.set(
                cache_key,
                config if config else {"__none__": True},
                ttl=DISPLAY_CONFIG_CACHE_TTL,
            )
        except Exception:
            pass

        return config

    async def find_configs_for_workflows(
        self,
        workflow_codes: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Batch fetch display configs for multiple workflow codes.
        Returns dict keyed by workflow_code with config values.
        Only returns configs for workflows that have an active config.
        """
        if not workflow_codes:
            return {}

        # Build parameterized IN clause
        placeholders = ', '.join(f'${i+1}' for i in range(len(workflow_codes)))
        rows = await self.db.fetch(f"""
            SELECT workflow_code, list_columns, preview_sections, labels
            FROM workflow_display_config
            WHERE is_active = true
              AND workflow_code IN ({placeholders})
              AND deleted_at IS NULL
        """, *workflow_codes)

        result: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            d = dict(row)
            wc = d.pop('workflow_code')
            # Parse JSONB fields if returned as strings
            for key in ('list_columns', 'preview_sections', 'labels'):
                if isinstance(d.get(key), str):
                    d[key] = json.loads(d[key])
            result[wc] = d
        return result

    @staticmethod
    async def invalidate_cache(workflow_code: str) -> None:
        """Invalidate cached display config for a workflow code."""
        try:
            cache = get_cache()
            await cache.delete(CacheKeys.display_config(workflow_code))
        except Exception:
            pass

    async def get_available_columns_for_workflow(
        self,
        workflow_code: str,
        is_minor: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Discover available columns from workflow's get_document_requirements()
        and JSON extraction schemas.

        Source of truth: each workflow class defines its document requirements
        (with condition_type and schema_key). The schema_loader resolves
        extraction fields from JSON schema files.

        Handles three workflow resolution scenarios:
        1. Direct match: workflow_code is a registered parent code
        2. Variant resolution: workflow_code is a variant (e.g., VEHICULO_RENOVACION_CUVE)
           resolved to parent workflow + specific sub_type
        3. DB fallback: workflow has no registered class, uses workflow_document_requirements

        Args:
            workflow_code: Exact workflow code (e.g., 'PASAPORTE_NUEVO', 'VEHICULO_RENOVACION_CUVE')
            is_minor: Filter by minor status (True/False/None=all)

        Returns:
            Dict with extracted_columns, available_filters, document_count
        """
        from app.modules.service_requests.services.workflow_engine import workflow_engine
        from app.modules.service_requests.workflows.workflow_interface import (
            PredefinedWorkflow, WorkflowContext, RenovacionMotivo,
        )
        # BaseWorkflow removed — all workflows are now v2 (PredefinedWorkflow)
        from app.modules.service_requests.models.enums import (
            DocumentConditionType, SolicitudType, WorkflowCode as WFCode,
        )
        from app.modules.service_requests.services.schema_loader import schema_loader
        from uuid import uuid4

        empty_result = {
            "total_requests": 0,
            "extracted_columns": [],
            "filters_applied": {"is_minor": is_minor} if is_minor is not None else None,
            "available_filters": {},
            "suggested_columns": [],
            "document_count": 0,
        }

        # 1. Resolve workflow: direct lookup, then variant→parent, then DB fallback
        workflow = workflow_engine.get_workflow_by_string(workflow_code)
        resolved_sub_type = None

        if workflow is not None:
            # Direct match — but we still need to resolve the sub_type
            # so _collect_v2_documents uses only the correct combo.
            # E.g., PASAPORTE_NUEVO → sub_type="NUEVO" → (EXPEDICION, None) only
            _, resolved_sub_type = self._resolve_variant_workflow(
                workflow_code, workflow_engine
            )

        if workflow is None:
            # Try resolving variant code (e.g., VEHICULO_RENOVACION_CUVE → VehiculoWorkflow)
            workflow, resolved_sub_type = self._resolve_variant_workflow(
                workflow_code, workflow_engine
            )

        if workflow is None:
            # DB fallback: use workflow_document_requirements table
            logger.info(f"No workflow class for {workflow_code}, trying DB fallback")
            return await self._get_columns_from_db(
                workflow_code, is_minor, schema_loader
            )

        # 2. Collect ALL document requirements (all variants, both minor/adult)
        all_docs = []
        seen_codes: set = set()

        def _add_docs(docs):
            for doc in docs:
                if doc.document_code not in seen_codes:
                    seen_codes.add(doc.document_code)
                    all_docs.append(doc)

        if isinstance(workflow, PredefinedWorkflow):
            self._collect_v2_documents(
                workflow, workflow_code, resolved_sub_type, _add_docs
            )

        if not all_docs:
            logger.info(f"No documents found for {workflow_code}")
            return empty_result

        # 3. Determine available_filters from condition_types present
        all_condition_types = set()
        for doc in all_docs:
            ct = doc.condition_type
            ct_val = ct.value if isinstance(ct, DocumentConditionType) else str(ct)
            all_condition_types.add(ct_val)

        available_filters: Dict[str, Any] = {}
        if 'is_minor' in all_condition_types or 'is_adult' in all_condition_types:
            available_filters["is_minor"] = [False, True]

        # 4. Filter documents by is_minor condition
        #    Also check condition_value for CUSTOM conditions that embed is_minor
        filtered_docs = []
        for doc in all_docs:
            ct = doc.condition_type
            ct_val = ct.value if isinstance(ct, DocumentConditionType) else str(ct)

            # Check CUSTOM conditions that embed is_minor in condition_value
            cv = getattr(doc, 'condition_value', None) or {}
            cv_is_minor = cv.get('is_minor') if isinstance(cv, dict) else None

            if is_minor is True:
                if ct_val == 'is_adult':
                    continue
                if ct_val == 'custom' and cv_is_minor is False:
                    continue
                filtered_docs.append(doc)
            elif is_minor is False:
                if ct_val == 'is_minor':
                    continue
                if ct_val == 'custom' and cv_is_minor is True:
                    continue
                filtered_docs.append(doc)
            else:
                filtered_docs.append(doc)

        # 5. For each document with a schema_key, load extraction fields
        #    Also check config.accepted_schemas for multi-schema documents
        #    (e.g., documento_representante accepts DIP, NIE, or PASAPORTE)
        extracted_columns = []
        doc_with_extraction = 0
        for doc in filtered_docs:
            schema_key = doc.schema_key
            # Fallback: check config.accepted_schemas (first value)
            if not schema_key and hasattr(doc, 'config') and doc.config:
                accepted = doc.config.get('accepted_schemas')
                if isinstance(accepted, dict) and accepted:
                    # Use first accepted schema (most common document type)
                    schema_key = next(iter(accepted.values()))
            if not schema_key:
                continue

            doc_with_extraction += 1
            doc_code = doc.document_code
            doc_name = doc.document_name_es or doc_code

            try:
                fields = schema_loader.get_extraction_fields(
                    schema_key=schema_key,
                    extraction_schema_key=schema_key,
                )
            except Exception as e:
                logger.warning(f"Failed to load schema for {schema_key}: {e}")
                continue

            for field_name, field_config in fields.items():
                col_id = f"{doc_code}.{field_name}"
                extracted_columns.append({
                    "id": col_id,
                    "label_key": f"columns.{col_id}",
                    "label": _extract_es_label(field_config.get("field_label", field_name)),
                    "source": "extracted",
                    "data_type": field_config.get("type", "string"),
                    "sample_count": 0,
                    "document_code": doc_code,
                    "document_name_es": doc_name,
                })

        # 6. Build response
        filters_applied = {}
        if is_minor is not None:
            filters_applied["is_minor"] = is_minor

        return {
            "total_requests": 0,
            "extracted_columns": extracted_columns,
            "filters_applied": filters_applied if filters_applied else None,
            "available_filters": available_filters,
            "suggested_columns": [],
            "document_count": doc_with_extraction,
        }

    # =========================================================================
    # Private helpers for column discovery
    # =========================================================================

    @staticmethod
    def _resolve_variant_workflow(workflow_code_str, workflow_engine):
        """
        Resolve a variant workflow code to its parent workflow + sub_type.

        E.g., VEHICULO_RENOVACION_CUVE → (VehiculoWorkflow, "RENOVACION_CUVE")
              RESIDENCIA_RENOVACION → (ResidenciaWorkflow, "RENOVACION")
              PASAPORTE_ROBO → (PasaporteWorkflow, "ROBO")
        """
        from app.modules.service_requests.models.enums import WorkflowCode as WFCode

        try:
            target_code = WFCode(workflow_code_str)
        except ValueError:
            return None, None

        for _wf_code, wf in workflow_engine._workflows.items():
            if wf.allowed_sub_types:
                for sub in wf.allowed_sub_types:
                    try:
                        if wf.get_workflow_code_for_subtype(sub) == target_code:
                            return wf, sub
                    except Exception:
                        continue

        return None, None

    @staticmethod
    def _collect_v2_documents(workflow, workflow_code, resolved_sub_type, add_docs_fn):
        """
        Collect documents from a v2 PredefinedWorkflow.

        For parent codes: iterates all solicitud_types × motivos × is_minor contexts.
        For variant codes: uses specific (solicitud_type, motivo) from SUBTYPE_TO_SOLICITUD_MOTIVO.
        Always calls with both is_minor=True and is_minor=False contexts to capture
        all possible documents (adult-only AND minor-only).
        """
        from app.modules.service_requests.workflows.workflow_interface import (
            PredefinedWorkflow, WorkflowContext, RenovacionMotivo,
        )
        from app.modules.service_requests.models.enums import (
            SolicitudType, WorkflowCode as WFCode,
        )
        from uuid import uuid4

        try:
            wf_code_enum = WFCode(workflow_code)
        except ValueError:
            wf_code_enum = workflow.workflow_code

        # Determine which (solicitud_type, motivo) combinations to call with
        sol_motivo_combos = []
        if resolved_sub_type and hasattr(workflow, 'SUBTYPE_TO_SOLICITUD_MOTIVO'):
            specific = workflow.SUBTYPE_TO_SOLICITUD_MOTIVO.get(resolved_sub_type)
            if specific:
                sol_motivo_combos.append(specific)
        if not sol_motivo_combos:
            # Parent code or unknown sub_type: iterate all combinations
            for sol_type in workflow.allowed_solicitud_types:
                if sol_type == SolicitudType.RENOVACION:
                    for motivo_val in RenovacionMotivo:
                        sol_motivo_combos.append((sol_type, motivo_val))
                else:
                    sol_motivo_combos.append((sol_type, None))

        # Call with both is_minor=True and is_minor=False contexts to capture all docs
        for sol_type, motivo in sol_motivo_combos:
            for minor_flag in [False, True]:
                try:
                    ctx = WorkflowContext(
                        service_request_id=uuid4(),
                        user_id=uuid4(),
                        workflow_code=wf_code_enum,
                        solicitud_type=sol_type,
                        form_data={"is_minor": minor_flag},
                    )
                    docs = workflow.get_document_requirements(
                        solicitud_type=sol_type,
                        motivo=motivo,
                        context=ctx,
                    )
                    add_docs_fn(docs)
                except Exception as e:
                    logger.debug(
                        f"Error getting docs for {workflow_code}/"
                        f"{sol_type}/{motivo}/minor={minor_flag}: {e}"
                    )

    async def _get_columns_from_db(
        self,
        workflow_code: str,
        is_minor: Optional[bool],
        schema_loader,
    ) -> Dict[str, Any]:
        """
        DB fallback: discover columns from workflow_document_requirements table.
        Used for workflows without a registered Python class (e.g., generic workflows).
        """
        from app.modules.service_requests.models.enums import DocumentConditionType

        rows = await self.db.fetch("""
            SELECT document_code, document_name_es, condition_type,
                   condition_value, extraction_schema_key
            FROM workflow_document_requirements
            WHERE workflow_code = $1
              AND is_active = true
            ORDER BY display_order, document_code
        """, workflow_code)

        if not rows:
            logger.info(f"No DB document requirements for {workflow_code}")
            return {
                "total_requests": 0,
                "extracted_columns": [],
                "filters_applied": {"is_minor": is_minor} if is_minor is not None else None,
                "available_filters": {},
                "suggested_columns": [],
                "document_count": 0,
            }

        # Determine available_filters
        all_condition_types = {r['condition_type'] for r in rows}
        available_filters: Dict[str, Any] = {}
        if 'is_minor' in all_condition_types or 'is_adult' in all_condition_types:
            available_filters["is_minor"] = [False, True]

        # Filter by is_minor
        filtered_rows = []
        for row in rows:
            ct = row['condition_type']
            if is_minor is True:
                if ct not in ('is_adult',):
                    filtered_rows.append(row)
            elif is_minor is False:
                if ct not in ('is_minor',):
                    filtered_rows.append(row)
            else:
                filtered_rows.append(row)

        # Load extraction fields
        extracted_columns = []
        doc_with_extraction = 0
        for row in filtered_rows:
            schema_key = row['extraction_schema_key']
            if not schema_key:
                continue

            doc_with_extraction += 1
            doc_code = row['document_code']
            doc_name = row['document_name_es'] or doc_code

            try:
                fields = schema_loader.get_extraction_fields(
                    schema_key=schema_key,
                    extraction_schema_key=schema_key,
                )
            except Exception as e:
                logger.warning(f"Failed to load schema for {schema_key}: {e}")
                continue

            for field_name, field_config in fields.items():
                col_id = f"{doc_code}.{field_name}"
                extracted_columns.append({
                    "id": col_id,
                    "label_key": f"columns.{col_id}",
                    "label": _extract_es_label(field_config.get("field_label", field_name)),
                    "source": "extracted",
                    "data_type": field_config.get("type", "string"),
                    "sample_count": 0,
                    "document_code": doc_code,
                    "document_name_es": doc_name,
                })

        filters_applied = {}
        if is_minor is not None:
            filters_applied["is_minor"] = is_minor

        return {
            "total_requests": 0,
            "extracted_columns": extracted_columns,
            "filters_applied": filters_applied if filters_applied else None,
            "available_filters": available_filters,
            "suggested_columns": [],
            "document_count": doc_with_extraction,
        }

    async def get_sample_request(
        self,
        workflow_code: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a sample service request for preview purposes.

        Args:
            workflow_code: Exact workflow code

        Returns:
            Sample request dict or None if no requests found
        """
        result = await self.db.fetchrow("""
            SELECT
                sr.id, sr.reference, sr.citizen_name,
                sr.workflow_code, sr.status, sr.priority,
                sr.extracted_data, sr.form_data, sr.created_at
            FROM service_requests sr
            WHERE sr.workflow_code = $1
            AND (sr.extracted_data IS NOT NULL OR sr.form_data IS NOT NULL)
            ORDER BY sr.created_at DESC
            LIMIT 1
        """, workflow_code)

        if result is None:
            return None

        return dict(result)
