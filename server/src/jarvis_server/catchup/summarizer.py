"""Summarizer - uses Claude to synthesize context into summaries."""

import logging
from datetime import datetime

import anthropic

from jarvis_server.config import get_settings

logger = logging.getLogger(__name__)


class Summarizer:
    """Summarizes gathered context using Claude API."""

    def __init__(self):
        settings = get_settings()
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def summarize(self, context, style: str = "detailed") -> str:
        """Generate a summary from gathered context."""
        if not context.items:
            return f"No relevant information found for '{context.topic}' in the specified timeframe."

        # Build context document
        context_doc = self._build_context_document(context)

        # Choose prompt based on style
        if style == "summary":
            prompt = self._summary_prompt(context.topic, context_doc)
        else:
            prompt = self._detailed_prompt(context.topic, context_doc)

        try:
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return f"Error generating summary: {e}"

    def _build_context_document(self, context) -> str:
        """Build a document from context items."""
        lines = []
        lines.append(f"## Context for: {context.topic}")
        if context.timeframe_start and context.timeframe_end:
            lines.append(f"Timeframe: {context.timeframe_start:%Y-%m-%d} to {context.timeframe_end:%Y-%m-%d}")
        lines.append(f"Sources: {', '.join(f'{k}({v})' for k, v in context.total_sources.items())}")
        lines.append("")

        for item in context.items:
            lines.append(f"### [{item.source.upper()}] {item.timestamp:%Y-%m-%d %H:%M}")
            content = item.content[:1000] if item.content else "(no content)"
            lines.append(content)
            lines.append("")

        return "\n".join(lines)

    def _summary_prompt(self, topic: str, context_doc: str) -> str:
        return f"""Based on the following context about "{topic}", provide a brief summary (2-3 paragraphs) covering:
1. What has been happening with this topic
2. Key decisions or outcomes
3. Any open items or next steps

Context:
{context_doc}

Provide a concise, actionable summary."""

    def _detailed_prompt(self, topic: str, context_doc: str) -> str:
        return f"""Based on the following context about "{topic}", provide a detailed catch-up briefing covering:

1. **Timeline**: What happened chronologically
2. **Key Points**: Important decisions, outcomes, or changes
3. **People Involved**: Who has been involved and their roles
4. **Current Status**: Where things stand now
5. **Open Items**: Pending tasks or unresolved questions
6. **Recommendations**: Suggested next steps

Context:
{context_doc}

Format as a clear briefing document that would help someone quickly get up to speed."""

    async def generate_meeting_brief(self, context, meeting_summary: str, attendees: list[str]) -> str:
        """Generate a pre-meeting briefing."""
        if not context.items:
            return f"No prior context found for meeting: {meeting_summary}"

        context_doc = self._build_context_document(context)

        prompt = f"""You are preparing a briefing for an upcoming meeting.

Meeting: {meeting_summary}
Attendees: {', '.join(attendees) if attendees else 'Not specified'}

Based on the following historical context, prepare a pre-meeting brief covering:

1. **Background**: What you should know before this meeting
2. **Recent Activity**: Relevant recent interactions or decisions
3. **Key People**: What you know about the attendees from past interactions
4. **Suggested Topics**: Things you might want to discuss based on history
5. **Open Questions**: Unresolved items from previous interactions

Context:
{context_doc}

Keep the brief focused and actionable."""

        try:
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return f"Error generating meeting brief: {e}"
