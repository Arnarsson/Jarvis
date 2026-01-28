"""Search API endpoints."""

import logging

from fastapi import APIRouter, HTTPException

from ..search.hybrid import hybrid_search
from ..search.schemas import SearchRequest, SearchResponse
from ..search.synthesis import generate_search_synthesis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("/", response_model=SearchResponse)
async def search_memories(request: SearchRequest) -> SearchResponse:
    """Search captured memories using natural language.

    Performs hybrid search combining semantic understanding (dense vectors)
    with keyword matching (sparse vectors) using RRF fusion.

    Additionally returns:
    - synthesis: top-of-results summary + extracted entities
    - sources_grouped: results grouped by system/app
    - why: plain-language reasons + confidence + supporting sources

    Filters:
    - start_date/end_date: Time range filter
    - sources: Filter by content source (screen, chatgpt, claude, grok, email)
    """

    def group_key(source: str) -> str:
        s = (source or "").lower()
        if s == "email":
            return "email"
        if s == "calendar":
            return "calendar"
        if s in {"screen", "capture", "captures"}:
            return "captures"
        if s in {"chatgpt", "claude", "grok"}:
            return "conversations"
        return "other"

    try:
        results = hybrid_search(request)

        grouped: dict[str, list[dict]] = {
            "email": [],
            "calendar": [],
            "captures": [],
            "conversations": [],
            "other": [],
        }

        for r in results:
            g = group_key(r.source)

            if g == "email":
                grouped[g].append(
                    {
                        "id": r.id,
                        "subject": r.subject or (r.metadata or {}).get("subject") or "",
                        "snippet": (r.snippet or r.text_preview or "")[:400],
                        "date": r.timestamp.isoformat(),
                    }
                )
            elif g == "calendar":
                grouped[g].append(
                    {
                        "id": r.id,
                        "title": r.title or (r.metadata or {}).get("title") or "",
                        "date": r.timestamp.isoformat(),
                    }
                )
            elif g == "captures":
                grouped[g].append(
                    {
                        "id": r.id,
                        "ocr_snippet": (r.text_preview or "")[:400],
                        "timestamp": r.timestamp.isoformat(),
                        "filepath": r.filepath,
                    }
                )
            elif g == "conversations":
                grouped[g].append(
                    {
                        "id": r.id,
                        "title": r.title or (r.metadata or {}).get("title") or "",
                        "source": r.source,
                        "date": r.timestamp.isoformat(),
                        "snippet": (r.text_preview or "")[:400],
                    }
                )
            else:
                grouped[g].append(
                    {
                        "id": r.id,
                        "source": r.source,
                        "date": r.timestamp.isoformat(),
                        "snippet": (r.text_preview or "")[:400],
                    }
                )

        evidence: list[dict] = []
        for r in results[:10]:
            evidence.append(
                {
                    "id": r.id,
                    "source": r.source,
                    "timestamp": r.timestamp.isoformat(),
                    "title": r.title,
                    "subject": r.subject,
                    "snippet": (r.text_preview or "")[:700],
                }
            )

        synthesis_dict = await generate_search_synthesis(request.query, evidence)
        confidence = float(synthesis_dict.get("confidence", 0.5) or 0.5)

        # Basic "Why" reasons: count query term matches in evidence snippets
        q_terms = [t.lower() for t in request.query.split() if len(t) >= 3]
        term_counts: dict[str, int] = {t: 0 for t in q_terms}
        for ev in evidence:
            hay = (ev.get("snippet") or "").lower()
            for t in q_terms:
                if t in hay:
                    term_counts[t] += 1

        top_terms = sorted(term_counts.items(), key=lambda kv: kv[1], reverse=True)[:3]
        reasons = [f"Matched '{t}' in {n} sources" for t, n in top_terms if n > 0]
        if not reasons and results:
            reasons = ["Returned top-ranked results via hybrid (semantic + keyword) search"]

        return SearchResponse(
            query=request.query,
            total=len(results),
            results=results,
            synthesis=synthesis_dict,
            sources_grouped=grouped,
            why={
                "reasons": reasons,
                "confidence": confidence,
                "sources": evidence[:5],
            },
        )

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search failed")


@router.get("/health")
async def search_health() -> dict:
    """Check if search service is operational."""
    from ..vector.qdrant import get_qdrant

    try:
        qdrant = get_qdrant()
        collections = qdrant.client.get_collections()
        has_captures = any(c.name == "captures" for c in collections.collections)
        return {
            "status": "healthy" if has_captures else "degraded",
            "collection_exists": has_captures,
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
