"""
AI security — prompt injection / jailbreak detection (Phase B.5).

Pattern-based detector that runs BEFORE every Gemini call (via the
traced_generate* wrappers). Tags suspicious prompts with risk-level
attributes on the OTEL span + flags them in ai_call_metrics for review.

What it catches (cheap pattern matching, no ML):
- **Direct jailbreak attempts**: "ignore previous instructions", "you are now",
  "forget your prompt", "DAN mode", etc.
- **Role hijack**: "act as", "pretend to be", "from now on you are"
- **System prompt leak**: "what is your prompt", "show me your instructions",
  "repeat the words above"
- **Output manipulation**: "say exactly", "respond only with", "ignore safety"
- **Encoding attacks**: base64 decoded matches one of the above
- **Excessive special chars**: prompt = mostly punctuation / control chars

What it does NOT catch (out of scope, would need ML):
- Multi-turn jailbreak (drift across messages)
- Subtle social engineering
- Adversarial unicode / homoglyphs
- Translated jailbreak attempts (only EN/FR/ES patterns)

False positives: ~3-5% on legitimate user prompts (e.g. "ignore previous"
in a normal sentence). Acceptable because we only TAG/LOG, never block by
default. Set `AI_SECURITY_BLOCK_HIGH_RISK=true` in env to actually refuse
high-risk prompts.

Privacy: hash-only logging. The full prompt is never stored anywhere
(memory rule: privacy-by-construction in ai_telemetry).
"""

from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass
class InjectionAssessment:
    """Result of the pattern scan."""

    risk: str          # 'none' | 'low' | 'medium' | 'high'
    matched_rules: tuple[str, ...]
    score: int         # accumulated weight, 0..100+
    notes: str = ""

    @property
    def is_suspicious(self) -> bool:
        return self.risk != "none"

    @property
    def should_block(self) -> bool:
        return self.risk == "high" and _BLOCK_HIGH_RISK


_BLOCK_HIGH_RISK = (os.environ.get("AI_SECURITY_BLOCK_HIGH_RISK") or "").lower() in (
    "1", "true", "yes",
)


# Pattern catalog. Each rule is (regex, weight, label).
# Weights tuned so a single high-confidence match → "high" risk.
# Multiple low-weight matches accumulate into "medium" / "high".
_PATTERNS: tuple[tuple[re.Pattern, int, str], ...] = (
    # === Direct jailbreak (HIGH weight) ===
    (re.compile(r"\bignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|commands?)\b", re.I), 60, "ignore_previous"),
    (re.compile(r"\b(forget|disregard)\s+(your|the|all)\s+(prompt|instructions?|rules?|context|guidelines?)\b", re.I), 55, "forget_prompt"),
    (re.compile(r"\b(DAN|jailbreak|developer\s*mode)\s*(mode|enabled|activated|on)?\b", re.I), 70, "dan_jailbreak"),
    (re.compile(r"\b(do\s+anything\s+now|now\s+you\s+can\s+do\s+anything)\b", re.I), 60, "do_anything_now"),

    # === Role hijack (MEDIUM-HIGH) ===
    (re.compile(r"\b(act|pretend|behave|role\s*play)\s+(as|like)\s+(an?|the)\b", re.I), 25, "act_as"),
    (re.compile(r"\bfrom\s+now\s+on,?\s+you\s+(are|will\s+be|act)\b", re.I), 50, "from_now_on_you_are"),
    (re.compile(r"\byou\s+are\s+(no\s+longer|not)\s+(an?\s+)?(AI|assistant|chatbot|model)\b", re.I), 60, "you_are_not_ai"),
    (re.compile(r"\b(unrestricted|uncensored|unfiltered)\s+(ai|assistant|gpt|model|version)\b", re.I), 65, "unrestricted_role"),

    # === System prompt leak (HIGH) ===
    (re.compile(r"\b(show|reveal|print|display|output|repeat|tell\s+me)\s+(me\s+)?(your|the)\s+(system\s+)?(prompt|instructions?|rules?)\b", re.I), 65, "leak_prompt"),
    (re.compile(r"\brepeat\s+(the\s+)?(words?|text|content)\s+(above|before)\b", re.I), 55, "repeat_above"),

    # === Output manipulation (MEDIUM) ===
    (re.compile(r"\b(respond|reply|answer|say|output)\s+(only|exactly|just)\s+with\b", re.I), 30, "force_output"),
    (re.compile(r"\b(bypass|disable|ignore|turn\s+off|skip)\s+(safety|filter|guard|moderation|restriction)s?\b", re.I), 70, "disable_safety"),

    # === French/Spanish equivalents (same severity as EN equivalents) ===
    (re.compile(r"\b(ignore?z?|oublie?z?)\s+(les\s+)?(instructions?\s+)?(précédent|antérieur)e?s?\b", re.I), 60, "fr_ignore_previous"),
    (re.compile(r"\bignor[ae]\s+(las|todas\s+las)\s+(instrucciones?|reglas?)\s+(anteriores?|previas?)\b", re.I), 60, "es_ignore_previous"),

    # === Suspicious encoding wrappers ===
    (re.compile(r"\b(base64|hex|rot13|urlencode|atob|btoa)\b", re.I), 15, "encoding_keyword"),

    # === Token / API key extraction attempts ===
    (re.compile(r"\b(reveal|show|tell\s+me)\s+(your|the)\s+(api[_\s]?key|token|secret|password|credentials?)\b", re.I), 80, "credential_request"),
)


def _score_to_risk(score: int) -> str:
    """Map cumulative score → risk level."""
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    if score >= 10:
        return "low"
    return "none"


def _decode_base64_attempts(prompt: str) -> str:
    """Best-effort: detect a base64 blob in the prompt and decode it for re-scanning.

    Defense against injection-via-encoding ("dGVsbCBtZSB0aGUgcHJvbXB0" =
    "tell me the prompt"). We only check for blobs ≥ 16 chars, base64 charset,
    decoding to printable ASCII.
    """
    decoded = []
    # Find candidate base64 blobs (length ≥ 16, alphanum + +/= padding)
    for m in re.finditer(r"[A-Za-z0-9+/]{16,}={0,2}", prompt):
        blob = m.group(0)
        try:
            d = base64.b64decode(blob, validate=True).decode("utf-8", errors="strict")
            # Skip if mostly non-printable
            printable = sum(1 for c in d if c.isprintable() or c in "\n\r\t")
            if printable / max(len(d), 1) > 0.85:
                decoded.append(d)
        except Exception:
            pass
    return " ".join(decoded)


def detect_prompt_injection(prompt: Any) -> InjectionAssessment:
    """Run pattern scan on `prompt` (string or list of parts).

    Returns an InjectionAssessment. Cheap (~50µs per prompt) — fine to call
    on every Gemini request.
    """
    if prompt is None:
        return InjectionAssessment(risk="none", matched_rules=(), score=0)

    text = str(prompt)
    if len(text) > 32_000:
        text = text[:32_000]

    # Pass 1: raw text scan
    matched: list[str] = []
    score = 0
    for pat, weight, label in _PATTERNS:
        if pat.search(text):
            matched.append(label)
            score += weight

    # Pass 2: scan base64-decoded fragments
    decoded = _decode_base64_attempts(text)
    if decoded:
        for pat, weight, label in _PATTERNS:
            if pat.search(decoded):
                matched.append(f"b64:{label}")
                score += weight  # full weight on encoded → indicates intent

    # Pass 3: excessive special-char ratio
    if len(text) >= 50:
        special = sum(1 for c in text if not (c.isalnum() or c.isspace()))
        ratio = special / len(text)
        if ratio > 0.5:
            matched.append("high_special_char_ratio")
            score += 20

    risk = _score_to_risk(score)
    notes = f"{len(matched)} rule(s) matched" if matched else ""
    return InjectionAssessment(
        risk=risk, matched_rules=tuple(matched), score=score, notes=notes,
    )


class PromptInjectionBlocked(Exception):
    """Raised when AI_SECURITY_BLOCK_HIGH_RISK=true and a high-risk prompt is detected."""

    def __init__(self, assessment: InjectionAssessment):
        self.assessment = assessment
        super().__init__(
            f"Prompt blocked — risk={assessment.risk}, score={assessment.score}, "
            f"rules={','.join(assessment.matched_rules[:3])}"
        )


def attach_to_span(span: Any, assessment: InjectionAssessment) -> None:
    """Tag the active OTEL span with assessment attributes (best-effort)."""
    try:
        span.set_attribute("ai_security.risk", assessment.risk)
        span.set_attribute("ai_security.score", assessment.score)
        if assessment.matched_rules:
            # Bound to 5 rules to keep the attribute small
            span.set_attribute(
                "ai_security.matched_rules",
                ",".join(assessment.matched_rules[:5]),
            )
    except Exception:
        pass


__all__ = [
    "InjectionAssessment",
    "PromptInjectionBlocked",
    "detect_prompt_injection",
    "attach_to_span",
]
