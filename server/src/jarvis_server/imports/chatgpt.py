"""ChatGPT export parser.

Parses the conversations.json file from ChatGPT data export.
Export obtained from: ChatGPT Settings -> Data Controls -> Export data
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterator
import orjson

from .base import Conversation, Message

logger = logging.getLogger(__name__)


def parse_chatgpt_export(filepath: str | Path) -> Iterator[Conversation]:
    """Parse ChatGPT conversations.json export file.

    Args:
        filepath: Path to conversations.json file

    Yields:
        Conversation objects for each conversation in the export
    """
    filepath = Path(filepath)

    with open(filepath, "rb") as f:
        data = orjson.loads(f.read())

    for conv in data:
        try:
            conversation = _parse_conversation(conv)
            if conversation and conversation.messages:
                yield conversation
        except Exception as e:
            logger.warning(f"Failed to parse conversation {conv.get('id', 'unknown')}: {e}")
            continue


def _parse_conversation(conv: dict) -> Conversation | None:
    """Parse a single conversation from ChatGPT export."""
    conv_id = conv.get("id")
    if not conv_id:
        return None

    title = conv.get("title", "Untitled")
    mapping = conv.get("mapping", {})

    messages = []
    for node_id, node in mapping.items():
        message_data = node.get("message")
        if not message_data:
            continue

        author = message_data.get("author", {})
        role = author.get("role")  # "user", "assistant", "system"
        if role not in ("user", "assistant", "system"):
            continue

        content = message_data.get("content", {})
        content_type = content.get("content_type")
        parts = content.get("parts", [])

        if content_type == "text" and parts:
            text = parts[0] if isinstance(parts[0], str) else ""
            if text.strip():
                timestamp = message_data.get("create_time")
                messages.append(
                    Message(
                        role=role,
                        content=text.strip(),
                        timestamp=datetime.fromtimestamp(timestamp) if timestamp else None,
                    )
                )

    # Sort by timestamp
    messages.sort(key=lambda m: m.timestamp or datetime.min)

    # Get conversation creation time from first message
    created_at = messages[0].timestamp if messages else None

    return Conversation(
        id=conv_id,
        title=title,
        source="chatgpt",
        messages=messages,
        created_at=created_at,
    )
