"""AI synthesis for search results.

This module is intentionally defensive:
- If no LLM credentials are configured, it falls back to heuristic synthesis.
- If the LLM returns invalid JSON, it falls back gracefully.

The goal is to provide a top-of-results summary + extracted entities (dates/people/actions)
with a confidence score.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any

from ..config import get_settings

logger = logging.getLogger(__name__)


def _safe_json_loads(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except Exception:
        return None


def _extract_json_block(text: str) -> str | None:
    """Try to extract a JSON object from an LLM response."""
    # Common: model wraps JSON in markdown fences
    fence = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if fence:
        return fence.group(1)

    # Otherwise, grab first '{' ... last '}'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return None


def _heuristic_synthesis(query: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Fallback synthesis when no LLM is available."""
    # Evidence items expected: {source, timestamp/date, snippet/title/subject}
    dates: list[str] = []
    people: list[str] = []
    actions: list[str] = []

    # Simple person heuristic: capitalized tokens from query
    for token in re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", query):
        if token not in people:
            people.append(token)

    # Date heuristic: YYYY-MM-DD in snippets
    for ev in evidence:
        snippet = (ev.get("snippet") or "")
        for d in re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", snippet):
            if d not in dates:
                dates.append(d)

    # Action heuristic: look for TODO-like patterns
    action_patterns = [
        r"\bTODO\b[:\-]?\s*(.{0,80})",
        r"\bFollow up\b[:\-]?\s*(.{0,80})",
        r"\bNext\s+step\b[:\-]?\s*(.{0,80})",
        r"\bI\s+will\b\s+(.{0,80})",
    ]
    for ev in evidence:
        snippet = (ev.get("snippet") or "")
        for pat in action_patterns:
            m = re.search(pat, snippet, re.IGNORECASE)
            if m:
                act = m.group(1).strip().strip(". ")
                if act and act not in actions:
                    actions.append(act)

    # Summary: stitch top 1-2 snippets
    top_bits = []
    for ev in evidence[:2]:
        label = ev.get("title") or ev.get("subject") or ev.get("source")
        snip = (ev.get("snippet") or "").strip().replace("\n", " ")
        if snip:
            top_bits.append(f"[{label}] {snip[:180]}")

    summary = (
        f"Search results for '{query}'. "
        + (" ".join(top_bits) if top_bits else "No additional context available.")
    )

    return {
        "summary": summary,
        "confidence": 0.35 if evidence else 0.1,
        "key_dates": dates[:5],
        "key_people": people[:10],
        "action_items": actions[:10],
    }


async def generate_search_synthesis(query: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate synthesis JSON.

    evidence: list of compact items (already curated) to keep prompts small.
    """
    settings = get_settings()

    # If no paid providers configured, fall back.
    if not settings.anthropic_api_key and not settings.openai_api_key:
        return _heuristic_synthesis(query, evidence)

    prompt = {
        "query": query,
        "instructions": [
            "You are Jarvis, an executive assistant.",
            "Given the user's search query and evidence snippets from their personal memory, produce a concise synthesis.",
            "Return STRICT JSON (no markdown) matching this schema:",
            "{summary: string, confidence: number 0..1, key_dates: string[], key_people: string[], action_items: string[]}",
            "If unsure, lower confidence.",
            "Key dates must be ISO YYYY-MM-DD when possible.",
            "Action items should be imperative (e.g. 'Send the pricing doc').",
        ],
        "evidence": evidence[:20],
        "now": datetime.utcnow().isoformat() + "Z",
    }

    # Prefer Anthropic (used elsewhere in repo) if configured.
    if settings.anthropic_api_key:
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            resp = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                temperature=0.2,
                messages=[
                    {
                        "role": "user",
                        "content": "Return STRICT JSON only.\n" + json.dumps(prompt, ensure_ascii=False),
                    }
                ],
            )
            text = "".join([b.text for b in resp.content if getattr(b, "text", None)])
            parsed = _safe_json_loads(text) or _safe_json_loads(_extract_json_block(text) or "")
            if isinstance(parsed, dict) and "summary" in parsed:
                return parsed
        except Exception:
            logger.exception("search_synthesis_anthropic_failed")

    if settings.openai_api_key:
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are Jarvis. Return STRICT JSON only; no markdown.",
                    },
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
                temperature=0.2,
                max_tokens=500,
                response_format={"type": "json_object"},
            )
            text = resp.choices[0].message.content or ""
            parsed = _safe_json_loads(text) or _safe_json_loads(_extract_json_block(text) or "")
            if isinstance(parsed, dict) and "summary" in parsed:
                return parsed
        except Exception:
            logger.exception("search_synthesis_openai_failed")

    return _heuristic_synthesis(query, evidence)
