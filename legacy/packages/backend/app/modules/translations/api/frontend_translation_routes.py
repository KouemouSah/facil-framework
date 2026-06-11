"""
Frontend Translation API Routes - Manage frontend UI translations

Store and manage translations for frontend JSON files (next-intl).
Uses the `translations` table with category prefix 'frontend.'

Endpoints:
- GET /translations/frontend/namespaces - List all frontend namespaces
- GET /translations/frontend/export/{namespace} - Export namespace as JSON for frontend
- GET /translations/frontend/export-all - Export all frontend translations as JSON
- POST /translations/frontend/import - Import JSON translations
- GET /translations/frontend - Search frontend translations
- POST /translations/frontend - Create frontend translation
- PUT /translations/frontend/{id} - Update frontend translation
- DELETE /translations/frontend/{id} - Delete frontend translation

Prefix: /api/v1/translations/frontend
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from loguru import logger
import asyncpg
import json

from ..models.translation import (
    TranslationCreate,
    TranslationUpdate,
    TranslationResponse,
    TranslationListResponse,
)
from ..services.translation_service import TranslationService
from ..repositories.translation_repository import TranslationRepository
from app.database.connection import get_database as get_db
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.core.cache import get_translations_cache, CacheKeys, invalidate_translations_cache


router = APIRouter(prefix="/translations/frontend", tags=["Frontend Translations"])

# Frontend translation categories are prefixed with 'frontend.'
# Example: frontend.common, frontend.nav, frontend.admin
FRONTEND_CATEGORY_PREFIX = "frontend."


def flatten_json(data: dict, parent_key: str = '', sep: str = '.') -> Dict[str, str]:
    """
    Flatten nested JSON into dot-notation keys.

    Example:
        {"common": {"save": "Guardar"}} -> {"common.save": "Guardar"}
    """
    items = []
    for key, value in data.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        if isinstance(value, dict):
            items.extend(flatten_json(value, new_key, sep).items())
        else:
            items.append((new_key, str(value) if value is not None else ""))
    return dict(items)


def unflatten_json(data: Dict[str, str], sep: str = '.') -> dict:
    """
    Unflatten dot-notation keys back into nested JSON.

    Example:
        {"common.save": "Guardar"} -> {"common": {"save": "Guardar"}}
    """
    result = {}
    for key, value in data.items():
        parts = key.split(sep)
        current = result
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    return result


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@router.get("/namespaces")
async def list_frontend_namespaces(
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get list of all frontend translation namespaces

    Returns:
        List of namespace names (without 'frontend.' prefix)
    """
    query = """
        SELECT DISTINCT category FROM translations
        WHERE category LIKE 'frontend.%'
        ORDER BY category
    """
    results = await conn.fetch(query)

    namespaces = [r["category"].replace(FRONTEND_CATEGORY_PREFIX, "") for r in results]

    return {
        "namespaces": namespaces,
        "count": len(namespaces),
    }


@router.get("/stats")
async def get_frontend_translation_stats(
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get statistics about frontend translations

    Returns:
        Statistics by namespace and language coverage
    """
    # Count by namespace
    by_namespace_query = """
        SELECT category, COUNT(*) as count
        FROM translations
        WHERE category LIKE 'frontend.%'
        GROUP BY category
        ORDER BY category
    """
    by_ns_results = await conn.fetch(by_namespace_query)
    by_namespace = {
        r["category"].replace(FRONTEND_CATEGORY_PREFIX, ""): r["count"]
        for r in by_ns_results
    }

    # Total count
    total_query = """
        SELECT COUNT(*) FROM translations WHERE category LIKE 'frontend.%'
    """
    total = await conn.fetchval(total_query)

    # Check for missing translations (where es, fr, or en is empty or same as key_code)
    missing_query = """
        SELECT
            SUM(CASE WHEN es IS NULL OR es = '' THEN 1 ELSE 0 END) as missing_es,
            SUM(CASE WHEN fr IS NULL OR fr = '' THEN 1 ELSE 0 END) as missing_fr,
            SUM(CASE WHEN en IS NULL OR en = '' THEN 1 ELSE 0 END) as missing_en
        FROM translations
        WHERE category LIKE 'frontend.%'
    """
    missing = await conn.fetchrow(missing_query)

    return {
        "total_keys": total,
        "by_namespace": by_namespace,
        "missing_translations": {
            "es": missing["missing_es"] or 0,
            "fr": missing["missing_fr"] or 0,
            "en": missing["missing_en"] or 0,
        },
        "coverage": {
            "es": round(100 * (total - (missing["missing_es"] or 0)) / max(total, 1), 1),
            "fr": round(100 * (total - (missing["missing_fr"] or 0)) / max(total, 1), 1),
            "en": round(100 * (total - (missing["missing_en"] or 0)) / max(total, 1), 1),
        }
    }


@router.get("/export/{namespace}")
async def export_namespace_json(
    namespace: str,
    language: str = Query("es", description="Language to export (es, fr, en)"),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Export a namespace as nested JSON for frontend

    Uses translations cache (1h TTL) since translation data rarely changes.

    Args:
        namespace: Namespace to export (e.g., 'common', 'admin')
        language: Language code (es, fr, en)

    Returns:
        Nested JSON structure for next-intl
    """
    if language not in ["es", "fr", "en"]:
        raise HTTPException(status_code=400, detail="Invalid language code. Use es, fr, or en.")

    # Check cache first
    cache = get_translations_cache()
    cache_key = CacheKeys.translations(language, f"frontend.{namespace}")

    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    category = f"{FRONTEND_CATEGORY_PREFIX}{namespace}"

    query = f"""
        SELECT key_code, {language} as translation
        FROM translations
        WHERE category = $1
        ORDER BY key_code
    """
    results = await conn.fetch(query, category)

    # Build flat dict
    flat_translations = {r["key_code"]: r["translation"] for r in results}

    # Unflatten to nested JSON
    nested = unflatten_json(flat_translations)

    # Store in cache (1h TTL from get_translations_cache default)
    await cache.set(cache_key, nested)

    return nested


@router.get("/export-all")
async def export_all_frontend_json(
    language: str = Query("es", description="Language to export (es, fr, en)"),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Export ALL frontend translations as nested JSON

    This generates a complete messages/{lang}.json file content.
    Uses translations cache (1h TTL) since translation data rarely changes.

    Args:
        language: Language code (es, fr, en)

    Returns:
        Complete nested JSON structure for next-intl
    """
    if language not in ["es", "fr", "en"]:
        raise HTTPException(status_code=400, detail="Invalid language code. Use es, fr, or en.")

    # Check cache first
    cache = get_translations_cache()
    cache_key = CacheKeys.translations(language, "frontend._all")

    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    query = f"""
        SELECT
            REPLACE(category, 'frontend.', '') as namespace,
            key_code,
            {language} as translation
        FROM translations
        WHERE category LIKE 'frontend.%'
        ORDER BY category, key_code
    """
    results = await conn.fetch(query)

    # Build flat dict with full path
    flat_translations = {}
    for r in results:
        namespace = r["namespace"]
        key = r["key_code"]
        # Full path is namespace.key
        full_key = f"{namespace}.{key}" if key else namespace
        flat_translations[full_key] = r["translation"]

    # Unflatten to nested JSON
    nested = unflatten_json(flat_translations)

    # Store in cache (1h TTL from get_translations_cache default)
    await cache.set(cache_key, nested)

    return nested


@router.post("/import")
async def import_frontend_json(
    namespace: str = Query(..., description="Namespace to import into (e.g., 'common')"),
    language: str = Query(..., description="Language being imported (es, fr, en)"),
    data: Dict[str, Any] = None,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Import nested JSON translations for a namespace

    Args:
        namespace: Namespace (e.g., 'common', 'admin')
        language: Language being imported (es, fr, en)
        data: Nested JSON data

    Returns:
        Import result with counts
    """
    if language not in ["es", "fr", "en"]:
        raise HTTPException(status_code=400, detail="Invalid language code. Use es, fr, or en.")

    if not data:
        raise HTTPException(status_code=400, detail="No data provided")

    category = f"{FRONTEND_CATEGORY_PREFIX}{namespace}"
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub") if isinstance(current_user, dict) else None

    # Flatten the nested JSON
    flat_data = flatten_json(data)

    created_count = 0
    updated_count = 0
    errors = []

    repository = TranslationRepository()

    for key_code, translation_text in flat_data.items():
        try:
            # Check if exists
            existing = await repository.get_by_key(conn, category, key_code, None)

            if existing:
                # Update only the specific language
                update_kwargs = {language: translation_text}
                await repository.update(
                    conn,
                    existing["id"],
                    **{language: translation_text},
                    user_id=user_id,
                )
                updated_count += 1
            else:
                # Create with all languages (using same text for missing ones initially)
                await repository.create(
                    conn,
                    category=category,
                    key_code=key_code,
                    es=translation_text if language == "es" else "",
                    fr=translation_text if language == "fr" else "",
                    en=translation_text if language == "en" else "",
                    translation_source="import",
                    user_id=user_id,
                )
                created_count += 1

        except Exception as e:
            errors.append(f"Error importing {key_code}: {str(e)}")
            logger.error(f"Import error for {key_code}: {e}")

    # Invalidate translations cache after import
    if created_count > 0 or updated_count > 0:
        await invalidate_translations_cache()

    return {
        "namespace": namespace,
        "language": language,
        "created": created_count,
        "updated": updated_count,
        "total_processed": created_count + updated_count,
        "errors": errors[:10] if errors else [],  # Limit errors shown
        "error_count": len(errors),
    }


@router.post("/import-file")
async def import_frontend_json_file(
    file: UploadFile = File(...),
    namespace: str = Query(..., description="Namespace to import into"),
    language: str = Query(..., description="Language being imported"),
    conn: asyncpg.Connection = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Import translations from uploaded JSON file

    Args:
        file: JSON file to import
        namespace: Namespace
        language: Language

    Returns:
        Import result
    """
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="File must be JSON")

    try:
        content = await file.read()
        data = json.loads(content.decode('utf-8'))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    # Reuse the import endpoint logic
    return await import_frontend_json(
        namespace=namespace,
        language=language,
        data=data,
        conn=conn,
        current_user=current_user,
    )


class SyncFromJsonRequest(BaseModel):
    """Request body for sync-from-json endpoint"""
    es: Dict[str, Any]
    fr: Dict[str, Any]
    en: Dict[str, Any]

    class Config:
        extra = "forbid"


@router.post("/sync-from-json")
async def sync_frontend_from_json_files(
    data: SyncFromJsonRequest,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Sync all frontend translations from JSON data provided by the frontend.

    The frontend reads es.json, fr.json, en.json and sends them in the request body.
    This allows the backend to work in Cloud Run where it doesn't have access
    to the frontend's message files.

    Args:
        data: JSON object containing es, fr, en translation dictionaries

    Returns:
        Sync result with statistics
    """
    import traceback

    try:
        # current_user is a UserResponse Pydantic model, not a dict
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub") if isinstance(current_user, dict) else None
        logger.info(f"Starting sync-from-json for user: {user_id}")

        json_data = {
            "es": data.es,
            "fr": data.fr,
            "en": data.en,
        }

        logger.info(f"Received JSON data - es keys: {len(data.es)}, fr keys: {len(data.fr)}, en keys: {len(data.en)}")

        # Flatten all languages
        es_flat = flatten_json(json_data["es"])
        fr_flat = flatten_json(json_data["fr"])
        en_flat = flatten_json(json_data["en"])

        logger.info(f"Flattened - es: {len(es_flat)}, fr: {len(fr_flat)}, en: {len(en_flat)}")

        # Get all unique keys
        all_keys = set(es_flat.keys()) | set(fr_flat.keys()) | set(en_flat.keys())

        logger.info(f"Syncing {len(all_keys)} translation keys from JSON files")

        stats = {"created": 0, "updated": 0, "errors": 0, "total": len(all_keys)}
        errors = []

        # Process each key
        for full_key in all_keys:
            # Split key into namespace and remaining key
            parts = full_key.split('.', 1)
            if len(parts) == 1:
                namespace = parts[0]
                key_code = ""
            else:
                namespace = parts[0]
                key_code = parts[1]

            category = f"{FRONTEND_CATEGORY_PREFIX}{namespace}"

            es_value = es_flat.get(full_key, "")
            fr_value = fr_flat.get(full_key, "")
            en_value = en_flat.get(full_key, "")

            try:
                # Check if exists (handle NULL context)
                check_query = """
                    SELECT id FROM translations
                    WHERE category = $1 AND key_code = $2 AND context IS NULL
                """
                existing = await conn.fetchrow(check_query, category, key_code)

                if existing:
                    # Update
                    update_query = """
                        UPDATE translations
                        SET es = $2, fr = $3, en = $4, updated_at = NOW(),
                            updated_by = $5, version = version + 1
                        WHERE id = $1
                    """
                    await conn.execute(
                        update_query,
                        existing["id"],
                        es_value,
                        fr_value,
                        en_value,
                        user_id,
                    )
                    stats["updated"] += 1
                else:
                    # Insert
                    insert_query = """
                        INSERT INTO translations (
                            category, key_code, context, es, fr, en,
                            description, translation_source,
                            created_by, updated_by, created_at, updated_at, version
                        )
                        VALUES ($1, $2, NULL, $3, $4, $5, NULL, 'json_sync', $6, $6, NOW(), NOW(), 1)
                    """
                    await conn.execute(
                        insert_query,
                        category,
                        key_code,
                        es_value,
                        fr_value,
                        en_value,
                        user_id,
                    )
                    stats["created"] += 1

            except Exception as e:
                logger.error(f"Error syncing {full_key}: {e}")
                errors.append(f"{full_key}: {str(e)}")
                stats["errors"] += 1

        logger.info(f"Sync complete: {stats}")

        # Invalidate translations cache after sync
        if stats["created"] > 0 or stats["updated"] > 0:
            await invalidate_translations_cache()

        return {
            "message": "Sync completed",
            "stats": stats,
            "errors": errors[:10] if errors else [],
            "namespaces_synced": list(set(k.split('.')[0] for k in all_keys)),
        }

    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Fatal error in sync-from-json: {e}\n{error_trace}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "type": type(e).__name__,
                "trace": error_trace.split("\n")[-5:],  # Last 5 lines of traceback
            }
        )


# ============================================================================
# CRUD ENDPOINTS
# ============================================================================

@router.get("/", response_model=TranslationListResponse)
async def search_frontend_translations(
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    key_code: Optional[str] = Query(None, description="Search in key_code"),
    search_term: Optional[str] = Query(None, description="Search in translation text"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Search frontend translations

    Args:
        namespace: Optional namespace filter
        key_code: Optional key_code search (partial)
        search_term: Optional text search
        limit: Max results
        offset: Pagination offset

    Returns:
        Paginated list of translations
    """
    service = TranslationService()

    category = f"{FRONTEND_CATEGORY_PREFIX}{namespace}" if namespace else None

    # If no namespace specified, search all frontend categories
    if not category:
        # Custom search for all frontend categories
        where_parts = ["category LIKE 'frontend.%'"]
        params = []
        param_counter = 1

        if key_code:
            where_parts.append(f"key_code ILIKE ${param_counter}")
            params.append(f"%{key_code}%")
            param_counter += 1

        if search_term:
            where_parts.append(f"(es ILIKE ${param_counter} OR fr ILIKE ${param_counter} OR en ILIKE ${param_counter})")
            params.append(f"%{search_term}%")
            param_counter += 1

        where_clause = " AND ".join(where_parts)

        count_query = f"SELECT COUNT(*) FROM translations WHERE {where_clause}"
        total = await conn.fetchval(count_query, *params)

        params.extend([limit, offset])
        data_query = f"""
            SELECT * FROM translations
            WHERE {where_clause}
            ORDER BY category, key_code
            LIMIT ${param_counter} OFFSET ${param_counter + 1}
        """
        results = await conn.fetch(data_query, *params)
        translations = [dict(r) for r in results]

        return {
            "translations": translations,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    # With specific namespace - use TranslationSearchParams
    from ..models.translation import TranslationSearchParams
    search_params = TranslationSearchParams(
        category=category,
        key_code=key_code,
        search_term=search_term,
        limit=limit,
        offset=offset,
    )
    translations, total = await service.search_translations(conn, search_params)

    return {
        "translations": translations,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/", response_model=TranslationResponse)
async def create_frontend_translation(
    namespace: str = Query(..., description="Namespace"),
    key_code: str = Query(..., description="Key code (dot notation)"),
    es: str = Query(..., description="Spanish translation"),
    fr: str = Query(..., description="French translation"),
    en: str = Query(..., description="English translation"),
    description: Optional[str] = Query(None, description="Description"),
    conn: asyncpg.Connection = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Create a single frontend translation

    Args:
        namespace: Namespace (e.g., 'common')
        key_code: Key code (e.g., 'save' or 'buttons.save')
        es, fr, en: Translations
        description: Optional description

    Returns:
        Created translation
    """
    service = TranslationService()
    category = f"{FRONTEND_CATEGORY_PREFIX}{namespace}"
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub") if isinstance(current_user, dict) else None

    translation_data = TranslationCreate(
        category=category,
        key_code=key_code,
        context=None,
        es=es,
        fr=fr,
        en=en,
        description=description,
        translation_source="manual",
    )

    try:
        result = await service.create_translation(conn, translation_data, user_id)
        return result
    except Exception as e:
        if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Translation already exists")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{translation_id}", response_model=TranslationResponse)
async def update_frontend_translation(
    translation_id: int,
    update_data: TranslationUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Update a frontend translation

    Args:
        translation_id: Translation ID
        update_data: Update data

    Returns:
        Updated translation
    """
    service = TranslationService()
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub") if isinstance(current_user, dict) else None

    result = await service.update_translation(conn, translation_id, update_data, user_id)

    if result is None:
        raise HTTPException(status_code=404, detail="Translation not found")

    return result


@router.delete("/{translation_id}")
async def delete_frontend_translation(
    translation_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Delete a frontend translation

    Args:
        translation_id: Translation ID

    Returns:
        Success message
    """
    service = TranslationService()

    deleted = await service.delete_translation(conn, translation_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Translation not found")

    return {"message": "Translation deleted successfully"}


# ============================================================================
# GITHUB PUBLISHING ENDPOINT
# ============================================================================

GITHUB_REPO_OWNER = "KouemouSah"
GITHUB_REPO_NAME = "taxasge"
GITHUB_BRANCH = "develop"
GITHUB_MESSAGE_FILES_PATH = "packages/web/messages"


def deep_merge_dicts(base: dict, updates: dict) -> dict:
    """
    Deep merge two dictionaries. Updates values from 'updates' into 'base',
    preserving keys in 'base' that don't exist in 'updates'.
    """
    result = base.copy()
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


@router.post("/publish-to-github")
async def publish_translations_to_github(
    conn: asyncpg.Connection = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Publish frontend translations to GitHub repository.

    Exports translations from database and MERGES them with existing file content,
    preserving keys that exist in the file but not in the database.
    Then commits to GitHub, which triggers the frontend deployment workflow.

    Requires:
        - GitHub PAT configured in Secret Manager (github-pat)
        - User must be authenticated

    Returns:
        Commit URL and deployment status
    """
    import httpx
    import base64
    from app.core.secrets import get_github_pat

    # Get GitHub PAT from Secret Manager
    github_token = get_github_pat()
    if not github_token:
        raise HTTPException(
            status_code=500,
            detail="GitHub PAT not configured. Please add 'github-pat' secret in Secret Manager."
        )

    user_id = current_user.id if hasattr(current_user, 'id') else None
    logger.info(f"Publishing translations to GitHub by user: {user_id}")

    # GitHub API setup
    github_api = "https://api.github.com"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        # Export translations for each language
        languages = ["es", "fr", "en"]
        db_translations = {}

        for lang in languages:
            query = f"""
                SELECT
                    REPLACE(category, 'frontend.', '') as namespace,
                    key_code,
                    {lang} as translation
                FROM translations
                WHERE category LIKE 'frontend.%'
                ORDER BY category, key_code
            """
            results = await conn.fetch(query)

            # Build flat dict with full path
            flat_translations = {}
            for r in results:
                namespace = r["namespace"]
                key = r["key_code"]
                full_key = f"{namespace}.{key}" if key else namespace
                flat_translations[full_key] = r["translation"] or ""

            # Unflatten to nested JSON
            db_translations[lang] = unflatten_json(flat_translations)

        logger.info(f"Exported DB translations for {len(languages)} languages")

        commit_results = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for lang in languages:
                file_path = f"{GITHUB_MESSAGE_FILES_PATH}/{lang}.json"

                # Get current file content and SHA from GitHub
                get_url = f"{github_api}/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents/{file_path}?ref={GITHUB_BRANCH}"
                get_resp = await client.get(get_url, headers=headers)

                sha = None
                existing_content = {}

                if get_resp.status_code == 200:
                    resp_data = get_resp.json()
                    sha = resp_data.get("sha")
                    # Decode existing file content
                    try:
                        encoded_content = resp_data.get("content", "")
                        decoded_bytes = base64.b64decode(encoded_content)
                        existing_content = json.loads(decoded_bytes.decode("utf-8"))
                        logger.info(f"Fetched existing {lang}.json with {len(existing_content)} top-level keys")
                    except Exception as e:
                        logger.warning(f"Could not decode existing {lang}.json: {e}")
                        existing_content = {}
                elif get_resp.status_code != 404:
                    logger.error(f"GitHub API error getting {file_path}: {get_resp.text}")

                # Merge existing content with DB translations
                # This preserves keys in the file that don't exist in the database
                merged_content = deep_merge_dicts(existing_content, db_translations[lang])
                content = json.dumps(merged_content, ensure_ascii=False, indent=2)
                logger.info(f"Merged {lang}.json: {len(existing_content)} existing + DB updates = {len(merged_content)} top-level keys")

                # Update/Create file
                put_url = f"{github_api}/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents/{file_path}"
                put_data = {
                    "message": f"chore(i18n): Update {lang}.json translations from admin UI",
                    "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                    "branch": GITHUB_BRANCH,
                }
                if sha:
                    put_data["sha"] = sha

                put_resp = await client.put(put_url, headers=headers, json=put_data)

                if put_resp.status_code in [200, 201]:
                    result = put_resp.json()
                    commit_results.append({
                        "file": f"{lang}.json",
                        "status": "updated" if sha else "created",
                        "commit_sha": result.get("commit", {}).get("sha", "")[:7],
                        "commit_url": result.get("commit", {}).get("html_url", ""),
                    })
                    logger.info(f"✅ {lang}.json published to GitHub")
                else:
                    error_msg = put_resp.json().get("message", put_resp.text)
                    logger.error(f"❌ Failed to publish {lang}.json: {error_msg}")
                    commit_results.append({
                        "file": f"{lang}.json",
                        "status": "failed",
                        "error": error_msg,
                    })

        # Check if all succeeded
        success_count = sum(1 for r in commit_results if r["status"] in ["updated", "created"])

        if success_count == 3:
            return {
                "message": "Translations published to GitHub successfully!",
                "status": "success",
                "files": commit_results,
                "deployment_note": "Frontend deployment will start automatically via GitHub Actions (~5-10 min)",
                "branch": GITHUB_BRANCH,
            }
        elif success_count > 0:
            return {
                "message": f"Partial success: {success_count}/3 files published",
                "status": "partial",
                "files": commit_results,
            }
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Failed to publish translations",
                    "files": commit_results,
                }
            )

    except httpx.HTTPError as e:
        logger.error(f"HTTP error publishing to GitHub: {e}")
        raise HTTPException(status_code=500, detail=f"GitHub API error: {str(e)}")
    except Exception as e:
        logger.error(f"Error publishing to GitHub: {e}")
        raise HTTPException(status_code=500, detail=str(e))
