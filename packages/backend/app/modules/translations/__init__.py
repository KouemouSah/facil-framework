"""
Translations Module - Centralized multilingual content management

Handles all application translations:
- System translations (table: translations) - ENUMs, UI, Forms, Messages
- Entity translations (table: entity_translations) - Ministries, Sectors, Categories
- Frontend UI translations (JSON sync) - next-intl message files
- Language detection and management

Supported languages:
- Spanish (es) - Default (Equatorial Guinea official)
- French (fr) - Secondary official
- English (en) - International

Architecture: 3-tier (Routes → Services → Repositories)

API Endpoints:
- /api/v1/translations - System translations CRUD
- /api/v1/translations/entities - Entity translations CRUD
- /api/v1/translations/frontend - Frontend UI translations (JSON sync)
"""

from app.modules.translations.models.language import Language, get_default_language, get_supported_languages
from app.modules.translations.services.translation_service import TranslationService
from app.modules.translations.services.language_service import LanguageService
from app.modules.translations.services.entity_translation_service import EntityTranslationService
from app.modules.translations.models.entity_translation import (
    TranslatableEntityType,
    LanguageCode,
    EntityTranslationCreate,
    EntityTranslationResponse,
)

__all__ = [
    # Language utilities
    "Language",
    "get_default_language",
    "get_supported_languages",
    # System translations
    "TranslationService",
    "LanguageService",
    # Entity translations
    "EntityTranslationService",
    "TranslatableEntityType",
    "LanguageCode",
    "EntityTranslationCreate",
    "EntityTranslationResponse",
]
