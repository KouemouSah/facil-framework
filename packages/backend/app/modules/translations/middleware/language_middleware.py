"""
Language Detection Middleware - Detects user language from headers

Detects language from:
1. Query parameter: ?lang=es
2. Accept-Language header
3. Cookie: language=es (future)
4. User preferences in database (future)

Module: Translations
"""

from typing import Optional
from fastapi import Request
from loguru import logger

from app.modules.translations.models.language import Language, get_default_language


def detect_language(request: Request) -> Language:
    """
    Detect language from request

    Priority:
    1. Query parameter (?lang=es)
    2. Accept-Language header
    3. Default to Spanish

    Args:
        request: FastAPI request object

    Returns:
        Detected Language enum
    """
    # 1. Check query parameter
    lang_param = request.query_params.get("lang")
    if lang_param:
        try:
            language = Language.from_code(lang_param)
            logger.debug(f"Language detected from query param: {language.value}")
            return language
        except ValueError:
            logger.warning(f"Invalid language in query param: {lang_param}")

    # 2. Check Accept-Language header
    accept_language = request.headers.get("Accept-Language")
    if accept_language:
        language = Language.from_accept_language(accept_language)
        logger.debug(f"Language detected from header: {language.value}")
        return language

    # 3. Default to Spanish
    default_lang = get_default_language()
    logger.debug(f"Using default language: {default_lang.value}")
    return default_lang


def get_language_from_request(request: Request, default: Optional[Language] = None) -> Language:
    """
    Get language from request with optional default override

    Args:
        request: FastAPI request object
        default: Optional default language override

    Returns:
        Language enum
    """
    if default is None:
        default = get_default_language()

    try:
        return detect_language(request)
    except Exception as e:
        logger.error(f"Error detecting language: {e}")
        return default


async def language_middleware(request: Request, call_next):
    """
    FastAPI middleware for language detection

    Adds detected language to request.state for easy access

    Usage in FastAPI:
        app.middleware("http")(language_middleware)

    Then in routes:
        language = request.state.language

    Args:
        request: FastAPI request
        call_next: Next middleware/route

    Returns:
        Response
    """
    # Detect and store language in request state
    request.state.language = detect_language(request)

    logger.debug(
        f"Request language: {request.state.language.value} "
        f"(path: {request.url.path})"
    )

    response = await call_next(request)
    return response
