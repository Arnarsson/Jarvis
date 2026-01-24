# Phase 2: Searchable Memory (RAG Core) - Verification Guide

This guide verifies that the RAG pipeline is working correctly.

## Prerequisites

1. Docker Compose services running:
   ```bash
   cd server
   docker compose up -d
   ```

2. Database migrations applied:
   ```bash
   docker compose exec jarvis-server alembic upgrade head
   ```

3. Qdrant collection initialized (happens on first upload/search)

## Verification Steps

### 1. Service Health

Check all services are healthy:
```bash
docker compose ps
# All should show "healthy" or "running"

# API health
curl http://localhost:8000/health/
# Should return {"status": "healthy", ...}

# Search health
curl http://localhost:8000/api/search/health
# Should return {"status": "healthy", "collection_exists": true}
```

### 2. Capture Upload and Processing

Upload a test screenshot:
```bash
# Create a test image
convert -size 800x600 xc:white -font Helvetica -pointsize 36 \
  -draw "text 50,100 'Hello World - Test Capture'" test.jpg

# Upload
curl -X POST http://localhost:8000/api/captures/ \
  -F "file=@test.jpg;type=image/jpeg" \
  -F 'metadata={"timestamp":"2026-01-24T12:00:00Z","width":800,"height":600}'
# Should return capture ID

# Check worker logs for processing
docker compose logs jarvis-worker --tail=20
# Should see "Processed capture ... status: processed"
```

### 3. Search Functionality

Wait ~30 seconds for processing, then search:
```bash
curl -X POST http://localhost:8000/api/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello World", "limit": 5}'
# Should return results with the test capture
```

### 4. Timeline Browsing

Check timeline API:
```bash
# Get recent captures
curl "http://localhost:8000/api/timeline/?limit=10"
# Should return captures with pagination

# Get day summaries
curl "http://localhost:8000/api/timeline/days?limit=7"
# Should return capture counts per day
```

### 5. Chat Import

Test with a sample ChatGPT export:
```bash
# Create minimal test export
echo '[{"id":"test-1","title":"Test Chat","mapping":{"msg1":{"message":{"author":{"role":"user"},"content":{"content_type":"text","parts":["Hello AI"]},"create_time":1706100000}}}}]' > test_export.json

# Import
curl -X POST http://localhost:8000/api/import/ \
  -F "file=@test_export.json" \
  -F "source=chatgpt"
# Should return {"imported": 1, "skipped": 0, "errors": 0, "source": "chatgpt"}

# Search for imported content
curl -X POST http://localhost:8000/api/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello AI", "sources": ["chatgpt"], "limit": 5}'
# Should return the imported conversation
```

## Troubleshooting

### Worker Not Processing

```bash
# Check worker status
docker compose logs jarvis-worker --tail=50

# Check Redis connection
docker compose exec redis redis-cli ping
# Should return PONG

# Check job queue
docker compose exec redis redis-cli LLEN arq:queue
# Shows pending jobs
```

### Search Returns No Results

```bash
# Check Qdrant collection
curl http://localhost:6333/collections/captures

# Check collection has points
curl http://localhost:6333/collections/captures/points/count
```

### OCR Not Working

```bash
# Check if models are downloaded
docker compose exec jarvis-worker ls -la /data/models/

# Check EasyOCR logs
docker compose logs jarvis-worker | grep -i easyocr
```

## Success Criteria

- [ ] All Docker services healthy
- [ ] Captures upload and are queued for processing
- [ ] Worker processes captures (OCR + embedding)
- [ ] Search returns relevant results
- [ ] Timeline shows capture history
- [ ] Chat imports are indexed and searchable
