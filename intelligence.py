#!/usr/bin/env python3
"""
Intelligence Layer for Unified Memory System

Provides:
- Entity extraction using LLM
- Proactive memory surfacing
- Belief/preference detection
- Contradiction detection
- Temporal pattern recognition
"""

import json
import logging
import math
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from openai import OpenAI
from time_filters import TimeRange, parse_time_query, timestamp_in_range

if TYPE_CHECKING:
    from unified_memory import UnifiedMemoryDB

log = logging.getLogger("intelligence")


class IntelligenceEngine:
    """
    Intelligence layer for memory system.

    Handles:
    - LLM-based entity extraction
    - Proactive suggestion generation
    - Belief consolidation
    - Contradiction detection
    """

    def __init__(self, db: "UnifiedMemoryDB"):
        self.db = db
        self.model = "gpt-4o-mini"  # Fast and cheap for extraction
        self.enabled = True
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            log.warning("OPENAI_API_KEY not set; disabling intelligence layer.")
            self.openai = None
            self.enabled = False
        else:
            try:
                self.openai = OpenAI()
            except Exception as exc:
                log.warning(f"OpenAI client unavailable: {exc}")
                self.openai = None
                self.enabled = False

    def extract_entities(self, content: str) -> List[Dict[str, str]]:
        """
        Extract entities from content using LLM.

        Returns list of: [{name, type, context}]
        """
        if not self.enabled or not self.openai:
            return []

        if len(content) < 20:
            return []

        try:
            response = self.openai.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """Extract named entities from the text. Return JSON array with objects containing:
- name: The entity name (proper capitalization)
- type: One of: person, project, technology, concept, organization
- context: Brief context about the entity from this text (max 50 words)

Only extract concrete, specific entities. Skip generic terms.
Return empty array [] if no entities found.
Return ONLY valid JSON, no markdown.""",
                    },
                    {"role": "user", "content": content[:2000]},  # Limit input
                ],
                temperature=0.1,
                max_tokens=500,
            )

            result = response.choices[0].message.content.strip()

            # Clean up response
            if result.startswith("```"):
                result = re.sub(r"```\w*\n?", "", result).strip()

            entities = json.loads(result)

            # Validate structure
            valid_entities = []
            valid_types = {"person", "project", "technology", "concept", "organization"}

            for e in entities:
                if isinstance(e, dict) and "name" in e and "type" in e:
                    if e["type"] in valid_types and len(e["name"]) > 1:
                        valid_entities.append({
                            "name": e["name"],
                            "type": e["type"],
                            "context": e.get("context", "")[:200],
                        })

            return valid_entities[:10]  # Limit to 10 entities

        except json.JSONDecodeError as e:
            log.warning(f"Failed to parse entity extraction response: {e}")
            return []
        except Exception as e:
            log.warning(f"Entity extraction failed: {e}")
            return []

    def extract_beliefs(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract beliefs/preferences/facts from content.

        Returns list of: [{fact, subject, category, confidence}]
        """
        if not self.enabled or not self.openai:
            return []

        if len(content) < 50:
            return []

        try:
            response = self.openai.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """Extract explicit statements of preference, belief, or fact from the text.

Return JSON array with objects containing:
- fact: The belief/preference/fact statement (concise, max 100 words)
- subject: What this is about (e.g., "coding", "tools", "workflow")
- category: One of: preference, fact, belief, decision
- confidence: How confident this seems (0.5-1.0)

Only extract EXPLICIT statements, not inferences.
Skip generic statements. Focus on personal preferences and decisions.
Return empty array [] if nothing clear found.
Return ONLY valid JSON, no markdown.""",
                    },
                    {"role": "user", "content": content[:2000]},
                ],
                temperature=0.1,
                max_tokens=500,
            )

            result = response.choices[0].message.content.strip()

            if result.startswith("```"):
                result = re.sub(r"```\w*\n?", "", result).strip()

            beliefs = json.loads(result)

            valid_beliefs = []
            valid_categories = {"preference", "fact", "belief", "decision"}

            for b in beliefs:
                if isinstance(b, dict) and "fact" in b and "category" in b:
                    if b["category"] in valid_categories:
                        valid_beliefs.append({
                            "fact": b["fact"][:500],
                            "subject": b.get("subject", "general")[:100],
                            "category": b["category"],
                            "confidence": min(1.0, max(0.5, float(b.get("confidence", 0.8)))),
                        })

            return valid_beliefs[:5]  # Limit to 5 beliefs

        except json.JSONDecodeError:
            return []
        except Exception as e:
            log.warning(f"Belief extraction failed: {e}")
            return []

    def detect_contradiction(self, new_belief: str, existing_belief: str) -> bool:
        """
        Check if two beliefs contradict each other.
        """
        try:
            response = self.openai.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """Determine if these two statements contradict each other.
Return ONLY "yes" or "no".""",
                    },
                    {
                        "role": "user",
                        "content": f"Statement 1: {existing_belief}\n\nStatement 2: {new_belief}",
                    },
                ],
                temperature=0,
                max_tokens=10,
            )

            result = response.choices[0].message.content.strip().lower()
            return "yes" in result

        except Exception:
            return False

    def get_suggestions(
        self,
        recent_accessed: List[str],
        mentioned_entities: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Generate proactive memory suggestions.

        Types:
        1. Entity context - memories related to mentioned entities
        2. Temporal patterns - similar timeframe memories
        3. Forgotten relevant - decayed but potentially useful
        4. Related chains - memories connected to recently accessed
        """
        suggestions = []
        conn = self.db._get_conn()
        cur = conn.cursor()

        # 1. Entity-based suggestions
        for entity_name in mentioned_entities[:5]:
            entity = self.db.find_entity_by_name(entity_name)
            if entity:
                # Find memories mentioning this entity
                cur.execute("""
                    SELECT DISTINCT r.from_id
                    FROM relations r
                    WHERE r.to_id = ? AND r.relation_type = 'mentions'
                    ORDER BY r.created_at DESC
                    LIMIT 3
                """, (entity.id,))

                memory_ids = [row["from_id"] for row in cur.fetchall()]
                if memory_ids:
                    suggestions.append({
                        "type": "entity_context",
                        "trigger": f"You mentioned {entity.name}",
                        "entity": entity.name,
                        "related_memories": memory_ids,
                        "relevance": 0.8,
                    })

        # 2. Temporal pattern suggestions
        now = datetime.now()
        week_ago = (now - timedelta(days=7)).isoformat()

        cur.execute("""
            SELECT memory_id, content
            FROM memories
            WHERE created_at >= ?
            ORDER BY importance DESC
            LIMIT 5
        """, (week_ago,))

        recent_memories = cur.fetchall()
        if recent_memories:
            suggestions.append({
                "type": "temporal_pattern",
                "trigger": "Recent important memories",
                "memories": [{"id": r["memory_id"], "snippet": r["content"][:100]} for r in recent_memories],
                "relevance": 0.6,
            })

        # 3. Forgotten but relevant (high importance, not accessed recently)
        two_weeks_ago = (now - timedelta(days=14)).isoformat()

        cur.execute("""
            SELECT m.memory_id, m.content, m.importance
            FROM memories m
            LEFT JOIN access_log a ON m.memory_id = a.memory_id
            WHERE m.importance >= 0.7
            GROUP BY m.memory_id
            HAVING MAX(a.ts_accessed) < ? OR MAX(a.ts_accessed) IS NULL
            ORDER BY m.importance DESC
            LIMIT 3
        """, (two_weeks_ago,))

        forgotten = cur.fetchall()
        if forgotten:
            suggestions.append({
                "type": "forgotten_relevant",
                "trigger": "Important memories you haven't accessed recently",
                "memories": [
                    {"id": r["memory_id"], "snippet": r["content"][:100], "importance": r["importance"]}
                    for r in forgotten
                ],
                "relevance": 0.7,
            })

        # 4. Related chain suggestions (based on recently accessed)
        if recent_accessed:
            for mem_id in recent_accessed[-3:]:
                relations = self.db.get_relations(mem_id)
                related_ids = [r.to_id for r in relations if r.to_id not in recent_accessed][:3]

                if related_ids:
                    suggestions.append({
                        "type": "chain_continuation",
                        "trigger": f"Related to recently accessed memory",
                        "source_memory": mem_id,
                        "related_memories": related_ids,
                        "relevance": 0.65,
                    })
                    break  # Only one chain suggestion

        # 5. Belief updates (recent changes)
        cur.execute("""
            SELECT b1.id, b1.fact, b1.subject, b2.fact as old_fact
            FROM semantic_beliefs b1
            JOIN semantic_beliefs b2 ON b1.id = b2.superseded_by
            WHERE b1.ts_established >= ?
            LIMIT 3
        """, (week_ago,))

        belief_updates = cur.fetchall()
        if belief_updates:
            suggestions.append({
                "type": "belief_update",
                "trigger": "Your views have recently changed",
                "updates": [
                    {
                        "subject": r["subject"],
                        "old": r["old_fact"][:100],
                        "new": r["fact"][:100],
                    }
                    for r in belief_updates
                ],
                "relevance": 0.9,
            })

        conn.close()

        # Sort by relevance
        suggestions.sort(key=lambda x: x.get("relevance", 0), reverse=True)

        return suggestions[:5]  # Return top 5 suggestions

    def consolidate_memories(
        self,
        time_range_days: int = 7,
        force: bool = False,
        max_batch: int = 50,
    ) -> Dict[str, Any]:
        """
        Run memory consolidation:
        1. Extract entities from unconsolidated memories
        2. Extract beliefs from unconsolidated memories
        3. Create relations between related memories
        4. Update importance scores based on access patterns

        Returns summary of consolidation actions.
        """
        conn = self.db._get_conn()
        cur = conn.cursor()

        cutoff = (datetime.now() - timedelta(days=time_range_days)).isoformat()
        batch_limit = max(10, min(200, max_batch if not force else max_batch * 2))

        stats = {
            "entities_created": 0,
            "beliefs_created": 0,
            "relations_created": 0,
            "memories_processed": 0,
        }

        # Find memories to consolidate (not processed recently)
        base_query = """
            SELECT memory_id, content, importance
            FROM memories
        """
        params: List[Any] = []
        if not force:
            base_query += " WHERE created_at >= ?"
            params.append(cutoff)
        base_query += " ORDER BY importance DESC LIMIT ?"
        params.append(batch_limit)

        cur.execute(base_query, params)

        memories = cur.fetchall()

        for mem in memories:
            memory_id = mem["memory_id"]
            content = mem["content"]
            stats["memories_processed"] += 1

            # Extract and create entities
            try:
                entities = self.extract_entities(content)
                for ent in entities:
                    entity = self.db.create_entity(
                        name=ent["name"],
                        entity_type=ent["type"],
                        description=ent.get("context", ""),
                    )

                    # Link memory to entity
                    self.db.create_relation(
                        from_id=memory_id,
                        from_type="memory",
                        to_id=entity.id,
                        to_type="entity",
                        relation_type="mentions",
                    )
                    stats["entities_created"] += 1
                    stats["relations_created"] += 1
            except Exception as e:
                log.warning(f"Entity extraction failed for {memory_id}: {e}")

            # Extract and create beliefs
            try:
                beliefs = self.extract_beliefs(content)
                for belief in beliefs:
                    self.db.store_belief(
                        fact=belief["fact"],
                        subject=belief["subject"],
                        category=belief["category"],
                        confidence=belief["confidence"],
                        source_memories=[memory_id],
                    )
                    stats["beliefs_created"] += 1
            except Exception as e:
                log.warning(f"Belief extraction failed for {memory_id}: {e}")

        conn.close()

        stats["time_range_days"] = time_range_days
        stats["force"] = force
        stats["batch_limit"] = batch_limit

        return stats

    def analyze_history(
        self,
        batch_size: int = 50,
        time_filter: str = "all",
    ) -> Dict[str, Any]:
        """
        Process historical conversation chunks for entities and beliefs.
        """
        batch_size = max(1, min(200, batch_size))
        conn = self.db._get_conn()
        cur = conn.cursor()

        fetch_limit = batch_size * 3
        cur.execute("""
            SELECT chunk_id, text, ts_start, title, created_at
            FROM rag_chunks
            WHERE text IS NOT NULL
            ORDER BY created_at ASC
            LIMIT ?
        """, (fetch_limit,))
        rows = cur.fetchall()

        chunk_ids = [row["chunk_id"] for row in rows]
        processed_flags: Set[str] = set()
        if chunk_ids:
            placeholders = ",".join("?" for _ in chunk_ids)
            rel_cur = conn.cursor()
            rel_cur.execute(
                f"SELECT DISTINCT from_id FROM relations WHERE relation_type = 'mentions' AND from_id IN ({placeholders})",
                chunk_ids,
            )
            processed_flags = {row["from_id"] for row in rel_cur.fetchall()}

        conn.close()

        stats: Dict[str, Any] = {
            "chunks_considered": len(rows),
            "chunks_processed": 0,
            "chunks_skipped_processed": 0,
            "chunks_skipped_time": 0,
            "chunks_skipped_empty": 0,
            "entities_linked": 0,
            "beliefs_created": 0,
            "time_filter": time_filter,
            "time_filter_parsed": True,
        }
        processed_ids: List[str] = []

        time_range: Optional[TimeRange] = None
        if time_filter and time_filter.lower() not in {"", "all", "any"}:
            time_range = parse_time_query(time_filter)
            if time_range is None:
                stats["time_filter_parsed"] = False

        for row in rows:
            if stats["chunks_processed"] >= batch_size:
                break

            chunk_id = row["chunk_id"]
            chunk_text = (row["text"] or "").strip()

            if chunk_id in processed_flags:
                stats["chunks_skipped_processed"] += 1
                continue

            if time_range and not timestamp_in_range(row["ts_start"], time_range):
                stats["chunks_skipped_time"] += 1
                continue

            if len(chunk_text) < 40:
                stats["chunks_skipped_empty"] += 1
                continue

            stats["chunks_processed"] += 1
            processed_ids.append(chunk_id)

            try:
                entities = self.extract_entities(chunk_text)
                for ent in entities:
                    entity = self.db.create_entity(
                        name=ent["name"],
                        entity_type=ent["type"],
                        description=ent.get("context", ""),
                    )
                    self.db.create_relation(
                        from_id=chunk_id,
                        from_type="chunk",
                        to_id=entity.id,
                        to_type="entity",
                        relation_type="mentions",
                        metadata={"source": "history_analysis"},
                    )
                    stats["entities_linked"] += 1
            except Exception as e:
                log.warning(f"Historical entity extraction failed for {chunk_id}: {e}")

            try:
                beliefs = self.extract_beliefs(chunk_text)
                for belief in beliefs:
                    self.db.store_belief(
                        fact=belief["fact"],
                        subject=belief["subject"],
                        category=belief["category"],
                        confidence=belief["confidence"],
                        source_memories=[chunk_id],
                    )
                    stats["beliefs_created"] += 1
            except Exception as e:
                log.warning(f"Historical belief extraction failed for {chunk_id}: {e}")

        stats["processed_chunk_ids"] = processed_ids
        stats["requested_batch_size"] = batch_size

        return stats

    def generate_executive_brief(
        self,
        time_range_days: int = 30,
        focus: str = "general business strategy",
        chunk_limit: int = 40,
        memory_limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Create a high-level executive summary over recent data.
        """
        if not self.enabled or not self.openai:
            return {
                "message": "Intelligence engine disabled (missing OPENAI_API_KEY).",
                "generated": False,
                "brief": None,
            }

        cutoff = datetime.now() - timedelta(days=time_range_days)
        documents = self.db.collect_documents_for_brief(
            cutoff_iso=cutoff.isoformat(),
            chunk_limit=chunk_limit,
            memory_limit=memory_limit,
        )

        if not documents:
            return {
                "message": "No recent documents available",
                "generated": False,
                "brief": None,
            }

        context_blocks = []
        for doc in documents:
            snippet = doc["content"][:1000]
            context_blocks.append(
                f"[{doc['type']}] {doc.get('timestamp', 'unknown')} {doc.get('title', '')}\n{snippet}"
            )

        context_text = "\n\n".join(context_blocks)
        context_text = context_text[:15000]

        system_prompt = """You are an elite executive assistant.
Summarize the key developments, risks, and opportunities in JSON."""
        user_prompt = f"""
Time range: last {time_range_days} days (since {cutoff.date().isoformat()}).
Focus: {focus}.

Provide JSON with keys:
summary (string),
highlights (array of strings),
risks (array of strings),
opportunities (array of strings),
recommendations (array of strings),
notable_entities (array of people/projects/clients).

Context:
{context_text}
"""

        try:
            completion = self.openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=800,
            )
            content = completion.choices[0].message.content.strip()
            if content.startswith("```"):
                content = re.sub(r"```[a-zA-Z]*", "", content).strip("` \n")
            parsed = json.loads(content)
        except Exception as exc:
            log.warning(f"Executive brief generation failed: {exc}")
            return {
                "message": f"Brief generation failed: {exc}",
                "generated": False,
                "brief": None,
            }

        brief = self.db.store_executive_brief(
            period_label=f"Last {time_range_days} days",
            scope=focus,
            summary=parsed.get("summary", ""),
            highlights=parsed.get("highlights", []),
            risks=parsed.get("risks", []),
            opportunities=parsed.get("opportunities", []),
            recommendations=parsed.get("recommendations", []),
            notable_entities=parsed.get("notable_entities", []),
            metadata={
                "documents_considered": [doc["id"] for doc in documents],
                "context_size": len(context_text),
            },
        )

        return {
            "message": "Brief generated",
            "generated": True,
            "brief": {
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
            },
        }


def main():
    """Test the intelligence engine."""
    from unified_memory import UnifiedMemoryDB

    db = UnifiedMemoryDB(
        db_path="memory.sqlite",
        qdrant_url="http://localhost:6333",
        collection="memory_chunks",
    )

    engine = IntelligenceEngine(db)

    # Test entity extraction
    test_content = """
    I've been working on the FastAPI project with Sarah.
    We decided to use PostgreSQL instead of MongoDB because of better
    transaction support. The frontend team is using React with TypeScript.
    """

    print("Testing entity extraction...")
    entities = engine.extract_entities(test_content)
    print(f"Extracted entities: {json.dumps(entities, indent=2)}")

    print("\nTesting belief extraction...")
    beliefs = engine.extract_beliefs(test_content)
    print(f"Extracted beliefs: {json.dumps(beliefs, indent=2)}")

    print("\nTesting suggestions...")
    suggestions = engine.get_suggestions([], [])
    print(f"Suggestions: {json.dumps(suggestions, indent=2)}")


if __name__ == "__main__":
    main()
