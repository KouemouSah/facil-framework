"""
Redis-backed Conversation Memory for LLM Analyst Agents.

Maintains a rolling window of conversation turns per session.
Enables slot inheritance (fill missing parameters from prior context)
and conversational continuity for follow-up questions.

Uses the existing app.core.cache infrastructure (HybridCache with Redis + in-memory fallback).
"""

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger


# ──────────────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ConversationTurn:
    """One Q&A exchange stored in conversation history."""
    question:         str
    intent:           str
    entity_codes:     List[str]
    agent_name:       Optional[str]
    time_period_days: Optional[int]
    metric:           Optional[str]
    tools_used:       List[str]
    key_findings:     str          # First ~200 chars of the LLM answer
    timestamp:        float = field(default_factory=time.time)


# ──────────────────────────────────────────────────────────────────────────────
# ConversationMemory
# ──────────────────────────────────────────────────────────────────────────────

class ConversationMemory:
    """
    Sliding-window conversation history stored in Redis (HybridCache).

    Key format : "conv:{safe_session_id}"
    Value       : JSON list[ConversationTurn] — max MAX_TURNS entries
    TTL         : SESSION_TTL_SECONDS (refreshed on each new turn)

    Slot inheritance strategy:
      - Only inherited when current question has low confidence (< 0.6)
      - Most recent turns win (oldest → newest iteration)
      - Entity codes, time period, metric, agent name are inherited independently
    """

    MAX_TURNS           = 6
    SESSION_TTL_SECONDS = 1800   # 30-minute idle TTL
    KEY_PREFIX          = "conv:"

    # ── Key helpers ───────────────────────────────────────────────────────────

    def _make_key(self, session_id: str) -> str:
        safe = session_id[:64].replace("/", "").replace(":", "").replace(" ", "")
        return f"{self.KEY_PREFIX}{safe}"

    # ── Write ─────────────────────────────────────────────────────────────────

    async def add_turn(self, session_id: str, turn: ConversationTurn) -> None:
        """Append a turn to the session, maintaining the rolling window."""
        try:
            from app.core.cache import get_cache
            cache = get_cache()
            key = self._make_key(session_id)

            existing = await cache.get(key) or []
            if not isinstance(existing, list):
                existing = []

            existing.append(asdict(turn))
            existing = existing[-self.MAX_TURNS:]   # rolling window

            await cache.set(key, existing, ttl=self.SESSION_TTL_SECONDS)
        except Exception as exc:
            logger.warning(f"ConversationMemory.add_turn failed (session={session_id}): {exc}")

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_turns(self, session_id: str) -> List[ConversationTurn]:
        """Return ordered list of turns (oldest first)."""
        try:
            from app.core.cache import get_cache
            cache = get_cache()
            raw = await cache.get(self._make_key(session_id)) or []
            if not isinstance(raw, list):
                return []
            return [ConversationTurn(**t) for t in raw if isinstance(t, dict)]
        except Exception as exc:
            logger.warning(f"ConversationMemory.get_turns failed (session={session_id}): {exc}")
            return []

    async def get_accumulated_context(self, session_id: str) -> Dict[str, Any]:
        """
        Build accumulated context from recent turns (oldest → newest, newest wins).

        Returns a flat dict usable for slot inheritance and prompt enrichment.
        """
        turns = await self.get_turns(session_id)
        if not turns:
            return {}

        ctx: Dict[str, Any] = {}
        for turn in turns:
            if turn.entity_codes:
                ctx["entity_codes"] = turn.entity_codes
            if turn.agent_name:
                ctx["agent_name"] = turn.agent_name
            if turn.time_period_days is not None:
                ctx["time_period_days"] = turn.time_period_days
            if turn.metric:
                ctx["metric"] = turn.metric
            if turn.intent and turn.intent != "general":
                ctx["intent"] = turn.intent
            if turn.tools_used:
                ctx["last_tools"] = turn.tools_used

        # Key findings from the most recent turn
        if turns:
            ctx["key_findings"] = turns[-1].key_findings

        return ctx

    async def resolve_missing_slots(
        self,
        session_id: str,
        slots,   # ExtractedSlots — avoid circular import by typing loosely
    ):
        """
        Fill missing slots from conversation history.

        Only activates when current question has low confidence (< 0.6),
        indicating it's likely a follow-up ("et pour CNEDOGE?", "y los rechazos?").

        Examples:
          Q1: "ingresos de CNEDOGE esta semana"  → entity=CNEDOGE, days=7
          Q2: "y los rechazos?"                  → inherits entity=CNEDOGE, days=7
        """
        if slots.confidence >= 0.6:
            return slots  # high-confidence = self-contained question, don't inherit

        ctx = await self.get_accumulated_context(session_id)
        if not ctx:
            return slots

        from app.modules.shared.services.nlp_preprocessor import IntentCategory

        if not slots.entity_codes and ctx.get("entity_codes"):
            slots.entity_codes = ctx["entity_codes"]
        if slots.time_period_days is None and ctx.get("time_period_days") is not None:
            slots.time_period_days = ctx["time_period_days"]
        if not slots.metric and ctx.get("metric"):
            slots.metric = ctx["metric"]
        if not slots.agent_name and ctx.get("agent_name"):
            slots.agent_name = ctx["agent_name"]
        # Inherit intent only if current is GENERAL
        if slots.intent == IntentCategory.GENERAL and ctx.get("intent"):
            try:
                slots.intent = IntentCategory(ctx["intent"])
            except ValueError:
                pass

        return slots


# ── Module-level singleton ────────────────────────────────────────────────────
conversation_memory = ConversationMemory()
