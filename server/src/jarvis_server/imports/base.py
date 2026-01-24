"""Base types for chat import parsers."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Message:
    """A single message in a conversation."""

    role: str  # "user", "assistant", "system"
    content: str
    timestamp: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class Conversation:
    """A conversation with messages."""

    id: str
    title: str
    source: str  # "chatgpt", "claude", "grok"
    messages: list[Message] = field(default_factory=list)
    created_at: Optional[datetime] = None

    @property
    def full_text(self) -> str:
        """Concatenate all messages for embedding."""
        parts = [f"Title: {self.title}"]
        for msg in self.messages:
            parts.append(f"{msg.role.upper()}: {msg.content}")
        return "\n\n".join(parts)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
