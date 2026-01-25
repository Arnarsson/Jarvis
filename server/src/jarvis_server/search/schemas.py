"""Search request and response schemas."""
from datetime import datetime
from typing import Optional
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
    """Single search result."""

    id: str = Field(..., description="Capture or document ID")
    score: float = Field(..., description="Relevance score (higher is better)")
    text_preview: str = Field(..., description="Preview of matching text")
    timestamp: datetime = Field(..., description="When content was captured/created")
    source: str = Field(..., description="Content source: screen, chatgpt, claude, grok, email")
    filepath: Optional[str] = Field(default=None, description="Path to image file (for screen captures)")


class SearchResponse(BaseModel):
    """Search response with results and metadata."""

    query: str
    total: int
    results: list[SearchResult]
