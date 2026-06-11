"""
Repository for the `dashboard_registrations` table (migrations 317 + 319 + 323).

Stateless static methods — easy to mock in tests, no shared connection state.
All SELECTs project the same column list (no SELECT *) so that adding a
column to the table doesn't silently change the API contract.

Mig 323 (2026-05-05): added i18n + presentation columns (title_*, description_*,
category, display_order, embed_mode, panel_id, default_time_range, icon_name,
rls_mode). The metadata is now BD-driven instead of the in-code _REPORTS_METADATA
dict, so admins can add/remove dashboards without code changes.
"""

from typing import Optional

import asyncpg


# Column projection shared by all SELECTs. Includes the dual-provider columns
# from migration 319 (provider, grafana_dashboard_uid, grafana_org_id) and the
# metadata columns from migration 323 (i18n + presentation).
_COLS = (
    "dashboard_id, looker_report_id, looker_page_id, "
    "provider::text AS provider, grafana_dashboard_uid, grafana_org_id, "
    "is_active, updated_by, updated_at, created_at, "
    "title_es, title_fr, title_en, "
    "description_es, description_fr, description_en, "
    "rls_mode, embed_mode, panel_id, "
    "display_order, default_time_range, icon_name, category"
)


class DashboardConfigRepository:
    """asyncpg DAO for dashboard_registrations (E1 admin config + Grafana provider)."""

    @staticmethod
    async def list_active(
        conn: asyncpg.Connection,
        *,
        rls_modes: Optional[list[str]] = None,
    ) -> list[asyncpg.Record]:
        """Rows used by GET /reports-config — active rows only, ordered.

        :param rls_modes: optional whitelist of rls_mode values. When provided,
            rows whose rls_mode is NOT in the list are filtered out (used to
            hide 'admin_only' dashboards from non-admin callers).
            None = no filter (admin path).
        """
        if rls_modes is None:
            return await conn.fetch(
                f"SELECT {_COLS} FROM dashboard_registrations "
                "WHERE is_active = true "
                "ORDER BY display_order, dashboard_id"
            )
        return await conn.fetch(
            f"SELECT {_COLS} FROM dashboard_registrations "
            "WHERE is_active = true AND rls_mode = ANY($1::text[]) "
            "ORDER BY display_order, dashboard_id",
            rls_modes,
        )

    @staticmethod
    async def list_all(conn: asyncpg.Connection) -> list[asyncpg.Record]:
        """Rows used by the admin UI — both active and inactive, ordered."""
        return await conn.fetch(
            f"SELECT {_COLS} FROM dashboard_registrations "
            "ORDER BY display_order, dashboard_id"
        )

    @staticmethod
    async def list_grafana_uids(
        conn: asyncpg.Connection,
    ) -> list[str]:
        """Return all UIDs already registered for provider='grafana'.

        Used by the /admin/grafana/discover endpoint to filter out
        dashboards that are already imported.
        """
        rows = await conn.fetch(
            "SELECT grafana_dashboard_uid FROM dashboard_registrations "
            "WHERE provider = 'grafana' AND grafana_dashboard_uid IS NOT NULL"
        )
        return [r["grafana_dashboard_uid"] for r in rows]

    @staticmethod
    async def get_by_id(
        conn: asyncpg.Connection, dashboard_id: str
    ) -> Optional[asyncpg.Record]:
        """Used to fetch the previous state for the audit log diff."""
        return await conn.fetchrow(
            f"SELECT {_COLS} FROM dashboard_registrations WHERE dashboard_id = $1",
            dashboard_id,
        )

    @staticmethod
    async def create(
        conn: asyncpg.Connection,
        *,
        dashboard_id: str,
        provider: str,
        looker_report_id: Optional[str],
        looker_page_id: Optional[str],
        grafana_dashboard_uid: Optional[str],
        grafana_org_id: int,
        is_active: bool,
        title_es: str,
        title_fr: str,
        title_en: str,
        description_es: Optional[str],
        description_fr: Optional[str],
        description_en: Optional[str],
        rls_mode: str,
        embed_mode: str,
        panel_id: Optional[int],
        display_order: int,
        default_time_range: str,
        icon_name: Optional[str],
        category: Optional[str],
        updated_by: str,
    ) -> asyncpg.Record:
        """INSERT a new dashboard row. Raises asyncpg.UniqueViolationError
        when dashboard_id already exists — caller maps to 409.
        """
        return await conn.fetchrow(
            f"""
            INSERT INTO dashboard_registrations (
                dashboard_id, provider, looker_report_id, looker_page_id,
                grafana_dashboard_uid, grafana_org_id,
                is_active,
                title_es, title_fr, title_en,
                description_es, description_fr, description_en,
                rls_mode, embed_mode, panel_id,
                display_order, default_time_range, icon_name, category,
                updated_by, updated_at, created_at
            )
            VALUES (
                $1, $2::dashboard_provider_enum, $3, $4,
                $5, $6,
                $7,
                $8, $9, $10,
                $11, $12, $13,
                $14, $15, $16,
                $17, $18, $19, $20,
                $21::uuid, NOW(), NOW()
            )
            RETURNING {_COLS}
            """,
            dashboard_id, provider, looker_report_id, looker_page_id,
            grafana_dashboard_uid, grafana_org_id,
            is_active,
            title_es, title_fr, title_en,
            description_es, description_fr, description_en,
            rls_mode, embed_mode, panel_id,
            display_order, default_time_range, icon_name, category,
            updated_by,
        )

    @staticmethod
    async def soft_delete(
        conn: asyncpg.Connection,
        *,
        dashboard_id: str,
        updated_by: str,
    ) -> Optional[asyncpg.Record]:
        """Set is_active=false (preserves audit trail). Returns updated row or None."""
        return await conn.fetchrow(
            f"""
            UPDATE dashboard_registrations
            SET is_active = false, updated_by = $2::uuid, updated_at = NOW()
            WHERE dashboard_id = $1
            RETURNING {_COLS}
            """,
            dashboard_id, updated_by,
        )

    @staticmethod
    async def upsert(
        conn: asyncpg.Connection,
        *,
        dashboard_id: str,
        provider: str,
        looker_report_id: Optional[str],
        looker_page_id: Optional[str],
        grafana_dashboard_uid: Optional[str],
        grafana_org_id: int,
        is_active: bool,
        updated_by: str,
    ) -> asyncpg.Record:
        """Atomic UPSERT with RETURNING — used by PUT /admin/configs/{id}.

        DOES NOT touch metadata columns (title/description/category/etc.) —
        those are admin-managed via the dedicated metadata fields in the
        update form (POST flow handles them via create()).

        Note on dual-provider semantics:
        - When provider='looker_studio', looker_* fields are authoritative.
        - When provider='grafana', grafana_* fields are authoritative.
        """
        return await conn.fetchrow(
            f"""
            INSERT INTO dashboard_registrations
                (dashboard_id, provider, looker_report_id, looker_page_id,
                 grafana_dashboard_uid, grafana_org_id,
                 is_active, updated_by, updated_at, created_at)
            VALUES (
                $1, $2::dashboard_provider_enum, $3, $4,
                $5, $6,
                $7, $8::uuid, NOW(), NOW()
            )
            ON CONFLICT (dashboard_id) DO UPDATE SET
                provider              = EXCLUDED.provider,
                looker_report_id      = EXCLUDED.looker_report_id,
                looker_page_id        = EXCLUDED.looker_page_id,
                grafana_dashboard_uid = EXCLUDED.grafana_dashboard_uid,
                grafana_org_id        = EXCLUDED.grafana_org_id,
                is_active             = EXCLUDED.is_active,
                updated_by            = EXCLUDED.updated_by,
                updated_at            = NOW()
            RETURNING {_COLS}
            """,
            dashboard_id,
            provider,
            looker_report_id,
            looker_page_id,
            grafana_dashboard_uid,
            grafana_org_id,
            is_active,
            updated_by,
        )

    @staticmethod
    async def update_metadata(
        conn: asyncpg.Connection,
        *,
        dashboard_id: str,
        title_es: Optional[str] = None,
        title_fr: Optional[str] = None,
        title_en: Optional[str] = None,
        description_es: Optional[str] = None,
        description_fr: Optional[str] = None,
        description_en: Optional[str] = None,
        rls_mode: Optional[str] = None,
        embed_mode: Optional[str] = None,
        panel_id: Optional[int] = None,
        display_order: Optional[int] = None,
        default_time_range: Optional[str] = None,
        icon_name: Optional[str] = None,
        category: Optional[str] = None,
        updated_by: str,
    ) -> Optional[asyncpg.Record]:
        """Patch metadata fields. NULL params are skipped (preserve existing).

        Used by PATCH /admin/configs/{id}/metadata.
        """
        sets: list[str] = []
        vals: list = []
        i = 2  # $1 reserved for dashboard_id

        for col, val in (
            ("title_es", title_es), ("title_fr", title_fr), ("title_en", title_en),
            ("description_es", description_es), ("description_fr", description_fr),
            ("description_en", description_en),
            ("rls_mode", rls_mode), ("embed_mode", embed_mode),
            ("panel_id", panel_id),
            ("display_order", display_order),
            ("default_time_range", default_time_range),
            ("icon_name", icon_name), ("category", category),
        ):
            if val is not None:
                sets.append(f"{col} = ${i}")
                vals.append(val)
                i += 1

        if not sets:
            # Nothing to patch — just return current row
            return await DashboardConfigRepository.get_by_id(conn, dashboard_id)

        sets.append(f"updated_by = ${i}::uuid")
        vals.append(updated_by)
        sets.append("updated_at = NOW()")

        return await conn.fetchrow(
            f"""
            UPDATE dashboard_registrations SET {', '.join(sets)}
            WHERE dashboard_id = $1
            RETURNING {_COLS}
            """,
            dashboard_id, *vals,
        )
