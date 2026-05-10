"""
Language Service - Business logic for language management

Handles:
- Supported languages
- Language detection
- Language preferences
- Language statistics

Module: Translations
"""

from typing import List, Dict
from loguru import logger

from app.modules.translations.models.language import (
    Language,
    get_default_language,
    get_supported_languages,
    get_language_names,
)


class LanguageService:
    """Service for language management"""

    def __init__(self):
        """Initialize language service"""
        logger.info("LanguageService initialized")

    def get_supported_languages(self) -> List[Language]:
        """
        Get list of all supported languages

        Returns:
            List of Language enums
        """
        return get_supported_languages()

    def get_default_language(self) -> Language:
        """
        Get default platform language

        Returns:
            Language.SPANISH
        """
        return get_default_language()

    def get_language_info(self) -> List[Dict[str, str]]:
        """
        Get information about all supported languages

        Returns:
            List of dicts with language info
        """
        return [
            {
                "code": lang.value,
                "name": lang.display_name,
                "native_name": lang.native_name,
                "is_default": lang == get_default_language(),
            }
            for lang in get_supported_languages()
        ]

    def detect_language_from_header(self, accept_language: str) -> Language:
        """
        Detect language from Accept-Language header

        Args:
            accept_language: Accept-Language header value

        Returns:
            Detected language (defaults to Spanish)
        """
        return Language.from_accept_language(accept_language)

    def validate_language_code(self, code: str) -> Language:
        """
        Validate and parse language code

        Args:
            code: Language code string

        Returns:
            Language enum

        Raises:
            ValueError: If language code is invalid
        """
        return Language.from_code(code)

    def is_supported_language(self, code: str) -> bool:
        """
        Check if language code is supported

        Args:
            code: Language code

        Returns:
            True if supported
        """
        try:
            Language.from_code(code)
            return True
        except ValueError:
            return False

    def get_language_name(self, language: Language) -> str:
        """
        Get display name for language

        Args:
            language: Language enum

        Returns:
            Display name
        """
        return language.display_name

    def get_fallback_language(self, preferred_language: Language) -> Language:
        """
        Get fallback language if preferred is not available

        Args:
            preferred_language: Preferred language

        Returns:
            Fallback language (always Spanish for GQ)
        """
        # Always fallback to Spanish (official language of Equatorial Guinea)
        return get_default_language()
