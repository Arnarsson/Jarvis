# Phase 1: Privacy-First Capture Foundation - Research

**Researched:** 2026-01-24
**Domain:** Desktop screen capture agent (Python) + Server infrastructure (Docker/PostgreSQL/Qdrant)
**Confidence:** MEDIUM-HIGH

## Summary

This phase implements a desktop screen capture agent that runs on Linux (primary) and macOS (secondary), capturing screenshots at configurable intervals with change detection, uploading them securely to a Hetzner-hosted server via Tailscale VPN. The agent provides both system tray and CLI interfaces, with exclusion rules for sensitive applications and idle detection to pause capture.

The standard approach for Python desktop agents in this space involves:
- **Screenshot capture**: mss library for high-performance, cross-platform multi-monitor capture
- **System tray**: pystray for cross-platform tray icon with menu support
- **CLI**: Typer (built on Click) for modern, type-safe subcommand interfaces
- **Change detection**: imagehash library with perceptual hashing (phash/dhash) for efficient similarity comparison
- **Window detection**: PyWinCtl for cross-platform active window/app detection
- **Input monitoring**: pynput for keyboard/mouse activity detection (idle detection)
- **PII detection**: Microsoft Presidio for detecting/masking sensitive content in OCR text
- **OCR**: pytesseract wrapping Tesseract-OCR for text extraction from screenshots

The server stack uses Docker Compose with FastAPI (async), PostgreSQL (via SQLAlchemy 2.0 + asyncpg), and Qdrant for vector storage.

**Primary recommendation:** Fork OpenRecall as the base, replacing/extending its capture and storage logic to support the required hybrid trigger behavior, multi-monitor capture, Tailscale transport, and server-side architecture.

## Standard Stack

The established libraries/tools for this domain:

### Core - Desktop Agent

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mss | 9.x | Screenshot capture | 180 FPS benchmark, cross-platform, multi-monitor native |
| pystray | 0.19.x | System tray icon | Only mature cross-platform Python tray library |
| typer | 0.12.x | CLI framework | Type hints, auto-docs, built on Click, Pythonic |
| imagehash | 4.3.x | Change detection | Multiple algorithms (phash, dhash), fast comparison |
| PyWinCtl | 0.4.x | Window detection | Cross-platform active window/title detection |
| pynput | 1.8.x | Input monitoring | Industry standard for keyboard/mouse listeners |
| Pillow | 10.x | Image processing | JPEG compression, format conversion, ubiquitous |
| pytesseract | 0.3.x | OCR | Standard Python wrapper for Tesseract-OCR |
| presidio-analyzer | 2.x | PII detection | Microsoft-backed, credit cards, SSN, names, etc. |

### Core - Server

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.110.x | HTTP API | Async-native, OpenAPI docs, high performance |
| SQLAlchemy | 2.0.x | ORM | Async support, mature, Python standard |
| asyncpg | 0.29.x | PostgreSQL driver | Best async Postgres driver, 3x faster than psycopg |
| qdrant-client | 1.9.x | Vector database | Official Python client, async support |
| structlog | 24.x | Structured logging | JSON-native, contextual, audit-friendly |
| python-json-logger | 2.x | JSON log formatter | Standard library logging + JSON output |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.27.x | HTTP client | Agent-to-server uploads, async support |
| aiofiles | 24.x | Async file I/O | Server-side file storage operations |
| pydantic-settings | 2.x | Configuration | Settings management with env vars |
| alembic | 1.13.x | DB migrations | PostgreSQL schema management |
| python-multipart | 0.0.9 | File uploads | FastAPI multipart form handling |
| tailscale (PyPI) | 0.6.x | Tailscale API | Optional: programmatic Tailscale control |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| mss | Pillow.ImageGrab | Pillow is simpler but slower (8 FPS vs 180 FPS) |
| pystray | PyQt/GTK tray | Qt/GTK are heavier, require more dependencies |
| typer | Click directly | Click is more verbose, less Pythonic |
| imagehash | pixelmatch | Pixelmatch is pixel-level (too sensitive for screenshots) |
| presidio | regex-only | Regex misses context-dependent PII like names |
| httpx | requests | requests lacks native async, httpx is modern replacement |

**Installation (Agent):**
```bash
pip install mss pystray typer imagehash pywinctl pynput pillow pytesseract presidio-analyzer httpx python-json-logger
# Also: brew install tesseract (Mac) or apt install tesseract-ocr (Linux)
```

**Installation (Server):**
```bash
pip install fastapi uvicorn sqlalchemy asyncpg qdrant-client structlog pydantic-settings alembic python-multipart aiofiles
```

## Architecture Patterns

### Recommended Project Structure (Agent)

```
jarvis-agent/
├── src/
│   └── jarvis/
│       ├── __init__.py
│       ├── cli.py              # Typer CLI entry point
│       ├── tray.py             # System tray implementation
│       ├── capture/
│       │   ├── __init__.py
│       │   ├── screenshot.py   # mss-based capture
│       │   ├── change.py       # imagehash comparison
│       │   └── exclusions.py   # App/window filtering
│       ├── privacy/
│       │   ├── __init__.py
│       │   ├── detector.py     # Presidio-based PII detection
│       │   └── masking.py      # Content redaction
│       ├── monitor/
│       │   ├── __init__.py
│       │   ├── idle.py         # pynput-based idle detection
│       │   └── window.py       # PyWinCtl window tracking
│       ├── sync/
│       │   ├── __init__.py
│       │   ├── uploader.py     # httpx async uploads
│       │   └── queue.py        # Local queue for offline
│       ├── config/
│       │   ├── __init__.py
│       │   ├── settings.py     # pydantic-settings
│       │   └── exclusions.yaml # Default exclusion list
│       └── logging.py          # Structured JSON logging
├── tests/
├── pyproject.toml
└── README.md
```

### Recommended Project Structure (Server)

```
jarvis-server/
├── src/
│   └── jarvis_server/
│       ├── __init__.py
│       ├── main.py             # FastAPI app
│       ├── api/
│       │   ├── __init__.py
│       │   ├── captures.py     # Upload endpoints
│       │   └── health.py       # Health checks
│       ├── db/
│       │   ├── __init__.py
│       │   ├── models.py       # SQLAlchemy models
│       │   ├── session.py      # Async session factory
│       │   └── crud.py         # Database operations
│       ├── storage/
│       │   ├── __init__.py
│       │   └── filesystem.py   # File storage operations
│       ├── vector/
│       │   ├── __init__.py
│       │   └── qdrant.py       # Qdrant client wrapper
│       └── config.py           # Settings
├── alembic/                    # Migrations
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

### Pattern 1: Hybrid Capture Trigger

**What:** Combines change detection with minimum interval fallback
**When to use:** Capturing screenshots efficiently without missing important changes

```python
# Source: Derived from imagehash and mss documentation
import imagehash
from PIL import Image
import mss
import time

class HybridCaptureTrigger:
    def __init__(self, min_interval: float = 15.0, hash_threshold: int = 5):
        self.min_interval = min_interval
        self.hash_threshold = hash_threshold
        self.last_capture_time = 0
        self.last_hash = None
        self.sct = mss.mss()

    def should_capture(self, monitor: dict) -> bool:
        now = time.time()
        elapsed = now - self.last_capture_time

        # Always capture if minimum interval exceeded
        if elapsed >= self.min_interval:
            return True

        # Check for significant change
        screenshot = self.sct.grab(monitor)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        current_hash = imagehash.dhash(img)

        if self.last_hash is None:
            return True

        # Hamming distance below threshold = similar images
        distance = current_hash - self.last_hash
        return distance > self.hash_threshold

    def record_capture(self, img: Image.Image):
        self.last_capture_time = time.time()
        self.last_hash = imagehash.dhash(img)
```

### Pattern 2: Cross-Platform Idle Detection

**What:** Detect user inactivity by monitoring input events
**When to use:** Pausing capture when user is idle (5+ minutes no input)

```python
# Source: pynput documentation
from pynput import mouse, keyboard
import threading
import time

class IdleDetector:
    def __init__(self, idle_threshold: float = 300.0):  # 5 minutes
        self.idle_threshold = idle_threshold
        self.last_activity = time.time()
        self._lock = threading.Lock()
        self._running = False

    def _on_activity(self, *args):
        with self._lock:
            self.last_activity = time.time()

    def is_idle(self) -> bool:
        with self._lock:
            return (time.time() - self.last_activity) > self.idle_threshold

    def start(self):
        self._running = True
        # Mouse listener
        self.mouse_listener = mouse.Listener(
            on_move=self._on_activity,
            on_click=self._on_activity,
            on_scroll=self._on_activity
        )
        # Keyboard listener
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_activity,
            on_release=self._on_activity
        )
        self.mouse_listener.start()
        self.keyboard_listener.start()

    def stop(self):
        self._running = False
        self.mouse_listener.stop()
        self.keyboard_listener.stop()
```

### Pattern 3: Application Exclusion Filtering

**What:** Skip capture when excluded applications are in foreground
**When to use:** Protecting sensitive apps (password managers, banking)

```python
# Source: PyWinCtl documentation
import pywinctl

class ExclusionFilter:
    def __init__(self, exclusions: list[str]):
        # Exclusions can be app names or window title patterns
        self.exclusions = [e.lower() for e in exclusions]

    def should_exclude(self) -> bool:
        window = pywinctl.getActiveWindow()
        if window is None:
            return False

        # Check app name
        app_name = (window.getAppName() or "").lower()
        window_title = (window.title or "").lower()

        for exclusion in self.exclusions:
            if exclusion in app_name or exclusion in window_title:
                return True
        return False

# Default exclusions (shipped with agent)
DEFAULT_EXCLUSIONS = [
    "1password",
    "bitwarden",
    "lastpass",
    "keepass",
    "keychain",
    "private browsing",
    "incognito",
    # Banking apps would be user-configured
]
```

### Pattern 4: Async File Upload with Retry

**What:** Upload captures to server with retry logic
**When to use:** Reliable agent-to-server file transfer

```python
# Source: httpx documentation
import httpx
from pathlib import Path
import asyncio

class CaptureUploader:
    def __init__(self, server_url: str, max_retries: int = 3):
        self.server_url = server_url
        self.max_retries = max_retries

    async def upload(self, filepath: Path, metadata: dict) -> bool:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(self.max_retries):
                try:
                    with open(filepath, "rb") as f:
                        files = {"file": (filepath.name, f, "image/jpeg")}
                        data = {"metadata": json.dumps(metadata)}
                        response = await client.post(
                            f"{self.server_url}/api/captures",
                            files=files,
                            data=data
                        )
                        response.raise_for_status()
                        return True
                except httpx.HTTPStatusError as e:
                    if e.response.status_code >= 500:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise
                except httpx.RequestError:
                    await asyncio.sleep(2 ** attempt)
                    continue
            return False
```

### Pattern 5: Presidio PII Detection

**What:** Detect and optionally mask sensitive content in OCR text
**When to use:** Filtering passwords, credit cards, API keys from searchable text

```python
# Source: Microsoft Presidio documentation
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

class PIIDetector:
    def __init__(self):
        # Initialize with default recognizers
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()

    def detect(self, text: str) -> list[dict]:
        """Detect PII in text, returns list of findings."""
        results = self.analyzer.analyze(
            text=text,
            language="en",
            entities=[
                "CREDIT_CARD",
                "CRYPTO",  # Bitcoin wallets
                "EMAIL_ADDRESS",
                "IBAN_CODE",
                "IP_ADDRESS",
                "PHONE_NUMBER",
                "US_SSN",
                # Custom: API keys detected via pattern
            ]
        )
        return [
            {
                "type": r.entity_type,
                "start": r.start,
                "end": r.end,
                "score": r.score
            }
            for r in results
        ]

    def anonymize(self, text: str) -> str:
        """Replace PII with placeholders."""
        results = self.analyzer.analyze(text=text, language="en")
        anonymized = self.anonymizer.anonymize(text=text, analyzer_results=results)
        return anonymized.text
```

### Anti-Patterns to Avoid

- **Blocking main thread in tray app:** pystray.run() blocks; use run_detached() or threading
- **Capturing on every tick:** Use change detection to avoid redundant captures and storage bloat
- **Synchronous uploads:** Block capture loop; use async queue + background upload thread
- **Storing raw PNGs:** Use JPEG compression (quality=80-85) to reduce storage 5-10x
- **Polling for idle:** Use event-driven listeners (pynput) instead of polling mouse position
- **Hard-coded exclusions:** Make exclusion list user-configurable, ship defaults as YAML
- **Single-threaded OCR:** OCR is CPU-heavy; offload to thread pool or server-side

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Image similarity | Pixel diff algorithm | imagehash (phash/dhash) | Handles compression artifacts, resize, minor changes |
| Credit card detection | Regex for card numbers | Presidio | Handles Luhn validation, multiple formats, context |
| Cross-platform screenshots | Platform-specific code | mss | Handles DPI scaling, multi-monitor, Wayland/X11 |
| System tray | GTK/Qt wrappers | pystray | Handles AppIndicator, GNOME, macOS menu bar |
| Active window detection | Xlib/Quartz directly | PyWinCtl | Abstracts Linux (X11/Wayland) and macOS |
| Async HTTP uploads | requests + threading | httpx AsyncClient | Native async, connection pooling, streaming |
| JSON logging | Custom formatters | structlog/python-json-logger | Standardized, contextual, parseable |
| Database migrations | Raw SQL scripts | Alembic | Version control, rollback, auto-generation |

**Key insight:** Desktop cross-platform compatibility is deceptively hard. Libraries like mss, pystray, and PyWinCtl have already solved platform-specific edge cases (DPI scaling, Wayland vs X11, AppIndicator vs GTK tray, macOS accessibility permissions).

## Common Pitfalls

### Pitfall 1: pystray Threading Issues

**What goes wrong:** App freezes or tray doesn't respond
**Why it happens:** pystray.run() must be called from main thread on macOS; mixing with other event loops
**How to avoid:** Use run_detached() and handle icon updates via icon.update_menu()
**Warning signs:** "NSApplication must be used on main thread" errors on macOS

### Pitfall 2: Wayland Screenshot Restrictions

**What goes wrong:** mss returns black/empty screenshots on Wayland
**Why it happens:** Wayland security model restricts screen capture without portal consent
**How to avoid:** Use XDG Desktop Portal (requires user consent dialog) or fall back to Xwayland
**Warning signs:** All black images on GNOME 43+ or recent Fedora/Ubuntu

### Pitfall 3: pynput Permission Requirements

**What goes wrong:** Input listeners don't receive events
**Why it happens:** macOS requires Accessibility permissions; Linux needs X11 or root for uinput
**How to avoid:** macOS: Guide user to enable in System Preferences > Privacy > Accessibility. Linux: Ensure $DISPLAY is set, or run with elevated permissions
**Warning signs:** Silent failures with no events captured

### Pitfall 4: Presidio Model Loading Time

**What goes wrong:** First PII detection call takes 5-10 seconds
**Why it happens:** Presidio loads NLP models on first use
**How to avoid:** Initialize AnalyzerEngine at startup, not per-capture; consider server-side only
**Warning signs:** Intermittent slow captures after cold start

### Pitfall 5: JPEG Quality vs File Size Tradeoff

**What goes wrong:** Screenshots either too large or visibly degraded
**Why it happens:** Quality 95 is nearly lossless but large; quality 60 shows artifacts
**How to avoid:** Use quality=80-85 with optimize=True for good balance
**Warning signs:** Storage growing faster than expected, or OCR accuracy dropping

### Pitfall 6: Async Database Session Leaks

**What goes wrong:** "too many connections" errors, memory leaks
**Why it happens:** Not properly closing async sessions, missing context managers
**How to avoid:** Always use `async with` for sessions; use FastAPI dependency injection with proper cleanup
**Warning signs:** Connection pool exhaustion under load

### Pitfall 7: Qdrant Collection Configuration

**What goes wrong:** Search returns unexpected results, slow queries
**Why it happens:** Wrong distance metric, inappropriate vector size
**How to avoid:** Match vector size to embedding model output; use COSINE for normalized embeddings
**Warning signs:** All results have similar scores, or scores not in expected range

## Code Examples

Verified patterns from official sources:

### Multi-Monitor Screenshot Capture (mss)

```python
# Source: python-mss documentation
import mss
from PIL import Image

def capture_monitors(primary_only: bool = False) -> list[Image.Image]:
    """Capture screenshots from monitors."""
    images = []
    with mss.mss() as sct:
        # sct.monitors[0] is "all monitors combined"
        # sct.monitors[1] is primary, [2]+ are secondary
        monitors = [sct.monitors[1]] if primary_only else sct.monitors[1:]

        for monitor in monitors:
            screenshot = sct.grab(monitor)
            # Convert to PIL Image (BGRA -> RGB)
            img = Image.frombytes(
                "RGB",
                screenshot.size,
                screenshot.bgra,
                "raw",
                "BGRX"
            )
            images.append(img)
    return images
```

### JPEG Compression with Pillow

```python
# Source: Pillow documentation
from PIL import Image
from io import BytesIO
from pathlib import Path

def compress_screenshot(img: Image.Image, quality: int = 80) -> bytes:
    """Compress image to JPEG with optimal settings."""
    buffer = BytesIO()
    img.save(
        buffer,
        format="JPEG",
        quality=quality,
        optimize=True,  # Extra pass for optimal encoding
        progressive=True  # Progressive loading
    )
    return buffer.getvalue()

def save_capture(img: Image.Image, path: Path, quality: int = 80):
    """Save capture to disk with compression."""
    img.save(
        path,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=True
    )
```

### Typer CLI with Subcommands

```python
# Source: Typer documentation
import typer
from typing import Optional
from enum import Enum

app = typer.Typer(help="Jarvis screen capture agent")
capture_app = typer.Typer(help="Capture management commands")
app.add_typer(capture_app, name="capture")

class OutputFormat(str, Enum):
    human = "human"
    json = "json"

@capture_app.command("start")
def capture_start(
    interval: int = typer.Option(15, help="Capture interval in seconds"),
    background: bool = typer.Option(False, "--background", "-b")
):
    """Start the capture service."""
    typer.echo(f"Starting capture with {interval}s interval...")

@capture_app.command("stop")
def capture_stop():
    """Stop the capture service."""
    typer.echo("Stopping capture...")

@app.command()
def status(
    format: OutputFormat = typer.Option(OutputFormat.human, "--format", "-f")
):
    """Show agent status."""
    if format == OutputFormat.json:
        typer.echo('{"status": "active", "captures_today": 150}')
    else:
        typer.echo("Status: Active\nCaptures today: 150")

@app.command()
def config():
    """Manage configuration."""
    typer.echo("Configuration wizard...")

if __name__ == "__main__":
    app()
```

### pystray System Tray

```python
# Source: pystray documentation
import pystray
from PIL import Image, ImageDraw
from enum import Enum
import threading

class TrayStatus(Enum):
    ACTIVE = "green"
    PAUSED = "yellow"
    ERROR = "red"

def create_icon(color: str, size: int = 64) -> Image.Image:
    """Create a solid color icon."""
    img = Image.new("RGBA", (size, size), color)
    return img

class JarvisTray:
    def __init__(self):
        self.status = TrayStatus.ACTIVE
        self.icon = None

    def _create_menu(self):
        return pystray.Menu(
            pystray.MenuItem(
                "Pause" if self.status == TrayStatus.ACTIVE else "Resume",
                self._toggle_capture
            ),
            pystray.MenuItem("Open Settings", self._open_settings),
            pystray.MenuItem("View Recent", self._view_recent),
            pystray.MenuItem("Force Sync", self._force_sync),
            pystray.MenuItem("View Logs", self._view_logs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit)
        )

    def _toggle_capture(self, icon, item):
        if self.status == TrayStatus.ACTIVE:
            self.status = TrayStatus.PAUSED
        else:
            self.status = TrayStatus.ACTIVE
        self._update_icon()

    def _update_icon(self):
        self.icon.icon = create_icon(self.status.value)
        self.icon.menu = self._create_menu()

    def _open_settings(self, icon, item): pass
    def _view_recent(self, icon, item): pass
    def _force_sync(self, icon, item): pass
    def _view_logs(self, icon, item): pass
    def _quit(self, icon, item):
        icon.stop()

    def run(self):
        self.icon = pystray.Icon(
            "jarvis",
            create_icon(self.status.value),
            "Jarvis Capture",
            menu=self._create_menu()
        )
        # Use run_detached() if integrating with other event loops
        self.icon.run()
```

### FastAPI Capture Upload Endpoint

```python
# Source: FastAPI documentation
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import aiofiles
from pathlib import Path
import json
from datetime import datetime
import uuid

app = FastAPI()

STORAGE_PATH = Path("/data/captures")

async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session

@app.post("/api/captures")
async def upload_capture(
    file: UploadFile = File(...),
    metadata: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Receive capture from agent."""
    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid metadata JSON")

    # Generate storage path: /data/captures/2026/01/24/{uuid}.jpg
    now = datetime.utcnow()
    date_path = STORAGE_PATH / now.strftime("%Y/%m/%d")
    date_path.mkdir(parents=True, exist_ok=True)

    file_id = str(uuid.uuid4())
    file_path = date_path / f"{file_id}.jpg"

    # Stream file to disk
    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(8192):
            await f.write(chunk)

    # Store metadata in database
    capture = Capture(
        id=file_id,
        filepath=str(file_path),
        timestamp=meta.get("timestamp"),
        monitor_index=meta.get("monitor_index"),
        ocr_text=meta.get("ocr_text"),
    )
    db.add(capture)
    await db.commit()

    return {"id": file_id, "status": "stored"}
```

### Qdrant Vector Storage

```python
# Source: Qdrant documentation
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue
)
import uuid

class VectorStore:
    def __init__(self, host: str = "localhost", port: int = 6333):
        self.client = QdrantClient(host=host, port=port)
        self.collection = "captures"

    def init_collection(self, vector_size: int = 1024):
        """Create collection if not exists."""
        collections = self.client.get_collections().collections
        if not any(c.name == self.collection for c in collections):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE
                )
            )

    def store_embedding(
        self,
        capture_id: str,
        embedding: list[float],
        payload: dict
    ):
        """Store capture embedding with metadata."""
        self.client.upsert(
            collection_name=self.collection,
            points=[
                PointStruct(
                    id=capture_id,
                    vector=embedding,
                    payload=payload
                )
            ]
        )

    def search_similar(
        self,
        query_vector: list[float],
        limit: int = 10,
        date_filter: str = None
    ) -> list[dict]:
        """Search for similar captures."""
        filter_condition = None
        if date_filter:
            filter_condition = Filter(
                must=[
                    FieldCondition(
                        key="date",
                        match=MatchValue(value=date_filter)
                    )
                ]
            )

        results = self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            query_filter=filter_condition,
            limit=limit,
            with_payload=True
        ).points

        return [
            {"id": r.id, "score": r.score, "payload": r.payload}
            for r in results
        ]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pillow.ImageGrab | mss | 2020+ | 20x faster captures, better multi-monitor |
| argparse | Typer | 2020+ | Type hints, auto-docs, less boilerplate |
| requests | httpx | 2021+ | Async support, HTTP/2, connection pooling |
| psycopg2 | asyncpg | 2020+ | 3x faster async PostgreSQL |
| SQLAlchemy 1.x sync | SQLAlchemy 2.x async | 2023+ | Native async, better typing |
| Custom PII regex | Presidio | 2021+ | Context-aware, multiple entity types |
| Logging to files | Structured JSON stdout | 2022+ | Cloud-native, container-friendly |

**Deprecated/outdated:**
- **pyscreenshot**: Documentation says "obsolete in most cases", use Pillow or mss
- **PyGetWindow**: Superseded by PyWinCtl with Linux/Mac support
- **SQLAlchemy 1.x ORM patterns**: 2.0 style is preferred, uses select() not Query

## Open Questions

Things that couldn't be fully resolved:

1. **Wayland Screenshot Portal Integration**
   - What we know: mss may return black images on pure Wayland
   - What's unclear: Best library for XDG Desktop Portal integration
   - Recommendation: Test on target systems; consider dbus-python + portal protocol or fall back to Xwayland for now

2. **Embedding Model Choice for Qdrant**
   - What we know: Need embedding model for semantic search of OCR text
   - What's unclear: OpenRecall's model, best size/quality tradeoff for self-hosted
   - Recommendation: Defer to later phase; plan for 768-1024 dimension vectors

3. **Smart Retention Algorithm**
   - What we know: User wants to keep "important moments"
   - What's unclear: How to determine importance (activity level? content changes? user-marked?)
   - Recommendation: Start simple (time-based), add intelligence later

4. **OpenRecall Fork Points**
   - What we know: AGPLv3, Python 3.11+, web UI on port 8082
   - What's unclear: Exact internal architecture, OCR engine used, embedding model
   - Recommendation: Clone and audit before forking; may extract concepts rather than fork directly

## Sources

### Primary (HIGH confidence)
- mss documentation - https://python-mss.readthedocs.io/examples.html
- pystray documentation - https://pystray.readthedocs.io/en/latest/usage.html
- Qdrant quickstart - https://qdrant.tech/documentation/quickstart/
- imagehash GitHub - https://github.com/JohannesBuchner/imagehash
- Microsoft Presidio GitHub - https://github.com/microsoft/presidio
- FastAPI official docs - https://fastapi.tiangolo.com/

### Secondary (MEDIUM confidence)
- OpenRecall GitHub - https://github.com/openrecall/openrecall
- PyWinCtl GitHub - https://github.com/Kalmat/PyWinCtl
- pynput documentation - https://pynput.readthedocs.io/
- Typer documentation - via Typer PyPI
- httpx documentation - https://www.python-httpx.org/
- structlog documentation - validated via multiple sources

### Tertiary (LOW confidence)
- Wayland screenshot capabilities - community discussions, may be outdated
- Specific performance benchmarks - vary by system, treat as estimates

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Libraries verified via official documentation
- Architecture patterns: MEDIUM - Patterns derived from docs but not production-tested in this combination
- Pitfalls: MEDIUM - Based on documentation warnings and community reports

**Research date:** 2026-01-24
**Valid until:** 2026-02-24 (30 days - libraries are stable)
