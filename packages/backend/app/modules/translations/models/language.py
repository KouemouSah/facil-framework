"""
Language Models - Supported languages for translations

Default language: Spanish (es) - Equatorial Guinea official language
Also supported: French (fr), English (en)
"""

from enum import Enum
from typing import List


class Language(str, Enum):
    """
    Supported languages for TaxasGE Platform

    Based on Equatorial Guinea's linguistic landscape:
    - Spanish: Official language, primary
    - French: Official language, secondary
    - English: International business language
    """
    SPANISH = "es"
    FRENCH = "fr"
    ENGLISH = "en"

    @property
    def display_name(self) -> str:
        """Get display name for language"""
        return {
            Language.SPANISH: "Español",
            Language.FRENCH: "Français",
            Language.ENGLISH: "English",
        }[self]

    @property
    def native_name(self) -> str:
        """Get native name for language"""
        return {
            Language.SPANISH: "Español",
            Language.FRENCH: "Français",
            Language.ENGLISH: "English",
        }[self]

    @classmethod
    def from_code(cls, code: str) -> "Language":
        """
        Get Language from code (case-insensitive)

        Args:
            code: Language code (es, fr, en)

        Returns:
            Language enum

        Raises:
            ValueError: If code is not supported
        """
        code_lower = code.lower().strip()

        # Handle both 2-letter and extended codes
        if code_lower in ["es", "spa", "spanish", "español"]:
            return cls.SPANISH
        elif code_lower in ["fr", "fra", "french", "français"]:
            return cls.FRENCH
        elif code_lower in ["en", "eng", "english"]:
            return cls.ENGLISH
        else:
            raise ValueError(f"Unsupported language code: {code}")

    @classmethod
    def from_accept_language(cls, accept_language: str) -> "Language":
        """
        Parse Accept-Language header and return best match

        Args:
            accept_language: Accept-Language header value

        Returns:
            Best matching Language, defaults to Spanish

        Examples:
            "es-ES,es;q=0.9,en;q=0.8" -> Language.SPANISH
            "fr-FR,fr;q=0.9" -> Language.FRENCH
            "en-US,en;q=0.9" -> Language.ENGLISH
        """
        if not accept_language:
            return cls.SPANISH

        # Parse accept-language header
        # Format: "es-ES,es;q=0.9,en;q=0.8,fr;q=0.7"
        languages = []
        for lang in accept_language.split(","):
            # Remove quality factor
            lang_code = lang.split(";")[0].strip()
            # Get primary language code
            primary = lang_code.split("-")[0].lower()
            languages.append(primary)

        # Find first supported language
        for lang_code in languages:
            try:
                return cls.from_code(lang_code)
            except ValueError:
                continue

        # Default to Spanish
        return cls.SPANISH


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_default_language() -> Language:
    """
    Get default language for platform

    Returns:
        Language.SPANISH (Equatorial Guinea official language)
    """
    return Language.SPANISH


def get_supported_languages() -> List[Language]:
    """
    Get list of all supported languages

    Returns:
        List of Language enums
    """
    return [Language.SPANISH, Language.FRENCH, Language.ENGLISH]


def get_language_names() -> dict[Language, str]:
    """
    Get mapping of languages to display names

    Returns:
        Dictionary {Language: display_name}
    """
    return {lang: lang.display_name for lang in get_supported_languages()}


def validate_language(language: str) -> Language:
    """
    Validate and convert language string to Language enum

    Args:
        language: Language code string

    Returns:
        Language enum

    Raises:
        ValueError: If language not supported
    """
    try:
        return Language.from_code(language)
    except ValueError as e:
        raise ValueError(
            f"Unsupported language '{language}'. "
            f"Supported: {', '.join(lang.value for lang in get_supported_languages())}"
        ) from e
