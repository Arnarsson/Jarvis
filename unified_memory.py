#!/usr/bin/env python3
"""
Unified Memory Database Layer

Combines:
- RAG chunks (imported ChatGPT/Claude conversations)
- User-stored memories
- Knowledge graph (entities, observations, relations)
- Semantic beliefs (consolidated preferences/facts)
- Access logging for decay calculation

Uses existing memory.sqlite database, adds new tables additively.
"""

import hashlib
import json
import logging
import math
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

try:
    import tiktoken
except ImportError:
    tiktoken = None

load_dotenv()

log = logging.getLogger("unified-memory")


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def chunk_id_to_uuid(chunk_id: str) -> str:
    """Convert chunk_id to valid UUID for Qdrant."""
    if chunk_id.startswith("chunk_") or chunk_id.startswith("mem_") or chunk_id.startswith("ent_"):
        hex_str = chunk_id.split("_", 1)[1]
    else:
        hex_str = chunk_id
    hex_32 = (hex_str + "0" * 32)[:32]
    return str(uuid.UUID(hex_32))


def token_count(text: str, model: str = "text-embedding-3-small") -> int:
    if not text:
        return 0
    if tiktoken is None:
        return max(1, len(text) // 4)
    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


@dataclass
class Entity:
    """Knowledge graph node."""
    id: str
    type: str  # person, project, technology, concept, organization
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Observation:
    """Fact about an entity."""
    id: str
    entity_id: str
    content: str
    confidence: float = 1.0
    source: str = "user"
    timestamp: str = ""


@dataclass
class Relation:
    """Connection between entities/memories."""
    id: str
    from_id: str
    from_type: str  # entity, memory, chunk
    to_id: str
    to_type: str
    relation_type: str  # related_to, mentions, works_on, prefers, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""


@dataclass
class SemanticBelief:
    """Consolidated belief/preference/fact."""
    id: str
    fact: str
    subject: str
    category: str  # preference, fact, belief
    confidence: float = 0.8
    source_memories: List[str] = field(default_factory=list)
    ts_established: str = ""
    ts_last_verified: str = ""
    superseded_by: Optional[str] = None


@dataclass
class ExecutiveBrief:
    """High-level executive summary."""
    id: str
    period_label: str
    scope: str
    summary: str
    highlights: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    opportunities: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    notable_entities: List[str] = field(default_factory=list)
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class UnifiedMemoryDB:
    """
    Unified memory database with knowledge graph support.

    Extends existing SQLite schema with:
    - entities: Knowledge graph nodes
    - observations: Facts about entities
    - relations: Connections between any nodes
    - semantic_beliefs: Consolidated preferences/facts
    - access_log: For decay calculation
    - change_log: Audit trail
    """

    def __init__(
        self,
        db_path: str,
        qdrant_url: str = "http://localhost:6333",
        collection: str = "memory_chunks",
        embed_model: str = "text-embedding-3-small",
    ):
        self.db_path = db_path
        self.qdrant_url = qdrant_url
        self.collection = collection
        self.embed_model = embed_model

        self.semantic_enabled = True
        self.openai: Optional[OpenAI] = None
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            log.warning("OPENAI_API_KEY not set; semantic retrieval disabled.")
            self.semantic_enabled = False
        else:
            try:
                self.openai = OpenAI()
            except Exception as exc:
                log.warning(f"OpenAI client unavailable: {exc}")
                self.semantic_enabled = False

        try:
            self.qdrant = QdrantClient(url=qdrant_url)
        except Exception as exc:
            log.warning(f"Qdrant unavailable ({exc}); vector search disabled.")
            self.qdrant = None

        self._ensure_schema()
        if self.qdrant and self.semantic_enabled and self.openai:
            self._ensure_collection()
        else:
            log.warning("Skipping Qdrant collection ensure; semantic stack unavailable.")

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        """Create all required tables (additive - doesn't modify existing)."""
        conn = self._get_conn()
        cur = conn.cursor()

        # ============================================================
        # EXISTING TABLES (from mcp_memory.py) - just ensure they exist
        # ============================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS rag_chunks (
            chunk_id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            title TEXT,
            ts_start TEXT,
            ts_end TEXT,
            msg_start_id TEXT,
            msg_end_id TEXT,
            token_count INTEGER NOT NULL,
            text TEXT NOT NULL,
            embedded INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            memory_id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            tags TEXT,
            importance REAL DEFAULT 0.5,
            metadata TEXT,
            token_count INTEGER NOT NULL,
            embedded INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT
        )
        """)

        cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts USING fts5(
            chunk_id UNINDEXED,
            title,
            text
        )
        """)

        cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            memory_id UNINDEXED,
            content,
            tags
        )
        """)

        # ============================================================
        # NEW TABLES - Knowledge Graph
        # ============================================================

        # Entities (knowledge graph nodes)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            normalized_name TEXT,
            properties TEXT NOT NULL DEFAULT '{}',
            description TEXT,
            first_seen TEXT,
            last_seen TEXT,
            mention_count INTEGER DEFAULT 0,
            importance REAL DEFAULT 0.5,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(normalized_name)")

        # Observations (facts about entities)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id TEXT PRIMARY KEY,
            entity_id TEXT NOT NULL,
            content TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 1.0,
            source TEXT NOT NULL,
            source_memory_id TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (entity_id) REFERENCES entities(id)
        )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_observations_entity ON observations(entity_id)")

        # Relations (edges in the graph)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS relations (
            id TEXT PRIMARY KEY,
            from_id TEXT NOT NULL,
            from_type TEXT NOT NULL,
            to_id TEXT NOT NULL,
            to_type TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            strength REAL DEFAULT 0.5,
            metadata TEXT NOT NULL DEFAULT '{}',
            evidence_memories TEXT DEFAULT '[]',
            created_at TEXT NOT NULL
        )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_relations_from ON relations(from_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_relations_to ON relations(to_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(relation_type)")

        # Semantic beliefs (consolidated preferences/facts)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS semantic_beliefs (
            id TEXT PRIMARY KEY,
            fact TEXT NOT NULL,
            subject TEXT,
            category TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.8,
            source_memories TEXT DEFAULT '[]',
            ts_established TEXT NOT NULL,
            ts_last_verified TEXT,
            ts_superseded TEXT,
            superseded_by TEXT
        )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_beliefs_subject ON semantic_beliefs(subject)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_beliefs_category ON semantic_beliefs(category)")

        # Access log (for decay calculation)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS access_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id TEXT NOT NULL,
            memory_type TEXT NOT NULL,
            access_type TEXT NOT NULL,
            context TEXT,
            ts_accessed TEXT NOT NULL
        )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_access_memory ON access_log(memory_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_access_time ON access_log(ts_accessed)")

        # Change log (audit trail)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS change_log (
            id TEXT PRIMARY KEY,
            entity_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL
        )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_changelog_entity ON change_log(entity_id)")

        # Executive briefs
        cur.execute("""
        CREATE TABLE IF NOT EXISTS executive_briefs (
            brief_id TEXT PRIMARY KEY,
            period_label TEXT NOT NULL,
            scope TEXT,
            summary TEXT NOT NULL,
            highlights TEXT,
            risks TEXT,
            opportunities TEXT,
            recommendations TEXT,
            notable_entities TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL
        )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_briefs_created ON executive_briefs(created_at)")

        # FTS for entities
        cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
            id UNINDEXED,
            name,
            description,
            properties
        )
        """)

        # FTS for beliefs
        cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS beliefs_fts USING fts5(
            id UNINDEXED,
            fact,
            subject
        )
        """)

        conn.commit()
        conn.close()
        log.info(f"Schema initialized at {self.db_path}")

    def _ensure_collection(self):
        """Ensure Qdrant collection exists."""
        if not self.qdrant or not self.semantic_enabled or not self.openai:
            log.warning("Cannot ensure collection: Qdrant/OpenAI unavailable.")
            return
        try:
            self.qdrant.get_collection(self.collection)
        except Exception:
            probe = self.openai.embeddings.create(model=self.embed_model, input="probe")
            dim = len(probe.data[0].embedding)
            log.info(f"Creating Qdrant collection {self.collection} with dim={dim}")
            self.qdrant.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )

    def _embed_text(self, text: str) -> List[float]:
        """Get embedding for text."""
        if not self.semantic_enabled or not self.openai:
            raise RuntimeError("OpenAI embeddings unavailable; set OPENAI_API_KEY to enable semantic search.")
        resp = self.openai.embeddings.create(model=self.embed_model, input=text)
        return resp.data[0].embedding

    def _log_change(self, entity_id: str, operation: str, old_value: Any, new_value: Any, source: str):
        """Log a change for audit trail."""
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO change_log (id, entity_id, operation, old_value, new_value, timestamp, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            entity_id,
            operation,
            json.dumps(old_value) if old_value else None,
            json.dumps(new_value) if new_value else None,
            datetime.now().isoformat(),
            source,
        ))
        conn.commit()
        conn.close()

    def log_access(self, memory_id: str, memory_type: str, access_type: str = "recall", context: str = ""):
        """Log memory access for decay calculation."""
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO access_log (memory_id, memory_type, access_type, context, ts_accessed)
            VALUES (?, ?, ?, ?, ?)
        """, (memory_id, memory_type, access_type, context, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    # ============================================================
    # ENTITY OPERATIONS
    # ============================================================

    def create_entity(
        self,
        name: str,
        entity_type: str,
        properties: Optional[Dict[str, Any]] = None,
        description: str = "",
    ) -> Entity:
        """Create a new entity in the knowledge graph."""
        entity_id = "ent_" + sha1(f"{entity_type}:{name.lower()}")
        now = datetime.now().isoformat()
        normalized = name.lower().strip()

        conn = self._get_conn()
        cur = conn.cursor()

        # Check if exists
        cur.execute("SELECT id FROM entities WHERE id = ?", (entity_id,))
        if cur.fetchone():
            # Update mention count and last_seen
            cur.execute("""
                UPDATE entities SET mention_count = mention_count + 1, last_seen = ?, updated_at = ?
                WHERE id = ?
            """, (now, now, entity_id))
            conn.commit()
            conn.close()
            return self.get_entity(entity_id)

        # Insert new entity
        cur.execute("""
            INSERT INTO entities (id, type, name, normalized_name, properties, description,
                                  first_seen, last_seen, mention_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (
            entity_id,
            entity_type,
            name,
            normalized,
            json.dumps(properties or {}),
            description,
            now,
            now,
            now,
            now,
        ))

        # Add to FTS
        cur.execute("""
            INSERT INTO entities_fts (id, name, description, properties)
            VALUES (?, ?, ?, ?)
        """, (entity_id, name, description, json.dumps(properties or {})))

        conn.commit()
        conn.close()

        self._log_change(entity_id, "create", None, {"type": entity_type, "name": name}, "system")

        return Entity(
            id=entity_id,
            type=entity_type,
            name=name,
            properties=properties or {},
            created_at=now,
            updated_at=now,
        )

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get entity by ID."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return None

        return Entity(
            id=row["id"],
            type=row["type"],
            name=row["name"],
            properties=json.loads(row["properties"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def find_entity_by_name(self, name: str, entity_type: str = None) -> Optional[Entity]:
        """Find entity by name (fuzzy match)."""
        normalized = name.lower().strip()
        conn = self._get_conn()
        cur = conn.cursor()

        if entity_type:
            cur.execute("""
                SELECT * FROM entities WHERE normalized_name = ? AND type = ?
            """, (normalized, entity_type))
        else:
            cur.execute("SELECT * FROM entities WHERE normalized_name = ?", (normalized,))

        row = cur.fetchone()
        conn.close()

        if not row:
            return None

        return Entity(
            id=row["id"],
            type=row["type"],
            name=row["name"],
            properties=json.loads(row["properties"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def search_entities(self, query: str, entity_type: str = None, limit: int = 20) -> List[Entity]:
        """Search entities using FTS."""
        conn = self._get_conn()
        cur = conn.cursor()

        # FTS search
        sanitized = " ".join(query.split())
        if not sanitized:
            return []

        cur.execute("""
            SELECT DISTINCT e.* FROM entities e
            JOIN entities_fts fts ON e.id = fts.id
            WHERE entities_fts MATCH ?
            LIMIT ?
        """, (sanitized, limit))

        results = []
        for row in cur.fetchall():
            if entity_type and row["type"] != entity_type:
                continue
            results.append(Entity(
                id=row["id"],
                type=row["type"],
                name=row["name"],
                properties=json.loads(row["properties"] or "{}"),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            ))

        conn.close()
        return results

    # ============================================================
    # OBSERVATION OPERATIONS
    # ============================================================

    def add_observation(
        self,
        entity_id: str,
        content: str,
        confidence: float = 1.0,
        source: str = "user",
        source_memory_id: str = None,
    ) -> Observation:
        """Add an observation (fact) to an entity."""
        obs_id = "obs_" + sha1(f"{entity_id}:{content}:{time.time()}")
        now = datetime.now().isoformat()

        conn = self._get_conn()
        conn.execute("""
            INSERT INTO observations (id, entity_id, content, confidence, source, source_memory_id, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (obs_id, entity_id, content, confidence, source, source_memory_id, now))
        conn.commit()
        conn.close()

        self._log_change(entity_id, "add_observation", None, {"content": content}, source)

        return Observation(
            id=obs_id,
            entity_id=entity_id,
            content=content,
            confidence=confidence,
            source=source,
            timestamp=now,
        )

    def get_observations(self, entity_id: str) -> List[Observation]:
        """Get all observations for an entity."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM observations WHERE entity_id = ? ORDER BY timestamp DESC
        """, (entity_id,))

        results = []
        for row in cur.fetchall():
            results.append(Observation(
                id=row["id"],
                entity_id=row["entity_id"],
                content=row["content"],
                confidence=row["confidence"],
                source=row["source"],
                timestamp=row["timestamp"],
            ))

        conn.close()
        return results

    # ============================================================
    # RELATION OPERATIONS
    # ============================================================

    def create_relation(
        self,
        from_id: str,
        from_type: str,
        to_id: str,
        to_type: str,
        relation_type: str,
        strength: float = 0.5,
        metadata: Dict[str, Any] = None,
        evidence_memories: List[str] = None,
    ) -> Relation:
        """Create a relation between two nodes."""
        rel_id = "rel_" + sha1(f"{from_id}:{to_id}:{relation_type}")
        now = datetime.now().isoformat()

        conn = self._get_conn()
        cur = conn.cursor()

        # Check if exists
        cur.execute("SELECT id FROM relations WHERE id = ?", (rel_id,))
        if cur.fetchone():
            # Update strength
            cur.execute("""
                UPDATE relations SET strength = MIN(1.0, strength + 0.1) WHERE id = ?
            """, (rel_id,))
            conn.commit()
            conn.close()
            return self.get_relation(rel_id)

        cur.execute("""
            INSERT INTO relations (id, from_id, from_type, to_id, to_type, relation_type,
                                   strength, metadata, evidence_memories, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rel_id,
            from_id,
            from_type,
            to_id,
            to_type,
            relation_type,
            strength,
            json.dumps(metadata or {}),
            json.dumps(evidence_memories or []),
            now,
        ))
        conn.commit()
        conn.close()

        return Relation(
            id=rel_id,
            from_id=from_id,
            from_type=from_type,
            to_id=to_id,
            to_type=to_type,
            relation_type=relation_type,
            metadata=metadata or {},
            created_at=now,
        )

    def get_relation(self, rel_id: str) -> Optional[Relation]:
        """Get relation by ID."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM relations WHERE id = ?", (rel_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return None

        return Relation(
            id=row["id"],
            from_id=row["from_id"],
            from_type=row["from_type"],
            to_id=row["to_id"],
            to_type=row["to_type"],
            relation_type=row["relation_type"],
            metadata=json.loads(row["metadata"] or "{}"),
            created_at=row["created_at"],
        )

    def get_relations(self, node_id: str, direction: str = "both") -> List[Relation]:
        """Get all relations for a node."""
        conn = self._get_conn()
        cur = conn.cursor()

        if direction == "outgoing":
            cur.execute("SELECT * FROM relations WHERE from_id = ?", (node_id,))
        elif direction == "incoming":
            cur.execute("SELECT * FROM relations WHERE to_id = ?", (node_id,))
        else:
            cur.execute("SELECT * FROM relations WHERE from_id = ? OR to_id = ?", (node_id, node_id))

        results = []
        for row in cur.fetchall():
            results.append(Relation(
                id=row["id"],
                from_id=row["from_id"],
                from_type=row["from_type"],
                to_id=row["to_id"],
                to_type=row["to_type"],
                relation_type=row["relation_type"],
                metadata=json.loads(row["metadata"] or "{}"),
                created_at=row["created_at"],
            ))

        conn.close()
        return results

    # ============================================================
    # SEMANTIC BELIEF OPERATIONS
    # ============================================================

    def store_belief(
        self,
        fact: str,
        subject: str,
        category: str,
        confidence: float = 0.8,
        source_memories: List[str] = None,
    ) -> SemanticBelief:
        """Store or update a semantic belief."""
        belief_id = "belief_" + sha1(f"{subject}:{fact}")
        now = datetime.now().isoformat()

        conn = self._get_conn()
        cur = conn.cursor()

        # Check for existing belief about same subject
        cur.execute("""
            SELECT id, fact, confidence FROM semantic_beliefs
            WHERE subject = ? AND ts_superseded IS NULL
            ORDER BY ts_established DESC LIMIT 1
        """, (subject,))
        existing = cur.fetchone()

        if existing and existing["id"] != belief_id:
            # Check if this contradicts existing belief
            # For now, just supersede if different
            cur.execute("""
                UPDATE semantic_beliefs SET ts_superseded = ?, superseded_by = ?
                WHERE id = ?
            """, (now, belief_id, existing["id"]))

        # Insert or update
        cur.execute("""
            INSERT OR REPLACE INTO semantic_beliefs
            (id, fact, subject, category, confidence, source_memories, ts_established, ts_last_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            belief_id,
            fact,
            subject,
            category,
            confidence,
            json.dumps(source_memories or []),
            now,
            now,
        ))

        # Add to FTS
        try:
            cur.execute("DELETE FROM beliefs_fts WHERE id = ?", (belief_id,))
            cur.execute("""
                INSERT INTO beliefs_fts (id, fact, subject) VALUES (?, ?, ?)
            """, (belief_id, fact, subject))
        except:
            pass

        conn.commit()
        conn.close()

        return SemanticBelief(
            id=belief_id,
            fact=fact,
            subject=subject,
            category=category,
            confidence=confidence,
            source_memories=source_memories or [],
            ts_established=now,
            ts_last_verified=now,
        )

    def get_beliefs(
        self,
        subject: str = None,
        category: str = None,
        include_superseded: bool = False,
    ) -> List[SemanticBelief]:
        """Get beliefs, optionally filtered."""
        conn = self._get_conn()
        cur = conn.cursor()

        query = "SELECT * FROM semantic_beliefs WHERE 1=1"
        params = []

        if subject:
            query += " AND subject LIKE ?"
            params.append(f"%{subject}%")

        if category:
            query += " AND category = ?"
            params.append(category)

        if not include_superseded:
            query += " AND ts_superseded IS NULL"

        query += " ORDER BY ts_established DESC"

        cur.execute(query, params)

        results = []
        for row in cur.fetchall():
            results.append(SemanticBelief(
                id=row["id"],
                fact=row["fact"],
                subject=row["subject"],
                category=row["category"],
                confidence=row["confidence"],
                source_memories=json.loads(row["source_memories"] or "[]"),
                ts_established=row["ts_established"],
                ts_last_verified=row["ts_last_verified"],
                superseded_by=row["superseded_by"],
            ))

        conn.close()
        return results

    # ============================================================
    # IMPORTANCE DECAY
    # ============================================================

    def calculate_decay_score(self, memory_id: str, base_importance: float = 0.5) -> float:
        """
        Calculate effective importance using Ebbinghaus forgetting curve.

        Formula: effective = base * decay_factor * reinforcement_bonus
        Where:
        - decay_factor = exp(-0.1 * days / retention_strength)
        - retention_strength = 1 + (importance * 2)
        - reinforcement_bonus = 1 + log(1 + access_count) * 0.1
        """
        conn = self._get_conn()
        cur = conn.cursor()

        # Get access count and last access time
        cur.execute("""
            SELECT COUNT(*) as count, MAX(ts_accessed) as last_access
            FROM access_log WHERE memory_id = ?
        """, (memory_id,))
        row = cur.fetchone()
        conn.close()

        access_count = row["count"] if row["count"] else 0
        last_access = row["last_access"]

        if not last_access:
            # Never accessed - use creation time, apply base decay
            days_since = 30  # Assume old
        else:
            try:
                last_dt = datetime.fromisoformat(last_access.replace("Z", "+00:00"))
                days_since = (datetime.now() - last_dt.replace(tzinfo=None)).days
            except:
                days_since = 30

        # Retention strength based on importance
        retention_strength = 1 + (base_importance * 2)

        # Decay factor (Ebbinghaus curve)
        decay_factor = math.exp(-0.1 * days_since / retention_strength)

        # Reinforcement bonus from access
        reinforcement_bonus = 1 + math.log(1 + access_count) * 0.1

        return base_importance * decay_factor * reinforcement_bonus

    # ============================================================
    # STATISTICS
    # ============================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive database statistics."""
        conn = self._get_conn()
        cur = conn.cursor()

        stats = {}

        # Existing tables
        cur.execute("SELECT COUNT(*) FROM rag_chunks")
        stats["imported_conversations"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM memories")
        stats["stored_memories"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM rag_chunks WHERE embedded = 1")
        embedded_chunks = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM memories WHERE embedded = 1")
        embedded_memories = cur.fetchone()[0]

        stats["total_embedded"] = embedded_chunks + embedded_memories

        # Knowledge graph
        cur.execute("SELECT COUNT(*) FROM entities")
        stats["entities"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM observations")
        stats["observations"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM relations")
        stats["relations"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM semantic_beliefs WHERE ts_superseded IS NULL")
        stats["active_beliefs"] = cur.fetchone()[0]

        # Entity types breakdown
        cur.execute("SELECT type, COUNT(*) as count FROM entities GROUP BY type")
        stats["entity_types"] = {row["type"]: row["count"] for row in cur.fetchall()}

        conn.close()
        stats["status"] = "healthy"

        return stats

    # ============================================================
    # EXECUTIVE BRIEFS
    # ============================================================

    def store_executive_brief(
        self,
        period_label: str,
        scope: str,
        summary: str,
        highlights: Optional[List[str]] = None,
        risks: Optional[List[str]] = None,
        opportunities: Optional[List[str]] = None,
        recommendations: Optional[List[str]] = None,
        notable_entities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExecutiveBrief:
        """Persist an executive brief."""
        brief_id = "brief_" + sha1(f"{period_label}:{scope}:{datetime.now().isoformat()}")
        now = datetime.now().isoformat()

        conn = self._get_conn()
        conn.execute("""
            INSERT INTO executive_briefs (
                brief_id, period_label, scope, summary,
                highlights, risks, opportunities, recommendations,
                notable_entities, metadata, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            brief_id,
            period_label,
            scope,
            summary,
            json.dumps(highlights or []),
            json.dumps(risks or []),
            json.dumps(opportunities or []),
            json.dumps(recommendations or []),
            json.dumps(notable_entities or []),
            json.dumps(metadata or {}),
            now,
        ))
        conn.commit()
        conn.close()

        return ExecutiveBrief(
            id=brief_id,
            period_label=period_label,
            scope=scope,
            summary=summary,
            highlights=highlights or [],
            risks=risks or [],
            opportunities=opportunities or [],
            recommendations=recommendations or [],
            notable_entities=notable_entities or [],
            created_at=now,
            metadata=metadata or {},
        )

    def get_executive_briefs(self, limit: int = 5) -> List[ExecutiveBrief]:
        """Fetch most recent executive briefs."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT *
            FROM executive_briefs
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        results = []
        for row in cur.fetchall():
            results.append(ExecutiveBrief(
                id=row["brief_id"],
                period_label=row["period_label"],
                scope=row["scope"],
                summary=row["summary"],
                highlights=json.loads(row["highlights"] or "[]"),
                risks=json.loads(row["risks"] or "[]"),
                opportunities=json.loads(row["opportunities"] or "[]"),
                recommendations=json.loads(row["recommendations"] or "[]"),
                notable_entities=json.loads(row["notable_entities"] or "[]"),
                created_at=row["created_at"],
                metadata=json.loads(row["metadata"] or "{}"),
            ))
        conn.close()
        return results

    def collect_documents_for_brief(
        self,
        cutoff_iso: str,
        chunk_limit: int = 40,
        memory_limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Collect recent chunks and memories for briefing summaries."""
        conn = self._get_conn()
        cur = conn.cursor()
        documents: List[Dict[str, Any]] = []

        cur.execute("""
            SELECT chunk_id, title, text, ts_start
            FROM rag_chunks
            WHERE ts_start IS NOT NULL AND ts_start >= ?
            ORDER BY ts_start DESC
            LIMIT ?
        """, (cutoff_iso, chunk_limit))
        for row in cur.fetchall():
            documents.append({
                "id": row["chunk_id"],
                "title": row["title"] or "Conversation chunk",
                "content": row["text"],
                "timestamp": row["ts_start"],
                "type": "conversation",
            })

        cur.execute("""
            SELECT memory_id, content, created_at
            FROM memories
            WHERE created_at IS NOT NULL AND created_at >= ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (cutoff_iso, memory_limit))
        for row in cur.fetchall():
            documents.append({
                "id": row["memory_id"],
                "title": "Memory",
                "content": row["content"],
                "timestamp": row["created_at"],
                "type": "memory",
            })

        conn.close()

        def sort_key(doc):
            ts = doc.get("timestamp")
            if not ts:
                return ""
            return ts

        documents.sort(key=sort_key, reverse=True)
        return documents
