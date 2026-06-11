"""
Company Repository - Data access layer for companies and user_company_roles

ALIGNED WITH DB (Migration 218 Phase 1.3)
Tables: companies (26 columns), user_company_roles
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from loguru import logger
import asyncpg

from app.modules.companies.models import CompanyCreate, CompanyUpdate, CompanyMemberRole


class CompanyRepository:
    """Repository for companies and members."""

    def __init__(self):
        # Cached flag: does search_vector column exist? (set on first query)
        self._has_search_vector: Optional[bool] = None

    @staticmethod
    def _uid(val) -> UUID:
        """Convert str to UUID if needed. Pass-through if already UUID."""
        return UUID(val) if isinstance(val, str) else val

    async def _check_fts_available(self, conn: asyncpg.Connection) -> bool:
        """Check if tsvector search_vector column exists (migration 234).

        Caches result in instance to avoid repeated schema queries.
        """
        if self._has_search_vector is None:
            self._has_search_vector = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'companies' AND column_name = 'search_vector')"
            )
        return self._has_search_vector

    async def create(self, conn: asyncpg.Connection, company: CompanyCreate, owner_id: str) -> Dict[str, Any]:
        """Create company with all OCR-aligned fields."""
        query = """
            INSERT INTO companies (
                legal_name, tax_id, trade_name, nif, forma_juridica,
                nacionalidad, capital_social, registration_number, registration_date,
                sector_actividad, subsector_actividad, objeto_social,
                commerce_type, regimen_fiscal,
                employee_count, establishment_count,
                address, phone, email, zone_id, city_id,
                is_active, is_verified,
                representante_legal,
                created_at, updated_at
            )
            VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8, $9,
                $10, $11, $12,
                $13, $14,
                $15, $16,
                $17, $18, $19, $20, $21,
                $22, $23,
                $24,
                NOW(), NOW()
            )
            RETURNING *
        """
        regimen = company.regimen_fiscal.value if company.regimen_fiscal else 'pendiente'
        result = await conn.fetchrow(
            query,
            company.legal_name, company.tax_id, company.trade_name,
            company.nif, company.forma_juridica,
            company.nacionalidad, company.capital_social,
            company.registration_number, company.registration_date,
            company.sector_actividad, company.subsector_actividad, company.objeto_social,
            company.commerce_type, regimen,
            company.employee_count, company.establishment_count,
            company.address, company.phone, company.email,
            company.zone_id, company.city_id,
            company.is_active, company.is_verified,
            company.representante_legal,
        )

        # Add owner as member
        await self.add_member(conn, dict(result)["id"], owner_id, CompanyMemberRole.COMPANY_OWNER)
        return dict(result)

    async def get_by_id(self, conn: asyncpg.Connection, company_id: str) -> Optional[Dict[str, Any]]:
        """Get company by ID with city/zone names."""
        query = """
            SELECT c.*,
                   ct.name as city_name,
                   cz.zone_code,
                   COUNT(ucr.user_id) as member_count
            FROM companies c
            LEFT JOIN cities ct ON c.city_id = ct.id
            LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
            LEFT JOIN user_company_roles ucr ON c.id = ucr.company_id
            WHERE c.id = $1
            GROUP BY c.id, ct.name, cz.zone_code
        """
        result = await conn.fetchrow(query, self._uid(company_id))
        return dict(result) if result else None

    async def get_by_nif(self, conn: asyncpg.Connection, nif: str) -> Optional[Dict[str, Any]]:
        """Get company by NIF (unique fiscal identifier)."""
        query = """
            SELECT c.*,
                   ct.name as city_name,
                   cz.zone_code
            FROM companies c
            LEFT JOIN cities ct ON c.city_id = ct.id
            LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
            WHERE c.nif = $1
        """
        result = await conn.fetchrow(query, nif)
        return dict(result) if result else None

    async def list_by_user(
        self,
        conn: asyncpg.Connection,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        include_archived: bool = False,
    ) -> tuple[List[Dict[str, Any]], int]:
        """List companies where user is member.

        By default archived companies are filtered out (citizen surface). Pass
        ``include_archived=True`` for admin/audit views that need to see them.
        """
        archived_filter = "" if include_archived else " AND c.archived_at IS NULL"

        count_query = f"""
            SELECT COUNT(DISTINCT c.id)
            FROM companies c
            JOIN user_company_roles ucr ON c.id = ucr.company_id
            WHERE ucr.user_id = $1{archived_filter}
        """
        total = await conn.fetchval(count_query, self._uid(user_id))

        data_query = f"""
            SELECT c.*,
                   ct.name as city_name,
                   cz.zone_code,
                   COUNT(ucr2.user_id) as member_count
            FROM companies c
            JOIN user_company_roles ucr ON c.id = ucr.company_id
            LEFT JOIN cities ct ON c.city_id = ct.id
            LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
            LEFT JOIN user_company_roles ucr2 ON c.id = ucr2.company_id
            WHERE ucr.user_id = $1{archived_filter}
            GROUP BY c.id, ct.name, cz.zone_code
            ORDER BY c.created_at DESC
            LIMIT $2 OFFSET $3
        """
        results = await conn.fetch(data_query, self._uid(user_id), limit, offset)
        return [dict(r) for r in results], total

    async def update(self, conn: asyncpg.Connection, company_id: str, update_data: CompanyUpdate) -> Optional[Dict[str, Any]]:
        """Update company with dynamic field handling.

        Supports setting fields to NULL (exclude_unset distinguishes
        'not sent' from 'explicitly sent as null').
        """
        updates = []
        params = [self._uid(company_id)]
        param_idx = 2

        for field, value in update_data.model_dump(exclude_unset=True).items():
            # Handle enum serialization
            if hasattr(value, 'value'):
                value = value.value
            updates.append(f"{field} = ${param_idx}")
            params.append(value)
            param_idx += 1

        if not updates:
            return await self.get_by_id(conn, company_id)

        updates.append("updated_at = NOW()")

        query = f"""
            UPDATE companies SET {', '.join(updates)}
            WHERE id = $1
            RETURNING *
        """
        row = await conn.fetchrow(query, *params)
        if not row:
            return None
        return await self.get_by_id(conn, company_id)

    async def delete(self, conn: asyncpg.Connection, company_id: str) -> bool:
        """Hard-delete company and memberships (atomic).

        DANGEROUS — should only be invoked by an admin holding
        ``company.hard_delete``, AND only after :meth:`archive` has been
        applied + :meth:`check_archive_blockers` returns no blockers. The
        public route enforces both pre-conditions; this method itself does
        NOT re-check (kept low-level so back-office tooling can call it after
        its own validation).
        """
        cid = self._uid(company_id)
        async with conn.transaction():
            await conn.execute("DELETE FROM user_company_roles WHERE company_id = $1", cid)
            result = await conn.execute("DELETE FROM companies WHERE id = $1", cid)
            return result == "DELETE 1"

    # =========================================================================
    # Soft-delete (archive / unarchive)
    #
    # See migration 314_companies_soft_delete_archive.sql and
    # .claude/plans/SOFT_DELETE_COMPANIES_PLAN.md.
    # =========================================================================

    async def check_archive_blockers(
        self, conn: asyncpg.Connection, company_id: str
    ) -> Dict[str, int]:
        """Count active dependencies that prevent archiving / hard-deleting.

        Returns a dict with the same keys whether or not blockers exist; the
        caller decides on emptiness by ``sum(values) == 0``.

        Active definition (per the plan):
          - active_licenses    : commercial_licenses where status NOT IN
                                 ('cancelled', 'expired', 'revoked')
          - pending_payments   : service_payments where workflow_status NOT IN
                                 ('completed', 'cancelled', 'refunded')
          - open_requests      : service_requests where status NOT IN
                                 ('completed', 'cancelled', 'rejected')
          - active_inspections : field_inspections where status IN
                                 ('pending', 'in_progress')
        """
        cid = self._uid(company_id)
        rows = await conn.fetchrow(
            """
            SELECT
              (SELECT COUNT(*) FROM commercial_licenses
                 WHERE company_id = $1
                   AND status::text NOT IN ('cancelled', 'expired', 'revoked'))::int
                 AS active_licenses,
              (SELECT COUNT(*) FROM service_payments
                 WHERE company_id = $1
                   AND workflow_status::text NOT IN
                       ('completed', 'cancelled', 'refunded'))::int
                 AS pending_payments,
              (SELECT COUNT(*) FROM service_requests
                 WHERE company_id = $1
                   AND status::text NOT IN
                       ('completed', 'cancelled', 'rejected'))::int
                 AS open_requests,
              (SELECT COUNT(*) FROM field_inspections
                 WHERE company_id = $1
                   AND status::text IN ('pending', 'in_progress'))::int
                 AS active_inspections
            """,
            cid,
        )
        return {
            "active_licenses": rows["active_licenses"] or 0,
            "pending_payments": rows["pending_payments"] or 0,
            "open_requests": rows["open_requests"] or 0,
            "active_inspections": rows["active_inspections"] or 0,
        }

    async def archive(
        self,
        conn: asyncpg.Connection,
        company_id: str,
        archived_by_user_id: str,
        reason: str = "archived_by_owner",
    ) -> bool:
        """Soft-delete: mark the company as archived.

        Sets ``is_active=false`` (legacy flag — keeps the existing index
        ``idx_companies_active_verified`` honest) AND
        ``archived_at = NOW(), archive_reason, archived_by``. Idempotent: a
        re-archive simply refreshes the timestamp (no error).

        Caller is responsible for verifying ownership and calling
        :meth:`check_archive_blockers` first. This method does NOT validate
        — it just executes.
        """
        cid = self._uid(company_id)
        result = await conn.execute(
            """
            UPDATE companies
               SET archived_at    = NOW(),
                   archive_reason = $2,
                   archived_by    = $3,
                   is_active      = FALSE,
                   updated_at     = NOW()
             WHERE id = $1
            """,
            cid,
            reason,
            self._uid(archived_by_user_id),
        )
        return result == "UPDATE 1"

    async def unarchive(self, conn: asyncpg.Connection, company_id: str) -> bool:
        """Restore an archived company. Admin-only at the route layer."""
        cid = self._uid(company_id)
        result = await conn.execute(
            """
            UPDATE companies
               SET archived_at    = NULL,
                   archive_reason = NULL,
                   archived_by    = NULL,
                   is_active      = TRUE,
                   updated_at     = NOW()
             WHERE id = $1
               AND archived_at IS NOT NULL
            """,
            cid,
        )
        return result == "UPDATE 1"

    async def add_member(self, conn: asyncpg.Connection, company_id: str, user_id: str, role: CompanyMemberRole) -> Dict[str, Any]:
        """Add member to company."""
        query = """
            INSERT INTO user_company_roles (company_id, user_id, role, is_active, assigned_at)
            VALUES ($1, $2, $3, TRUE, NOW())
            ON CONFLICT (user_id, company_id) DO UPDATE SET role = $3, is_active = TRUE
            RETURNING *
        """
        result = await conn.fetchrow(query, self._uid(company_id), self._uid(user_id), role.value)
        return dict(result)

    async def remove_member(self, conn: asyncpg.Connection, company_id: str, user_id: str) -> bool:
        """Remove member from company."""
        result = await conn.execute(
            "DELETE FROM user_company_roles WHERE company_id = $1 AND user_id = $2",
            self._uid(company_id), self._uid(user_id)
        )
        return result == "DELETE 1"

    async def get_members(self, conn: asyncpg.Connection, company_id: str) -> List[Dict[str, Any]]:
        """Get company members."""
        query = """
            SELECT ucr.*, u.email as user_email, u.first_name || ' ' || u.last_name as user_name
            FROM user_company_roles ucr
            JOIN users u ON ucr.user_id = u.id
            WHERE ucr.company_id = $1
            ORDER BY ucr.assigned_at
        """
        results = await conn.fetch(query, self._uid(company_id))
        return [dict(r) for r in results]

    async def check_membership(self, conn: asyncpg.Connection, company_id: str, user_id: str) -> Optional[str]:
        """Check if user is member and return role."""
        return await conn.fetchval(
            "SELECT role FROM user_company_roles WHERE company_id = $1 AND user_id = $2",
            self._uid(company_id), self._uid(user_id)
        )

    # =========================================================================
    # ADMIN METHODS
    # =========================================================================

    async def list_all(
        self,
        conn: asyncpg.Connection,
        limit: int = 20,
        offset: int = 0,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_verified: Optional[bool] = None,
        regimen_fiscal: Optional[str] = None,
        zone_id: Optional[str] = None,
        city_id: Optional[str] = None,
        city_ids: Optional[List[str]] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        archived: str = "active",  # 'active' | 'archived' | 'all'
    ) -> List[Dict[str, Any]]:
        """List all companies with filters — admin view.

        Includes license_count and total_obligations_amount via LEFT JOIN.
        Uses tsvector FTS when available (migration 234), falls back to ILIKE.
        """
        await self._check_fts_available(conn)
        allowed_sort = {
            "created_at": "c.created_at",
            "legal_name": "c.legal_name",
            "is_active": "c.is_active",
            "is_verified": "c.is_verified",
            "member_count": "mem.cnt",
            "license_count": "lic.cnt",
        }
        sort_col = allowed_sort.get(sort_by, "c.created_at")
        sort_dir = "ASC" if sort_order.lower() == "asc" else "DESC"

        conditions = []
        params: List[Any] = []
        idx = 1

        if search:
            # Use tsvector FTS if available (O(log N) for 1M+), else ILIKE
            if self._has_search_vector:
                conditions.append(f"c.search_vector @@ company_search_query(${idx})")
                params.append(search.strip())
            else:
                conditions.append(f"(c.legal_name ILIKE ${idx} OR c.tax_id ILIKE ${idx} OR c.nif ILIKE ${idx})")
                escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                params.append(f"%{escaped}%")
            idx += 1
        if is_active is not None:
            conditions.append(f"c.is_active = ${idx}")
            params.append(is_active)
            idx += 1
        if is_verified is not None:
            conditions.append(f"c.is_verified = ${idx}")
            params.append(is_verified)
            idx += 1
        if regimen_fiscal:
            conditions.append(f"c.regimen_fiscal = ${idx}")
            params.append(regimen_fiscal)
            idx += 1
        if zone_id:
            conditions.append(f"c.zone_id = ${idx}")
            params.append(self._uid(zone_id))
            idx += 1
        if city_id:
            conditions.append(f"c.city_id = ${idx}")
            params.append(self._uid(city_id))
            idx += 1
        if city_ids:
            conditions.append(f"""(
                c.city_id = ANY(${idx}::uuid[])
                OR c.id IN (
                    SELECT DISTINCT cl.company_id
                    FROM commercial_licenses cl
                    WHERE cl.city_id = ANY(${idx}::uuid[])
                )
            )""")
            params.append(city_ids)
            idx += 1

        # Archive filter — admin views default to 'active' (matches the
        # historical behaviour). 'archived' restricts to soft-deleted rows;
        # 'all' shows everything (used by the audit log surface).
        if archived == "active":
            conditions.append("c.archived_at IS NULL")
        elif archived == "archived":
            conditions.append("c.archived_at IS NOT NULL")
        # 'all' -> no filter

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT c.*,
                   ct.name as city_name,
                   cz.zone_code,
                   au.email as archived_by_email,
                   au.first_name || ' ' || au.last_name as archived_by_name,
                   COALESCE(mem.cnt, 0) as member_count,
                   COALESCE(lic.cnt, 0) as license_count,
                   COALESCE(lic.total_amt, 0) as total_obligations_amount
            FROM companies c
            LEFT JOIN cities ct ON c.city_id = ct.id
            LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
            LEFT JOIN users au ON au.id = c.archived_by
            LEFT JOIN LATERAL (
                SELECT COUNT(*) as cnt
                FROM user_company_roles ucr
                WHERE ucr.company_id = c.id
            ) mem ON true
            LEFT JOIN LATERAL (
                SELECT COUNT(*) as cnt, COALESCE(SUM(total_amount), 0) as total_amt
                FROM commercial_licenses cl
                WHERE cl.company_id = c.id
            ) lic ON true
            {where}
            ORDER BY {sort_col} {sort_dir}
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        params.extend([limit, offset])
        results = await conn.fetch(query, *params)
        return [dict(r) for r in results]

    async def count_all(
        self,
        conn: asyncpg.Connection,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_verified: Optional[bool] = None,
        regimen_fiscal: Optional[str] = None,
        zone_id: Optional[str] = None,
        city_id: Optional[str] = None,
        city_ids: Optional[List[str]] = None,
        archived: str = "active",  # 'active' | 'archived' | 'all'
    ) -> int:
        """Count companies matching filters."""
        await self._check_fts_available(conn)
        conditions = []
        params: List[Any] = []
        idx = 1

        if search:
            if self._has_search_vector:
                conditions.append(f"search_vector @@ company_search_query(${idx})")
                params.append(search.strip())
            else:
                conditions.append(f"(legal_name ILIKE ${idx} OR tax_id ILIKE ${idx} OR nif ILIKE ${idx})")
                escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                params.append(f"%{escaped}%")
            idx += 1
        if is_active is not None:
            conditions.append(f"is_active = ${idx}")
            params.append(is_active)
            idx += 1
        if is_verified is not None:
            conditions.append(f"is_verified = ${idx}")
            params.append(is_verified)
            idx += 1
        if regimen_fiscal:
            conditions.append(f"regimen_fiscal = ${idx}")
            params.append(regimen_fiscal)
            idx += 1
        if zone_id:
            conditions.append(f"zone_id = ${idx}")
            params.append(self._uid(zone_id))
            idx += 1
        if city_id:
            conditions.append(f"city_id = ${idx}")
            params.append(self._uid(city_id))
            idx += 1
        if city_ids:
            conditions.append(f"""(
                city_id = ANY(${idx}::uuid[])
                OR id IN (
                    SELECT DISTINCT cl.company_id
                    FROM commercial_licenses cl
                    WHERE cl.city_id = ANY(${idx}::uuid[])
                )
            )""")
            params.append(city_ids)
            idx += 1

        # Archive filter — same semantics as list_all.
        if archived == "active":
            conditions.append("archived_at IS NULL")
        elif archived == "archived":
            conditions.append("archived_at IS NOT NULL")
        # 'all' -> no filter

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT COUNT(*) FROM companies {where}"
        return await conn.fetchval(query, *params)

    async def get_stats(self, conn: asyncpg.Connection) -> Dict[str, Any]:
        """Aggregated company statistics for admin dashboard."""
        query = """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_active = true) as active,
                COUNT(*) FILTER (WHERE is_verified = true) as verified,
                COUNT(*) FILTER (WHERE is_active = false) as inactive,
                (SELECT COUNT(DISTINCT company_id) FROM commercial_licenses) as with_licenses
            FROM companies
        """
        row = await conn.fetchrow(query)
        stats = dict(row)

        # by_regimen breakdown
        regimen_query = """
            SELECT COALESCE(regimen_fiscal, 'pendiente') as regimen, COUNT(*) as count
            FROM companies
            GROUP BY regimen_fiscal
        """
        regimen_rows = await conn.fetch(regimen_query)
        stats["by_regimen"] = {r["regimen"]: r["count"] for r in regimen_rows}

        return stats

    async def get_stats_by_cities(
        self,
        conn: asyncpg.Connection,
        city_ids: List[str],
    ) -> Dict[str, Any]:
        """Aggregated company statistics scoped to specific cities.

        Companies matched via city_id OR commercial_licenses.city_id.
        """
        query = """
            WITH scoped_companies AS (
                SELECT DISTINCT c.id, c.is_active, c.is_verified, c.regimen_fiscal
                FROM companies c
                WHERE c.city_id = ANY($1::uuid[])
                UNION
                SELECT DISTINCT c.id, c.is_active, c.is_verified, c.regimen_fiscal
                FROM companies c
                JOIN commercial_licenses cl ON cl.company_id = c.id
                WHERE cl.city_id = ANY($1::uuid[])
            )
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_active = true) as active,
                COUNT(*) FILTER (WHERE is_verified = true) as verified,
                COUNT(*) FILTER (WHERE is_active = false) as inactive,
                (SELECT COUNT(DISTINCT cl.company_id)
                 FROM commercial_licenses cl
                 WHERE cl.city_id = ANY($1::uuid[])
                ) as with_licenses
            FROM scoped_companies
        """
        row = await conn.fetchrow(query, city_ids)
        stats = dict(row)

        # by_regimen breakdown
        regimen_query = """
            WITH scoped_companies AS (
                SELECT DISTINCT c.id, c.regimen_fiscal
                FROM companies c
                WHERE c.city_id = ANY($1::uuid[])
                UNION
                SELECT DISTINCT c.id, c.regimen_fiscal
                FROM companies c
                JOIN commercial_licenses cl ON cl.company_id = c.id
                WHERE cl.city_id = ANY($1::uuid[])
            )
            SELECT COALESCE(regimen_fiscal, 'pendiente') as regimen, COUNT(*) as count
            FROM scoped_companies
            GROUP BY regimen_fiscal
        """
        regimen_rows = await conn.fetch(regimen_query, city_ids)
        stats["by_regimen"] = {r["regimen"]: r["count"] for r in regimen_rows}

        return stats

    async def get_entity_city_ids(
        self,
        conn: asyncpg.Connection,
        entity_id: str,
    ) -> List[str]:
        """Get city_ids served by an entity (from entity_locations).

        Returns list of city_id UUIDs as strings.
        """
        query = """
            SELECT DISTINCT city_id
            FROM entity_locations
            WHERE entity_id = $1
              AND is_active = true
              AND city_id IS NOT NULL
        """
        rows = await conn.fetch(query, self._uid(entity_id))
        return [str(r["city_id"]) for r in rows]

    async def search(
        self,
        conn: asyncpg.Connection,
        query_str: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Lightweight company search for autocomplete.

        Uses tsvector full-text search if available (O(log N) for 1M+),
        falls back to trigram ILIKE on legal_name, tax_id, and nif.
        """
        has_fts = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'companies' AND column_name = 'search_vector')"
        )
        if has_fts:
            query = """
                SELECT c.id, c.legal_name, c.tax_id, c.nif, c.registration_number,
                       c.is_verified, ct.name as city_name, cz.zone_code
                FROM companies c
                LEFT JOIN cities ct ON c.city_id = ct.id
                LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
                WHERE c.search_vector @@ company_search_query($1)
                ORDER BY ts_rank(c.search_vector, company_search_query($1)) DESC
                LIMIT $2
            """
            results = await conn.fetch(query, query_str.strip(), limit)
        else:
            escaped = query_str.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            query = """
                SELECT c.id, c.legal_name, c.tax_id, c.nif, c.registration_number,
                       c.is_verified, ct.name as city_name, cz.zone_code
                FROM companies c
                LEFT JOIN cities ct ON c.city_id = ct.id
                LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
                WHERE c.legal_name ILIKE $1
                   OR c.tax_id ILIKE $1
                   OR c.nif ILIKE $1
                   OR c.registration_number ILIKE $1
                ORDER BY c.legal_name
                LIMIT $2
            """
            results = await conn.fetch(query, f"%{escaped}%", limit)
        return [dict(r) for r in results]

    async def verify(
        self,
        conn: asyncpg.Connection,
        company_id: str,
        is_verified: bool,
    ) -> Optional[Dict[str, Any]]:
        """Toggle company verification status."""
        cid = self._uid(company_id)
        result = await conn.fetchrow(
            "UPDATE companies SET is_verified = $2, updated_at = NOW() WHERE id = $1 RETURNING id",
            cid, is_verified,
        )
        if not result:
            return None
        return await self.get_by_id(conn, company_id)

    async def update_member_role(
        self,
        conn: asyncpg.Connection,
        company_id: str,
        user_id: str,
        role: str,
    ) -> Optional[Dict[str, Any]]:
        """Update a member's role within a company."""
        result = await conn.fetchrow(
            """
            UPDATE user_company_roles
            SET role = $3
            WHERE company_id = $1 AND user_id = $2
            RETURNING *
            """,
            self._uid(company_id), self._uid(user_id), role,
        )
        if not result:
            return None
        # Re-fetch with user info
        member = await conn.fetchrow(
            """
            SELECT ucr.*, u.email as user_email, u.first_name || ' ' || u.last_name as user_name
            FROM user_company_roles ucr
            JOIN users u ON ucr.user_id = u.id
            WHERE ucr.company_id = $1 AND ucr.user_id = $2
            """,
            self._uid(company_id), self._uid(user_id),
        )
        return dict(member) if member else None
