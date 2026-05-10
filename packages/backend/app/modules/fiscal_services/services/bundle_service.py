"""Bundle Service — Business logic for service bundles and zone-based pricing."""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from app.core.cache import get_services_cache
from app.modules.fiscal_services.repositories.bundle_repository import BundleRepository

logger = logging.getLogger(__name__)

CACHE_TTL = 3600  # 1 hour for semi-static bundle data


class BundleService:
    """Service layer for bundles — caching, business rules, installment preview."""

    # ------------------------------------------------------------------
    # Zones
    # ------------------------------------------------------------------

    @staticmethod
    async def list_zones(conn) -> List[Dict]:
        """List all zones (cached)."""
        cache = get_services_cache()
        cache_key = "bundle:zones:all"
        cached = await cache.get(cache_key)
        if cached:
            return cached

        zones = await BundleRepository.list_zones(conn)
        await cache.set(cache_key, zones, ttl=CACHE_TTL)
        return zones

    @staticmethod
    async def list_commerce_types(conn) -> List[Dict]:
        """List active commerce types (cached 1h)."""
        cache = get_services_cache()
        cache_key = "bundle:commerce_types"
        cached = await cache.get(cache_key)
        if cached:
            return cached

        rows = await conn.fetch("""
            SELECT sb.commerce_type, sb.name_es, sb.bundle_code, sb.id,
                   sb.description_es, sb.installment_eligible
            FROM service_bundles sb
            WHERE sb.is_active = true
            ORDER BY sb.name_es
        """)
        result = [dict(r) for r in rows]
        await cache.set(cache_key, result, ttl=CACHE_TTL)
        return result

    # ------------------------------------------------------------------
    # Bundles — Read
    # ------------------------------------------------------------------

    @staticmethod
    async def list_bundles(
        conn,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        commerce_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ):
        """List bundles (no cache — paginated with filters)."""
        return await BundleRepository.list_bundles(
            conn, is_active=is_active, search=search,
            commerce_type=commerce_type, page=page, page_size=page_size,
        )

    @staticmethod
    async def get_bundle(conn, bundle_id: UUID) -> Optional[Dict]:
        """Get bundle detail."""
        return await BundleRepository.get_bundle(conn, bundle_id)

    # ------------------------------------------------------------------
    # Pricing
    # ------------------------------------------------------------------

    @staticmethod
    async def get_bundle_pricing(conn, bundle_id: UUID, zone_id: UUID) -> Dict:
        """Get bundle items + total for a specific zone (cached).

        Total is computed from items in Python — avoids a second SQL query.
        """
        cache = get_services_cache()
        cache_key = f"bundle:{bundle_id}:zone:{zone_id}"
        cached = await cache.get(cache_key)
        if cached:
            return cached

        items = await BundleRepository.get_bundle_items(conn, bundle_id, zone_id)
        total = sum(item["amount"] for item in items)

        # Calculate sub-totals by fee_type
        fee_totals = {"tesoro": Decimal("0"), "municipal": Decimal("0"), "chamber": Decimal("0")}
        for item in items:
            ft = item.get("fee_type", "tesoro")
            fee_totals[ft] = fee_totals.get(ft, Decimal("0")) + item["amount"]
        fee_totals["grand_total"] = total

        # Normalize Decimal→str in items for cache consistency
        normalized_items = []
        for item in items:
            d = dict(item)
            for k in ("amount", "base_amount", "tasa_expedicion"):
                if k in d and isinstance(d[k], Decimal):
                    d[k] = str(d[k])
            normalized_items.append(d)

        result = {
            "items": normalized_items,
            "total_amount": str(total),
            "fee_type_totals": {k: str(v) for k, v in fee_totals.items()},
            "currency": "XAF",
        }
        await cache.set(cache_key, result, ttl=CACHE_TTL)
        return result

    @staticmethod
    async def get_pricing_matrix(conn, bundle_id: UUID) -> Dict:
        """Get complete pricing matrix (all zones)."""
        cache = get_services_cache()
        cache_key = f"bundle:{bundle_id}:matrix"
        cached = await cache.get(cache_key)
        if cached:
            return cached

        items = await BundleRepository.get_pricing_matrix(conn, bundle_id)
        zone_totals = await BundleRepository.get_zone_totals(conn, bundle_id)

        result = {
            "items": items,
            "zone_totals": zone_totals,
            "currency": "XAF",
        }
        await cache.set(cache_key, result, ttl=CACHE_TTL)
        return result

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    @staticmethod
    async def get_required_documents(conn, bundle_id: UUID) -> List[Dict]:
        """Get documents required by bundle services."""
        return await BundleRepository.get_required_documents(conn, bundle_id)

    # ------------------------------------------------------------------
    # Installment Preview
    # ------------------------------------------------------------------

    @staticmethod
    async def preview_installments(
        conn,
        bundle_id: UUID,
        zone_id: UUID,
        num_installments: int = 3,
    ) -> Dict:
        """Simulate an installment payment plan for a bundle+zone."""
        bundle = await BundleRepository.get_bundle(conn, bundle_id)
        if not bundle:
            return {"error": "Bundle not found"}

        if not bundle.get("installment_eligible"):
            return {"error": "Bundle not eligible for installment payments"}

        max_inst = bundle.get("max_installments", 1)
        if num_installments > max_inst:
            num_installments = max_inst

        total = await BundleRepository.calculate_total(conn, bundle_id, zone_id)
        if total <= 0:
            return {"error": "No items found for this zone"}

        # Calculate installment amounts
        installment_amount = (total / num_installments).quantize(Decimal("1"))
        # Last installment absorbs rounding
        last_amount = total - (installment_amount * (num_installments - 1))

        frequency = bundle.get("installment_frequency", "monthly")
        freq_days = {"monthly": 30, "bi-monthly": 60, "quarterly": 90}.get(frequency, 30)

        today = date.today()
        installments = []
        cumulative = Decimal("0")

        for i in range(1, num_installments + 1):
            amt = last_amount if i == num_installments else installment_amount
            cumulative += amt
            due = today + timedelta(days=freq_days * i)
            installments.append({
                "installment_number": i,
                "amount_due": str(amt),
                "due_date": due.isoformat(),
                "cumulative_paid": str(cumulative),
            })

        # Resolve penalty config from fiscal_config_rules (specificity-based)
        penalty_config = await conn.fetchrow("""
            SELECT config FROM fiscal_config_rules
            WHERE config_type = 'penalty'
              AND is_enabled = true
              AND (bundle_id = $1 OR bundle_id IS NULL)
              AND effective_from <= CURRENT_DATE
              AND (effective_to IS NULL OR effective_to >= CURRENT_DATE)
            ORDER BY specificity DESC
            LIMIT 1
        """, bundle_id)
        penalty_cfg = penalty_config["config"] if penalty_config else {}

        # Resolve installment config from fiscal_config_rules
        installment_config = await conn.fetchrow("""
            SELECT config FROM fiscal_config_rules
            WHERE config_type = 'installment'
              AND is_enabled = true
              AND (bundle_id = $1 OR bundle_id IS NULL)
              AND effective_from <= CURRENT_DATE
              AND (effective_to IS NULL OR effective_to >= CURRENT_DATE)
            ORDER BY specificity DESC
            LIMIT 1
        """, bundle_id)
        installment_cfg = installment_config["config"] if installment_config else {}

        return {
            "bundle_code": bundle["bundle_code"],
            "total_amount": str(total),
            "num_installments": num_installments,
            "frequency": frequency,
            "grace_period_days": penalty_cfg.get("grace_days", 0),
            "late_fee_rate": str(penalty_cfg.get("rate", 0)),
            "installments": installments,
            "currency": "XAF",
        }

    # ------------------------------------------------------------------
    # Simulator — single call for public page
    # ------------------------------------------------------------------

    @staticmethod
    async def simulate(conn, commerce_type: str, zone_code: str, language: str = "es") -> Dict:
        """Simulate bundle pricing for a commerce_type + zone_code.

        Returns bundle + items grouped by fee_type + totals + documents
        + installment preview — all in 1 call. Cached 1h per language.
        """
        lang = language if language in ("es", "fr", "en") else "es"
        cache = get_services_cache()
        cache_key = f"bundle:sim:{commerce_type}:{zone_code}:{lang}"
        cached = await cache.get(cache_key)
        if cached:
            return cached

        # Resolve commerce_type → bundle
        bundle = await BundleRepository.get_bundle_by_commerce_type(conn, commerce_type)
        if not bundle:
            return {"error": f"No active bundle for commerce_type '{commerce_type}'"}

        # Resolve zone_code → zone
        zone = await BundleRepository.get_zone_by_code(conn, zone_code)
        if not zone:
            return {"error": f"Unknown zone_code '{zone_code}'"}

        bundle_id = bundle["id"]
        zone_id = zone["id"]

        # Parallel-safe: all reads, no writes
        items = await BundleRepository.get_bundle_items(conn, bundle_id, zone_id, language=lang)
        documents = await BundleRepository.get_required_documents(conn, bundle_id, language=lang)

        # Group items by fee_type + compute totals
        fee_groups: Dict[str, list] = {"tesoro": [], "municipal": [], "chamber": []}
        fee_totals = {"tesoro": Decimal("0"), "municipal": Decimal("0"), "chamber": Decimal("0")}
        for item in items:
            ft = item.get("fee_type", "tesoro")
            fee_groups.setdefault(ft, []).append(item)
            fee_totals[ft] = fee_totals.get(ft, Decimal("0")) + item["amount"]

        grand_total = sum(fee_totals.values())

        # Installment preview (only if eligible AND public visibility enabled)
        installment_preview = None
        if (
            bundle.get("installment_eligible")
            and bundle.get("public_installment_visible")
            and grand_total > 0
        ):
            max_inst = bundle.get("max_installments", 1)
            preview = await BundleService.preview_installments(
                conn, bundle_id, zone_id, min(max_inst, 4)
            )
            if "error" not in preview:
                installment_preview = preview

        # Normalize Decimal→str in items to avoid cache deserialization mismatch
        # (Decimal → json.dumps(default=str) → "50000" on cache write,
        #  but Decimal → FastAPI JSON → 50000.0 on uncached response)
        def _normalize_item(item: dict) -> dict:
            d = dict(item)
            for k in ("amount", "base_amount", "tasa_expedicion"):
                if k in d and isinstance(d[k], Decimal):
                    d[k] = str(d[k])
            return d

        result = {
            "bundle": bundle,
            "zone": zone,
            "fee_groups": {
                ft: [_normalize_item(i) for i in group]
                for ft, group in fee_groups.items()
                if group
            },
            "fee_totals": {k: str(v) for k, v in fee_totals.items()},
            "grand_total": str(grand_total),
            "documents": documents,
            "installment_preview": installment_preview,
            "currency": "XAF",
        }
        await cache.set(cache_key, result, ttl=CACHE_TTL)
        return result

    # ------------------------------------------------------------------
    # Bundles — Write
    # ------------------------------------------------------------------

    @staticmethod
    async def create_bundle(conn, data: Dict, user_id: Optional[UUID] = None) -> Dict:
        """Create a new bundle."""
        result = await BundleRepository.create_bundle(conn, data, user_id)
        await BundleService._invalidate_cache()
        return result

    @staticmethod
    async def update_bundle(
        conn, bundle_id: UUID, data: Dict, user_id: Optional[UUID] = None
    ) -> Optional[Dict]:
        """Update a bundle."""
        result = await BundleRepository.update_bundle(conn, bundle_id, data, user_id)
        await BundleService._invalidate_cache(bundle_id)
        return result

    @staticmethod
    async def delete_bundle(conn, bundle_id: UUID) -> bool:
        """Soft delete a bundle."""
        success = await BundleRepository.delete_bundle(conn, bundle_id)
        if success:
            await BundleService._invalidate_cache(bundle_id)
        return success

    # ------------------------------------------------------------------
    # Items — Write
    # ------------------------------------------------------------------

    @staticmethod
    async def upsert_item(
        conn, bundle_id: UUID, data: Dict, user_id: Optional[UUID] = None
    ) -> Dict:
        """Upsert a bundle item with audit context."""
        async with conn.transaction():
            if user_id:
                await conn.execute(
                    "SET LOCAL app.current_user_id = $1::text", str(user_id)
                )
            result = await BundleRepository.upsert_item(conn, bundle_id, data)
            await BundleService._invalidate_cache(bundle_id)
        return result

    @staticmethod
    async def delete_item(conn, item_id: UUID, user_id: Optional[UUID] = None) -> bool:
        """Delete a bundle item with audit context."""
        async with conn.transaction():
            if user_id:
                await conn.execute(
                    "SET LOCAL app.current_user_id = $1::text", str(user_id)
                )
            success, bundle_id = await BundleRepository.delete_item(conn, item_id)
            if success and bundle_id:
                await BundleService._invalidate_cache(bundle_id)
        return success

    @staticmethod
    async def copy_zone_prices(
        conn,
        bundle_id: UUID,
        source_zone_id: UUID,
        target_zone_id: UUID,
        multiplier: Decimal = Decimal("1.0"),
        user_id: Optional[UUID] = None,
    ) -> int:
        """Copy prices from one zone to another with audit context + batch_id."""
        batch_id = uuid4()
        async with conn.transaction():
            if user_id:
                await conn.execute(
                    "SET LOCAL app.current_user_id = $1::text", str(user_id)
                )
            await conn.execute(
                "SET LOCAL app.audit_batch_id = $1::text", str(batch_id)
            )
            count = await BundleRepository.copy_zone_prices(
                conn, bundle_id, source_zone_id, target_zone_id, multiplier
            )
            await BundleService._invalidate_cache(bundle_id)
        return count

    # ------------------------------------------------------------------
    # Cache Invalidation
    # ------------------------------------------------------------------

    @staticmethod
    async def _invalidate_cache(bundle_id: Optional[UUID] = None):
        """Invalidate bundle cache entries using pattern delete."""
        try:
            cache = get_services_cache()
            if bundle_id:
                # Zone-specific + matrix keys
                await cache.delete_pattern(f"bundle:{bundle_id}:")
            # Simulator keys use commerce_type, not bundle_id — nuke all sim cache
            # Only 10 types × 12 zones = 120 keys max, acceptable
            await cache.delete_pattern("bundle:sim:")
            # Always invalidate zones + commerce_types (cheap to refresh)
            await cache.delete("bundle:zones:all")
            await cache.delete("bundle:commerce_types")
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")
