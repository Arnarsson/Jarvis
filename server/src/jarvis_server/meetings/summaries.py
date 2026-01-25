"""Meeting summarization with action item extraction using LLM."""

import json
import os
from dataclasses import dataclass
from typing import Optional

import anthropic
import structlog

logger = structlog.get_logger()


@dataclass
class ActionItem:
    """An action item extracted from meeting."""

    task: str
    owner: Optional[str]
    due_date: Optional[str]
    priority: str  # high, medium, low


@dataclass
class MeetingSummary:
    """Structured meeting summary."""

    summary: str
    action_items: list[ActionItem]
    key_decisions: list[str]
    follow_ups: list[str]


# LLM client singleton
_client: Optional[anthropic.AsyncAnthropic] = None


def get_llm_client() -> anthropic.AsyncAnthropic:
    """Get or create Anthropic client."""
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        _client = anthropic.AsyncAnthropic(api_key=api_key)
    return _client


SUMMARY_PROMPT = """Analyze this meeting transcript and extract a structured summary.

<transcript>
{transcript}
</transcript>

For each action item you identify, determine:
- Task description (what needs to be done)
- Assigned owner (who is responsible, if mentioned - use name or "Unassigned")
- Due date (if specified, otherwise null)
- Priority (high/medium/low based on urgency cues in discussion)

Return your analysis as JSON in this exact format:
{{
  "summary": "2-3 sentence meeting summary focusing on key outcomes",
  "action_items": [
    {{
      "task": "string",
      "owner": "string or null",
      "due_date": "string or null",
      "priority": "high|medium|low"
    }}
  ],
  "key_decisions": ["string"],
  "follow_ups": ["string"]
}}

Focus on:
- Concrete, actionable items (not general discussion points)
- Decisions that were actually made (not just discussed)
- Topics requiring follow-up in future meetings

Return ONLY valid JSON, no additional text."""


async def generate_meeting_summary(
    transcript: str, meeting_title: Optional[str] = None
) -> MeetingSummary:
    """
    Generate a structured summary from meeting transcript.

    Args:
        transcript: Full meeting transcript text
        meeting_title: Optional title for context

    Returns:
        MeetingSummary with action items and key decisions
    """
    logger.info("summary_generation_started", transcript_length=len(transcript))

    # Truncate very long transcripts (keep first and last portions)
    max_chars = 100000  # ~25k tokens
    if len(transcript) > max_chars:
        half = max_chars // 2
        transcript = (
            transcript[:half]
            + "\n\n[... middle portion omitted for length ...]\n\n"
            + transcript[-half:]
        )
        logger.info(
            "transcript_truncated", original_length=len(transcript), truncated_to=max_chars
        )

    prompt = SUMMARY_PROMPT.format(transcript=transcript)

    if meeting_title:
        prompt = f"Meeting: {meeting_title}\n\n{prompt}"

    try:
        client = get_llm_client()
        message = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text

        # Parse JSON response
        # Handle potential markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Remove first and last lines (```json and ```)
            response_text = "\n".join(lines[1:-1])

        data = json.loads(response_text)

        action_items = [
            ActionItem(
                task=item["task"],
                owner=item.get("owner"),
                due_date=item.get("due_date"),
                priority=item.get("priority", "medium"),
            )
            for item in data.get("action_items", [])
        ]

        result = MeetingSummary(
            summary=data.get("summary", ""),
            action_items=action_items,
            key_decisions=data.get("key_decisions", []),
            follow_ups=data.get("follow_ups", []),
        )

        logger.info(
            "summary_generation_completed",
            summary_length=len(result.summary),
            action_item_count=len(action_items),
            decision_count=len(result.key_decisions),
        )

        return result

    except json.JSONDecodeError as e:
        logger.error(
            "summary_json_parse_failed", error=str(e), response=response_text[:500]
        )
        raise ValueError(f"Failed to parse LLM response as JSON: {e}")
    except Exception as e:
        logger.error("summary_generation_failed", error=str(e))
        raise


def summary_to_dict(summary: MeetingSummary) -> dict:
    """Convert MeetingSummary to JSON-serializable dict."""
    return {
        "summary": summary.summary,
        "action_items": [
            {
                "task": item.task,
                "owner": item.owner,
                "due_date": item.due_date,
                "priority": item.priority,
            }
            for item in summary.action_items
        ],
        "key_decisions": summary.key_decisions,
        "follow_ups": summary.follow_ups,
    }
