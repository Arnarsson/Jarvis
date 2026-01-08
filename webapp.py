#!/usr/bin/env python3
"""
Perfect Executive Assistant API Server
Aligned with https://frontend-xi-ashen.vercel.app/

Standalone API - does not depend on MCP layer.
"""
import json
import logging
import os
import re
import sqlite3
import time as time_module
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load environment
load_dotenv()

# Constants
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(PROJECT_ROOT, "memory.sqlite"))
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.environ.get("QDRANT_COLLECTION", "memory_chunks")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("webapp_api")

# Import core modules
try:
    from unified_memory import UnifiedMemoryDB, Entity, token_count, sha1
    from intelligence import IntelligenceEngine
    from time_filters import parse_time_query, timestamp_in_range, TimeRange
    from score_utils import normalize_scores
    CORE_AVAILABLE = True
except ImportError as e:
    log.warning(f"Core modules not available: {e}")
    CORE_AVAILABLE = False


class MemoryServer:
    """
    Standalone Memory Server - no MCP dependencies.
    Provides all functionality needed by the Executive Dashboard.
    """

    def __init__(self, db_path: str, qdrant_url: str, collection: str, embed_model: str):
        self.db = UnifiedMemoryDB(
            db_path=db_path,
            qdrant_url=qdrant_url,
            collection=collection,
            embed_model=embed_model,
        )
        try:
            self.intelligence = IntelligenceEngine(self.db)
        except Exception as e:
            log.warning(f"Intelligence engine not available: {e}")
            self.intelligence = None

        self.session_accessed: List[str] = []
        self.session_entities: set = set()

    def _fts_search(self, query: str, limit: int = 20) -> Dict[str, float]:
        """Full-text search across tables."""
        sanitized = re.sub(r'[^\w\s]', ' ', query)
        sanitized = ' '.join(sanitized.split())
        if not sanitized:
            return {}

        conn = self.db._get_conn()
        raw_scores: Dict[str, float] = {}

        # Search rag_chunks
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT chunk_id, bm25(rag_chunks_fts) AS bm
                FROM rag_chunks_fts
                WHERE rag_chunks_fts MATCH ?
                LIMIT ?
            """, (sanitized, limit))
            for cid, bm in cur.fetchall():
                raw_scores[cid] = float(bm)
        except Exception:
            pass

        # Search memories
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT memory_id, bm25(memories_fts) AS bm
                FROM memories_fts
                WHERE memories_fts MATCH ?
                LIMIT ?
            """, (sanitized, limit))
            for mid, bm in cur.fetchall():
                raw_scores[mid] = float(bm)
        except Exception:
            pass

        conn.close()
        return normalize_scores(raw_scores)

    def recall(
        self,
        query: str = "",
        limit: int = 8,
        time_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Multi-dimensional memory recall with hybrid search."""
        if not query:
            return {"results": [], "count": 0, "message": "No query provided"}

        results = []
        warnings: List[str] = []
        time_range: Optional[TimeRange] = parse_time_query(time_filter) if time_filter else None

        # Semantic search
        sem_scores: Dict[str, float] = {}
        try:
            embedding = self.db._embed_text(query)
            sem_hits = self.db.qdrant.query_points(
                collection_name=self.db.collection,
                query=embedding,
                limit=limit * 4,
                with_payload=True,
            ).points

            for h in sem_hits:
                cid = h.payload.get("chunk_id", str(h.id))
                sem_scores[cid] = float(h.score)
        except Exception as exc:
            warnings.append(f"Semantic search unavailable: {exc}")

        # Lexical search
        lex_scores = self._fts_search(query, limit=limit * 4)

        sem_norm = normalize_scores(sem_scores)
        lex_norm = normalize_scores(lex_scores)

        # Combine (60% semantic, 40% lexical)
        w_sem, w_lex = 0.60, 0.40
        all_ids = set(sem_norm.keys()) | set(lex_norm.keys())
        ranked = []
        for cid in all_ids:
            base_score = w_sem * sem_norm.get(cid, 0.0) + w_lex * lex_norm.get(cid, 0.0)
            try:
                decay_score = self.db.calculate_decay_score(cid, base_importance=0.5)
                score = base_score * (0.7 + 0.3 * decay_score)
            except Exception:
                score = base_score
            ranked.append((cid, score))

        ranked.sort(key=lambda x: x[1], reverse=True)

        # Fetch details
        conn = self.db._get_conn()
        cur = conn.cursor()

        for cid, score in ranked[:limit * 2]:
            result = None

            # Check memories table
            if cid.startswith("mem_"):
                cur.execute("""
                    SELECT memory_id, content, tags, importance, created_at
                    FROM memories WHERE memory_id = ?
                """, (cid,))
                row = cur.fetchone()
                if row:
                    created = row["created_at"]
                    if time_range and not timestamp_in_range(created, time_range):
                        continue
                    result = {
                        "id": row["memory_id"],
                        "type": "memory",
                        "content": row["content"],
                        "snippet": row["content"][:200],
                        "tags": json.loads(row["tags"] or "[]"),
                        "importance": row["importance"],
                        "created_at": created,
                        "score": round(score, 4),
                    }

            # Check rag_chunks table
            elif cid.startswith("chunk_") or not cid.startswith(("mem_", "ent_")):
                cur.execute("""
                    SELECT chunk_id, title, text, ts_start, ts_end
                    FROM rag_chunks WHERE chunk_id = ?
                """, (cid,))
                row = cur.fetchone()
                if row:
                    ts = row["ts_start"]
                    if time_range and not timestamp_in_range(ts, time_range):
                        continue
                    result = {
                        "id": row["chunk_id"],
                        "type": "conversation",
                        "title": row["title"],
                        "content": row["text"],
                        "snippet": row["text"][:200] if row["text"] else "",
                        "created_at": ts,
                        "score": round(score, 4),
                    }

            if result:
                try:
                    self.db.log_access(cid, result["type"], "recall", query)
                except Exception:
                    pass
                results.append(result)
                if len(results) >= limit:
                    break

        conn.close()

        return {
            "results": results,
            "count": len(results),
            "query": query,
            "warnings": warnings,
        }

    def store(
        self,
        content: str,
        memory_type: str = "episodic",
        importance: float = 0.5,
        tags: str = "",
        auto_extract: bool = True,
    ) -> Dict[str, Any]:
        """Store a new memory."""
        from unified_memory import chunk_id_to_uuid
        from qdrant_client.http.models import PointStruct

        memory_id = "mem_" + sha1(f"{content}|{time_module.time()}")
        now = datetime.now().isoformat()
        tokens = token_count(content)
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

        conn = self.db._get_conn()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO memories (memory_id, content, tags, importance, metadata, token_count, embedded, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
        """, (memory_id, content, json.dumps(tag_list), importance, json.dumps({"type": memory_type}), tokens, now))

        try:
            cur.execute("""
                INSERT INTO memories_fts (memory_id, content, tags)
                VALUES (?, ?, ?)
            """, (memory_id, content, " ".join(tag_list)))
        except Exception:
            pass

        conn.commit()
        conn.close()

        # Embed
        try:
            embedding = self.db._embed_text(content)
            point_uuid = chunk_id_to_uuid(memory_id)
            self.db.qdrant.upsert(
                collection_name=self.db.collection,
                points=[PointStruct(
                    id=point_uuid,
                    vector=embedding,
                    payload={"chunk_id": memory_id, "type": "memory", "content": content[:500], "tags": tag_list, "importance": importance, "created_at": now}
                )]
            )
            conn = self.db._get_conn()
            conn.execute("UPDATE memories SET embedded = 1 WHERE memory_id = ?", (memory_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            log.warning(f"Embedding failed: {e}")

        result = {"memory_id": memory_id, "tokens": tokens, "message": f"Stored ({tokens} tokens)"}

        # Auto-extract entities
        if auto_extract and self.intelligence:
            try:
                extracted = self.intelligence.extract_entities(content)
                if extracted:
                    entities_created = []
                    for ent in extracted:
                        entity = self.db.create_entity(name=ent["name"], entity_type=ent["type"], description=ent.get("context", ""))
                        entities_created.append(entity.name)
                        self.db.create_relation(from_id=memory_id, from_type="memory", to_id=entity.id, to_type="entity", relation_type="mentions")
                    result["entities_extracted"] = entities_created
            except Exception as e:
                log.warning(f"Entity extraction failed: {e}")

        return result

    def get_beliefs(self, subject: str = "", category: str = "") -> Dict[str, Any]:
        """Query semantic beliefs."""
        beliefs = self.db.get_beliefs(
            subject=subject if subject else None,
            category=category if category else None,
        )
        return {
            "beliefs": [{"id": b.id, "fact": b.fact, "subject": b.subject, "category": b.category, "confidence": b.confidence, "established": b.ts_established} for b in beliefs],
            "count": len(beliefs),
        }

    def query_entities(self, query: str = "", entity_type: str = "", limit: int = 20) -> Dict[str, Any]:
        """Query knowledge graph entities."""
        if query:
            entities = self.db.search_entities(query=query, entity_type=entity_type if entity_type else None, limit=limit)
        else:
            conn = self.db._get_conn()
            cur = conn.cursor()
            sql = "SELECT * FROM entities"
            params = []
            if entity_type:
                sql += " WHERE type = ?"
                params.append(entity_type)
            sql += " ORDER BY last_seen DESC LIMIT ?"
            params.append(limit)
            cur.execute(sql, params)
            entities = [Entity(id=row["id"], type=row["type"], name=row["name"], properties=json.loads(row["properties"] or "{}"), created_at=row["created_at"], updated_at=row["updated_at"]) for row in cur.fetchall()]
            conn.close()

        return {
            "entities": [{"id": e.id, "type": e.type, "name": e.name, "properties": e.properties} for e in entities],
            "count": len(entities),
        }

    def generate_morning_brief(self) -> Dict[str, Any]:
        """Generate morning brief."""
        if not self.intelligence:
            return {"error": "Intelligence layer unavailable"}
        try:
            return self.intelligence.generate_executive_brief()
        except Exception as e:
            return {"error": str(e)}


# FastAPI App
app = FastAPI(title="Perfect Executive Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Models
class SearchRequest(BaseModel):
    query: str
    limit: int = 8
    time_filter: Optional[str] = None


class StoreMemoryRequest(BaseModel):
    content: str
    tags: List[str] = []
    importance: float = 0.5
    source: str = "chat"
    auto_extract: bool = True


# Global server instance
_server: Optional[MemoryServer] = None


def get_server() -> MemoryServer:
    global _server
    if _server is None:
        if not CORE_AVAILABLE:
            raise HTTPException(status_code=503, detail="Core modules not available")
        _server = MemoryServer(db_path=DB_PATH, qdrant_url=QDRANT_URL, collection=COLLECTION, embed_model=EMBED_MODEL)
    return _server


@app.get("/")
async def root():
    return {"status": "online", "message": "Perfect Executive Assistant API", "version": "2.3"}


@app.get("/health")
async def health():
    """Health check for all services."""
    db_ok = False
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT 1")
        conn.close()
        db_ok = True
    except Exception:
        pass

    qdrant_ok = False
    try:
        from qdrant_client import QdrantClient
        qd = QdrantClient(url=QDRANT_URL, timeout=2)
        qd.get_collections()
        qdrant_ok = True
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "degraded",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "database": "connected" if db_ok else "disconnected",
            "qdrant": "connected" if qdrant_ok else "disconnected",
        }
    }


@app.get("/memory/stats")
@app.get("/api/stats")
async def api_stats():
    """Memory statistics."""
    try:
        server = get_server()
        stats = server.db.get_stats()
        stats["chunks"] = stats.get("imported_conversations", 0)
        stats["memories"] = stats.get("stored_memories", 0)
        return {**stats, "timestamp": datetime.now().isoformat(), "status": "ready"}
    except Exception as e:
        return {"error": str(e), "chunks": 0, "memories": 0, "entities": 0, "beliefs": 0}


@app.get("/memory/search")
@app.get("/api/search")
async def api_search_get(q: str = Query(...), limit: int = Query(8), time: Optional[str] = Query(None)):
    return await _perform_search(q, limit, time)


@app.post("/memory/search")
@app.post("/api/search")
async def api_search_post(req: SearchRequest):
    return await _perform_search(req.query, req.limit, req.time_filter)


async def _perform_search(query: str, limit: int, time_filter: Optional[str]):
    if not query.strip():
        return {"results": [], "query": query, "count": 0}
    try:
        server = get_server()
        results = server.recall(query=query.strip(), limit=limit, time_filter=time_filter)
        return {"results": results.get("results", []), "query": query, "count": len(results.get("results", [])), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"results": [], "query": query, "count": 0, "error": str(e)}


@app.get("/api/morning_brief")
@app.post("/api/morning_brief")
async def api_morning_brief():
    try:
        server = get_server()
        return server.generate_morning_brief()
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/store")
async def api_store(req: StoreMemoryRequest):
    try:
        server = get_server()
        res = server.store(content=req.content, tags=",".join(req.tags), importance=req.importance, memory_type=req.source, auto_extract=req.auto_extract)
        return {"stored": True, "memory_id": res.get("memory_id"), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"error": str(e), "stored": False}


@app.get("/api/entities")
@app.post("/api/entities")
async def api_entities(limit: int = Query(20)):
    try:
        server = get_server()
        return server.query_entities(limit=limit)
    except Exception as e:
        return {"entities": [], "error": str(e)}


@app.get("/api/entity/{entity_id}")
async def api_entity_detail(entity_id: str):
    try:
        server = get_server()
        entity = server.db.get_entity(entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        return {
            "entity": {"id": entity.id, "type": entity.type, "name": entity.name, "properties": entity.properties},
            "observations": [{"id": o.id, "content": o.content, "confidence": o.confidence} for o in server.db.get_observations(entity_id)],
            "relations": [{"id": r.id, "from_id": r.from_id, "to_id": r.to_id, "relation_type": r.relation_type} for r in server.db.get_relations(entity_id)],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/beliefs")
@app.post("/api/beliefs")
async def api_beliefs():
    try:
        server = get_server()
        return server.get_beliefs()
    except Exception as e:
        return {"beliefs": [], "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
