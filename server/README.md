# Jarvis Server

Backend server for Jarvis AI Chief of Staff. Handles screen capture ingestion, OCR processing, vector storage, and API endpoints.

## Requirements

- Python 3.11+
- PostgreSQL with asyncpg driver
- Qdrant for vector storage

## Installation

```bash
# Development installation
pip install -e ".[dev]"

# Production installation
pip install .
```

## Configuration

Configuration via environment variables with `JARVIS_` prefix:

| Variable | Description | Default |
|----------|-------------|---------|
| `JARVIS_DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://jarvis:jarvis@localhost:5432/jarvis` |
| `JARVIS_QDRANT_HOST` | Qdrant server hostname | `localhost` |
| `JARVIS_QDRANT_PORT` | Qdrant server port | `6333` |
| `JARVIS_STORAGE_PATH` | Path for capture file storage | `/data/captures` |
| `JARVIS_LOG_LEVEL` | Logging level | `INFO` |
| `JARVIS_CORS_ORIGINS` | Allowed CORS origins (JSON array) | `["*"]` |

## Running

```bash
# Start the server
jarvis-server

# Or with uvicorn directly
uvicorn jarvis_server.main:app --host 0.0.0.0 --port 8000
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
ruff format .
```
