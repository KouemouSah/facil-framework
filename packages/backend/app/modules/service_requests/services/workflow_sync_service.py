"""
Workflow Sync Service — Single source of truth synchronization.

ONE function does everything: sync_all_workflows()
Called from:
  - main.py lifespan (startup, no dry_run)
  - POST /admin/service-requests/sync/workflows (admin, supports dry_run)

Syncs 5 DB targets from PredefinedWorkflow Python classes:
  1. workflows table (UPSERT)
  2. workflow_tariffs (UPSERT)
  3. workflow_document_requirements (UPSERT)
  4. workflow_menu_mapping (INSERT if missing)
  5. workflow_display_config (INSERT if missing)
  + Deactivate orphaned predefined workflows
  + Invalidate Redis caches

100% dynamic: reads properties from workflow classes via workflow_engine registry.
Zero hardcoded mapping. Adding a new PredefinedWorkflow class automatically
populates all related DB tables.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Tuple
from uuid import uuid4

from app.core.cache import (
    get_menu_cache,
    CacheKeys,
    invalidate_workflow_mappings_cache,
)

logger = logging.getLogger(__name__)


# ─── Result model ───────────────────────────────────────────────────────────

@dataclass
class WorkflowSyncResult:
    """Result of a full workflow sync operation."""
    workflows_synced: int = 0
    workflows_created: int = 0
    workflows_updated: int = 0
    workflows_deactivated: int = 0
    tariffs_synced: int = 0
    tariffs_created: int = 0
    tariffs_updated: int = 0
    documents_synced: int = 0
    documents_created: int = 0
    documents_updated: int = 0
    menu_mappings_synced: int = 0
    menu_mappings_created: int = 0
    display_configs_synced: int = 0
    display_configs_created: int = 0
    errors: List[str] = field(default_factory=list)
    details: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON response / logging."""
        return {
            "workflows_synced": self.workflows_synced,
            "workflows_created": self.workflows_created,
            "workflows_updated": self.workflows_updated,
            "workflows_deactivated": self.workflows_deactivated,
            "tariffs_synced": self.tariffs_synced,
            "tariffs_created": self.tariffs_created,
            "tariffs_updated": self.tariffs_updated,
            "documents_synced": self.documents_synced,
            "documents_created": self.documents_created,
            "documents_updated": self.documents_updated,
            "menu_mappings_synced": self.menu_mappings_synced,
            "menu_mappings_created": self.menu_mappings_created,
            "display_configs_synced": self.display_configs_synced,
            "display_configs_created": self.display_configs_created,
            "errors": self.errors,
            "details": self.details,
        }


# Default display_config columns/sections per category
_DEFAULT_LIST_COLUMNS = ["reference", "beneficiary", "status", "created_at"]
_DEFAULT_PREVIEW_SECTIONS = ["identity", "documents"]


# ─── Sub_type → SolicitudType mapping (for document extraction) ──────────

def _map_sub_type_to_solicitud_type(sub_type: str) -> "SolicitudType":
    """Map a workflow sub_type string to the correct SolicitudType enum.

    Workflows use sub_types like 'PRIMERA_VEZ', 'TRANSFERENCIA', etc.
    but get_document_requirements() compares with SolicitudType enum
    which is lowercase ('expedicion', 'renovacion', 'duplicado').
    """
    from app.modules.service_requests.models.enums import SolicitudType

    _MAP = {
        # EXPEDICION indicators
        "NUEVO": SolicitudType.EXPEDICION,
        "NUEVA": SolicitudType.EXPEDICION,
        "PRIMERA_VEZ": SolicitudType.EXPEDICION,
        "PRIMERA_MATRICULACION": SolicitudType.EXPEDICION,
        "EXPEDICION": SolicitudType.EXPEDICION,
        # RENOVACION indicators
        "RENOVACION": SolicitudType.RENOVACION,
        "RENOVACION_ITV": SolicitudType.RENOVACION,
        "RENOVACION_CUVE": SolicitudType.RENOVACION,
        # DUPLICADO indicators
        "DUPLICADO": SolicitudType.DUPLICADO,
        "DUPLICADO_PERMISO": SolicitudType.DUPLICADO,
        "DUPLICADO_CUVE": SolicitudType.DUPLICADO,
    }
    return _MAP.get(sub_type, SolicitudType.EXPEDICION)


# ─── Helpers (extracted from admin_routes.py) ───────────────────────────────

def _extract_tariff_from_workflow(
    workflow, sub_type: str, code: str = "",
) -> Tuple[int, str]:
    """Extract tariff amount and type from a workflow class.

    Uses multiple key strategies to find the right amount in fixed_amounts:
    1. Exact sub_type match (case-insensitive)
    2. Code-derived parts (e.g. VEHICULO_DUPLICADO_PERMISO → DUPLICADO)
    3. Standard fallbacks (expedicion, renovacion)
    4. First non-zero value as representative
    """
    tariff_config = getattr(workflow, '_tariff_config', None)
    tariff_type = "FIXED"

    if tariff_config:
        config_type = getattr(tariff_config, 'tariff_type', None)
        if config_type:
            tariff_type = config_type.value if hasattr(config_type, 'value') else str(config_type)

        # For non-fixed types, amount is computed dynamically
        if tariff_type in ("PERCENTAGE", "RBC", "NOTA_INGRESO"):
            # Extract base amount from fixed_amounts if available
            fixed_amounts = getattr(tariff_config, 'fixed_amounts', {})
            if fixed_amounts:
                amount = fixed_amounts.get(sub_type) or fixed_amounts.get(sub_type.lower())
                if amount:
                    return (amount, tariff_type)
                # Use first non-zero as representative
                for v in fixed_amounts.values():
                    if v and v > 0:
                        return (v, tariff_type)
            return (0, tariff_type)

        if tariff_type == "FIXED" and hasattr(tariff_config, 'fixed_amounts'):
            fixed_amounts = tariff_config.fixed_amounts
            # Strategy 1: exact sub_type match
            amount = fixed_amounts.get(sub_type) or fixed_amounts.get(sub_type.lower())
            if amount and amount > 0:
                return (amount, tariff_type)

            # Strategy 2: code-derived parts
            # e.g. code=VEHICULO_DUPLICADO_PERMISO → try DUPLICADO_PERMISO, DUPLICADO
            if code and '_' in code:
                code_parts = code.split('_', 1)[1].split('_')
                for part in code_parts:
                    amount = fixed_amounts.get(part) or fixed_amounts.get(part.lower())
                    if amount and amount > 0:
                        return (amount, tariff_type)

            # Strategy 3: standard fallbacks
            for key in ('expedicion', 'renovacion'):
                amount = fixed_amounts.get(key)
                if amount and amount > 0:
                    return (amount, tariff_type)

            # Strategy 4: first non-zero as representative
            for v in fixed_amounts.values():
                if v and v > 0:
                    return (v, tariff_type)

            return (0, tariff_type)

    if hasattr(workflow, 'TARIFF'):
        return (getattr(workflow, 'TARIFF', 0), tariff_type)

    if hasattr(workflow, 'TARIFFS'):
        tariffs_dict = workflow.TARIFFS
        amount = tariffs_dict.get(sub_type) or tariffs_dict.get(sub_type.lower())
        if amount and amount > 0:
            return (amount, tariff_type)
        # Code-derived fallback
        if code and '_' in code:
            for part in code.split('_', 1)[1].split('_'):
                amount = tariffs_dict.get(part) or tariffs_dict.get(part.lower())
                if amount and amount > 0:
                    return (amount, tariff_type)
        return (0, tariff_type)

    return (0, tariff_type)


def _extract_document_requirements(workflow, sub_type: str) -> List[Dict[str, Any]]:
    """Extract document requirements from a workflow class.

    Creates a minimal WorkflowContext so that:
    1. solicitud_type is a proper SolicitudType enum (not uppercase string)
    2. context.sub_type is set for workflows that branch on it (vehiculos)
    """
    requirements = []
    try:
        if hasattr(workflow, 'get_document_requirements_legacy'):
            docs = workflow.get_document_requirements_legacy(sub_type)
        elif hasattr(workflow, 'get_document_requirements'):
            from app.modules.service_requests.workflows.workflow_interface import WorkflowContext
            from app.modules.service_requests.models.enums import SolicitudType, WorkflowCode

            solicitud_type = _map_sub_type_to_solicitud_type(sub_type)
            wf_code = getattr(workflow, 'workflow_code', WorkflowCode.RESIDENCIA_PRIMERA_VEZ)

            # Minimal context: only sub_type matters for document branching.
            # service_request_id and user_id are dummy — never used in extraction.
            minimal_context = WorkflowContext(
                service_request_id=uuid4(),
                user_id=uuid4(),
                workflow_code=wf_code,
                solicitud_type=solicitud_type,
                sub_type=sub_type,
            )
            docs = workflow.get_document_requirements(
                solicitud_type, context=minimal_context,
            )
        else:
            return requirements

        for doc in docs:
            req = {
                "document_code": doc.document_code,
                "document_name_es": doc.document_name_es,
                "is_required": doc.is_required,
                "display_order": doc.display_order,
                "condition_type": doc.condition_type.value if hasattr(doc.condition_type, 'value') else str(doc.condition_type),
                "condition_value": doc.condition_value if hasattr(doc, 'condition_value') else {},
                "instructions_es": doc.instructions_es if hasattr(doc, 'instructions_es') else None,
                "extraction_schema_key": doc.schema_key if hasattr(doc, 'schema_key') else None,
            }
            requirements.append(req)
    except Exception as e:
        logger.warning(f"Failed to extract documents for {sub_type}: {e}")

    return requirements


def _resolve_workflow_codes(workflow, base_code) -> List[Tuple[str, str]]:
    """
    Resolve all (code, sub_type) pairs for a workflow class.

    Priority order:
    B) get_all_workflow_codes() — definitive code list (preferred)
    A) allowed_sub_types + get_workflow_code_for_subtype — legacy mapping
    C) Single-code from base_code — fallback

    Pattern B is checked FIRST because allowed_sub_types may contain
    solicitud types (e.g. REGISTRO_NUEVO) that don't match the
    get_workflow_code_for_subtype mapping (e.g. OBRA→CONTRATO_OBRA).
    get_all_workflow_codes() is always authoritative.
    """
    # Pattern B: get_all_workflow_codes() — multi-code workflows (preferred)
    codes = workflow.get_all_workflow_codes()
    if len(codes) > 1:
        # Build reverse map for accurate sub_type derivation:
        # sub_type is used for tariff/document extraction, so correctness matters.
        # Collision detection: if N sub_types map to the same code, it means
        # allowed_sub_types is a different dimension (e.g. solicitud types vs
        # contract types in ContratoWorkflow). Skip collided entries.
        reverse_map = {}
        seen_codes: Dict[Any, List[str]] = {}
        for sub in workflow.allowed_sub_types:
            try:
                mapped_code = workflow.get_workflow_code_for_subtype(sub)
                if mapped_code not in seen_codes:
                    seen_codes[mapped_code] = []
                seen_codes[mapped_code].append(sub)
            except Exception:
                pass
        # Only keep 1:1 mappings (no collisions)
        for code_key, subs in seen_codes.items():
            if len(subs) == 1:
                reverse_map[code_key] = subs[0]

        pairs = []
        for wf_code in codes:
            # Use reverse_map if available, else strip category prefix
            # split('_', 1)[1] gives full suffix: CONTRATO_JOINT_VENTURE → JOINT_VENTURE
            sub = reverse_map.get(
                wf_code,
                wf_code.value.split('_', 1)[1] if '_' in wf_code.value else wf_code.value,
            )
            pairs.append((wf_code.value, sub))
        return pairs

    # Pattern A: allowed_sub_types (single-code workflows with sub-types)
    allowed_sub_types = workflow.allowed_sub_types
    if allowed_sub_types:
        pairs = []
        for sub_type in allowed_sub_types:
            wf_code = workflow.get_workflow_code_for_subtype(sub_type)
            pairs.append((wf_code.value, sub_type))
        return pairs

    # Pattern C: single code
    code_val = base_code.value
    sub = code_val.rsplit('_', 1)[-1] if '_' in code_val else code_val
    return [(code_val, sub)]


# ─── Main sync function ────────────────────────────────────────────────────

async def sync_all_workflows(
    db_connection,
    *,
    dry_run: bool = False,
    delete_existing: bool = False,
) -> WorkflowSyncResult:
    """
    Single sync function: PredefinedWorkflow classes → all DB tables.

    Called at startup (dry_run=False) and from admin endpoint.

    Steps:
    1. Optionally delete existing data (admin only, dangerous)
    2. Resolve all codes from workflow_engine (3 patterns)
    3. UPSERT workflows table (ON CONFLICT DO UPDATE)
    4. UPSERT tariffs (ON CONFLICT by workflow_code)
    5. UPSERT document requirements
    6. Deactivate orphaned predefined workflows
    7. Sync menu_mapping (INSERT if missing)
    8. Sync display_config (batch INSERT, no N+1)
    9. Invalidate Redis caches
    """
    from app.modules.service_requests.services.workflow_engine import workflow_engine

    result = WorkflowSyncResult()

    # Step 1: Optionally delete existing data
    if delete_existing:
        if dry_run:
            result.details.append({
                "action": "would_delete_existing",
                "note": "All existing workflows would be deleted",
            })
        else:
            try:
                await db_connection.execute("DELETE FROM workflow_tariffs")
                await db_connection.execute("DELETE FROM workflow_document_requirements")
                deleted = await db_connection.execute("DELETE FROM workflows")
                count = int(deleted.split()[-1]) if deleted else 0
                result.details.append({"action": "deleted_existing", "count": count})
            except Exception as e:
                result.errors.append(f"Error deleting existing workflows: {e}")
                return result

    # Step 2-5: Iterate workflows and sync each code
    all_workflows = workflow_engine.get_all_workflows()
    synced_codes: Set[str] = set()

    # Build display names and parent mapping dynamically from workflow classes
    subtype_names_es: Dict[str, str] = {}
    subtype_parent_mapping: Dict[str, Optional[str]] = {}
    for _base_code, wf in all_workflows.items():
        if hasattr(wf, 'get_subtype_display_names'):
            subtype_names_es.update(wf.get_subtype_display_names())
        if hasattr(wf, 'get_parent_mapping'):
            subtype_parent_mapping.update(wf.get_parent_mapping())

    for base_code, workflow in all_workflows.items():
        try:
            category = workflow.category.value if hasattr(workflow, 'category') else 'GENERAL'
            entity_code = workflow.entity_code.value if hasattr(workflow, 'entity_code') else 'GENERAL'
            requires_appointment = getattr(workflow, 'requires_appointment', False)
            requires_agent = getattr(workflow, 'requires_agent_review', True)
            sla_hours = getattr(workflow, 'sla_hours', 48)

            codes_to_sync = _resolve_workflow_codes(workflow, base_code)

            for code, sub_type in codes_to_sync:
                if code in synced_codes:
                    continue

                try:
                    name_es = subtype_names_es.get(code, code.replace('_', ' ').title())
                    parent_code = subtype_parent_mapping.get(code)
                    # All predefined workflows are real workflows, NOT category headers.
                    # is_parent=True is reserved for generic "category" rows (e.g. "PASAPORTE").
                    # The frontend filters out is_parent=True, so we must set False here.
                    is_parent = False
                    tariff_amount, tariff_type = _extract_tariff_from_workflow(workflow, sub_type, code)

                    if dry_run:
                        result.details.append({
                            "action": "would_sync",
                            "workflow_code": code,
                            "sub_type": sub_type,
                            "name_es": name_es,
                            "parent_code": parent_code,
                            "tariff_amount": tariff_amount,
                            "tariff_type": tariff_type,
                        })
                        synced_codes.add(code)
                        result.workflows_synced += 1
                        continue

                    # ── Step 3: UPSERT workflow ──
                    # No WHERE filter: predefined workflows ALWAYS take over,
                    # even if an old row exists with is_generic=TRUE.
                    row = await db_connection.fetchrow(
                        """
                        INSERT INTO workflows (
                            code, name_es, description_es, category, entity_code,
                            workflow_type, requires_agent_validation, requires_appointment,
                            is_generic, is_active, sla_hours, parent_workflow_code, is_parent
                        ) VALUES ($1, $2, $3, $4, $5, 'standard', $6, $7, FALSE, TRUE, $8, $9, $10)
                        ON CONFLICT (code) DO UPDATE SET
                            name_es = EXCLUDED.name_es,
                            description_es = EXCLUDED.description_es,
                            category = EXCLUDED.category,
                            entity_code = EXCLUDED.entity_code,
                            requires_agent_validation = EXCLUDED.requires_agent_validation,
                            requires_appointment = EXCLUDED.requires_appointment,
                            sla_hours = EXCLUDED.sla_hours,
                            parent_workflow_code = EXCLUDED.parent_workflow_code,
                            is_parent = EXCLUDED.is_parent,
                            is_generic = EXCLUDED.is_generic,
                            is_active = TRUE,
                            updated_at = NOW()
                        RETURNING (xmax = 0) AS is_new
                        """,
                        code, name_es, f"Trámite de {name_es}",
                        category, entity_code,
                        requires_agent, requires_appointment,
                        sla_hours, parent_code, is_parent,
                    )

                    if row and row['is_new']:
                        result.workflows_created += 1
                    elif row:
                        result.workflows_updated += 1

                    # Workflow row secured — add to synced_codes IMMEDIATELY.
                    # Tariff/document failures must NOT cause orphan deletion.
                    synced_codes.add(code)
                    result.workflows_synced += 1

                    # ── Step 4: REPLACE tariffs (delete stale + insert fresh) ──
                    # Old data may have solicitud_type='renovacion'/'duplicado' which
                    # the previous SELECT-by-expedicion approach never cleaned up.
                    try:
                        await db_connection.execute(
                            "DELETE FROM workflow_tariffs WHERE workflow_code = $1",
                            code,
                        )
                        await db_connection.execute(
                            """
                            INSERT INTO workflow_tariffs (
                                workflow_code, solicitud_type, amount, tariff_type,
                                currency, is_active
                            ) VALUES ($1, 'expedicion', $2, $3, 'XAF', true)
                            """,
                            code, tariff_amount, tariff_type,
                        )
                        result.tariffs_created += 1
                        result.tariffs_synced += 1
                    except Exception as e:
                        result.errors.append(f"Tariff error for {code}: {e}")

                    # ── Step 5: REPLACE document requirements (delete stale + insert fresh) ──
                    try:
                        await db_connection.execute(
                            "DELETE FROM workflow_document_requirements WHERE workflow_code = $1",
                            code,
                        )
                        doc_requirements = _extract_document_requirements(workflow, sub_type)
                        for doc_req in doc_requirements:
                            condition_value = doc_req.get('condition_value') or {}
                            condition_json = json.dumps(condition_value) if isinstance(condition_value, dict) else condition_value

                            await db_connection.execute(
                                """
                                INSERT INTO workflow_document_requirements (
                                    workflow_code, document_code, document_name_es,
                                    is_required, display_order, condition_type,
                                    condition_value, instructions_es, extraction_schema_key,
                                    is_active
                                ) VALUES ($1, $2, $3, $4, $5, $6::document_condition_type_enum,
                                          $7::jsonb, $8, $9, true)
                                """,
                                code, doc_req['document_code'],
                                doc_req['document_name_es'],
                                doc_req['is_required'],
                                doc_req['display_order'],
                                doc_req['condition_type'].lower(),
                                condition_json,
                                doc_req.get('instructions_es'),
                                doc_req.get('extraction_schema_key'),
                            )
                            result.documents_created += 1
                            result.documents_synced += 1
                    except Exception as e:
                        result.errors.append(f"Document error for {code}: {e}")

                except Exception as e:
                    result.errors.append(f"Error syncing {code}: {e}")

        except Exception as e:
            result.errors.append(f"Error processing workflow {base_code.value}: {e}")

    # Step 6: Delete orphaned predefined workflows
    # If a code is removed from Python, delete it from DB. If it's re-added
    # later, the sync will recreate it. No point keeping dead rows.
    if not dry_run and synced_codes:
        try:
            # Delete dependent rows first (FK constraints)
            await db_connection.execute("""
                DELETE FROM workflow_document_requirements
                WHERE workflow_code IN (
                    SELECT code FROM workflows
                    WHERE is_generic = FALSE AND code != ALL($1)
                )
            """, list(synced_codes))
            await db_connection.execute("""
                DELETE FROM workflow_tariffs
                WHERE workflow_code IN (
                    SELECT code FROM workflows
                    WHERE is_generic = FALSE AND code != ALL($1)
                )
            """, list(synced_codes))
            await db_connection.execute("""
                DELETE FROM workflow_display_config
                WHERE workflow_code IN (
                    SELECT code FROM workflows
                    WHERE is_generic = FALSE AND code != ALL($1)
                )
            """, list(synced_codes))
            # Delete the workflows themselves
            orphaned = await db_connection.fetch("""
                DELETE FROM workflows
                WHERE is_generic = FALSE
                  AND code != ALL($1)
                RETURNING code
            """, list(synced_codes))
            if orphaned:
                orphan_codes = [r['code'] for r in orphaned]
                result.workflows_deactivated = len(orphan_codes)
                result.details.append({
                    "action": "deleted_orphans",
                    "codes": orphan_codes,
                })
                logger.info(f"Deleted {len(orphan_codes)} orphaned workflows: {orphan_codes}")
        except Exception as e:
            result.errors.append(f"Error deleting orphans: {e}")

    # Steps 7-9: Menu mapping + display config + cache (skip in dry_run)
    if not dry_run:
        await _sync_menu_and_display_config(db_connection, result)

    logger.info(
        f"Workflow sync complete: "
        f"{result.workflows_synced} workflows "
        f"({result.workflows_created} new, {result.workflows_updated} updated, "
        f"{result.workflows_deactivated} deactivated), "
        f"{result.tariffs_synced} tariffs, {result.documents_synced} docs, "
        f"{result.menu_mappings_synced} menus, {result.display_configs_synced} display configs"
    )

    return result


# ─── Menu + Display Config sync (substep) ──────────────────────────────────

async def _sync_menu_and_display_config(
    db_connection,
    result: WorkflowSyncResult,
) -> None:
    """
    Steps 7-9: Sync menu_mapping, display_config, invalidate caches.

    Uses ON CONFLICT DO NOTHING — never overwrites admin customizations.
    """
    from app.modules.menu_config.services.menu_config_service import (
        get_workflow_menu_metadata,
        get_workflow_category_index,
        invalidate_workflow_indexes,
    )

    # Force rebuild indexes to pick up any new workflow registrations
    invalidate_workflow_indexes()
    category_index = get_workflow_category_index()
    menu_metadata = get_workflow_menu_metadata()

    # Step 7: Sync workflow_menu_mapping (one row per menu_group)
    display_order_counter = 0
    for menu_group, meta in menu_metadata.items():
        pattern = f"{menu_group}_%"
        menu_group_id = menu_group.lower().replace('_', '-')

        try:
            row = await db_connection.fetchrow(
                """
                INSERT INTO workflow_menu_mapping (
                    workflow_pattern, menu_group_id, menu_title_key, menu_icon,
                    display_order, include_appointments, permission_prefix, is_active
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE)
                ON CONFLICT (workflow_pattern) DO NOTHING
                RETURNING id
                """,
                pattern, menu_group_id, meta["title_key"], meta["icon"],
                display_order_counter, meta["has_appointments"], "service_requests",
            )
            if row:
                result.menu_mappings_created += 1
            display_order_counter += 1
            result.menu_mappings_synced += 1
        except Exception as e:
            logger.warning(f"Failed to sync menu mapping for {menu_group}: {e}")

    # Step 8: Sync workflow_display_config (batch — no N+1)
    list_columns = json.dumps(_DEFAULT_LIST_COLUMNS)
    preview_sections = json.dumps(_DEFAULT_PREVIEW_SECTIONS)
    codes = list(category_index.keys())

    if codes:
        try:
            # Single batch INSERT for all missing codes
            inserted = await db_connection.fetch(
                """
                INSERT INTO workflow_display_config (workflow_code, list_columns, preview_sections)
                SELECT code, $2::jsonb, $3::jsonb
                FROM unnest($1::text[]) AS code
                WHERE NOT EXISTS (
                    SELECT 1 FROM workflow_display_config wdc WHERE wdc.workflow_code = code
                )
                RETURNING workflow_code
                """,
                codes, list_columns, preview_sections,
            )
            result.display_configs_created = len(inserted)
            result.display_configs_synced = len(codes)
        except Exception as e:
            logger.warning(f"Failed to batch sync display configs: {e}")

    # Step 9: Invalidate caches
    try:
        await invalidate_workflow_mappings_cache()
        cache = get_menu_cache()
        # Batch delete all display config cache keys
        for code in codes:
            await cache.delete(CacheKeys.display_config(code))
    except Exception as e:
        logger.warning(f"Cache invalidation warning (non-critical): {e}")
