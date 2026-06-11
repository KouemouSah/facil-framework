"""
Chatbot Service - RAG-powered AI assistance

Implements Retrieval-Augmented Generation (RAG) using:
- Gemini for chat and embeddings
- pgvector for semantic search
- PostgreSQL for fiscal services data

Author: Claude Code
Date: 2025-01-22
"""

from typing import Dict, Any, List, Optional, AsyncGenerator
from loguru import logger
import asyncio
import hashlib
import json
import re
import unicodedata
import uuid
import asyncpg
from datetime import datetime

from app.modules.chatbot.services.embedding_service import embedding_service
from app.modules.chatbot.services.gemini_service import gemini_service
from app.modules.chatbot.services.chatbot_tools import (
    CHATBOT_FUNC_DECLS, CHATBOT_FUNCTION_MAP,
    CHATBOT_AUTH_FUNC_DECLS, CHATBOT_AUTH_FUNCTION_MAP,
)
from app.modules.chatbot.services.query_preprocessor import QueryPreprocessor
from app.modules.chatbot.repositories.semantic_search_repository import SemanticSearchRepository
from app.modules.chatbot.repositories.legislacion_repository import LegislacionRepository
from app.config import settings

MAX_TOOL_ROUNDS = 4  # Allow multi-step reasoning (compare, calculate across zones)
CACHE_TTL_SECONDS = 3600  # 1 hour cache for common queries


class ChatbotServiceRAG:
    """
    RAG-powered chatbot service

    Workflow:
    1. User query → Generate embedding
    2. Semantic search → Find relevant services
    3. Build context → Enrich with DB data
    4. LLM generation → Gemini with context
    5. Response → Structured answer with sources
    """

    def __init__(self):
        """Initialize chatbot service"""
        self.provider = "gemini-rag"
        self.enabled = embedding_service.enabled and gemini_service.enabled
        self.preprocessor = QueryPreprocessor()

        if self.enabled:
            logger.info("ChatbotServiceRAG initialized successfully (RAG mode active)")
        else:
            logger.warning("ChatbotServiceRAG initialized (limited mode, AI disabled)")

    async def chat(
        self,
        message: str,
        context: Dict[str, Any],
        language: str = "es",
        db: Optional[asyncpg.Connection] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Process chat message using RAG

        Args:
            message: User message
            context: Conversation context (user_id, role, conversation_id)
            language: Response language (es/fr/en)
            db: Database connection (required for RAG)
            conversation_history: Previous messages for context continuity
                Each message is {"role": "user"|"assistant", "content": "..."}

        Returns:
            Dict with:
            - message: AI response
            - conversation_id: Conversation ID
            - suggestions: Follow-up suggestions
            - related_services: Related fiscal services
            - follow_up_actions: Recommended actions
            - confidence: Confidence score (0-1)
            - response_time: Processing time
            - sources: Service codes cited
        """
        start_time = datetime.now()
        conversation_id = context.get("conversation_id") or str(uuid.uuid4())

        # Fallback if AI disabled
        if not self.enabled or not db:
            return await self._fallback_response(message, conversation_id, language)

        # ── Security: Prompt injection detection ────────────────────────
        if self._detect_prompt_injection(message):
            logger.warning(f"Prompt injection detected: '{message[:80]}...'")
            return {
                "message": {
                    "es": "Lo siento, no puedo procesar esa solicitud. ¿En qué puedo ayudarte con los trámites fiscales?",
                    "fr": "Désolé, je ne peux pas traiter cette demande. Comment puis-je vous aider avec les démarches fiscales ?",
                    "en": "Sorry, I cannot process that request. How can I help you with fiscal procedures?",
                }.get(language, "Sorry, I cannot process that request."),
                "conversation_id": conversation_id,
                "suggestions": [],
                "related_services": [],
                "confidence": 0.0,
                "response_time": (datetime.now() - start_time).total_seconds(),
                "sources": [],
                "model": "security-filter",
            }

        # ── Cache check (user-scoped) ────────────────────────────────
        user_id = context.get("user_id") if context else None
        if not conversation_history:
            cached = await self._get_cached_response(message, language, user_id=user_id)
            if cached:
                cached["conversation_id"] = conversation_id
                cached["response_time"] = (datetime.now() - start_time).total_seconds()
                cached["model"] = "gemini-rag-cached"
                logger.info(f"Cache HIT for: '{message[:50]}...'")
                return cached

        try:
            # Load persisted conversation history if available
            if not conversation_history and db:
                persisted = await self._load_conversation(db, conversation_id)
                if persisted:
                    conversation_history = persisted
                    logger.info(f"Loaded {len(persisted)} persisted messages for {conversation_id}")

            # Summarize long conversations to save context tokens
            if conversation_history and len(conversation_history) > 10:
                conversation_history = self._summarize_history(conversation_history)
                logger.info(f"Conversation summarized to {len(conversation_history)} messages")

            # Step 0: Preprocess query (normalize, expand abbreviations, extract entities)
            processed = self.preprocessor.preprocess(message)
            logger.info(
                f"Processing chat: '{message[:50]}...' (lang: {language}) "
                f"entities={processed.entities}, hints={processed.detected_intent_hints}"
            )

            # Step 0b: Load user profile for personalization
            user_profile_context = await self._load_user_profile(db, user_id)

            # Step 1: Generate embedding (with cache) + classify intent IN PARALLEL
            embedding_task = self._get_or_create_embedding(processed.expanded)
            intent_task = gemini_service.classify_intent(processed.expanded, language)

            query_embedding, intent_result = await asyncio.gather(
                embedding_task, intent_task, return_exceptions=True
            )

            # Handle embedding failure
            if isinstance(query_embedding, Exception) or not query_embedding:
                logger.warning(f"Failed to generate query embedding: {query_embedding}")
                return await self._fallback_response(message, conversation_id, language)

            # Extract intent (fallback to preprocessor hints if Gemini failed)
            if isinstance(intent_result, Exception):
                logger.warning(f"Intent classification failed: {intent_result}")
                intent = processed.detected_intent_hints[0] if processed.detected_intent_hints else 'search'
                intent_confidence = 0.3
            else:
                intent = intent_result.get('intent', 'search')
                intent_confidence = intent_result.get('confidence', 0.5)

            logger.info(f"Intent: {intent} (confidence: {intent_confidence:.2f})")

            # Step 2: Smart routing based on intent
            # Adjust semantic weight per intent type
            semantic_weights = {
                'calculate': 0.5,  # Price keywords are exact
                'document': 0.6,   # Document names are keywords
                'guide': 0.7,
                'search': 0.7,
                'general': 0.7,
                'status': 0.7,
            }
            semantic_weight = semantic_weights.get(intent, 0.7)

            # For status/general, skip expensive search if intent is clear
            skip_search = (intent == 'status' and intent_confidence > 0.7)

            if skip_search:
                relevant_docs_extended = []
                relevant_services_extended = []
                logger.info("Skipping search for status intent — forcing tools")
            else:
                # Step 2a: Semantic search for legislative documents
                legislacion_repo = LegislacionRepository(db)
                relevant_docs_extended = await legislacion_repo.search_documents(
                    query_embedding=query_embedding,
                    limit=settings.RAG_EXTENDED_SEARCH_TOP_K,
                    similarity_threshold=settings.SEMANTIC_SEARCH_SIMILARITY_THRESHOLD
                )
                logger.info(f"Found {len(relevant_docs_extended)} legislative doc chunks")

                # Step 2b: Hybrid search for fiscal services
                search_repo = SemanticSearchRepository(db)
                relevant_services_extended = await search_repo.search_services_hybrid(
                    query_embedding=query_embedding,
                    query_text=processed.normalized,
                    limit=settings.RAG_EXTENDED_SEARCH_TOP_K,
                    similarity_threshold=settings.SEMANTIC_SEARCH_SIMILARITY_THRESHOLD,
                    semantic_weight=semantic_weight,
                )
                logger.info(f"Found {len(relevant_services_extended)} services (hybrid, sw={semantic_weight})")

            # Filter + deduplicate
            relevant_docs = [doc for doc in relevant_docs_extended if doc.get('similarity', 0) >= settings.SEMANTIC_SEARCH_SIMILARITY_THRESHOLD][:settings.RAG_MAX_CONTEXT_DOCUMENTS]
            relevant_services = self._deduplicate_services(
                [svc for svc in relevant_services_extended if svc.get('similarity', 0) >= settings.SEMANTIC_SEARCH_SIMILARITY_THRESHOLD]
            )[:settings.RAG_MAX_CONTEXT_SERVICES]

            # Step 2c: Bundle enrichment (only for price/commerce queries)
            bundle_context = None
            if intent == 'calculate' or processed.entities.get('commerce_type'):
                bundle_context = await self._enrich_with_bundles(db, message)

            # Step 3: Consolidate context with intent hint
            consolidated_context, context_sources = self._consolidate_context(
                relevant_docs, relevant_services, bundle_context
            )
            # Prepend intent + auth status + user profile to context
            is_authenticated = bool(user_id)
            prefix_parts = []
            if intent != 'search':
                prefix_parts.append(f"=== INTENCIÓN DETECTADA: {intent} (confianza: {intent_confidence:.0%}) ===")
            # Auth context — tells the LLM what the user can/cannot do
            if is_authenticated:
                prefix_parts.append("=== USUARIO AUTENTICADO === Puede: iniciar trámites, ver estado de solicitudes, historial personalizado.")
            else:
                prefix_parts.append(
                    "=== USUARIO NO AUTENTICADO (público) === "
                    "NO puede: consultar estado de solicitudes, acceder a datos personales. "
                    "Si pregunta por el estado de una solicitud o datos personales, responde: "
                    "'Para consultar el estado de su solicitud, necesita iniciar sesión en la plataforma Facil.' "
                    "El botón 'Iniciar en Facil' redirigirá al usuario a la página de connexión."
                )
            if user_profile_context:
                prefix_parts.append(user_profile_context)
            # Inject vault + memory + permissions context (if authenticated)
            if is_authenticated and db:
                vault_memory_context = await self._build_full_agent_context(db, user_id)
                if vault_memory_context:
                    prefix_parts.append(vault_memory_context)
            if prefix_parts:
                consolidated_context = "\n".join(prefix_parts) + "\n" + consolidated_context

            # --- Fallback Logic (Suggestion 2 & 6 Implementation) ---
            message_to_llm = message # The message to send to LLM, might be refined by fallback
            fallback_message = ""
            did_you_mean_suggestions = []

            # Check for insufficient primary context — only fallback if NO tools available AND no context
            # When tools are available, ALWAYS let Gemini handle it (it can call tools)
            has_tools = bool(CHATBOT_FUNC_DECLS)
            if not has_tools and not relevant_docs and not relevant_services and len(consolidated_context) < settings.RAG_MIN_CONTEXT_LENGTH:
                logger.warning(f"Insufficient primary context found for query: '{message[:50]}...' (length: {len(consolidated_context)})")
                
                # Try to generate "Did you mean?" suggestions
                did_you_mean_suggestions = self._generate_did_you_mean_suggestions(
                    query=message,
                    relevant_docs_extended=relevant_docs_extended,
                    relevant_services_extended=relevant_services_extended,
                    language=language
                )
                
                if did_you_mean_suggestions:
                    fallback_message = did_you_mean_suggestions[0] # Take the first "Did you mean?" message
                    logger.info(f"Using 'Did you mean?' fallback: {fallback_message}")
                else:
                    # Reuse already-computed intent (no duplicate Gemini call)
                    logger.info(f"Using pre-computed intent '{intent}' for fallback.")

                    if intent in ["search", "general", "guide", "document", "calculate"]:
                        # General clarification if intent is broad or specific but no results
                        clarification_template = {
                            "es": "No encontré una respuesta directa a su pregunta. Por favor, intente reformular o añadir más detalles. Por ejemplo, ¿busca información sobre {intent_es}?",
                            "fr": "Je n'ai pas trouvé de réponse directe à votre question. Veuillez essayer de reformuler ou d'ajouter plus de détails. Par exemple, cherchez-vous des informations sur {intent_fr} ?",
                            "en": "I couldn't find a direct answer to your question. Please try rephrasing or adding more details. For example, are you looking for information about {intent_en}?"
                        }
                        intent_phrases = {
                            "search": {"es": "un servicio específico", "fr": "un service spécifique", "en": "a specific service"},
                            "general": {"es": "un tema general", "fr": "un sujet général", "en": "a general topic"},
                            "guide": {"es": "guías paso a paso", "fr": "des guides étape par étape", "en": "step-by-step guides"},
                            "document": {"es": "documentos requeridos", "fr": "les documents requis", "en": "required documents"},
                            "calculate": {"es": "cálculo de costos", "fr": "le calcul des coûts", "en": "cost calculation"}
                        }
                        fallback_message = clarification_template.get(language, clarification_template["es"]).format(
                            intent_es=intent_phrases.get(intent, {}).get("es", "este tema"),
                            intent_fr=intent_phrases.get(intent, {}).get("fr", "ce sujet"),
                            intent_en=intent_phrases.get(intent, {}).get("en", "this topic"),
                        )
                    else:
                        # Catch-all if intent is very unusual or unhandled for now
                        fallback_resp = await self._fallback_response(message, conversation_id, language)
                        fallback_message = fallback_resp.get("message", "")
            
            # If a fallback message is generated, we return it directly without calling Gemini for content generation
            if fallback_message:
                logger.info("Returning fallback message due to insufficient context.")
                return {
                    "message": fallback_message,
                    "conversation_id": conversation_id,
                    "suggestions": did_you_mean_suggestions if did_you_mean_suggestions else [],
                    "related_services": self._format_related_services(relevant_services), # Still show primary services if any
                    "related_documents": self._format_related_documents(relevant_docs), # Still show primary docs if any
                    "follow_up_actions": [],
                    "confidence": 0.1, # Low confidence for fallback
                    "response_time": (datetime.now() - start_time).total_seconds(),
                    "sources": [],
                    "model": "gemini-rag-fallback"
                }

            # Step 4: Generate AI response with RAG context + function calling tools
            # Merge public + authenticated tools when user is logged in
            func_decls = list(CHATBOT_FUNC_DECLS) if CHATBOT_FUNC_DECLS else []
            active_function_map = dict(CHATBOT_FUNCTION_MAP)
            if is_authenticated and CHATBOT_AUTH_FUNC_DECLS:
                func_decls = func_decls + list(CHATBOT_AUTH_FUNC_DECLS)
                active_function_map.update(CHATBOT_AUTH_FUNCTION_MAP)
            func_decls = func_decls or None

            # Smart routing: force tools based on intent + context availability
            rag_is_empty = not relevant_docs and not relevant_services
            # Intents that benefit from forced tool use
            tool_biased_intents = {'status', 'guide', 'document'}
            structured_keywords = [
                "empresa", "ministerio", "oficina", "trámite", "categoría",
                "directorio", "dónde", "horario", "licencia comercial",
                "company", "ministry", "office", "entreprise", "ministère",
            ]
            is_structured_query = any(kw in message.lower() for kw in structured_keywords)
            should_force_tools = func_decls and (
                rag_is_empty or is_structured_query or
                (intent in tool_biased_intents and intent_confidence > 0.5) or
                skip_search
            )

            if should_force_tools:
                logger.info(f"Forcing tools: intent={intent}, rag_empty={rag_is_empty}, structured={is_structured_query}")

            # Smart Thinking Budget: adjust reasoning depth by query complexity
            # Simple (greetings, basic info) → 0 (no thinking, fast)
            # Medium (price, procedure, documents) → 1024 (light reasoning)
            # Complex (comparisons, multi-zone calculations) → 8192 (deep reasoning)
            complexity_signals = sum([
                len(processed.entities) >= 2,           # multiple entities = complex
                intent == 'calculate',                   # price calculation
                'compar' in message.lower(),             # comparison
                'diferencia' in message.lower() or 'différence' in message.lower(),
                len(message) > 150,                      # long query = complex
                bool(conversation_history and len(conversation_history) > 4),  # deep conversation
            ])
            if intent in ('status', 'general') and len(message) < 30:
                thinking_budget = 0  # Simple: no thinking needed
            elif complexity_signals >= 2:
                thinking_budget = 8192  # Complex: deep reasoning
            else:
                thinking_budget = 1024  # Medium: light reasoning

            logger.info(f"Thinking budget: {thinking_budget} (complexity_signals={complexity_signals})")

            ai_response = await gemini_service.chat(
                user_message=message,
                context_content=consolidated_context,
                context_services=relevant_services,
                language=language,
                conversation_history=conversation_history,
                function_declarations=func_decls,
                force_tools=should_force_tools,
                thinking_budget=thinking_budget,
            )

            # Step 4b: Multi-round tool execution if Gemini requested function calls
            tools_used = []
            tool_round = 0
            while ai_response.get("function_calls") and tool_round < MAX_TOOL_ROUNDS:
                tool_round += 1
                function_results_data = []

                for fc in ai_response["function_calls"]:
                    fn_name = fc["name"]
                    fn_args = fc.get("args", {})
                    fn_impl = active_function_map.get(fn_name)

                    if not fn_impl:
                        logger.warning(f"Unknown tool called: {fn_name}")
                        function_results_data.append({
                            "name": fn_name,
                            "args": fn_args,
                            "result": {"error": f"Unknown function: {fn_name}"},
                        })
                        continue

                    try:
                        # Inject user_id for authenticated tools
                        if fn_name in CHATBOT_AUTH_FUNCTION_MAP and user_id:
                            fn_args["user_id"] = user_id
                        result = await fn_impl(db, **fn_args)
                        tools_used.append(fn_name)

                        # Check for empty results → suggest platform_info as fallback
                        is_empty = (
                            isinstance(result, dict)
                            and result.get("count", 1) == 0
                            and not result.get("error")
                        )
                        if is_empty:
                            result["suggestion"] = (
                                "No se encontraron resultados. "
                                "Intenta con otros filtros o consulta get_platform_info."
                            )

                        logger.info(f"Tool {fn_name}({fn_args}) → {len(str(result))} chars")
                        function_results_data.append({
                            "name": fn_name,
                            "args": fn_args,
                            "result": result,
                        })
                    except Exception as tool_err:
                        logger.error(f"Tool {fn_name} error: {tool_err}")
                        # Error recovery: provide helpful context instead of raw error
                        function_results_data.append({
                            "name": fn_name,
                            "args": fn_args,
                            "result": {
                                "error": str(tool_err),
                                "recovery_hint": "Esta herramienta falló. Intenta responder con el contexto disponible o sugiere preguntas alternativas al usuario.",
                            },
                        })

                # Send tool results back to Gemini (round 2+)
                ai_response = await gemini_service.chat_round2(
                    round1_response=ai_response["round1_response"],
                    chat_history=ai_response["chat_history"],
                    function_results_data=function_results_data,
                    context_services=relevant_services,
                    function_declarations=func_decls,
                )

            if tools_used:
                logger.info(f"Chatbot used {len(tools_used)} tools in {tool_round} round(s): {tools_used}")

            # Extract action buttons from tool results
            actions = self._extract_actions_from_tools(tools_used, function_results_data if tools_used else [])

            # Override ai_response sources with our consolidated ones
            ai_response["sources"] = context_sources

            # Step 5: Self-evaluation + retry if empty or low quality
            response_message = ai_response.get("message", "")

            # CRITICAL: if response is empty, retry with force_tools immediately
            if not response_message.strip() and func_decls:
                logger.warning("Empty response from Gemini, retrying with force_tools=True")
                retry_response = await gemini_service.chat(
                    user_message=message,
                    context_content=consolidated_context,
                    context_services=relevant_services,
                    language=language,
                    conversation_history=conversation_history,
                    function_declarations=func_decls,
                    force_tools=True,
                )
                # Execute tools if requested
                if retry_response.get("function_calls"):
                    retry_results = []
                    for fc in retry_response["function_calls"]:
                        fn_impl = active_function_map.get(fc["name"])
                        if fn_impl:
                            try:
                                call_args = dict(fc.get("args", {}))
                                if fc["name"] in CHATBOT_AUTH_FUNCTION_MAP and user_id:
                                    call_args["user_id"] = user_id
                                result = await fn_impl(db, **call_args)
                                tools_used.append(fc["name"])
                                retry_results.append({"name": fc["name"], "args": fc.get("args", {}), "result": result})
                            except Exception as e:
                                retry_results.append({"name": fc["name"], "args": fc.get("args", {}), "result": {"error": str(e)}})
                    if retry_results:
                        ai_response = await gemini_service.chat_round2(
                            round1_response=retry_response["round1_response"],
                            chat_history=retry_response["chat_history"],
                            function_results_data=retry_results,
                            context_services=relevant_services,
                            function_declarations=func_decls,
                        )
                        response_message = ai_response.get("message", "")
                elif retry_response.get("message"):
                    response_message = retry_response["message"]

            # If STILL empty after retry, provide a helpful fallback
            if not response_message.strip():
                fallback_messages = {
                    "es": f"No pude generar una respuesta para tu consulta sobre \"{message[:50]}\". "
                          f"Te sugiero intentar con una pregunta más específica, por ejemplo:\n"
                          f"- ▸ ¿Cuánto cuesta un pasaporte?\n"
                          f"- ▸ ¿Qué documentos necesito para la residencia?\n"
                          f"- ▸ ¿Cuáles son los ministerios?",
                    "fr": f"Je n'ai pas pu générer de réponse pour votre question. "
                          f"Essayez une question plus spécifique.",
                    "en": f"I couldn't generate a response for your query. "
                          f"Try a more specific question.",
                }
                response_message = fallback_messages.get(language, fallback_messages["es"])
                logger.error(f"Empty response even after retry for: '{message[:50]}'")

            quality_score = await self._evaluate_response(
                message, response_message, consolidated_context
            )

            # If quality too low and we haven't used tools yet, force tool use (mode=ANY)
            if quality_score < 0.4 and not tools_used and func_decls:
                logger.warning(
                    f"Low quality ({quality_score:.2f}), retrying with force_tools=True"
                )
                retry_response = await gemini_service.chat(
                    user_message=message,
                    context_content="",
                    context_services=[],
                    language=language,
                    conversation_history=conversation_history,
                    function_declarations=func_decls,
                    force_tools=True,
                )
                # Execute tools if requested
                if retry_response.get("function_calls"):
                    retry_results = []
                    for fc in retry_response["function_calls"]:
                        fn_impl = active_function_map.get(fc["name"])
                        if fn_impl:
                            try:
                                call_args = dict(fc.get("args", {}))
                                if fc["name"] in CHATBOT_AUTH_FUNCTION_MAP and user_id:
                                    call_args["user_id"] = user_id
                                result = await fn_impl(db, **call_args)
                                tools_used.append(fc["name"])
                                retry_results.append({
                                    "name": fc["name"],
                                    "args": fc.get("args", {}),
                                    "result": result,
                                })
                            except Exception as e:
                                retry_results.append({
                                    "name": fc["name"],
                                    "args": fc.get("args", {}),
                                    "result": {"error": str(e)},
                                })
                    if retry_results:
                        ai_response = await gemini_service.chat_round2(
                            round1_response=retry_response["round1_response"],
                            chat_history=retry_response["chat_history"],
                            function_results_data=retry_results,
                            context_services=relevant_services,
                            function_declarations=func_decls,
                        )
                        response_message = ai_response.get("message", response_message)
                        quality_score = await self._evaluate_response(
                            message, response_message, consolidated_context
                        )
                        logger.info(f"Retry quality: {quality_score:.2f}")

            # Step 5b: Self-Reflection Loop — LLM evaluates its own response
            reflection_score = await self._self_reflect(
                message, response_message, language
            )
            if reflection_score is not None and reflection_score < 5 and not tools_used:
                logger.info(f"Self-reflection score {reflection_score}/10 < 5, regenerating with enriched context")
                retry = await gemini_service.chat(
                    user_message=(
                        f"Tu as répondu à cette question: \"{message}\"\n"
                        f"Ta réponse précédente a été évaluée {reflection_score}/10.\n"
                        f"Améliore ta réponse en étant plus complet, précis et structuré.\n"
                        f"Contexte disponible:\n{consolidated_context}"
                    ),
                    context_content=consolidated_context,
                    context_services=relevant_services,
                    language=language,
                    function_declarations=func_decls,
                )
                retry_msg = retry.get("message", "")
                if retry_msg and len(retry_msg) > len(response_message) * 0.5:
                    response_message = retry_msg
                    logger.info("Self-reflection: regenerated response accepted")

            # Step 6: Build structured response
            response_time = (datetime.now() - start_time).total_seconds()
            confidence = max(ai_response.get("confidence", 0.5), quality_score)
            logger.info(f"Response quality: {quality_score:.2f}, confidence: {confidence:.2f}")

            # Persist conversation + update user preferences + learning (non-blocking, non-fatal)
            if db:
                await self._save_conversation(
                    db, conversation_id, message, response_message,
                    user_id=user_id, language=language,
                )
                await self._update_user_preferences(
                    db, user_id, language,
                    processed.entities if processed else {},
                )
                # Post-interaction learning — enrich agent memory
                if user_id:
                    # Build tool_calls_log from function_results_data (available after tool rounds)
                    tool_calls_log = []
                    if tools_used:
                        try:
                            tool_calls_log = function_results_data
                        except NameError:
                            tool_calls_log = []
                    await self._post_interaction_learning(
                        db, user_id, conversation_id,
                        tool_calls=tool_calls_log,
                        language=language,
                    )

            final_response = {
                "message": response_message,
                "conversation_id": conversation_id,
                "suggestions": self._generate_suggestions(
                    relevant_docs, relevant_services, language,
                    user_query=message, intent=intent,
                    entities=processed.entities if processed else {},
                ),
                "related_services": self._format_related_services(relevant_services),
                "related_documents": self._format_related_documents(relevant_docs),
                "follow_up_actions": self._generate_follow_up_actions(relevant_services, language),
                "actions": actions,
                "confidence": confidence,
                "response_time": response_time,
                "sources": ai_response.get("sources", []),
                "model": ai_response.get("model", "gemini-rag")
            }

            # Step 7: Cache successful response for future identical queries
            await self._cache_response(message, language, final_response, user_id=user_id)

            return final_response

        except Exception as e:
            logger.error(f"Chat processing error: {e}")
            return await self._fallback_response(message, conversation_id, language, error=str(e))

    async def chat_stream(
        self,
        message: str,
        context: Dict[str, Any],
        language: str = "es",
        db: Optional[asyncpg.Connection] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat response in real-time

        Args:
            message: User message
            context: Conversation context
            language: Response language
            db: Database connection

        Yields:
            Stream chunks:
            - {"type": "chunk", "text": "..."}
            - {"type": "done", "sources": [...]}
            - {"type": "error", "message": "..."}
        """
        if not self.enabled or not db:
            yield {"type": "error", "message": "AI service temporarily unavailable"}
            return

        try:
            # Preprocess query
            processed = self.preprocessor.preprocess(message)

            # Status: searching
            yield {"type": "status", "step": "searching", "text": self._status_text("searching", language)}

            # Generate query embedding (use expanded query)
            query_embedding = await embedding_service.generate_query_embedding(processed.expanded)

            if not query_embedding:
                yield {"type": "error", "message": "Failed to process query"}
                return

            # Semantic search for relevant legislative documents (PDFs)
            legislacion_repo = LegislacionRepository(db)
            relevant_docs_extended = await legislacion_repo.search_documents(
                query_embedding=query_embedding,
                limit=settings.RAG_EXTENDED_SEARCH_TOP_K,
                similarity_threshold=settings.SEMANTIC_SEARCH_SIMILARITY_THRESHOLD
            )

            # Hybrid search for relevant fiscal services (semantic + full-text)
            search_repo = SemanticSearchRepository(db)
            relevant_services_extended = await search_repo.search_services_hybrid(
                query_embedding=query_embedding,
                query_text=processed.normalized,
                limit=settings.RAG_EXTENDED_SEARCH_TOP_K,
                similarity_threshold=settings.SEMANTIC_SEARCH_SIMILARITY_THRESHOLD,
                semantic_weight=0.7,
            )

            # Status: analyzing
            yield {"type": "status", "step": "analyzing", "text": self._status_text("analyzing", language)}
            
            # Filter for primary context (above SEMANTIC_SEARCH_SIMILARITY_THRESHOLD) + deduplicate
            relevant_docs = [doc for doc in relevant_docs_extended if doc.get('similarity', 0) >= settings.SEMANTIC_SEARCH_SIMILARITY_THRESHOLD][:settings.RAG_MAX_CONTEXT_DOCUMENTS]
            relevant_services = self._deduplicate_services(
                [svc for svc in relevant_services_extended if svc.get('similarity', 0) >= settings.SEMANTIC_SEARCH_SIMILARITY_THRESHOLD]
            )[:settings.RAG_MAX_CONTEXT_SERVICES]
            
            # Enrich with bundle pricing data (only for commerce/pricing queries)
            bundle_context = None
            if processed.entities.get('commerce_type') or any(
                kw in processed.normalized for kw in ['precio', 'prix', 'price', 'cuesta', 'coûte', 'cost']
            ):
                bundle_context = await self._enrich_with_bundles(db, message)

            consolidated_context, context_sources = self._consolidate_context(
                relevant_docs, relevant_services, bundle_context
            )

            # Inject vault + memory + permissions context (same as chat())
            user_id = context.get("user_id") if context else None
            is_authenticated = bool(user_id)
            prefix_parts = []
            if is_authenticated:
                prefix_parts.append("=== USUARIO AUTENTICADO === Puede: iniciar trámites, ver estado de solicitudes, historial personalizado.")
            else:
                prefix_parts.append(
                    "=== USUARIO NO AUTENTICADO (público) === "
                    "NO puede: consultar estado de solicitudes, acceder a datos personales. "
                    "Si pregunta por el estado de una solicitud o datos personales, responde: "
                    "'Para consultar el estado de su solicitud, necesita iniciar sesión en la plataforma Facil.' "
                    "El botón 'Iniciar en Facil' redirigirá al usuario a la página de connexión."
                )
            if is_authenticated and db:
                try:
                    vault_memory_context = await self._build_full_agent_context(db, user_id)
                    if vault_memory_context:
                        prefix_parts.append(vault_memory_context)
                except Exception as e:
                    logger.debug(f"Vault context build failed in stream: {e}")
            if prefix_parts:
                consolidated_context = "\n".join(prefix_parts) + "\n" + consolidated_context

            # --- Fallback Logic (Suggestion 2 & 6 Implementation for stream) ---
            if len(consolidated_context) < settings.RAG_MIN_CONTEXT_LENGTH:
                logger.warning(f"Insufficient primary context found for stream query: '{message[:50]}...' (length: {len(consolidated_context)})")

                did_you_mean_suggestions = self._generate_did_you_mean_suggestions(
                    query=message,
                    relevant_docs_extended=relevant_docs_extended,
                    relevant_services_extended=relevant_services_extended,
                    language=language
                )
                
                if did_you_mean_suggestions:
                    fallback_message = did_you_mean_suggestions[0]
                    logger.info(f"Using 'Did you mean?' fallback for stream: {fallback_message}")
                else:
                    intent_classification = await gemini_service.classify_intent(message, language)
                    intent = intent_classification.get('intent', 'search')
                    logger.info(f"Intent classified as '{intent}' for stream fallback.")

                    clarification_template = {
                        "es": "No encontré una respuesta directa a su pregunta. Por favor, intente reformular o añadir más detalles. Por ejemplo, ¿busca información sobre {intent_es}?",
                        "fr": "Je n'ai pas trouvé de réponse directe à votre question. Veuillez essayer de reformuler ou d'ajouter plus de détails. Par exemple, cherchez-vous des informations sur {intent_fr} ?",
                        "en": "I couldn't find a direct answer to your question. Please try rephrasing or adding more details. For example, are you looking for information about {intent_en}?"
                    }
                    intent_phrases = {
                        "search": {"es": "un servicio específico", "fr": "un service spécifique", "en": "a specific service"},
                        "general": {"es": "un tema general", "fr": "un sujet général", "en": "a general topic"},
                        "guide": {"es": "guías paso a paso", "fr": "des guides étape par étape", "en": "step-by-step guides"},
                        "document": {"es": "documentos requeridos", "fr": "les documents requis", "en": "required documents"},
                        "calculate": {"es": "cálculo de costos", "fr": "le calcul des coûts", "en": "cost calculation"}
                    }
                    fallback_message = clarification_template.get(language, clarification_template["es"]).format(
                        intent_es=intent_phrases.get(intent, {}).get("es", "este tema"),
                        intent_fr=intent_phrases.get(intent, {}).get("fr", "ce sujet"),
                        intent_en=intent_phrases.get(intent, {}).get("en", "this topic"),
                    )

                logger.info("Yielding fallback message for stream.")
                yield {"type": "chunk", "text": fallback_message}
                yield {"type": "done", "sources": [], "confidence": 0.1, "model": "gemini-rag-fallback", "suggestions": did_you_mean_suggestions}
                return # Exit early if fallback is used

            # Status: generating
            yield {"type": "status", "step": "generating", "text": self._status_text("generating", language)}

            # Pre-stream: execute tools if context is insufficient (non-streaming tool call)
            func_decls = CHATBOT_FUNC_DECLS if CHATBOT_FUNC_DECLS else None
            rag_is_empty = not relevant_docs and not relevant_services
            if rag_is_empty and func_decls:
                logger.info("Stream: RAG empty, executing tools before streaming")
                tool_response = await gemini_service.chat(
                    user_message=message,
                    context_content=consolidated_context,
                    context_services=relevant_services,
                    language=language,
                    function_declarations=func_decls,
                    force_tools=True,
                )
                # Execute tools if Gemini requested them
                if tool_response.get("function_calls"):
                    tool_results = []
                    for fc in tool_response["function_calls"]:
                        fn_impl = active_function_map.get(fc["name"])
                        if fn_impl:
                            try:
                                call_args = dict(fc.get("args", {}))
                                if fc["name"] in CHATBOT_AUTH_FUNCTION_MAP and user_id:
                                    call_args["user_id"] = user_id
                                result = await fn_impl(db, **call_args)
                                tool_results.append({"name": fc["name"], "args": fc.get("args", {}), "result": result})
                            except Exception as e:
                                tool_results.append({"name": fc["name"], "args": fc.get("args", {}), "result": {"error": str(e)}})
                    if tool_results:
                        final = await gemini_service.chat_round2(
                            round1_response=tool_response["round1_response"],
                            chat_history=tool_response["chat_history"],
                            function_results_data=tool_results,
                            context_services=relevant_services,
                            function_declarations=func_decls,
                        )
                        # Yield the tool-enriched response as stream chunks
                        response_text = final.get("message", "")
                        if response_text:
                            yield {"type": "chunk", "text": response_text}
                            yield {"type": "done", "sources": context_sources}
                            return

            # Stream AI response (standard path)
            async for chunk in gemini_service.chat_stream(
                user_message=message,
                context_content=consolidated_context,
                context_services=relevant_services,
                language=language
            ):
                if chunk.get("type") == "done":
                    chunk["sources"] = context_sources
                yield chunk

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield {"type": "error", "message": str(e)}

    async def intelligent_search(
        self,
        query: str,
        language: str,
        filters: Dict[str, Any],
        limit: int,
        user_context: Dict[str, Any],
        db: Optional[asyncpg.Connection] = None
    ) -> Dict[str, Any]:
        """
        AI-powered intelligent search for fiscal services

        Args:
            query: Search query
            language: Search language
            filters: Optional filters (category_id, service_type, etc.)
            limit: Max results
            user_context: User context (user_id, role)
            db: Database connection

        Returns:
            Dict with:
            - results: List of matching services
            - total: Total matches
            - query_understanding: AI's interpretation
            - search_intent: Detected intent
            - suggestions: Search suggestions
            - semantic_matches: Similarity scores
        """
        start_time = datetime.now()

        if not self.enabled or not db:
            return {
                "results": [],
                "total": 0,
                "query_understanding": query,
                "message": "Search temporarily unavailable"
            }

        try:
            # Step 1: Classify search intent
            intent = await gemini_service.classify_intent(query, language)
            logger.info(f"Search intent: {intent.get('intent')} (confidence: {intent.get('confidence')})")

            # Step 2: Generate query embedding
            query_embedding = await embedding_service.generate_query_embedding(query)

            if not query_embedding:
                return {"results": [], "total": 0, "error": "Failed to process query"}

            # Step 3: Semantic search with filters
            search_repo = SemanticSearchRepository(db)
            results = await search_repo.search_services(
                query_embedding=query_embedding,
                limit=limit,
                filters=filters
            )

            # Step 4: Format results
            return {
                "results": results,
                "total": len(results),
                "query_understanding": query,
                "search_intent": intent.get("intent"),
                "suggestions": self._generate_search_suggestions(results, query, language),
                "related_topics": self._extract_related_topics(results),
                "semantic_matches": [
                    {"service_code": s["service_code"], "similarity": s.get("similarity", 0)}
                    for s in results
                ],
                "language": language,
                "response_time": (datetime.now() - start_time).total_seconds()
            }

        except Exception as e:
            logger.error(f"Intelligent search error: {e}")
            return {"results": [], "total": 0, "error": str(e)}

    async def get_recommendations(
        self,
        user_intent: str,
        context: Dict[str, Any],
        language: str,
        user_profile: Dict[str, Any],
        db: Optional[asyncpg.Connection] = None
    ) -> Dict[str, Any]:
        """
        Get AI-powered service recommendations

        Args:
            user_intent: What user wants to do
            context: Additional context
            language: Response language
            user_profile: User profile (user_id, role)
            db: Database connection

        Returns:
            Recommended services with explanations
        """
        if not self.enabled or not db:
            return {
                "services": [],
                "explanation": "Recommendations temporarily unavailable"
            }

        try:
            # Generate embedding for user intent
            intent_embedding = await embedding_service.generate_query_embedding(user_intent)

            if not intent_embedding:
                return {"services": [], "explanation": "Failed to process intent"}

            # Search for relevant services (top 3 + 3 alternatives)
            search_repo = SemanticSearchRepository(db)
            all_services = await search_repo.search_services(
                query_embedding=intent_embedding,
                limit=6  # Top 3 + 3 alternatives
            )

            services = all_services[:3]
            alternatives = all_services[3:6]

            # Generate explanation using Gemini
            explanation = await self._generate_recommendation_explanation(
                services,
                user_intent,
                language
            )

            return {
                "services": services,
                "explanation": explanation,
                "confidence_scores": {
                    s["service_code"]: s.get("similarity", 0)
                    for s in services
                },
                "alternatives": [
                    {"service_code": s["service_code"], "name": s.get("name_es", ""), "similarity": s.get("similarity", 0)}
                    for s in alternatives
                ],
                "next_steps": self._generate_next_steps(services, language)
            }

        except Exception as e:
            logger.error(f"Recommendations error: {e}")
            return {"services": [], "error": str(e)}

    # ========================================================================
    # CONTEXT CONSOLIDATION
    # ========================================================================

    def _deduplicate_services(self, services: List[Dict]) -> List[Dict]:
        """Deduplicate services by service_code, keeping highest similarity.
        Filters test data (cost < 100 XAF) — validated: no real service costs < 100 XAF."""
        seen = {}
        filtered_count = 0
        for svc in services:
            code = svc.get('service_code', '')
            if not code:
                continue
            price = svc.get('tasa_expedicion', 0)
            if price and float(price) > 0 and float(price) < 100:
                filtered_count += 1
                continue
            if code not in seen or svc.get('similarity', 0) > seen[code].get('similarity', 0):
                seen[code] = svc
        if filtered_count:
            logger.debug(f"Dedup: filtered {filtered_count} test services (<100 XAF)")
        return list(seen.values())

    # Commerce keywords for bundle detection
    COMMERCE_KEYWORDS = {
        'restaurant': 'BARES_RESTAURANTES',
        'restaurante': 'BARES_RESTAURANTES',
        'bar': 'BARES_RESTAURANTES',
        'farmacia': 'CLINICAS_FARMACIAS',
        'clinica': 'CLINICAS_FARMACIAS',
        'clínica': 'CLINICAS_FARMACIAS',
        'discoteca': 'DISCOTECAS',
        'ferretería': 'FERRETERIAS',
        'ferreteria': 'FERRETERIAS',
        'carpintería': 'CARPINTERIAS',
        'carpinteria': 'CARPINTERIAS',
        'cafetería': 'CAFETERIAS_PASTELERIAS',
        'cafeteria': 'CAFETERIAS_PASTELERIAS',
        'panadería': 'CAFETERIAS_PASTELERIAS',
        'panaderia': 'CAFETERIAS_PASTELERIAS',
        'pastelería': 'CAFETERIAS_PASTELERIAS',
        'pasteleria': 'CAFETERIAS_PASTELERIAS',
        'snack': 'CAFETERIAS_PASTELERIAS',
        'taller': 'TALLERES_BLOQUERIAS',
        'bloquería': 'TALLERES_BLOQUERIAS',
        'bloqueria': 'TALLERES_BLOQUERIAS',
        'artesanal': 'TALLERES_ARTESANALES',
        'artesanía': 'TALLERES_ARTESANALES',
        'artesania': 'TALLERES_ARTESANALES',
        'video club': 'VIDEOS_CLUBS',
        'videoclub': 'VIDEOS_CLUBS',
        'abacería': 'ABACERIAS',
        'abaceria': 'ABACERIAS',
        'factoría': 'ABACERIAS',
        'factoria': 'ABACERIAS',
        'comercio': 'ABACERIAS',
        'tienda': 'ABACERIAS',
        'negocio': None,  # generic → show all bundles summary
        'apertura': None,
        'licencia comercial': None,
        'abrir': None,
    }

    CITY_ZONE_MAP = {
        'malabo': 'A1',
        'bata': 'A1',
        'ebebiyin': 'B1',
        'evinayong': 'B1',
        'mongomo': 'B1',
        'luba': 'B1',
        'añisok': 'C1',
        'anisok': 'C1',
        'niefang': 'C1',
        'micomeseng': 'C1',
        'acurenam': 'C1',
        'nsork': 'C1',
        'mbini': 'C1',
    }

    async def _enrich_with_bundles(
        self,
        db: asyncpg.Connection,
        message: str,
    ) -> Optional[str]:
        """
        Detect commerce/pricing intent in message and fetch bundle pricing from DB.
        Returns structured pricing context string, or None if not relevant.
        """
        msg_lower = message.lower()

        # Detect commerce type
        detected_bundle = None
        for keyword, bundle_code in self.COMMERCE_KEYWORDS.items():
            if keyword in msg_lower:
                detected_bundle = bundle_code
                break

        if detected_bundle is None and not any(
            kw in msg_lower for kw in ['precio', 'prix', 'price', 'cuánto', 'combien', 'cost', 'cuesta', 'coûte', 'tarifa', 'tasa']
        ):
            return None

        # Detect zone from city name
        detected_zone = None
        for city, zone_code in self.CITY_ZONE_MAP.items():
            if city in msg_lower:
                detected_zone = zone_code
                break

        try:
            if detected_bundle:
                # Specific bundle: fetch pricing by zone
                rows = await db.fetch("""
                    SELECT cz.name_es as zone_name, cz.zone_code,
                           SUM(sbi.amount) as total,
                           COUNT(sbi.id) as item_count,
                           array_agg(
                               fs.name_es || ': ' || sbi.amount || ' XAF'
                               ORDER BY sbi.display_order
                           ) as items
                    FROM service_bundle_items sbi
                    JOIN service_bundles sb ON sb.id = sbi.bundle_id
                    JOIN fiscal_services fs ON fs.id = sbi.fiscal_service_id
                    JOIN commerce_zones cz ON cz.id = sbi.zone_id
                    WHERE sb.bundle_code = $1 AND sbi.is_active = true
                    GROUP BY cz.name_es, cz.zone_code
                    ORDER BY SUM(sbi.amount) DESC
                """, detected_bundle)

                if not rows:
                    return None

                # Get bundle name
                bundle_name = await db.fetchval(
                    "SELECT name_es FROM service_bundles WHERE bundle_code = $1",
                    detected_bundle
                )

                parts = [f"=== PRECIOS DE PAQUETE FISCAL: {bundle_name} ==="]
                parts.append(f"Tipo de negocio: {bundle_name}")
                parts.append("")

                if detected_zone:
                    # Show detailed breakdown for specific zone
                    zone_rows = [r for r in rows if r['zone_code'] == detected_zone]
                    if zone_rows:
                        r = zone_rows[0]
                        parts.append(f"### {r['zone_name']} (Zona {r['zone_code']})")
                        parts.append(f"TOTAL: {r['total']:,.0f} XAF".replace(',', '.'))
                        parts.append("Desglose:")
                        for item in r['items']:
                            parts.append(f"  - {item}")
                    parts.append("")
                    parts.append("Comparación con otras zonas:")

                # Summary table all zones
                parts.append("| Zona | Código | Total XAF |")
                parts.append("|------|--------|-----------|")
                for r in rows:
                    marker = " ←" if r['zone_code'] == detected_zone else ""
                    parts.append(f"| {r['zone_name']} | {r['zone_code']} | {r['total']:,.0f}{marker} |".replace(',', '.'))

                return "\n".join(parts)

            else:
                # Generic commerce query: show all bundle types with price range
                rows = await db.fetch("""
                    SELECT sb.name_es as bundle_name, sb.bundle_code,
                           MIN(zone_totals.total) as min_total,
                           MAX(zone_totals.total) as max_total,
                           COUNT(DISTINCT zone_totals.zone_id) as zone_count
                    FROM service_bundles sb
                    JOIN (
                        SELECT sbi.bundle_id, sbi.zone_id, SUM(sbi.amount) as total
                        FROM service_bundle_items sbi
                        WHERE sbi.is_active = true
                        GROUP BY sbi.bundle_id, sbi.zone_id
                    ) zone_totals ON zone_totals.bundle_id = sb.id
                    WHERE sb.is_active = true
                    GROUP BY sb.name_es, sb.bundle_code
                    ORDER BY MAX(zone_totals.total) DESC
                """)

                if not rows:
                    return None

                parts = ["=== PAQUETES FISCALES PARA NEGOCIOS COMERCIALES ==="]
                parts.append("Precios varían según la zona geográfica (A1=Capitales Regiones/más alto → D1=Poblados/más bajo)")
                parts.append("")
                parts.append("| Tipo de Negocio | Precio Mínimo | Precio Máximo |")
                parts.append("|----------------|---------------|---------------|")
                for r in rows:
                    parts.append(
                        f"| {r['bundle_name']} | {r['min_total']:,.0f} XAF | {r['max_total']:,.0f} XAF |".replace(',', '.')
                    )

                return "\n".join(parts)

        except Exception as e:
            logger.warning(f"Bundle enrichment failed: {e}")
            return None

    def _consolidate_context(
        self,
        relevant_docs: List[Dict],
        relevant_services: List[Dict],
        bundle_context: Optional[str] = None,
    ) -> tuple:
        """
        Build structured context string from legislative docs + fiscal services + bundles for LLM.
        Priority: legislative documents first (official sources), then bundles, then services.

        Returns:
            (context_text: str, source_codes: List[str])
        """
        parts = []
        sources = []

        # Priority 1: Legislative documents (official government sources)
        if relevant_docs:
            parts.append("=== DOCUMENTOS LEGISLATIVOS (FUENTE OFICIAL) ===")
            for doc in relevant_docs[:getattr(settings, 'RAG_MAX_CONTEXT_DOCUMENTS', 5)]:
                doc_name = doc.get('document_name', 'Documento')
                page = doc.get('page_number', '?')
                content = doc.get('content', '')
                # Smart truncation at sentence boundary (1000 chars for richer context)
                if len(content) > 1000:
                    cut = content[:1000].rfind('.')
                    content = content[:cut + 1] if cut > 300 else content[:1000]
                parts.append(f"[{doc_name} - Pág. {page}]")
                parts.append(content)
                sources.append(f"DOC:{doc_name}:p{page}")

        # Priority 2: Bundle pricing (commerce packages with zone pricing)
        if bundle_context:
            parts.append(bundle_context)
            sources.append("BUNDLE_PRICING")

        # Priority 3: Fiscal services (individual service details)
        if relevant_services:
            parts.append("=== SERVICIOS FISCALES ===")
            for svc in relevant_services[:getattr(settings, 'RAG_MAX_CONTEXT_SERVICES', 5)]:
                code = svc.get('service_code', '')
                name = svc.get('name_es', '')
                desc = svc.get('description_es', '') or ''
                price_exp = svc.get('tasa_expedicion', 0)
                price_ren = svc.get('tasa_renovacion', 0)
                cat = svc.get('category_name', '')
                bundle = svc.get('bundle_name', '')
                zone = svc.get('zone_name', '')
                svc_type = svc.get('service_type', '')
                legal_ref = svc.get('legal_reference', '')
                processing_days = svc.get('processing_time_days', '')
                validity_months = svc.get('validity_period_months', '')

                parts.append(f"[{code}] {name} ({cat})")
                if desc:
                    # Smart truncation (500 chars for richer context)
                    short_desc = desc[:500].rsplit('.', 1)[0] + '.' if len(desc) > 500 else desc
                    parts.append(f"  Descripción: {short_desc}")
                if price_exp and float(price_exp) > 0:
                    parts.append(f"  Tarifa expedición: {price_exp} XAF")
                if price_ren and float(price_ren) > 0:
                    parts.append(f"  Tarifa renovación: {price_ren} XAF")
                if svc_type:
                    parts.append(f"  Tipo: {svc_type}")
                if processing_days:
                    parts.append(f"  Tiempo de procesamiento: {processing_days} días")
                if validity_months:
                    parts.append(f"  Validez: {validity_months} meses")
                if legal_ref:
                    parts.append(f"  Referencia legal: {legal_ref}")
                if bundle:
                    parts.append(f"  Paquete fiscal: {bundle}")
                if zone:
                    parts.append(f"  Zona: {zone}")

                # Include required documents if available
                docs_req = svc.get('required_documents')
                if docs_req:
                    parts.append("  Documentos requeridos:")
                    if isinstance(docs_req, list):
                        for d in docs_req[:10]:
                            doc_name_req = d.get('document_name_es', d.get('template_code', '')) if isinstance(d, dict) else str(d)
                            if doc_name_req:
                                parts.append(f"    - {doc_name_req}")

                # Include procedures if available
                procedures = svc.get('procedures')
                if procedures:
                    parts.append("  Procedimientos:")
                    if isinstance(procedures, list):
                        for p in procedures[:5]:
                            p_name = p.get('name_es', p.get('template_code', '')) if isinstance(p, dict) else str(p)
                            if p_name:
                                parts.append(f"    - {p_name}")
                            steps = p.get('steps', []) if isinstance(p, dict) else []
                            if isinstance(steps, list):
                                for step in steps[:8]:
                                    step_desc = step.get('description', '') if isinstance(step, dict) else str(step)
                                    step_num = step.get('step_number', '') if isinstance(step, dict) else ''
                                    if step_desc:
                                        parts.append(f"      {step_num}. {step_desc}")

                sources.append(code)

        context_text = "\n".join(parts)

        # Truncate to MAX_CONTEXT_TOKENS (~4 chars/token) — section-aware
        max_chars = getattr(settings, 'MAX_CONTEXT_TOKENS', 3000) * 4
        if len(context_text) > max_chars:
            # Find last complete section boundary (===) before limit
            cut_point = context_text[:max_chars].rfind('\n===')
            if cut_point < max_chars * 0.5:
                # No good section boundary — find last double newline
                cut_point = context_text[:max_chars].rfind('\n\n')
            context_text = context_text[:cut_point] if cut_point > 0 else context_text[:max_chars]

        return context_text, sources

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    async def _fallback_response(
        self,
        message: str,
        conversation_id: str,
        language: str,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fallback response when AI is unavailable"""
        messages = {
            "es": "Lo siento, el servicio de AI no está disponible en este momento. Por favor, intenta de nuevo más tarde o contacta al soporte.",
            "fr": "Désolé, le service AI n'est pas disponible pour le moment. Veuillez réessayer plus tard ou contacter le support.",
            "en": "Sorry, the AI service is temporarily unavailable. Please try again later or contact support."
        }

        return {
            "message": messages.get(language, messages["es"]),
            "conversation_id": conversation_id,
            "suggestions": [],
            "related_services": [],
            "follow_up_actions": [],
            "confidence": 0.0,
            "response_time": 0,
            "error": error or "AI service disabled"
        }

    def _generate_suggestions(
        self,
        relevant_docs: List[Dict],
        services: List[Dict],
        language: str,
        user_query: str = "",
        intent: str = "search",
        entities: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """Generate contextual follow-up suggestions based on intent + entities.

        Intent-aware: suggests complementary actions, not generic questions.
        """
        suggestions = []
        entities = entities or {}
        query_lower = (user_query or "").lower()

        # Intent-based suggestions (most relevant — complementary to what was asked)
        _intent_suggestions = {
            "calculate": {
                "es": ["¿Qué documentos necesito?", "¿Cómo iniciar el trámite?", "¿Dónde se realiza?"],
                "fr": ["Quels documents faut-il ?", "Comment démarrer la démarche ?", "Où se fait-elle ?"],
                "en": ["What documents do I need?", "How to start the procedure?", "Where is it done?"],
            },
            "guide": {
                "es": ["¿Cuánto cuesta?", "¿Qué documentos necesito?", "Quiero iniciar este trámite"],
                "fr": ["Combien ça coûte ?", "Quels documents faut-il ?", "Je veux commencer"],
                "en": ["How much does it cost?", "What documents do I need?", "I want to start"],
            },
            "document": {
                "es": ["¿Cuánto cuesta?", "Quiero iniciar este trámite", "¿Cuánto tarda?"],
                "fr": ["Combien ça coûte ?", "Je veux commencer", "Combien de temps ?"],
                "en": ["How much does it cost?", "I want to start", "How long does it take?"],
            },
        }

        intent_sugg = _intent_suggestions.get(intent, {}).get(language, [])

        # Personalize with workflow entity if detected
        workflow_name = entities.get('workflow_keyword', '')
        if workflow_name and intent_sugg:
            # Use language-appropriate connector
            connector = {'es': 'para', 'fr': 'pour', 'en': 'for'}.get(language, 'para')
            suffix = {'es': '?', 'fr': ' ?', 'en': '?'}.get(language, '?')
            suggestions = [
                s.rstrip(' ?¿').strip() + f' {connector} {workflow_name}{suffix}'
                if workflow_name.lower() not in s.lower() else s
                for s in intent_sugg[:3]
            ]
        elif intent_sugg:
            suggestions = intent_sugg[:3]

        # Fallback: generic service-based suggestions (NO name_es to avoid language mixing)
        if not suggestions and services:
            # Use workflow_keyword if detected (language-neutral), else generic
            topic = entities.get('workflow_keyword') or entities.get('commerce_keyword') or ''
            if topic:
                suggestions.append({
                    "es": f"¿Qué documentos necesito para {topic}?",
                    "fr": f"Quels documents faut-il pour {topic} ?",
                    "en": f"What documents do I need for {topic}?",
                }.get(language, f"What documents do I need for {topic}?"))
                suggestions.append({
                    "es": f"¿Cuánto cuesta {topic}?",
                    "fr": f"Combien coûte {topic} ?",
                    "en": f"How much does {topic} cost?",
                }.get(language, f"How much does {topic} cost?"))
            else:
                suggestions.append({
                    "es": "¿Qué documentos necesito para este servicio?",
                    "fr": "Quels documents sont nécessaires pour ce service ?",
                    "en": "What documents do I need for this service?",
                }.get(language, "What documents do I need?"))
                suggestions.append({
                    "es": "¿Cuánto cuesta este servicio?",
                    "fr": "Combien coûte ce service ?",
                    "en": "How much does this service cost?",
                }.get(language, "How much does it cost?"))

        # Topic-based suggestions when no services found (multilingual)
        if not suggestions:
            topic_suggestions = {
                "pasaporte": {
                    "es": ["¿Cuánto cuesta un pasaporte?", "¿Qué documentos necesito para el pasaporte?", "¿Dónde se tramita el pasaporte?"],
                    "fr": ["Combien coûte un passeport ?", "Quels documents faut-il pour le passeport ?", "Où se fait le passeport ?"],
                    "en": ["How much does a passport cost?", "What documents do I need for a passport?", "Where to get a passport?"],
                },
                "passport": {
                    "es": ["¿Cuánto cuesta un pasaporte?", "¿Qué documentos necesito?", "¿Dónde se tramita?"],
                    "fr": ["Combien coûte un passeport ?", "Quels documents faut-il ?", "Où se fait le passeport ?"],
                    "en": ["How much does a passport cost?", "What documents do I need?", "Where to apply?"],
                },
                "empresa": {
                    "es": ["¿Cuántas empresas hay registradas?", "Empresas en Malabo", "Empresas del sector comercio"],
                    "fr": ["Combien d'entreprises sont enregistrées ?", "Entreprises à Malabo", "Entreprises du secteur commerce"],
                    "en": ["How many companies are registered?", "Companies in Malabo", "Commerce sector companies"],
                },
                "entreprise": {
                    "es": ["¿Cuántas empresas hay registradas?", "Empresas en Malabo", "Empresas del sector comercio"],
                    "fr": ["Combien d'entreprises sont enregistrées ?", "Entreprises à Malabo", "Entreprises du secteur commerce"],
                    "en": ["How many companies are registered?", "Companies in Malabo", "Commerce sector companies"],
                },
                "ministerio": {
                    "es": ["¿Cuáles son los ministerios?", "¿Qué servicios ofrece cada ministerio?", "Contacto de los ministerios"],
                    "fr": ["Quels sont les ministères ?", "Quels services offre chaque ministère ?", "Contact des ministères"],
                    "en": ["What are the ministries?", "What services does each ministry offer?", "Ministry contacts"],
                },
                "ministère": {
                    "es": ["¿Cuáles son los ministerios?", "¿Qué servicios ofrece cada ministerio?", "Contacto"],
                    "fr": ["Quels sont les ministères ?", "Quels services offre chaque ministère ?", "Contact des ministères"],
                    "en": ["What are the ministries?", "What services does each ministry offer?", "Contacts"],
                },
                "residencia": {
                    "es": ["¿Cuánto cuesta el permiso de residencia?", "Documentos para la residencia", "¿Cuánto tarda?"],
                    "fr": ["Combien coûte le permis de résidence ?", "Documents pour la résidence", "Combien de temps ?"],
                    "en": ["How much does a residence permit cost?", "Residence documents", "How long does it take?"],
                },
                "résidence": {
                    "es": ["¿Cuánto cuesta el permiso de residencia?", "Documentos para la residencia", "¿Cuánto tarda?"],
                    "fr": ["Combien coûte le permis de résidence ?", "Documents pour la résidence", "Combien de temps ?"],
                    "en": ["How much does a residence permit cost?", "Residence documents", "How long does it take?"],
                },
                "conducir": {
                    "es": ["¿Cuánto cuesta la licencia de conducir?", "Documentos para la licencia", "Tipos de licencia"],
                    "fr": ["Combien coûte le permis de conduire ?", "Documents pour le permis", "Types de permis"],
                    "en": ["How much does a driver's license cost?", "License documents", "License types"],
                },
            }
            for keyword, lang_suggestions in topic_suggestions.items():
                if keyword in query_lower:
                    suggestions.extend(lang_suggestions.get(language, lang_suggestions.get("es", []))[:3])
                    break

            # Generic fallback
            if not suggestions:
                suggestions = {
                    "es": ["¿Qué servicios están disponibles?", "¿Cuáles son los ministerios?", "¿Cómo funciona Facil?"],
                    "fr": ["Quels services sont disponibles ?", "Quels sont les ministères ?", "Comment fonctionne Facil ?"],
                    "en": ["What services are available?", "What are the ministries?", "How does Facil work?"],
                }.get(language, ["What services are available?"])

        return list(dict.fromkeys(suggestions))[:3]

    def _format_related_services(self, services: List[Dict]) -> List[Dict]:
        """Format services for response"""
        return [
            {
                "service_code": s["service_code"],
                "name": s["name_es"],
                "category": s.get("category_name", ""),
                "similarity": round(s.get("similarity", 0), 2)
            }
            for s in services[:5]
        ]

    def _format_related_documents(self, documents: List[Dict]) -> List[Dict]:
        """Format legislative documents for response"""
        return [
            {
                "document_name": d["document_name"],
                "page_number": d["page_number"],
                "similarity": round(d.get("similarity", 0), 2)
            }
            for d in documents[:settings.RAG_MAX_CONTEXT_DOCUMENTS] # Limit to top N documents
        ]

    def _generate_follow_up_actions(
        self,
        services: List[Dict],
        language: str
    ) -> List[str]:
        """Generate recommended next actions"""
        if not services:
            return []

        actions_templates = {
            "es": [
                "Ver detalles completos del servicio",
                "Calcular el costo total",
                "Iniciar el trámite"
            ],
            "fr": [
                "Voir les détails complets du service",
                "Calculer le coût total",
                "Commencer la procédure"
            ],
            "en": [
                "View complete service details",
                "Calculate total cost",
                "Start the procedure"
            ]
        }

        return actions_templates.get(language, actions_templates["es"])

    def _generate_search_suggestions(
        self,
        results: List[Dict],
        original_query: str,
        language: str
    ) -> List[str]:
        """Generate search refinement suggestions"""
        if not results:
            suggestions = {
                "es": ["Intenta con palabras diferentes", "Revisa la ortografía"],
                "fr": ["Essayez avec des mots différents", "Vérifiez l'orthographe"],
                "en": ["Try different words", "Check spelling"]
            }
            return suggestions.get(language, suggestions["es"])

        # Extract unique categories
        categories = list(set(
            r.get("category_name", "") for r in results
            if r.get("category_name")
        ))

        return [f"Buscar más servicios en {cat}" for cat in categories[:3]]

    def _extract_related_topics(self, results: List[Dict]) -> List[str]:
        """Extract related topics from results"""
        topics = set()

        for result in results:
            if result.get("category_name"):
                topics.add(result["category_name"])
            if result.get("sector_name"):
                topics.add(result["sector_name"])

        return list(topics)[:5]

    async def _generate_recommendation_explanation(
        self,
        services: List[Dict],
        user_intent: str,
        language: str
    ) -> str:
        """Generate explanation for recommendations using AI"""
        if not services or not gemini_service.enabled:
            return "Servicios recomendados basados en tu búsqueda."

        # Use Gemini to explain why these services are recommended
        prompt = f"""Explain briefly (2-3 sentences) why these services are recommended for: "{user_intent}"

Services:
{chr(10).join(f"- {s['service_code']}: {s['name_es']}" for s in services)}

Language: {language}
Keep it helpful and concise."""

        try:
            from app.modules.chatbot.services.gemini_service import gemini_service
            response = await gemini_service.chat(
                user_message=prompt,
                context_services=services,
                language=language
            )
            return response.get("message", "Servicios relevantes encontrados.")
        except Exception:
            return "Servicios recomendados basados en tu búsqueda."

    def _generate_next_steps(
        self,
        services: List[Dict],
        language: str
    ) -> List[str]:
        """Generate next steps for recommended services"""
        steps_templates = {
            "es": [
                "Revisar los requisitos de cada servicio",
                "Preparar los documentos necesarios",
                "Calcular los costos totales",
                "Iniciar el trámite cuando estés listo"
            ],
            "fr": [
                "Examiner les exigences de chaque service",
                "Préparer les documents nécessaires",
                "Calculer les coûts totaux",
                "Commencer la procédure quand vous êtes prêt"
            ],
            "en": [
                "Review requirements for each service",
                "Prepare necessary documents",
                "Calculate total costs",
                "Start the process when ready"
            ]
        }

        return steps_templates.get(language, steps_templates["es"])

    def _generate_did_you_mean_suggestions(
        self,
        query: str,
        relevant_docs_extended: List[Dict],
        relevant_services_extended: List[Dict],
        language: str
    ) -> List[str]:
        """
        Generates "Did you mean?" suggestions from extended search results
        that are below the main similarity threshold but above the suggestion threshold.
        """
        suggestions = []
        
        # Collect potential suggestions from docs
        for doc in relevant_docs_extended:
            if settings.SUGGESTION_SIMILARITY_THRESHOLD <= doc.get('similarity', 0) < settings.SEMANTIC_SEARCH_SIMILARITY_THRESHOLD:
                doc_name = doc.get('document_name', '')
                if doc_name and doc_name not in suggestions: # Avoid duplicates
                    suggestions.append(f"{doc_name}")
        
        # Collect potential suggestions from services
        for svc in relevant_services_extended:
            if settings.SUGGESTION_SIMILARITY_THRESHOLD <= svc.get('similarity', 0) < settings.SEMANTIC_SEARCH_SIMILARITY_THRESHOLD:
                svc_name = svc.get('name_es', '') # Assuming name_es is always present and descriptive enough
                if svc_name and svc_name not in suggestions: # Avoid duplicates
                    suggestions.append(f"{svc_name}")
        
        if suggestions:
            # Craft a polite "Did you mean?" question
            did_you_mean_template = {
                "es": "No encontré una respuesta directa. ¿Quizás quisiste decir sobre: {suggestions_list}?",
                "fr": "Je n'ai pas trouvé de réponse directe. Vouliez-vous dire : {suggestions_list} ?",
                "en": "I couldn't find a direct answer. Did you mean: {suggestions_list}?"
            }
            suggestions_list_str = ", ".join(suggestions[:3]) # Limit to top 3 suggestions
            return [did_you_mean_template.get(language, did_you_mean_template["es"]).format(suggestions_list=suggestions_list_str)]
        
        return []

    # ========================================================================
    # CONVERSATION PERSISTENCE
    # ========================================================================

    async def _load_conversation(
        self, db: asyncpg.Connection, conversation_id: str
    ) -> Optional[List[Dict[str, str]]]:
        """Load conversation history from DB. Returns list of messages or None."""
        try:
            row = await db.fetchrow(
                "SELECT messages FROM chatbot_conversations WHERE conversation_id = $1",
                conversation_id,
            )
            if row and row["messages"]:
                messages = json.loads(row["messages"]) if isinstance(row["messages"], str) else row["messages"]
                return messages
        except Exception as e:
            logger.warning(f"Failed to load conversation {conversation_id}: {e}")
        return None

    async def _save_conversation(
        self,
        db: asyncpg.Connection,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
        user_id: Optional[str] = None,
        language: str = "es",
    ) -> None:
        """Append user+assistant messages to conversation and persist."""
        try:
            new_messages = [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message},
            ]
            # Upsert: create or append
            await db.execute(
                """
                INSERT INTO chatbot_conversations
                    (conversation_id, user_id, messages, language, message_count, last_message_at)
                VALUES ($1, $2::uuid, $3::jsonb, $4, 2, NOW())
                ON CONFLICT (conversation_id) DO UPDATE SET
                    messages = chatbot_conversations.messages || $3::jsonb,
                    message_count = chatbot_conversations.message_count + 2,
                    last_message_at = NOW()
                """,
                conversation_id,
                user_id,
                json.dumps(new_messages),
                language,
            )
        except Exception as e:
            # Non-fatal: log and continue
            logger.warning(f"Failed to save conversation {conversation_id}: {e}")

    # ========================================================================
    # RESPONSE CACHE (Redis-backed, 1h TTL for common queries)
    # ========================================================================

    async def _get_cached_response(self, message: str, language: str, user_id: Optional[str] = None) -> Optional[Dict]:
        """Check Redis cache for a previous response (user-scoped)."""
        try:
            from app.core.cache import get_cache
            cache = get_cache()
            uid = user_id or "anon"
            cache_key = f"chat:resp:{language}:{uid}:{hashlib.md5(message.lower().strip().encode()).hexdigest()}"
            cached = await cache.get(cache_key)
            if cached and isinstance(cached, dict):
                return cached
        except Exception:
            pass
        return None

    async def _cache_response(self, message: str, language: str, response: Dict, user_id: Optional[str] = None):
        """Cache a successful response (user-scoped, 10min TTL, confidence >= 0.6)."""
        try:
            from app.core.cache import get_cache
            cache = get_cache()
            uid = user_id or "anon"
            cache_key = f"chat:resp:{language}:{uid}:{hashlib.md5(message.lower().strip().encode()).hexdigest()}"
            # Only cache high-confidence responses (0.6 threshold)
            if response.get("confidence", 0) >= 0.6:
                cache_data = {
                    "message": response.get("message", ""),
                    "suggestions": response.get("suggestions", []),
                    "related_services": response.get("related_services", []),
                    "related_documents": response.get("related_documents", []),
                    "follow_up_actions": response.get("follow_up_actions", []),
                    "actions": response.get("actions", []),
                    "confidence": response.get("confidence", 0),
                    "sources": response.get("sources", []),
                }
                await cache.set(cache_key, cache_data, ttl=600)  # 10 minutes (was 1 hour)
                logger.debug(f"Cached response for user={uid}: '{message[:40]}...'")
        except Exception as e:
            logger.debug(f"Cache set failed (non-fatal): {e}")

    # ========================================================================
    # CONVERSATION SUMMARIZATION
    # ========================================================================

    def _summarize_history(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Compress old conversation messages into a summary.

        Keeps last 10 messages verbatim. Summarizes older ones into a
        single system message so Gemini has context without token bloat.
        """
        if not history or len(history) <= 10:
            return history

        # Split: old messages to summarize + recent to keep
        old_messages = history[:-10]
        recent_messages = history[-10:]

        # Build summary from old messages
        topics = []
        for msg in old_messages:
            if msg.get("role") == "user":
                topics.append(msg.get("content", "")[:100])
            elif msg.get("role") == "assistant":
                # Extract first sentence of assistant response
                content = msg.get("content", "")
                first_sentence = content.split(".")[0][:120] if content else ""
                if first_sentence:
                    topics.append(f"→ {first_sentence}")

        summary_text = (
            "RESUMEN DE CONVERSACIÓN ANTERIOR:\n"
            + "\n".join(topics[-8:])  # Last 8 exchanges max
        )

        summary_message = {
            "role": "system",
            "content": summary_text,
        }

        return [summary_message] + recent_messages

    # ========================================================================
    # SELF-EVALUATION (quality check)
    # ========================================================================

    async def _evaluate_response(
        self, question: str, response_text: str, context: str
    ) -> float:
        """Self-evaluation with hallucination guardrails.

        Returns quality score 0-1:
        - >= 0.7: High quality, grounded response
        - 0.4-0.7: Acceptable, may need improvement
        - < 0.4: Low quality, likely off-topic or hallucinated → triggers retry
        """
        if not response_text or len(response_text) < 20:
            return 0.1

        score = 0.4  # Base score

        # ── Quality checks (positive signals) ──

        # Check 1: Response length (meaningful content)
        if len(response_text) > 100:
            score += 0.05
        if len(response_text) > 300:
            score += 0.05

        # Check 2: Response mentions key terms from question
        question_words = {w.lower() for w in question.split() if len(w) > 3}
        response_lower = response_text.lower()
        overlap = sum(1 for w in question_words if w in response_lower)
        if overlap >= 2:
            score += 0.1
        if overlap >= 4:
            score += 0.05

        # Check 3: Response uses data from context (grounding)
        if context:
            context_words = {w.lower() for w in context.split() if len(w) > 5}
            grounded = sum(1 for w in list(context_words)[:30] if w in response_lower)
            if grounded >= 3:
                score += 0.1
            if grounded >= 8:
                score += 0.1

        # Check 4: Response has structure (markdown = used context intelligently)
        has_bold = "**" in response_text
        has_list = "- " in response_text or "1." in response_text
        has_heading = "###" in response_text or "##" in response_text
        if has_bold:
            score += 0.05
        if has_list:
            score += 0.05
        if has_heading:
            score += 0.05

        # ── Guardrails (negative signals — hallucination detection) ──

        # Guard 1: Response says "I don't know" or "no information"
        refusal_phrases = [
            "no tengo", "no puedo", "no dispongo", "no encuentro",
            "je ne peux pas", "i cannot", "i don't have",
            "no hay información", "sin información",
        ]
        if any(phrase in response_lower for phrase in refusal_phrases):
            score -= 0.15

        # Guard 2: Response mentions URLs (we told it not to)
        if "http://" in response_text or "https://" in response_text or "www." in response_text:
            score -= 0.1

        # Guard 3: Response has colored emojis (monographic symbols → ▸ ● ✓ are OK)
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF\U0001F900-\U0001F9FF]"
        )
        if emoji_pattern.search(response_text):
            score -= 0.05

        # Guard 4: Response is too short for a factual question
        factual_keywords = ["cuanto", "costo", "precio", "documentos", "requisitos", "procedimiento"]
        is_factual = any(kw in question.lower() for kw in factual_keywords)
        if is_factual and len(response_text) < 100:
            score -= 0.1

        return max(0.0, min(1.0, score))

    # ========================================================================
    # USER MEMORY — Personalization
    # ========================================================================

    async def _load_user_profile(self, db: asyncpg.Connection, user_id: Optional[str]) -> Optional[str]:
        """Load user preferences and build a profile context string for the LLM."""
        if not user_id:
            return None
        try:
            prefs = await db.fetchrow(
                "SELECT * FROM chatbot_user_preferences WHERE user_id = $1",
                user_id
            )
            if not prefs:
                return None

            parts = ["=== PROFIL UTILISATEUR ==="]
            if prefs["preferred_language"]:
                parts.append(f"Langue préférée: {prefs['preferred_language']}")
            if prefs["preferred_city"]:
                parts.append(f"Ville: {prefs['preferred_city']} (zone {prefs.get('preferred_zone_code', '?')})")
            if prefs["user_type"]:
                type_labels = {
                    "citizen": "Citoyen",
                    "business_owner": "Entrepreneur / Chef d'entreprise",
                    "accountant": "Comptable",
                    "agent": "Agent gouvernemental",
                }
                parts.append(f"Profil: {type_labels.get(prefs['user_type'], prefs['user_type'])}")
            if prefs["frequent_topics"]:
                parts.append(f"Sujets fréquents: {', '.join(prefs['frequent_topics'][:5])}")
            if prefs["total_conversations"]:
                parts.append(f"Conversations précédentes: {prefs['total_conversations']}")

            return "\n".join(parts) if len(parts) > 1 else None
        except Exception as e:
            logger.warning(f"User profile load failed (table may not exist yet): {e}")
            return None

    async def _update_user_preferences(
        self,
        db: asyncpg.Connection,
        user_id: Optional[str],
        language: str,
        entities: Dict[str, str],
    ):
        """Update user preferences based on conversation context (non-blocking)."""
        if not user_id:
            return
        try:
            city = entities.get('city')
            zone = entities.get('zone_code')
            topic = entities.get('workflow_keyword') or entities.get('commerce_keyword')

            await db.execute("""
                INSERT INTO chatbot_user_preferences (user_id, preferred_language, preferred_city, preferred_zone_code, total_conversations, last_interaction_at)
                VALUES ($1::uuid, $2, $3, $4, 1, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    preferred_language = COALESCE(EXCLUDED.preferred_language, chatbot_user_preferences.preferred_language),
                    preferred_city = COALESCE(EXCLUDED.preferred_city, chatbot_user_preferences.preferred_city),
                    preferred_zone_code = COALESCE(EXCLUDED.preferred_zone_code, chatbot_user_preferences.preferred_zone_code),
                    total_conversations = chatbot_user_preferences.total_conversations + 1,
                    last_interaction_at = NOW(),
                    updated_at = NOW()
            """, user_id, language, city, zone)

            # Append topic to frequent_topics array (max 10, no duplicates)
            if topic:
                await db.execute("""
                    UPDATE chatbot_user_preferences
                    SET frequent_topics = (
                        SELECT array_agg(t) FROM (
                            SELECT DISTINCT t FROM unnest(
                                array_append(COALESCE(frequent_topics, ARRAY[]::text[]), $2)
                            ) t
                            ORDER BY t
                            LIMIT 10
                        ) sub
                    )
                    WHERE user_id = $1
                """, user_id, topic)

        except Exception as e:
            logger.debug(f"User preferences update failed: {e}")

    # ========================================================================
    # SELF-REFLECTION LOOP
    # ========================================================================

    async def _self_reflect(
        self,
        question: str,
        response: str,
        language: str,
    ) -> Optional[int]:
        """Ask the LLM to evaluate its own response. Returns score 1-10 or None on failure."""
        if not response or len(response) < 50:
            return None

        eval_prompt = {
            "es": f'Evalúa esta respuesta a la pregunta "{question[:100]}" en 3 criterios: exactitud, completitud, claridad. Responde SOLO con un número del 1 al 10. Nada más.\n\nRespuesta a evaluar:\n{response[:500]}',
            "fr": f'Évalue cette réponse à la question "{question[:100]}" sur 3 critères : exactitude, complétude, clarté. Réponds UNIQUEMENT avec un nombre de 1 à 10. Rien d\'autre.\n\nRéponse à évaluer :\n{response[:500]}',
            "en": f'Evaluate this response to "{question[:100]}" on 3 criteria: accuracy, completeness, clarity. Reply ONLY with a number from 1 to 10. Nothing else.\n\nResponse to evaluate:\n{response[:500]}',
        }

        try:
            result = await gemini_service.chat(
                user_message=eval_prompt.get(language, eval_prompt["es"]),
                context_content="",
                context_services=[],
                language=language,
            )
            score_text = result.get("message", "").strip()
            # Extract first number from response
            match = re.search(r'\b(\d{1,2})\b', score_text)
            if match:
                score = int(match.group(1))
                if 1 <= score <= 10:
                    logger.info(f"Self-reflection score: {score}/10 for '{question[:40]}...'")
                    return score
        except Exception as e:
            logger.debug(f"Self-reflection failed: {e}")

        return None

    # ========================================================================
    # SECURITY: PROMPT INJECTION DETECTION
    # ========================================================================

    _INJECTION_PATTERNS = [
        # English
        'ignore previous', 'ignore all previous', 'forget your instructions',
        'disregard your', 'override your', 'new instructions',
        'you are now', 'pretend you are', 'act as', 'roleplay',
        'what are your instructions', 'show me your prompt',
        'system prompt', 'system message', 'reveal your',
        # Spanish
        'ignora las instrucciones', 'olvida tus instrucciones',
        'ignora todo lo anterior', 'nuevas instrucciones',
        'ahora eres', 'finge que eres', 'actúa como',
        'muéstrame tu prompt', 'cuáles son tus instrucciones',
        # French
        'ignore les instructions', 'oublie tes instructions',
        'ignore tout ce qui précède', 'nouvelles instructions',
        'tu es maintenant', 'fais semblant', 'joue le rôle',
        'montre-moi ton prompt', 'quelles sont tes instructions',
    ]

    def _detect_prompt_injection(self, message: str) -> bool:
        """Detect prompt injection patterns with unicode normalization."""
        # Normalize unicode (strip homoglyphs, zero-width chars)
        normalized = unicodedata.normalize('NFKC', message)
        # Remove zero-width characters
        normalized = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff]', '', normalized)
        msg_lower = normalized.lower()
        return any(pattern in msg_lower for pattern in self._INJECTION_PATTERNS)

    # ========================================================================
    # EMBEDDING CACHE (24h TTL)
    # ========================================================================

    async def _get_or_create_embedding(self, query: str) -> Optional[List[float]]:
        """Get embedding from cache or generate fresh one. 24h TTL."""
        from app.core.cache import get_cache
        cache = get_cache()
        cache_key = f"emb:query:{hashlib.md5(query.lower().strip().encode()).hexdigest()}"

        try:
            cached = await cache.get(cache_key)
            if cached and isinstance(cached, list) and len(cached) > 0:
                logger.debug(f"Embedding cache HIT for: '{query[:40]}...'")
                return cached
        except Exception:
            pass

        embedding = await embedding_service.generate_query_embedding(query)
        if embedding:
            try:
                await cache.set(cache_key, embedding, ttl=86400)  # 24 hours
            except Exception:
                pass
        return embedding

    # ========================================================================
    # ACTION BUTTONS EXTRACTION
    # ========================================================================

    def _build_permission_action(
        self, perm_type: str, label_key: str = "activatePermission"
    ) -> Dict[str, Any]:
        """
        Build an `open_settings` action for permission refusals.

        Emits both the legacy `label` (Spanish, for backward compat with
        older frontends) and the new `label_key`/`label_params` pair for
        i18n-aware frontends. The URL carries `permission` so the
        DocumentVault reader can auto-scroll to the target row.
        """
        return {
            "type": "open_settings",
            "label": f"Activar permiso: {perm_type}",  # legacy Spanish fallback
            "label_key": f"chatbot.actions.{label_key}",
            "label_params": {"permission_key": perm_type},
            "url": f"/dashboard/documents?settings=agent&permission={perm_type}",
            "permission_type": perm_type,
        }

    def _extract_actions_from_tools(
        self,
        tools_used: List[str],
        function_results_data: List[Dict],
    ) -> List[Dict[str, Any]]:
        """
        Extract action buttons from tool execution results.

        Every action emits both a legacy `label` (Spanish) and an i18n
        `label_key` (+ optional `label_params`). The frontend prefers the
        key when present, falls back to the literal label. This dual-write
        lets us ship backend and frontend independently.
        """
        actions: List[Dict[str, Any]] = []

        for fr in function_results_data:
            fn_name = fr.get("name", "")
            result = fr.get("result", {})

            if fn_name == "start_workflow" and result.get("wizard_url"):
                workflow_name = result.get("workflow_name", "trámite")
                actions.append({
                    "type": "start_workflow",
                    "label": f"Iniciar {workflow_name} en Facil",
                    "label_key": "chatbot.actions.startWorkflow",
                    "label_params": {"workflow": workflow_name},
                    "url": result["wizard_url"],
                    "workflow_code": result.get("workflow_code", ""),
                })

            elif fn_name == "get_workflow_guide" and result.get("workflow_code"):
                actions.append({
                    "type": "start_workflow",
                    "label": "Iniciar en Facil",
                    "label_key": "chatbot.actions.startInFacil",
                    "url": f"/dashboard/service-requests/new?workflow={result['workflow_code']}",
                    "workflow_code": result["workflow_code"],
                })

            elif fn_name == "search_bundles" and result.get("bundles"):
                actions.append({
                    "type": "view_pricing",
                    "label": "Ver todos los precios por zona",
                    "label_key": "chatbot.actions.viewPricing",
                })

            elif fn_name == "get_document_checklist" and result.get("documents"):
                actions.append({
                    "type": "start_workflow",
                    "label": "Iniciar trámite en Facil",
                    "label_key": "chatbot.actions.startInFacil",
                    "url": f"/dashboard/service-requests/new?workflow={result.get('workflow_code', '')}",
                    "workflow_code": result.get("workflow_code", ""),
                })

            # Auto-prepare wizard — Level 2 agent action
            elif fn_name == "auto_prepare_wizard":
                if result.get("status") == "prepared" and result.get("action"):
                    action = result["action"]
                    actions.append({
                        "type": action.get("type", "open_wizard"),
                        "label": action.get("label", "Finalizar solicitud"),
                        "label_key": "chatbot.actions.finalize",
                        "url": action.get("url", ""),
                        "workflow_code": result.get("workflow_code", ""),
                    })
                elif result.get("status") == "missing_documents" and result.get("requires_user_choice"):
                    # Don't add action — the response message asks the user to choose
                    pass
                elif result.get("status") == "permission_required":
                    perm_type = result.get("permission_type", "prepare_request")
                    actions.append(self._build_permission_action(perm_type))

            elif fn_name == "submit_prepared_request":
                if result.get("status") == "submitted" and result.get("action"):
                    action = result["action"]
                    actions.append({
                        "type": action.get("type", "open_wizard"),
                        "label": action.get("label", "Ver solicitud"),
                        "label_key": "chatbot.actions.viewRequest",
                        "url": action.get("url", ""),
                    })
                elif result.get("status") == "confirmation_required":
                    # Phase 5 — executive tool needs per-action consent.
                    # Frontend opens a destructive modal with the summary,
                    # user confirms → POST /chatbot/execute-confirmed with
                    # the code, which dispatches to the real execution.
                    actions.append({
                        "type": "confirm_executive",
                        "label": "Confirmer et envoyer",
                        "label_key": "chatbot.actions.confirmAndSubmit",
                        "confirmation_code": result.get("confirmation_code", ""),
                        "summary": result.get("summary", ""),
                        "tool_name": result.get("tool_name", "submit_prepared_request"),
                    })
                elif result.get("status") == "permission_required":
                    actions.append(
                        self._build_permission_action(
                            result.get("permission_type", "submit_request"),
                            label_key="activateSubmitPermission",
                        )
                    )

            elif fn_name == "book_appointment":
                if result.get("status") == "booked":
                    appointment_date = result.get("appointment_date", "")
                    actions.append({
                        "type": "appointment_booked",
                        "label": f"Cita reservada: {appointment_date}",
                        "label_key": "chatbot.actions.appointmentBooked",
                        "label_params": {"date": appointment_date},
                        "url": "",
                    })
                elif result.get("status") == "confirmation_required":
                    actions.append({
                        "type": "confirm_executive",
                        "label": "Confirmer la réservation",
                        "label_key": "chatbot.actions.confirmAndSubmit",
                        "confirmation_code": result.get("confirmation_code", ""),
                        "summary": result.get("summary", ""),
                        "tool_name": result.get("tool_name", "book_appointment"),
                    })
                elif result.get("status") == "permission_required":
                    actions.append(
                        self._build_permission_action(
                            result.get("permission_type", "book_appointment"),
                            label_key="activateBookPermission",
                        )
                    )

            elif fn_name == "prepare_renewal":
                if result.get("status") == "prepared":
                    wf_code = result.get("workflow_code", "")
                    actions.append({
                        "type": "start_workflow",
                        "label": "Iniciar renovación",
                        "label_key": "chatbot.actions.startRenewal",
                        "url": f"/dashboard/service-requests/new?workflow={wf_code}",
                        "workflow_code": wf_code,
                    })
                elif result.get("status") == "permission_required":
                    actions.append(
                        self._build_permission_action(
                            result.get("permission_type", "prepare_renewal")
                        )
                    )

        return actions

    # ========================================================================
    # STREAMING STATUS MESSAGES
    # ========================================================================

    _STATUS_TEXTS = {
        "searching": {
            "es": "Buscando en documentos y servicios...",
            "fr": "Recherche dans les documents et services...",
            "en": "Searching documents and services...",
        },
        "analyzing": {
            "es": "Analizando resultados...",
            "fr": "Analyse des résultats...",
            "en": "Analyzing results...",
        },
        "generating": {
            "es": "Preparando respuesta...",
            "fr": "Préparation de la réponse...",
            "en": "Preparing response...",
        },
    }

    def _status_text(self, step: str, language: str = "es") -> str:
        return self._STATUS_TEXTS.get(step, {}).get(language, self._STATUS_TEXTS.get(step, {}).get("es", ""))

    # ========================================================================
    # FEEDBACK & ANALYTICS
    # ========================================================================

    async def record_feedback(
        self,
        db: asyncpg.Connection,
        conversation_id: str,
        rating: int,
        feedback_text: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record user feedback (thumbs up/down) for a chatbot response."""
        try:
            await db.execute("""
                INSERT INTO chatbot_feedback (conversation_id, rating, feedback_text, user_id)
                VALUES ($1, $2, $3, $4)
            """, conversation_id, rating, feedback_text,
                user_id if user_id else None)

            logger.info(f"Feedback recorded: conv={conversation_id}, rating={rating}")

            # Reinforce or weaken recent memories based on feedback
            if user_id:
                try:
                    delta = 0.1 if rating >= 4 else -0.15 if rating <= 2 else 0
                    if delta != 0:
                        await self._reinforce_recent_memories(db, user_id, delta)
                except Exception as mem_err:
                    logger.debug(f"Memory reinforcement failed: {mem_err}")

            return {"status": "success", "message": "Feedback recorded"}
        except Exception as e:
            logger.error(f"Failed to record feedback: {e}")
            return {"status": "error", "message": str(e)}

    async def get_usage_stats(
        self,
        db: asyncpg.Connection,
    ) -> Dict[str, Any]:
        """Get chatbot usage statistics for admin dashboard."""
        try:
            # Conversation stats
            conv_stats = await db.fetchrow("""
                SELECT
                    COUNT(*) as total_conversations,
                    COALESCE(SUM(message_count), 0) as total_messages,
                    COUNT(*) FILTER (WHERE last_message_at >= NOW() - INTERVAL '24 hours') as active_24h,
                    COUNT(*) FILTER (WHERE last_message_at >= NOW() - INTERVAL '7 days') as active_7d
                FROM chatbot_conversations
            """)

            # Feedback stats (from view if table exists, otherwise empty)
            try:
                feedback_stats = await db.fetchrow("SELECT * FROM v_chatbot_feedback_stats")
                feedback = dict(feedback_stats) if feedback_stats else {}
            except Exception:
                feedback = {
                    "total_feedback": 0, "positive_count": 0, "negative_count": 0,
                    "avg_rating": 0, "unique_conversations": 0,
                    "feedback_last_24h": 0, "feedback_last_7d": 0,
                }

            # Rating distribution
            try:
                dist_rows = await db.fetch("""
                    SELECT rating, COUNT(*) as count
                    FROM chatbot_feedback
                    GROUP BY rating ORDER BY rating
                """)
                rating_distribution = {str(r["rating"]): r["count"] for r in dist_rows}
            except Exception:
                rating_distribution = {}

            return {
                "conversations": dict(conv_stats) if conv_stats else {},
                "feedback": feedback,
                "rating_distribution": rating_distribution,
            }
        except Exception as e:
            logger.error(f"Failed to get usage stats: {e}")
            return {"error": str(e)}

    # ========================================================================
    # AGENT MEMORY — Learning loop + Context builder
    # ========================================================================

    async def _post_interaction_learning(
        self,
        db: asyncpg.Connection,
        user_id: str,
        conversation_id: str,
        tool_calls: list = None,
        language: str = "es",
    ):
        """
        Post-interaction learning: detect patterns and enrich agent memory.
        Called after each chat response (non-blocking, non-fatal).
        """
        if not user_id or not db:
            return
        try:
            tool_calls = tool_calls or []
            for tc in tool_calls:
                name = tc.get("name", "") if isinstance(tc, dict) else str(tc)
                args = tc.get("args", {}) if isinstance(tc, dict) else {}

                # Pattern: user checked readiness for a workflow
                if name == "check_readiness" and args.get("workflow_code"):
                    wf = args["workflow_code"]
                    await self._learn_memory(db, user_id, {
                        "type": "behavioral",
                        "key": f"interested_in_{wf}",
                        "content": f"Usuario interesado en trámite: {wf}",
                        "learned_from": "pattern_detected",
                        "conversation_id": conversation_id,
                    })

                # Pattern: user listed vault documents for a workflow
                if name == "list_vault_documents" and args.get("workflow_code"):
                    wf = args["workflow_code"]
                    await self._learn_memory(db, user_id, {
                        "type": "behavioral",
                        "key": f"docs_for_{wf}",
                        "content": f"Usuario busca documentos para: {wf}",
                        "learned_from": "pattern_detected",
                        "conversation_id": conversation_id,
                    })

                # Pattern: user prepared a renewal
                if name == "prepare_renewal":
                    doc_type = args.get("document_type", "unknown")
                    await self._learn_memory(db, user_id, {
                        "type": "capability",
                        "key": f"renewal_{doc_type}",
                        "content": f"Asistente preparó renovación de {doc_type}",
                        "learned_from": "action_confirmed",
                        "conversation_id": conversation_id,
                    })

                # Pattern: user checked expiring documents
                if name == "get_expiring_documents":
                    await self._learn_memory(db, user_id, {
                        "type": "behavioral",
                        "key": "monitors_expiry",
                        "content": "Usuario monitorea vencimiento de documentos",
                        "learned_from": "pattern_detected",
                        "conversation_id": conversation_id,
                    })

                # Pattern: user asked about a specific workflow via get_workflow_guide
                if name == "get_workflow_guide" and args.get("workflow_code"):
                    wf = args["workflow_code"]
                    await self._learn_memory(db, user_id, {
                        "type": "behavioral",
                        "key": f"guides_{wf}",
                        "content": f"Usuario consulto guia de: {wf}",
                        "learned_from": "pattern_detected",
                        "conversation_id": conversation_id,
                    })

                # Pattern: user used start_workflow — they're actively pursuing
                if name == "start_workflow":
                    wf = args.get("workflow_name", "")
                    await self._learn_memory(db, user_id, {
                        "type": "capability",
                        "key": f"started_{wf}",
                        "content": f"Usuario inicio tramite: {wf}",
                        "learned_from": "action_confirmed",
                        "conversation_id": conversation_id,
                    })

                # Pattern: user asked auto_prepare_wizard — they trust the agent
                if name == "auto_prepare_wizard":
                    await self._learn_memory(db, user_id, {
                        "type": "behavioral",
                        "key": "trusts_agent_preparation",
                        "content": "Usuario confia en preparacion automatica del agente",
                        "learned_from": "action_confirmed",
                        "conversation_id": conversation_id,
                    })

            # Detect language preference
            if language and language != "es":
                lang_names = {"fr": "francés", "en": "inglés"}
                lang_label = lang_names.get(language, language)
                await self._learn_memory(db, user_id, {
                    "type": "preference",
                    "key": "preferred_language",
                    "content": f"Usuario prefiere comunicarse en {lang_label}",
                    "learned_from": "preference_detected",
                    "conversation_id": conversation_id,
                })

        except Exception as e:
            logger.debug(f"Post-interaction learning failed: {e}")

    async def _learn_memory(
        self,
        db: asyncpg.Connection,
        user_id: str,
        memory: dict,
    ):
        """Create or reinforce a memory entry (UPSERT)."""
        try:
            await db.execute("""
                INSERT INTO user_agent_memory (
                    user_id, memory_type, content, content_key,
                    learned_from, source_conversation_id, confidence
                ) VALUES ($1::uuid, $2, $3, $4, $5, $6::uuid, 0.5)
                ON CONFLICT (user_id, content_key)
                    WHERE is_active = TRUE AND content_key IS NOT NULL
                DO UPDATE SET
                    confirmation_count = user_agent_memory.confirmation_count + 1,
                    confidence = LEAST(user_agent_memory.confidence + 0.1, 1.0),
                    last_used_at = NOW(),
                    updated_at = NOW()
            """,
                user_id,
                memory.get("type", "behavioral"),
                memory["content"],
                memory.get("key"),
                memory.get("learned_from", "pattern_detected"),
                memory.get("conversation_id"),
            )
        except Exception as e:
            logger.debug(f"Learn memory failed: {e}")

    async def _reinforce_recent_memories(
        self,
        db: asyncpg.Connection,
        user_id: str,
        delta: float,
    ):
        """Reinforce or weaken memories used in the last 5 minutes."""
        try:
            if delta > 0:
                await db.execute("""
                    UPDATE user_agent_memory
                    SET confidence = LEAST(confidence + $2, 1.0),
                        confirmation_count = confirmation_count + 1,
                        last_used_at = NOW(), updated_at = NOW()
                    WHERE user_id = $1::uuid AND is_active = TRUE
                      AND last_used_at > NOW() - INTERVAL '5 minutes'
                """, user_id, abs(delta))
            else:
                await db.execute("""
                    UPDATE user_agent_memory
                    SET confidence = GREATEST(confidence - $2, 0.0),
                        rejection_count = rejection_count + 1,
                        updated_at = NOW()
                    WHERE user_id = $1::uuid AND is_active = TRUE
                      AND last_used_at > NOW() - INTERVAL '5 minutes'
                """, user_id, abs(delta))

            # Deactivate memories with very low confidence + multiple rejections
            await db.execute("""
                UPDATE user_agent_memory
                SET is_active = FALSE, updated_at = NOW()
                WHERE user_id = $1::uuid AND confidence < 0.2 AND rejection_count >= 3
            """, user_id)
        except Exception as e:
            logger.debug(f"Memory reinforcement failed: {e}")

    async def _build_full_agent_context(
        self,
        db: asyncpg.Connection,
        user_id: str,
    ) -> str:
        """
        Build vault + memory + permissions context for injection into system prompt.
        Limited to ~1500 tokens to avoid diluting RAG context.
        """
        parts = []
        try:
            # 1. Vault stats (quick aggregate)
            vault_stats = await db.fetchrow("""
                SELECT
                    COUNT(*) FILTER (WHERE status = 'active') as total,
                    COUNT(*) FILTER (WHERE expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '90 days' AND status = 'active') as expiring,
                    COUNT(*) FILTER (WHERE expiry_date < CURRENT_DATE AND status = 'active') as expired,
                    COALESCE(SUM(file_size_bytes) FILTER (WHERE source = 'personal' AND deleted_at IS NULL), 0) as used_bytes
                FROM user_documents
                WHERE user_id = $1::uuid AND deleted_at IS NULL
            """, user_id)

            if vault_stats and vault_stats["total"] > 0:
                used_mb = round(int(vault_stats["used_bytes"]) / 1024 / 1024, 1)
                parts.append(
                    f"=== COFRE DIGITAL DEL USUARIO ===\n"
                    f"Documentos: {vault_stats['total']} total"
                    f" ({vault_stats['expiring']} por vencer, {vault_stats['expired']} expirados)"
                    f"\nEspacio: {used_mb}/100 Mo"
                )

            # 2. Learned memories (max 12, confidence >= 0.4)
            memories = await db.fetch("""
                SELECT id, content, memory_type, confidence
                FROM user_agent_memory
                WHERE user_id = $1::uuid AND is_active = TRUE AND confidence >= 0.4
                ORDER BY confidence DESC, last_used_at DESC NULLS LAST
                LIMIT 12
            """, user_id)

            if memories:
                # Mark ONLY fetched memories as used (for targeted feedback reinforcement)
                memory_ids = [m["id"] for m in memories if m.get("id")]
                if memory_ids:
                    await db.execute("""
                        UPDATE user_agent_memory
                        SET last_used_at = NOW()
                        WHERE id = ANY($1::uuid[])
                    """, memory_ids)

                type_marker = {
                    "preference": "[PREF]", "behavioral": "[PATTERN]",
                    "correction": "[CORRECTED]", "capability": "[SKILL]", "context": "[CONTEXT]",
                }
                lines = [f"=== MEMORIAS APRENDIDAS ({len(memories)}) ==="]
                for m in memories:
                    marker = type_marker.get(m["memory_type"], "[INFO]")
                    lines.append(f"- {marker} {m['content']} ({m['confidence']:.0%})")

                # Derive behavioral directives from memories
                directives = []
                for m in memories:
                    content_lower = m["content"].lower()
                    mtype = m["memory_type"]
                    conf = float(m["confidence"])

                    if mtype == "correction" and conf >= 0.7:
                        directives.append(f"CORRECCION ({conf:.0%}): {m['content']}")
                    elif mtype == "preference" and conf >= 0.6:
                        directives.append(f"PREFERENCIA ({conf:.0%}): {m['content']}")
                    elif mtype == "behavioral" and conf >= 0.5:
                        # Convert behavioral patterns to actionable directives
                        if "interesado en" in content_lower:
                            workflow = content_lower.split("interesado en")[-1].strip().rstrip(".")
                            directives.append(
                                f"SUGERENCIA: El usuario suele preguntar sobre {workflow}. "
                                "Proactivamente ofrecer informacion relacionada."
                            )
                        elif "renueva" in content_lower or "renovar" in content_lower:
                            directives.append(
                                "SUGERENCIA: El usuario tiene historial de renovaciones. "
                                "Ofrecer auto_prepare_wizard si corresponde."
                            )

                if directives:
                    lines.append("\n--- DIRECTIVAS COMPORTAMENTALES ---")
                    for d in directives:
                        lines.append(f"-> {d}")

                parts.append("\n".join(lines))

            # 3. Active permissions
            permissions = await db.fetch("""
                SELECT permission_type, scope, level
                FROM user_agent_permissions
                WHERE user_id = $1::uuid AND is_active = TRUE
            """, user_id)

            perm_lines = ["=== PERMISOS DEL ASISTENTE ==="]
            if permissions:
                for p in permissions:
                    scope_label = f" ({p['scope']})" if p["scope"] else " (todos)"
                    level_label = "proactivo" if p["level"] == 2 else "preparación"
                    perm_lines.append(f"- [GRANTED] {p['permission_type']}{scope_label} — nivel {level_label}")
            else:
                perm_lines.append("- Sin permisos especiales. Modo informacional solamente.")
                perm_lines.append("- Sugerir activación de permisos de forma no intrusiva (máximo 1 vez por sesión).")

            # Always add autonomy rules
            perm_lines.extend([
                "\n=== REGLAS DE AUTONOMÍA ===",
                "- Nivel 0 (siempre): Consultar, informar, guiar. Sin confirmación.",
                "- Nivel 1 (si permiso): Preparar acciones, presentar resumen. Confirmación REQUERIDA.",
                "- Nivel 2 (si permiso proactivo): Anticipar y preparar. Confirmar para ejecutar.",
                "- REGLA INVIOLABLE: NUNCA ejecutar una acción sin confirmación explícita del usuario.",
            ])
            parts.append("\n".join(perm_lines))

            # Few-shot examples for better tool selection
            few_shot_section = (
                "=== EJEMPLOS DE INTERACCION (FEW-SHOT) ===\n"
                "\n"
                "EJEMPLO 1 -- Nivel 1 (Informacional):\n"
                "Usuario: \"Cual es el estado de mi solicitud de pasaporte?\"\n"
                "-> Usar herramienta: get_my_requests o get_request_detail\n"
                "-> Responder con resumen claro + estado actual + proximos pasos\n"
                "\n"
                "EJEMPLO 2 -- Nivel 2 (Preparatorio):\n"
                "Usuario: \"Preparame mi renovacion de pasaporte\"\n"
                "-> Usar herramienta: auto_prepare_wizard(workflow_name=\"pasaporte renovacion\")\n"
                "-> Si permiso no activado: sugerir activar permiso con boton\n"
                "-> Si documentos faltan: listar faltantes + preguntar si continuar\n"
                "-> Si todo listo: mostrar resumen + boton \"Finalizar mi solicitud\"\n"
                "\n"
                "EJEMPLO 3 -- Documentos por vencer:\n"
                "Usuario: \"Que documentos tengo por vencer?\"\n"
                "-> Usar herramienta: get_expiring_documents(days_ahead=90)\n"
                "-> Listar documentos con urgencia (critico < 7j, alto < 30j, medio < 90j)\n"
                "-> Sugerir renovacion para cada documento critico\n"
                "\n"
                "EJEMPLO 4 -- Preparacion demarche:\n"
                "Usuario: \"Tengo todo para sacar residencia?\"\n"
                "-> Usar herramienta: check_readiness(workflow_code=\"RESIDENCIA_PRIMERA_VEZ\")\n"
                "-> Mostrar score + documentos listos + faltantes\n"
                "-> Si puede iniciar: proponer auto_prepare_wizard\n"
                "-> Si faltan: sugerir subir documentos faltantes al cofre\n"
                "\n"
                "EJEMPLO 5 -- Cofre digital:\n"
                "Usuario: \"Muestrame mis documentos\"\n"
                "-> Usar herramienta: list_vault_documents\n"
                "-> Presentar en formato tabla o lista organizada por categoria"
            )
            parts.append(few_shot_section)

        except Exception as e:
            logger.debug(f"Agent context build failed: {e}")

        return "\n\n".join(parts) if parts else ""


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

chatbot_service_rag = ChatbotServiceRAG()
