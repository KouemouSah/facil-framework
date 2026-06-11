"""
Chatbot Routes - AI-powered assistance API

Migrated from app/api/v1/ai_services.py to modern module architecture
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Request, status, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, AsyncGenerator
from loguru import logger
import json

from app.modules.chatbot.models import (
    ChatRequest,
    ChatResponse,
    AISearchRequest,
    AISearchResponse,
    RecommendationRequest,
    RecommendationResponse,
    DocumentAnalysisRequest,
    DocumentAnalysisResponse,
    TranslationRequest,
    TranslationResponse,
    GuidanceRequest,
    GuidanceResponse,
    ValidationRequest,
    ValidationResponse,
    LanguageCode,
)
from app.modules.chatbot.services import chatbot_service
from app.modules.auth.middleware.auth_middleware import get_current_user, get_current_user_optional
from app.modules.users.models import UserResponse
from app.database.connection import get_database as get_db
from app.core.cache import check_rate_limit
from app.config import get_settings
import asyncpg

router = APIRouter(tags=["Chatbot"])


# ============================================================================
# INFORMATION ENDPOINT
# ============================================================================

@router.get("/", response_model=Dict[str, Any])
async def get_chatbot_info():
    """Get Chatbot API information and capabilities"""
    from app.modules.chatbot.services import embedding_service, gemini_service

    # Check actual service status
    ai_status = "active" if (embedding_service.enabled and gemini_service.enabled) else "fallback_mode"

    return {
        "message": "TaxasGE Chatbot & AI Services API",
        "version": "2.0.0",
        "description": "AI-powered assistance for fiscal services and document processing",
        "status": ai_status,
        "note": "RAG-powered AI with Gemini" if ai_status == "active" else "AI services unavailable - using fallback responses",
        "endpoints": {
            "chat": "POST /chat - Interactive AI chat assistance",
            "stream": "POST /chat/stream - Streaming AI chat",
            "search": "POST /search - AI-powered service search",
            "recommend": "POST /recommend - Service recommendations",
            "analyze": "POST /analyze-document - Document analysis",
            "translate": "POST /translate - Text translation",
            "guide": "POST /guide - Step-by-step guidance",
            "validate": "POST /validate - Form validation assistance",
            "stats": "GET /stats - Usage statistics (admin)",
            "feedback": "POST /feedback - Submit feedback"
        },
        "features": [
            "Multilingual AI chat (Spanish, French, English)",
            "Intelligent fiscal service search and recommendations",
            "Document analysis and data extraction (pending)",
            "Real-time translation services (pending)",
            "Step-by-step procedure guidance",
            "Form validation and error correction",
            "Contextual help and explanations"
        ],
        "supported_languages": ["es", "fr", "en"],
        "services": {
            "embedding": {
                "enabled": embedding_service.enabled,
                "model": embedding_service.get_stats().get("model") if embedding_service.enabled else None
            },
            "gemini": {
                "enabled": gemini_service.enabled
            }
        }
    }


@router.get("/status", response_model=Dict[str, Any])
async def get_chatbot_status(db: asyncpg.Connection = Depends(get_db)):
    """
    Get detailed chatbot service status for debugging

    Returns status of:
    - Embedding service (Vertex AI)
    - Gemini service (Vertex AI)
    - Overall RAG availability
    - Database embedding coverage
    """
    from app.modules.chatbot.services import embedding_service, gemini_service, chatbot_service
    from app.config import settings

    # Get embedding stats from database
    embedding_db_stats = {}
    try:
        # Direct query to check embedding coverage
        stats = await db.fetchrow("""
            SELECT
                COUNT(*) as total_services,
                COUNT(embedding) as with_embeddings,
                COUNT(*) - COUNT(embedding) as without_embeddings,
                ROUND(COUNT(embedding)::numeric / NULLIF(COUNT(*), 0) * 100, 2) as coverage_percentage
            FROM fiscal_services
            WHERE status = 'active'
        """)
        if stats:
            embedding_db_stats = dict(stats)
    except Exception as e:
        embedding_db_stats = {"error": str(e)}

    return {
        "overall_status": "active" if chatbot_service.enabled else "fallback_mode",
        "provider": chatbot_service.provider,
        "services": {
            "embedding": {
                "enabled": embedding_service.enabled,
                "stats": embedding_service.get_stats() if embedding_service.enabled else {"error": "Service disabled"}
            },
            "gemini": {
                "enabled": gemini_service.enabled,
                "chat_model": settings.GEMINI_CHAT_MODEL,
                "pro_model": settings.GEMINI_PRO_MODEL
            }
        },
        "database": {
            "embedding_coverage": embedding_db_stats,
            "note": "If with_embeddings is 0, run the populate_embeddings script"
        },
        "config": {
            "project": settings.GOOGLE_CLOUD_PROJECT,
            "location": settings.GOOGLE_CLOUD_LOCATION,
            "embedding_model": settings.GEMINI_EMBEDDING_MODEL,
            "max_context_services": settings.RAG_MAX_CONTEXT_SERVICES,
            "similarity_threshold": settings.SEMANTIC_SEARCH_SIMILARITY_THRESHOLD
        },
        "troubleshooting": {
            "if_fallback": [
                "Check GOOGLE_CLOUD_PROJECT env var is set correctly",
                "Check GOOGLE_CLOUD_LOCATION env var is set correctly",
                "Verify Cloud Run service account has Vertex AI permissions",
                "Check google-cloud-aiplatform is installed in requirements.txt"
            ],
            "if_no_results": [
                "Check database.embedding_coverage.with_embeddings > 0",
                "If 0, run: python scripts/populate_embeddings.py",
                "Or trigger GitHub Actions workflow_dispatch for embeddings job"
            ]
        }
    }


# ============================================================================
# DEBUG ENDPOINT - Semantic Search Test (Protected: admin only)
# ============================================================================

@router.get("/debug/search", response_model=Dict[str, Any])
async def debug_semantic_search(
    query: str = Query(..., description="Search query to test"),
    threshold: float = Query(0.1, description="Similarity threshold (0-1)"),
    limit: int = Query(10, description="Max results"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Debug endpoint to test semantic search directly (staging only).
    Returns 404 in production.
    """
    _settings = get_settings()
    if _settings.environment == "production":
        raise HTTPException(status_code=404, detail="Not found")
    from app.modules.chatbot.services import embedding_service

    result = {
        "query": query,
        "threshold": threshold,
        "limit": limit,
        "embedding_service_enabled": embedding_service.enabled,
        "query_embedding": None,
        "search_results": [],
        "raw_sql_test": None,
        "error": None
    }

    try:
        # Step 1: Generate query embedding
        query_embedding = await embedding_service.generate_query_embedding(query)

        if not query_embedding:
            result["error"] = "Failed to generate query embedding"
            return result

        result["query_embedding"] = {
            "dimensions": len(query_embedding),
            "first_5_values": query_embedding[:5],
            "last_5_values": query_embedding[-5:]
        }

        # Step 2: Test raw SQL query directly (simpler query for debugging)
        embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

        # Simple test query without all the joins
        test_query = """
            SELECT
                fs.id,
                fs.service_code,
                fs.name_es,
                (1 - (fs.embedding <=> $1::vector))::FLOAT as similarity
            FROM fiscal_services fs
            WHERE fs.status = 'active'
              AND fs.embedding IS NOT NULL
            ORDER BY fs.embedding <=> $1::vector
            LIMIT $2
        """

        try:
            raw_results = await db.fetch(test_query, embedding_str, limit)
            result["raw_sql_test"] = {
                "success": True,
                "count": len(raw_results),
                "results": [
                    {
                        "id": r["id"],
                        "service_code": r["service_code"],
                        "name_es": r["name_es"][:50] if r["name_es"] else None,
                        "similarity": float(r["similarity"]) if r["similarity"] else 0
                    }
                    for r in raw_results[:5]
                ]
            }
        except Exception as sql_err:
            result["raw_sql_test"] = {
                "success": False,
                "error": str(sql_err)
            }

        # Step 3: Check if embeddings exist in DB
        count_query = """
            SELECT
                COUNT(*) as total,
                COUNT(embedding) as with_embedding
            FROM fiscal_services
            WHERE status = 'active'
        """
        counts = await db.fetchrow(count_query)
        result["db_counts"] = {
            "total_active": counts["total"],
            "with_embedding": counts["with_embedding"]
        }

        # Step 4: Check embedding dimensions in DB (sample first row)
        try:
            dimension_query = """
                SELECT
                    fs.service_code,
                    array_length(fs.embedding::real[], 1) as embedding_dim,
                    fs.embedding_model
                FROM fiscal_services fs
                WHERE fs.embedding IS NOT NULL
                LIMIT 1
            """
            dim_result = await db.fetchrow(dimension_query)
            if dim_result:
                result["db_embedding_sample"] = {
                    "service_code": dim_result["service_code"],
                    "stored_dimensions": dim_result["embedding_dim"],
                    "model": dim_result["embedding_model"],
                    "query_dimensions": len(query_embedding),
                    "dimensions_match": dim_result["embedding_dim"] == len(query_embedding)
                }
        except Exception as dim_err:
            result["db_embedding_sample"] = {"error": str(dim_err)}

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Debug search error: {e}", exc_info=True)

    return result


# ============================================================================
# CONVERSATION HISTORY ENDPOINT
# ============================================================================

@router.get("/conversations/{conversation_id}")
async def get_conversation_history(
    conversation_id: str,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Load conversation history from database.

    Returns stored messages for a given conversation_id.
    If user is authenticated, also verifies ownership.
    """
    query = "SELECT messages, language, message_count, last_message_at, user_id FROM chatbot_conversations WHERE conversation_id = $1"
    row = await db.fetchrow(query, conversation_id)

    if not row:
        return {"messages": [], "conversation_id": conversation_id, "found": False}

    # Verify ownership: authenticated users can only access their own conversations
    # Anonymous users can only access conversations with no user_id (anonymous conversations)
    if row["user_id"]:
        if not current_user or str(row["user_id"]) != str(current_user.id):
            raise HTTPException(status_code=403, detail="Access denied to this conversation")

    messages = row["messages"]
    if isinstance(messages, str):
        messages = json.loads(messages)

    return {
        "messages": messages,
        "conversation_id": conversation_id,
        "language": row["language"],
        "message_count": row["message_count"],
        "last_message_at": row["last_message_at"].isoformat() if row["last_message_at"] else None,
        "found": True,
    }


# ============================================================================
# CHAT ENDPOINTS
# ============================================================================

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    http_request: Request,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Interactive AI chat assistance for fiscal services
    """
    # Rate limiting: 30/min authenticated, 10/min per-IP anonymous
    client_ip = (http_request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                 or (http_request.client.host if http_request.client else "unknown"))
    rate_key = str(current_user.id) if current_user else f"anon:{client_ip}"
    rate_limit = 30 if current_user else 10
    is_allowed, remaining = await check_rate_limit(rate_key, "/chatbot/chat", rate_limit, 60)
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in 60 seconds. (limit: {rate_limit}/min)"
        )

    try:
        # Prepare chat context
        context = {
            "user_id": str(current_user.id) if current_user else None,
            "user_role": current_user.role.value if current_user else "guest",
            "language": request.language.value,
            "conversation_id": request.conversation_id,
            "additional_context": request.context or {}
        }

        # Convert history to list of dicts for service
        conversation_history = None
        if request.history:
            conversation_history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.history
            ]

        # Get AI response
        ai_response = await chatbot_service.chat(
            message=request.message,
            context=context,
            language=request.language.value,
            db=db,  # CRITICAL: Pass db connection for RAG to work
            conversation_history=conversation_history
        )

        logger.info(f"Chat processed - User: {current_user.id if current_user else 'anonymous'}")

        return ChatResponse(
            response=ai_response["message"],
            conversation_id=ai_response["conversation_id"],
            suggestions=ai_response.get("suggestions", []),
            related_services=ai_response.get("related_services", []),
            follow_up_actions=ai_response.get("follow_up_actions", []),
            actions=ai_response.get("actions", []),
            confidence=ai_response.get("confidence", 0.5),
            response_time=ai_response.get("response_time", 0),
            language=request.language
        )

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing chat request"
        )


class ExecuteConfirmedRequest(BaseModel):
    """Body for POST /chatbot/execute-confirmed (Phase 5 executive tools)."""
    confirmation_code: str = Field(..., min_length=16, max_length=128)
    locale: LanguageCode = LanguageCode.SPANISH


@router.post(
    "/execute-confirmed",
    response_model=Dict[str, Any],
    summary="Redeem a Level 3 executive confirmation code and run the tool",
    description=(
        "Consume a single-use `confirmation_code` issued by a Level 3 "
        "executive tool (`submit_prepared_request`, `book_appointment`) and "
        "dispatch directly to that tool for execution — bypassing Gemini to "
        "save tokens and avoid re-parsing risk. Protected by: (1) "
        "authentication, (2) rate limit 20/min/user, (3) single-use Redis "
        "cache, (4) args_hash tamper detection, (5) audit log. "
        "See `app/modules/chatbot/services/executive_consent.py`."
    ),
)
async def execute_confirmed(
    body: ExecuteConfirmedRequest,
    http_request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """Probe + dispatch for executive confirmation codes."""
    from app.modules.chatbot.services.executive_consent import (
        peek_confirmation_code,
        ALLOWED_TOOLS,
    )
    from app.modules.chatbot.services.chatbot_tools import CHATBOT_AUTH_FUNCTION_MAP

    # Rate limit: normal usage is ≤ 1-2 confirmations/min; 20 gives headroom
    allowed, _ = await check_rate_limit(
        str(current_user.id), "/chatbot/execute-confirmed", 20, 60
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again in 60 seconds.",
        )

    # Probe Redis for the payload WITHOUT consuming it — the tool itself
    # redeems the code inside its own critical section.
    stored = await peek_confirmation_code(
        str(current_user.id), body.confirmation_code
    )
    if not stored:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "CODE_EXPIRED_OR_INVALID",
                "message": "Le code de confirmation est expiré ou invalide.",
            },
        )

    tool_name = stored.get("tool", "")
    if tool_name not in ALLOWED_TOOLS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TOOL_NOT_ALLOWED"},
        )

    tool_fn = CHATBOT_AUTH_FUNCTION_MAP.get(tool_name)
    if not tool_fn:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "TOOL_NOT_FOUND"},
        )

    # Re-inject user_id + confirmation_code so the tool redeems + executes
    full_args = {
        **stored.get("args", {}),
        "user_id": str(current_user.id),
        "confirmation_code": body.confirmation_code,
    }
    result = await tool_fn(db, **full_args)

    logger.info(
        f"execute_confirmed dispatched tool={tool_name} "
        f"user={current_user.id} outcome={result.get('status', 'unknown')}"
    )
    return {"status": "ok", "tool_name": tool_name, "result": result}


@router.post("/chat/stream")
async def chat_stream(
    http_request: Request,
    message: str = Query(..., min_length=1, max_length=2000),
    conversation_id: Optional[str] = Query(None),
    language: LanguageCode = Query(LanguageCode.SPANISH),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Streaming AI chat for real-time responses
    """
    # Rate limiting: 30/min authenticated, 10/min per-IP anonymous
    client_ip = (http_request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                 or (http_request.client.host if http_request.client else "unknown"))
    rate_key = str(current_user.id) if current_user else f"anon:{client_ip}"
    rate_limit = 30 if current_user else 10
    is_allowed, remaining = await check_rate_limit(rate_key, "/chatbot/chat/stream", rate_limit, 60)
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in 60 seconds. (limit: {rate_limit}/min)"
        )

    try:
        # Prepare context
        context = {
            "user_id": str(current_user.id) if current_user else None,
            "user_role": current_user.role.value if current_user else "guest",
            "language": language.value,
            "conversation_id": conversation_id,
            "streaming": True
        }

        # Create streaming response
        async def generate_stream() -> AsyncGenerator[str, None]:
            try:
                async for chunk in chatbot_service.chat_stream(message, context, language.value, db=db):
                    yield f"data: {json.dumps(chunk)}\n\n"
                    # chat_stream already yields a 'done' chunk — no need to send another

            except Exception as e:
                logger.error(f"Stream error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': 'Stream error'})}\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )

    except Exception as e:
        logger.error(f"Stream setup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error setting up chat stream"
        )


# ============================================================================
# SEARCH & RECOMMENDATIONS
# ============================================================================

@router.post("/search", response_model=AISearchResponse)
async def ai_search(
    request: AISearchRequest,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    AI-powered intelligent search for fiscal services

    Status: Placeholder until semantic search integration
    """
    try:
        search_results = await chatbot_service.intelligent_search(
            query=request.query,
            language=request.language.value,
            filters=request.filters or {},
            limit=request.limit,
            user_context={
                "user_id": str(current_user.id) if current_user else None,
                "user_role": current_user.role.value if current_user else "guest"
            },
            db=db  # Pass db connection for RAG semantic search
        )

        return AISearchResponse(
            results=search_results["results"],
            total=search_results["total"],
            query_understanding=search_results.get("query_understanding", ""),
            search_intent=search_results.get("search_intent"),
            suggestions=search_results.get("suggestions", []),
            related_topics=search_results.get("related_topics", []),
            semantic_matches=search_results.get("semantic_matches", []),
            language=request.language,
            response_time=search_results.get("response_time", 0)
        )

    except Exception as e:
        logger.error(f"AI search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error performing AI search"
        )


@router.post("/recommend", response_model=RecommendationResponse)
async def get_recommendations(
    request: RecommendationRequest,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Get AI-powered service recommendations

    Status: Placeholder until recommendation engine integration
    """
    try:
        recommendations = await chatbot_service.get_recommendations(
            user_intent=request.user_intent,
            context=request.context or {},
            language=request.language.value,
            user_profile={
                "user_id": str(current_user.id) if current_user else None,
                "user_role": current_user.role.value if current_user else "guest"
            },
            db=db  # Pass db connection for RAG recommendations
        )

        return RecommendationResponse(
            recommendations=recommendations.get("services", []),
            explanation=recommendations.get("explanation", ""),
            confidence_scores=recommendations.get("confidence_scores", {}),
            alternative_options=recommendations.get("alternatives", []),
            estimated_cost=recommendations.get("estimated_cost"),
            estimated_time=recommendations.get("estimated_time"),
            required_documents=recommendations.get("required_documents", []),
            next_steps=recommendations.get("next_steps", []),
            language=request.language
        )

    except Exception as e:
        logger.error(f"Recommendations error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error getting recommendations"
        )


# ============================================================================
# DOCUMENT ANALYSIS
# ============================================================================

@router.post("/analyze-document", response_model=DocumentAnalysisResponse)
async def analyze_document(
    file: UploadFile = File(...),
    request: DocumentAnalysisRequest = Depends(),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """
    Analyze uploaded document using AI

    Status: Placeholder until document AI integration
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )

        # Check file size (max 10MB)
        file_content = await file.read()
        if len(file_content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File too large (max 10MB)"
            )

        # Analyze document
        analysis_result = await chatbot_service.analyze_document(
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type,
            analysis_type=request.analysis_type.value,
            language=request.language.value,
            user_context={
                "user_id": str(current_user.id) if current_user else None
            }
        )

        return DocumentAnalysisResponse(
            analysis=analysis_result.get("analysis", {}),
            extracted_data=analysis_result.get("extracted_data", {}),
            document_type=analysis_result.get("document_type", "unknown"),
            confidence=analysis_result.get("confidence", 0.0),
            suggestions=analysis_result.get("suggestions", []),
            required_actions=analysis_result.get("required_actions", []),
            validation_status=analysis_result.get("validation_status", {}),
            language=request.language,
            file_info={
                "filename": file.filename,
                "size": len(file_content),
                "type": file.content_type
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document analysis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error analyzing document"
        )


# ============================================================================
# TRANSLATION
# ============================================================================

@router.post("/translate", response_model=TranslationResponse)
async def translate(
    request: TranslationRequest,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """
    Translate text using AI

    Status: Placeholder until translation API integration
    """
    try:
        if request.source_language == request.target_language:
            return TranslationResponse(
                translated_text=request.text,
                source_language=request.source_language,
                target_language=request.target_language,
                confidence=1.0,
                detected_language=request.source_language
            )

        translation_result = await chatbot_service.translate_text(
            text=request.text,
            source_language=request.source_language.value,
            target_language=request.target_language.value,
            context=request.context
        )

        return TranslationResponse(
            translated_text=translation_result.get("translated_text", ""),
            source_language=request.source_language,
            target_language=request.target_language,
            confidence=translation_result.get("confidence", 0.0),
            alternatives=translation_result.get("alternatives", []),
            detected_language=request.source_language,
            translation_time=translation_result.get("translation_time", 0)
        )

    except Exception as e:
        logger.error(f"Translation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error translating text"
        )


# ============================================================================
# GUIDANCE & VALIDATION
# ============================================================================

@router.post("/guide", response_model=GuidanceResponse)
async def get_guidance(
    request: GuidanceRequest,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """
    Get AI-powered step-by-step guidance

    Status: Placeholder until knowledge base integration
    """
    try:
        guidance = await chatbot_service.get_process_guidance(
            service_id=request.service_id,
            process_type=request.process_type,
            language=request.language.value,
            current_step=request.current_step,
            user_context={
                "user_id": str(current_user.id) if current_user else None,
                "user_role": current_user.role.value if current_user else "guest"
            }
        )

        return GuidanceResponse(
            steps=guidance.get("steps", []),
            current_step=guidance.get("current_step", 1),
            total_steps=guidance.get("total_steps", 0),
            estimated_time=guidance.get("estimated_time"),
            required_documents=guidance.get("required_documents", []),
            tips=guidance.get("tips", []),
            common_issues=guidance.get("common_issues", []),
            next_actions=guidance.get("next_actions", []),
            help_resources=guidance.get("help_resources", []),
            language=request.language
        )

    except Exception as e:
        logger.error(f"Guidance error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error getting guidance"
        )


@router.post("/validate", response_model=ValidationResponse)
async def validate(
    request: ValidationRequest,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """
    AI-powered form validation

    Status: Placeholder until validation engine integration
    """
    try:
        validation_result = await chatbot_service.validate_form_data(
            form_data=request.form_data,
            form_type=request.form_type,
            language=request.language.value
        )

        return ValidationResponse(
            is_valid=validation_result.get("is_valid", True),
            errors=validation_result.get("errors", []),
            warnings=validation_result.get("warnings", []),
            suggestions=validation_result.get("suggestions", []),
            corrected_data=validation_result.get("corrected_data"),
            completeness_score=validation_result.get("completeness_score", 0.0),
            required_fields=validation_result.get("required_fields", []),
            optional_improvements=validation_result.get("optional_improvements", []),
            language=request.language
        )

    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error validating form"
        )


# ============================================================================
# ADMIN & FEEDBACK
# ============================================================================

@router.get("/stats", response_model=Dict[str, Any])
async def get_stats(
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get AI services usage statistics (conversations, feedback, ratings).
    """
    try:
        stats = await chatbot_service.get_usage_stats(db=db)
        return stats

    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving statistics"
        )


@router.post("/feedback", response_model=Dict[str, str])
async def submit_feedback(
    conversation_id: str = Query(...),
    rating: int = Query(..., ge=1, le=5),
    feedback: Optional[str] = Query(None),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Submit feedback (thumbs up/down) for a chatbot response.
    """
    try:
        await chatbot_service.record_feedback(
            db=db,
            conversation_id=conversation_id,
            rating=rating,
            feedback_text=feedback,
            user_id=str(current_user.id) if current_user else None
        )

        return {
            "status": "success",
            "message": "Feedback recorded successfully"
        }

    except Exception as e:
        logger.error(f"Feedback error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error recording feedback"
        )


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@router.get("/admin/legislacion-stats", response_model=Dict[str, Any])
async def get_legislacion_stats(
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Get statistics about indexed legislative documents.
    Requires authenticated user (admin).
    """
    if current_user.role.value not in ("admin", "supervisor"):
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        stats = await db.fetchrow("""
            SELECT
                COUNT(*) as total_chunks,
                COUNT(embedding) as embedded_chunks,
                COUNT(DISTINCT document_name) as distinct_documents,
                MIN(created_at) as oldest_chunk,
                MAX(embedding_generated_at) as latest_embedding
            FROM legislacion_documents
        """)

        docs = await db.fetch("""
            SELECT
                document_name,
                COUNT(*) as chunks,
                COUNT(embedding) as embedded,
                MIN(page_number) as min_page,
                MAX(page_number) as max_page
            FROM legislacion_documents
            GROUP BY document_name
            ORDER BY document_name
        """)

        return {
            "total_chunks": stats["total_chunks"] if stats else 0,
            "embedded_chunks": stats["embedded_chunks"] if stats else 0,
            "distinct_documents": stats["distinct_documents"] if stats else 0,
            "oldest_chunk": str(stats["oldest_chunk"]) if stats and stats["oldest_chunk"] else None,
            "latest_embedding": str(stats["latest_embedding"]) if stats and stats["latest_embedding"] else None,
            "documents": [dict(d) for d in docs],
        }

    except Exception as e:
        logger.error(f"Legislacion stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving legislacion stats"
        )


@router.post("/admin/reindex-legislacion", response_model=Dict[str, Any])
async def admin_reindex_legislacion(
    force: bool = Query(False, description="Force re-index existing chunks"),
    doc: str = Query("", description="Filter by document name (partial match)"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Admin endpoint to trigger re-indexation of legislative PDFs.
    Requires admin role. Delegates to the same logic as the cron endpoint.
    """
    if current_user.role.value not in ("admin", "supervisor"):
        raise HTTPException(status_code=403, detail="Admin access required")

    import glob
    import os
    import time as time_module

    try:
        from app.modules.chatbot.services.embedding_service import embedding_service

        if not embedding_service.enabled:
            raise HTTPException(
                status_code=503,
                detail="Embedding service disabled (Vertex AI not available)"
            )

        # Find PDFs - same discovery logic as cron
        pdf_folder = None
        candidates = [
            os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'data', 'legislacion'),
            os.path.join(os.getcwd(), 'data', 'legislacion'),
            '/app/data/legislacion',
            os.path.join(os.getcwd(), '..', 'web', 'public', 'documents', 'legislacion'),
        ]
        for candidate in candidates:
            if os.path.isdir(candidate):
                pdf_folder = candidate
                break

        if not pdf_folder:
            raise HTTPException(status_code=404, detail="No legislacion PDF folder found")

        pdf_files = sorted(glob.glob(os.path.join(pdf_folder, '*.pdf')))
        if doc:
            pdf_files = [f for f in pdf_files if doc.lower() in os.path.basename(f).lower()]

        if not pdf_files:
            return {"message": "No matching PDFs found", "pdf_count": 0}

        import pdfplumber
        from app.config import get_settings
        settings = get_settings()
        chunk_size = settings.PDF_CHUNK_SIZE
        chunk_overlap = settings.PDF_CHUNK_OVERLAP
        start_time = time_module.time()

        total_stats = {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0, "pdfs_processed": 0}

        for pdf_path in pdf_files:
            filename = os.path.basename(pdf_path)
            doc_name = os.path.splitext(filename)[0]

            existing = set()
            if not force:
                rows = await db.fetch(
                    "SELECT chunk_id FROM legislacion_documents WHERE document_name = $1",
                    doc_name,
                )
                existing = {r['chunk_id'] for r in rows}

            try:
                with pdfplumber.open(pdf_path) as pdf:
                    for page_num, page in enumerate(pdf.pages, 1):
                        text = page.extract_text() or ''
                        if not text.strip():
                            continue
                        step = max(1, chunk_size - chunk_overlap)
                        for i in range(0, len(text), step):
                            chunk_text = text[i:i + chunk_size]
                            if len(chunk_text.strip()) < 50:
                                continue
                            chunk_idx = i // step
                            chunk_id = f'{doc_name.lower()}_p{page_num}_c{chunk_idx}'
                            if chunk_id in existing and not force:
                                total_stats['skipped'] += 1
                                continue
                            emb = await embedding_service.generate_embedding(
                                chunk_text.strip(),
                                task_type='RETRIEVAL_DOCUMENT',
                                title=f"{doc_name} - Página {page_num}",
                            )
                            if not emb:
                                total_stats['failed'] += 1
                                continue
                            emb_str = '[' + ','.join(str(x) for x in emb) + ']'
                            is_update = chunk_id in existing
                            await db.execute(
                                """
                                INSERT INTO legislacion_documents
                                    (document_name, page_number, chunk_id, content,
                                     embedding, embedding_model, embedding_generated_at)
                                VALUES ($1, $2, $3, $4, $5::vector, $6, NOW())
                                ON CONFLICT (document_name, chunk_id) DO UPDATE SET
                                    content = EXCLUDED.content,
                                    embedding = EXCLUDED.embedding,
                                    embedding_model = EXCLUDED.embedding_model,
                                    embedding_generated_at = NOW(),
                                    updated_at = NOW()
                                """,
                                doc_name, page_num, chunk_id, chunk_text.strip(),
                                emb_str, 'text-embedding-005',
                            )
                            if is_update:
                                total_stats['updated'] += 1
                            else:
                                total_stats['inserted'] += 1
            except Exception as pdf_err:
                logger.error(f"Error processing {filename}: {pdf_err}")
                total_stats['failed'] += 1

            total_stats['pdfs_processed'] += 1

        elapsed = time_module.time() - start_time
        return {
            "message": f"Indexation completed in {elapsed:.1f}s",
            "pdf_folder": pdf_folder,
            "pdf_count": len(pdf_files),
            **total_stats,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin reindex error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
