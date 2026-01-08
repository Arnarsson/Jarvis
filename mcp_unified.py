#!/usr/bin/env python3
"""
Unified Memory MCP Server - AI-Assisted EA Memory Intelligence System

Combines:
- Hybrid semantic+lexical search across 21,622+ conversation chunks
- Knowledge graph with entities, observations, and relations
- Semantic beliefs (preferences, facts, decisions)
- Importance decay and proactive surfacing
- Automatic entity extraction

MCP Tools:
1. recall     - Multi-dimensional memory search
2. store      - Store with auto-enrichment
3. beliefs    - Query semantic memories
4. entities   - Knowledge graph queries
5. context    - Proactive suggestions
6. link       - Create relations

Usage:
    python mcp_unified.py --db memory.sqlite

Or add to Claude Desktop config:
    {
      "mcpServers": {
        "memory": {
          "command": "python",
          "args": ["/path/to/mcp_unified.py", "--db", "/path/to/memory.sqlite"]
        }
      }
    }
"""

import argparse
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastmcp import FastMCP

from unified_memory import UnifiedMemoryDB, token_count, sha1
from intelligence import IntelligenceEngine
from time_filters import TimeRange, parse_time_query, timestamp_in_range
from score_utils import normalize_scores

load_dotenv()

# Suppress noisy logging
logging.basicConfig(level=logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("qdrant_client").setLevel(logging.WARNING)

log = logging.getLogger("mcp-unified")
log.setLevel(logging.INFO)



class UnifiedMemoryServer:
    """
    Unified Memory Server with all intelligence features.
    """

    def __init__(self, db_path: str, qdrant_url: str, collection: str, embed_model: str):
        self.db = UnifiedMemoryDB(
            db_path=db_path,
            qdrant_url=qdrant_url,
            collection=collection,
            embed_model=embed_model,
        )
        self.intelligence = IntelligenceEngine(self.db)

        # Session context
        self.session_accessed = []  # Recently accessed memory IDs
        self.session_entities = set()  # Mentioned entities in session

    def _fts_search(self, query: str, limit: int = 20) -> Dict[str, float]:
        """Full-text search across all tables."""
        import sqlite3

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
        except:
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
        except:
            pass

        # Search entities
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, bm25(entities_fts) AS bm
                FROM entities_fts
                WHERE entities_fts MATCH ?
                LIMIT ?
            """, (sanitized, limit))
            for eid, bm in cur.fetchall():
                raw_scores[eid] = float(bm)
        except:
            pass

        conn.close()
        return normalize_scores(raw_scores)

    def recall(
        self,
        query: str = "",
        memory_types: str = "all",
        time_filter: str = "",
        entity_filter: str = "",
        limit: int = 5,
        include_chain: bool = True,
    ) -> Dict[str, Any]:
        """
        Multi-dimensional memory recall with hybrid search.
        """
        if not query and not entity_filter:
            return {"results": [], "count": 0, "message": "No query provided"}

        results = []
        warnings: List[str] = []
        time_range: Optional[TimeRange] = parse_time_query(time_filter) if time_filter else None
        filters_applied: Dict[str, Any] = {}
        filters_failed: List[Dict[str, Any]] = []

        if time_filter:
            if time_range:
                filters_applied["time"] = {
                    "requested": time_filter,
                    "parsed": True,
                    "range": [
                        time_range[0].isoformat() if time_range[0] else None,
                        time_range[1].isoformat() if time_range[1] else None,
                    ],
                }
            else:
                filters_failed.append({
                    "filter": "time",
                    "requested": time_filter,
                    "reason": "Unable to interpret time filter",
                })

        # Parse memory types
        types_to_search = ["conversation", "memory", "entity", "belief"]
        if memory_types != "all":
            types_to_search = [t.strip() for t in memory_types.split(",")]

        # Semantic search
        sem_scores: Dict[str, float] = {}
        if query:
            semantic_ready = getattr(self.db, "semantic_enabled", True) and getattr(self.db, "qdrant", None) is not None
            if semantic_ready:
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
                    warnings.append(f"Semantic retrieval unavailable: {exc}")
            else:
                warnings.append("Semantic retrieval disabled; using lexical-only search.")

        # Lexical search
        lex_scores = self._fts_search(query, limit=limit * 4) if query else {}

        sem_norm = normalize_scores(sem_scores)
        lex_norm = normalize_scores(lex_scores)

        # Combine scores (60% semantic, 40% lexical)
        w_sem, w_lex = 0.60, 0.40
        all_ids = set(sem_norm.keys()) | set(lex_norm.keys())
        ranked = []
        for cid in all_ids:
            base_score = w_sem * sem_norm.get(cid, 0.0) + w_lex * lex_norm.get(cid, 0.0)

            # Apply importance decay
            decay_score = self.db.calculate_decay_score(cid, base_importance=0.5)
            score = base_score * (0.7 + 0.3 * decay_score)  # Decay affects 30% of score

            ranked.append((cid, score))

        ranked.sort(key=lambda x: x[1], reverse=True)

        # Fetch details
        conn = self.db._get_conn()
        cur = conn.cursor()

        for cid, score in ranked[:limit * 2]:
            result = None

            # Check memories table
            if cid.startswith("mem_") and "memory" in types_to_search:
                cur.execute("""
                    SELECT memory_id, content, tags, importance, metadata, created_at
                    FROM memories WHERE memory_id = ?
                """, (cid,))
                row = cur.fetchone()
                if row:
                    created = row["created_at"]
                    if not timestamp_in_range(created, time_range):
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
            elif cid.startswith("chunk_") and "conversation" in types_to_search:
                cur.execute("""
                    SELECT chunk_id, title, text, ts_start, ts_end
                    FROM rag_chunks WHERE chunk_id = ?
                """, (cid,))
                row = cur.fetchone()
                if row:
                    ts = row["ts_start"]
                    if not timestamp_in_range(ts, time_range):
                        continue

                    result = {
                        "id": row["chunk_id"],
                        "type": "conversation",
                        "title": row["title"],
                        "content": row["text"],
                        "snippet": row["text"][:200],
                        "created_at": ts,
                        "score": round(score, 4),
                    }

            # Check entities
            elif cid.startswith("ent_") and "entity" in types_to_search:
                entity = self.db.get_entity(cid)
                if entity:
                    observations = self.db.get_observations(cid)
                    result = {
                        "id": entity.id,
                        "type": "entity",
                        "entity_type": entity.type,
                        "name": entity.name,
                        "content": f"{entity.name} ({entity.type})",
                        "snippet": observations[0].content if observations else "",
                        "observations_count": len(observations),
                        "created_at": entity.created_at,
                        "score": round(score, 4),
                    }

            if result:
                # Log access
                self.db.log_access(cid, result["type"], "recall", query)
                self.session_accessed.append(cid)

                results.append(result)
                if len(results) >= limit:
                    break

        conn.close()

        # Include related memories if requested
        if include_chain and results:
            for r in results[:3]:  # Only for top 3
                relations = self.db.get_relations(r["id"])
                if relations:
                    r["related"] = [
                        {"id": rel.to_id, "type": rel.relation_type}
                        for rel in relations[:3]
                    ]

        filters_meta = {
            "types": types_to_search,
            "time": time_filter or None,
        }
        if time_range:
            filters_meta["time_range"] = [
                time_range[0].isoformat() if time_range[0] else None,
                time_range[1].isoformat() if time_range[1] else None,
            ]

        return {
            "results": results,
            "count": len(results),
            "query": query,
            "filters": filters_meta,
            "filters_applied": filters_applied or None,
            "filters_failed": filters_failed,
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
        """
        Store a new memory with optional auto-enrichment.
        """
        import time as time_module

        memory_id = "mem_" + sha1(f"{content}|{time_module.time()}")
        now = datetime.now().isoformat()
        tokens = token_count(content)

        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

        conn = self.db._get_conn()
        cur = conn.cursor()

        # Insert into memories table
        cur.execute("""
            INSERT INTO memories (memory_id, content, tags, importance, metadata, token_count, embedded, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
        """, (
            memory_id,
            content,
            json.dumps(tag_list),
            importance,
            json.dumps({"type": memory_type}),
            tokens,
            now,
        ))

        # Insert into FTS
        cur.execute("""
            INSERT INTO memories_fts (memory_id, content, tags)
            VALUES (?, ?, ?)
        """, (memory_id, content, " ".join(tag_list)))

        conn.commit()
        conn.close()

        # Embed and store in Qdrant
        try:
            from unified_memory import chunk_id_to_uuid
            from qdrant_client.http.models import PointStruct

            embedding = self.db._embed_text(content)
            point_uuid = chunk_id_to_uuid(memory_id)
            self.db.qdrant.upsert(
                collection_name=self.db.collection,
                points=[PointStruct(
                    id=point_uuid,
                    vector=embedding,
                    payload={
                        "chunk_id": memory_id,
                        "type": "memory",
                        "content": content[:500],
                        "tags": tag_list,
                        "importance": importance,
                        "created_at": now,
                    }
                )]
            )

            # Mark as embedded
            conn = self.db._get_conn()
            conn.execute("UPDATE memories SET embedded = 1 WHERE memory_id = ?", (memory_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            log.error(f"Failed to embed memory: {e}")

        result = {
            "memory_id": memory_id,
            "tokens": tokens,
            "message": f"Memory stored successfully ({tokens} tokens)",
        }

        # Auto-extract entities
        if auto_extract:
            try:
                extracted = self.intelligence.extract_entities(content)
                if extracted:
                    entities_created = []
                    for ent in extracted:
                        entity = self.db.create_entity(
                            name=ent["name"],
                            entity_type=ent["type"],
                            description=ent.get("context", ""),
                        )
                        entities_created.append(entity.name)

                        # Link memory to entity
                        self.db.create_relation(
                            from_id=memory_id,
                            from_type="memory",
                            to_id=entity.id,
                            to_type="entity",
                            relation_type="mentions",
                        )

                    result["entities_extracted"] = entities_created
            except Exception as e:
                log.warning(f"Entity extraction failed: {e}")

        return result

    def get_beliefs(
        self,
        subject: str = "",
        category: str = "",
        include_history: bool = False,
    ) -> Dict[str, Any]:
        """
        Query semantic beliefs/preferences.
        """
        beliefs = self.db.get_beliefs(
            subject=subject if subject else None,
            category=category if category else None,
            include_superseded=include_history,
        )

        results = []
        for b in beliefs:
            result = {
                "id": b.id,
                "fact": b.fact,
                "subject": b.subject,
                "category": b.category,
                "confidence": b.confidence,
                "established": b.ts_established,
                "last_verified": b.ts_last_verified,
            }

            if include_history and b.superseded_by:
                result["superseded_by"] = b.superseded_by

            results.append(result)

        return {
            "beliefs": results,
            "count": len(results),
            "filters": {
                "subject": subject or None,
                "category": category or None,
            },
        }

    def query_entities(
        self,
        query: str = "",
        entity_type: str = "",
        include_relations: bool = True,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Query knowledge graph entities.
        """
        if query:
            entities = self.db.search_entities(
                query=query,
                entity_type=entity_type if entity_type else None,
                limit=limit,
            )
        else:
            # Return recent entities
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

            from unified_memory import Entity
            entities = []
            for row in cur.fetchall():
                entities.append(Entity(
                    id=row["id"],
                    type=row["type"],
                    name=row["name"],
                    properties=json.loads(row["properties"] or "{}"),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                ))

            conn.close()

        results = []
        for e in entities:
            result = {
                "id": e.id,
                "type": e.type,
                "name": e.name,
                "properties": e.properties,
                "created_at": e.created_at,
            }

            if include_relations:
                observations = self.db.get_observations(e.id)
                relations = self.db.get_relations(e.id)

                result["observations"] = [
                    {"content": o.content, "confidence": o.confidence}
                    for o in observations[:5]
                ]
                result["relations"] = [
                    {"to": r.to_id, "type": r.relation_type}
                    for r in relations[:5]
                ]

            # Track in session
            self.session_entities.add(e.name)

            results.append(result)

        return {
            "entities": results,
            "count": len(results),
            "filters": {
                "query": query or None,
                "type": entity_type or None,
            },
        }

    def get_context(self) -> Dict[str, Any]:
        """
        Get proactive suggestions based on session context.
        """
        suggestions = self.intelligence.get_suggestions(
            recent_accessed=self.session_accessed[-10:],
            mentioned_entities=list(self.session_entities),
        )

        # Recent activity
        conn = self.db._get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT memory_id, memory_type, access_type, ts_accessed
            FROM access_log
            ORDER BY ts_accessed DESC
            LIMIT 5
        """)
        recent = [dict(row) for row in cur.fetchall()]

        conn.close()

        return {
            "suggestions": suggestions,
            "recent_activity": recent,
            "session_entities": list(self.session_entities),
            "session_accessed_count": len(self.session_accessed),
        }

    def generate_briefing(
        self,
        time_range_days: int = 30,
        focus: str = "general strategy",
        include_history: bool = True,
        regenerate: bool = True,
    ) -> Dict[str, Any]:
        """Generate or fetch executive briefs."""
        generated = None
        if regenerate:
            generated = self.intelligence.generate_executive_brief(
                time_range_days=time_range_days,
                focus=focus,
            )
        history = []
        if include_history:
            for brief in self.db.get_executive_briefs(limit=5):
                history.append({
                    "id": brief.id,
                    "period": brief.period_label,
                    "scope": brief.scope,
                    "summary": brief.summary,
                    "highlights": brief.highlights,
                    "risks": brief.risks,
                    "opportunities": brief.opportunities,
                    "recommendations": brief.recommendations,
                    "notable_entities": brief.notable_entities,
                    "created_at": brief.created_at,
                })
        return {
            "generated": generated,
            "history": history,
        }

    def create_link(
        self,
        source_id: str,
        target_id: str,
        relation_type: str = "related_to",
    ) -> Dict[str, Any]:
        """
        Create explicit link between memories/entities.
        """
        # Determine types
        source_type = "entity" if source_id.startswith("ent_") else "memory" if source_id.startswith("mem_") else "chunk"
        target_type = "entity" if target_id.startswith("ent_") else "memory" if target_id.startswith("mem_") else "chunk"

        relation = self.db.create_relation(
            from_id=source_id,
            from_type=source_type,
            to_id=target_id,
            to_type=target_type,
            relation_type=relation_type,
        )

        return {
            "relation_id": relation.id,
            "from": source_id,
            "to": target_id,
            "type": relation_type,
            "message": "Link created successfully",
        }

    def run_consolidation(self, time_range_days: int = 7, force: bool = False) -> Dict[str, Any]:
        """Trigger the intelligence layer consolidation."""
        days = max(1, min(60, time_range_days))
        stats = self.intelligence.consolidate_memories(time_range_days=days, force=force)
        stats["run_at"] = datetime.now().isoformat()
        return stats

    def analyze_history(self, batch_size: int = 50, time_range: str = "all") -> Dict[str, Any]:
        """Process historical conversation chunks for enrichment."""
        batch = max(1, min(200, batch_size))
        stats = self.intelligence.analyze_history(batch_size=batch, time_filter=time_range)
        stats["run_at"] = datetime.now().isoformat()
        return stats


def make_mcp_server(db_path: str, qdrant_url: str, collection: str, embed_model: str) -> FastMCP:
    """Create the unified MCP server with all tools."""

    server = UnifiedMemoryServer(db_path, qdrant_url, collection, embed_model)

    mcp = FastMCP(
        name="UnifiedMemory",
        instructions="""AI-Assisted EA Memory Intelligence System.

Your persistent memory across sessions with:
- Hybrid semantic + lexical search
- Knowledge graph (entities, relations)
- Semantic beliefs (preferences, facts)
- Importance decay and proactive surfacing

Tools:
- recall: Search memories, conversations, entities
- store: Save new memories with auto-enrichment
- consolidate: Run entity/belief extraction on recent memories
- analyze_history: Bulk-process historical conversations for entities/beliefs
- brief: Generate executive-ready summaries over recent conversations
- beliefs: Query your preferences and facts
- entities: Browse knowledge graph
- context: Get proactive suggestions
- link: Connect memories and entities

Examples:
- recall(query="FastAPI deployment") - find relevant memories
- recall(query="project", time_filter="last week") - recent project discussions
- store(content="User prefers TypeScript", tags="preference,coding")
- consolidate(time_range_days=14) - reprocess recent memories
- analyze_history(batch_size=25, time_range="December 2024")
- beliefs(subject="coding") - get coding preferences
- entities(query="Python") - find Python-related entities
- context() - get suggestions based on current session
""",
    )

    @mcp.tool()
    def recall(
        query: str = "",
        memory_types: str = "all",
        time_filter: str = "",
        entities: str = "",
        limit: int = 5,
        include_chain: bool = True,
    ) -> str:
        """
        Search and recall memories using hybrid semantic + lexical + graph search.

        Args:
            query: Search query (semantic + keyword search)
            memory_types: Types to search (conversation,memory,entity,belief or "all")
            time_filter: Natural language time filter ("today", "last week", "last 3 days")
            entities: Comma-separated entity names to filter by
            limit: Max results (1-50, default 5)
            include_chain: Include related memories (default True)

        Returns:
            JSON with matching memories, entities, and relevance scores
        """
        result = server.recall(
            query=query,
            memory_types=memory_types,
            time_filter=time_filter,
            entity_filter=entities,
            limit=min(max(1, limit), 50),
            include_chain=include_chain,
        )
        return json.dumps(result, indent=2, ensure_ascii=False)

    @mcp.tool()
    def store(
        content: str,
        memory_type: str = "episodic",
        importance: float = 0.5,
        tags: str = "",
        auto_extract: bool = True,
    ) -> str:
        """
        Store a new memory with optional auto-enrichment.

        Args:
            content: The memory content to store (required)
            memory_type: Type of memory (episodic, semantic, procedural)
            importance: Importance score 0.0-1.0 (default 0.5)
            tags: Comma-separated tags for categorization
            auto_extract: Auto-extract entities from content (default True)

        Returns:
            JSON with memory_id, tokens, and extracted entities
        """
        result = server.store(
            content=content,
            memory_type=memory_type,
            importance=max(0.0, min(1.0, importance)),
            tags=tags,
            auto_extract=auto_extract,
        )
        return json.dumps(result, indent=2, ensure_ascii=False)

    @mcp.tool()
    def consolidate(
        time_range_days: int = 7,
        force: bool = False,
    ) -> str:
        """
        Run memory consolidation to extract entities and beliefs from recent memories.

        Args:
            time_range_days: How many recent days of memories to process (1-60)
            force: Process beyond the recent window even if already consolidated

        Returns:
            JSON summary of entities/beliefs created
        """
        stats = server.run_consolidation(time_range_days=time_range_days, force=force)
        return json.dumps(stats, indent=2, ensure_ascii=False)

    @mcp.tool()
    def analyze_history(
        batch_size: int = 50,
        time_range: str = "all",
    ) -> str:
        """
        Process historical conversation chunks for entity/belief extraction.

        Args:
            batch_size: Number of chunks to analyze this run (1-200)
            time_range: Natural language time filter (or "all")

        Returns:
            JSON summary of processed chunks and extracted intelligence
        """
        stats = server.analyze_history(batch_size=batch_size, time_range=time_range)
        return json.dumps(stats, indent=2, ensure_ascii=False)

    @mcp.tool()
    def brief(
        time_range_days: int = 30,
        focus: str = "general strategy",
        include_history: bool = True,
        regenerate: bool = True,
    ) -> str:
        """
        Generate or fetch executive-ready summaries across recent conversations.

        Args:
            time_range_days: Window to consider for new summary generation.
            focus: Optional theme (e.g., "finance", "clients in EMEA").
            include_history: Include recent stored briefs in the response.
            regenerate: When False, skip generation and only fetch history.
        """
        result = server.generate_briefing(
            time_range_days=time_range_days,
            focus=focus,
            include_history=include_history,
            regenerate=regenerate,
        )

        payload = {
            "generated": result.get("generated"),
            "history": result.get("history") if include_history else [],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    @mcp.tool()
    def beliefs(
        subject: str = "",
        category: str = "",
        include_history: bool = False,
    ) -> str:
        """
        Query semantic beliefs, preferences, and facts.

        Args:
            subject: Filter by subject (e.g., "coding", "python", "planning")
            category: Filter by category (preference, fact, belief)
            include_history: Include superseded beliefs (default False)

        Returns:
            JSON with beliefs, confidence scores, and establishment dates
        """
        result = server.get_beliefs(
            subject=subject,
            category=category,
            include_history=include_history,
        )
        return json.dumps(result, indent=2, ensure_ascii=False)

    @mcp.tool()
    def entities(
        query: str = "",
        entity_type: str = "",
        include_relations: bool = True,
        limit: int = 10,
    ) -> str:
        """
        Query knowledge graph entities.

        Args:
            query: Search query for entity names/descriptions
            entity_type: Filter by type (person, project, technology, concept)
            include_relations: Include observations and relations (default True)
            limit: Max results (default 10)

        Returns:
            JSON with entities, their observations, and relations
        """
        result = server.query_entities(
            query=query,
            entity_type=entity_type,
            include_relations=include_relations,
            limit=limit,
        )
        return json.dumps(result, indent=2, ensure_ascii=False)

    @mcp.tool()
    def context() -> str:
        """
        Get proactive suggestions based on current session context.

        Returns contextually relevant:
        - Entity-based suggestions (related memories for mentioned entities)
        - Temporal patterns (similar timeframe memories)
        - Forgotten but relevant memories (decayed but matching context)
        - Recent activity summary

        Returns:
            JSON with suggestions and session context
        """
        result = server.get_context()
        return json.dumps(result, indent=2, ensure_ascii=False)

    @mcp.tool()
    def link(
        source_id: str,
        target_id: str,
        relation_type: str = "related_to",
    ) -> str:
        """
        Create explicit link between memories or entities.

        Args:
            source_id: Source memory/entity ID
            target_id: Target memory/entity ID
            relation_type: Type of relation (related_to, mentions, supports, contradicts)

        Returns:
            JSON with relation_id and confirmation
        """
        result = server.create_link(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
        )
        return json.dumps(result, indent=2, ensure_ascii=False)

    @mcp.tool()
    def memory_stats() -> str:
        """
        Get comprehensive memory database statistics.

        Returns:
            JSON with counts of conversations, memories, entities, beliefs, and health status
        """
        result = server.db.get_stats()
        return json.dumps(result, indent=2, ensure_ascii=False)

    return mcp


def main():
    parser = argparse.ArgumentParser(description="Unified Memory MCP Server")
    parser.add_argument("--db", default=os.environ.get("MEMORY_DB", "memory.sqlite"))
    parser.add_argument("--qdrant-url", default=os.environ.get("QDRANT_URL", "http://localhost:6333"))
    parser.add_argument("--collection", default=os.environ.get("QDRANT_COLLECTION", "memory_chunks"))
    parser.add_argument("--embed-model", default=os.environ.get("EMBED_MODEL", "text-embedding-3-small"))
    parser.add_argument("--transport", default="stdio", choices=["stdio", "sse"])
    args = parser.parse_args()

    mcp = make_mcp_server(args.db, args.qdrant_url, args.collection, args.embed_model)

    log.info(f"Starting Unified Memory MCP Server (db={args.db}, transport={args.transport})")
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
