"""Search request and response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Search query parameters."""

    query: str = Field(..., min_length=1, max_length=1000, description="Natural language search query")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results to return")
    start_date: Optional[datetime] = Field(default=None, description="Filter: earliest timestamp")
    end_date: Optional[datetime] = Field(default=None, description="Filter: latest timestamp")
    sources: Optional[list[str]] = Field(
        default=None,
        description="Filter by source type: screen, chatgpt, claude, grok, email",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "meeting notes about project alpha",
                "limit": 10,
                "start_date": "2026-01-01T00:00:00Z",
                "sources": ["screen", "chatgpt"],
            }
        }


class SearchResult(BaseModel):
    """Single search result.

    NOTE: This is also used as the "flat" list for backwards compatibility.
    The UI / MCP may use richer fields when present.
    """

    id: str = Field(..., description="Capture or document ID")
    score: float = Field(..., description="Relevance score (higher is better)")
    text_preview: str = Field(..., description="Preview of matching text")
    timestamp: datetime = Field(..., description="When content was captured/created")
    source: str = Field(..., description="Content source: screen, chatgpt, claude, grok, email, calendar")

    # Optional metadata (depends on source)
    filepath: Optional[str] = Field(default=None, description="Path to image file (for screen captures)")
    title: Optional[str] = Field(default=None, description="Conversation title / calendar title")
    subject: Optional[str] = Field(default=None, description="Email subject")
    snippet: Optional[str] = Field(default=None, description="Email snippet")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="Additional source-specific metadata")


class SearchSynthesis(BaseModel):
    summary: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    key_dates: list[str] = Field(default_factory=list)
    key_people: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)


class SearchWhy(BaseModel):
    reasons: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    sources: list[dict[str, Any]] = Field(default_factory=list)


class SearchGroupedSources(BaseModel):
    email: list[dict[str, Any]] = Field(default_factory=list)
    calendar: list[dict[str, Any]] = Field(default_factory=list)
    captures: list[dict[str, Any]] = Field(default_factory=list)
    conversations: list[dict[str, Any]] = Field(default_factory=list)
    other: list[dict[str, Any]] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """Search response with synthesis + grouped sources.

    Keeps legacy flat list (results/total) for backwards compatibility.
    """

    query: str
    total: int
    results: list[SearchResult]

    synthesis: Optional[SearchSynthesis] = None
    sources_grouped: Optional[SearchGroupedSources] = None
    why: Optional[SearchWhy] = None
