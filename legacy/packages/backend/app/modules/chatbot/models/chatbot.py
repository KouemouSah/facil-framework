"""
Chatbot Models - AI-powered assistance for TaxasGE

Pydantic models for chatbot, AI search, document analysis, translations, and guidance.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════


class LanguageCode(str, Enum):
    """Supported languages"""
    SPANISH = "es"
    FRENCH = "fr"
    ENGLISH = "en"


class AnalysisType(str, Enum):
    """Document analysis types"""
    GENERAL = "general"
    FISCAL = "fiscal"
    LEGAL = "legal"
    IDENTITY = "identity"


# ═══════════════════════════════════════════════════════════════════════════
# CHAT MODELS
# ═══════════════════════════════════════════════════════════════════════════


class ChatMessage(BaseModel):
    """Single chat message"""
    role: str = Field(..., description="Message role: user, assistant, system")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConversationContext(BaseModel):
    """Conversation context"""
    user_id: Optional[str] = None
    user_role: str = "guest"
    language: LanguageCode = LanguageCode.SPANISH
    conversation_id: Optional[str] = None
    additional_context: Dict[str, Any] = Field(default_factory=dict)


class ChatHistoryMessage(BaseModel):
    """Message in conversation history"""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Chat request"""
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
    language: LanguageCode = LanguageCode.SPANISH
    context: Optional[Dict[str, Any]] = None
    history: Optional[List[ChatHistoryMessage]] = Field(
        default=None,
        description="Previous messages in the conversation for context continuity"
    )


class ChatResponse(BaseModel):
    """Chat response"""
    response: str
    conversation_id: str
    suggestions: List[str] = Field(default_factory=list)
    related_services: List[Dict[str, Any]] = Field(default_factory=list)
    follow_up_actions: List[str] = Field(default_factory=list)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.8
    response_time: float = 0.0
    language: LanguageCode
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# AI SEARCH MODELS
# ═══════════════════════════════════════════════════════════════════════════


class AISearchRequest(BaseModel):
    """AI-powered search request"""
    query: str = Field(..., min_length=1, max_length=500)
    language: LanguageCode = LanguageCode.SPANISH
    filters: Optional[Dict[str, Any]] = None
    limit: int = Field(10, ge=1, le=50)


class AISearchResponse(BaseModel):
    """AI search response"""
    results: List[Dict[str, Any]]
    total: int
    query_understanding: str
    search_intent: Optional[str] = None
    suggestions: List[str] = Field(default_factory=list)
    related_topics: List[str] = Field(default_factory=list)
    semantic_matches: List[Dict[str, Any]] = Field(default_factory=list)
    language: LanguageCode
    response_time: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════
# RECOMMENDATION MODELS
# ═══════════════════════════════════════════════════════════════════════════


class RecommendationRequest(BaseModel):
    """Service recommendation request"""
    user_intent: str = Field(..., min_length=1, max_length=500)
    context: Optional[Dict[str, Any]] = None
    language: LanguageCode = LanguageCode.SPANISH


class RecommendationResponse(BaseModel):
    """Service recommendation response"""
    recommendations: List[Dict[str, Any]]
    explanation: str
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    alternative_options: List[Dict[str, Any]] = Field(default_factory=list)
    estimated_cost: Optional[Dict[str, Any]] = None
    estimated_time: Optional[Dict[str, Any]] = None
    required_documents: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    language: LanguageCode


# ═══════════════════════════════════════════════════════════════════════════
# DOCUMENT ANALYSIS MODELS
# ═══════════════════════════════════════════════════════════════════════════


class DocumentAnalysisRequest(BaseModel):
    """Document analysis request"""
    analysis_type: AnalysisType = AnalysisType.GENERAL
    language: LanguageCode = LanguageCode.SPANISH


class DocumentAnalysisResponse(BaseModel):
    """Document analysis response"""
    analysis: Dict[str, Any]
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    document_type: str = "unknown"
    confidence: float = 0.0
    suggestions: List[str] = Field(default_factory=list)
    required_actions: List[str] = Field(default_factory=list)
    validation_status: Dict[str, Any] = Field(default_factory=dict)
    language: LanguageCode
    file_info: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════════════════
# TRANSLATION MODELS
# ═══════════════════════════════════════════════════════════════════════════


class TranslationRequest(BaseModel):
    """Translation request"""
    text: str = Field(..., min_length=1, max_length=5000)
    source_language: LanguageCode
    target_language: LanguageCode
    context: Optional[str] = None


class TranslationResponse(BaseModel):
    """Translation response"""
    translated_text: str
    source_language: LanguageCode
    target_language: LanguageCode
    confidence: float = 0.0
    alternatives: List[str] = Field(default_factory=list)
    detected_language: Optional[LanguageCode] = None
    translation_time: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════
# GUIDANCE MODELS
# ═══════════════════════════════════════════════════════════════════════════


class GuidanceRequest(BaseModel):
    """Process guidance request"""
    service_id: Optional[str] = None
    process_type: str = Field(..., min_length=1)
    language: LanguageCode = LanguageCode.SPANISH
    current_step: Optional[int] = None


class GuidanceResponse(BaseModel):
    """Process guidance response"""
    steps: List[Dict[str, Any]]
    current_step: int = 1
    total_steps: int = 0
    estimated_time: Optional[Dict[str, Any]] = None
    required_documents: List[str] = Field(default_factory=list)
    tips: List[str] = Field(default_factory=list)
    common_issues: List[str] = Field(default_factory=list)
    next_actions: List[str] = Field(default_factory=list)
    help_resources: List[Dict[str, Any]] = Field(default_factory=list)
    language: LanguageCode


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATION MODELS
# ═══════════════════════════════════════════════════════════════════════════


class ValidationRequest(BaseModel):
    """Form validation request"""
    form_data: Dict[str, Any]
    form_type: str = Field(..., min_length=1)
    language: LanguageCode = LanguageCode.SPANISH


class ValidationResponse(BaseModel):
    """Form validation response"""
    is_valid: bool
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    corrected_data: Optional[Dict[str, Any]] = None
    completeness_score: float = 0.0
    required_fields: List[str] = Field(default_factory=list)
    optional_improvements: List[str] = Field(default_factory=list)
    language: LanguageCode
