"""LLM-based behavioral pattern detector.

Replaces the old keyword-counting approach with Anthropic Claude analysis
of conversations, screen captures, and activity timestamps to detect
REAL behavioral patterns like:
  - "checks LinkedIn at 11am daily"
  - "context-switches every 45min"
  - "peak productivity 11:00-13:00"
  - "forgets Thursday follow-ups"

Run with: python -m jarvis_server.patterns.llm_detector
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import anthropic
import structlog
from sqlalchemy import select, text, delete
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.config import get_settings
from jarvis_server.db.session import AsyncSessionLocal
from jarvis_server.db.models import DetectedPattern

logger = structlog.get_logger(__name__)

# Pattern types for the new behavioral analysis
BEHAVIORAL_PATTERN_TYPES = [
    "time_habit",           # Regular time-based behaviors
    "context_switching",    # How/when context switches happen
    "productivity_window",  # Peak focus / productivity times
    "recurring_theme",      # Genuine recurring topics/interests
    "communication_pattern",# How and when they communicate
    "forgotten_followup",   # Things that keep getting dropped
    "work_rhythm",          # Daily/weekly work cadence
    "tool_preference",      # Tool and platform usage patterns
]

ANALYSIS_PROMPT = """You are analyzing behavioral data for a personal AI assistant (Jarvis) that observes its user's digital activity. Your job is to find REAL, actionable behavioral patterns.

## Data Sources

### Recent Conversation Topics & Titles (AI chat sessions)
{conversation_data}

### Screen Activity Timeline (what was on screen and when)
{capture_data}

### Conversation Content Samples
{content_samples}

## Your Task

Analyze this data to identify genuine behavioral patterns. Look for:

1. **Time Habits** — Regular behaviors at specific times (e.g., "checks email first thing at 9am", "browses Reddit after lunch")
2. **Context Switching** — How often and when context switches happen (e.g., "switches between coding and chat every 30min")
3. **Productivity Windows** — When deep work vs. shallow work happens (e.g., "peak coding productivity 10:00-13:00")
4. **Recurring Themes** — Genuine topics that keep coming up across conversations (not code tokens, but real interests/concerns)
5. **Communication Patterns** — When and how communication happens
6. **Forgotten Follow-ups** — Things mentioned multiple times but seemingly never resolved
7. **Work Rhythm** — Daily or weekly cadence patterns
8. **Tool Preferences** — Which tools/platforms are used for what

## Output Format

Return a JSON array of patterns. Each pattern must be:
```json
{{
  "pattern_type": "time_habit|context_switching|productivity_window|recurring_theme|communication_pattern|forgotten_followup|work_rhythm|tool_preference",
  "pattern_key": "short identifier (3-6 words)",
  "description": "Human-readable description of the pattern with specific details (times, frequencies, etc.)",
  "confidence": 0.0-1.0,
  "suggested_action": "What Jarvis could do with this insight",
  "evidence_summary": "Brief summary of what data supports this pattern"
}}
```

## Rules
- Only include patterns you're genuinely confident about (confidence >= 0.5)
- Be SPECIFIC — "checks email at 9am" not "uses email"
- Include actual times, frequencies, and durations when possible
- Maximum 20 patterns
- Do NOT identify code tokens, programming keywords, or generic words as patterns
- Focus on the HUMAN behind the data — their habits, rhythms, and blind spots
- If there's insufficient data for a category, skip it rather than guessing
- Return ONLY the JSON array, no other text"""


async def gather_conversation_data(session: AsyncSession, days: int = 30) -> tuple[str, str]:
    """Gather conversation titles, topics, and content samples from the database."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get conversation titles and metadata
    result = await session.execute(
        text("""
            SELECT id, title, source, message_count, conversation_date 
            FROM conversations 
            WHERE conversation_date > :cutoff OR conversation_date IS NULL
            ORDER BY conversation_date DESC NULLS LAST
            LIMIT 100
        """),
        {"cutoff": cutoff}
    )
    rows = result.fetchall()
    
    conversation_lines = []
    for row in rows:
        date_str = row[4].strftime("%Y-%m-%d %H:%M") if row[4] else "unknown"
        conversation_lines.append(
            f"- [{date_str}] \"{row[1]}\" ({row[2]}, {row[3]} messages)"
        )
    
    conversation_data = "\n".join(conversation_lines) if conversation_lines else "No recent conversations found."
    
    # Get content samples — first 500 chars of recent conversations
    result = await session.execute(
        text("""
            SELECT title, LEFT(full_text, 1500), conversation_date
            FROM conversations 
            WHERE (conversation_date > :cutoff OR conversation_date IS NULL)
              AND message_count > 3
            ORDER BY conversation_date DESC NULLS LAST
            LIMIT 15
        """),
        {"cutoff": cutoff}
    )
    content_rows = result.fetchall()
    
    content_samples = []
    for row in content_rows:
        date_str = row[2].strftime("%Y-%m-%d") if row[2] else "unknown"
        # Truncate intelligently
        text_preview = row[1][:1200] if row[1] else ""
        content_samples.append(
            f"### {row[0]} ({date_str})\n{text_preview}\n"
        )
    
    content_data = "\n---\n".join(content_samples) if content_samples else "No conversation content available."
    
    return conversation_data, content_data


async def gather_capture_data(session: AsyncSession, days: int = 7) -> str:
    """Gather screen capture timeline data."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get capture timestamps to analyze activity patterns
    result = await session.execute(
        text("""
            SELECT timestamp, monitor_index, 
                   LEFT(ocr_text, 300) as ocr_preview
            FROM captures 
            WHERE timestamp > :cutoff
              AND ocr_text IS NOT NULL 
              AND LENGTH(ocr_text) > 50
            ORDER BY timestamp DESC
            LIMIT 200
        """),
        {"cutoff": cutoff}
    )
    rows = result.fetchall()
    
    if not rows:
        # Try older data
        result = await session.execute(
            text("""
                SELECT timestamp, monitor_index,
                       LEFT(ocr_text, 300) as ocr_preview
                FROM captures
                WHERE ocr_text IS NOT NULL 
                  AND LENGTH(ocr_text) > 50
                ORDER BY timestamp DESC
                LIMIT 200
            """)
        )
        rows = result.fetchall()
    
    if not rows:
        return "No screen capture data available."
    
    # Group by day and hour for timeline analysis
    timeline = {}
    for row in rows:
        ts = row[0]
        day_key = ts.strftime("%Y-%m-%d (%A)")
        hour_key = ts.strftime("%H:%M")
        
        if day_key not in timeline:
            timeline[day_key] = []
        
        # Clean OCR text — remove garbage
        ocr = (row[2] or "").strip()
        # Only include if it has some readable content
        readable_chars = sum(1 for c in ocr if c.isalpha())
        if readable_chars > len(ocr) * 0.3:  # At least 30% alphabetic
            timeline[day_key].append(f"  {hour_key} — {ocr[:150]}")
        else:
            timeline[day_key].append(f"  {hour_key} — [screen capture, monitor {row[1]}]")
    
    lines = []
    for day, entries in sorted(timeline.items()):
        lines.append(f"\n**{day}**")
        for entry in entries[:20]:  # Limit per day
            lines.append(entry)
    
    return "\n".join(lines) if lines else "No readable screen capture data."


async def gather_activity_stats(session: AsyncSession) -> str:
    """Gather activity statistics — hourly distribution, etc."""
    # Capture distribution by hour of day
    result = await session.execute(
        text("""
            SELECT EXTRACT(HOUR FROM timestamp) as hour,
                   COUNT(*) as capture_count
            FROM captures
            WHERE timestamp > NOW() - INTERVAL '30 days'
            GROUP BY hour
            ORDER BY hour
        """)
    )
    hourly = result.fetchall()
    
    if hourly:
        stats = "Activity by hour of day (last 30 days):\n"
        for row in hourly:
            hour = int(row[0])
            count = row[1]
            bar = "█" * min(count // 2, 30)
            stats += f"  {hour:02d}:00 — {count} captures {bar}\n"
        return stats
    
    return ""


async def analyze_with_llm(conversation_data: str, capture_data: str, content_samples: str) -> list[dict]:
    """Send data to Anthropic Claude for behavioral pattern analysis."""
    settings = get_settings()
    
    api_key = settings.anthropic_api_key
    if not api_key:
        logger.error("No Anthropic API key configured (JARVIS_ANTHROPIC_API_KEY)")
        return []
    
    client = anthropic.Anthropic(api_key=api_key)
    
    prompt = ANALYSIS_PROMPT.format(
        conversation_data=conversation_data[:8000],  # Limit to avoid token overflow
        capture_data=capture_data[:6000],
        content_samples=content_samples[:12000],
    )
    
    logger.info("Sending data to Claude for pattern analysis",
                conv_len=len(conversation_data),
                capture_len=len(capture_data),
                content_len=len(content_samples))
    
    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )
        
        response_text = message.content[0].text.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        if response_text.startswith("```"):
            # Strip markdown code fences
            lines = response_text.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```"):
                    in_block = not in_block
                    continue
                if in_block or not line.startswith("```"):
                    json_lines.append(line)
            response_text = "\n".join(json_lines).strip()
        
        # Parse JSON
        patterns = json.loads(response_text)
        
        if not isinstance(patterns, list):
            logger.error("LLM response is not a JSON array", response=response_text[:200])
            return []
        
        logger.info("LLM analysis complete", pattern_count=len(patterns))
        return patterns
        
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM response as JSON", error=str(e), response=response_text[:500])
        return []
    except anthropic.APIError as e:
        logger.error("Anthropic API error", error=str(e))
        return []
    except Exception as e:
        logger.error("Unexpected error in LLM analysis", error=str(e))
        return []


async def store_patterns(session: AsyncSession, llm_patterns: list[dict]) -> list[DetectedPattern]:
    """Store LLM-extracted patterns in the database, replacing old ones."""
    now = datetime.now(timezone.utc)
    
    # Dismiss all old active patterns
    result = await session.execute(
        select(DetectedPattern).where(DetectedPattern.status == "active")
    )
    old_patterns = result.scalars().all()
    dismissed_count = 0
    for old in old_patterns:
        old.status = "dismissed"
        dismissed_count += 1
    
    logger.info("Dismissed old patterns", count=dismissed_count)
    
    # Insert new patterns
    new_patterns = []
    for p in llm_patterns:
        confidence = p.get("confidence", 0.5)
        if confidence < 0.4:
            continue  # Skip low-confidence patterns
        
        pattern = DetectedPattern(
            id=str(uuid4()),
            pattern_type=p.get("pattern_type", "recurring_theme"),
            pattern_key=p.get("pattern_key", "unknown"),
            description=p.get("description", ""),
            frequency=max(1, int(confidence * 10)),  # Map confidence to frequency
            first_seen=now,
            last_seen=now,
            suggested_action=p.get("suggested_action"),
            status="active",
        )
        # Store evidence in conversation_ids as a JSON hack
        evidence = p.get("evidence_summary", "")
        pattern.conversation_ids = [evidence] if evidence else []
        
        session.add(pattern)
        new_patterns.append(pattern)
    
    await session.commit()
    logger.info("Stored new patterns", count=len(new_patterns))
    
    return new_patterns


async def run_detection() -> list[dict]:
    """Main detection pipeline — gather data, analyze with LLM, store results.
    
    Returns list of pattern dicts for API response.
    """
    logger.info("=" * 60)
    logger.info("LLM BEHAVIORAL PATTERN DETECTOR — Starting")
    logger.info("=" * 60)
    
    async with AsyncSessionLocal() as session:
        # Step 1: Gather data
        logger.info("Gathering conversation data...")
        conversation_data, content_samples = await gather_conversation_data(session, days=60)
        
        logger.info("Gathering screen capture data...")
        capture_data = await gather_capture_data(session, days=14)
        
        logger.info("Gathering activity statistics...")
        activity_stats = await gather_activity_stats(session)
        
        # Merge capture data with activity stats
        full_capture_data = f"{capture_data}\n\n{activity_stats}"
        
        # Step 2: Analyze with LLM
        logger.info("Analyzing with Claude...")
        llm_patterns = await analyze_with_llm(conversation_data, full_capture_data, content_samples)
        
        if not llm_patterns:
            logger.warning("No patterns detected by LLM")
            return []
        
        # Step 3: Store in DB
        logger.info("Storing patterns...")
        stored = await store_patterns(session, llm_patterns)
        
        # Step 4: Summary
        by_type = {}
        for p in llm_patterns:
            pt = p.get("pattern_type", "unknown")
            by_type[pt] = by_type.get(pt, 0) + 1
        
        logger.info("=" * 60)
        logger.info("DETECTION COMPLETE")
        logger.info("=" * 60)
        for pt, count in sorted(by_type.items()):
            logger.info(f"  {pt}: {count}")
        logger.info(f"  TOTAL: {len(stored)} patterns stored")
        
        return llm_patterns


async def main():
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO)
    await run_detection()


if __name__ == "__main__":
    asyncio.run(main())
