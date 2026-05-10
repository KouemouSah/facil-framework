"""Config Rules Repository — Data access for fiscal_config_rules."""

import json
import logging
from typing import Dict, List, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


class ConfigRulesRepository:
    """Repository for fiscal_config_rules CRUD + recompute."""

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    async def list_rules(
        conn,
        config_type: Optional[str] = None,
        bundle_id: Optional[UUID] = None,
        is_enabled: Optional[bool] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict], int]:
        """List config rules with filters, enriched with bundle/ministry names."""
        conditions = []
        params = []
        idx = 1

        if config_type:
            conditions.append(f"fcr.config_type = ${idx}")
            params.append(config_type)
            idx += 1

        if bundle_id:
            conditions.append(f"fcr.bundle_id = ${idx}")
            params.append(bundle_id)
            idx += 1

        if is_enabled is not None:
            conditions.append(f"fcr.is_enabled = ${idx}")
            params.append(is_enabled)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        # Count
        count_row = await conn.fetchrow(
            f"SELECT COUNT(*) as total FROM fiscal_config_rules fcr {where}",
            *params,
        )
        total = count_row["total"]

        # Data with JOINs
        offset = (page - 1) * page_size
        params_data = params + [page_size, offset]
        rows = await conn.fetch(f"""
            SELECT fcr.*,
                   sb.name_es as bundle_name,
                   m.name_es as ministry_name
            FROM fiscal_config_rules fcr
            LEFT JOIN service_bundles sb ON fcr.bundle_id = sb.id
            LEFT JOIN ministries m ON fcr.ministry_id = m.id
            {where}
            ORDER BY fcr.specificity DESC, fcr.config_type, fcr.created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """, *params_data)

        return [dict(r) for r in rows], total

    @staticmethod
    async def get_rule(conn, rule_id: UUID) -> Optional[Dict]:
        """Get a single config rule by ID."""
        row = await conn.fetchrow("""
            SELECT fcr.*,
                   sb.name_es as bundle_name,
                   m.name_es as ministry_name
            FROM fiscal_config_rules fcr
            LEFT JOIN service_bundles sb ON fcr.bundle_id = sb.id
            LEFT JOIN ministries m ON fcr.ministry_id = m.id
            WHERE fcr.id = $1
        """, rule_id)
        return dict(row) if row else None

    @staticmethod
    async def get_effective_for_item(
        conn, bundle_id: UUID, fee_type: str,
        ministry_id: Optional[int], item_id: UUID
    ) -> Dict:
        """Get resolved effective config for a specific item (debug/preview)."""
        penalty_row = await conn.fetchrow("""
            SELECT fcr.id, fcr.config, fcr.specificity, fcr.name_es
            FROM fiscal_config_rules fcr
            WHERE fcr.config_type = 'penalty'
              AND fcr.is_enabled = true
              AND (fcr.bundle_id = $1 OR fcr.bundle_id IS NULL)
              AND (fcr.fee_type = $2 OR fcr.fee_type IS NULL)
              AND (fcr.ministry_id = $3 OR fcr.ministry_id IS NULL)
              AND (fcr.item_id = $4 OR fcr.item_id IS NULL)
              AND fcr.effective_from <= CURRENT_DATE
              AND (fcr.effective_to IS NULL OR fcr.effective_to >= CURRENT_DATE)
            ORDER BY fcr.specificity DESC
            LIMIT 1
        """, bundle_id, fee_type, ministry_id, item_id)

        deadline_row = await conn.fetchrow("""
            SELECT fcr.id, fcr.config, fcr.specificity, fcr.name_es
            FROM fiscal_config_rules fcr
            WHERE fcr.config_type = 'deadline'
              AND fcr.is_enabled = true
              AND (fcr.bundle_id = $1 OR fcr.bundle_id IS NULL)
              AND (fcr.fee_type = $2 OR fcr.fee_type IS NULL)
              AND (fcr.ministry_id = $3 OR fcr.ministry_id IS NULL)
              AND (fcr.item_id = $4 OR fcr.item_id IS NULL)
              AND fcr.effective_from <= CURRENT_DATE
              AND (fcr.effective_to IS NULL OR fcr.effective_to >= CURRENT_DATE)
            ORDER BY fcr.specificity DESC
            LIMIT 1
        """, bundle_id, fee_type, ministry_id, item_id)

        return {
            "penalty": dict(penalty_row) if penalty_row else None,
            "deadline": dict(deadline_row) if deadline_row else None,
        }

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    @staticmethod
    async def create_rule(conn, data: Dict, user_id: Optional[UUID] = None) -> Dict:
        """Create a config rule. Trigger auto-recomputes affected items."""
        fee_type = data.get("fee_type")
        if hasattr(fee_type, "value"):
            fee_type = fee_type.value
        config_type = data.get("config_type")
        if hasattr(config_type, "value"):
            config_type = config_type.value

        row = await conn.fetchrow("""
            INSERT INTO fiscal_config_rules
                (config_type, bundle_id, fee_type, ministry_id, item_id,
                 effective_from, effective_to, is_enabled, config,
                 name_es, description, created_by, updated_by)
            VALUES ($1, $2, $3, $4, $5,
                    COALESCE($6, CURRENT_DATE), $7, $8, $9,
                    $10, $11, $12, $12)
            RETURNING *
        """,
            config_type,
            data.get("bundle_id"),
            fee_type,
            data.get("ministry_id"),
            data.get("item_id"),
            data.get("effective_from"),
            data.get("effective_to"),
            data.get("is_enabled", True),
            json.dumps(data.get("config", {})) if isinstance(data.get("config", {}), dict) else data.get("config", "{}"),
            data.get("name_es"),
            data.get("description"),
            user_id,
        )
        # Re-query with JOINs for enriched response
        return await ConfigRulesRepository.get_rule(conn, row["id"])

    @staticmethod
    async def update_rule(
        conn, rule_id: UUID, data: Dict, user_id: Optional[UUID] = None
    ) -> Optional[Dict]:
        """Update a config rule. Trigger auto-recomputes affected items."""
        sets = []
        params = []
        idx = 1

        for field in ["effective_from", "effective_to", "is_enabled",
                       "config", "name_es", "description"]:
            if field in data:
                value = data[field]
                # JSONB columns need json.dumps() — asyncpg expects str, not dict
                if field == "config" and isinstance(value, dict):
                    value = json.dumps(value)
                sets.append(f"{field} = ${idx}")
                params.append(value)
                idx += 1

        if not sets:
            return await ConfigRulesRepository.get_rule(conn, rule_id)

        sets.append(f"updated_by = ${idx}")
        params.append(user_id)
        idx += 1

        sets.append("updated_at = now()")

        params.append(rule_id)
        row = await conn.fetchrow(f"""
            UPDATE fiscal_config_rules
            SET {', '.join(sets)}
            WHERE id = ${idx}
            RETURNING *
        """, *params)

        if not row:
            return None
        return await ConfigRulesRepository.get_rule(conn, rule_id)

    @staticmethod
    async def delete_rule(conn, rule_id: UUID) -> bool:
        """Delete a config rule. Trigger auto-recomputes affected items."""
        result = await conn.execute(
            "DELETE FROM fiscal_config_rules WHERE id = $1", rule_id
        )
        return result == "DELETE 1"

    # ------------------------------------------------------------------
    # Recompute
    # ------------------------------------------------------------------

    @staticmethod
    async def recompute(conn, bundle_id: Optional[UUID] = None) -> int:
        """Manually trigger recompute (admin action)."""
        if bundle_id:
            row = await conn.fetchrow(
                "SELECT recompute_effective_configs($1) as affected", bundle_id
            )
        else:
            row = await conn.fetchrow(
                "SELECT recompute_effective_configs() as affected"
            )
        return row["affected"]
