"""Why + Confidence data models for all suggestions.

Provides transparency about why Jarvis is suggesting something,
with confidence scores and links back to source data.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Source(BaseModel):
    """Pointer to original data that informed a suggestion."""
    
    type: Literal['email', 'capture', 'calendar', 'chat', 'conversation']
    id: str
    timestamp: datetime
    snippet: str = Field(..., description="Preview text (first 200 chars)")
    url: str | None = Field(None, description="Open-in-context link")


class WhyPayload(BaseModel):
    """Explanation of why a suggestion was made.
    
    Provides transparency and traceability for all Jarvis suggestions.
    """
    
    reasons: list[str] = Field(
        ...,
        description="Plain English reasons (e.g., 'Sender is VIP', 'Contains deadline')",
        min_length=1
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score 0-1 (even rough heuristics)"
    )
    sources: list[Source] = Field(
        ...,
        description="Pointers to original data",
        min_length=1
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "reasons": [
                    "Sender is VIP contact",
                    "Email contains deadline mention",
                    "Related to active project"
                ],
                "confidence": 0.85,
                "sources": [
                    {
                        "type": "email",
                        "id": "msg_12345",
                        "timestamp": "2025-01-28T10:30:00Z",
                        "snippet": "Hi Sven, can you send the proposal by Friday?",
                        "url": "/email/msg_12345"
                    }
                ]
            }
        }
