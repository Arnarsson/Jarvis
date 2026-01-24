"""Claude export parser.

Parses Claude conversation exports. Claude exports are ZIP files containing
JSON files with conversation data. Format may vary by export type.
"""
import logging
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterator
import orjson

from .base import Conversation, Message

logger = logging.getLogger(__name__)


def parse_claude_export(filepath: str | Path) -> Iterator[Conversation]:
    """Parse Claude export ZIP file.

    Args:
        filepath: Path to Claude export ZIP file

    Yields:
        Conversation objects for each conversation in the export

    Note:
        Claude export format varies. This parser attempts to handle
        common structures but may need updates for specific formats.
    """
    filepath = Path(filepath)

    # Handle both ZIP and direct JSON
    if filepath.suffix == ".zip":
        yield from _parse_zip(filepath)
    elif filepath.suffix == ".json":
        yield from _parse_json_file(filepath)
    else:
        logger.warning(f"Unknown Claude export format: {filepath.suffix}")


def _parse_zip(filepath: Path) -> Iterator[Conversation]:
    """Parse Claude export ZIP file."""
    with zipfile.ZipFile(filepath, "r") as zf:
        for name in zf.namelist():
            if name.endswith(".json"):
                try:
                    with zf.open(name) as f:
                        data = orjson.loads(f.read())
                        yield from _parse_conversations(data, name)
                except Exception as e:
                    logger.warning(f"Failed to parse {name}: {e}")


def _parse_json_file(filepath: Path) -> Iterator[Conversation]:
    """Parse Claude JSON export file."""
    with open(filepath, "rb") as f:
        data = orjson.loads(f.read())
    yield from _parse_conversations(data, filepath.name)


def _parse_conversations(data: dict | list, source_name: str) -> Iterator[Conversation]:
    """Parse conversation data from Claude export."""
    # Handle list of conversations
    if isinstance(data, list):
        for i, conv in enumerate(data):
            conversation = _parse_single_conversation(conv, f"{source_name}_{i}")
            if conversation:
                yield conversation
        return

    # Handle single conversation object
    if isinstance(data, dict):
        # Check if this looks like a conversation
        if "chat_messages" in data or "messages" in data:
            conversation = _parse_single_conversation(data, source_name)
            if conversation:
                yield conversation
            return

        # Check for nested conversations
        for key in ["conversations", "chats"]:
            if key in data and isinstance(data[key], list):
                for i, conv in enumerate(data[key]):
                    conversation = _parse_single_conversation(conv, f"{source_name}_{i}")
                    if conversation:
                        yield conversation
                return


def _parse_single_conversation(conv: dict, fallback_id: str) -> Conversation | None:
    """Parse a single Claude conversation."""
    conv_id = conv.get("uuid") or conv.get("id") or fallback_id
    title = conv.get("name") or conv.get("title") or "Untitled"

    # Try different message field names
    raw_messages = conv.get("chat_messages") or conv.get("messages") or []

    messages = []
    for msg in raw_messages:
        role = msg.get("sender") or msg.get("role")
        if role == "human":
            role = "user"
        elif role == "assistant":
            role = "assistant"
        else:
            continue

        content = msg.get("text") or msg.get("content")
        if isinstance(content, list):
            # Handle structured content
            content = " ".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )

        if content and content.strip():
            timestamp_str = msg.get("created_at") or msg.get("timestamp")
            timestamp = None
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
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
        source="claude",
        messages=messages,
        created_at=created_at,
    )
