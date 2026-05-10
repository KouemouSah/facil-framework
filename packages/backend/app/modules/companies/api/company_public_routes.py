"""Public Company Directory — Unauthenticated API

Annuaire public des entreprises enregistrées en Guinée Équatoriale.
Rate-limited (100 req/min par IP). Données publiques uniquement.

Visible: legal_name, nif, registration_number, localidad, sector, objeto_social,
         regimen_fiscal, address (siège social).
Filtré: is_active=true AND is_verified=true uniquement.
"""

import hashlib
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from loguru import logger
import asyncpg

from app.core.cache import check_rate_limit, get_cache
from app.database.connection import get_database

router = APIRouter(tags=["Public Directory"])

# Rate limit: 100 requests per minute per IP
RATE_LIMIT_MAX = 100
RATE_LIMIT_WINDOW = 60

# Search cache: 30s TTL for popular queries
SEARCH_CACHE_TTL = 30
FILTER_CACHE_TTL = 120  # 2 min for filter options (zones, sectors, etc.)


async def _check_public_rate_limit(request: Request) -> None:
    """Enforce rate limiting on public endpoints by client IP.

    Graceful degradation: if Redis is down, allow the request
    (prefer availability over strict rate limiting).
    """
    client_ip = request.client.host if request.client else "unknown"
    try:
        allowed, remaining = await check_rate_limit(
            f"public_dir:{client_ip}", "/public/companies", RATE_LIMIT_MAX, RATE_LIMIT_WINDOW
        )
        if not allowed:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Try again in {RATE_LIMIT_WINDOW}s."
            )
    except Exception as e:
        # Redis down, connection error, etc. — allow request (graceful degradation)
        if "Rate limit" in str(e) or "429" in str(e):
            raise  # Re-raise our own HTTPException
        logger.debug(f"Rate limit check skipped (Redis unavailable): {e}")


@router.get("/search")
async def search_public_directory(
    request: Request,
    q: str = Query("", max_length=100, description="Search term (legal_name, NIF, activity)"),
    zone_id: Optional[str] = Query(None, description="Filter by commerce zone"),
    sector: Optional[str] = Query(None, description="Filter by sector_actividad"),
    forma_juridica: Optional[str] = Query(None, description="Filter by forma_juridica"),
    provincia: Optional[str] = Query(None, description="Filter by provincia (via cities)"),
    ciudad: Optional[str] = Query(None, description="Filter by city name"),
    sort_by: str = Query("legal_name", description="Sort column"),
    sort_order: str = Query("asc", description="Sort direction"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: asyncpg.Connection = Depends(get_database),
):
    """Public company directory search with advanced filters.

    Returns only verified active companies with public-safe fields.
    Cached for 30s per unique query combination.
    """
    await _check_public_rate_limit(request)

    # Build cache key from all query params
    cache_key_raw = f"pub_dir:search:{q}:{zone_id}:{sector}:{forma_juridica}:{provincia}:{ciudad}:{sort_by}:{sort_order}:{page}:{page_size}"
    cache_key = f"pub_dir:s:{hashlib.md5(cache_key_raw.encode()).hexdigest()}"

    cache = get_cache()
    try:
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached
    except Exception:
        pass  # Redis down — continue without cache

    conditions = ["c.is_active = true", "c.is_verified = true"]
    params: List[Any] = []
    idx = 1

    # Full-text search via websearch_to_tsquery + ILIKE fallback
    if q and len(q) >= 2:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append(
            f"(c.search_vector @@ websearch_to_tsquery('spanish', ${idx})"
            f" OR c.legal_name ILIKE ${idx + 1}"
            f" OR c.nif ILIKE ${idx + 1}"
            f" OR c.registration_number ILIKE ${idx + 1})"
        )
        params.append(q)
        params.append(f"%{escaped}%")
        idx += 2

    if zone_id:
        conditions.append(f"c.zone_id = ${idx}::uuid")
        params.append(zone_id)
        idx += 1

    if sector:
        conditions.append(f"c.sector_actividad = ${idx}")
        params.append(sector)
        idx += 1

    if forma_juridica:
        conditions.append(f"c.forma_juridica = ${idx}")
        params.append(forma_juridica)
        idx += 1

    if provincia:
        conditions.append(f"ct.provincia = ${idx}")
        params.append(provincia)
        idx += 1

    if ciudad:
        conditions.append(f"ct.name = ${idx}")
        params.append(ciudad)
        idx += 1

    # Sort — whitelist
    allowed_sort = {"legal_name": "c.legal_name", "city": "ct.name", "sector": "c.sector_actividad", "forma": "c.forma_juridica"}
    sort_col = allowed_sort.get(sort_by, "c.legal_name")
    sort_dir = "ASC" if sort_order.lower() == "asc" else "DESC"

    where = " AND ".join(conditions)
    offset = (page - 1) * page_size

    # Count (needs JOINs for provincia/ciudad filters)
    count_q = f"""SELECT COUNT(*) FROM companies c
        LEFT JOIN cities ct ON c.city_id = ct.id
        LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
        WHERE {where}"""
    total = await db.fetchval(count_q, *params)

    # Data — public-safe fields only (NO email, NO phone, NO capital)
    data_q = f"""
        SELECT
            c.id, c.legal_name, c.nif, c.registration_number,
            c.forma_juridica, c.sector_actividad, c.subsector_actividad,
            c.objeto_social, c.address,
            ct.name AS city_name, ct.provincia,
            cz.zone_code, cz.zone_tier
        FROM companies c
        LEFT JOIN cities ct ON c.city_id = ct.id
        LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
        WHERE {where}
        ORDER BY {sort_col} {sort_dir}
        LIMIT ${idx} OFFSET ${idx + 1}
    """
    params.extend([page_size, offset])
    rows = await db.fetch(data_q, *params)

    result = {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }

    # Cache result (fire-and-forget)
    try:
        await cache.set(cache_key, result, ttl=SEARCH_CACHE_TTL)
    except Exception:
        pass

    return result


@router.get("/zones")
async def list_public_zones(
    request: Request,
    db: asyncpg.Connection = Depends(get_database),
):
    """List commerce zones for directory filter dropdown. Cached 2min."""
    await _check_public_rate_limit(request)

    cache = get_cache()
    cache_key = "pub_dir:zones"
    try:
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached
    except Exception:
        pass

    rows = await db.fetch(
        "SELECT id, zone_code, zone_tier, name_es "
        "FROM commerce_zones ORDER BY zone_code"
    )
    result = [dict(r) for r in rows]
    try:
        await cache.set(cache_key, result, ttl=FILTER_CACHE_TTL)
    except Exception:
        pass
    return result


@router.get("/sectors")
async def list_public_sectors(
    request: Request,
    db: asyncpg.Connection = Depends(get_database),
):
    """List distinct sectors for directory filter dropdown. Cached 2min."""
    await _check_public_rate_limit(request)

    cache = get_cache()
    cache_key = "pub_dir:sectors"
    try:
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached
    except Exception:
        pass

    rows = await db.fetch(
        "SELECT DISTINCT sector_actividad AS sector "
        "FROM companies "
        "WHERE sector_actividad IS NOT NULL AND is_active = true AND is_verified = true "
        "ORDER BY sector_actividad"
    )
    result = [r["sector"] for r in rows]
    try:
        await cache.set(cache_key, result, ttl=FILTER_CACHE_TTL)
    except Exception:
        pass
    return result


@router.get("/provincias")
async def list_public_provincias(
    request: Request,
    db: asyncpg.Connection = Depends(get_database),
):
    """List distinct provincias for directory filter dropdown."""
    await _check_public_rate_limit(request)
    rows = await db.fetch(
        "SELECT DISTINCT ct.provincia "
        "FROM companies c "
        "JOIN cities ct ON c.city_id = ct.id "
        "WHERE c.is_active = true AND c.is_verified = true AND ct.provincia IS NOT NULL "
        "ORDER BY ct.provincia"
    )
    return [r["provincia"] for r in rows]


@router.get("/ciudades")
async def list_public_ciudades(
    request: Request,
    provincia: Optional[str] = Query(None, description="Filter cities by provincia"),
    db: asyncpg.Connection = Depends(get_database),
):
    """List distinct cities for directory filter dropdown. Optionally filtered by provincia."""
    await _check_public_rate_limit(request)
    if provincia:
        rows = await db.fetch(
            "SELECT DISTINCT ct.name "
            "FROM companies c "
            "JOIN cities ct ON c.city_id = ct.id "
            "WHERE c.is_active AND c.is_verified AND ct.provincia = $1 "
            "ORDER BY ct.name",
            provincia,
        )
    else:
        rows = await db.fetch(
            "SELECT DISTINCT ct.name "
            "FROM companies c "
            "JOIN cities ct ON c.city_id = ct.id "
            "WHERE c.is_active AND c.is_verified AND ct.name IS NOT NULL "
            "ORDER BY ct.name"
        )
    return [r["name"] for r in rows]


@router.get("/formas-juridicas")
async def list_public_formas_juridicas(
    request: Request,
    db: asyncpg.Connection = Depends(get_database),
):
    """List distinct formas juridicas with counts for directory filter. Cached 2min."""
    await _check_public_rate_limit(request)

    cache = get_cache()
    cache_key = "pub_dir:formas"
    try:
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached
    except Exception:
        pass

    rows = await db.fetch(
        "SELECT forma_juridica, COUNT(*) as count "
        "FROM companies "
        "WHERE is_active AND is_verified AND forma_juridica IS NOT NULL "
        "GROUP BY forma_juridica "
        "ORDER BY count DESC"
    )
    result = [{"value": r["forma_juridica"], "count": r["count"]} for r in rows]
    try:
        await cache.set(cache_key, result, ttl=FILTER_CACHE_TTL)
    except Exception:
        pass
    return result
