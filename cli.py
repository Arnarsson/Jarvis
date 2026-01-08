#!/usr/bin/env python3
"""
Unified Memory CLI - Search your ChatGPT + Claude conversation history

Usage:
    memory init                    # Initialize project (submodule, deps, Qdrant)
    memory ingest <file>           # Import conversation exports
    memory index                   # Build chunks + embed
    memory search "query"          # CLI search (no server needed)
    memory serve                   # Start MCP server
    memory status                  # Show DB stats, health check
"""
import argparse
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Configure logging - suppress HTTP noise by default
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("qdrant_client").setLevel(logging.WARNING)
log = logging.getLogger("memory")

# Project paths
PROJECT_ROOT = Path(__file__).parent.absolute()
VENDOR_DIR = PROJECT_ROOT / "vendor" / "chat-export-structurer"
INGEST_SCRIPT = VENDOR_DIR / "src" / "ingest.py"
DEFAULT_DB = PROJECT_ROOT / "memory.sqlite"
HISTORY_DIR = PROJECT_ROOT / "claude-history-explorer-main"


def _load_history_cli():
    """Load the Claude History Explorer CLI entrypoint."""
    pkg_dir = HISTORY_DIR / "claude_history_explorer"
    if not pkg_dir.exists():
        raise FileNotFoundError(
            "Claude History Explorer sources not found. "
            "Ensure claude-history-explorer-main/claude_history_explorer exists."
        )
    history_path = str(HISTORY_DIR)
    if history_path not in sys.path:
        sys.path.insert(0, history_path)
    try:
        from claude_history_explorer import cli as claude_cli
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError(f"Failed to load Claude History Explorer CLI: {exc}") from exc
    return claude_cli.main


# ============================================================================
# Query Expansion - Map natural language to search terms
# ============================================================================

INTENT_KEYWORDS = {
    "planning": {
        "triggers": ["plan", "week", "schedule", "todo", "agenda", "organize"],
        "expand": ["tasks", "todos", "action items", "commitments", "goals", "deadlines", "priorities"]
    },
    "recall": {
        "triggers": ["remember", "discussed", "talked about", "mentioned", "said"],
        "expand": ["conversation", "discussion", "topic", "idea", "point"]
    },
    "projects": {
        "triggers": ["working on", "building", "project", "feature", "developing"],
        "expand": ["implementing", "progress", "milestone", "status", "blocker"]
    },
    "issues": {
        "triggers": ["problem", "bug", "error", "fix", "issue", "broken"],
        "expand": ["troubleshoot", "debug", "resolve", "solution", "workaround"]
    },
    "decisions": {
        "triggers": ["decide", "choose", "option", "should I", "which"],
        "expand": ["alternative", "approach", "recommendation", "tradeoff", "pros", "cons"]
    },
    "learning": {
        "triggers": ["learn", "understand", "explain", "how to", "tutorial"],
        "expand": ["example", "documentation", "guide", "concept", "pattern"]
    },
}


def expand_query(query: str) -> str:
    """Expand natural language query with relevant terms."""
    query_lower = query.lower()
    expansions = set()

    for intent, config in INTENT_KEYWORDS.items():
        if any(kw in query_lower for kw in config["triggers"]):
            expansions.update(config["expand"])

    if expansions:
        return f"{query} {' '.join(expansions)}"
    return query


# ============================================================================
# Temporal Ranking - Boost recent conversations
# ============================================================================

def temporal_boost(ts: Optional[str], boost_factor: float = 0.2) -> float:
    """Boost recent conversations in ranking."""
    if not ts:
        return 1.0
    try:
        # Handle various timestamp formats
        if ts.endswith('Z'):
            ts = ts.replace('Z', '+00:00')
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_days = (now - dt).days
    except Exception:
        return 1.0

    if age_days < 7:
        return 1.0 + boost_factor       # Last week: +20%
    elif age_days < 30:
        return 1.0 + boost_factor * 0.5  # Last month: +10%
    elif age_days < 90:
        return 1.0 + boost_factor * 0.2  # Last quarter: +4%
    return 1.0


# ============================================================================
# Format Detection - Auto-detect ChatGPT vs Claude exports
# ============================================================================

def detect_format(file_path: Path) -> str:
    """Auto-detect export format from file structure."""
    if file_path.suffix.lower() == '.zip':
        with zipfile.ZipFile(file_path, 'r') as zf:
            names = zf.namelist()

            # Check for conversations.json and examine its content
            if 'conversations.json' in names:
                with zf.open('conversations.json') as f:
                    # Read first chunk to detect format
                    try:
                        # Stream the first part to detect format quickly
                        content = f.read(5000).decode('utf-8')
                        # Claude: has 'chat_messages' and 'uuid' patterns
                        if '"chat_messages"' in content and '"uuid"' in content:
                            return 'claude'
                        # ChatGPT: has 'mapping' pattern
                        if '"mapping"' in content:
                            return 'chatgpt'
                    except Exception:
                        pass

            # Claude exports have conversations/ directory with individual JSON files
            if any(n.startswith('conversations/') and n.endswith('.json') for n in names):
                return 'claude'

            # Check first JSON file content
            json_files = [n for n in names if n.endswith('.json')]
            if json_files:
                with zf.open(json_files[0]) as f:
                    try:
                        data = json.load(f)
                        return _detect_json_format(data)
                    except Exception:
                        pass
        raise ValueError(f"Could not detect format from ZIP: {file_path}")

    # Direct JSON file
    with open(file_path) as f:
        data = json.load(f)
    return _detect_json_format(data)


def _detect_json_format(data: Any) -> str:
    """Detect format from JSON content."""
    if isinstance(data, list) and data:
        first = data[0]
        # ChatGPT: has 'mapping' with message nodes
        if isinstance(first, dict) and 'mapping' in first:
            return 'chatgpt'
        # Claude: has 'uuid' and 'chat_messages'
        if isinstance(first, dict) and 'chat_messages' in first:
            return 'claude'
    raise ValueError("Unknown JSON format - expected ChatGPT or Claude export")


# ============================================================================
# Command: init
# ============================================================================

def cmd_init(args):
    """Initialize the memory system."""
    print("🚀 Initializing Memory system...\n")

    # 1. Check/init submodule
    print("📦 Checking git submodule...")
    if not (VENDOR_DIR / "structurer.py").exists():
        print("   Initializing chat-export-structurer submodule...")
        result = subprocess.run(
            ["git", "submodule", "update", "--init", "--recursive"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"   ⚠️  Submodule init failed: {result.stderr}")
            print("   Try manually: git submodule update --init --recursive")
        else:
            print("   ✅ Submodule initialized")
    else:
        print("   ✅ Submodule already present")

    # 2. Check Python dependencies
    print("\n📦 Checking Python dependencies...")
    try:
        import qdrant_client
        import openai
        import tiktoken
        import fastmcp
        print("   ✅ Core dependencies installed")
    except ImportError as e:
        print(f"   ⚠️  Missing: {e.name}")
        print("   Run: pip install -r requirements.txt")

    # 3. Check .env
    print("\n🔧 Checking environment...")
    env_file = PROJECT_ROOT / ".env"
    env_example = PROJECT_ROOT / ".env.example"
    if not env_file.exists():
        if env_example.exists():
            shutil.copy(env_example, env_file)
            print("   Created .env from .env.example")
            print("   ⚠️  Edit .env and add your OPENAI_API_KEY")
        else:
            print("   ⚠️  No .env file - create one with OPENAI_API_KEY")
    else:
        load_dotenv(env_file)
        if os.environ.get("OPENAI_API_KEY"):
            print("   ✅ OPENAI_API_KEY configured")
        else:
            print("   ⚠️  OPENAI_API_KEY not set in .env")

    # 4. Check Qdrant
    print("\n🔍 Checking Qdrant...")
    qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    try:
        from qdrant_client import QdrantClient
        qd = QdrantClient(url=qdrant_url, timeout=5)
        qd.get_collections()
        print(f"   ✅ Qdrant running at {qdrant_url}")
    except Exception as e:
        print(f"   ⚠️  Qdrant not reachable at {qdrant_url}")
        print("   Start with: docker compose up -d")

    print("\n✨ Initialization complete!")
    print("\nNext steps:")
    print("  1. memory ingest <export.zip>   # Import conversations")
    print("  2. memory index                 # Build search index")
    print("  3. memory search 'your query'   # Search!")


# ============================================================================
# Command: ingest
# ============================================================================

def cmd_ingest(args):
    """Ingest conversation exports."""
    file_path = Path(args.file).expanduser().absolute()
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        sys.exit(1)

    db_path = Path(args.db).expanduser().absolute()

    # Detect format
    fmt = args.format
    if fmt == 'auto':
        print(f"🔍 Auto-detecting format for: {file_path.name}")
        try:
            fmt = detect_format(file_path)
            print(f"   Detected: {fmt}")
        except ValueError as e:
            print(f"❌ {e}")
            sys.exit(1)

    print(f"\n📥 Ingesting {fmt} export: {file_path.name}")
    print(f"   Database: {db_path}")

    # Check structurer exists
    if not INGEST_SCRIPT.exists():
        print("❌ chat-export-structurer not found. Run: memory init")
        sys.exit(1)

    # Map our format names to structurer format names
    structurer_format = fmt
    if fmt == 'claude':
        structurer_format = 'anthropic'

    # Handle ZIP extraction
    work_dir = None
    json_path = file_path

    if file_path.suffix.lower() == '.zip':
        print("   Extracting ZIP...")
        work_dir = tempfile.mkdtemp(prefix="memory_ingest_")
        with zipfile.ZipFile(file_path, 'r') as zf:
            zf.extractall(work_dir)

        # Find the JSON file(s)
        work_path = Path(work_dir)
        if fmt == 'chatgpt':
            json_path = work_path / "conversations.json"
            if not json_path.exists():
                # Try finding it
                candidates = list(work_path.glob("**/conversations.json"))
                if candidates:
                    json_path = candidates[0]
        elif fmt == 'claude':
            # Claude exports can have:
            # 1. conversations.json at root (single file with all conversations)
            # 2. conversations/ directory with individual JSON files
            conv_json = work_path / "conversations.json"
            conv_dir = work_path / "conversations"

            if conv_json.exists():
                # Single file format
                json_path = conv_json
            elif conv_dir.exists():
                json_files = list(conv_dir.glob("*.json"))
                if json_files:
                    # Combine all conversation files into one
                    all_convs = []
                    for jf in json_files:
                        with open(jf) as f:
                            try:
                                data = json.load(f)
                                if isinstance(data, list):
                                    all_convs.extend(data)
                                else:
                                    all_convs.append(data)
                            except Exception as e:
                                log.warning(f"Skipping {jf.name}: {e}")
                    # Write combined file
                    json_path = work_path / "combined_conversations.json"
                    with open(json_path, 'w') as f:
                        json.dump(all_convs, f)
                    print(f"   Combined {len(json_files)} Claude conversation files")

    if not json_path.exists():
        print(f"❌ Could not find JSON file in export")
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)
        sys.exit(1)

    print(f"   Processing: {json_path.name}")

    # Run structurer
    try:
        cmd = [
            sys.executable, str(INGEST_SCRIPT),
            "--in", str(json_path),
            "--db", str(db_path),
            "--format", structurer_format
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=VENDOR_DIR)

        if result.returncode != 0:
            print(f"❌ Structurer failed:")
            print(result.stderr)
            sys.exit(1)

        print(result.stdout)
        print(f"\n✅ Ingested to: {db_path}")

    finally:
        # Cleanup temp dir
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)

    # Show stats
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM messages")
        msg_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT canonical_thread_id) FROM messages")
        thread_count = cur.fetchone()[0]
        conn.close()
        print(f"   Messages: {msg_count:,}")
        print(f"   Threads: {thread_count:,}")
    except Exception:
        pass


# ============================================================================
# Command: index
# ============================================================================

def cmd_index(args):
    """Build chunks and embeddings."""
    db_path = Path(args.db).expanduser().absolute()

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("   Run 'memory ingest' first")
        sys.exit(1)

    load_dotenv()

    # Check API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not set")
        print("   Add it to .env file")
        sys.exit(1)

    print("📊 Building search index...\n")

    # Import indexer functions
    sys.path.insert(0, str(PROJECT_ROOT))
    from indexer import build_chunks, embed

    # Build chunks
    print("1️⃣  Building chunks...")
    build_chunks(
        db_path=str(db_path),
        max_tokens=args.max_tokens,
        overlap_msgs=args.overlap,
        min_tokens=args.min_tokens,
        token_model=args.embed_model
    )

    # Embed chunks
    print("\n2️⃣  Embedding chunks...")
    embed(
        db_path=str(db_path),
        qdrant_url=args.qdrant_url,
        collection=args.collection,
        embed_model=args.embed_model,
        batch_size=args.batch_size
    )

    print("\n✅ Indexing complete!")
    print("   Run 'memory search \"your query\"' to search")


# ============================================================================
# Command: search (CLI search without server)
# ============================================================================

def cmd_search(args):
    """Search conversations from CLI."""
    db_path = Path(args.db).expanduser().absolute()

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    load_dotenv()

    query = args.query.strip()
    if not query:
        print("❌ Empty query")
        sys.exit(1)

    # Expand query with intent keywords
    expanded = expand_query(query)
    if expanded != query and not args.json:
        print(f"🔍 Searching: {query}")
        print(f"   Expanded: {expanded}\n")
    elif not args.json:
        print(f"🔍 Searching: {query}\n")

    # Import search function
    sys.path.insert(0, str(PROJECT_ROOT))
    from server import hybrid_search, fetch_chunk

    qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    collection = os.environ.get("QDRANT_COLLECTION", "memory_chunks")
    embed_model = os.environ.get("EMBED_MODEL", "text-embedding-3-small")

    try:
        results = hybrid_search(
            db_path=str(db_path),
            qdrant_url=qdrant_url,
            collection=collection,
            embed_model=embed_model,
            base_url="memory://",
            query=expanded,
            k=args.limit
        )
    except Exception as e:
        if "OPENAI_API_KEY" in str(e):
            print("❌ OPENAI_API_KEY not set")
        else:
            print(f"❌ Search failed: {e}")
        sys.exit(1)

    if not results:
        print("No results found.")
        return

    # Apply temporal boost and re-rank
    conn = sqlite3.connect(str(db_path))
    for r in results:
        chunk = fetch_chunk(conn, r["id"])
        if chunk:
            r["_temporal_boost"] = temporal_boost(chunk.get("ts_start"))
            r["_final_score"] = r["_score"] * r["_temporal_boost"]
            r["_chunk"] = chunk
    conn.close()

    # Re-sort by boosted score
    results.sort(key=lambda x: x.get("_final_score", x["_score"]), reverse=True)

    # Output
    if args.json:
        output = []
        for r in results:
            item = {
                "id": r["id"],
                "title": r["title"],
                "score": r.get("_final_score", r["_score"]),
            }
            if args.full and "_chunk" in r:
                item["text"] = r["_chunk"]["text"]
                item["ts_start"] = r["_chunk"].get("ts_start")
                item["ts_end"] = r["_chunk"].get("ts_end")
            output.append(item)
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        for i, r in enumerate(results, 1):
            chunk = r.get("_chunk", {})
            score = r.get("_final_score", r["_score"])
            ts = chunk.get("ts_start", "")[:10] if chunk.get("ts_start") else ""

            print(f"{'─' * 60}")
            print(f"#{i} [{ts}] {r['title']}")
            print(f"   Score: {score:.3f} | ID: {r['id'][:20]}...")

            if args.full and chunk.get("text"):
                print(f"\n{chunk['text'][:800]}...")
            else:
                # Show snippet
                text = chunk.get("text", "")[:200]
                if text:
                    print(f"   {text.replace(chr(10), ' ')}...")

        print(f"{'─' * 60}")
        print(f"Found {len(results)} results")


# ============================================================================
# Command: serve
# ============================================================================

def cmd_serve(args):
    """Start MCP server."""
    db_path = Path(args.db).expanduser().absolute()

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    load_dotenv()

    # Run server
    cmd = [
        sys.executable, str(PROJECT_ROOT / "server.py"),
        "--db", str(db_path),
        "--transport", args.transport,
        "--port", str(args.port),
    ]

    if args.qdrant_url:
        cmd.extend(["--qdrant-url", args.qdrant_url])

    print(f"🚀 Starting MCP server...")
    print(f"   Transport: {args.transport}")
    print(f"   Database: {db_path}")

    os.execv(sys.executable, cmd)


# ============================================================================
# Command: status
# ============================================================================

def cmd_status(args):
    """Show system status."""
    db_path = Path(args.db).expanduser().absolute()
    load_dotenv()

    print("📊 Memory System Status\n")

    # Database
    print("Database:")
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        print(f"   ✅ {db_path.name} ({size_mb:.1f} MB)")

        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()

            # Messages
            try:
                cur.execute("SELECT COUNT(*) FROM messages")
                msg_count = cur.fetchone()[0]
                print(f"   Messages: {msg_count:,}")
            except Exception:
                print("   Messages: (table not found)")

            # Chunks
            try:
                cur.execute("SELECT COUNT(*) FROM rag_chunks")
                chunk_count = cur.fetchone()[0]
                cur.execute("SELECT SUM(token_count) FROM rag_chunks")
                total_tokens = cur.fetchone()[0] or 0
                print(f"   Chunks: {chunk_count:,}")
                print(f"   Tokens: {total_tokens:,}")
            except Exception:
                print("   Chunks: (not indexed yet)")

            # Embedded
            try:
                cur.execute("SELECT COUNT(*) FROM rag_chunks WHERE embedded = 1")
                embedded = cur.fetchone()[0]
                print(f"   Embedded: {embedded:,}")
            except Exception:
                pass

            conn.close()
        except Exception as e:
            print(f"   ⚠️  Error reading DB: {e}")
    else:
        print(f"   ❌ Not found: {db_path}")

    # Qdrant
    print("\nQdrant:")
    qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    collection = os.environ.get("QDRANT_COLLECTION", "memory_chunks")
    try:
        from qdrant_client import QdrantClient
        qd = QdrantClient(url=qdrant_url, timeout=5)
        collections = qd.get_collections().collections
        print(f"   ✅ Running at {qdrant_url}")

        # Check our collection
        col_names = [c.name for c in collections]
        if collection in col_names:
            info = qd.get_collection(collection)
            print(f"   Collection: {collection}")
            print(f"   Vectors: {info.points_count:,}")
        else:
            print(f"   ⚠️  Collection '{collection}' not found")
    except Exception as e:
        print(f"   ❌ Not reachable at {qdrant_url}")

    # API Key
    print("\nOpenAI:")
    if os.environ.get("OPENAI_API_KEY"):
        key = os.environ["OPENAI_API_KEY"]
        print(f"   ✅ API key configured ({key[:8]}...)")
    else:
        print("   ❌ OPENAI_API_KEY not set")

    # Submodule
    print("\nSubmodule:")
    if (VENDOR_DIR / "structurer.py").exists():
        print("   ✅ chat-export-structurer present")
    else:
        print("   ❌ Not initialized (run 'memory init')")


# ============================================================================
# Command: export
# ============================================================================

def cmd_export(args):
    """Export search results."""
    # Reuse search logic
    args.json = (args.output_format == 'json')
    args.full = True
    cmd_search(args)


def cmd_history(args):
    """Delegate to Claude History Explorer CLI."""
    try:
        history_cli = _load_history_cli()
    except Exception as exc:
        print(f"❌ {exc}")
        print("Ensure the claude-history-explorer-main folder exists at the project root.")
        return

    passthrough = args.history_args or []
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]
    if not passthrough:
        passthrough = ["--help"]

    try:
        history_cli.main(
            args=passthrough,
            prog_name="memory history",
            standalone_mode=False,
        )
    except SystemExit as exc:
        if exc.code not in (0, None):
            raise


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        prog='memory',
        description='Unified Memory - Search your AI conversation history',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  memory init                           # Initialize project
  memory ingest ~/Downloads/export.zip  # Import ChatGPT/Claude export
  memory index                          # Build search index
  memory search "plan the week"         # Search conversations
  memory status                         # Check system health
"""
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # init
    p_init = subparsers.add_parser('init', help='Initialize memory system')
    p_init.set_defaults(func=cmd_init)

    # ingest
    p_ingest = subparsers.add_parser('ingest', help='Import conversation exports')
    p_ingest.add_argument('file', help='Path to export file (ZIP or JSON)')
    p_ingest.add_argument('--format', choices=['chatgpt', 'claude', 'grok', 'auto'], default='auto',
                          help='Export format (default: auto-detect)')
    p_ingest.add_argument('--db', default=str(DEFAULT_DB), help='Database path')
    p_ingest.set_defaults(func=cmd_ingest)

    # index
    p_index = subparsers.add_parser('index', help='Build search index')
    p_index.add_argument('--db', default=str(DEFAULT_DB), help='Database path')
    p_index.add_argument('--max-tokens', type=int, default=1100, help='Max tokens per chunk')
    p_index.add_argument('--min-tokens', type=int, default=250, help='Min tokens per chunk')
    p_index.add_argument('--overlap', type=int, default=2, help='Message overlap between chunks')
    p_index.add_argument('--embed-model', default='text-embedding-3-small', help='Embedding model')
    p_index.add_argument('--qdrant-url', default='http://localhost:6333', help='Qdrant URL')
    p_index.add_argument('--collection', default='memory_chunks', help='Qdrant collection name')
    p_index.add_argument('--batch-size', type=int, default=64, help='Embedding batch size')
    p_index.set_defaults(func=cmd_index)

    # search
    p_search = subparsers.add_parser('search', help='Search conversations')
    p_search.add_argument('query', help='Search query')
    p_search.add_argument('--db', default=str(DEFAULT_DB), help='Database path')
    p_search.add_argument('-n', '--limit', type=int, default=8, help='Number of results')
    p_search.add_argument('--full', action='store_true', help='Show full content')
    p_search.add_argument('--json', action='store_true', help='Output as JSON')
    p_search.set_defaults(func=cmd_search)

    # serve
    p_serve = subparsers.add_parser('serve', help='Start MCP server')
    p_serve.add_argument('--db', default=str(DEFAULT_DB), help='Database path')
    p_serve.add_argument('--transport', choices=['sse', 'stdio'], default='stdio',
                         help='MCP transport (default: stdio)')
    p_serve.add_argument('--port', type=int, default=8000, help='Server port (for SSE)')
    p_serve.add_argument('--qdrant-url', help='Qdrant URL')
    p_serve.set_defaults(func=cmd_serve)

    # status
    p_status = subparsers.add_parser('status', help='Show system status')
    p_status.add_argument('--db', default=str(DEFAULT_DB), help='Database path')
    p_status.set_defaults(func=cmd_status)

    # export
    p_export = subparsers.add_parser('export', help='Export search results')
    p_export.add_argument('query', help='Search query')
    p_export.add_argument('--db', default=str(DEFAULT_DB), help='Database path')
    p_export.add_argument('-n', '--limit', type=int, default=20, help='Number of results')
    p_export.add_argument('--format', dest='output_format', choices=['json', 'md'], default='json',
                          help='Output format')
    p_export.set_defaults(func=cmd_export)

    # history explorer passthrough
    p_history = subparsers.add_parser(
        'history',
        help='Run Claude History Explorer commands (pass through to claude-history CLI)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""
Bridge command for the upstream claude-history-explorer CLI.

Examples:
  memory history projects
  memory history sessions myproject -n 5
  memory history show abc123 --raw
  memory history -- search "TODO" -p myproject
""",
    )
    p_history.add_argument(
        'history_args',
        nargs=argparse.REMAINDER,
        help='Arguments to forward (use "--" to pass flags that overlap with memory CLI)',
    )
    p_history.set_defaults(func=cmd_history)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
