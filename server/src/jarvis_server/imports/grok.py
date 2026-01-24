"""Grok export parser.

Parses Grok conversation exports. Export obtained via accounts.x.ai
or third-party export tools.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterator
import orjson

from .base import Conversation, Message

logger = logging.getLogger(__name__)


def parse_grok_export(filepath: str | Path) -> Iterator[Conversation]:
    """Parse Grok export JSON file.

    Args:
        filepath: Path to Grok export JSON file

    Yields:
        Conversation objects for each conversation in the export

    Note:
        Grok export format may vary. This parser handles common structures
        but may need updates for specific export tools.
    """
    filepath = Path(filepath)

    with open(filepath, "rb") as f:
        data = orjson.loads(f.read())

    # Handle list of conversations
    if isinstance(data, list):
        for i, conv in enumerate(data):
            conversation = _parse_conversation(conv, f"grok_{i}")
            if conversation:
                yield conversation
        return

    # Handle single conversation or wrapped structure
    if isinstance(data, dict):
        # Check for conversations list
        conversations = data.get("conversations") or data.get("chats") or [data]
        for i, conv in enumerate(conversations):
            conversation = _parse_conversation(conv, f"grok_{i}")
            if conversation:
                yield conversation


def _parse_conversation(conv: dict, fallback_id: str) -> Conversation | None:
    """Parse a single Grok conversation."""
    conv_id = conv.get("id") or conv.get("conversationId") or fallback_id
    title = conv.get("title") or conv.get("name") or "Grok Conversation"

    # Try different message field names
    raw_messages = conv.get("messages") or conv.get("turns") or []

    messages = []
    for msg in raw_messages:
        role = msg.get("role") or msg.get("author") or msg.get("sender")
        if role in ("human", "user"):
            role = "user"
        elif role in ("assistant", "grok", "ai"):
            role = "assistant"
        else:
            continue

        content = msg.get("content") or msg.get("text") or msg.get("message")
        if isinstance(content, list):
            content = " ".join(str(part) for part in content)

        if content and content.strip():
            timestamp_str = msg.get("timestamp") or msg.get("created_at")
            timestamp = None
            if timestamp_str:
                try:
                    if isinstance(timestamp_str, (int, float)):
                        timestamp = datetime.fromtimestamp(timestamp_str)
                    else:
                        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                except (ValueError, TypeError, OSError):
                    pass

            messages.append(
                Message(role=role, content=content.strip(), timestamp=timestamp)
            )

    if not messages:
        return None

    created_at = messages[0].timestamp if messages else None

    return Conversation(
        id=conv_id,
        title=title,
        source="grok",
        messages=messages,
        created_at=created_at,
    )
