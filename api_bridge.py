#!/usr/bin/env python3
"""
HTTP API Bridge for Executive Assistant MemoryService
Exposes unified_memory capabilities via REST endpoints
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import logging
from unified_memory import UnifiedMemoryDB
from intelligence import IntelligenceEngine
import sqlite3
from qdrant_client import QdrantClient
from openai import OpenAI
import re

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api_bridge")

# === HELPER FUNCTIONS ===

def simple_search(db_path: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Simple FTS5-based search"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Sanitize query for FTS5
        sanitized = re.sub(r'[^\w\s]', ' ', query)
        sanitized = ' '.join(sanitized.split())

        if not sanitized:
            return []

        # Search in observations first
        results = []
        try:
            cur.execute("""
                SELECT o.id, o.content, o.timestamp, e.name as entity_name
                FROM observations o
                JOIN entities e ON o.entity_id = e.id
                WHERE o.content LIKE ?
                LIMIT ?
            """, (f'%{query}%', limit))

            for row in cur.fetchall():
                results.append({
                    "id": row["id"],
                    "title": f"Observation about {row['entity_name']}",
                    "content": row["content"],
                    "timestamp": row["timestamp"],
                    "_score": 1.0
                })
        except Exception as e:
            log.warning(f"Observation search error: {e}")

        conn.close()
        return results
    except Exception as e:
        log.error(f"Search error: {e}")
        return []

# Initialize
app = FastAPI(title="Executive Memory API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Lock down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DB and Intelligence
db_path = os.getenv("DB_PATH", "./memory.sqlite")
qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")

try:
    db = UnifiedMemoryDB(db_path=db_path, qdrant_url=qdrant_url)
    intel = IntelligenceEngine(db)
    log.info(f"✅ Initialized memory DB at {db_path}")
except Exception as e:
    log.error(f"❌ Failed to initialize: {e}")
    db = None
    intel = None

# === REQUEST MODELS ===

class ObservationRequest(BaseModel):
    entity_name: str
    content: str
    source: str
    metadata: Optional[Dict[str, Any]] = None

class EntityRequest(BaseModel):
    name: str
    type: str  # person, project, technology, concept, organization
    metadata: Optional[Dict[str, Any]] = None

class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 10
    time_filter: Optional[str] = None

class BriefRequest(BaseModel):
    scope: str  # "business", "technical", "personal"
    time_range: str  # "today", "this week", "this month"

# === ENDPOINTS ===

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if db is None:
        return {
            "status": "unhealthy",
            "error": "Database not initialized"
        }

    try:
        stats = db.get_stats()
        return {
            "status": "healthy",
            "db_path": db.db_path,
            "chunks": stats.get("total_chunks", 0),
            "entities": stats.get("total_entities", 0)
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e)
        }

@app.post("/memory/observation")
async def add_observation(req: ObservationRequest, background_tasks: BackgroundTasks):
    """Store a new memory observation"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Create or get entity
        entity = db.find_entity_by_name(req.entity_name)
        if not entity:
            entity = db.create_entity(
                name=req.entity_name,
                entity_type="concept",
                properties=req.metadata or {}
            )

        # Add observation
        obs = db.add_observation(
            entity_id=entity.id,
            content=req.content,
            source=req.source,
            confidence=1.0
        )

        # Background: Extract entities if intelligence is enabled
        if intel and intel.enabled:
            background_tasks.add_task(intel.extract_and_link_entities, req.content, obs.id)

        return {
            "success": True,
            "observation_id": obs.id,
            "entity_id": entity.id
        }
    except Exception as e:
        log.error(f"Error adding observation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/memory/entity")
async def create_entity_endpoint(req: EntityRequest):
    """Create a new entity"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        entity = db.create_entity(
            name=req.name,
            entity_type=req.type,
            properties=req.metadata or {}
        )
        return {
            "success": True,
            "entity": {
                "id": entity.id,
                "name": entity.name,
                "type": entity.type
            }
        }
    except Exception as e:
        log.error(f"Error creating entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/memory/search")
async def search_memory(q: str, limit: int = 10, time_filter: Optional[str] = None):
    """Simple lexical search"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Use simple search function
        results = simple_search(db.db_path, q, limit)

        return {
            "success": True,
            "results": [
                {
                    "id": r.get("id", ""),
                    "title": r.get("title", ""),
                    "content": r.get("content", "")[:200],
                    "score": r.get("_score", 0.0),
                    "timestamp": r.get("timestamp")
                }
                for r in results
            ]
        }
    except Exception as e:
        log.error(f"Error searching: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/memory/suggestions")
async def proactive_suggestions(context: Optional[str] = None):
    """Generate proactive memory suggestions"""
    if intel is None or not intel.enabled:
        return {"success": True, "suggestions": []}

    try:
        suggestions = intel.generate_proactive_suggestions(
            current_context=context,
            limit=5
        )
        return {
            "success": True,
            "suggestions": suggestions
        }
    except Exception as e:
        log.error(f"Error generating suggestions: {e}")
        return {"success": True, "suggestions": []}

@app.get("/memory/stats")
async def get_stats():
    """Memory system statistics"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    return db.get_stats()

# === BACKEND-COMPATIBLE API ENDPOINTS ===
# These endpoints match what the exec backend MemoryService.ts expects

@app.post("/api/search")
async def api_search(req: SearchRequest):
    """Search endpoint compatible with backend MemoryService.ts"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        results = simple_search(db.db_path, req.query, req.limit or 10)

        return {
            "results": [
                {
                    "id": r.get("id", ""),
                    "title": r.get("title", ""),
                    "url": f"/memory/{r.get('id', '')}",  # URL for fetch endpoint
                    "score": r.get("_score", 0.0)
                }
                for r in results
            ]
        }
    except Exception as e:
        log.error(f"Error searching: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def api_stats():
    """Stats endpoint compatible with backend MemoryService.ts"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    stats = db.get_stats()
    return {
        "chunks": stats.get("total_chunks", 0),
        "memories": stats.get("total_observations", 0),
        "entities": stats.get("total_entities", 0),
        "beliefs": 0,  # Not implemented yet
        "timestamp": stats.get("timestamp", "")
    }

@app.post("/api/suggestions")
async def api_suggestions(request: Dict[str, Any]):
    """Proactive suggestions endpoint compatible with backend MemoryService.ts"""
    if intel is None or not intel.enabled:
        return {
            "suggestions": [],
            "mentioned_entities": [],
            "enabled": False,
            "timestamp": ""
        }

    try:
        context = request.get("context", "")
        suggestions = intel.generate_proactive_suggestions(
            current_context=context,
            limit=5
        )
        return {
            "suggestions": suggestions,
            "mentioned_entities": [],
            "enabled": True,
            "timestamp": ""
        }
    except Exception as e:
        log.error(f"Error generating suggestions: {e}")
        return {
            "suggestions": [],
            "mentioned_entities": [],
            "enabled": True,
            "timestamp": "",
            "error": str(e)
        }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Executive Memory API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "observation": "POST /memory/observation",
            "entity": "POST /memory/entity",
            "search": "GET /memory/search?q=query (deprecated, use POST /api/search)",
            "api_search": "POST /api/search",
            "api_stats": "GET /api/stats",
            "api_suggestions": "POST /api/suggestions",
            "suggestions": "GET /memory/suggestions?context=... (deprecated)",
            "stats": "GET /memory/stats"
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8000"))
    log.info(f"🚀 Starting API Bridge on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
