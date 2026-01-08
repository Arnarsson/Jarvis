import argparse
import hashlib
import logging
import os
import sqlite3
import time
import uuid
from typing import Dict, List, Tuple, Optional

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

from openai import OpenAI

try:
    import tiktoken
except Exception:
    tiktoken = None


logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("indexer")


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def chunk_id_to_uuid(chunk_id: str) -> str:
    """Convert chunk_id (chunk_<sha1>) to valid UUID for Qdrant."""
    # Extract the SHA1 hash from chunk_id
    if chunk_id.startswith("chunk_"):
        hex_str = chunk_id[6:]  # Remove "chunk_" prefix
    else:
        hex_str = chunk_id

    # SHA1 is 40 hex chars, UUID needs 32 hex chars
    # Take first 32 chars and format as UUID
    hex_32 = hex_str[:32]
    return str(uuid.UUID(hex_32))


def token_count(text: str, model: str) -> int:
    if not text:
        return 0
    if tiktoken is None:
        # rough fallback
        return max(1, len(text) // 4)
    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


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
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rag_chunks_thread ON rag_chunks(thread_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedded ON rag_chunks(embedded)")

    # FTS over chunks for fast lexical matching
    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts USING fts5(
        chunk_id UNINDEXED,
        title,
        text
    )
    """)
    conn.commit()


def detect_message_schema(conn: sqlite3.Connection) -> Dict[str, str]:
    """
    chat-export-structurer uses a messages table; names may evolve.
    We detect common column names so you don't have to hand-edit.
    """
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(messages)")
    cols = [r[1] for r in cur.fetchall()]
    low = {c.lower(): c for c in cols}

    def pick(*names: str) -> str:
        for n in names:
            if n.lower() in low:
                return low[n.lower()]
        raise RuntimeError(f"Missing columns. Tried {names}. Have: {cols}")

    schema = {
        "message_id": pick("message_id", "id"),
        "thread_id": pick("canonical_thread_id", "thread_id", "conversation_id"),
        "role": pick("role", "author_role", "sender"),
        "text": pick("text", "content", "message"),
        "ts": pick("ts", "timestamp", "created_at", "time"),
    }
    # title is optional
    for cand in ("title", "thread_title", "conversation_title"):
        if cand in low:
            schema["title"] = low[cand]
            break
    log.info("Detected message schema: %s", schema)
    return schema


def upsert_chunk_fts(conn: sqlite3.Connection, chunk_id: str, title: str, text: str) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM rag_chunks_fts WHERE chunk_id = ?", (chunk_id,))
    cur.execute("INSERT INTO rag_chunks_fts(chunk_id, title, text) VALUES(?,?,?)", (chunk_id, title, text))


def build_chunks(db_path: str, max_tokens: int, overlap_msgs: int, min_tokens: int, token_model: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ensure_tables(conn)
    s = detect_message_schema(conn)

    q = f"""
    SELECT
      {s["thread_id"]} AS thread_id,
      {s["message_id"]} AS message_id,
      {s["role"]} AS role,
      {s["text"]} AS text,
      {s["ts"]} AS ts
      {"," + s["title"] + " AS title" if "title" in s else ""}
    FROM messages
    WHERE {s["text"]} IS NOT NULL AND TRIM({s["text"]}) != ''
    ORDER BY thread_id, ts
    """
    cur = conn.cursor()
    cur.execute(q)
    rows = cur.fetchall()

    # group by thread
    threads: Dict[str, List[sqlite3.Row]] = {}
    for r in rows:
        threads.setdefault(r["thread_id"], []).append(r)

    log.info("Threads: %d | Messages: %d", len(threads), len(rows))

    inserted = 0
    now = int(time.time())

    for thread_id, msgs in threads.items():
        title = (msgs[0]["title"] if "title" in msgs[0].keys() else None) or f"Thread {thread_id}"

        window: List[sqlite3.Row] = []
        window_tokens = 0

        def window_text(ws: List[sqlite3.Row]) -> str:
            parts = []
            for m in ws:
                role = (m["role"] or "").strip().upper()
                txt = (m["text"] or "").strip()
                if txt:
                    parts.append(f"{role}: {txt}")
            return "\n\n".join(parts).strip()

        def flush():
            nonlocal inserted, window, window_tokens
            if not window:
                return
            if window_tokens < min_tokens and len(msgs) > len(window):
                return

            txt = window_text(window)
            if not txt:
                window, window_tokens = [], 0
                return

            msg_start_id = window[0]["message_id"]
            msg_end_id = window[-1]["message_id"]
            ts_start = window[0]["ts"]
            ts_end = window[-1]["ts"]

            cid = "chunk_" + sha1(f"{thread_id}|{msg_start_id}|{msg_end_id}|{len(txt)}")
            tc = token_count(txt, token_model)

            conn.execute("""
              INSERT OR IGNORE INTO rag_chunks(
                chunk_id, thread_id, title, ts_start, ts_end,
                msg_start_id, msg_end_id, token_count, text, embedded, created_at
              ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """, (cid, thread_id, title, ts_start, ts_end, msg_start_id, msg_end_id, tc, txt, 0, now))

            upsert_chunk_fts(conn, cid, title, txt)
            conn.commit()
            inserted += 1

            # overlap
            if overlap_msgs > 0:
                window = window[-overlap_msgs:]
                window_tokens = token_count(window_text(window), token_model)
            else:
                window, window_tokens = [], 0

        for m in msgs:
            piece = f"{(m['role'] or '').strip().upper()}: {(m['text'] or '').strip()}"
            pt = token_count(piece, token_model)

            if pt >= max_tokens:
                flush()
                window = [m]
                window_tokens = pt
                flush()
                continue

            if window_tokens + pt > max_tokens:
                flush()

            window.append(m)
            window_tokens += pt

        flush()

    log.info("Chunks created: %d", inserted)
    conn.close()


def ensure_collection(q: QdrantClient, collection: str, vec_size: int) -> None:
    try:
        q.get_collection(collection)
        return
    except Exception:
        log.info("Creating Qdrant collection=%s size=%d", collection, vec_size)
        q.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=vec_size, distance=Distance.COSINE),
        )


def embed(db_path: str, qdrant_url: str, collection: str, embed_model: str, batch_size: int) -> None:
    client = OpenAI()
    q = QdrantClient(url=qdrant_url)

    # dimension probe
    probe = client.embeddings.create(model=embed_model, input="probe")
    dim = len(probe.data[0].embedding)
    ensure_collection(q, collection, dim)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ensure_tables(conn)

    cur = conn.cursor()
    cur.execute("SELECT chunk_id, thread_id, title, ts_start, ts_end, text, token_count FROM rag_chunks WHERE embedded = 0")
    rows = cur.fetchall()
    log.info("To embed: %d", len(rows))

    def batches(xs, n):
        for i in range(0, len(xs), n):
            yield xs[i:i+n]

    # Filter out chunks that exceed embedding model's token limit (8191 tokens)
    MAX_EMBED_TOKENS = 8000  # Leave some margin
    valid_rows = [r for r in rows if r["token_count"] <= MAX_EMBED_TOKENS]
    skipped = len(rows) - len(valid_rows)
    if skipped > 0:
        log.warning("Skipping %d chunks exceeding %d tokens", skipped, MAX_EMBED_TOKENS)
        # Mark oversized chunks as embedded=-1 to skip them
        oversized = [r for r in rows if r["token_count"] > MAX_EMBED_TOKENS]
        conn.executemany("UPDATE rag_chunks SET embedded = -1 WHERE chunk_id = ?", [(r["chunk_id"],) for r in oversized])
        conn.commit()

    done = 0
    for b in batches(valid_rows, batch_size):
        texts = [r["text"] for r in b]
        resp = client.embeddings.create(model=embed_model, input=texts)
        vectors = [d.embedding for d in resp.data]

        points = []
        for r, v in zip(b, vectors):
            cid = r["chunk_id"]
            # Convert chunk_id to UUID for Qdrant compatibility
            point_uuid = chunk_id_to_uuid(cid)
            points.append(PointStruct(
                id=point_uuid,
                vector=v,
                payload={
                    "chunk_id": cid,
                    "thread_id": r["thread_id"],
                    "title": r["title"],
                    "ts_start": r["ts_start"],
                    "ts_end": r["ts_end"],
                }
            ))

        q.upsert(collection_name=collection, points=points)
        conn.executemany("UPDATE rag_chunks SET embedded = 1 WHERE chunk_id = ?", [(r["chunk_id"],) for r in b])
        conn.commit()

        done += len(b)
        log.info("Embedded %d/%d", done, len(valid_rows))

    conn.close()
    log.info("Embedding done.")


def main():
    load_dotenv()

    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("build-chunks")
    a.add_argument("--db", required=True)
    a.add_argument("--max-tokens", type=int, default=1100)
    a.add_argument("--min-tokens", type=int, default=250)
    a.add_argument("--overlap-msgs", type=int, default=2)
    a.add_argument("--token-model", default=os.environ.get("EMBED_MODEL", "text-embedding-3-small"))

    b = sub.add_parser("embed")
    b.add_argument("--db", required=True)
    b.add_argument("--qdrant-url", default=os.environ.get("QDRANT_URL", "http://localhost:6333"))
    b.add_argument("--collection", default=os.environ.get("QDRANT_COLLECTION", "memory_chunks"))
    b.add_argument("--embed-model", default=os.environ.get("EMBED_MODEL", "text-embedding-3-small"))
    b.add_argument("--batch-size", type=int, default=64)

    args = ap.parse_args()

    if args.cmd == "build-chunks":
        build_chunks(args.db, args.max_tokens, args.overlap_msgs, args.min_tokens, args.token_model)
    elif args.cmd == "embed":
        embed(args.db, args.qdrant_url, args.collection, args.embed_model, args.batch_size)


if __name__ == "__main__":
    main()
