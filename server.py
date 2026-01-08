import argparse
import json
import logging
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from fastmcp import FastMCP
from qdrant_client import QdrantClient
from openai import OpenAI
from score_utils import normalize_scores


logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("mcp")


def ensure_tables(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
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
    CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts USING fts5(
        chunk_id UNINDEXED,
        title,
        text
    )
    """)
    conn.commit()


def fts_search(conn: sqlite3.Connection, query: str, limit: int) -> Dict[str, float]:
    # Sanitize query for FTS5: remove special characters that cause syntax errors
    import re
    sanitized = re.sub(r'[^\w\s]', ' ', query)  # Keep only alphanumeric and spaces
    sanitized = ' '.join(sanitized.split())  # Normalize whitespace
    if not sanitized:
        return {}

    cur = conn.cursor()
    try:
        cur.execute("""
          SELECT chunk_id, bm25(rag_chunks_fts) AS bm
          FROM rag_chunks_fts
          WHERE rag_chunks_fts MATCH ?
          LIMIT ?
        """, (sanitized, limit))
    except Exception:
        return {}  # Fallback to empty on any FTS error
    raw_scores: Dict[str, float] = {}
    for cid, bm in cur.fetchall():
        raw_scores[cid] = float(bm)
    return normalize_scores(raw_scores)


def fetch_chunk(conn: sqlite3.Connection, chunk_id: str) -> Optional[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute("""
      SELECT chunk_id, thread_id, title, ts_start, ts_end, token_count, text
      FROM rag_chunks
      WHERE chunk_id = ?
    """, (chunk_id,))
    row = cur.fetchone()
    if not row:
        return None
    return {
        "chunk_id": row[0],
        "thread_id": row[1],
        "title": row[2] or "Memory chunk",
        "ts_start": row[3],
        "ts_end": row[4],
        "token_count": row[5],
        "text": row[6],
    }


def hybrid_search(
    db_path: str,
    qdrant_url: str,
    collection: str,
    embed_model: str,
    base_url: str,
    query: str,
    k: int = 8,
) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    ensure_tables(conn)

    # lexical
    lex = fts_search(conn, query, limit=20)

    # semantic
    sem_norm: Dict[str, float] = {}
    try:
        oc = OpenAI()
        qd = QdrantClient(url=qdrant_url)
        emb = oc.embeddings.create(model=embed_model, input=query).data[0].embedding
        sem_hits = qd.query_points(collection_name=collection, query=emb, limit=20, with_payload=True).points
        # Use chunk_id from payload, not the UUID id
        sem = {h.payload.get("chunk_id", str(h.id)): float(h.score) for h in sem_hits}
        sem_norm = normalize_scores(sem)
    except Exception as exc:
        log.warning("Semantic retrieval fallback (lexical only): %s", exc)
        sem_norm = {}
    lex_norm = normalize_scores(lex)

    # combine
    w_sem, w_lex = 0.60, 0.40
    cands = set(lex_norm.keys()) | set(sem_norm.keys())
    ranked: List[Tuple[str, float]] = []
    for cid in cands:
        ranked.append((cid, w_sem * sem_norm.get(cid, 0.0) + w_lex * lex_norm.get(cid, 0.0)))
    ranked.sort(key=lambda x: x[1], reverse=True)
    ranked = ranked[:k]

    out: List[Dict[str, Any]] = []
    for cid, score in ranked:
        ch = fetch_chunk(conn, cid)
        if not ch:
            continue
        out.append({
            "id": cid,
            "title": ch["title"],
            "url": f"{base_url.rstrip('/')}/chunk/{cid}",
            "_score": score,
        })

    conn.close()
    return out


def make_app(db_path: str, qdrant_url: str, collection: str, embed_model: str, base_url: str) -> FastMCP:
    mcp = FastMCP(
        name="Unified Chat Memory",
        instructions="Merged ChatGPT + Claude memory. Use search() then fetch(id).",
    )

    @mcp.tool()
    async def search(query: str) -> Dict[str, Any]:
        query = (query or "").strip()
        results = []
        if query:
            hits = hybrid_search(db_path, qdrant_url, collection, embed_model, base_url, query, k=8)
            results = [{"id": h["id"], "title": h["title"], "url": h["url"]} for h in hits]

        # Required by OpenAI MCP docs: content array + JSON-encoded string.
        payload = {"results": results}
        return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}

    @mcp.tool()
    async def fetch(id: str) -> Dict[str, Any]:
        conn = sqlite3.connect(db_path)
        ensure_tables(conn)
        ch = fetch_chunk(conn, id)
        conn.close()

        if not ch:
            doc = {
                "id": id,
                "title": "Not found",
                "text": "No chunk found for this id.",
                "url": f"{base_url.rstrip('/')}/chunk/{id}",
                "metadata": {"error": "not_found"},
            }
        else:
            doc = {
                "id": ch["chunk_id"],
                "title": ch["title"],
                "text": ch["text"],
                "url": f"{base_url.rstrip('/')}/chunk/{ch['chunk_id']}",
                "metadata": {
                    "thread_id": ch["thread_id"],
                    "ts_start": ch["ts_start"],
                    "ts_end": ch["ts_end"],
                    "token_count": ch["token_count"],
                },
            }

        return {"content": [{"type": "text", "text": json.dumps(doc, ensure_ascii=False)}]}

    return mcp


def main():
    load_dotenv()

    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--qdrant-url", default=os.environ.get("QDRANT_URL", "http://localhost:6333"))
    ap.add_argument("--collection", default=os.environ.get("QDRANT_COLLECTION", "memory_chunks"))
    ap.add_argument("--embed-model", default=os.environ.get("EMBED_MODEL", "text-embedding-3-small"))
    ap.add_argument("--base-url", default=os.environ.get("PUBLIC_BASE_URL", "https://example.com"))
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--transport", default="sse", choices=["sse", "http", "stdio"])
    args = ap.parse_args()

    app = make_app(args.db, args.qdrant_url, args.collection, args.embed_model, args.base_url)
    log.info("Serving MCP transport=%s host=%s port=%d", args.transport, args.host, args.port)
    app.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
