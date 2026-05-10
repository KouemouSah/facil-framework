"""Bundle Repository — Data access layer for commerce zones and service bundles."""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


class BundleRepository:
    """Repository for commerce_zones, service_bundles, and service_bundle_items."""

    # ------------------------------------------------------------------
    # Commerce Zones
    # ------------------------------------------------------------------

    @staticmethod
    async def list_zones(conn) -> List[Dict]:
        """List all commerce zones sorted by display_order."""
        rows = await conn.fetch("""
            SELECT id, zone_code, zone_tier, zone_rank,
                   name_es, description_es, display_order,
                   created_at, updated_at
            FROM commerce_zones
            ORDER BY display_order
        """)
        return [dict(r) for r in rows]

    @staticmethod
    async def get_zone_by_code(conn, zone_code: str) -> Optional[Dict]:
        """Get a single zone by zone_code (e.g. 'A1')."""
        row = await conn.fetchrow("""
            SELECT id, zone_code, zone_tier, zone_rank,
                   name_es, description_es, display_order,
                   created_at, updated_at
            FROM commerce_zones
            WHERE zone_code = $1
        """, zone_code.upper())
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Service Bundles — Read
    # ------------------------------------------------------------------

    @staticmethod
    async def get_bundle_by_commerce_type(conn, commerce_type: str) -> Optional[Dict]:
        """Get a single active bundle by commerce_type."""
        row = await conn.fetchrow("""
            SELECT sb.*,
                   COALESCE(stats.item_count, 0) as item_count,
                   COALESCE(stats.zone_count, 0) as zone_count
            FROM service_bundles sb
            LEFT JOIN LATERAL (
                SELECT COUNT(*) as item_count,
                       COUNT(DISTINCT zone_id) as zone_count
                FROM service_bundle_items
                WHERE bundle_id = sb.id AND is_active = true
            ) stats ON true
            WHERE sb.commerce_type = $1 AND sb.is_active = true
            LIMIT 1
        """, commerce_type)
        return dict(row) if row else None

    @staticmethod
    async def list_bundles(
        conn,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        commerce_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict], int]:
        """List bundles with pagination, filters, and item/zone counts."""
        conditions = []
        params = []
        idx = 1

        if is_active is not None:
            conditions.append(f"sb.is_active = ${idx}")
            params.append(is_active)
            idx += 1

        if search:
            conditions.append(f"(sb.name_es ILIKE ${idx} OR sb.bundle_code ILIKE ${idx})")
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{escaped}%")
            idx += 1

        if commerce_type:
            conditions.append(f"sb.commerce_type = ${idx}")
            params.append(commerce_type)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        # Count
        count_row = await conn.fetchrow(
            f"SELECT COUNT(*) as total FROM service_bundles sb {where}",
            *params,
        )
        total = count_row["total"]

        # Data with item/zone counts
        offset = (page - 1) * page_size
        params_data = params + [page_size, offset]
        rows = await conn.fetch(f"""
            SELECT sb.*,
                   COALESCE(stats.item_count, 0) as item_count,
                   COALESCE(stats.zone_count, 0) as zone_count
            FROM service_bundles sb
            LEFT JOIN LATERAL (
                SELECT COUNT(*) as item_count,
                       COUNT(DISTINCT zone_id) as zone_count
                FROM service_bundle_items
                WHERE bundle_id = sb.id AND is_active = true
            ) stats ON true
            {where}
            ORDER BY sb.bundle_code
            LIMIT ${idx} OFFSET ${idx + 1}
        """, *params_data)

        return [dict(r) for r in rows], total

    @staticmethod
    async def get_bundle(conn, bundle_id: UUID) -> Optional[Dict]:
        """Get a single bundle by ID with item/zone counts."""
        row = await conn.fetchrow("""
            SELECT sb.*,
                   COALESCE(stats.item_count, 0) as item_count,
                   COALESCE(stats.zone_count, 0) as zone_count
            FROM service_bundles sb
            LEFT JOIN LATERAL (
                SELECT COUNT(*) as item_count,
                       COUNT(DISTINCT zone_id) as zone_count
                FROM service_bundle_items
                WHERE bundle_id = sb.id AND is_active = true
            ) stats ON true
            WHERE sb.id = $1
        """, bundle_id)
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Bundle Items — Read
    # ------------------------------------------------------------------

    @staticmethod
    async def get_bundle_items(
        conn, bundle_id: UUID, zone_id: UUID, language: str = "es"
    ) -> List[Dict]:
        """Get items for a bundle+zone with enriched service/ministry names.

        Joins entity_translations for service and ministry names when language != 'es'.
        """
        lang = language if language in ("es", "fr", "en") else "es"
        if lang == "es":
            # Fast path: no translation JOINs needed
            rows = await conn.fetch("""
                SELECT sbi.id, sbi.bundle_id, sbi.fiscal_service_id, sbi.zone_id,
                       sbi.ministry_id, sbi.amount, sbi.fee_type,
                       sbi.is_fixed_across_zones,
                       sbi.display_order, sbi.notes, sbi.is_active,
                       sbi.effective_penalty, sbi.effective_deadline,
                       sbi.config_resolved_at, sbi.requires_document,
                       sbi.document_template_id,
                       fs.service_code, fs.name_es as service_name,
                       m.name_es as ministry_name
                FROM service_bundle_items sbi
                JOIN fiscal_services fs ON sbi.fiscal_service_id = fs.id
                LEFT JOIN ministries m ON sbi.ministry_id = m.id
                WHERE sbi.bundle_id = $1 AND sbi.zone_id = $2 AND sbi.is_active = true
                ORDER BY sbi.fee_type, sbi.display_order, fs.service_code
            """, bundle_id, zone_id)
        else:
            rows = await conn.fetch("""
                SELECT sbi.id, sbi.bundle_id, sbi.fiscal_service_id, sbi.zone_id,
                       sbi.ministry_id, sbi.amount, sbi.fee_type,
                       sbi.is_fixed_across_zones,
                       sbi.display_order, sbi.notes, sbi.is_active,
                       sbi.effective_penalty, sbi.effective_deadline,
                       sbi.config_resolved_at, sbi.requires_document,
                       sbi.document_template_id,
                       fs.service_code,
                       COALESCE(et_svc.translation_text, fs.name_es) as service_name,
                       COALESCE(et_min.translation_text, m.name_es) as ministry_name
                FROM service_bundle_items sbi
                JOIN fiscal_services fs ON sbi.fiscal_service_id = fs.id
                LEFT JOIN ministries m ON sbi.ministry_id = m.id
                LEFT JOIN entity_translations et_svc ON
                    et_svc.entity_type = 'service'
                    AND et_svc.entity_code = fs.service_code
                    AND et_svc.field_name = 'name'
                    AND et_svc.language_code = $3
                LEFT JOIN entity_translations et_min ON
                    et_min.entity_type = 'ministry'
                    AND et_min.entity_code = m.ministry_code
                    AND et_min.field_name = 'name'
                    AND et_min.language_code = $3
                WHERE sbi.bundle_id = $1 AND sbi.zone_id = $2 AND sbi.is_active = true
                ORDER BY sbi.fee_type, sbi.display_order, fs.service_code
            """, bundle_id, zone_id, lang)
        return [dict(r) for r in rows]

    @staticmethod
    async def calculate_total(
        conn, bundle_id: UUID, zone_id: UUID
    ) -> Decimal:
        """Calculate total amount for a bundle+zone (all fee types)."""
        row = await conn.fetchrow("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM service_bundle_items
            WHERE bundle_id = $1 AND zone_id = $2 AND is_active = true
        """, bundle_id, zone_id)
        return row["total"]

    @staticmethod
    async def calculate_totals_by_fee_type(
        conn, bundle_id: UUID, zone_id: UUID
    ) -> Dict[str, Decimal]:
        """Calculate sub-totals per fee_type + grand total for a bundle+zone."""
        rows = await conn.fetch("""
            SELECT fee_type, COALESCE(SUM(amount), 0) as subtotal
            FROM service_bundle_items
            WHERE bundle_id = $1 AND zone_id = $2 AND is_active = true
            GROUP BY fee_type
            ORDER BY CASE fee_type
                WHEN 'tesoro' THEN 1
                WHEN 'municipal' THEN 2
                WHEN 'chamber' THEN 3
            END
        """, bundle_id, zone_id)
        result = {r["fee_type"]: r["subtotal"] for r in rows}
        result["grand_total"] = sum(result.values())
        return result

    @staticmethod
    async def get_pricing_matrix(conn, bundle_id: UUID) -> List[Dict]:
        """Get all items across all zones for a bundle (for matrix view)."""
        rows = await conn.fetch("""
            SELECT sbi.id, sbi.bundle_id, sbi.fiscal_service_id, sbi.zone_id,
                   sbi.ministry_id, sbi.amount, sbi.fee_type,
                   sbi.is_fixed_across_zones,
                   sbi.display_order, sbi.notes, sbi.is_active,
                   sbi.effective_penalty, sbi.effective_deadline,
                   sbi.config_resolved_at, sbi.requires_document,
                   sbi.document_template_id,
                   fs.service_code, fs.name_es as service_name,
                   m.name_es as ministry_name
            FROM service_bundle_items sbi
            JOIN fiscal_services fs ON sbi.fiscal_service_id = fs.id
            LEFT JOIN ministries m ON sbi.ministry_id = m.id
            JOIN commerce_zones cz ON sbi.zone_id = cz.id
            WHERE sbi.bundle_id = $1 AND sbi.is_active = true
            ORDER BY sbi.fee_type, sbi.display_order, fs.service_code, cz.display_order
        """, bundle_id)
        return [dict(r) for r in rows]

    @staticmethod
    async def get_zone_totals(conn, bundle_id: UUID) -> List[Dict]:
        """Get total amount per zone for a bundle, including fee_type sub-totals."""
        rows = await conn.fetch("""
            SELECT cz.id, cz.zone_code, cz.zone_tier, cz.zone_rank,
                   cz.name_es, cz.description_es, cz.display_order,
                   cz.created_at, cz.updated_at,
                   COALESCE(SUM(sbi.amount), 0) as total_amount,
                   COUNT(sbi.id) as item_count,
                   COALESCE(SUM(sbi.amount) FILTER (WHERE sbi.fee_type = 'tesoro'), 0) as tesoro_total,
                   COALESCE(SUM(sbi.amount) FILTER (WHERE sbi.fee_type = 'municipal'), 0) as municipal_total,
                   COALESCE(SUM(sbi.amount) FILTER (WHERE sbi.fee_type = 'chamber'), 0) as chamber_total
            FROM commerce_zones cz
            LEFT JOIN service_bundle_items sbi
                ON sbi.zone_id = cz.id AND sbi.bundle_id = $1 AND sbi.is_active = true
            GROUP BY cz.id
            ORDER BY cz.display_order
        """, bundle_id)
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Required Documents (deduced from bundle services)
    # ------------------------------------------------------------------

    @staticmethod
    async def get_required_documents(conn, bundle_id: UUID, language: str = "es") -> List[Dict]:
        """Get distinct documents required by all services in the bundle."""
        lang = language if language in ("es", "fr", "en") else "es"
        if lang == "es":
            rows = await conn.fetch("""
                SELECT DISTINCT dt.id as document_template_id,
                       dt.document_name_es, dt.template_code,
                       sda.is_required_expedition as is_required
                FROM service_bundle_items sbi
                JOIN service_document_assignments sda ON sda.fiscal_service_id = sbi.fiscal_service_id
                JOIN document_templates dt ON dt.id = sda.document_template_id
                WHERE sbi.bundle_id = $1 AND sbi.is_active = true
                ORDER BY dt.document_name_es
            """, bundle_id)
        else:
            rows = await conn.fetch("""
                SELECT DISTINCT dt.id as document_template_id,
                       COALESCE(et_doc.translation_text, dt.document_name_es) as document_name_es,
                       dt.template_code,
                       sda.is_required_expedition as is_required
                FROM service_bundle_items sbi
                JOIN service_document_assignments sda ON sda.fiscal_service_id = sbi.fiscal_service_id
                JOIN document_templates dt ON dt.id = sda.document_template_id
                LEFT JOIN entity_translations et_doc ON
                    et_doc.entity_type = 'document_template'
                    AND et_doc.entity_code = dt.template_code
                    AND et_doc.field_name = 'name'
                    AND et_doc.language_code = $2
                WHERE sbi.bundle_id = $1 AND sbi.is_active = true
                ORDER BY document_name_es
            """, bundle_id, lang)
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Service Bundles — Write
    # ------------------------------------------------------------------

    @staticmethod
    async def create_bundle(conn, data: Dict, user_id: Optional[UUID] = None) -> Dict:
        """Create a new service bundle."""
        processing_mode = data.get("processing_mode", "per_line")
        if hasattr(processing_mode, "value"):
            processing_mode = processing_mode.value
        row = await conn.fetchrow("""
            INSERT INTO service_bundles
                (bundle_code, commerce_type, name_es, description_es, legal_reference,
                 is_active, installment_eligible, max_installments, installment_frequency,
                 public_installment_visible, processing_mode, deadline_month, deadline_day,
                 created_by, updated_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $14)
            RETURNING *
        """,
            data["bundle_code"], data["commerce_type"], data["name_es"],
            data.get("description_es"), data.get("legal_reference"),
            data.get("is_active", True),
            data.get("installment_eligible", False),
            data.get("max_installments", 1),
            data.get("installment_frequency", "monthly"),
            data.get("public_installment_visible", False),
            processing_mode,
            data.get("deadline_month", 4),
            data.get("deadline_day", 30),
            user_id,
        )
        result = dict(row)
        result["item_count"] = 0
        result["zone_count"] = 0
        return result

    @staticmethod
    async def update_bundle(
        conn, bundle_id: UUID, data: Dict, user_id: Optional[UUID] = None
    ) -> Optional[Dict]:
        """Update bundle metadata. Re-queries with real item/zone counts."""
        sets = []
        params = []
        idx = 1

        # Fields that CAN be set to NULL in the database
        nullable_fields = {"description_es", "legal_reference"}

        for field in [
            "bundle_code", "commerce_type", "name_es", "description_es",
            "legal_reference", "is_active", "installment_eligible",
            "max_installments", "installment_frequency",
            "public_installment_visible", "processing_mode",
            "deadline_month", "deadline_day",
        ]:
            if field not in data:
                continue
            value = data[field]
            # Skip None for non-nullable fields (avoid SQL errors)
            if value is None and field not in nullable_fields:
                continue
            sets.append(f"{field} = ${idx}")
            params.append(value)
            idx += 1

        if not sets:
            return await BundleRepository.get_bundle(conn, bundle_id)

        sets.append(f"updated_by = ${idx}")
        params.append(user_id)
        idx += 1

        sets.append("updated_at = now()")

        params.append(bundle_id)
        row = await conn.fetchrow(f"""
            UPDATE service_bundles
            SET {', '.join(sets)}
            WHERE id = ${idx}
            RETURNING *
        """, *params)

        if not row:
            return None
        # Re-query with LATERAL for real item/zone counts
        return await BundleRepository.get_bundle(conn, bundle_id)

    @staticmethod
    async def delete_bundle(conn, bundle_id: UUID) -> bool:
        """Soft delete a bundle (set is_active=false)."""
        result = await conn.execute("""
            UPDATE service_bundles SET is_active = false, updated_at = now()
            WHERE id = $1
        """, bundle_id)
        return result == "UPDATE 1"

    # ------------------------------------------------------------------
    # Bundle Items — Write
    # ------------------------------------------------------------------

    @staticmethod
    async def upsert_item(conn, bundle_id: UUID, data: Dict) -> Dict:
        """Insert or update a bundle item (ON CONFLICT upsert on bundle+service+zone+fee_type)."""
        fee_type = data.get("fee_type", "tesoro")
        # Handle enum values
        if hasattr(fee_type, "value"):
            fee_type = fee_type.value
        row = await conn.fetchrow("""
            INSERT INTO service_bundle_items
                (bundle_id, fiscal_service_id, zone_id, ministry_id,
                 amount, fee_type, is_fixed_across_zones, display_order, notes, is_active)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (bundle_id, fiscal_service_id, zone_id, fee_type)
            DO UPDATE SET
                amount = EXCLUDED.amount,
                ministry_id = EXCLUDED.ministry_id,
                is_fixed_across_zones = EXCLUDED.is_fixed_across_zones,
                display_order = EXCLUDED.display_order,
                notes = EXCLUDED.notes,
                is_active = EXCLUDED.is_active,
                updated_at = now()
            RETURNING *
        """,
            bundle_id,
            data["fiscal_service_id"],
            data["zone_id"],
            data.get("ministry_id"),
            data["amount"],
            fee_type,
            data.get("is_fixed_across_zones", False),
            data.get("display_order", 0),
            data.get("notes"),
            data.get("is_active", True),
        )
        return dict(row)

    @staticmethod
    async def delete_item(conn, item_id: UUID) -> Tuple[bool, Optional[UUID]]:
        """Delete a bundle item. Returns (success, bundle_id) for cache invalidation."""
        row = await conn.fetchrow(
            "DELETE FROM service_bundle_items WHERE id = $1 RETURNING bundle_id",
            item_id,
        )
        if row:
            return True, row["bundle_id"]
        return False, None

    @staticmethod
    async def copy_zone_prices(
        conn,
        bundle_id: UUID,
        source_zone_id: UUID,
        target_zone_id: UUID,
        multiplier: Decimal = Decimal("1.0"),
    ) -> int:
        """Copy all item prices from one zone to another with optional multiplier."""
        result = await conn.execute("""
            INSERT INTO service_bundle_items
                (bundle_id, fiscal_service_id, zone_id, ministry_id,
                 amount, fee_type, is_fixed_across_zones, display_order, notes, is_active)
            SELECT bundle_id, fiscal_service_id, $3, ministry_id,
                   ROUND(amount * $4, 2), fee_type, is_fixed_across_zones, display_order, notes, is_active
            FROM service_bundle_items
            WHERE bundle_id = $1 AND zone_id = $2 AND is_active = true
            ON CONFLICT (bundle_id, fiscal_service_id, zone_id, fee_type)
            DO UPDATE SET
                amount = EXCLUDED.amount,
                ministry_id = EXCLUDED.ministry_id,
                updated_at = now()
        """, bundle_id, source_zone_id, target_zone_id, multiplier)
        # Parse "INSERT 0 N" or "INSERT N N"
        try:
            return int(result.split()[-1])
        except (IndexError, ValueError):
            return 0
